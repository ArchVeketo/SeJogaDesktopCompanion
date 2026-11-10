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

from sejoga import configuracao


def main():
    profile = Path(tempfile.mkdtemp(prefix="sejoga-mouse-smoke-"))
    configuracao.default_config_path = lambda: profile / "config.toml"
    import win32gui
    from PIL import ImageGrab

    from sejoga.animacao.animation import AnimationState
    from sejoga.render.window import WS_EX_TRANSPARENT, OverlayApp

    settings = configuracao.Settings()
    settings.physics.enabled = "--physics" in sys.argv
    settings.physics.collide_with_windows = False
    settings.music.enabled = False
    settings.window.start_position = (600, 200)
    app = OverlayApp(settings)
    # This smoke injects its own cursor samples. Real desktop activity during
    # startup must not leave HoverAttention in its one-second cooldown.
    app.taskMgr.remove("mouse-poll")
    # Avoid registering shortcuts already owned by the user's running companion.
    app.hotkey_manager.close()
    results = {"physics": settings.physics.enabled, "profile": str(profile)}

    def poll(local, buttons=(), *, screen=False):
        position = local if screen else win32gui.ClientToScreen(app.hwnd, local)
        # A mocked position does not move the OS cursor or change its shape.
        # Keep the virtual cursor neutral instead of inheriting an I-beam/link
        # from wherever the user is currently pointing on the real desktop.
        cursor = win32gui.LoadCursor(0, 32512)  # IDC_ARROW
        with patch("sejoga.render.window.win32gui.GetCursorPos", return_value=position), \
             patch("sejoga.render.window.win32gui.GetCursorInfo", return_value=(1, cursor, position)), \
             patch("sejoga.render.window.win32api.GetAsyncKeyState", return_value=0), \
             patch("sejoga.render.window.win32gui.GetForegroundWindow", return_value=app._hover_foreground), \
             patch.object(app, "_mouse_buttons", return_value=frozenset(buttons)):
            app._mouse_poll(None)

    try:
        for _ in range(20):
            app.taskMgr.step()
            time.sleep(0.017)
        app.taskMgr.remove("mouse-poll")
        app.taskMgr.remove("animation-frame")
        with patch("sejoga.render.window.win32api.GetAsyncKeyState", return_value=0):
            app._native_mouse_button("left", True)
            assert "left" in app._mouse_buttons(), "Native input must survive a zero async key state"
            app._native_mouse_button("left", False)
            assert not app._mouse_buttons()
        canvas_shift = (app.renderer.width-settings.window.size)//2
        expected_origin = settings.window.start_position if app.physics else tuple(v-canvas_shift for v in settings.window.start_position)
        assert win32gui.GetWindowRect(app.hwnd)[:2] == expected_origin
        app._hover_attention = type(app._hover_attention)()
        assert win32gui.GetWindowLong(app.hwnd, -20) & 0x00000008, "Panda reset always-on-top"
        assert app.renderer._outline_nodes
        for _ in range(2):
            app.graphicsEngine.renderFrame()
        outline_default = bytes(app.win.getScreenshot().getRamImageAs("RGB"))
        settings.window.outline_color = "#00FF00"
        app.renderer.set_outline_settings(settings.window)
        for _ in range(2):
            app.graphicsEngine.renderFrame()
        outline_green = bytes(app.win.getScreenshot().getRamImageAs("RGB"))
        assert outline_green != outline_default, "Changing outline color did not change the rendered frame"
        settings.window.outline_enabled = False
        app.renderer.set_outline_settings(settings.window)
        for _ in range(2):
            app.graphicsEngine.renderFrame()
        assert bytes(app.win.getScreenshot().getRamImageAs("RGB")) != outline_green
        settings.window.outline_enabled = True
        settings.window.outline_color = "#FF65CC"
        app.renderer.set_outline_settings(settings.window)
        points = [(x, y) for y in range(50, app.renderer.height-20, 10) for x in range(60, app.renderer.width-20, 10)
                  if app.renderer.hit_test(x, y)]
        assert points, "Picking did not find any model geometry"
        point = min(points, key=lambda p: (p[0] - 240) ** 2 + (p[1] - 300) ** 2)
        assert not app.renderer.hit_test(5, 5)
        results["pick_point"] = point
        poll((5, 5))
        assert not win32gui.GetWindowLong(app.hwnd, -20) & WS_EX_TRANSPARENT
        corner = win32gui.ClientToScreen(app.hwnd, (5, 5))
        assert win32gui.WindowFromPoint(corner) != app.hwnd
        assert ImageGrab.grab(bbox=(corner[0], corner[1], corner[0] + 1, corner[1] + 1)).getpixel((0, 0)) != (214, 0, 214)
        poll(point)
        assert app._mouse_hovered, "Model must be accessible to Windows hit testing"
        assert not win32gui.GetWindowLong(app.hwnd, -20) & WS_EX_TRANSPARENT
        for button, state in (("left", AnimationState.POKE), ("right", AnimationState.PET), ("middle", AnimationState.CLICK)):
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
        assert configuracao.load_settings().window.start_position == (before[0] + 90, before[1] + 35)

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
            left, top, right, _bottom = p.bounds
            p.set_position((left + right) / 2, top + 300)
            with patch("sejoga.desktop.physics.time.monotonic", return_value=10.0):
                p.start_drag(*p.state.position)
            with patch("sejoga.desktop.physics.time.monotonic", return_value=10.02):
                p.update_drag(p.state.position[0] + 20, p.state.position[1] - 10)
                velocity = p.end_drag()
            assert velocity[0] > 0 and velocity[1] < 0
            for _ in range(720):
                p.step(1 / 120)
            assert p.state.grounded
            assert abs(p.state.velocity[0]) < 5
            origin = win32gui.GetWindowRect(app.hwnd)[:2]
            assert origin == tuple(round(p.state.position[i] - app._physics_local[i]) for i in (0, 1))
            assert configuracao.load_settings().window.start_position == origin
            results["throw"] = {"release_velocity": velocity, "rest": list(p.state.position), "origin": origin}

        app.set_debug_overlay(True)
        app.graphicsEngine.renderFrame()
        time.sleep(0.1)
        debug_corner = win32gui.ClientToScreen(app.hwnd, (5, 5))
        debug_pixel = ImageGrab.grab(bbox=(debug_corner[0], debug_corner[1], debug_corner[0] + 1, debug_corner[1] + 1)).getpixel((0, 0))
        assert debug_pixel == (214, 0, 214), (debug_pixel, hex(app._background_key))
        face_point = win32gui.ClientToScreen(app.hwnd, (240+canvas_shift, 260+canvas_shift))
        face_pixel = ImageGrab.grab(bbox=(face_point[0], face_point[1], face_point[0] + 1, face_point[1] + 1)).getpixel((0, 0))
        assert face_pixel[0] < 200, (face_pixel, "outline is filling the transparent face")
        for _ in range(10):
            pose = app.animation_controller.update(0.016, hovered=True, look_direction=0.5)
            app.renderer.apply_rig_pose(pose)
        app.debug_tools.update(0.016)
        for _ in range(3):
            app.graphicsEngine.renderFrame()
        results["capture"] = str(app.debug_tools.capture_once())
        results["checks"] = "outline color/toggle, transparent background/debug pink, picking, click/pet/poke, drag, saved position, external drag, disabled drag"
        print(json.dumps(results, indent=2))
    finally:
        app.debug_tools.close()
        app.music_listener.stop()
        app.tray_icon.hide()
        app.destroy()


if __name__ == "__main__":
    main()
