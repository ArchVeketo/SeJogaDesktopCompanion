"""Classificação pura de sessões SMTC e decisão híbrida música vs vídeo/fala.

Este módulo não importa WinRT, SoundCard, Panda3D, Qt ou Win32.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

CategoriaMidia = Literal[
    "music_app",
    "browser_music",
    "ambiguous",
    "video_or_speech",
    "none",
]

_DURACAO_MIN_MUSICA_S = 35.0
_DURACAO_MAX_MUSICA_S = 900.0
_DURACAO_ALBUM_MAX_S = 720.0

_APPS_MUSICA: tuple[str, ...] = (
    "spotify",
    "applemusic",
    "itunes",
    "tidal",
    "deezer",
    "amazonmusic",
    "foobar2000",
    "musicbee",
    "aimp",
    "winamp",
    "zunemusic",
    "microsoft.media.player",
    "soundcloud",
    "qobuz",
    "ytmusic",
    "youtubemusic",
    "cider",
    "plexamp",
)

_APPS_VIDEO_OU_CHAMADA: tuple[str, ...] = (
    "netflix",
    "primevideo",
    "disney",
    "twitch",
    "zunevideo",
    "discord",
    "teams",
    "zoom",
    "whatsapp",
    "telegram",
    "obs64",
    "obs",
    "skype",
)

_PLAYERS_GENERICOS: tuple[str, ...] = (
    "vlc",
    "mpv",
    "mpc-hc",
    "mpc-be",
    "potplayer",
    "wmplayer",
    "kodi",
)

_NAVEGADORES: tuple[str, ...] = (
    "chrome",
    "msedge",
    "firefox",
    "brave",
    "opera",
    "vivaldi",
    "arc",
    "zen",
    "waterfox",
)

_TERMOS_PODCAST_FALA: tuple[str, ...] = (
    "podcast",
    "audiobook",
    "entrevista",
    "spoken",
)

_RE_TERMOS_NEGATIVOS = re.compile(
    r"(?<!\w)("
    r"podcast|cortes|entrevista|review|tutorial|aula|react|gameplay|"
    r"vlog|not[ií]cias|news|trailer|ao\s+vivo|livestream|shorts|"
    r"unboxing|detonado|document[aá]rio|palestra|debate|epis[oó]dio|ep\."
    r")(?!\w)",
    re.IGNORECASE,
)

_PATROES_MUSICA_TITULO: tuple[str, ...] = (
    "official music video",
    "official audio",
    "lyric video",
    "visualizer",
    "feat.",
    "ft.",
    "remix",
    "prod.",
)

_SUFIXOS_ARTISTA_MUSICA: tuple[str, ...] = (
    " - topic",
    "vevo",
)

_RE_TRACO_ARTISTA_MUSICA = re.compile(r"\S+\s[-\u2013\u2014]\s+\S+")

_PONTOS_SELECAO: dict[CategoriaMidia, float] = {
    "music_app": 4.0,
    "browser_music": 3.0,
    "ambiguous": 1.5,
    "video_or_speech": 0.5,
    "none": 0.0,
}


@dataclass(frozen=True, slots=True)
class MetadadosSessao:
    """Metadados normalizados extraídos de uma sessão SMTC."""

    source_app_id: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    subtitle: str | None = None
    playback_type: str = "unknown"
    duration_seconds: float | None = None
    genres: tuple[str, ...] = ()
    track_number: int | None = None


@dataclass(frozen=True, slots=True)
class ResultadoClassificacaoMidia:
    """Resultado da classificação de uma sessão de mídia."""

    categoria: CategoriaMidia
    confianca_meta: float
    motivo: str


def _norm_app_id(app_id: str | None) -> str:
    return (app_id or "").strip().lower()


def _corresponde_app(app_norm: str, candidatos: tuple[str, ...]) -> bool:
    if not app_norm:
        return False
    base = app_norm.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    stem = base.split("!", 1)[0]
    return any(cand in app_norm or stem.startswith(cand) for cand in candidatos)


def _texto_combinado(meta: MetadadosSessao) -> str:
    partes = [
        meta.title or "",
        meta.artist or "",
        meta.album or "",
        meta.album_artist or "",
        meta.subtitle or "",
        " ".join(meta.genres),
    ]
    return " ".join(partes).strip()


def _tem_termo_podcast(texto: str) -> bool:
    baixo = texto.lower()
    return any(termo in baixo for termo in _TERMOS_PODCAST_FALA)


def _tem_pista_musical_forte(meta: MetadadosSessao) -> bool:
    titulo_baixo = (meta.title or "").strip().lower()
    artista_baixo = (meta.artist or "").strip().lower()
    album_limpo = (meta.album or "").strip()
    if any(artista_baixo.endswith(suf) for suf in _SUFIXOS_ARTISTA_MUSICA):
        return True
    if any(pad in titulo_baixo for pad in _PATROES_MUSICA_TITULO):
        return True
    if album_limpo and artista_baixo:
        dur = meta.duration_seconds
        if dur is None or _DURACAO_MIN_MUSICA_S <= dur <= _DURACAO_ALBUM_MAX_S:
            return True
    return bool(artista_baixo and titulo_baixo and _RE_TRACO_ARTISTA_MUSICA.search(titulo_baixo))


def _duracao_invalida_para_musica(dur: float | None) -> str | None:
    if dur is None:
        return None
    if dur <= 0.0:
        return "duracao_live_ou_nula"
    if dur < _DURACAO_MIN_MUSICA_S:
        return "duracao_curta"
    if dur > _DURACAO_MAX_MUSICA_S:
        return "duracao_longa"
    return None


def _classificar_navegador(
    meta: MetadadosSessao,
    texto: str,
    tipo: str,
) -> ResultadoClassificacaoMidia:
    if _RE_TERMOS_NEGATIVOS.search(texto):
        return ResultadoClassificacaoMidia("video_or_speech", 0.90, "palavra_chave_video_fala")
    motivo_dur = _duracao_invalida_para_musica(meta.duration_seconds)
    if motivo_dur is not None:
        return ResultadoClassificacaoMidia("video_or_speech", 0.85, motivo_dur)
    pista_forte = _tem_pista_musical_forte(meta)
    if tipo == "music":
        return ResultadoClassificacaoMidia("browser_music", 0.88, "browser_playback_type_music")
    if pista_forte:
        return ResultadoClassificacaoMidia("browser_music", 0.82, "browser_pista_musical_forte")
    if tipo == "video":
        return ResultadoClassificacaoMidia("video_or_speech", 0.78, "browser_video_sem_pista_musical")
    return ResultadoClassificacaoMidia("ambiguous", 0.45, "browser_ambiguo")


def _classificar_app_musica_dedicado(
    meta: MetadadosSessao,
    texto: str,
    tipo: str,
) -> ResultadoClassificacaoMidia:
    if tipo == "video":
        return ResultadoClassificacaoMidia("video_or_speech", 0.85, "app_musica_em_video")
    if meta.duration_seconds is not None and meta.duration_seconds > _DURACAO_MAX_MUSICA_S:
        return ResultadoClassificacaoMidia("video_or_speech", 0.85, "app_musica_podcast_longo")
    if _tem_termo_podcast(texto):
        return ResultadoClassificacaoMidia("video_or_speech", 0.85, "app_musica_podcast_termo")
    return ResultadoClassificacaoMidia("music_app", 0.95, "app_musica_dedicado")


def _classificar_player_generico(
    meta: MetadadosSessao,
    texto: str,
    tipo: str,
) -> ResultadoClassificacaoMidia:
    dur = meta.duration_seconds
    dur_ok = dur is not None and _DURACAO_MIN_MUSICA_S <= dur <= _DURACAO_ALBUM_MAX_S
    if tipo == "music" and dur_ok:
        return ResultadoClassificacaoMidia("music_app", 0.88, "player_generico_musica")
    if (
        meta.album
        and meta.artist
        and tipo != "video"
        and not _RE_TERMOS_NEGATIVOS.search(texto)
        and (dur is None or dur_ok)
    ):
        return ResultadoClassificacaoMidia("music_app", 0.80, "player_generico_album")
    return ResultadoClassificacaoMidia("video_or_speech", 0.85, "player_generico_video")


def classificar_sessao_midia(meta: MetadadosSessao) -> ResultadoClassificacaoMidia:
    """Classifica uma sessão SMTC como música, navegador musical, vídeo/fala ou ambígua."""
    app_norm = _norm_app_id(meta.source_app_id)
    if not app_norm and not (meta.title or meta.artist or meta.album):
        return ResultadoClassificacaoMidia("none", 0.0, "sem_sessao")

    tipo = (meta.playback_type or "unknown").strip().lower()
    texto = _texto_combinado(meta)

    if _corresponde_app(app_norm, _APPS_VIDEO_OU_CHAMADA):
        return ResultadoClassificacaoMidia("video_or_speech", 0.95, "app_video_ou_chamada")
    if _corresponde_app(app_norm, _APPS_MUSICA):
        return _classificar_app_musica_dedicado(meta, texto, tipo)
    if _corresponde_app(app_norm, _PLAYERS_GENERICOS):
        return _classificar_player_generico(meta, texto, tipo)
    if _corresponde_app(app_norm, _NAVEGADORES):
        return _classificar_navegador(meta, texto, tipo)
    if _RE_TERMOS_NEGATIVOS.search(texto) or tipo == "video":
        return ResultadoClassificacaoMidia("video_or_speech", 0.75, "desconhecido_video_ou_fala")
    if tipo == "music":
        return ResultadoClassificacaoMidia("music_app", 0.80, "desconhecido_playback_music")
    return ResultadoClassificacaoMidia("ambiguous", 0.40, "app_desconhecido")


def pontuar_sessao_para_selecao(meta: MetadadosSessao) -> float:
    """Pontua sessão ativa para priorizar apps de música sobre navegadores e vídeos."""
    res = classificar_sessao_midia(meta)
    return _PONTOS_SELECAO[res.categoria] + res.confianca_meta * 0.1


def _decidir_media_session(
    categoria: CategoriaMidia,
    smtc_playing: bool,
    ignore_video_sessions: bool,
) -> tuple[bool, float]:
    if not smtc_playing or categoria == "none":
        return False, 0.0
    if categoria == "music_app":
        return True, 0.90
    if categoria == "browser_music":
        return True, 0.80
    if categoria == "video_or_speech":
        return (True, 0.70) if not ignore_video_sessions else (False, 0.0)
    return False, 0.35


def _decidir_modo_auto(
    categoria: CategoriaMidia,
    smtc_playing: bool,
    *,
    audio_active: bool,
    audio_level: float,
    conf: float,
    speech_like: bool,
    has_loopback_data: bool,
    dsp_estrito: bool,
) -> tuple[bool, float]:
    if smtc_playing and categoria == "music_app":
        if not has_loopback_data:
            return True, 0.88
        if audio_active or audio_level > 0.015:
            return True, max(0.75, conf)
        return False, conf * 0.4

    if smtc_playing and categoria == "browser_music":
        if not has_loopback_data:
            return True, 0.78
        if audio_active and not speech_like:
            return True, max(0.65, conf)
        if audio_level > 0.025 and not speech_like and conf >= 0.35:
            return True, max(0.55, conf)
        return False, min(conf, 0.30)

    return (True, conf) if dsp_estrito else (False, min(conf, 0.35))


def decidir_musica_ativa(
    source_mode: str,
    categoria: CategoriaMidia,
    smtc_playing: bool,
    *,
    audio_active: bool,
    audio_level: float,
    music_confidence: float,
    speech_like: bool = False,
    ignore_video_sessions: bool = True,
    has_loopback_data: bool = True,
) -> tuple[bool, float]:
    """Combina classificação SMTC e confiança DSP para decidir se há música real."""
    conf = max(0.0, min(1.0, float(music_confidence)))
    dsp_estrito = bool(audio_active and not speech_like and conf >= 0.45)

    if source_mode == "off":
        return False, 0.0
    if smtc_playing and categoria == "video_or_speech" and ignore_video_sessions:
        return False, 0.0
    if source_mode == "loopback":
        return (True, max(conf, 0.50)) if dsp_estrito else (False, conf)
    if source_mode == "media_session":
        return _decidir_media_session(categoria, smtc_playing, ignore_video_sessions)
    return _decidir_modo_auto(
        categoria,
        smtc_playing,
        audio_active=audio_active,
        audio_level=audio_level,
        conf=conf,
        speech_like=speech_like,
        has_loopback_data=has_loopback_data,
        dsp_estrito=dsp_estrito,
    )
