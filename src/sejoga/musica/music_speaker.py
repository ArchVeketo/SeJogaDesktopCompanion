"""A low-poly speaker ejected from the cabinet at the start of a dance."""
from math import cos, exp, sin, tau

from panda3d.core import (
    CardMaker,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    Point3,
    Texture,
    Vec3,
)

# ─────────────────────────────────────────────────────────────────────────────
# Orientação "de frente" do mascote (rota B / Frente 3).
# ─────────────────────────────────────────────────────────────────────────────
# Antes da rota B, o modelo era girado 180° por model_np.setH(180) e toda a
# geometria/posição da caixa musical foi autorada NESSE referencial já girado:
# o ponto da caixa era transformado por ``model_np.getMat()`` (que incluía o
# flip) e o rótulo encarava a câmera por heading 180.
#
# Na rota B o flip saiu do código e foi assado no nó-raiz do .gltf — então
# ``model_np`` NÃO carrega mais o 180°; ele vive num filho (node60). Para a
# caixa nascer no MESMO lugar/orientação de antes (sem regressão), recompomos
# aqui o referencial visível do mascote: a matriz de ``model_np`` composta com
# este heading. É o único ponto da caixa que dependia do flip morar no código.
# A_VALIDAR (GPU): lado/altura/orientação da caixa na nova montagem.
FACING_MASCOTE_GRAUS = 180.0
# Inclinação extra da caixa em relação ao mascote (leve giro de palco). Somada
# ao facing para o heading final do corpo da caixa.
FACING_CAIXA_EXTRA_GRAUS = 8.0


def box(parent, name, size, color):
    data = GeomVertexData(name, GeomVertexFormat.getV3c4(), Geom.UHStatic)
    writer = GeomVertexWriter(data, 'vertex')
    colors = GeomVertexWriter(data, 'color')
    corners = ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))
    tris = GeomTriangles(Geom.UHStatic)
    for face_index, face in enumerate(((0,1,2,3),(4,7,6,5),(0,4,5,1),(3,2,6,7),(0,3,7,4),(1,5,6,2))):
        shade = (.65,1.3,.8,1,.7,.9)[face_index]
        for index in face:
            x,y,z=corners[index]
            writer.addData3(x*size[0]/2,y*size[1]/2,z*size[2]/2)
            colors.addData4(*(min(1,v*shade) for v in color[:3]),color[3])
        start=face_index*4
        tris.addVertices(start,start+1,start+2);tris.addVertices(start,start+2,start+3)
    geom=Geom(data);geom.addPrimitive(tris);node=GeomNode(name);node.addGeom(geom)
    result=parent.attachNewNode(node);result.setTwoSided(True)
    return result


def disc(parent, radius, color):
    data=GeomVertexData('speaker-disc',GeomVertexFormat.getV3c4(),Geom.UHStatic)
    writer=GeomVertexWriter(data,'vertex');colors=GeomVertexWriter(data,'color')
    writer.addData3(0,.012,0);colors.addData4(*color)
    for i in range(13):
        angle=i/12*tau
        writer.addData3(cos(angle)*radius,0,sin(angle)*radius)
        colors.addData4(color[0]*.65,color[1]*.65,color[2]*.65,1)
    triangles=GeomTriangles(Geom.UHStatic)
    for i in range(12):triangles.addVertices(0,i+1,i+2)
    geom=Geom(data);geom.addPrimitive(triangles)
    node=GeomNode('faceted-speaker-cone');node.addGeom(geom)
    result=parent.attachNewNode(node);result.setTwoSided(True)
    return result


