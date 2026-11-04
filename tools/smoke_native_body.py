"""Real Windows input: drag, reverse, release and check body/tray recovery.

Uses a temporary profile and restores the cursor/buttons in finally. It does
move the real cursor briefly, unlike smoke_mouse.py's injected polling.
"""
import ctypes
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sejoga import config


def main():
    profile = Path(tempfile.mkdtemp(prefix="sejoga-native-body-"))
    config.default_config_path = lambda: profile / "config.toml"
    from sejoga.window import OverlayApp
    from sejoga.tray_registration import IconData
    import win32api
    import win32con
    import win32gui
    from panda3d.core import Filename

    settings = config.Settings()
    settings.physics.enabled = settings.music.enabled = False
    settings.window.start_position = (600, 250)
    settings.window.outline_enabled = False
    app = OverlayApp(settings)
    app.hotkey_manager.close()
    original_cursor = win32gui.GetCursorPos()

    def frames(count):
        for _ in range(count):
            app.taskMgr.step()
            time.sleep(.016)

    def capture(name):
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(profile / f"{name}.png")))

    try:
        frames(40)
        initial = app.tray_registration.ensure()
        assert initial["registered"], initial
        data = IconData()
        data.cbSize = ctypes.sizeof(data)
        data.hWnd = initial["hwnd"]
        app.tray_registration._notify(2, ctypes.byref(data))
        assert app.tray_icon.isVisible() and not app.tray_registration.status()["registered"]
        recovered = app.tray_registration.ensure()
        assert recovered["registered"], recovered

        point = win32gui.ClientToScreen(app.hwnd, (240, 300))
        assert app.renderer.hit_test(240, 300)
        win32api.SetCursorPos(point)
        frames(3)
        assert win32gui.WindowFromPoint(point) == app.hwnd
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        frames(3)
        for step in range(1, 25):
            win32api.SetCursorPos((point[0] + step * 6, point[1]))
            frames(1)
        assert app._drag_active, "Native drag was not captured"
        first = app.animation_controller.body_motion.snapshot.roll
        capture("right")
        for step in range(1, 49):
            win32api.SetCursorPos((point[0] + 144 - step * 6, point[1]))
            frames(1)
        second = app.animation_controller.body_motion.snapshot.roll
        capture("left")
        assert first > 1 and second < -1, (first, second)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        frames(12)
        assert not app._drag_active
        app.taskMgr.remove("mouse-poll")
        app._mouse_hovered = False
        frames(150)
        settled = app.animation_controller.body_motion.snapshot.roll
        assert abs(settled) < .15, settled
        capture("settled")
        assert app.renderer._hidden_export_planes == ["mesh11", "mesh12", "mesh13", "mesh14"]
        print(json.dumps({"profile": str(profile), "native_drag_roll": [first, second],
                          "settled_roll": settled, "tray_recovered": recovered,
                          "hidden_export_planes": app.renderer._hidden_export_planes}, indent=2))
    finally:
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        frames(8)
        win32api.SetCursorPos(original_cursor)
        app.debug_tools.close()
        app.music_listener.stop()
        app.tray_icon.hide()
        app.tray_registration.close()
        app.desktop.close()
        app.desktop = None
        app.destroy()


if __name__ == "__main__":
    main()
