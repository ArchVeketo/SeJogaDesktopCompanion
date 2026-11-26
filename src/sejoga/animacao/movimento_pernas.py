"""Independent hip/knee motion, in degrees; no engine dependencies."""

from dataclasses import astuple, dataclass
from math import (
    acos,
    asin,
    atan2,
    cos,
    degrees,
    hypot,
    pi,
    radians,
    sin,
    sqrt,
    tanh,
    tau,
)

from sejoga.animacao import danca_tuning as dtune
from sejoga.animacao.dados_autorais import reacoes_ativas
from sejoga.animacao.danca_clipes import (
    amostrar_pernas_emote,
    carregar_clipe_emote,
)
from sejoga.animacao.interpolacao import suavizar_quintico

# --------------------------------------------------------------------------- #
# Calibração das pernas (graus/ganhos/tempos autorais por estado). Extraídos da
# lógica de LegMotion; valores IDÊNTICOS aos de antes. "LIFT" é deslocamento
# vertical do pé (não graus). Mantidos aqui (destino 2: constantes do módulo)
# por serem específicos deste movimento de pernas.
# --------------------------------------------------------------------------- #
#: dt máximo por quadro (clamp anti-salto).
DT_MAXIMO = 0.1

# Locomoção: avanço de fase e amplitude de passada por estado.
FASE_CORRIDA = 2.2
FASE_CAMINHADA = 1.25
AMPLITUDE_CORRIDA = 32.0
AMPLITUDE_CAMINHADA = 27.0
PASSADA_JOELHO = 32.0
PASSADA_LIFT = 0.028

# Queda: descida/deriva/chute a partir da velocidade de física.
QUEDA_DESCIDA_ESCALA = 260.0
QUEDA_DERIVA_ESCALA = 550.0
QUEDA_FASE = 2.4
QUEDA_QUADRIL_ESQ = (-10.0, 12.0, 8.0, 16.0)  # base, descida, deriva, chute
QUEDA_QUADRIL_DIR = (8.0, 10.0, 7.0, 15.0)
QUEDA_JOELHO_ESQ = (20.0, 18.0, 24.0)  # base, descida, chute
QUEDA_JOELHO_DIR = (16.0, 16.0, 24.0)
QUEDA_LIFT_ESQ = 0.024
QUEDA_LIFT_DIR = 0.022

# Arrasto: resposta ao balanço (sway).
DRAG_QUADRIL = (-3.0, 0.65, 2.0, 0.5)  # esq_base, esq_ganho, dir_base, dir_ganho
DRAG_JOELHO = (5.0, 0.22, 4.0, 0.18)

# Aterrissagem/pancada: compressão temporal com peso real.
IMPACTO_DURACAO = 0.58
IMPACTO_QUADRIL = 34.0
IMPACTO_JOELHO = 62.0

# Dança: passo base e poses por estilo.
DANCA_FASE = 1.3
DANCA_PASSO_FASE = 0.5
DANCA_PASSO_QUADRIL = 7.0
DANCA_PASSO_JOELHO = 12.0
DANCA_PASSO_LIFT = 0.012
DANCA_HEADBOB = (0.0, -3.0, 2.0, 7.0)  # pose fixa do head_bob
#: Rock: base larga (pouco passo no quadril) e joelhos que absorvem o headbang.
DANCA_ROCK_QUADRIL = 4.0
DANCA_ROCK_JOELHO = 14.0
#: Hip hop: quique de joelho no onset, somado à transferência de peso do passo.
DANCA_HIPHOP_JOELHO = 6.0
DANCA_BREAK_QUADRIL = 8.0
DANCA_BREAK_QUADRIL_FLOOR = (35.0, 30.0)  # esq, dir
DANCA_BREAK_JOELHO = (8.0, 20.0, 12.0)  # base, floor_esq, floor_dir

# Idle/hover: pequeno peso lateral e respiração orgânica.
IDLE_SWAY_ESCALA = 5.0
IDLE_QUADRIL = 3.5
IDLE_JOELHO = 7.0


@dataclass(frozen=True)
class LegPose:
    """Pose das pernas calculada a cada frame."""

    left: float = 0
    right: float = 0
    left_knee: float = 0
    right_knee: float = 0
    left_lift: float = 0
    right_lift: float = 0
    left_yaw: float = 0
    right_yaw: float = 0
    left_roll: float = 0
    right_roll: float = 0
    left_ankle: float = 0.0
    right_ankle: float = 0.0
    left_ankle_roll: float = 0.0
    right_ankle_roll: float = 0.0
    left_foot_squash: float = 0.0
    right_foot_squash: float = 0.0
    left_ankle_yaw: float = 0.0
    right_ankle_yaw: float = 0.0


#: Braço de alavanca efetivo da sola (quadril→eixo + rolagem controlada da bota).
PASSO_RAIO_SOLA = 0.192
#: Amplitude de referência em marcha com velocidade acoplada ao chão (graus).
ANGULO_PASSO_CAMINHADA = 36.0
ANGULO_PASSO_CORRIDA = 42.0
#: Fração de contra-inclinação do tornozelo no apoio para manter a sola plana no solo.
TORNOZELO_PLANO_APOIO = 0.78


def apoiar_passada(quadril, joelho, coxa, canela, elevacao):
    """Mantém o arco horizontal do FK e resolve o apoio vertical por IK."""
    y = coxa * sin(radians(quadril)) + canela * sin(radians(quadril + joelho))
    alcance_max = coxa + canela - 1e-5
    alcance_min = abs(coxa - canela) + 1e-5
    z_circ = sqrt(max(alcance_min**2, alcance_max**2 - y * y))
    z = min(z_circ, coxa + canela - elevacao)
    alcance = min(alcance_max, max(alcance_min, hypot(y, z)))
    cos_flex = max(-1.0, min(1.0, (alcance**2 - coxa**2 - canela**2) / (2.0 * coxa * canela)))
    flexao = acos(cos_flex)
    direcao = atan2(y, z)
    correcao = atan2(canela * sin(flexao), coxa + canela * cos(flexao))
    return degrees(direcao - correcao), degrees(flexao)


def _cinematica_perna_marcha(
    phi: float,
    sin_amp: float,
    escala_tornozelo: float,
) -> tuple[float, float, float, float, float]:
    """Calcula (quadril°, joelho°, elevacao, tornozelo°, squash) com apoio e absorção no chão."""
    heel_deg, toe_deg = -3.5, 4.5
    if phi <= pi:
        s = phi / pi
        u = -1.0 + 2.0 * s
        quadril = degrees(asin(max(-0.98, min(0.98, sin_amp * u))))
        joelho_apoio = (13.5 * escala_tornozelo) * sin(pi * min(1.0, s / 0.62)) ** 1.3
        heel_flare = heel_deg * (1.0 - suavizar_quintico(min(1.0, s / 0.16)))
        toe_push = toe_deg * suavizar_quintico(max(0.0, (s - 0.80) / 0.20))
        tornozelo = max(
            -52.0,
            min(
                52.0,
                (-quadril * TORNOZELO_PLANO_APOIO + heel_flare + toe_push) * escala_tornozelo
                - joelho_apoio * TORNOZELO_PLANO_APOIO,
            ),
        )
        squash_recepcao = 0.13 * sin(pi * min(1.0, s / 0.50)) ** 1.2
        squash_impulso = 0.11 * sin(pi * max(0.0, min(1.0, (s - 0.70) / 0.30))) ** 1.2
        squash = max(-0.22, min(0.32, (squash_recepcao + squash_impulso) * escala_tornozelo))
        return quadril, joelho_apoio, 0.0, tornozelo, squash
    w = (phi - pi) / pi
    u = 1.0 - 2.0 * suavizar_quintico(w)
    quadril = degrees(asin(max(-0.98, min(0.98, sin_amp * u))))
    balanco = sin(pi * w) ** 1.15
    joelho = balanco * PASSADA_JOELHO
    elevacao = balanco * PASSADA_LIFT
    ang_w0 = (-degrees(asin(sin_amp)) * TORNOZELO_PLANO_APOIO + toe_deg) * escala_tornozelo
    ang_w1 = (degrees(asin(sin_amp)) * TORNOZELO_PLANO_APOIO + heel_deg) * escala_tornozelo
    base_swing = ang_w0 + (ang_w1 - ang_w0) * suavizar_quintico(w)
    tornozelo = max(-52.0, min(52.0, base_swing - 16.0 * balanco * escala_tornozelo))
    return quadril, joelho, elevacao, tornozelo, -0.10 * balanco * escala_tornozelo


