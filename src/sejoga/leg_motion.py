"""Independent hip/knee motion, in degrees; no engine dependencies."""
from dataclasses import dataclass
from math import exp, sin, tanh, tau


@dataclass(frozen=True)
class LegPose:
    left: float = 0
    right: float = 0
    left_knee: float = 0
    right_knee: float = 0
    left_lift: float = 0
    right_lift: float = 0


class LegMotion:
    def __init__(self):
        self.pose = LegPose()
        self.phase = 0.0

    def update(self, dt, state, velocity=(0, 0), time=0, sway=0):
        dt = max(0, min(.1, dt))
        target = LegPose()
        if state in ('walk', 'run'):
            self.phase += dt * tau * (2.2 if state == 'run' else 1.35)
            stride = sin(self.phase)
            amplitude = 20 if state == 'run' else 12
            target = LegPose(stride*amplitude, -stride*amplitude,
                             max(0, stride)*22, max(0, -stride)*22,
                             max(0, stride)*.035, max(0, -stride)*.035)
        elif state == 'fall':
            descent = .5 + .5*tanh(velocity[1]/320)
            drift = tanh(velocity[0]/700)
            self.phase += dt * tau * 1.05
            kick = sin(self.phase)
            target = LegPose(-7-9*descent+4*drift+5*kick,
                             4-7*descent-3*drift-4*kick,
                             17+13*descent+4*max(0, kick),
                             12+10*descent+4*max(0, -kick),
                             max(0, kick)*.018, max(0, -kick)*.016)
        elif state == 'drag':
            target = LegPose(-6, 3, 12, 9)
        elif state in ('land', 'hit'):
            compress = sin(min(1, time/.45)*3.14159265)
            target = LegPose(-8*compress, -8*compress, 16*compress, 16*compress)
        elif state in ('idle', 'hover', 'dance'):
            shift = max(-1, min(1, sway/5))
            target = LegPose(2*shift, -2*shift, max(0, shift)*4, max(0, -shift)*4)
        blend = 1-exp(-dt*7.5)
        self.pose = LegPose(*(a+(b-a)*blend for a,b in zip(
            self.pose.__dict__.values(), target.__dict__.values())))
        return self.pose
