"""Seleção de estado de animação baseado em estímulos físicos.

Extraído de `controlador_animacao.py` para manter o módulo < 200 linhas.
Decide qual estado de animação o Mário deve estar com base na velocidade,
gravidade, arraste e música.

Manifesto: §4.1 — Camada 1 (Agência & Sistema de Desejos).
"""

from __future__ import annotations

from sejoga.animacao.controlador_animacao import AnimationState


def escolher_estado(
    *,
    speed: float,
    grounded: bool,
    gravity_active: bool,
    dragging: bool,
    music_playing: bool,
    music_intensity: float,
) -> AnimationState:
    """Escolhe o estado de animação com base nos estímulos atuais.

    Prioridade: arraste > queda > dança > corrida > caminhada > idle.

    Parâmetros
    ----------
    speed : float
        Velocidade horizontal do corpo (pixels/s).
    grounded : bool
        True se o corpo está apoiado no piso.
    gravity_active : bool
        True se a gravidade está atuando (queda livre).
    dragging : bool
        True se o usuário está arrastando o mascote.
    music_playing : bool
        True se há música sendo reproduzida.
    music_intensity : float
        Intensidade da música (0..1).

    Retorna
    -------
    AnimationState
        O estado mais adequado para os estímulos atuais.
    """
    if dragging:
        return AnimationState.DRAG
    if gravity_active or (not grounded and speed > 120.0):
        return AnimationState.FALL
    if music_playing and music_intensity > 0.01:
        return AnimationState.DANCE
    if grounded and speed > 700.0:
        return AnimationState.RUN
    if grounded and speed > 120.0:
        return AnimationState.WALK
    return AnimationState.IDLE
