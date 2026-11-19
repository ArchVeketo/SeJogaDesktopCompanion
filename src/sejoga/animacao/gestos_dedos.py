"""Regras puras de gestos e pegada natural dos dedos (sem dependências de engine).

FRONTEIRA: Python puro; a aplicação aos pivôs Panda3D vive em ``render.gestos_dedos``.

Cada mão tem o próprio alvo por dedo (polegar..mindinho). Os gestos de estado
(``thumbs_up``, ``peace``...) continuam na mão direita por padrão
(``LADO_DOS_GESTOS``), mas qualquer gesto pode ser pedido na mão esquerda
(``gesto_esquerda`` em ``FingerGestures.update``) e as cenas/clipes controlam os
10 dedos de forma independente pela flexão individual (``pegada_de_curl``).
"""

from __future__ import annotations

from math import sin

from sejoga.animacao import dedos_tuning as tuning_dedos

#: Flexão de gesto (graus) por dedo: polegar, indicador, médio, anelar, mindinho.
GESTURES = {
    "hang_loose": (0, 75, 75, 75, 0),
    "thumbs_up": (0, 80, 80, 80, 80),
    "rock": (65, 0, 80, 80, 0),
    "finger_gun": (0, 0, 80, 80, 80),
    "peace": (42, 0, 0, 80, 80),
    # Apontar: só o indicador estendido, polegar dobrado por cima do médio.
    "point": (60, 0, 80, 80, 80),
}
#: (lado, grupo do bloco dos dedos, malhas polegar..mindinho).
MAOS = (
    (1, "fingers", tuning_dedos.MESH_DEDOS_DIREITA),
    (-1, "fingers2", tuning_dedos.MESH_DEDOS_ESQUERDA),
)
#: Mão que recebe os gestos de estado quando nenhum lado é pedido explicitamente.
LADO_DOS_GESTOS = 1
#: Gestos cujo polegar dobra por cima dos dedos fechados (não fica para fora).
_POLEGAR_DOBRADO = frozenset({"rock", "point"})
PEGADAS = {
    "open_hands": -1.0,
    "close_fists": 1.0,
    "blue_balls": 1.0,
    "virtual_insanity": -0.86,
}
#: Curl (0..1) que corresponde à pegada neutra (curvatura natural de repouso).
CURL_NEUTRO = 0.45 / 1.45


def pegada_de_curl(curl: float) -> float:
    """Converte a flexão individual de clipe/cena (0..1) em pegada (-0.90..1)."""
    c = max(0.0, min(1.0, float(curl)))
    if c <= CURL_NEUTRO:
        return -0.90 * (1.0 - c / CURL_NEUTRO)
    return (c - CURL_NEUTRO) / (1.0 - CURL_NEUTRO)


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
        if estado == "point" and dedo == 1:
            return -0.85
        if dedo == 0 or GESTURES[estado][dedo] == 0:
            return -0.65 if dedo == 0 else -0.35
        return 0.0
    if fase_danca is not None:
        # Alterna abertura e pegada ao longo de dois tempos, com atraso nos dedos.
        return 0.67 * sin(fase_danca * 0.5 - atraso)
    amplitude = {"idle": 0.24, "hover": 0.28, "wave": 0.5, "stretch": 0.45}.get(
        estado, 0.0
    )
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
        oponente = -tuning_dedos.OPOSICAO_POLEGAR_GRAUS * sinal
        return oponente * max(pegada, min(1.0, gesto / 75.0))
    gesticula = (lado == LADO_DOS_GESTOS) if com_gesto is None else com_gesto
    if estado == "peace" and dedo == 2 and gesticula:
        # Afasta o dedo médio em direção oposta ao indicador para abrir o V.
        return -10.5 if lado > 0 else 10.5
    if dedo > 0 and (pegada > 0.0 or gesto >= 45.0):
        # Folga paralela anticolisão ao fechar para os blocos não entrarem um no outro.
        fecho = max(pegada, min(1.0, gesto / 60.0))
        return abertura_maxima * 0.18 * fecho
    return abertura_maxima * max(0.0, -pegada)
