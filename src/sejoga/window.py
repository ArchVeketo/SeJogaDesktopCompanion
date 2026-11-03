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

import sys
import os
from pathlib import Path
from typing import Optional, Tuple

# Win32 API
import win32gui
import win32con
import win32api
import ctypes
from ctypes import wintypes

# Panda3D - configurar ANTES de importar ShowBase
from panda3d.core import loadPrcFileData

loadPrcFileData("", "window-type none")
loadPrcFileData("", "framebuffer-alpha 1")
loadPrcFileData("", "framebuffer-multisample 1")
loadPrcFileData("", "multisamples 4")
loadPrcFileData("", "win-size 480 480")
loadPrcFileData("", "win-origin 0 0")
loadPrcFileData("", "undecorated 1")
loadPrcFileData("", "cursor-hidden 0")
loadPrcFileData("", "framebuffer-alpha 1")
loadPrcFileData("", "framebuffer-multisample 1")

# Panda3D imports (depois do loadPrcFileData)
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import (
    WindowProperties, FrameBufferProperties, GraphicsPipe,
    GraphicsWindow, GraphicsOutput, Texture, CardMaker, NodePath,
    LColor, LVecBase3, LVecBase4, Vec3, Vec4,
    GraphicsPipeSelection, FrameBufferProperties, WindowProperties,
    PerspectiveLens, AmbientLight, DirectionalLight, PointLight,
    AntialiasAttrib, TransparencyAttrib, ColorBlendAttrib,
    ConfigVariableBool, ConfigVariableInt,
    AntialiasAttrib, loadPrcFileData
)
from direct.task import Task
from direct.showbase.ShowBase import ShowBase

# Panda3D GLTF loader
import gltf

# PySide6 (apenas para system tray)
from PySide6.QtCore import QTimer, QPoint, QObject
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QCursor

# Win32 API
import win32gui
import win32con
import win32api
import ctypes
from ctypes import wintypes

# Project imports
from .assets import resolve_model
from .model import load_model
from .rig import Rig, ALL_GROUPS
from .config import load_settings, Settings

# ============================================================
# Win32 Constants & Helpers
# ============================================================

GWL_EXSTYLE = -20
GWL_STYLE = -16

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000

LWA_COLORKEY = 0x00000001
LWA_ALPHA = 0x00000002

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
HWND_BOTTOM = 1

SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040

# Magenta color key (0xFF00FF = RGB(255, 0, 255)) - BGR format for Win32
COLOR_KEY = 0x00FF00FF

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

def set_window_ex_style(hwnd: int, add_flags: int = 0, remove_flags: int = 0) -> None:
    """Modifica extended window style."""
    ex_style = win32gui.GetWindowLong(hwnd, -20)  # GWL_EXSTYLE
    ex_style = (ex_style | add_flags) & ~remove_flags
    win32gui.SetWindowLong(hwnd, -20, ex_style)

def set_layered_window_attributes(hwnd: int, color_key: int = 0x00FF00FF, alpha: int = 255, flags: int = 0x00000001) -> bool:
    """Define color key e/ou alpha para layered window."""
    return ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, color_key, alpha, flags)

def set_window_pos_zorder(hwnd: int, zorder: int) -> bool:
    """Define Z-order: HWND_TOPMOST (-1), HWND_NOTOPMOST (-2), HWND_BOTTOM (1)."""
    return ctypes.windll.user32.SetWindowPos(hwnd, zorder, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0010)

# Magenta color key (0xFF00FF = RGB(255, 0, 255)) - BGR format for Win32
COLOR_KEY = 0x00FF00FF

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

def set_window_ex_style(hwnd: int, add_flags: int = 0, remove_flags: int = 0) -> None:
    ex_style = win32gui.GetWindowLong(hwnd, -20)
    ex_style = (ex_style | add_flags) & ~remove_flags
    win32gui.SetWindowLong(hwnd, -20, ex_style)

def set_layered_window_attributes(hwnd: int, color_key: int = 0x00FF00FF, alpha: int = 255, flags: int = 0x00000001) -> bool:
    return ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, color_key, alpha, flags)

