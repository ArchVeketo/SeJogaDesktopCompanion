"""Animação de saída e encerramento ("morte") do mascote para fora do desktop."""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import pi, sin, sqrt
from typing import ClassVar

from sejoga.animacao.dados_autorais import reacoes_ativas

EXIT_STYLES = (
    "classic",
    "sonic_classic",
    "fnf_blue_balls",
    "lego_disassemble",
    "thanos_snap",
    "peace_fade_out",
    "virtual_insanity_out",
    "cyberpsicopata_out",
    "goku_teleport_out",
    "portal_pull_out",
    "aleatoria",
)

_RANDOM_DEATH_POOL = (
    "sonic_classic",
    "fnf_blue_balls",
    "lego_disassemble",
    "thanos_snap",
    "peace_fade_out",
    "virtual_insanity_out",
    "cyberpsicopata_out",
    "goku_teleport_out",
    "portal_pull_out",
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _smooth(value: float) -> float:
    u = _clamp01(value)
    return _clamp01(u * u * u * (10.0 + u * (-15.0 + 6.0 * u)))


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
    glitch_offset: float = 0.0
    glitch_pulse: float = 0.0
    dissolve_mode: float = 0.0
    warp_scale: tuple[float, float, float] = (1.0, 1.0, 1.0)


class ExitAnimation:
    """Anima a saída/encerramento do mascote conforme o estilo configurado."""

    DURATION = 1.35
    HIT_STOP = 0.14
    STYLE_DURATIONS: ClassVar[dict[str, float]] = {
        "classic": 1.35,
        "sonic_classic": 1.45,
        "fnf_blue_balls": 2.35,
        "lego_disassemble": 1.95,
        "thanos_snap": 2.05,
        "peace_fade_out": 1.55,
        "virtual_insanity_out": 1.80,
        "cyberpsicopata_out": 2.45,
        "goku_teleport_out": 1.45,
        "portal_pull_out": 1.50,
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
        saida_cfg = reacoes_ativas().get("saidas", {}).get(style, {})
        vel = max(0.1, float(saida_cfg.get("velocidade", 1.0)))
        dur_base = float(saida_cfg.get("duracao_s", self.STYLE_DURATIONS[style]))
        self.duration = dur_base / vel
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
        if elapsed < self.HIT_STOP:
            ant = sin(_clamp01(elapsed / max(1e-4, self.HIT_STOP)) * pi)
            wz = 1.0 - 0.09 * ant
            wxy = sqrt(1.0 / wz)
            return ExitFrame(
                round(self.origin[0] - self.direction * 6.0 * ant),
                round(self.origin[1] + 5.0 * ant),
                -self.direction * 7.0 * ant,
                False,
                pitch=6.0 * ant,
                warp_scale=(wxy, wxy, wz),
            )
        move_duration = max(0.15, self.duration - self.HIT_STOP)
        progress = _clamp01((elapsed - self.HIT_STOP) / move_duration)
        x = self.origin[0] + (self.exit_x - self.origin[0]) * progress * progress
        y = self.origin[1] + 540 * progress * (progress - 0.72)
        giro = 1080 * progress**1.25
        impulso = sin(pi * _clamp01(progress / 0.30))
        wz = 1.0 - 0.09 * impulso
        wxy = sqrt(1.0 / wz)
        return ExitFrame(
            round(x), round(y), self.direction * giro, done,
            warp_scale=(wxy, wxy, wz),
        )

    def _sample_sonic_classic(self, elapsed: float, p: float, done: bool) -> ExitFrame:
        ox, oy = self.origin
        if p < 0.14:
            u = p / 0.14
            coil = sin(u * pi)
            jitter = sin(elapsed * 58.0) * 3.0 * coil
            return ExitFrame(
                round(ox + jitter),
                round(oy + 10.0 * coil),
                0.0,
                False,
                pitch=8.0 * coil - 8.0 * _smooth(u),
                scale=1.0 + 0.05 * _smooth(u) - 0.10 * coil,
                locomotion="hit",
            )
        jump_u = (p - 0.14) / 0.86
        if jump_u < 0.28:
            rise = sin((jump_u / 0.28) * (pi * 0.5))
            return ExitFrame(
                round(ox),
                round(oy - 180.0 * rise),
                self.direction * 42.0 * rise,
                done,
                pitch=-8.0 - 12.0 * rise,
                scale=1.05 - 0.05 * rise,
                locomotion="hit",
            )
        fall_u = (jump_u - 0.28) / 0.72
        peak_y = oy - 180.0
        drop_y = peak_y + (self.bottom_exit_y - peak_y) * (fall_u * fall_u)
        return ExitFrame(
            round(ox + 28.0 * self.direction * fall_u),
            round(drop_y),
            self.direction * (42.0 + 480.0 * fall_u),
            done,
            pitch=-20.0 + 42.0 * fall_u,
            locomotion="fall",
        )

    def _sample_fnf_blue_balls(self, elapsed: float, p: float, done: bool) -> ExitFrame:
        ox, oy = self.origin
        if p < 0.22:
            u = _smooth(p / 0.22)
            carga = sin(_clamp01(p / 0.22) * pi)
            tremor = sin(elapsed * 39.0) * 4.0 * carga
            return ExitFrame(
                round(ox + tremor),
                round(oy),
                0.0,
                False,
                blue_balls=0.28 * u,
                locomotion="blue_balls",
                shock=0.24 * carga,
            )
        if p < 0.78:
            pop_u = _clamp01((p - 0.22) / 0.14)
            pop_e = _smooth(pop_u)
            beat = 0.82 + 0.18 * (0.5 + 0.5 * sin((elapsed - 0.5) * 8.5))
            pop_boost = 1.0 + 0.14 * sin(pop_u * pi)
            alvo_bb = min(1.0, beat * pop_boost)
            # Costura C0/C1 contínua a partir de 0.28 em p=0.22
            bb = 0.28 * (1.0 - pop_e) + alvo_bb * pop_e
            return ExitFrame(
                round(ox),
                round(oy),
                0.0,
                False,
                blue_balls=bb,
                locomotion="blue_balls",
                shock=0.0,
            )
        fade_u = _smooth((p - 0.78) / 0.22)
        beat = 0.82 + 0.18 * (0.5 + 0.5 * sin((elapsed - 0.5) * 8.5))
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
        if p < 0.10:
            carga = sin((p / 0.10) * pi)
            jitter = sin(elapsed * 55.0) * 3.5 * carga
            anticipation = carga * 0.06
            return ExitFrame(
                round(ox + jitter),
                round(oy),
                0.0,
                False,
                scale=1.0 + anticipation,
                locomotion="hit",
            )
        explode = _smooth((p - 0.10) / 0.62)
        return ExitFrame(
            round(ox),
            round(oy),
            0.0,
            done,
            explode=explode,
            dissolve=_smooth(max(0.0, p - 0.80) / 0.20),
            locomotion="hit",
        )

    def _sample_thanos_snap(self, _elapsed: float, p: float, done: bool) -> ExitFrame:
        ox, oy = self.origin
        if p < 0.22:
            u = _smooth(p / 0.22)
            return ExitFrame(
                round(ox),
                round(oy),
                -3.0 * u,
                False,
                yaw=-14.0 * u,
                pitch=5.0 * u,
                locomotion="open_hands",
            )
        dust_u = _clamp01((p - 0.22) / 0.78)
        pitch_settle = 5.0 * (1.0 - _smooth(min(1.0, dust_u / 0.35)))
        drift = dust_u**1.32
        return ExitFrame(
            round(ox + 34.0 * self.direction * drift),
            round(oy - 14.0 * drift),
            -3.0 + 6.5 * self.direction * drift,
            done,
            yaw=-14.0 + 20.0 * dust_u,
            pitch=pitch_settle,
            dissolve=_smooth(dust_u),
            ash=dust_u,
            locomotion="open_hands",
        )

    def _sample_peace_fade_out(self, _elapsed: float, p: float, done: bool) -> ExitFrame:
        ox, oy = self.origin
        fade_u = _smooth(max(0.0, p - 0.42) / 0.58)
        nod = sin(_smooth(p / 0.48) * pi)
        lean = _smooth(min(1.0, p / 0.50))
        return ExitFrame(
            round(ox + 8.0 * self.direction * fade_u),
            round(oy - 8.0 * fade_u),
            -4.5 * self.direction * lean * (1.0 - 0.4 * fade_u),
            done,
            yaw=-8.5 * nod,
            pitch=-5.0 * nod,
            dissolve=fade_u,
            locomotion="peace",
        )

    def _sample_virtual_insanity_out(self, _elapsed: float, p: float, done: bool) -> ExitFrame:
        ox, oy = self.origin
        glide = _smooth(p) * 0.25 + (p * p) * 0.75
        x = ox + (self.exit_x - ox) * glide
        lean = _smooth(min(1.0, p / 0.35)) * (1.0 - _smooth(max(0.0, p - 0.75) / 0.25))
        return ExitFrame(
            round(x),
            round(oy),
            -7.5 * self.direction * lean,
            done,
            yaw=self.direction * 14.0 * lean,
            pitch=-3.5 * sin(p * pi) + 2.0 * sin(p * 2.0 * pi) * lean,
            dissolve=_smooth(max(0.0, p - 0.76) / 0.24),
            locomotion="virtual_insanity",
        )

    def _sample_cyberpsicopata_out(self, elapsed: float, p: float, done: bool) -> ExitFrame:
        ox, oy = self.origin
        # Fase 1 (0..0.28): sobrecarga neural súbita — cabeça joga para trás em choque e pulso ciano/carmesim.
        if p < 0.28:
            u = _smooth(p / 0.28)
            tremor = sin(elapsed * 42.0) * (3.5 + 5.0 * u)
            return ExitFrame(
                round(ox + tremor),
                round(oy - 4.0 * u),
                -7.5 * u + sin(elapsed * 32.0) * 3.0,
                False,
                yaw=-22.0 * u + sin(elapsed * 21.0) * 6.0,
                pitch=-14.0 * u,
                glitch_offset=0.75 + 0.35 * u,
                glitch_pulse=0.45 + 0.50 * abs(sin(elapsed * 22.0)),
                shock=0.45 * u,
                locomotion="surprise",
            )
        # Fase 2 (0.28..0.68): teletransportes de glitch quantizados (±28px) com costura de entrada/saída.
        if p < 0.68:
            u = (p - 0.28) / 0.40
            in_blend = _smooth(min(1.0, (p - 0.28) / 0.08))
            out_blend = _smooth(max(0.0, (p - 0.60) / 0.08))
            slot = int(p * 18.0)
            snap_step = (((slot * 7) % 5) - 2) * 14.0
            snap_y = (((slot * 11) % 3) - 1) * 7.0
            espasmos = sin(elapsed * 48.0)
            deslize = sin(u * pi) * 12.0 * self.direction
            env_f2 = in_blend * (1.0 - out_blend)
            roll_ini = -7.5 + sin(elapsed * 32.0) * 3.0
            yaw_ini = -22.0 + sin(elapsed * 21.0) * 6.0
            roll_f2 = roll_ini * (1.0 - in_blend) + (
                espasmos * 9.5 - 7.0 * self.direction * u
            ) * env_f2
            yaw_f2 = yaw_ini * (1.0 - in_blend) + (
                (18.0 * espasmos - 14.0 * u * self.direction) * (1.0 - out_blend)
                + (-12.0 * self.direction) * out_blend
            ) * in_blend
            pitch_f2 = -14.0 + 30.0 * _smooth(u)
            return ExitFrame(
                round(ox + (deslize + snap_step) * env_f2),
                round(oy - 4.0 * (1.0 - in_blend) + snap_y * env_f2),
                roll_f2,
                False,
                yaw=yaw_f2,
                pitch=pitch_f2,
                shock=0.45 * (1.0 - in_blend) + (0.72 + 0.28 * abs(espasmos)) * in_blend,
                glitch_offset=1.10 + 0.05 * in_blend,
                glitch_pulse=0.72 + 0.28 * abs(sin(elapsed * 30.0)),
                locomotion="hit" if p < 0.56 else "fall",
            )
        # Fase 3 (0.68..1.0): desintegração holográfica em scanlines e fagulhas ciano/carmesim.
        fade_u = _smooth((p - 0.68) / 0.32)
        entrada_ruido = _smooth((p - 0.68) / 0.045)
        jitter_fin = sin(elapsed * 60.0) * 8.0 * entrada_ruido * (1.0 - fade_u)
        return ExitFrame(
            round(ox + 10.0 * self.direction * fade_u + jitter_fin),
            round(oy - 10.0 * fade_u),
            -10.0 * fade_u,
            done,
            yaw=-12.0 * self.direction,
            pitch=16.0 + 12.0 * fade_u,
            scale=max(0.84, 1.0 - 0.14 * fade_u),
            dissolve=fade_u,
            ash=fade_u * 0.95,
            shock=max(0.0, 0.85 * (1.0 - fade_u)),
            glitch_offset=max(0.0, 1.05 * (1.0 - fade_u * 0.75)),
            glitch_pulse=max(0.0, 0.92 * (1.0 - fade_u)),
            locomotion="fall",
            dissolve_mode=2.0,
        )

    def _sample_goku_teleport_out(self, _elapsed: float, p: float, done: bool) -> ExitFrame:
        """Saída estilo Teleporte do Goku (Shunkan Idō): dois dedos na testa e sumiço em risco vertical."""
        ox, oy = self.origin
        if p < 0.62:
            u = _smooth(p / 0.62)
            return ExitFrame(
                round(ox),
                round(oy),
                0.0,
                False,
                pitch=-2.5 * sin(u * pi),
                shock=0.45 * u,
                locomotion="goku_teleport",
                dissolve_mode=3.0,
            )
        if p < 0.86:
            u = _smooth((p - 0.62) / 0.24)
            wz = 1.0 + 0.85 * u
            wx = 1.0 / wz
            # Escala encolhe suavemente até 0.05 em p=0.86 sem salto C0
            scale = 1.0 - 0.95 * (u * u)
            return ExitFrame(
                round(ox),
                round(oy),
                0.0,
                False,
                scale=scale,
                dissolve=u,
                shock=(0.45 + 0.36 * sin(u * pi)) * (1.0 - u),
                glitch_offset=0.55 * u,
                glitch_pulse=0.75 * sin(u * pi),
                locomotion="goku_teleport",
                dissolve_mode=3.0,
                warp_scale=(wx, 1.0, wz),
            )
        return ExitFrame(
            round(ox),
            round(oy),
            0.0,
            done,
            scale=0.05,
            dissolve=1.0,
            locomotion="goku_teleport",
            dissolve_mode=3.0,
            warp_scale=(1.0 / 1.85, 1.0, 1.85),
        )

    def _sample_portal_pull_out(self, _elapsed: float, p: float, done: bool) -> ExitFrame:
        """Saída sugada em espiral para fenda dimensional com esticamento e dissolução."""
        ox, oy = self.origin
        if p < 0.34:
            u = _smooth(p / 0.34)
            return ExitFrame(
                round(ox),
                round(oy - 6.0 * u),
                -8.0 * u * self.direction,
                False,
                yaw=22.0 * u * self.direction,
                pitch=-6.0 * u,
                shock=0.35 * u,
                locomotion="surprise",
            )
        u = _smooth((p - 0.34) / 0.66)
        wx = max(0.22, 1.0 - 0.75 * u)
        wz = 1.0 + 0.55 * sin(u * pi)
        return ExitFrame(
            round(ox),
            round(oy - 6.0 - 18.0 * u),
            (-8.0 - 24.0 * u) * self.direction,
            done,
            yaw=(22.0 + 520.0 * u * u) * self.direction,
            pitch=-6.0 + 28.0 * u,
            scale=max(0.08, 1.0 - 0.90 * u),
            dissolve=u,
            ash=u * 0.88,
            shock=(0.35 + 0.26 * sin(u * pi)) * (1.0 - u),
            locomotion="fall",
            dissolve_mode=1.0,
            warp_scale=(wx, wx, wz),
        )


_STYLE_SAMPLERS = {
    "classic": ExitAnimation._sample_classic,
    "sonic_classic": ExitAnimation._sample_sonic_classic,
    "fnf_blue_balls": ExitAnimation._sample_fnf_blue_balls,
    "lego_disassemble": ExitAnimation._sample_lego_disassemble,
    "thanos_snap": ExitAnimation._sample_thanos_snap,
    "peace_fade_out": ExitAnimation._sample_peace_fade_out,
    "virtual_insanity_out": ExitAnimation._sample_virtual_insanity_out,
    "cyberpsicopata_out": ExitAnimation._sample_cyberpsicopata_out,
    "goku_teleport_out": ExitAnimation._sample_goku_teleport_out,
    "portal_pull_out": ExitAnimation._sample_portal_pull_out,
}
