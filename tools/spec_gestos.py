"""FORMATO DE SPEC DE GESTO (código puro, sem engine, só dados).

Uma SPEC descreve, por junta/eixo, o comportamento que um gesto DEVERIA ter —
numa saudação o braço ergue e a mão oscila no eixo do aceno. É a camada
SEMÂNTICA que complementa o analisador objetivo de ``tools/analisar_anim.py``:
o analisador mede qualidade de curva (suavidade, loop, follow-through); a spec
mede CORREÇÃO de gesto (o movimento é mesmo o que aquele gesto exige?).

Aqui ficam APENAS os dados: enum de tipos de expectativa, a dataclass de uma
expectativa e a dataclass de uma spec. A lógica de verificação vive em
``tools/verificar_gesto.py``. A fronteira é Python puro: nada de Panda3D/Qt/Win32.

O formato generaliza para os demais gestos do backlog — uma :class:`SpecGesto`
é só ``nome`` + ``duracao`` + ``loop`` + uma lista de :class:`ExpectativaGesto`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TipoExpectativa(StrEnum):
    """Vocabulário checável de comportamento esperado de um gesto."""

    #: O eixo varia de forma quase-monotônica até um alvo, com amplitude mínima
    #: (ex.: right-arm eixo Z reduz de ~56 para <=0 → o braço ergue).
    ERGUE = "ERGUE"

    #: Igual a ERGUE, mas no sentido oposto (o eixo cresce até o alvo).
    ABAIXA = "ABAIXA"

    #: Vai-e-volta repetido num eixo: >= ``inversoes_min`` inversões de direção
    #: e amplitude mínima ("a mão deve acenar, não ficar parada").
    OSCILA = "OSCILA"

    #: Amplitude pico-a-pico <= ``epsilon`` ("a perna não deve se mexer").
    ESTAVEL = "ESTAVEL"

    #: A variação principal da junta está no eixo esperado ("mexe, mas no eixo
    #: errado"). Compara a amplitude do eixo esperado com a dos demais.
    EIXO_CORRETO = "EIXO_CORRETO"

    #: Fase/ordem: o movimento desta junta começa ANTES do movimento da junta
    #: referida em ``antes_de`` (ex.: o braço ergue antes de a mão acenar).
    FASE = "FASE"

    #: No instante final do gesto, uma PARTE do corpo (lida por
    #: ``sejoga.rig_mapa.rig_debug.estado_rig``) deve estar numa FLAG esperada — ex.:
    #: "ao fim do aceno a palma direita aponta para FORA". Complementa os eixos
    #: crus: em vez de medir oscilação, afirma a ORIENTAÇÃO final legível.
    FLAG = "FLAG"


#: Sentido de uma expectativa ERGUE/ABAIXA no eixo:
#: "negativo" = o ângulo diminui até o alvo; "positivo" = aumenta.
SENTIDO_NEGATIVO = "negativo"
SENTIDO_POSITIVO = "positivo"


@dataclass(frozen=True)
class ExpectativaGesto:
    """Uma expectativa checável sobre o movimento de uma junta.

    Campos usados variam por ``tipo``:

    - ERGUE/ABAIXA: ``eixo``, ``amplitude_min``, ``sentido``.
    - OSCILA: ``eixo``, ``amplitude_min``, ``inversoes_min``.
    - ESTAVEL: ``eixo`` (ou ``None`` = a junta inteira), ``epsilon``.
    - EIXO_CORRETO: ``eixo`` (o eixo que deve dominar a amplitude).
    - FASE: ``antes_de`` (grupo cujo movimento deve começar DEPOIS deste).
    - FLAG: ``parte`` + ``flag_esperada`` (e ``instante``, padrão = fim do gesto).

    ``descricao`` é texto legível em PT para o laudo.
    """

    grupo: str
    tipo: TipoExpectativa
    descricao: str
    eixo: str | None = None
    #: Amplitude pico-a-pico mínima exigida, em graus (ERGUE/ABAIXA/OSCILA).
    amplitude_min: float = 0.0
    #: Amplitude máxima tolerada, em graus (ESTAVEL).
    epsilon: float = 2.0
    #: Número mínimo de inversões de direção exigidas (OSCILA).
    inversoes_min: int = 2
    #: Sentido esperado da variação (ERGUE/ABAIXA).
    sentido: str = SENTIDO_NEGATIVO
    #: Grupo cujo movimento deve começar depois deste (FASE).
    antes_de: str | None = None
    #: Parte do corpo lida por ``rig_debug.estado_rig`` (FLAG). Ex.: "mao_direita",
    #: "cabeca", "orientacao_global", "right-arm" (membro), "cotovelo_direito".
    parte: str | None = None
    #: Flag esperada da ``parte`` no instante medido (FLAG). Ex.: "PALMA_PARA_FORA".
    flag_esperada: str | None = None
    #: Instante (s) em que a FLAG é medida; ``None`` = fim do gesto (duração).
    instante: float | None = None


@dataclass(frozen=True)
class SpecGesto:
    """Descrição completa de um gesto: identidade + lista de expectativas."""

    nome: str
    duracao: float
    loop: bool
    expectativas: tuple[ExpectativaGesto, ...]


# --------------------------------------------------------------------------- #
# SPEC-PILOTO DA SAUDAÇÃO (wave).
#
# Derivada do comportamento real de ``rig.pose_flourish(rig, "wave", t)`` E do
# que uma saudação humana deve ter. Leitura das curvas de pose_flourish wave
# (lift sobe de 0→1→0; wave inverte +1,-0.78,+0.78,-0.5,0):
#
#   right-arm: x=-12*lift; elevação por IK no eixo Z → ERGUE (z vai de ~+74
#     baixado para ~-66 acima do ombro, amp ~140°).
#     (Convenção PROVADA em pixels: a elevação é o ROLL (Z) e z NEGATIVO ergue;
#      o código antigo erguia por Y/heading, mandando o braço p/ profundidade.)
#   ant-arm:   z=-26*lift + 7*wave.
#   hand:      x=180*lift + 12*wave, z=2*wave
#              → o eixo X carrega o lift (gira o pulso 180° pra mostrar a palma)
#                SOMADO ao termo de aceno 12*wave; é o eixo de maior oscilação
#                do aceno, logo é o EIXO_CORRETO do wave da mão.
#   left-feet/right-feet: NÃO tocados em wave → ficam ~0 (ESTAVEL, sem chute).
#
# Limiares calibrados contra o wave de produção real (ver laudo no resumo):
# braço ergue bem acima de 40°; a mão inverte várias vezes no eixo X com
# amplitude grande. Os pés ficam exatamente em 0°.
# --------------------------------------------------------------------------- #

SPEC_WAVE = SpecGesto(
    nome="wave",
    duracao=2.2,
    loop=False,
    expectativas=(
        ExpectativaGesto(
            grupo="right-arm",
            tipo=TipoExpectativa.ERGUE,
            eixo="z",
            amplitude_min=40.0,
            sentido=SENTIDO_NEGATIVO,
            # Convenção PROVADA em pixels: a ELEVAÇÃO do braço é o ROLL
            # (Z = ``Rotation3.z``), não o heading, e z NEGATIVO ergue. No aceno
            # o braço ergue de ~+74° (baixado) até ~-66° (acima do ombro), então
            # a amplitude em Z é grande e o SENTIDO é NEGATIVO (z diminui). O
            # eixo Y passou a ser a profundidade, que quase não muda no wave.
            descricao="o braço direito ergue (elevação Z cai de ~+74° até ≈-66°)",
        ),
        ExpectativaGesto(
            grupo="hand",
            tipo=TipoExpectativa.OSCILA,
            eixo="x",
            amplitude_min=8.0,
            inversoes_min=3,
            descricao="a mão direita acena (oscila no eixo X, não fica parada)",
        ),
        ExpectativaGesto(
            grupo="hand",
            tipo=TipoExpectativa.EIXO_CORRETO,
            eixo="x",
            descricao="o aceno da mão está no eixo X (não é um aceno no eixo errado)",
        ),
        ExpectativaGesto(
            grupo="left-feet",
            tipo=TipoExpectativa.ESTAVEL,
            epsilon=1.0,
            descricao="o pé esquerdo não se mexe (sem chute numa saudação)",
        ),
        ExpectativaGesto(
            grupo="right-feet",
            tipo=TipoExpectativa.ESTAVEL,
            epsilon=1.0,
            descricao="o pé direito não se mexe (sem chute numa saudação)",
        ),
        ExpectativaGesto(
            grupo="hand",
            tipo=TipoExpectativa.FLAG,
            parte="mao_direita",
            flag_esperada="PALMA_PARA_FORA",
            # Migração para IK (alvo de mão): o braço agora ergue por IK e
            # RETORNA ao repouso ao fim do gesto (lift→0 em t=2.2), com a mão
            # baixada — ao contrário da pose antiga, que deixava o braço preso
            # em z=70 no fim. A palma deve ficar para FORA no PICO do aceno
            # (quando a mão está acima do ombro), não no retorno ao repouso;
            # por isso medimos a FLAG no pico (t≈1.0), não no fim. Além disso, a
            # geometria diagonal inverteu o sentido do roll do pulso: a palma
            # vira para FORA com o pulso NEUTRO (não mais com o roll de 180°).
            instante=1.0,
            descricao="no pico do aceno a palma direita fica virada para FORA",
        ),
    ),
)


#: Registro de specs conhecidas, por nome de gesto. Generaliza para o backlog.
SPECS: dict[str, SpecGesto] = {
    "wave": SPEC_WAVE,
}
