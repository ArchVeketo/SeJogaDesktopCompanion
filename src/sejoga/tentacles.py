"""Malhas procedurais curvas e pequenas gotas rosas no recolhimento."""
import math
import random

from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexData,
                         GeomVertexFormat, GeomVertexWriter, Vec3, Texture)
from .appendages import AppendageMotion
from .assets import model_dir
import gltf
from panda3d.core import NodePath


class TentacleRenderer:
    RINGS = 19
    SIDES = 8

    def __init__(self, head):
        self.root = head.attachNewNode("procedural-tentacles")
        self.motion = AppendageMotion()
        self.clock = 0.0
        self._rng = random.Random()
        self._slime_cooldown = 5.0
        self.drops = []
        self.meshes = []
        # White texture keeps both the outline alpha-test and exit flash valid.
        texture = Texture("tentacle-white")
        texture.setup2dTexture(1, 1, Texture.TUnsignedByte, Texture.FRgba)
        texture.setRamImage(bytes([255, 255, 255, 255]))
        self.root.setTexture(texture, 1)
        model = NodePath(gltf.load_model(str(model_dir() / "tentacle.gltf")))
        for index in range(4):
            np = model.copyTo(self.root)
            np.setName(f"thick-tentacle-{index}")
            self.meshes.append(np)
        self.drop_template = self._drop_mesh()
        self.root.hide()

    def _drop_mesh(self):
        data = GeomVertexData("slime", GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
        v, n, c = (GeomVertexWriter(data, key) for key in ("vertex", "normal", "color"))
        points = [(0, 0, .035), (.02, 0, 0), (0, .02, 0), (-.02, 0, 0), (0, -.02, 0), (0, 0, -.05)]
        for point in points:
            v.addData3(*point)
            n.addData3(Vec3(*point).normalized())
            c.addData4(1.0, .02, .36, 1.0)
        triangles = GeomTriangles(Geom.UHStatic)
        for i in range(4):
            a, b = 1+i, 1+(i+1)%4
            triangles.addVertices(0, a, b)
            triangles.addVertices(5, b, a)
        triangles.closePrimitive()
        geom = Geom(data)
        geom.addPrimitive(triangles)
        node = GeomNode("pink-slime-drop")
        node.addGeom(geom)
        return node

    def update(self, dt, door_degrees):
        dt = min(.1, max(0.0, dt))
        self.clock += dt
        extent = self.motion.update(dt, door_degrees)
        if extent <= .001 and not self.drops:
            self.root.hide()
            return
        self.root.show()
        self._slime_cooldown -= dt
        retracting = extent < self.motion.previous_extension and extent > .1
        if retracting and self._slime_cooldown <= 0 and self._rng.random() < dt * .65:
            np = self.root.attachNewNode(self.drop_template)
            self.drops.append([np, 0.0, self._rng.uniform(-.1, .1)])
            self._slime_cooldown = self._rng.uniform(5, 12)
        for drop in self.drops[:]:
            np, age, x = drop
            age += dt
            drop[1] = age
            np.setPos(x + age*.035, .21, .04 - age*.2 - age*age*.35)
            np.setScale(max(.1, 1 - age))
            if age > .85:
                np.removeNode()
                self.drops.remove(drop)
        roots = [(-.06, .15, .18), (.06, .15, .18), (-.065, .15, .035), (.065, .15, .035)]
        rolls = [-55, 55, -110, 140]
        for index, np in enumerate(self.meshes):
            local_extent = max(0.0, min(1.0, (extent - index * .1) / .7))
            if local_extent < .01:
                np.hide()
                continue
            np.show()
            x, y, z = roots[index]
            np.setPos(x, y - .09*(1-local_extent), z)
            np.setScale(local_extent ** .4, local_extent ** .4, local_extent)
            np.setHpr(0, math.sin(self.clock*1.5 + index)*6*local_extent,
                      rolls[index] + math.sin(self.clock*1.3 + index*1.6)*8*local_extent)
