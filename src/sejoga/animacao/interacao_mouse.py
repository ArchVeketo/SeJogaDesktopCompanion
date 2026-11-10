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

        if not enabled or (self.dragging and not allow_drag):  # noqa: PLR1702  # TODO convenção: fatiar sem prova visual na GPU arrisca mudar o movimento; lote próprio com caracterização
            if self.dragging:
                emit("drag_cancel")
            self.dragging = False
            self._owned.clear()
            self.press_position = None
        else:
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
                        emit("drag_start")
                    if self.dragging:
                        emit("drag_move")

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
                elif hit and allow_click and not was_dragging:
                    emit({"right": "pet", "middle": "click"}[button])

        self.buttons = buttons
        return events
