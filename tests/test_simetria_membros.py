"""Simetria como contrato: o lado esquerdo é o espelho sagital do direito.

Lei única (``cinematica.espelhar_rotacao``): ``Rotation3 (x, y, z) → (x, -y, -z)``;
em posição, o punho esquerdo é o direito com ``x`` invertido. Gestos assimétricos
por definição ficam fora (``ASSIMETRIAS_INTENCIONAIS``).
"""

from __future__ import annotations

from math import radians

import pytest

from fk_bracos import punho
from sejoga.animacao.estados_delta import delta_dance
from sejoga.animacao.pose_repouso import REPOUSO, pose_repouso
from sejoga.animacao.poses_base import pose_idle, pose_sleep
from sejoga.nucleo.esqueleto import ALL_GROUPS, IdlePersonality, Rig, Rotation3

#: Gestos/estilos assimétricos por definição (não entram no contrato de espelho).
ASSIMETRIAS_INTENCIONAIS = frozenset(
    {
        "wave",
        "thumbs_up",
        "finger_gun",
        "hang_loose",
        "rock",
        "walk",
        "run",
        "street",
        "fighter",
        "rhythm",
        "stylish",
        "curious",
        "playful",
        "confident",
        "brc_stance",
        "vibing",
    }
)
#: Tolerância (u) da posição do punho espelhado.
TOLERANCIA_U = 1e-6
#: Instantes amostrados (s).
INSTANTES = tuple(i * 0.37 for i in range(40))


def _rig():
    repouso = {g: Rotation3() for g in ALL_GROUPS}

    return Rig(rest=dict(repouso), current=dict(repouso))


def _espelhado(pose):
    d, e = punho(pose, "right"), punho(pose, "left")

    return e == pytest.approx((-d[0], d[1], d[2]), abs=TOLERANCIA_U)


def test_repouso_e_espelhado():
    assert _espelhado(pose_repouso())


def test_sono_e_espelhado():
    rig = _rig()

    for t in INSTANTES:
        pose_sleep(rig, t)
        assert _espelhado(rig.pose()), t


@pytest.mark.parametrize(
    "delta_de", [lambda t: delta_dance(t, 0.8)]
)
def test_deltas_simetricos_preservam_o_espelho(delta_de):
    base = pose_repouso()

    for t in INSTANTES:
        delta = delta_de(t)
        pose = {
            g: Rotation3(
                r.x + delta.get(g, Rotation3()).x,
                r.y + delta.get(g, Rotation3()).y,
                r.z + delta.get(g, Rotation3()).z,
            )
            for g, r in base.items()
        }
        assert _espelhado(pose), t


@pytest.mark.parametrize(
    "personalidade",
    [p for p in IdlePersonality if p.value not in ASSIMETRIAS_INTENCIONAIS],
)
def test_torcao_dos_ombros_nao_vai_em_tesoura_no_idle(personalidade):
    """A torção (x) oscila no MESMO sentido nos dois ombros (lei do espelho)."""
    rig = _rig()
    correlacao = 0.0

    for t in INSTANTES:
        pose_idle(rig, t, personalidade)
        dx_dir = rig.current["right-arm"].x - radians(REPOUSO.BRACO_X)
        dx_esq = rig.current["left-arm"].x - radians(REPOUSO.BRACO_X)
        correlacao += dx_dir * dx_esq

    assert correlacao >= 0.0
