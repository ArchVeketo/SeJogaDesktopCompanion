"""Regressões de arremesso e contatos com o Pymunk real (Windows)."""
import math
import sys
from unittest.mock import patch

import pytest

if sys.platform != "win32":
    pytest.skip("Windows physics backend", allow_module_level=True)
pytest.importorskip("pymunk")

from sejoga.config import Settings
from sejoga.physics import ScreenSpacePhysics, Shelf, MAX_VELOCITY


def physics():
    settings = Settings()
    settings.physics.collide_with_windows = False
    p = ScreenSpacePhysics(screen_width=1000, screen_height=800, settings=settings)
    p.set_position(300, 200)
    return p


def advance(p, seconds=3):
    for _ in range(round(seconds * 120)):
        p.step(1 / 120)


def test_throw_uses_current_samples_multiplier_and_grab_offset():
    p = physics()
    p.settings.physics.throw_multiplier = 2
    with patch("sejoga.physics.time.monotonic", return_value=10.0):
        p.start_drag(280, 190)
    with patch("sejoga.physics.time.monotonic", return_value=10.02):
        p.update_drag(300, 200)
        velocity = p.end_drag()
    assert tuple(p.body.position) == pytest.approx((320, 210))
    assert velocity == pytest.approx((2000, 1000))
    assert p.state.gravity_active
    advance(p, 0.1)
    assert all(math.isfinite(v) for v in p.state.position)


def test_pause_before_release_and_cancel_do_not_throw():
    for cancel in (True, False):
        p = physics()
        with patch("sejoga.physics.time.monotonic", return_value=10):
            p.start_drag(300, 200)
        with patch("sejoga.physics.time.monotonic", return_value=10.02):
            p.update_drag(500, 200)
        with patch("sejoga.physics.time.monotonic", return_value=11):
            assert p.end_drag(cancel=cancel) == (0, 0)
        assert p.state.gravity_active == (not cancel)


def test_throw_clamps_velocity_and_supports_negative_monitor_origin():
    p = physics()
    p.set_bounds((-1200, -100, 0, 800))
    with patch("sejoga.physics.time.monotonic", return_value=10):
        p.start_drag(300, 200)
    with patch("sejoga.physics.time.monotonic", return_value=10.001):
        p.update_drag(1000, -500)
        p.end_drag()
    assert p.body.velocity.length <= MAX_VELOCITY + 1e-6
    assert -1200 < p.body.position.x < 0
    assert -100 < p.body.position.y < 800


def test_fall_bounces_and_settles_without_sleep_crash():
    p = physics()
    impacts = []
    p.on_collision = lambda *args: impacts.append(args)
    p.set_gravity(True)
    advance(p, 6)
    assert impacts
    assert p.state.grounded
    assert p.body.position.y == pytest.approx(758, abs=4)
    assert abs(p.body.velocity.y) < 30


def test_shelf_lands_from_above_and_body_passes_from_below():
    p = physics()
    shelf = Shelf(123, (100, 400, 700, 600), 400, 100, 700)
    with patch("sejoga.physics.get_all_shelves", return_value=[shelf]):
        p.refresh_shelves(force=True)
    p.set_gravity(True)
    advance(p, 3)
    assert p.state.on_shelf == 123
    assert p.body.position.y == pytest.approx(358, abs=4)
    p.set_position(300, 500)
    p.set_gravity(False)
    p.body.velocity = (0, -600)
    advance(p, .4)
    assert p.body.position.y < 350


def test_moving_and_closing_shelf_updates_collision_shape_and_body_falls():
    p = physics()
    shelf = Shelf(123, (100, 400, 700, 600), 400, 100, 700)
    with patch("sejoga.physics.get_all_shelves", return_value=[shelf]):
        p.refresh_shelves(force=True)
    p.set_gravity(True)
    advance(p)
    assert p.state.grounded
    moved = Shelf(123, (100, 600, 700, 750), 600, 100, 700)
    with patch("sejoga.physics.get_all_shelves", return_value=[moved]):
        p.refresh_shelves(force=True)
    assert p.shelf_shapes[123].a.y == 600
    advance(p)
    assert p.body.position.y == pytest.approx(558, abs=4)
    with patch("sejoga.physics.get_all_shelves", return_value=[]):
        p.refresh_shelves(force=True)
    advance(p)
    assert p.state.on_shelf is None
    assert p.body.position.y > 700


def test_nearby_shelf_is_not_ground_without_actual_contact():
    p = physics()
    p.shelves = [Shelf(123, (100, 400, 700, 600), 400, 100, 700)]
    p.set_position(300, 358)
    p.update_grounded_state()
    assert not p.state.grounded
    assert p.state.on_shelf is None


def test_walking_off_support_keeps_gravity_and_does_not_walk_in_air():
    p = physics()
    shelf = Shelf(123, (100, 400, 450, 600), 400, 100, 450)
    with patch("sejoga.physics.get_all_shelves", return_value=[shelf]):
        p.refresh_shelves(force=True)
    p.set_gravity(True)
    advance(p)
    assert p.state.grounded
    p.settings.physics.friction = 0
    p.shape.friction = 0
    p.body.velocity = (1200, 0)
    advance(p, .3)
    assert not p.state.grounded
    assert p.state.gravity_active
    assert p.state.on_shelf is None


def test_only_exposed_parts_of_background_window_are_shelves():
    from sejoga.physics import get_all_shelves
    bounds = {101: (400, 100, 600, 600), 102: (100, 300, 900, 700)}
    def enumerate_windows(callback, arg):
        for hwnd in bounds:
            callback(hwnd, arg)
    with patch("sejoga.physics.win32gui.EnumWindows", side_effect=enumerate_windows), \
         patch("sejoga.physics.is_valid_shelf", return_value=True), \
         patch("sejoga.physics.frame_bounds", side_effect=bounds.get):
        shelves = get_all_shelves(0, 0)
    assert [(s.left, s.right) for s in shelves if s.hwnd == 102] == [(100, 400), (600, 900)]
