from panda3d.core import NodePath

from sejoga.musica.speaker_effects import SpeakerEffects


def test_slime_flows_then_clears_and_can_replay():
    effects = SpeakerEffects(NodePath('speaker'))
    effects.update(1.0, 0, .8)
    assert all(node.isHidden() for node in effects.slime)
    effects.update(1.6, 0, .8)
    lengths = [node.getSz() for node in effects.slime]
    assert all(not node.isHidden() for node in effects.slime)
    effects.update(4, 0, .8)
    assert all(node.getSz() > initial for node, initial in zip(effects.slime, lengths, strict=True))
    effects.update(7, 0, .8)
    assert all(node.isHidden() for node in effects.slime)
    effects.update(1.6, 0, .8)
    assert all(not node.isHidden() for node in effects.slime)


def test_waves_wait_for_landing_and_stop_without_energy():
    effects = SpeakerEffects(NodePath('speaker'))
    effects.update(1.6, 0, .8)
    assert all(node.isHidden() for node in effects.waves)
    effects.update(3, 0, .8)
    assert any(not node.isHidden() for node in effects.waves)
    effects.update(3, 0, 0)
    assert all(node.isHidden() for node in effects.waves)
