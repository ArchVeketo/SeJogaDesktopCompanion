"""Independent hip/knee motion, in degrees; no engine dependencies."""

from dataclasses import astuple, dataclass
from math import acos, atan2, cos, degrees, hypot, pi, radians, sin, tanh, tau

from sejoga.animacao import danca_tuning as dtune
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

# Aterrissagem/pancada: compressão temporal.
IMPACTO_DURACAO = 0.50
IMPACTO_QUADRIL = 24.0
IMPACTO_JOELHO = 46.0

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


def apoiar_passada(quadril, joelho, coxa, canela, elevacao):
    """Mantém o arco horizontal do FK e resolve o apoio vertical por IK."""
    y = coxa * sin(radians(quadril)) + canela * sin(radians(quadril + joelho))
    z = coxa + canela - elevacao
    alcance = min(coxa + canela - 1e-5, max(abs(coxa - canela) + 1e-5, hypot(y, z)))
    flexao = acos((alcance**2 - coxa**2 - canela**2) / (2 * coxa * canela))
    direcao = atan2(y, z)
    correcao = atan2(canela * sin(flexao), coxa + canela * cos(flexao))
    return degrees(direcao - correcao), degrees(flexao)


class LegMotion:
    """Fase da passada e transições entre poses das pernas."""

    def __init__(self):
        """Inicia as pernas paradas."""
        self.pose = LegPose()
        self.phase = 0.0
        self._transicao_de = self.pose
        self._transicao_tempo = 0.0
        self._estado = None

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
    ):
        """Avança as pernas um passo e devolve a pose resultante."""
        dt = max(0, min(DT_MAXIMO, dt))
        target = LegPose()
        if state in ("walk", "run"):
            vx = abs(velocity[0]) if velocity else 0.0
            vel_ref = 285.0 if state == "run" else 160.0
            # Acopla cadência e amplitude ao deslocamento real quando há velocidade horizontal
            # (sem alterar testes estáticos que passam velocity=(0, 0)).
            escala_vel = (
                max(0.72, min(1.55, vx / vel_ref)) if vx > 5.0 else 1.0
            )
            escala_amp = 0.78 + 0.22 * min(1.35, escala_vel)
            self.phase += (
                dt * tau * (FASE_CORRIDA if state == "run" else FASE_CAMINHADA) * escala_vel
            )
            # ``left < 0`` gira a coxa para a frente (-Y local); com ``-sin`` a
            # perna erguida no balanço (cos > 0) avança de trás para a frente,
            # sincronizada com a contrafase dos braços (braço dir. à frente em pi/2).
            stride = -sin(self.phase)
            amplitude = (
                AMPLITUDE_CORRIDA if state == "run" else AMPLITUDE_CAMINHADA
            ) * escala_amp
            # Flexão no começo do balanço, extensão antes de apoiar a sola.
            balanco_esq = max(0, cos(self.phase))
            balanco_dir = max(0, -cos(self.phase))
            target = LegPose(
                stride * amplitude,
                -stride * amplitude,
                balanco_esq * PASSADA_JOELHO,
                balanco_dir * PASSADA_JOELHO,
                balanco_esq * PASSADA_LIFT,
                balanco_dir * PASSADA_LIFT,
            )
        elif state == "fall":
            descent = 0.5 + 0.5 * tanh(velocity[1] / QUEDA_DESCIDA_ESCALA)
            drift = tanh(velocity[0] / QUEDA_DERIVA_ESCALA)
            self.phase += dt * tau * QUEDA_FASE
            kick = sin(self.phase + 0.45)
            panic = max(0.45, min(1.0, hypot(velocity[0], velocity[1]) / 450.0))
            qe, qd = QUEDA_QUADRIL_ESQ, QUEDA_QUADRIL_DIR
            je, jd = QUEDA_JOELHO_ESQ, QUEDA_JOELHO_DIR
            target = LegPose(
                qe[0] - qe[1] * descent + qe[2] * drift + qe[3] * kick * panic,
                qd[0] - qd[1] * descent - qd[2] * drift - qd[3] * kick * panic,
                je[0] + je[1] * descent + je[2] * max(0, kick) * panic,
                jd[0] + jd[1] * descent + jd[2] * max(0, -kick) * panic,
                max(0, kick) * QUEDA_LIFT_ESQ,
                max(0, -kick) * QUEDA_LIFT_DIR,
                left_roll=drift * 6.0 + kick * 5.0 * panic,
                right_roll=drift * 6.0 - kick * 5.0 * panic,
            )
        elif state == "drag":
            # Esperneio cômico e ativo no ar: pernas pedalando
            pedal_fase = time * 12.0
            pedal_esq = sin(pedal_fase) * 16.0
            pedal_dir = -sin(pedal_fase) * 16.0
            joelho_pedal_esq = max(6.0, cos(pedal_fase) * 24.0)
            joelho_pedal_dir = max(6.0, -cos(pedal_fase) * 24.0)
            target = LegPose(
                pedal_esq + sway * 0.5,
                pedal_dir + sway * 0.5,
                joelho_pedal_esq + abs(sway) * 0.2,
                joelho_pedal_dir + abs(sway) * 0.2,
            )
        elif state in ("land", "hit"):
            progresso = max(0.0, min(1.0, time / IMPACTO_DURACAO))
            compress = sin((progresso**0.65) * 3.14159265)
            target = LegPose(
                -IMPACTO_QUADRIL * compress,
                -IMPACTO_QUADRIL * compress,
                IMPACTO_JOELHO * compress,
                IMPACTO_JOELHO * compress,
            )
        elif state == "dance":
            if dance_phase is None:
                self.phase += dt * tau * DANCA_FASE
            else:
                self.phase = dance_phase
            step = sin(self.phase * DANCA_PASSO_FASE) * dance_strength
            target = LegPose(
                step * DANCA_PASSO_QUADRIL,
                -step * DANCA_PASSO_QUADRIL,
                max(0, step) * DANCA_PASSO_JOELHO,
                max(0, -step) * DANCA_PASSO_JOELHO,
                max(0, step) * DANCA_PASSO_LIFT,
                max(0, -step) * DANCA_PASSO_LIFT,
            )
            if dance_style == "head_bob":
                # Mario sentado no topo da jukebox estilo FNF Girlfriend:
                # Coxas apoiadas à frente no topo da caixa e pernas balançando alternadas ao som
                balanco_canelas = (
                    sin(self.phase * 0.5) * 9.0 * max(0.4, dance_strength)
                )
                quique_assento = (0.5 + 0.5 * cos(self.phase)) * 2.5 * dance_strength
                target = LegPose(
                    -88.0 + quique_assento,
                    -88.0 + quique_assento,
                    62.0 + balanco_canelas,
                    62.0 - balanco_canelas,
                )
            elif dance_style == "hip_hop":
                quique = (0.5 + 0.5 * cos(self.phase)) * DANCA_HIPHOP_JOELHO
                target = LegPose(
                    target.left,
                    target.right,
                    target.left_knee + quique,
                    target.right_knee + quique,
                    target.left_lift,
                    target.right_lift,
                )
            elif dance_style == "rock":
                # cos(fase) vale 1 no onset da batida: o joelho flexiona no acento.
                absorve = (0.5 + 0.5 * cos(self.phase)) * DANCA_ROCK_JOELHO
                target = LegPose(
                    step * DANCA_ROCK_QUADRIL,
                    -step * DANCA_ROCK_QUADRIL,
                    absorve,
                    absorve,
                )
            elif dance_style == "cyber_bounce":
                bounce = (0.5 + 0.5 * cos(self.phase)) ** 2 * 14.0 * max(0.5, dance_strength)
                target = LegPose(
                    step * 9.0,
                    -step * 9.0,
                    bounce + max(0, step) * 8.0,
                    bounce + max(0, -step) * 8.0,
                    max(0, step) * 0.016,
                    max(0, -step) * 0.016,
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
                    left_yaw=-14.0 * fase_e,
                    right_yaw=14.0 * fase_d,
                    left_roll=14.0 * fase_e,
                    right_roll=-14.0 * fase_d,
                )
            elif dance_style == "graffiti_dance":
                apoio = (0.5 + 0.5 * cos(self.phase * 0.5)) * 7.0
                target = LegPose(
                    step * 6.0,
                    -step * 6.0,
                    apoio + 6.0,
                    apoio + 6.0,
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
                )
        elif state == "virtual_insanity":
            # Base baixa e plantada estilo Jamiroquai: joelhos flexionados e zero quique.
            deslize = sin(time * 2.2) * 2.0
            target = LegPose(
                left=-14.0 + deslize,
                right=12.0 - deslize,
                left_knee=22.0,
                right_knee=20.0,
                left_yaw=-8.0,
                right_yaw=8.0,
                left_roll=5.0,
                right_roll=-5.0,
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
                "sentado": LegPose(-82.0 * entrada, -80.0 * entrada, 78.0 * entrada, 76.0 * entrada),
                "deitado": LegPose(-30.0, -22.0, 45.0, 40.0),
            }.get(modo_sono, LegPose(0.0, 0.0, 4.0, 4.0))
        elif state in ("idle", "hover"):
            # Completa o pouso do passo se acabou de sair de walk/run antes do repouso.
            if self._estado and self._estado[0] in ("walk", "run"):
                passo_neutro = round(self.phase / pi) * pi
                erro_passo = passo_neutro - self.phase
                if abs(erro_passo) > 0.05:
                    self.phase += erro_passo * min(1.0, dt * 14.0)
            # Transferência de peso orgânica e micro-respiração nos joelhos
            balanco_tempo = sin(time * 0.9) * 0.6 + sin(time * 0.35) * 0.4
            shift = max(-1.0, min(1.0, sway / IDLE_SWAY_ESCALA + balanco_tempo * 0.7))
            respiro_joelho = (0.5 + 0.5 * cos(time * 1.5)) * 3.5
            target = LegPose(
                IDLE_QUADRIL * shift,
                -IDLE_QUADRIL * shift,
                max(0.0, shift) * IDLE_JOELHO + respiro_joelho,
                max(0.0, -shift) * IDLE_JOELHO + respiro_joelho,
            )
        chave = ("idle", None) if state == "hover" else (
            state, dance_style if state == "dance" else modo_sono if state == "sleep" else None
        )
        if chave != self._estado:
            self._estado = chave
            self._transicao_de = self.pose
            self._transicao_tempo = 0.0
        duracao = 0.14 if state in ("drag", "fall", "hit", "blue_balls") else (
            0.20 if state == "virtual_insanity" else 0.32
        )
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
