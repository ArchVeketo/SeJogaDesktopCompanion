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


def verificar_redimensionamento(app, desktop, win32gui):
    """Simula a mudança das métricas e confere o framebuffer real."""
    size_x, size_y = app.renderer.width, app.renderer.height
    metrics = {76: desktop[0], 77: desktop[1], 78: size_x - 48, 79: size_y - 48}
    saved_position = app._mascot_screen
    with patch("sejoga.render.janela.win32api.GetSystemMetrics", side_effect=metrics.__getitem__):
        app._sincronizar_desktop(0.6)
        assert app._desktop_rect[2:] == (size_x - 48, size_y - 48)
        assert app._mascot_screen == saved_position
        for _ in range(5):
            app.taskMgr.step()
        assert (app.win.getXSize(), app.win.getYSize()) == app._desktop_rect[2:]
    app._sincronizar_desktop(0.6)
    for _ in range(5):
        app.taskMgr.step()
    assert (app.win.getXSize(), app.win.getYSize()) == (size_x, size_y)
    app.settings.window.scale = 1.1
    app._sincronizar_desktop(0.6)
    for _ in range(5):
        app.taskMgr.step()
    assert app._mascot_screen == saved_position
    assert app.win.getXSize() == min(app._desktop_rect[2], round(size_x * 1.1))
    assert app.win.getYSize() == min(app._desktop_rect[3], round(size_y * 1.1))
    assert win32gui.ClientToScreen(app.hwnd, tuple(map(round, app._physics_local))) == tuple(
        map(round, saved_position)
    )
    app.settings.window.scale = 1.0
    app._sincronizar_desktop(0.1)
    assert app.win.getXSize() > size_x
    for _ in range(16):
        app._sincronizar_desktop(0.1)
    assert (app.win.getXSize(), app.win.getYSize()) == (size_x, size_y)
    assert win32gui.ClientToScreen(app.hwnd, tuple(map(round, app._physics_local))) == tuple(
        map(round, saved_position)
    )


def _aguardar_pouso_inicial(app, land_state) -> None:
    if not app.physics:
        return
    for _ in range(180):
        if (
            app.physics.state.grounded
            and app.animation_controller.state != land_state
            and app.animation_controller._reaction is None
        ):
            break
        app.taskMgr.step()
        time.sleep(0.017)
    assert app.physics.state.grounded


