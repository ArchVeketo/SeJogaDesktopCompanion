"""Tensão por junta: tabela de calibração das molas do rig (engine-agnóstico).

Este módulo centraliza a "firmeza" de cada junta do corpo em um único lugar,
sem depender de Panda3D, Qt ou Win32. A ideia física é simples:

- Perto da âncora (corpo, pernas, ombros) a junta é firme: rigidez alta,
  amortecimento perto de 1 (assenta seco, quase sem balanço) e lag zero.
- Perto da ponta (mãos, dedos) a junta é solta: rigidez baixa, amortecimento
  menor (dá mais balanço) e lag alto (arrasta atrás da base).
- ``amortecimento`` < 1 dá balanço; perto de 1 assenta seco sem oscilar.

A rigidez é expressa como ``frequencia`` (Hz) da mola analítica subamortecida
de ``body_motion.Spring``: quanto maior a frequência, mais rápido e firme o
retorno ao alvo. ``lag`` (0..1) é o atraso perceptível da ponta em relação à
base, consumido por quem propaga o movimento ao longo da cadeia.
"""

from __future__ import annotations

from dataclasses import dataclass

from sejoga.nucleo.rig import ALL_GROUPS


@dataclass(frozen=True, slots=True)
class TensaoJunta:
    """Tensão de uma junta: rigidez (frequência), amortecimento e atraso.

    - ``frequencia``: rigidez da mola em Hz (maior = mais firme/rápido).
    - ``amortecimento``: 0..1; < 1 dá balanço, perto de 1 assenta seco.
    - ``lag``: 0..1; atraso perceptível da ponta em relação à âncora.
    """

    frequencia: float
    amortecimento: float
    lag: float


#: Tensão padrão para grupos sem entrada explícita. Iguala os defaults atuais
#: de ``JointSpring``/``SpringPose`` (frequência 2.2, amortecimento 0.72) para
#: que um grupo desconhecido se comporte exatamente como antes.
TENSAO_PADRAO = TensaoJunta(frequencia=2.2, amortecimento=0.72, lag=0.0)


#: Amortecimento (ζ) da cadeia do braço — ombro->antebraço->mão->dedos.
#: Subidos em relação à calibração antiga (valores ANTES entre parênteses) para
#: tirar a sensação de "sem ossos / gelatina" no idle de repouso: a ponta
#: passava do alvo em 16-25 % e demorava 1.3-2.9 s para assentar. Mantidos
#: abaixo de 1.0 (a mola analítica usa sqrt(1-ζ²)) e com body (0.90) >= dedos,
#: o invariante de ``tests/test_spring_tuning.py``. NOMEADOS para calibração
#: fina na GPU: mexer aqui ajusta o "osso" sem tocar na pose de repouso.
AMORT_BRACO = 0.72       # right-arm/left-arm (antes 0.60)
AMORT_ANTEBRACO = 0.78   # ant-arm/ant-arm2   (antes 0.50) — pior gelatina
AMORT_MAO = 0.75         # hand/hand2         (antes 0.50)
AMORT_DEDOS = 0.62       # fingers/fingers2   (antes 0.40)


