"""Authored idle phrases sampled in degrees; independent of the renderer.

These are runtime keyframes, not clips exported from Blockbench. Each track
starts and ends at zero; the relaxed base pose remains underneath the phrase.
"""

from dataclasses import dataclass
from math import cos, sin, tau

from sejoga.animacao.interpolacao import amostrar_pista
from sejoga.animacao.pose_repouso import REPOUSO

# Mantém o import usado por ferramentas de inspeção e testes existentes.
sample_track = amostrar_pista


@dataclass(frozen=True)
class IdleClip:
    """Clipe de idle autoral: pistas de keyframes por grupo do rig."""

    duration: float
    tracks: dict[str, tuple[tuple[float, tuple[float, float, float]], ...]]


def phrase(*keys):
    """Monta uma frase de keyframes a partir de pares (tempo, valor)."""
    return ((0.0, (0, 0, 0)), *keys, (10.0, (0, 0, 0)))


#: Excursão (graus, pico a pico) da elevação do braço por batida do "rhythm".
#: Em 100 BPM o jerk senoidal é A*(2*pi*f)^3; com A = 5 (metade do pico a pico)
#: dá ~5.700 graus/s^3, abaixo do limiar de tranco (8.000). Antes 23/20 -> 13 k.
RHYTHM_BRACO_DIR = 10
RHYTHM_BRACO_ESQ = 9

#: Batida interna do idle "playful" (segundos): keys a cada meia batida (0,5 s),
#: o espaçamento mínimo que mantém o jerk do quíntico longe do limiar de tranco.
PLAYFUL_BATIDA = 1.0
#: Quantas batidas dura o quique e quantas por lado antes de alternar.
PLAYFUL_BATIDAS = 6
PLAYFUL_BATIDAS_POR_LADO = 2
#: Instante (s) em que o quique começa, depois de um respiro inicial parado.
PLAYFUL_INICIO = 1.0


