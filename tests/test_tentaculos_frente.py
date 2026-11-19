"""Regressão: tentáculos saem pela frente da cabeça, não pelo espaço do modelo."""

import random

import pytest
from panda3d.core import NodePath, Vec3

from sejoga.nucleo.esqueleto import ALL_GROUPS, IdlePersonality, Rig, Rotation3
from sejoga.tentaculos.sistema_tentaculos import TentacleDirector, TentaclePool

ESCALA = 0.004
QUADROS = 300
ALCANCE_MINIMO_FRENTE = 0.15  # unidades do modelo à frente da âncora (medido: .202)


def test_painel_que_tampa_a_boca_e_separado_da_geometria():
    import gltf

    from sejoga.nucleo.recursos import resolve_model
    from sejoga.render.renderizador import Panda3DRenderer

    raiz = NodePath(gltf.load_model(str(resolve_model())))
    gabinete = raiz.find("**/Armario/+GeomNode")
    total = gabinete.node().getGeom(0).getPrimitive(0).getNumPrimitives()
    Panda3DRenderer._separar_painel_armario(raiz)
    painel = gabinete.find("moldura-armario")
    assert painel.node().getGeom(0).getPrimitive(0).getNumPrimitives() == 8
    assert gabinete.node().getGeom(0).getPrimitive(0).getNumPrimitives() == total - 2


def test_corredor_fica_na_boca_quando_a_folha_gira():
    rig = Rig(rest={name: Rotation3() for name in ALL_GROUPS})
    raiz = NodePath("raiz")
    head = raiz.attachNewNode("head")
    head.setH(40)
    door = head.attachNewNode("door")
    door.setPos(-0.125, 0.15625, 0.1875)
    pool = TentaclePool(rig, raiz, raiz, [Vec3(0)])
    diretor = TentacleDirector(pool, rig, raiz, raiz, door)
    diretor._door_current = 60
    boca, fora = diretor._corredor_porta_aberta()
    door.setH(95)

    assert diretor._corredor_porta_aberta() == (boca, fora)
    assert tuple(head.getRelativePoint(raiz, boca)) == pytest.approx((0, 0.15625, 0.1225), abs=1e-7)
    assert head.getRelativePoint(raiz, fora).y > 0.3


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
        diretor.update(1 / 60, IdlePersonality.CALM)

    ativos = [t for t in pool.tentacles if t.target is not None]
    assert ativos
    for tentaculo in ativos:
        assert (tentaculo.visible_tip() - tentaculo.anchor).dot(
            frente
        ) > ALCANCE_MINIMO_FRENTE


def test_fundo_interno_usa_superficie_original_sem_ampliar_cabeca():
    import gltf
    from panda3d.core import GeomVertexReader, TextureAttrib
    from sejoga.nucleo.recursos import resolve_model
    from sejoga.render.renderizador import Panda3DRenderer

    raiz = NodePath(gltf.load_model(str(resolve_model())))
    antes = raiz.getTightBounds()
    Panda3DRenderer._separar_painel_armario(raiz)
    Panda3DRenderer._escurecer_fundo_interno(raiz)
    assert raiz.getTightBounds() == antes
    fundo = raiz.find("**/fundo-interno-armario")
    geom = fundo.node().getGeom(0)
    assert fundo.node().getGeomState(0).hasAttrib(TextureAttrib)
    prim = geom.getPrimitive(0)
    assert prim.getNumPrimitives() > 0
    reader = GeomVertexReader(geom.getVertexData(), "vertex")
    normais = GeomVertexReader(geom.getVertexData(), "normal")
    for i in range(0, prim.getNumVertices(), 3):
        pontos = []
        for j in range(i, i + 3):
            reader.setRow(prim.getVertex(j))
            pontos.append(raiz.find("**/head").getRelativePoint(fundo, reader.getData3()))
        normal = (pontos[1] - pontos[0]).cross(pontos[2] - pontos[0])
        normais.setRow(prim.getVertex(i))
        normal_luz = raiz.find("**/head").getRelativeVector(fundo, normais.getData3())
        assert normal.dot(normal_luz) > 0
        centro = (pontos[0] + pontos[1] + pontos[2]) / 3
        assert normal.dot(Vec3(0, 0, .17) - centro) > 0
    assert not fundo.getTwoSided()
