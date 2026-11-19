"""Testes do detector rítmico DSP e do MusicListener multi-sessão/loopback."""

from __future__ import annotations

import builtins
import time
from types import SimpleNamespace

import numpy as np
import pytest

from sejoga.configuracao import MusicSettings, Settings
from sejoga.musica.analisador_ritmo import AnalisadorRitmo
from sejoga.musica.escuta_musica import MusicListener, MusicSnapshot


def _simular_fluxo(
    signal: np.ndarray,
    *,
    sample_rate: int = 48_000,
    hop_size: int = 512,
    sensitivity: float = 0.6,
    smtc_playing: bool = False,
):
    analisador = AnalisadorRitmo(
        sample_rate=sample_rate,
        hop_size=hop_size,
        window_size=2048,
    )
    frames = []
    t = 100.0
    hop_dt = hop_size / sample_rate
    for idx in range(0, len(signal) - hop_size + 1, hop_size):
        t += hop_dt
        frames.append(
            (
                t,
                analisador.processar_bloco(
                    signal[idx : idx + hop_size],
                    now=t,
                    sensitivity=sensitivity,
                    smtc_playing=smtc_playing,
                ),
            )
        )
    return frames


@pytest.mark.parametrize("bpm", [90.0, 128.0, 160.0])
def test_analisador_ritmo_trava_bpm_e_fase_em_click_track(bpm: float) -> None:
    sr = 48_000
    n = int(sr * 8.0)
    sig = np.zeros(n, dtype=np.float64)
    period = int(sr * 60.0 / bpm)
    env = np.exp(-np.arange(1600) / 320.0)
    rng = np.random.default_rng(1)
    click = env * np.sin(2 * np.pi * 80.0 * np.arange(1600) / sr) + 0.5 * env * rng.normal(
        0, 0.25, 1600
    )
    beat_samples = list(range(0, n - 1600, period))
    for k in beat_samples:
        sig[k : k + 1600] += 0.55 * click

    frames = _simular_fluxo(sig, sample_rate=sr)
    cauda = frames[-120:]
    bpms = [frame.bpm for _, frame in cauda if frame.bpm is not None]
    assert bpms
    med_bpm = float(np.median(bpms))
    assert abs(med_bpm - bpm) <= 2.5
    assert frames[-1][1].music_active is True

    # Verifica que o PLL mantém fase perto de 0.0 (wrap em +/- 0.25) perto do fim da faixa.
    erros_fase = []
    for sample_idx in beat_samples[-4:]:
        t_batida = 100.0 + sample_idx / sr
        _, quadro = min(frames, key=lambda item: abs(item[0] - t_batida))
        err = abs(((quadro.beat_phase + 0.5) % 1.0) - 0.5)
        erros_fase.append(err)
    assert float(np.median(erros_fase)) < 0.20


def test_analisador_detecta_edm_comprimido_e_baixo_volume() -> None:
    sr = 48_000
    n = int(sr * 8.0)
    tt = np.arange(n) / sr
    pad = 0.42 * np.sin(2 * np.pi * 220 * tt) + 0.22 * np.sin(2 * np.pi * 440 * tt)
    kick_len = 2400
    kt = np.arange(kick_len) / sr
    kick = 0.20 * np.exp(-kt * 22.0) * np.sin(2 * np.pi * (95.0 - 450.0 * kt) * kt)
    edm = pad.copy()
    for k in range(0, n - kick_len, int(sr * 60.0 / 128.0)):
        edm[k : k + kick_len] += kick
        edm[k : k + kick_len] -= 0.08 * np.exp(-kt * 18.0) * pad[k : k + kick_len]

    frames_alto = _simular_fluxo(edm, sample_rate=sr)
    bpms_alto = [f.bpm for _, f in frames_alto[-120:] if f.bpm is not None]
    assert bpms_alto and abs(float(np.median(bpms_alto)) - 128.0) <= 2.5
    assert frames_alto[-1][1].music_active is True
    assert frames_alto[-1][1].bass_level > 0.15

    # Mesmo muito baixo (-26 dB), o AGC mantém detecção viva.
    frames_baixo = _simular_fluxo(edm * 0.05, sample_rate=sr)
    bpms_baixo = [f.bpm for _, f in frames_baixo[-120:] if f.bpm is not None]
    assert bpms_baixo and abs(float(np.median(bpms_baixo)) - 128.0) <= 2.5
    assert frames_baixo[-1][1].music_active is True
    assert frames_baixo[-1][1].audio_level > 0.35


