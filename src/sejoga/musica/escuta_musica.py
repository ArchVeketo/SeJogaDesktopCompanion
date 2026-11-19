"""Leitura não bloqueante de metadados SMTC multi-sessão e análise rítmica WASAPI.

As APIs WinRT e SoundCard rodam em workers próprios. Áudio capturado é
processado em memória por fluxo espectral multi-banda e descartado; nenhum
buffer é salvo em disco.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from sejoga.configuracao import MusicSettings
from sejoga.musica.analisador_ritmo import AnalisadorRitmo

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MusicSnapshot:
    """Snapshot imutável, seguro para leitura pelo loop gráfico."""

    source_app_id: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    is_playing: bool = False
    playback_status: str = "unknown"
    thumbnail_available: bool = False
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

    @classmethod
    def _escolher_sessao(cls, manager, playing_status):
        """Seleciona a sessão SMTC priorizando qualquer reprodução ativa."""
        current = manager.get_current_session()
        if cls._sessao_esta_tocando(current, playing_status):
            return current
        with contextlib.suppress(Exception):
            for candidate in manager.get_sessions() or ():
                if cls._sessao_esta_tocando(candidate, playing_status):
                    return candidate
        return current

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

    async def _publicar_sessao_smtc(self, session, playing_status) -> None:
        if session is None:
            self._publish(
                source_app_id=None,
                title=None,
                artist=None,
                album=None,
                is_playing=False,
                playback_status="none",
                thumbnail_available=False,
                media_error=None,
            )
            return

        playback = session.get_playback_info()
        status = playback.playback_status
        properties = await session.try_get_media_properties_async()
        if properties is None:
            return
        status_name = str(status).rsplit(".", 1)[-1].lower()
        self._publish(
            source_app_id=session.source_app_user_model_id,
            title=properties.title or None,
            artist=properties.artist or None,
            album=properties.album_title or None,
            is_playing=status == playing_status,
            playback_status=status_name,
            thumbnail_available=properties.thumbnail is not None,
            media_error=None,
        )

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
            if session is not watched_session:
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
        smtc_playing = self.settings.source == "auto" and self.snapshot.is_playing
        frame = analisador.processar_bloco(
            samples,
            now=time.monotonic(),
            sensitivity=self.settings.sensitivity,
            smtc_playing=smtc_playing,
        )
        self._publish(
            stamp_audio=True,
            audio_level=frame.audio_level,
            bass_level=frame.bass_level,
            beat_detected=frame.beat_detected,
            bpm=frame.bpm,
            beat_phase=frame.beat_phase,
            audio_active=frame.music_active,
            music_confidence=frame.music_confidence,
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
