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
    data=GeomVertexData('speaker-slime',GeomVertexFormat.getV3c4(),Geom.UHStatic)
    vertices=GeomVertexWriter(data,'vertex');colors=GeomVertexWriter(data,'color')
    points=((-1,0,0),(1,0,0),(.7,.7,-.85),(0,1,-1),(-.7,.7,-.85),(0,-.5,-.3))
    for x,y,z in points:
        vertices.addData3(x,y,z)
        colors.addData4(1,.08+.08*max(0,y),.48+.08*max(0,y),1)
    triangles=GeomTriangles(Geom.UHStatic)
    for a,b,c in ((0,1,2),(0,2,4),(2,3,4),(0,5,1),(1,5,2),(2,5,3),(3,5,4),(4,5,0)):
        triangles.addVertices(a,b,c)
    geom=Geom(data);geom.addPrimitive(triangles)
    node=GeomNode('faceted-speaker-slime');node.addGeom(geom)
    return node


class SpeakerEffects:
    def __init__(self, geometry):
        template=slime_mesh()
        self.slime=[]
        for index,x in enumerate((-.105,-.045,.035,.10)):
            node=geometry.attachNewNode(template.makeCopy())
            node.setPos(x,.17,.225-index*.006)
            node.setTwoSided(True);node.setCollideMask(0);node.hide()
            self.slime.append(node)
        self.waves=[]
        for _index in range(3):
            lines=LineSegs('speaker-sound-wave')
            lines.setThickness(1.5)
            lines.setColor(1,.2,.6,1)
            for step in range(25):
                angle=step/24*tau
                point=(cos(angle)*.108,.172,sin(angle)*.108-.08)
                (lines.moveTo if step==0 else lines.drawTo)(*point)
            node=geometry.attachNewNode(lines.create())
            node.setCollideMask(0);node.hide()
            self.waves.append(node)

    def update(self,age,phase,strength):
        flow=max(0,min(1,(age-1.45)/2.8))
        dry=max(0,min(1,(6.5-age)/1.2))
        for index,node in enumerate(self.slime):
            if age < 1.45 or dry <= 0:
                node.hide();continue
            node.show()
            length=(.025+flow*(.12+.025*(index%2)))
            node.setScale((.007+.003*(index%2))*dry,.012*dry,length)
        for index,node in enumerate(self.waves):
            progress=(phase/tau+index/3)%1
            if age < 2.1 or strength < .06 or progress > .75:
                node.hide();continue
            node.show()
            node.setScale(1+progress*.22)
            node.setColorScale(1,.65+.35*strength,1,1)
