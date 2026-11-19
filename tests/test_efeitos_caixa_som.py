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


@pytest.mark.parametrize(("estilo", "ratios"), [("palco", (2, 1, 1)), ("radio", (0.38,))])
def test_caixas_do_palco_ou_radio_assentam_no_chao(monkeypatch, estilo, ratios):  # noqa: PLR0915
    from sejoga.musica.caixa_som import MusicSpeaker

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
    palco = MusicSpeaker(renderer, estilo)
    arremessos = []
    for _ in range(round(palco.end_throws * 60) + 5):
        palco.update(1 / 60, True, 0, 0)
        if palco.throw_index >= 0 and palco.throw_index not in arremessos:
            arremessos.append(palco.throw_index)
        for box in palco.boxes:
            if not box.isHidden():
                baixo, _ = box.find("mesh*").getTightBounds(palco.root)
                assert baixo.y >= 0.24 - 1e-5
                assert baixo.z >= palco.floor_z - 1e-5
    assert arremessos == list(range(len(ratios)))
    for box, ratio in zip(palco.boxes, ratios, strict=True):
        assert not box.isHidden()
        low, high = box.find("mesh*").getTightBounds(palco.root)
        assert low.z == pytest.approx(palco.floor_z, abs=1e-6)
        assert high.z - low.z == pytest.approx(palco.character_size.z * ratio, rel=0.085)
        if palco.compact:
            assert high.x - low.x > high.z - low.z
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
    if not palco.compact:
        assert palco.seat.z == pytest.approx(high.z, abs=1e-6)
    palco.update(1 / 60, True, 3.14159265, 1)
    assert caixa.getSz() == pytest.approx(neutro)


def test_palco_fica_fixo_no_desktop_quando_mascote_e_canvas_se_movem():
    from sejoga.musica.caixa_som import MusicSpeaker

    palco = MusicSpeaker.__new__(MusicSpeaker)
    cena = NodePath("cena")
    mascote = cena.attachNewNode("mascote")
    palco.root = cena.attachNewNode("palco")
    app = SimpleNamespace(render=cena, _mascot_screen=(500, 480), _canvas_origin=(0, 0))
    palco.renderer = SimpleNamespace(
        showbase=app, model_np=mascote, model_anchor=mascote, width=1000,
        height=1000, _view_width=10, _view_height=10, _view_target_z=0,
    )
    palco._stage_world_anchor = palco._stage_screen_anchor = palco._stage_scale = None
    palco._atualizar_ancora_palco()
    antes = palco.root.getPos()
    app._mascot_screen = (750, 470)
    mascote.setX(2.5)
    palco._atualizar_ancora_palco()
    assert palco.root.getPos() == antes
    app._canvas_origin = (100, 80)
    palco._atualizar_ancora_palco()
    assert palco.root.getX() == pytest.approx(antes.x - 1)
    assert palco.root.getZ() == pytest.approx(antes.z + 0.8)
