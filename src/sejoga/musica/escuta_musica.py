"""Leitura não bloqueante de metadados de música e energia de loopback.

As APIs WinRT e SoundCard rodam em workers próprios. Áudio capturado é
processado em memória e descartado; nenhum buffer é salvo em disco.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import statistics
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace

from sejoga.configuracao import MusicSettings

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


class _BeatTracker:
    """Estimativa leve de onset/RMS adequada para resposta visual, não análise musical."""

    def __init__(self) -> None:
        self._levels: deque[float] = deque(maxlen=32)
        self._beat_times: deque[float] = deque(maxlen=12)
        self._last_beat = 0.0
        self._bpm: float | None = None
        self._period = 0.0

    def update(self, rms: float, now: float, sensitivity: float) -> tuple[bool, float | None, float]:
        if self._last_beat and now-self._last_beat > 4:
            self._bpm = None
            self._period = 0.0
            self._beat_times.clear()
        baseline = statistics.median(self._levels) if self._levels else 0.0
        previous = self._levels[-1] if self._levels else 0.0
        self._levels.append(rms)

        multiplier = 2.4 - 1.7 * max(0.0, min(1.0, sensitivity))
        threshold = max(0.012, baseline * multiplier)
        detected = (
            len(self._levels) >= 5
            and rms >= threshold
            and rms >= 0.018
            and rms > previous * 1.08
            and now - self._last_beat >= 0.26
        )
        if detected:
            self._last_beat = now
            if self._beat_times:
                interval = now - self._beat_times[-1]
                if 0.30 <= interval <= 1.50:
                    self._beat_times.append(now)
                    intervals = [
                        current - previous
                        for previous, current in zip(self._beat_times, list(self._beat_times)[1:], strict=False)
                    ]
                    if intervals:
                        self._period = statistics.median(intervals)
                        self._bpm = 60.0 / self._period
                else:
                    self._beat_times.clear()
                    self._beat_times.append(now)
            else:
                self._beat_times.append(now)

        phase = 0.0
        if self._period and self._last_beat:
            phase = ((now - self._last_beat) / self._period) % 1.0
        return detected, self._bpm, phase


class MusicListener:
    """Monitora a sessão de mídia e, opcionalmente, o loopback WASAPI."""

    def __init__(
        self,
        settings: MusicSettings,
        *,
        poll_interval: float = 1.0,
        on_update: Callable[[MusicSnapshot], None] | None = None,
    ) -> None:
        self.settings = settings
        self.poll_interval = max(0.25, poll_interval)
        self.on_update = on_update
        self._snapshot = MusicSnapshot()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    @property
    def snapshot(self) -> MusicSnapshot:
        with self._lock:
            return self._snapshot

    def start(self) -> None:
        if not self.settings.enabled or self.settings.source == "off" or self._threads:
            return

        self._stop.clear()
        self._start_worker(self._media_worker, "music-media-session")
        if self.settings.source == "loopback":
            self._start_worker(self._loopback_worker, "music-wasapi-loopback")

    def _start_worker(self, target: Callable[[], None], name: str) -> None:
        thread = threading.Thread(target=target, name=name, daemon=True)
        self._threads.append(thread)
        thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads.clear()

    def _publish(self, **changes: object) -> None:
        with self._lock:
            # mypy nao verifica kwargs via **dict[str, object] contra os campos
            # tipados de MusicSnapshot; os chamadores passam os tipos corretos.
            self._snapshot = replace(self._snapshot, updated_at=time.time(), **changes)  # type: ignore[arg-type]
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
            if apartment_initialized:
                with contextlib.suppress(Exception):
                    uninit_apartment()

    async def _poll_media_sessions(self) -> None:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as SessionManager,
        )
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
        )

        manager = await SessionManager.request_async()
        while not self._stop.is_set():
            try:
                session = manager.get_current_session()
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
                else:
                    playback = session.get_playback_info()
                    status = playback.playback_status
                    properties = await session.try_get_media_properties_async()
                    if properties is not None:
                        status_name = str(status).rsplit(".", 1)[-1].lower()
                        self._publish(
                            source_app_id=session.source_app_user_model_id,
                            title=properties.title or None,
                            artist=properties.artist or None,
                            album=properties.album_title or None,
                            is_playing=status == PlaybackStatus.PLAYING,
                            playback_status=status_name,
                            thumbnail_available=properties.thumbnail is not None,
                            media_error=None,
                        )
            except Exception as exc:
                self._publish(media_error=f"Falha ao consultar a sessão: {exc}")
            await asyncio.sleep(self.poll_interval)

    def _loopback_worker(self) -> None:
        try:
            import numpy as np
            import soundcard as sc

            speaker = sc.default_speaker()
            microphone = sc.get_microphone(id=str(speaker.name), include_loopback=True)
            tracker = _BeatTracker()
            sample_rate = 16_000
            block_size = 1024
            frequencies = np.fft.rfftfreq(block_size, 1/sample_rate)
            bass_band = (frequencies >= 40) & (frequencies <= 220)
            window = np.hanning(block_size)
            with microphone.recorder(samplerate=sample_rate, blocksize=block_size) as recorder:
                self._publish(audio_error=None)
                while not self._stop.is_set():
                    samples = recorder.record(numframes=block_size)
                    if samples.size == 0:
                        continue
                    rms = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64)))
                    mono = samples.mean(axis=1) if samples.ndim > 1 else samples
                    spectrum = np.abs(np.fft.rfft(mono*window))**2
                    bass_share = float(spectrum[bass_band].sum()/max(1e-12, spectrum.sum()))  # type: ignore[operator]  # overloads do numpy nao cobrem max() aqui
                    now = time.monotonic()
                    beat, bpm, phase = tracker.update(rms, now, self.settings.sensitivity)
                    self._publish(
                        audio_level=max(0.0, min(1.0, rms * 5.0)),
                        bass_level=max(0.0, min(1.0, rms*5*bass_share**.5)),
                        beat_detected=beat,
                        bpm=bpm,
                        beat_phase=phase,
                        audio_error=None,
                    )
        except ImportError:
            message = "Loopback requer a dependência opcional soundcard."
            self._publish(audio_error=message)
            logger.warning(message)
        except Exception as exc:
            self._publish(audio_error=f"Loopback indisponível: {exc}")
            logger.warning("Loopback indisponível: %s", exc)
