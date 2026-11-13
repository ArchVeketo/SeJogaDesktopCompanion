"""Inertial body motion driven by mouse gestures, independent of the engine.

Springs use their analytic underdamped solution so a 30/60/120 Hz renderer
does not change the weight or stability of the character.
"""

from dataclasses import dataclass
from math import cos, exp, isfinite, pi, sin, sqrt

from sejoga.animacao import movimento_corpo_tuning as tune


def clamp(value, low, high):
    """Limita ``value`` ao intervalo ``[low, high]``."""
    return max(low, min(high, value))


def calcular_alvo_angular(valor: float, alvo: float) -> float:
    """Reposiciona ``alvo`` (graus) para o caminho angular mais curto a partir de ``valor``."""
    diferenca = ((alvo - valor + 180.0) % 360.0) - 180.0
    return valor + diferenca


@dataclass
class Spring:
    """Mola amortecida de um grau de liberdade (regime subamortecido).

    Parâmetros
    ----------
    frequency:
        Frequência nominal em Hz. Deve ser positiva.
    damping:
        Razão de amortecimento (zeta). Deve estar em ``(0, 1)`` — somente o
        regime subamortecido é suportado. Para amortecimento crítico
        (``zeta == 1``), usar ``mola_critica.avancar_mola_critica``.
    """

    frequency: float
    damping: float
    value: float = 0.0
    velocity: float = 0.0

    def __post_init__(self) -> None:
        """Valida faixa de frequência e amortecimento na construção."""
        if self.frequency <= 0:
            msg = (
                f"frequency deve ser positiva, recebeu {self.frequency!r}. "
                "Uma mola com frequência zero não oscila."
            )
            raise ValueError(msg)
        if not (0 < self.damping < 1):
            msg = (
                f"damping deve estar em (0, 1), recebeu {self.damping!r}. "
                "Spring só implementa o regime subamortecido; para "
                "amortecimento crítico use mola_critica.avancar_mola_critica."
            )
            raise ValueError(msg)

    def update(self, dt, target):
        """Avança a mola um passo rumo ao alvo e devolve o valor."""
        if not isfinite(dt) or dt <= 0:
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
            -decay * displacement
            + oscillation * (-offset * sin(phase) + coefficient * cos(phase))
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

    # Teto padrão do giro parcial (graus). Perfil de lado.
    LIMITE_GRAUS = 90.0
    # Teto ampliado para pacotes de animação/costas completas (180°).
    LIMITE_COSTAS_GRAUS = 180.0
    # Fração do olhar (-1..1) convertida em ângulo-alvo antes do clamp.
    GANHO_OLHAR = 70.0
    # Abaixo deste |olhar| o corpo fica de frente (só a cabeça acompanha).
    ZONA_MORTA_OLHAR = 0.35
    # Tensão da mola do giro (mais lenta/pesada que o olhar da cabeça).
    FREQUENCIA = 1.1
    AMORTECIMENTO = 0.9

    def __init__(self, *, limite_graus: float | None = None):
        """Inicia o giro do corpo parado."""
        self._mola = Spring(self.FREQUENCIA, self.AMORTECIMENTO)
        self.limite_graus = (
            self.LIMITE_GRAUS if limite_graus is None else float(limite_graus)
        )

    @property
    def angulo(self):
        """Heading suavizado atual, em graus."""
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
        excedente = (abs(direcao) - self.ZONA_MORTA_OLHAR) / (
            1.0 - self.ZONA_MORTA_OLHAR
        )
        sinal = 1.0 if direcao > 0 else -1.0
        return sinal * excedente * self.GANHO_OLHAR

    def update(
        self,
        dt,
        *,
        direcao_olhar=0.0,
        angulo_pedido=None,
        permitir_costas=False,
    ):
        """Avança a mola um quadro e devolve o heading suavizado e clampado.

        - ``direcao_olhar``: sinal de atenção (-1..1) de ``foco_atencao``; o corpo
          acompanha a cabeça com giro parcial quando o alvo está muito de lado.
        - ``angulo_pedido``: gancho para estados de animação (ex.: danças que
          viram de lado ou pacote Olhar a tela) pedirem um heading explícito em graus.
          Quando informado, tem precedência sobre o olhar.
        - ``permitir_costas``: quando True, libera o teto até ``LIMITE_COSTAS_GRAUS``
          (180°) e usa ``calcular_alvo_angular`` para escolher o caminho curto.

        ``dt <= 0`` não avança a mola (devolve o ângulo atual), como ``Spring``.
        """
        teto = self.LIMITE_COSTAS_GRAUS if permitir_costas else self.limite_graus
        alvo = (
            float(angulo_pedido)
            if angulo_pedido is not None
            else self._alvo_do_olhar(direcao_olhar)
        )
        alvo = clamp(alvo, -teto, teto)
        if permitir_costas:
            alvo = clamp(calcular_alvo_angular(self._mola.value, alvo), -teto, teto)
        teto_transiente = max(teto, abs(self._mola.value))
        self._mola.update(dt, alvo)
        # Contém overshoot sem cortar o retorno suave de costas para frente.
        self._mola.value = clamp(self._mola.value, -teto_transiente, teto_transiente)
        return self._mola.value


