"""Amostra pistas de animação com interpolação quíntica."""

from itertools import pairwise

Trio = tuple[float, float, float]
Chaves = tuple[tuple[float, Trio], ...]


def suavizar_quintico(fracao: float) -> float:
    """Interpola entre zero e um com velocidade e aceleração nulas nas pontas."""
    fracao = max(0.0, min(1.0, fracao))
    return fracao * fracao * fracao * (fracao * (fracao * 6 - 15) + 10)


def amostrar_pista(chaves: Chaves, tempo: float) -> Trio:
    """Amostra uma pista ordenada, mantendo as poses fora do intervalo."""
    if tempo <= chaves[0][0]:
        return chaves[0][1]
    for (inicio, origem), (fim, destino) in pairwise(chaves):
        if tempo <= fim:
            fator = suavizar_quintico((tempo - inicio) / (fim - inicio))
            x, y, z = (
                a + (b - a) * fator for a, b in zip(origem, destino, strict=True)
            )
            return x, y, z
    return chaves[-1][1]
