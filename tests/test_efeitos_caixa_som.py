"""Testa os efeitos visuais da caixa de som."""

from types import SimpleNamespace

import pytest
from panda3d.core import NodePath, TextureStage, Vec3

from sejoga.musica.efeitos_caixa_som import SpeakerEffects


def test_slime_flows_then_clears_and_can_replay():
    effects = SpeakerEffects(NodePath("speaker"))
    stage = TextureStage.getDefault()
    effects.update(-0.01)
    assert all(node.isHidden() for node in effects.slime)
    effects.update(0.2)
    assert all(not node.isHidden() for node in effects.slime)
    splash = effects.slime[0].getTexOffset(stage)
    assert all(abs(node.getZ()) < 0.13 for node in effects.slime)
    effects.update(0.9)
    assert effects.slime[0].getTexOffset(stage).y < splash.y
    effects.update(2.5)
    assert all(node.isHidden() for node in effects.slime)
    effects.update(0.2)
    assert effects.slime[0].getTexOffset(stage) == splash


def test_palco_lanca_tres_caixas_e_assenta_no_chao(monkeypatch):  # noqa: PLR0915
    from sejoga.musica.caixa_som import FIM_ARREMESSOS_S, MusicSpeaker

    def medir_mascote(speaker):
        speaker.character_size = Vec3(1, 1, 1.2)
        speaker.floor_z = 0.1

    monkeypatch.setattr(MusicSpeaker, "_measure_character", medir_mascote)
    renderer = SimpleNamespace(
        model_anchor=NodePath("anchor"),
        model_np=NodePath("mascote"),
        showbase=SimpleNamespace(
            settings=SimpleNamespace(audio=SimpleNamespace(enabled=False))
        ),
    )
    palco = MusicSpeaker(renderer)
    arremessos = []
    for _ in range(round(FIM_ARREMESSOS_S * 60) + 5):
        palco.update(1 / 60, True, 0, 0)
        if palco.throw_index >= 0 and palco.throw_index not in arremessos:
            arremessos.append(palco.throw_index)
        for box in palco.boxes:
            if not box.isHidden():
                baixo, _ = box.find("mesh*").getTightBounds(palco.root)
                assert baixo.y >= 0.24 - 1e-5
                assert baixo.z >= palco.floor_z - 1e-5
    assert arremessos == [0, 1, 2]
    for box, ratio in zip(palco.boxes, (2, 1, 1), strict=True):
        assert not box.isHidden()
        low, high = box.find("mesh*").getTightBounds(palco.root)
        assert low.z == pytest.approx(palco.floor_z, abs=1e-6)
        assert high.z - low.z == pytest.approx(palco.character_size.z * ratio, rel=0.085)
    assert palco.jump_progress == 0
    assert palco.boxes[0].getH() % 360 == pytest.approx(180)
    palco.update(2, True, 0, 0)
    assert palco.jump_progress == 1

    caixa = palco.boxes[0]
    neutro = caixa.getSz()
    palco.update(1 / 60, True, 0, 1)
    assert caixa.getSz() < neutro
    low, high = caixa.find("mesh*").getTightBounds(palco.root)
    assert low.z == pytest.approx(palco.floor_z, abs=1e-6)
    assert palco.seat.z == pytest.approx(high.z, abs=1e-6)
    palco.update(1 / 60, True, 3.14159265, 1)
    assert caixa.getSz() == pytest.approx(neutro)
