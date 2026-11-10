"""Testa a suspensão por parte pega e a recuperação ao soltar."""

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
    assert poses["right-arm"].roll > 35
    assert poses["left-arm"].roll < -35
    assert poses["left-feet"].roll < -140
    assert poses["right-arm"].stretch > poses["body"].stretch
