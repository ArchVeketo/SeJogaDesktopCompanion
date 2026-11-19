"""Amostra pistas de animação com interpolação quíntica e curvas configuráveis."""

from collections.abc import Sequence
from itertools import pairwise

Trio = tuple[float, float, float]
Chaves = tuple[tuple[float, Trio], ...]

CURVAS_SUPORTADAS: tuple[str, ...] = (
    "quintic",
    "linear",
    "ease_in",
    "ease_out",
    "ease_in_out",
    "step",
)


def suavizar_quintico(fracao: float) -> float:
    """Interpola entre zero e um com velocidade e aceleração nulas nas pontas."""
    fracao = max(0.0, min(1.0, fracao))
    return fracao * fracao * fracao * (fracao * (fracao * 6 - 15) + 10)


def suavizar_curva(fracao: float, curva: str = "quintic") -> float:
    """Aplica o perfil de interpolação selecionado em ``[0, 1]``."""
    u = max(0.0, min(1.0, fracao))
    if curva == "linear":
        return u
    if curva == "step":
        return 1.0 if u >= 1.0 else 0.0
    if curva == "ease_in":
        return u * u * u
    if curva == "ease_out":
        inv = 1.0 - u
        return 1.0 - inv * inv * inv
    if curva == "ease_in_out":
        return u * u * (3.0 - 2.0 * u)
    return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


def amostrar_pista(
    chaves: Chaves,
    tempo: float,
    *,
    curvas: Sequence[str] | None = None,
) -> Trio:
    """Amostra uma pista ordenada, mantendo as poses fora do intervalo."""
    if not chaves:
        return 0.0, 0.0, 0.0
    if tempo <= chaves[0][0]:
        return chaves[0][1]
    for indice, ((inicio, origem), (fim, destino)) in enumerate(pairwise(chaves)):
        if tempo <= fim:
            curva = (
                curvas[indice]
                if curvas is not None and indice < len(curvas)
                else "quintic"
            )
            dur = fim - inicio
            fracao = (tempo - inicio) / dur if dur > 1e-9 else 1.0
            fator = suavizar_curva(fracao, curva)
            x, y, z = (
                a + (b - a) * fator for a, b in zip(origem, destino, strict=True)
            )
            return x, y, z
    return chaves[-1][1]
