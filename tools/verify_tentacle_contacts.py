"""Check rendered vertices, joint frames and closure through a complete peek."""
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sejoga import config


def main():
    profile = Path(tempfile.mkdtemp(prefix="sejoga-contact-review-"))
    config.default_config_path = lambda: profile / "config.toml"
    from sejoga.window import OverlayApp
    from panda3d.core import Filename, GeomVertexReader

    settings = config.Settings()
    settings.physics.enabled = settings.music.enabled = False
    settings.window.outline_enabled = False
    app = OverlayApp(settings)
    app.hotkey_manager.close()
    app.taskMgr.remove("mouse-poll")
    controller = app.animation_controller
    controller._ambient_in = controller._peek_in = 1000
    renderer = app.renderer
    samples, worst, minimum_volume = 0, 0.0, 1.0

    def tick():
        pose = controller.update(1 / 60)
        renderer.apply_rig_pose(pose)
        renderer.apply_body_motion(controller.body_motion.snapshot)
        renderer.update_appendages(1 / 60, controller.state.value == "peek")
    app._animation_tick = tick

    try:
        for _ in range(20):
            app.taskMgr.step()
        controller.interact("peek")
        for frame in range(660):
            if frame in (160, 260, 350):
                controller.body_motion.impulse("poke", direction=1 if frame != 260 else -1)
            app.taskMgr.step()
            if frame % 15 == 0:
                # Refresh after applying the actual door angle, not the previous frame's.
                renderer._update_tentacle_contacts()
                for limb in renderer.tentacle_pool.tentacles:
                    if limb.reveal <= .015 or limb.mesh_node.isHidden():
                        continue
                    for _, tangent, right, front in limb.frames:
                        minimum_volume = min(minimum_volume, abs(right.cross(front).dot(tangent)))
                        assert abs(right.dot(front)) < .0001
                        assert abs(right.dot(tangent)) < .0001
                    reader = GeomVertexReader(limb.mesh_vdata, "vertex")
                    while not reader.isAtEnd():
                        vertex = reader.getData3()
                        for box in renderer.tentacle_contacts.boxes:
                            distance = box.distance(vertex)
                            worst = min(worst, distance)
                            assert distance >= -.002, (frame, box.name, distance, tuple(vertex))
                        samples += 1
            if frame in (60, 150, 240, 360, 450, 540, 659):
                app.win.getScreenshot().write(Filename.fromOsSpecific(str(profile / f"contact-{frame}.png")))
        assert minimum_volume > .999
        assert all(limb.state.value == "dormant" for limb in renderer.tentacle_pool.tentacles)
        # Idle deliberately leaves the door ajar by up to three degrees.
        assert renderer.tentacle_director._door_current < 4
        result = {"profile": str(profile), "vertices_checked": samples,
                  "worst_penetration_model_units": worst, "minimum_frame_volume": minimum_volume,
                  "door_degrees": renderer.tentacle_director._door_current,
                  "obstacles": len(renderer.tentacle_contacts.boxes)}
        (profile / "contacts.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2), flush=True)
    finally:
        app.debug_tools.close()
        app.music_listener.stop()
        app.tray_icon.hide()
        app.desktop.close()
        app.desktop = None
        app.destroy()


if __name__ == "__main__":
    main()
