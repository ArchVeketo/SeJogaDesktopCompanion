"""Independent hip/knee motion, in degrees; no engine dependencies."""

from dataclasses import dataclass
from math import cos, sin, tanh, tau

from sejoga.animacao import danca_tuning as dtune
from sejoga.animacao.mola_tuning import amortecimento_de, frequencia_de
from sejoga.animacao.movimento_corpo import Spring

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
FASE_CAMINHADA = 1.35
AMPLITUDE_CORRIDA = 20.0
AMPLITUDE_CAMINHADA = 12.0
PASSADA_JOELHO = 22.0
PASSADA_LIFT = 0.035

# Queda: descida/deriva/chute a partir da velocidade de física.
QUEDA_DESCIDA_ESCALA = 320.0
QUEDA_DERIVA_ESCALA = 700.0
QUEDA_FASE = 1.05
QUEDA_QUADRIL_ESQ = (-7.0, 9.0, 4.0, 5.0)  # base, descida, deriva, chute
QUEDA_QUADRIL_DIR = (4.0, 7.0, 3.0, 4.0)
QUEDA_JOELHO_ESQ = (17.0, 13.0, 4.0)  # base, descida, chute
QUEDA_JOELHO_DIR = (12.0, 10.0, 4.0)
QUEDA_LIFT_ESQ = 0.018
QUEDA_LIFT_DIR = 0.016

# Arrasto: resposta ao balanço (sway).
DRAG_QUADRIL = (-3.0, 0.65, 2.0, 0.5)  # esq_base, esq_ganho, dir_base, dir_ganho
DRAG_JOELHO = (5.0, 0.22, 4.0, 0.18)

# Aterrissagem/pancada: compressão temporal.
IMPACTO_DURACAO = 0.45
IMPACTO_QUADRIL = 8.0
IMPACTO_JOELHO = 16.0

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

# Idle/hover: pequeno peso lateral.
IDLE_SWAY_ESCALA = 5.0
IDLE_QUADRIL = 2.0
IDLE_JOELHO = 4.0


@dataclass(frozen=True)
class LegPose:
    """Pose das pernas calculada a cada frame."""

    left: float = 0
    right: float = 0
    left_knee: float = 0
    right_knee: float = 0
    left_lift: float = 0
    right_lift: float = 0


class LegMotion:
    """Fase e molas das pernas na caminhada, corrida e dança."""

    def __init__(self):
        """Inicia as pernas paradas."""
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
            frequencia_de("left-feet"), amortecimento_de("left-feet")
        )
        self._mola_right_lift = Spring(
            frequencia_de("right-feet"), amortecimento_de("right-feet")
        )

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
        personality="calm",
    ):
        """Avança as pernas um passo e devolve a pose resultante."""
        dt = max(0, min(DT_MAXIMO, dt))
        target = LegPose()
        if state in ("walk", "run"):
            self.phase += (
                dt * tau * (FASE_CORRIDA if state == "run" else FASE_CAMINHADA)
            )
            fator_amp = 1.0
            fator_joelho = 1.0
            fator_lift = 1.0
            if personality == "fighter":
                fator_amp, fator_joelho, fator_lift = 0.95, 1.25, 1.2
            elif personality == "street":
                fator_amp, fator_joelho, fator_lift = 1.2, 0.95, 0.9
            elif personality == "playful":
                fator_amp, fator_joelho, fator_lift = 1.1, 1.35, 1.45
            elif personality == "shy":
                fator_amp, fator_joelho, fator_lift = 0.8, 0.75, 0.7
            elif personality == "stylish":
                fator_amp, fator_joelho, fator_lift = 1.1, 1.1, 1.1
            elif personality == "confident":
                fator_amp, fator_joelho, fator_lift = 1.15, 1.0, 1.0
            elif personality == "rhythm":
                fator_amp, fator_joelho, fator_lift = 1.05, 1.2, 1.25

            stride = sin(self.phase)
            amplitude = (AMPLITUDE_CORRIDA if state == "run" else AMPLITUDE_CAMINHADA) * fator_amp
            p_joelho = PASSADA_JOELHO * fator_joelho
            p_lift = PASSADA_LIFT * fator_lift
            target = LegPose(
                stride * amplitude,
                -stride * amplitude,
                max(0, stride) * p_joelho,
                max(0, -stride) * p_joelho,
                max(0, stride) * p_lift,
                max(0, -stride) * p_lift,
            )
        elif state == "fall":
            descent = 0.5 + 0.5 * tanh(velocity[1] / QUEDA_DESCIDA_ESCALA)
            drift = tanh(velocity[0] / QUEDA_DERIVA_ESCALA)
            self.phase += dt * tau * QUEDA_FASE
            kick = sin(self.phase)
            qe, qd = QUEDA_QUADRIL_ESQ, QUEDA_QUADRIL_DIR
            je, jd = QUEDA_JOELHO_ESQ, QUEDA_JOELHO_DIR
            target = LegPose(
                qe[0] - qe[1] * descent + qe[2] * drift + qe[3] * kick,
                qd[0] - qd[1] * descent - qd[2] * drift - qd[3] * kick,
                je[0] + je[1] * descent + je[2] * max(0, kick),
                jd[0] + jd[1] * descent + jd[2] * max(0, -kick),
                max(0, kick) * QUEDA_LIFT_ESQ,
                max(0, -kick) * QUEDA_LIFT_DIR,
            )
        elif state == "drag":
            dq, dj = DRAG_QUADRIL, DRAG_JOELHO
            target = LegPose(
                dq[0] + sway * dq[1],
                dq[2] + sway * dq[3],
                dj[0] + abs(sway) * dj[1],
                dj[2] + abs(sway) * dj[3],
            )
        elif state in ("land", "hit"):
            compress = sin(min(1, time / IMPACTO_DURACAO) * 3.14159265)
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
                balanco_canelas = sin(self.phase * 0.5) * 16.0 * max(0.4, dance_strength)
                quique_assento = (0.5 + 0.5 * cos(self.phase)) * 2.5 * dance_strength
                target = LegPose(
                    -68.0 + quique_assento,
                    -68.0 + quique_assento,
                    78.0 + balanco_canelas,
                    78.0 - balanco_canelas,
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
        elif state in ("idle", "hover"):
            shift = max(-1, min(1, sway / IDLE_SWAY_ESCALA))
            target = LegPose(
                IDLE_QUADRIL * shift,
                -IDLE_QUADRIL * shift,
                max(0, shift) * IDLE_JOELHO,
                max(0, -shift) * IDLE_JOELHO,
            )
        self.pose = LegPose(
            self._mola_left.update(dt, target.left),
            self._mola_right.update(dt, target.right),
            self._mola_left_knee.update(dt, target.left_knee),
            self._mola_right_knee.update(dt, target.right_knee),
            self._mola_left_lift.update(dt, target.left_lift),
            self._mola_right_lift.update(dt, target.right_lift),
        )
        return self.pose
