"""Render complete idle cycles, contact sheets and animated previews.

Uses an isolated config and a deterministic animation clock without moving
the user's mouse. Run from the repository root: python tools/preview_idle_styles.py
"""
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sejoga import config


def main():
    profile = Path(tempfile.mkdtemp(prefix="sejoga-idle-styles-"))
    config.default_config_path = lambda: profile / "config.toml"
    from panda3d.core import Filename
    from PIL import Image, ImageDraw

    from sejoga.window import OverlayApp

    settings = config.Settings()
    settings.physics.enabled = False
    settings.music.enabled = False
    settings.window.outline_enabled = False
    settings.behavior.sleep_after_idle_seconds = 0
    app = OverlayApp(settings)
    app.hotkey_manager.close()
    app.taskMgr.remove("mouse-poll")
    animation = app.animation_controller
    animation._ambient_in = animation._peek_in = 10000

    def tick():
        pose = animation.update(1 / 60)
        app.renderer.apply_rig_pose(pose)
        app.renderer.update_appendages(1 / 60, False)

    app._animation_tick = tick
    metadata = {}
    try:
        for style in ("street", "fighter", "rhythm", "stylish"):
            app._personality_actions[style].trigger()
            frames = []
            snapshots = []
            start = time.perf_counter()
            for frame in range(600):
                app.taskMgr.step()
                if frame % 6 == 0 or frame in (119, 179, 209, 299, 599):
                    path = profile / f"{style}-{frame:03}.png"
                    app.win.getScreenshot().write(Filename.fromOsSpecific(str(path)))
                    with Image.open(path) as source:
                        current = source.convert("RGB")
                    if frame % 6 == 0:
                        frames.append(current)
                    if frame in (0, 119, 179, 209, 299, 599):
                        snapshots.append((frame, current))
            frames[0].save(profile / f"{style}.gif", save_all=True,
                           append_images=frames[1:], duration=100, loop=0)
            sheet = Image.new("RGB", (240 * len(snapshots), 270), "#202026")
            draw = ImageDraw.Draw(sheet)
            for index, (frame, current) in enumerate(snapshots):
                sheet.paste(current.resize((240, 240)), (index * 240, 26))
                draw.text((index * 240 + 8, 5), f"{style} {frame / 60:.2f}s", fill="white")
            sheet.save(profile / f"{style}-sheet.png")
            metadata[style] = {"frames": 600, "elapsed": time.perf_counter() - start}
            print(style, "complete", flush=True)
        (profile / "review.json").write_text(json.dumps(metadata, indent=2))
        print("REVIEW", profile, flush=True)
    finally:
        app.debug_tools.close()
        app.music_listener.stop()
        app.tray_icon.hide()
        app.desktop.close()
        app.desktop = None
        app.destroy()


if __name__ == "__main__":
    main()
