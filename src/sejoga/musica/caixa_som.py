"""Palco e jukebox 3D renderizados com os modelos Blockbench originais.

Carrega o BoomboxGRANDE central e duas caixas laterais BoomboxSIde1 anguladas,
formando o palco do mascote. No head bob (estilo Girlfriend do FNF), o mascote
senta diretamente no topo da jukebox central com as pernas balançando sobre a frente;
nas outras danças (rock, hip hop, breakdance), as caixas emolduram o fundo do palco.
"""

from __future__ import annotations

import json
from math import cos, exp, sin, tau
from pathlib import Path

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    NodePath,
    PNMImage,
    Point3,
    StringStream,
    Texture,
    Vec3,
)

from sejoga.nucleo.recursos import assets_dir

FACING_MASCOTE_GRAUS = 0.0
FACING_CAIXA_EXTRA_GRAUS = 0.0


def _build_bbmodel_node(
    bbmodel_path: Path,
    texture_path: Path,
    scale: float = 0.024,
    name: str = "boombox",
) -> NodePath:
    """Carrega geometria e textura de um modelo Blockbench (.bbmodel) em um NodePath Panda3D."""
    data = json.loads(bbmodel_path.read_text(encoding="utf-8"))
    res = data.get("resolution", {"width": 16, "height": 16})
    tex_w, tex_h = float(res.get("width", 16)), float(res.get("height", 16))

    vdata = GeomVertexData(name, GeomVertexFormat.getV3n3t2(), Geom.UHStatic)
    vwriter = GeomVertexWriter(vdata, "vertex")
    nwriter = GeomVertexWriter(vdata, "normal")
    twriter = GeomVertexWriter(vdata, "texcoord")
    tris = GeomTriangles(Geom.UHStatic)

    vert_idx = 0
    for elem in data.get("elements", []):
        verts = elem.get("vertices", {})
        faces = elem.get("faces", {})

        for _face_id, face in faces.items():
            f_verts = face.get("vertices", [])
            f_uv = face.get("uv", {})
            if len(f_verts) != 4:
                continue

            # No Blockbench: X = largura, Y = altura, Z = profundidade (frente = -Z com os alto-falantes).
            # No Panda: X = largura, Y = profundidade (frente = -Y voltado para a câmera), Z = altura (+Z).
            p_pts = []
            for vid in f_verts:
                bx, by, bz = verts[vid]
                px = bx * scale
                py = bz * scale
                pz = by * scale
                p_pts.append(Vec3(px, py, pz))

            v0, v1, v2 = p_pts[0], p_pts[1], p_pts[2]
            n = (v1 - v0).cross(v2 - v0)
            if n.lengthSquared() > 1e-6:
                n.normalize()
            else:
                n = Vec3(0, -1, 0)

            for vid in f_verts:
                bx, by, bz = verts[vid]
                px = bx * scale
                py = bz * scale
                pz = by * scale
                uv = f_uv.get(vid, [0, 0])
                u = uv[0] / tex_w
                v = 1.0 - (uv[1] / tex_h)

                vwriter.addData3(px, py, pz)
                nwriter.addData3(n)
                twriter.addData2(u, v)

            tris.addVertices(vert_idx, vert_idx + 1, vert_idx + 2)
            tris.addVertices(vert_idx, vert_idx + 2, vert_idx + 3)
            vert_idx += 4

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gnode = GeomNode(name)
    gnode.addGeom(geom)
    np = NodePath(gnode)

    pnm = PNMImage()
    if texture_path.exists() and pnm.read(
        StringStream(texture_path.read_bytes()), texture_path.name
    ):
        tex = Texture(name + "_tex")
        tex.load(pnm)
        tex.setMinfilter(Texture.FTNearest)
        tex.setMagfilter(Texture.FTNearest)
        np.setTexture(tex, 1)

    np.setTwoSided(True)
    return np


