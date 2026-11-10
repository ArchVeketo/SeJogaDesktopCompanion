"""Small original landing sound, independent of media playback."""

import logging
import math
import struct
import tempfile
import threading
import wave
from pathlib import Path


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
                with wave.open(str(path), "wb") as out:
                    out.setnchannels(1)
                    out.setsampwidth(2)
                    out.setframerate(rate)
                    out.writeframes(b"".join(samples))
            winsound.PlaySound(
                str(path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except Exception:
            logging.getLogger("sejoga").debug(
                "Speaker landing sound unavailable", exc_info=True
            )

    threading.Thread(target=worker, name="speaker-landing-audio", daemon=True).start()
