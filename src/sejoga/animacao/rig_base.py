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

    Convenção de espelho: o lado esquerdo usa o sinal oposto nos eixos Y e Z,
    então left-arm = (-BRACO_Y, -BRACO_Z) e ant-arm2 = -ANTEBRACO_Z.

    IMPORTANTE — convenção de elevação PROVADA em pixels de tela (ver arm_ik):
    o eixo LONGO do bone é +X e o renderer mapeia H=y, P=x, R=z. A ELEVAÇÃO do
    braço na TELA (sobe/desce) é o ROLL (Z), NÃO o heading:
      Z (roll) do ``right-arm``: z NEGATIVO ERGUE (mão acima do ombro); z
        POSITIVO BAIXA. "braço baixado" (idle) ≈ Z=+74.
      Y (heading) do ``right-arm``: AZIMUTE/profundidade (dentro/fora da tela).
    Isso é geometria do bone (eixo longo ±X), não artefato do antigo
    ``setH(180)``: a rota B assou o facing no asset sem mudar a orientação de
    mundo, então a convenção e o espelho (x,-y,-z) seguem válidos. Estes valores
    vêm do solver de IK para o ALVO DE MÃO de idle (mãos ao lado do quadril), em
    ``arm_targets.ALVO_IDLE`` — não são ângulos chutados. Mantidos aqui como
    fallback/const para quem não injeta o ``Model`` (``pose_repouso()`` sem
    modelo e os deltas de ``delta_states``).
    """

    # Braço (ombro): baixado ao lado do quadril (IK do alvo idle, render-exato).
    BRACO_X: float = 0.0       # torção neutra (não move a ponta da mão)
    BRACO_Y: float = -14.45    # AZIMUTE: leve avanço/profundidade
    BRACO_Z: float = 73.93     # ELEVAÇÃO: braço baixado ao lado (z+ baixa)

    # Antebraço (cotovelo): leve dobra (IK do alvo idle).
    ANTEBRACO_X: float = 0.0
    ANTEBRACO_Z: float = 18.03  # cotovelo levemente dobrado

    # Mão
    MAO_X: float = 0.0
    MAO_Z: float = 0.0

    # Dedos
    DEDOS_Z: float = 0.0


#: Instância global de repouso — usar em vez de recriar.
REPOUSO = RepousoAnatomico()


def pose_repouso() -> dict[str, Rotation3]:
    """Pose anatômica base em radianos. Todos os estados partem daqui.

    Os braços usam os HPR de repouso derivados do IK (alvo de mão de idle). Sem
    um ``Model`` injetado, usamos as constantes ``REPOUSO`` (que são a saída do
    IK para o alvo idle, cacheadas aqui como fallback). Quem quiser recalcular a
    partir da geometria viva pode usar ``arm_ik.pose_repouso_bracos(model)``.
    """
    from math import radians

    return {
        "body": Rotation3(0, 0, 0),
        "head": Rotation3(0, 0, 0),
        "right-arm": Rotation3(radians(REPOUSO.BRACO_X), radians(REPOUSO.BRACO_Y), radians(REPOUSO.BRACO_Z)),
        "left-arm": Rotation3(radians(REPOUSO.BRACO_X), radians(-REPOUSO.BRACO_Y), radians(-REPOUSO.BRACO_Z)),
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
