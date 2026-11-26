"""Small original landing sound, independent of media playback."""

import logging
import math
import os
import struct
import tempfile
import threading
import wave
from pathlib import Path

_AUDIO_CACHE_LOCK = threading.Lock()


def _gravar_wav_atomico(path: Path, rate: int, frames: bytes) -> None:
    """Escreve um WAV no cache protegido por trava e substituição atômica."""
    with _AUDIO_CACHE_LOCK:
        if path.exists():
            return
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f"{path.stem}-",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
        try:
            with wave.open(str(tmp_path), "wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(rate)
                out.writeframes(frames)
            os.replace(tmp_path, path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise


def play_speaker_landing(volume):
    """Toca o som de aterrissagem da caixa no volume dado."""
    volume = max(0, min(1, volume))
    if not volume:
        return

    def worker():
        try:
            import winsound

            directory = Path(tempfile.gettempdir()) / "SeJogaCompanionAudio"
            directory.mkdir(exist_ok=True)
            path = directory / f"speaker-land-{round(volume * 100)}.wav"
            if not path.exists():
                rate = 22050
                samples = []
                phase = 0.0
                for index in range(int(rate * 0.18)):
                    t = index / rate
                    phase += 2 * math.pi * (65 - 100 * t) / rate
                    envelope = min(1, t / 0.006) * math.exp(-t * 28)
                    value = math.sin(phase) * envelope * 0.18 * volume
                    samples.append(struct.pack("<h", round(value * 32767)))
                _gravar_wav_atomico(path, rate, b"".join(samples))
            winsound.PlaySound(
                str(path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except Exception:
            logging.getLogger("sejoga").debug(
                "Speaker landing sound unavailable", exc_info=True
            )

    threading.Thread(target=worker, name="speaker-landing-audio", daemon=True).start()


def _sintetizar_goku_teleport(volume: float, rate: int = 22050) -> bytes:
    samples = []
    p1 = 0.0
    p2 = 0.0
    dur = 0.22
    for index in range(int(rate * dur)):
        t = index / rate
        u = t / dur
        # Varredura rápida FM descendente/ascendente com vibrato metálico de ki.
        f1 = 1480.0 - 980.0 * math.sin(u * math.pi) + 260.0 * math.sin(u * 14.0 * math.pi)
        f2 = 2420.0 * (1.0 - 0.55 * u) + 520.0 * math.cos(u * 18.0 * math.pi)
        p1 += math.tau * f1 / rate
        p2 += math.tau * f2 / rate
        env = min(1.0, t / 0.008) * math.exp(-t * 9.5) * (1.0 - 0.25 * math.sin(u * 10.0 * math.pi))
        val = (0.62 * math.sin(p1) + 0.38 * math.sin(p2)) * env * 0.22 * volume
        samples.append(struct.pack("<h", max(-32767, min(32767, round(val * 32767)))))
    return b"".join(samples)


def play_goku_teleport(volume: float = 0.65) -> None:
    """Sintetiza e toca o efeito sonoro clássico de Teleporte Instantâneo (DBZ BWOOP-ZIP!)."""
    volume = max(0.0, min(1.0, float(volume)))
    if not volume:
        return

    def worker() -> None:
        try:
            import winsound

            directory = Path(tempfile.gettempdir()) / "SeJogaCompanionAudio"
            directory.mkdir(exist_ok=True)
            path = directory / f"goku-teleport-{round(volume * 100)}.wav"
            if not path.exists():
                _gravar_wav_atomico(path, 22050, _sintetizar_goku_teleport(volume))
            winsound.PlaySound(
                str(path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except Exception:
            logging.getLogger("sejoga").debug(
                "Goku teleport sound unavailable", exc_info=True
            )

    threading.Thread(target=worker, name="goku-teleport-audio", daemon=True).start()

