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

    # Mesmo com SMTC sinalizando playing, o DSP puro não aceita fala isolada sem ritmo.
    frames_smtc = _simular_fluxo(speech * 0.2, sample_rate=sr, smtc_playing=True)
    assert frames_smtc[-1][1].music_active is False

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


def test_classificador_midia_separa_musica_de_videos_e_podcasts() -> None:
    from sejoga.musica.classificador_midia import (
        MetadadosSessao,
        classificar_sessao_midia,
        pontuar_sessao_para_selecao,
    )

    spotify_musica = MetadadosSessao(
        source_app_id="Spotify.exe",
        title="Around the World",
        artist="Daft Punk",
        album="Homework",
        playback_type="music",
        duration_seconds=240.0,
    )
    spotify_podcast = MetadadosSessao(
        source_app_id="Spotify.exe",
        title="Episódio 42 - Conversa Tech",
        artist="Flow Podcast",
        album="Flow Podcast",
        playback_type="music",
        duration_seconds=3600.0,
    )
    yt_clipe = MetadadosSessao(
        source_app_id="chrome.exe",
        title="Harder, Better, Faster, Stronger (Official Audio)",
        artist="Daft Punk - Topic",
        album="Discovery",
        playback_type="video",
        duration_seconds=224.0,
    )
    yt_vlog = MetadadosSessao(
        source_app_id="chrome.exe",
        title="Review completo do novo notebook - Unboxing",
        artist="Canal Tech",
        playback_type="video",
        duration_seconds=1120.0,
    )
    yt_shorts = MetadadosSessao(
        source_app_id="msedge.exe",
        title="Dica rápida #shorts",
        artist="Criador",
        playback_type="video",
        duration_seconds=22.0,
    )
    twitch = MetadadosSessao(
        source_app_id="Twitch.exe",
        title="Ao vivo jogando",
        artist="Streamer",
        playback_type="video",
        duration_seconds=0.0,
    )
    vlc_filme = MetadadosSessao(
        source_app_id="vlc.exe",
        title="Filme.2025.1080p.mkv",
        playback_type="video",
        duration_seconds=5400.0,
    )

    assert classificar_sessao_midia(spotify_musica).categoria == "music_app"
    assert classificar_sessao_midia(spotify_podcast).categoria == "video_or_speech"
    assert classificar_sessao_midia(yt_clipe).categoria == "browser_music"
    assert classificar_sessao_midia(yt_vlog).categoria == "video_or_speech"
    assert classificar_sessao_midia(yt_shorts).categoria == "video_or_speech"
    assert classificar_sessao_midia(twitch).categoria == "video_or_speech"
    assert classificar_sessao_midia(vlc_filme).categoria == "video_or_speech"

    assert pontuar_sessao_para_selecao(spotify_musica) > pontuar_sessao_para_selecao(yt_clipe)
    assert pontuar_sessao_para_selecao(yt_clipe) > pontuar_sessao_para_selecao(yt_vlog)


def test_escolher_sessao_prioriza_spotify_sobre_navegador_em_video() -> None:
    from datetime import timedelta

    chrome_vid = SimpleNamespace(
        source_app_user_model_id="chrome.exe",
        get_playback_info=lambda: SimpleNamespace(playback_status=3, playback_type=2),
        get_timeline_properties=lambda: SimpleNamespace(
            start_time=timedelta(0), end_time=timedelta(minutes=25)
        ),
    )
    spotify = SimpleNamespace(
        source_app_user_model_id="Spotify.exe",
        get_playback_info=lambda: SimpleNamespace(playback_status=3, playback_type=1),
        get_timeline_properties=lambda: SimpleNamespace(
            start_time=timedelta(0), end_time=timedelta(minutes=3, seconds=20)
        ),
    )
    manager = SimpleNamespace(
        get_current_session=lambda: chrome_vid,
        get_sessions=lambda: [chrome_vid, spotify],
    )
    assert MusicListener._escolher_sessao(manager, 3) is spotify


def test_analisador_rejeita_fala_masculina_grave_e_fala_com_bgm_baixa() -> None:
    sr = 48_000
    n = int(sr * 8.0)
    tt = np.arange(n) / sr
    rng = np.random.default_rng(19)

    # 1) Voz masculina grave (135 Hz fundamental + formantes 650/1200 Hz + sibilantes + pausas)
    fala_grave = np.zeros(n, dtype=np.float64)
    pos = 0
    while pos < n - int(0.45 * sr):
        dur_sil = int(rng.uniform(0.14, 0.28) * sr)
        pausa = int(rng.uniform(0.12, 0.36) * sr)
        seg_t = np.arange(min(dur_sil, n - pos)) / sr
        env = np.hanning(len(seg_t))
        pulso = (
            0.22 * np.sin(2 * np.pi * 135.0 * seg_t)
            + 0.30 * np.sin(2 * np.pi * 680.0 * seg_t)
            + 0.16 * np.sin(2 * np.pi * 1350.0 * seg_t)
            + 0.08 * rng.normal(0.0, 0.4, len(seg_t))
        ) * env
        fala_grave[pos : pos + len(seg_t)] = pulso
        pos += dur_sil + pausa

    frames_fala = _simular_fluxo(fala_grave, sample_rate=sr)
    assert all(not f.music_active for _, f in frames_fala[150:])

    # 2) Fala em primeiro plano com música de fundo fraca (-16 dB)
    bgm = 0.03 * np.sin(2 * np.pi * 180.0 * tt) + 0.02 * np.sin(2 * np.pi * 360.0 * tt)
    misto = fala_grave + bgm
    frames_bgm = _simular_fluxo(misto, sample_rate=sr)
    assert all(not f.music_active for _, f in frames_bgm[180:])


def test_fusao_smtc_dsp_e_debounce_de_entrada_no_controlador() -> None:
    from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
    from sejoga.musica.classificador_midia import decidir_musica_ativa
    from sejoga.nucleo.esqueleto import Rig
    from sejoga.nucleo.modelo import load_model
    from sejoga.nucleo.recursos import resolve_model

    # Vídeo no navegador nunca dispara música mesmo com áudio alto
    tocar_video, conf_video = decidir_musica_ativa(
        "auto",
        "video_or_speech",
        True,
        audio_active=True,
        audio_level=0.8,
        music_confidence=0.9,
        ignore_video_sessions=True,
    )
    assert (tocar_video, conf_video) == (False, 0.0)

    # Spotify tocando música audível aprova mesmo com trecho calmo
    tocar_spot, conf_spot = decidir_musica_ativa(
        "auto",
        "music_app",
        True,
        audio_active=False,
        audio_level=0.25,
        music_confidence=0.35,
    )
    assert tocar_spot is True and conf_spot >= 0.75

    # Debounce de 1.0s no controlador evita disparo em pulso rápido (< 1s)
    ctrl = AnimationController(Rig.from_model(load_model(resolve_model())))
    ctrl.agencia._gerar_desejo_espontaneo = lambda: None
    ctrl._cooldowns["cena_contextual"] = 999.0
    for _ in range(5):
        ctrl.update(
            0.1,
            music_playing=True,
            music_entry_debounce_s=1.0,
            music_intensity=0.7,
            dance_chance=1.0,
        )
    assert ctrl.state != AnimationState.DANCE

    for _ in range(7):
        ctrl.update(
            0.1,
            music_playing=True,
            music_entry_debounce_s=1.0,
            music_intensity=0.7,
            dance_chance=1.0,
        )
    assert ctrl.state == AnimationState.DANCE
