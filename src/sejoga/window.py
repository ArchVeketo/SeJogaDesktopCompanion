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
import math
import time
import random
from pathlib import Path
from typing import Optional, Tuple

# Load Qt before Panda3D: their Windows bundles ship different MSVC runtime
# DLLs, and the first loaded copy wins for the whole process.
from PySide6.QtGui import QActionGroup, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

# Win32 API
import win32gui
import win32con
import win32api
import ctypes
from ctypes import wintypes

# Panda3D - configurar ANTES de importar ShowBase
from panda3d.core import loadPrcFileData

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
loadPrcFileData("", "framebuffer-alpha 1")
loadPrcFileData("", "framebuffer-multisample 1")

# Panda3D imports (depois do loadPrcFileData)
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import (
    WindowProperties, FrameBufferProperties, GraphicsPipe,
    GraphicsWindow, GraphicsOutput, Texture, CardMaker, NodePath,
    LColor, LVecBase3, LVecBase4, Point3, Vec3, Vec4,
    GraphicsPipeSelection, FrameBufferProperties, WindowProperties,
    PerspectiveLens, AmbientLight, DirectionalLight, PointLight,
    AntialiasAttrib, TransparencyAttrib, ColorBlendAttrib,
    ConfigVariableBool, ConfigVariableInt,
    AntialiasAttrib, loadPrcFileData
)
from direct.task import Task
from direct.showbase.ShowBase import ShowBase

# Panda3D GLTF loader registers support for .gltf and .glb files.
import gltf

# Win32 API
import win32gui
import win32con
import win32api
import ctypes
from ctypes import wintypes

# Project imports
from .assets import brand_dir, resolve_model
from .animation import AnimationController, AnimationState
from .model import load_model
from .rig import Rig, ALL_GROUPS, IdlePersonality
from .config import load_settings, save_settings, Settings
from .physics import ScreenSpacePhysics, create_physics, PhysicsState
from .music import MusicListener
from .ui import HotkeyManager, SettingsDialog
from .debug import DebugTools, configure_logging
from .interaction import MouseInteraction
from .desktop_shell import DesktopIntegration
from .exit_animation import ExitAnimation
from .tentacle_system import (
    TentaclePool, TentacleDirector, TentacleState,
    create_tentacle_geometry, update_tentacle_render,
)
from .attention import HoverAttention
from .tray_registration import TrayRegistration
from .tentacle_constraints import ObstacleBox, TentacleContacts

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

# The calibrated final framebuffer key is RGB(214, 0, 214); keep the clear color and Win32 key paired.
COLOR_KEY = 0x00D600D6

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi


def set_window_ex_style(hwnd: int, add_flags: int = 0, remove_flags: int = 0) -> None:
    """Modifica extended window style."""
    ex_style = win32gui.GetWindowLong(hwnd, -20)  # GWL_EXSTYLE
    ex_style = (ex_style | add_flags) & ~remove_flags
    win32gui.SetWindowLong(hwnd, -20, ex_style)


def set_layered_window_attributes(hwnd: int, color_key: int = COLOR_KEY, alpha: int = 255, flags: int = LWA_COLORKEY) -> bool:
    """Define color key e/ou alpha para layered window."""
    return ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, color_key, alpha, flags)


def set_window_pos_zorder(hwnd: int, zorder: int) -> bool:
    """Define Z-order: HWND_TOPMOST (-1), HWND_NOTOPMOST (-2), HWND_BOTTOM (1)."""
    return ctypes.windll.user32.SetWindowPos(hwnd, zorder, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0010)


# ============================================================
# Panda3D Renderer
# ============================================================

