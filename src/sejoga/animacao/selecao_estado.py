"""Seleção de estado de animação baseado em estímulos físicos.

Extraído de `controlador_animacao.py` para manter o módulo < 200 linhas.
Decide qual estado de animação o Mário deve estar com base na velocidade,
gravidade, arraste e música.

Manifesto: §4.1 — Camada 1 (Agência & Sistema de Desejos).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sejoga.animacao.controlador_animacao import AnimationState


def escolher_estado(
    *,
    speed: float,
    grounded: bool,
    gravity_active: bool,
    dragging: bool,
    music_playing: bool,
    music_intensity: float,
    current_state: AnimationState | None = None,
) -> AnimationState:
    """Escolhe o estado de animação com base nos estímulos atuais (com histerese)."""
    from sejoga.animacao.controlador_animacao import AnimationState

    if dragging:
        return AnimationState.DRAG
    if gravity_active or (not grounded and speed > 120.0):
        return AnimationState.FALL
    if music_playing and music_intensity > 0.01:
        return AnimationState.DANCE
    limiar_run = 560.0 if current_state == AnimationState.RUN else 700.0
    if grounded and speed > limiar_run:
        return AnimationState.RUN
    limiar_walk = 75.0 if current_state == AnimationState.WALK else 120.0
    if grounded and speed > limiar_walk:
        return AnimationState.WALK
    return AnimationState.IDLE
