"""Ângulos das juntas dos dedos: flexão em cascata + movimento secundário.

Função pura. Recebe o giro do bloco (nó ``fingers``/``fingers2``), a flexão de
gesto e o estado, e devolve o ângulo de cada junta da cadeia base → ponta.
Ângulo POSITIVO = dedo fechando, igual para os dois lados (o espelho fica no
eixo de flexão, ver ``nucleo.malha_corte.eixo_de_flexao``).

FRONTEIRA: Python puro (só ``math``); NÃO importa Panda3D, Qt nem Win32.
"""

from __future__ import annotations

from math import exp, pi, sin

from sejoga.animacao import dedos_tuning as tuning_dedos

INDICE_POLEGAR = 0


def numero_de_juntas(indice_dedo: int) -> int:
    """2 para o polegar, 3 para os demais."""
    return len(
        tuning_dedos.PESOS_FLEXAO_POLEGAR
        if indice_dedo == INDICE_POLEGAR
        else tuning_dedos.PESOS_FLEXAO_DEDO
    )


def _tabelas(indice_dedo: int) -> tuple[tuple, tuple, tuple, tuple]:
    if indice_dedo == INDICE_POLEGAR:
        return (
            tuning_dedos.PESOS_FLEXAO_POLEGAR,
            tuning_dedos.LIMITES_JUNTA_POLEGAR_GRAUS,
            tuning_dedos.CURL_REPOUSO_POLEGAR_GRAUS,
            tuning_dedos.AMPLITUDE_SECUNDARIA_POLEGAR_GRAUS,
        )

    return (
        tuning_dedos.PESOS_FLEXAO_DEDO,
        tuning_dedos.LIMITES_JUNTA_DEDO_GRAUS,
        tuning_dedos.CURL_REPOUSO_DEDO_GRAUS,
        tuning_dedos.AMPLITUDE_SECUNDARIA_DEDO_GRAUS,
    )


def angulos_juntas(
    indice_dedo: int,
    lado: int,
    t: float,
    estado: str | None,
    curl_bloco_graus: float,
    flexao_gesto_graus: float = 0.0,
    *,
    pegada: float = 0.0,
) -> tuple[float, ...]:
    """Ângulo (graus) de cada junta do dedo ``indice_dedo`` (0 = polegar).

    ``lado``: +1 direita, -1 esquerda. ``curl_bloco_graus``: giro do nó do bloco
    já com o sinal de "fechar" positivo. ``flexao_gesto_graus``: flexão total
    pedida por um gesto (0 = sem gesto). A pegada varia de -1 (estendida)
    a 1 (punho fechado), com 0 mantendo a curvatura natural do dedo.
    """
    pesos, limites, repouso, amplitude = _tabelas(indice_dedo)
    atividade = tuning_dedos.ATIVIDADE_POR_ESTADO.get(
        estado or "", tuning_dedos.ATIVIDADE_PADRAO
    )
    frequencia = (
        tuning_dedos.FREQUENCIA_SECUNDARIA_HZ
        * tuning_dedos.FREQUENCIA_POR_ESTADO.get(
            estado or "", tuning_dedos.FREQUENCIA_PADRAO
        )
    )
    # Gesto firme manda no dedo: o movimento secundário some conforme a flexão.
    domina = min(
        1.0, abs(flexao_gesto_graus) / tuning_dedos.FLEXAO_GESTO_REFERENCIA_GRAUS
    )
    atividade *= 1.0 - domina

    flexao_total = (
        curl_bloco_graus * tuning_dedos.GANHO_CASCATA_DO_BLOCO
        + flexao_gesto_graus * tuning_dedos.FATOR_FLEXAO_GESTO
    )
    fase_dedo = (
        indice_dedo * tuning_dedos.ATRASO_FASE_DEDO_RAD
        + lado * tuning_dedos.DESLOCAMENTO_FASE_LADO_RAD
    )
    angulos = []
    pegada = max(-1.0, min(1.0, pegada))
    punho = (
        tuning_dedos.CURL_PUNHO_POLEGAR_GRAUS
        if indice_dedo == INDICE_POLEGAR
        else tuning_dedos.CURL_PUNHO_DEDO_GRAUS
    )

    for junta, (peso, (minimo, maximo)) in enumerate(zip(pesos, limites, strict=True)):
        natural = repouso[junta] * tuning_dedos.VARIACAO_REPOUSO_POR_DEDO[indice_dedo]
        fase = (
            2.0 * pi * frequencia * t
            - fase_dedo
            - junta * tuning_dedos.ATRASO_FASE_JUNTA_RAD
        )
        secundario = amplitude[junta] * atividade * sin(fase)
        bruto = natural * (1.0 - domina) + peso * flexao_total + secundario
        extremo = punho[junta] if pegada > 0 else 0.0
        bruto += (extremo - bruto) * abs(pegada)
        angulos.append(max(minimo, min(maximo, bruto)))

    return tuple(angulos)


def suavizar(
    atual: tuple[float, ...], alvo: tuple[float, ...], dt: float
) -> tuple[float, ...]:
    """Aproxima cada ângulo do alvo (absorve troca de estado sem salto)."""
    passo = max(0.0, min(tuning_dedos.PASSO_MAXIMO_S, dt))
    k = 1.0 - exp(-passo * tuning_dedos.SUAVIZACAO_ANGULOS_POR_S)

    return tuple(a + (b - a) * k for a, b in zip(atual, alvo, strict=True))
