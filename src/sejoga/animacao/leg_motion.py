"""Independent hip/knee motion, in degrees; no engine dependencies."""
from dataclasses import dataclass
from math import sin, tanh, tau

from sejoga.animacao.body_motion import Spring
from sejoga.animacao.spring_tuning import amortecimento_de, frequencia_de


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
        # Uma mola por campo de LegPose. Quadris e joelhos usam a tensão de
        # 'legs' (âncora firme); os lifts dos pés usam a tensão de 'left-feet'
        # /'right-feet' (mais solta), tudo lido de spring_tuning. A resposta
        # analítica da Spring mantém o movimento independente do framerate.
        freq_pernas = frequencia_de("legs")
        amort_pernas = amortecimento_de("legs")
        self._mola_left = Spring(freq_pernas, amort_pernas)
        self._mola_right = Spring(freq_pernas, amort_pernas)
        self._mola_left_knee = Spring(freq_pernas, amort_pernas)
        self._mola_right_knee = Spring(freq_pernas, amort_pernas)
        self._mola_left_lift = Spring(
            frequencia_de("left-feet"), amortecimento_de("left-feet"))
        self._mola_right_lift = Spring(
            frequencia_de("right-feet"), amortecimento_de("right-feet"))

    def update(self, dt, state, velocity=(0, 0), time=0, sway=0,
               dance_phase=None, dance_strength=1.0, dance_style='head_bob'):
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
            target = LegPose(-3+sway*.65, 2+sway*.5,
                             5+abs(sway)*.22, 4+abs(sway)*.18)
        elif state in ('land', 'hit'):
            compress = sin(min(1, time/.45)*3.14159265)
            target = LegPose(-8*compress, -8*compress, 16*compress, 16*compress)
        elif state == 'dance':
            if dance_phase is None:
                self.phase += dt*tau*1.3
            else:
                self.phase = dance_phase
            step = sin(self.phase*.5)*dance_strength
            target = LegPose(step*7, -step*7, max(0,step)*12,
                             max(0,-step)*12, max(0,step)*.012, max(0,-step)*.012)
            if dance_style == 'head_bob':
                target = LegPose(0, -3, 2, 7)
            elif dance_style == 'breakdance':
                beat = self.phase/tau % 16
                floor = max(0,min(1,(beat-4)/2,(15-beat)/3))
                target = LegPose(step*8+floor*35, -step*8-floor*30,
                                 8+floor*20, 8+floor*12)
        elif state in ('idle', 'hover'):
            shift = max(-1, min(1, sway/5))
            target = LegPose(2*shift, -2*shift, max(0, shift)*4, max(0, -shift)*4)
        self.pose = LegPose(
            self._mola_left.update(dt, target.left),
            self._mola_right.update(dt, target.right),
            self._mola_left_knee.update(dt, target.left_knee),
            self._mola_right_knee.update(dt, target.right_knee),
            self._mola_left_lift.update(dt, target.left_lift),
            self._mola_right_lift.update(dt, target.right_lift),
        )
        return self.pose
