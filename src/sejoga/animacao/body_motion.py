"""Inertial body motion driven by mouse gestures, independent of the engine.

Springs use their analytic underdamped solution so a 30/60/120 Hz renderer
does not change the weight or stability of the character.
"""
from dataclasses import dataclass
from math import cos, exp, isfinite, pi, sin, sqrt

from sejoga.animacao import body_motion_tuning as tune


def clamp(value, low, high):
    return max(low, min(high, value))


@dataclass
class Spring:
    frequency: float
    damping: float
    value: float = 0.0
    velocity: float = 0.0

    def update(self, dt, target):
        if dt <= 0:
            return self.value
        omega = 2 * pi * self.frequency
        decay = self.damping * omega
        oscillation = omega * sqrt(1 - self.damping * self.damping)
        offset = self.value - target
        coefficient = (self.velocity + decay * offset) / oscillation
        phase = oscillation * dt
        attenuation = exp(-decay * dt)
        displacement = offset * cos(phase) + coefficient * sin(phase)
        self.value = target + attenuation * displacement
        self.velocity = attenuation * (
            -decay * displacement + oscillation * (-offset * sin(phase) + coefficient * cos(phase))
        )
        return self.value


class GiroCorpo:
    """Giro de corpo LIMITADO: vira o mascote de lado mantendo a câmera fixa.

    Decide um ângulo de heading (em graus) para o nó dedicado ``body_facing`` do
    renderer, suavizado por uma mola (precedente: ``_dance_stage_yaw``) para não
    teletransportar a orientação, e CLAMPADO em ``±LIMITE_GRAUS`` (~virar de
    lado). NÃO faz giro amplo de costas completas nem locomoção: essas fases
    dependem de decisão do usuário, do Plano B de fullscreen e de teste na GPU.

    Esta classe é pura (sem Panda3D/Qt/Win32), para ser testável sem GPU. O
    renderer só lê ``angulo`` e aplica ``body_facing.setH(angulo)``.

    Parâmetros CALIBRÁVEIS (validar visualmente na GPU):
    - ``LIMITE_GRAUS``: teto do giro. Mantido em 90° (perfil puro) para caber no
      envelope da janela dinâmica atual sem braços estendidos; subir além disso
      aproxima das costas e tende a reintroduzir franja/flicker.
    - ``GANHO_OLHAR``: quanto do giro vem do olhar. O corpo acompanha a cabeça só
      parcialmente (a cabeça/tronco já olham via pose_interaction); aqui o corpo
      entra quando o alvo está muito para o lado.
    - ``ZONA_MORTA_OLHAR``: abaixo deste |olhar| o corpo não gira (evita girar o
      corpo por micro-ajustes de olhar perto do centro).
    - ``FREQUENCIA``/``AMORTECIMENTO`` da mola: peso/estabilidade do giro.
    """

    # Teto do giro parcial (graus). Perfil de lado, sem costas completas.
    LIMITE_GRAUS = 90.0
    # Fração do olhar (-1..1) convertida em ângulo-alvo antes do clamp.
    GANHO_OLHAR = 70.0
    # Abaixo deste |olhar| o corpo fica de frente (só a cabeça acompanha).
    ZONA_MORTA_OLHAR = 0.35
    # Tensão da mola do giro (mais lenta/pesada que o olhar da cabeça).
    FREQUENCIA = 1.1
    AMORTECIMENTO = 0.9

    def __init__(self):
        self._mola = Spring(self.FREQUENCIA, self.AMORTECIMENTO)

    @property
    def angulo(self):
        """Heading suavizado atual, em graus, já dentro do limite."""
        return self._mola.value

    def _alvo_do_olhar(self, direcao_olhar):
        """Converte o olhar (-1..1) em ângulo-alvo, com zona morta e clamp.

        ``direcao_olhar > 0`` significa alvo à DIREITA da janela; o corpo vira
        nessa direção. A zona morta mantém o mascote de frente a olhares sutis.
        """
        direcao = clamp(direcao_olhar, -1.0, 1.0)
        if abs(direcao) <= self.ZONA_MORTA_OLHAR:
            return 0.0
        # Reescala o trecho fora da zona morta para 0..1 antes do ganho.
        excedente = (abs(direcao) - self.ZONA_MORTA_OLHAR) / (1.0 - self.ZONA_MORTA_OLHAR)
        sinal = 1.0 if direcao > 0 else -1.0
        return sinal * excedente * self.GANHO_OLHAR

    def update(self, dt, *, direcao_olhar=0.0, angulo_pedido=None):
        """Avança a mola um quadro e devolve o heading suavizado e clampado.

        - ``direcao_olhar``: sinal de atenção (-1..1) de ``foco_atencao``; o corpo
          acompanha a cabeça com giro parcial quando o alvo está muito de lado.
        - ``angulo_pedido``: gancho para estados de animação (ex.: danças que
          viram de lado) pedirem um heading explícito em graus. Quando informado,
          tem precedência sobre o olhar. Sempre clampado em ``±LIMITE_GRAUS``.

        ``dt <= 0`` não avança a mola (devolve o ângulo atual), como ``Spring``.
        """
        alvo = float(angulo_pedido) if angulo_pedido is not None else self._alvo_do_olhar(direcao_olhar)
        alvo = clamp(alvo, -self.LIMITE_GRAUS, self.LIMITE_GRAUS)
        self._mola.update(dt, alvo)
        # Clamp de segurança: a mola pode ultrapassar o alvo no transiente; o nó
        # de giro nunca deve passar do limite para não sair do envelope da janela.
        self._mola.value = clamp(self._mola.value, -self.LIMITE_GRAUS, self.LIMITE_GRAUS)
        return self._mola.value