def test_analisador_suporta_breakdown_e_troca_de_bpm() -> None:
    sr = 48_000
    kt = np.arange(2000) / sr
    kick = 0.45 * np.exp(-kt * 20.0) * np.sin(2 * np.pi * 65.0 * kt)

    def _trecho(bpm: float, secs: float) -> np.ndarray:
        ns = int(sr * secs)
        s = 0.08 * np.sin(2 * np.pi * 220 * (np.arange(ns) / sr))
        for k in range(0, ns - 2000, int(sr * 60.0 / bpm)):
            s[k : k + 2000] += kick
        return s

    brk = 0.08 * np.sin(2 * np.pi * 220 * (np.arange(int(sr * 1.4)) / sr))
    full = np.concatenate([_trecho(120.0, 5.0), brk, _trecho(140.0, 7.0)])
    frames = _simular_fluxo(full, sample_rate=sr)

    seg1 = [f.bpm for _, f in frames[350:440] if f.bpm is not None]
    seg2 = [f.bpm for _, f in frames[-100:] if f.bpm is not None]
    assert seg1 and abs(float(np.median(seg1)) - 120.0) <= 3.0
    assert frames[540][1].music_active is True
    assert seg2 and abs(float(np.median(seg2)) - 140.0) <= 3.5


def test_analisador_ignora_fala_isolada_e_silencio_sem_smtc() -> None:
    sr = 48_000
    n = int(sr * 8.0)
    rng = np.random.default_rng(7)
    speech = np.zeros(n, dtype=np.float64)
    pos = 0
    while pos < n - 6000:
        slen = int(rng.uniform(0.08, 0.24) * sr)
        gap = int(rng.uniform(0.05, 0.35) * sr)
        ts = np.arange(min(slen, n - pos)) / sr
        speech[pos : pos + len(ts)] = (
            0.25 * np.sin(2 * np.pi * rng.uniform(500, 1400) * ts) * np.hanning(len(ts))
        )
        pos += slen + gap

    frames_fala = _simular_fluxo(speech, sample_rate=sr, smtc_playing=False)
    assert all(not frame.music_active for _, frame in frames_fala[200:])

    # Se SMTC afirmar explicitamente que há mídia tocando, força music_active.
    frames_smtc = _simular_fluxo(speech * 0.2, sample_rate=sr, smtc_playing=True)
    assert frames_smtc[-1][1].music_active is True

    frames_silencio = _simular_fluxo(np.zeros(n, dtype=np.float64), sample_rate=sr)
    assert frames_silencio[-1][1].music_active is False
    assert frames_silencio[-1][1].audio_level < 1e-3
    assert frames_silencio[-1][1].bpm is None


def test_music_listener_timestamp_monotonico_e_preferencia_de_sessao() -> None:
    paused = SimpleNamespace(get_playback_info=lambda: SimpleNamespace(playback_status=4))
    playing = SimpleNamespace(get_playback_info=lambda: SimpleNamespace(playback_status=3))
    manager = SimpleNamespace(
        get_current_session=lambda: paused,
        get_sessions=lambda: [paused, playing],
    )
    assert MusicListener._escolher_sessao(manager, 3) is playing

    listener = MusicListener(MusicSettings(source="auto"))
    listener._publish(title="Musica", is_playing=True)
    snap1 = listener.snapshot
    assert isinstance(snap1, MusicSnapshot)
    assert abs(snap1.updated_at - time.monotonic()) < 2.0
    assert snap1.audio_updated_at == 0.0

    listener._publish(stamp_audio=True, audio_level=0.5, audio_active=True)
    snap2 = listener.snapshot
    assert snap2.audio_updated_at >= snap1.updated_at
    assert snap2.audio_active is True


def test_music_listener_auto_inicia_workers_e_degrada_sem_soundcard(monkeypatch) -> None:
    orig_import = builtins.__import__

    def _sem_soundcard(name, *args, **kwargs):
        if name == "soundcard":
            raise ImportError("sem soundcard")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _sem_soundcard)
    listener_auto = MusicListener(MusicSettings(source="auto"))
    listener_auto._loopback_worker(optional=True)
    assert listener_auto.snapshot.audio_error is None

    listener_lb = MusicListener(MusicSettings(source="loopback"))
    listener_lb._loopback_worker(optional=False)
    assert listener_lb.snapshot.audio_error is not None

    launched: list[str] = []
    monkeypatch.setattr(
        listener_auto,
        "_start_worker",
        lambda _target, name: launched.append(name),
    )
    listener_auto.start()
    assert launched == ["music-media-session", "music-wasapi-loopback"]


@pytest.mark.parametrize("legacy_source", ["auto", "media_session", "loopback", "off"])
def test_configuracao_aceita_todas_as_fontes_de_musica(legacy_source: str) -> None:
    s = Settings.model_validate({"music": {"source": legacy_source}})
    assert s.music.source == legacy_source