def _leg_pose_de_canais(canais: dict[str, float], sq_batida: float = 0.0) -> LegPose:
    """Constrói ``LegPose`` a partir de canais 3D de perna/tornozelo de um clipe."""
    lift_e = canais.get("left_lift", 0.0)
    lift_d = canais.get("right_lift", 0.0)
    hip_e, knee_e = canais.get("left", 0.0), canais.get("left_knee", 0.0)
    hip_d, knee_d = canais.get("right", 0.0), canais.get("right_knee", 0.0)
    peso_ar_e = min(1.0, max(0.0, lift_e * 35.0))
    peso_ar_d = min(1.0, max(0.0, lift_d * 35.0))
    apoio_e = max(-32.0, min(32.0, -0.75 * (hip_e + knee_e)))
    apoio_d = max(-32.0, min(32.0, -0.75 * (hip_d + knee_d)))
    ar_e = 14.0 * peso_ar_e - 0.18 * knee_e
    ar_d = 14.0 * peso_ar_d - 0.18 * knee_d
    ank_e = apoio_e * (1.0 - peso_ar_e) + ar_e * peso_ar_e
    ank_d = apoio_d * (1.0 - peso_ar_d) + ar_d * peso_ar_d
    return LegPose(
        left=canais.get("left", 0.0),
        right=canais.get("right", 0.0),
        left_knee=canais.get("left_knee", 0.0),
        right_knee=canais.get("right_knee", 0.0),
        left_lift=lift_e,
        right_lift=lift_d,
        left_yaw=canais.get("left_yaw", 0.0),
        right_yaw=canais.get("right_yaw", 0.0),
        left_roll=canais.get("left_roll", 0.0),
        right_roll=canais.get("right_roll", 0.0),
        left_ankle=canais.get("left_ankle", ank_e),
        right_ankle=canais.get("right_ankle", ank_d),
        left_ankle_roll=canais.get("left_roll", 0.0) * 0.35,
        right_ankle_roll=canais.get("right_roll", 0.0) * 0.35,
        left_foot_squash=sq_batida * (1.0 - min(1.0, lift_e * 30.0)),
        right_foot_squash=sq_batida * (1.0 - min(1.0, lift_d * 30.0)),
    )


def _eh_chave_locomocao(chave: object) -> tuple[bool, bool]:
    """Retorna ``(eh_locomocao, eh_corrida)`` para uma chave de estado de ``LegMotion``."""
    if not isinstance(chave, tuple) or len(chave) < 2:
        return False, False
    tipo, nome = chave[0], chave[1]
    if tipo == "run":
        return True, True
    if tipo == "walk":
        return True, False
    if tipo == "acao" and isinstance(nome, str):
        if nome.startswith("run_"):
            return True, True
        if nome.startswith("walk_"):
            return True, False
    return False, False


def _suave_pos(valor: float, eps: float = 0.04) -> float:
    """Rampa C∞ positiva (~max(0, valor)) sem quina V em zero."""
    return 0.5 * (valor + sqrt(valor * valor + eps * eps)) - 0.5 * eps


def _limitar_aducao_pernas(pose: LegPose) -> LegPose:
    """Impede hiperextensão de joelhos e adução interna exagerada das coxas."""
    left_knee = max(0.0, pose.left_knee)
    right_knee = max(0.0, pose.right_knee)
    left_roll = min(pose.left_roll, 8.0)
    right_roll = max(pose.right_roll, -8.0)
    left_yaw = pose.left_yaw
    right_yaw = pose.right_yaw
    if pose.left < -10.0 and pose.right < -10.0:
        # Flexão dupla de quadril (sentar/agachar): impede joelhos e botas de cruzar a linha média.
        left_roll = min(left_roll, 4.0)
        right_roll = max(right_roll, -4.0)
        left_yaw = max(left_yaw, -6.0)
        right_yaw = min(right_yaw, 6.0)
    if (
        left_knee == pose.left_knee
        and right_knee == pose.right_knee
        and left_roll == pose.left_roll
        and right_roll == pose.right_roll
        and left_yaw == pose.left_yaw
        and right_yaw == pose.right_yaw
    ):
        return pose
    return LegPose(
        left=pose.left,
        right=pose.right,
        left_knee=left_knee,
        right_knee=right_knee,
        left_lift=pose.left_lift,
        right_lift=pose.right_lift,
        left_yaw=left_yaw,
        right_yaw=right_yaw,
        left_roll=left_roll,
        right_roll=right_roll,
        left_ankle=pose.left_ankle,
        right_ankle=pose.right_ankle,
        left_ankle_roll=pose.left_ankle_roll,
        right_ankle_roll=pose.right_ankle_roll,
        left_foot_squash=pose.left_foot_squash,
        right_foot_squash=pose.right_foot_squash,
        left_ankle_yaw=pose.left_ankle_yaw,
        right_ankle_yaw=pose.right_ankle_yaw,
    )


