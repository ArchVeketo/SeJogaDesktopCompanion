"""Inspeção visual de hover, tentáculos, recolhimento e encerramento no Windows."""
import sys
import time
import tempfile
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sejoga import config


def main():
    profile = Path(tempfile.mkdtemp(prefix="sejoga-effects-"))
    config.default_config_path = lambda: profile / "config.toml"
    from sejoga.window import OverlayApp
    import win32gui
    import win32con
    settings = config.Settings()
    settings.music.enabled = False
    settings.physics.enabled = False
    settings.window.start_position = (700, 250)
    app = OverlayApp(settings)
    app.hotkey_manager.close()
    if "--exit-check" in sys.argv:
        app.taskMgr.doMethodLater(.5, lambda task: (win32gui.PostMessage(app.hwnd, win32con.WM_CLOSE, 0, 0), task.done)[1], "close-test")
        app.run()
        return

    def frame():
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()

    def capture(name):
        from panda3d.core import Filename
        frame()
        path = profile / f"{name}.png"
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(path)))
        print(path)

    def check_clearance():
        from panda3d.core import GeomVertexReader
        tentacles = app.renderer.tentacles
        for data, np in zip(tentacles._data, tentacles.meshes):
            if np.isHidden():
                continue
            reader = GeomVertexReader(data, "vertex")
            while not reader.isAtEnd():
                point = reader.getData3()
                assert tentacles.door.distance(point, tentacles.door.angle) >= -1e-5, (point, tentacles.door.angle)
        for arm in ("right-arm", "left-arm"):
            assert app.renderer._rig_nodes[arm].getPos().almostEqual(app.renderer._rig_base_pos[arm], 1e-6)
        for forearm, direction in (("hand", 1), ("hand2", -1)):
            bounds = app.renderer._rig_nodes[forearm].getTightBounds(app.renderer.model_np)
            for obstacle in ("body", "legs"):
                body = app.renderer._rig_nodes[obstacle].getTightBounds(app.renderer.model_np)
                if bounds[0].z < body[1].z and bounds[1].z > body[0].z and bounds[0].y < body[1].y and bounds[1].y > body[0].y:
                    assert (bounds[0].x >= body[1].x if direction > 0 else bounds[1].x <= body[0].x), (forearm, obstacle, bounds, body, app.renderer._rig_nodes["right-arm"].getHpr(), app.renderer._rig_nodes["ant-arm"].getHpr())

    try:
        for _ in range(20):
            app.taskMgr.step()
            time.sleep(.02)
        app.taskMgr.remove("animation-frame")
        app.taskMgr.remove("mouse-poll")
        assert win32gui.GetWindowLong(app.hwnd, -20) & win32con.WS_EX_APPWINDOW
        assert win32gui.SendMessage(app.hwnd, win32con.WM_GETICON, win32con.ICON_BIG, 0)
        menu = win32gui.GetSystemMenu(app.hwnd, False)
        import ctypes
        get_text = ctypes.windll.user32.GetMenuStringW
        get_text.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_uint]
        buffer = ctypes.create_unicode_buffer(256)
        get_text(menu, win32con.SC_CLOSE, buffer, len(buffer), win32con.MF_BYCOMMAND)
        assert "Mário" in buffer.value
        for name, horizontal, vertical in (("look-left-up", -1, -1), ("look-right-down", 1, 1)):
            app.animation_controller.interact("drag_start")
            for _ in range(25):
                pose = app.animation_controller.update(.033, hovered=True, look_direction=horizontal, look_vertical=vertical)
                app.renderer.apply_rig_pose(pose)
                app.renderer.update_appendages(.033)
            assert pose["head"].x * vertical < 0 and pose["head"].y * horizontal > 0
            capture(name)
        from sejoga.rig import IdlePersonality, pose_idle
        for personality in IdlePersonality:
            for phase in (0, .6, 1.2, 2.0):
                app.renderer.rig.reset()
                pose_idle(app.renderer.rig, phase, personality)
                app.renderer.apply_rig_pose(app.renderer.rig.pose())
                app.renderer.update_appendages(.033)
                capture(f"idle-{personality}-{phase}")
                check_clearance()
        for kind in ("wave", "stretch", "peek", "hit"):
            app.animation_controller.interact(kind)
            frames = int(app.animation_controller.REACTION_SECONDS[kind] / .033)
            for step in range(frames):
                pose = app.animation_controller.update(.033, idle_enabled=False)
                app.renderer.apply_rig_pose(pose)
                app.renderer.update_appendages(.033)
                check_clearance()
                if step in (0, frames//2, frames-1):
                    capture(f"{kind}-{step}")
            capture(kind)
        # Full opening, then a half-retracted frame and a closed frame.
        from sejoga.rig import Rotation3
        import math
        for _ in range(150):
            app.renderer.apply_rig_pose({"door": Rotation3(y=math.radians(85))})
            app.renderer.update_appendages(.033)
            check_clearance()
        assert app.renderer.tentacles.motion.extension > .95
        capture("tentacles-open")
        app.renderer.apply_rig_pose({"head": Rotation3(y=math.radians(30)), "door": Rotation3(y=math.radians(85))})
        capture("tentacles-three-quarter")
        app.renderer.apply_rig_pose({"head": Rotation3(), "door": Rotation3(y=math.radians(85))})
        app.renderer.tentacles._slime_cooldown = 0
        app.renderer.tentacles._rng.random = lambda: 0.0
        for _ in range(8):
            app.renderer.apply_rig_pose({"door": Rotation3()})
            app.renderer.update_appendages(.033)
            check_clearance()
        assert 0 < app.renderer.tentacles.motion.extension < .9
        assert app.renderer.tentacles.drops
        capture("tentacles-retract")
        for _ in range(160):
            app.renderer.apply_rig_pose({"door": Rotation3()})
            app.renderer.update_appendages(.033)
            check_clearance()
        assert app.renderer.tentacles.motion.extension == 0
        capture("tentacles-closed")
        app.renderer.begin_exit_effect()
        capture("exit-white")
        app.renderer.set_exit_rotation(110)
        capture("exit-spin")
    finally:
        app.debug_tools.close()
        app.music_listener.stop()
        app.tray_icon.hide()
        app.desktop.close()
        app.desktop = None
        app.destroy()
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--exit-check"], capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert b"Traceback" not in result.stderr
    print("Native WM_CLOSE animated exit completed with code 0.")


if __name__ == "__main__":
    main()
