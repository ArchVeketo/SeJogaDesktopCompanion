"""
OverlayWindow — Janela transparente always-on-top com render 3D (Panda3D) + PySide6 system tray.

Arquitetura:
- Panda3D cria a janela principal (HWND nativo) via ShowBase
- Win32 API aplica: WS_EX_LAYERED + color key (magenta) + click-through seletivo
- PySide6 usado APENAS para QSystemTrayIcon (system tray)
- Eventos de mouse/drag via Win32 polling no task loop do Panda3D
- Z-order toggle: HWND_TOPMOST / HWND_BOTTOM / HWND_NOTOPMOST
"""

from __future__ import annotations

import contextlib
import ctypes
import logging
import math
import os
import sys
import time
from typing import Any

# Win32 API
import win32api
import win32con
import win32gui

# Panda3D - configurar ANTES de importar ShowBase
from panda3d.core import loadPrcFileData

# Load Qt before Panda3D: their Windows bundles ship different MSVC runtime
# DLLs, and the first loaded copy wins for the whole process.
from PySide6.QtGui import QActionGroup, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

loadPrcFileData("", "window-type none")
loadPrcFileData("", "load-display pandagl")
loadPrcFileData("", "aux-display p3tinydisplay")
loadPrcFileData("", "framebuffer-alpha 1")
loadPrcFileData("", "framebuffer-multisample 1")
loadPrcFileData("", "multisamples 4")
loadPrcFileData("", "win-size 480 480")
loadPrcFileData("", "win-origin 0 0")
loadPrcFileData("", "undecorated 1")
loadPrcFileData("", "cursor-hidden 0")

# Panda3D imports (depois do loadPrcFileData)
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import (
    FrameBufferProperties,
    Point3,
    Vec3,
    WindowProperties,
)

# Project imports
from .animation import AnimationController
from .assets import brand_dir
from .attention import HoverAttention
from .config import Settings, load_settings, save_settings
from .debug import DebugTools, configure_logging
from .desktop_shell import DesktopIntegration
from .exit_animation import ExitAnimation
from .interaction import MouseInteraction
from .music import MusicListener
from .physics import create_physics
from .renderer import Panda3DRenderer
from .rig import IdlePersonality
from .tray_registration import TrayRegistration
from .ui import HotkeyManager, SettingsDialog
from .win32_overlay import (
    COLOR_KEY,
    GWL_EXSTYLE,
    HWND_BOTTOM,
    HWND_NOTOPMOST,
    HWND_TOPMOST,
    LWA_ALPHA,
    LWA_COLORKEY,
    SWP_NOACTIVATE,
    SWP_NOMOVE,
    SWP_NOSIZE,
    SWP_NOZORDER,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TOPMOST,
    WS_EX_TRANSPARENT,
)

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

logger = logging.getLogger(__name__)

# ============================================================
# OverlayApp - Main Application
# ============================================================

