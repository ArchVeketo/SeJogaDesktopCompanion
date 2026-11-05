"""Prevent disappearing tentacles and doors closing before retraction."""
import random

import pytest
from panda3d.core import NodePath, Vec3

from sejoga.rig import ALL_GROUPS, IdlePersonality, Rig, Rotation3
from sejoga.tentacle_system import TentacleDirector, TentaclePool, TentacleState


def scene():
    rig = Rig(rest={name: Rotation3() for name in ALL_GROUPS})
    root = NodePath("test-root")
    pool = TentaclePool(rig, root, root, [Vec3(0)], rng=random.Random(1), unit_scale=.004)
    director = TentacleDirector(pool, rig, root, root, None, rng=random.Random(2))
    return pool, director


def test_retraction_preserves_volume_then_reaches_dormant_without_restarting():
    pool, director = scene()
    director.trigger_curious()
    director._door_current = director._door_requested = 70
    for _ in range(120):
        director.update(1 / 60, 0, IdlePersonality.CALM)
    limb = pool.tentacles[0]
    initial = (limb.visible_tip() - limb.anchor).length()
    assert initial > .1
    pool.release(limb)
    director.update(1 / 60, 0, IdlePersonality.CALM)
    assert (limb.visible_tip() - limb.anchor).length() > initial * .99
    previous = initial
    for _ in range(110):
        # Repeated cancellation must not reset the easing clock.
        pool.release(limb)
        director.update(1 / 60, 0, IdlePersonality.CALM)
        distance = (limb.visible_tip() - limb.anchor).length()
        assert distance <= previous + 1e-6
        previous = distance
    assert limb.state == TentacleState.DORMANT
    assert previous == pytest.approx(0, abs=1e-6)


def test_emergence_waits_for_door_and_root_never_drifts():
    pool, director = scene()
    director.trigger_curious()
    limb = pool.tentacles[0]
    for _ in range(10):
        director.update(1 / 60, 0, IdlePersonality.PLAYFUL)
    assert limb.state_time == 0
    director._door_current = 70
    director._door_requested = 70
    for _ in range(120):
        director.update(1 / 60, 0, IdlePersonality.PLAYFUL)
        assert limb.segments[0].pos.almostEqual(limb.anchor, 1e-7)
    assert (limb.segments[-1].pos - limb.anchor).length() > .1


def test_door_closing_respects_speed_limit():
    _, director = scene()
    director._door_current = 48
    director._door_requested = 0
    for _ in range(240):
        before = director._door_current
        director.update(1 / 60, 0, IdlePersonality.STREET)
        assert 0 <= before - director._door_current <= 38 / 60 + 1e-6
    assert director._door_current < .01


def test_speaker_throw_releases_limbs_and_allows_pool_reuse():
    _pool, director = scene()
    director.trigger_speaker_throw()
    limb = director.speaker_throw_limbs[0]
    limb.target = Vec3(.4, .3, .1)
    director._door_current = director._door_requested = 100
    for _ in range(60):
        director.update(1 / 60, 0, IdlePersonality.CALM)
    assert limb.reveal > .9
    assert limb.speaker_throw
    for _ in range(150):
        director.update(1 / 60, 0, IdlePersonality.CALM)
    assert not director.speaker_throw_limbs
    assert not limb.speaker_throw
    assert limb.state == TentacleState.DORMANT
    director.trigger_curious()
    assert limb.state == TentacleState.CURIOUS
    assert not limb.speaker_throw