class Panda3DRenderer:
    """Encapsula Panda3D render e modelo."""

    FRAME_FILL = 0.66
    MODEL_FACING_HEADING = 180

    def __init__(self, showbase: ShowBase, hwnd: int, width: int, height: int):
        self.showbase = showbase
        self.hwnd = hwnd
        self.width = width
        self.height = height
        self.model_np: Optional[NodePath] = None
        self.model_anchor: Optional[NodePath] = None
        self.rig: Optional[Rig] = None
        self._rig_nodes: dict[str, NodePath] = {}
        self._outline_nodes: dict[str, NodePath] = {}
        self._rig_base_hpr: dict[str, tuple[float, float, float]] = {}
        self._rig_base_pos = {}
        self._view_width = 1.0
        self._view_height = 1.0
        self._view_target_z = 1.0
        self._fit_scale = 1.0
        self._model_dimensions = Vec3(0, 0, 0)
        self._model_center = Vec3(0, 0, 0)
        self._model_min_z = 0.0
        self._model_radius_px = 0.0
        self.tentacles = None
        self.tentacle_pool = None
        self.tentacle_director = None
        self._door_requested = 0.0

        self._setup_scene()
        self._load_model()
        from .lower_body import LowerBody
        self.lower_body = LowerBody(self)
        self._setup_picking()

    def _setup_picking(self) -> None:
        from panda3d.core import (
            BitMask32, CollisionHandlerQueue, CollisionNode, CollisionRay, CollisionTraverser,
        )

        self._pick_ray = CollisionRay()
        node = CollisionNode("mouse-pick-ray")
        node.addSolid(self._pick_ray)
        node.setFromCollideMask(BitMask32.bit(1))
        node.setIntoCollideMask(BitMask32.allOff())
        ray_np = self.showbase.cam.attachNewNode(node)
        self.model_np.setCollideMask(BitMask32.bit(1))
        for limb in self.tentacle_pool.tentacles:
            for axis in limb.axis_nodes:
                axis.setCollideMask(0)
        self._pick_queue = CollisionHandlerQueue()
        self._pick_traverser = CollisionTraverser("mouse-picking")
        self._pick_traverser.addCollider(ray_np, self._pick_queue)

    def hit_test(self, x: float, y: float) -> bool:
        """Testa a malha na pose atual, em pixels da área cliente da janela."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        self._pick_ray.setFromLens(
            self.showbase.cam.node(), 2.0 * x / self.width - 1.0, 1.0 - 2.0 * y / self.height
        )
        self._pick_queue.clearEntries()
        self._pick_traverser.traverse(self.model_np)
        if self._pick_queue.getNumEntries():
            self._pick_queue.sortEntries()
            self._pick_point_model = self._pick_queue.getEntry(0).getSurfacePoint(self.model_np)
        return self._pick_queue.getNumEntries() > 0

    def _setup_scene(self) -> None:
        render = self.showbase.render
        render.setShaderAuto()
        render.setAntialias(AntialiasAttrib.MMultisample)

        # Câmera
        cam = self.showbase.cam
        cam.setPos(0, -15, 1)
        cam.lookAt(0, 0, 1)

        # Lens
        from panda3d.core import OrthographicLens
        lens = OrthographicLens()
        lens.setFilmSize(12.4264 * self.width / self.height, 12.4264)
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
            import simplepbr

            simplepbr.init(use_normal_maps=False, use_emission_maps=False, max_lights=8,
                           msaa_samples=4)
        except ImportError:
            pass
        except Exception as e:
            print(f"[ERROR] SimplePBR initialization failed: {e}")

    def _load_model(self) -> None:
        model_path = resolve_model()
        model = load_model(model_path)
        rig = Rig.from_model(model)

        if rig.missing:
            print(f"WARNING: Grupos de rig ausentes: {rig.missing}")

        self.rig = rig

        # panda3d-gltf 1.x expõe load_model diretamente no módulo.
        model_np = NodePath(gltf.load_model(str(model_path)))
        self._hidden_export_planes = []
        head = model_np.find("**/head")
        for name in ("mesh11", "mesh12", "mesh13", "mesh14"):
            plane = model_np.find(f"**/{name}")
            if not plane.isEmpty() and head.isAncestorOf(plane) and plane.getParent().getName() == "plane":
                # Crossed export/decorative planes around the headphone antennae
                # show dotted triangular scaffolding in the desktop projection.
                plane.stash()
                self._hidden_export_planes.append(name)
        # O glTF foi exportado com a frente apontando para +Y. Como a câmera
        # observa o mascote pelo lado -Y, giramos a malha para mostrar o rosto.
        model_np.setH(self.MODEL_FACING_HEADING)
        bounds = model_np.getTightBounds()
        if not bounds:
            raise ValueError(f"não foi possível calcular os limites do modelo: {model_path}")
        minimum, maximum = bounds
        dimensions = maximum - minimum
        if dimensions.x <= 0 or dimensions.z <= 0:
            raise ValueError(f"modelo sem largura/altura utilizável: {model_path}")

        center = (minimum + maximum) * 0.5
        self._update_view_dimensions()
        target_width = self._view_width * self.FRAME_FILL
        target_height = self._view_height * self.FRAME_FILL
        fit_scale = min(target_width / dimensions.x, target_height / dimensions.z)
        self._fit_scale = fit_scale
        self._model_dimensions = dimensions
        self._model_center = center
        self._model_min_z = float(minimum.z)
        self._model_radius_px = self.showbase.settings.physics.mascot_radius

        self.model_anchor = self.showbase.render.attachNewNode("mascot-motion-root")
        model_np.reparentTo(self.model_anchor)
        self.model_np = model_np
        self._setup_outline()
        self.set_visual_scale(self.showbase.settings.window.scale)

        self._apply_rig_to_model()

        unit_scale = float(self._view_height / self.height / self.model_np.getScale().x)
        head_node = self._rig_nodes["head"]
        spawn_points = [
            self.model_np.getRelativePoint(head_node, Vec3(.035, .10, .12)),
            self.model_np.getRelativePoint(head_node, Vec3(-.04, .10, .20)),
            self.model_np.getRelativePoint(head_node, Vec3(-.02, .20, .16)),
            self.model_np.getRelativePoint(head_node, Vec3(.035, .20, .10)),
            self.model_np.getRelativePoint(head_node, Vec3(0, .23, .12)),
            self.model_np.getRelativePoint(head_node, Vec3(0, .16, .14)),
        ]
        self.tentacle_pool = TentaclePool(
            self.rig, self.model_np, self.outline_np, spawn_points,
            rng=random.Random(), unit_scale=unit_scale,
        )
        from .tentacle_drips import TentacleDrips
        self.tentacle_drips = TentacleDrips(self.model_np)
        from .finger_gestures import FingerGestures
        self.finger_gestures = FingerGestures(self)
        for tentacle in self.tentacle_pool.tentacles:
            create_tentacle_geometry(tentacle, self.model_np, self.outline_np)
        self.tentacle_director = TentacleDirector(
            self.tentacle_pool, self.rig, self.model_np, self.outline_np,
            self._rig_nodes.get("door"), rng=random.Random(),
        )
        self._tentacles_were_visible = False
        self._tentacle_anchor_local = [head_node.getRelativePoint(self.model_np, t.anchor)
                                      for t in self.tentacle_pool.tentacles]
        self._setup_tentacle_contacts()
        self.set_outline_settings(self.showbase.settings.window)
        self.set_model_screen_position(
            self.width / 2,
            self.height - self._model_radius_px - 35,
        )

    def set_visual_scale(self, scale: float) -> None:
        """Atualiza a escala sem deslocar o centro nem os pés do personagem."""
        if not self.model_np:
            return
        model_scale = self._fit_scale * scale
        units_per_pixel_z = self._view_height / self.height
        self.model_np.setScale(model_scale)
        self.model_np.setPos(
            -self._model_center.x * model_scale,
            -self._model_center.y * model_scale,
            -self._model_min_z * model_scale - self._model_radius_px * units_per_pixel_z,
        )
        if self.outline_np:
            self.outline_np.setScale(self.model_np.getScale())
            self.outline_np.setPos(self.model_np.getPos())

    def _setup_outline(self) -> None:
        from panda3d.core import CullFaceAttrib, Shader

        vertex = """#version 130
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;
out vec2 outline_uv;
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform float outline_thickness;
void main() {
    outline_uv = p3d_MultiTexCoord0;
    gl_Position = p3d_ModelViewProjectionMatrix *
        (p3d_Vertex + vec4(normalize(p3d_Normal) * outline_thickness, 0.0));
}
"""
        fragment = """#version 130
