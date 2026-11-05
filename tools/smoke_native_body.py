"""Real Windows input: drag, reverse, release and check body/tray recovery.

Uses a temporary profile and restores the cursor/buttons in finally. It does
move the real cursor briefly, unlike smoke_mouse.py's injected polling.
"""
import ctypes
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sejoga import config


def main():
    profile = Path(tempfile.mkdtemp(prefix="sejoga-native-body-"))
    config.default_config_path = lambda: profile / "config.toml"
    import win32api
    import win32con
    import win32gui
    from panda3d.core import Filename

    from sejoga.tray_registration import IconData
    from sejoga.window import OverlayApp

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
        for _ in range(2):
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
            frames(2)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
            frames(2)
        assert app.animation_controller.state.value == "double_click"
        capture("double-click")
        frames(100)
        # The reaction changes the silhouette. Reacquire a solid shirt pixel
        # instead of pressing the former head/neck edge after it moved.
        candidates = [(x, y) for y in range(320, 370, 5) for x in range(220, 265, 5)
                      if app.renderer.hit_test(x, y)]
        local = next(p for p in sorted(candidates, key=lambda p: (p[0]-240)**2 + (p[1]-345)**2)
                     if win32gui.WindowFromPoint(win32gui.ClientToScreen(app.hwnd, p)) == app.hwnd)
        point = win32gui.ClientToScreen(app.hwnd, local)
        win32api.SetCursorPos(point)
        frames(3)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        frames(3)
        for step in range(1, 25):
            win32api.SetCursorPos((point[0] + step * 6, point[1]))
            frames(1)
        assert app._drag_active, "Native drag was not captured"
        first = app.animation_controller.body_motion.snapshot.roll
        from panda3d.core import Point2
        projected = Point2()
        grabbed = app.cam.getRelativePoint(app.renderer.model_np, app._body_grab_point)
        app.cam.node().getLens().project(grabbed, projected)
        screen_grab = win32gui.ClientToScreen(app.hwnd, (
            round((projected.x+1)*app.renderer.width/2),
            round((1-projected.y)*app.renderer.height/2)))
        cursor = win32gui.GetCursorPos()
        grab_error = ((screen_grab[0]-cursor[0])**2+(screen_grab[1]-cursor[1])**2)**.5
        print('grab_cursor_error_px', grab_error, 'canvas', app.renderer.width)
        assert grab_error < 12, (screen_grab, cursor)
        assert app.win.getXSize() == app.renderer.width
        assert app.renderer.width >= settings.window.size
        from panda3d.core import Point3
        low, high = app.renderer.model_np.getTightBounds(app.render)
        for x in (low.x, high.x):
            for y in (low.y, high.y):
                for z in (low.z, high.z):
                    corner = Point2()
                    app.cam.node().getLens().project(app.cam.getRelativePoint(app.render, Point3(x,y,z)), corner)
                    assert abs(corner.x) <= 1.01 and abs(corner.y) <= 1.01, corner
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
                          "native_double_click": True,
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
