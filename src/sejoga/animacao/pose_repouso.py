"""Fonte única de verdade para a pose anatômica de repouso do mascote.

Todos os estados de animação partem desta base e expressam suas poses como
deltas aditivos.
"""

from __future__ import annotations

from dataclasses import dataclass

from sejoga.nucleo.cinematica import espelhar_rotacao
from sejoga.nucleo.esqueleto import Rotation3


@dataclass(frozen=True)
class RepousoAnatomico:
    """Constantes de repouso em GRAUS (``Rotation3`` x=P, y=H, z=R do renderer).

    Os valores do braço/antebraço são a SAÍDA de ``arm_ik.pose_repouso_bracos``
    para ``arm_targets.ALVO_IDLE``, cacheada aqui para quem não injeta o
    ``Model``. ``tests/test_ik_bracos.py`` garante ``REPOUSO == IK(ALVO_IDLE)``:
    se o alvo ou o solver mudarem, estes números precisam ser regenerados (nunca
    ajustados à mão).

    Eixos medidos no grafo de cena (``tools/gerar_oraculo_cena.py --eixos``), braço
    direito com o eixo longo em +X: H (y) positivo leva a mão para a FRENTE;
    R (z) positivo BAIXA a mão; P (x) torce o braço no próprio eixo (escolhe o
    plano em que o cotovelo dobra). O cotovelo é o R do antebraço, com a
    torção-base de ``braco_tuning.TORCAO_BASE_ANTEBRACO_GRAUS`` somada pelo
    renderer, então ``ANTEBRACO_Z`` positivo dobra para a frente.

    Lado esquerdo = ``espelhar_rotacao`` do direito: ``(x, -y, -z)``. Verificado
    SÓ a nível de nó (posição de punho no grafo de cena, ``test_cinematica_oraculo``).
    NÃO provado visualmente: a simetria na tela depende do usuário (C3).
    """

    # Ombro (osso base da cadeia): IK do alvo idle.
    BRACO_X: float = 27.05  # torção: põe a dobradiça do cotovelo à frente
    BRACO_Y: float = 0.81  # azimute: braço para o lado, sem recuo
    BRACO_Z: float = 33.49  # elevação: braço caído, afastado do tronco

    # Antebraço (cotovelo): flexão para a frente (IK do alvo idle).
    ANTEBRACO_X: float = 0.0
    ANTEBRACO_Z: float = 1.63

    # Mão
    MAO_X: float = 0.0
    MAO_Z: float = 0.0

    # Dedos
    DEDOS_Z: float = 0.0


#: Instância global de repouso — usar em vez de recriar.
REPOUSO = RepousoAnatomico()


def pose_repouso() -> dict[str, Rotation3]:
    """Pose anatômica base em radianos. Todos os estados partem daqui."""
    from math import radians

    braco = Rotation3(
        radians(REPOUSO.BRACO_X), radians(REPOUSO.BRACO_Y), radians(REPOUSO.BRACO_Z)
    )
    antebraco = Rotation3(radians(REPOUSO.ANTEBRACO_X), 0, radians(REPOUSO.ANTEBRACO_Z))
    mao = Rotation3(radians(REPOUSO.MAO_X), 0, radians(REPOUSO.MAO_Z))
    dedos = Rotation3(0, 0, radians(REPOUSO.DEDOS_Z))

    return {
        "body": Rotation3(0, 0, 0),
        "head": Rotation3(0, 0, 0),
        "right-arm": braco,
        "left-arm": espelhar_braco(braco),
        "ant-arm": antebraco,
        "ant-arm2": espelhar_braco(antebraco),
        "hand": mao,
        "hand2": espelhar_braco(mao),
        "fingers": dedos,
        "fingers2": espelhar_braco(dedos),
        "legs": Rotation3(0, 0, 0),
        "left-feet": Rotation3(0, 0, 0),
        "right-feet": Rotation3(0, 0, 0),
        "door": Rotation3(0, 0, 0),
        "shoulder": Rotation3(0, 0, 0),
        "shoulder2": Rotation3(0, 0, 0),
    }


def espelhar_braco(rotacao: Rotation3) -> Rotation3:
    """Espelha uma rotação do lado direito para o esquerdo (lei única de cinematica)."""
    return espelhar_rotacao(rotacao)
