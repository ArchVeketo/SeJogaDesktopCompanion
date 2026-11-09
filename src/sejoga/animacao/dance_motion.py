"""Dança guiada por áudio: fraseado por batida/compasso e molas por junta.

A amplitude e os acentos vêm de um envelope por batida (acento no downbeat,
transições em borda de frase) em vez de ``sin(t)`` cru; o resultado por junta
é suavizado por molas amortecidas, dando peso e recuperação naturais.
"""
from math import exp, sin, tau

from sejoga.animacao import dance_tuning as tune
from sejoga.animacao.joint_springs import SpringPose
from sejoga.animacao.spring_tuning import DANCA_AMORTECIMENTO, DANCA_FREQUENCIA


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
        self._molas = SpringPose(frequencia=DANCA_FREQUENCIA,
                                 amortecimento=DANCA_AMORTECIMENTO)

    def update(self, dt, level, bass, bpm=None, beat=False):
        self.dt = dt
        blend = 1-exp(-max(0,dt)*tune.SUAVIZACAO_AUDIO)
        self.energy += (max(0,min(1,level))-self.energy)*blend
        self.bass += (max(0,min(1,bass))-self.bass)*blend
        tempo = max(tune.TEMPO_MIN,min(tune.TEMPO_MAX,bpm or tune.TEMPO_PADRAO))
        self.tempo += (tempo-self.tempo)*(1-exp(-dt*tune.SUAVIZACAO_TEMPO))
        previous_bar = int(self.phase/tune.COMPASSO_FASE)
        self.phase += dt*self.tempo/60*tau
        self.style_beats += dt*self.tempo/60
        bar_boundary = int(self.phase/tune.COMPASSO_FASE) != previous_bar
        if beat:
            # Soft phase correction avoids a discontinuity in the joints.
            error = (self.phase+tau/2)%tau-tau/2
            self.phase -= error*tune.CORRECAO_FASE
        self.dwell += dt
        desired = ('breakdance' if self.energy > tune.BREAK_ENERGIA_MIN and self.bass > tune.BREAK_GRAVE_MIN
                   else 'rock' if tune.TEMPO_ROCK_MIN <= self.tempo <= tune.TEMPO_ROCK_MAX
                   and self.energy > tune.ROCK_ENERGIA_MIN and self.bass < tune.ROCK_GRAVE_MAX
                   else 'hip_hop' if self.bass > tune.HIPHOP_GRAVE_MIN and self.energy > tune.HIPHOP_ENERGIA_MIN
                   else 'head_bob')
        if self.override != 'auto':
            desired = self.override
        if desired != self.style and self.dwell > tune.DWELL_MINIMO and bar_boundary:
            self.style, self.dwell = desired, 0.0
            self.style_beats = 0.0
        target_strength = (tune.FORCA_HEAD_BOB if self.style == 'head_bob'
                           else tune.FORCA_HIP_HOP if self.style == 'hip_hop' else tune.FORCA_PADRAO)
        self.strength += (target_strength-self.strength)*(1-exp(-dt*tune.SUAVIZACAO_FORCA))
        # Envelope por batida: acento forte no downbeat (início do compasso),
        # decaindo ao longo da batida. A energia do áudio escala o acento.
        batida = (self.phase / tau) % 1
        downbeat = (self.phase / tune.COMPASSO_FASE) % 1
        acento = (1 - batida) ** 2 * (1 + (1 - downbeat) * tune.ACENTO_DOWNBEAT)
        self.acento += (acento * (tune.ACENTO_BASE + self.energy * tune.ACENTO_GANHO_ENERGIA) - self.acento) \
            * (1 - exp(-dt * tune.SUAVIZACAO_ACENTO))

    def _montar_alvo(self, rig):
        """Autora a pose crua da dança no rig e devolve o snapshot alvo.

        Compartilhado por apply (que grava no rig) e contribuicao (que apenas
        lê o resultado suavizado por molas), garantindo o mesmo resultado.
        """
        p = self.phase
        # Acento vindo do envelope por batida/compasso (downbeat mais forte),
        # em vez de um pulso derivado só da fase local.
        local = (p/tau) % 1
        pulse = (sin(local/tune.PULSO_LARGURA*3.14159265)**2 if local < tune.PULSO_LARGURA else 0)
        pulse = max(pulse, self.acento)
        amount = tune.AMOUNT_BASE+self.energy*tune.AMOUNT_ENERGIA
        lento = p*tune.GROOVE_FASE_LENTA
        rig.set_rotation('door', y=0)
        if self.style == 'head_bob':
            rig.set_rotation('head', x=tune.HEADBOB_HEAD_X_BASE-pulse*tune.HEADBOB_HEAD_X_PULSO,
                             y=tune.HEADBOB_HEAD_Y, z=tune.HEADBOB_HEAD_Z_BASE+sin(p)*tune.HEADBOB_HEAD_Z_SIN)
            rig.set_rotation('body', x=tune.HEADBOB_BODY_X, y=tune.HEADBOB_BODY_Y, z=tune.HEADBOB_BODY_Z)
            rig.set_rotation('right-arm', x=tune.HEADBOB_RARM_X, z=tune.HEADBOB_RARM_Z)
            rig.set_rotation('left-arm', x=tune.HEADBOB_LARM_X, z=tune.HEADBOB_LARM_Z)
            rig.set_rotation('ant-arm', x=tune.HEADBOB_RANT_X, z=tune.HEADBOB_RANT_Z)
            rig.set_rotation('ant-arm2', x=tune.HEADBOB_LANT_X, z=tune.HEADBOB_LANT_Z)
            rig.set_rotation('hand', x=tune.HEADBOB_RHAND_X, z=tune.HEADBOB_RHAND_Z)
            rig.set_rotation('hand2', x=tune.HEADBOB_LHAND_X, z=tune.HEADBOB_LHAND_Z)
        elif self.style == 'rock':
            rig.set_rotation('head', x=tune.ROCK_HEAD_X_BASE-pulse*tune.ROCK_HEAD_X_PULSO, z=tune.ROCK_HEAD_Z)
            rig.set_rotation('body', x=-pulse*tune.ROCK_BODY_X_PULSO, z=tune.ROCK_BODY_Z)
            rig.set_rotation('right-arm', x=tune.ROCK_RARM_X, z=tune.ROCK_RARM_Z)
            rig.set_rotation('ant-arm', x=tune.ROCK_RANT_X, z=tune.ROCK_RANT_Z)
            rig.set_rotation('hand', x=tune.ROCK_RHAND_X)
            rig.set_rotation('left-arm', x=tune.ROCK_LARM_X, z=tune.ROCK_LARM_Z)
            rig.set_rotation('ant-arm2', z=tune.ROCK_LANT_Z)
        else:
            power = tune.POTENCIA_BREAKDANCE if self.style == 'breakdance' else tune.POTENCIA_PADRAO
            rig.set_rotation('body', x=-pulse*tune.GROOVE_BODY_X_PULSO*amount,
                             z=sin(lento)*tune.GROOVE_BODY_Z_SIN*power*amount,
                             y=sin(lento)*tune.GROOVE_BODY_Y_SIN*power*amount)
            rig.set_rotation('head', x=-pulse*tune.GROOVE_HEAD_X_PULSO, z=-sin(lento)*tune.GROOVE_HEAD_Z_SIN)
            rig.set_rotation('right-arm', x=sin(p)*tune.GROOVE_RARM_X_SIN,
                             z=tune.GROOVE_RARM_Z_BASE-tune.GROOVE_RARM_Z_PULSO*pulse*power)
            rig.set_rotation('left-arm', x=-sin(p)*tune.GROOVE_LARM_X_SIN,
                             z=tune.GROOVE_LARM_Z_BASE+tune.GROOVE_LARM_Z_PULSO*(1-pulse)*power)
        if self.style in ('hip_hop', 'breakdance'):
            rig.set_rotation('ant-arm', z=tune.GROOVE_RANT_Z_BASE-pulse*tune.GROOVE_RANT_Z_PULSO)
            rig.set_rotation('ant-arm2', z=tune.GROOVE_LANT_Z_BASE+(1-pulse)*tune.GROOVE_LANT_Z_PULSO)
        if self.style == 'breakdance':
            floor = self.floor_amount
            rig.set_rotation('right-arm', x=tune.BREAK_RARM_X_FLOOR*floor, z=tune.BREAK_RARM_Z_BASE*(1-floor))
            rig.set_rotation('ant-arm', x=tune.BREAK_RANT_X_FLOOR*floor,
                             z=tune.BREAK_RANT_Z_BASE*(1-floor)+tune.BREAK_RANT_Z_FLOOR*floor)
            rig.set_rotation('left-arm', x=tune.BREAK_LARM_X_FLOOR*floor,
                             z=tune.BREAK_LARM_Z_BASE+tune.BREAK_LARM_Z_FLOOR*floor)
            rig.set_rotation('ant-arm2', z=tune.BREAK_LANT_Z_BASE+tune.BREAK_LANT_Z_FLOOR*floor)
            rig.set_rotation('head', x=tune.BREAK_HEAD_X_BASE+tune.BREAK_HEAD_X_FLOOR*floor,
                             z=tune.BREAK_HEAD_Z_FLOOR*floor)
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
            value = max(0,min(1,self.style_beats/tune.LEAN_HEADBOB_BATIDAS))
            return value*value*(3-2*value)
        beat = self.style_beats % tune.FRASE_BATIDAS
        value = max(0,min(1,beat-tune.LEAN_JANELA_INICIO,tune.LEAN_JANELA_FIM-beat))
        return value*value*(3-2*value)

    @property
    def floor_amount(self):
        beat = self.style_beats % tune.FRASE_BATIDAS
        value = max(0, min(1, (beat-tune.FLOOR_INICIO)/tune.FLOOR_SUBIDA,
                          (tune.FLOOR_FIM-beat)/tune.FLOOR_DESCIDA))
        return value*value*(3-2*value)

    @property
    def floor_spin(self):
        beat = self.style_beats % tune.FRASE_BATIDAS
        return max(0,min(1,(beat-tune.SPIN_INICIO)/tune.SPIN_SUBIDA))*tune.SPIN_GRAUS
