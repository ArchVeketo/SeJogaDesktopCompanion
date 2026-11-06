from math import isfinite

import pytest

from sejoga.animacao.body_motion import BodyMotion, Spring


def test_spring_response_is_frame_rate_independent():
    results = []
    for rate in (30, 60, 120):
        spring = Spring(1.65, .52)
        for _ in range(rate):
            spring.update(1 / rate, 17)
        for _ in range(rate * 2):
            spring.update(1 / rate, 0)
        results.append((spring.value, spring.velocity))
    for result in results[1:]:
        assert result == pytest.approx(results[0], abs=1e-10)


def test_drag_sways_on_velocity_reversal_and_settles_after_release():
    body = BodyMotion()
    for frame in range(60):
        pose = body.update(1 / 60, pointer=(frame * 12, 0), dragging=True)
    right = pose.roll
    assert right > 4
    for frame in range(60):
        pose = body.update(1 / 60, pointer=(720 - frame * 12, 0), dragging=True)
    assert pose.roll < -4
    before = pose.roll
    pose = body.update(1 / 60, pointer=(0, 0))
    assert abs(pose.roll - before) < 3
    for _ in range(300):
        pose = body.update(1 / 60, pointer=(0, 0))
    assert abs(pose.roll) < .01 and pose.hanging < .001


def test_entering_hover_after_external_mouse_movement_does_not_kick_body():
    body = BodyMotion()
    body.update(.016, pointer=(0, 0))
    pose = body.update(.016, pointer=(2000, 1000), hovered=True)
    assert pose.roll == pose.pitch == 0
    assert body.pointer_velocity == (0, 0)


def test_impacts_keep_finite_bounded_motion_and_a_delayed_neck():
    body = BodyMotion()
    body.impulse('hit', direction=1, strength=2)
    frames = [body.update(1 / 60) for _ in range(40)]
    assert any(abs(frame.head_roll) > .1 for frame in frames)
    assert any(frame.compression > .01 for frame in frames)
    for frame in frames:
        assert all(isfinite(value) for value in vars(frame).values())
        assert abs(frame.roll) <= 28 and abs(frame.pitch) <= 16
