"""Gestos de mouse independentes do renderer e das APIs do Windows."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True)
class MouseEvent:
    kind: str
    position: tuple[int, int]


class MouseInteraction:
    """Só aceita gestos iniciados no mascote; soltar fora encerra o arraste."""

    def __init__(self, drag_threshold: float = 6.0, buttons: frozenset[str] = frozenset()):
        self.drag_threshold = drag_threshold
        self.buttons = buttons
        self.hovered = False
        self.dragging = False
        self.press_position: tuple[int, int] | None = None
        self._owned: set[str] = set()
        self._moved = False

    @property
    def has_press(self) -> bool:
        return bool(self._owned)

    def update(
        self,
        position: tuple[int, int],
        buttons: frozenset[str],
        *,
        hit: bool,
        enabled: bool = True,
        allow_drag: bool = True,
        allow_click: bool = True,
    ) -> list[MouseEvent]:
        events: list[MouseEvent] = []

        def emit(kind: str) -> None:
            events.append(MouseEvent(kind, position))

        hover = hit and enabled
        if hover != self.hovered:
            emit("hover_enter" if hover else "hover_exit")
            self.hovered = hover

        if not enabled or (self.dragging and not allow_drag):
            if self.dragging:
                emit("drag_cancel")
            self.dragging = False
            self._owned.clear()
            self.press_position = None
        else:
            for button in buttons - self.buttons:
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
                        emit("click")
                    self.dragging = False
                    self.press_position = None
                elif hit and allow_click and not was_dragging:
                    emit({"right": "pet", "middle": "poke"}[button])

        self.buttons = buttons
        return events
