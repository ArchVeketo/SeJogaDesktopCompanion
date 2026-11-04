"""Windows: exercita picking, gestos e movimento real sem mover o cursor do usuário.

Usa perfil temporário; execute `python tools/smoke_mouse.py [--physics]`.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sejoga import config


def main():
    profile = Path(tempfile.mkdtemp(prefix="sejoga-mouse-smoke-"))
    config.default_config_path = lambda: profile / "config.toml"
    from sejoga.window import OverlayApp, WS_EX_TRANSPARENT
    from sejoga.animation import AnimationState
    import win32gui

    settings = config.Settings()
    settings.physics.enabled = "--physics" in sys.argv
    settings.physics.collide_with_windows = False
    settings.music.enabled = False
    settings.window.start_position = (600, 200)
    app = OverlayApp(settings)
    # Avoid registering shortcuts already owned by the user's running companion.
    app.hotkey_manager.close()
    results = {"physics": settings.physics.enabled, "profile": str(profile)}

    def poll(local, buttons=(), *, screen=False):
        position = local if screen else win32gui.ClientToScreen(app.hwnd, local)
        with patch("sejoga.window.win32gui.GetCursorPos", return_value=position), \
             patch("sejoga.window.win32api.GetAsyncKeyState", return_value=0), \
             patch.object(app, "_mouse_buttons", return_value=frozenset(buttons)):
            app._mouse_poll(None)

    try:
        for _ in range(20):
            app.taskMgr.step()
            time.sleep(0.017)
        app.taskMgr.remove("mouse-poll")
        app.animation_timer.stop()
        assert win32gui.GetWindowRect(app.hwnd)[:2] == settings.window.start_position
        assert win32gui.GetWindowLong(app.hwnd, -20) & 0x00000008, "Panda reset always-on-top"
        points = [(x, y) for y in range(50, 440, 10) for x in range(60, 420, 10)
                  if app.renderer.hit_test(x, y)]
        assert points, "Picking did not find any model geometry"
        point = min(points, key=lambda p: (p[0] - 240) ** 2 + (p[1] - 300) ** 2)
        assert not app.renderer.hit_test(5, 5)
        results["pick_point"] = point
        poll((5, 5))
        assert win32gui.GetWindowLong(app.hwnd, -20) & WS_EX_TRANSPARENT
        poll(point)
        assert app._mouse_hovered, "Model must be accessible to Windows hit testing"
        assert not win32gui.GetWindowLong(app.hwnd, -20) & WS_EX_TRANSPARENT
        for button, state in (("left", AnimationState.CLICK), ("right", AnimationState.PET), ("middle", AnimationState.POKE)):
            poll(point, (button,))
            poll(point)
            app.animation_controller.update(0.05)
            assert app.animation_controller.state == state

        before = win32gui.GetWindowRect(app.hwnd)[:2]
        poll(point, ("left",))
        destination = win32gui.ClientToScreen(app.hwnd, (point[0] + 90, point[1] + 35))
        poll(destination, ("left",), screen=True)
        assert app._drag_active
        assert win32gui.GetWindowRect(app.hwnd)[:2] == (before[0] + 90, before[1] + 35)
        poll(destination, screen=True)
        assert not app._drag_active
        assert config.load_settings().window.start_position == (before[0] + 90, before[1] + 35)

        # Holding a button from outside cannot steal another application's drag.
        before = win32gui.GetWindowRect(app.hwnd)[:2]
        poll((5, 5), ("left",))
        poll(point, ("left",))
        poll((point[0] + 30, point[1]), ("left",))
        poll(point)
        assert not app._drag_active
        assert win32gui.GetWindowRect(app.hwnd)[:2] == before

        app.settings.behavior.react_to_drag = False
        poll(point, ("left",))
        poll((point[0] + 30, point[1]), ("left",))
        poll(point)
        assert not app._drag_active
        assert win32gui.GetWindowRect(app.hwnd)[:2] == before

        if app.physics:
            # Exercise a release through real Pymunk steps and real HWND moves.
            p = app.physics
            left, top, right, bottom = p.bounds
            p.set_position((left + right) / 2, top + 300)
            with patch("sejoga.physics.time.monotonic", return_value=10.0):
                p.start_drag(*p.state.position)
            with patch("sejoga.physics.time.monotonic", return_value=10.02):
                p.update_drag(p.state.position[0] + 20, p.state.position[1] - 10)
                velocity = p.end_drag()
            assert velocity[0] > 0 and velocity[1] < 0
            for _ in range(720):
                p.step(1 / 120)
            assert p.state.grounded
            assert abs(p.state.velocity[0]) < 5
            origin = win32gui.GetWindowRect(app.hwnd)[:2]
            assert origin == tuple(round(p.state.position[i] - app._physics_local[i]) for i in (0, 1))
            assert config.load_settings().window.start_position == origin
            results["throw"] = {"release_velocity": velocity, "rest": list(p.state.position), "origin": origin}

        app.set_debug_overlay(True)
        for _ in range(10):
            pose = app.animation_controller.update(0.016, hovered=True, look_direction=0.5)
            app.renderer.apply_rig_pose(pose)
        app.debug_tools.update(0.016)
        for _ in range(3):
            app.graphicsEngine.renderFrame()
        results["capture"] = str(app.debug_tools.capture_once())
        results["checks"] = "picking, pass-through, click/pet/poke, drag, saved position, external drag, disabled drag"
        print(json.dumps(results, indent=2))
    finally:
        app.debug_tools.close()
        app.music_listener.stop()
        app.tray_icon.hide()
        app.destroy()


if __name__ == "__main__":
    main()
