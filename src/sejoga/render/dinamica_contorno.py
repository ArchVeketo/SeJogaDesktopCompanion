"""Matemática do contorno "vivo", independente do engine.

Dá vida ao inverted hull do mascote sem tocar no render: a espessura base
(em unidades de modelo) ganha uma leve respiração acionada pela compressão do
tórax (``body_motion.snapshot.compression``), suavizada por um ``Spring``.

Mantém a fronteira engine: nada de Panda3D/Qt/Win32 aqui.
"""

from __future__ import annotations

from sejoga.animacao.movimento_corpo import Spring, clamp

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

    Encapsula um ``Spring`` (reusado de ``movimento_corpo``) para que a espessura não
    salte entre frames. ``reset`` fixa o estado em repouso quando as settings são
    (re)aplicadas; ``update`` avança o alvo calculado por ``espessura_efetiva``.
    """

    def __init__(self, frequency: float = 1.6, damping: float = 0.65) -> None:
        """Cria a mola do contorno com frequência e amortecimento dados."""
        self._spring = Spring(frequency, damping)

    def reset(self, base: float) -> None:
        """Fixa a espessura em ``base`` (estado de repouso), zerando a inércia."""
        valor = max(0.0, base)
        self._spring.value = valor
        self._spring.velocity = 0.0

    def update(
        self, dt: float, base: float, compression: float, intensidade: float
    ) -> float:
        """Avança a respiração e devolve a espessura suavizada do frame."""
        alvo = espessura_efetiva(base, compression, intensidade)
        valor = self._spring.update(dt, alvo)
        return max(0.0, valor)


def cor_contorno_viva(
    base_rgb: tuple[float, float, float],
    estado: str,
    *,
    bass: float = 0.0,
    choque: bool = False,
    carinho: bool = False,
    impacto: float = 0.0,
    album_rgb: tuple[float, float, float] | None = None,
) -> tuple[float, float, float]:
    """Tinta viva Cyber-Ink (v2.0): modula sutilmente a cor do contorno conforme o momento.

    Sempre parte da cor configurada pelo usuário (``base_rgb``), aceita sotaque da
    capa do álbum em execução e evita a zona de colorkey magenta.
    """
    r, g, b = base_rgb
    alvo = base_rgb
    peso = 0.0
    if choque:
        alvo = (0.30, 0.96, 1.0)  # ciano elétrico
        peso = 0.72
    elif impacto > 0.15 or estado in ("hit", "teimosia"):
        alvo = (1.0, 0.34, 0.24)  # coral de impacto/atitude
        peso = min(0.75, 0.38 + impacto * 0.45)
    elif carinho or estado in ("pet", "celebrate"):
        alvo = (1.0, 0.84, 0.34)  # brilho dourado caloroso
        peso = 0.55 if estado == "celebrate" else 0.42
    elif album_rgb is not None and (estado == "dance" or bass > 0.12):
        alvo = album_rgb
        peso = min(0.65, 0.24 + max(0.0, bass) * 0.48)
    elif estado == "dance" and bass > 0.22:
        alvo = (0.28, 0.94, 0.92)  # pulso neon no grave
        peso = min(0.62, (bass - 0.20) * 0.78)

    if peso <= 1e-4:
        return base_rgb
    nr = r + (alvo[0] - r) * peso
    ng = g + (alvo[1] - g) * peso
    nb = b + (alvo[2] - b) * peso
    if nr > 0.68 and nb > 0.68 and ng < 0.28:
        ng = 0.30
    return (max(0.0, min(1.0, nr)), max(0.0, min(1.0, ng)), max(0.0, min(1.0, nb)))
