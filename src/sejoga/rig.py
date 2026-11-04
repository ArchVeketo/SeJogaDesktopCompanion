"""Catálogo do rig e utilitários de animação procedural.

O modelo do Mário (export Blockbench 4.12.4) **não tem skin**: os grupos
``head``, ``door``, ``shoulder``... são nós de transformação. Isso permite
animar em Python sem nenhum clip pré-autorado:

    rig.set_rotation("head", yaw=8)      # olha para o lado
    rig.set_rotation("door", yaw=-90)    # abre a portinha

A camada de render só precisa ler ``rig.pose()`` e aplicar nos nós do engine.

Os nomes abaixo foram extraídos do arquivo real (``tools/inspect_model.py``);
``tests/test_model.py`` garante que continuam presentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import radians

from .model import Model

#: Grupos que formam o rig animável, por região do corpo.
HEAD_GROUPS = ("head", "door")
BODY_GROUPS = ("body", "legs")
ARM_GROUPS = ("right-arm", "left-arm")
ARM_SUBGROUPS = (
    "shoulder",
    "shoulder2",
    "ant-arm",
    "ant-arm2",
    "hand",
    "hand2",
    "fingers",
    "fingers2",
)
FOOT_GROUPS = ("left-feet", "right-feet")

ALL_GROUPS = HEAD_GROUPS + BODY_GROUPS + ARM_GROUPS + ARM_SUBGROUPS + FOOT_GROUPS


class IdlePersonality(StrEnum):
    CALM = "calm"
    CURIOUS = "curious"
    PLAYFUL = "playful"
    SHY = "shy"
    CONFIDENT = "confident"


@dataclass(frozen=True, slots=True)
class Rotation3:
    """Rotação em radianos (eixo Y = "olhar para os lados")."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Rig:
    """Estado de pose por nome de grupo.

    ``rest`` guarda o estado inicial lido do modelo, para que qualquer pose
    seja relativa (evita "deriva" acumulada entre animações).
    """

    rest: dict[str, Rotation3] = field(default_factory=dict)
    current: dict[str, Rotation3] = field(default_factory=dict)

    @classmethod
    def from_model(cls, model: Model) -> Rig:
        rig = cls()
        for group in ALL_GROUPS:
            if model.find(group) is not None:
                rig.rest[group] = Rotation3()
                rig.current[group] = Rotation3()
        return rig

    @property
    def groups(self) -> tuple[str, ...]:
        return tuple(self.rest)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(g for g in ALL_GROUPS if g not in self.rest)

    def set_rotation(
        self,
        group: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        degrees: bool = True,
    ) -> None:
        """Define a rotação *absoluta* do grupo (em graus por padrão)."""
        if group not in self.rest:
            raise KeyError(f"grupo de rig desconhecido: {group!r}")
        if degrees:
            x, y, z = radians(x), radians(y), radians(z)
        self.current[group] = Rotation3(x, y, z)

    def pose(self) -> dict[str, Rotation3]:
        """Snapshot imutável para o renderizador."""
        return dict(self.current)

    def reset(self) -> None:
        self.current = dict(self.rest)


