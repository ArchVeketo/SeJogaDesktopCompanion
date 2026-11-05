"""HUD, eixos de referência, logs e captura opcional de frames."""

from __future__ import annotations

import json
import logging
import logging.handlers
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import LineSegs, TextNode

from .config import default_config_path


def configure_logging() -> logging.Logger:
    """Configura log rotativo no perfil do usuário sem bloquear a inicialização."""
    logger = logging.getLogger("sejoga")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    try:
        log_dir = default_config_path().parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            log_dir / "companion.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    except OSError as exc:
        logger.addHandler(logging.StreamHandler())
        logger.warning("Could not create the log file: %s", exc)

    previous_excepthook = sys.excepthook

    def log_uncaught_exception(exc_type, exc_value, exc_traceback):
        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        previous_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = log_uncaught_exception
    if hasattr(threading, "excepthook"):
        threading.excepthook = lambda args: logger.error(
            "Uncaught worker exception",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
    return logger


class DebugTools:
    """Diagnóstico visual e gravação de frames sem custo no modo normal."""

    MAX_RECORDING_FRAMES = 300
    FRAME_QUEUE_SIZE = 16

    def __init__(self, app, on_recording_changed=None, debug_hotkey="ctrl+alt+f11"):
        self.app = app
        self.on_recording_changed = on_recording_changed
        self.debug_hotkey = debug_hotkey.upper()
        self.visible = False
        self.recording = False
        self._frame_count = 0
        self._dropped_frames = 0
        self._fps = 0.0
        self._last_hud_update = 0.0
        self._capture_dir: Path | None = None
        self._queue: queue.Queue[tuple[Path, bytes, int, int, dict[str, Any]] | None] = queue.Queue(
            maxsize=self.FRAME_QUEUE_SIZE
        )
        self._worker = threading.Thread(
            target=self._write_frames,
            name="debug-frame-writer",
            daemon=True,
        )
        self._worker.start()

        self.hud = OnscreenText(
            text="",
            parent=app.aspect2d,
            pos=(-0.95, 0.96),
            align=TextNode.ALeft,
            scale=0.045,
            fg=(1.0, 1.0, 1.0, 1.0),
            bg=(0.035, 0.035, 0.055, 0.88),
            mayChange=True,
            wordwrap=62,
        )
        self.hud.hide()
        self._local_axes = self._make_axes(app.renderer.model_np)
        self._world_axes = self._make_axes(app.render)
        self._world_axes.setPos(0.0, 0.0, app.renderer._view_target_z)
        self._local_axes.hide()
        self._world_axes.hide()
        joints = app.renderer.lower_body.joints + [node for chain in app.renderer.flexible_rig.chains[:1]
                                                   for node in (chain[0],chain[1],*chain[2])]
        self._joint_axes = [self._make_axes(joint) for joint in joints]
        for axis in self._joint_axes:
            axis.setScale(.12)
            axis.hide()

    @staticmethod
    def _make_axes(root):
        lines = LineSegs("debug-axes")
        lines.setThickness(2.5)
        lines.setColor(1.0, 0.18, 0.2, 1.0)
        lines.moveTo(0, 0, 0)
        lines.drawTo(0.42, 0, 0)
        lines.setColor(0.2, 1.0, 0.35, 1.0)
        lines.moveTo(0, 0, 0)
        lines.drawTo(0, 0.42, 0)
        lines.setColor(0.25, 0.55, 1.0, 1.0)
        lines.moveTo(0, 0, 0)
        lines.drawTo(0, 0, 0.42)
        return root.attachNewNode(lines.create())

    def set_visible(self, visible: bool) -> None:
        for axis in self._joint_axes:
            (axis.show if visible else axis.hide)()
        self.visible = bool(visible)
        if self.visible:
            self.hud.show()
            self._local_axes.show()
            self._world_axes.show()
        else:
            self.hud.hide()
            self._local_axes.hide()
            self._world_axes.hide()

    def toggle_visible(self) -> bool:
        self.set_visible(not self.visible)
        return self.visible

    def set_recording(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self.recording:
            return
        if enabled:
            try:
                self._capture_dir = self._new_capture_dir()
            except OSError:
                logging.getLogger("sejoga").exception("Could not create frame capture directory")
                return
            self._frame_count = 0
            self._dropped_frames = 0
            self.set_visible(True)
        self.recording = enabled
        if self.on_recording_changed:
            self.on_recording_changed(self.recording)

    def toggle_recording(self) -> bool:
        self.set_recording(not self.recording)
        return self.recording

    def capture_once(self) -> Path | None:
        if not self.recording:
            try:
                self._capture_dir = self._new_capture_dir()
            except OSError:
                logging.getLogger("sejoga").exception("Could not create frame capture directory")
                return None
            self._frame_count = 0
            self._dropped_frames = 0
        return self._capture_frame(self._metadata(), recording=False)

    def update(self, dt: float) -> None:
        if dt > 0:
            instant_fps = 1.0 / dt
            self._fps = instant_fps if self._fps == 0 else self._fps * 0.85 + instant_fps * 0.15
        if self.visible and time.monotonic() - self._last_hud_update >= 0.2:
            self.hud.setText(self._format_hud())
            self._last_hud_update = time.monotonic()
        if self.recording:
            self._capture_frame(self._metadata(), recording=True)

    def _metadata(self) -> dict[str, Any]:
        state = self.app.physics.get_state() if self.app.physics else None
        music = self.app.music_listener.snapshot if self.app.music_listener else None
        animation = self.app.animation_controller
        renderer = self.app.renderer
        return {
            "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "fps": round(self._fps, 2),
            "animation_state": animation.state.value if animation and animation.state else None,
            "idle_personality": animation.idle_personality.value if animation else None,
            "dance_style": animation.dance_motion.style if animation else None,
            "dance_preview": animation._dance_preview_remaining > 0 if animation else False,
            "appendage_remaining": animation.appendage_remaining if animation else 0,
            "body_motion": vars(animation.body_motion.snapshot) if animation else None,
            "pointer_velocity": list(animation.body_motion.pointer_velocity) if animation else None,
            "hidden_export_planes": renderer._hidden_export_planes,
            "tray_registration": self.app.tray_registration.last_status,
            "tentacle_contacts": renderer.tentacle_contacts.contacts,
            "tentacles": [
                {
                    "state": limb.state.value,
                    "reveal": round(limb.reveal, 4),
                    "anchor": list(limb.anchor),
                    "tip": list(limb.visible_tip()),
                    "joints": [
                        {"position": list(center), "x": list(right),
                         "y": list(front), "z": list(tangent)}
                        for center, tangent, right, front in limb.frames
                    ],
                }
                for limb in renderer.tentacle_pool.tentacles
                if limb.state.value != "dormant"
            ],
            "mouse": {
                "local_position": list(self.app._mouse_local),
                "hovered": self.app._mouse_hovered,
                "dragging": self.app._drag_active,
            },
            "window_pixels": [renderer.width, renderer.height],
            "model_scale": round(float(renderer.model_np.getScale().x), 4),
            "model_bounds_units": list(map(float, renderer._model_dimensions)),
            "model_anchor": list(map(float, renderer.model_anchor.getPos())),
            "model_rotation_hpr": list(map(float, renderer.model_anchor.getHpr())),
            "door_rotation_hpr": (
                list(map(float, renderer._rig_nodes["door"].getHpr()))
                if "door" in renderer._rig_nodes
                else None
            ),
            "camera_position": list(map(float, self.app.cam.getPos(self.app.render))),
            "camera_fov": list(map(float, self.app.cam.node().getLens().getFov())),
            "physics": (
                {
                    "position": list(state.position),
                    "velocity": list(state.velocity),
                    "grounded": state.grounded,
                    "gravity_active": state.gravity_active,
                }
                if state
                else None
            ),
            "music": (
                {
                    "title": music.title,
                    "artist": music.artist,
                    "playing": music.is_playing,
                    "level": music.audio_level,
                    "bpm": music.bpm,
                }
                if music
                else None
            ),
        }

    def _format_hud(self) -> str:
        meta = self._metadata()
        physics = meta["physics"]
        music = meta["music"]
        state = physics or {"position": (0, 0), "velocity": (0, 0), "grounded": True}
        camera_pos = meta["camera_position"]
        fov = meta["camera_fov"]
        music_text = "off" if not music else f"{music['level']:.2f} / {music['bpm'] or 'n/a'} BPM"
        bounds = " x ".join(f"{value:.2f}" for value in meta["model_bounds_units"])
        camera = ", ".join(f"{value:.2f}" for value in camera_pos)
        camera_fov = ", ".join(f"{value:.1f}" for value in fov)
        return (
            f"SEJOGA DEBUG  |  {self.debug_hotkey} fecha\n"
            f"FPS {self._fps:5.1f}   Janela {meta['window_pixels'][0]}x{meta['window_pixels'][1]}\n"
            f"Estado {meta['animation_state']}   Persona {meta['idle_personality']}\n"
            f"Balanço {meta['body_motion']['roll']:.1f}°  Suspensão {meta['body_motion']['hanging']:.2f}\n"
            f"Tentáculos {len(meta['tentacles'])}   Contatos {meta['tentacle_contacts']}\n"
            f"Mouse {meta['mouse']['local_position']} Hover {meta['mouse']['hovered']} Drag {meta['mouse']['dragging']}\n"
            f"Pos {state['position'][0]:.1f}, {state['position'][1]:.1f} px\n"
            f"Vel {state['velocity'][0]:.1f}, {state['velocity'][1]:.1f} px/s\n"
            f"Chão {state['grounded']}   Gravidade {state.get('gravity_active', False)}\n"
            f"Escala {meta['model_scale']:.3f} Bounds {bounds}\n"
            f"Câmera {camera} FOV {camera_fov}\n"
            f"Música {music_text}\n"
            f"Gravação {'ON' if self.recording else 'off'}  Frames {self._frame_count}  Perdidos {self._dropped_frames}\n"
            "Eixos: X vermelho | Y verde | Z azul"
        )

    def _new_capture_dir(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        directory = default_config_path().parent / "debug-captures" / stamp
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _capture_frame(self, metadata: dict[str, Any], *, recording: bool) -> Path | None:
        if recording and self._frame_count >= self.MAX_RECORDING_FRAMES:
            self.set_recording(False)
            return None
        try:
            texture = self.app.win.getScreenshot()
            if texture is None:
                return None
            pixels = bytes(texture.getRamImageAs("RGB"))
            width, height = texture.getXSize(), texture.getYSize()
            if not pixels or width <= 0 or height <= 0:
                return None
            directory = self._capture_dir or self._new_capture_dir()
            self._capture_dir = directory
            self._frame_count += 1
            metadata["frame"] = self._frame_count
            metadata["capture_kind"] = "recording" if recording else "single"
            metadata["image_size"] = [width, height]
            path = directory / f"frame-{self._frame_count:04d}.png"
            item = (path, pixels, width, height, metadata)
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                self._dropped_frames += 1
                return None
            return path
        except Exception:
            logging.getLogger("sejoga").exception("Frame capture failed")
            return None

    def _write_frames(self) -> None:
        from PIL import Image

        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                path, pixels, width, height, metadata = item
                image = Image.frombytes("RGB", (width, height), pixels)
                image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                image.save(path, format="PNG")
                with (path.parent / "frames.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            except Exception:
                logging.getLogger("sejoga").exception("Could not write captured frame")
            finally:
                self._queue.task_done()

    def close(self) -> None:
        self.set_recording(False)
        try:
            self._queue.join()
            self._queue.put(None, timeout=0.5)
        except queue.Full:
            return
        self._worker.join(timeout=2.0)
