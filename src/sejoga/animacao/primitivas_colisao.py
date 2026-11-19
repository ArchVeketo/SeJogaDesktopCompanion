"""Primitivas de interseção para o anti-atravessamento dos braços.

Cápsula (tubo de um membro) e caixa orientada (volume do corpo), com a
profundidade de penetração cápsula-caixa e cápsula-cápsula, em unidades do
modelo (``u``). Python puro: só ``math`` e ``dataclasses``.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

Vetor3 = tuple[float, float, float]

#: Pontos amostrados ao longo do eixo da cápsula em ``penetracao_capsula_caixa``.
AMOSTRAS_CAPSULA_CAIXA: int = 12


@dataclass(frozen=True)
class Capsula:
    """Segmento ``a``->``b`` com raio: o "tubo" de um membro."""

    a: Vetor3
    b: Vetor3
    raio: float


@dataclass(frozen=True)
class CaixaOrientada:
    """Caixa centrada em ``centro``, com três ``eixos`` ortonormais e meias-dimensões."""

    centro: Vetor3
    eixos: tuple[Vetor3, Vetor3, Vetor3]
    meias_dim: Vetor3


def _sub(a: Vetor3, b: Vetor3) -> Vetor3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _soma(a: Vetor3, b: Vetor3) -> Vetor3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _escala(v: Vetor3, k: float) -> Vetor3:
    return (v[0] * k, v[1] * k, v[2] * k)


def _dot(a: Vetor3, b: Vetor3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norma(v: Vetor3) -> float:
    return sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _clamp(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


def dist_segmento_segmento(p1: Vetor3, q1: Vetor3, p2: Vetor3, q2: Vetor3) -> float:  # noqa: PLR0915  # TODO convenção: fatiar sem prova visual na GPU arrisca mudar o movimento; lote próprio com caracterização
    """Menor distância entre os segmentos ``[p1,q1]`` e ``[p2,q2]``.

    Algoritmo clássico (Ericson, *Real-Time Collision Detection*). Trata
    segmentos degenerados (ponto) e paralelos sem divisão por zero.
    """
    d1 = _sub(q1, p1)
    d2 = _sub(q2, p2)
    r = _sub(p1, p2)

    a = _dot(d1, d1)
    e = _dot(d2, d2)
    f = _dot(d2, r)

    epsilon = 1e-12

    if a <= epsilon and e <= epsilon:
        return _norma(_sub(p1, p2))

    if a <= epsilon:
        s = 0.0
        t = _clamp(f / e, 0.0, 1.0)
    else:
        c = _dot(d1, r)

        if e <= epsilon:
            t = 0.0
            s = _clamp(-c / a, 0.0, 1.0)
        else:
            b = _dot(d1, d2)
            denominador = a * e - b * b

            # Paralelos (denominador ~0): escolhe s=0 e resolve t.
            s = (
                _clamp((b * f - c * e) / denominador, 0.0, 1.0)
                if denominador > epsilon
                else 0.0
            )

            t = (b * s + f) / e

            # Se t saiu de [0,1], prende e recalcula s para o t preso.
            if t < 0.0:
                t = 0.0
                s = _clamp(-c / a, 0.0, 1.0)
            elif t > 1.0:
                t = 1.0
                s = _clamp((b - c) / a, 0.0, 1.0)

    ponto1 = _soma(p1, _escala(d1, s))
    ponto2 = _soma(p2, _escala(d2, t))

    return _norma(_sub(ponto1, ponto2))


def dist_ponto_caixa(ponto: Vetor3, caixa: CaixaOrientada) -> float:
    """Distância ASSINADA de ``ponto`` à caixa (negativa DENTRO, positiva fora)."""
    cx, cy, cz = caixa.centro
    rx = ponto[0] - cx
    ry = ponto[1] - cy
    rz = ponto[2] - cz
    ex, ey, ez = caixa.eixos
    hx, hy, hz = caixa.meias_dim

    lx = rx * ex[0] + ry * ex[1] + rz * ex[2]
    ly = rx * ey[0] + ry * ey[1] + rz * ey[2]
    lz = rx * ez[0] + ry * ez[1] + rz * ez[2]

    dx = abs(lx) - hx
    dy = abs(ly) - hy
    dz = abs(lz) - hz

    if dx <= 0.0 and dy <= 0.0 and dz <= 0.0:
        menor_folga = -dx
        if -dy < menor_folga:
            menor_folga = -dy
        if -dz < menor_folga:
            menor_folga = -dz
        return -menor_folga

    fora_quadrado = 0.0
    if dx > 0.0:
        fora_quadrado += dx * dx
    if dy > 0.0:
        fora_quadrado += dy * dy
    if dz > 0.0:
        fora_quadrado += dz * dz
    return sqrt(fora_quadrado)


def penetracao_capsula_capsula(ca: Capsula, cb: Capsula) -> float:
    """Profundidade de interpenetração entre duas cápsulas (0.0 se separadas)."""
    distancia = dist_segmento_segmento(ca.a, ca.b, cb.a, cb.b)

    return max(0.0, (ca.raio + cb.raio) - distancia)


def _profundidade_ponto_caixa(
    px: float, py: float, pz: float, hx: float, hy: float, hz: float, raio: float
) -> float:
    ox, oy, oz = abs(px) - hx, abs(py) - hy, abs(pz) - hz
    if ox <= 0.0 and oy <= 0.0 and oz <= 0.0:
        return raio + min(-ox, -oy, -oz)
    fora = max(0.0, ox) ** 2 + max(0.0, oy) ** 2 + max(0.0, oz) ** 2
    return raio - sqrt(fora)


def penetracao_capsula_caixa(cap: Capsula, caixa: CaixaOrientada) -> float:
    """Profundidade de interpenetração entre cápsula e caixa (0.0 se separadas).

    Amostra ``AMOSTRAS_CAPSULA_CAIXA`` pontos ao longo do eixo da cápsula e
    devolve a MAIOR ``raio - dist_ponto_caixa``.
    """
    passos = max(2, AMOSTRAS_CAPSULA_CAIXA)
    ax, ay, az = cap.a
    bx, by, bz = cap.b
    dx, dy, dz = bx - ax, by - ay, bz - az
    inv = 1.0 / (passos - 1)
    cx, cy, cz = caixa.centro
    ex, ey, ez = caixa.eixos
    hx, hy, hz = caixa.meias_dim
    maior = 0.0

    for i in range(passos):
        fracao = i * inv
        rx = ax + dx * fracao - cx
        ry = ay + dy * fracao - cy
        rz = az + dz * fracao - cz
        px = rx * ex[0] + ry * ex[1] + rz * ex[2]
        py = rx * ey[0] + ry * ey[1] + rz * ey[2]
        pz = rx * ez[0] + ry * ez[1] + rz * ez[2]
        maior = max(maior, _profundidade_ponto_caixa(px, py, pz, hx, hy, hz, cap.raio))

    return maior
