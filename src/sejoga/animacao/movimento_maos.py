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
            "idle": 0.45,
            "hover": 0.65,
            "walk": 1,
            "run": 1.2,
            "dance": 1.1,
            "drag": 0.7,
            "fall": 0.7,
            "wave": 0.12,
            "sneeze": 0.2,
            "sleep": 0.08,
        }.get(state, 0.25)
        for arm, wrist, fingers, side in (
            ("ant-arm", "hand", "fingers", 1),
            ("ant-arm2", "hand2", "fingers2", -1),
        ):
            if arm not in pose:
                continue
            authored = pose[arm]
            previous = self.previous.get(arm, authored)
            speed = (authored.x - previous.x) / dt if dt else 0
            self.previous[arm] = authored
            lag = max(-radians(7), min(radians(7), -speed * 0.035)) * energy
            phase = self.clock * 1.15 - side * 0.65
            targets = {
                arm: (radians(1.8) * sin(phase) * energy, 0, 0),
                wrist: (
                    lag,
                    radians(2.5) * sin(phase - 0.5) * energy,
                    radians(3) * sin(phase - 0.8) * side * energy,
                ),
                fingers: (0, 0, radians(4) * sin(phase - 1.1) * side * energy),
            }
            for joint, target in targets.items():
                if joint not in pose:
                    continue
                old = self.offsets.get(joint, (0, 0, 0))
                rate = 10 if joint == arm else 7 if joint == wrist else 5
                blend = 1 - exp(-dt * rate)
                offset = tuple(
                    a + (b - a) * blend for a, b in zip(old, target, strict=True)
                )
                self.offsets[joint] = offset
                base = pose[joint]
                result[joint] = Rotation3(
                    base.x + offset[0], base.y + offset[1], base.z + offset[2]
                )
        return result
