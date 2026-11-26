"""Regras puras de gestos e pegada natural dos dedos (sem dependências de engine).

FRONTEIRA: Python puro; a aplicação aos pivôs Panda3D vive em ``render.gestos_dedos``.

Cada mão tem o próprio alvo por dedo (polegar..mindinho). Os gestos de estado
(``thumbs_up``, ``peace``...) continuam na mão direita por padrão
(``LADO_DOS_GESTOS``), mas qualquer gesto pode ser pedido na mão esquerda
(``gesto_esquerda`` em ``FingerGestures.update``) e as cenas/clipes controlam os
10 dedos de forma independente pela flexão individual (``pegada_de_curl``).
"""

from __future__ import annotations

from math import exp, pi, sin

# --------------------------------------------------------------------------- #
# Constantes dos dedos (ex-``dedos_tuning``)
# --------------------------------------------------------------------------- #
MESH_DEDOS_DIREITA = (32, 33, 34, 35, 36)
MESH_DEDOS_ESQUERDA = (40, 41, 42, 44, 43)
FRACOES_SEGMENTOS_DEDO = (0.40, 0.33, 0.27)
FRACOES_SEGMENTOS_POLEGAR = (0.55, 0.45)
ANGULO_PROJETO_SOBREPOSICAO_GRAUS = 14.0
FRACAO_MAXIMA_SOBREPOSICAO = 0.10
FRACAO_SECAO_DA_RAIZ = 0.05
PESOS_FLEXAO_DEDO = (0.34, 0.40, 0.26)
PESOS_FLEXAO_POLEGAR = (0.50, 0.50)
LIMITES_JUNTA_DEDO_GRAUS = ((-20.0, 95.0), (0.0, 105.0), (0.0, 80.0))
LIMITES_JUNTA_POLEGAR_GRAUS = ((-15.0, 70.0), (0.0, 80.0))
GANHO_CASCATA_DO_BLOCO = 1.0
FATOR_FLEXAO_GESTO = 1.18
FLEXAO_GESTO_REFERENCIA_GRAUS = 60.0
PRONACAO_POLEGAR_GRAUS = 8.0
CURL_REPOUSO_DEDO_GRAUS = (9.0, 14.0, 10.0)
CURL_REPOUSO_POLEGAR_GRAUS = (5.0, 7.0)
CURL_PUNHO_DEDO_GRAUS = (54.0, 62.0, 40.0)
CURL_PUNHO_POLEGAR_GRAUS = (28.0, 34.0)
ABERTURA_MAXIMA_GRAUS = (24.0, 14.0, 5.0, 6.0, 16.0)
OPOSICAO_POLEGAR_GRAUS = 2.5
VARIACAO_REPOUSO_POR_DEDO = (0.8, 0.85, 1.0, 1.15, 1.3)
FREQUENCIA_SECUNDARIA_HZ = 0.35
AMPLITUDE_SECUNDARIA_DEDO_GRAUS = (2.5, 3.5, 3.0)
AMPLITUDE_SECUNDARIA_POLEGAR_GRAUS = (2.0, 2.5)
ATRASO_FASE_JUNTA_RAD = 0.75
ATRASO_FASE_DEDO_RAD = 0.55
DESLOCAMENTO_FASE_LADO_RAD = 0.9
ATIVIDADE_POR_ESTADO = {
    "sleep": 0.4,
    "drag": 0.7,
    "walk": 1.5,
    "run": 2.0,
    "fall": 2.2,
    "dance": 2.5,
    "wave": 3.2,
    "stretch": 1.8,
    "peek": 1.5,
    "hit": 1.5,
}
FREQUENCIA_POR_ESTADO = {
    "sleep": 0.6,
    "walk": 1.5,
    "run": 2.2,
    "fall": 1.8,
    "dance": 2.6,
    "wave": 3.0,
    "stretch": 1.2,
    "hit": 2.0,
}
SUAVIZACAO_ANGULOS_POR_S = 14.0
PASSO_MAXIMO_S = 0.05
ATIVIDADE_PADRAO = 1.0
FREQUENCIA_PADRAO = 1.0

# --------------------------------------------------------------------------- #
# Cinemática em cascata (ex-``dedos_cascata``)
# --------------------------------------------------------------------------- #
INDICE_POLEGAR = 0


def numero_de_juntas(indice_dedo: int) -> int:
    """2 para o polegar, 3 para os demais."""
    return len(PESOS_FLEXAO_POLEGAR if indice_dedo == INDICE_POLEGAR else PESOS_FLEXAO_DEDO)