# --------------------------------------------------------------------------- #
# Presets de pose — ponto de partida para as animações do companion
# --------------------------------------------------------------------------- #
def pose_idle(
    rig: Rig,
    t: float,
    personality: IdlePersonality = IdlePersonality.CALM,
) -> None:
    """Idle com personalidade própria, sem deixar de respeitar a dobradiça."""
    from math import cos, sin

    breath = sin(t * 0.8)
    sway = sin(t * 0.55)

    if personality == IdlePersonality.CURIOUS:
        look = sin(t * 0.7)
        tilt = sin(t * 0.39)
        door_open = max(0.0, sin(t * 0.42))
        rig.set_rotation("body", x=breath * 1.1, y=sway * 2.0, z=tilt * 1.5)
        rig.set_rotation("head", x=-4.0 + sin(t * 0.9) * 2.0, y=look * 15.0, z=tilt * 7.0)
        rig.set_rotation("door", y=door_open * 24.0)
        rig.set_rotation("right-arm", x=sin(t * 0.8) * 5.0, z=42.0)
        rig.set_rotation("left-arm", x=-sin(t * 0.8) * 3.0, z=-22.0)
        rig.set_rotation("ant-arm", x=4.0 + sin(t * 0.9) * 7.0, z=tilt * 8.0)
        rig.set_rotation("ant-arm2", x=4.0 - sin(t * 0.9) * 4.0, z=-tilt * 5.0)
    elif personality == IdlePersonality.PLAYFUL:
        bounce = sin(t * 2.0)
        door_open = max(0.0, sin(t * 2.0))
        rig.set_rotation("body", x=abs(bounce) * 3.2, y=sway * 3.0, z=bounce * 3.0)
        rig.set_rotation("head", x=-abs(bounce) * 2.5, y=sin(t * 1.0) * 7.0, z=bounce * 4.0)
        rig.set_rotation("door", y=door_open * 38.0)
        rig.set_rotation("right-arm", x=bounce * 12.0, z=66.0)
        rig.set_rotation("left-arm", x=-bounce * 12.0, z=-66.0)
        rig.set_rotation("ant-arm", x=sin(t * 2.0 + 0.5) * 13.0, z=bounce * 10.0)
        rig.set_rotation("ant-arm2", x=-sin(t * 2.0 + 0.5) * 13.0, z=-bounce * 10.0)
    elif personality == IdlePersonality.SHY:
        peek = max(0.0, sin(t * 0.36))
        rig.set_rotation("body", x=1.0 + breath * 0.7, y=-3.0 + sway * 1.2, z=-2.0)
        rig.set_rotation("head", x=8.0 + breath, y=sin(t * 0.42) * 5.0, z=-6.0 + sway * 2.0)
        rig.set_rotation("door", y=peek * 13.0)
        rig.set_rotation("right-arm", x=3.0, z=82.0)
        rig.set_rotation("left-arm", x=-3.0, z=-82.0)
        rig.set_rotation("ant-arm", x=10.0 + breath, z=sin(t * 0.7) * 3.0)
        rig.set_rotation("ant-arm2", x=10.0 + breath, z=-sin(t * 0.7) * 3.0)
    elif personality == IdlePersonality.CONFIDENT:
        nod = sin(t * 0.46)
        rig.set_rotation("body", x=-2.5 + breath * 0.8, y=sway * 1.0, z=sin(t * 0.34) * 1.5)
        rig.set_rotation("head", x=-5.0 + nod * 2.0, y=sin(t * 0.32) * 5.0, z=nod * 2.0)
        rig.set_rotation("door", y=max(0.0, sin(t * 0.28)) * 18.0)
        rig.set_rotation("right-arm", x=1.0, z=54.0)
        rig.set_rotation("left-arm", x=-1.0, z=-54.0)
        rig.set_rotation("ant-arm", x=2.0 + sin(t * 0.5) * 3.0, z=2.0)
        rig.set_rotation("ant-arm2", x=2.0 - sin(t * 0.5) * 3.0, z=-2.0)
    else:
        door_open = (1.0 - cos(t * 0.75)) * 0.5
        rig.set_rotation("body", x=breath * 1.1, y=sway * 1.7, z=sway * 1.2)
        rig.set_rotation("head", x=sin(t * 0.7) * 1.5, y=sin(t * 0.48) * 3.5)
        rig.set_rotation("door", y=door_open * 40.0)
        rig.set_rotation("right-arm", x=sin(t * 0.7) * 3.0, z=28.0 - breath * 2.0)
        rig.set_rotation("left-arm", x=-sin(t * 0.7) * 3.0, z=-28.0 + breath * 2.0)
        rig.set_rotation("ant-arm", x=4.0, z=sin(t * 0.9) * 5.0)
        rig.set_rotation("ant-arm2", x=4.0, z=-sin(t * 0.9) * 5.0)


def pose_walk(rig: Rig, t: float, *, run: bool = False) -> None:
    """Passada alternada com braços, antebraços, pés e balanço do tronco."""
    from math import sin

    frequency = 2.5 if run else 1.5
    stride_angle = 11.0 if run else 7.0
    arm_angle = 24.0 if run else 16.0
    stride = sin(t * 2.0 * 3.141592653589793 * frequency)
    rig.set_rotation("legs", x=stride * stride_angle)
    rig.set_rotation("left-feet", x=-stride * stride_angle * 1.25)
    rig.set_rotation("right-feet", x=stride * stride_angle * 1.25)
    rig.set_rotation("right-arm", x=-stride * arm_angle, z=9.0 if run else 7.0)
    rig.set_rotation("left-arm", x=stride * arm_angle, z=-9.0 if run else -7.0)
    rig.set_rotation("ant-arm", x=-stride * arm_angle * 0.65)
    rig.set_rotation("ant-arm2", x=stride * arm_angle * 0.65)
    rig.set_rotation("body", x=4.0 if run else 1.5, z=stride * (4.0 if run else 2.0))
    rig.set_rotation("head", x=5.0 if run else 0.0, y=-stride * 3.5)