def main():  # noqa: C901, PLR0915  # TODO convenção: ferramenta de captura/GPU: fatiar sem rodar na GPU arrisca a saída; lote próprio
    """Executa o smoke de mouse na janela real."""
    profile = Path(tempfile.mkdtemp(prefix="sejoga-mouse-smoke-"))
    configuracao.default_config_path = lambda: profile / "config.toml"
    import win32api
    import win32gui
    from PIL import ImageGrab

    from sejoga.animacao.controlador_animacao import AnimationState
    from sejoga.render.janela import WS_EX_TRANSPARENT, OverlayApp

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
        with (
            patch("sejoga.render.janela.win32gui.GetCursorPos", return_value=position),
            patch(
                "sejoga.render.janela.win32gui.GetCursorInfo",
                return_value=(1, cursor, position),
            ),
            patch("sejoga.render.janela.win32api.GetAsyncKeyState", return_value=0),
            patch(
                "sejoga.render.janela.win32gui.GetForegroundWindow",
                return_value=app._hover_foreground,
            ),
            patch.object(app, "_mouse_buttons", return_value=frozenset(buttons)),
        ):
            app._mouse_poll(None)

    try:
        for _ in range(20):
            app.taskMgr.step()
            time.sleep(0.017)
        _aguardar_pouso_inicial(app, AnimationState.LAND)
        app.taskMgr.remove("mouse-poll")
        app.taskMgr.remove("animation-frame")
        with patch("sejoga.render.janela.win32api.GetAsyncKeyState", return_value=0):
            app._native_mouse_button("left", True)
            assert "left" in app._mouse_buttons(), (
                "Native input must survive a zero async key state"
            )
            app._native_mouse_button("left", False)
            assert not app._mouse_buttons()
        desktop = win32gui.GetWindowRect(app.hwnd)
        assert desktop[:2] == app._canvas_origin
        assert (desktop[2] - desktop[0], desktop[3] - desktop[1]) == (app.renderer.width, app.renderer.height)
        centro_x, centro_y = map(round, app._physics_local)
        app._hover_attention = type(app._hover_attention)()
        assert win32gui.GetWindowLong(app.hwnd, -20) & 0x00000008, (
            "Panda reset always-on-top"
        )
        assert app.renderer._outline_nodes
        for _ in range(2):
            app.graphicsEngine.renderFrame()
        outline_default = bytes(app.win.getScreenshot().getRamImageAs("RGB"))
        settings.window.outline_color = "#00FF00"
        app.renderer.set_outline_settings(settings.window)
        for _ in range(2):
            app.graphicsEngine.renderFrame()
        outline_green = bytes(app.win.getScreenshot().getRamImageAs("RGB"))
        assert outline_green != outline_default, (
            "Changing outline color did not change the rendered frame"
        )
        settings.window.outline_enabled = False
        app.renderer.set_outline_settings(settings.window)
        for _ in range(2):
            app.graphicsEngine.renderFrame()
        assert bytes(app.win.getScreenshot().getRamImageAs("RGB")) != outline_green
        settings.window.outline_enabled = True
        settings.window.outline_color = "#FF65CC"
        app.renderer.set_outline_settings(settings.window)
        points = [
            (x, y)
            for y in range(centro_y - 250, centro_y + 10, 10)
            for x in range(centro_x - 135, centro_x + 135, 10)
            if app.renderer.hit_test(x, y)
            and win32gui.WindowFromPoint(win32gui.ClientToScreen(app.hwnd, (x, y))) == app.hwnd
        ]
        assert points, "Picking did not find any model geometry"
        point = min(points, key=lambda p: (p[0] - centro_x) ** 2 + (p[1] - (centro_y - 100)) ** 2)
        assert not app.renderer.hit_test(5, 5)
        results["pick_point"] = point
        poll((5, 5))
        assert not win32gui.GetWindowLong(app.hwnd, -20) & WS_EX_TRANSPARENT
        corner = win32gui.ClientToScreen(app.hwnd, (5, 5))
        assert win32gui.WindowFromPoint(corner) != app.hwnd
        assert ImageGrab.grab(
            bbox=(corner[0], corner[1], corner[0] + 1, corner[1] + 1)
        ).getpixel((0, 0)) != (214, 0, 214)
        poll(point)
        assert app._mouse_hovered, "Model must be accessible to Windows hit testing"
        assert not win32gui.GetWindowLong(app.hwnd, -20) & WS_EX_TRANSPARENT
        for button, state in (
            ("left", AnimationState.POKE),
            ("right", AnimationState.PET),
            ("middle", AnimationState.CLICK),
        ):
            poll(point, (button,))
            poll(point)
            app.animation_controller.update(0.05)
            assert app.animation_controller.state == state, (point, button, app.animation_controller.state)

        before = app._mascot_screen
        poll(point, ("left",))
        destination = win32gui.ClientToScreen(app.hwnd, (point[0] + 90, point[1] + 35))
        poll(destination, ("left",), screen=True)
        assert app._drag_active
        assert app._mascot_screen == (before[0] + 90, before[1] + 35)
        assert (app.win.getXSize(), app.win.getYSize()) == (app.renderer.width, app.renderer.height)
        poll(destination, screen=True)
        assert not app._drag_active
        assert configuracao.load_settings().window.start_position == tuple(
            round(v - o) for v, o in zip(app._mascot_screen, app._offset_mascote, strict=True)
        )
        point = win32gui.ScreenToClient(app.hwnd, destination)

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
            with patch("sejoga.desktop.fisica.time.monotonic", return_value=10.0):
                p.start_drag(*p.state.position)
            with patch("sejoga.desktop.fisica.time.monotonic", return_value=10.02):
                p.update_drag(p.state.position[0] + 20, p.state.position[1] - 10)
                velocity = p.end_drag()
            assert velocity[0] > 0 and velocity[1] < 0
            for _ in range(720):
                p.step(1 / 120)
            assert p.state.grounded
            assert abs(p.state.velocity[0]) < 5
            assert (app.win.getXSize(), app.win.getYSize()) == (app.renderer.width, app.renderer.height)
            origin = tuple(round(v - o) for v, o in zip(
                p.state.position, app._offset_mascote, strict=True
            ))
            assert configuracao.load_settings().window.start_position == origin
            results["throw"] = {
                "release_velocity": velocity,
                "rest": list(p.state.position),
                "origin": origin,
            }

        for _ in range(5):
            app.taskMgr.step()
        app.set_debug_overlay(True)
        for _ in range(5):
            app.taskMgr.step()
            time.sleep(0.017)
        monitor = win32api.MonitorFromPoint(tuple(map(round, app._mascot_screen)), 2)
        left, top, _, _ = win32api.GetMonitorInfo(monitor)["Monitor"]
        canvas_left, canvas_top = win32gui.ClientToScreen(app.hwnd, (0, 0))
        debug_corner = (max(left, canvas_left) + 5, max(top, canvas_top) + 5)
        debug_pixel = ImageGrab.grab(
            bbox=(
                debug_corner[0],
                debug_corner[1],
                debug_corner[0] + 1,
                debug_corner[1] + 1,
            )
        ).getpixel((0, 0))
        assert debug_pixel == (214, 0, 214), (debug_pixel, hex(app._background_key))
        from panda3d.core import Point2

        door = app.renderer._rig_nodes["door"]
        low, high = door.getTightBounds(app.cam)
        center = Point2()
        assert app.cam.node().getLens().project((low + high) * 0.5, center)
        face_point = win32gui.ClientToScreen(app.hwnd, (
            round((center.x + 1) * app.renderer.width / 2),
            round((1 - center.y) * app.renderer.height / 2),
        ))
        face_pixel = ImageGrab.grab(
            bbox=(face_point[0], face_point[1], face_point[0] + 1, face_point[1] + 1)
        ).getpixel((0, 0))
        assert face_pixel == (214, 0, 214) or face_pixel[0] < 200, (
            face_pixel,
            "outline is filling the transparent face",
        )
        for _ in range(10):
            pose = app.animation_controller.update(
                0.016, hovered=True, look_direction=0.5
            )
            app.renderer.apply_rig_pose(pose)
        app.debug_tools.update(0.016)
        for _ in range(3):
            app.graphicsEngine.renderFrame()
        results["capture"] = str(app.debug_tools.capture_once())
        results["checks"] = (
            "outline color/toggle, transparent background/debug pink, picking, click/pet/poke, drag, saved position, external drag, disabled drag"
        )
        if not app.physics:
            verificar_redimensionamento(app, desktop, win32gui)
        print(json.dumps(results, indent=2))
    finally:
        app.debug_tools.close()
        app.music_listener.stop()
        app.tray_icon.hide()
        app.destroy()


if __name__ == "__main__":
    main()
