"""Deterministic rendered review of body actions, hover idles and silhouettes."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sejoga import configuracao


def main():  # noqa: C901, PLR0915  # TODO convenção: ferramenta de captura/GPU: fatiar sem rodar na GPU arrisca a saída; lote próprio
    """Renderiza as prévias das ações do corpo."""
    profile = Path(tempfile.mkdtemp(prefix="sejoga-body-actions-"))
    configuracao.default_config_path = lambda: profile / "config.toml"
    import win32gui
    from PIL import Image, ImageDraw, ImageGrab

    from sejoga.animacao.controlador_animacao import AnimationController
    from sejoga.render.janela import OverlayApp

    # isort: split
    # O overlay carrega as DLLs do Qt antes do Panda3D no Windows.
    from panda3d.core import Filename

    settings = configuracao.Settings()
    settings.physics.enabled = settings.music.enabled = False
    settings.window.outline_enabled = False
    settings.window.start_position = (600, 200)
    app = OverlayApp(settings)
    app.hotkey_manager.close()
    app.taskMgr.remove("mouse-poll")
    app._animation_tick = lambda: None
    cases = [
        ("wave", {}),
        ("stretch", {}),
        ("fall", {"grounded": False, "gravity_active": True}),
        ("walk", {"velocity": (250, 0)}),
        ("run", {"velocity": (800, 0)}),
        ("hover", {"hovered": True, "look_direction": 0.7}),
        ("drag", {"dragging": True, "drag_direction": 0.8, "drag_intensity": 0.8}),
        ("dance", {"music_playing": True, "music_intensity": 0.5, "dance_chance": 1.0}),
    ]
    cases.extend(
        (f"idle-{style}", {})
        for style in (
            "calm",
            "curious",
            "playful",
            "shy",
            "confident",
            "street",
            "fighter",
            "rhythm",
            "stylish",
        )
    )
    cases.extend(
        (name, {}) for name in ("hang_loose", "thumbs_up", "rock", "finger_gun")
    )
    cases.extend(
        (f"grab-{part}", dict(dragging=True, grab_part=part))
        for part in ("right-arm", "left-arm", "left-feet", "right-feet")
    )
    cases.extend(
        (
            name,
            dict(
                music_playing=True,
                music_intensity=level,
                music_bass=bass,
                music_bpm=bpm,
                dance_chance=1.0,
            ),
        )
        for name, level, bass, bpm in (
            ("music-soft", 0.2, 0.02, 75),
            ("music-hiphop", 0.55, 0.35, 95),
            ("music-heavy", 0.95, 0.7, 145),
        )
    )
    requested = set(sys.argv[1:])
    if requested:
        cases = [case for case in cases if case[0] in requested]
    metadata = {}
    try:  # noqa: PLR1702  # TODO convenção: ferramenta de captura/GPU: fatiar sem rodar na GPU arrisca a saída; lote próprio
        for kind, args in cases:
            animation = AnimationController(app.renderer.rig)
            app.animation_controller = animation
            if kind.startswith("music-"):
                for _ in range(240):
                    animation.update(1 / 60, **args)
            if kind in (
                "wave",
                "stretch",
                "hang_loose",
                "thumbs_up",
                "rock",
                "finger_gun",
            ):
                animation.interact(kind)
            if kind == "dance":
                animation._dance_rng.random = lambda: 0.0
            if kind.startswith("idle-"):
                animation.set_idle_personality(kind.removeprefix("idle-"))
            frame_count = 300 if kind.startswith("idle-") else 180
            key_frames = (
                {0, 30, 60, 90, 150, 240, 299}
                if kind.startswith("idle-")
                else {0, 35, 65, 95, 145, 179}
            )
            snapshots = []
            frames = []
            for frame in range(frame_count):
                dt = 1 / 60
                params = dict(args)
                if kind == "drag" or kind.startswith("grab-"):
                    from math import sin

                    params["pointer_position"] = (
                        600 + 120 * sin(frame / 25),
                        300 + 35 * sin(frame / 35),
                    )
                if kind == "fall":
                    params["velocity"] = (180, -450 + frame * 8)
                pose = animation.update(dt, **params)
                app.renderer.apply_rig_pose(pose)
                part = params.get("grab_part", "body")
                grip = app.renderer._rig_nodes[part].getPos(app.renderer.model_np)
                app.renderer.lower_body.apply(
                    animation.leg_motion.pose,
                    params.get("grounded", True) and not params.get("dragging", False),
                )
                app.renderer.apply_body_motion(
                    animation.body_motion.snapshot,
                    grip,
                    grounded=params.get("grounded", True),
                    dragging=params.get("dragging", False),
                )
                app.renderer.update_appendages(dt, False)
                app._sincronizar_desktop(dt)
                app.taskMgr.step()
                if frame % 6 == 0 or frame in key_frames:
                    file = profile / f"{kind}-{frame}.png"
                    app.win.getScreenshot().write(Filename.fromOsSpecific(str(file)))
                    im = Image.open(file).convert("RGB")
                    if frame % 6 == 0:
                        frames.append(im)
                    if frame in key_frames:
                        snapshots.append((frame, im))
            sheet = Image.new("RGB", (len(snapshots) * 240, 270), "#202026")
            draw = ImageDraw.Draw(sheet)
            for i, (frame, im) in enumerate(snapshots):
                sheet.paste(im.resize((240, 240)), (i * 240, 30))
                draw.text((i * 240 + 5, 8), f"{kind} {frame / 60:.2f}s", fill="white")
            sheet.save(profile / f"{kind}-sheet.png")
            frames[0].save(
                profile / f"{kind}.gif",
                save_all=True,
                append_images=frames[1:],
                duration=100,
                loop=0,
            )
            metadata[kind] = {
                "state": animation.state.value,
                "idle_clock": animation._idle_clock,
            }
            print(kind, flush=True)
        ImageGrab.grab(bbox=win32gui.GetWindowRect(app.hwnd), all_screens=True).save(
            profile / "desktop.png"
        )
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
