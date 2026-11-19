"""Inertial body motion driven by mouse gestures, independent of the engine.

Springs use their analytic underdamped solution so a 30/60/120 Hz renderer
does not change the weight or stability of the character.
"""

from dataclasses import dataclass
from math import atan2, cos, degrees, exp, hypot, isfinite, pi, radians, sin, sqrt

from sejoga.animacao import movimento_corpo_tuning as tune
from sejoga.animacao.dados_autorais import reacoes_ativas


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
        if permitir_costas:
            alvo = calcular_alvo_angular(self._mola.value, alvo)
            self._mola.update(dt, alvo)
            return self._mola.value
        if abs(self._mola.value) > self.LIMITE_COSTAS_GRAUS + 1e-6:
            # Normaliza giros completos acumulados (ex.: danças com 360°+) antes do retorno ao repouso.
            self._mola.value = ((self._mola.value + 180.0) % 360.0) - 180.0
        alvo = clamp(alvo, -teto, teto)
        teto_transiente = max(teto, abs(self._mola.value))
        self._mola.update(dt, alvo)
        # Contém overshoot sem cortar o retorno suave de costas para frente.
        self._mola.value = clamp(self._mola.value, -teto_transiente, teto_transiente)
        return self._mola.value


_CM_ALTURA_MODELO = 0.48


def _alvo_pendulo_bruto(
    grab_part: str, grab_point: tuple[float, float, float] | None
) -> tuple[float, float]:
    """Calcula ``(r0x, r0z)`` do pivô ao CM conforme a parte agarrada."""
    if grab_part in ("right-arm", "left-arm"):
        sinal = 1.0 if grab_part == "right-arm" else -1.0
        r0x = clamp(abs(float(grab_point[0])) * 0.6, 0.14, 0.24) * sinal if grab_point is not None else 0.18 * sinal
        return r0x, -0.40
    if grab_part in ("legs", "left-feet", "right-feet"):
        r0x = {"left-feet": -0.05, "right-feet": 0.05}.get(grab_part, 0.04)
        r0z = clamp(_CM_ALTURA_MODELO - float(grab_point[2]), 0.26, 0.44) if grab_point is not None else 0.36
        return r0x, r0z
    if grab_point is None:
        return (0.0, -0.36) if grab_part == "head" else (0.0, -0.18)
    lim_z = (-0.46, -0.20) if grab_part == "head" else (-0.32, -0.10)
    return clamp(float(grab_point[0]), -0.22, 0.22), clamp(_CM_ALTURA_MODELO - float(grab_point[2]), *lim_z)


def _geometria_pendulo(
    grab_part: str,
    grab_point: tuple[float, float, float] | None,
) -> tuple[float, float, float, float]:
    """Devolve ``(r0x, r0z, rest_rad, alavanca_eff)`` no plano da tela (X=dir, Z=cima)."""
    r0x, r0z = _alvo_pendulo_bruto(grab_part, grab_point)
    rest_rad = atan2(-r0x, -r0z)
    alavanca = max(tune.PENDULO_ALAVANCA_MIN, hypot(r0x, r0z))
    return r0x, r0z, rest_rad, alavanca


@dataclass(frozen=True)
class BodyPose:
    """Offsets do corpo calculados pelas molas e pêndulo a cada frame."""

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
    spin_speed: float = 0.0
    reach_cursor: float = 0.0
    surprise_jolt: float = 0.0
    roll_velocity: float = 0.0


