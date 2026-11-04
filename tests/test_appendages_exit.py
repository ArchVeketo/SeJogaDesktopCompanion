import math
from sejoga.appendages import AppendageMotion
from sejoga.exit_animation import ExitAnimation


def test_tentacles_retract_progressively_instead_of_popping():
    motion = AppendageMotion()
    for _ in range(30):
        motion.update(.033, 85)
    assert motion.extension == 1
    first = motion.update(.033, 0)
    assert .9 < first < 1
    samples = [motion.update(.033, 0) for _ in range(30)]
    assert samples[-1] == 0
    assert samples == sorted(samples, reverse=True)


def test_tentacle_model_is_short_thick_faceted_and_has_raised_suckers():
    from sejoga.tentacle_model import build_tentacle
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
