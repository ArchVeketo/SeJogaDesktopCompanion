"""Hover acompanha o cursor ocioso, sem disputar outras interações do desktop."""


class HoverAttention:
    """Atenção ao cursor sob hover, com atraso para retomar o idle."""

    def __init__(self, resume_delay=1.0):
        """Guarda o atraso de retomada após o cursor sair."""
        self.resume_delay = resume_delay
        self.resume_at = 0.0

    def update(
        self,
        now,
        *,
        external_press=False,
        typing=False,
        busy_cursor=False,
        focus_changed=False,
    ):
        """Atualiza a atenção a partir do hover e da posição do cursor."""
        if external_press or typing or busy_cursor or focus_changed:
            self.resume_at = now + self.resume_delay
            return False
        return now >= self.resume_at
