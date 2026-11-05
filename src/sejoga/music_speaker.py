"""A low-poly speaker ejected from the cabinet at the start of a dance."""
from math import cos, exp, sin, tau
from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter


def box(parent, name, size, color):
    data = GeomVertexData(name, GeomVertexFormat.getV3(), Geom.UHStatic)
    writer = GeomVertexWriter(data, 'vertex')
    for x,y,z in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)):
        writer.addData3(x*size[0]/2,y*size[1]/2,z*size[2]/2)
    tris = GeomTriangles(Geom.UHStatic)
    for face in ((0,1,2,3),(4,7,6,5),(0,4,5,1),(3,2,6,7),(0,3,7,4),(1,5,6,2)):
        tris.addVertices(face[0],face[1],face[2]);tris.addVertices(face[0],face[2],face[3])
    geom=Geom(data);geom.addPrimitive(tris);node=GeomNode(name);node.addGeom(geom)
    result=parent.attachNewNode(node);result.setColor(*color);result.setTwoSided(True)
    return result


class MusicSpeaker:
    def __init__(self, renderer):
        self.renderer=renderer
        self.root=renderer.model_anchor.attachNewNode('music-speaker')
        self.root.setLightOff(1);self.root.setShaderOff(1);self.root.setCollideMask(0)
        box(self.root,'speaker-cabinet',(.28,.19,.46),(.07,.06,.10,1))
        self.cones=[]
        for z,radius in ((-.08,.105),(.125,.057)):
            # Faceted concentric plates give the grille visible depth.
            ring=box(self.root,'woofer',(radius*1.7,.025,radius*1.7),(.25,.12,.27,1))
            ring.setPos(0,.11,z);ring.setR(45)
            cone=box(self.root,'cone',(radius,.018,radius),(.10,.08,.13,1))
            cone.setPos(0,.13,z);self.cones.append(cone)
        self.age=0.0;self.visibility=0.0;self.was_dancing=False
        self.root.hide()

    def update(self, dt, dancing, phase, energy):
        if dancing and not self.was_dancing:
            self.age=0
        self.was_dancing=dancing
        self.age += dt
        self.visibility += ((1 if dancing else 0)-self.visibility)*(1-exp(-dt*5))
        if self.visibility < .005:
            self.root.hide();return
        self.root.show()
        u=min(1,self.age/1.15);ease=u*u*(3-2*u)
        from panda3d.core import Point3
        position = Point3(-.40*ease,.19+.06*sin(u*3.14159),.86*(1-ease)+.25*ease+.12*sin(u*3.14159))
        self.root.setPos(self.renderer.model_np.getMat().xformPoint(position))
        self.root.setH(self.renderer.MODEL_FACING_HEADING)
        self.root.setScale(self.renderer.model_np.getScale().x*max(.005,self.visibility*(.12+.88*ease)))
        self.root.setR((1-ease)*-100)
        for cone in self.cones:
            cone.setY(.13+max(0,sin(phase))*.012*energy)
