"""Hover acompanha o cursor ocioso, sem disputar outras interações do desktop."""


class HoverAttention:
    def __init__(self, resume_delay=1.0):
        self.resume_delay = resume_delay
        self.resume_at = 0.0

    def update(self, now, *, external_press=False, typing=False, busy_cursor=False, focus_changed=False):
        if external_press or typing or busy_cursor or focus_changed:
            self.resume_at = now + self.resume_delay
            return False
        return now >= self.resume_at
