"""Ângulos das juntas dos dedos: flexão em cascata + movimento secundário.

Função pura. Recebe o giro do bloco (nó ``fingers``/``fingers2``), a flexão de
gesto e o estado, e devolve o ângulo de cada junta da cadeia base → ponta.
Ângulo POSITIVO = dedo fechando, igual para os dois lados (o espelho fica no
eixo de flexão, ver ``nucleo.malha_corte.eixo_de_flexao``).

FRONTEIRA: Python puro (só ``math``); NÃO importa Panda3D, Qt nem Win32.
"""

from __future__ import annotations

from math import exp, pi, sin

from sejoga.animacao import dedos_tuning as T

INDICE_POLEGAR = 0


def numero_de_juntas(indice_dedo: int) -> int:
    """2 para o polegar, 3 para os demais."""
    return len(T.PESOS_FLEXAO_POLEGAR if indice_dedo == INDICE_POLEGAR else T.PESOS_FLEXAO_DEDO)


def _tabelas(indice_dedo: int) -> tuple[tuple, tuple, tuple, tuple]:
    if indice_dedo == INDICE_POLEGAR:
        return (
            T.PESOS_FLEXAO_POLEGAR, T.LIMITES_JUNTA_POLEGAR_GRAUS,
            T.CURL_REPOUSO_POLEGAR_GRAUS, T.AMPLITUDE_SECUNDARIA_POLEGAR_GRAUS,
        )

    return (
        T.PESOS_FLEXAO_DEDO, T.LIMITES_JUNTA_DEDO_GRAUS,
        T.CURL_REPOUSO_DEDO_GRAUS, T.AMPLITUDE_SECUNDARIA_DEDO_GRAUS,
    )


def angulos_juntas(
    indice_dedo: int,
    lado: int,
    t: float,
    estado: str | None,
    curl_bloco_graus: float,
    flexao_gesto_graus: float = 0.0,
) -> tuple[float, ...]:
    """Ângulo (graus) de cada junta do dedo ``indice_dedo`` (0 = polegar).

    ``lado``: +1 direita, -1 esquerda. ``curl_bloco_graus``: giro do nó do bloco
    já com o sinal de "fechar" positivo. ``flexao_gesto_graus``: flexão total
    pedida por um gesto (0 = sem gesto).
    """
    pesos, limites, repouso, amplitude = _tabelas(indice_dedo)
    atividade = T.ATIVIDADE_POR_ESTADO.get(estado or "", T.ATIVIDADE_PADRAO)
    frequencia = T.FREQUENCIA_SECUNDARIA_HZ * T.FREQUENCIA_POR_ESTADO.get(estado or "", T.FREQUENCIA_PADRAO)
    # Gesto firme manda no dedo: o movimento secundário some conforme a flexão.
    domina = min(1.0, abs(flexao_gesto_graus) / T.FLEXAO_GESTO_REFERENCIA_GRAUS)
    atividade *= 1.0 - domina

    flexao_total = (
        curl_bloco_graus * T.GANHO_CASCATA_DO_BLOCO
        + flexao_gesto_graus * T.FATOR_FLEXAO_GESTO
    )
    fase_dedo = indice_dedo * T.ATRASO_FASE_DEDO_RAD + lado * T.DESLOCAMENTO_FASE_LADO_RAD
    angulos = []

    for junta, (peso, (minimo, maximo)) in enumerate(zip(pesos, limites, strict=True)):
        natural = repouso[junta] * T.VARIACAO_REPOUSO_POR_DEDO[indice_dedo]
        fase = 2.0 * pi * frequencia * t - fase_dedo - junta * T.ATRASO_FASE_JUNTA_RAD
        secundario = amplitude[junta] * atividade * sin(fase)
        bruto = natural * (1.0 - domina) + peso * flexao_total + secundario
        angulos.append(max(minimo, min(maximo, bruto)))

    return tuple(angulos)


def suavizar(atual: tuple[float, ...], alvo: tuple[float, ...], dt: float) -> tuple[float, ...]:
    """Aproxima cada ângulo do alvo (absorve troca de estado sem salto)."""
    passo = max(0.0, min(T.PASSO_MAXIMO_S, dt))
    k = 1.0 - exp(-passo * T.SUAVIZACAO_ANGULOS_POR_S)

    return tuple(a + (b - a) * k for a, b in zip(atual, alvo, strict=True))
