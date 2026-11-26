"""Leitura não bloqueante de metadados SMTC multi-sessão e análise rítmica WASAPI.

As APIs WinRT e SoundCard rodam em workers próprios. Áudio capturado é
processado em memória por fluxo espectral multi-banda e descartado; nenhum
buffer é salvo em disco.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from sejoga.configuracao import MusicSettings
from sejoga.musica.analisador_ritmo import AnalisadorRitmo
from sejoga.musica.classificador_midia import (
    MetadadosSessao,
    classificar_sessao_midia,
    decidir_musica_ativa,
    pontuar_sessao_para_selecao,
)

logger = logging.getLogger(__name__)


def _cor_segura_chroma_unit(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Afasta a cor extraída da zona do color key magenta (#FF00FF)."""
    if r > 0.68 and b > 0.68 and g < 0.28:
        g = 0.30
    return (max(0.0, min(1.0, r)), max(0.0, min(1.0, g)), max(0.0, min(1.0, b)))


def _ler_pixels_album(image_bytes: bytes) -> list[tuple[int, int, int]]:
    if not image_bytes:
        return []
    try:
        from PIL import Image
    except ImportError:
        return []
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            thumb = img.convert("RGB").resize((24, 24))
            return (
                list(thumb.get_flattened_data())
                if hasattr(thumb, "get_flattened_data")
                else list(thumb.getdata())
            )
    except Exception:
        return []


