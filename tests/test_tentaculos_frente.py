"""Regressão: tentáculos saem pela frente da cabeça, não pelo espaço do modelo."""

import random

import pytest
from panda3d.core import NodePath, Vec3

from sejoga.nucleo.esqueleto import ALL_GROUPS, IdlePersonality, Rig, Rotation3
from sejoga.tentaculos.sistema_tentaculos import TentacleDirector, TentaclePool

ESCALA = 0.004
QUADROS = 300
ALCANCE_MINIMO_FRENTE = 0.15  # unidades do modelo à frente da âncora (medido: .202)


@pytest.mark.parametrize("frente", [Vec3(0, 1, 0), Vec3(0, -1, 0)])
def test_pontas_passam_da_porta_na_frente_da_cabeca(frente):
    rig = Rig(rest={name: Rotation3() for name in ALL_GROUPS})
    raiz = NodePath("raiz")
    pool = TentaclePool(
        rig, raiz, raiz, [Vec3(0)], rng=random.Random(1), unit_scale=ESCALA
    )
    diretor = TentacleDirector(pool, rig, raiz, raiz, None, rng=random.Random(2))

    for tentaculo in pool.tentacles:
        tentaculo.reference_front = Vec3(frente)
    diretor.trigger_curious()
    for _ in range(QUADROS):
        diretor.update(1 / 60, 0, IdlePersonality.CALM)

    ativos = [t for t in pool.tentacles if t.target is not None]
    assert ativos
    for tentaculo in ativos:
        assert (tentaculo.visible_tip() - tentaculo.anchor).dot(
            frente
        ) > ALCANCE_MINIMO_FRENTE
