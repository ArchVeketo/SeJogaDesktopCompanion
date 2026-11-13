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
from sejoga import configuracao


def _pegar_parte(app, win32gui, *partes):
    largura, altura = app.renderer.width, app.renderer.height
    x0, y0 = map(round, app._physics_local)
    pontos = (
        (x, y)
        for y in range(max(0, y0 - 250), min(altura, y0 + 8), 6)
        for x in range(max(0, x0 - 130), min(largura, x0 + 130), 6)
    )
    for x, y in sorted(pontos, key=lambda p: abs(p[0] - x0) + abs(p[1] - (y0 - 85))):
        if all(
            app.renderer.hit_test(x + dx, y + dy) and app.renderer._pick_part in partes
            for dx, dy in ((0, 0), (0, -6), (0, 6), (-6, 0), (6, 0))
        ):
            tela = win32gui.ClientToScreen(app.hwnd, (x, y))
            if win32gui.WindowFromPoint(tela) == app.hwnd:
                return tela
    raise AssertionError(f"Nenhuma pega nativa para {partes} no HWND {app.hwnd}")


def _verificar_enquadramento(app):
    from panda3d.core import Point2, Point3

    low, high = app.renderer.model_np.getTightBounds(app.render)
    for x in (low.x, high.x):
        for y in (low.y, high.y):
            for z in (low.z, high.z):
                corner = Point2()
                app.cam.node().getLens().project(
                    app.cam.getRelativePoint(app.render, Point3(x, y, z)), corner
                )
                assert abs(corner.x) <= 1.01 and abs(corner.y) <= 1.01, corner


def main():  # noqa: PLR0915  # TODO convenção: ferramenta de captura/GPU: fatiar sem rodar na GPU arrisca a saída; lote próprio
    """Executa o smoke do corpo com mouse nativo."""
    profile = Path(tempfile.mkdtemp(prefix="sejoga-native-body-"))
    configuracao.default_config_path = lambda: profile / "config.toml"
    import win32api
    import win32con
    import win32gui

    from sejoga.desktop.registro_bandeja import IconData
    from sejoga.render.janela import OverlayApp

    # isort: split
    # OverlayApp loads Qt's runtime DLLs before Panda3D on Windows.
    from panda3d.core import Filename

    settings = configuracao.Settings()
    settings.physics.enabled = settings.music.enabled = False
    settings.window.start_position = (600, 250)
    settings.window.outline_enabled = False
    app = OverlayApp(settings)
    app.hotkey_manager.close()
    original_cursor = win32gui.GetCursorPos()

    def frames(count):
        for _ in range(count):
            app.taskMgr.step()
            time.sleep(0.016)

    def capture(name):
        app.win.getScreenshot().write(
            Filename.fromOsSpecific(str(profile / f"{name}.png"))
        )

    try:
        frames(40)
        initial = app.tray_registration.ensure()
        assert initial["registered"], initial
        data = IconData()
        data.cbSize = ctypes.sizeof(data)
        data.hWnd = initial["hwnd"]
        app.tray_registration._notify(2, ctypes.byref(data))
        assert (
            app.tray_icon.isVisible()
            and not app.tray_registration.status()["registered"]
        )
        recovered = app.tray_registration.ensure()
        assert recovered["registered"], recovered

        point = _pegar_parte(app, win32gui, "body", "head")
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
        point = _pegar_parte(app, win32gui, "body")
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
        screen_grab = win32gui.ClientToScreen(
            app.hwnd,
            (
                round((projected.x + 1) * app.renderer.width / 2),
                round((1 - projected.y) * app.renderer.height / 2),
            ),
        )
        cursor = win32gui.GetCursorPos()
        grab_error = (
            (screen_grab[0] - cursor[0]) ** 2 + (screen_grab[1] - cursor[1]) ** 2
        ) ** 0.5
        print("grab_cursor_error_px", grab_error, "canvas", app.renderer.width)
        assert grab_error < 12, (screen_grab, cursor)
        assert app.win.getXSize() == app.renderer.width
        assert app.renderer.width >= settings.window.size
        _verificar_enquadramento(app)
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
        point = _pegar_parte(app, win32gui, "left-feet", "right-feet", "legs")
        win32api.SetCursorPos(point)
        frames(2)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        frames(3)
        for step in range(1, 13):
            win32api.SetCursorPos((point[0] + step * 4, point[1] - step * 3))
            frames(1)
        assert app._drag_active and app._body_grab_part in ("left-feet", "right-feet", "legs")
        assert (app.renderer.width, app.renderer.height) == (app.win.getXSize(), app.win.getYSize())
        grabbed = app.cam.getRelativePoint(app.renderer.model_np, app._body_grab_point)
        app.cam.node().getLens().project(grabbed, projected)
        screen_grab = win32gui.ClientToScreen(
            app.hwnd,
            (round((projected.x + 1) * app.renderer.width / 2),
             round((1 - projected.y) * app.renderer.height / 2)),
        )
        cursor = win32gui.GetCursorPos()
        assert max(abs(a - b) for a, b in zip(screen_grab, cursor, strict=True)) < 12
        _verificar_enquadramento(app)
        capture("foot-drag")
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        frames(12)
        assert not app._drag_active
        app.taskMgr.remove("mouse-poll")
        app._mouse_hovered = False
        frames(150)
        settled = app.animation_controller.body_motion.snapshot.roll
        assert abs(settled) < 0.15, settled
        capture("settled")
        print(
            json.dumps(
                {
                    "profile": str(profile),
                    "native_drag_roll": [first, second],
                    "settled_roll": settled,
                    "tray_recovered": recovered,
                    "native_double_click": True,
                    "hidden_export_planes": app.renderer._hidden_export_planes,
                },
                indent=2,
            )
        )
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
