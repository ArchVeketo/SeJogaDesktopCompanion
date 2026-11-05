"""Tentáculos volumétricos deformados por curvas 3D, com contato na porta."""
import math
import random
from itertools import pairwise

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    Material,
    PointLight,
    Texture,
    Vec3,
)

from .appendages import AppendageMotion, DoorJoint, tentacle_center
from .tentacle_model import build_tentacle


class TentacleRenderer:

    def __init__(self, head):
        self.root = head.attachNewNode("procedural-tentacles")
        self.motion = AppendageMotion()
        self.door = DoorJoint()
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
        self.vertices, _, colors, indices = build_tentacle()
        self._rest_vertices = [(max(0, min(1, z/.432)), x-self._rest_center(z), y)
                               for x, y, z in self.vertices]
        self._data = []
        self._slices = {}
        for x, y, z in self.vertices:
            u = max(0.0, min(1.0, z/.432))
            rx = x - self._rest_center(z)
            radius = math.hypot(rx, y)
            self._slices[u] = max(self._slices.get(u, 0), radius)
        self._contact_slices = sorted(self._slices)[::max(1, len(self._slices)//12)]
        for index in range(2):
            data = GeomVertexData(f"deformable-tentacle-{index}", GeomVertexFormat.getV3n3c4t2(), Geom.UHDynamic)
            data.setNumRows(len(self.vertices))
            color, uv = GeomVertexWriter(data, 'color'), GeomVertexWriter(data, 'texcoord')
            for rgba in colors:
                linear = tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgba[:3])
                color.setData4(*linear, rgba[3])
                uv.setData2(0, 0)
            triangles = GeomTriangles(Geom.UHStatic)
            for i in range(0, len(indices), 3):
                triangles.addVertices(*indices[i:i+3])
            triangles.closePrimitive()
            geom = Geom(data)
            geom.addPrimitive(triangles)
            node = GeomNode(f"thick-tentacle-{index}")
            node.addGeom(geom)
            np = self.root.attachNewNode(node)
            np.setTwoSided(True)
            self.meshes.append(np)
            self._data.append(data)
        material = Material('tentacle-volume')
        material.setBaseColor((1, 1, 1, 1))
        material.setRoughness(.55)
        material.setMetallic(0)
        self.root.setMaterial(material, 1)
        light = PointLight('cabinet-depth-light')
        light.setColor((.32, .25, .36, 1))
        light.setAttenuation((1, 0, 5))
        lamp = head.attachNewNode(light)
        lamp.setPos(-.3, .55, .4)
        self.root.setLight(lamp)
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

    def update(self, dt, door_degrees, visible=True):
        dt = min(.1, max(0.0, dt))
        self.clock += dt
        extent = self.motion.update(dt, door_degrees if visible else 0, self.door.angle)
        spheres = []
        for index in range(2):
            local_extent = self._extension(index, extent)
            if local_extent > .02:
                for u in self._contact_slices:
                    center = tentacle_center(index, u, self.clock, local_extent)
                    radius = self._radius(self._slices[u], center, local_extent)
                    spheres.append((center, radius))
        self.door.update(dt, door_degrees, spheres)
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
        for index, np in enumerate(self.meshes):
            extent_here = self._extension(index, extent)
            if extent_here < .01:
                np.hide()
                continue
            np.show()
            frames = {}
            for u, radius in self._slices.items():
                p = tentacle_center(index, u, self.clock, extent_here)
                radius_here = self._radius(radius, p, extent_here)
                center = Vec3(*self.door.project(p, radius_here))
                a = Vec3(*tentacle_center(index, max(0, u-.005), self.clock, extent_here))
                b = Vec3(*tentacle_center(index, min(1, u+.005), self.clock, extent_here))
                tangent = (b-a).normalized()
                axis = Vec3(0, 1, 0).cross(tangent)
                if axis.lengthSquared() < 1e-8:
                    axis = Vec3(1, 0, 0)
                axis.normalize()
                side = tangent.cross(axis).normalized()
                twist = [-.45, .55, -.7, .8][index] + math.sin(self.clock*.9+index)*.3*u
                x_axis = axis*math.cos(twist) + side*math.sin(twist)
                y_axis = -axis*math.sin(twist) + side*math.cos(twist)
                scale = radius_here/radius if radius > 1e-8 else 0
                frames[u] = (center, x_axis, y_axis, scale)
            points = []
            cache = {}
            for u, x, y in self._rest_vertices:
                center, axis, side, scale = frames[u]
                key = (u, x, y)
                if key not in cache:
                    cache[key] = center + axis*(x*scale) + side*(y*scale)
                points.append(cache[key])
            vertex, normal = GeomVertexWriter(self._data[index], 'vertex'), GeomVertexWriter(self._data[index], 'normal')
            for i in range(0, len(points), 3):
                face_normal = (points[i+1]-points[i]).cross(points[i+2]-points[i])
                if face_normal.lengthSquared() > 1e-12:
                    face_normal.normalize()
                else:
                    face_normal = Vec3(0, 1, 0)
                for point in points[i:i+3]:
                    vertex.setData3(point)
                    normal.setData3(face_normal)

    @staticmethod
    def _extension(index, extent):
        return max(0.0, min(1.0, (extent-index*.22)/.78))

    @staticmethod
    def _rest_center(z):
        profile = [(0, 0), (.0675, -.00805), (.135, -.0069), (.207, .00575),
                   (.279, .02875), (.351, .0644), (.432, .115)]
        for (a, x), (b, y) in pairwise(profile):
            if z <= b:
                return x + (y-x)*max(0.0, (z-a)/(b-a))
        return profile[-1][1]

    @staticmethod
    def _radius(radius, center, extent):
        radius *= extent**.4
        if center[1] < .23:
            radius = min(radius, max(.008, .12-abs(center[0])),
                         max(.008, center[2]+.043), max(.008, .32-center[2]))
        return radius
