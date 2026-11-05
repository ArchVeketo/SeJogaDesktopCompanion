"""Dança guiada por áudio: fraseado por batida/compasso e molas por junta.

A amplitude e os acentos vêm de um envelope por batida (acento no downbeat,
transições em borda de frase) em vez de ``sin(t)`` cru; o resultado por junta
é suavizado por molas amortecidas, dando peso e recuperação naturais.
"""
from math import exp, sin, tau

from .joint_springs import SpringPose


class DanceMotion:
    def __init__(self):
        self.phase = 0.0
        self.energy = self.bass = 0.0
        self.style = 'head_bob'
        self.dwell = 0.0
        self.pose = {}
        self.dt = 0.0
        self.tempo = 90.0
        self.strength = 0.0
        self.override = 'auto'
        self.style_beats = 0.0
        # Acento do downbeat (0..1) e molas por junta para a saída.
        self.acento = 0.0
        self._molas = SpringPose(frequencia=4.5, amortecimento=0.55)

    def update(self, dt, level, bass, bpm=None, beat=False):
        self.dt = dt
        blend = 1-exp(-max(0,dt)*3)
        self.energy += (max(0,min(1,level))-self.energy)*blend
        self.bass += (max(0,min(1,bass))-self.bass)*blend
        tempo = max(55,min(180,bpm or 90))
        self.tempo += (tempo-self.tempo)*(1-exp(-dt*2))
        previous_bar = int(self.phase/(4*tau))
        self.phase += dt*self.tempo/60*tau
        self.style_beats += dt*self.tempo/60
        bar_boundary = int(self.phase/(4*tau)) != previous_bar
        if beat:
            # Soft phase correction avoids a discontinuity in the joints.
            error = (self.phase+tau/2)%tau-tau/2
            self.phase -= error*.25
        self.dwell += dt
        desired = ('breakdance' if self.energy > .65 and self.bass > .3
                   else 'rock' if 110 <= self.tempo <= 170 and self.energy > .35 and self.bass < .22
                   else 'hip_hop' if self.bass > .12 and self.energy > .25
                   else 'head_bob')
        if self.override != 'auto':
            desired = self.override
        if desired != self.style and self.dwell > 3 and bar_boundary:
            self.style, self.dwell = desired, 0.0
            self.style_beats = 0.0
        target_strength = .22 if self.style == 'head_bob' else .65 if self.style == 'hip_hop' else 1.0
        self.strength += (target_strength-self.strength)*(1-exp(-dt*4))
        # Envelope por batida: acento forte no downbeat (início do compasso),
        # decaindo ao longo da batida. A energia do áudio escala o acento.
        batida = (self.phase / tau) % 1
        downbeat = (self.phase / (4 * tau)) % 1
        acento = (1 - batida) ** 2 * (1 + (1 - downbeat) * .6)
        self.acento += (acento * (.4 + self.energy * .6) - self.acento) * (1 - exp(-dt * 9))

    def _montar_alvo(self, rig):
        """Autora a pose crua da dança no rig e devolve o snapshot alvo.

        Compartilhado por apply (que grava no rig) e contribuicao (que apenas
        lê o resultado suavizado por molas), garantindo o mesmo resultado.
        """
        p = self.phase
        # Acento vindo do envelope por batida/compasso (downbeat mais forte),
        # em vez de um pulso derivado só da fase local.
        local = (p/tau) % 1
        pulse = (sin(local/.42*3.14159265)**2 if local < .42 else 0)
        pulse = max(pulse, self.acento)
        amount = .4+self.energy*.6
        rig.set_rotation('door', y=0)
        if self.style == 'head_bob':
            rig.set_rotation('head', x=-4-pulse*7, y=12, z=4+sin(p)*3)
            rig.set_rotation('body', x=-2, y=8, z=5)
            rig.set_rotation('right-arm', x=24, z=62)
            rig.set_rotation('left-arm', x=18, z=-62)
            rig.set_rotation('ant-arm', x=28, z=75)
            rig.set_rotation('ant-arm2', x=20, z=-70)
            rig.set_rotation('hand', x=-8, z=-8)
            rig.set_rotation('hand2', x=-8, z=8)
        elif self.style == 'rock':
            rig.set_rotation('head', x=-8-pulse*25, z=4)
            rig.set_rotation('body', x=-pulse*6, z=2)
            rig.set_rotation('right-arm', x=-10, z=-42)
            rig.set_rotation('ant-arm', x=-8, z=-30)
            rig.set_rotation('hand', x=180)
            rig.set_rotation('left-arm', x=-4, z=-62)
            rig.set_rotation('ant-arm2', z=15)
        else:
            power = 1.6 if self.style == 'breakdance' else 1
            rig.set_rotation('body', x=-pulse*7*amount, z=sin(p*.5)*10*power*amount,
                             y=sin(p*.5)*14*power*amount)
            rig.set_rotation('head', x=-pulse*10, z=-sin(p*.5)*6)
            rig.set_rotation('right-arm', x=sin(p)*16, z=48-24*pulse*power)
            rig.set_rotation('left-arm', x=-sin(p)*16, z=-48+24*(1-pulse)*power)
        if self.style in ('hip_hop', 'breakdance'):
            rig.set_rotation('ant-arm', z=-20-pulse*12)
            rig.set_rotation('ant-arm2', z=20+(1-pulse)*12)
        if self.style == 'breakdance':
            floor = self.floor_amount
            rig.set_rotation('right-arm', x=-5*floor, z=45*(1-floor))
            rig.set_rotation('ant-arm', x=-3*floor, z=-12*(1-floor)+5*floor)
            rig.set_rotation('left-arm', x=-20*floor, z=-48+32*floor)
            rig.set_rotation('ant-arm2', z=20+35*floor)
            rig.set_rotation('head', x=-8-12*floor, z=5*floor)
        return rig.pose()

    def _suavizar(self, rig):
        """Avança as molas por junta sobre o alvo cru e grava em self.pose."""
        target = self._montar_alvo(rig)
        # Molas por junta: o corpo "pesa" no acento e recupera suavemente,
        # em vez de um blend exponencial uniforme para todas as juntas.
        if not self.pose:
            self._molas.definir(target)
        self.pose = self._molas.atualizar(max(0.0, self.dt), target)
        return self.pose

    def apply(self, rig):
        rig.current = dict(self._suavizar(rig))

    def contribuicao(self, rig):
        """Pose de dança suavizada por molas, sem mutar o rig do controlador.

        Usa o rig recebido apenas como scratch para montar o alvo (o chamador
        deve passar um rig em reset); devolve o mesmo dict que apply gravaria.
        """
        return dict(self._suavizar(rig))

    @property
    def lean_amount(self):
        if self.style == 'head_bob':
            value = max(0,min(1,self.style_beats/2))
            return value*value*(3-2*value)
        beat = self.style_beats % 16
        value = max(0,min(1,beat-7,15-beat))
        return value*value*(3-2*value)

    @property
    def floor_amount(self):
        beat = self.style_beats % 16
        value = max(0, min(1, (beat-4)/2, (15-beat)/3))
        return value*value*(3-2*value)

    @property
    def floor_spin(self):
        beat = self.style_beats % 16
        return max(0,min(1,(beat-8)/4))*360
