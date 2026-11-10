"""Catálogo do rig e utilitários de animação procedural.

O modelo do Mário (export Blockbench 4.12.4) **não tem skin**: os grupos
``head``, ``door``, ``shoulder``... são nós de transformação. Isso permite
animar em Python sem nenhum clip pré-autorado:

    rig.set_rotation("head", yaw=8)      # olha para o lado
    rig.set_rotation("door", yaw=-90)    # abre a portinha

A camada de render só precisa ler ``rig.pose()`` e aplicar nos nós do engine.

Os nomes abaixo foram extraídos do arquivo real (``tools/inspect_model.py``);
``tests/test_modelo.py`` garante que continuam presentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import radians

from sejoga.nucleo.modelo import Model

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
    STREET = "street"
    FIGHTER = "fighter"
    RHYTHM = "rhythm"
    STYLISH = "stylish"


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