class MusicSpeaker:
    """Caixa de som / jukebox que surge durante a dança do mascote."""

    def __init__(self, renderer):
        """Monta a geometria da jukebox 3D sob o renderer."""
        self.renderer = renderer
        self._measure_character()

        # Dimensões gerais do palco (baseadas no layout das 3 caixas)
        self.width = 1.25
        self.height = 0.68
        self.depth = 0.75
        self.final_position = Point3(0.0, 0.05, self.floor_z)

        self.root = renderer.model_anchor.attachNewNode("music-speaker")
        self.root.setLightOff(1)
        self.root.setShaderOff(1)
        self.root.setCollideMask(0)

        self.geometry = self.root.attachNewNode("speaker-stage")

        # 1. Caixa central grande (BoomboxGRANDE)
        bb_grande_model = (
            assets_dir() / "assets" / "boomboxgrande" / "BoomboxGRANDE.bbmodel"
        )
        bb_grande_tex = assets_dir() / "assets" / "boomboxgrande" / "texture.png"
        self.center_box = _build_bbmodel_node(
            bb_grande_model,
            bb_grande_tex,
            scale=0.024,
            name="boombox-center",
        )
        self.center_box.reparentTo(self.geometry)
        self.center_box.setPos(0, 0, 0)

        # 2. Caixas laterais anguladas (BoomboxSIde1)
        bb_side_model = assets_dir() / "assets" / "BoomboxSIde1.bbmodel"
        bb_side_tex = assets_dir() / "assets" / "texture.png"

        self.left_box = _build_bbmodel_node(
            bb_side_model,
            bb_side_tex,
            scale=0.024,
            name="boombox-side-left",
        )
        self.left_box.reparentTo(self.geometry)
        self.left_box.setPos(-0.48, 0.06, 0)
        self.left_box.setH(-17.5)

        self.right_box = _build_bbmodel_node(
            bb_side_model,
            bb_side_tex,
            scale=0.024,
            name="boombox-side-right",
        )
        self.right_box.reparentTo(self.geometry)
        self.right_box.setPos(0.48, 0.06, 0)
        self.right_box.setH(15.0)

        from sejoga.musica.efeitos_caixa_som import SpeakerEffects

        self.effects = SpeakerEffects(self.geometry)
        self.age = 0.0
        self.visibility = 0.0
        self.was_dancing = False
        self.ejecting = False
        self.landed = False
        self._landing_sound_played = False
        self.current_position = Point3(0, 0.19, 0.86)
        self.root.hide()

    def _measure_character(self):
        from sejoga.animacao.poses_base import pose_idle
        from sejoga.nucleo.esqueleto import IdlePersonality

        rig = self.renderer.rig
        previous = rig.pose()
        rig.reset()
        pose_idle(rig, 0, IdlePersonality.CALM)
        self.renderer.apply_rig_pose(rig.pose())
        bounds = [
            self.renderer._rig_nodes[name].getTightBounds(self.renderer.model_np)
            for name in (
                "head",
                "body",
                "right-arm",
                "left-arm",
                "legs",
                "left-feet",
                "right-feet",
            )
        ]
        low = Vec3(*(min(b[0][i] for b in bounds) for i in range(3)))
        high = Vec3(*(max(b[1][i] for b in bounds) for i in range(3)))
        self.character_size = high - low
        self.floor_z = low.z
        self.renderer.apply_rig_pose(previous)
        rig.current = previous

    def _matriz_visivel(self):
        """Matriz do referencial visível do mascote."""
        from panda3d.core import TransformState

        model_np = self.renderer.model_np
        transform = TransformState.makePosHprScale(
            model_np.getPos(),
            (FACING_MASCOTE_GRAUS, 0.0, 0.0),
            model_np.getScale(),
        )
        return transform.getMat()

    @property
    def settle(self):
        """Assenta o palco após a descida."""
        value = max(0, min(1, (self.age - 2.0) / 0.8))
        return value * value * (3 - 2 * value)

    @property
    def support_plane(self):
        """Devolve o plano de apoio superior da caixa central."""
        return Point3(0.0, 0.0, self.floor_z + 0.44)

    def support_in_stage(self):
        """Devolve o apoio no palco para contatos."""
        point = Point3(0, 0, self.floor_z + 0.44)
        point = self.renderer.model_anchor.getRelativePoint(self.root, point)
        normal = (
            self.root.getQuat(self.renderer.model_anchor)
            .xform(Vec3(0, 0, 1))
            .normalized()
        )
        return point, normal

    def update(self, dt, dancing, phase, energy, bass=0):
        """Atualiza a visibilidade, animação e pulso das caixas de som."""
        if dancing and not self.was_dancing:
            self.age = 0.0
            self._landing_sound_played = False
            self.current_position = Point3(0, 0.19, 0.86)
        self.was_dancing = dancing
        self.age += dt
        self.visibility += ((1 if dancing else 0) - self.visibility) * (
            1 - exp(-dt * 5)
        )
        self.ejecting = dancing and 0.55 <= self.age < 2.1
        self.landed = self.age >= 2.1 and self.visibility > 0.95

        if self.visibility < 0.005 or (dancing and self.age < 1.35):
            self.root.hide()
            return
        self.root.show()

        controller = getattr(self.renderer.showbase, "animation_controller", None)
        style = getattr(controller.dance_motion, "style", "head_bob") if controller else "head_bob"

        # Posição final: diretamente sob o mascote no head_bob (ele senta em cima);
        # levemente atrás no rock/hip_hop/breakdance para emoldurar o mascote no palco.
        target_y = 0.16 if style == "head_bob" else 0.38
        target_pos = Point3(0.0, target_y, self.floor_z - 0.30)

        u = max(0, min(1, (self.age - 1.35) / 0.65))
        ease = u * u * (3 - 2 * u)
        start = Point3(0, 0.20, 0.86)
        position = start * (1 - ease) + target_pos * ease
        position.z += self.height * 0.15 * sin(u * 3.14159265)

        if 1.95 <= self.age < 2.25:
            position.z += (
                self.height * 0.03 * sin((self.age - 1.95) / 0.30 * 3.14159265)
            )
        self.current_position = Point3(position)

        pulse = max(0, cos(phase)) ** 6
        strength = max(0, min(1, energy * 0.7 + bass * 0.9))

        if self.age > 2.1:
            position.x += self.width * 0.002 * sin(phase * 8) * strength
            position.y += self.depth * 0.005 * sin(phase * 6) * strength

        self.root.setPos(self._matriz_visivel().xformPoint(position))
        self.root.setH(FACING_MASCOTE_GRAUS + FACING_CAIXA_EXTRA_GRAUS)
        self.root.setScale(
            self.renderer.model_np.getScale().x
            * max(0.005, self.visibility * (0.10 + 0.90 * ease))
        )
        self.root.setR((1 - ease) * -90)

        # Pulso rítmico nas caixas com o grave e o beat
        if self.age > 2.1:
            box_scale = 1.0 + pulse * 0.035 * strength
            self.center_box.setScale(box_scale, box_scale, box_scale)
            side_scale = 1.0 + pulse * 0.025 * strength
            self.left_box.setScale(side_scale, side_scale, side_scale)
            self.right_box.setScale(side_scale, side_scale, side_scale)
        else:
            self.center_box.setScale(1.0, 1.0, 1.0)
            self.left_box.setScale(1.0, 1.0, 1.0)
            self.right_box.setScale(1.0, 1.0, 1.0)

        self.effects.update(self.age, phase, strength)

        if self.age >= 1.95 and not self._landing_sound_played:
            self._landing_sound_played = True
            settings = self.renderer.showbase.settings.audio
            if settings.enabled and controller and controller._dance_preview_remaining <= 0:
                from sejoga.musica.efeitos_sonoros import play_speaker_landing

                play_speaker_landing(settings.master_volume)
