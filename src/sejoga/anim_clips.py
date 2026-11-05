"""Clipes de animação autorais como DADOS, amostrados em graus.

Mesma filosofia de ``idle_clips``: keyframes com easing quíntico (velocidade e
aceleração contínuas nos holds), nenhum clipe exportado de ferramenta externa.
Aqui ficam os clipes cíclicos de locomoção. O ``walk`` deixa de ser senóide
crua e passa a ser um ciclo de passada descrito por keyframes, preservando a
alternância contrabalançada dos braços ao longo do ciclo.
"""

from __future__ import annotations

from dataclasses import dataclass

from .idle_clips import sample_track
from .rig import Rotation3


@dataclass(frozen=True)
class ClipeAnim:
    """Clipe cíclico: duração e tracks grupo->keyframes (tempo, (x, y, z))."""

    duracao: float
    tracks: dict[str, tuple[tuple[float, tuple[float, float, float]], ...]]


def _ciclo(*keys: tuple[float, tuple[float, float, float]]
           ) -> tuple[tuple[float, tuple[float, float, float]], ...]:
    """Garante que o ciclo feche no mesmo valor com que começou (sem salto)."""
    if keys[0][1] != keys[-1][1]:
        raise ValueError("clipe cíclico deve começar e terminar no mesmo valor")
    return keys


# Ciclo de passada normalizado em t=0..1. Braços contrabalançam as pernas: no
# meio do ciclo o braço direito está atrás e o esquerdo à frente, invertendo-se
# na volta. Antebraços e dobradiça do tronco acompanham a passada.
_PASSADA = {
    "right-arm": _ciclo((0.0, (0, 0, 58)), (0.25, (-16, 0, 46)),
                        (0.5, (0, 0, 58)), (0.75, (16, 0, 70)), (1.0, (0, 0, 58))),
    "left-arm": _ciclo((0.0, (0, 0, -58)), (0.25, (16, 0, -70)),
                       (0.5, (0, 0, -58)), (0.75, (-16, 0, -46)), (1.0, (0, 0, -58))),
    "ant-arm": _ciclo((0.0, (0, 0, -22)), (0.25, (10.4, 0, -12)),
                      (0.5, (0, 0, -22)), (0.75, (-10.4, 0, -32)), (1.0, (0, 0, -22))),
    "ant-arm2": _ciclo((0.0, (0, 0, 22)), (0.25, (-10.4, 0, 32)),
                       (0.5, (0, 0, 22)), (0.75, (10.4, 0, 12)), (1.0, (0, 0, 22))),
    "body": _ciclo((0.0, (1.5, 0, 0)), (0.25, (1.5, 0, 2)),
                   (0.5, (1.5, 0, 0)), (0.75, (1.5, 0, -2)), (1.0, (1.5, 0, 0))),
    "head": _ciclo((0.0, (0, 0, 0)), (0.25, (0, -3.5, 0)),
                   (0.5, (0, 0, 0)), (0.75, (0, 3.5, 0)), (1.0, (0, 0, 0))),
}

# Variante corrida: mesma estrutura, amplitudes maiores (braços e tronco).
_CORRIDA = {
    "right-arm": _ciclo((0.0, (0, 0, 50)), (0.25, (-24, 0, 32)),
                        (0.5, (0, 0, 50)), (0.75, (24, 0, 68)), (1.0, (0, 0, 50))),
    "left-arm": _ciclo((0.0, (0, 0, -50)), (0.25, (24, 0, -68)),
                       (0.5, (0, 0, -50)), (0.75, (-24, 0, -32)), (1.0, (0, 0, -50))),
    "ant-arm": _ciclo((0.0, (0, 0, -22)), (0.25, (15.6, 0, -12)),
                      (0.5, (0, 0, -22)), (0.75, (-15.6, 0, -32)), (1.0, (0, 0, -22))),
    "ant-arm2": _ciclo((0.0, (0, 0, 22)), (0.25, (-15.6, 0, 32)),
                       (0.5, (0, 0, 22)), (0.75, (15.6, 0, 12)), (1.0, (0, 0, 22))),
    "body": _ciclo((0.0, (4.0, 0, 0)), (0.25, (4.0, 0, 4)),
                   (0.5, (4.0, 0, 0)), (0.75, (4.0, 0, -4)), (1.0, (4.0, 0, 0))),
    "head": _ciclo((0.0, (5.0, 0, 0)), (0.25, (5.0, -3.5, 0)),
                   (0.5, (5.0, 0, 0)), (0.75, (5.0, 3.5, 0)), (1.0, (5.0, 0, 0))),
}

CLIPES = {
    "walk": ClipeAnim(1.0, _PASSADA),
    "run": ClipeAnim(1.0, _CORRIDA),
}


def amostrar_clipe(nome: str, t: float) -> dict[str, tuple[float, float, float]]:
    """Amostra um clipe cíclico no tempo normalizado ``t`` (ciclos)."""
    clipe = CLIPES[nome]
    local = (t % clipe.duracao)
    pose: dict[str, tuple[float, float, float]] = {}
    for grupo, keys in clipe.tracks.items():
        pose[grupo] = sample_track(keys, local)
    return pose


def amostrar_clipe_rotacoes(nome: str, t: float) -> dict[str, Rotation3]:
    """Igual a :func:`amostrar_clipe`, porém devolvendo ``Rotation3`` em graus."""
    return {grupo: Rotation3(*valor) for grupo, valor in amostrar_clipe(nome, t).items()}
