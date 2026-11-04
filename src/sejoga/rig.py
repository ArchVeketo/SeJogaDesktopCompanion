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
    from math import sin

    breath = sin(t * 0.8)
    sway = sin(t * 0.55)

    # Finger micro-movement: breathing + occasional twitch
    finger_breath = sin(t * 0.8) * 3.0
    finger_twitch = sin(t * 7.3) * 1.5

    if personality == IdlePersonality.CURIOUS:
        look = sin(t * 0.7)
        tilt = sin(t * 0.39)
        rig.set_rotation("body", x=breath * 1.1, y=sway * 2.0, z=tilt * 1.5)
        rig.set_rotation("head", x=-4.0 + sin(t * 0.9) * 2.0, y=look * 15.0, z=tilt * 7.0)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        rig.set_rotation("right-arm", x=sin(t * 0.8) * 5.0, z=36.0)
        rig.set_rotation("left-arm", x=-sin(t * 0.8) * 3.0, z=-22.0)
        rig.set_rotation("ant-arm", x=4.0 + sin(t * 0.9) * 7.0, z=tilt * 8.0)
        rig.set_rotation("ant-arm2", x=4.0 - sin(t * 0.9) * 4.0, z=-tilt * 5.0)
        # Fingers: curious = more expressive
        rig.set_rotation("fingers", z=finger_breath + finger_twitch)
        rig.set_rotation("fingers2", z=finger_breath - finger_twitch)
    elif personality == IdlePersonality.PLAYFUL:
        bounce = sin(t * 2.0)
        rig.set_rotation("body", x=abs(bounce) * 3.2, y=sway * 3.0, z=bounce * 3.0)
        rig.set_rotation("head", x=-abs(bounce) * 2.5, y=sin(t * 1.0) * 7.0, z=bounce * 4.0)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        rig.set_rotation("right-arm", x=bounce * 12.0, z=38.0)
        rig.set_rotation("left-arm", x=-bounce * 12.0, z=-38.0)
        rig.set_rotation("ant-arm", x=sin(t * 2.0 + 0.5) * 13.0, z=bounce * 10.0)
        rig.set_rotation("ant-arm2", x=-sin(t * 2.0 + 0.5) * 13.0, z=-bounce * 10.0)
        # Fingers: playful = more movement
        rig.set_rotation("fingers", z=finger_breath * 1.5 + finger_twitch * 2.0)
        rig.set_rotation("fingers2", z=finger_breath * 1.5 - finger_twitch * 2.0)
    elif personality == IdlePersonality.SHY:
        rig.set_rotation("body", x=1.0 + breath * 0.7, y=-3.0 + sway * 1.2, z=-2.0)
        rig.set_rotation("head", x=8.0 + breath, y=sin(t * 0.42) * 5.0, z=-6.0 + sway * 2.0)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        rig.set_rotation("right-arm", x=3.0, z=36.0)
        rig.set_rotation("left-arm", x=-3.0, z=-36.0)
        rig.set_rotation("ant-arm", x=10.0 + breath, z=sin(t * 0.7) * 3.0)
        rig.set_rotation("ant-arm2", x=10.0 + breath, z=-sin(t * 0.7) * 3.0)
        # Fingers: shy = subtle
        rig.set_rotation("fingers", z=finger_breath * 0.5)
        rig.set_rotation("fingers2", z=finger_breath * 0.5)
    elif personality == IdlePersonality.CONFIDENT:
        nod = sin(t * 0.46)
        rig.set_rotation("body", x=-2.5 + breath * 0.8, y=sway * 1.0, z=sin(t * 0.34) * 1.5)
        rig.set_rotation("head", x=-5.0 + nod * 2.0, y=sin(t * 0.32) * 5.0, z=nod * 2.0)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        rig.set_rotation("right-arm", x=1.0, z=40.0)
        rig.set_rotation("left-arm", x=-1.0, z=-40.0)
        rig.set_rotation("ant-arm", x=2.0 + sin(t * 0.5) * 3.0, z=2.0)
        rig.set_rotation("ant-arm2", x=2.0 - sin(t * 0.5) * 3.0, z=-2.0)
        # Fingers: confident = relaxed but alive
        rig.set_rotation("fingers", z=finger_breath + finger_twitch * 0.5)
        rig.set_rotation("fingers2", z=finger_breath - finger_twitch * 0.5)
    else:
        rig.set_rotation("body", x=breath * 1.1, y=sway * 1.7, z=sway * 1.2)
        rig.set_rotation("head", x=sin(t * 0.7) * 1.5, y=sin(t * 0.48) * 3.5)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        rig.set_rotation("right-arm", x=sin(t * 0.7) * 3.0, z=28.0 - breath * 2.0)
        rig.set_rotation("left-arm", x=-sin(t * 0.7) * 3.0, z=-28.0 + breath * 2.0)
        rig.set_rotation("ant-arm", x=4.0, z=sin(t * 0.9) * 5.0)
        rig.set_rotation("ant-arm2", x=4.0, z=-sin(t * 0.9) * 5.0)
        # Fingers: calm = subtle breathing
        rig.set_rotation("fingers", z=finger_breath)
        rig.set_rotation("fingers2", z=finger_breath)


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
    # Finger curl: 0° = open, 45° = closed
    finger_curl = 45.0 * grip
    rig.set_rotation("fingers", z=finger_curl)
    rig.set_rotation("fingers2", z=-finger_curl)

    direction = max(-1.0, min(1.0, direction))
    rig.set_rotation("body", y=-direction * 10.0, z=direction * 8.0)
    rig.set_rotation("head", y=direction * 5.0, z=-direction * 3.0)
    rig.set_rotation("right-arm", x=-8.0 + sin(t * 5.0) * 3.0, z=-24.0)
    rig.set_rotation("left-arm", x=8.0 - sin(t * 5.0) * 3.0, z=24.0)
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
        rig.set_rotation(shoulder, x=max(-3, min(3, degrees(arm.x)*.12)))
        rig.set_rotation(hand, x=-degrees(arm.x)*.12 + sin(t*.8-side*.35)*1.5,
                         z=side*sin(t*.65-side*.3)*2)
        if state != "drag":
            amplitude = 2.5 if personality in (IdlePersonality.CURIOUS, IdlePersonality.PLAYFUL) else 1.2
            curl = 3 + sin(t*.8-side*.35)*amplitude
            if state == "sleep":
                curl = 8 + sin(t*.6)*.7
            elif state == "fall":
                # Fingers slightly open during fall
                curl = -5 + sin(t * 4.0) * 3.0
            elif state in ("wave", "stretch", "peek", "hit"):
                # Reactive finger movement during flourishes
                curl = 5 + sin(t * 3.0 + side) * 4.0
            rig.set_rotation(fingers, z=side*curl)


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
