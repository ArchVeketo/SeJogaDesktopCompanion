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


def _idle_pulse(t: float, period: float, attack: float, hold: float, release: float, offset: float = 0.0) -> float:
    """One eased gesture followed by a readable rest inside an idle loop."""
    phase = (t + offset) % period

    def ease(value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value * value * (3.0 - 2.0 * value)

    if phase < attack:
        return ease(phase / attack)
    phase -= attack
    if phase < hold:
        return 1.0
    phase -= hold
    if phase < release:
        return 1.0 - ease(phase / release)
    return 0.0

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


# --------------------------------------------------------------------------- #
# Presets de pose — ponto de partida para as animações do companion
# --------------------------------------------------------------------------- #
def pose_idle(
    rig: Rig,
    t: float,
    personality: IdlePersonality = IdlePersonality.CALM,
) -> None:
    """Idle com personalidade própria, sem deixar de respeitar a dobradiça."""
    from math import sin

    from .idle_clips import CLIPS, sample_idle
    if personality.value in CLIPS:
        for group, (x, y, z) in sample_idle(personality.value, t).items():
            rig.set_rotation(group, x=x, y=y, z=z)
        return

    breath = sin(t * 0.72)
    sway = sin(t * 0.42)
    # Keep small movements slow enough to read as weight shifts, not vibration.
    finger_breath = sin(t * 0.48) * 2.0

    if personality == IdlePersonality.CURIOUS:
        look = sin(t * 0.43)
        tilt = sin(t * 0.31)
        rig.set_rotation("body", x=breath * 0.9, y=sway * 1.5, z=tilt * 1.2)
        rig.set_rotation("head", x=-3.0 + sin(t * 0.62) * 1.5, y=look * 16.0, z=tilt * 8.0)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        rig.set_rotation("right-arm", x=sin(t * 0.43) * 3.0, z=14.0)
        rig.set_rotation("left-arm", x=-sin(t * 0.43 + .4) * 2.5, z=-38.0)
        rig.set_rotation("ant-arm", x=3.0 + sin(t * 0.48) * 4.5, z=9.0 + tilt * 5.0)
        rig.set_rotation("ant-arm2", x=3.0 - sin(t * 0.48 + .5) * 3.5, z=-5.0 - tilt * 4.0)
        rig.set_rotation("fingers", z=finger_breath + sin(t * .33) * 1.0)
        rig.set_rotation("fingers2", z=finger_breath - sin(t * .33 + .6) * 1.0)
    elif personality == IdlePersonality.PLAYFUL:
        bounce = sin(t * 1.12)
        compression = (1.0 - sin(t * 2.24 + 1.5707963268)) * .5
        rig.set_rotation("body", x=compression * 2.2, y=sway * 2.2, z=bounce * 2.2)
        rig.set_rotation("head", x=-compression * 1.8, y=sin(t * .72) * 6.0, z=bounce * 3.0)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        rig.set_rotation("right-arm", x=bounce * 6.0, z=27.0 + bounce * 4.0)
        rig.set_rotation("left-arm", x=-bounce * 6.0, z=-28.0 - bounce * 4.0)
        rig.set_rotation("ant-arm", x=sin(t * 1.12 + .35) * 8.0, z=7.0 + bounce * 8.0)
        rig.set_rotation("ant-arm2", x=-sin(t * 1.12 + .35) * 8.0, z=-7.0 - bounce * 8.0)
        rig.set_rotation("fingers", z=finger_breath * 1.4 + sin(t * .78) * 2.0)
        rig.set_rotation("fingers2", z=finger_breath * 1.4 - sin(t * .78 + .45) * 2.0)
    elif personality == IdlePersonality.SHY:
        rig.set_rotation("body", x=1.0 + breath * 0.6, y=-2.0 + sway * 1.0, z=-1.5)
        rig.set_rotation("head", x=6.0 + breath * .7, y=sin(t * 0.34) * 4.0, z=-5.0 + sway * 1.5)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        rig.set_rotation("right-arm", x=2.0, z=42.0)
        rig.set_rotation("left-arm", x=-2.0, z=-42.0)
        rig.set_rotation("ant-arm", x=7.0 + breath * 1.5, z=16.0 + sin(t * 0.36) * 3.0)
        rig.set_rotation("ant-arm2", x=7.5 + breath * 1.2, z=-16.0 - sin(t * 0.36 + .25) * 3.0)
        rig.set_rotation("fingers", z=finger_breath * .7)
        rig.set_rotation("fingers2", z=finger_breath * .7 + 1.0)
    elif personality == IdlePersonality.CONFIDENT:
        nod = sin(t * 0.4)
        punctuation = _idle_pulse(t, 6.4, .3, .18, .7, offset=1.1)
        rig.set_rotation("body", x=-2.5 + breath * 0.6, y=sway * 1.0, z=sin(t * 0.3) * 1.2)
        rig.set_rotation("head", x=-4.0 + nod * 1.8 - punctuation * 3.0, y=sin(t * 0.29) * 5.0, z=nod * 1.5)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        rig.set_rotation("right-arm", x=sin(t * .3) * 1.5, z=42.0)
        rig.set_rotation("left-arm", x=-sin(t * .3 + .4) * 1.5, z=-48.0)
        rig.set_rotation("ant-arm", x=2.0 + sin(t * 0.4) * 2.5, z=3.0 + sway * 2.0)
        rig.set_rotation("ant-arm2", x=2.0 - sin(t * 0.4 + .4) * 2.5, z=-3.0 - sway * 2.0)
        rig.set_rotation("fingers", z=finger_breath)
        rig.set_rotation("fingers2", z=finger_breath - 1.0)
    else:
        rig.set_rotation("body", x=breath * 0.9, y=sway * 1.5, z=sway * 1.0)
        rig.set_rotation("head", x=sin(t * 0.52) * 1.3, y=sin(t * 0.36) * 3.0)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        rig.set_rotation("right-arm", x=sin(t * 0.36) * 2.5, z=52.0 + sin(t * .4) * 2.5 - breath * .6)
        rig.set_rotation("left-arm", x=-sin(t * 0.36) * 2.5, z=-54.0 - sin(t * .4 + .3) * 2.5 + breath * .6)
        rig.set_rotation("ant-arm", x=3.0 + sin(t * .42) * 2.0, z=sin(t * 0.42) * 5.0)
        rig.set_rotation("ant-arm2", x=3.0 - sin(t * .42 + .35) * 2.0, z=-sin(t * 0.42 + .35) * 5.0)
        # Calm hands breathe with the shoulders; no rapid idle twitch.
        rig.set_rotation("fingers", z=finger_breath)
        rig.set_rotation("fingers2", z=finger_breath)

    # Short authored phrases interrupt breathing, then return to the same rest.
    # Each phrase has anticipation, a readable hold and a slower recovery.
    def add(group, x=0.0, y=0.0, z=0.0):
        current = rig.current[group]
        rig.set_rotation(group, x=current.x + radians(x), y=current.y + radians(y),
                         z=current.z + radians(z), degrees=False)

    if personality == IdlePersonality.CURIOUS:
        inspect = _idle_pulse(t, 12.0, .8, 1.1, 1.2, offset=2.0)
        follow = _idle_pulse(t, 12.0, 1.0, .9, 1.4, offset=1.8)
        add("head", x=-5 * inspect, y=12 * inspect, z=4 * inspect)
        add("body", y=3 * follow)
        add("ant-arm", x=-8 * follow, z=12 * follow)
    elif personality == IdlePersonality.PLAYFUL:
        groove = _idle_pulse(t, 9.6, .65, 1.0, 1.1, offset=2.4)
        add("body", y=sin(t * 2.2) * 5 * groove)
        add("head", x=sin(t * 2.2 - .3) * 4 * groove)
        add("right-arm", x=sin(t * 2.2 - .5) * 7 * groove)
        add("left-arm", x=-sin(t * 2.2 - .5) * 7 * groove)
    elif personality == IdlePersonality.CONFIDENT:
        taunt = _idle_pulse(t, 13.0, .45, .7, 1.1, offset=3.0)
        add("head", x=-4 * taunt, y=-10 * taunt)
        add("body", y=4 * taunt, z=-2 * taunt)
        add("ant-arm", x=-8 * taunt, z=10 * taunt)
    elif personality == IdlePersonality.SHY:
        glance = _idle_pulse(t, 11.0, .65, .45, 1.2, offset=2.0)
        add("head", y=-12 * glance, x=-3 * glance)
        add("body", y=-2 * glance)
    else:
        settle = _idle_pulse(t, 14.0, 1.4, .5, 1.8, offset=3.0)
        add("body", z=2 * settle)
        add("head", z=-2.5 * settle)
        add("right-arm", z=-3 * settle)
        add("left-arm", z=-3 * settle)


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
    rig.set_rotation("right-arm", x=-stride * arm_angle, z=42.0 if run else 50.0)
    rig.set_rotation("left-arm", x=stride * arm_angle, z=-42.0 if run else -50.0)
    ant_arm_x = -stride * arm_angle * 0.65
    rig.set_rotation("ant-arm", x=ant_arm_x)
    rig.set_rotation("ant-arm2", x=-ant_arm_x)
    rig.set_rotation("body", x=4.0 if run else 1.5, z=stride * (4.0 if run else 2.0))
    rig.set_rotation("head", x=5.0 if run else 0.0, y=-stride * 3.5)

    # Shoulder compensation
    shoulder_comp = ant_arm_x * 0.15
    rig.set_rotation("shoulder", x=shoulder_comp)
    rig.set_rotation("shoulder2", x=-shoulder_comp)


def pose_wave(rig: Rig, t: float) -> None:
    """Aceno: braço direito sobe e o antebraço oscila."""
    from math import sin

    rig.set_rotation("right-arm", z=-65.0, x=-15.0)
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
    ant_arm_z = -12.0 + beat * amp * 0.55
    rig.set_rotation("ant-arm", z=ant_arm_z)
    rig.set_rotation("ant-arm2", z=-ant_arm_z)
    rig.set_rotation("legs", x=sin(t * 9.0) * amp * 0.25)

    # Shoulder compensation for ant-arm z rotation (minimal since x is ~0)
    # But add subtle shoulder movement for visual appeal
    rig.set_rotation("shoulder", x=sin(t * 9.0) * amp * 0.1)
    rig.set_rotation("shoulder2", x=-sin(t * 9.0) * amp * 0.1)


def pose_drag(rig: Rig, t: float, direction: float = 0.0, drag_intensity: float = 0.0) -> None:
    """Inclina-se na direção do arraste e estende os braços para se equilibrar."""
    from math import sin

    grip = max(0, min(1, drag_intensity))
    rig.set_rotation("fingers", z=8 + 24*grip)
    rig.set_rotation("fingers2", z=-8 - 24*grip)

    direction = max(-1.0, min(1.0, direction))
    rig.set_rotation("body", y=-direction * 3.0)
    rig.set_rotation("head", y=direction * 3.0)
    rig.set_rotation("right-arm", x=-5.0, z=48.0)
    rig.set_rotation("left-arm", x=-5.0, z=-48.0)
    rig.set_rotation("ant-arm", x=-12.0, z=-direction * 8.0)
    rig.set_rotation("ant-arm2", x=-12.0, z=-direction * 8.0)

    # Shoulder compensation: shoulder follows ~15% of ant-arm x rotation
    ant_arm_x = -12.0  # from ant-arm pose
    shoulder_comp = ant_arm_x * 0.15
    rig.set_rotation("shoulder", x=shoulder_comp)
    rig.set_rotation("shoulder2", x=-shoulder_comp)


def pose_sleep(rig: Rig, t: float) -> None:
    """Pose repousada com respiração lenta."""
    from math import sin

    breath = sin(t * 0.75)
    rig.set_rotation("body", x=1.5 + breath * 0.6, z=-2.0)
    rig.set_rotation("head", x=12.0 + breath * 0.8, y=4.0)
    rig.set_rotation("right-arm", x=10.0, z=55.0)
    rig.set_rotation("left-arm", x=10.0, z=-55.0)
    rig.set_rotation("ant-arm", x=8.0)
    rig.set_rotation("ant-arm2", x=8.0)

    # Shoulder compensation (minimal since ant-arms are static)
    rig.set_rotation("shoulder", x=1.2)
    rig.set_rotation("shoulder2", x=-1.2)

    # Fingers: relaxed curl
    rig.set_rotation("fingers", z=15.0 + breath * 2.0)
    rig.set_rotation("fingers2", z=-15.0 - breath * 2.0)


def pose_thrown(rig: Rig, t: float = 0.0) -> None:
    """Pose de queda com braços abertos e pequenas oscilações no ar."""
    from math import sin

    wobble = sin(t * 8.0)
    rig.set_rotation("right-arm", x=-28.0 + wobble * 5.0, z=-42.0)
    rig.set_rotation("left-arm", x=-28.0 - wobble * 5.0, z=42.0)
    ant_arm_x = -18.0 - wobble * 8.0
    rig.set_rotation("ant-arm", x=ant_arm_x)
    rig.set_rotation("ant-arm2", x=-ant_arm_x)
    rig.set_rotation("legs", x=-12.0 + wobble * 3.0)
    rig.set_rotation("head", x=-8.0, y=wobble * 4.0)

    # Shoulder compensation
    shoulder_comp = ant_arm_x * 0.15
    rig.set_rotation("shoulder", x=shoulder_comp)
    rig.set_rotation("shoulder2", x=-shoulder_comp)

    # Fingers: slightly open during fall
    rig.set_rotation("fingers", z=-10.0 + wobble * 5.0)
    rig.set_rotation("fingers2", z=10.0 - wobble * 5.0)


def pose_interaction(rig: Rig, kind: str, t: float, direction: float = 0.0, vertical: float = 0.0) -> None:
    """Reações procedurais: porta gira na dobradiça, sem escala da malha."""
    from math import pi, sin

    direction = max(-1.0, min(1.0, direction))
    # Mantém os braços junto ao corpo durante as reações.
    rig.set_rotation("right-arm", z=65.0)
    rig.set_rotation("left-arm", z=-65.0)
    rig.set_rotation("head", x=-max(-1.0, min(1.0, vertical)) * 18.0, y=direction * 30.0)
    if kind == "hover":
        rig.set_rotation("door", y=20.0)
    elif kind == "click":
        pulse = sin(pi * min(1.0, t / 0.5))
        rig.set_rotation("head", y=direction * 35.0, z=pulse * 8.0)
        rig.set_rotation("door", y=45.0 * sin(t * 4.0 * pi) ** 2)
    elif kind == "pet":
        pulse = sin(pi * min(1.0, t / 1.5))
        rig.set_rotation("head", x=-12.0 * pulse, y=direction * 25.0, z=8.0 * pulse)
        rig.set_rotation("body", z=direction * 5.0 * pulse)
        rig.set_rotation("door", y=pulse * (20.0 + 4.0 * sin(t * 20.0)))
    elif kind == "poke":
        pulse = sin(pi * min(1.0, t / 0.4))
        rig.set_rotation("body", x=-8.0 * pulse)
        rig.set_rotation("head", x=-12.0 * pulse, z=8.0 * pulse)
        rig.set_rotation("right-arm", z=65.0 - pulse * 75.0)
        rig.set_rotation("door", y=35.0 * pulse)
    elif kind == "land":
        pulse = sin(pi * min(1.0, t / 0.45))
        rig.set_rotation("body", x=10.0 * pulse)
        rig.set_rotation("legs", x=-12.0 * pulse)
        rig.set_rotation("head", x=8.0 * pulse)
        rig.set_rotation("door", y=15.0 * pulse)
    elif kind == "wake":
        pulse = sin(pi * min(1.0, t / 1.2))
        rig.set_rotation("body", x=-6.0 * pulse)
        rig.set_rotation("head", x=-10.0 * pulse, y=sin(t * 12.0) * 5.0 * pulse)
        rig.set_rotation("door", y=75.0 * pulse)
        rig.set_rotation("right-arm", z=65.0 - 95.0 * pulse)
        rig.set_rotation("left-arm", z=-65.0 + 95.0 * pulse)
        # Shoulder compensation for wake (arms move)
        shoulder_comp = -47.5 * pulse * 0.15  # approx half of 95
        rig.set_rotation("shoulder", x=shoulder_comp)
        rig.set_rotation("shoulder2", x=-shoulder_comp)


def pose_flourish(rig: Rig, kind: str, t: float) -> None:
    """Aceno, alongamento, espiada e recuperação de impacto."""
    from math import pi, sin
    durations = {"wave": 2.0, "stretch": 2.8, "peek": 9.0, "hit": .65}
    phase = min(1.0, max(0.0, t / durations[kind]))
    envelope = sin(phase * pi)
    rig.set_rotation("right-arm", z=65)
    rig.set_rotation("left-arm", z=-65)
    if kind == "wave":
        rig.set_rotation("right-arm", x=-15 * envelope, z=65 - 130 * envelope)
        rig.set_rotation("ant-arm", x=sin(t * 11) * 22 * envelope)
        rig.set_rotation("head", z=8 * envelope)
        rig.set_rotation("door", y=25 * envelope)
        # Shoulder compensation for wave
        ant_arm_x = sin(t * 11) * 22 * envelope
        shoulder_comp = ant_arm_x * 0.15
        rig.set_rotation("shoulder", x=shoulder_comp)
        rig.set_rotation("shoulder2", x=-shoulder_comp)
    elif kind == "stretch":
        rig.set_rotation("right-arm", x=-25 * envelope, z=65 - 125 * envelope)
        rig.set_rotation("left-arm", x=-25 * envelope, z=-65 + 125 * envelope)
        rig.set_rotation("body", x=-8 * envelope)
        rig.set_rotation("head", x=-12 * envelope)
        rig.set_rotation("door", y=60 * envelope)
    elif kind == "peek":
        rig.set_rotation("head", y=sin(t * 2) * 12 * envelope, z=5 * envelope)
        opening = min(1.0, t / 2.5, max(0.0, (9.0-t) / 2.5))
        opening = opening*opening*(3-2*opening)
        rig.set_rotation("door", y=85 * opening)
        rig.set_rotation("ant-arm", x=-12 * envelope)
        rig.set_rotation("ant-arm2", x=-12 * envelope)
        # Shoulder compensation for peek
        shoulder_comp = -12 * envelope * 0.15
        rig.set_rotation("shoulder", x=shoulder_comp)
        rig.set_rotation("shoulder2", x=-shoulder_comp)
    else:
        recoil = sin(t * 18) * (1 - phase) ** 2
        rig.set_rotation("body", x=-15 * envelope, z=recoil * 10)
        rig.set_rotation("head", x=-18 * envelope, z=-recoil * 12)
        rig.set_rotation("door", y=40 * envelope)


def pose_secondary(rig: Rig, t: float, state: str, personality=IdlePersonality.CALM) -> None:
    """Small shoulder/wrist follow-through; finger curl follows mirrored rig axes."""
    from math import sin, degrees
    for forearm, shoulder, hand, fingers, side in (
        ("ant-arm", "shoulder", "hand", "fingers", 1),
        ("ant-arm2", "shoulder2", "hand2", "fingers2", -1),
    ):
        arm = rig.current[forearm]
        authored_hand = rig.current[hand]
        authored_fingers = rig.current[fingers]
        rig.set_rotation(shoulder, x=max(-3, min(3, degrees(arm.x)*.12)))
        arm_roll = degrees(arm.z)
        wrist_follow = max(-12.0, min(12.0, -arm_roll*.28))
        hand_sway = sin(t*.58-side*.35)*4.5
        wrist_pitch = -degrees(arm.x)*.24 + sin(t*.52-side*.3)*2.0
        rig.set_rotation(hand, x=degrees(authored_hand.x) + wrist_pitch,
                         y=degrees(authored_hand.y),
                         z=degrees(authored_hand.z) + wrist_follow + side*hand_sway)
        if state != "drag":
            amplitude = 7.0 if personality in (IdlePersonality.CURIOUS, IdlePersonality.PLAYFUL) else 4.5
            curl = 12 + sin(t*.62-side*.3)*amplitude + wrist_follow*.3
            idle_wrist = 0.0
            if state == "idle" and personality == IdlePersonality.CURIOUS and side == 1:
                reach = _idle_pulse(t, 7.8, .65, .55, .9, offset=1.0)
                idle_wrist += 15.0 * reach
                curl -= 5.0 * reach
            elif state == "idle" and personality == IdlePersonality.PLAYFUL and side == 1:
                flick = _idle_pulse(t, 4.8, .18, .08, .35, offset=.7)
                idle_wrist += 10.0 * flick
                curl -= 8.0 * flick
            elif state == "idle" and personality == IdlePersonality.SHY:
                fidget = _idle_pulse(t, 6.2, .5, .2, .6, offset=side * .8)
                idle_wrist += side * 4.0 * fidget
            if state == "sleep":
                curl = 8 + sin(t*.6)*.7
            elif state == "fall":
                # Fingers slightly open during fall
                curl = -5 + sin(t * 4.0) * 3.0
            elif state in ("wave", "stretch", "peek", "hit"):
                # Reactive finger movement during flourishes
                curl = 5 + sin(t * 1.3 + side) * 4.0
            rig.set_rotation(hand, x=degrees(authored_hand.x) + wrist_pitch,
                             y=degrees(authored_hand.y),
                             z=degrees(authored_hand.z) + wrist_follow + side * hand_sway + idle_wrist)
            rig.set_rotation(fingers, z=degrees(authored_fingers.z) + side*curl)


def pose_throw_release(rig: Rig, t: float, grip: float = .5) -> None:
    """Release the captured grip, overshoot open, then settle over 0.9 seconds."""
    keys = [(0, 8+32*max(0, min(1, grip))), (.22, -22), (.6, 7), (.9, 3)]
    curl = keys[-1][1]
    for (a, x), (b, y) in zip(keys, keys[1:]):
        if t <= b:
            u = max(0, (t-a)/(b-a));u=u*u*(3-2*u)
            curl = x+(y-x)*u
            break
    rig.set_rotation("fingers", z=curl)
    rig.set_rotation("fingers2", z=-curl)
