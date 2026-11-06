"""Vocabulário de ALVOS DE MÃO por gesto/estado (dados puros, sem engine).

Cada gesto de braço declara ONDE a mão deve ficar — a posição-alvo da ponta da
mão RELATIVA ao ombro, no espaço do modelo (+X=direita, +Y=cima, +Z=frente) — e
um ``polo`` (direção preferida do cotovelo). O solver 3D (``arm_ik.braco_para``)
converte isso nos HPR reais dos bones, respeitando a geometria diagonal do
modelo. Assim as poses deixam de ser ângulos diretos (inviáveis de calibrar) e
passam a ser posições no espaço, legíveis e verificáveis por
``tools/dump_rig_estado.py`` (offset x,y,z da mão).

Alcance do braço ≈ 0.281 (upper 0.125 + forearm 0.15625). Os alvos ficam DENTRO
do alcance; alvos fora são clampados por ``solve_arm`` sem gerar NaN.

Os valores são CALIBRÁVEIS contra o dump: ajuste o alvo e releia o offset da mão
em ``dump_rig_estado`` até a pose ficar como o gesto pede. Os alvos abaixo foram
calibrados assim (idle: mão baixada junto ao quadril; wave: mão acima do ombro,
à direita).

FRONTEIRA: Python puro. Só ``dataclass``; nenhum import de engine.
"""

from __future__ import annotations

from dataclasses import dataclass

Vec3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class AlvoBraco:
    """Alvo de mão (relativo ao ombro) + polo (direção do cotovelo)."""

    #: Posição-alvo da ponta da mão relativa ao ombro (espaço do modelo).
    alvo: Vec3
    #: Direção preferida do cotovelo (desempata a dobra). Default +Z (frente).
    polo: Vec3 = (0.0, 0.0, 1.0)

    def alvo_espelhado(self) -> Vec3:
        """Alvo com o X invertido (pose simétrica para o braço esquerdo)."""
        return (-self.alvo[0], self.alvo[1], self.alvo[2])


# --------------------------------------------------------------------------- #
# Alvos calibrados (ver docstring). O alcance total é ≈ 0.281.
# --------------------------------------------------------------------------- #

#: REPOUSO/idle: mão baixada ao lado do quadril, levemente afastada do corpo e
#: um tiquinho à frente (postura natural relaxada). Braço quase reto para baixo.
ALVO_IDLE = AlvoBraco(alvo=(0.075, -0.265, 0.02), polo=(0.0, 0.0, 1.0))

#: WAVE/aceno: mão ACIMA do ombro, à direita, antebraço apontando para cima. O
#: balanço do aceno e o giro do pulso entram como termos aditivos por cima (em
#: ``rig.pose_flourish``); aqui fica só o alvo do pico do lift.
ALVO_WAVE = AlvoBraco(alvo=(0.11, 0.235, 0.03), polo=(0.0, 0.0, 1.0))

#: DRAG/arraste: mão à frente e um pouco para fora, como quem se equilibra ao
#: ser puxado. O deslocamento por direção/intensidade é somado em ``pose_drag``.
ALVO_DRAG = AlvoBraco(alvo=(0.14, -0.08, 0.17), polo=(0.0, 0.0, 1.0))

#: STRETCH/alongamento: mão alta, à frente, como quem ajusta a jaqueta/espreguiça.
ALVO_STRETCH = AlvoBraco(alvo=(0.12, 0.18, 0.12), polo=(0.0, 0.0, 1.0))

#: DANCE/dança: mão à frente e em cima, pronta para o balanço no ritmo (o
#: ``beat`` modula por cima em ``pose_dance``).
ALVO_DANCE = AlvoBraco(alvo=(0.15, 0.1, 0.15), polo=(0.0, 0.0, 1.0))

#: SLEEP/sono: mãos recolhidas junto ao corpo, baixas (braços relaxados colados).
ALVO_SLEEP = AlvoBraco(alvo=(0.05, -0.25, 0.08), polo=(0.0, 0.0, 1.0))

#: THROWN/arremesso: mãos à frente e para fora, silhueta aérea legível.
ALVO_THROWN = AlvoBraco(alvo=(0.16, 0.0, 0.16), polo=(0.0, 0.0, 1.0))

#: INTERACTION/interação (base): mãos à frente, levemente abertas, como quem
#: reage ao cursor. Ramos específicos (hover/poke...) modulam por cima.
ALVO_INTERACTION = AlvoBraco(alvo=(0.13, -0.02, 0.18), polo=(0.0, 0.0, 1.0))

#: DRAG_PERNA: pego pela perna, os braços pendem e se recolhem junto ao corpo —
#: mais baixos e mais para dentro que o repouso (a gravidade os puxa ao tronco).
ALVO_DRAG_PERNA = AlvoBraco(alvo=(0.035, -0.272, 0.0), polo=(0.0, 0.0, 1.0))

#: FALL/queda: mãos abertas para fora, silhueta aérea (flailing entra aditivo).
ALVO_FALL = AlvoBraco(alvo=(0.19, 0.03, 0.05), polo=(0.0, 0.0, 1.0))


#: Registro por nome (facilita consumo e documentação).
ALVOS: dict[str, AlvoBraco] = {
    "idle": ALVO_IDLE,
    "wave": ALVO_WAVE,
    "drag": ALVO_DRAG,
    "drag_perna": ALVO_DRAG_PERNA,
    "stretch": ALVO_STRETCH,
    "dance": ALVO_DANCE,
    "sleep": ALVO_SLEEP,
    "thrown": ALVO_THROWN,
    "fall": ALVO_FALL,
    "interaction": ALVO_INTERACTION,
}
