"""Testa a suspensão por parte pega e a recuperação ao soltar."""

import pytest

from sejoga.animacao.movimento_corpo import BodyMotion


def test_grab_parts_change_suspension_and_release_recovers():
    poses = {}
    for part in ("body", "right-arm", "left-arm", "left-feet"):
        motion = BodyMotion()
        for _ in range(180):
            pose = motion.update(1 / 60, dragging=True, grab_part=part)
        poses[part] = pose
        for _ in range(360):
            released = motion.update(1 / 60)
        assert abs(released.roll) < 0.1
        assert released.stretch == 0
    assert poses["right-arm"].roll < -15
    assert poses["left-arm"].roll > 15
    assert poses["right-arm"].roll == pytest.approx(-poses["left-arm"].roll, abs=1.0)
    assert abs(poses["left-feet"].roll) > 140
    assert poses["right-arm"].stretch > poses["body"].stretch


def test_curve_drag_spins_and_release_carries_momentum():
    motion = BodyMotion()
    # Arraste em curva circular gera torque angular
    import math

    for i in range(45):
        ang = i * 0.14
        px = 240.0 + math.cos(ang) * 90.0
        py = 240.0 + math.sin(ang) * 90.0
        pose = motion.update(1 / 60, pointer=(px, py), dragging=True, grab_part="body")
    assert abs(pose.spin_speed) > 1.0
    # Soltura no ar mantém velocidade de giro antes de assentar
    released = motion.update(1 / 60, dragging=False, grounded=False, velocity=(300.0, 200.0))
    assert abs(motion.roll.velocity) > 0.0
    assert released is not None


def test_arm_grab_reaches_cursor_on_deceleration_and_head_surprises():
    motion = BodyMotion()
    for _ in range(30):
        pose = motion.update(1 / 60, pointer=(200.0, 200.0), dragging=True, grab_part="right-arm")
    assert pose.reach_cursor > 0.5

    head_motion = BodyMotion()
    for i in range(6):
        head_motion.update(1 / 60, pointer=(100.0 + i * 25.0, 200.0), dragging=True, grab_part="head")
    # Reversão brusca de direção
    for i in range(4):
        jolt_pose = head_motion.update(1 / 60, pointer=(220.0 - i * 35.0, 200.0), dragging=True, grab_part="head")
    assert jolt_pose.surprise_jolt > 0.0


def test_leg_motion_per_grab_part_and_heavy_land():
    from sejoga.animacao.movimento_pernas import LegMotion

    lm_left = LegMotion()
    for t in range(20):
        p_left = lm_left.update(1 / 60, "drag", time=t / 60, grab_part="left-feet")
    assert abs(p_left.left_knee) < 5.0
    assert p_left.right_knee > 10.0

    lm_land = LegMotion()
    for t in range(30):
        p_land = lm_land.update(1 / 60, "land", time=t / 60, heavy_land=True)
    assert p_land.left < -40.0
    assert p_land.left_knee > 40.0