def pose_wave(rig: Rig, t: float) -> None:
    """Aceno: braço direito sobe e o antebraço oscila."""
    from math import sin

    rig.set_rotation("right-arm", z=95.0, x=-15.0)
    rig.set_rotation("ant-arm", x=sin(t * 8.0) * 25.0)
    rig.set_rotation("head", z=6.0)


def pose_dance(rig: Rig, t: float, intensity: float = 0.6) -> None:
    """Dança reativa a batida; ``intensity`` 0..1 amortece a amplitude."""
    from math import sin

    amp = 6.0 + 18.0 * max(0.0, min(1.0, intensity))
    beat = sin(t * 9.0)
    rig.set_rotation("body", y=beat * amp * 0.5, z=sin(t * 4.5) * amp * 0.4)
    rig.set_rotation("head", y=sin(t * 4.5) * amp * 0.6, z=beat * amp * 0.3)
    # A porta pulsa para fora no beat; os braços ficam mais recolhidos junto
    # ao tronco em vez de abrir para cima e para os lados.
    door_open = max(0.0, sin(t * 4.5))
    rig.set_rotation("door", y=door_open * 48.0)
    rig.set_rotation("right-arm", x=beat * amp, z=70.0)
    rig.set_rotation("left-arm", x=-beat * amp, z=-70.0)
    rig.set_rotation("ant-arm", z=-12.0 + beat * amp * 0.55)
    rig.set_rotation("ant-arm2", z=12.0 - beat * amp * 0.55)
    rig.set_rotation("legs", x=sin(t * 9.0) * amp * 0.25)


def pose_drag(rig: Rig, t: float, direction: float = 0.0) -> None:
    """Inclina-se na direção do arraste e estende os braços para se equilibrar."""
    from math import sin

    direction = max(-1.0, min(1.0, direction))
    rig.set_rotation("body", y=-direction * 10.0, z=direction * 8.0)
    rig.set_rotation("head", y=direction * 5.0, z=-direction * 3.0)
    rig.set_rotation("right-arm", x=-8.0 + sin(t * 5.0) * 3.0, z=-24.0)
    rig.set_rotation("left-arm", x=8.0 - sin(t * 5.0) * 3.0, z=24.0)
    rig.set_rotation("ant-arm", x=-12.0, z=-direction * 8.0)
    rig.set_rotation("ant-arm2", x=-12.0, z=-direction * 8.0)


def pose_sleep(rig: Rig, t: float) -> None:
    """Pose repousada com respiração lenta."""
    from math import sin

    breath = sin(t * 0.75)
    rig.set_rotation("body", x=1.5 + breath * 0.6, z=-2.0)
    rig.set_rotation("head", x=12.0 + breath * 0.8, y=4.0)
    rig.set_rotation("right-arm", x=10.0, z=-12.0)
    rig.set_rotation("left-arm", x=10.0, z=12.0)
    rig.set_rotation("ant-arm", x=8.0)
    rig.set_rotation("ant-arm2", x=8.0)


def pose_thrown(rig: Rig, t: float = 0.0) -> None:
    """Pose de queda com braços abertos e pequenas oscilações no ar."""
    from math import sin

    wobble = sin(t * 8.0)
    rig.set_rotation("right-arm", x=-28.0 + wobble * 5.0, z=-42.0)
    rig.set_rotation("left-arm", x=-28.0 - wobble * 5.0, z=42.0)
    rig.set_rotation("ant-arm", x=-18.0 - wobble * 8.0)
    rig.set_rotation("ant-arm2", x=-18.0 + wobble * 8.0)
    rig.set_rotation("legs", x=-12.0 + wobble * 3.0)
    rig.set_rotation("head", x=-8.0, y=wobble * 4.0)
