"""Ondulação dos tentáculos: uma onda viaja da base à ponta (lógica pura).

Cada segmento recebe a mesma senoide com atraso de fase proporcional à posição
ao longo do tentáculo. O envelope cresce da base (presa à cabeça) até a ponta,
o que dá a aparência de algo flexível e sinuoso. O deslocamento sai em px de
autoria; quem chama aplica a escala e a base (lateral, cima) da frente da cabeça.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sejoga.nucleo.esqueleto import IdlePersonality

# Defasagem entre o plano lateral e o plano vertical: a ponta descreve uma
# elipse (serpentear) em vez de oscilar num único plano.
DEFASAGEM_PLANOS_RAD = math.pi / 2

# Fases iniciais derivadas da semente do tentáculo (rad por unidade de semente).
FASE_POR_SEMENTE_RAD = 1e-3


@dataclass(frozen=True, slots=True)
class OndulacaoTuning:
    """Parâmetros da onda para um temperamento."""

    amplitude_lateral_px: float  # deslocamento máximo na ponta, plano lateral
    amplitude_cima_px: float  # deslocamento máximo na ponta, plano vertical
    frequencia_hz: float  # ciclos por segundo no tempo
    comprimento_onda: float  # em frações do comprimento do tentáculo
    expoente_envelope: float  # 1 = cresce linear da base à ponta; >1 concentra na ponta


ONDULACAO_CALMA = OndulacaoTuning(
    amplitude_lateral_px=7.0,
    amplitude_cima_px=4.0,
    frequencia_hz=0.45,
    comprimento_onda=1.1,
    expoente_envelope=1.3,
)
ONDULACAO_CURIOSA = OndulacaoTuning(
    amplitude_lateral_px=10.0,
    amplitude_cima_px=6.0,
    frequencia_hz=0.7,
    comprimento_onda=0.9,
    expoente_envelope=1.2,
)
ONDULACAO_AGITADA = OndulacaoTuning(
    amplitude_lateral_px=16.0,
    amplitude_cima_px=10.0,
    frequencia_hz=1.5,
    comprimento_onda=0.65,
    expoente_envelope=1.0,
)
ONDULACAO_TIMIDA = OndulacaoTuning(
    amplitude_lateral_px=5.0,
    amplitude_cima_px=3.0,
    frequencia_hz=0.35,
    comprimento_onda=1.2,
    expoente_envelope=1.4,
)
ONDULACAO_CONFIANTE = OndulacaoTuning(
    amplitude_lateral_px=12.0,
    amplitude_cima_px=7.0,
    frequencia_hz=0.9,
    comprimento_onda=0.8,
    expoente_envelope=1.1,
)

# Espirro (rajada): mesma onda, bem mais ampla e rápida; ativa só durante o burst.
ONDULACAO_ESPIRRO = OndulacaoTuning(
    amplitude_lateral_px=22.0,
    amplitude_cima_px=14.0,
    frequencia_hz=0.8,
    comprimento_onda=0.85,
    expoente_envelope=1.0,
)

ONDULACAO_POR_TEMPERAMENTO: dict[IdlePersonality, OndulacaoTuning] = {
    IdlePersonality.CALM: ONDULACAO_CALMA,
    IdlePersonality.CURIOUS: ONDULACAO_CURIOSA,
    IdlePersonality.PLAYFUL: ONDULACAO_AGITADA,
    IdlePersonality.SHY: ONDULACAO_TIMIDA,
    IdlePersonality.CONFIDENT: ONDULACAO_CONFIANTE,
    # Estilos herdam o temperamento mais próximo, como em SPRING_PARAMS.
    IdlePersonality.STREET: ONDULACAO_CALMA,
    IdlePersonality.FIGHTER: ONDULACAO_CONFIANTE,
    IdlePersonality.RHYTHM: ONDULACAO_CALMA,
    IdlePersonality.STYLISH: ONDULACAO_CURIOSA,
}


def atraso_de_fase_por_segmento(tuning: OndulacaoTuning, segmentos: int) -> float:
    """Atraso de fase (rad) entre segmentos vizinhos."""
    return math.tau / (tuning.comprimento_onda * max(1, segmentos - 1))


def deslocamento_ondulante(
    tuning: OndulacaoTuning,
    posicao: float,
    tempo: float,
    fase_inicial: float = 0.0,
) -> tuple[float, float]:
    """Deslocamento (lateral, cima) em px para a posição 0..1 ao longo do tentáculo.

    A base (posicao = 0) não se move. A onda avança da base para a ponta: a fase
    de um ponto é a do instante anterior da base, atrasada por `posicao`.
    """
    posicao = max(0.0, min(1.0, posicao))
    envelope = posicao**tuning.expoente_envelope
    fase = (
        math.tau * (tuning.frequencia_hz * tempo - posicao / tuning.comprimento_onda)
        + fase_inicial
    )
    return (
        tuning.amplitude_lateral_px * envelope * math.sin(fase),
        tuning.amplitude_cima_px * envelope * math.sin(fase - DEFASAGEM_PLANOS_RAD),
    )
