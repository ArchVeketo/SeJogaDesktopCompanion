"""Animações procedurais de entrada (abertura) do mascote, sem dependências de engine."""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import pi, sin
from typing import ClassVar

from sejoga.animacao.dados_autorais import reacoes_ativas

INTRO_STYLES = (
    "padrao",
    "fade_in",
    "virtual_insanity_in",
    "run_from_depth",
    "kagebunshin_in",
    "sandevistan_in",
    "aleatoria",
)

_RANDOM_POOL = (
    "fade_in",
    "virtual_insanity_in",
    "run_from_depth",
    "kagebunshin_in",
    "sandevistan_in",
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
    afterimage: float = 0.0
    locomotion: str = "idle"
    finished: bool = True


class IntroAnimation:
    """Produz a sequência de abertura escolhida até pousar no desktop."""

    DURATIONS: ClassVar[dict[str, float]] = {
        "padrao": 0.0,
        "fade_in": 2.35,
        "virtual_insanity_in": 3.55,
        "run_from_depth": 2.60,
        "kagebunshin_in": 2.45,
        "sandevistan_in": 2.15,
    }

    def __init__(
        self,
        style: str = "padrao",
        *,
        from_side: int = 1,
        entry_distance: float = 560.0,
        rng: random.Random | None = None,
    ) -> None:
        """Resolve estilo (inclusive aleatório), lado e alcance na tela."""
        chooser = rng or random.Random()
        if style == "aleatoria":
            style = chooser.choice(_RANDOM_POOL)
        if style not in self.DURATIONS:
            style = "padrao"
        self.style = style
        entrada_cfg = reacoes_ativas().get("entradas", {}).get(style, {})
        vel = max(0.1, float(entrada_cfg.get("velocidade", 1.0)))
        dur_base = float(entrada_cfg.get("duracao_s", self.DURATIONS[style]))
        self.duration = dur_base / vel
        self.side = 1 if from_side >= 0 else -1
        self.entry_distance = max(360.0, float(entry_distance))

    def _sample_fade_in(self, p: float, done: bool) -> IntroFrame:
        dissolve = max(0.0, 1.0 - _smooth(min(1.0, p / 0.44)))
        if p < 0.42:
            ant_u = _quintic(p / 0.42)
            scale = 0.78 + 0.14 * ant_u
            yaw = self.side * 12.0 * (1.0 - ant_u * 0.4)
            pitch = 6.5 * sin(ant_u * pi)
            loco = "idle"
        elif p < 0.76:
            swell_u = _quintic((p - 0.42) / 0.34)
            scale = 0.92 + 0.135 * swell_u
            yaw = self.side * 7.2 * (1.0 - swell_u)
            pitch = -7.0 * sin(swell_u * pi)
            loco = "wave" if p >= 0.46 else "idle"
        else:
            settle_u = _quintic((p - 0.76) / 0.24)
            rebound = sin((1.0 - settle_u) * pi) * 0.014
            scale = 1.055 - 0.055 * settle_u + rebound
            yaw = 0.0
            pitch = 3.2 * sin(settle_u * pi) * (1.0 - settle_u)
            loco = "wave" if p < 0.90 else "idle"
        return IntroFrame(
            scale=scale,
            yaw=yaw,
            pitch=pitch,
            dissolve=dissolve,
            locomotion=loco if not done else "idle",
            finished=done,
        )

    def _sample_virtual_insanity_in(self, p: float, done: bool) -> IntroFrame:
        dissolve = max(0.0, 1.0 - min(1.0, p / 0.07))
        overshoot = 30.0
        if p < 0.76:
            u = _clamp01(p / 0.76)
            groove = _quintic(u) + 0.065 * sin(u * 2.0 * pi) * u * (1.0 - u)
            offset_x = self.side * (
                self.entry_distance * (1.0 - groove)
                - overshoot * _smooth(max(0.0, (p - 0.56) / 0.20))
            )
            mid_arc = sin(u * pi)
            roll = self.side * (-9.0 * mid_arc - 2.5 * sin(u * 3.0 * pi) * (1.0 - u))
            yaw = self.side * (16.0 * (1.0 - u) - 4.0 * mid_arc)
            pitch = -4.2 * sin(u * 2.0 * pi)
            scale = 1.0 - 0.03 * sin(u * 2.0 * pi) * (1.0 - u * 0.5)
        else:
            settle_u = _quintic((p - 0.76) / 0.24)
            snap = sin(settle_u * pi) * (1.0 - settle_u)
            offset_x = -self.side * overshoot * (1.0 - settle_u)
            roll = self.side * 4.0 * snap
            yaw = 0.0
            pitch = -8.5 * snap
            scale = 1.0 + 0.036 * snap
        return IntroFrame(
            offset_x=offset_x,
            scale=scale,
            roll=roll,
            yaw=yaw,
            pitch=pitch,
            dissolve=dissolve,
            locomotion="virtual_insanity" if p < 0.80 else "idle",
            finished=done,
        )

    def _sample_run_from_depth(self, elapsed: float, p: float, done: bool) -> IntroFrame:
        if p < 0.64:
            run_u = p / 0.64
            depth = run_u**1.42
            arc = sin(run_u * pi)
            hop = abs(sin(run_u * 3.0 * pi)) * 18.0 * (0.3 + 0.7 * run_u)
            return IntroFrame(
                offset_x=self.side * (78.0 * (1.0 - depth) + 24.0 * arc),
                offset_y=-hop,
                scale=0.16 + 0.88 * depth,
                roll=sin(elapsed * 16.0) * 4.4 * (1.0 - run_u * 0.40),
                yaw=self.side * -14.0 * arc,
                pitch=12.0 - 9.0 * run_u,
                dissolve=max(0.0, 1.0 - min(1.0, p / 0.09)),
                locomotion="run",
                finished=done,
            )
        if p < 0.80:
            brake_u = (p - 0.64) / 0.16
            skid = sin(brake_u * pi)
            roll_blend = _smooth(brake_u)
            return IntroFrame(
                scale=1.04 - 0.08 * _smooth(brake_u) + 0.045 * skid,
                roll=self.side * (2.5 * sin(brake_u * pi) * (1.0 - roll_blend)),
                pitch=3.0 * (1.0 - roll_blend) - 10.5 * skid,
                locomotion="land",
                finished=done,
            )
        settle_u = _clamp01((p - 0.80) / 0.20)
        rebound = sin(settle_u * pi) * (1.0 - settle_u)
        return IntroFrame(
            scale=1.0 + 0.026 * rebound,
            pitch=3.5 * rebound,
            locomotion="ajeitar_fone" if p < 0.96 else "idle",
            finished=done,
        )

    def _sample_sandevistan_in(self, p: float, done: bool) -> IntroFrame:
        alcance = self.entry_distance * 1.15
        if p < 0.60:
            dash_u = p / 0.60
            passos = 3
            passo = min(passos - 1, int(dash_u * passos))
            sub = (dash_u * passos) - passo
            # Cada corte Sandevistan dispara rápido e congela em micro hit-stop no ápice.
            explosao = _quintic(min(1.0, sub / 0.58))
            pos_passo = (passo + explosao) / passos
            progress_x = pos_passo**0.94
            zip_hop = sin(min(1.0, sub / 0.65) * pi)
            lunge_scale = 0.76 + 0.30 * progress_x + 0.05 * zip_hop
            taper = _smooth(max(0.0, (dash_u - 0.82) / 0.18))
            zigue = 1.0 if passo % 2 == 0 else -0.45
            return IntroFrame(
                offset_x=self.side * alcance * (1.0 - progress_x),
                offset_y=-24.0 * zip_hop,
                scale=lunge_scale,
                roll=self.side * (-18.0 * zigue * (1.0 - 0.45 * taper) - 5.5 * zip_hop),
                yaw=self.side * (-28.0 + 12.0 * taper) * (0.85 if passo % 2 == 0 else 1.05),
                pitch=15.0 * (1.0 - 0.55 * taper) + 5.0 * zip_hop,
                afterimage=1.0,
                locomotion="run",
                finished=False,
            )
        if p < 0.78:
            freio_u = (p - 0.60) / 0.18
            deslize = 1.0 - _quintic(freio_u)
            whip = sin(freio_u * pi)
            return IntroFrame(
                offset_x=-self.side * 36.0 * whip,
                scale=1.0 + 0.055 * whip,
                roll=self.side * (-8.5 * deslize + 8.0 * whip),
                yaw=self.side * -18.0 * deslize,
                pitch=6.0 * deslize - 14.0 * whip,
                afterimage=max(0.0, 1.0 - freio_u * 1.25),
                locomotion="land",
                finished=False,
            )
        settle_u = _clamp01((p - 0.78) / 0.22)
        rebound = sin(settle_u * pi) * (1.0 - settle_u)
        return IntroFrame(
            scale=1.0 + 0.022 * rebound,
            pitch=3.0 * rebound,
            locomotion="ajeitar_fone" if p < 0.96 else "idle",
            finished=done,
        )

    def _sample_kagebunshin_in(self, p: float, done: bool) -> IntroFrame:
        if p < 0.16:
            smoke_p = p / 0.16
            return IntroFrame(
                scale=0.68,
                dissolve=1.0,
                smoke_burst=min(1.0, 0.68 + smoke_p * 0.32),
                locomotion="land",
                finished=False,
            )
        drop_p = _quintic((p - 0.16) / 0.38)
        smoke_fade = max(0.0, 1.0 - max(0.0, p - 0.32) / 0.64)
        etapa = int(min(4, max(0, (p - 0.16) / 0.08)))
        dissolve = max(0.0, 1.0 - etapa / 4.0) if p < 0.48 else 0.0
        if p < 0.54:
            arc = sin(_clamp01((p - 0.16) / 0.38) * pi)
            return IntroFrame(
                offset_y=-20.0 * arc,
                scale=0.68 + 0.42 * drop_p + 0.04 * arc,
                roll=self.side * 6.5 * (1.0 - drop_p),
                yaw=self.side * -22.0 * (1.0 - drop_p),
                pitch=12.0 * arc - 9.0 * (1.0 - drop_p),
                dissolve=dissolve,
                smoke_burst=smoke_fade,
                locomotion="land",
                finished=False,
            )
        land_u = _clamp01((p - 0.54) / 0.46)
        eased_settle = _quintic(land_u)
        squash = sin(min(1.0, land_u / 0.45) * pi)
        bounce = sin(land_u * pi) * (1.0 - land_u * 0.40)
        return IntroFrame(
            scale=1.10 - 0.10 * eased_settle - 0.055 * squash + 0.03 * bounce,
            pitch=-7.5 * squash if p > 0.72 else 8.0 * squash,
            smoke_burst=smoke_fade,
            locomotion="land" if p < 0.68 else ("wave" if p < 0.92 else "idle"),
            finished=done,
        )

    def sample(self, elapsed: float) -> IntroFrame:
        """Amostra o quadro de abertura no instante ``elapsed`` (segundos)."""
        if self.style == "padrao" or self.duration <= 0.0:
            return IntroFrame(finished=True)

        p = _clamp01(elapsed / self.duration)
        done = elapsed >= self.duration
        if self.style == "fade_in":
            return self._sample_fade_in(p, done)
        if self.style == "virtual_insanity_in":
            return self._sample_virtual_insanity_in(p, done)
        if self.style == "run_from_depth":
            return self._sample_run_from_depth(elapsed, p, done)
        if self.style == "sandevistan_in":
            return self._sample_sandevistan_in(p, done)
        return self._sample_kagebunshin_in(p, done)