def set_window_pos_zorder(hwnd: int, zorder: int) -> bool:
    return ctypes.windll.user32.SetWindowPos(hwnd, zorder, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0010)

COLOR_KEY = 0x00FF00FF

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

# ============================================================
# Panda3D Renderer
# ============================================================

class Panda3DRenderer:
    """Encapsula Panda3D render e modelo."""
    
    def __init__(self, showbase: ShowBase, hwnd: int, width: int, height: int):
        self.showbase = showbase
        self.hwnd = hwnd
        self.width = width
        self.height = height
        self.model_np: Optional[NodePath] = None
        self.rig: Optional[Rig] = None
        self.model_np: Optional[NodePath] = None
        
        self._setup_scene()
        self._load_model()
    
    def _setup_scene(self) -> None:
        render = self.showbase.render
        render.setShaderAuto()
        render.setAntialias(1)  # AntialiasAttrib.MMultisample
        
        # Câmera
        cam = self.showbase.cam
        cam.setPos(0, -15, 2)
        cam.lookAt(0, 0, 1)
        
        # Lens
        from panda3d.core import PerspectiveLens
        lens = PerspectiveLens()
        lens.setFov(45)
        lens.setAspectRatio(self.width / self.height)
        lens.setNear(0.1)
        lens.setFar(100)
        self.showbase.cam.node().setLens(lens)
        
        # Iluminação
        from panda3d.core import AmbientLight, DirectionalLight
        ambient = AmbientLight("ambient")
        ambient.setColor((0.4, 0.4, 0.4, 1))
        ambient_np = self.showbase.render.attachNewNode(ambient)
        self.showbase.render.setLight(ambient_np)
        
        dirlight = DirectionalLight("dirlight")
        dirlight.setColor((0.8, 0.8, 0.8, 1))
        dirlight_np = self.showbase.render.attachNewNode(dirlight)
        dirlight_np.setHpr(-45, -45, 0)
        self.showbase.render.setLight(dirlight_np)
        
        # SimplePBR
        try:
            from panda3d.simplepbr import simplepbr
            simplepbr(use_normal_maps=False, use_emission_maps=False, max_lights=8)
        except ImportError:
            pass
    
    def _load_model(self) -> None:
        model_path = resolve_model()
        model = load_model(model_path)
        rig = Rig.from_model(model)
        
        if rig.missing:
            print(f"⚠️ Grupos de rig ausentes: {rig.missing}")
        
        self.rig = rig
        
        # Carrega modelo via panda3d_gltf loader
        loader = gltf.get_loader()
        model_np = loader.load_model(str(resolve_model()))
        model_np.reparentTo(self.showbase.render)
        model_np.setScale(1.0)
        model_np.setPos(0, 0, -0.5)
        self.model_np = model_np
        
        self._apply_rig_to_model()
    
    def _apply_rig_to_model(self) -> None:
        if not self.model_np or not self.rig:
            return
        
        for group_name in self.rig.groups:
            node = self.model_np.find(f"**/{group_name}")
            if not node.isEmpty():
                pass
    
    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        lens = self.showbase.cam.node().getLens()
        if hasattr(lens, 'setAspectRatio'):
            lens.setAspectRatio(width / height)
    
    def set_model_rotation(self, x: float = 0, y: float = 0, z: float = 0) -> None:
        if hasattr(self, 'model_np') and self.model_np:
            self.model_np.setHpr(y, x, z)
    
    def set_model_position(self, x: float, y: float, z: float) -> None:
        if hasattr(self, 'model_np') and self.model_np:
            self.model_np.setPos(x, y, z)
    
    def apply_rig_pose(self, pose_dict: dict) -> None:
        if not self.model_np:
            return
        
        for group_name, rotation in pose_dict.items():
            node = self.model_np.find(f"**/{group_name}")
            if not node.isEmpty():
                x, y, z = rotation
                node.setHpr(y, x, z)


# ============================================================
# OverlayApp - Main Application
# ============================================================

