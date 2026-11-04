from sejoga.animation import AnimationController, AnimationState
from sejoga.rig import ALL_GROUPS, Rig, Rotation3


def controller():
    return AnimationController(Rig(rest={group: Rotation3() for group in ALL_GROUPS}))


def test_click_wakes_sleep_and_does_not_immediately_fall_asleep():
    animation = controller()
    for _ in range(12):
        animation.update(0.1, sleep_after_idle_seconds=1)
    assert animation.state == AnimationState.SLEEP
    animation.interact("click")
    animation.update(0.1, sleep_after_idle_seconds=1)
    assert animation.state == AnimationState.WAKE
    for _ in range(12):
        animation.update(0.1, sleep_after_idle_seconds=1)
    assert animation.state == AnimationState.IDLE


def test_reactions_expire_and_drag_has_priority():
    animation = controller()
    animation.interact("pet")
    animation.update(0.1)
    assert animation.state == AnimationState.PET
    animation.interact("drag_start")
    animation.update(0.1, dragging=True)
    assert animation.state == AnimationState.DRAG
    animation.update(0.1)
    assert animation.state == AnimationState.IDLE


def test_rapid_click_does_not_restart_reaction_forever():
    animation = controller()
    animation.interact("click")
    for _ in range(5):
        animation.interact("click")
        animation.update(0.1)
    assert animation.state == AnimationState.IDLE


def test_hover_tracks_cursor_and_exits_smoothly():
    animation = controller()
    for _ in range(10):
        pose = animation.update(0.1, hovered=True, look_direction=1.0)
    assert animation.state == AnimationState.HOVER
    assert pose["head"].y > 0
    assert pose["door"].y > 0
    previous_pose = pose
    pose = animation.update(0.01)
    assert animation.state == AnimationState.IDLE
    assert pose == previous_pose


def test_landing_reaction_finishes_and_returns_to_idle():
    animation = controller()
    animation.interact("land")
    animation.update(0.1)
    assert animation.state == AnimationState.LAND
    for _ in range(5):
        animation.update(0.1)
    assert animation.state == AnimationState.IDLE


def test_music_preferences_disable_and_enable_dance():
    animation = controller()
    animation.update(.1, music_playing=True, music_intensity=.5, dance_chance=0)
    assert animation.state == AnimationState.IDLE
    animation.update(.1, music_playing=True, music_intensity=.5, react_to_beat=False)
    assert animation.state == AnimationState.IDLE
    animation.update(.1, music_playing=True, music_intensity=.5)
    assert animation.state == AnimationState.DANCE
    animation.update(.1, music_playing=False)
    assert animation.state == AnimationState.IDLE


def test_music_probability_is_not_sampled_every_frame():
    from unittest.mock import Mock
    animation = controller()
    animation._dance_rng.random = Mock(return_value=.9)
    for _ in range(60):
        animation.update(.016, music_playing=True, music_intensity=.5, dance_chance=.35)
    assert animation.state == AnimationState.IDLE
    assert animation._dance_rng.random.call_count == 1
