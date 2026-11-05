"""Engine independent arm follow-through layered over authored gestures."""
from math import exp, radians, sin

from .rig import Rotation3


class HandMotion:
    """Keep authored rotations and add bounded, delayed joint offsets."""

    def __init__(self):
        self.clock = 0.0
        self.offsets = {}
        self.previous = {}

    def apply(self, pose, dt, state):
        dt = max(0.0, min(.05, dt))
        self.clock += dt
        result = dict(pose)
        energy = {'idle': .45, 'hover': .65, 'walk': 1, 'run': 1.2,
                  'dance': 1.1, 'drag': .7, 'fall': .7,
                  'wave': .12, 'sneeze': .2, 'sleep': .08}.get(state, .25)
        for arm, wrist, fingers, side in (
            ('ant-arm', 'hand', 'fingers', 1),
            ('ant-arm2', 'hand2', 'fingers2', -1),
        ):
            if arm not in pose:
                continue
            authored = pose[arm]
            previous = self.previous.get(arm, authored)
            speed = (authored.x-previous.x)/dt if dt else 0
            self.previous[arm] = authored
            lag = max(-radians(7), min(radians(7), -speed*.035))*energy
            phase = self.clock*1.15-side*.65
            targets = {
                arm: (radians(1.8)*sin(phase)*energy, 0, 0),
                wrist: (lag, radians(2.5)*sin(phase-.5)*energy,
                        radians(3)*sin(phase-.8)*side*energy),
                fingers: (0, 0, radians(4)*sin(phase-1.1)*side*energy),
            }
            for joint, target in targets.items():
                if joint not in pose:
                    continue
                old = self.offsets.get(joint, (0, 0, 0))
                rate = 10 if joint == arm else 7 if joint == wrist else 5
                blend = 1-exp(-dt*rate)
                offset = tuple(a+(b-a)*blend for a,b in zip(old,target, strict=True))
                self.offsets[joint] = offset
                base = pose[joint]
                result[joint] = Rotation3(base.x+offset[0], base.y+offset[1], base.z+offset[2])
        return result