class MusicSpeaker:
    def __init__(self, renderer):
        self.renderer=renderer
        self._measure_character()
        self.width=self.character_size.x*1.20
        self.height=self.character_size.z*1.15
        self.depth=self.character_size.x*.40
        self.final_position=Point3(-self.width*.36,-.10-self.depth/2,self.floor_z+self.height/2)
        self.root=renderer.model_anchor.attachNewNode('music-speaker')
        self.root.setLightOff(1);self.root.setShaderOff(1);self.root.setCollideMask(0)
        self.geometry=self.root.attachNewNode('speaker-geometry')
        self.geometry.setScale(self.width/.28,self.depth/.19,self.height/.46)
        box(self.geometry,'speaker-cabinet',(.28,.19,.46),(.07,.06,.10,1))
        self.cones=[]
        for z,radius in ((-.08,.105),(.125,.057)):
            # Faceted concentric plates give the grille visible depth.
            ring=disc(self.geometry,radius,(.32,.16,.35,1))
            ring.setPos(0,.11,z)
            cone=disc(self.geometry,radius*.68,(.12,.09,.16,1))
            cone.setPos(0,.13,z);self.cones.append(cone)
        badge=box(self.geometry,'speaker-pink-label',(.26,.015,.056),(.95,.14,.48,1))
        badge.setPos(0,.145,.201)
        self._add_graffiti()
        from sejoga.musica.speaker_effects import SpeakerEffects
        self.effects=SpeakerEffects(self.geometry)
        self.age=0.0;self.visibility=0.0;self.was_dancing=False
        self.ejecting=False
        self.landed=False
        self._landing_sound_played=False
        self.current_position=Point3(0,.19,.86)
        self.root.hide()

    def _measure_character(self):
        from sejoga.animacao.poses_base import pose_idle
        from sejoga.nucleo.esqueleto import IdlePersonality
        rig=self.renderer.rig
        previous=rig.pose()
        rig.reset();pose_idle(rig,0,IdlePersonality.CALM)
        self.renderer.apply_rig_pose(rig.pose())
        bounds=[self.renderer._rig_nodes[name].getTightBounds(self.renderer.model_np)
                for name in ('head','body','right-arm','left-arm','legs','left-feet','right-feet')]
        low=Vec3(*(min(b[0][i] for b in bounds) for i in range(3)))
        high=Vec3(*(max(b[1][i] for b in bounds) for i in range(3)))
        self.character_size=high-low
        self.floor_z=low.z
        self.renderer.apply_rig_pose(previous)
        rig.current=previous

    def _add_graffiti(self):
        from panda3d.core import PNMImage, StringStream

        from sejoga.nucleo.recursos import assets_dir
        # Read through Python's native filesystem. Frozen Panda's virtual
        # filesystem can reject the onedir path even when the PNG exists.
        image=PNMImage()
        path=assets_dir()/'textures'/'speaker_graffiti.png'
        if not image.read(StringStream(path.read_bytes()),'speaker_graffiti.png'):
            raise RuntimeError('Could not decode speaker graffiti texture')
        texture=Texture('speaker-graffiti')
        texture.load(image)
        texture.setMinfilter(Texture.FTLinear);texture.setMagfilter(Texture.FTLinear)
        card=CardMaker('speaker-graffiti')
        card.setFrame(-.12,.12,-.025,.025)
        label=self.geometry.attachNewNode(card.generate())
        label.setPos(0,.155,.201)
        label.setH(180)
        label.setTexture(texture,1);label.setTwoSided(True)

    def _matriz_visivel(self):
        """Matriz do referencial VISÍVEL do mascote (model_np + facing da rota B).

        Reproduz o que ``model_np.getMat()`` entregava antes da rota B, quando o
        flip de 180° ainda morava no código (``model_np.setH(180)``). Agora o
        flip está assado no asset e ``model_np`` não o carrega mais; recompomos
        o MESMO referencial reaplicando o heading de facing sobre a posição e a
        escala atuais de ``model_np``, sem depender de onde o 180° é aplicado.
        """
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
        value=max(0,min(1,(self.age-2.2)/.8))
        return value*value*(3-2*value)

    @property
    def support_plane(self):
        return Point3(self.final_position.x,self.final_position.y+self.depth/2,self.floor_z+.55)

    def support_in_stage(self):
        point=Point3(self.width/2,0,self.floor_z+.55-self.final_position.z)
        point=self.renderer.model_anchor.getRelativePoint(self.root,point)
        normal=self.root.getQuat(self.renderer.model_anchor).xform(Vec3(1,0,0)).normalized()
        return point,normal

    def update(self, dt, dancing, phase, energy,bass=0):
        if dancing and not self.was_dancing:
            self.age=0
            self._landing_sound_played=False
            self.current_position=Point3(0,.19,.86)
        self.was_dancing=dancing
        self.age += dt
        self.visibility += ((1 if dancing else 0)-self.visibility)*(1-exp(-dt*5))
        self.ejecting=dancing and .55 <= self.age < 2.3
        self.landed=self.age >= 2.3 and self.visibility > .95
        if self.visibility < .005 or (dancing and self.age < 1.45):
            self.root.hide();return
        self.root.show()
        u=max(0,min(1,(self.age-1.45)/.60));ease=u*u*(3-2*u)
        start=Point3(0,.19,.86)
        position=start*(1-ease)+self.final_position*ease
        position.z += self.height*.20*sin(u*3.14159265)
        if 2.05 <= self.age < 2.35:
            position.z += self.height*.035*sin((self.age-2.05)/.30*3.14159265)
        self.current_position=Point3(position)
        pulse=max(0,cos(phase))**6
        strength=max(0,min(1,energy*.7+bass*.9))
        if self.age > 2.3:
            position.x += self.width*.0025*sin(phase*9)*strength
            position.y += self.depth*.008*sin(phase*7)*strength
        self.root.setPos(self._matriz_visivel().xformPoint(position))
        self.root.setH(FACING_MASCOTE_GRAUS+FACING_CAIXA_EXTRA_GRAUS)
        self.root.setScale(self.renderer.model_np.getScale().x*max(.005,self.visibility*(.08+.92*ease)))
        self.root.setR((1-ease)*-100+(sin(phase*6)*.6*strength if self.age > 2.3 else 0))
        for cone in self.cones:
            cone.setY(.13+pulse*.018*strength)
            cone.setScale(1+pulse*.14*strength)
        self.effects.update(self.age,phase,strength)
        if self.age >= 2.05 and not self._landing_sound_played:
            self._landing_sound_played=True
            settings=self.renderer.showbase.settings.audio
            controller=self.renderer.showbase.animation_controller
            if settings.enabled and controller._dance_preview_remaining <= 0:
                from sejoga.musica.sound_effects import play_speaker_landing
                play_speaker_landing(settings.master_volume)