uniform vec4 outline_color;
uniform bool outline_enabled;
uniform sampler2D p3d_Texture0;
in vec2 outline_uv;
out vec4 fragColor;
void main() {
    if (!outline_enabled || texture(p3d_Texture0, outline_uv).a < 0.05) discard;
    fragColor = outline_color;
}
"""
        self.outline_np = self.model_np.copyTo(self.model_anchor)
        self.outline_np.setName("mascot-outline")
        self.outline_np.setShader(Shader.make(Shader.SL_GLSL, vertex, fragment), 1000)
        self.outline_np.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise), 1000)
        self.outline_np.setLightOff(1000)
        self.outline_np.setCollideMask(0)

    def set_outline_settings(self, settings) -> None:
        if not self.outline_np:
            return
        self.outline_np.setShaderInput("outline_enabled", bool(settings.outline_enabled))
        if not settings.outline_enabled:
            # Disable both the duplicate model and all child shells. The shader
            # guard also suppresses stale per-mesh copies after live settings changes.
            self.outline_np.hide()
            self.outline_np.stash()
            return
        self.outline_np.unstash()
        self.outline_np.show()
        color = settings.outline_color.lstrip("#")
        rgb = tuple(int(color[index:index + 2], 16) / 255 for index in (0, 2, 4))
        self.outline_np.setShaderInput("outline_color", (*rgb, 1.0))
        # Model units per displayed pixel; the border follows each part's normals.
        visible_height = self.height * self.FRAME_FILL * settings.scale
        thickness = settings.outline_width * self._model_dimensions.z / visible_height
        self.outline_np.setShaderInput("outline_thickness", thickness)

    def _update_view_dimensions(self) -> None:
        lens = self.showbase.cam.node().getLens()
        from panda3d.core import OrthographicLens
        if isinstance(lens, OrthographicLens):
            self._view_width, self._view_height = map(float, lens.getFilmSize())
            return
        fov_x, fov_y = lens.getFov()
        camera_pos = self.showbase.cam.getPos(self.showbase.render)
        target = Vec3(0, 0, self._view_target_z)
        distance = (camera_pos - target).length()
        self._view_width = 2.0 * distance * math.tan(math.radians(float(fov_x)) / 2.0)
        self._view_height = 2.0 * distance * math.tan(math.radians(float(fov_y)) / 2.0)

    def _apply_rig_to_model(self) -> None:
        if not self.model_np or not self.rig:
            return

        for group_name in self.rig.groups:
            node = self.model_np.find(f"**/{group_name}")
            if not node.isEmpty():
                self._rig_nodes[group_name] = node
                self._rig_base_pos[group_name] = node.getPos()
                outline_node = self.outline_np.find(f"**/{group_name}")
                if not outline_node.isEmpty():
                    self._outline_nodes[group_name] = outline_node
                hpr = node.getHpr()
                self._rig_base_hpr[group_name] = (float(hpr.x), float(hpr.y), float(hpr.z))

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        lens = self.showbase.cam.node().getLens()
        if hasattr(lens, 'setAspectRatio'):
            lens.setAspectRatio(width / height)

    def set_model_rotation(self, x: float = 0, y: float = 0, z: float = 0) -> None:
        if self.model_anchor:
            self.model_anchor.setHpr(y, x, z)

    def set_model_position(self, x: float, y: float, z: float) -> None:
        if self.model_anchor:
            self.model_anchor.setPos(x, y, z)

    def set_model_screen_position(self, x: float, y: float) -> None:
        """Converte pixels locais da janela para o plano X/Z do mundo Panda3D."""
        if not self.model_anchor:
            return
        world_x = (x - self.width / 2.0) * self._view_width / self.width
        world_z = self._view_target_z + (self.height / 2.0 - y) * self._view_height / self.height
        self.model_anchor.setPos(world_x, 0.0, world_z)

    def apply_rig_pose(self, pose_dict: dict) -> None:
        if not self.model_np:
            return
        for group in ("head", "body", "right-arm", "left-arm", "legs", "left-feet", "right-feet"):
            if group in self._rig_nodes:
                self._rig_nodes[group].setPos(self._rig_base_pos[group])

        for group_name, rotation in pose_dict.items():
            node = self._rig_nodes.get(group_name)
            if not node:
                continue
            if hasattr(rotation, "x"):
                x, y, z = rotation.x, rotation.y, rotation.z
            else:
                x, y, z = rotation
            # Beyond vertical the upper arms fold inward through the torso.
            if group_name == "right-arm":
                z = max(math.radians(-75), min(math.radians(65), z))
            elif group_name == "left-arm":
                z = max(math.radians(-65), min(math.radians(75), z))
            base_h, base_p, base_r = self._rig_base_hpr.get(group_name, (0.0, 0.0, 0.0))
            if group_name == "door":
                self._door_requested = max(0.0, math.degrees(y))
                if self.tentacles:
                    y = math.radians(self.tentacles.door.angle)
            node.setHpr(
                base_h + math.degrees(y),
                base_p + math.degrees(x),
                base_r + math.degrees(z),
            )
            outline_node = self._outline_nodes.get(group_name)
            if outline_node:
                outline_node.setHpr(node.getHpr())
        self._resolve_arm_clearance()

    def apply_body_motion(self, motion, grab_point=None, *, grounded=True, dragging=False):
        """Rotate connected root parts around the hips/grip without editing the asset rig."""
        from panda3d.core import Mat4, TransformState

        hip = Vec3(self._rig_base_pos["body"])
        grip = Vec3(grab_point) if grab_point is not None else hip

        def around(pivot, pitch, yaw, roll, translation=Vec3(0)):
            rotation = TransformState.makeHpr(Vec3(yaw, pitch, roll)).getMat()
            return Mat4.translateMat(-pivot) * rotation * Mat4.translateMat(pivot + translation)

        hanging = motion.hanging
        upper = around(hip, motion.pitch * (1 - .6 * hanging), motion.yaw,
                       motion.roll * (1 - .7 * hanging), Vec3(0, 0, -motion.compression * .08))
        whole = around(grip if dragging else hip, motion.pitch * .6 * hanging, 0,
                       motion.roll * .7 * hanging)
        for group in ("head", "body", "right-arm", "left-arm", "legs", "left-feet", "right-feet"):
            node = self._rig_nodes[group]
            transform = node.getMat(self.model_np)
            if group in ("head", "body", "right-arm", "left-arm"):
                transform = transform * upper * whole
            elif dragging or not grounded:
                transform = transform * whole
            node.setMat(self.model_np, transform)
            if group == "head":
                node.setR(node.getR() + motion.head_roll)
                node.setP(node.getP() + motion.head_pitch)
            self._outline_nodes[group].setMat(self.outline_np, node.getMat(self.model_np))
        for name, side in (("ant-arm", 1), ("ant-arm2", -1)):
            node = self._rig_nodes[name]
            node.setR(node.getR() + side * motion.arm_lag)
            self._outline_nodes[name].setHpr(node.getHpr())

    def _resolve_arm_clearance(self):
        # Hands inherit the forearm transform. Keep a continuous outward elbow
        # bend instead of solving bounding boxes in discrete five-degree jumps.
        for arm, forearm, direction in (("right-arm", "ant-arm", 1),
                                         ("left-arm", "ant-arm2", -1)):
            upper = self._rig_nodes[arm]
            node = self._rig_nodes[forearm]
            base = self._rig_base_hpr[forearm][2]
            bend = direction * (node.getR()-base)
            inward = max(0.0, direction*(upper.getR()-self._rig_base_hpr[arm][2]))
            bend = min(bend, -max(0.0, inward-42)*.32)
            node.setR(base + direction*bend)
            self._outline_nodes[forearm].setHpr(node.getHpr())

    def _setup_tentacle_contacts(self):
        self.tentacle_contacts = TentacleContacts()
        self._collider_sources = []
        head = self._rig_nodes["head"]
        door = self._rig_nodes["door"]
        cabinet = head.find("**/mesh0")
        if not cabinet.isEmpty():
            low, high = cabinet.getTightBounds(head)
            thickness = .022
            # The cabinet is hollow. Its opening must remain traversable.
            panels = [
                (Vec3(low), Vec3(high.x, low.y + thickness, high.z)),
                (Vec3(low), Vec3(low.x + thickness, high.y, high.z)),
                (Vec3(high.x - thickness, low.y, low.z), Vec3(high)),
                (Vec3(low), Vec3(high.x, high.y, low.z + thickness)),
                (Vec3(low.x, low.y, high.z - thickness), Vec3(high)),
            ]
            for index, (minimum, maximum) in enumerate(panels):
                self._collider_sources.append((f"cabinet-wall-{index}", head, minimum, maximum))
        for mesh in self.model_np.findAllMatches("**/+GeomNode"):
            if mesh == cabinet or mesh.getName().startswith(("procedural-tentacle", "tentacle-joint-")):
                continue
            # Decorative alpha planes are not solid obstacles.
            if "plane" in mesh.getParent().getName().lower():
                continue
            bounds = mesh.getTightBounds(mesh)
            if bounds and min(bounds[1][axis] - bounds[0][axis] for axis in range(3)) > .0001:
                name = "door" if door.isAncestorOf(mesh) else mesh.getName()
                self._collider_sources.append((name, mesh, Vec3(bounds[0]), Vec3(bounds[1])))
        for tentacle in self.tentacle_pool.tentacles:
            tentacle.contacts = self.tentacle_contacts

    def _update_tentacle_contacts(self):
        head = self._rig_nodes["head"]
        self.tentacle_contacts.contacts = 0
        self.tentacle_contacts.boxes = [
            ObstacleBox(name, low, high, self.model_np.getMat(node), node.getMat(self.model_np))
            for name, node, low, high in self._collider_sources
        ]
        for tentacle, local_anchor in zip(self.tentacle_pool.tentacles, self._tentacle_anchor_local):
            anchor = self.model_np.getRelativePoint(head, local_anchor)
            delta = anchor - tentacle.anchor
            tentacle.anchor = Vec3(anchor)
            for segment in tentacle.segments:
                segment.pos += delta
            if tentacle.target is not None:
                tentacle.target += delta
            tentacle.reference_front = self.model_np.getRelativeVector(head, Vec3(0, 1, 0)).normalized()

    def update_appendages(self, dt, visible=True):
        if not self.tentacle_director:
            return
        controller = self.showbase.animation_controller
        self.finger_gestures.update(dt, controller.state.value if controller.state else None)
        sneezing = controller.state is not None and controller.state.value == 'sneeze'
        if sneezing and controller._reaction_time >= 3.6 and not self.tentacle_director.burst:
            self.tentacle_director.trigger_sneeze()
            self.tentacle_drips.spray(self.tentacle_pool.tentacles)
        if not sneezing and not any(t.state != TentacleState.DORMANT for t in self.tentacle_pool.tentacles):
            self.tentacle_director.burst = False
        if visible:
            if not self._tentacles_were_visible:
                self.tentacle_director.trigger_curious()
        elif self._tentacles_were_visible:
            self.tentacle_director._retract_all()
        active = any(t.state != TentacleState.DORMANT for t in self.tentacle_pool.tentacles)
        door = self._rig_nodes.get("door")
        if door:
            base_h, base_p, base_r = self._rig_base_hpr["door"]
            door.setHpr(base_h + self.tentacle_director._door_current, base_p, base_r)
        if active:
            self._update_tentacle_contacts()
        self.tentacle_director._door_requested = max(self._door_requested, 85.0 if active else 0.0)
        # The animation controller owns ambient timing. Keep updating the door
        # after the last limb is dormant, so it can finish closing smoothly.
        self.tentacle_director.update(dt, 0.0, controller.idle_personality)
        self.tentacle_drips.update(dt, self.tentacle_pool.tentacles)
        self._tentacles_were_visible = visible
        for tentacle in self.tentacle_pool.tentacles:
            active = tentacle.state != TentacleState.DORMANT and tentacle.reveal > .015
            if active:
                update_tentacle_render(tentacle)
            for index, axis in enumerate(tentacle.axis_nodes):
                debug = self.showbase.debug_tools
                shown = active and debug and debug.visible and index / (len(tentacle.segments) - 1) <= tentacle.reveal
                (axis.show if shown else axis.hide)()
            if tentacle.mesh_node:
                (tentacle.mesh_node.show if active else tentacle.mesh_node.hide)()
                tentacle.mesh_node.setCollideMask(2 if active else 0)
            if tentacle.outline_mesh_node:
                (tentacle.outline_mesh_node.show if active else tentacle.outline_mesh_node.hide)()
        door = self._rig_nodes.get("door")
        if door:
            base_h, base_p, base_r = self._rig_base_hpr["door"]
            door.setHpr(base_h + self.tentacle_director._door_current, base_p, base_r)
            self._outline_nodes["door"].setHpr(door.getHpr())

    def begin_exit_effect(self):
        from panda3d.core import Shader
        vertex = """#version 130
