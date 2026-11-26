"""Amostra pistas de animação com curvas de ataque, overshoot e splines Catmull-Rom C1."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise
from math import pi, sin

Trio = tuple[float, float, float]
Chaves = tuple[tuple[float, Trio], ...]

CURVAS_SUPORTADAS: tuple[str, ...] = (
    "quintic",
    "linear",
    "ease_in",
    "ease_out",
    "ease_in_out",
    "step",
    "catmull",
    "snap_out",
    "anticipate",
    "overshoot",
)


def suavizar_quintico(fracao: float) -> float:
    """Interpola entre zero e um com velocidade e aceleração nulas nas pontas."""
    fracao = max(0.0, min(1.0, fracao))
    return fracao * fracao * fracao * (fracao * (fracao * 6.0 - 15.0) + 10.0)


def _curva_anticipate(u: float) -> float:
    if u < 0.28:
        return -0.14 * sin((u / 0.28) * pi)
    t = (u - 0.28) / 0.72
    return 1.0 - (1.0 - t) ** 3


def _curva_overshoot(u: float) -> float:
    inv = u - 1.0
    return 1.0 + 2.15 * inv * inv * inv + 1.15 * inv * inv


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
    if curva == "snap_out":
        inv = 1.0 - u
        return 1.0 - inv * inv * inv * inv
    if curva == "anticipate":
        return _curva_anticipate(u)
    if curva == "overshoot":
        return _curva_overshoot(u)
    if curva == "ease_in_out":
        return u * u * (3.0 - 2.0 * u)
    return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


def _catmull_eixo(
    p0: float, p1: float, p2: float, p3: float, span0: float, span1: float, dt_seg: float,
    h00: float, h10: float, h01: float, h11: float,
) -> float:
    dv = p2 - p1
    if abs(dv) < 1e-6:
        return p1
    m1 = 0.0 if (p1 - p0) * dv <= 0.0 else ((p2 - p0) / span0) * dt_seg
    m2 = 0.0 if (p3 - p2) * dv <= 0.0 else ((p3 - p1) / span1) * dt_seg
    return h00 * p1 + h10 * m1 + h01 * p2 + h11 * m2


def _interpolar_catmull_segmento(
    chaves: Chaves, indice: int, u: float
) -> Trio:
    t1, p1 = chaves[indice]
    t2, p2 = chaves[indice + 1]
    dt_seg = max(1e-6, t2 - t1)
    t0, p0 = chaves[indice - 1] if indice > 0 else (t1 - dt_seg, tuple(2.0 * p1[k] - p2[k] for k in range(3)))
    t3, p3 = chaves[indice + 2] if indice + 2 < len(chaves) else (t2 + dt_seg, tuple(2.0 * p2[k] - p1[k] for k in range(3)))
    span0, span1 = max(1e-6, t2 - t0), max(1e-6, t3 - t1)
    u2, u3 = u * u, u * u * u
    h00, h10, h01, h11 = 2.0 * u3 - 3.0 * u2 + 1.0, u3 - 2.0 * u2 + u, -2.0 * u3 + 3.0 * u2, u3 - u2
    return (
        _catmull_eixo(p0[0], p1[0], p2[0], p3[0], span0, span1, dt_seg, h00, h10, h01, h11),
        _catmull_eixo(p0[1], p1[1], p2[1], p3[1], span0, span1, dt_seg, h00, h10, h01, h11),
        _catmull_eixo(p0[2], p1[2], p2[2], p3[2], span0, span1, dt_seg, h00, h10, h01, h11),
    )


def amostrar_pista_continua(
    chaves: Chaves,
    tempo: float,
    *,
    curvas: Sequence[str] | None = None,
    padrao: str = "catmull",
) -> Trio:
    """Amostra pista contínua usando C1 Catmull-Rom por padrão ou curva explícita."""
    if not chaves:
        return 0.0, 0.0, 0.0
    if tempo <= chaves[0][0]:
        return chaves[0][1]
    for indice, ((inicio, origem), (fim, destino)) in enumerate(pairwise(chaves)):
        if tempo <= fim:
            curva = (
                curvas[indice]
                if curvas is not None and indice < len(curvas)
                else padrao
            )
            dur = fim - inicio
            fracao = (tempo - inicio) / dur if dur > 1e-9 else 1.0
            if curva == "catmull" and len(chaves) >= 3:
                return _interpolar_catmull_segmento(chaves, indice, max(0.0, min(1.0, fracao)))
            fator = suavizar_curva(fracao, curva)
            x, y, z = (
                a + (b - a) * fator for a, b in zip(origem, destino, strict=True)
            )
            return x, y, z
    return chaves[-1][1]


def amostrar_pista(
    chaves: Chaves,
    tempo: float,
    *,
    curvas: Sequence[str] | None = None,
) -> Trio:
    """Amostra uma pista ordenada, mantendo as poses fora do intervalo."""
    return amostrar_pista_continua(chaves, tempo, curvas=curvas, padrao="quintic")