def _acumular_buckets_album(
    pixels: list[tuple[int, int, int]],
) -> list[list[float]]:
    buckets: dict[tuple[int, int, int], list[float]] = {}
    for r8, g8, b8 in pixels:
        r, g, b = r8 / 255.0, g8 / 255.0, b8 / 255.0
        sat = max(r, g, b) - min(r, g, b)
        lum = (r + g + b) / 3.0
        peso = (sat * 1.8 + 0.05) * max(0.15, 1.0 - abs(lum - 0.54) * 1.05)
        chave = (r8 // 32, g8 // 32, b8 // 32)
        acc = buckets.get(chave)
        if acc is None:
            buckets[chave] = [peso, r * peso, g * peso, b * peso]
        else:
            acc[0] += peso
            acc[1] += r * peso
            acc[2] += g * peso
            acc[3] += b * peso
    return sorted(buckets.values(), key=lambda v: v[0], reverse=True)


def extrair_paleta_album(
    image_bytes: bytes,
) -> tuple[tuple[float, float, float], ...]:
    """Extrai até 2 cores de sotaque saturadas (RGB 0..1) dos bytes da capa."""
    pixels = _ler_pixels_album(image_bytes)
    if not pixels:
        return ()
    paleta: list[tuple[float, float, float]] = []
    for total, sr, sg, sb in _acumular_buckets_album(pixels):
        if total <= 1e-6:
            continue
        cor = _cor_segura_chroma_unit(sr / total, sg / total, sb / total)
        if not paleta:
            paleta.append(cor)
            continue
        p0 = paleta[0]
        dist = ((cor[0] - p0[0]) ** 2 + (cor[1] - p0[1]) ** 2 + (cor[2] - p0[2]) ** 2) ** 0.5
        if dist >= 0.30:
            paleta.append(cor)
            break
    return tuple(paleta)


async def _ler_thumbnail_bytes_async(thumbnail_ref) -> bytes:
    """Lê bytes brutos do IRandomAccessStreamReference da SMTC de forma segura."""
    if thumbnail_ref is None:
        return b""
    try:
        stream = await thumbnail_ref.open_read_async()
        if stream is None:
            return b""
        try:
            size = int(getattr(stream, "size", 0) or 0)
            if size <= 0 or size > 4 * 1024 * 1024:
                return b""
            from winrt.windows.storage.streams import Buffer, InputStreamOptions

            buf = Buffer(size)
            result = await stream.read_async(buf, size, InputStreamOptions.NONE)
            return bytes(result) if result is not None else b""
        finally:
            with contextlib.suppress(Exception):
                stream.close()
    except Exception:
        return b""


@dataclass(frozen=True, slots=True)
class MusicSnapshot:
    """Snapshot imutável, seguro para leitura pelo loop gráfico."""

    source_app_id: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    is_playing: bool = False
    playback_status: str = "unknown"
    media_type: str = "unknown"
    media_category: str = "none"
    duration_seconds: float | None = None
    is_music_playing: bool = False
    thumbnail_available: bool = False
    album_colors: tuple[tuple[float, float, float], ...] = ()
    audio_level: float = 0.0
    bass_level: float = 0.0
    beat_detected: bool = False
    bpm: float | None = None
    beat_phase: float = 0.0
    media_error: str | None = None
    audio_error: str | None = None
    updated_at: float = 0.0
    audio_active: bool = False
    music_confidence: float = 0.0
    audio_updated_at: float = 0.0
    capture_backend: str | None = None


class MusicListener:
    """Monitora sessões de mídia do Windows (SMTC) e áudio loopback WASAPI."""

    _SAMPLE_RATES = (48_000, 44_100, 32_000)
    _HOP_SIZE = 512
    _WINDOW_SIZE = 2048

    def __init__(
        self,
        settings: MusicSettings,
        *,
        poll_interval: float = 1.0,
        on_update: Callable[[MusicSnapshot], None] | None = None,
    ) -> None:
        """Guarda as configurações; a escuta começa em ``start``."""
        self.settings = settings
        self.poll_interval = max(0.25, poll_interval)
        self.on_update = on_update
        self._snapshot = MusicSnapshot()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._smtc_wake: tuple[asyncio.AbstractEventLoop, asyncio.Event] | None = None
        self._last_dsp_speech_like: bool = False
        self._album_palette_cache: dict[
            tuple[str | None, str | None], tuple[tuple[float, float, float], ...]
        ] = {}

    @property
    def snapshot(self) -> MusicSnapshot:
        """Devolve o último estado da música."""
        with self._lock:
            return self._snapshot

    def start(self) -> None:
        """Inicia a escuta em segundo plano conforme ``settings.source``."""
        if not self.settings.enabled or self.settings.source == "off" or self._threads:
            return

        self._stop.clear()
        source = self.settings.source
        if source in ("auto", "media_session"):
            self._start_worker(self._media_worker, "music-media-session")
        if source in ("auto", "loopback"):
            optional = source == "auto"
            self._start_worker(
                lambda: self._loopback_worker(optional=optional),
                "music-wasapi-loopback",
            )

    def _start_worker(self, target: Callable[[], None], name: str) -> None:
        thread = threading.Thread(target=target, name=name, daemon=True)
        self._threads.append(thread)
        thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Para a escuta e acorda imediatamente os workers para encerrar."""
        self._stop.set()
        wake = self._smtc_wake
        if wake is not None:
            loop, event = wake
            with contextlib.suppress(Exception):
                loop.call_soon_threadsafe(event.set)
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads.clear()

    def _publish(self, *, stamp_audio: bool = False, **changes: object) -> None:
        now = time.monotonic()
        if stamp_audio:
            changes["audio_updated_at"] = now
        with self._lock:
            # mypy nao verifica kwargs via **dict[str, object] contra os campos
            # tipados de MusicSnapshot; os chamadores passam os tipos corretos.
            self._snapshot = replace(self._snapshot, updated_at=now, **changes)  # type: ignore[arg-type]
            snapshot = self._snapshot
        if self.on_update:
            with contextlib.suppress(Exception):
                self.on_update(snapshot)

    def _media_worker(self) -> None:
        apartment_initialized = False
        try:
            from winrt.runtime import MTA, init_apartment, uninit_apartment

            init_apartment(MTA)  # type: ignore[arg-type]  # stub do winrt tipa MTA como int, mas a API aceita
            apartment_initialized = True
            asyncio.run(self._poll_media_sessions())
        except Exception as exc:
            self._publish(media_error=f"Media session indisponível: {exc}")
            logger.warning("Sessão de mídia indisponível: %s", exc)
        finally:
            self._smtc_wake = None
            if apartment_initialized:
                with contextlib.suppress(Exception):
                    uninit_apartment()

    _SESSION_EVENT_PAIRS = (
        ("add_playback_info_changed", "remove_playback_info_changed"),
        ("add_media_properties_changed", "remove_media_properties_changed"),
    )
    _MANAGER_EVENT_PAIRS = (
        ("add_current_session_changed", "remove_current_session_changed"),
        ("add_sessions_changed", "remove_sessions_changed"),
    )

    @staticmethod
    def _sessao_esta_tocando(session, playing_status) -> bool:
        if session is None:
            return False
        with contextlib.suppress(Exception):
            return session.get_playback_info().playback_status == playing_status
        return False

    @staticmethod
    def _extrair_media_type(playback, properties=None) -> str:
        raw = getattr(playback, "playback_type", None)
        if raw is None and properties is not None:
            raw = getattr(properties, "playback_type", None)
        if raw is None:
            return "unknown"
        if isinstance(raw, int):
            return {1: "music", 2: "video", 3: "image"}.get(raw, "unknown")
        nome = str(raw).rsplit(".", 1)[-1].lower()
        return nome if nome in ("music", "video", "image", "unknown") else "unknown"

    @staticmethod
    def _extrair_duracao_sessao(session) -> float | None:
        get_tl = getattr(session, "get_timeline_properties", None)
        if not callable(get_tl):
            return None
        with contextlib.suppress(Exception):
            tl = get_tl()
            if tl is None:
                return None
            start = getattr(tl, "start_time", None)
            end = getattr(tl, "end_time", None)
            if start is None or end is None:
                return None
            delta = end - start
            sec = delta.total_seconds() if hasattr(delta, "total_seconds") else float(delta)
            return float(sec) if sec >= 0.0 else None
        return None

    @classmethod
    def _metadados_sincronos_sessao(cls, session) -> MetadadosSessao:
        source_app_id = getattr(session, "source_app_user_model_id", None)
        playback_type = "unknown"
        with contextlib.suppress(Exception):
            playback = session.get_playback_info()
            if playback is not None:
                playback_type = cls._extrair_media_type(playback)
        return MetadadosSessao(
            source_app_id=source_app_id,
            playback_type=playback_type,
            duration_seconds=cls._extrair_duracao_sessao(session),
        )

    @classmethod
    def _escolher_sessao(cls, manager, playing_status):
        """Seleciona a sessão SMTC ativa priorizando apps/abas musicais."""
        current = manager.get_current_session()
        sessoes_tocando = []
        with contextlib.suppress(Exception):
            for candidate in manager.get_sessions() or ():
                if cls._sessao_esta_tocando(candidate, playing_status):
                    sessoes_tocando.append(candidate)
        if cls._sessao_esta_tocando(current, playing_status) and current not in sessoes_tocando:
            sessoes_tocando.insert(0, current)
        if not sessoes_tocando:
            return current

        melhor = current if cls._sessao_esta_tocando(current, playing_status) else sessoes_tocando[0]
        melhor_score = (
            pontuar_sessao_para_selecao(cls._metadados_sincronos_sessao(melhor)) + 0.01
        )
        for candidate in sessoes_tocando:
            score = pontuar_sessao_para_selecao(cls._metadados_sincronos_sessao(candidate))
            if score > melhor_score:
                melhor = candidate
                melhor_score = score
        return melhor

    @staticmethod
    def _conectar_evento(registrar, remover, callback):
        try:
            token = registrar(lambda *_args: callback())
        except Exception:
            return None
        return (remover, token)

    @classmethod
    def _registrar_eventos(cls, target, pairs, loop, wake_event: asyncio.Event):
        if target is None:
            return []

        def _wake() -> None:
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(wake_event.set)

        handles = []
        for add_name, rem_name in pairs:
            reg = getattr(target, add_name, None)
            rem = getattr(target, rem_name, None)
            if callable(reg) and callable(rem):
                item = cls._conectar_evento(reg, rem, _wake)
                if item is not None:
                    handles.append(item)
        return handles

    @classmethod
    def _registrar_eventos_sessao(cls, session, loop, wake_event: asyncio.Event):
        return cls._registrar_eventos(session, cls._SESSION_EVENT_PAIRS, loop, wake_event)

    @staticmethod
    def _desconectar_eventos(handles) -> None:
        for remover, token in handles:
            with contextlib.suppress(Exception):
                remover(token)

    async def _extrair_paleta_thumb_async(
        self, thumbnail_ref, chave: tuple[str | None, str | None]
    ) -> tuple[tuple[float, float, float], ...]:
        if thumbnail_ref is None:
            return ()
        if chave in self._album_palette_cache:
            return self._album_palette_cache[chave]
        raw = await _ler_thumbnail_bytes_async(thumbnail_ref)
        paleta = extrair_paleta_album(raw)
        if len(self._album_palette_cache) >= 16:
            primeiro = next(iter(self._album_palette_cache))
            self._album_palette_cache.pop(primeiro, None)
        self._album_palette_cache[chave] = paleta
        return paleta

    def _calcular_veredito_atual(
        self,
        *,
        categoria: str,
        smtc_playing: bool,
        audio_active: bool,
        audio_level: float,
        music_confidence: float,
        audio_updated_at: float,
        speech_like: bool,
    ) -> tuple[bool, float]:
        return decidir_musica_ativa(
            self.settings.source,
            categoria,  # type: ignore[arg-type]
            smtc_playing,
            audio_active=audio_active,
            audio_level=audio_level,
            music_confidence=music_confidence,
            speech_like=speech_like,
            ignore_video_sessions=bool(getattr(self.settings, "ignore_video_sessions", True)),
            has_loopback_data=audio_updated_at > 0.0,
        )

    def _publicar_sem_sessao(self) -> None:
        snap_atual = self.snapshot
        tocando, conf = self._calcular_veredito_atual(
            categoria="none",
            smtc_playing=False,
            audio_active=snap_atual.audio_active,
            audio_level=snap_atual.audio_level,
            music_confidence=snap_atual.music_confidence,
            audio_updated_at=snap_atual.audio_updated_at,
            speech_like=self._last_dsp_speech_like,
        )
        self._publish(
            source_app_id=None,
            title=None,
            artist=None,
            album=None,
            is_playing=False,
            playback_status="none",
            media_type="unknown",
            media_category="none",
            duration_seconds=None,
            is_music_playing=tocando,
            music_confidence=conf,
            thumbnail_available=False,
            album_colors=(),
            media_error=None,
        )

    @staticmethod
    def _montar_meta_smtc(
        source_app_id: str | None,
        media_type: str,
        duration_seconds: float | None,
        properties,
    ) -> MetadadosSessao:
        if properties is None:
            return MetadadosSessao(
                source_app_id=source_app_id,
                playback_type=media_type,
                duration_seconds=duration_seconds,
            )
        genres_raw = getattr(properties, "genres", None)
        track_num = getattr(properties, "track_number", None)
        return MetadadosSessao(
            source_app_id=source_app_id,
            title=getattr(properties, "title", None) or None,
            artist=getattr(properties, "artist", None) or None,
            album=getattr(properties, "album_title", None) or None,
            album_artist=getattr(properties, "album_artist", None) or None,
            subtitle=getattr(properties, "subtitle", None) or None,
            playback_type=media_type,
            duration_seconds=duration_seconds,
            genres=tuple(str(g) for g in genres_raw) if genres_raw else (),
            track_number=int(track_num) if isinstance(track_num, int) else None,
        )

    async def _publicar_sessao_smtc(self, session, playing_status) -> None:
        if session is None:
            self._publicar_sem_sessao()
            return

        playback = session.get_playback_info()
        if playback is None:
            return
        status = playback.playback_status
        status_name = str(status).rsplit(".", 1)[-1].lower()
        is_playing = status == playing_status
        source_app_id = getattr(session, "source_app_user_model_id", None)
        duration_seconds = self._extrair_duracao_sessao(session)
        properties = await session.try_get_media_properties_async()
        media_type = self._extrair_media_type(playback, properties)
        meta = self._montar_meta_smtc(source_app_id, media_type, duration_seconds, properties)
        classif = classificar_sessao_midia(meta)
        snap_atual = self.snapshot
        tocando, conf = self._calcular_veredito_atual(
            categoria=classif.categoria,
            smtc_playing=is_playing,
            audio_active=snap_atual.audio_active,
            audio_level=snap_atual.audio_level,
            music_confidence=snap_atual.music_confidence,
            audio_updated_at=snap_atual.audio_updated_at,
            speech_like=self._last_dsp_speech_like,
        )
        if properties is None:
            self._publish(
                source_app_id=source_app_id,
                is_playing=is_playing,
                playback_status=status_name,
                media_type=media_type,
                media_category=classif.categoria,
                duration_seconds=duration_seconds,
                is_music_playing=tocando,
                music_confidence=conf,
                media_error=None,
            )
            return
        thumb = getattr(properties, "thumbnail", None)
        cores_album = (
            await self._extrair_paleta_thumb_async(thumb, (meta.artist, meta.title))
            if thumb is not None
            else ()
        )
        self._publish(
            source_app_id=source_app_id,
            title=meta.title,
            artist=meta.artist,
            album=meta.album,
            is_playing=is_playing,
            playback_status=status_name,
            media_type=media_type,
            media_category=classif.categoria,
            duration_seconds=duration_seconds,
            is_music_playing=tocando,
            music_confidence=conf,
            thumbnail_available=thumb is not None,
            album_colors=cores_album,
            media_error=None,
        )

    @staticmethod
    def _identidade_sessao(session) -> str | None:
        return getattr(session, "source_app_user_model_id", None) if session is not None else None

    async def _sincronizar_e_publicar_smtc(
        self,
        manager,
        playing_status,
        watched_session,
        session_handles,
        loop,
        wake_event: asyncio.Event,
    ):
        try:
            session = self._escolher_sessao(manager, playing_status)
            if self._identidade_sessao(session) != self._identidade_sessao(watched_session):
                self._desconectar_eventos(session_handles)
                watched_session = session
                session_handles = self._registrar_eventos_sessao(
                    session, loop, wake_event
                )
            await self._publicar_sessao_smtc(session, playing_status)
        except Exception as exc:
            self._publish(media_error=f"Falha ao consultar a sessão: {exc}")
        return watched_session, session_handles

    async def _poll_media_sessions(self) -> None:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as SessionManager,
        )
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
        )

        manager = await SessionManager.request_async()
        loop = asyncio.get_running_loop()
        wake_event = asyncio.Event()
        self._smtc_wake = (loop, wake_event)
        mgr_handles = self._registrar_eventos(
            manager, self._MANAGER_EVENT_PAIRS, loop, wake_event
        )
        watched_session = None
        session_handles = []
        try:
            while not self._stop.is_set():
                wake_event.clear()
                watched_session, session_handles = await self._sincronizar_e_publicar_smtc(
                    manager,
                    PlaybackStatus.PLAYING,
                    watched_session,
                    session_handles,
                    loop,
                    wake_event,
                )
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(wake_event.wait(), timeout=self.poll_interval)
        finally:
            self._desconectar_eventos(session_handles)
            self._desconectar_eventos(mgr_handles)
            self._smtc_wake = None

    def _processar_bloco_loopback(
        self,
        samples,
        analisador: AnalisadorRitmo,
        backend_tag: str,
    ) -> None:
        """Processa bloco PCM no ``AnalisadorRitmo`` e publica snapshot atualizado."""
        snap_atual = self.snapshot
        smtc_playing = self.settings.source == "auto" and snap_atual.is_playing
        frame = analisador.processar_bloco(
            samples,
            now=time.monotonic(),
            sensitivity=self.settings.sensitivity,
            smtc_playing=smtc_playing,
        )
        self._last_dsp_speech_like = frame.speech_like
        tocando, conf = self._calcular_veredito_atual(
            categoria=snap_atual.media_category,
            smtc_playing=snap_atual.is_playing,
            audio_active=frame.music_active,
            audio_level=frame.audio_level,
            music_confidence=frame.music_confidence,
            audio_updated_at=time.monotonic(),
            speech_like=frame.speech_like,
        )
        self._publish(
            stamp_audio=True,
            audio_level=frame.audio_level,
            bass_level=frame.bass_level,
            beat_detected=frame.beat_detected,
            bpm=frame.bpm,
            beat_phase=frame.beat_phase,
            audio_active=frame.music_active,
            is_music_playing=tocando,
            music_confidence=conf,
            capture_backend=backend_tag,
            audio_error=None,
        )

    @classmethod
    def _abrir_captura_soundcard(cls, sc, speaker):
        """Abre loopback no GUID exato do dispositivo padrão tentando taxas estáveis."""
        speaker_id = str(getattr(speaker, "id", "") or speaker.name)
        try:
            microphone = sc.get_microphone(id=speaker_id, include_loopback=True)
        except Exception:
            microphone = sc.get_microphone(id=str(speaker.name), include_loopback=True)

        last_exc: Exception | None = None
        for rate in cls._SAMPLE_RATES:
            try:
                recorder = microphone.recorder(samplerate=rate, blocksize=cls._HOP_SIZE)
                return recorder, rate, speaker_id
            except Exception as exc:
                last_exc = exc
        assert last_exc is not None
        raise last_exc

    @staticmethod
    def _mesmo_dispositivo_padrao(sc, speaker_id: str) -> bool:
        atual = sc.default_speaker()
        atual_id = str(getattr(atual, "id", "") or atual.name)
        return atual_id == speaker_id

    def _executar_sessao_loopback(self, sc) -> None:
        """Captura áudio em loopback e reinicia se o dispositivo padrão mudar."""
        speaker = sc.default_speaker()
        recorder_ctx, sample_rate, speaker_id = self._abrir_captura_soundcard(sc, speaker)
        analisador = AnalisadorRitmo(
            sample_rate=sample_rate,
            hop_size=self._HOP_SIZE,
            window_size=self._WINDOW_SIZE,
        )
        backend_tag = f"wasapi-loopback:{sample_rate}hz"
        check_every = max(60, round(2.0 * sample_rate / self._HOP_SIZE))
        hops = 0

        with recorder_ctx as recorder:
            self._publish(audio_error=None, capture_backend=backend_tag)
            while not self._stop.is_set():
                samples = recorder.record(numframes=self._HOP_SIZE)
                if samples.size == 0:
                    continue
                self._processar_bloco_loopback(samples, analisador, backend_tag)
                hops += 1
                if hops % check_every == 0 and not self._mesmo_dispositivo_padrao(
                    sc, speaker_id
                ):
                    logger.info("Dispositivo padrão de áudio mudou; reabrindo loopback.")
                    break

    def _loopback_worker(self, *, optional: bool = False) -> None:
        try:
            import soundcard as sc
        except ImportError:
            message = "Loopback requer a dependência opcional soundcard."
            if optional:
                logger.info("%s Modo automático seguirá apenas com SMTC.", message)
            else:
                self._publish(audio_error=message)
                logger.warning(message)
            return

        backoff_s = 1.5
        while not self._stop.is_set():
            try:
                self._executar_sessao_loopback(sc)
                backoff_s = 1.5
            except Exception as exc:
                self._publish(audio_error=f"Loopback indisponível: {exc}")
                logger.warning("Loopback indisponível (tentando novamente): %s", exc)
                if self._stop.wait(backoff_s):
                    break
                backoff_s = min(6.0, backoff_s * 1.5)