in vec4 p3d_Vertex; in vec2 p3d_MultiTexCoord0;
uniform mat4 p3d_ModelViewProjectionMatrix; out vec2 uv;
void main() { uv = p3d_MultiTexCoord0; gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex; }
"""
        fragment = """#version 130
uniform sampler2D p3d_Texture0; in vec2 uv; out vec4 fragColor;
void main() { if (texture(p3d_Texture0, uv).a < 0.05) discard; fragColor = vec4(100.0, 100.0, 100.0, 1.0); }
"""
        self.model_np.setShader(Shader.make(Shader.SL_GLSL, vertex, fragment), 1001)
        self.outline_np.hide()
        minimum, maximum = self.model_np.getTightBounds(self.showbase.render)
        self.exit_pivot = self.showbase.render.attachNewNode("exit-spin-center")
        self.exit_pivot.setPos((minimum + maximum) * .5)
        self.model_anchor.wrtReparentTo(self.exit_pivot)

    def set_exit_rotation(self, roll):
        self.exit_pivot.setR(roll)


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
        self.renderer: Optional = None
        self.physics: Optional = None
        self.music_listener: Optional[MusicListener] = None
        self.debug_tools: Optional[DebugTools] = None
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
        self.animation_controller: Optional[AnimationController] = None

        self.qt_app: Optional = None
        self.tray_icon: Optional = None
        self.tray_menu: Optional = None
        self._settings_dialog: Optional[SettingsDialog] = None
        self._topmost_action = None
        self._debug_action = None
        self._recording_action = None
        self.hotkey_manager: Optional[HotkeyManager] = None

        self.logger = configure_logging()
        self._drag_active = False
        self._drag_start_pos = (0, 0)
        self._window_start_pos = (0, 0)

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

        print("OverlayApp initialized.")

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

        self.win.setClearColor((1.0, 0.0, 1.0, 1.0))  # Magenta color key (tone-maps to RGB 214, 0, 214)
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

        ex_style = win32gui.GetWindowLong(self.hwnd, -20)
        ex_style |= 0x00080000 | 0x08000000  # WS_EX_LAYERED | WS_EX_NOACTIVATE
        if self._is_topmost:
            ex_style |= 0x00000008
        win32gui.SetWindowLong(self.hwnd, -20, ex_style)

        self._refresh_background_mode()
        self._update_z_order()

        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            pass

    def _refresh_background_mode(self) -> None:
        """Windows uses the final framebuffer color, after PBR tone mapping."""
        ex_style = win32gui.GetWindowLong(self.hwnd, -20)
        if ex_style & WS_EX_TRANSPARENT:
            win32gui.SetWindowLong(self.hwnd, -20, ex_style & ~WS_EX_TRANSPARENT)
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
        win32gui.SetWindowPos(self.hwnd, 0, x, y, size, size, 0x0004 | 0x0010)
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

        # Obtém HWND e PID próprio
        own_hwnd = self.hwnd
        own_pid = os.getpid()

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
        if state.grounded and math.hypot(*state.velocity) < 5:
            if self._last_rest_position != (x, y):
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
        pose = self.animation_controller.update(
            dt,
            velocity=state.velocity if state else (0.0, 0.0),
            grounded=state.grounded if state else True,
            gravity_active=state.gravity_active if state else False,
            dragging=self._drag_active,
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
        self.renderer.apply_body_motion(
            self.animation_controller.body_motion.snapshot, self._body_grab_point,
            grounded=state.grounded if state else True, dragging=self._drag_active,
        )
        self.renderer.lower_body.apply(self.animation_controller.leg_motion.pose,
                                       bool(not self._drag_active and (state.grounded if state else True)))
        self.renderer.update_appendages(dt, self.animation_controller.state == AnimationState.PEEK)
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
        events = self.mouse_interaction.update(
            position, buttons, hit=hit, enabled=enabled,
            allow_drag=self.settings.behavior.react_to_drag,
            allow_click=self.settings.behavior.react_to_click,
        )
        previous_hover = self._mouse_hovered
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
        self._mouse_hovered = enabled and allowed and not self._drag_active and dx*dx + dy*dy <= 1
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
            print(f"[settings] failed to save configuration: {exc}")

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
        print("Starting SeJogaDesktopCompanion...")
        try:
            ShowBase.run(self)
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
