"""Testes do carregador de modelo — usam o asset real do repositório.

Objetivo: se alguém reexportar o Blockbench e quebrar nomes de grupos ou a
escala, o CI falha aqui em vez de o companion abrir torto.
"""

from __future__ import annotations

import pytest

from sejoga.animacao.poses_base import pose_idle, pose_thrown, pose_walk
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rig
from sejoga.nucleo.modelo import load_gltf_document, load_model
from sejoga.nucleo.recursos import model_dir, resolve_model


@pytest.fixture(scope="module")
def model():
    return load_model(resolve_model())


def test_counts(model):
    assert len(model.nodes) == 89
    assert model.mesh_count == 56
    assert model.vertex_count > 1000
    assert model.material_count >= 1
    assert model.texture_count >= 1


def test_no_skinning_and_no_baked_animations(model):
    # O rig blocky do Blockbench é por nó; a animação é procedural.
    assert model.is_skinned is False
    assert model.animation_names == ()


def test_all_rig_groups_present(model):
    names = model.named_set()
    missing = [g for g in ALL_GROUPS if g not in names]
    assert missing == [], f"grupos ausentes no modelo: {missing}"


def test_bounds_are_sane(model):
    b = model.bounds
    assert b.height > 0
    assert b.size[1] == pytest.approx(b.height)
    # modelo baixo-poly de desktop: unidades do Blockbench ~1.5-3
    assert 1.0 < b.height < 10.0
    # O modelo tem os pés ABAIXO da origem (y < 0), então ground_offset() é negativo.
    # Isso é esperado: o companion deve ser posicionado com o chão em y=0,
    # então o offset negativo indica quanto o modelo precisa subir.
    assert model.ground_offset() < 0


def test_find_is_exact(model):
    assert model.find("head") is not None
    assert model.find("Head") is None


def test_rig_from_model_and_pose(model):
    rig = Rig.from_model(model)
    assert rig.missing == ()
    assert "head" in rig.groups
    rig.set_rotation("head", y=10.0)
    assert rig.pose()["head"].y == pytest.approx(0.1745, rel=1e-3)
    rig.reset()
    assert rig.pose()["head"].y == 0.0
    with pytest.raises(KeyError):
        rig.set_rotation("nao-existe", y=1.0)


def test_pose_presets_do_not_raise(model):
    rig = Rig.from_model(model)
    for fn, args in ((pose_idle, (0.5,)), (pose_walk, (0.2,))):
        fn(rig, *args)
    pose_thrown(rig)

@pytest.mark.parametrize(
    "arquivo",
    sorted(p for p in model_dir().rglob("*") if p.suffix.lower() in {".gltf", ".glb"}),
    ids=lambda p: p.name,
)
def test_modelos_usam_pintura_pixel_com_uv_e_amostragem_nearest(arquivo):
    doc = load_gltf_document(arquivo)
    for malha in doc["meshes"]:
        for primitiva in malha["primitives"]:
            material = doc["materials"][primitiva["material"]]
            pintura = material["pbrMetallicRoughness"]["baseColorTexture"]
            assert f"TEXCOORD_{pintura.get('texCoord', 0)}" in primitiva["attributes"]
            textura = doc["textures"][pintura["index"]]
            assert doc["images"][textura["source"]]
            sampler = doc["samplers"][textura["sampler"]]
            assert sampler["minFilter"] == sampler["magFilter"] == 9728