class BodyMotion:
    """Molas do corpo e pêndulo rígido 360° que respondem a cursor, arraste e impactos."""

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
        self._was_dragging = False
        self._spin_angle = 0.0
        self._spin_velocity = 0.0
        self._reach_cursor = 0.0
        self._surprise_timer = 0.0
        self._pendulo_angulo = 0.0
        self._pendulo_vel = 0.0
        self._pendulo_rest = 0.0
        self._pendulo_alavanca = tune.PENDULO_ALAVANCA_MIN
        self._grab_part_pendulo = "body"
        self._grab_point_pendulo = None
        self._sling_velocity = (0.0, 0.0)

    @property
    def sling_velocity(self) -> tuple[float, float]:
        """Velocidade tangencial de arremesso calculada pelo pêndulo."""
        return self._sling_velocity

    @property
    def grab_part(self) -> str:
        """Parte atualmente segurada no arraste."""
        return self._grab_part_pendulo

    @staticmethod
    def _impulsos_config() -> tuple[float, float, float, float, float, float, float]:
        imp = reacoes_ativas().get("impulsos_corpo", {})
        return (
            float(imp.get("clique_roll", tune.IMPULSO_CLIQUE_ROLL)),
            float(imp.get("clique_pitch", tune.IMPULSO_CLIQUE_PITCH)),
            float(imp.get("direcao_padrao", tune.IMPULSO_DIRECAO_PADRAO)),
            float(imp.get("impacto_compression", tune.IMPULSO_IMPACTO_COMPRESSION)),
            float(imp.get("pet_roll", tune.IMPULSO_PET_ROLL)),
            float(imp.get("impacto_roll", tune.IMPULSO_IMPACTO_ROLL)),
            float(imp.get("impacto_pitch", tune.IMPULSO_IMPACTO_PITCH)),
        )

    def impulse(self, kind, direction=0.0, strength=1.0, *, part="body"):
        """Aplica um impulso de reação nas molas do corpo."""
        direction = clamp(direction, tune.IMPULSO_DIRECAO_MIN, tune.IMPULSO_DIRECAO_MAX)
        strength = clamp(strength, tune.IMPULSO_FORCA_MIN, tune.IMPULSO_FORCA_MAX)
        zona = str(part or "body").lower()
        lado_parte = 1.0 if "left" in zona else (-1.0 if "right" in zona else 0.0)
        c_roll, c_pitch, dir_pad, i_comp, p_roll, i_roll, i_pitch = self._impulsos_config()
        if kind in ("click", "poke", "double_click"):
            mult_pitch = 1.35 if "head" in zona else (0.75 if "feet" in zona or "legs" in zona else 1.0)
            roll_dir = lado_parte if (lado_parte and kind in ("poke", "double_click")) else (direction or dir_pad)
            self.roll.velocity += roll_dir * c_roll * strength
            self.pitch.velocity -= c_pitch * strength * mult_pitch
            if "feet" in zona or "legs" in zona:
                self.compression.velocity += i_comp * 0.45 * strength
        elif kind == "celebrate":
            self.compression.velocity += i_comp * 0.65 * strength
            self.pitch.velocity -= c_pitch * 0.85 * strength
            self.roll.velocity += (direction or 0.6) * c_roll * 0.55 * strength
        elif kind == "pet":
            self.roll.velocity += direction * p_roll * strength
        elif kind in ("hit", "land"):
            self.roll.velocity += direction * i_roll * strength
            self.pitch.velocity += i_pitch * strength
            self.compression.velocity += i_comp * strength

    def _atualizar_ponteiro(self, dt: float, pointer, engaged: bool):
        """Atualiza histórico e velocidade suavizada do ponteiro em px/s."""
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
        prev_vx, prev_vy = self.pointer_velocity
        response = 1 - exp(-tune.PONTEIRO_SUAVIZACAO * dt)
        self.pointer_velocity = tuple(
            old + (new - old) * response
            for old, new in zip(self.pointer_velocity, raw, strict=True)
        )
        return raw, prev_vx, prev_vy

    def _iniciar_pendulo_arraste(self, grab_part: str, grab_point) -> float:
        """Atualiza geometria do pêndulo e alinha o ângulo inicial ao entrar em arraste."""
        _r0x, _r0z, rest_rad, alavanca = _geometria_pendulo(grab_part, grab_point)
        self._pendulo_rest = rest_rad
        self._pendulo_alavanca = alavanca
        self._grab_part_pendulo = grab_part
        self._grab_point_pendulo = grab_point
        if not self._was_dragging:
            self._pendulo_angulo = radians(self.roll.value)
            self._pendulo_vel = radians(self.roll.velocity)
            if (
                cos(self._pendulo_angulo - rest_rad) < -0.5
                and abs(sin(self._pendulo_angulo - rest_rad)) < 0.08
                and abs(self._pendulo_vel) < 0.5
            ):
                self._pendulo_vel += 1.8 if rest_rad >= 0.0 else -1.8
        return rest_rad

    def _integrar_pendulo(
        self,
        dt: float,
        prev_vx: float,
        prev_vy: float,
        rest_efetivo: float,
        alavanca: float,
        cross_mundo: float,
        corpo_altura_px: float,
    ) -> float:
        """Integra o pêndulo rígido com subpassos e atualiza roll e sling_velocity."""
        vx, vy = self.pointer_velocity
        ax = clamp((vx - prev_vx) / dt, -25000.0, 25000.0)
        ay = clamp((vy - prev_vy) / dt, -25000.0, 25000.0)
        n_sub = max(1, int(dt / tune.PENDULO_PASSO_MAX) + 1)
        h = dt / n_sub
        g_l = tune.PENDULO_GRAVIDADE_RAD_S2 / alavanca
        ganho_acel = tune.PENDULO_ACEL_GANHO / alavanca
        arrasto = tune.PENDULO_ARRASTO_AR / alavanca
        torque_curva = cross_mundo * tune.PENDULO_CURVA_TORQUE_GANHO
        for _ in range(n_sub):
            phi = self._pendulo_angulo - rest_efetivo
            alpha = (
                -g_l * sin(phi)
                - ganho_acel * (ax * cos(phi) - ay * sin(phi))
                - arrasto * (vx * cos(phi) - vy * sin(phi))
                + torque_curva
                - tune.PENDULO_AMORTECIMENTO * self._pendulo_vel
            )
            self._pendulo_vel = clamp(
                self._pendulo_vel + alpha * h,
                -tune.PENDULO_VEL_ANGULAR_MAX_RAD,
                tune.PENDULO_VEL_ANGULAR_MAX_RAD,
            )
            self._pendulo_angulo += self._pendulo_vel * h
        self.roll.value = degrees(self._pendulo_angulo)
        self.roll.velocity = degrees(self._pendulo_vel)
        self._spin_velocity = self.roll.velocity
        self._spin_angle = ((self.roll.value + 180.0) % 360.0) - 180.0
        phi_fim = self._pendulo_angulo - rest_efetivo
        r_px = min(220.0, alavanca * max(160.0, float(corpo_altura_px)) * 0.95)
        self._sling_velocity = (
            self._pendulo_vel * r_px * cos(phi_fim),
            -self._pendulo_vel * r_px * sin(phi_fim),
        )
        return phi_fim

    def _passo_arraste(
        self,
        dt: float,
        raw: tuple[float, float],
        prev_vx: float,
        prev_vy: float,
        cross_mundo: float,
        grab_part: str,
        grab_point,
        corpo_altura_px: float,
        meta_direcao,
        resistencia_nivel: float,
    ) -> tuple[float, float]:
        """Simula pêndulo rígido, resistência por objetivo e reações de pega."""
        rest_rad = self._iniciar_pendulo_arraste(grab_part, grab_point)
        res_roll = res_pitch = res_yaw = 0.0
        if resistencia_nivel > 0.05 and meta_direcao is not None:
            dir_x = clamp(meta_direcao[0] / 240.0, -1.0, 1.0)
            dir_y = clamp(meta_direcao[1] / 240.0, -1.0, 1.0)
            res_roll = -dir_x * resistencia_nivel * 22.0
            res_pitch = -dir_y * resistencia_nivel * 16.0
            res_yaw = dir_x * resistencia_nivel * 14.0
        phi_fim = self._integrar_pendulo(
            dt,
            prev_vx,
            prev_vy,
            rest_rad + radians(res_roll),
            self._pendulo_alavanca,
            cross_mundo,
            corpo_altura_px,
        )
        vx, vy = self.pointer_velocity
        speed = sqrt(vx * vx + vy * vy)
        if grab_part in ("right-arm", "left-arm"):
            alvo_alcance = (
                1.0
                if speed < tune.DRAG_ALCANCE_VEL_MAX and abs(self._spin_velocity) < 90.0
                else 0.0
            )
            self._reach_cursor += (alvo_alcance - self._reach_cursor) * (
                1.0 - exp(-5.5 * dt)
            )
        else:
            self._reach_cursor = 0.0
        if (
            grab_part == "head"
            and (prev_vx * raw[0] + prev_vy * raw[1]) < tune.DRAG_CABECA_SURPRESA_LIMIAR
        ):
            self._surprise_timer = tune.DRAG_CABECA_SURPRESA_DURACAO
            self.compression.velocity += 2.2
            self.limbs.velocity += -120.0 if vx >= 0 else 120.0
        pitch_base = (
            tune.DRAG_PITCH_BASE_CORPO
            if grab_part == "body"
            else -3.0
            if grab_part == "head"
            else tune.DRAG_PITCH_BASE_OUTRO
        )
        pitch_target = clamp(
            pitch_base
            - vy * tune.DRAG_PITCH_GANHO * cos(phi_fim)
            - vx * tune.DRAG_PITCH_GANHO * 0.45 * sin(phi_fim)
            - abs(self._pendulo_vel) * 0.75
            + res_pitch,
            tune.DRAG_PITCH.minimo,
            tune.DRAG_PITCH.maximo,
        )
        yaw_target = clamp(
            -vx * tune.DRAG_YAW_GANHO
            + self._pendulo_vel * 1.15
            + cross_mundo * 4.5e-6
            + res_yaw,
            tune.DRAG_YAW.minimo,
            tune.DRAG_YAW.maximo,
        )
        return pitch_target, yaw_target

    def _passo_livre(
        self,
        dt: float,
        hovered: bool,
        grounded: bool,
        look: tuple[float, float],
        velocity: tuple[float, float],
    ) -> tuple[float, float]:
        """Normaliza soltura de pega e atualiza roll/pitch/yaw em hover, queda ou chão."""
        vx, vy = self.pointer_velocity
        if self._was_dragging:
            self.roll.value = ((degrees(self._pendulo_angulo) + 180.0) % 360.0) - 180.0
            self.neck_roll.value = ((self.neck_roll.value + 180.0) % 360.0) - 180.0
            vel_deg = degrees(self._pendulo_vel)
            if abs(vel_deg) >= tune.DRAG_VEL_ANGULAR_ARREMESSO_MIN and not grounded:
                self.roll.velocity = clamp(vel_deg, -1100.0, 1100.0)
            else:
                self.roll.velocity = clamp(vel_deg * 0.4, -360.0, 360.0)
        self._sling_velocity = (0.0, 0.0)
        self._reach_cursor = 0.0
        self._spin_velocity *= exp(-tune.QUEDA_GIRO_RETORNO * dt)
        self._spin_angle *= exp(-tune.QUEDA_GIRO_RETORNO * dt)
        if hovered:
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
        return pitch_target, yaw_target

    def update(
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
        grab_point=None,
        corpo_altura_px=300.0,
        # Resistência orientada por objetivo (manifesto §1.2 — Tensão Viva)
        meta_direcao=None,       # (alvo_x, alvo_y) em coordenadas da janela
        resistencia_nivel=0.0,   # 0..1: quanto Mário resiste ao arraste
    ):
        """Avança as molas e o pêndulo rígido um passo e devolve a pose resultante.

        Durante arraste, ``roll`` segue pêndulo rígido contínuo não-clampado (360°+),
        com equilíbrio em ``atan2(-r0x, -r0z)`` e velocidade tangencial de soltura.
        """
        dt = clamp(dt, 0.0, tune.DT_MAXIMO) if isfinite(dt) else 0.0
        if dt == 0:
            return self.snapshot
        raw, prev_vx, prev_vy = self._atualizar_ponteiro(
            dt, pointer, dragging or hovered
        )
        vx, vy = self.pointer_velocity
        if self._surprise_timer > 0.0:
            self._surprise_timer = max(0.0, self._surprise_timer - dt)

        # Produto vetorial em coordenadas de mundo (+X dir, +Z cima -> vz = -vy).
        cross_mundo = -(prev_vx * vy - prev_vy * vx)
        if dragging:
            pitch_target, yaw_target = self._passo_arraste(
                dt,
                raw,
                prev_vx,
                prev_vy,
                cross_mundo,
                grab_part,
                grab_point,
                corpo_altura_px,
                meta_direcao,
                resistencia_nivel,
            )
        else:
            pitch_target, yaw_target = self._passo_livre(
                dt, hovered, grounded, look, velocity
            )

        self._was_dragging = dragging
        self.pitch.update(dt, pitch_target)
        self.yaw.update(dt, yaw_target)
        self.neck_roll.update(dt, self.roll.value)
        self.neck_pitch.update(dt, self.pitch.value)
        self.compression.update(dt, 0)
        self.suspension.update(dt, 1.0 if dragging or not grounded else 0.0)
        self.limbs.update(
            dt,
            clamp(
                -vx * tune.DRAG_LIMBS_GANHO - degrees(self._pendulo_vel) * 0.045,
                tune.DRAG_LIMBS.minimo,
                tune.DRAG_LIMBS.maximo,
            )
            if dragging
            else 0,
        )

        if dragging or not grounded:
            roll_out = self.roll.value
        else:
            roll_out = clamp(self.roll.value, tune.SNAP_ROLL.minimo, tune.SNAP_ROLL.maximo)

        self.snapshot = BodyPose(
            roll=roll_out,
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
            spin_speed=self._spin_velocity,
            reach_cursor=self._reach_cursor,
            surprise_jolt=clamp(
                self._surprise_timer / tune.DRAG_CABECA_SURPRESA_DURACAO, 0.0, 1.0
            ),
            roll_velocity=self.roll.velocity,
        )
        return self.snapshot