def _quique(inicio, batidas, amplitude):
    """Keys de quique por batida com o lado alternando a cada 2 batidas.

    ``amplitude`` = (vertical em x, lateral em y, rolagem em z) em graus: x
    vale na metade de cada batida (descida) e volta a zero na fronteira; y e z
    seguem o lado da batida e cruzam zero ao trocar de lado. Abre e fecha em 0.
    """
    ax, ay, az = amplitude
    lados = [
        1 if (n // PLAYFUL_BATIDAS_POR_LADO) % 2 == 0 else -1 for n in range(batidas)
    ]

    def fronteira(k):
        if k in (0, batidas):
            return 0.0
        return (lados[k - 1] + lados[k]) / 2

    chaves = [(inicio, (0, 0, 0))]
    for n in range(batidas):
        meio = inicio + (n + 0.5) * PLAYFUL_BATIDA
        fim = inicio + (n + 1) * PLAYFUL_BATIDA
        chaves.append((meio, (ax, ay * lados[n], az * lados[n])))
        chaves.append((fim, (0, ay * fronteira(n + 1), az * fronteira(n + 1))))
    return tuple(chaves)


# --------------------------------------------------------------------------- #
# Pose de repouso natural do braço (base comum das 9 personalidades)
# --------------------------------------------------------------------------- #
# Eixos locais: X inclina à frente, Y gira, Z rola. O braço é longo
# (right-arm/left-arm -> ombro -> ant-arm/ant-arm2 -> mão -> dedos); antes o
# ombro ficava aberto (z≈62°, braço "pendurado" = gorila) e o cotovelo
# assimétrico (um dobrado, outro estendido). Esta base fecha o ombro, dobra o
# cotovelo dos dois lados por igual e deixa o punho neutro, dando um repouso
# "relaxado mas com osso". NOMEADOS/comentados para calibração fina: as 9
# personalidades partem daqui e só somam a oscilação própria por cima.
#
# Convenção de espelho (lei única cinematica.espelhar_rotacao): o lado esquerdo
# inverte Y e Z e mantém X: left-arm = (X, -Y, -Z) do direito.
# Constantes migradas para pose_repouso.py — importadas no topo do módulo.

# Aliases para retrocompatibilidade de código que ainda usa os nomes antigos.
REPOUSO_BRACO_Z = REPOUSO.BRACO_Z
REPOUSO_BRACO_X = REPOUSO.BRACO_X
REPOUSO_BRACO_Y = REPOUSO.BRACO_Y  # azimute do braço em repouso (pós-IK)
REPOUSO_ANTEBRACO_Z = REPOUSO.ANTEBRACO_Z
REPOUSO_ANTEBRACO_X = REPOUSO.ANTEBRACO_X

# Local axes: X pitches forward, Y turns, Z rolls. Mirrored arms need
# opposite roll signs. The hands remain children of the original forearms.
CLIPS = {
    "street": IdleClip(
        10.0,
        {
            "body": phrase(
                (1.0, (0, 0, 0)),
                (1.8, (3, -7, -3)),
                (2.6, (1, 7, 3)),
                (3.4, (2, -5, -2)),
                (4.5, (0, 0, 0)),
                (5.4, (0, 0, 0)),
                (6.3, (-2, 6, 3.5)),
                (7.3, (2.5, -6, -3)),
                (8.3, (1, 4, 2)),
                (9.3, (0, 0, 0)),
            ),
            "cintura": phrase(
                (1.0, (0, 0, 0)),
                (1.8, (1.5, -3, -2.5)),
                (2.6, (0.5, 3, 2.5)),
                (3.4, (1, -2.5, -1.5)),
                (4.5, (0, 0, 0)),
                (5.4, (0, 0, 0)),
                (6.3, (-1, 3, 3)),
                (7.3, (1.5, -3, -2.5)),
                (8.3, (0.5, 2, 1.5)),
                (9.3, (0, 0, 0)),
            ),
            "peitoral": phrase(
                (1.0, (0, 0, 0)),
                (1.8, (2.5, -4, -2)),
                (2.6, (1, 4, 2)),
                (3.4, (1.5, -3, -1.5)),
                (4.5, (0, 0, 0)),
                (5.4, (0, 0, 0)),
                (6.3, (-1.5, 4, 2.5)),
                (7.3, (2, -4, -2)),
                (8.3, (1, 2.5, 1.5)),
                (9.3, (0, 0, 0)),
            ),
            "head": phrase(
                (1.2, (0, 0, 0)),
                (2.0, (-3, 9, 3)),
                (2.8, (1, -7, -2)),
                (3.6, (-2, 5, 2)),
                (4.8, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.4, (-4, -8, -3)),
                (7.4, (2, 8, 2.5)),
                (8.4, (-2, -4, -1.5)),
                (9.4, (0, 0, 0)),
            ),
            "right-arm": phrase(
                (1.2, (0, 0, 0)),
                (2.0, (-24, 6, -34)),
                (2.8, (8, -4, 13)),
                (3.6, (-10, 4, -22)),
                (4.8, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.4, (6, -5, 10)),
                (7.4, (-18, 8, -26)),
                (8.4, (5, -3, 8)),
                (9.4, (0, 0, 0)),
            ),
            "left-arm": phrase(
                (1.2, (0, 0, 0)),
                (2.0, (6, 4, 8)),
                (2.8, (-16, -6, 24)),
                (3.6, (8, 3, -6)),
                (4.8, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.4, (-22, -8, 30)),
                (7.4, (7, 5, -10)),
                (8.4, (-12, -4, 18)),
                (9.4, (0, 0, 0)),
            ),
            "ant-arm": phrase(
                (1.4, (0, 0, 0)),
                (2.2, (-14, 0, -18)),
                (3.0, (8, 0, 8)),
                (3.8, (-8, 0, -12)),
                (5.0, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.5, (6, 0, 6)),
                (7.5, (-12, 0, -14)),
                (8.5, (4, 0, 5)),
                (9.5, (0, 0, 0)),
            ),
            "ant-arm2": phrase(
                (1.4, (0, 0, 0)),
                (2.2, (7, 0, -5)),
                (3.0, (-12, 0, 16)),
                (3.8, (7, 0, 2)),
                (5.0, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.5, (-14, 0, 18)),
                (7.5, (6, 0, -6)),
                (8.5, (-8, 0, 10)),
                (9.5, (0, 0, 0)),
            ),
            "hand": phrase(
                (1.6, (0, 0, 0)),
                (2.4, (-4, 0, 8)),
                (3.2, (3, 0, -4)),
                (4.0, (-2, 0, 4)),
                (5.2, (0, 0, 0)),
                (6.0, (0, 0, 0)),
                (7.0, (-5, 4, 9)),
                (8.0, (3, -3, -5)),
                (9.2, (0, 0, 0)),
            ),
            "hand2": phrase(
                (1.6, (0, 0, 0)),
                (2.6, (3, 0, -6)),
                (3.6, (-4, 0, 7)),
                (4.8, (0, 0, 0)),
                (5.8, (0, 0, 0)),
                (6.7, (-6, -4, -10)),
                (7.8, (3, 2, 5)),
                (9.1, (0, 0, 0)),
            ),
        },
    ),
    "fighter": IdleClip(
        10.0,
        {
            "body": phrase(
                (1.0, (0, 0, 0)),
                (1.6, (3, 8, -2)),
                (2.0, (2, 8, -2)),
                (2.7, (-2, -8, 2)),
                (3.5, (-2, -8, 2)),
                (4.8, (0, 0, 0)),
                (5.4, (0, 0, 0)),
                (6.3, (4, -9, 3)),
                (7.2, (-3, 9, -3)),
                (8.2, (2, -5, 1.5)),
                (9.3, (0, 0, 0)),
            ),
            "cintura": phrase(
                (1.0, (0, 0, 0)),
                (1.7, (1.5, 4, -1.5)),
                (2.8, (-1.5, -4, 1.5)),
                (4.6, (0, 0, 0)),
                (5.4, (0, 0, 0)),
                (6.4, (2, -4.5, 2)),
                (7.4, (-1.5, 4.5, -2)),
                (9.2, (0, 0, 0)),
            ),
            "peitoral": phrase(
                (1.0, (0, 0, 0)),
                (1.7, (2.5, 5, -1.5)),
                (2.8, (-2, -5, 1.5)),
                (4.6, (0, 0, 0)),
                (5.4, (0, 0, 0)),
                (6.4, (3, -5.5, 2)),
                (7.4, (-2, 5.5, -2)),
                (9.2, (0, 0, 0)),
            ),
            "head": phrase(
                (1.1, (0, 0, 0)),
                (1.7, (2, -10, 2)),
                (2.1, (2, -10, 2)),
                (2.9, (-5, 12, -3)),
                (3.6, (-5, 12, -3)),
                (4.9, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.4, (-4, 10, -2.5)),
                (7.3, (3, -11, 3)),
                (8.3, (-3, 6, -1.5)),
                (9.4, (0, 0, 0)),
            ),
            "right-arm": phrase(
                (1.2, (0, 0, 0)),
                (1.8, (-20, 8, -28)),
                (2.2, (-20, 8, -28)),
                (2.9, (-8, 3, -12)),
                (4.9, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.4, (-10, 4, -14)),
                (7.4, (-22, 10, -26)),
                (8.4, (-8, 3, -10)),
                (9.4, (0, 0, 0)),
            ),
            "left-arm": phrase(
                (2.6, (0, 0, 0)),
                (3.15, (-8, -6, 18)),
                (3.55, (-8, -6, 18)),
                (4.2, (0, 0, 0)),
                (5.0, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.4, (-18, -8, 24)),
                (7.3, (-6, -3, 10)),
                (8.3, (-14, -6, 18)),
                (9.4, (0, 0, 0)),
            ),
            "ant-arm": phrase(
                (1.35, (0, 0, 0)),
                (1.95, (-24, 0, -22)),
                (2.3, (-24, 0, -22)),
                (3.1, (-8, 0, -6)),
                (5.0, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.5, (-12, 0, -10)),
                (7.5, (-22, 0, -20)),
                (8.5, (-8, 0, -6)),
                (9.5, (0, 0, 0)),
            ),
            "ant-arm2": phrase(
                (2.4, (0, 0, 0)),
                (3.2, (-14, 0, 14)),
                (4.3, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.4, (-20, 0, 20)),
                (7.4, (-8, 0, 8)),
                (8.4, (-14, 0, 14)),
                (9.4, (0, 0, 0)),
            ),
            "fingers": phrase(
                (1.3, (0, 0, 0)),
                (1.9, (0, 0, 20)),
                (2.3, (0, 0, 20)),
                (3.0, (0, 0, -8)),
                (4.7, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.6, (0, 0, 18)),
                (7.6, (0, 0, 22)),
                (8.8, (0, 0, 0)),
            ),
            "fingers2": phrase(
                (2.4, (0, 0, 0)),
                (3.2, (0, 0, -18)),
                (4.4, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.5, (0, 0, -22)),
                (7.6, (0, 0, -14)),
                (8.8, (0, 0, 0)),
            ),
            "hand": phrase(
                (1.5, (0, 0, 0)),
                (2.1, (-8, 0, 8)),
                (3.0, (0, 0, -10)),
                (4.8, (0, 0, 0)),
                (5.7, (0, 0, 0)),
                (6.7, (-6, 0, 7)),
                (7.7, (-10, 0, 10)),
                (8.9, (0, 0, 0)),
            ),
        },
    ),
    "rhythm": IdleClip(
        10.0,
        {
            # Rampas >= 0,7 s: o jerk de um quíntico é 60*delta/T^3, então rampas
            # longas somam pouco ao balanço por batida (que já usa parte do limite).
            "body": phrase(
                (1.2, (0, 0, 0)),
                (2.2, (2, -5, -2.5)),
                (3.4, (-1, 5, 2.5)),
                (4.6, (0, 0, 0)),
                (5.4, (0, 0, 0)),
                (6.4, (2.5, 6, 3)),
                (7.6, (-1.5, -6, -3)),
                (8.8, (0, 0, 0)),
            ),
            "cintura": phrase(
                (1.2, (0, 0, 0)),
                (2.2, (1, -3, -2)),
                (3.4, (-0.5, 3, 2)),
                (4.6, (0, 0, 0)),
                (5.4, (0, 0, 0)),
                (6.4, (1.5, 3.5, 2.5)),
                (7.6, (-1, -3.5, -2.5)),
                (8.8, (0, 0, 0)),
            ),
            "right-arm": phrase(
                (1.8, (0, 0, 0)),
                (2.8, (-8, 5, -15)),
                (3.8, (-8, 5, -15)),
                (4.8, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.6, (-10, -4, -14)),
                (7.8, (-6, 4, -10)),
                (9.0, (0, 0, 0)),
            ),
            "left-arm": phrase(
                (1.8, (0, 0, 0)),
                (2.8, (-6, -4, 12)),
                (3.8, (-6, -4, 12)),
                (4.8, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.6, (-10, -6, 16)),
                (7.8, (-8, 4, 14)),
                (9.0, (0, 0, 0)),
            ),
            "ant-arm": phrase(
                (2.1, (0, 0, 0)),
                (2.9, (-12, 0, -8)),
                (3.7, (-12, 0, -8)),
                (4.6, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.6, (-14, 0, -10)),
                (7.8, (-10, 0, -6)),
                (9.0, (0, 0, 0)),
            ),
            "ant-arm2": phrase(
                (2.1, (0, 0, 0)),
                (2.9, (-10, 0, 8)),
                (3.7, (-10, 0, 8)),
                (4.6, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.6, (-14, 0, 12)),
                (7.8, (-10, 0, 8)),
                (9.0, (0, 0, 0)),
            ),
            "hand": phrase(
                (2.3, (0, 0, 0)),
                (3.0, (0, 0, 10)),
                (3.8, (0, 0, -4)),
                (4.6, (0, 0, 0)),
                (5.8, (0, 0, 0)),
                (6.8, (-4, 5, 11)),
                (7.9, (3, -4, -6)),
                (9.0, (0, 0, 0)),
            ),
            "fingers": phrase(
                (2.3, (0, 0, 0)),
                (3.0, (0, 0, -8)),
                (3.8, (0, 0, 8)),
                (4.6, (0, 0, 0)),
                (5.8, (0, 0, 0)),
                (6.8, (0, 0, -9)),
                (7.9, (0, 0, 9)),
                (9.0, (0, 0, 0)),
            ),
        },
    ),
    "stylish": IdleClip(
        10.0,
        {
            "body": phrase(
                (1.0, (0, 0, 0)),
                (1.8, (0, -10, -3)),
                (3.2, (0, -10, -3)),
                (4.6, (0, 0, 0)),
                (5.4, (0, 0, 0)),
                (6.4, (-2, 9, 3.5)),
                (7.8, (-2, 9, 3.5)),
                (9.2, (0, 0, 0)),
            ),
            "cintura": phrase(
                (1.0, (0, 0, 0)),
                (1.8, (0, -4, -2.5)),
                (3.2, (0, -4, -2.5)),
                (4.6, (0, 0, 0)),
                (5.4, (0, 0, 0)),
                (6.4, (-1, 4, 3)),
                (7.8, (-1, 4, 3)),
                (9.2, (0, 0, 0)),
            ),
            "peitoral": phrase(
                (1.0, (0, 0, 0)),
                (1.8, (-1.5, -6, -2)),
                (3.2, (-1.5, -6, -2)),
                (4.6, (0, 0, 0)),
                (5.4, (0, 0, 0)),
                (6.4, (-2, 6, 2.5)),
                (7.8, (-2, 6, 2.5)),
                (9.2, (0, 0, 0)),
            ),
            "head": phrase(
                (1.1, (0, 0, 0)),
                (1.9, (-5, 16, 5)),
                (3.3, (-5, 16, 5)),
                (4.9, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.5, (-4, -14, -4.5)),
                (7.9, (-4, -14, -4.5)),
                (9.3, (0, 0, 0)),
            ),
            "right-arm": phrase(
                (1.25, (0, 0, 0)),
                (2.0, (-10, 6, -25)),
                (3.4, (-10, 6, -25)),
                (4.9, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.5, (4, -4, 8)),
                (7.9, (4, -4, 8)),
                (9.3, (0, 0, 0)),
            ),
            "left-arm": phrase(
                (1.25, (0, 0, 0)),
                (2.1, (4, 3, -6)),
                (3.4, (4, 3, -6)),
                (4.9, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.5, (-12, -6, 22)),
                (7.9, (-12, -6, 22)),
                (9.3, (0, 0, 0)),
            ),
            "ant-arm": phrase(
                (1.4, (0, 0, 0)),
                (2.15, (-18, 0, -12)),
                (3.5, (-18, 0, -12)),
                (5.1, (0, 0, 0)),
                (5.7, (0, 0, 0)),
                (6.7, (6, 0, 6)),
                (8.0, (6, 0, 6)),
                (9.3, (0, 0, 0)),
            ),
            "ant-arm2": phrase(
                (1.4, (0, 0, 0)),
                (2.2, (4, 0, -4)),
                (3.5, (4, 0, -4)),
                (5.0, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.6, (-16, 0, 14)),
                (8.0, (-16, 0, 14)),
                (9.3, (0, 0, 0)),
            ),
            "hand": phrase(
                (1.55, (0, 0, 0)),
                (2.3, (0, 12, -14)),
                (3.6, (0, 12, -14)),
                (5.3, (0, 0, 0)),
                (6.0, (0, 0, 0)),
                (7.0, (-4, -6, 8)),
                (8.2, (-4, -6, 8)),
                (9.4, (0, 0, 0)),
            ),
            "hand2": phrase(
                (5.5, (0, 0, 0)),
                (6.6, (0, -10, 12)),
                (8.0, (0, -10, 12)),
                (9.3, (0, 0, 0)),
            ),
            "fingers": phrase(
                (1.65, (0, 0, 0)),
                (2.4, (0, 0, -8)),
                (3.7, (0, 0, -8)),
                (5.4, (0, 0, 0)),
                (6.2, (0, 0, 0)),
                (7.2, (0, 0, 6)),
                (8.3, (0, 0, 6)),
                (9.4, (0, 0, 0)),
            ),
        },
    ),
    # Calma (Hollow Knight/Celeste): deriva de peso lenta e contemplativa nos dois lados.
    "calm": IdleClip(
        10.0,
        {
            "body": phrase(
                (1.4, (0, 0, 0)),
                (3.2, (1, 3, 2.5)),
                (4.6, (1, 3, 2.5)),
                (6.4, (-1, -3, -2.5)),
                (7.8, (-1, -3, -2.5)),
                (9.4, (0, 0, 0)),
            ),
            "cintura": phrase(
                (1.4, (0, 0, 0)),
                (3.2, (0.5, 1.5, 1.5)),
                (4.6, (0.5, 1.5, 1.5)),
                (6.4, (-0.5, -1.5, -1.5)),
                (7.8, (-0.5, -1.5, -1.5)),
                (9.4, (0, 0, 0)),
            ),
            "head": phrase(
                (1.6, (0, 0, 0)),
                (3.4, (1.5, -5, -3)),
                (4.8, (1.5, -5, -3)),
                (6.6, (-1.5, 5, 3)),
                (8.0, (-1.5, 5, 3)),
                (9.5, (0, 0, 0)),
            ),
            "right-arm": phrase(
                (1.8, (0, 0, 0)),
                (3.6, (3, 3, -6)),
                (4.8, (3, 3, -6)),
                (6.6, (-2, -2, 4)),
                (8.0, (-2, -2, 4)),
                (9.5, (0, 0, 0)),
            ),
            "left-arm": phrase(
                (1.8, (0, 0, 0)),
                (3.6, (3, -3, 6)),
                (4.8, (3, -3, 6)),
                (6.6, (-2, 2, -4)),
                (8.0, (-2, 2, -4)),
                (9.5, (0, 0, 0)),
            ),
            "ant-arm": phrase(
                (2.0, (0, 0, 0)),
                (3.8, (-4, 0, 5)),
                (5.0, (-4, 0, 5)),
                (6.8, (2, 0, -3)),
                (8.2, (2, 0, -3)),
                (9.5, (0, 0, 0)),
            ),
            "ant-arm2": phrase(
                (2.0, (0, 0, 0)),
                (3.8, (-4, 0, -5)),
                (5.0, (-4, 0, -5)),
                (6.8, (2, 0, 3)),
                (8.2, (2, 0, 3)),
                (9.5, (0, 0, 0)),
            ),
            "fingers": phrase(
                (2.2, (0, 0, 0)),
                (4.0, (0, 0, 5)),
                (5.2, (0, 0, 5)),
                (7.0, (0, 0, -3)),
                (8.4, (0, 0, -3)),
                (9.5, (0, 0, 0)),
            ),
            "fingers2": phrase(
                (2.2, (0, 0, 0)),
                (4.0, (0, 0, -5)),
                (5.2, (0, 0, -5)),
                (7.0, (0, 0, 3)),
                (8.4, (0, 0, 3)),
                (9.5, (0, 0, 0)),
            ),
        },
    ),
    # Curiosa (Animal Crossing): inspeciona um lado inclinando o tronco e erguendo o braço,
    # depois examina o outro lado com as antenas acompanhando.
    "curious": IdleClip(
        10.0,
        {
            "head": phrase(
                (1.0, (0, 0, 0)),
                (1.8, (0, -3, 0)),
                (3.0, (-6, 15, 5)),
                (4.2, (-6, 15, 5)),
                (5.4, (0, 0, 0)),
                (6.6, (-5, -14, -5)),
                (7.8, (-5, -14, -5)),
                (9.3, (0, 0, 0)),
            ),
            "body": phrase(
                (1.2, (0, 0, 0)),
                (2.8, (-3, 5, 3)),
                (4.2, (-3, 5, 3)),
                (5.4, (0, 0, 0)),
                (6.6, (-3, -5, -3)),
                (7.8, (-3, -5, -3)),
                (9.3, (0, 0, 0)),
            ),
            "peitoral": phrase(
                (1.2, (0, 0, 0)),
                (2.8, (-2.5, 4, 2)),
                (4.2, (-2.5, 4, 2)),
                (5.4, (0, 0, 0)),
                (6.6, (-2.5, -4, -2)),
                (7.8, (-2.5, -4, -2)),
                (9.3, (0, 0, 0)),
            ),
            "right-arm": phrase(
                (1.4, (0, 0, 0)),
                (2.8, (-6, 8, -18)),
                (4.2, (-6, 8, -18)),
                (5.5, (0, 0, 0)),
                (6.8, (4, -3, 6)),
                (8.0, (4, -3, 6)),
                (9.3, (0, 0, 0)),
            ),
            "left-arm": phrase(
                (1.4, (0, 0, 0)),
                (2.8, (4, 3, -6)),
                (4.2, (4, 3, -6)),
                (5.5, (0, 0, 0)),
                (6.8, (-6, -8, 18)),
                (8.0, (-6, -8, 18)),
                (9.3, (0, 0, 0)),
            ),
            "ant-arm": phrase(
                (1.6, (0, 0, 0)),
                (3.0, (-10, 0, -14)),
                (4.3, (-10, 0, -14)),
                (5.6, (0, 0, 0)),
                (6.9, (4, 0, 5)),
                (8.1, (4, 0, 5)),
                (9.4, (0, 0, 0)),
            ),
            "ant-arm2": phrase(
                (5.5, (0, 0, 0)),
                (6.8, (-10, 0, 14)),
                (8.0, (-10, 0, 14)),
                (9.4, (0, 0, 0)),
            ),
            "hand": phrase(
                (1.8, (0, 0, 0)),
                (3.2, (0, 8, -7)),
                (4.4, (0, 8, -7)),
                (5.8, (0, 0, 0)),
            ),
            "hand2": phrase(
                (5.6, (0, 0, 0)),
                (6.9, (0, -8, 7)),
                (8.1, (0, -8, 7)),
                (9.4, (0, 0, 0)),
            ),
        },
    ),
    # Brincalhona (Hi-Fi Rush/FNF Girlfriend): quique por batida interna de
    # 1 s, alternando o lado a cada 2 batidas, cobrindo 8 batidas do ciclo.
    "playful": IdleClip(
        10.0,
        {
            "body": phrase(*_quique(0.8, 8, (2.6, 5.0, 3.0))),
            "cintura": phrase(*_quique(0.8, 8, (1.4, 2.8, 2.2))),
            "peitoral": phrase(*_quique(0.8, 8, (2.0, 3.5, 2.2))),
            "head": phrase(*_quique(0.8, 8, (-2.2, 4.5, 3.0))),
            "right-arm": phrase(*_quique(0.8, 8, (3.5, 5.0, -12.0))),
            "left-arm": phrase(*_quique(0.8, 8, (3.5, -5.0, -12.0))),
            "ant-arm": phrase(*_quique(0.8, 8, (-5.0, 0.0, 8.0))),
            "ant-arm2": phrase(*_quique(0.8, 8, (-5.0, 0.0, -8.0))),
        },
    ),
    # Tímida (Celeste): encolhe os ombros e olha de lado na primeira metade,
    # depois junta os antebraços e brinca com os dedos na segunda metade.
    "shy": IdleClip(
        10.0,
        {
            "head": phrase(
                (1.0, (0, 0, 0)),
                (2.2, (-4, -13, -3)),
                (3.5, (-4, -13, -3)),
                (4.8, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.7, (4, 9, 3)),
                (7.9, (4, 9, 3)),
                (9.2, (0, 0, 0)),
            ),
            "body": phrase(
                (1.0, (0, 0, 0)),
                (2.2, (2, -4, -2)),
                (3.5, (2, -4, -2)),
                (4.8, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.7, (2.5, 3, 2)),
                (7.9, (2.5, 3, 2)),
                (9.2, (0, 0, 0)),
            ),
            "shoulder": phrase(
                (1.0, (0, 0, 0)),
                (2.2, (3, 0, -3)),
                (3.6, (3, 0, -3)),
                (4.9, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.8, (3.5, 0, -3.5)),
                (8.0, (3.5, 0, -3.5)),
                (9.2, (0, 0, 0)),
            ),
            "shoulder2": phrase(
                (1.0, (0, 0, 0)),
                (2.2, (3, 0, 3)),
                (3.6, (3, 0, 3)),
                (4.9, (0, 0, 0)),
                (5.6, (0, 0, 0)),
                (6.8, (3.5, 0, 3.5)),
                (8.0, (3.5, 0, 3.5)),
                (9.2, (0, 0, 0)),
            ),
            "right-arm": phrase(
                (1.2, (0, 0, 0)),
                (2.4, (4, -6, 5)),
                (3.6, (4, -6, 5)),
                (4.9, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.5, (4, -8, -8)),
                (7.8, (4, -8, -8)),
                (9.1, (0, 0, 0)),
            ),
            "left-arm": phrase(
                (1.2, (0, 0, 0)),
                (2.4, (4, 6, -5)),
                (3.6, (4, 6, -5)),
                (4.9, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.5, (4, 8, 8)),
                (7.8, (4, 8, 8)),
                (9.1, (0, 0, 0)),
            ),
            "ant-arm": phrase(
                (1.3, (0, 0, 0)),
                (2.5, (-6, 0, 8)),
                (3.7, (-6, 0, 8)),
                (5.0, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.5, (-8, 0, -12)),
                (7.6, (-4, 0, -5)),
                (8.9, (0, 0, 0)),
            ),
            "ant-arm2": phrase(
                (1.3, (0, 0, 0)),
                (2.5, (-6, 0, -8)),
                (3.7, (-6, 0, -8)),
                (5.0, (0, 0, 0)),
                (5.5, (0, 0, 0)),
                (6.5, (-8, 0, 12)),
                (7.6, (-4, 0, 5)),
                (8.9, (0, 0, 0)),
            ),
            "fingers": phrase(
                (5.5, (0, 0, 0)),
                (6.3, (0, 0, 7)),
                (7.1, (0, 0, -2)),
                (7.9, (0, 0, 6)),
                (8.9, (0, 0, 0)),
            ),
            "fingers2": phrase(
                (5.5, (0, 0, 0)),
                (6.3, (0, 0, -7)),
                (7.1, (0, 0, 2)),
                (7.9, (0, 0, -6)),
                (8.9, (0, 0, 0)),
            ),
        },
    ),
    # Confiante: peito aberto, queixo alto, pontuação firme de ombro/braço
    # na primeira metade e troca de apoio orgulhosa na segunda metade.
    "confident": IdleClip(
        10.0,
        {
            "head": phrase(
                (1.4, (0, 0, 0)),
                (2.5, (-4, -10, -2)),
                (3.7, (-4, -10, -2)),
                (5.0, (0, 0, 0)),
                (5.7, (0, 0, 0)),
                (6.8, (-5, 11, 2.5)),
                (8.0, (-5, 11, 2.5)),
                (9.3, (0, 0, 0)),
            ),
            "body": phrase(
                (1.4, (0, 0, 0)),
                (2.5, (-2, 6, -3)),
                (3.7, (-2, 6, -3)),
                (5.0, (0, 0, 0)),
                (5.7, (0, 0, 0)),
                (6.8, (-2.5, -6, 3)),
                (8.0, (-2.5, -6, 3)),
                (9.3, (0, 0, 0)),
            ),
            "peitoral": phrase(
                (1.4, (0, 0, 0)),
                (2.5, (-3, 4, -2)),
                (3.7, (-3, 4, -2)),
                (5.0, (0, 0, 0)),
                (5.7, (0, 0, 0)),
                (6.8, (-3, -4, 2)),
                (8.0, (-3, -4, 2)),
                (9.3, (0, 0, 0)),
            ),
            "right-arm": phrase(
                (1.5, (0, 0, 0)),
                (2.6, (-6, 6, -18)),
                (3.7, (-6, 6, -18)),
                (5.0, (0, 0, 0)),
                (5.7, (0, 0, 0)),
                (6.8, (2, -3, -8)),
                (8.0, (2, -3, -8)),
                (9.3, (0, 0, 0)),
            ),
            "left-arm": phrase(
                (1.6, (0, 0, 0)),
                (2.7, (2, 3, 10)),
                (3.7, (2, 3, 10)),
                (5.0, (0, 0, 0)),
                (5.7, (0, 0, 0)),
                (6.8, (-6, -6, 18)),
                (8.0, (-6, -6, 18)),
                (9.3, (0, 0, 0)),
            ),
            "ant-arm": phrase(
                (1.6, (0, 0, 0)),
                (2.7, (-10, 0, 12)),
                (3.8, (-10, 0, 12)),
                (5.1, (0, 0, 0)),
                (5.8, (0, 0, 0)),
                (6.9, (-4, 0, 6)),
                (8.1, (-4, 0, 6)),
                (9.3, (0, 0, 0)),
            ),
            "ant-arm2": phrase(
                (1.6, (0, 0, 0)),
                (2.7, (-4, 0, -6)),
                (3.8, (-4, 0, -6)),
                (5.1, (0, 0, 0)),
                (5.8, (0, 0, 0)),
                (6.9, (-10, 0, -12)),
                (8.1, (-10, 0, -12)),
                (9.3, (0, 0, 0)),
            ),
        },
    ),
}

#: Ajuste de base (graus, somado à base natural) das personalidades novas.
#: Fica por baixo das frases, como a base de fighter/stylish em ``sample_idle``.
AJUSTE_BASE = {
    "calm": {
        "head": (1, 0, -1),
        "right-arm": (1.5, -1.5, 2.0),
        "left-arm": (1.5, 1.5, -2.0),
    },
    "playful": {
        "body": (1.5, 0, 0),
        "head": (-1.5, 0, 1.5),
        "right-arm": (-3.0, 3.0, -5.0),
        "left-arm": (-3.0, -3.0, 5.0),
        "ant-arm": (-4.0, 0.0, 5.0),
        "ant-arm2": (-4.0, 0.0, -5.0),
    },
    "curious": {
        "body": (-1.5, 1.5, 1.0),
        "head": (-3.5, 2.0, 1.5),
        "right-arm": (-2.0, 3.0, -4.0),
        "ant-arm": (-4.0, 0.0, 4.0),
    },
    "shy": {
        "body": (2.0, -1.5, -1.5),
        "head": (4.5, -2.0, -3.0),
        "right-arm": (3.0, -5.0, 4.0),
        "left-arm": (3.0, 5.0, -4.0),
        "ant-arm": (3.0, 0, 6.0),
        "ant-arm2": (3.0, 0, -6.0),
    },
    "confident": {
        "body": (-2.5, 2.0, -1.5),
        "head": (-4.5, -2.0, 1.5),
        "right-arm": (-4.0, 4.0, -7.0),
        "left-arm": (-4.0, -4.0, 7.0),
        "ant-arm": (-5.0, 0.0, 6.0),
        "ant-arm2": (-5.0, 0.0, -6.0),
    },
    "street": {
        "body": (1.5, -2.5, -2.0),
        "head": (-2.0, 3.0, 2.0),
        "right-arm": (-5.0, 4.0, -8.0),
        "left-arm": (-3.0, -3.0, 6.0),
        "ant-arm": (-6.0, 0.0, 5.0),
        "ant-arm2": (-4.0, 0.0, -4.0),
    },
}


#: Ganho (graus) da respiração sobre cada parte, para uma respiração cheia
#: (centrada == 1). O peito (body.x) carrega o grosso do movimento; ombros e
#: cabeça só acompanham de leve, como num corpo que respira de verdade. A
#: calibração fina por personalidade vem de ``respiracao_tuning`` (amplitude).
RESPIRACAO_GANHO_PEITO = 1.6
RESPIRACAO_GANHO_OMBRO = 0.5
RESPIRACAO_GANHO_CABECA = 0.4


def camada_respiracao(
    respiracao: float,
    amplitude: float = 1.0,
) -> dict[str, tuple[float, float, float]]:
    """Camada aditiva de respiração em graus, a ser somada à pose do idle.

    ``respiracao`` é o valor centrado (-1..1) vindo de ``Respiracao`` (0 no
    repouso). ``amplitude`` escala o quanto o peito infla por personalidade
    (vem de ``respiracao_tuning.parametros_de``). O peito (``body`` eixo x) sobe
    e desce; ombros e cabeça acompanham de leve, como a respiração real causa.
    Com ``respiracao == 0`` devolve tudo zero, preservando quem não respira.
    """
    peito = respiracao * amplitude * RESPIRACAO_GANHO_PEITO
    ombro = respiracao * amplitude * RESPIRACAO_GANHO_OMBRO
    cabeca = respiracao * amplitude * RESPIRACAO_GANHO_CABECA

    return {
        "body": (peito, 0.0, 0.0),
        "right-arm": (ombro, 0.0, 0.0),
        "left-arm": (ombro, 0.0, 0.0),
        "head": (cabeca, 0.0, 0.0),
    }


def sample_idle(
    style: str,
    time: float,
    respiracao: float = 0.0,
    amplitude_respiracao: float = 1.0,
) -> dict[str, tuple[float, float, float]]:
    """Amostra o idle da personalidade no tempo ``t``, com respiração."""
    clip = CLIPS[style]
    local = time % clip.duration
    # Base de repouso natural com oscilação contínua suave de tronco, braços e
    # cotovelos: mesmo nos vales entre keyframes o corpo respira e balança.
    onda_corpo = sin(time * 0.85)
    onda_lat = sin(time * 0.52)
    onda_braco = sin(time * 0.78 - 0.35)
    onda_cotovelo = sin(time * 0.92 - 0.65)
    pose = {
        "body": (onda_corpo * 1.4, onda_lat * 1.8, -1.5 + onda_lat * 1.4),
        "head": (-onda_corpo * 0.9, sin(time * 0.42) * 3.2, 1.5 - onda_lat * 1.1),
        "right-arm": (
            REPOUSO_BRACO_X + onda_braco * 2.2,
            REPOUSO_BRACO_Y + onda_lat * 2.4,
            REPOUSO_BRACO_Z - (0.5 + 0.5 * onda_corpo) * 3.2,
        ),
        "left-arm": (
            REPOUSO_BRACO_X + onda_braco * 2.2,
            -REPOUSO_BRACO_Y + onda_lat * 2.4,
            -REPOUSO_BRACO_Z + (0.5 + 0.5 * onda_corpo) * 3.2,
        ),
        "ant-arm": (
            REPOUSO_ANTEBRACO_X + onda_cotovelo * 2.0,
            0.0,
            REPOUSO_ANTEBRACO_Z + (0.5 + 0.5 * onda_cotovelo) * 3.5,
        ),
        "ant-arm2": (
            REPOUSO_ANTEBRACO_X + onda_cotovelo * 2.0,
            0.0,
            -REPOUSO_ANTEBRACO_Z - (0.5 + 0.5 * onda_cotovelo) * 3.5,
        ),
    }
    if style == "fighter":
        # Guarda alta e fechada: ginga contínua de luta + cotovelos dobrados.
        ginga = sin(time * 1.45)
        pose.update(
            {
                "body": (3.0 + ginga * 1.8, 5.0 + onda_lat * 3.0, -2.0 + ginga * 1.5),
                "head": (1.0 - ginga * 1.2, -5.0 - onda_lat * 2.5, 2.0 - ginga * 1.0),
                "right-arm": (
                    REPOUSO_BRACO_X - 12.0 + ginga * 3.0,
                    REPOUSO_BRACO_Y + 6.0,
                    REPOUSO_BRACO_Z - 6.0 - (ginga * ginga) * 3.0,
                ),
                "left-arm": (
                    REPOUSO_BRACO_X - 8.0 - ginga * 3.0,
                    -REPOUSO_BRACO_Y - 5.0,
                    -(REPOUSO_BRACO_Z - 6.0 - (ginga * ginga) * 3.0),
                ),
                "ant-arm": (
                    REPOUSO_ANTEBRACO_X - 14.0,
                    0.0,
                    REPOUSO_ANTEBRACO_Z - 4.0 + (0.5 + 0.5 * ginga) * 4.0,
                ),
                "ant-arm2": (
                    REPOUSO_ANTEBRACO_X - 10.0,
                    0.0,
                    -(REPOUSO_ANTEBRACO_Z - 4.0 + (0.5 - 0.5 * ginga) * 4.0),
                ),
                "fingers": (0, 0, 22),
                "fingers2": (0, 0, -20),
            }
        )
    elif style == "stylish":
        # Um braço mais solto/aberto (assimetria intencional do estilo), partindo
        # da base natural para o lado direito e mantendo o espelho à esquerda.
        pose.update(
            {
                "body": (-2.0 + onda_corpo * 1.2, 3.0 + onda_lat * 2.2, -2.0 + onda_lat * 1.6),
                "head": (-3.0 - onda_corpo * 0.8, -4.0 - onda_lat * 2.0, 3.0),
                "right-arm": (
                    REPOUSO_BRACO_X - 6.0 + onda_braco * 2.0,
                    REPOUSO_BRACO_Y + 3.0,
                    REPOUSO_BRACO_Z - 16.0 - onda_corpo * 2.5,
                ),
                "left-arm": (
                    REPOUSO_BRACO_X + 2.0 - onda_braco * 2.0,
                    -REPOUSO_BRACO_Y - 2.0,
                    -REPOUSO_BRACO_Z + onda_corpo * 2.0,
                ),
                "ant-arm": (REPOUSO_ANTEBRACO_X - 8.0, 0.0, REPOUSO_ANTEBRACO_Z + 3.0),
                "ant-arm2": (REPOUSO_ANTEBRACO_X - 2.0, 0.0, -(REPOUSO_ANTEBRACO_Z - 2.0)),
                "hand": (0, 12, -8),
            }
        )
    elif style == "rhythm":
        # Internal cadence at 100 BPM, not a claim of synchronization to audio.
        beat = tau * time / 0.6
        pulse = (1 - cos(beat)) * 0.5
        groove = sin(beat * 0.5)
        pose["body"] = (pulse * 2.8, groove * 3.2, sin(beat * 0.25) * 2.8)
        pose["head"] = (-1.5 + (1 - cos(beat - 0.28)) * 1.4, -groove * 2.5, groove * 1.8)
        pose["right-arm"] = (
            REPOUSO_BRACO_X - 4 + sin(beat - 0.45) * 5,
            REPOUSO_BRACO_Y + groove * 4.0,
            REPOUSO_BRACO_Z - 8 - pulse * RHYTHM_BRACO_DIR,
        )
        pose["left-arm"] = (
            REPOUSO_BRACO_X - 2 - sin(beat - 0.45) * 5,
            -REPOUSO_BRACO_Y + groove * 4.0,
            -REPOUSO_BRACO_Z + 4 + pulse * RHYTHM_BRACO_ESQ,
        )
        pose["ant-arm"] = (
            REPOUSO_ANTEBRACO_X - 4.0,
            0.0,
            REPOUSO_ANTEBRACO_Z + pulse * 6.0,
        )
        pose["ant-arm2"] = (
            REPOUSO_ANTEBRACO_X - 4.0,
            0.0,
            -REPOUSO_ANTEBRACO_Z - pulse * 6.0,
        )
    for group, extra in AJUSTE_BASE.get(style, {}).items():
        base = pose.get(group, (0, 0, 0))
        pose[group] = tuple(a + b for a, b in zip(base, extra, strict=True))
    for group, keys in clip.tracks.items():
        delta = amostrar_pista(keys, local)
        base = pose.get(group, (0, 0, 0))
        pose[group] = tuple(a + b for a, b in zip(base, delta, strict=True))
    # Respiração viva por cima da frase autoral: peito sobe/desce sempre, mesmo
    # quando a frase está no repouso, então nenhum idle fica totalmente estático.
    if respiracao:
        for group, (ex, ey, ez) in camada_respiracao(
            respiracao, amplitude_respiracao
        ).items():
            bx, by, bz = pose.get(group, (0, 0, 0))
            pose[group] = (bx + ex, by + ey, bz + ez)
    return pose