@dataclass(frozen=True)
class BodyPose:
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    head_roll: float = 0.0
    head_pitch: float = 0.0
    arm_lag: float = 0.0
    compression: float = 0.0
    hanging: float = 0.0
    limb_swing: float = 0.0
    stretch: float = 0.0


class BodyMotion:
    def __init__(self):
        self.roll = Spring(tune.MOLA_ROLL.frequencia, tune.MOLA_ROLL.amortecimento)
        self.pitch = Spring(tune.MOLA_PITCH.frequencia, tune.MOLA_PITCH.amortecimento)
        self.yaw = Spring(tune.MOLA_YAW.frequencia, tune.MOLA_YAW.amortecimento)
        self.neck_roll = Spring(tune.MOLA_NECK_ROLL.frequencia, tune.MOLA_NECK_ROLL.amortecimento)
        self.neck_pitch = Spring(tune.MOLA_NECK_PITCH.frequencia, tune.MOLA_NECK_PITCH.amortecimento)
        self.compression = Spring(tune.MOLA_COMPRESSION.frequencia, tune.MOLA_COMPRESSION.amortecimento)
        self.suspension = Spring(tune.MOLA_SUSPENSION.frequencia, tune.MOLA_SUSPENSION.amortecimento)
        self.limbs = Spring(tune.MOLA_LIMBS.frequencia, tune.MOLA_LIMBS.amortecimento)
        self.snapshot = BodyPose()
        self.pointer_velocity = (0.0, 0.0)
        self._pointer = None
        self._engaged = False

    def impulse(self, kind, direction=0.0, strength=1.0):
        direction = clamp(direction, tune.IMPULSO_DIRECAO_MIN, tune.IMPULSO_DIRECAO_MAX)
        strength = clamp(strength, tune.IMPULSO_FORCA_MIN, tune.IMPULSO_FORCA_MAX)
        if kind in ("click", "poke", "double_click"):
            self.roll.velocity += (direction or tune.IMPULSO_DIRECAO_PADRAO) * tune.IMPULSO_CLIQUE_ROLL * strength
            self.pitch.velocity -= tune.IMPULSO_CLIQUE_PITCH * strength
        elif kind == "pet":
            self.roll.velocity += direction * tune.IMPULSO_PET_ROLL * strength
        elif kind in ("hit", "land"):
            self.roll.velocity += direction * tune.IMPULSO_IMPACTO_ROLL * strength
            self.pitch.velocity += tune.IMPULSO_IMPACTO_PITCH * strength
            self.compression.velocity += tune.IMPULSO_IMPACTO_COMPRESSION * strength

    def update(self, dt, *, pointer=None, dragging=False, hovered=False,
               look=(0.0, 0.0), grounded=True, velocity=(0.0, 0.0), grab_part='body'):
        dt = clamp(dt, 0.0, tune.DT_MAXIMO) if isfinite(dt) else 0.0
        if dt == 0:
            return self.snapshot
        engaged = dragging or hovered
        raw = (0.0, 0.0)
        valid_pointer = pointer is not None and all(isfinite(v) for v in pointer)
        if valid_pointer and self._pointer is not None and engaged and self._engaged:
            raw = tuple(clamp((pointer[k] - self._pointer[k]) / dt,
                              tune.VELOCIDADE_PONTEIRO.minimo, tune.VELOCIDADE_PONTEIRO.maximo)
                        for k in range(2))
        self._pointer = tuple(pointer) if valid_pointer else None
        self._engaged = engaged
        response = 1 - exp(-tune.PONTEIRO_SUAVIZACAO * dt)
        self.pointer_velocity = tuple(old + (new - old) * response
                                      for old, new in zip(self.pointer_velocity, raw, strict=True))
        vx, vy = self.pointer_velocity
        if dragging:
            roll_target = clamp(vx * tune.DRAG_ROLL_GANHO, tune.DRAG_ROLL.minimo, tune.DRAG_ROLL.maximo)
            if grab_part in ('left-feet', 'right-feet', 'legs'):
                roll_target += tune.DRAG_ROLL_PES if grab_part != 'left-feet' else -tune.DRAG_ROLL_PES
            elif grab_part in ('right-arm', 'left-arm'):
                roll_target += tune.DRAG_ROLL_BRACO if grab_part == 'right-arm' else -tune.DRAG_ROLL_BRACO
            pitch_base = tune.DRAG_PITCH_BASE_CORPO if grab_part == 'body' else tune.DRAG_PITCH_BASE_OUTRO
            pitch_target = clamp(pitch_base - vy * tune.DRAG_PITCH_GANHO,
                                 tune.DRAG_PITCH.minimo, tune.DRAG_PITCH.maximo)
            yaw_target = clamp(-vx * tune.DRAG_YAW_GANHO, tune.DRAG_YAW.minimo, tune.DRAG_YAW.maximo)
        elif hovered:
            roll_target = clamp(vx * tune.HOVER_ROLL_GANHO_PONTEIRO - look[0] * tune.HOVER_ROLL_GANHO_OLHAR,
                                tune.HOVER_ROLL.minimo, tune.HOVER_ROLL.maximo)
            pitch_target = clamp(-vy * tune.HOVER_PITCH_GANHO_PONTEIRO - look[1] * tune.HOVER_PITCH_GANHO_OLHAR,
                                 tune.HOVER_PITCH.minimo, tune.HOVER_PITCH.maximo)
            yaw_target = tune.TRONCO_OLHAR_YAW_SINAL * look[0] * tune.HOVER_YAW_GANHO_OLHAR
        elif not grounded:
            roll_target = clamp(velocity[0] * tune.QUEDA_ROLL_GANHO,
                                tune.QUEDA_ROLL.minimo, tune.QUEDA_ROLL.maximo)
            pitch_target = clamp(-velocity[1] * tune.QUEDA_PITCH_GANHO,
                                 tune.QUEDA_PITCH.minimo, tune.QUEDA_PITCH.maximo)
            yaw_target = 0
        else:
            roll_target = pitch_target = yaw_target = 0
        self.roll.update(dt, roll_target)
        self.pitch.update(dt, pitch_target)
        self.yaw.update(dt, yaw_target)
        self.neck_roll.update(dt, self.roll.value)
        self.neck_pitch.update(dt, self.pitch.value)
        self.compression.update(dt, 0)
        self.suspension.update(dt, 1.0 if dragging or not grounded else 0.0)
        self.limbs.update(dt, clamp(-vx * tune.DRAG_LIMBS_GANHO,
                                    tune.DRAG_LIMBS.minimo, tune.DRAG_LIMBS.maximo) if dragging else 0)
        # Bound the visual response without modifying desktop physics or cursor.
        self.snapshot = BodyPose(
            roll=clamp(self.roll.value, tune.SNAP_ROLL.minimo, tune.SNAP_ROLL.maximo),
            pitch=clamp(self.pitch.value, tune.SNAP_PITCH.minimo, tune.SNAP_PITCH.maximo),
            yaw=clamp(self.yaw.value, tune.SNAP_YAW.minimo, tune.SNAP_YAW.maximo),
            head_roll=clamp((self.neck_roll.value - self.roll.value) * tune.SNAP_HEAD_ROLL_GANHO,
                            tune.SNAP_HEAD_ROLL.minimo, tune.SNAP_HEAD_ROLL.maximo),
            head_pitch=clamp((self.neck_pitch.value - self.pitch.value) * tune.SNAP_HEAD_PITCH_GANHO
                             - tune.SNAP_HEAD_PITCH_SUSPENSAO * self.suspension.value,
                             tune.SNAP_HEAD_PITCH.minimo, tune.SNAP_HEAD_PITCH.maximo),
            arm_lag=clamp(-self.roll.velocity * tune.SNAP_ARM_LAG_GANHO,
                          tune.SNAP_ARM_LAG.minimo, tune.SNAP_ARM_LAG.maximo),
            compression=clamp(self.compression.value, tune.SNAP_COMPRESSION.minimo, tune.SNAP_COMPRESSION.maximo),
            hanging=clamp(self.suspension.value, tune.SNAP_HANGING.minimo, tune.SNAP_HANGING.maximo),
            limb_swing=clamp(self.limbs.value, tune.SNAP_LIMB_SWING.minimo, tune.SNAP_LIMB_SWING.maximo),
            stretch=(tune.SNAP_STRETCH_PONTA if grab_part != 'body' else tune.SNAP_STRETCH_CORPO)
                    * clamp(self.suspension.value, tune.SNAP_SUSPENSAO.minimo, tune.SNAP_SUSPENSAO.maximo)
                    if dragging else 0,
        )
        return self.snapshot
