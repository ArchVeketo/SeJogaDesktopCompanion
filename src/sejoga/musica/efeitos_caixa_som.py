"""Low-poly slime and visible woofer waves; no transparent texture planes."""

from math import cos, sin, tau

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LineSegs,
)


def slime_mesh():
    """Cria a malha de gosma da caixa de som."""
    data = GeomVertexData("speaker-slime", GeomVertexFormat.getV3c4(), Geom.UHStatic)
    vertices = GeomVertexWriter(data, "vertex")
    colors = GeomVertexWriter(data, "color")
    points = (
        (-1, 0, 0),
        (1, 0, 0),
        (0.7, 0.7, -0.85),
        (0, 1, -1),
        (-0.7, 0.7, -0.85),
        (0, -0.5, -0.3),
    )
    for x, y, z in points:
        vertices.addData3(x, y, z)
        colors.addData4(1, 0.08 + 0.08 * max(0, y), 0.48 + 0.08 * max(0, y), 1)
    triangles = GeomTriangles(Geom.UHStatic)
    for a, b, c in (
        (0, 1, 2),
        (0, 2, 4),
        (2, 3, 4),
        (0, 5, 1),
        (1, 5, 2),
        (2, 5, 3),
        (3, 5, 4),
        (4, 5, 0),
    ):
        triangles.addVertices(a, b, c)
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode("faceted-speaker-slime")
    node.addGeom(geom)
    return node


class SpeakerEffects:
    """Efeitos visuais da caixa de som."""

    def __init__(self, geometry):
        """Monta os efeitos sobre a geometria da caixa."""
        template = slime_mesh()
        self.slime = []
        for index, x in enumerate((-0.105, -0.045, 0.035, 0.10)):
            node = geometry.attachNewNode(template.makeCopy())
            node.setPos(x, 0.17, 0.225 - index * 0.006)
            node.setTwoSided(True)
            node.setCollideMask(0)
            node.hide()
            self.slime.append(node)
        self.waves = []
        for _index in range(3):
            lines = LineSegs("speaker-sound-wave")
            lines.setThickness(1.5)
            lines.setColor(1, 0.2, 0.6, 1)
            for step in range(25):
                angle = step / 24 * tau
                point = (cos(angle) * 0.108, 0.172, sin(angle) * 0.108 - 0.08)
                (lines.moveTo if step == 0 else lines.drawTo)(*point)
            node = geometry.attachNewNode(lines.create())
            node.setCollideMask(0)
            node.hide()
            self.waves.append(node)

    def update(self, age, phase, strength):
        """Anima os efeitos com a idade, a fase e a força."""
        flow = max(0, min(1, (age - 1.45) / 2.8))
        dry = max(0, min(1, (6.5 - age) / 1.2))
        for index, node in enumerate(self.slime):
            if age < 1.45 or dry <= 0:
                node.hide()
                continue
            node.show()
            length = 0.025 + flow * (0.12 + 0.025 * (index % 2))
            node.setScale((0.007 + 0.003 * (index % 2)) * dry, 0.012 * dry, length)
        for index, node in enumerate(self.waves):
            progress = (phase / tau + index / 3) % 1
            if age < 2.1 or strength < 0.06 or progress > 0.75:
                node.hide()
                continue
            node.show()
            node.setScale(1 + progress * 0.22)
            node.setColorScale(1, 0.65 + 0.35 * strength, 1, 1)
