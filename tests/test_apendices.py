import math

from sejoga.animacao.apendices import AppendageMotion, DoorJoint, tentacle_center
from sejoga.animacao.animacao_saida import ExitAnimation


def test_tentacles_retract_progressively_instead_of_popping():
    motion = AppendageMotion()
    for _ in range(120):
        motion.update(.033, 85)
    assert motion.extension == 1
    first = motion.update(.033, 0)
    assert .9 < first < 1
    samples = [motion.update(.033, 0) for _ in range(150)]
    assert samples[-1] == 0
    assert samples == sorted(samples, reverse=True)


def test_tentacle_model_is_short_thick_faceted_and_has_raised_suckers():
    from sejoga.tentaculos.modelo_tentaculo import build_tentacle
    vertices, normals, colors, indices = build_tentacle()
    width = max(v[0] for v in vertices)-min(v[0] for v in vertices)
    height = max(v[2] for v in vertices)-min(v[2] for v in vertices)
    assert height/width < 3.5
    assert len(indices)//3 < 300
    assert len(vertices) == len(normals) == len(colors)
    assert max(v[1] for v in vertices) > .06
    assert any(c[0] == 1 for c in colors)
    assert all(math.isfinite(v) for p in vertices for v in p)


def test_exit_freezes_then_spins_outside_desktop_both_directions():
    for origin in ((-1000, 300), (500, 300)):
        effect = ExitAnimation(origin, 480, (-1920, -200, 1920, 1080))
        frozen = effect.sample(.1)
        assert (frozen.x, frozen.y, frozen.roll) == (*origin, 0)
        halfway = effect.sample(.7)
        assert not halfway.done and abs(halfway.roll) > 100
        end = effect.sample(2)
        assert end.done and end.y + 480 < -200
        assert end.x + 480 < -1920 or end.x > 1920


def test_door_is_pushed_open_by_contact_and_closes_after_retraction():
    door = DoorJoint()
    sphere = ((0, .155, .15), .04)
    for _ in range(120):
        door.update(.033, 0, [sphere])
    assert door.angle > 20
    assert door.distance(sphere[0], door.angle) >= sphere[1]
    for _ in range(150):
        door.update(.033, 0, [])
    assert door.angle == 0


def test_contact_projection_clears_door_volume():
    door = DoorJoint()
    for angle in (0, 40, 85, 120):
        door.angle = angle
        point = (-.02, .15, .15)
        result = door.project(point, .06)
        assert door.distance(result, angle) >= .06 - 1e-7


def test_tentacle_roots_are_inside_opening_and_tips_move_in_depth():
    for index in range(4):
        root = tentacle_center(index, 0, 0, 1)
        assert abs(root[0]) < .07 and root[1] < .116
        assert 0 < root[2] < .3
        tip_a = tentacle_center(index, 1, 0, 1)
        tip_b = tentacle_center(index, 1, 1, 1)
        assert tip_a != tip_b
        assert tip_a[1] > root[1]+.15
    motion = AppendageMotion()
    motion.update(.1, 85, actual_door=0)
    assert motion.extension == 0  # The mesh waits for room at the hinge.


def test_door_contact_never_teleports_and_common_poses_keep_tentacles_hidden():
    door = DoorJoint()
    previous = 0
    for _ in range(180):
        door.update(1/60, 85, [((0, .155, .15), .04)])
        assert abs(door.angle-previous) <= 38/60 + 1e-6
        previous = door.angle
    motion = AppendageMotion()
    for _ in range(600):
        motion.update(1/60, 48, actual_door=85)
    assert motion.extension == 0
