"""Animações procedurais de entrada (abertura) do mascote, sem dependências de engine."""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import cos, pi, sin, sqrt
from typing import ClassVar

from sejoga.animacao.dados_autorais import reacoes_ativas

INTRO_STYLES = (
    "padrao",
    "fade_in",
    "virtual_insanity_in",
    "run_from_depth",
    "kagebunshin_in",
    "sandevistan_in",
    "goku_teleport_in",
    "hero_drop_in",
    "aleatoria",
)

_RANDOM_POOL = (
    "fade_in",
    "virtual_insanity_in",
    "run_from_depth",
    "kagebunshin_in",
    "sandevistan_in",
    "goku_teleport_in",
    "hero_drop_in",
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _smooth(value: float) -> float:
    u = _clamp01(value)
    return u * u * (3.0 - 2.0 * u)


def _quintic(value: float) -> float:
    u = _clamp01(value)
    return _clamp01(u * u * u * (10.0 + u * (-15.0 + 6.0 * u)))


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
    dissolve_mode: float = 0.0
    warp_scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    door_open: float = 0.0
    head_yaw: float = 0.0


class IntroAnimation:
    """Produz a sequência de abertura escolhida até pousar no desktop."""

    DURATIONS: ClassVar[dict[str, float]] = {
        "padrao": 0.0,
        "fade_in": 2.35,
        "virtual_insanity_in": 3.55,
        "run_from_depth": 2.60,
        "kagebunshin_in": 2.45,
        "sandevistan_in": 2.15,
        "goku_teleport_in": 1.65,
        "hero_drop_in": 1.55,
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
        # O olhar encontra o usuário antes de o corpo completar a virada.
        olhar = _quintic((p - 0.16) / 0.20) * (1.0 - _quintic((p - 0.46) / 0.23))
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
            head_yaw=-self.side * 13.0 * olhar,
            dissolve=dissolve,
            locomotion=loco if not done else "idle",
            finished=done,
        )

    def _sample_virtual_insanity_in(self, p: float, done: bool) -> IntroFrame:
        dissolve = max(0.0, 1.0 - _quintic(p / 0.09))
        overshoot = 30.0
        if p < 0.76:
            u = _clamp01(p / 0.76)
            u_q = _quintic(u)
            groove = u_q + 0.065 * sin(u * 2.0 * pi) * u * (1.0 - u)
            offset_x = self.side * (
                self.entry_distance * (1.0 - groove)
                - overshoot * _quintic(max(0.0, (p - 0.56) / 0.20))
            )
            mid_arc = sin(u * pi)
            roll = self.side * (-9.0 * mid_arc - 2.5 * sin(u * 3.0 * pi) * (1.0 - u))
            yaw = self.side * (16.0 * (1.0 - u_q) - 4.0 * mid_arc)
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
            head_yaw=-self.side * 15.0 * _quintic((p - 0.07) / 0.18)
            * (1.0 - _quintic((p - 0.62) / 0.31)),
            dissolve=dissolve,
            locomotion="virtual_insanity" if p < 0.80 else "idle",
            finished=done,
        )

    def _sample_run_from_depth(self, elapsed: float, p: float, done: bool) -> IntroFrame:
        if p < 0.64:
            run_u = p / 0.64
            depth = run_u**1.42
            arc = sin(run_u * pi)
            # Passadas C∞ contínuas (sem quina V de abs(sin))
            hop = (0.5 - 0.5 * cos(run_u * 6.0 * pi)) * 18.0 * (0.3 + 0.7 * run_u)
            pitch_run = 12.0 - 9.0 * _quintic(run_u)
            return IntroFrame(
                offset_x=self.side * (78.0 * (1.0 - depth) + 24.0 * arc),
                offset_y=-hop,
                scale=0.16 + 0.88 * depth,
                roll=sin(elapsed * 16.0) * 4.4 * (1.0 - _quintic((run_u - 0.78) / 0.22)),
                yaw=self.side * -14.0 * arc,
                pitch=pitch_run,
                dissolve=max(0.0, 1.0 - _quintic(p / 0.10)),
                locomotion="run",
                finished=done,
            )
        if p < 0.80:
            brake_u = (p - 0.64) / 0.16
            skid = sin(brake_u * pi)
            roll_blend = _quintic(brake_u)
            return IntroFrame(
                scale=1.04 - 0.04 * roll_blend,
                roll=self.side * (2.5 * skid * (1.0 - roll_blend)),
                pitch=3.0 * (1.0 - roll_blend) - 10.5 * skid,
                warp_scale=(1.0 + 0.085 * skid, 1.0 + 0.060 * skid, 1.0 - 0.11 * skid),
                head_yaw=-self.side * 8.0 * skid,
                locomotion="land",
                finished=done,
            )
        settle_u = _quintic((p - 0.80) / 0.20)
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
            # Cada corte Sandevistan dispara rápido e segura em micro hit-stop no ápice.
            explosao = _quintic(min(1.0, sub / 0.58))
            pos_passo = (passo + explosao) / passos
            progress_x = pos_passo**0.94
            zip_hop = sin(min(1.0, sub / 0.65) * pi)
            lunge_scale = 0.76 + 0.30 * progress_x + 0.05 * zip_hop
            taper = _quintic(max(0.0, (dash_u - 0.82) / 0.18))
            # Zigue-zague contínuo sem salto de 26° nos cortes de passo (p=0.20 / p=0.40)
            zigue = 0.275 + 0.725 * cos(dash_u * passos * pi)
            yaw_mod = 0.95 - 0.10 * cos(dash_u * passos * pi)
            return IntroFrame(
                offset_x=self.side * alcance * (1.0 - progress_x),
                offset_y=-24.0 * zip_hop,
                scale=lunge_scale,
                roll=self.side * (-18.0 * zigue * (1.0 - 0.45 * taper) - 5.5 * zip_hop),
                yaw=self.side * (-28.0 + 12.0 * taper) * yaw_mod,
                pitch=15.0 * (1.0 - 0.55 * taper) + 5.0 * zip_hop,
                afterimage=1.0,
                locomotion="run",
                finished=False,
            )
        if p < 0.78:
            freio_u = (p - 0.60) / 0.18
            deslize = 1.0 - _quintic(freio_u)
            whip = sin(freio_u * pi)
            # Valores iniciais em freio_u=0 casam exatamente com dash_u=1 (cos(3*pi)=-1 -> zigue=-0.45, yaw_mod=1.05).
            roll_ini = -18.0 * (-0.45) * 0.55
            yaw_ini = -16.0 * 1.05
            return IntroFrame(
                offset_x=-self.side * 36.0 * whip,
                scale=1.06 - 0.06 * _quintic(freio_u) + 0.045 * whip,
                roll=self.side * (roll_ini * deslize + 8.0 * whip),
                yaw=self.side * yaw_ini * deslize,
                pitch=6.75 * deslize - 14.0 * whip,
                warp_scale=(1.0 + 0.07 * whip, 1.0, 1.0 - 0.09 * whip),
                afterimage=max(0.0, 1.0 - _quintic(freio_u * 1.15)),
                locomotion="land",
                finished=False,
            )
        settle_u = _quintic((p - 0.78) / 0.22)
        rebound = sin(settle_u * pi) * (1.0 - settle_u)
        return IntroFrame(
            scale=1.0 + 0.022 * rebound,
            pitch=3.0 * rebound,
            locomotion="ajeitar_fone" if p < 0.96 else "idle",
            finished=done,
        )

    def _sample_kagebunshin_in(self, p: float, done: bool) -> IntroFrame:
        if p < 0.16:
            smoke_p = _quintic(p / 0.16)
            return IntroFrame(
                scale=0.68,
                roll=self.side * 6.5 * smoke_p,
                yaw=self.side * -22.0 * smoke_p,
                pitch=-9.0 * smoke_p,
                dissolve=1.0,
                smoke_burst=min(1.0, 0.68 + smoke_p * 0.32),
                locomotion="idle",
                finished=False,
            )
        drop_p = _quintic((p - 0.16) / 0.38)
        smoke_fade = 1.0 - _quintic((p - 0.30) / 0.60)
        dissolve = max(0.0, 1.0 - _quintic((p - 0.16) / 0.32)) if p < 0.48 else 0.0
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
                locomotion="fall",
                finished=False,
            )
        land_u = _clamp01((p - 0.54) / 0.46)
        eased_settle = _quintic(land_u)
        squash = sin(min(1.0, land_u / 0.45) * pi)
        bounce = sin(land_u * pi) * (1.0 - land_u * 0.40)
        return IntroFrame(
            scale=1.10 - 0.10 * eased_settle + 0.03 * bounce,
            pitch=8.0 * sin(land_u * pi * 2.0) * (1.0 - land_u),
            warp_scale=(1.0 + 0.095 * squash, 1.0, 1.0 - 0.12 * squash),
            head_yaw=self.side * 14.0 * _quintic(land_u / 0.45)
            * (1.0 - _quintic((land_u - 0.55) / 0.36)),
            smoke_burst=smoke_fade,
            locomotion="land" if p < 0.72 else ("wave" if p < 0.92 else "idle"),
            finished=done,
        )

    def _sample_goku_teleport_in(self, p: float, done: bool) -> IntroFrame:
        """Chegada estilo Teleporte do Goku (Shunkan Idō): risco vertical + dois dedos na testa."""
        if p < 0.18:
            u = _quintic(p / 0.18)
            dissolve = max(0.0, 1.0 - u)
            # Risco vertical nítido (wx * wy * wz == 1.0 exatamente) no teleporte Shunkan Idō.
            wz = 1.74 - 0.80 * u
            wx = 1.0 / wz
            return IntroFrame(
                scale=1.0,
                dissolve=dissolve,
                dissolve_mode=3.0,
                smoke_burst=0.0,
                afterimage=1.0 - 0.5 * u,
                locomotion="goku_teleport",
                finished=False,
                warp_scale=(wx, 1.0, wz),
            )
        if p < 0.76:
            hold_t = (p - 0.18) / 0.58
            settle = _quintic(min(1.0, hold_t / 0.30))
            wz = 0.94 + 0.06 * settle
            wx = 1.0 / wz
            # Micro-vida na pose de teleporte (sem congelar 58% da duração) e afterimage contínuo
            after = 0.5 * (1.0 - _quintic(min(1.0, hold_t / 0.24)))
            respiro = sin(hold_t * pi * 2.0) * (1.0 - 0.5 * hold_t)
            return IntroFrame(
                scale=1.0 + 0.012 * respiro,
                dissolve=0.0,
                dissolve_mode=3.0,
                smoke_burst=0.0,
                afterimage=after,
                locomotion="goku_teleport",
                finished=False,
                warp_scale=(wx, 1.0, wz),
                pitch=-5.0 * sin(settle * pi) + 1.4 * respiro,
                head_yaw=self.side * 5.0 * sin(hold_t * pi),
            )
        out_u = _quintic((p - 0.76) / 0.24)
        rebound = sin(out_u * pi) * (1.0 - out_u)
        return IntroFrame(
            scale=1.0 + 0.015 * rebound,
            pitch=1.8 * rebound,
            locomotion="idle",
            finished=done,
        )

    def _sample_hero_drop_in(self, p: float, done: bool) -> IntroFrame:
        """Queda, rebote da porta e olhar de soslaio antes de voltar ao idle."""
        if p < 0.32:
            u = (p / 0.32) ** 2
            late = _quintic((p - 0.24) / 0.08)
            wz = 1.24 - 0.24 * late
            wxy = sqrt(1.0 / wz)
            return IntroFrame(
                offset_y=-215.0 * (1.0 - u),
                scale=0.92 + 0.08 * u,
                pitch=10.0 * u * (1.0 - late),
                locomotion="fall",
                finished=False,
                warp_scale=(wxy, wxy, wz),
            )
        # Pico de squash mais próximo do impacto (p=0.355) com preservação de volume
        squash = _quintic((p - 0.32) / 0.035) * (1.0 - _quintic((p - 0.355) / 0.22))
        door = _quintic((p - 0.34) / 0.10) * (1.0 - _quintic((p - 0.48) / 0.24))
        glance = _quintic((p - 0.55) / 0.16) * (1.0 - _quintic((p - 0.80) / 0.20))
        wz = max(0.83, 1.0 - 0.17 * squash)
        wxy = sqrt(1.0 / wz)
        return IntroFrame(
            pitch=10.0 * squash,
            locomotion="land" if p < 0.68 else "idle",
            finished=done,
            warp_scale=(wxy, wxy, wz),
            door_open=42.0 * door,
            head_yaw=self.side * 22.0 * glance,
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
        if self.style == "goku_teleport_in":
            return self._sample_goku_teleport_in(p, done)
        if self.style == "hero_drop_in":
            return self._sample_hero_drop_in(p, done)
        return self._sample_kagebunshin_in(p, done)
