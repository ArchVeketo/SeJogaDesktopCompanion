"""Trajetória de saída: hit stop branco, giro e lançamento para fora do desktop."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ExitFrame:
    x: int
    y: int
    roll: float
    done: bool


class ExitAnimation:
    DURATION = 1.35
    HIT_STOP = 0.14

    def __init__(self, origin, size, desktop_bounds):
        self.origin = origin
        left, top, right, _bottom = desktop_bounds
        self.direction = 1 if origin[0] + size / 2 >= (left + right) / 2 else -1
        self.target = (right + size if self.direction > 0 else left - size * 2, top - size * 2)

    def sample(self, elapsed: float) -> ExitFrame:
        progress = max(0.0, min(1.0, (elapsed - self.HIT_STOP) / (self.DURATION - self.HIT_STOP)))
        x = self.origin[0] + (self.target[0] - self.origin[0]) * progress ** 1.7
        y = self.origin[1] + (self.target[1] - self.origin[1]) * progress ** 1.3
        return ExitFrame(round(x), round(y), self.direction * 1080 * progress, elapsed >= self.DURATION)
