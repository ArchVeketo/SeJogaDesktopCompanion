"""Small falling slime droplets, attached to the model coordinate space."""
import random

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    TransparencyAttrib,
    Vec3,
)


class TentacleDrips:
    def __init__(self, parent):
        self.parent = parent
        self.rng = random.Random()
        self.remaining = .6
        self.drops = []
        data = GeomVertexData('pink-slime', GeomVertexFormat.getV3(), Geom.UHStatic)
        writer = GeomVertexWriter(data, 'vertex')
        for point in ((0, 0, 1.5), (.7, 0, 0), (0, .7, 0),
                      (-.7, 0, 0), (0, -.7, 0), (0, 0, -.9)):
            writer.addData3(*point)
        triangles = GeomTriangles(Geom.UHStatic)
        for a, b in ((1, 2), (2, 3), (3, 4), (4, 1)):
            triangles.addVertices(0, a, b)
            triangles.addVertices(5, b, a)
        geom = Geom(data)
        geom.addPrimitive(triangles)
        self.template = GeomNode('pink-slime-drop')
        self.template.addGeom(geom)

    def spray(self, tentacles):
        """A short outward burst of pink droplets at the sneeze."""
        limbs = [t for t in tentacles if t.state.value != 'dormant']
        for _ in range(min(10, 16-len(self.drops))):
            if not limbs:
                break
            limb = self.rng.choice(limbs)
            node = self.parent.attachNewNode(self.template.makeCopy())
            node.setPos(limb.anchor + limb.reference_front*.18)
            size = self.rng.uniform(.006, .013)
            node.setScale(size)
            node.setColor(1, .08, .48, 1)
            node.setLightOff(1)
            node.setShaderOff(1)
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setCollideMask(0)
            velocity = limb.reference_front*self.rng.uniform(.35, .8)
            velocity += Vec3(self.rng.uniform(-.3,.3), 0, self.rng.uniform(-.05,.3))
            self.drops.append([node, velocity, 0, size])

    def update(self, dt, tentacles):
        dt = max(0, min(.05, dt))
        self.remaining -= dt
        exposed = [t for t in tentacles if t.reveal > .45 and t.state.value != 'dormant']
        if exposed and self.remaining <= 0 and len(self.drops) < 16:
            limb = self.rng.choice(exposed)
            index = max(1, int((len(limb.segments)-1) * limb.reveal * self.rng.uniform(.5, .95)))
            node = self.parent.attachNewNode(self.template.makeCopy())
            node.setPos(limb.segments[index].pos)
            size = self.rng.uniform(.009, .015) * limb.girth_scale
            node.setScale(size)
            node.setColor(1, .08, .48, 1)
            node.setLightOff(1)
            node.setShaderOff(1)
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setCollideMask(0)
            self.drops.append([node, Vec3(self.rng.uniform(-.025, .025), 0, -.025), 0, size])
            self.remaining = self.rng.uniform(.4, 1.1)
        alive = []
        for drop in self.drops:
            node, velocity, age, size = drop
            age += dt
            if age >= 1.0:
                node.removeNode()
                continue
            velocity.z -= .65 * dt
            node.setPos(node.getPos() + velocity * dt)
            node.setScale(size, size, size * (1 + age * .7))
            node.setColor(1, .08, .48, min(1, (1-age)/.3))
            drop[2] = age
            alive.append(drop)
        self.drops = alive
