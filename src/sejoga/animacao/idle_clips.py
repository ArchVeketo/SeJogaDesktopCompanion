"""Authored idle phrases sampled in degrees; independent of the renderer.

These are runtime keyframes, not clips exported from Blockbench. Each track
starts and ends at zero; the relaxed base pose remains underneath the phrase.
"""

from dataclasses import dataclass
from itertools import pairwise
from math import cos, sin, tau

from sejoga.animacao.rig_base import REPOUSO


@dataclass(frozen=True)
class IdleClip:
    duration: float
    tracks: dict[str, tuple[tuple[float, tuple[float, float, float]], ...]]


def sample_track(keys, time):
    """Quintic easing keeps velocity and acceleration continuous at holds."""
    if time <= keys[0][0]:
        return keys[0][1]
    for (start, a), (end, b) in pairwise(keys):
        if time <= end:
            u = (time - start) / (end - start)
            blend = u * u * u * (u * (u * 6 - 15) + 10)
            return tuple(x + (y - x) * blend for x, y in zip(a, b, strict=True))
    return keys[-1][1]


def phrase(*keys):
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
    lados = [1 if (n // PLAYFUL_BATIDAS_POR_LADO) % 2 == 0 else -1
             for n in range(batidas)]

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
# Constantes migradas para rig_base.py — importadas no topo do módulo.

# Aliases para retrocompatibilidade de código que ainda usa os nomes antigos.
REPOUSO_BRACO_Z = REPOUSO.BRACO_Z
REPOUSO_BRACO_X = REPOUSO.BRACO_X
REPOUSO_BRACO_Y = REPOUSO.BRACO_Y  # azimute do braço em repouso (pós-IK)
REPOUSO_ANTEBRACO_Z = REPOUSO.ANTEBRACO_Z
REPOUSO_ANTEBRACO_X = REPOUSO.ANTEBRACO_X

# Local axes: X pitches forward, Y turns, Z rolls. Mirrored arms need
# opposite roll signs. The hands remain children of the original forearms.
CLIPS = {
    "street": IdleClip(10.0, {
        "body": phrase((1.0, (0, 0, 0)), (1.8, (3, -7, -3)), (2.6, (1, 7, 3)),
                       (3.4, (2, -5, -2)), (4.5, (0, 0, 0))),
        "head": phrase((1.2, (0, 0, 0)), (2.0, (-3, 9, 3)), (2.8, (1, -7, -2)),
                       (3.6, (-2, 5, 2)), (4.8, (0, 0, 0))),
        "right-arm": phrase((1.2, (0, 0, 0)), (2.0, (-24, 0, -34)),
                            (2.8, (8, 0, 13)), (3.6, (-10, 0, -22)), (4.8, (0, 0, 0))),
        "left-arm": phrase((1.2, (0, 0, 0)), (2.0, (6, 0, 8)),
                           (2.8, (-16, 0, 24)), (3.6, (8, 0, -6)), (4.8, (0, 0, 0))),
        "ant-arm": phrase((1.4, (0, 0, 0)), (2.2, (-14, 0, -18)),
                          (3.0, (8, 0, 8)), (3.8, (-8, 0, -12)), (5.0, (0, 0, 0))),
        "ant-arm2": phrase((1.4, (0, 0, 0)), (2.2, (7, 0, -5)),
                           (3.0, (-12, 0, 16)), (3.8, (7, 0, 2)), (5.0, (0, 0, 0))),
        "hand": phrase((1.6, (0, 0, 0)), (2.4, (-4, 0, 8)),
                       (3.2, (3, 0, -4)), (4.0, (-2, 0, 4)), (5.2, (0, 0, 0))),
    }),
    "fighter": IdleClip(10.0, {
        "body": phrase((1.0, (0, 0, 0)), (1.6, (3, 8, -2)),
                       (2.0, (2, 8, -2)), (2.7, (-2, -8, 2)), (3.5, (-2, -8, 2)),
                       (4.8, (0, 0, 0))),
        "head": phrase((1.1, (0, 0, 0)), (1.7, (2, -10, 2)),
                       (2.1, (2, -10, 2)), (2.9, (-5, 12, -3)),
                       (3.6, (-5, 12, -3)), (4.9, (0, 0, 0))),
        "right-arm": phrase((1.2, (0, 0, 0)), (1.8, (-20, 0, -28)),
                            (2.2, (-20, 0, -28)), (2.9, (-8, 0, -12)), (4.9, (0, 0, 0))),
        "left-arm": phrase((2.6, (0, 0, 0)), (3.15, (-8, 0, 18)),
                           (3.55, (-8, 0, 18)), (4.2, (0, 0, 0)), (5.0, (0, 0, 0))),
        "ant-arm": phrase((1.35, (0, 0, 0)), (1.95, (-24, 0, -22)),
                          (2.3, (-24, 0, -22)), (3.1, (-8, 0, -6)), (5.0, (0, 0, 0))),
        "fingers": phrase((1.3, (0, 0, 0)), (1.9, (0, 0, 20)),
                          (2.3, (0, 0, 20)), (3.0, (0, 0, -8)), (4.7, (0, 0, 0))),
        "hand": phrase((1.5, (0, 0, 0)), (2.1, (-8, 0, 8)),
                       (3.0, (0, 0, -10)), (4.8, (0, 0, 0))),
    }),
    "rhythm": IdleClip(10.0, {
        # Rampas >= 0,7 s: o jerk de um quíntico é 60*delta/T^3, então rampas
        # longas somam pouco ao balanço por batida (que já usa parte do limite).
        "right-arm": phrase((1.8, (0, 0, 0)), (2.8, (-8, 0, -15)),
                            (3.8, (-8, 0, -15)), (4.8, (0, 0, 0))),
        "ant-arm": phrase((2.1, (0, 0, 0)), (2.9, (-12, 0, -8)),
                          (3.7, (-12, 0, -8)), (4.6, (0, 0, 0))),
        "hand": phrase((2.3, (0, 0, 0)), (3.0, (0, 0, 10)),
                       (3.8, (0, 0, -4)), (4.6, (0, 0, 0))),
        "fingers": phrase((2.3, (0, 0, 0)), (3.0, (0, 0, -8)),
                          (3.8, (0, 0, 8)), (4.6, (0, 0, 0))),
    }),
    "stylish": IdleClip(10.0, {
        "body": phrase((1.0, (0, 0, 0)), (1.8, (0, -10, -3)),
                       (3.2, (0, -10, -3)), (4.6, (0, 0, 0))),
        "head": phrase((1.1, (0, 0, 0)), (1.9, (-5, 16, 5)),
                       (3.3, (-5, 16, 5)), (4.9, (0, 0, 0))),
        "right-arm": phrase((1.25, (0, 0, 0)), (2.0, (-10, 0, -25)),
                            (3.4, (-10, 0, -25)), (4.9, (0, 0, 0))),
        "ant-arm": phrase((1.4, (0, 0, 0)), (2.15, (-18, 0, -12)),
                          (3.5, (-18, 0, -12)), (5.1, (0, 0, 0))),
        "hand": phrase((1.55, (0, 0, 0)), (2.3, (0, 12, -14)),
                       (3.6, (0, 12, -14)), (5.3, (0, 0, 0))),
        "fingers": phrase((1.65, (0, 0, 0)), (2.4, (0, 0, -8)),
                          (3.7, (0, 0, -8)), (5.4, (0, 0, 0))),
    }),
    # Calma (Hollow Knight/Celeste): deriva de peso lenta, quase parada. Tudo
    # com rampas >= 1,5 s; a respiração vem da camada de respiração.
    "calm": IdleClip(10.0, {
        "body": phrase((2.0, (0, 0, 0)), (4.0, (0, 2, 2)),
                       (5.2, (0, 2, 2)), (7.6, (0, 0, 0))),
        "head": phrase((2.2, (0, 0, 0)), (4.2, (1, -4, -2.5)),
                       (5.4, (1, -4, -2.5)), (7.8, (0, 0, 0))),
        "right-arm": phrase((2.4, (0, 0, 0)), (4.4, (2, 0, -3)),
                            (5.4, (2, 0, -3)), (7.8, (0, 0, 0))),
        "left-arm": phrase((2.4, (0, 0, 0)), (4.4, (2, 0, 3)),
                           (5.4, (2, 0, 3)), (7.8, (0, 0, 0))),
        "fingers": phrase((2.6, (0, 0, 0)), (4.6, (0, 0, 3)),
                          (5.6, (0, 0, 3)), (8.0, (0, 0, 0))),
        "fingers2": phrase((2.6, (0, 0, 0)), (4.6, (0, 0, -3)),
                           (5.6, (0, 0, -3)), (8.0, (0, 0, 0))),
    }),
    # Curiosa (Animal Crossing): olhar com antecipação (contra-movimento
    # pequeno), giro da cabeça, pausa e retorno lento.
    "curious": IdleClip(10.0, {
        "head": phrase((1.0, (0, 0, 0)), (1.8, (0, -2, 0)),
                       (3.0, (-5, 14, 4)), (4.2, (-5, 14, 4)),
                       (6.0, (0, 0, 0))),
        "body": phrase((1.4, (0, 0, 0)), (2.8, (0, 3, 0)),
                       (4.2, (0, 3, 0)), (6.0, (0, 0, 0))),
        "right-arm": phrase((1.6, (0, 0, 0)), (3.0, (2, 0, -14)),
                            (4.2, (2, 0, -14)), (6.0, (0, 0, 0))),
        "ant-arm": phrase((1.8, (0, 0, 0)), (3.2, (-6, 0, -14)),
                          (4.4, (-6, 0, -14)), (6.2, (0, 0, 0))),
        "hand": phrase((2.0, (0, 0, 0)), (3.4, (0, 6, -5)),
                       (4.4, (0, 6, -5)), (6.2, (0, 0, 0))),
    }),
    # Brincalhona (Hi-Fi Rush/FNF Girlfriend): quique por batida interna de
    # 1 s, alternando o lado a cada 2 batidas. Não alega sincronia com áudio.
    "playful": IdleClip(10.0, {
        "body": phrase(*_quique(PLAYFUL_INICIO, PLAYFUL_BATIDAS, (2.2, 4, 2))),
        "head": phrase(*_quique(PLAYFUL_INICIO, PLAYFUL_BATIDAS, (-1.5, 3, 2))),
        "right-arm": phrase(*_quique(PLAYFUL_INICIO, PLAYFUL_BATIDAS, (2, 0, -8))),
        "left-arm": phrase(*_quique(PLAYFUL_INICIO, PLAYFUL_BATIDAS, (2, 0, -8))),
    }),
    # Tímida (Celeste): olhar de lado que volta, depois um fidget de braço e
    # de dedos (espelhados) com as mãos junto ao corpo.
    "shy": IdleClip(10.0, {
        "head": phrase((1.2, (0, 0, 0)), (2.4, (-3, -12, 0)),
                       (3.4, (-3, -12, 0)), (5.0, (0, 0, 0))),
        "body": phrase((1.2, (0, 0, 0)), (2.4, (0, -2, 0)),
                       (3.4, (0, -2, 0)), (5.0, (0, 0, 0))),
        "right-arm": phrase((5.5, (0, 0, 0)), (6.5, (2, 0, -6)),
                            (8.5, (0, 0, 0))),
        "left-arm": phrase((5.5, (0, 0, 0)), (6.5, (2, 0, 6)),
                           (8.5, (0, 0, 0))),
        "ant-arm": phrase((5.5, (0, 0, 0)), (6.5, (0, 0, -10)),
                          (7.5, (0, 0, -4)), (8.7, (0, 0, 0))),
        "ant-arm2": phrase((5.5, (0, 0, 0)), (6.5, (0, 0, 10)),
                           (7.5, (0, 0, 4)), (8.7, (0, 0, 0))),
        "fingers": phrase((5.5, (0, 0, 0)), (6.3, (0, 0, 5)),
                          (7.1, (0, 0, -1)), (7.9, (0, 0, 4)),
                          (8.9, (0, 0, 0))),
        "fingers2": phrase((5.5, (0, 0, 0)), (6.3, (0, 0, -5)),
                           (7.1, (0, 0, 1)), (7.9, (0, 0, -4)),
                           (8.9, (0, 0, 0))),
    }),
    # Confiante: queixo alto (na base) e uma "pontuação" com o ombro direito
    # e a cabeça, que sobe, segura e volta.
    "confident": IdleClip(10.0, {
        "head": phrase((2.0, (0, 0, 0)), (2.8, (-3, -8, 0)),
                       (3.6, (-3, -8, 0)), (5.0, (0, 0, 0))),
        "body": phrase((2.0, (0, 0, 0)), (2.8, (0, 4, -2)),
                       (3.6, (0, 4, -2)), (5.0, (0, 0, 0))),
        "right-arm": phrase((2.0, (0, 0, 0)), (2.8, (0, 0, -14)),
                            (3.6, (0, 0, -14)), (5.2, (0, 0, 0))),
        "left-arm": phrase((2.2, (0, 0, 0)), (3.0, (0, 0, 8)),
                           (3.6, (0, 0, 8)), (5.2, (0, 0, 0))),
        "ant-arm": phrase((2.1, (0, 0, 0)), (2.9, (-6, 0, 8)),
                          (3.7, (-6, 0, 8)), (5.2, (0, 0, 0))),
    }),
}

#: Ajuste de base (graus, somado à base natural) das personalidades novas.
#: Fica por baixo das frases, como a base de fighter/stylish em ``sample_idle``.
AJUSTE_BASE = {
    "calm": {"head": (1, 0, -1)},
    "playful": {"body": (1, 0, 0), "head": (-1, 0, 1)},
    "curious": {"head": (-3, 0, 0)},
    "shy": {"body": (1, -1, -1), "head": (4, 0, -3),
            "ant-arm": (2, 0, 0), "ant-arm2": (2, 0, 0)},
    "confident": {"body": (-2, 0, 0), "head": (-4, 0, 0)},
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
    clip = CLIPS[style]
    local = time % clip.duration
    # Base de repouso natural: ombro fechado, cotovelo levemente dobrado dos dois
    # lados (simetria correta) e punho neutro. As personalidades partem daqui.
    pose = {
        "body": (sin(time * .8) * .7, 0, -1.5),
        "head": (0, sin(time * .36) * 2, 1.5),
        "right-arm": (REPOUSO_BRACO_X, REPOUSO_BRACO_Y, REPOUSO_BRACO_Z),
        "left-arm": (REPOUSO_BRACO_X, -REPOUSO_BRACO_Y, -REPOUSO_BRACO_Z),
        "ant-arm": (REPOUSO_ANTEBRACO_X, 0, REPOUSO_ANTEBRACO_Z),
        "ant-arm2": (REPOUSO_ANTEBRACO_X, 0, -REPOUSO_ANTEBRACO_Z),
    }
    if style == "fighter":
        # Guarda alta e fechada: ombros mais recolhidos e cotovelos bem dobrados,
        # como offset sobre a base natural (não uma pose inventada do zero).
        pose.update({"body": (3, 5, -2), "head": (1, -5, 2),
        "right-arm": (REPOUSO_BRACO_X - 12, REPOUSO_BRACO_Y, REPOUSO_BRACO_Z - 4),
        "left-arm": (REPOUSO_BRACO_X - 8, -REPOUSO_BRACO_Y, -(REPOUSO_BRACO_Z - 4)),
        "ant-arm": (REPOUSO_ANTEBRACO_X - 14, 0, REPOUSO_ANTEBRACO_Z - 4),
        "ant-arm2": (REPOUSO_ANTEBRACO_X - 10, 0, -(REPOUSO_ANTEBRACO_Z - 4)),
                     "fingers": (0, 0, 22), "fingers2": (0, 0, -20)})
    elif style == "stylish":
        # Um braço mais solto/aberto (assimetria intencional do estilo), partindo
        # da base natural para o lado direito e mantendo o espelho à esquerda.
        pose.update({"body": (-2, 3, -2), "head": (-3, -4, 3),
                     "right-arm": (REPOUSO_BRACO_X - 6, REPOUSO_BRACO_Y, REPOUSO_BRACO_Z - 16),
                     "left-arm": (REPOUSO_BRACO_X + 2, -REPOUSO_BRACO_Y, -REPOUSO_BRACO_Z),
                     "ant-arm": (REPOUSO_ANTEBRACO_X - 8, 0, REPOUSO_ANTEBRACO_Z),
                     "ant-arm2": (REPOUSO_ANTEBRACO_X - 2, 0, -(REPOUSO_ANTEBRACO_Z - 2)),
                     "hand": (0, 12, -8)})
    elif style == "rhythm":
        # Internal cadence at 100 BPM, not a claim of synchronization to audio.
        beat = tau * time / .6
        pulse = (1 - cos(beat)) * .5
        pose["body"] = (pulse * 2.0, 0, sin(beat * .25) * 2.0)
        pose["head"] = (-1 + (1 - cos(beat - .28)), 0, 0)
        pose["right-arm"] = (REPOUSO_BRACO_X - 4 + sin(beat - .45) * 5, REPOUSO_BRACO_Y,
                             REPOUSO_BRACO_Z - 8 - pulse * RHYTHM_BRACO_DIR)
        pose["left-arm"] = (REPOUSO_BRACO_X - 2 + sin(beat - .45) * 5, -REPOUSO_BRACO_Y,
                            -REPOUSO_BRACO_Z + 4 + pulse * RHYTHM_BRACO_ESQ)
    for group, extra in AJUSTE_BASE.get(style, {}).items():
        base = pose.get(group, (0, 0, 0))
        pose[group] = tuple(a + b for a, b in zip(base, extra, strict=True))
    for group, keys in clip.tracks.items():
        delta = sample_track(keys, local)
        base = pose.get(group, (0, 0, 0))
        pose[group] = tuple(a + b for a, b in zip(base, delta, strict=True))
    # Respiração viva por cima da frase autoral: peito sobe/desce sempre, mesmo
    # quando a frase está no repouso, então nenhum idle fica totalmente estático.
    if respiracao:
        for group, (ex, ey, ez) in camada_respiracao(respiracao, amplitude_respiracao).items():
            bx, by, bz = pose.get(group, (0, 0, 0))
            pose[group] = (bx + ex, by + ey, bz + ez)
    return pose
