"""Analisador DSP em tempo real de ritmo, fluxo espectral, BPM e atividade musical."""

from __future__ import annotations

import itertools
import math
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class FrameRitmo:
    """Resultado de análise rítmica para um passo do fluxo de áudio."""

    audio_level: float = 0.0
    bass_level: float = 0.0
    beat_detected: bool = False
    bpm: float | None = None
    beat_phase: float = 0.0
    music_active: bool = False
    music_confidence: float = 0.0
    rms: float = 0.0


class AnalisadorRitmo:
    """Detector multi-banda com Spectral Flux, tempograma por autocorrelação e PLL."""

    _SILENCE_RMS = 0.0018
    _MIN_BPM = 55.0
    _MAX_BPM = 185.0
    _PREF_BPM = 118.0
    _BEAT_HOLD_S = 0.048
    _REFRACTORY_S = 0.24

    def __init__(
        self,
        *,
        sample_rate: int = 48_000,
        hop_size: int = 512,
        window_size: int = 2048,
    ) -> None:
        """Inicializa buffers deslizantes, máscaras de bandas e estado do PLL."""
        self.sample_rate = max(8_000, int(sample_rate))
        self.hop_size = max(128, int(hop_size))
        self.window_size = max(self.hop_size * 2, int(window_size))
        self.hop_dt = self.hop_size / float(self.sample_rate)
        self.frame_rate = float(self.sample_rate) / self.hop_size
        self._init_bandas_espectrais()
        self._init_buffers_e_estado()

    def _init_bandas_espectrais(self) -> None:
        freqs = np.fft.rfftfreq(self.window_size, 1.0 / self.sample_rate)
        self._mask_sub = (freqs >= 35.0) & (freqs < 125.0)
        self._mask_punch = (freqs >= 125.0) & (freqs < 280.0)
        self._mask_bass_full = (freqs >= 35.0) & (freqs <= 240.0)
        self._mask_vocal = (freqs >= 300.0) & (freqs < 2500.0)
        self._mask_air = (freqs >= 2500.0) & (freqs <= min(7500.0, self.sample_rate * 0.45))

        self._sub_norm = math.sqrt(max(1, int(self._mask_sub.sum())))
        self._punch_norm = math.sqrt(max(1, int(self._mask_punch.sum())))
        self._air_norm = math.sqrt(max(1, int(self._mask_air.sum())))
        self._window = np.hanning(self.window_size).astype(np.float64)
        self._win_norm = float(np.sum(self._window)) * 0.5

    def _init_buffers_e_estado(self) -> None:
        self._ring = np.zeros(self.window_size, dtype=np.float64)
        self._pending = np.empty(0, dtype=np.float64)
        self._prev_log_mag: np.ndarray | None = None
        self._peak_rms = 0.05
        self._audio_level = 0.0
        self._bass_level = 0.0

        self._novelty_hist: deque[float] = deque(maxlen=max(24, round(0.85 * self.frame_rate)))
        self._onset_curve: deque[float] = deque(maxlen=max(128, round(6.5 * self.frame_rate)))
        hist_len = max(16, round(1.5 * self.frame_rate))
        self._bass_share_hist: deque[float] = deque(maxlen=hist_len)
        self._vocal_share_hist: deque[float] = deque(maxlen=hist_len)

        self._prev_nov = 0.0
        self._prev2_nov = 0.0
        self._prev_thresh = 0.0
        self._hop_count = 0
        self._tempo_check_interval = max(8, round(0.22 * self.frame_rate))
        self._init_tempo_e_gate()

    def _init_tempo_e_gate(self) -> None:
        self._ioi_times: deque[float] = deque(maxlen=10)
        self._last_onset_at = 0.0
        self._beat_hold_until = 0.0
        self._bpm: float | None = None
        self._candidate_bpm: float | None = None
        self._candidate_streak = 0
        self._pulse_clarity = 0.0
        self._phase = 0.0
        self._phase_offbeat_streak = 0
        self._music_active = False
        self._music_on_accum = 0.0
        self._music_off_accum = 0.0
        self._music_confidence = 0.0
        self._ultimo_frame = FrameRitmo()

    def _limpar_estado_silencio(self, rms: float, now: float) -> FrameRitmo:
        """Decai suavemente níveis e reseta fase após silêncio prolongado."""
        decay_lvl = math.exp(-self.hop_dt * 12.0)
        self._audio_level *= decay_lvl
        self._bass_level *= decay_lvl
        self._peak_rms = max(0.025, self._peak_rms * math.exp(-self.hop_dt / 4.0))
        self._prev_log_mag = None
        self._prev_nov = 0.0
        self._prev2_nov = 0.0
        self._novelty_hist.append(0.0)
        self._onset_curve.append(0.0)

        recent_onset = self._last_onset_at > 0.0 and (now - self._last_onset_at) <= 2.5
        if recent_onset and self._hop_count % self._tempo_check_interval == 0:
            self._estimar_tempograma()

        if self._last_onset_at and (now - self._last_onset_at) > 3.5:
            self._bpm = None
            self._candidate_bpm = None
            self._candidate_streak = 0
            self._pulse_clarity = 0.0
            self._ioi_times.clear()
            self._bass_share_hist.clear()
            self._vocal_share_hist.clear()

        self._atualizar_gate_musica(rms, now=now, smtc_playing=False)
        self._ultimo_frame = FrameRitmo(
            audio_level=self._audio_level,
            bass_level=self._bass_level,
            beat_detected=now < self._beat_hold_until,
            bpm=self._bpm,
            beat_phase=self._phase,
            music_active=self._music_active,
            music_confidence=self._music_confidence,
            rms=rms,
        )
        return self._ultimo_frame

    def _calcular_espectro_e_fluxo(
        self, mono_window: np.ndarray, rms: float
    ) -> tuple[float, float, float]:
        """Calcula fluxo espectral multi-banda em magnitude logarítmica."""
        agc_decay = math.exp(-self.hop_dt / 3.5)
        self._peak_rms = max(0.02, self._peak_rms * agc_decay, rms)
        norm_gain = 0.95 / self._peak_rms
        raw_audio_lvl = max(0.0, min(1.0, rms * norm_gain))

        spectrum = np.abs(np.fft.rfft(mono_window * self._window))
        power = spectrum * spectrum
        total_pow = max(1e-12, float(power.sum()))
        bass_share = float(power[self._mask_bass_full].sum()) / total_pow
        vocal_share = float(power[self._mask_vocal].sum()) / total_pow

        raw_bass_lvl = max(0.0, min(1.0, raw_audio_lvl * (bass_share**0.45)))
        smooth_lvl = 1.0 - math.exp(-self.hop_dt * 18.0)
        self._audio_level += (raw_audio_lvl - self._audio_level) * smooth_lvl
        self._bass_level += (raw_bass_lvl - self._bass_level) * smooth_lvl

        scale = max(1e-6, self._peak_rms * self._win_norm)
        log_mag = np.log1p(22.0 * (spectrum / scale))
        if self._prev_log_mag is None:
            self._prev_log_mag = log_mag
            return 0.0, bass_share, vocal_share

        diff = np.maximum(0.0, log_mag - self._prev_log_mag)
        self._prev_log_mag = log_mag
        flux_sub = float(diff[self._mask_sub].sum()) / self._sub_norm
        flux_punch = float(diff[self._mask_punch].sum()) / self._punch_norm
        flux_air = float(diff[self._mask_air].sum()) / self._air_norm
        novelty = 1.85 * flux_sub + 1.25 * flux_punch + 0.75 * flux_air
        return novelty, bass_share, vocal_share

    def _detectar_pico_onset(self, novelty: float, now: float, sensitivity: float) -> bool:
        """Executa peak-picking adaptativo sobre a curva de fluxo espectral."""
        self._novelty_hist.append(novelty)
        self._onset_curve.append(novelty)

        sens = max(0.0, min(1.0, float(sensitivity)))
        if len(self._novelty_hist) >= 6:
            hist_arr = np.fromiter(self._novelty_hist, dtype=np.float64)
            med = float(np.median(hist_arr))
            mad = float(np.median(np.abs(hist_arr - med)))
            alpha = 2.1 - 1.35 * sens
            min_floor = 0.06 + 0.08 * (1.0 - sens)
            thresh = med + alpha * max(mad * 1.4826, 0.14 * float(hist_arr.mean()), min_floor)
        else:
            thresh = 999.0

        onset_fired = False
        peak_val = self._prev_nov
        is_local_peak = peak_val > self._prev2_nov and peak_val >= novelty
        onset_time = now - self.hop_dt
        if (
            is_local_peak
            and peak_val >= self._prev_thresh
            and peak_val > 0.12
            and (onset_time - self._last_onset_at) >= self._REFRACTORY_S
        ):
            onset_fired = True
            self._registrar_onset(onset_time)

        self._prev2_nov = self._prev_nov
        self._prev_nov = novelty
        self._prev_thresh = thresh
        return onset_fired

    def _registrar_onset(self, onset_time: float) -> None:
        """Atualiza histórico rápido de IOI e alinha a fase do PLL no onset."""
        if self._last_onset_at > 0.0:
            interval = onset_time - self._last_onset_at
            if 0.30 <= interval <= 1.50:
                self._ioi_times.append(onset_time)
            elif interval > 2.4:
                self._ioi_times.clear()
                self._ioi_times.append(onset_time)
        else:
            self._ioi_times.append(onset_time)
        self._last_onset_at = onset_time
        self._beat_hold_until = max(self._beat_hold_until, onset_time + self._BEAT_HOLD_S)

        if self._bpm is None and len(self._ioi_times) >= 3:
            intervals = [
                b - a
                for a, b in itertools.pairwise(self._ioi_times)
                if 0.30 <= (b - a) <= 1.50
            ]
            if len(intervals) >= 2:
                med_ioi = float(np.median(intervals))
                self._bpm = max(self._MIN_BPM, min(self._MAX_BPM, 60.0 / med_ioi))

        err = ((0.0 - self._phase + 0.5) % 1.0) - 0.5
        if abs(err) <= 0.28:
            self._phase = (self._phase + 0.38 * err) % 1.0
            self._phase_offbeat_streak = 0
        else:
            self._phase_offbeat_streak += 1
            if self._phase_offbeat_streak >= 3:
                self._phase = 0.0
                self._phase_offbeat_streak = 0

    def _autocorrelacao_onset(self) -> np.ndarray | None:
        min_hops = max(64, round(2.2 * self.frame_rate))
        if len(self._onset_curve) < min_hops:
            return None
        curve = np.fromiter(self._onset_curve, dtype=np.float64)
        centered = np.maximum(0.0, curve - float(curve.mean()))
        energy0 = float(np.dot(centered, centered))
        if energy0 <= 1e-8:
            self._pulse_clarity = 0.0
            return None
        n = centered.size
        n_fft = 1 << (2 * n - 1).bit_length()
        spec = np.fft.rfft(centered, n=n_fft)
        return np.fft.irfft(spec * np.conj(spec), n=n_fft)[:n] / energy0

    def _melhor_lag_comb(
        self, ac: np.ndarray, lag_min: int, lag_max: int
    ) -> tuple[int, float, float]:
        best_score = -1.0
        best_lag = lag_min
        raw_peak = 0.0
        n = ac.size
        for lag in range(lag_min, lag_max + 1):
            base_ac = float(ac[lag])
            raw_peak = max(raw_peak, base_ac)
            bpm_cand = (self.frame_rate * 60.0) / lag
            comb = 0.68 * base_ac
            if lag * 2 < n:
                comb += 0.24 * float(ac[lag * 2])
            if lag // 2 >= 3:
                comb += 0.08 * float(ac[lag // 2])
            prior = math.exp(-0.5 * (math.log2(bpm_cand / self._PREF_BPM) / 0.62) ** 2)
            score = comb * prior
            if score > best_score:
                best_score = score
                best_lag = lag
        return best_lag, best_score, max(0.0, min(1.0, raw_peak))

    @staticmethod
    def _refinar_pico_parabolico(
        ac: np.ndarray, best_lag: int, lag_min: int, lag_max: int
    ) -> float:
        if not (lag_min < best_lag < lag_max):
            return float(best_lag)
        left, mid, right = float(ac[best_lag - 1]), float(ac[best_lag]), float(ac[best_lag + 1])
        denom = left - 2.0 * mid + right
        if denom >= -1e-9:
            return float(best_lag)
        delta = max(-0.5, min(0.5, 0.5 * (left - right) / denom))
        return float(best_lag) + delta

    def _estimar_tempograma(self) -> None:
        """Estima BPM e clareza rítmica via autocorrelação comb com prior perceptual."""
        ac = self._autocorrelacao_onset()
        if ac is None:
            return
        lag_min = max(4, round(self.frame_rate * 60.0 / self._MAX_BPM))
        lag_max = min(ac.size - 2, round(self.frame_rate * 60.0 / self._MIN_BPM))
        if lag_max <= lag_min:
            return
        best_lag, best_score, raw_peak = self._melhor_lag_comb(ac, lag_min, lag_max)
        self._pulse_clarity = raw_peak
        if self._pulse_clarity < 0.14 or best_score <= 0.0:
            return
        refined_lag = self._refinar_pico_parabolico(ac, best_lag, lag_min, lag_max)
        bpm_est = max(self._MIN_BPM, min(self._MAX_BPM, (self.frame_rate * 60.0) / refined_lag))
        self._atualizar_bpm_travado(bpm_est)

    def _atualizar_bpm_travado(self, bpm_est: float) -> None:
        """Aplica suavização e trava contra saltos espúrios de oitava."""
        if self._bpm is None:
            self._bpm = bpm_est
            self._candidate_bpm = None
            self._candidate_streak = 0
            return

        ratio = bpm_est / max(1e-3, self._bpm)
        if 0.88 <= ratio <= 1.12:
            self._bpm += (bpm_est - self._bpm) * 0.25
            self._candidate_bpm = None
            self._candidate_streak = 0
            return

        if (0.47 <= ratio <= 0.54 or 1.85 <= ratio <= 2.15) and self._pulse_clarity < 0.35:
            return

        if self._candidate_bpm is not None and abs(bpm_est - self._candidate_bpm) <= 6.0:
            self._candidate_streak += 1
        else:
            self._candidate_bpm = bpm_est
            self._candidate_streak = 1

        if self._candidate_streak >= 3:
            self._bpm = bpm_est
            self._candidate_bpm = None
            self._candidate_streak = 0

    def _medias_bandas_gate(
        self, bass_share: float | None, vocal_share: float | None
    ) -> tuple[float, float]:
        if bass_share is not None:
            self._bass_share_hist.append(bass_share)
        if vocal_share is not None:
            self._vocal_share_hist.append(vocal_share)
        avg_bass = (
            sum(self._bass_share_hist) / len(self._bass_share_hist)
            if self._bass_share_hist
            else 0.0
        )
        avg_vocal = (
            sum(self._vocal_share_hist) / len(self._vocal_share_hist)
            if self._vocal_share_hist
            else 0.0
        )
        return avg_bass, avg_vocal

    def _aplicar_histerese_gate(self, rhythmic: bool) -> None:
        if rhythmic:
            self._music_on_accum += self.hop_dt
            self._music_off_accum = 0.0
            if self._music_on_accum >= 0.45:
                self._music_active = True
            return
        self._music_on_accum = max(0.0, self._music_on_accum - self.hop_dt * 0.5)
        self._music_off_accum += self.hop_dt
        if self._music_off_accum >= 1.8:
            self._music_active = False

    def _atualizar_gate_musica(
        self,
        rms: float,
        *,
        now: float,
        smtc_playing: bool,
        bass_share: float | None = None,
        vocal_share: float | None = None,
    ) -> None:
        """Distingue música ativa de silêncio ou fala isolada com histerese."""
        avg_bass, avg_vocal = self._medias_bandas_gate(bass_share, vocal_share)
        if smtc_playing:
            self._music_active = True
            self._music_on_accum = 1.0
            self._music_off_accum = 0.0
            self._music_confidence = max(0.85, self._pulse_clarity)
            return

        recent_beat = self._last_onset_at > 0.0 and (now - self._last_onset_at) <= 1.35
        audible = (rms >= self._SILENCE_RMS * 1.1) or recent_beat
        speech_like = avg_vocal > 0.60 and avg_bass < 0.12 and not recent_beat
        if speech_like:
            self._bpm = None
            self._candidate_bpm = None
            self._candidate_streak = 0
        rhythmic = (
            audible
            and not speech_like
            and (
                self._pulse_clarity >= 0.17
                or (
                    recent_beat
                    and (self._bpm is not None or avg_bass >= 0.12 or len(self._ioi_times) >= 3)
                )
            )
        )
        conf_raw = (
            0.55 * min(1.0, self._pulse_clarity / 0.35)
            + 0.30 * min(1.0, avg_bass / 0.25)
            + (0.15 if audible and not speech_like else 0.0)
        )
        if speech_like:
            conf_raw *= 0.25
        self._music_confidence += (
            max(0.0, min(1.0, conf_raw)) - self._music_confidence
        ) * min(1.0, self.hop_dt * 6.0)
        self._aplicar_histerese_gate(rhythmic)

    def _avancar_um_hop(
        self,
        now: float,
        sensitivity: float,
        *,
        smtc_playing: bool,
    ) -> FrameRitmo:
        """Executa um passo DSP sobre a janela atual do anel."""
        self._hop_count += 1
        frame_slice = self._ring[-self.hop_size :]
        rms = float(math.sqrt(float(np.mean(np.square(frame_slice), dtype=np.float64))))
        bpm_pll = self._bpm if self._bpm is not None else 118.0
        self._phase = (self._phase + self.hop_dt * bpm_pll / 60.0) % 1.0

        if rms < self._SILENCE_RMS:
            return self._limpar_estado_silencio(rms, now)

        novelty, bass_share, vocal_share = self._calcular_espectro_e_fluxo(self._ring, rms)
        onset_fired = self._detectar_pico_onset(novelty, now, sensitivity)
        if self._hop_count % self._tempo_check_interval == 0:
            self._estimar_tempograma()

        self._atualizar_gate_musica(
            rms,
            now=now,
            smtc_playing=smtc_playing,
            bass_share=bass_share,
            vocal_share=vocal_share,
        )
        self._ultimo_frame = FrameRitmo(
            audio_level=self._audio_level,
            bass_level=self._bass_level,
            beat_detected=onset_fired or (now < self._beat_hold_until),
            bpm=self._bpm,
            beat_phase=self._phase,
            music_active=self._music_active,
            music_confidence=self._music_confidence,
            rms=rms,
        )
        return self._ultimo_frame

    def processar_bloco(
        self,
        samples: np.ndarray,
        *,
        now: float,
        sensitivity: float = 0.6,
        smtc_playing: bool = False,
    ) -> FrameRitmo:
        """Ingere bloco PCM mono/estéreo e devolve o último ``FrameRitmo``."""
        arr = np.asarray(samples, dtype=np.float64)
        if arr.size == 0:
            return self._ultimo_frame
        mono = arr.mean(axis=1) if arr.ndim > 1 else arr
        if mono.size == 0:
            return self._ultimo_frame

        joined = mono if self._pending.size == 0 else np.concatenate((self._pending, mono))
        total_hops = joined.size // self.hop_size
        if total_hops == 0:
            self._pending = joined
            return self._ultimo_frame

        self._pending = joined[total_hops * self.hop_size :]
        t_base = now - (total_hops - 1) * self.hop_dt
        for idx in range(total_hops):
            hop = joined[idx * self.hop_size : (idx + 1) * self.hop_size]
            self._ring = np.roll(self._ring, -self.hop_size)
            self._ring[-self.hop_size :] = hop
            self._ultimo_frame = self._avancar_um_hop(
                t_base + idx * self.hop_dt,
                sensitivity,
                smtc_playing=smtc_playing,
            )
        return self._ultimo_frame
