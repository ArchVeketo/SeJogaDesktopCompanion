"""Animação de saída e encerramento ("morte") do mascote para fora do desktop."""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import pi, sin
from typing import ClassVar

EXIT_STYLES = (
    "classic",
    "sonic_classic",
    "fnf_blue_balls",
    "lego_disassemble",
    "thanos_snap",
    "peace_fade_out",
    "virtual_insanity_out",
    "aleatoria",
)

_RANDOM_DEATH_POOL = (
    "sonic_classic",
    "fnf_blue_balls",
    "lego_disassemble",
    "thanos_snap",
    "peace_fade_out",
    "virtual_insanity_out",
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _smooth(value: float) -> float:
    u = _clamp01(value)
    return u * u * (3.0 - 2.0 * u)


@dataclass(frozen=True, slots=True)
class ExitFrame:
    """Posição, rotação e efeitos de um frame da animação de saída."""

    x: int
    y: int
    roll: float
    done: bool
    pitch: float = 0.0
    yaw: float = 0.0
    scale: float = 1.0
    dissolve: float = 0.0
    explode: float = 0.0
    ash: float = 0.0
    blue_balls: float = 0.0
    locomotion: str | None = None
    shock: float = 0.0


class ExitAnimation:
    """Anima a saída/encerramento do mascote conforme o estilo configurado."""

    DURATION = 1.35
    HIT_STOP = 0.14
    STYLE_DURATIONS: ClassVar[dict[str, float]] = {
        "classic": 1.35,
        "sonic_classic": 1.45,
        "fnf_blue_balls": 2.05,
        "lego_disassemble": 1.60,
        "thanos_snap": 1.70,
        "peace_fade_out": 1.45,
        "virtual_insanity_out": 1.65,
    }

    def __init__(
        self,
        origin,
        size,
        desktop_bounds,
        style: str = "classic",
        rng: random.Random | None = None,
    ):
        """Calcula direção de saída, borda-alvo e parâmetros do estilo escolhido."""
        chooser = rng or random.Random()
        if style == "aleatoria":
            style = chooser.choice(_RANDOM_DEATH_POOL)
        if style not in self.STYLE_DURATIONS:
            style = "classic"
        self.style = style
        self.duration = self.STYLE_DURATIONS[style]
        self.origin = origin
        self.size = size
        self.bounds = desktop_bounds
        left, _top, right, _bottom = desktop_bounds
        center_x = origin[0] + size / 2
        self.direction = -1 if center_x < (left + right) / 2 else 1
        self.exit_x = left - size if self.direction < 0 else right + size
        self.bottom_exit_y = desktop_bounds[3] + size

    def sample(self, elapsed: float) -> ExitFrame:
        """Amostra o quadro de encerramento em ``elapsed`` segundos."""
        sampler = _STYLE_SAMPLERS.get(self.style, ExitAnimation._sample_classic)
        p = _clamp01(elapsed / max(1e-4, self.duration))
        done = elapsed >= self.duration
        return sampler(self, elapsed, p, done)

    def _sample_classic(self, elapsed: float, _p: float, done: bool) -> ExitFrame:
        move_duration = self.DURATION - self.HIT_STOP
        progress = _clamp01((elapsed - self.HIT_STOP) / move_duration)
        x = self.origin[0] + (self.exit_x - self.origin[0]) * progress * progress
        y = self.origin[1] + 540 * progress * (progress - 0.72)
        return ExitFrame(round(x), round(y), self.direction * 1080 * progress, done)

    def _sample_sonic_classic(self, elapsed: float, p: float, done: bool) -> ExitFrame:
        ox, oy = self.origin
        if p < 0.14:
            jitter = sin(elapsed * 55.0) * 5.0
            return ExitFrame(
                round(ox + jitter),
                round(oy),
                0.0,
                False,
                pitch=-6.0,
                scale=1.04,
                locomotion="hit",
            )
        jump_u = (p - 0.14) / 0.86
        if jump_u < 0.28:
            rise = sin((jump_u / 0.28) * (pi * 0.5))
            return ExitFrame(
                round(ox),
                round(oy - 165.0 * rise),
                0.0,
                done,
                pitch=-16.0 * rise,
                locomotion="hit",
            )
        fall_u = (jump_u - 0.28) / 0.72
        peak_y = oy - 165.0
        drop_y = peak_y + (self.bottom_exit_y - peak_y) * (fall_u * fall_u)
        return ExitFrame(
            round(ox),
            round(drop_y),
            0.0,
            done,
            pitch=-16.0 + 38.0 * fall_u,
            locomotion="fall",
        )

    def _sample_fnf_blue_balls(self, elapsed: float, p: float, done: bool) -> ExitFrame:
        ox, oy = self.origin
        if p < 0.22:
            u = p / 0.22
            tremor = sin(elapsed * 56.0) * 5.0 * (1.0 - u * 0.35)
            strobe = 0.5 + 0.5 * sin(elapsed * 52.0)
            return ExitFrame(
                round(ox + tremor),
                round(oy),
                0.0,
                False,
                blue_balls=0.0,
                locomotion="blue_balls",
                shock=0.35 + 0.65 * strobe,
            )
        if p < 0.74:
            pop_u = min(1.0, (p - 0.22) / 0.08)
            beat = 0.78 + 0.22 * (0.5 + 0.5 * sin((elapsed - 0.45) * 9.0))
            pop_boost = 1.0 + 0.18 * sin(pop_u * pi)
            return ExitFrame(
                round(ox),
                round(oy),
                0.0,
                False,
                blue_balls=min(1.0, beat * pop_boost),
                locomotion="blue_balls",
                shock=0.0,
            )
        fade_u = _smooth((p - 0.74) / 0.26)
        beat = 0.80 + 0.20 * (0.5 + 0.5 * sin((elapsed - 0.45) * 9.0))
        return ExitFrame(
            round(ox),
            round(oy),
            0.0,
            done,
            dissolve=fade_u,
            blue_balls=max(0.0, (1.0 - fade_u) * beat),
            locomotion="blue_balls",
            shock=0.0,
        )

    def _sample_lego_disassemble(self, elapsed: float, p: float, done: bool) -> ExitFrame:
        ox, oy = self.origin
        if p < 0.12:
            jitter = sin(elapsed * 60.0) * 4.5
            return ExitFrame(
                round(ox + jitter), round(oy), 0.0, False, scale=1.04, locomotion="hit"
            )
        return ExitFrame(
            round(ox),
            round(oy),
            0.0,
            done,
            explode=_clamp01((p - 0.12) / 0.68),
            dissolve=_smooth(max(0.0, p - 0.72) / 0.28),
            locomotion="hit",
        )

    def _sample_thanos_snap(self, _elapsed: float, p: float, done: bool) -> ExitFrame:
        ox, oy = self.origin
        if p < 0.22:
            u = p / 0.22
            return ExitFrame(
                round(ox),
                round(oy),
                0.0,
                False,
                yaw=-12.0 * u,
                pitch=4.0 * u,
                locomotion="open_hands",
            )
        dust_u = _clamp01((p - 0.22) / 0.78)
        return ExitFrame(
            round(ox + 22.0 * dust_u),
            round(oy),
            0.0,
            done,
            yaw=-12.0 + 18.0 * dust_u,
            pitch=0.0,
            dissolve=dust_u,
            ash=dust_u,
            locomotion="open_hands",
        )

    def _sample_peace_fade_out(self, _elapsed: float, p: float, done: bool) -> ExitFrame:
        ox, oy = self.origin
        fade_u = _smooth(max(0.0, p - 0.42) / 0.58)
        nod = sin(min(1.0, p / 0.45) * pi)
        return ExitFrame(
            round(ox),
            round(oy),
            0.0,
            done,
            yaw=-7.0 * nod,
            pitch=0.0,
            dissolve=fade_u,
            locomotion="peace",
        )

    def _sample_virtual_insanity_out(self, _elapsed: float, p: float, done: bool) -> ExitFrame:
        ox, oy = self.origin
        glide = _smooth(p) * 0.35 + (p * p) * 0.65
        x = ox + (self.exit_x - ox) * glide
        return ExitFrame(
            round(x),
            round(oy),
            0.0,
            done,
            yaw=0.0,
            pitch=0.0,
            dissolve=_smooth(max(0.0, p - 0.76) / 0.24),
            locomotion="virtual_insanity",
        )


_STYLE_SAMPLERS = {
    "classic": ExitAnimation._sample_classic,
    "sonic_classic": ExitAnimation._sample_sonic_classic,
    "fnf_blue_balls": ExitAnimation._sample_fnf_blue_balls,
    "lego_disassemble": ExitAnimation._sample_lego_disassemble,
    "thanos_snap": ExitAnimation._sample_thanos_snap,
    "peace_fade_out": ExitAnimation._sample_peace_fade_out,
    "virtual_insanity_out": ExitAnimation._sample_virtual_insanity_out,
}
