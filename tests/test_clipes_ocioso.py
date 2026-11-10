"""Continuity and layering contracts for authored idle phrases."""
from math import degrees

import pytest

from sejoga.animacao.controlador_animacao import AnimationController
from sejoga.animacao.clipes_ocioso import CLIPS, sample_idle, sample_track
from sejoga.configuracao import Settings
from sejoga.animacao.poses_base import pose_idle, pose_secondary
from sejoga.nucleo.esqueleto import ALL_GROUPS, IdlePersonality, Rig, Rotation3


@pytest.mark.parametrize("style", CLIPS)
def test_idle_tracks_close_with_zero_velocity(style):
    clip = CLIPS[style]
    for keys in clip.tracks.values():
        assert keys[0][1] == keys[-1][1] == (0, 0, 0)
        assert list(t for t, _ in keys) == sorted(set(t for t, _ in keys))
        for t, value in keys:
            for axis, center in enumerate(value):
                before = sample_track(keys, max(0, t - .0001))[axis]
                after = sample_track(keys, min(clip.duration, t + .0001))[axis]
                assert abs(after - center) < .00001
                assert abs(before - center) < .00001


@pytest.mark.parametrize("style", CLIPS)
def test_style_persists_and_manual_choice_stays_locked(style):
    settings = Settings.model_validate({"behavior": {"idle_personality": style}})
    animation = AnimationController(Rig(rest={g: Rotation3() for g in ALL_GROUPS}))
    animation.set_idle_personality(settings.behavior.idle_personality)
    animation._ambient_in = animation._peek_in = 1000
    for _ in range(300):
        animation.update(.1)
    assert animation.idle_personality.value == style
    animation.set_idle_personality("auto")
    assert not animation._personality_locked


def test_secondary_motion_keeps_authored_hand_pitch_and_finger_gesture():
    style = IdlePersonality.STYLISH
    rig = Rig(rest={g: Rotation3() for g in ALL_GROUPS})
    rig.reset()
    neutral = Rig(rest=dict(rig.rest))
    pose_idle(rig, 2.5, style)
    neutral.current = dict(rig.current)
    authored_hand = rig.current["hand"]
    authored_fingers = rig.current["fingers"]
    neutral.current["hand"] = neutral.current["fingers"] = Rotation3()
    pose_secondary(rig, 2.5, "idle", style)
    pose_secondary(neutral, 2.5, "idle", style)
    assert degrees(rig.current["hand"].y) == pytest.approx(degrees(authored_hand.y))
    assert rig.current["hand"].z - neutral.current["hand"].z == pytest.approx(authored_hand.z)
    assert rig.current["fingers"].z - neutral.current["fingers"].z == pytest.approx(authored_fingers.z)


def test_four_styles_have_distinct_rest_and_peak_silhouettes():
    for time in (0, 2.5):
        poses = [sample_idle(style, time) for style in CLIPS]
        assert all(a != b for i, a in enumerate(poses) for b in poses[i + 1:])

def test_clips_tem_as_nove_personalidades():
    assert set(CLIPS) == {p.value for p in IdlePersonality}