class LegMotion:
    """Fase da passada e transições entre poses das pernas."""

    def __init__(self):
        """Inicia as pernas paradas."""
        self.pose = LegPose()
        self.phase = 0.0
        self._transicao_de = self.pose
        self._transicao_tempo = 0.0
        self._estado = None
        self._tempo_freada = 10.0
        self._duracao_freada = 0.48
        self._vel_freada_x = 0.0
        self._freada_de_corrida = False
        self._freada_pe_esq_frente = True
        self._ultima_vel_x = 0.0

    @property
    def em_freada(self) -> bool:
        """True enquanto o plantio de freada de caminhada/corrida ainda assenta."""
        return self._tempo_freada < self._duracao_freada

    def _aplicar_freada_zzz(self, idle_target: LegPose) -> LegPose:
        """Calcula plantio de freada ZZZ e mistura suavemente no ``idle_target``."""
        u = max(0.0, min(1.0, self._tempo_freada / max(1e-4, self._duracao_freada)))
        descida = suavizar_quintico(max(0.0, min(1.0, (u - 0.34) / 0.66)))
        peso_joelho = 1.0 - descida
        # Rebound sutil de assento na segunda metade da freada, zerado em u=1.
        peso_base = peso_joelho - (
            0.10 * sin(pi * max(0.0, min(1.0, (u - 0.62) / 0.38))) * (1.0 - 0.35 * descida)
        )
        corrida = self._freada_de_corrida
        escala = 0.90 + 0.18 * min(1.0, abs(self._vel_freada_x) / 380.0)
        joelho_f, joelho_t = (22.0, 18.0) if corrida else (14.0, 11.5)
        qf = -(17.5 if corrida else 11.0) * escala
        qt = (12.5 if corrida else 7.8) * escala
        tf = -(qf + joelho_f) * 0.72 + (4.5 if corrida else 2.5)
        tt = -(qt + joelho_t) * 0.72 - (3.5 if corrida else 2.0)
        sf, st = (0.24, 0.14) if corrida else (0.16, 0.10)
        (q_e, q_d), (j_e, j_d), (t_e, t_d), (s_e, s_d), (ar_e, ar_d) = (
            ((qf, qt), (joelho_f, joelho_t), (tf, tt), (sf, st), (4.0, -3.0))
            if self._freada_pe_esq_frente
            else ((qt, qf), (joelho_t, joelho_f), (tt, tf), (st, sf), (-3.0, 4.0))
        )
        return LegPose(
            left=idle_target.left + (q_e - idle_target.left) * peso_base,
            right=idle_target.right + (q_d - idle_target.right) * peso_base,
            left_knee=max(0.0, idle_target.left_knee + (j_e - idle_target.left_knee) * peso_joelho),
            right_knee=max(0.0, idle_target.right_knee + (j_d - idle_target.right_knee) * peso_joelho),
            left_lift=0.0,
            right_lift=0.0,
            left_yaw=idle_target.left_yaw + (8.5 - idle_target.left_yaw) * peso_joelho,
            right_yaw=idle_target.right_yaw + (-8.5 - idle_target.right_yaw) * peso_joelho,
            left_roll=idle_target.left_roll + (-4.0 - idle_target.left_roll) * peso_joelho,
            right_roll=idle_target.right_roll + (4.0 - idle_target.right_roll) * peso_joelho,
            left_ankle=idle_target.left_ankle + (t_e - idle_target.left_ankle) * peso_base,
            right_ankle=idle_target.right_ankle + (t_d - idle_target.right_ankle) * peso_base,
            left_ankle_roll=idle_target.left_ankle_roll + (ar_e - idle_target.left_ankle_roll) * peso_base,
            right_ankle_roll=idle_target.right_ankle_roll + (ar_d - idle_target.right_ankle_roll) * peso_base,
            left_foot_squash=idle_target.left_foot_squash + (s_e - idle_target.left_foot_squash) * peso_joelho,
            right_foot_squash=idle_target.right_foot_squash + (s_d - idle_target.right_foot_squash) * peso_joelho,
        )

    @staticmethod
    def _target_drag_pernas(
        time: float,
        sway: float,
        grab_part: str,
        roll: float,
        roll_velocity: float,
        resistencia: float = 0.0,
    ) -> LegPose:
        """Calcula pose das pernas no arraste 350° conforme ponto de pega, antecipação e resistência."""
        coil = sin(min(1.0, max(0.0, time) / 0.16) * pi) if time < 0.16 else 0.0
        kick_res = sin(time * 18.0) * 24.0 * max(0.0, min(1.0, resistencia))
        pedal_fase = time * 12.0
        fator_upe = cos(roll * 0.017453292519943295)
        invertido = max(0.0, -fator_upe)
        whip = max(-22.0, min(22.0, roll_velocity * 1.4))
        centrifugo = min(1.0, abs(roll_velocity) / 14.0)
        if grab_part in ("left-feet", "right-feet"):
            pedal = sin(pedal_fase) * 20.0 - 8.0 + sway * 0.45 + whip * 0.35 + kick_res * 0.7
            joelho_livre = max(12.0, 26.0 + cos(pedal_fase) * 22.0 + invertido * 12.0 + 20.0 * coil)
            fixo = 2.0 + sway * 0.15
            tornozelo_livre = 14.0 + cos(pedal_fase) * 10.0
            if grab_part == "left-feet":
                return LegPose(fixo, pedal, 2.0, joelho_livre, left_ankle=4.0, right_ankle=tornozelo_livre, right_ankle_roll=whip * 0.35, right_foot_squash=-0.08)
            return LegPose(pedal, fixo, joelho_livre, 2.0, left_ankle=tornozelo_livre, right_ankle=4.0, left_ankle_roll=whip * 0.35, left_foot_squash=-0.08)
        if grab_part in ("body", "head", "right-arm", "left-arm"):
            sinal_arm = 1.0 if grab_part == "right-arm" else (-1.0 if grab_part == "left-arm" else 0.0)
            pendulo = sway * 0.78 + whip * 0.52 - invertido * 15.0 - 16.0 * coil
            assimetria = 6.0 * sinal_arm + sin(time * 3.6) * (5.0 + 3.5 * invertido) + kick_res
            joelho = max(
                10.0,
                (24.0 + abs(sway) * 0.30 + invertido * 28.0) * (1.0 - 0.50 * centrifugo)
                + 34.0 * coil
                + abs(kick_res) * 0.4,
            )
            ponta = 26.0 * fator_upe - whip * 0.34 - 18.0 * coil
            roll_solto = max(-22.0, min(22.0, sway * 0.32 + whip * 0.42))
            return LegPose(
                pendulo - assimetria, pendulo + assimetria, joelho, joelho,
                left_ankle=ponta + 4.5 * sinal_arm + sin(time * 3.5) * 4.5,
                right_ankle=ponta - 4.5 * sinal_arm - sin(time * 3.5) * 4.5,
                left_ankle_roll=roll_solto, right_ankle_roll=roll_solto if sinal_arm else -roll_solto,
                left_foot_squash=-0.14 * (1.0 + centrifugo), right_foot_squash=-0.14 * (1.0 + centrifugo),
            )
        return LegPose(
            sin(pedal_fase) * 16.0 + sway * 0.5 + whip * 0.3 + kick_res - 12.0 * coil,
            -sin(pedal_fase) * 16.0 + sway * 0.5 + whip * 0.3 - kick_res - 12.0 * coil,
            max(6.0, cos(pedal_fase) * 24.0 + invertido * 14.0) + abs(sway) * 0.2 + 30.0 * coil,
            max(6.0, -cos(pedal_fase) * 24.0 + invertido * 14.0) + abs(sway) * 0.2 + 30.0 * coil,
            left_ankle=8.0 + sin(pedal_fase) * 12.0, right_ankle=8.0 - sin(pedal_fase) * 12.0,
        )

    @staticmethod
    def _reacao_celebrate(time: float) -> LegPose:
        u = max(0.0, min(1.0, time / 2.0))
        if u < 0.18:
            carga = sin((u / 0.18) * pi)
            return LegPose(
                left=-28.0 * carga, right=-28.0 * carga,
                left_knee=52.0 * carga, right_knee=52.0 * carga,
                left_yaw=6.0 * carga, right_yaw=-6.0 * carga,
                left_ankle=-14.0 * carga, right_ankle=-14.0 * carga,
                left_foot_squash=0.22 * carga, right_foot_squash=0.22 * carga,
            )
        if u < 0.58:
            fase = (u - 0.18) / 0.40
            salto = sin(fase * pi)
            balanco = sin(fase * 2.0 * pi) * 4.0 * salto
            return LegPose(
                left=6.0 * salto + balanco, right=-34.0 * salto - balanco,
                left_knee=22.0 * salto, right_knee=68.0 * salto,
                left_lift=0.022 * salto, right_lift=0.055 * salto,
                left_yaw=5.0 * salto, right_yaw=-6.0 * salto,
                left_ankle=14.0 * salto, right_ankle=16.0 * salto,
                left_foot_squash=-0.10 * salto, right_foot_squash=-0.12 * salto,
            )
        if u < 0.82:
            pouso = sin(((u - 0.58) / 0.24) * pi)
            return LegPose(
                left=-22.0 * pouso, right=-22.0 * pouso,
                left_knee=42.0 * pouso, right_knee=42.0 * pouso,
                left_yaw=6.0 * pouso, right_yaw=-6.0 * pouso,
                left_ankle=-12.0 * pouso, right_ankle=-12.0 * pouso,
                left_foot_squash=0.22 * pouso, right_foot_squash=0.22 * pouso,
            )
        reb = sin(((u - 0.82) / 0.18) * pi) * 0.35
        return LegPose(
            left=-5.0 * reb, right=-5.0 * reb,
            left_knee=10.0 * reb, right_knee=10.0 * reb,
            left_ankle=-3.0 * reb, right_ankle=-3.0 * reb,
        )

    @staticmethod
    def _reacao_toque(state: str, time: float, reaction_part: str, reaction_direction: float) -> LegPose:
        parte = (reaction_part or "body").lower()
        dur = 1.4 if state == "double_click" else 0.85
        u = max(0.0, min(1.0, time / dur))
        env = sin(min(1.0, u * 1.1) * pi)
        if "feet" in parte:
            eh_esq = "left" in parte
            tremor = sin(time * 28.0) * 16.0 * env
            return LegPose(
                left=-52.0 * env if eh_esq else 8.0 * env, right=8.0 * env if eh_esq else -52.0 * env,
                left_knee=72.0 * env if eh_esq else 12.0 * env, right_knee=12.0 * env if eh_esq else 72.0 * env,
                left_lift=0.045 * env if eh_esq else 0.0, right_lift=0.0 if eh_esq else 0.045 * env,
                left_ankle=tremor if eh_esq else -6.0 * env, right_ankle=-6.0 * env if eh_esq else tremor,
                left_foot_squash=-0.08 * env if eh_esq else 0.12 * env,
                right_foot_squash=0.12 * env if eh_esq else -0.08 * env,
            )
        if "leg" in parte:
            return LegPose(
                left=-22.0 * env, right=-22.0 * env,
                left_knee=38.0 * env, right_knee=38.0 * env,
                left_roll=-6.0 * env, right_roll=6.0 * env,
                left_ankle=-10.0 * env, right_ankle=-10.0 * env,
                left_foot_squash=0.14 * env, right_foot_squash=0.14 * env,
            )
        recuo = 1.0 if reaction_direction >= 0.0 else -1.0
        carga = sin(min(1.0, u / 0.25) * pi) * 0.5 + env * 0.7
        return LegPose(
            left=-7.0 * carga - 5.0 * recuo * env, right=-7.0 * carga + 5.0 * recuo * env,
            left_knee=14.0 * carga + max(0.0, -recuo) * 8.0 * env,
            right_knee=14.0 * carga + max(0.0, recuo) * 8.0 * env,
            left_yaw=4.0 * env, right_yaw=-4.0 * env,
            left_roll=-3.0 * recuo * env, right_roll=-3.0 * recuo * env,
            left_ankle=-5.0 * carga, right_ankle=-5.0 * carga,
            left_foot_squash=0.10 * carga, right_foot_squash=0.10 * carga,
        )

    @staticmethod
    def _reacao_teimosia(time: float, teimosia_fase: str) -> LegPose:
        t = max(0.0, time)
        fase = teimosia_fase or "resistencia"
        if fase == "resistencia":
            ent = suavizar_quintico(min(1.0, t / 0.25))
            pulso = sin(t * 9.0) * 2.5 * ent
            return LegPose(
                left=14.0 * ent + pulso, right=-8.0 * ent - pulso,
                left_knee=24.0 * ent + abs(pulso), right_knee=18.0 * ent + abs(pulso),
                left_yaw=10.0 * ent, right_yaw=-10.0 * ent, left_roll=-5.0 * ent, right_roll=5.0 * ent,
                left_ankle=-8.0 * ent, right_ankle=-4.0 * ent,
                left_foot_squash=0.14 * ent, right_foot_squash=0.12 * ent,
            )
        if fase == "repreensao":
            batida = 0.5 - 0.5 * cos((t - 1.0) * 8.5)
            return LegPose(
                left=-8.0 + 4.0 * batida, right=14.0 - 3.0 * batida,
                left_knee=14.0 + 10.0 * batida, right_knee=22.0 + 8.0 * batida,
                left_yaw=7.0, right_yaw=-9.0, left_roll=-4.0, right_roll=4.0,
                left_ankle=-5.0 * batida, right_ankle=-7.0 * batida,
                left_foot_squash=0.12 * batida, right_foot_squash=0.15 * batida,
            )
        if fase == "bote":
            bt = max(0.0, t - 2.0)
            if bt <= 0.36:
                coil = suavizar_quintico(bt / 0.36)
                return LegPose(
                    left=-24.0 * coil, right=-22.0 * coil, left_knee=48.0 * coil, right_knee=46.0 * coil,
                    left_yaw=10.0 * coil, right_yaw=-10.0 * coil, left_ankle=-14.0 * coil, right_ankle=-14.0 * coil,
                    left_foot_squash=0.22 * coil, right_foot_squash=0.22 * coil,
                )
            lunge = suavizar_quintico(min(1.0, (bt - 0.36) / 0.24))
            inv = 1.0 - lunge
            return LegPose(
                left=34.0 * lunge - 24.0 * inv, right=-28.0 * lunge - 22.0 * inv,
                left_knee=42.0 * lunge + 48.0 * inv, right_knee=14.0 * lunge + 46.0 * inv,
                left_yaw=8.0 * lunge + 10.0 * inv, right_yaw=-12.0 * lunge - 10.0 * inv,
                left_ankle=-8.0 * lunge - 14.0 * inv, right_ankle=14.0 * lunge - 14.0 * inv,
                left_foot_squash=0.16 * lunge + 0.22 * inv, right_foot_squash=-0.06 * lunge + 0.22 * inv,
            )
        if fase == "roubo":
            tranco = sin(max(0.0, t - 3.0) * 5.2)
            return LegPose(
                left=22.0 + 3.0 * tranco, right=-18.0 - 2.5 * tranco,
                left_knee=36.0 + 4.0 * tranco, right_knee=24.0 - 3.0 * tranco,
                left_yaw=6.0 + 1.5 * tranco, right_yaw=-6.0 - 1.5 * tranco,
                left_ankle=-8.0 - 2.0 * tranco, right_ankle=10.0 + 2.0 * tranco,
                left_foot_squash=0.14 + 0.03 * tranco, right_foot_squash=0.06 - 0.02 * tranco,
            )
        ct = max(0.0, min(1.0, (t - 5.0) / 1.0))
        env = sin(ct * pi)
        return LegPose(
            left=-14.0 * env, right=-10.0 * env, left_knee=28.0 * env, right_knee=24.0 * env,
            left_yaw=6.0 * env, right_yaw=-6.0 * env, left_ankle=-7.0 * env, right_ankle=-5.0 * env,
            left_foot_squash=0.14 * env, right_foot_squash=0.12 * env,
        )

    @staticmethod
    def _reacao_sneeze(time: float) -> LegPose:
        t = max(0.0, time)
        # Sincronizado com pose_sneeze (explosão exata em t=3.68s).
        prep = suavizar_quintico(min(1.0, t / 2.2)) * (
            1.0 - suavizar_quintico(max(0.0, min(1.0, (t - 3.45) / 0.22)))
        )
        env_rajada = suavizar_quintico(max(0.0, min(1.0, (t - 3.52) / 0.14))) * (
            1.0 - suavizar_quintico(max(0.0, min(1.0, (t - 4.05) / 0.45)))
        )
        env_tontura = suavizar_quintico(max(0.0, min(1.0, (t - 4.10) / 0.60))) * (
            1.0 - suavizar_quintico(max(0.0, min(1.0, (t - 7.75) / 1.15)))
        )
        tremor = sin(t * 14.0) * 1.5 * prep
        rajada = (0.35 + 0.65 * abs(sin(max(0.0, t - 3.52) * 3.8))) * env_rajada
        tontura = sin(max(0.0, t - 4.10) * 2.2) * env_tontura
        base_calma = 6.0 * env_tontura
        return LegPose(
            left=-10.0 * prep + tremor - 20.0 * rajada - base_calma + 4.0 * tontura,
            right=-10.0 * prep - tremor - 18.0 * rajada - base_calma - 4.0 * tontura,
            left_knee=20.0 * prep + 42.0 * rajada + 14.0 * env_tontura + max(0.0, tontura) * 6.0,
            right_knee=20.0 * prep + 38.0 * rajada + 14.0 * env_tontura + max(0.0, -tontura) * 6.0,
            left_yaw=6.0 * (rajada + 0.5 * env_tontura), right_yaw=-6.0 * (rajada + 0.5 * env_tontura),
            left_roll=-3.0 * env_tontura, right_roll=3.0 * env_tontura,
            left_ankle=-6.0 * prep - 12.0 * rajada - 4.0 * env_tontura,
            right_ankle=-6.0 * prep - 10.0 * rajada - 4.0 * env_tontura,
            left_foot_squash=0.10 * prep + 0.18 * rajada, right_foot_squash=0.10 * prep + 0.16 * rajada,
        )

    @staticmethod
    def _reacao_leve(state: str, time: float) -> LegPose:
        dur_mapa = {"wave": 2.6, "stretch": 3.2, "wake": 1.2, "pet": 1.5, "click": 0.50, "peek": 9.0}
        u = max(0.0, min(1.0, time / dur_mapa[state]))
        env = sin(u * pi)
        if state == "stretch":
            shift = sin(u * 2.0 * pi) * 4.0
            return LegPose(
                left=-6.0 * env + shift, right=-6.0 * env - shift,
                left_knee=14.0 * env, right_knee=10.0 * env, left_lift=0.008 * env, right_lift=0.008 * env,
                left_ankle=8.0 * env, right_ankle=8.0 * env, left_foot_squash=-0.05 * env, right_foot_squash=-0.05 * env,
            )
        if state == "wake":
            subida = 1.0 - suavizar_quintico(min(1.0, u / 0.72))
            respiro = sin(u * 3.0 * pi) * 3.0 * env
            return LegPose(
                left=-18.0 * subida + respiro, right=-16.0 * subida - respiro,
                left_knee=34.0 * subida + 6.0 * env, right_knee=30.0 * subida + 6.0 * env,
                left_yaw=6.0 * env, right_yaw=-6.0 * env, left_ankle=6.0 * env, right_ankle=6.0 * env,
            )
        if state in ("wave", "pet", "peek"):
            balanco = sin(time * (4.2 if state == "pet" else 3.0)) * env
            return LegPose(
                left=-5.0 * env + 5.0 * balanco, right=-5.0 * env - 5.0 * balanco,
                left_knee=10.0 * env + _suave_pos(balanco) * 6.0, right_knee=10.0 * env + _suave_pos(-balanco) * 6.0,
                left_yaw=4.0 * env, right_yaw=-4.0 * env, left_roll=-2.5 * env, right_roll=2.5 * env,
                left_ankle=-3.0 * env, right_ankle=-3.0 * env, left_foot_squash=0.08 * env, right_foot_squash=0.08 * env,
            )
        return LegPose(
            left=-7.0 * env, right=-7.0 * env, left_knee=14.0 * env, right_knee=14.0 * env,
            left_ankle=-5.0 * env, right_ankle=-5.0 * env, left_foot_squash=0.10 * env, right_foot_squash=0.10 * env,
        )

    @classmethod
    def _target_reacao_pernas(
        cls,
        state: str,
        time: float,
        reaction_part: str,
        *,
        reaction_direction: float = 0.0,
        teimosia_fase: str = "",
    ) -> LegPose | None:
        """Calcula a pose das pernas para comemoração, teimosia e reações por parte."""
        if state == "celebrate":
            return cls._reacao_celebrate(time)
        if state in ("double_click", "poke"):
            return cls._reacao_toque(state, time, reaction_part, reaction_direction)
        if state == "teimosia":
            return cls._reacao_teimosia(time, teimosia_fase)
        if state == "surprise":
            u = max(0.0, min(1.0, time / 0.70))
            recuo = 1.0 if reaction_direction >= 0.0 else -1.0
            dip = suavizar_quintico(sin(min(1.0, u / 0.30) * pi))
            hop = sin(suavizar_quintico(max(0.0, (u - 0.10) / 0.90)) * pi)
            return LegPose(
                left=-16.0 * dip + (-12.0 - 8.0 * recuo) * hop, right=-16.0 * dip + (-12.0 + 8.0 * recuo) * hop,
                left_knee=30.0 * dip + 34.0 * hop, right_knee=30.0 * dip + 22.0 * hop,
                left_lift=0.024 * hop, right_lift=0.016 * hop,
                left_ankle=-9.0 * dip + 10.0 * hop, right_ankle=-9.0 * dip + 6.0 * hop,
                left_foot_squash=0.18 * dip - 0.06 * hop, right_foot_squash=0.18 * dip - 0.04 * hop,
            )
        if state == "sneeze":
            return cls._reacao_sneeze(time)
        if state in ("wave", "stretch", "wake", "pet", "click", "peek"):
            return cls._reacao_leve(state, time)
        return None

    def update(  # noqa: C901, PLR0915  # TODO convenção: fatiar sem prova visual na GPU arrisca mudar o movimento; lote próprio com caracterização
        self,
        dt,
        state,
        velocity=(0, 0),
        time=0,
        sway=0,
        dance_phase=None,
        dance_strength=1.0,
        dance_style="head_bob",
        modo_sono="em_pe",
        grab_part="body",
        heavy_land=False,
        dance_time: float = 0.0,
        roll: float = 0.0,
        roll_velocity: float = 0.0,
        pixels_per_unit: float = 216.8,
        reaction_part: str = "body",
        acao_canais: dict[str, float] | None = None,
        acao_nome: str | None = None,
        cena_nome: str = "",
        cena_pernas: tuple[float, ...] | None = None,
        teimosia_fase: str = "",
        reaction_direction: float = 0.0,
        respiracao: float | None = None,
        height_above_floor_px: float = 0.0,
        resistencia: float = 0.0,
        fase_clipe: float | None = None,
    ):
        """Avança as pernas um passo e devolve a pose resultante."""
        dt = max(0, min(DT_MAXIMO, dt))
        if acao_nome:
            chave = ("acao", acao_nome)
        elif cena_nome:
            chave = ("cena", cena_nome, cena_pernas is not None)
        elif state == "teimosia":
            chave = ("teimosia", teimosia_fase or "resistencia")
        else:
            chave = ("idle", None) if state == "hover" else (
                state, dance_style if state == "dance" else modo_sono if state == "sleep" else None
            )

        eh_loco_atual, _ = _eh_chave_locomocao(chave)
        if (state in ("walk", "run") or eh_loco_atual) and velocity and abs(velocity[0]) > 1.0:
            self._ultima_vel_x = float(velocity[0])

        veio_loco, veio_corrida = _eh_chave_locomocao(self._estado)
        eh_repouso_puro = (
            state in ("idle", "hover")
            and not acao_nome
            and not cena_nome
            and not acao_canais
            and cena_pernas is None
        )
        if eh_repouso_puro and veio_loco:
            self._tempo_freada = 0.0
            self._freada_de_corrida = veio_corrida
            vx_atual = float(velocity[0]) if velocity else 0.0
            self._vel_freada_x = vx_atual if abs(vx_atual) > 1.0 else self._ultima_vel_x
            self._duracao_freada = 0.56 if veio_corrida else 0.42
            self._freada_pe_esq_frente = self.pose.left <= self.pose.right
        elif not eh_repouso_puro:
            self._tempo_freada = max(self._tempo_freada, self._duracao_freada)

        eh_corrida = state == "run"
        sin_amp = 0.0
        if state in ("walk", "run"):
            pernas_cfg = reacoes_ativas().get("pernas", {})
            vx = abs(velocity[0]) if velocity else 0.0
            if vx > 5.0:
                amp_deg = ANGULO_PASSO_CORRIDA if eh_corrida else ANGULO_PASSO_CAMINHADA
                sin_amp = sin(radians(amp_deg))
                y_amp = PASSO_RAIO_SOLA * sin_amp
                v_modelo = vx / max(50.0, pixels_per_unit)
                freq = max(0.42, min(3.8, v_modelo / max(1e-4, 4.0 * y_amp)))
            else:
                amp_deg = float(
                    pernas_cfg.get("amplitude_corrida", AMPLITUDE_CORRIDA)
                    if eh_corrida
                    else pernas_cfg.get("amplitude_caminhada", AMPLITUDE_CAMINHADA)
                )
                sin_amp = sin(radians(amp_deg))
                freq = float(
                    pernas_cfg.get("fase_corrida", FASE_CORRIDA)
                    if eh_corrida
                    else pernas_cfg.get("fase_caminhada", FASE_CAMINHADA)
                )
            if fase_clipe is not None:
                self.phase = float(fase_clipe)
            else:
                self.phase += dt * tau * freq

        target = LegPose()
        if acao_canais:
            target = _leg_pose_de_canais(acao_canais)
        elif cena_pernas is not None:
            if len(cena_pernas) >= 12:
                hl, hr, kl, kr, yl, yr, rl, rr, al, ar, ll, lr = cena_pernas[:12]
                target = LegPose(
                    left=hl,
                    right=hr,
                    left_knee=kl,
                    right_knee=kr,
                    left_yaw=yl,
                    right_yaw=yr,
                    left_roll=rl,
                    right_roll=rr,
                    left_ankle=al,
                    right_ankle=ar,
                    left_lift=ll,
                    right_lift=lr,
                )
            else:
                hl, hr, kl, kr, yl, yr = cena_pernas[:6]
                # Compensação automática de tornozelo/sola para manter os pés plantados no chão.
                al = max(-26.0, min(26.0, -0.52 * (hl + kl)))
                ar = max(-26.0, min(26.0, -0.52 * (hr + kr)))
                sql = min(0.18, max(0.0, (kl - 4.0) / 140.0))
                sqr = min(0.18, max(0.0, (kr - 4.0) / 140.0))
                target = LegPose(
                    left=hl,
                    right=hr,
                    left_knee=kl,
                    right_knee=kr,
                    left_yaw=yl,
                    right_yaw=yr,
                    left_ankle=al,
                    right_ankle=ar,
                    left_foot_squash=sql,
                    right_foot_squash=sqr,
                )
        elif state in ("walk", "run"):
            escala_tornozelo = 1.18 if eh_corrida else 1.0
            phi_esq = (self.phase - pi * 0.5) % tau
            phi_dir = (self.phase + pi * 0.5) % tau
            qe, je, le, te, se = _cinematica_perna_marcha(phi_esq, sin_amp, escala_tornozelo)
            qd, jd, ld, td, sd = _cinematica_perna_marcha(phi_dir, sin_amp, escala_tornozelo)
            c_ph = cos(self.phase)
            target = LegPose(
                qe, qd, je, jd, le, ld,
                left_yaw=3.5,
                right_yaw=-3.5,
                left_roll=-1.5,
                right_roll=1.5,
                left_ankle=te,
                right_ankle=td,
                left_ankle_roll=3.5 * c_ph,
                right_ankle_roll=-3.5 * c_ph,
                left_foot_squash=se,
                right_foot_squash=sd,
            )
        elif state == "fall":
            descent = 0.5 + 0.5 * tanh(velocity[1] / QUEDA_DESCIDA_ESCALA)
            drift = tanh(velocity[0] / QUEDA_DERIVA_ESCALA)
            self.phase += dt * tau * QUEDA_FASE
            u_fall = max(0.0, min(1.0, time / 0.26))
            e_fall = u_fall * u_fall * (3.0 - 2.0 * u_fall)
            apice = sin(u_fall * pi)
            kick = sin(self.phase + 0.45) * (0.20 + 0.80 * e_fall)
            panic = max(0.32, min(1.0, hypot(velocity[0], velocity[1]) / 450.0)) * (0.28 + 0.72 * e_fall)
            qe, qd = QUEDA_QUADRIL_ESQ, QUEDA_QUADRIL_DIR
            je, jd = QUEDA_JOELHO_ESQ, QUEDA_JOELHO_DIR
            tuck_joelho = 18.0 * apice
            target = LegPose(
                (qe[0] - qe[1] * descent + qe[2] * drift) * e_fall + qe[3] * kick * panic - 10.0 * apice,
                (qd[0] - qd[1] * descent - qd[2] * drift) * e_fall - qd[3] * kick * panic - 10.0 * apice,
                (je[0] + je[1] * descent) * e_fall + je[2] * max(0, kick) * panic + tuck_joelho,
                (jd[0] + jd[1] * descent) * e_fall + jd[2] * max(0, -kick) * panic + tuck_joelho,
                max(0, kick) * QUEDA_LIFT_ESQ,
                max(0, -kick) * QUEDA_LIFT_DIR,
                left_roll=drift * 6.0 * e_fall + kick * 5.0 * panic,
                right_roll=drift * 6.0 * e_fall - kick * 5.0 * panic,
                left_ankle=14.0 - 15.0 * kick * panic,
                right_ankle=14.0 + 15.0 * kick * panic,
                left_ankle_roll=drift * 8.0 * e_fall + kick * 6.0,
                right_ankle_roll=drift * 8.0 * e_fall - kick * 6.0,
                left_foot_squash=-0.10,
                right_foot_squash=-0.10,
            )
            if velocity[1] > 0.0 and 0.0 < height_above_floor_px < 160.0:
                prox = suavizar_quintico(1.0 - height_above_floor_px / 160.0) * 0.85
                alvos_pouso = (-8.0, -12.0, 22.0, 26.0, -12.0, -10.0)
                target = LegPose(
                    left=target.left + (alvos_pouso[0] - target.left) * prox,
                    right=target.right + (alvos_pouso[1] - target.right) * prox,
                    left_knee=target.left_knee + (alvos_pouso[2] - target.left_knee) * prox,
                    right_knee=target.right_knee + (alvos_pouso[3] - target.right_knee) * prox,
                    left_lift=target.left_lift * (1.0 - prox),
                    right_lift=target.right_lift * (1.0 - prox),
                    left_roll=target.left_roll * (1.0 - prox),
                    right_roll=target.right_roll * (1.0 - prox),
                    left_ankle=target.left_ankle + (alvos_pouso[4] - target.left_ankle) * prox,
                    right_ankle=target.right_ankle + (alvos_pouso[5] - target.right_ankle) * prox,
                    left_foot_squash=target.left_foot_squash * (1.0 - prox) + 0.12 * prox,
                    right_foot_squash=target.right_foot_squash * (1.0 - prox) + 0.12 * prox,
                )
        elif state == "drag":
            target = self._target_drag_pernas(
                time, sway, grab_part, roll, roll_velocity, resistencia=resistencia
            )
        elif state in ("land", "hit"):
            if state == "land" and heavy_land:
                # Impacto forte: derruba sentado (0..0.35s), encara indignado (0.35..0.95s), levanta (0.95..1.45s).
                t_s = max(0.0, min(1.45, time))
                if t_s < 0.35:
                    f = suavizar_quintico(t_s / 0.35)
                elif t_s < 0.95:
                    f = 1.0
                else:
                    f = 1.0 - suavizar_quintico((t_s - 0.95) / 0.50)
                target = LegPose(
                    -78.0 * f,
                    -74.0 * f,
                    74.0 * f,
                    74.0 * f,
                    left_yaw=8.0 * f,
                    right_yaw=-8.0 * f,
                    left_roll=-5.0 * f,
                    right_roll=5.0 * f,
                    left_ankle=-10.0 * f,
                    right_ankle=-10.0 * f,
                    left_foot_squash=0.26 * f,
                    right_foot_squash=0.26 * f,
                )
            else:
                progresso = max(0.0, min(1.0, time / IMPACTO_DURACAO))
                compress = sin((progresso**0.65) * pi)
                target = LegPose(
                    -IMPACTO_QUADRIL * compress,
                    -IMPACTO_QUADRIL * compress,
                    IMPACTO_JOELHO * compress,
                    IMPACTO_JOELHO * compress,
                    left_ankle=-14.0 * compress,
                    right_ankle=-14.0 * compress,
                    left_foot_squash=0.30 * compress,
                    right_foot_squash=0.30 * compress,
                )
        elif state == "dance":
            if dance_phase is None:
                self.phase += dt * tau * DANCA_FASE
            else:
                self.phase = dance_phase
            clipe_emote = (
                carregar_clipe_emote(dance_style)
                if dance_style != "head_bob"
                else None
            )
            step = sin(self.phase * DANCA_PASSO_FASE) * dance_strength
            step_p = _suave_pos(step)
            step_n = _suave_pos(-step)
            target = LegPose(
                step * DANCA_PASSO_QUADRIL,
                -step * DANCA_PASSO_QUADRIL,
                step_p * DANCA_PASSO_JOELHO,
                step_n * DANCA_PASSO_JOELHO,
                step_p * DANCA_PASSO_LIFT,
                step_n * DANCA_PASSO_LIFT,
            )
            if clipe_emote is not None:
                t_emote = (
                    dance_time
                    if dance_time > 0.0
                    else max(0.0, self.phase / tau) * 0.55
                )
                canais = amostrar_pernas_emote(clipe_emote, t_emote)
                if canais:
                    beat_batida = (0.5 + 0.5 * cos(self.phase)) * max(0.35, dance_strength)
                    sq_batida = 0.16 * (beat_batida ** 2)
                    target = _leg_pose_de_canais(canais, sq_batida)
            elif dance_style == "head_bob":
                # Mario sentado no topo da caixa FNF: balanço vivo de canelas e toe-tap alternado
                amp_b = max(0.50, dance_strength)
                balanco_canelas = sin(self.phase * 0.5) * 16.0 * amp_b
                quique_assento = (0.5 + 0.5 * cos(self.phase)) * 4.0 * amp_b
                tap_e = 14.0 + sin(self.phase * 0.5) * 18.0 * amp_b
                tap_d = 14.0 - sin(self.phase * 0.5) * 18.0 * amp_b
                target = LegPose(
                    -88.0 + quique_assento,
                    -88.0 + quique_assento,
                    60.0 + balanco_canelas,
                    60.0 - balanco_canelas,
                    left_yaw=6.0,
                    right_yaw=-6.0,
                    left_roll=-3.0,
                    right_roll=3.0,
                    left_ankle=tap_e,
                    right_ankle=tap_d,
                    left_foot_squash=-0.08,
                    right_foot_squash=-0.08,
                )
            elif dance_style == "hip_hop":
                sw_hh = sin(self.phase * 0.5)
                quique = (0.5 + 0.5 * cos(self.phase)) * (DANCA_HIPHOP_JOELHO * 1.45)
                sq_beat = 0.24 * (0.5 + 0.5 * cos(self.phase)) ** 2 * max(0.5, dance_strength)
                target = LegPose(
                    target.left + 4.0 * sw_hh,
                    target.right - 4.0 * sw_hh,
                    target.left_knee + quique,
                    target.right_knee + quique,
                    target.left_lift,
                    target.right_lift,
                    left_yaw=8.0 * max(0.0, sw_hh),
                    right_yaw=-8.0 * max(0.0, -sw_hh),
                    left_roll=-4.0 * sw_hh,
                    right_roll=4.0 * sw_hh,
                    left_ankle=-12.0 * max(0.0, step) + 10.0 * max(0.0, -step),
                    right_ankle=-12.0 * max(0.0, -step) + 10.0 * max(0.0, step),
                    left_foot_squash=sq_beat,
                    right_foot_squash=sq_beat,
                )
            elif dance_style == "rock":
                # cos(fase) vale 1 no onset da batida: base aberta de palco e joelho forte no acento.
                absorve = (0.5 + 0.5 * cos(self.phase)) * (DANCA_ROCK_JOELHO * 1.35)
                sq_beat = 0.24 * (0.5 + 0.5 * cos(self.phase)) * max(0.5, dance_strength)
                target = LegPose(
                    step * (DANCA_ROCK_QUADRIL * 1.25) - 6.0,
                    -step * (DANCA_ROCK_QUADRIL * 1.25) - 6.0,
                    absorve + 4.0,
                    absorve + 4.0,
                    left_yaw=10.0,
                    right_yaw=-10.0,
                    left_roll=-5.0,
                    right_roll=5.0,
                    left_ankle=-0.40 * absorve,
                    right_ankle=-0.40 * absorve,
                    left_foot_squash=sq_beat,
                    right_foot_squash=sq_beat,
                )
            elif dance_style == "cyber_bounce":
                bounce = (0.5 + 0.5 * cos(self.phase)) ** 2 * 14.0 * max(0.5, dance_strength)
                sq_beat = 0.24 * (0.5 + 0.5 * cos(self.phase)) ** 2 * max(0.5, dance_strength)
                target = LegPose(
                    step * 9.0,
                    -step * 9.0,
                    bounce + max(0, step) * 8.0,
                    bounce + max(0, -step) * 8.0,
                    max(0, step) * 0.016,
                    max(0, -step) * 0.016,
                    left_ankle=-0.35 * bounce + 10.0 * max(0, step),
                    right_ankle=-0.35 * bounce + 10.0 * max(0, -step),
                    left_foot_squash=sq_beat * (1.0 - max(0, step)),
                    right_foot_squash=sq_beat * (1.0 - max(0, -step)),
                )
            elif dance_style == "street_groove":
                beat = (self.phase / tau) % 2.0
                fase_d = suavizar_quintico(sin(pi * min(1.0, max(0.0, beat))))
                fase_e = suavizar_quintico(sin(pi * min(1.0, max(0.0, beat - 1.0))))
                quique = (0.5 + 0.5 * cos(self.phase * 2.0)) * 7.5
                target = LegPose(
                    left=-16.0 * fase_e + 6.0 * fase_d,
                    right=-16.0 * fase_d + 6.0 * fase_e,
                    left_knee=quique + 20.0 * fase_e,
                    right_knee=quique + 20.0 * fase_d,
                    left_lift=0.024 * fase_e,
                    right_lift=0.024 * fase_d,
                    left_yaw=14.0 * fase_e,
                    right_yaw=-14.0 * fase_d,
                    left_roll=-14.0 * fase_e,
                    right_roll=14.0 * fase_d,
                    left_ankle=14.0 * fase_e - 6.0 * fase_d,
                    right_ankle=14.0 * fase_d - 6.0 * fase_e,
                    left_ankle_roll=9.0 * fase_e,
                    right_ankle_roll=-9.0 * fase_d,
                    left_foot_squash=0.18 * (1.0 - fase_e),
                    right_foot_squash=0.18 * (1.0 - fase_d),
                )
            elif dance_style == "graffiti_dance":
                apoio = (0.5 + 0.5 * cos(self.phase * 0.5)) * 7.0
                target = LegPose(
                    step * 6.0,
                    -step * 6.0,
                    apoio + 6.0,
                    apoio + 6.0,
                    left_ankle=-0.3 * apoio + 8.0 * step,
                    right_ankle=-0.3 * apoio - 8.0 * step,
                    left_foot_squash=0.14 * (apoio / 7.0),
                    right_foot_squash=0.14 * (apoio / 7.0),
                )
            elif dance_style == "walkman_shuffle":
                sw = sin(self.phase)
                bounce = (0.5 + 0.5 * cos(self.phase * 2.0)) * 9.0 * max(0.45, dance_strength)
                target = LegPose(
                    left=-12.0 * max(0.0, sw) + 6.0 * max(0.0, -sw),
                    right=-12.0 * max(0.0, -sw) + 6.0 * max(0.0, sw),
                    left_knee=bounce + 16.0 * max(0.0, sw),
                    right_knee=bounce + 16.0 * max(0.0, -sw),
                    left_lift=0.018 * max(0.0, sw),
                    right_lift=0.018 * max(0.0, -sw),
                    left_yaw=10.0 * sw,
                    right_yaw=-10.0 * sw,
                    left_ankle=10.0 * max(0.0, sw) - 5.0 * max(0.0, -sw),
                    right_ankle=10.0 * max(0.0, -sw) - 5.0 * max(0.0, sw),
                    left_foot_squash=0.16 * (1.0 - max(0.0, sw)),
                    right_foot_squash=0.16 * (1.0 - max(0.0, -sw)),
                )
            elif dance_style == "funk_glide":
                slide = sin(self.phase * 0.5)
                pulse = (0.5 + 0.5 * cos(self.phase)) * 11.0 * max(0.45, dance_strength)
                target = LegPose(
                    left=slide * 10.0 - 6.0,
                    right=-slide * 10.0 - 6.0,
                    left_knee=pulse + 6.0,
                    right_knee=pulse + 6.0,
                    left_yaw=12.0 * abs(slide),
                    right_yaw=-12.0 * abs(slide),
                    left_roll=-6.0 - 5.0 * slide,
                    right_roll=6.0 - 5.0 * slide,
                    left_ankle=-0.4 * pulse + 8.0 * slide,
                    right_ankle=-0.4 * pulse - 8.0 * slide,
                    left_ankle_roll=6.0 * slide,
                    right_ankle_roll=-6.0 * slide,
                    left_foot_squash=0.14 * (0.5 + 0.5 * cos(self.phase)),
                    right_foot_squash=0.14 * (0.5 + 0.5 * cos(self.phase)),
                )
            elif dance_style == "cyber_skank":
                sk = sin(self.phase)
                lift_l = max(0.0, sk)
                lift_r = max(0.0, -sk)
                punch = (0.5 + 0.5 * cos(self.phase * 2.0)) * 12.0 * max(0.5, dance_strength)
                target = LegPose(
                    left=-20.0 * lift_l + 6.0 * lift_r,
                    right=-20.0 * lift_r + 6.0 * lift_l,
                    left_knee=punch + 26.0 * lift_l,
                    right_knee=punch + 26.0 * lift_r,
                    left_lift=0.028 * lift_l,
                    right_lift=0.028 * lift_r,
                    left_yaw=12.0 * lift_l,
                    right_yaw=-12.0 * lift_r,
                    left_roll=-8.0 * lift_l,
                    right_roll=8.0 * lift_r,
                    left_ankle=14.0 * lift_l - 8.0 * lift_r,
                    right_ankle=14.0 * lift_r - 8.0 * lift_l,
                    left_foot_squash=0.20 * (1.0 - lift_l),
                    right_foot_squash=0.20 * (1.0 - lift_r),
                )
            elif dance_style == "breakdance":
                beat = self.phase / tau % dtune.FRASE_BATIDAS
                floor_lin = max(
                    0.0,
                    min(
                        1.0,
                        (beat - dtune.FLOOR_INICIO) / dtune.FLOOR_SUBIDA,
                        (dtune.FLOOR_FIM - beat) / dtune.FLOOR_DESCIDA,
                    ),
                )
                floor = suavizar_quintico(floor_lin)
                bf = DANCA_BREAK_QUADRIL_FLOOR
                bj = DANCA_BREAK_JOELHO
                target = LegPose(
                    step * DANCA_BREAK_QUADRIL + floor * bf[0],
                    -step * DANCA_BREAK_QUADRIL - floor * bf[1],
                    bj[0] + floor * bj[1],
                    bj[0] + floor * bj[2],
                    left_ankle=16.0 * floor - 8.0 * step_p,
                    right_ankle=16.0 * floor - 8.0 * step_n,
                    left_ankle_roll=10.0 * floor,
                    right_ankle_roll=-10.0 * floor,
                )
        elif state == "virtual_insanity":
            # Base baixa e plantada estilo Jamiroquai: joelhos flexionados e zero quique.
            deslize = sin(time * 2.2) * 2.0
            target = LegPose(
                left=-14.0 + deslize,
                right=12.0 - deslize,
                left_knee=22.0,
                right_knee=20.0,
                left_yaw=9.0,
                right_yaw=-9.0,
                left_roll=-6.0,
                right_roll=6.0,
            )
        elif state == "goku_teleport":
            # Base marcial firme de Dragon Ball (Shunkan Idō): joelhos semi-flexionados e pés plantados.
            target = LegPose(
                left=-13.0,
                right=-11.0,
                left_knee=24.0,
                right_knee=22.0,
                left_yaw=10.0,
                right_yaw=-10.0,
                left_roll=-5.0,
                right_roll=5.0,
                left_ankle=-10.0,
                right_ankle=-10.0,
            )
        elif state == "blue_balls":
            # Choque elétrico inicial com transição quíntica contínua para agachamento dobrado.
            blend = suavizar_quintico(max(0.0, min(1.0, (time - 0.28) / 0.14)))
            inv_b = 1.0 - blend
            tremor = sin(time * 48.0) * 3.0 * inv_b
            latejo = (0.5 - 0.5 * cos(max(0.0, time - 0.28) * 9.0)) * 4.5 * blend
            target = LegPose(
                left=(4.0 + tremor) * inv_b - 18.0 * blend,
                right=(4.0 - tremor) * inv_b - 18.0 * blend,
                left_knee=8.0 * inv_b + (40.0 + latejo) * blend,
                right_knee=8.0 * inv_b + (40.0 + latejo) * blend,
                left_yaw=8.0 * blend,
                right_yaw=-8.0 * blend,
                left_roll=-6.0 * blend,
                right_roll=6.0 * blend,
            )
        elif state == "sit":
            ent = suavizar_quintico(min(1.0, max(0.0, time) / 0.45))
            bal = sin(time * 1.4) * 3.5 * ent
            target = LegPose(
                left=-80.0 * ent,
                right=-78.0 * ent,
                left_knee=34.0 * ent + _suave_pos(bal),
                right_knee=36.0 * ent + _suave_pos(-bal),
                left_yaw=18.0 * ent,
                right_yaw=-18.0 * ent,
                left_roll=-6.0 * ent,
                right_roll=6.0 * ent,
                left_ankle=-10.0 * ent + bal,
                right_ankle=-10.0 * ent - bal,
                left_ankle_roll=-5.0 * ent,
                right_ankle_roll=5.0 * ent,
            )
        elif state == "jump":
            coil = suavizar_quintico(max(0.0, min(1.0, time / 0.11)))
            if time <= 0.11:
                target = LegPose(
                    left=-28.0 * coil,
                    right=-26.0 * coil,
                    left_knee=54.0 * coil,
                    right_knee=52.0 * coil,
                    left_yaw=8.0 * coil,
                    right_yaw=-8.0 * coil,
                    left_ankle=-16.0 * coil,
                    right_ankle=-16.0 * coil,
                    left_foot_squash=0.22 * coil,
                    right_foot_squash=0.22 * coil,
                )
            else:
                voo = suavizar_quintico(min(1.0, max(0.0, time - 0.11) / 0.15))
                inv_v = 1.0 - voo
                target = LegPose(
                    left=-28.0 * inv_v - 38.0 * voo,
                    right=-26.0 * inv_v - 10.0 * voo,
                    left_knee=54.0 * inv_v + 60.0 * voo,
                    right_knee=52.0 * inv_v + 22.0 * voo,
                    left_yaw=8.0 * inv_v + 6.0 * voo,
                    right_yaw=-8.0 * inv_v - 6.0 * voo,
                    left_ankle=-16.0 * inv_v + 16.0 * voo,
                    right_ankle=-16.0 * inv_v + 20.0 * voo,
                    left_foot_squash=0.22 * inv_v - 0.10 * voo,
                    right_foot_squash=0.22 * inv_v - 0.10 * voo,
                )
        elif state == "sleep":
            entrada = suavizar_quintico((time - 0.25) / 1.75)
            resp_s = sin(time * 1.15) * entrada
            # Sentado no chão com pernas abertas em V (anatomicamente limpo no rig!)
            # e deitado com micro-respiração relaxada nas pernas.
            target = {
                "sentado": LegPose(
                    -82.0 * entrada + 0.8 * resp_s,
                    -80.0 * entrada - 0.6 * resp_s,
                    26.0 * entrada + 1.2 * resp_s,
                    28.0 * entrada + 1.0 * resp_s,
                    left_yaw=22.0 * entrada,
                    right_yaw=-22.0 * entrada,
                    left_roll=-8.0 * entrada,
                    right_roll=8.0 * entrada,
                    left_ankle=-12.0 * entrada + 1.4 * resp_s,
                    right_ankle=-10.0 * entrada + 1.2 * resp_s,
                    left_ankle_roll=-6.0 * entrada,
                    right_ankle_roll=6.0 * entrada,
                ),
                "deitado": LegPose(
                    -30.0 * entrada + 1.4 * resp_s,
                    -22.0 * entrada - 1.0 * resp_s,
                    45.0 * entrada + 1.8 * resp_s,
                    40.0 * entrada + 1.4 * resp_s,
                    left_ankle=20.0 * entrada + 1.8 * resp_s,
                    right_ankle=20.0 * entrada + 1.5 * resp_s,
                ),
            }.get(
                modo_sono,
                LegPose(
                    0.5 * resp_s,
                    -0.5 * resp_s,
                    4.0 + 1.4 * (0.5 + 0.5 * resp_s),
                    4.0 + 1.4 * (0.5 + 0.5 * resp_s),
                    left_ankle=-1.5 * (0.5 + 0.5 * resp_s),
                    right_ankle=-1.5 * (0.5 + 0.5 * resp_s),
                ),
            )
        elif (
            reacao := self._target_reacao_pernas(
                state,
                time,
                reaction_part,
                reaction_direction=reaction_direction,
                teimosia_fase=teimosia_fase,
            )
        ) is not None:
            target = reacao
        elif state in ("idle", "hover"):
            # Completa o pouso do passo se acabou de sair de walk/run antes do repouso.
            if self._estado and self._estado[0] in ("walk", "run"):
                passo_neutro = round(self.phase / pi) * pi
                erro_passo = passo_neutro - self.phase
                if abs(erro_passo) > 0.05:
                    self.phase += erro_passo * min(1.0, dt * 14.0)
            # Transferência de peso orgânica e micro-respiração nos joelhos
            # (inclui ginga discreta nas cenas de idle sem agachamento explícito).
            groove_cena = 1.6 if cena_nome in ("escutar_fone", "batida_guardada") else (
                1.25 if cena_nome else 1.0
            )
            balanco_tempo = sin(time * (2.6 if cena_nome in ("escutar_fone", "batida_guardada") else 0.9)) * 0.6 + sin(time * 0.35) * 0.4
            shift = max(-1.0, min(1.0, (sway / IDLE_SWAY_ESCALA + balanco_tempo * 0.7) * groove_cena))
            if respiracao is not None and cena_nome not in ("escutar_fone", "batida_guardada"):
                respiro_joelho = max(0.0, min(1.0, 0.5 + 0.5 * float(respiracao))) * (3.8 * groove_cena)
            else:
                respiro_joelho = (0.5 + 0.5 * cos(time * (3.2 if cena_nome in ("escutar_fone", "batida_guardada") else 1.5))) * (3.5 * groove_cena)
            joelho_e = max(0.0, shift) * IDLE_JOELHO + respiro_joelho
            joelho_d = max(0.0, -shift) * IDLE_JOELHO + respiro_joelho
            target = LegPose(
                IDLE_QUADRIL * shift,
                -IDLE_QUADRIL * shift,
                joelho_e,
                joelho_d,
                left_yaw=5.0,
                right_yaw=-5.0,
                left_roll=-2.5,
                right_roll=2.5,
                left_ankle=-4.0 * shift - 0.45 * joelho_e,
                right_ankle=4.0 * shift - 0.45 * joelho_d,
                left_ankle_roll=3.0 * shift,
                right_ankle_roll=-3.0 * shift,
                left_foot_squash=max(0.0, -shift) * 0.07 + 0.03 * (respiro_joelho / 3.5),
                right_foot_squash=max(0.0, shift) * 0.07 + 0.03 * (respiro_joelho / 3.5),
                left_ankle_yaw=4.5,
                right_ankle_yaw=-4.5,
            )
            if self._tempo_freada < self._duracao_freada:
                self._tempo_freada = min(self._duracao_freada, self._tempo_freada + dt)
                target = self._aplicar_freada_zzz(target)
        # Inercialização Hermite C1 contínua para pernas (elimina quina de velocidade nas trocas).
        pose_prev = astuple(self.pose)
        estado_anterior = self._estado
        if chave != self._estado:
            self._estado = chave
            alvo_t = astuple(target)
            vel_atual = getattr(self, "_vel_pernas", (0.0,) * len(pose_prev))
            self._inercia_offset = tuple(p - a for p, a in zip(pose_prev, alvo_t, strict=True))
            self._inercia_vel = vel_atual
            self._transicao_tempo = 0.0
            self._duracao_transicao_atual = self._calcular_duracao_transicao(
                state, estado_anterior, chave, acao_nome, cena_nome
            )
        duracao = max(0.08, getattr(self, "_duracao_transicao_atual", 0.32))
        self._transicao_tempo = min(duracao, self._transicao_tempo + dt)
        alvo_t = astuple(target)
        offsets = getattr(self, "_inercia_offset", None)
        if offsets is not None and self._transicao_tempo < duracao:
            u = self._transicao_tempo / duracao
            # Polinômio Hermite cúbico que parte de (offset, vel*dur) e zera suave em u=1.
            h00 = 2.0 * u * u * u - 3.0 * u * u + 1.0
            h10 = u * u * u - 2.0 * u * u + u
            vels = getattr(self, "_inercia_vel", (0.0,) * len(alvo_t))
            nova = tuple(
                a + o * h00 + v * duracao * h10 * 0.35
                for a, o, v in zip(alvo_t, offsets, vels, strict=True)
            )
            self.pose = LegPose(*nova)
        else:
            self.pose = target
            self._inercia_offset = None
        self.pose = _limitar_aducao_pernas(self.pose)
        if dt > 1e-4:
            nova_t = astuple(self.pose)
            self._vel_pernas = tuple(
                max(-220.0, min(220.0, (n - p) / dt))
                for n, p in zip(nova_t, pose_prev, strict=True)
            )
        return self.pose

    def _calcular_duracao_transicao(
        self,
        state: str,
        estado_anterior: object,
        chave: object,
        acao_nome: str | None,
        cena_nome: str,
    ) -> float:
        """Escolhe crossfade suave sem estalos nos joelhos em trocas de ação/cena."""
        sair_de_joelho_alto = max(abs(self.pose.left_knee), abs(self.pose.right_knee)) > 26.0
        veio_loco, veio_corrida = _eh_chave_locomocao(estado_anterior)
        if veio_loco and state in ("idle", "hover") and not acao_nome and not cena_nome:
            return 0.22 if (veio_corrida or sair_de_joelho_alto) else 0.17
        if state in ("drag", "fall", "hit", "blue_balls") and not acao_nome:
            return 0.16
        if acao_nome:
            return 0.30 if (isinstance(estado_anterior, tuple) and estado_anterior[0] == "acao") else 0.24
        if cena_nome or (isinstance(estado_anterior, tuple) and estado_anterior[0] == "cena"):
            return 0.42 if sair_de_joelho_alto else 0.32
        if sair_de_joelho_alto and state in ("idle", "hover", "wake"):
            return 0.44
        if state == "teimosia":
            return 0.24
        return 0.20 if state == "virtual_insanity" else 0.32
