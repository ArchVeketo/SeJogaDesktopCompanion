"""Curvas e transição dos tentáculos, sem dependência de renderização."""


class AppendageMotion:
    def __init__(self):
        self.extension = 0.0
        self.previous_extension = 0.0

    def update(self, dt, door_degrees):
        self.previous_extension = self.extension
        target = max(0.0, min(1.0, (door_degrees - 10.0) / 60.0))
        rate = 2.8 if target > self.extension else 1.5
        distance = max(0.0, min(.1, dt)) * rate
        delta = target - self.extension
        self.extension += max(-distance, min(distance, delta))
        return self.extension