def _tabelas(indice_dedo: int) -> tuple[tuple, tuple, tuple, tuple]:
    if indice_dedo == INDICE_POLEGAR:
        return (
            PESOS_FLEXAO_POLEGAR,
            LIMITES_JUNTA_POLEGAR_GRAUS,
            CURL_REPOUSO_POLEGAR_GRAUS,
            AMPLITUDE_SECUNDARIA_POLEGAR_GRAUS,
        )
    return (
        PESOS_FLEXAO_DEDO,
        LIMITES_JUNTA_DEDO_GRAUS,
        CURL_REPOUSO_DEDO_GRAUS,
        AMPLITUDE_SECUNDARIA_DEDO_GRAUS,
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
    """Ângulo (graus) de cada junta do dedo ``indice_dedo`` (0 = polegar)."""
    pesos, limites, repouso, amplitude = _tabelas(indice_dedo)
    atividade = ATIVIDADE_POR_ESTADO.get(estado or "", ATIVIDADE_PADRAO)
    frequencia = FREQUENCIA_SECUNDARIA_HZ * FREQUENCIA_POR_ESTADO.get(estado or "", FREQUENCIA_PADRAO)
    domina = min(1.0, abs(flexao_gesto_graus) / FLEXAO_GESTO_REFERENCIA_GRAUS)
    atividade *= 1.0 - domina
    flexao_total = curl_bloco_graus * GANHO_CASCATA_DO_BLOCO + flexao_gesto_graus * FATOR_FLEXAO_GESTO
    fase_dedo = indice_dedo * ATRASO_FASE_DEDO_RAD + lado * DESLOCAMENTO_FASE_LADO_RAD
    angulos = []
    pegada = max(-1.0, min(1.0, pegada))
    punho = CURL_PUNHO_POLEGAR_GRAUS if indice_dedo == INDICE_POLEGAR else CURL_PUNHO_DEDO_GRAUS
    for junta, (peso, (minimo, maximo)) in enumerate(zip(pesos, limites, strict=True)):
        natural = repouso[junta] * VARIACAO_REPOUSO_POR_DEDO[indice_dedo]
        fase = 2.0 * pi * frequencia * t - fase_dedo - junta * ATRASO_FASE_JUNTA_RAD
        secundario = amplitude[junta] * atividade * sin(fase)
        bruto = natural * (1.0 - domina) + peso * flexao_total + secundario
        extremo = punho[junta] if pegada > 0 else 0.0
        bruto += (extremo - bruto) * abs(pegada)
        angulos.append(max(minimo, min(maximo, bruto)))
    return tuple(angulos)


def suavizar(atual: tuple[float, ...], alvo: tuple[float, ...], dt: float) -> tuple[float, ...]:
    """Aproxima cada ângulo do alvo (absorve troca de estado sem salto)."""
    passo = max(0.0, min(PASSO_MAXIMO_S, dt))
    k = 1.0 - exp(-passo * SUAVIZACAO_ANGULOS_POR_S)
    return tuple(a + (b - a) * k for a, b in zip(atual, alvo, strict=True))

#: Flexão de gesto (graus) por dedo: polegar, indicador, médio, anelar, mindinho.
GESTURES = {
    "hang_loose": (0, 75, 75, 75, 0),
    "thumbs_up": (0, 80, 80, 80, 80),
    "rock": (45, 0, 80, 80, 0),
    "finger_gun": (0, 0, 80, 80, 80),
    "peace": (30, 0, 0, 80, 80),
    # Apontar: só o indicador estendido, polegar dobrado à frente sem invadir o médio.
    "point": (42, 0, 80, 80, 80),
    # Teleporte do Goku (Shunkan Idō): indicador e médio unidos e retos na testa, demais dobrados.
    "goku_teleport": (55, 0, 0, 128, 132),
}
#: (lado, grupo do bloco dos dedos, malhas polegar..mindinho).
MAOS = (
    (1, "fingers", MESH_DEDOS_DIREITA),
    (-1, "fingers2", MESH_DEDOS_ESQUERDA),
)
#: Mão que recebe os gestos de estado quando nenhum lado é pedido explicitamente.
LADO_DOS_GESTOS = 1
#: Gestos cujo polegar dobra por cima dos dedos fechados (não fica para fora).
_POLEGAR_DOBRADO = frozenset({"rock", "point", "goku_teleport"})
PEGADAS = {
    "open_hands": -1.0,
    "close_fists": 1.0,
    "celebrate": 1.0,
    "blue_balls": 1.0,
    "virtual_insanity": -0.86,
}
#: Curl (0..1) que corresponde à pegada neutra (curvatura natural de repouso).
CURL_NEUTRO = 0.45 / 1.45


def pegada_de_curl(curl: float) -> float:
    """Converte a flexão individual de clipe/cena (0..1) em pegada (-0.90..1) C1 suave."""
    c = max(0.0, min(1.0, float(curl)))
    # Curva cúbica Hermite monotônica por (0, -0.90), (CURL_NEUTRO, 0.0), (1, 1.0)
    # eliminando a quina de derivada 2x em CURL_NEUTRO.
    m_mid = 1.90
    if c <= CURL_NEUTRO:
        h = CURL_NEUTRO
        u = c / h
        h00 = 2.0 * u * u * u - 3.0 * u * u + 1.0
        h10 = u * u * u - 2.0 * u * u + u
        h11 = u * u * u - u * u
        return -0.90 * h00 + h * (2.60 * h10 + m_mid * h11)
    h = 1.0 - CURL_NEUTRO
    u = (c - CURL_NEUTRO) / h
    h01 = -2.0 * u * u * u + 3.0 * u * u
    h10 = u * u * u - 2.0 * u * u + u
    h11 = u * u * u - u * u
    return h01 + h * (m_mid * h10 + 1.15 * h11)


def _pegada_natural(
    estado: str,
    relogio: float,
    fase_danca: float | None,
    lado: int,
    dedo: int,
    *,
    com_gesto: bool | None = None,
) -> float:
    """Calcula o fator de abertura/fechamento orgânico de cada dedo.

    ``com_gesto`` diz se esta mão está fazendo o gesto ``estado``; ``None``
    mantém a regra histórica (só ``LADO_DOS_GESTOS``).
    """
    if estado in PEGADAS:
        return PEGADAS[estado]
    atraso = lado * 0.9 + dedo * 0.17
    gesticula = (lado == LADO_DOS_GESTOS) if com_gesto is None else com_gesto
    if estado in GESTURES and gesticula:
        if estado in _POLEGAR_DOBRADO and dedo == 0:
            return 0.55
        if estado == "peace" and dedo in (1, 2):
            # Indicador abre para fora e médio afasta para formar o V do peace sign.
            return -1.0 if dedo == 1 else -0.85
        if estado == "goku_teleport" and dedo in (1, 2):
            # Indicador e médio retos e firmes na testa.
            return -0.90
        if estado == "point" and dedo == 1:
            return -0.85
        if dedo == 0 or GESTURES[estado][dedo] == 0:
            return -0.65 if dedo == 0 else -0.35
        return 0.0
    if fase_danca is not None:
        # Alterna abertura e pegada ao longo de dois tempos, com atraso nos dedos.
        return 0.67 * sin(fase_danca * 0.5 - atraso)
    amplitude = {
        "idle": 0.24,
        "hover": 0.28,
        "sit": 0.20,
        "wave": 0.50,
        "stretch": 0.45,
        "pet": 0.34,
        "peek": 0.30,
        "surprise": 0.42,
        "hit": 0.38,
        "poke": 0.34,
        "land": 0.26,
        "jump": 0.32,
        "teimosia": 0.45,
    }.get(estado, 0.0)
    if estado == "sleep":
        # Micro-espasmos REM suaves e esparsos nos dedos durante o sono.
        surto = max(0.0, sin(relogio * 0.37 + dedo * 1.3 + lado * 0.8) - 0.45) / 0.55
        return 0.22 * surto * sin(relogio * 2.4 - atraso)
    return amplitude * sin(relogio * 1.7 - atraso)


def abertura_dedo(
    estado: str,
    dedo: int,
    lado: int,
    pegada: float,
    gesto: float,
    abertura_maxima: float,
    *,
    com_gesto: bool | None = None,
) -> float:
    """Calcula o ângulo alvo de abertura lateral de um dedo (graus)."""
    if dedo == 0 and (pegada > 0 or gesto >= 50):
        # O polegar cruza o indicador e pousa sobre o punho.
        sinal = 1.0 if abertura_maxima >= 0 else -1.0
        oponente = -OPOSICAO_POLEGAR_GRAUS * sinal
        return oponente * max(pegada, min(1.0, gesto / 75.0))
    gesticula = (lado == LADO_DOS_GESTOS) if com_gesto is None else com_gesto
    if estado == "peace" and dedo == 1 and gesticula:
        # Abre o indicador para fora (+Y) formando o V sem empurrar o médio no anelar.
        return 14.0 if lado > 0 else -14.0
    if estado == "peace" and dedo == 2 and gesticula:
        # Médio afasta só 2° (evita atravessar o anelar colado).
        return -2.0 if lado > 0 else 2.0
    if estado == "goku_teleport" and dedo in (1, 2) and gesticula:
        # Indicador e médio colados um no outro para o gesto de teleporte na testa.
        return (-2.5 if dedo == 1 else 2.0) * (1.0 if lado > 0 else -1.0)
    if dedo > 0 and (pegada > 0.0 or gesto >= 45.0):
        # Folga paralela anticolisão ao fechar para os blocos não entrarem um no outro.
        fecho = max(pegada, min(1.0, gesto / 60.0))
        return abertura_maxima * 0.18 * fecho
    return abertura_maxima * max(0.0, -pegada)