#: Uma entrada por grupo de ``rig.ALL_GROUPS``. Valores de PARTIDA aprovados;
#: a ordenação (rigidez decrescente da âncora para a ponta) é um invariante
#: testado em ``tests/test_spring_tuning.py``.
TENSAO_POR_JUNTA: dict[str, TensaoJunta] = {
    # Corpo e pernas: âncora firme. Rigidez alta, amortecimento perto de 1
    # (assenta seco, quase sem balanço), sem atraso.
    "body": TensaoJunta(frequencia=3.2, amortecimento=0.9, lag=0.0),
    "legs": TensaoJunta(frequencia=3.2, amortecimento=0.9, lag=0.0),
    # Cabeça: rigidez média-alta, amortecimento médio-alto, atraso leve para
    # dar um balanço discreto no pescoço.
    "head": TensaoJunta(frequencia=2.6, amortecimento=0.7, lag=0.1),
    # Portinha do peito: rigidez média, amortecimento médio-alto, sem atraso.
    "door": TensaoJunta(frequencia=2.2, amortecimento=0.8, lag=0.0),
    # Ombros: presos ao tronco, quase tão firmes quanto o corpo. Rigidez alta,
    # amortecimento alto, sem atraso.
    "shoulder": TensaoJunta(frequencia=3.0, amortecimento=0.85, lag=0.0),
    "shoulder2": TensaoJunta(frequencia=3.0, amortecimento=0.85, lag=0.0),
    # Braços (parte alta): rigidez média, atraso leve — começam a soltar em
    # relação ao ombro. Amortecimento firmado (0.60 -> 0.72) para dar "osso":
    # alvo de overshoot de repouso < ~5 % (antes ~9.5 %). A frequência não muda
    # (preserva a ordenação âncora->ponta testada).
    "right-arm": TensaoJunta(frequencia=2.2, amortecimento=AMORT_BRACO, lag=0.15),
    "left-arm": TensaoJunta(frequencia=2.2, amortecimento=AMORT_BRACO, lag=0.15),
    # Antebraços: rigidez média-baixa, atraso médio — arrastam atrás do braço.
    # Amortecimento firmado (0.50 -> 0.78) para matar o balanço do cotovelo, que
    # era o pior ofensor da "gelatina": alvo de overshoot < ~5 % (antes 16.3 %).
    "ant-arm": TensaoJunta(frequencia=1.8, amortecimento=AMORT_ANTEBRACO, lag=0.3),
    "ant-arm2": TensaoJunta(frequencia=1.8, amortecimento=AMORT_ANTEBRACO, lag=0.3),
    # Mãos: rigidez baixa, atraso alto — a ponta solta, mas com tônus.
    # Amortecimento firmado (0.50 -> 0.75) para a mão não ficar "morta":
    # alvo de overshoot < ~8 % (antes 16.3 %).
    "hand": TensaoJunta(frequencia=1.4, amortecimento=AMORT_MAO, lag=0.5),
    "hand2": TensaoJunta(frequencia=1.4, amortecimento=AMORT_MAO, lag=0.5),
    # Dedos: a ponta mais solta de todas. Rigidez muito baixa, atraso o mais
    # alto. Amortecimento firmado (0.40 -> 0.62): ainda soltos, mas sem gelatina;
    # alvo de overshoot < ~12 % (antes 25.4 %). Mantido abaixo de body (0.90)
    # para o invariante `body >= fingers` de test_spring_tuning.
    "fingers": TensaoJunta(frequencia=1.1, amortecimento=AMORT_DEDOS, lag=0.6),
    "fingers2": TensaoJunta(frequencia=1.1, amortecimento=AMORT_DEDOS, lag=0.6),
    # Pés: presos ao chão pela IK, mas soltos o suficiente para acompanhar o
    # passo. Rigidez baixa, amortecimento médio, atraso médio.
    "left-feet": TensaoJunta(frequencia=1.6, amortecimento=0.55, lag=0.3),
    "right-feet": TensaoJunta(frequencia=1.6, amortecimento=0.55, lag=0.3),
}


#: Molas existentes, nomeadas aqui para centralizar a calibração. Os números
#: são os de hoje (não mudar): ``DanceMotion._molas`` e ``LagChain``.
DANCA_FREQUENCIA = 4.5
DANCA_AMORTECIMENTO = 0.55
CADEIA_FREQUENCIA = 3.2
CADEIA_AMORTECIMENTO = 0.9
CADEIA_ATENUACAO = 0.78


def tensao_de(grupo: str) -> TensaoJunta:
    """Devolve a tensão da junta, ou ``TENSAO_PADRAO`` para grupo desconhecido."""
    return TENSAO_POR_JUNTA.get(grupo, TENSAO_PADRAO)


def frequencia_de(grupo: str) -> float:
    """Rigidez (Hz) da junta, com fallback ao padrão para grupo desconhecido."""
    return tensao_de(grupo).frequencia


def amortecimento_de(grupo: str) -> float:
    """Amortecimento da junta, com fallback ao padrão para grupo desconhecido."""
    return tensao_de(grupo).amortecimento


def lag_de(grupo: str) -> float:
    """Atraso (0..1) da junta, com fallback ao padrão para grupo desconhecido."""
    return tensao_de(grupo).lag


# Falha cedo se o rig ganhar um grupo sem tensão definida: a tabela precisa
# cobrir todo o corpo (uma entrada por grupo de ALL_GROUPS).
_faltando = tuple(grupo for grupo in ALL_GROUPS if grupo not in TENSAO_POR_JUNTA)
if _faltando:
    raise RuntimeError(f"TENSAO_POR_JUNTA sem entrada para: {_faltando}")
