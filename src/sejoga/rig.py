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
def pose_idle(rig: Rig, t: float) -> None:
    """Balanço suave do corpo + respiração da cabeça."""
    from math import sin

    sway = sin(t * 1.6)
    rig.set_rotation("body", y=sway * 2.0, z=sway * 1.5)
    rig.set_rotation("head", x=sin(t * 1.1) * 1.2, y=sin(t * 0.7) * 3.0)
    rig.set_rotation("door", y=sin(t * 0.9) * 2.0)


def pose_walk(rig: Rig, t: float) -> None:
    """Passada simples alternando braços e pés."""
    from math import sin

    s = sin(t * 6.0)
    rig.set_rotation("legs", x=s * 4.0)
    rig.set_rotation("right-arm", x=s * 12.0)
    rig.set_rotation("left-arm", x=-s * 12.0)
    rig.set_rotation("head", y=s * 2.0)


def pose_wave(rig: Rig, t: float) -> None:
    """Aceno: braço direito sobe e o antebraço oscila."""
    from math import sin

    rig.set_rotation("right-arm", z=-95.0, x=-15.0)
    rig.set_rotation("ant-arm", x=sin(t * 8.0) * 25.0)
    rig.set_rotation("head", z=6.0)


def pose_dance(rig: Rig, t: float, intensity: float = 0.6) -> None:
    """Dança reativa a batida; ``intensity`` 0..1 amortece a amplitude."""
    from math import sin

    amp = 6.0 + 18.0 * max(0.0, min(1.0, intensity))
    beat = sin(t * 9.0)
    rig.set_rotation("body", y=beat * amp * 0.5, z=sin(t * 4.5) * amp * 0.4)
    rig.set_rotation("head", y=sin(t * 4.5) * amp * 0.6, z=beat * amp * 0.3)
    rig.set_rotation("door", y=sin(t * 4.5) * amp * 0.4)
    rig.set_rotation("right-arm", x=beat * amp, z=-20.0)
    rig.set_rotation("left-arm", x=-beat * amp, z=20.0)


def pose_thrown(rig: Rig) -> None:
    """Pose de "sendo arremessado": braços para cima e pernas soltas."""
    rig.set_rotation("right-arm", x=-35.0, z=-40.0)
    rig.set_rotation("left-arm", x=-35.0, z=40.0)
    rig.set_rotation("legs", x=-12.0)
    rig.set_rotation("head", x=-10.0)
