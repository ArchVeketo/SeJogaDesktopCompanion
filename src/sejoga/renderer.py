"""Panda3DRenderer — render 3D do mascote (Panda3D).

Extraído de window.py sem reescrever a lógica de render. Mantém os mesmos
imports do lado engine: Panda3D, o loader glTF e os módulos de tentáculo.
Preserva nomes/hierarquia do rig, a calibração do color key (feita em window.py)
e os guards IsWindow/erro 1400 (que permanecem em OverlayApp).
"""

from __future__ import annotations

import logging
import math
import random
from typing import Optional

# Panda3D GLTF loader registers support for .gltf and .glb files.
import gltf
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AntialiasAttrib,
    NodePath,
    Point3,
    Vec3,
)

from .animation import AnimationState
from .assets import resolve_model
from .model import load_model
from .rig import Rig
from .tentacle_constraints import ObstacleBox, TentacleContacts
from .tentacle_system import (
    TentacleDirector,
    TentaclePool,
    TentacleState,
    create_tentacle_geometry,
    update_tentacle_render,
)

logger = logging.getLogger(__name__)


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
        # Criados sob demanda no primeiro frame de física; pré-inicializados
        # para evitar hasattr por frame em apply_body_motion.
        self._suspension_pivot = None
        from .body_motion import Spring
        self._dance_stage_yaw = Spring(1.4, .85)

        self._setup_scene()
        self._load_model()
        from .lower_body import LowerBody
        self.lower_body = LowerBody(self)
        self._setup_picking()

    def _setup_picking(self) -> None:
        from panda3d.core import (
            BitMask32,
            CollisionHandlerQueue,
            CollisionNode,
            CollisionRay,
            CollisionTraverser,
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
            picked = self._pick_queue.getEntry(0).getIntoNodePath()
            self._pick_part = 'body'
            while not picked.isEmpty() and picked != self.model_np:
                name = picked.getName()
                if name in ('right-arm', 'left-arm', 'left-feet', 'right-feet', 'legs', 'head'):
                    self._pick_part = name
                    break
                picked = picked.getParent()
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

            pipeline = simplepbr.init(use_normal_maps=False, use_emission_maps=False, max_lights=8,
                                      msaa_samples=4)
            from .chroma_resolve import install_chroma_resolve
            install_chroma_resolve(pipeline)
        except ImportError:
            pass
        except Exception as e:
            logger.error("Falha ao inicializar SimplePBR: %s", e)

    def _load_model(self) -> None:
        model_path = resolve_model()
        model = load_model(model_path)
        rig = Rig.from_model(model)

        if rig.missing:
            logger.warning("Grupos de rig ausentes: %s", rig.missing)

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
        from .flexible_rig import FlexibleRig
        self.flexible_rig = FlexibleRig(self)

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
        from .music_speaker import MusicSpeaker
        self.music_speaker = MusicSpeaker(self)
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
                if not hasattr(self, '_rig_base_scale'):
                    self._rig_base_scale = {}
                self._rig_base_scale[group_name] = node.getScale()
                if not hasattr(self, '_rig_base_mat'):
                    self._rig_base_mat = {}
                self._rig_base_mat[group_name] = node.getMat()
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
        self.flexible_rig.update(getattr(self.showbase.animation_controller, 'delta_time', 1/60), motion)
        if self._suspension_pivot is None:
            self._suspension_pivot = self.model_anchor.attachNewNode('suspension-pivot')
            self.model_np.reparentTo(self._suspension_pivot)
            self.outline_np.reparentTo(self._suspension_pivot)
        self._suspension_pivot.setMat(Mat4.identMat())
        controller = getattr(self.showbase, 'animation_controller', None)
        head_nod = (not dragging and controller and controller.state == AnimationState.DANCE
                    and controller.dance_motion.style == 'head_bob')
        settle = self.music_speaker.settle if hasattr(self,'music_speaker') else 0
        self._dance_stage_yaw.update(getattr(controller,'delta_time',1/60),-55*settle if head_nod else 0)
        if not dragging and controller and controller.state == AnimationState.DANCE and controller.dance_motion.style == 'breakdance':
            dance = controller.dance_motion
            ground = self.model_np.getTightBounds(self.model_anchor)[0].z
            self._suspension_pivot.setHpr(dance.floor_spin, 0, -65*dance.floor_amount)
            moved = self.model_np.getTightBounds(self.model_anchor)[0].z
            self._suspension_pivot.setZ(ground-moved)
            return
        if dragging or motion.hanging > .05:
            point = Vec3(grab_point) if grab_point is not None else Vec3(0,0,.6)
            pivot = self._suspension_pivot.getRelativePoint(self.model_np, point)
            rotation = TransformState.makeHpr(Vec3(motion.yaw, motion.pitch, motion.roll)).getMat()
            self._suspension_pivot.setMat(Mat4.translateMat(-pivot)*rotation*Mat4.translateMat(pivot))
            return
        # Grounded reaction now uses the shared spine and neck joints rather
        # than independently transforming disconnected top-level body parts.
        for spine, neck, shoulders in self.flexible_rig.chains:
            spine.setHpr(motion.yaw, motion.pitch*.6+(10*settle if head_nod else 0),
                         motion.roll*.55+self.flexible_rig.spine.value)
            spine.setZ(.44-motion.compression*.06)
            neck.setP(motion.head_pitch)
            neck.setR(neck.getR()+motion.head_roll)
        if abs(self._dance_stage_yaw.value) > .01:
            pivot=self._suspension_pivot.getRelativePoint(self.model_np,Point3(0,0,.44))
            rotation=TransformState.makeHpr(Vec3(self._dance_stage_yaw.value,0,0)).getMat()
            self._suspension_pivot.setMat(Mat4.translateMat(-pivot)*rotation*Mat4.translateMat(pivot))
        if head_nod and self.music_speaker.landed:
            body=self._rig_nodes['body']
            mesh=body.find('**/mesh20')
            low,high=mesh.getTightBounds(body)
            plane,normal=self.music_speaker.support_in_stage()
            corners=[self.model_anchor.getRelativePoint(body,Point3(x,low.y,z))
                     for x in (low.x,high.x) for z in (low.z,high.z)]
            distance=min((back-plane).dot(normal) for back in corners)
            limit=self.model_np.getScale().x*.60
            correction=max(-limit,min(limit,-distance))*settle
            self._suspension_pivot.setPos(self._suspension_pivot.getPos()+normal*correction)

    def _resolve_arm_clearance(self):
        controller = getattr(self.showbase, 'animation_controller', None)
        if controller and controller.state == AnimationState.DANCE and controller.dance_motion.style == 'head_bob':
            return  # Authored crossed arms sit forward of the torso.
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
        # Cache por fonte: (matriz node->model, ObstacleBox). As peças estáticas
        # nunca se movem em relação ao model_np; só porta/cabeça/speaker mudam,
        # então só elas recriam a matriz e a caixa orientada por frame.
        self._contact_box_cache = {}

    def _update_tentacle_contacts(self):
        head = self._rig_nodes["head"]
        self.tentacle_contacts.contacts = 0
        boxes = []
        for index, (name, node, low, high) in enumerate(self._collider_sources):
            to_model = node.getMat(self.model_np)
            cached = self._contact_box_cache.get(index)
            if cached is not None and cached[0] == to_model:
                boxes.append(cached[1])
                continue
            box = ObstacleBox(name, low, high, self.model_np.getMat(node), to_model)
            self._contact_box_cache[index] = (to_model, box)
            boxes.append(box)
        self.tentacle_contacts.boxes = boxes
        speaker=self.music_speaker
        if not speaker.root.isHidden():
            low=Vec3(-speaker.width/2,-speaker.depth/2,-speaker.height/2)
            high=Vec3(speaker.width/2,speaker.depth*.85,speaker.height/2)
            self.tentacle_contacts.boxes.append(ObstacleBox('music-speaker',low,high,
                self.model_np.getMat(speaker.root),speaker.root.getMat(self.model_np)))
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
        dancing = controller.state is not None and controller.state.value == 'dance'
        dance = controller.dance_motion
        gesture = 'rock' if dancing and dance.style == 'rock' else controller.state.value if controller.state else None
        self.finger_gestures.update(dt, gesture)
        speaker_active = dancing or (self.music_speaker.was_dancing and getattr(controller, 'music_active', False))
        self.music_speaker.update(dt, speaker_active, dance.phase, dance.energy,dance.bass)
        if self.music_speaker.age < .1:
            self._speaker_throw_started=False
        if speaker_active and self.music_speaker.age >= .9 and not getattr(self,'_speaker_throw_started',False):
            self._speaker_throw_started=True
            self.tentacle_director.trigger_speaker_throw()
        for index,limb in enumerate(self.tentacle_director.speaker_throw_limbs):
            speaker=self.music_speaker
            # Push separate points on the outside of the front rim, not the
            # cabinet centre: the contact solver must keep the tips outside.
            limb.target=Vec3(speaker.current_position)+Vec3(
                (index-1)*.12,speaker.depth/2+.10,speaker.height*(.22-.12*index))
        self.tentacle_director.music_ejection=self.music_speaker.ejecting
        if self.music_speaker.ejecting:
            self._door_requested=max(self._door_requested,100)
        if dancing and self.music_speaker.age < 2.3:
            age=self.music_speaker.age
            preparation=sum(amplitude*math.exp(-((age-at)/width)**2)
                            for at,width,amplitude in ((.35,.15,.3),(.8,.18,.6),(1.2,.20,1)))
            shot=math.exp(-((age-1.48)/.09)**2)
            envelope=math.sin(math.pi*min(1,age/2.3))
            head=self._rig_nodes['head']
            head.setH(head.getH()-50*envelope)
            head.setP(head.getP()-9*preparation-24*shot)
            self._outline_nodes['head'].setHpr(head.getHpr())
            for side,name in ((1,'right-arm'),(-1,'left-arm')):
                arm=self._rig_nodes[name]
                arm.setP(arm.getP()-18*shot)
                self._outline_nodes[name].setHpr(arm.getHpr())

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
