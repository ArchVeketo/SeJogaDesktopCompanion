"""Tronco: em pé (pivô da coluna) e pendurado (pivô de suspensão) no MESMO quadro.

Monta o ``FlexibleRig`` sobre o glTF real (Panda3D sem janela) e mede, no
referencial de autoria (nó raiz do asset: +X direita, +Y frente, +Z cima), para
onde a cabeça vai com pitch/roll. É a prova de que o tronco segue a convenção
de ``body_motion_tuning`` (pitch negativo = frente; roll positivo = direita) e
de que arraste e reação em pé não se contradizem.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace

import pytest

with contextlib.suppress(ImportError):
    import PySide6.QtWidgets  # noqa: F401  # Qt antes do Panda (ver test_cinematica_oraculo)

core = pytest.importorskip("panda3d.core", reason="Panda3D indisponível")
gltf = pytest.importorskip("gltf", reason="panda3d-gltf indisponível")

from sejoga.nucleo.assets import resolve_model  # noqa: E402
from sejoga.nucleo.flexible_rig import FlexibleRig, no_de_facing  # noqa: E402
from sejoga.nucleo.rig import ALL_GROUPS  # noqa: E402
from sejoga.render.renderer import Panda3DRenderer  # noqa: E402

#: Ângulo de teste (graus) e deslocamento mínimo (u) considerado movimento.
ANGULO = 10.0
MOVIMENTO_MINIMO = 0.01
#: Ponto alto da cabeça (u, local à cabeça) usado como "topo".
TOPO_LOCAL = (0.0, 0.0, 0.4)


@pytest.fixture()
def cena():
    core.loadPrcFileData("", "window-type none\naudio-library-name null")
    caminho = str(resolve_model())
    mundo = core.NodePath("mundo")
    suspensao = mundo.attachNewNode("suspension-pivot")
    modelo = core.NodePath(gltf.load_model(caminho))
    modelo.reparentTo(suspensao)
    contorno = core.NodePath(gltf.load_model(caminho))
    contorno.reparentTo(suspensao)
    nos = {g: modelo.find(f"**/{g}") for g in ALL_GROUPS if not modelo.find(f"**/{g}").isEmpty()}
    renderer = SimpleNamespace(
        model_np=modelo, outline_np=contorno, _rig_nodes=nos,
        _rig_base_pos={}, _rig_base_hpr={}, _rig_base_scale={}, _rig_base_mat={},
    )
    rig = FlexibleRig(renderer)

    return renderer, rig, suspensao


def _topo(renderer):
    referencia = no_de_facing(renderer.model_np)
    cabeca = renderer._rig_nodes["head"]
    p = referencia.getRelativePoint(cabeca, core.Point3(*TOPO_LOCAL))

    return p


def _delta_em_pe(renderer, rig, h, p, r):
    spine = rig.chains[0][0]
    base = _topo(renderer)
    spine.setHpr(h, p, r)
    fim = _topo(renderer)
    spine.setHpr(0, 0, 0)

    return fim - base


def _delta_pendurado(renderer, suspensao, h, p, r):
    mundo = suspensao.getParent()
    referencia = no_de_facing(renderer.model_np)
    cabeca = renderer._rig_nodes["head"]
    base = mundo.getRelativePoint(cabeca, core.Point3(*TOPO_LOCAL))
    rot = Panda3DRenderer._rotacao_no_quadro_de_autoria(renderer, h, p, r)
    suspensao.setMat(rot)
    fim = mundo.getRelativePoint(cabeca, core.Point3(*TOPO_LOCAL))
    suspensao.setMat(core.Mat4.identMat())

    # Deslocamento no mundo expresso nos eixos de autoria do REPOUSO.
    return referencia.getRelativeVector(mundo, fim - base)


def test_pitch_negativo_leva_o_topo_para_a_frente_em_pe_e_pendurado(cena):
    renderer, rig, suspensao = cena
    em_pe = _delta_em_pe(renderer, rig, 0, -ANGULO, 0)
    pendurado = _delta_pendurado(renderer, suspensao, 0, -ANGULO, 0)

    assert em_pe.y > MOVIMENTO_MINIMO
    assert pendurado.y > MOVIMENTO_MINIMO


def test_roll_positivo_tomba_o_topo_para_a_direita_nos_dois_caminhos(cena):
    renderer, rig, suspensao = cena
    em_pe = _delta_em_pe(renderer, rig, 0, 0, ANGULO)
    pendurado = _delta_pendurado(renderer, suspensao, 0, 0, ANGULO)

    assert em_pe.x > MOVIMENTO_MINIMO
    assert pendurado.x > MOVIMENTO_MINIMO


def test_pernas_e_pes_nao_seguem_o_pivo_da_coluna(cena):
    renderer, rig, _suspensao = cena
    referencia = no_de_facing(renderer.model_np)
    pes = renderer._rig_nodes["right-feet"]
    antes = pes.getPos(referencia)
    rig.chains[0][0].setHpr(ANGULO, -ANGULO, ANGULO)

    assert (pes.getPos(referencia) - antes).length() < 1e-6


def test_ombros_atrasam_para_o_mesmo_lado(cena):
    _renderer, rig, _suspensao = cena
    motion = SimpleNamespace(limb_swing=0.0, arm_lag=6.0)

    for _ in range(30):
        rig.update(1 / 60, motion)

    direito, esquerdo = rig.chains[0][2]

    assert direito.getR() == pytest.approx(esquerdo.getR())
    assert direito.getP() == pytest.approx(0.0)