@dataclass(frozen=True)
class BodyPose:
    """Offsets do corpo calculados pelas molas a cada frame."""

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
    """Molas do corpo que respondem a cursor, arraste, soltura e impactos."""

    def __init__(self):
        """Inicia todas as molas em repouso."""
        self.roll = Spring(tune.MOLA_ROLL.frequencia, tune.MOLA_ROLL.amortecimento)
        self.pitch = Spring(tune.MOLA_PITCH.frequencia, tune.MOLA_PITCH.amortecimento)
        self.yaw = Spring(tune.MOLA_YAW.frequencia, tune.MOLA_YAW.amortecimento)
        self.neck_roll = Spring(
            tune.MOLA_NECK_ROLL.frequencia, tune.MOLA_NECK_ROLL.amortecimento
        )
        self.neck_pitch = Spring(
            tune.MOLA_NECK_PITCH.frequencia, tune.MOLA_NECK_PITCH.amortecimento
        )
        self.compression = Spring(
            tune.MOLA_COMPRESSION.frequencia, tune.MOLA_COMPRESSION.amortecimento
        )
        self.suspension = Spring(
            tune.MOLA_SUSPENSION.frequencia, tune.MOLA_SUSPENSION.amortecimento
        )
        self.limbs = Spring(tune.MOLA_LIMBS.frequencia, tune.MOLA_LIMBS.amortecimento)
        self.snapshot = BodyPose()
        self.pointer_velocity = (0.0, 0.0)
        self._pointer = None
        self._engaged = False

    def impulse(self, kind, direction=0.0, strength=1.0):
        """Aplica um impulso de reação nas molas do corpo."""
        direction = clamp(direction, tune.IMPULSO_DIRECAO_MIN, tune.IMPULSO_DIRECAO_MAX)
        strength = clamp(strength, tune.IMPULSO_FORCA_MIN, tune.IMPULSO_FORCA_MAX)
        if kind in ("click", "poke", "double_click"):
            self.roll.velocity += (
                (direction or tune.IMPULSO_DIRECAO_PADRAO)
                * tune.IMPULSO_CLIQUE_ROLL
                * strength
            )
            self.pitch.velocity -= tune.IMPULSO_CLIQUE_PITCH * strength
        elif kind == "pet":
            self.roll.velocity += direction * tune.IMPULSO_PET_ROLL * strength
        elif kind in ("hit", "land"):
            self.roll.velocity += direction * tune.IMPULSO_IMPACTO_ROLL * strength
            self.pitch.velocity += tune.IMPULSO_IMPACTO_PITCH * strength
            self.compression.velocity += tune.IMPULSO_IMPACTO_COMPRESSION * strength

    def update(  # noqa: PLR0915  # TODO convenção: fatiar sem prova visual na GPU arrisca mudar o movimento; lote próprio com caracterização
        self,
        dt,
        *,
        pointer=None,
        dragging=False,
        hovered=False,
        look=(0.0, 0.0),
        grounded=True,
        velocity=(0.0, 0.0),
        grab_part="body",
        # Resistência orientada por objetivo (manifesto §1.2 — Tensão Viva)
        meta_direcao=None,       # (alvo_x, alvo_y) em coordenadas da janela
        resistencia_nivel=0.0,   # 0..1: quanto Mário resiste ao arraste
    ):
        """Avança as molas do corpo um passo e devolve a pose resultante.

        Quando ``resistencia_nivel > 0`` durante arraste, o corpo tensiona na
        direção da meta ativa em vez de ficar passivo como um pano (manifesto §1.2).
        """
        dt = clamp(dt, 0.0, tune.DT_MAXIMO) if isfinite(dt) else 0.0
        if dt == 0:
            return self.snapshot
        engaged = dragging or hovered
        raw = (0.0, 0.0)
        valid_pointer = pointer is not None and all(isfinite(v) for v in pointer)
        if valid_pointer and self._pointer is not None and engaged and self._engaged:
            raw = tuple(
                clamp(
                    (pointer[k] - self._pointer[k]) / dt,
                    tune.VELOCIDADE_PONTEIRO.minimo,
                    tune.VELOCIDADE_PONTEIRO.maximo,
                )
                for k in range(2)
            )
        self._pointer = tuple(pointer) if valid_pointer else None
        self._engaged = engaged
        response = 1 - exp(-tune.PONTEIRO_SUAVIZACAO * dt)
        self.pointer_velocity = tuple(
            old + (new - old) * response
            for old, new in zip(self.pointer_velocity, raw, strict=True)
        )
        vx, vy = self.pointer_velocity

        # ── Resistência orientada por objetivo (manifesto §1.2) ──────────
        # Quando Mário tem uma meta e está sendo arrastado, ele tensiona o corpo
        # na direção do alvo em vez de ficar passivo.
        resistencia_roll = 0.0
        resistencia_pitch = 0.0
        resistencia_yaw = 0.0
        if dragging and resistencia_nivel > 0.05 and meta_direcao is not None:
            # Direção da meta relativa ao centro da janela
            mx, my = meta_direcao
            # Normaliza para -1..1 (assumindo janela ~480px)
            norm = 240.0
            dir_x = clamp(mx / norm, -1.0, 1.0)
            dir_y = clamp(my / norm, -1.0, 1.0)
            # O corpo se inclina NA DIREÇÃO DA META, contra a força do arraste
            resistencia_roll = dir_x * resistencia_nivel * 25.0
            resistencia_pitch = -dir_y * resistencia_nivel * 20.0
            resistencia_yaw = dir_x * resistencia_nivel * 15.0

        if dragging:
            roll_target = clamp(
                vx * tune.DRAG_ROLL_GANHO + resistencia_roll,
                tune.DRAG_ROLL.minimo, tune.DRAG_ROLL.maximo
            )
            if grab_part in ("left-feet", "right-feet", "legs"):
                roll_target += (
                    tune.DRAG_ROLL_PES
                    if grab_part != "left-feet"
                    else -tune.DRAG_ROLL_PES
                )
            elif grab_part in ("right-arm", "left-arm"):
                roll_target += (
                    tune.DRAG_ROLL_BRACO
                    if grab_part == "right-arm"
                    else -tune.DRAG_ROLL_BRACO
                )
            pitch_base = (
                tune.DRAG_PITCH_BASE_CORPO
                if grab_part == "body"
                else tune.DRAG_PITCH_BASE_OUTRO
            )
            pitch_target = clamp(
                pitch_base - vy * tune.DRAG_PITCH_GANHO + resistencia_pitch,
                tune.DRAG_PITCH.minimo,
                tune.DRAG_PITCH.maximo,
            )
            yaw_target = clamp(
                -vx * tune.DRAG_YAW_GANHO + resistencia_yaw,
                tune.DRAG_YAW.minimo, tune.DRAG_YAW.maximo
            )
        elif hovered:
            roll_target = clamp(
                vx * tune.HOVER_ROLL_GANHO_PONTEIRO
                - look[0] * tune.HOVER_ROLL_GANHO_OLHAR,
                tune.HOVER_ROLL.minimo,
                tune.HOVER_ROLL.maximo,
            )
            pitch_target = clamp(
                -vy * tune.HOVER_PITCH_GANHO_PONTEIRO
                - look[1] * tune.HOVER_PITCH_GANHO_OLHAR,
                tune.HOVER_PITCH.minimo,
                tune.HOVER_PITCH.maximo,
            )
            yaw_target = (
                tune.TRONCO_OLHAR_YAW_SINAL * look[0] * tune.HOVER_YAW_GANHO_OLHAR
            )
        elif not grounded:
            roll_target = clamp(
                velocity[0] * tune.QUEDA_ROLL_GANHO,
                tune.QUEDA_ROLL.minimo,
                tune.QUEDA_ROLL.maximo,
            )
            pitch_target = clamp(
                -velocity[1] * tune.QUEDA_PITCH_GANHO,
                tune.QUEDA_PITCH.minimo,
                tune.QUEDA_PITCH.maximo,
            )
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
        self.limbs.update(
            dt,
            clamp(
                -vx * tune.DRAG_LIMBS_GANHO,
                tune.DRAG_LIMBS.minimo,
                tune.DRAG_LIMBS.maximo,
            )
            if dragging
            else 0,
        )
        # Bound the visual response without modifying desktop physics or cursor.
        self.snapshot = BodyPose(
            roll=clamp(self.roll.value, tune.SNAP_ROLL.minimo, tune.SNAP_ROLL.maximo),
            pitch=clamp(
                self.pitch.value, tune.SNAP_PITCH.minimo, tune.SNAP_PITCH.maximo
            ),
            yaw=clamp(self.yaw.value, tune.SNAP_YAW.minimo, tune.SNAP_YAW.maximo),
            head_roll=clamp(
                (self.neck_roll.value - self.roll.value) * tune.SNAP_HEAD_ROLL_GANHO,
                tune.SNAP_HEAD_ROLL.minimo,
                tune.SNAP_HEAD_ROLL.maximo,
            ),
            head_pitch=clamp(
                (self.neck_pitch.value - self.pitch.value) * tune.SNAP_HEAD_PITCH_GANHO
                - tune.SNAP_HEAD_PITCH_SUSPENSAO * self.suspension.value,
                tune.SNAP_HEAD_PITCH.minimo,
                tune.SNAP_HEAD_PITCH.maximo,
            ),
            arm_lag=clamp(
                -self.roll.velocity * tune.SNAP_ARM_LAG_GANHO,
                tune.SNAP_ARM_LAG.minimo,
                tune.SNAP_ARM_LAG.maximo,
            ),
            compression=clamp(
                self.compression.value,
                tune.SNAP_COMPRESSION.minimo,
                tune.SNAP_COMPRESSION.maximo,
            ),
            hanging=clamp(
                self.suspension.value,
                tune.SNAP_HANGING.minimo,
                tune.SNAP_HANGING.maximo,
            ),
            limb_swing=clamp(
                self.limbs.value,
                tune.SNAP_LIMB_SWING.minimo,
                tune.SNAP_LIMB_SWING.maximo,
            ),
            stretch=(
                tune.SNAP_STRETCH_PONTA
                if grab_part != "body"
                else tune.SNAP_STRETCH_CORPO
            )
            * clamp(
                self.suspension.value,
                tune.SNAP_SUSPENSAO.minimo,
                tune.SNAP_SUSPENSAO.maximo,
            )
            if dragging
            else 0,
        )
        return self.snapshot
