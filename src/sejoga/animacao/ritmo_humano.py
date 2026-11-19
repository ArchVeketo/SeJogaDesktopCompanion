"""Ritmo humano, variância orgânica e tempo de rebalanceio pós-ação (v2.0).

Humanos não se movem em metrônomo perfeito nem emendam ações instantaneamente:
variamos velocidade, força, cadência de transição e precisamos de um pequeno
respiro de rebalanceio depois de pular, correr, reagir ou terminar um gesto.

FRONTEIRA: Python puro, sem engine (Panda3D/Qt/Win32).
"""

from __future__ import annotations

import random
from math import sin

# Fator de cascata por região do rig nas transições (PoseResolver):
# centro de massa lidera (< 1.0), cabeça e braços seguem, pontas/antenas assentam por último.
FATOR_CASCATA_POR_GRUPO: dict[str, float] = {
    "body": 0.82,
    "legs": 0.82,
    "pelvis": 0.84,
    "cintura": 0.86,
    "abdomen": 0.90,
    "peitoral": 0.94,
    "shoulder": 0.96,
    "shoulder2": 0.96,
    "head": 1.05,
    "door": 1.08,
    "right-arm": 1.14,
    "left-arm": 1.14,
    "ant-arm": 1.22,
    "ant-arm2": 1.22,
    "hand": 1.30,
    "hand2": 1.30,
    "fingers": 1.36,
    "fingers2": 1.36,
    "fones": 1.34,
    "fone-direito": 1.38,
    "fone-esquerdo": 1.38,
    "antena-direita": 1.46,
    "antena-esquerda": 1.46,
}

MAX_FATOR_CASCATA: float = max(FATOR_CASCATA_POR_GRUPO.values())


def fator_cascata_grupo(grupo: str) -> float:
    """Devolve o multiplicador de duração da transição para ``grupo``."""
    return FATOR_CASCATA_POR_GRUPO.get(grupo, 1.0)


class RitmoHumano:
    """Injeta variância orgânica de velocidade, força, transições e respiro pós-ação."""

    def __init__(self, *, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self.escala_velocidade: float = 1.0
        self.escala_forca: float = 1.0
        self.fator_transicao: float = 1.0
        self.rebalanceio_restante: float = 0.0
        self._relogio: float = 0.0

    @property
    def em_rebalanceio(self) -> bool:
        """True enquanto Mário ainda está assentando o peso/respirando após uma ação."""
        return self.rebalanceio_restante > 0.0

    def atualizar(self, dt: float) -> None:
        """Avança o relógio orgânico e reduz o tempo de rebalanceio."""
        dt_c = max(0.0, dt)
        self._relogio += dt_c
        if self.rebalanceio_restante > 0.0:
            self.rebalanceio_restante = max(0.0, self.rebalanceio_restante - dt_c)

    def sortear_intencao(self, tipo: str = "normal") -> tuple[float, float, float]:
        """Sorteia (velocidade, força, fator_transicao) únicos para uma nova ação."""
        if tipo == "calma":
            vel = self._rng.uniform(0.84, 1.08)
            forca = self._rng.uniform(0.86, 1.10)
            trans = self._rng.uniform(1.00, 1.28)
        elif tipo == "impacto":
            vel = self._rng.uniform(0.94, 1.12)
            forca = self._rng.uniform(0.92, 1.18)
            trans = self._rng.uniform(0.88, 1.14)
        else:
            vel = self._rng.uniform(0.87, 1.14)
            forca = self._rng.uniform(0.88, 1.16)
            trans = self._rng.uniform(0.90, 1.24)
        self.escala_velocidade = vel
        self.escala_forca = forca
        self.fator_transicao = trans
        return (vel, forca, trans)

    def iniciar_rebalanceio(self, base_s: float = 1.25) -> None:
        """Concede um respiro orgânico pós-ação antes de disparar novas iniciativas."""
        dur = max(0.45, base_s * self._rng.uniform(0.82, 1.32))
        self.rebalanceio_restante = max(self.rebalanceio_restante, dur)

    def duracao_transicao(self, base_s: float, *, calma: bool = False) -> float:
        """Calcula duração humanizada de transição com assimetria natural."""
        fator = self._rng.uniform(1.02, 1.28) if calma else self._rng.uniform(0.88, 1.20)
        return max(0.08, base_s * fator)

    def modulacao_respiracao(self, tempo: float) -> float:
        """Micro-variação lenta e aperiódica na cadência respiratória (±8%)."""
        return 1.0 + 0.055 * sin(tempo * 0.27) + 0.030 * sin(tempo * 0.61 + 1.4)
