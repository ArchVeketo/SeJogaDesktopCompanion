"""Gestos de mouse independentes do renderer e das APIs do Windows."""

from __future__ import annotations

import time
from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True)
class MouseEvent:
    """Evento de mouse do polling, em coordenadas do desktop."""

    kind: str
    position: tuple[int, int]


class MouseInteraction:
    """Só aceita gestos iniciados no mascote; soltar fora encerra o arraste."""

    def __init__(
        self,
        drag_threshold: float = 6.0,
        buttons: frozenset[str] = frozenset(),
        double_click_seconds: float = 0.5,
        double_click_distance: float = 8.0,
    ):
        """Guarda o estado dos botões e a posição do cursor."""
        self.drag_threshold = drag_threshold
        self.buttons = buttons
        self.hovered = False
        self.dragging = False
        self.press_position: tuple[int, int] | None = None
        self._owned: set[str] = set()
        self._moved = False
        self.double_click_seconds = double_click_seconds
        self.double_click_distance = double_click_distance
        self._last_click: tuple[float, tuple[int, int]] | None = None
        # v2.0 — Carinho real por esfregar o cursor suavemente (sem clique)
        self._rub_pos: tuple[int, int] | None = None
        self._rub_time: float = 0.0
        self._rub_last_dir: int = 0
        self._rub_reversals: int = 0
        self._rub_distance: float = 0.0
        self._rub_last_pet: float = -999.0
        # v2.0 — Sacudida rápida durante arraste ("shake-to-dizzy")
        self._shake_pos: tuple[int, int] | None = None
        self._shake_last_dir: int = 0
        self._shake_times: list[float] = []
        self._shake_last_emit: float = -999.0

    def _resetar_carinho(self) -> None:
        self._rub_pos = None
        self._rub_last_dir = 0
        self._rub_reversals = 0
        self._rub_distance = 0.0

    def _resetar_sacudida(self) -> None:
        self._shake_pos = None
        self._shake_last_dir = 0
        self._shake_times.clear()

    def _atualizar_carinho(
        self, position: tuple[int, int], now: float, emit
    ) -> None:
        """Detecta passar a mão (vai-e-vem suave sobre o mascote) sem clicar."""
        if self._rub_pos is None:
            self._rub_pos = position
            self._rub_time = now
            return
        dt = now - self._rub_time
        dx = position[0] - self._rub_pos[0]
        dy = position[1] - self._rub_pos[1]
        dist = hypot(dx, dy)
        self._rub_pos = position
        self._rub_time = now
        if dt > 0.45 or dist < 1.5:
            if dt > 0.7:
                self._rub_reversals = 0
                self._rub_distance = 0.0
            return
        speed = dist / max(1e-3, dt)
        if speed > 1100.0:
            # Movimento brusco demais não é carinho.
            self._rub_reversals = 0
            self._rub_distance = 0.0
            return
        self._rub_distance += dist
        axis = dx if abs(dx) >= abs(dy) else dy
        if abs(axis) >= 3.0:
            direcao = 1 if axis > 0 else -1
            if self._rub_last_dir != 0 and direcao != self._rub_last_dir:
                self._rub_reversals += 1
            self._rub_last_dir = direcao
        if (
            self._rub_reversals >= 2
            and self._rub_distance >= 52.0
            and (now - self._rub_last_pet) >= 1.15
        ):
            emit("pet")
            self._rub_last_pet = now
            self._rub_reversals = 0
            self._rub_distance = 0.0

    def _atualizar_sacudida(
        self, position: tuple[int, int], now: float, emit
    ) -> None:
        """Detecta sacudida rápida horizontal durante o arraste."""
        if self._shake_pos is None:
            self._shake_pos = position
            return
        dx = position[0] - self._shake_pos[0]
        self._shake_pos = position
        if abs(dx) < 12.0:
            return
        direcao = 1 if dx > 0 else -1
        if self._shake_last_dir != 0 and direcao != self._shake_last_dir:
            self._shake_times = [t for t in self._shake_times if now - t <= 0.85]
            self._shake_times.append(now)
            if len(self._shake_times) >= 4 and (now - self._shake_last_emit) >= 1.6:
                emit("drag_shake")
                self._shake_last_emit = now
                self._shake_times.clear()
        self._shake_last_dir = direcao

    @property
    def has_press(self) -> bool:
        """Informa se o evento traz um clique pressionado."""
        return bool(self._owned)

    def update(  # noqa: C901, PLR0915  # TODO convenção: fatiar sem prova visual na GPU arrisca mudar o movimento; lote próprio com caracterização
        self,
        position: tuple[int, int],
        buttons: frozenset[str],
        *,
        hit: bool,
        enabled: bool = True,
        allow_drag: bool = True,
        allow_click: bool = True,
        now: float | None = None,
    ) -> list[MouseEvent]:
        """Processa o evento de mouse e devolve a interação reconhecida."""
        events: list[MouseEvent] = []
        now = time.monotonic() if now is None else now
        if not enabled or not allow_click:
            self._last_click = None

        def emit(kind: str) -> None:
            events.append(MouseEvent(kind, position))

        hover = hit and enabled
        if hover != self.hovered:
            emit("hover_enter" if hover else "hover_exit")
            self.hovered = hover

        if not enabled or (self.dragging and not allow_drag):  # noqa: PLR1702
            if self.dragging:
                emit("drag_cancel")
            self.dragging = False
            self._owned.clear()
            self.press_position = None
            self._resetar_carinho()
            self._resetar_sacudida()
        else:
            if hover and not buttons and not self.dragging and allow_click:
                self._atualizar_carinho(position, now, emit)
            else:
                self._resetar_carinho()

            for button in buttons - self.buttons:
                if button != "left" or not hit:
                    self._last_click = None
                if hit:
                    self._owned.add(button)
                    if button == "left":
                        self.press_position = position
                        self._moved = False

            if "left" in self._owned and self.press_position is not None:
                dx = position[0] - self.press_position[0]
                dy = position[1] - self.press_position[1]
                self._moved |= hypot(dx, dy) >= self.drag_threshold
                if "left" in buttons:
                    if self._moved and allow_drag and not self.dragging:
                        self._last_click = None
                        self.dragging = True
                        self._resetar_sacudida()
                        emit("drag_start")
                    if self.dragging:
                        emit("drag_move")
                        self._atualizar_sacudida(position, now, emit)

            was_dragging = self.dragging
            for button in sorted(self.buttons - buttons):
                if button not in self._owned:
                    continue
                self._owned.remove(button)
                if button == "left":
                    if self.dragging:
                        emit("drag_end")
                    elif hit and not self._moved and allow_click:
                        previous = self._last_click
                        if (
                            previous
                            and 0 <= now - previous[0] <= self.double_click_seconds
                            and hypot(
                                position[0] - previous[1][0],
                                position[1] - previous[1][1],
                            )
                            <= self.double_click_distance
                        ):
                            emit("double_click")
                            self._last_click = None
                        else:
                            emit("poke")
                            self._last_click = (now, position)
                    else:
                        self._last_click = None
                    self.dragging = False
                    self.press_position = None
                    self._resetar_sacudida()
                elif hit and allow_click and not was_dragging and button == "middle":
                    # Botão direito abre o menu de contexto; carinho agora é esfregar o mouse!
                    emit("click")

        self.buttons = buttons
        return events