class OverlayApp(ShowBase):
    """Aplicação principal - Panda3D ShowBase + Win32 layered window + PySide6 tray."""
    
    def __init__(self, settings: Settings):
        ShowBase.__init__(self, windowType="none")
        
        self.settings = settings
        self.settings_obj = settings
        self.renderer: Optional = None
        
        self._is_topmost = settings.window.always_on_top
        self._is_bottom = settings.window.mode == "desktop"
        self._click_through = settings.window.click_through_transparent
        self._drag_active = False
        self._drag_start_pos = (0, 0)
        self._window_start_pos = (0, 0)
        
        self.qt_app: Optional = None
        self.tray_icon: Optional = None
        self.tray_menu: Optional = None
        
        self._drag_active = False
        self._drag_start_pos = (0, 0)
        self._window_start_pos = (0, 0)
        
        self._init_pyside()
        self._create_panda_window()
        self._setup_win32()
        self._init_renderer()
        self._setup_tray()
        self._setup_timers()
        self._apply_window_state()
        
        print("✅ OverlayApp inicializado!")
    
    def _init_pyside(self) -> None:
        self.qt_app = QApplication.instance() or QApplication(sys.argv)
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
        
        self.win.setClearColor((1.0, 0.0, 1.0, 1.0))  # Magenta
        self.win.setClearColorActive(True)
        
        self.disableMouse()
    
    def _setup_win32(self) -> None:
        self.hwnd = int(self.win.getWindowHandle())
        
        ex_style = win32gui.GetWindowLong(self.hwnd, -20)
        ex_style |= 0x00080000 | 0x08000000  # WS_EX_LAYERED | WS_EX_NOACTIVATE
        if self._is_topmost:
            ex_style |= 0x00000008
        win32gui.SetWindowLong(self.hwnd, -20, ex_style)
        
        ctypes.windll.user32.SetLayeredWindowAttributes(
            self.hwnd, 0x00FF00FF, 255, 0x00000001
        )
        
        self._update_click_through()
        self._update_z_order()
        
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            pass
    
    def _update_click_through(self) -> None:
        ex_style = win32gui.GetWindowLong(self.hwnd, -20)
        if self._click_through:
            win32gui.SetWindowLong(self.hwnd, -20, ex_style | 0x00000020)
        else:
            win32gui.SetWindowLong(self.hwnd, -20, ex_style & ~0x00000020)
    
    def _update_z_order(self) -> None:
        if self._is_bottom:
            ctypes.windll.user32.SetWindowPos(self.hwnd, 1, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0010)
        elif self._is_topmost:
            ctypes.windll.user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0010)
        else:
            ctypes.windll.user32.SetWindowPos(self.hwnd, -2, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0010)
    
    def _init_renderer(self) -> None:
        from .renderer import Panda3DRenderer
        self.renderer = Panda3DRenderer(self, int(self.win.getWindowHandle()), 
                                       self.settings.window.size, self.settings.window.size)
    
    def _setup_tray(self) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon, QMenu
        from PySide6.QtGui import QIcon
        
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("⚠️ System tray não disponível")
            return
        
        self.tray_icon = QSystemTrayIcon()
        
        icon_path = Path(__file__).parent.parent.parent / "assets" / "brand" / "mascot-full.png"
        if icon_path.exists():
            self.tray_icon.setIcon(QIcon(str(icon_path)))
        else:
            app = QApplication.instance()
            if app:
                from PySide6.QtWidgets import QStyle
                self.tray_icon.setIcon(app.style().standardIcon(0))  # SP_ComputerIcon
        
        self.tray_icon.setToolTip("SeJogaDesktopCompanion - Mário")
        
        from PySide6.QtWidgets import QMenu
        self.tray_menu = QMenu()
        
        show_action = self.tray_menu.addAction("Mostrar/Ocultar")
        show_action.triggered.connect(self.toggle_visibility)
        
        self.tray_menu.addSeparator()
        
        toggle_topmost = self.tray_menu.addAction("Sempre no Topo")
        toggle_topmost.setCheckable(True)
        toggle_topmost.setChecked(self._is_topmost)
        toggle_topmost.toggled.connect(self.set_topmost)
        
        toggle_bottom = self.tray_menu.addAction("Modo Desktop (Atrás)")
        toggle_bottom.setCheckable(True)
        toggle_bottom.setChecked(self._is_bottom)
        toggle_bottom.toggled.connect(self.set_bottom)
        
        self.tray_menu.addSeparator()
        
        settings_action = self.tray_menu.addAction("Configurações")
        # settings_action.triggered.connect(self.show_settings)
        
        self.tray_menu.addSeparator()
        
        quit_action = self.tray_menu.addAction("Sair")
        quit_action.triggered.connect(self.quit_app)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()
    
    def _setup_timers(self) -> None:
        from PySide6.QtCore import QTimer
        self.animation_timer = QTimer()
        self.animation_timer.setInterval(16)
        self.animation_timer.timeout.connect(self._animation_tick)
        self.animation_timer.start()
    
    def _apply_window_state(self) -> None:
        pos = self.settings.window.start_position
        if pos:
            win32gui.SetWindowPos(self.hwnd, 0, pos[0], pos[1], 0, 0, 
                                 0x0001 | 0x0002 | 0x0010)
        else:
            import win32api
            screen_w = win32api.GetSystemMetrics(0)
            screen_h = win32api.GetSystemMetrics(1)
            size = self.settings.window.size
            win32gui.SetWindowPos(self.hwnd, 0, 
                                 screen_w - self.settings.window.size - 20, 
                                 screen_h - self.settings.window.size - 20, 
                                 0, 0, 0x0001 | 0x0002 | 0x0010)
    
    def _animation_tick(self) -> None:
        QApplication.processEvents()
        if self.renderer and self.renderer.rig:
            pass
    
    def _on_tray_activated(self, reason) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility()
    
    def _setup_mouse_hooks(self) -> None:
        self.taskMgr.add(self._mouse_poll, "mouse-poll")
    
    def _mouse_poll(self, task: Task) -> int:
        import win32api
        import win32con
        
        left_down = win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000
        
        if left_down and not self._drag_active:
            self._drag_active = True
            x, y = win32gui.GetCursorPos()
            self._drag_start_pos = (x, y)
            self._window_start_pos = win32gui.GetWindowRect(self.hwnd)[:2]
        
        elif not left_down and self._drag_active:
            self._drag_active = False
            rect = win32gui.GetWindowRect(self.hwnd)
            self.settings.window.start_position = [rect[0], rect[1]]
        
        elif self._drag_active:
            x, y = win32gui.GetCursorPos()
            dx = x - self._drag_start_pos[0]
            dy = y - self._drag_start_pos[1]
            new_x = self._window_start_pos[0] + dx
            new_y = self._window_start_pos[1] + dy
            win32gui.SetWindowPos(self.hwnd, 0, new_x, new_y, 0, 0, 
                                 0x0001 | 0x0002 | 0x0010)
        
        return Task.cont
    
    def toggle_visibility(self) -> None:
        if win32gui.IsWindowVisible(self.hwnd):
            win32gui.ShowWindow(self.hwnd, 0)
        else:
            win32gui.ShowWindow(self.hwnd, 5)
    
    def set_topmost(self, checked: bool) -> None:
        self._is_topmost = checked
        self._is_bottom = False
        self._update_z_order()
        self.settings.window.always_on_top = checked
        self.settings.window.mode = "overlay"
    
    def set_bottom(self, checked: bool) -> None:
        self._is_bottom = checked
        self._is_topmost = False
        self._update_z_order()
        self.settings.window.mode = "desktop" if checked else "overlay"
    
    def set_click_through(self, enabled: bool) -> None:
        self._click_through = enabled
        self._update_click_through()
        self.settings.window.click_through_transparent = enabled
    
    def toggle_visibility(self) -> None:
        if win32gui.IsWindowVisible(self.hwnd):
            win32gui.ShowWindow(self.hwnd, 0)
        else:
            win32gui.ShowWindow(self.hwnd, 5)
    
    def quit_app(self) -> None:
        self.userExit()
    
    def userExit(self) -> None:
        if hasattr(self, 'animation_timer') and self.animation_timer:
            self.animation_timer.stop()
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.hide()
        ShowBase.userExit(self)
    
    def run(self) -> None:
        print("🚀 Iniciando SeJogaDesktopCompanion...")
        try:
            self.main_loop()
        except KeyboardInterrupt:
            self.userExit()


def create_app(settings: Optional[Settings] = None):
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