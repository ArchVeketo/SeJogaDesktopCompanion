"""Engine independent arm follow-through layered over authored gestures."""

from math import exp, radians, sin

from sejoga.nucleo.esqueleto import Rotation3


class HandMotion:
    """Keep authored rotations and add bounded, delayed joint offsets."""

    def __init__(self):
        """Inicia os filtros das mãos em repouso."""
        self.clock = 0.0
        self.offsets = {}
        self.previous = {}

    def apply(self, pose, dt, state):
        """Aplica o follow-through das mãos sobre a pose."""
        dt = max(0.0, min(0.05, dt))
        self.clock += dt
        result = dict(pose)
        energy = {
            "idle": 1.20,
            "hover": 1.05,
            "walk": 1.15,
            "run": 1.35,
            "dance": 1.35,
            "drag": 0.75,
            "fall": 0.8,
            "wave": 0.2,
            "sneeze": 0.25,
            "sleep": 0.12,
            "open_hands": 0.0,
            "close_fists": 0.0,
        }.get(state, 0.35)
        for upper_arm, shoulder, arm, wrist, fingers, side in (
            ("right-arm", "shoulder", "ant-arm", "hand", "fingers", 1),
            ("left-arm", "shoulder2", "ant-arm2", "hand2", "fingers2", -1),
        ):
            if arm not in pose:
                continue
            authored = pose[arm]
            previous = self.previous.get(arm, authored)
            speed_x = (authored.x - previous.x) / dt if dt else 0.0
            speed_z = (authored.z - previous.z) / dt if dt else 0.0
            self.previous[arm] = authored
            lag_x = max(-radians(8), min(radians(8), -speed_x * 0.04)) * energy
            lag_z = max(-radians(9), min(radians(9), -speed_z * 0.045)) * energy
            phase = self.clock * 1.35 - side * 0.75
            relaxado = state in ("idle", "hover")
            variacao = sin(self.clock * 0.54 + side * 1.6) if relaxado else 0.0
            targets = {
                upper_arm: (
                    radians(1.6) * sin(phase + 0.3) * energy,
                    radians(2.2 + 3.8 * relaxado)
                    * sin(phase * 0.85 - side * 0.4)
                    * side
                    * energy,
                    radians(2.4 + 1.7 * relaxado) * sin(phase - 0.2) * side * energy,
                ),
                shoulder: (
                    radians(1.2) * sin(phase + 0.5) * energy,
                    0.0,
                    radians(1.5) * sin(phase) * side * energy,
                ),
                arm: (
                    radians(2.4) * sin(phase) * energy,
                    0.0,
                    (radians(3.2) * (0.5 + 0.5 * sin(phase - 0.35)) * side * energy)
                    + lag_z * 0.45,
                ),
                wrist: (
                    lag_x
                    + radians(4.0 + 5.0 * relaxado)
                    * sin(phase - 0.65 + variacao)
                    * energy,
                    radians(5.5) * sin(phase - 0.5) * energy,
                    lag_z + radians(4.5) * sin(phase - 0.8) * side * energy,
                ),
                fingers: (
                    0.0,
                    0.0,
                    radians(5.8) * sin(phase - 1.1) * side * energy + lag_z * 0.35,
                ),
            }
            for joint, target in targets.items():
                if joint not in pose:
                    continue
                old = self.offsets.get(joint, (0.0, 0.0, 0.0))
                rate = (
                    11
                    if joint in (upper_arm, shoulder)
                    else 9
                    if joint == arm
                    else 7
                    if joint == wrist
                    else 5
                )
                blend = 1 - exp(-dt * rate)
                offset = tuple(
                    a + (b - a) * blend for a, b in zip(old, target, strict=True)
                )
                self.offsets[joint] = offset
                base = result[joint]
                result[joint] = Rotation3(
                    base.x + offset[0], base.y + offset[1], base.z + offset[2]
                )
        return result
