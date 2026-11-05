"""Matemática do contorno "vivo", independente do engine.

Dá vida ao inverted hull do mascote sem tocar no render: a espessura base
(em unidades de modelo) ganha uma leve respiração acionada pela compressão do
tórax (``body_motion.snapshot.compression``), suavizada por um ``Spring``.

Mantém a fronteira engine: nada de Panda3D/Qt/Win32 aqui.
"""

from __future__ import annotations

from .body_motion import Spring, clamp

# Faixa conhecida de ``compression`` publicada por BodyMotion.snapshot.
COMPRESSION_MIN = -0.12
COMPRESSION_MAX = 0.20

# Variação máxima da espessura, como fração da base, quando a intensidade é 1.
# A respiração soma à espessura base; mantida sutil para não deformar a silhueta.
RESPIRACAO_GANHO_MAXIMO = 0.35


def espessura_efetiva(base: float, compression: float, intensidade: float) -> float:
    """Espessura efetiva do frame a partir da base e da respiração do corpo.

    ``base`` é a espessura de repouso em unidades de modelo. ``compression`` é o
    sinal de respiração/squash do tórax (faixa ``[-0.12, 0.20]``). ``intensidade``
    (``0..1``) escala a respiração; ``0`` devolve exatamente a base (comportamento
    estável anterior). O resultado nunca é negativo.
    """
    if intensidade <= 0.0:
        return max(0.0, base)

    intensidade = clamp(intensidade, 0.0, 1.0)
    compression = clamp(compression, COMPRESSION_MIN, COMPRESSION_MAX)
    # Normaliza a compressão para [-1, 1] ao redor do repouso (0), usando o lado
    # correspondente da faixa para que ±extremos cheguem a ±1.
    if compression >= 0.0:
        normalizado = compression / COMPRESSION_MAX
    else:
        normalizado = compression / -COMPRESSION_MIN
    ganho = 1.0 + normalizado * RESPIRACAO_GANHO_MAXIMO * intensidade
    return max(0.0, base * ganho)


class RespiracaoContorno:
    """Suaviza a espessura alvo do contorno ao longo do tempo.

    Encapsula um ``Spring`` (reusado de ``body_motion``) para que a espessura não
    salte entre frames. ``reset`` fixa o estado em repouso quando as settings são
    (re)aplicadas; ``update`` avança o alvo calculado por ``espessura_efetiva``.
    """

    def __init__(self, frequency: float = 1.6, damping: float = 0.65) -> None:
        self._spring = Spring(frequency, damping)

    def reset(self, base: float) -> None:
        """Fixa a espessura em ``base`` (estado de repouso), zerando a inércia."""
        valor = max(0.0, base)
        self._spring.value = valor
        self._spring.velocity = 0.0

    def update(self, dt: float, base: float, compression: float, intensidade: float) -> float:
        """Avança a respiração e devolve a espessura suavizada do frame."""
        alvo = espessura_efetiva(base, compression, intensidade)
        valor = self._spring.update(dt, alvo)
        return max(0.0, valor)