class OverlayApp(ShowBase):
    """Aplicação principal - Panda3D ShowBase + Win32 layered window + PySide6 tray."""

    def __init__(self, settings: Settings):
        DesktopIntegration.set_app_id()
        ShowBase.__init__(self, windowType="none")

        self.settings = settings
        self.settings_obj = settings
        self.renderer: Any = None
        self.physics: Any = None
        self.music_listener: MusicListener | None = None
        self.debug_tools: DebugTools | None = None
        self.desktop = None
        self._exit_started = None
        self._force_exit = False

        self._is_topmost = settings.window.always_on_top
        self._is_bottom = settings.window.mode == "desktop"
        self._background_key = COLOR_KEY
        self._drag_active = False
        self._drag_start_pos = (0, 0)
        self._window_start_pos = (0, 0)
        self._drag_direction = 0.0
        self._drag_intensity = 0.0
        self._animation_last_tick = time.perf_counter()
        self._physics_last_tick = time.perf_counter()
        self._mouse_hovered = False
        self._mouse_local = (0, 0)
        self._mouse_screen = None
        self._body_grab_point = None
        self._native_buttons: set[str] = set()
        self._hover_attention = HoverAttention()
        self._hover_foreground = win32gui.GetForegroundWindow()
        self._busy_cursors = {win32gui.LoadCursor(0, cursor) for cursor in
                              (win32con.IDC_IBEAM, win32con.IDC_HAND, win32con.IDC_SIZEALL,
                               win32con.IDC_SIZENS, win32con.IDC_SIZEWE)}
        self.mouse_interaction = MouseInteraction(
            buttons=self._mouse_buttons(),
            double_click_seconds=user32.GetDoubleClickTime() / 1000,
            double_click_distance=max(4, win32api.GetSystemMetrics(win32con.SM_CXDOUBLECLK) / 2),
        )
        self.animation_controller: AnimationController | None = None

        self.qt_app: Any = None
        self.tray_icon: Any = None
        self.tray_menu: Any = None
        self._settings_dialog: SettingsDialog | None = None
        self._topmost_action = None
        self._debug_action = None
        self._recording_action = None
        self.hotkey_manager: HotkeyManager | None = None

        self.logger = configure_logging()
        self._drag_active = False
        self._drag_start_pos = (0, 0)
        self._window_start_pos = (0, 0)
        # Estado do hot path pré-inicializado (evita hasattr/getattr por frame).
        size = self.settings.window.size
        self._physics_local = (size / 2, size - self.settings.physics.mascot_radius - 35)
        self._canvas_cooldown = 0.0
        self._fit_pose_cache = None

        self._init_pyside()
        self._create_panda_window()
        self._setup_win32()
        self._init_renderer()
        self._setup_mouse_hooks()
        if self.renderer and self.renderer.rig:
            self.animation_controller = AnimationController(self.renderer.rig)
            self.animation_controller.set_idle_personality(self.settings.behavior.idle_personality)
        if self.renderer:
            self.debug_tools = DebugTools(
                self,
                self._on_recording_changed,
                self.settings.hotkeys.toggle_debug,
            )
        self.music_listener = MusicListener(self.settings.music)
        self.music_listener.start()
        self._setup_tray()
        self._setup_timers()
        self._hotkey_callbacks = {
            "toggle_overlay": self.toggle_visibility,
            "open_settings": self.open_settings_dialog,
            "summon": self.summon_overlay,
            "toggle_debug": self.toggle_debug_overlay,
            "capture_frame": self.capture_debug_frame,
            "toggle_frame_recording": self.toggle_frame_recording,
        }
        self.hotkey_manager = HotkeyManager(
            self.settings.hotkeys.model_dump(), self._hotkey_callbacks
        )
        if self.hotkey_manager.unavailable_shortcuts:
            self.logger.warning(
                "Unavailable global shortcuts: %s",
                ", ".join(self.hotkey_manager.unavailable_shortcuts),
            )
        self._apply_window_state()
        self.taskMgr.doMethodLater(0.15, self._restore_z_order, "restore-z-order")
        self.taskMgr.doMethodLater(0.2, self._calibrate_background_key, "background-key")
        self._init_physics()
        icon = brand_dir() / "companion.ico"
        self.qt_app.setWindowIcon(QIcon(str(icon)))
        self.desktop = DesktopIntegration(self.hwnd, icon)

        self.logger.info("OverlayApp inicializado.")

    def _init_pyside(self) -> None:
        self.qt_app = QApplication.instance() or QApplication(sys.argv)
        self.qt_app.setApplicationName("SeJoga Companion")
        self.qt_app.setApplicationDisplayName("SeJoga Desktop Companion")
        self.qt_app.setOrganizationName("ArchVeketo")
        self.qt_app.setQuitOnLastWindowClosed(False)

    def _create_panda_window(self) -> None:
        wp = WindowProperties()
        wp.setSize(self.settings.window.size, self.settings.window.size)
        wp.setOrigin(0, 0)
        wp.setFullscreen(False)
        wp.setCursorHidden(False)
        wp.setTitle("SeJogaDesktopCompanion")

        fbprops = FrameBufferProperties()
        fbprops.setRgbColor(True)
        fbprops.setAlphaBits(8)
        fbprops.setDepthBits(24)
        fbprops.setStencilBits(8)
        fbprops.setMultisamples(4)

        self.openDefaultWindow(props=wp, fbprops=fbprops)

        self.win.setClearColor((1.0, 0.0, 1.0, 0.0))  # Zero alpha preserves MSAA coverage for chroma resolve.
        self.win.setClearColorActive(True)

        self.disableMouse()

    def _get_hwnd(self) -> int:
        """Extract integer HWND from Panda3D WindowHandle."""
        wh = self.win.getWindowHandle()
        # Try various WindowHandle API methods
        if hasattr(wh, 'getHandle'):
            return int(wh.getHandle())
        elif hasattr(wh, 'asInt'):
            return wh.asInt()
        elif hasattr(wh, '__int__'):
            return int(wh)
        elif hasattr(wh, 'handle'):
            return int(wh.handle)
        else:
            # String representation is typically a hex address like '0000000000360D5E'
            wh_str = str(wh).strip()
            if wh_str.startswith('0x') or all(c in '0123456789abcdefABCDEF' for c in wh_str):
                return int(wh_str, 16)
            return int(wh_str)

    def _setup_win32(self) -> None:
        self.hwnd = self._get_hwnd()

        ex_style = win32gui.GetWindowLong(self.hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_LAYERED | WS_EX_NOACTIVATE
        if self._is_topmost:
            ex_style |= WS_EX_TOPMOST
        win32gui.SetWindowLong(self.hwnd, GWL_EXSTYLE, ex_style)

        self._refresh_background_mode()
        self._update_z_order()

        with contextlib.suppress(Exception):
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

    def _refresh_background_mode(self) -> None:
        """Windows uses the final framebuffer color, after PBR tone mapping."""
        ex_style = win32gui.GetWindowLong(self.hwnd, GWL_EXSTYLE)
        if ex_style & WS_EX_TRANSPARENT:
            win32gui.SetWindowLong(self.hwnd, GWL_EXSTYLE, ex_style & ~WS_EX_TRANSPARENT)
        if self.debug_tools and self.debug_tools.visible:
            win32gui.SetLayeredWindowAttributes(self.hwnd, self._background_key, 255, LWA_ALPHA)
        else:
            win32gui.SetLayeredWindowAttributes(self.hwnd, self._background_key, 255, LWA_COLORKEY)

    def _calibrate_background_key(self, task: Task) -> int:
        if not win32gui.IsWindow(self.hwnd):
            return Task.done
        image = self.win.getScreenshot()
        if image:
            red, green, blue = bytes(image.getRamImageAs("RGB"))[:3]
            # Calibrate only the known magenta clear pixel after PBR tone mapping.
            if red > 128 and green < 20 and blue > 128:
                self._background_key = red | (green << 8) | (blue << 16)
                self._refresh_background_mode()
        return Task.done

    def _update_z_order(self) -> None:
        order = HWND_BOTTOM if self._is_bottom else HWND_TOPMOST if self._is_topmost else HWND_NOTOPMOST
        win32gui.SetWindowPos(self.hwnd, order, 0, 0, 0, 0,
                             SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def _restore_z_order(self, task: Task) -> int:
        if win32gui.IsWindow(self.hwnd):
            if self.desktop:
                self.desktop.apply_style()
            self._update_z_order()
        return Task.done

    def _apply_window_state(self) -> None:
        """Aplica tamanho, posição inicial e estilos definidos nas configurações."""
        size = self.settings.window.size
        start_position = self.settings.window.start_position
        if start_position is None:
            screen_w = win32api.GetSystemMetrics(0)
            screen_h = win32api.GetSystemMetrics(1)
            x = max(0, screen_w - size - 32)
            y = max(0, screen_h - size - 72)
        else:
            x, y = (int(start_position[0]), int(start_position[1]))

        # Panda applies pending window properties on its next frame. Keep its
        # requested origin in sync so it cannot overwrite the saved position.
        properties = WindowProperties()
        properties.setOrigin(x, y)
        properties.setSize(size, size)
        properties.setZOrder(
            WindowProperties.ZBottom if self._is_bottom else
            WindowProperties.ZTop if self._is_topmost else WindowProperties.ZNormal
        )
        self.win.requestProperties(properties)
        # SWP_NOZORDER | SWP_NOACTIVATE; z-order is applied separately below.
        win32gui.SetWindowPos(self.hwnd, 0, x, y, size, size, SWP_NOZORDER | SWP_NOACTIVATE)
        self._refresh_background_mode()
        self._update_z_order()

    def _init_renderer(self) -> None:
        # Panda3DRenderer is defined in this same file
        self.renderer = Panda3DRenderer(self, self._get_hwnd(),
                                       self.settings.window.size, self.settings.window.size)

    def _init_physics(self) -> None:
        """Inicializa sistema de física 2D (pymunk)."""
        if not self.settings.physics.enabled:
            return

        # Obtém dimensões da tela
        import win32api
        screen_w = win32api.GetSystemMetrics(0)
        screen_h = win32api.GetSystemMetrics(1)

        self.physics = create_physics(
            mascot_radius=self.settings.physics.mascot_radius,
            screen_width=screen_w,
            screen_height=screen_h,
            own_hwnd=self.hwnd,
            own_pid=os.getpid(),
            settings=self.settings
        )

        # Posiciona o mascote no centro inferior da janela
        size = self.settings.window.size
        self._physics_local = (size / 2, size - self.settings.physics.mascot_radius - 35)
        origin = win32gui.ClientToScreen(self.hwnd, (0, 0))
        self._set_physics_monitor((origin[0] + self._physics_local[0], origin[1] + self._physics_local[1]))
        self.physics.set_position(
            origin[0] + self._physics_local[0],
            origin[1] + self._physics_local[1],
        )
        self._last_rest_position = None
        self._was_grounded = False
        self.physics.on_collision = self._on_physics_collision

        # Configura callback de mudança de estado
        self.physics.on_state_change = self._on_physics_state_change

        # Adiciona task de física (120 Hz)
        self.taskMgr.add(self._physics_tick, "physics-tick", priority=10)

    def _on_physics_state_change(self, state) -> None:
        """Callback quando estado da física muda."""
        if not win32gui.IsWindow(self.hwnd):
            return
        if state.grounded and not self._was_grounded and self.animation_controller:
            self.animation_controller.interact("land")
        self._was_grounded = state.grounded
        x = round(state.position[0] - self._physics_local[0])
        y = round(state.position[1] - self._physics_local[1])
        try:
            win32gui.SetWindowPos(self.hwnd, 0, x, y, 0, 0,
                                 SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
        except win32gui.error as exc:
            if exc.winerror != 1400:
                raise
            return
        self.settings.window.start_position = (x, y)
        if state.grounded and math.hypot(*state.velocity) < 5 and self._last_rest_position != (x, y):
            self._last_rest_position = (x, y)
            self._persist_settings()

    def _set_physics_monitor(self, point) -> None:
        monitor = win32api.MonitorFromPoint(tuple(map(int, point)), 2)
        self.physics.set_bounds(win32api.GetMonitorInfo(monitor)["Work"])

    def _on_physics_collision(self, kind, velocity) -> None:
        self.logger.info("Physics %s velocity=%s", kind, velocity)
        if self.animation_controller:
            self.animation_controller.interact("hit", direction=max(-1, min(1, velocity[0] / 1000)),
                                               strength=min(2, math.hypot(*velocity) / 1200))

    def _physics_tick(self, task: Task) -> int:
        """Task de física - roda a 120 Hz."""
        if not self.physics:
            return Task.cont
        if not win32gui.IsWindow(self.hwnd):
            self.userExit()
            return Task.done

        now = time.perf_counter()
        dt = now - self._physics_last_tick
        self._physics_last_tick = now
        if not self._drag_active:
            self.physics.step(dt)
        return Task.cont

    def _sync_model_with_physics(self) -> None:
        """Sincroniza modelo 3D com estado da física."""
        if not self.physics or not self.renderer or not self.renderer.model_np:
            return

        state = self.physics.get_state()
        self.renderer.set_model_screen_position(*self._physics_local)

        vx, vy = state.velocity
        if not state.grounded and math.hypot(vx, vy) > 80:
            self.renderer.set_model_rotation(z=max(-20.0, min(20.0, -vx / 80)))
        else:
            self.renderer.set_model_rotation()

    def _animation_tick(self) -> None:
        if self._exit_started is not None:
            self._exit_tick()
            return
        if not self.renderer or not self.animation_controller:
            return

        now = time.perf_counter()
        dt = now - self._animation_last_tick
        self._animation_last_tick = now
        state = self.physics.get_state() if self.physics else None
        music = self.music_listener.snapshot if self.music_listener else None
        music_playing = bool(music and music.is_playing)
        music_intensity = music.audio_level if music else 0.0
        if music_playing and music_intensity == 0.0:
            music_intensity = 0.25
        self.animation_controller.dance_motion.override = self.settings.music.dance_style
        pose = self.animation_controller.update(
            dt,
            velocity=state.velocity if state else (0.0, 0.0),
            grounded=state.grounded if state else True,
            gravity_active=state.gravity_active if state else False,
            dragging=self._drag_active,
            grab_part=getattr(self, '_body_grab_part', 'body'),
            drag_direction=self._drag_direction,
            drag_intensity=self._drag_intensity,
            music_playing=music_playing,
            music_intensity=music_intensity,
            music_bass=music.bass_level if music else 0,
            music_bpm=music.bpm if music else None,
            dance_chance=self.settings.music.dance_chance,
            react_to_beat=self.settings.music.react_to_beat,
            beat_detected=bool(music and music.beat_detected),
            idle_enabled=self.settings.behavior.idle_animation,
            sleep_after_idle_seconds=self.settings.behavior.sleep_after_idle_seconds,
            hovered=self._mouse_hovered and self.settings.behavior.react_to_click,
            look_direction=(self._mouse_local[0] / self.renderer.width - 0.5) * 2.0,
            look_vertical=(self._mouse_local[1] / self.renderer.height - .52) * 2.0,
            pointer_position=self._mouse_screen,
        )
        self.renderer.apply_rig_pose(pose)
        self.renderer.lower_body.apply(self.animation_controller.leg_motion.pose,
                                       bool(not self._drag_active and (state.grounded if state else True)))
        self.renderer.apply_body_motion(
            self.animation_controller.body_motion.snapshot, self._body_grab_point,
            grounded=state.grounded if state else True, dragging=self._drag_active,
        )
        self.renderer.update_appendages(dt, self.animation_controller.appendage_remaining > 0)
        self._fit_pose_window(dt)
        if self.renderer.tentacle_director:
            mouse_world = Point3(
                (self._mouse_local[0] - self.renderer.width / 2) * self.renderer._view_width / self.renderer.width,
                0,
                self.renderer._view_target_z + (self.renderer.height / 2 - self._mouse_local[1]) * self.renderer._view_height / self.renderer.height,
            )
            mouse_local = self.renderer.model_np.getRelativePoint(self.render, mouse_world)
            self.renderer.tentacle_director.set_mouse(mouse_local, Vec3(0))
        if state:
            self._sync_model_with_physics()
        if self.debug_tools:
            self.debug_tools.update(dt)

    def set_debug_overlay(self, enabled: bool) -> None:
        if self.debug_tools:
            self.debug_tools.set_visible(enabled)
            self._refresh_background_mode()
            self._set_action_checked(self._debug_action, enabled)

    def toggle_debug_overlay(self) -> None:
        if self.debug_tools:
            self.set_debug_overlay(not self.debug_tools.visible)

    def capture_debug_frame(self) -> None:
        if not self.debug_tools:
            return
        path = self.debug_tools.capture_once()
        if self.tray_icon:
            if path:
                self.tray_icon.showMessage(
                    "Frame capturado",
                    str(path),
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )
            else:
                self.tray_icon.showMessage(
                    "Captura falhou",
                    "Veja o log para detalhes.",
                    QSystemTrayIcon.MessageIcon.Warning,
                    4000,
                )

    def set_frame_recording(self, enabled: bool) -> None:
        if self.debug_tools:
            self.debug_tools.set_recording(enabled)

    def toggle_frame_recording(self) -> None:
        if self.debug_tools:
            self.debug_tools.toggle_recording()

    def _on_recording_changed(self, recording: bool) -> None:
        self._refresh_background_mode()
        self._set_action_checked(self._recording_action, recording)
        if self.tray_icon:
            message = "Gravação iniciada (máximo 300 frames)." if recording else "Gravação encerrada."
            self.tray_icon.showMessage(
                "Diagnóstico",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    def _fit_pose_window(self, dt):
        """Expand the canvas around its center while preserving pixels per unit."""
        renderer = self.renderer
        if not renderer or not win32gui.IsWindow(self.hwnd):
            return
        bounds = renderer.model_np.getTightBounds(self.render)
        if hasattr(renderer, 'music_speaker') and not renderer.music_speaker.root.isHidden():
            speaker_bounds = renderer.music_speaker.root.getTightBounds(self.render)
            if bounds and speaker_bounds:
                bounds = (Vec3(*(min(bounds[0][i],speaker_bounds[0][i]) for i in range(3))),
                          Vec3(*(max(bounds[1][i],speaker_bounds[1][i]) for i in range(3))))
        if not bounds:
            return
        from panda3d.core import Point2, Point3, WindowProperties
        lens = self.cam.node().getLens()
        base = self.settings.window.size
        current = renderer.width
        # Reaproveita o `needed` do último frame quando o bounding box (e a
        # largura atual) não mudaram acima de um epsilon: a projeção dos 8
        # cantos é determinística, então o resultado seria o mesmo.
        snapshot = (
            round(bounds[0].x, 4), round(bounds[0].y, 4), round(bounds[0].z, 4),
            round(bounds[1].x, 4), round(bounds[1].y, 4), round(bounds[1].z, 4),
            current,
        )
        cached = self._fit_pose_cache
        if cached is not None and cached[0] == snapshot:
            needed = cached[1]
        else:
            projected = []
            for x in (bounds[0].x, bounds[1].x):
                for y in (bounds[0].y, bounds[1].y):
                    for z in (bounds[0].z, bounds[1].z):
                        pixel = Point2()
                        lens.project(self.cam.getRelativePoint(self.render, Point3(x,y,z)), pixel)
                        if math.isfinite(pixel.x) and math.isfinite(pixel.y):
                            projected.append((pixel.x*renderer.width/2, pixel.y*renderer.height/2))
            if not projected:
                return
            extent = max(max(abs(x),abs(y)) for x,y in projected)*2+32
            needed = base + math.ceil(max(0, extent-base)/64)*64
            needed = min(base*3, needed)
            self._fit_pose_cache = (snapshot, needed)
        self._canvas_cooldown = max(0, self._canvas_cooldown - dt)
        if needed == current or (needed < current and (self._drag_active or self._canvas_cooldown > 0)):
            return
        size = needed if needed > current else max(needed, current-64)
        shift = (size-current)//2
        left, top = win32gui.ClientToScreen(self.hwnd, (0,0))
        units = renderer._view_height/renderer.height
        lens.setFilmSize(units*size, units*size)
        renderer.width = renderer.height = size
        renderer._view_width = renderer._view_height = units*size
        local = self._physics_local
        self._physics_local = (local[0]+shift, local[1]+shift)
        if self._drag_active:
            self._window_start_pos = (self._window_start_pos[0]-shift, self._window_start_pos[1]-shift)
        renderer.set_model_screen_position(*self._physics_local)
        properties = WindowProperties()
        properties.setSize(size,size)
        properties.setOrigin(left-shift,top-shift)
        # Apply the native resize before the next draw; Panda otherwise keeps
        # a frame at the old framebuffer size while the lens has already grown.
        self.win.requestProperties(properties)
        self.graphicsEngine.openWindows()
        self.win.setClearColorActive(True)
        self.win.setClearDepthActive(True)
        win32gui.RedrawWindow(self.hwnd, None, None, 0x0001 | 0x0004 | 0x0080)
        self._canvas_cooldown = 1.0 if size > current else .15

    def _setup_tray(self) -> None:
        """Cria o ícone e o menu da bandeja do sistema."""
        icon_path = brand_dir() / "companion.ico"
        icon = QIcon(str(icon_path))
        if icon.isNull():
            icon = QIcon(str(icon_path.with_suffix(".png")))
        self.tray_icon = QSystemTrayIcon(icon, self.qt_app)
        self.tray_icon.setToolTip("SeJoga Desktop Companion")

        self.tray_menu = QMenu()
        toggle_action = self.tray_menu.addAction("Mostrar / ocultar")
        toggle_action.triggered.connect(lambda _checked=False: self.toggle_visibility())

        self.tray_menu.addSeparator()
        dance_preview = self.tray_menu.addMenu('Prévia de dança (sem som)')
        for style, label in (('head_bob','Head bob'), ('hip_hop','Hip hop'), ('rock','Rock'), ('breakdance','Breakdance')):
            dance_preview.addAction(label).triggered.connect(
                lambda _checked=False, style=style: self.animation_controller.preview_dance(style))

        self._topmost_action = self.tray_menu.addAction("Sempre no topo")
        self._topmost_action.setCheckable(True)
        self._topmost_action.setChecked(self._is_topmost)
        self._topmost_action.toggled.connect(self.set_topmost)

        settings_action = self.tray_menu.addAction("Configurações...")
        settings_action.triggered.connect(lambda _checked=False: self.open_settings_dialog())

        debug_shortcut = self.settings.hotkeys.toggle_debug.upper()
        self._debug_action = self.tray_menu.addAction(f"Diagnóstico ({debug_shortcut})")
        self._debug_action.setCheckable(True)
        self._debug_action.toggled.connect(self.set_debug_overlay)
        capture_action = self.tray_menu.addAction("Capturar frame (Ctrl+Alt+P)")
        capture_action.triggered.connect(lambda _checked=False: self.capture_debug_frame())
        self._recording_action = self.tray_menu.addAction("Gravar frames (Ctrl+Alt+R)")
        self._recording_action.setCheckable(True)
        self._recording_action.toggled.connect(self.set_frame_recording)

        self.tray_menu.addSeparator()
        personality_menu = self.tray_menu.addMenu("Personalidade do idle")
        personality_group = QActionGroup(personality_menu)
        personality_group.setExclusive(True)
        self._personality_actions = {}
        for value, label in (
            ("auto", "Automática"),
            ("calm", "Tranquila"),
            ("curious", "Curiosa"),
            ("playful", "Brincalhona"),
            ("shy", "Tímida"),
            ("confident", "Confiante"),
            ("street", "Street groove · Bomb Rush"),
            ("fighter", "Guarda e provocação · Lethal League"),
            ("rhythm", "Ritmada · Hi-Fi Rush"),
            ("stylish", "Estilosa · Persona 5"),
        ):
            action = personality_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.settings.behavior.idle_personality == value)
            personality_group.addAction(action)
            action.triggered.connect(
                lambda _checked=False, personality=value: self._set_idle_personality(personality)
            )
            self._personality_actions[value] = action

        for label, kind in (("Acenar", "wave"), ("Soltar os ombros", "stretch"), ("Mostrar tentáculos", "peek"), ("Espirro de tentáculos", "sneeze")):
            action = self.tray_menu.addAction(label)
            action.triggered.connect(lambda _checked=False, kind=kind: self.animation_controller.interact(kind))
        self.tray_menu.addSeparator()
        quit_action = self.tray_menu.addAction("Encerrar Mário")
        quit_action.triggered.connect(lambda _checked=False: self.quit_app())

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.setVisible(True)
        self.tray_icon.show()
        self.tray_registration = TrayRegistration(icon_path)
        self.taskMgr.doMethodLater(.75, self._ensure_tray_registration, "tray-registration")
        QApplication.processEvents()
        if icon.isNull() or not self.tray_icon.isVisible():
            self.logger.warning("System tray icon did not become visible (icon=%s, tray_available=%s)",
                                icon_path, QSystemTrayIcon.isSystemTrayAvailable())

    def _ensure_tray_registration(self, task):
        if self._exit_started is not None:
            return Task.done
        status = self.tray_registration.ensure()
        if not status["registered"]:
            self.logger.warning("Tray icon has no Shell registration: %s", status)
        task.delayTime = 15.0 if status["registered"] else 3.0
        return Task.again

    def _set_idle_personality(self, personality: str) -> None:
        """Aplica e salva a personalidade sem interromper o gesto atual."""
        if personality != "auto" and personality not in IdlePersonality:
            return
        self.settings.behavior.idle_personality = personality
        if self.animation_controller:
            self.animation_controller.set_idle_personality(personality)
        self._persist_settings()

    def _setup_timers(self) -> None:
        """Agenda a animação e bombeia os eventos do Qt junto ao loop Panda3D."""
        from panda3d.core import ClockObject
        clock = ClockObject.getGlobalClock()
        clock.setMode(ClockObject.MLimited)
        clock.setFrameRate(self.settings.window.fps)
        self.taskMgr.add(self._process_qt_events, "qt-event-pump", sort=40)
        self.taskMgr.add(self._animate_frame, "animation-frame", sort=45)

    def _animate_frame(self, task):
        self._animation_tick()
        return Task.cont

    def _process_qt_events(self, task: Task) -> int:
        QApplication.processEvents()
        if self.desktop:
            for request in self.desktop.requests[:]:
                self.desktop.requests.remove(request)
                if request == "quit":
                    self.quit_app()
                elif request == "settings" and self._exit_started is None:
                    self.open_settings_dialog()
                elif request == "peek" and self._exit_started is None:
                    self.animation_controller.interact("peek")
                elif request.startswith('dance:') and self._exit_started is None:
                    self.animation_controller.preview_dance(request.split(':',1)[1])
                elif request == 'capture' and self.debug_tools:
                    self.debug_tools.capture_once()
        return Task.cont

    def _on_tray_activated(self, reason) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility()

    def _setup_mouse_hooks(self) -> None:
        for event, button in (("mouse1", "left"), ("mouse2", "middle"), ("mouse3", "right")):
            self.accept(event, self._native_mouse_button, [button, True])
            self.accept(event + "-up", self._native_mouse_button, [button, False])
        self.taskMgr.add(self._mouse_poll, "mouse-poll")

    def _native_mouse_button(self, button: str, pressed: bool) -> None:
        if self._exit_started is not None:
            return
        if pressed:
            self._native_buttons.add(button)
            if win32gui.IsWindow(self.hwnd) and self._settings_dialog is None:
                win32gui.SetCapture(self.hwnd)
        else:
            self._native_buttons.discard(button)
            if not self._native_buttons and win32gui.GetCapture() == self.hwnd:
                win32gui.ReleaseCapture()
        self.logger.info("Native mouse %s %s", button, "down" if pressed else "up")

    def _mouse_buttons(self) -> frozenset[str]:
        return frozenset(self._native_buttons) | frozenset(
            name for name, key in (
                ("left", win32con.VK_LBUTTON),
                ("right", win32con.VK_RBUTTON),
                ("middle", win32con.VK_MBUTTON),
            ) if win32api.GetAsyncKeyState(key) & 0x8000
        )

    def _mouse_poll(self, task: Task) -> int:
        if not win32gui.IsWindow(self.hwnd):
            return Task.done
        try:
            position = win32gui.GetCursorPos()
        except win32gui.error as exc:
            if exc.winerror == 5:
                # The input desktop is unavailable while Windows is locked or
                # showing a secure desktop. Resume polling when it returns.
                return Task.cont
            raise
        self._mouse_screen = position
        buttons = self._mouse_buttons()
        self._mouse_local = win32gui.ScreenToClient(self.hwnd, position)
        enabled = bool(win32gui.IsWindowVisible(self.hwnd)) and self._settings_dialog is None
        enabled = enabled and not bool(win32api.GetAsyncKeyState(win32con.VK_ESCAPE) & 0x8000)
        # Com o mascote oculto/desabilitado, hit e hover são sempre falsos:
        # pula o hit_test (traversal de colisão), a varredura de ~43 teclas e as
        # chamadas Win32 de hover, que não alterariam o resultado.
        hit = enabled and self.renderer.hit_test(*self._mouse_local)
        newly_pressed = buttons - self.mouse_interaction.buttons
        if newly_pressed:
            self.logger.info(
                "Mouse press buttons=%s hit=%s target=%s own=%s",
                sorted(newly_pressed), hit, win32gui.WindowFromPoint(position), self.hwnd,
            )
        if hit and not self._drag_active:
            target = win32gui.WindowFromPoint(position)
            hit = target == self.hwnd or win32gui.IsChild(self.hwnd, target)
        if hit and "left" in newly_pressed:
            self._body_grab_point = Vec3(self.renderer._pick_point_model)
            self._body_grab_part = getattr(self.renderer, '_pick_part', 'body')
        events = self.mouse_interaction.update(
            position, buttons, hit=hit, enabled=enabled,
            allow_drag=self.settings.behavior.react_to_drag,
            allow_click=self.settings.behavior.react_to_click,
        )
        previous_hover = self._mouse_hovered
        if not enabled:
            # Hover forçado a falso; mantém o foreground sincronizado para a
            # próxima reavaliação quando o mascote voltar a ficar interativo.
            self._hover_foreground = win32gui.GetForegroundWindow()
            self._mouse_hovered = False
        else:
            dx = (self._mouse_local[0] - self.renderer.width * .5) / (self.renderer.width * .95)
            dy = (self._mouse_local[1] - self.renderer.height * .52) / (self.renderer.height * .85)
            foreground = win32gui.GetForegroundWindow()
            typing = foreground != self.hwnd and any(
                win32api.GetAsyncKeyState(key) & 0x8000 for key in
                (*range(0x30, 0x5B), win32con.VK_SPACE, win32con.VK_BACK, win32con.VK_RETURN)
            )
            target = win32gui.WindowFromPoint(position)
            target_class = win32gui.GetClassName(target) if target else ""
            busy_cursor = target != self.hwnd and (
                win32gui.GetCursorInfo()[1] in self._busy_cursors or
                target_class in ("#32768", "Button", "Edit", "ComboBox", "ListBox",
                                 "SysTreeView32", "SysListView32", "ToolbarWindow32") or "Popup" in target_class
            )
            allowed = self._hover_attention.update(
                time.perf_counter(),
                external_press=bool(buttons) and not self.mouse_interaction.has_press and not self._drag_active,
                typing=bool(typing), busy_cursor=busy_cursor,
                focus_changed=foreground != self._hover_foreground,
            )
            self._hover_foreground = foreground
            self._mouse_hovered = allowed and not self._drag_active and dx*dx + dy*dy <= 1
        if self._mouse_hovered and not previous_hover and self.animation_controller:
            self.animation_controller.interact("hover_enter")
        for event in events:
            if event.kind in ("hover_enter", "click", "double_click", "pet", "poke"):
                if (self.settings.behavior.react_to_click and self.animation_controller
                        and (event.kind != "hover_enter" or self._mouse_hovered)):
                    self.animation_controller.interact(event.kind)
            elif event.kind == "drag_start":
                self._drag_active = True
                self._drag_start_pos = self.mouse_interaction.press_position
                self._window_start_pos = win32gui.GetWindowRect(self.hwnd)[:2]
                if self.physics:
                    self.physics.start_drag(*self._drag_start_pos)
                if self.animation_controller:
                    self.animation_controller.interact("drag_start")
            elif event.kind in ("drag_move", "drag_end"):
                dx = position[0] - self._drag_start_pos[0]
                dy = position[1] - self._drag_start_pos[1]
                self._drag_direction = max(-1.0, min(1.0, dx / 80.0))
                self._drag_intensity = min(1.0, math.hypot(dx, dy)/160)
                win32gui.SetWindowPos(
                    self.hwnd, 0,
                    self._window_start_pos[0] + dx, self._window_start_pos[1] + dy,
                    0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE,
                )
                if self.physics:
                    self.physics.update_drag(*position)
            if event.kind in ("drag_end", "drag_cancel"):
                if self.physics:
                    self._set_physics_monitor(self.physics.get_state().position)
                    self.physics.end_drag(cancel=event.kind == "drag_cancel")
                self._drag_active = False
                self._drag_direction = 0.0
                self._drag_intensity = 0.0
                self.settings.window.start_position = win32gui.GetWindowRect(self.hwnd)[:2]
                self._persist_settings()
            if event.kind != "drag_move":
                self.logger.info("Mouse %s at %s", event.kind, position)
        return Task.cont

    def toggle_visibility(self) -> None:
        if win32gui.IsWindowVisible(self.hwnd):
            win32gui.ShowWindow(self.hwnd, 0)
        else:
            win32gui.ShowWindow(self.hwnd, 5)

    def summon_overlay(self) -> None:
        """Mostra o mascote e o traz para frente sem alterar sua posição salva."""
        self._is_bottom = False
        self._is_topmost = True
        self.settings.window.mode = "overlay"
        self.settings.window.always_on_top = True
        self._update_z_order()
        self._set_action_checked(self._topmost_action, True)
        win32gui.ShowWindow(self.hwnd, 5)
        self._persist_settings()

    def set_topmost(self, checked: bool) -> None:
        self._is_topmost = checked
        self._is_bottom = False
        self._update_z_order()
        self.settings.window.always_on_top = checked
        self.settings.window.mode = "overlay"
        self._persist_settings()

    def set_bottom(self, checked: bool) -> None:
        self._is_bottom = checked
        self._is_topmost = False
        self._update_z_order()
        self.settings.window.mode = "desktop" if checked else "overlay"
        self._persist_settings()

    def open_settings_dialog(self) -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.show()
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return

        dialog = SettingsDialog(self.settings)
        dialog.settings_applied.connect(self._apply_settings)
        dialog.finished.connect(lambda _result: setattr(self, "_settings_dialog", None))
        self._settings_dialog = dialog
        dialog.show()

    def _apply_settings(self, updated: Settings) -> None:
        previous = self.settings
        updated.window.start_position = previous.window.start_position
        restart_required = (
            previous.window.size != updated.window.size
            or previous.physics != updated.physics
        )
        music_changed = previous.music != updated.music
        hotkeys_changed = previous.hotkeys != updated.hotkeys

        self.settings = updated
        self.settings_obj = updated
        self._is_bottom = updated.window.mode == "desktop"
        self._is_topmost = updated.window.always_on_top and not self._is_bottom
        self._update_z_order()
        self._set_action_checked(self._topmost_action, self._is_topmost)
        if hotkeys_changed:
            if self.hotkey_manager:
                self.hotkey_manager.close()
            self.hotkey_manager = HotkeyManager(
                updated.hotkeys.model_dump(), self._hotkey_callbacks
            )
            unavailable = self.hotkey_manager.unavailable_shortcuts
            if unavailable:
                self.logger.warning(
                    "Unavailable global shortcuts after settings update: %s",
                    ", ".join(unavailable),
                )
                if self.tray_icon:
                    self.tray_icon.showMessage(
                        "Atalho indisponível",
                        "Já está sendo usado por outro programa: " + ", ".join(unavailable),
                        QSystemTrayIcon.MessageIcon.Warning,
                        6000,
                    )
        if self.renderer:
            self.renderer.set_visual_scale(updated.window.scale)
            self.renderer.set_outline_settings(updated.window)
        if self.animation_controller:
            self.animation_controller.set_idle_personality(updated.behavior.idle_personality)
        for value, action in self._personality_actions.items():
            self._set_action_checked(action, value == updated.behavior.idle_personality)

        if music_changed:
            if self.music_listener:
                self.music_listener.stop()
            self.music_listener = MusicListener(updated.music)
            self.music_listener.start()

        if restart_required and self.tray_icon:
            self.tray_icon.showMessage(
                "Configurações salvas",
                "Tamanho da janela e física serão aplicados ao reiniciar o companion.",
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )

    @staticmethod
    def _set_action_checked(action, checked: bool) -> None:
        if action is None:
            return
        previous = action.blockSignals(True)
        action.setChecked(checked)
        action.blockSignals(previous)

    def _persist_settings(self) -> None:
        try:
            save_settings(self.settings)
        except OSError as exc:
            self.logger.error("Falha ao salvar configuração: %s", exc)

    def quit_app(self) -> None:
        self.userExit()

    def userExit(self) -> None:
        if not self._force_exit and self.renderer and win32gui.IsWindow(self.hwnd):
            if self._exit_started is None:
                self._begin_exit()
            return
        self._finish_exit()

    def _begin_exit(self):
        self._persist_settings()
        self._exit_started = time.perf_counter()
        self.taskMgr.remove("physics-tick")
        self.taskMgr.remove("mouse-poll")
        self._native_buttons.clear()
        if win32gui.GetCapture() == self.hwnd:
            win32gui.ReleaseCapture()
        if self._settings_dialog:
            self._settings_dialog.reject()
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOWNOACTIVATE)
        rect = win32gui.GetWindowRect(self.hwnd)
        bounds = (win32api.GetSystemMetrics(76), win32api.GetSystemMetrics(77),
                  win32api.GetSystemMetrics(76) + win32api.GetSystemMetrics(78),
                  win32api.GetSystemMetrics(77) + win32api.GetSystemMetrics(79))
        self._exit_motion = ExitAnimation(rect[:2], self.settings.window.size, bounds)
        self.renderer.begin_exit_effect()
        self.logger.info("Exit animation started")

    def _exit_tick(self):
        if not win32gui.IsWindow(self.hwnd):
            self._force_exit = True
            self._finish_exit()
            return
        frame = self._exit_motion.sample(time.perf_counter() - self._exit_started)
        self.renderer.set_exit_rotation(frame.roll)
        win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOPMOST, frame.x, frame.y, 0, 0,
                             SWP_NOSIZE | SWP_NOACTIVATE)
        if self.debug_tools:
            self.debug_tools.update(1 / self.settings.window.fps)
        if frame.done:
            self._force_exit = True
            self._finish_exit()

    def _finish_exit(self):
        self.taskMgr.remove("physics-tick")
        self.taskMgr.remove("mouse-poll")
        if self.desktop:
            self.desktop.close()
            self.desktop = None
        self.taskMgr.remove("animation-frame")
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.hide()
        if hasattr(self, "tray_registration"):
            self.tray_registration.close()
        if self.music_listener:
            self.music_listener.stop()
        if self.debug_tools:
            self.debug_tools.close()
        if self.hotkey_manager:
            self.hotkey_manager.close()
        self._persist_settings()
        ShowBase.userExit(self)

    def run(self) -> None:
        self.logger.info("Iniciando SeJogaDesktopCompanion...")
        try:
            ShowBase.run(self)
        except KeyboardInterrupt:
            self.userExit()


def create_app(settings: Settings | None = None):
    if settings is None:
        settings = load_settings()
    return OverlayApp(settings)


def main() -> int:
    settings = load_settings()
    app = OverlayApp(settings)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
