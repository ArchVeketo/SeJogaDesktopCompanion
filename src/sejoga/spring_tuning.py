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

from .rig import ALL_GROUPS


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
    # Braços (parte alta): rigidez média, amortecimento médio, atraso leve —
    # começam a soltar em relação ao ombro.
    "right-arm": TensaoJunta(frequencia=2.2, amortecimento=0.6, lag=0.15),
    "left-arm": TensaoJunta(frequencia=2.2, amortecimento=0.6, lag=0.15),
    # Antebraços: rigidez média-baixa, mais balanço, atraso médio — arrastam
    # atrás do braço.
    "ant-arm": TensaoJunta(frequencia=1.8, amortecimento=0.5, lag=0.3),
    "ant-arm2": TensaoJunta(frequencia=1.8, amortecimento=0.5, lag=0.3),
    # Mãos: rigidez baixa, bastante balanço, atraso alto — a ponta solta.
    "hand": TensaoJunta(frequencia=1.4, amortecimento=0.5, lag=0.5),
    "hand2": TensaoJunta(frequencia=1.4, amortecimento=0.5, lag=0.5),
    # Dedos: a ponta mais solta de todas. Rigidez muito baixa, mais balanço,
    # atraso o mais alto.
    "fingers": TensaoJunta(frequencia=1.1, amortecimento=0.4, lag=0.6),
    "fingers2": TensaoJunta(frequencia=1.1, amortecimento=0.4, lag=0.6),
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
