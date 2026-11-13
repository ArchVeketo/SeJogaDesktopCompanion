"""Animações procedurais de entrada (abertura) do mascote, sem dependências de engine."""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import pi, sin
from typing import ClassVar

INTRO_STYLES = (
    "padrao",
    "fade_in",
    "virtual_insanity_in",
    "run_from_depth",
    "kagebunshin_in",
    "aleatoria",
)

_RANDOM_POOL = (
    "fade_in",
    "virtual_insanity_in",
    "run_from_depth",
    "kagebunshin_in",
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _smooth(value: float) -> float:
    u = _clamp01(value)
    return u * u * (3.0 - 2.0 * u)


def _quintic(value: float) -> float:
    u = _clamp01(value)
    return u * u * u * (10.0 + u * (-15.0 + 6.0 * u))


@dataclass(frozen=True, slots=True)
class IntroFrame:
    """Estado de um frame da animação de abertura."""

    offset_x: float = 0.0
    offset_y: float = 0.0
    scale: float = 1.0
    roll: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    dissolve: float = 0.0
    smoke_burst: float = 0.0
    locomotion: str = "idle"
    finished: bool = True


class IntroAnimation:
    """Produz a sequência de abertura escolhida até pousar no desktop."""

    DURATIONS: ClassVar[dict[str, float]] = {
        "padrao": 0.0,
        "fade_in": 0.95,
        "virtual_insanity_in": 1.45,
        "run_from_depth": 1.35,
        "kagebunshin_in": 1.25,
    }

    def __init__(
        self,
        style: str = "padrao",
        *,
        from_side: int = 1,
        rng: random.Random | None = None,
    ) -> None:
        """Resolve estilo (inclusive aleatório) e direção inicial."""
        chooser = rng or random.Random()
        if style == "aleatoria":
            style = chooser.choice(_RANDOM_POOL)
        if style not in self.DURATIONS:
            style = "padrao"
        self.style = style
        self.duration = self.DURATIONS[style]
        self.side = 1 if from_side >= 0 else -1

    def sample(self, elapsed: float) -> IntroFrame:
        """Amostra o quadro de abertura no instante ``elapsed`` (segundos)."""
        if self.style == "padrao" or self.duration <= 0.0:
            return IntroFrame(finished=True)

        p = _clamp01(elapsed / self.duration)
        done = elapsed >= self.duration

        if self.style == "fade_in":
            eased = _quintic(p)
            dissolve = max(0.0, 1.0 - _smooth(min(1.0, p / 0.85)))
            overshoot = sin(min(1.0, p) * pi) * 0.03
            return IntroFrame(
                offset_x=0.0,
                offset_y=0.0,
                scale=0.88 + 0.12 * eased + overshoot,
                pitch=0.0,
                dissolve=dissolve,
                locomotion="idle",
                finished=done,
            )

        if self.style == "virtual_insanity_in":
            # Deslize horizontal nivelado no chão mantendo pose icônica de Jamiroquai.
            glide = _quintic(p)
            remain = 1.0 - glide
            return IntroFrame(
                offset_x=self.side * 160.0 * remain,
                offset_y=0.0,
                scale=1.0,
                roll=0.0,
                yaw=0.0,
                pitch=0.0,
                dissolve=max(0.0, 1.0 - min(1.0, p / 0.14)),
                locomotion="virtual_insanity" if p < 0.88 else "idle",
                finished=done,
            )

        if self.style == "run_from_depth":
            # Corre lá do fundo mantendo a sola colada na mesma cota do desktop.
            if p < 0.82:
                run_u = p / 0.82
                depth = run_u ** 1.65
                scale = 0.22 + 0.78 * depth
                return IntroFrame(
                    offset_x=self.side * 36.0 * (1.0 - depth),
                    offset_y=0.0,
                    scale=scale,
                    roll=sin(elapsed * 12.0) * 2.5 * (1.0 - run_u * 0.4),
                    yaw=0.0,
                    pitch=5.0 * (1.0 - run_u * 0.5),
                    dissolve=max(0.0, 1.0 - min(1.0, p / 0.12)),
                    locomotion="run",
                    finished=done,
                )
            settle_u = (p - 0.82) / 0.18
            hop = sin(settle_u * pi)
            return IntroFrame(
                offset_x=0.0,
                offset_y=0.0,
                scale=1.0 + 0.03 * hop,
                pitch=6.0 * hop,
                dissolve=0.0,
                locomotion="land",
                finished=done,
            )

        # "kagebunshin_in": bomba de fumaça ninja na altura atual e pouso ágil no lugar.
        if p < 0.24:
            smoke_p = p / 0.24
            return IntroFrame(
                offset_y=0.0,
                scale=0.68,
                dissolve=1.0,
                smoke_burst=min(1.0, 0.35 + smoke_p * 0.65),
                locomotion="land",
                finished=False,
            )
        drop_p = _smooth((p - 0.24) / 0.38)
        smoke_fade = max(0.0, 1.0 - max(0.0, p - 0.22) / 0.72)
        dissolve = max(0.0, 1.0 - min(1.0, (p - 0.24) / 0.16))
        if p < 0.62:
            return IntroFrame(
                offset_y=0.0,
                scale=0.68 + 0.32 * drop_p,
                roll=0.0,
                pitch=-8.0 * (1.0 - drop_p),
                dissolve=dissolve,
                smoke_burst=smoke_fade,
                locomotion="land",
                finished=False,
            )
        land_u = (p - 0.62) / 0.38
        bounce = sin(land_u * pi) * (1.0 - land_u * 0.4)
        return IntroFrame(
            offset_y=0.0,
            scale=1.0 + 0.03 * bounce,
            pitch=5.0 * bounce,
            dissolve=0.0,
            smoke_burst=smoke_fade,
            locomotion="land" if land_u < 0.72 else "idle",
            finished=done,
        )
