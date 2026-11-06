"""Fonte única de verdade para a pose anatômica de repouso do mascote.

Todos os estados de animação partem desta base e expressam suas poses como
deltas aditivos. Elimina inconsistências entre z=62, z=65, z=68 etc.
"""

from __future__ import annotations

from dataclasses import dataclass

from sejoga.nucleo.rig import Rotation3


@dataclass(frozen=True)
class RepousoAnatomico:
    """Constantes de repouso em GRAUS. Única fonte de verdade.

    Convenção de espelho: o lado esquerdo usa o sinal oposto no eixo Z (roll),
    então left-arm = -BRACO_Z e ant-arm2 = -ANTEBRACO_Z.
    """

    # Braço (ombro)
    BRACO_X: float = -4.0      # leve rotação à frente
    BRACO_Z: float = 68.0      # ombro fechado (braços descidos)

    # Antebraço (cotovelo)
    ANTEBRACO_X: float = -8.0   # leve dobra à frente
    ANTEBRACO_Z: float = -28.0  # cotovelo dobrado

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

    return {
        "body": Rotation3(0, 0, 0),
        "head": Rotation3(0, 0, 0),
        "right-arm": Rotation3(radians(REPOUSO.BRACO_X), 0, radians(REPOUSO.BRACO_Z)),
        "left-arm": Rotation3(radians(REPOUSO.BRACO_X), 0, radians(-REPOUSO.BRACO_Z)),
        "ant-arm": Rotation3(radians(REPOUSO.ANTEBRACO_X), 0, radians(REPOUSO.ANTEBRACO_Z)),
        "ant-arm2": Rotation3(radians(REPOUSO.ANTEBRACO_X), 0, radians(-REPOUSO.ANTEBRACO_Z)),
        "hand": Rotation3(radians(REPOUSO.MAO_X), 0, radians(REPOUSO.MAO_Z)),
        "hand2": Rotation3(radians(REPOUSO.MAO_X), 0, radians(-REPOUSO.MAO_Z)),
        "fingers": Rotation3(0, 0, radians(REPOUSO.DEDOS_Z)),
        "fingers2": Rotation3(0, 0, radians(-REPOUSO.DEDOS_Z)),
        "legs": Rotation3(0, 0, 0),
        "left-feet": Rotation3(0, 0, 0),
        "right-feet": Rotation3(0, 0, 0),
        "door": Rotation3(0, 0, 0),
        "shoulder": Rotation3(0, 0, 0),
        "shoulder2": Rotation3(0, 0, 0),
    }


def espelhar_braco(rotacao: Rotation3) -> Rotation3:
    """Espelha uma rotação de braço direito para esquerdo (inverte Y e Z)."""
    return Rotation3(rotacao.x, -rotacao.y, -rotacao.z)
