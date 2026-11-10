"""Análise numérica mínima de curvas de ângulo (graus, 60 fps), sem engine.

Resto útil de ``tools/analisar_anim.py`` (removido no lote 4 do ponytail): só os
dois detectores que os testes usam, com os mesmos limiares e o mesmo algoritmo.
- ``SUAVIDADE``: pico de jerk >= ``LIMIAR_JERK_TRANCO`` numa junta/eixo ativo.
- ``LOOP``: pop de posição ou velocidade no fechamento de um clipe em loop.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

FPS = 60.0
#: Pico de jerk (graus/s^3) acima do qual o frame é um TRANCO.
LIMIAR_JERK_TRANCO = 8000.0
#: Descontinuidade de posição (graus) / velocidade (graus/s) no fechamento do loop.
LIMIAR_POP_POSICAO = 0.5
LIMIAR_POP_VELOCIDADE = 30.0
#: Amplitude mínima (graus) para a junta/eixo contar como ativo.
AMPLITUDE_MINIMA_ATIVA = 2.0
EIXOS = ("x", "y", "z")

Amostrador = Callable[[float], dict[str, tuple[float, float, float]]]


@dataclass(frozen=True)
class ClipeAnalisavel:
    """Clipe amostrável por tempo, com duração e laço."""

    nome: str
    amostrar: Amostrador
    duracao: float
    loop: bool


@dataclass
class SerieEixo:
    """Série de um eixo de um grupo amostrada no tempo."""

    angulo: list[float]
    velocidade: list[float]
    jerk: list[float]


@dataclass(frozen=True)
class Constatacao:
    """Constatação da análise de curva (tranco, salto ou pausa)."""

    categoria: str
    grupo: str
    eixo: str
    metrica: str


def _derivar(valores: list[float], dt: float) -> list[float]:
    """Diferenças centrais (bordas por diferença simples), mesmo comprimento."""
    n = len(valores)

    if n < 2:
        return [0.0] * n

    saida = [0.0] * n
    saida[0] = (valores[1] - valores[0]) / dt
    saida[-1] = (valores[-1] - valores[-2]) / dt

    for i in range(1, n - 1):
        saida[i] = (valores[i + 1] - valores[i - 1]) / (2.0 * dt)

    return saida


def amplitude(serie: SerieEixo) -> float:
    return max(serie.angulo) - min(serie.angulo) if serie.angulo else 0.0


def amostrar_clipe(clipe: ClipeAnalisavel) -> dict[str, tuple[SerieEixo, ...]]:
    """Amostra a ``FPS`` (inclusive o último frame) e deriva velocidade e jerk."""
    dt = 1.0 / FPS
    passos = max(2, round(clipe.duracao * FPS))
    brutos: dict[str, tuple[list[float], list[float], list[float]]] = {}

    for i in range(passos + 1):
        for grupo, angulos in clipe.amostrar(i * dt).items():
            trio = brutos.setdefault(grupo, ([], [], []))
            for lista, valor in zip(trio, angulos, strict=True):
                lista.append(valor)

    series: dict[str, tuple[SerieEixo, ...]] = {}

    for grupo, trio in brutos.items():
        eixos = []

        for ang in trio:
            vel = _derivar(ang, dt)
            eixos.append(SerieEixo(ang, vel, _derivar(_derivar(vel, dt), dt)))

        series[grupo] = tuple(eixos)

    return series


def analisar(clipe: ClipeAnalisavel) -> list[Constatacao]:
    """Detecta trancos (SUAVIDADE) e, se ``loop``, pops de fechamento (LOOP)."""
    achados: list[Constatacao] = []

    for grupo, trio in amostrar_clipe(clipe).items():
        for eixo, serie in zip(EIXOS, trio, strict=True):
            if amplitude(serie) < AMPLITUDE_MINIMA_ATIVA:
                continue

            pior_jerk = max((abs(j) for j in serie.jerk), default=0.0)

            if pior_jerk >= LIMIAR_JERK_TRANCO:
                achados.append(
                    Constatacao(
                        "SUAVIDADE",
                        grupo,
                        eixo,
                        f"tranco: pico de jerk {pior_jerk:,.0f}",
                    )
                )

            if not clipe.loop:
                continue

            salto_pos = abs(serie.angulo[-1] - serie.angulo[0])
            salto_vel = abs(serie.velocidade[-1] - serie.velocidade[0])

            if salto_pos >= LIMIAR_POP_POSICAO or salto_vel >= LIMIAR_POP_VELOCIDADE:
                achados.append(
                    Constatacao(
                        "LOOP",
                        grupo,
                        eixo,
                        f"pop no fechamento: {salto_pos:.2f} graus, {salto_vel:.1f} graus/s",
                    )
                )

    return achados
