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
    flexao = acos((alcance**2 - coxa**2 - canela**2) / (2 * coxa * canela))
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
    ank_e = 14.0 * min(1.0, lift_e * 35.0) - 0.18 * canais.get("left_knee", 0.0)
    ank_d = 14.0 * min(1.0, lift_d * 35.0) - 0.18 * canais.get("right_knee", 0.0)
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
    ) -> LegPose:
        """Calcula pose das pernas no arraste 350° conforme ponto de pega e giro."""
        pedal_fase = time * 12.0
        fator_upe = cos(roll * 0.017453292519943295)
        invertido = max(0.0, -fator_upe)
        whip = max(-22.0, min(22.0, roll_velocity * 1.4))
        centrifugo = min(1.0, abs(roll_velocity) / 14.0)
        if grab_part in ("left-feet", "right-feet"):
            pedal = sin(pedal_fase) * 20.0 - 8.0 + sway * 0.45 + whip * 0.35
            joelho_livre = max(12.0, 26.0 + cos(pedal_fase) * 22.0 + invertido * 12.0)
            fixo = 2.0 + sway * 0.15
            tornozelo_livre = 14.0 + cos(pedal_fase) * 10.0
            if grab_part == "left-feet":
                return LegPose(fixo, pedal, 2.0, joelho_livre, left_ankle=4.0, right_ankle=tornozelo_livre, right_ankle_roll=whip * 0.35, right_foot_squash=-0.08)
            return LegPose(pedal, fixo, joelho_livre, 2.0, left_ankle=tornozelo_livre, right_ankle=4.0, left_ankle_roll=whip * 0.35, left_foot_squash=-0.08)
        if grab_part in ("body", "head", "right-arm", "left-arm"):
            sinal_arm = 1.0 if grab_part == "right-arm" else (-1.0 if grab_part == "left-arm" else 0.0)
            pendulo = sway * 0.78 + whip * 0.52 - invertido * 15.0
            assimetria = 6.0 * sinal_arm + sin(time * 3.6) * (5.0 + 3.5 * invertido)
            joelho = max(10.0, (24.0 + abs(sway) * 0.30 + invertido * 28.0) * (1.0 - 0.50 * centrifugo))
            ponta = 26.0 * fator_upe - whip * 0.34
            roll_solto = max(-22.0, min(22.0, sway * 0.32 + whip * 0.42))
            return LegPose(
                pendulo - assimetria, pendulo + assimetria, joelho, joelho,
                left_ankle=ponta + 4.5 * sinal_arm + sin(time * 3.5) * 4.5,
                right_ankle=ponta - 4.5 * sinal_arm - sin(time * 3.5) * 4.5,
                left_ankle_roll=roll_solto, right_ankle_roll=roll_solto if sinal_arm else -roll_solto,
                left_foot_squash=-0.14 * (1.0 + centrifugo), right_foot_squash=-0.14 * (1.0 + centrifugo),
            )
        return LegPose(
            sin(pedal_fase) * 16.0 + sway * 0.5 + whip * 0.3,
            -sin(pedal_fase) * 16.0 + sway * 0.5 + whip * 0.3,
            max(6.0, cos(pedal_fase) * 24.0 + invertido * 14.0) + abs(sway) * 0.2,
            max(6.0, -cos(pedal_fase) * 24.0 + invertido * 14.0) + abs(sway) * 0.2,
            left_ankle=8.0 + sin(pedal_fase) * 12.0, right_ankle=8.0 - sin(pedal_fase) * 12.0,
        )

    @staticmethod
    def _reacao_celebrate(time: float) -> LegPose:
        u = max(0.0, min(1.0, time / 2.0))
        if u < 0.16:
            carga = sin((u / 0.16) * pi)
            return LegPose(
                left=-28.0 * carga, right=-28.0 * carga,
                left_knee=52.0 * carga, right_knee=52.0 * carga,
                left_ankle=-14.0 * carga, right_ankle=-14.0 * carga,
                left_foot_squash=0.20 * carga, right_foot_squash=0.20 * carga,
            )
        if u > 0.82:
            pouso = sin(((u - 0.82) / 0.18) * pi)
            return LegPose(
                left=-16.0 * pouso, right=-16.0 * pouso,
                left_knee=30.0 * pouso, right_knee=30.0 * pouso,
                left_ankle=-8.0 * pouso, right_ankle=-8.0 * pouso,
                left_foot_squash=0.16 * pouso, right_foot_squash=0.16 * pouso,
            )
        fase = (u - 0.16) / 0.66
        salto = sin(fase * pi)
        batida = max(0.0, sin(fase * 2.0 * pi)) * salto
        balanco = sin(fase * 3.0 * pi) * 8.0 * salto
        return LegPose(
            left=-12.0 * salto + balanco, right=-12.0 * salto - balanco,
            left_knee=18.0 * salto + 16.0 * batida,
            right_knee=18.0 * salto + 16.0 * (1.0 - batida) * salto,
            left_lift=0.032 * salto, right_lift=0.028 * salto,
            left_ankle=12.0 * batida - 7.0 * salto,
            right_ankle=12.0 * (1.0 - batida) * salto - 7.0 * salto,
            left_foot_squash=0.10 * salto - 0.16 * batida,
            right_foot_squash=0.10 * salto - 0.10 * batida,
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
            batida = abs(sin((t - 1.0) * 8.5))
            return LegPose(
                left=-8.0 + 4.0 * batida, right=14.0 - 3.0 * batida,
                left_knee=14.0 + 10.0 * batida, right_knee=22.0 + 8.0 * batida,
                left_yaw=7.0, right_yaw=-9.0, left_roll=-4.0, right_roll=4.0,
                left_ankle=-5.0 * batida, right_ankle=-7.0 * batida,
                left_foot_squash=0.12 * batida, right_foot_squash=0.15 * batida,
            )
        if fase == "bote":
            bt = max(0.0, t - 2.0)
            if bt < 0.36:
                coil = suavizar_quintico(bt / 0.36)
                return LegPose(
                    left=-24.0 * coil, right=-22.0 * coil, left_knee=48.0 * coil, right_knee=46.0 * coil,
                    left_yaw=10.0 * coil, right_yaw=-10.0 * coil, left_ankle=-14.0 * coil, right_ankle=-14.0 * coil,
                    left_foot_squash=0.22 * coil, right_foot_squash=0.22 * coil,
                )
            lunge = suavizar_quintico(min(1.0, (bt - 0.36) / 0.24))
            return LegPose(
                left=34.0 * lunge - 24.0 * (1.0 - lunge), right=-28.0 * lunge - 22.0 * (1.0 - lunge),
                left_knee=42.0 * lunge + 48.0 * (1.0 - lunge), right_knee=14.0 * lunge + 46.0 * (1.0 - lunge),
                left_yaw=8.0, right_yaw=-12.0, left_ankle=-8.0, right_ankle=14.0 * lunge,
                left_foot_squash=0.16, right_foot_squash=-0.06 * lunge,
            )
        if fase == "roubo":
            return LegPose(
                left=22.0, right=-18.0, left_knee=36.0, right_knee=24.0,
                left_yaw=6.0, right_yaw=-6.0, left_ankle=-8.0, right_ankle=10.0,
                left_foot_squash=0.14, right_foot_squash=0.06,
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
        prep = suavizar_quintico(min(1.0, t / 0.85)) * (
            1.0 - suavizar_quintico(max(0.0, min(1.0, (t - 1.25) / 0.45)))
        )
        env_rajada = suavizar_quintico(max(0.0, min(1.0, (t - 1.20) / 0.40))) * (
            1.0 - suavizar_quintico(max(0.0, min(1.0, (t - 3.95) / 0.65)))
        )
        env_tontura = suavizar_quintico(max(0.0, min(1.0, (t - 4.05) / 0.65))) * (
            1.0 - suavizar_quintico(max(0.0, min(1.0, (t - 7.75) / 1.15)))
        )
        tremor = sin(t * 14.0) * 1.5 * prep
        rajada = (0.35 + 0.65 * abs(sin(max(0.0, t - 1.20) * 3.8))) * env_rajada
        tontura = sin(max(0.0, t - 4.05) * 2.2) * env_tontura
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
        dur_mapa = {"wave": 1.6, "stretch": 1.45, "wake": 1.25, "pet": 1.1, "click": 0.45, "peek": 1.8}
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
                left_knee=10.0 * env + max(0.0, balanco) * 6.0, right_knee=10.0 * env + max(0.0, -balanco) * 6.0,
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
    ):
        """Avança as pernas um passo e devolve a pose resultante."""
        dt = max(0, min(DT_MAXIMO, dt))
        if acao_nome:
            chave = ("acao", acao_nome)
        elif cena_nome:
            chave = ("cena", cena_nome)
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
                freq = max(0.85, min(3.8, v_modelo / max(1e-4, 4.0 * y_amp)))
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
                target = LegPose(
                    left=hl, right=hr, left_knee=kl, right_knee=kr, left_yaw=yl, right_yaw=yr
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
        elif state == "drag":
            target = self._target_drag_pernas(
                time, sway, grab_part, roll, roll_velocity
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
                compress = sin((progresso**0.65) * 3.14159265)
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
            from sejoga.animacao.danca_clipes import (
                amostrar_pernas_emote,
                carregar_clipe_emote,
            )

            clipe_emote = (
                carregar_clipe_emote(dance_style)
                if dance_style != "head_bob"
                else None
            )
            step = sin(self.phase * DANCA_PASSO_FASE) * dance_strength
            target = LegPose(
                step * DANCA_PASSO_QUADRIL,
                -step * DANCA_PASSO_QUADRIL,
                max(0, step) * DANCA_PASSO_JOELHO,
                max(0, -step) * DANCA_PASSO_JOELHO,
                max(0, step) * DANCA_PASSO_LIFT,
                max(0, -step) * DANCA_PASSO_LIFT,
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
                # Mario sentado no topo da jukebox estilo FNF Girlfriend:
                # Coxas apoiadas à frente no topo da caixa e pernas balançando alternadas ao som
                balanco_canelas = (
                    sin(self.phase * 0.5) * 9.0 * max(0.4, dance_strength)
                )
                quique_assento = (0.5 + 0.5 * cos(self.phase)) * 2.5 * dance_strength
                tap_e = 12.0 + sin(self.phase * 0.5) * 14.0 * max(0.4, dance_strength)
                tap_d = 12.0 - sin(self.phase * 0.5) * 14.0 * max(0.4, dance_strength)
                target = LegPose(
                    -88.0 + quique_assento,
                    -88.0 + quique_assento,
                    62.0 + balanco_canelas,
                    62.0 - balanco_canelas,
                    left_ankle=tap_e,
                    right_ankle=tap_d,
                    left_foot_squash=-0.08,
                    right_foot_squash=-0.08,
                )
            elif dance_style == "hip_hop":
                quique = (0.5 + 0.5 * cos(self.phase)) * DANCA_HIPHOP_JOELHO
                sq_beat = 0.22 * (0.5 + 0.5 * cos(self.phase)) ** 2 * dance_strength
                target = LegPose(
                    target.left,
                    target.right,
                    target.left_knee + quique,
                    target.right_knee + quique,
                    target.left_lift,
                    target.right_lift,
                    left_ankle=-10.0 * max(0.0, step) + 8.0 * max(0.0, -step),
                    right_ankle=-10.0 * max(0.0, -step) + 8.0 * max(0.0, step),
                    left_foot_squash=sq_beat,
                    right_foot_squash=sq_beat,
                )
            elif dance_style == "rock":
                # cos(fase) vale 1 no onset da batida: o joelho flexiona no acento.
                absorve = (0.5 + 0.5 * cos(self.phase)) * DANCA_ROCK_JOELHO
                sq_beat = 0.20 * (0.5 + 0.5 * cos(self.phase)) * dance_strength
                target = LegPose(
                    step * DANCA_ROCK_QUADRIL,
                    -step * DANCA_ROCK_QUADRIL,
                    absorve,
                    absorve,
                    left_ankle=-0.35 * absorve,
                    right_ankle=-0.35 * absorve,
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
            elif dance_style == "breakdance":
                beat = self.phase / tau % dtune.FRASE_BATIDAS
                floor = max(
                    0,
                    min(
                        1,
                        (beat - dtune.FLOOR_INICIO) / dtune.FLOOR_SUBIDA,
                        (dtune.FLOOR_FIM - beat) / dtune.FLOOR_DESCIDA,
                    ),
                )
                bf = DANCA_BREAK_QUADRIL_FLOOR
                bj = DANCA_BREAK_JOELHO
                target = LegPose(
                    step * DANCA_BREAK_QUADRIL + floor * bf[0],
                    -step * DANCA_BREAK_QUADRIL - floor * bf[1],
                    bj[0] + floor * bj[1],
                    bj[0] + floor * bj[2],
                    left_ankle=16.0 * floor - 8.0 * max(0, step),
                    right_ankle=16.0 * floor - 8.0 * max(0, -step),
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
        elif state == "blue_balls":
            # Choque elétrico inicial seguido de agachamento dobrado com joelhos travados.
            if time < 0.28:
                tremor = sin(time * 48.0) * 3.0
                target = LegPose(
                    left=4.0 + tremor,
                    right=4.0 - tremor,
                    left_knee=8.0,
                    right_knee=8.0,
                )
            else:
                latejo = max(0.0, sin((time - 0.28) * 9.0)) * 4.5
                target = LegPose(
                    left=-18.0,
                    right=-18.0,
                    left_knee=40.0 + latejo,
                    right_knee=40.0 + latejo,
                    left_yaw=8.0,
                    right_yaw=-8.0,
                    left_roll=-6.0,
                    right_roll=6.0,
                )
        elif state == "sleep":
            entrada = suavizar_quintico((time - 0.30) / 1.75)
            # Poses de sono com joelhos dobrados naturalmente e pés firmes no chão
            target = {
                "sentado": LegPose(
                    -82.0 * entrada,
                    -80.0 * entrada,
                    78.0 * entrada,
                    76.0 * entrada,
                    left_yaw=12.0 * entrada,
                    right_yaw=-12.0 * entrada,
                    left_roll=-7.0 * entrada,
                    right_roll=7.0 * entrada,
                    left_ankle=14.0 * entrada,
                    right_ankle=14.0 * entrada,
                ),
                "deitado": LegPose(
                    -30.0,
                    -22.0,
                    45.0,
                    40.0,
                    left_ankle=20.0,
                    right_ankle=20.0,
                ),
            }.get(modo_sono, LegPose(0.0, 0.0, 4.0, 4.0))
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
            respiro_joelho = (0.5 + 0.5 * cos(time * (3.2 if cena_nome in ("escutar_fone", "batida_guardada") else 1.5))) * (3.5 * groove_cena)
            target = LegPose(
                IDLE_QUADRIL * shift,
                -IDLE_QUADRIL * shift,
                max(0.0, shift) * IDLE_JOELHO + respiro_joelho,
                max(0.0, -shift) * IDLE_JOELHO + respiro_joelho,
                left_yaw=5.0,
                right_yaw=-5.0,
                left_roll=-2.5,
                right_roll=2.5,
                left_ankle=-4.0 * shift - 0.15 * respiro_joelho,
                right_ankle=4.0 * shift - 0.15 * respiro_joelho,
                left_ankle_roll=3.0 * shift,
                right_ankle_roll=-3.0 * shift,
                left_foot_squash=max(0.0, -shift) * 0.07 + 0.03 * (respiro_joelho / 3.5),
                right_foot_squash=max(0.0, shift) * 0.07 + 0.03 * (respiro_joelho / 3.5),
            )
            if self._tempo_freada < self._duracao_freada:
                self._tempo_freada = min(self._duracao_freada, self._tempo_freada + dt)
                target = self._aplicar_freada_zzz(target)
        estado_anterior = self._estado
        if chave != self._estado:
            self._estado = chave
            self._transicao_de = self.pose
            self._transicao_tempo = 0.0
            self._duracao_transicao_atual = self._calcular_duracao_transicao(
                state, estado_anterior, chave, acao_nome, cena_nome
            )
        duracao = getattr(self, "_duracao_transicao_atual", 0.32)
        self._transicao_tempo = min(duracao, self._transicao_tempo + dt)
        peso = suavizar_quintico(self._transicao_tempo / duracao)
        if peso < 1.0:
            self.pose = LegPose(*(
                origem + (alvo - origem) * peso
                for origem, alvo in zip(astuple(self._transicao_de), astuple(target), strict=True)
            ))
        else:
            self.pose = target
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
