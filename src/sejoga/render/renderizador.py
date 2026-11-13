"""Panda3DRenderer — render 3D do mascote (Panda3D).

Extraído de janela.py sem reescrever a lógica de render. Mantém os mesmos
imports do lado engine: Panda3D, o loader glTF e os módulos de tentáculo.
Preserva nomes/hierarquia do rig, a calibração do color key (feita em janela.py)
e os guards IsWindow/erro 1400 (que permanecem em OverlayApp).
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any

# Panda3D GLTF loader registers support for .gltf and .glb files.
import gltf
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AntialiasAttrib,
    Mat4,
    NodePath,
    Point3,
    TransformState,
    Vec3,
)

from sejoga.animacao import danca_tuning as _danca
from sejoga.animacao import movimento_corpo_tuning as _tune
from sejoga.animacao.controlador_animacao import AnimationState
from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.animacao.squash_stretch import squash_stretch_composto
from sejoga.musica.caixa_som import (
    BATIDAS_ARREMESSO_S,
    FIM_ARREMESSOS_S,
    INICIO_SALTO_S,
)
from sejoga.nucleo.cinematica import BASE_ADICIONAL_GRAUS
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rig
from sejoga.nucleo.modelo import load_model
from sejoga.nucleo.recursos import resolve_model
from sejoga.render.dedos_malha import fatiar_dedos
from sejoga.render.fio_fone_malha import MalhaFioFone, ocultar_peca_rigida_do_fio
from sejoga.render.rig_flexivel import no_de_facing
from sejoga.tentaculos import coreografia_porta as coreo
from sejoga.tentaculos.restricoes_tentaculos import ObstacleBox, TentacleContacts
from sejoga.tentaculos.sistema_tentaculos import (
    TentacleDirector,
    TentaclePool,
    TentacleState,
    create_tentacle_geometry,
    update_tentacle_render,
)

logger = logging.getLogger(__name__)


# ============================================================
# Parâmetros estruturais do render (SimplePBR, antialias, contorno).
# ============================================================

# Amostras de MSAA do pipeline SimplePBR; a cobertura parcial alimenta o
# chroma resolve (ver chroma_resolve/chroma_tuning).
MSAA_AMOSTRAS = 4
# Teto de luzes dinâmicas do SimplePBR.
MAX_LUZES_PBR = 8
# Alpha mínimo da textura para o fragmento do contorno não ser descartado:
# abaixo disso a borda "vaza" por faces transparentes do modelo.
CONTORNO_ALPHA_DISCARD = 0.05


_NINJA_SMOKE_OFFSETS = (
    (-0.9, -0.35, -0.25, 0.55),
    (0.85, -0.30, -0.15, 0.52),
    (-0.45, -0.45, 0.65, 0.62),
    (0.50, -0.42, 0.58, 0.58),
    (0.0, -0.50, 0.25, 0.70),
    (-1.1, -0.20, 0.35, 0.46),
    (1.1, -0.20, 0.40, 0.46),
    (0.0, -0.40, 0.95, 0.50),
    (-0.35, -0.35, -0.75, 0.48),
    (0.35, -0.35, -0.70, 0.48),
)

_LEGO_SCATTER_PARTS = (
    "left-feet",
    "right-feet",
    "canela-direita",
    "canela-esquerda",
    "joelho-direito",
    "joelho-esquerdo",
    "coxa-direita",
    "coxa-esquerda",
    "hand",
    "hand2",
    "ant-arm",
    "ant-arm2",
    "right-arm",
    "left-arm",
    "door",
    "fones",
    "antena-direita",
    "antena-esquerda",
    "head",
    "peitoral",
    "abdomen",
    "cintura",
)


# ============================================================
# Panda3D Renderer
# ============================================================


class Panda3DRenderer:
    """Encapsula Panda3D render e modelo."""

    FRAME_FILL = 0.66

    def __init__(self, showbase: ShowBase, hwnd: int, width: int, height: int):  # noqa: PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        """Monta a cena, o modelo, o contorno e os pivôs do rig."""
        self.showbase = showbase
        self.hwnd = hwnd
        self.width = width
        self.height = height
        self.model_np: NodePath | None = None
        self.model_anchor: NodePath | None = None
        self.rig: Rig | None = None
        self._rig_nodes: dict[str, NodePath] = {}
        self._outline_nodes: dict[str, NodePath] = {}
        self._rig_base_hpr: dict[str, tuple[float, float, float]] = {}
        self._rig_base_pos: dict[str, Any] = {}
        self._view_width = 1.0
        self._view_height = 1.0
        self._view_target_z = 1.0
        self._fit_scale = 1.0
        self._model_dimensions = Vec3(0, 0, 0)
        self._model_center = Vec3(0, 0, 0)
        self._model_min_z = 0.0
        self._model_radius_px = 0.0
        self.tentacles: Any = None
        self.tentacle_pool: TentaclePool | None = None
        self.tentacle_director: TentacleDirector | None = None
        self._door_requested = 0.0
        # Criados sob demanda no primeiro frame de física; pré-inicializados
        # para evitar hasattr por frame em apply_body_motion.
        self._suspension_pivot = None
        self._squash_pivot = None
        self._shadow_np = None
        self._physics_velocity = (0.0, 0.0)
        self._is_grounded = True
        from sejoga.animacao.movimento_corpo import GiroCorpo, Spring

        self._dance_stage_yaw = Spring(1.4, 0.85)
        self._subida_palco = Spring(1.8, 0.95)
        self._assento_palco = Spring(2.2, 0.95)
        self._tempo_cobertura = 0.0
        self._cobertura_roupa = []
        # Nó dedicado do GIRO DE CORPO LIMITADO (virar de lado). Criado junto do
        # _suspension_pivot no primeiro frame de física. Mantém intactos o
        # setH(180) base da malha (model_np), o tilt de voo (model_anchor) e o
        # pivô de arraste/queda (_suspension_pivot): ver apply_body_motion.
        self._body_facing = None
        self._giro_corpo = GiroCorpo()
        # Respiração do contorno: espessura base em repouso e driver suavizado.
        from sejoga.render.dinamica_contorno import RespiracaoContorno

        self._outline_base_thickness = 0.0
        self._outline_breath = 0.0
        self._outline_enabled = True
        self._outline_respiracao = RespiracaoContorno()
        self._user_scale = 1.0
        self._escala_profundidade = 1.0
        self._subida_profundidade = 0.0
        self._pbr_pipeline = None
        self._fx_root = None
        self._fx_smoke_nodes: list = []
        self._fx_ash_nodes: list = []
        self._fx_blue_nodes: list = []
        self._lego_snapshot: list = []
        self._lego_root = None
        self._lego_floor_z = -0.5
        self._intro_pivot = None
        self._exit_orig_anchor_parent = None
        self._exit_orig_anchor_tf = None
        self._intro_orig_anchor_pos = None
        self._intro_orig_foot_local_z: float | None = None

        self._setup_scene()
        self._load_model()
        from sejoga.render.corpo_inferior import LowerBody

        self.lower_body = LowerBody(self)
        self._setup_picking()

    def _setup_picking(self) -> None:
        # Invariante: chamado apos _load_model(), que define model_np/tentacle_pool.
        assert self.model_np is not None and self.tentacle_pool is not None
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
            self.showbase.cam.node(),
            2.0 * x / self.width - 1.0,
            1.0 - 2.0 * y / self.height,
        )
        self._pick_queue.clearEntries()
        self._pick_traverser.traverse(self.model_np)
        if self._pick_queue.getNumEntries():
            self._pick_queue.sortEntries()
            self._pick_point_model = self._pick_queue.getEntry(0).getSurfacePoint(
                self.model_np
            )
            picked = self._pick_queue.getEntry(0).getIntoNodePath()
            self._pick_part = "body"
            while not picked.isEmpty() and picked != self.model_np:
                name = picked.getName()
                if name in (
                    "right-arm",
                    "left-arm",
                    "left-feet",
                    "right-feet",
                    "legs",
                    "head",
                ):
                    self._pick_part = name
                    break
                picked = picked.getParent()
        return self._pick_queue.getNumEntries() > 0

    def _setup_scene(self) -> None:  # noqa: PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
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
        dirlight.getLens().setFilmSize(24, 24)
        dirlight.getLens().setNearFar(0.5, 65)
        self._luz_palco = dirlight_np
        self.showbase.render.setLight(dirlight_np)

        # SimplePBR
        self._filter_manager = None
        try:
            import simplepbr

            pipeline = simplepbr.init(
                use_normal_maps=False,
                use_emission_maps=False,
                enable_shadows=True,
                max_lights=MAX_LUZES_PBR,
                msaa_samples=MSAA_AMOSTRAS,
            )
            self._pbr_pipeline = pipeline
            self._filter_manager = pipeline._filtermgr
            for buf in self._filter_manager.buffers:
                buf.setClearStencilActive(True)
                buf.setClearStencil(0)
            if self.showbase.win:
                self.showbase.win.setClearStencilActive(True)
                self.showbase.win.setClearStencil(0)
            from sejoga.render.resolucao_croma import install_chroma_resolve

            install_chroma_resolve(
                pipeline, self.showbase.settings.window.colorkey_color
            )
            pipeline._post_process_quad.setShaderInput(
                "u_viewport_size", (float(self.width), float(self.height))
            )
        except ImportError:
            logger.warning("SimplePBR não disponível: sombras e PBR desativados")
        except Exception as e:
            logger.error("Falha ao inicializar SimplePBR: %s", e)

    def _load_model(self) -> None:  # noqa: PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        model_path = resolve_model()
        model = load_model(model_path)
        rig = Rig.from_model(model)

        if rig.missing:
            logger.warning("Grupos de rig ausentes: %s", rig.missing)

        self.rig = rig

        # panda3d-gltf 1.x expõe load_model diretamente no módulo.
        model_np = NodePath(gltf.load_model(str(model_path)))
        # O asset rigado atual não tem mais os planos cruzados de exportação em
        # volta das antenas; a lista fica para o overlay de depuração.
        self._hidden_export_planes = []
        # O fio do fone do asset (``fio do fone``) continua visível: MalhaFioFone
        # move seus planos pela física da corda. Só um fio rígido legado some.
        ocultar_peca_rigida_do_fio(model_np)
        # Dedos viram cadeia de pivôs ANTES do copyTo do contorno (herda a cadeia).
        fatiar_dedos(model_np)
        # Rota B (Frente 3): a orientação "de frente" agora mora no ASSET —
        # o nó-raiz do mario.gltf carrega rotation=[0,1,0,0] (180° em torno de
        # +Y). O antigo model_np.setH(180) foi REMOVIDO; a malha já nasce com o
        # rosto para a câmera (-Y). A orientação de mundo de cada nó do rig é
        # idêntica à de antes (o flip só trocou de lugar: código -> asset), por
        # isso a convenção de braço (eixo longo ±X, elevação=roll) e a câmera
        # continuam válidas sem recalibrar. Ver .agents/tasks/frente3-animacao/
        # mapa-eixos.md.
        bounds = model_np.getTightBounds()
        if not bounds:
            raise ValueError(
                f"não foi possível calcular os limites do modelo: {model_path}"
            )
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
        self._setup_shadow()
        self.set_visual_scale(self.showbase.settings.window.scale)

        self._apply_rig_to_model()
        from sejoga.render.rig_flexivel import FlexibleRig

        self.flexible_rig = FlexibleRig(self)

        unit_scale = float(self._view_height / self.height / self.model_np.getScale().x)
        head_node = self._rig_nodes["head"]
        spawn_points = [
            self.model_np.getRelativePoint(head_node, Vec3(0.03, 0.045, 0.13)),
            self.model_np.getRelativePoint(head_node, Vec3(0.05, 0.050, 0.17)),
            self.model_np.getRelativePoint(head_node, Vec3(-0.01, 0.055, 0.14)),
            self.model_np.getRelativePoint(head_node, Vec3(0.035, 0.040, 0.09)),
            self.model_np.getRelativePoint(head_node, Vec3(0.01, 0.060, 0.12)),
            self.model_np.getRelativePoint(head_node, Vec3(0.02, 0.035, 0.14)),
            self.model_np.getRelativePoint(head_node, Vec3(-0.02, 0.035, 0.09)),
            self.model_np.getRelativePoint(head_node, Vec3(0.06, 0.045, 0.14)),
            self.model_np.getRelativePoint(head_node, Vec3(0.04, 0.055, 0.19)),
            self.model_np.getRelativePoint(head_node, Vec3(-0.02, 0.050, 0.07)),
        ]
        self.tentacle_pool = TentaclePool(
            self.rig,
            self.model_np,
            self.outline_np,
            spawn_points,
            rng=random.Random(),
            unit_scale=unit_scale,
        )
        from sejoga.tentaculos.gotas_tentaculos import TentacleDrips

        self.tentacle_drips = TentacleDrips(self.model_np)
        from sejoga.animacao.gestos_dedos import FingerGestures

        self.finger_gestures = FingerGestures(self)
        from sejoga.musica.caixa_som import MusicSpeaker

        self.music_speaker = MusicSpeaker(self)
        for tentacle in self.tentacle_pool.tentacles:
            create_tentacle_geometry(tentacle, self.model_np, self.outline_np)
        self.tentacle_director = TentacleDirector(
            self.tentacle_pool,
            self.rig,
            self.model_np,
            self.outline_np,
            self._rig_nodes.get("door"),
            rng=random.Random(),
        )
        self._tentacles_were_visible = False
        self._tentacle_anchor_local = [
            head_node.getRelativePoint(self.model_np, t.anchor)
            for t in self.tentacle_pool.tentacles
        ]
        head_front = self.model_np.getRelativeVector(head_node, Vec3(0, 1, 0)).normalized()
        for t in self.tentacle_pool.tentacles:
            t.reference_front = Vec3(head_front)
        self._setup_tentacle_contacts()
        self.fio_fone = MalhaFioFone(self)
        self.set_outline_settings(self.showbase.settings.window)
        self.set_model_screen_position(
            self.width / 2,
            self.height - self._model_radius_px - 35,
        )

    def set_visual_scale(
        self,
        scale: float,
        *,
        escala_profundidade: float | None = None,
        subida_fracao: float | None = None,
    ) -> None:
        """Atualiza a escala sem deslocar o centro nem os pés do personagem."""
        self._user_scale = scale
        if escala_profundidade is not None:
            self._escala_profundidade = escala_profundidade
        if subida_fracao is not None:
            self._subida_profundidade = subida_fracao
        if not self.model_np:
            return
        model_scale = self._fit_scale * self._user_scale * self._escala_profundidade
        units_per_pixel_z = self._view_height / self.height
        elevacao_z = (
            self._subida_profundidade
            * self._model_dimensions.z
            * self._fit_scale
            * self._user_scale
        )
        self.model_np.setScale(model_scale)
        self.model_np.setPos(
            -self._model_center.x * model_scale,
            -self._model_center.y * model_scale,
            -self._model_min_z * model_scale
            - self._model_radius_px * units_per_pixel_z
            + elevacao_z,
        )
        if self.outline_np:
            self.outline_np.setScale(self.model_np.getScale())
            self.outline_np.setPos(self.model_np.getPos())

    def aplicar_profundidade_visual(
        self, escala_profundidade: float, subida_fracao: float
    ) -> None:
        """Aplica a escala e subida da profundidade visual (Opção A de §8.5.1)."""
        if (
            abs(escala_profundidade - self._escala_profundidade) < 1e-4
            and abs(subida_fracao - self._subida_profundidade) < 1e-4
        ):
            return
        self.set_visual_scale(
            self._user_scale,
            escala_profundidade=escala_profundidade,
            subida_fracao=subida_fracao,
        )

    @staticmethod
    def _criar_textura_sombra(size: int = 64):
        from panda3d.core import PNMImage, Texture

        img = PNMImage(size, size, 4)
        cx = (size - 1) * 0.5
        cy = (size - 1) * 0.5
        for y in range(size):
            dy = (y - cy) / (size * 0.34)
            dy2 = dy * dy
            for x in range(size):
                dx = (x - cx) / (size * 0.46)
                r2 = dx * dx + dy2
                # Borda dithered limpa (sem semi-transparência que manche o chroma key).
                opaque = (
                    r2 <= 0.55
                    or (r2 <= 0.85 and (x + y) % 2 == 0)
                    or (r2 <= 1.0 and x % 2 == 0 and y % 2 == 0)
                )
                img.setXelA(x, y, 0.08, 0.07, 0.12, 1.0 if opaque else 0.0)
        tex = Texture("mascot-contact-shadow")
        tex.load(img)
        tex.setMinfilter(Texture.FTNearest)
        tex.setMagfilter(Texture.FTNearest)
        return tex

    def _setup_shadow(self) -> None:
        """Cria sombra de contato estilizada no chão, compatível com color key."""
        from panda3d.core import AlphaTestAttrib, CardMaker, TransparencyAttrib

        card = CardMaker("mascot-shadow-card")
        card.setFrame(-0.5, 0.5, -0.5, 0.5)
        shadow = self.model_anchor.attachNewNode(card.generate())
        shadow.setP(-90)
        shadow.setTexture(self._criar_textura_sombra())
        shadow.setTwoSided(True)
        shadow.setLightOff(1)
        shadow.setShaderOff(1)
        shadow.setTransparency(TransparencyAttrib.MAlpha)
        shadow.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MGreater, 0.5))
        shadow.setCollideMask(0)
        shadow.setBin("background", 10)
        self._shadow_np = shadow

    def _setup_outline(self) -> None:
        # Invariante: chamado dentro de _load_model() apos definir model_np.
        assert self.model_np is not None
        from panda3d.core import CullFaceAttrib, Shader

        vertex = """#version 130
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;
out vec2 outline_uv;
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat3 p3d_NormalMatrix;
// Espessura efetiva do frame (respiração). Cai para outline_thickness quando
// o render não atualiza o runtime, preservando o comportamento estático.
uniform float outline_thickness;
uniform float outline_thickness_runtime;
void main() {
    outline_uv = p3d_MultiTexCoord0;
    float thickness = outline_thickness_runtime > 0.0
        ? outline_thickness_runtime : outline_thickness;
    // Linha "desenhada": faces de perfil (normal perpendicular ao olhar) ganham
    // um pouco mais de espessura que as frontais, dando vida à silhueta low poly
    // em vez de uma borda uniforme dura. Variação limitada para não deformar.
    vec3 view_normal = normalize(p3d_NormalMatrix * p3d_Normal);
    vec3 view_pos = (p3d_ModelViewMatrix * p3d_Vertex).xyz;
    float facing = abs(dot(view_normal, normalize(-view_pos)));
    float orientacao = mix(1.15, 0.9, clamp(facing, 0.0, 1.0));
    gl_Position = p3d_ModelViewProjectionMatrix *
        (p3d_Vertex + vec4(normalize(p3d_Normal) * thickness * orientacao, 0.0));
}
"""
        fragment = f"""#version 130
uniform vec4 outline_color;
uniform bool outline_enabled;
uniform sampler2D p3d_Texture0;
in vec2 outline_uv;
out vec4 fragColor;
void main() {{
    if (!outline_enabled || texture(p3d_Texture0, outline_uv).a < {CONTORNO_ALPHA_DISCARD}) discard;
    fragColor = outline_color;
}}
"""
        self.outline_np = self.model_np.copyTo(self.model_anchor)
        self.outline_np.setName("mascot-outline")
        for tampa in self.outline_np.findAllMatches("**/*-tampa"):
            tampa.removeNode()
        self.outline_np.setShader(Shader.make(Shader.SL_GLSL, vertex, fragment), 1000)
        self.outline_np.setAttrib(
            CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise), 1000
        )
        self.outline_np.setLightOff(1000)
        self.outline_np.setCollideMask(0)
        # Runtime 0 => shader usa a espessura estática até a respiração começar.
        self.outline_np.setShaderInput("outline_thickness_runtime", 0.0)

    def set_outline_settings(self, settings) -> None:
        """Aplica as configurações do contorno."""
        if not self.outline_np:
            return
        self._outline_enabled = bool(settings.outline_enabled)
        self.outline_np.setShaderInput("outline_enabled", self._outline_enabled)
        if not settings.outline_enabled:
            # Disable both the duplicate model and all child shells. The shader
            # guard also suppresses stale per-mesh copies after live settings changes.
            self.outline_np.hide()
            self.outline_np.stash()
            return
        self.outline_np.unstash()
        self.outline_np.show()
        color = settings.outline_color.lstrip("#")
        rgb = tuple(int(color[index : index + 2], 16) / 255 for index in (0, 2, 4))
        self.outline_np.setShaderInput("outline_color", (*rgb, 1.0))
        if self.tentacle_pool:
            for tentacle in self.tentacle_pool.tentacles:
                if tentacle.outline_mesh_node:
                    tentacle.outline_mesh_node.setShaderInput(
                        "outline_color", (0.14, 0.02, 0.07, 1.0), 1
                    )
        # Model units per displayed pixel; the border follows each part's normals.
        visible_height = self.height * self.FRAME_FILL * settings.scale
        thickness = settings.outline_width * self._model_dimensions.z / visible_height
        self.outline_np.setShaderInput("outline_thickness", thickness)
        # Guarda a base e (re)inicia a respiração no estado de repouso.
        self._outline_base_thickness = thickness
        self._outline_breath = float(getattr(settings, "outline_breath", 0.0))
        self._outline_respiracao.reset(thickness)
        self.outline_np.setShaderInput("outline_thickness_runtime", thickness)

    def _update_outline_breath(self, dt, motion) -> None:
        """Modula a espessura do contorno pela respiração do tórax, por frame."""
        if (
            not self.outline_np
            or not self._outline_enabled
            or self.outline_np.isHidden()
        ):
            return
        if self._outline_base_thickness <= 0.0 or self._outline_breath <= 0.0:
            return
        compression = float(getattr(motion, "compression", 0.0))
        thickness = self._outline_respiracao.update(
            dt, self._outline_base_thickness, compression, self._outline_breath
        )
        self.outline_np.setShaderInput("outline_thickness_runtime", thickness)

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
                if not hasattr(self, "_rig_base_scale"):
                    self._rig_base_scale = {}
                self._rig_base_scale[group_name] = node.getScale()
                if not hasattr(self, "_rig_base_mat"):
                    self._rig_base_mat = {}
                self._rig_base_mat[group_name] = node.getMat()
                outline_node = self.outline_np.find(f"**/{group_name}")
                if not outline_node.isEmpty():
                    self._outline_nodes[group_name] = outline_node
                hpr = node.getHpr()
                self._rig_base_hpr[group_name] = (
                    float(hpr.x),
                    float(hpr.y),
                    float(hpr.z),
                )
        self._setup_hand_outline_stencil()

    def _setup_hand_outline_stencil(self) -> None:
        """Elimina listras internas do contorno entre falanges e palma via stencil."""
        from panda3d.core import CullBinManager, StencilAttrib

        cbm = CullBinManager.getGlobalPtr()
        if cbm.findBin("hand-outline") == -1:
            cbm.addBin("hand-outline", CullBinManager.BTUnsorted, 22)
        write_stencil = StencilAttrib.make2Sided(
            True,
            True,
            StencilAttrib.SCFAlways,
            StencilAttrib.SOKeep,
            StencilAttrib.SOKeep,
            StencilAttrib.SOReplace,
            2,
            0xFF,
            0xFF,
            StencilAttrib.SCFAlways,
            StencilAttrib.SOKeep,
            StencilAttrib.SOKeep,
            StencilAttrib.SOReplace,
        )
        test_stencil = StencilAttrib.make2Sided(
            True,
            True,
            StencilAttrib.SCFNotEqual,
            StencilAttrib.SOKeep,
            StencilAttrib.SOKeep,
            StencilAttrib.SOKeep,
            2,
            0xFF,
            0x00,
            StencilAttrib.SCFNotEqual,
            StencilAttrib.SOKeep,
            StencilAttrib.SOKeep,
            StencilAttrib.SOKeep,
        )
        for side in ("hand", "hand2"):
            node = self._rig_nodes.get(side)
            if node:
                node.setAttrib(write_stencil, 1000)
            outline_node = self._outline_nodes.get(side)
            if outline_node:
                outline_node.setBin("hand-outline", 0, 1000)
                outline_node.setAttrib(test_stencil, 1000)

    def resize(self, width: int, height: int) -> None:
        """Redimensiona a área de renderização."""
        self.width = width
        self.height = height
        if getattr(self, "_pbr_pipeline", None) is not None:
            self._pbr_pipeline._post_process_quad.setShaderInput(
                "u_viewport_size", (float(max(1, width)), float(max(1, height)))
            )
        lens = self.showbase.cam.node().getLens()
        if hasattr(lens, "setAspectRatio"):
            lens.setAspectRatio(width / height)

    def set_model_rotation(self, x: float = 0, y: float = 0, z: float = 0) -> None:
        """Define a rotação do modelo em graus."""
        if self.model_anchor:
            self.model_anchor.setHpr(y, x, z)

    def set_model_position(self, x: float, y: float, z: float) -> None:
        """Define a posição do modelo."""
        if self.model_anchor:
            self.model_anchor.setPos(x, y, z)

    def set_model_screen_position(self, x: float, y: float) -> None:
        """Converte pixels locais da janela para o plano X/Z do mundo Panda3D."""
        if not self.model_anchor:
            return
        self._scene_x_px = x
        world_x = (x - self.width / 2.0) * self._view_width / self.width
        world_z = (
            self._view_target_z
            + (self.height / 2.0 - y) * self._view_height / self.height
        )
        self.model_anchor.setPos(world_x, 0.0, world_z)

    def apply_rig_pose(self, pose_dict: dict) -> None:
        """Aplica a pose do rig nos nós do modelo."""
        if not self.model_np:
            return
        self._ultima_pose = pose_dict
        for group in ALL_GROUPS:
            if group in self._rig_nodes and group in self._rig_base_pos:
                self._rig_nodes[group].setPos(self._rig_base_pos[group])

        for group_name, rotation in pose_dict.items():
            node = self._rig_nodes.get(group_name)
            if not node:
                continue
            if hasattr(rotation, "x"):
                x, y, z = rotation.x, rotation.y, rotation.z
            else:
                x, y, z = rotation
            # Clamps e anti-atravessamento vêm do PoseResolver: o renderer só
            # aplica a pose. A base adicional (torção-base do cotovelo) é a mesma
            # que a FK pura usa (cinematica.BASE_ADICIONAL_GRAUS).
            base_h, base_p, base_r = self._rig_base_hpr.get(group_name, (0.0, 0.0, 0.0))
            extra_h, extra_p, extra_r = BASE_ADICIONAL_GRAUS.get(
                group_name, (0.0, 0.0, 0.0)
            )
            base_h, base_p, base_r = (
                base_h + extra_h,
                base_p + extra_p,
                base_r + extra_r,
            )
            if group_name == "door":
                self._door_requested = max(0.0, math.degrees(y))
            node.setHpr(
                base_h + math.degrees(y),
                base_p + math.degrees(x),
                base_r + math.degrees(z),
            )
            outline_node = self._outline_nodes.get(group_name)
            if outline_node:
                outline_node.setHpr(node.getHpr())
        self._aplicar_squash_stretch()
        self._atualizar_sombra_contato()

    def _atualizar_sombra_contato(self) -> None:
        """Posiciona e escala a sombra de contato no chão conforme apoio e pose."""
        if self._shadow_np is None or self.model_np is None:
            return
        controller = getattr(self.showbase, "animation_controller", None)
        dancing_stage = bool(
            controller
            and controller.state == AnimationState.DANCE
            and getattr(self, "music_speaker", None)
            and self.music_speaker.visibility > 0.1
        )
        if dancing_stage or not self._is_grounded:
            self._shadow_np.hide()
            return
        self._shadow_np.show()
        scale = self.model_np.getSz()
        base_w = max(0.35, float(self._model_dimensions.x) * scale * 1.15)
        base_d = max(0.25, float(self._model_dimensions.y) * scale * 0.95)
        # Acompanha squash lateral se ativo
        sx = self._squash_pivot.getSx() if self._squash_pivot is not None else 1.0
        sy = self._squash_pivot.getSy() if self._squash_pivot is not None else 1.0
        z_chao = self._model_min_z * scale - 0.01
        self._shadow_np.setPos(0.0, 0.0, z_chao)
        self._shadow_np.setScale(base_w * sx, base_d * sy, 1.0)

    def _parametros_squash_stretch(self, controller) -> dict[str, Any]:
        estado = controller.state.value if controller.state else "idle"
        dragging = controller.state == AnimationState.DRAG
        dancing = controller.state == AnimationState.DANCE
        dance = controller.dance_motion if dancing else None
        return {
            "estado": estado,
            "respiracao": getattr(controller, "respiracao_valor", 0.0) or 0.0,
            "fase_locomocao": getattr(controller.leg_motion, "phase", 0.0),
            "run": controller.state == AnimationState.RUN,
            "impacto_tempo": (
                controller.state_time if controller.state == AnimationState.LAND else 0.0
            ),
            "impacto_duracao": 0.50,
            "arraste_velocidade": (
                getattr(controller.body_motion, "pointer_velocity", (0.0, 0.0))
                if dragging
                else (0.0, 0.0)
            ),
            "arraste_intensidade": (
                getattr(controller, "drag_intensity", 0.0) if dragging else 0.0
            ),
            "queda_velocidade": self._physics_velocity,
            "queda_tempo": (
                controller.state_time if controller.state == AnimationState.FALL else 0.0
            ),
            "sono_modo": getattr(controller, "modo_sono", "em_pe"),
            "danca_fase_beat": ((dance.phase / math.tau) % 1.0) if dance else 0.0,
            "danca_intensidade": dance.strength if dance else 0.5,
            "danca_bass": dance.bass if dance else 0.0,
        }

    def _aplicar_squash_stretch(self) -> None:
        """Aplica Squash & Stretch (princípio 1) no corpo inteiro, preservando volume."""
        if self._squash_pivot is None:
            return
        controller = getattr(self.showbase, "animation_controller", None)
        if controller is None:
            return
        ss = squash_stretch_composto(**self._parametros_squash_stretch(controller))

        # Pivô nos pés quando apoiado para comprimir contra o chão sem flutuar
        scale = self.model_np.getSz() if self.model_np else 1.0
        pivot_z = (self._model_min_z * scale) if self._is_grounded else (0.44 * scale)
        mat = (
            Mat4.translateMat(0.0, 0.0, -pivot_z)
            * Mat4.scaleMat(ss.x, ss.y, ss.z)
            * Mat4.translateMat(0.0, 0.0, pivot_z)
        )
        self._squash_pivot.setMat(mat)

    def _posicionar_sono(self, modo):
        if modo == "deitado":
            ground = self.model_np.getTightBounds(self.model_anchor)[0].z
            self._suspension_pivot.setMat(self._giro_no_quadril(0, 0, 85.0))
            moved = self.model_np.getTightBounds(self.model_anchor)[0].z
            self._suspension_pivot.setZ(ground - moved)
            return True
        if modo == "sentado":
            shorts = self._rig_nodes["legs"].getTightBounds(self.model_np)[0].z
            floor = self.music_speaker.floor_z
            offset = max(floor - shorts, self.lower_body.ground_offset)
            self._suspension_pivot.setZ(offset * self.model_np.getSz())
            return True
        return False

    def apply_body_motion(  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        self,
        motion,
        grab_point=None,
        *,
        grounded=True,
        dragging=False,
        direcao_olhar=0.0,
        angulo_giro_pedido=None,
    ):
        """Rotate connected root parts around the hips/grip without editing the asset rig.

        Sobre o GIRO DE CORPO (body_facing): no uso normal ``direcao_olhar``
        chega 0.0 (window passa 0.0), ou seja, o olhar/atenção NÃO dirige mais
        o giro — a cabeça/tronco/braço seguem o cursor por outro caminho
        (look_direction/look_vertical no controller). O giro de corpo vem SÓ de
        ``angulo_giro_pedido`` explícito (ganchos de animação/locomoção
        futura); quando é ``None`` e ``direcao_olhar`` é 0.0, o corpo fica de
        frente. O parâmetro ``direcao_olhar`` segue existindo para chamadas que
        queiram, deliberadamente, acoplar giro ao olhar.
        """
        dt = getattr(self.showbase.animation_controller, "delta_time", 1 / 60)
        self._update_outline_breath(dt, motion)
        self.flexible_rig.update(dt, motion)
        if self._suspension_pivot is None:
            self._suspension_pivot = self.model_anchor.attachNewNode("suspension-pivot")
            self._squash_pivot = self._suspension_pivot.attachNewNode("squash-pivot")
            # body_facing fica ENTRE o pivô de squash e a malha: gira o corpo
            # sem tocar no setH(180) base (model_np) nem no tilt de voo.
            self._body_facing = self._squash_pivot.attachNewNode("body-facing")
            self.model_np.reparentTo(self._body_facing)
            self.outline_np.reparentTo(self._body_facing)
        self._is_grounded = bool(grounded and not dragging)
        self._suspension_pivot.setMat(Mat4.identMat())
        controller = getattr(self.showbase, "animation_controller", None)
        if (
            angulo_giro_pedido is None and controller
            and controller.state == AnimationState.SLEEP and controller.modo_sono == "sentado"
        ):
            angulo_giro_pedido = -22.0
        self._aplicar_giro_corpo(dt, direcao_olhar, angulo_giro_pedido, dragging)
        speaker = self.music_speaker
        dancing = bool(controller and controller.state == AnimationState.DANCE)
        yaw = speaker.turn if dancing else 0.0
        self._dance_stage_yaw.update(dt, yaw)
        scale = self.model_np.getSz()
        if grounded and not dragging:
            self._suspension_pivot.setZ(self.lower_body.ground_offset * scale)
        style = controller.dance_motion.style
        subir = dancing and not dragging and style != "breakdance"
        self._subida_palco.update(dt, float(subir))
        self._assento_palco.update(dt, float(subir and style == "head_bob"))
        if not dragging and self._subida_palco.value > 0.005:
            self._posicionar_no_palco(speaker, subir)
        if (
            not dragging
            and controller
            and controller.state == AnimationState.DANCE
            and controller.dance_motion.style == "breakdance"
            and speaker.jump_progress >= 1.0
            and self._subida_palco.value < 0.01
        ):
            dance = controller.dance_motion
            ground = self.model_np.getTightBounds(self.model_anchor)[0].z
            # shortcut: mão não fica fixa no cenário durante o giro; upgrade quando
            # houver contatos de cena (guia 7.1).
            self._suspension_pivot.setMat(
                self._giro_no_quadril(
                    dance.floor_spin, 0, _danca.FLOOR_ROLL_GRAUS * dance.floor_amount
                )
            )
            moved = self.model_np.getTightBounds(self.model_anchor)[0].z
            self._suspension_pivot.setZ(ground - moved)
            return
        if (
            not dragging
            and controller
            and controller.state == AnimationState.SLEEP
            and self._posicionar_sono(controller.modo_sono)
        ):
            return
        if dragging and motion.hanging > _tune.PENDURADO_LIMIAR:
            point = Vec3(grab_point) if grab_point is not None else Vec3(0, 0, 0.6)
            pivot = self._suspension_pivot.getRelativePoint(self.model_np, point)
            rotation = self._rotacao_no_quadro_de_autoria(
                motion.yaw, motion.pitch, motion.roll
            )
            self._suspension_pivot.setMat(
                Mat4.translateMat(-pivot) * rotation * Mat4.translateMat(pivot)
            )
            return
        if not grounded and not dragging:
            pivot = self._suspension_pivot.getRelativePoint(
                self.model_np, Point3(0, 0, 0.44)
            )
            rotation = self._rotacao_no_quadro_de_autoria(
                motion.yaw * 0.6, motion.pitch * 0.55, motion.roll * 0.55
            )
            self._suspension_pivot.setMat(
                Mat4.translateMat(-pivot) * rotation * Mat4.translateMat(pivot)
            )
        # Grounded reaction now uses the shared spine and neck joints rather
        # than independently transforming disconnected top-level body parts.
        # Ganhos e SINAIS do tronco vêm de body_motion_tuning (req 4): o tronco
        # deve inclinar/girar no MESMO sentido do resto do corpo. Os sinais são
        # calibráveis na GPU (default +1 preserva o comportamento atual).
        # O pivô compartilhado (spine) aplica o balanço/giro de corpo inteiro
        # a partir da cintura; peitoral já carrega cabeça e ombros no grafo de
        # cena (rig_flexivel), evitando somar cintura/abdomen/peitoral em dobro.
        for spine, neck, _shoulders in self.flexible_rig.chains:
            yaw_tronco = _tune.TRONCO_YAW_SINAL * motion.yaw
            if controller and controller.state in (AnimationState.IDLE, AnimationState.HOVER):
                yaw_tronco = max(-12, min(12, yaw_tronco))
            pitch_tronco = (
                _tune.TRONCO_PITCH_SINAL * motion.pitch * _tune.TRONCO_PITCH_GANHO
                + self.flexible_rig.spine_pitch.value
            )
            roll_tronco = (
                _tune.TRONCO_ROLL_SINAL * motion.roll * _tune.TRONCO_ROLL_GANHO
                + self.flexible_rig.spine.value
            )
            # Evita que o peitoral entre no short ou saia do esquadro do esqueleto.
            pitch_tronco = max(-18.0, min(14.0, pitch_tronco))
            roll_tronco = max(-18.0, min(18.0, roll_tronco))
            spine.setHpr(yaw_tronco, pitch_tronco, roll_tronco)
            spine.setZ(
                max(
                    _tune.TRONCO_PIVO_Z - 0.012,
                    _tune.TRONCO_PIVO_Z
                    - motion.compression * _tune.TRONCO_COMPRESSAO_DESCIDA,
                )
            )
            neck.setP(max(-12.0, min(12.0, self.flexible_rig.neck_pitch.value)))
            neck.setR(max(-16.0, min(16.0, self.flexible_rig.neck.value)))
        if abs(self._dance_stage_yaw.value) > 0.01 and not dragging:
            pivot = self._suspension_pivot.getRelativePoint(
                self.model_np, Point3(0, 0, 0.44)
            )
            rotation = TransformState.makeHpr(
                Vec3(self._dance_stage_yaw.value, 0, 0)
            ).getMat()
            self._suspension_pivot.setMat(
                Mat4.translateMat(-pivot)
                * rotation
                * Mat4.translateMat(pivot)
                * self._suspension_pivot.getMat()
            )

    def _posicionar_no_palco(self, speaker, dancing):
        """Segue o arco até o tampo e alinha o apoio com a geometria."""
        progress = speaker.jump_progress
        if progress <= 0:
            return
        blend = suavizar_quintico(progress) * self._subida_palco.value
        scale = self.model_np.getSz()
        pelvis = self.lower_body.pelvis.getTightBounds(self.model_np)[0].z
        sentar = self._assento_palco.value
        sola = speaker.floor_z - self.lower_body.ground_offset
        contato = sola + (pelvis - sola) * sentar
        profundidade = speaker.destinations[0].y
        profundidade += (speaker.seat.y - profundidade) * sentar
        if not dancing:
            profundidade *= blend * blend
        peso_altura = blend if dancing else min(1, 1.8 * blend)
        altura = (speaker.seat.z - contato) * peso_altura
        arco = math.sin(math.pi * progress) * 0.70 if dancing else 0.0
        centro_x = speaker.boxes[0].getX()
        apoio_x = centro_x + (speaker.seat.x - centro_x) * sentar
        self._suspension_pivot.setPos(
            apoio_x * scale * blend,
            profundidade * scale * blend,
            self._suspension_pivot.getZ() * (1 - blend) + (altura + arco) * scale,
        )

    def _giro_no_quadril(self, yaw, pitch, roll):
        """Rotação de autoria (yaw, pitch, roll) em torno do quadril, como matriz.

        Roll positivo tomba o topo para a direita do mascote (convenção de
        ``_rotacao_no_quadro_de_autoria``); usado pelo breakdance no chão.
        """
        pivot = self._suspension_pivot.getRelativePoint(
            self.model_np, Point3(0, 0, _danca.PIVO_QUADRIL_Z)
        )
        rotation = self._rotacao_no_quadro_de_autoria(yaw, pitch, roll)
        return Mat4.translateMat(-pivot) * rotation * Mat4.translateMat(pivot)

    def _rotacao_no_quadro_de_autoria(self, yaw, pitch, roll):
        """Matriz de ``Vec3(yaw, pitch, roll)`` interpretado no referencial de AUTORIA.

        O ``_suspension_pivot`` vive no quadro do mundo, girado em relação ao
        mascote pelo nó raiz do asset (giro de frente). Conjugar pela rotação
        desse nó (``F⁻¹ · R · F``, vetor-linha do Panda) faz o arraste usar o
        MESMO sentido de pitch/roll do tronco em pé (``rig_flexivel``).
        """
        facing = no_de_facing(self.model_np).getMat(self.model_np).getUpper3()
        quadro = Mat4(facing)
        inversa = Mat4(quadro)
        inversa.invertInPlace()
        rotacao = TransformState.makeHpr(Vec3(yaw, pitch, roll)).getMat()
        return inversa * rotacao * quadro

    def _aplicar_giro_corpo(self, dt, direcao_olhar, angulo_pedido, dragging):
        """Aplica o GIRO DE CORPO LIMITADO ao nó dedicado ``body_facing``.

        O giro é suavizado e clampado em ``GiroCorpo`` (até ~±90°). Gira em
        torno do eixo vertical pelo centro do corpo (mesma estratégia do
        ``_dance_stage_yaw``), para o mascote virar de lado NO LUGAR, sem
        orbitar nem sair do envelope da janela dinâmica. Durante o arraste o
        giro relaxa para 0: o arraste já reorienta o corpo pelo pivô de grip.

        NÃO reaplica color key, z-order ou SetLayeredWindowAttributes; é apenas
        transformação no grafo de cena. O hit-test segue a pose (raycast contra
        model_np), então a região clicável acompanha o giro, como esperado.

        Semântica das fontes do giro: no uso normal ``direcao_olhar`` chega 0.0
        (window não acopla mais o giro ao olhar no hover/idle), então o giro
        vem SÓ de ``angulo_pedido`` (ganchos de animação/locomoção). A classe
        ``GiroCorpo`` dá precedência a ``angulo_pedido`` sobre ``direcao_olhar``
        quando ambos chegam; a mola/clamp/LIMITE_GRAUS permanecem inalterados.
        """
        if self._body_facing is None:
            return
        olhar = 0.0 if dragging else direcao_olhar
        pedido = None if dragging else angulo_pedido
        controller = getattr(self.showbase, "animation_controller", None)
        permitir_costas = bool(
            not dragging and getattr(controller, "permitir_giro_costas", False)
        )
        angulo = self._giro_corpo.update(
            dt,
            direcao_olhar=olhar,
            angulo_pedido=pedido,
            permitir_costas=permitir_costas,
        )
        if abs(angulo) < 0.01:
            self._body_facing.setMat(Mat4.identMat())
            return
        # Centro do corpo no referencial do body_facing: gira em torno dele para
        # virar no lugar (sem deslocar os pés nem o centro visível).
        pivot = self._body_facing.getRelativePoint(self.model_np, Point3(0, 0, 0.44))
        rotacao = TransformState.makeHpr(Vec3(angulo, 0, 0)).getMat()
        self._body_facing.setMat(
            Mat4.translateMat(-pivot) * rotacao * Mat4.translateMat(pivot)
        )

    def _eh_inferior_ou_decorativa(self, mesh, lower_body_nodes) -> bool:
        if "plane" in mesh.getParent().getName().lower():
            return True
        cursor = mesh
        while not cursor.isEmpty() and cursor != self.model_np:
            if cursor.getName() in lower_body_nodes:
                return True
            cursor = cursor.getParent()
        return False

    def _setup_tentacle_contacts(self):
        self.tentacle_contacts = TentacleContacts()
        self._collider_sources = []
        head = self._rig_nodes["head"]
        door = self._rig_nodes["door"]
        # Gabinete da TV: grupo ``Armario`` no asset rigado (antes ``mesh0``).
        cabinet = head.find("**/Armario")
        if cabinet.isEmpty():
            cabinet = head.find("**/mesh0")
        elif not cabinet.find("+GeomNode").isEmpty():
            cabinet = cabinet.find("+GeomNode")
        if not cabinet.isEmpty():
            low, high = cabinet.getTightBounds(head)
            thickness = 0.022
            # The cabinet is hollow. Its opening must remain traversable.
            panels = (
                (Vec3(low), Vec3(high.x, low.y + thickness, high.z)),
                (Vec3(low), Vec3(low.x + thickness, high.y, high.z)),
                (Vec3(high.x - thickness, low.y, low.z), Vec3(high)),
                (Vec3(low), Vec3(high.x, high.y, low.z + thickness)),
                (Vec3(low.x, low.y, high.z - thickness), Vec3(high)),
            )
            for index, (minimum, maximum) in enumerate(panels):
                self._collider_sources.append((f"cabinet-wall-{index}", head, minimum, maximum))
        lower_body_nodes = frozenset(
            (
                "legs", "left-feet", "right-feet", "coxa-direita",
                "canela-direita", "joelho-direito", "coxa-esquerda",
                "canela-esquerda", "joelho-esquerdo",
            )
        )
        for mesh in self.model_np.findAllMatches("**/+GeomNode"):
            if mesh == cabinet or mesh.getName().startswith(("procedural-tentacle", "tentacle-joint-")):
                continue
            if self._eh_inferior_ou_decorativa(mesh, lower_body_nodes):
                continue
            bounds = mesh.getTightBounds(mesh)
            if bounds and min(bounds[1][axis] - bounds[0][axis] for axis in range(3)) > 0.0001:
                name = "door" if door.isAncestorOf(mesh) else mesh.getName()
                self._collider_sources.append((name, mesh, Vec3(bounds[0]), Vec3(bounds[1])))
        for tentacle in self.tentacle_pool.tentacles:
            tentacle.contacts = self.tentacle_contacts
        self._contact_box_cache = {}

    def _sync_tentacle_anchors_and_front(self):
        head = self._rig_nodes["head"]
        front = self.model_np.getRelativeVector(head, Vec3(0, 1, 0)).normalized()
        for tentacle, local_anchor in zip(
            self.tentacle_pool.tentacles, self._tentacle_anchor_local, strict=True
        ):
            anchor = self.model_np.getRelativePoint(head, local_anchor)
            self.tentacle_director.sincronizar_ancora_e_frente(
                tentacle, anchor, front
            )

    def _update_tentacle_contacts(self):
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
        speaker = self.music_speaker
        if not speaker.root.isHidden():
            for index, (box, (low, high)) in enumerate(
                zip(speaker.boxes, speaker.bounds, strict=True)
            ):
                if not box.isHidden() and index != speaker.throw_index:
                    boxes.append(
                        ObstacleBox(
                            "music-speaker",
                            low,
                            high,
                            self.model_np.getMat(box),
                            box.getMat(self.model_np),
                        )
                    )

    def iniciar_transicao_roupa(self):
        """Inicia a cobertura para uma futura troca de roupa."""
        if self._tempo_cobertura <= 0 and not self.music_speaker.ejecting:
            self._cobertura_roupa = self.tentacle_director.cobrir_roupa()
            if self._cobertura_roupa:
                self._tempo_cobertura = 2.9

    def _atualizar_cobertura(self, dt):
        if self._tempo_cobertura <= 0:
            return
        self._tempo_cobertura = max(0, self._tempo_cobertura - dt)
        if self._tempo_cobertura > 0:
            self._door_requested = max(100, self._door_requested)
        else:
            for limb in self._cobertura_roupa:
                self.tentacle_pool.release(limb)
            self._cobertura_roupa.clear()

    def _posar_cobertura_roupa(self):
        # A curva cobre o tronco entre a abertura e o recolhimento.
        for index, limb in enumerate(self._cobertura_roupa):
            if limb.state != TentacleState.CURIOUS:
                continue
            lado = -1 if index == 0 else 1
            curva = (
                limb.anchor,
                Vec3(lado * 0.68, -0.64, 0.68),
                Vec3(-lado * 0.58, -0.62, 0.46),
                Vec3(lado * 0.27, -0.47, 0.22),
            )
            for j, segmento in enumerate(limb.segments):
                u = j / (len(limb.segments) - 1)
                v = 1 - u
                segmento.pos = (
                    curva[0] * v**3 + curva[1] * (3 * v*v*u)
                    + curva[2] * (3 * v*u*u) + curva[3] * u**3
                )

    def update_appendages(self, dt, visible=True):  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        """Atualiza os apêndices (porta, tentáculos, caixa) no frame."""
        if not self.tentacle_director:
            return
        controller = self.showbase.animation_controller
        dancing = controller.state is not None and controller.state.value == "dance"
        dance = controller.dance_motion
        self.finger_gestures.update(
            dt,
            "rock"
            if dancing and dance.style == "rock"
            else controller.state.value
            if controller.state
            else None,
            fase_danca=dance.phase if dancing else None,
        )
        speaker_active = dancing or (
            self.music_speaker.was_dancing
            and getattr(controller, "music_active", False)
        )
        luz = self._luz_palco.node()
        sombras = speaker_active or self.music_speaker.visibility > 0.005
        if sombras != luz.isShadowCaster():
            luz.setShadowCaster(sombras, 1024, 1024)
        if sombras:
            self._luz_palco.setPos(self.model_anchor.getPos(self.showbase.render)
                                  - self._luz_palco.getQuat().getForward() * 28)
        self.music_speaker.update(
            dt, speaker_active, dance.phase, dance.energy, dance.bass
        )
        self._sync_tentacle_anchors_and_front()

        speaker = self.music_speaker
        throw_index = speaker.throw_index
        if (
            throw_index != getattr(self, "_speaker_throw_index", -1)
            and throw_index >= 0
        ):
            self.tentacle_director.trigger_speaker_throw()
        self._speaker_throw_index = throw_index
        for limb in self.tentacle_director.speaker_throw_limbs:
            if throw_index >= 0:
                box = speaker.boxes[throw_index]
                low, high = speaker.bounds[throw_index]
                anchor = box.getRelativePoint(self.model_np, limb.anchor)
                point = Point3(
                    *(
                        max(a, min(b, v))
                        for a, b, v in zip(low, high, anchor, strict=True)
                    )
                )
                target = self.model_np.getRelativePoint(box, point)
                limb.target = target - (target - limb.anchor).normalized() * 0.04
        self.tentacle_director.music_ejection = speaker.ejecting
        if speaker.ejecting:
            self._door_requested = max(self._door_requested, 110)
        if dancing and speaker.age < INICIO_SALTO_S + 0.35:
            age = speaker.age
            olhar = suavizar_quintico((age - FIM_ARREMESSOS_S) / 0.33)
            olhar *= 1 - suavizar_quintico((age - INICIO_SALTO_S) / 0.35)
            shot = sum(
                math.exp(-(((age - at) / 0.13) ** 2)) for at in BATIDAS_ARREMESSO_S
            )
            head = self._rig_nodes["head"]
            head.setH(head.getH() - 17 * shot + 62 * olhar)
            head.setP(head.getP() - 24 * shot)
            self._outline_nodes["head"].setHpr(head.getHpr())

        sneezing = controller.state is not None and controller.state.value == "sneeze"
        if (
            sneezing
            and controller._reaction_time >= 3.6
            and not self.tentacle_director.burst
        ):
            self.tentacle_director.trigger_sneeze()
            self.tentacle_drips.spray(self.tentacle_pool.tentacles)
        if not sneezing and not any(
            t.state != TentacleState.DORMANT for t in self.tentacle_pool.tentacles
        ):
            self.tentacle_director.burst = False
        if visible:
            if not self._tentacles_were_visible:
                self.tentacle_director.trigger_curious()
        elif self._tentacles_were_visible:
            self.tentacle_director.encerrar_espiada(
                interromper=controller.state
                in (AnimationState.DRAG, AnimationState.FALL, AnimationState.SLEEP)
            )
        tentacles_active = any(
            t.state != TentacleState.DORMANT for t in self.tentacle_pool.tentacles
        )
        if tentacles_active:
            self._update_tentacle_contacts()
        self._atualizar_cobertura(dt)
        choreography_active = self.tentacle_director.coreografia_ativa
        self.tentacle_director._pedido_porta_externo = (
            0.0
            if (
                (visible or choreography_active)
                and controller.state
                in (AnimationState.IDLE, AnimationState.HOVER, AnimationState.TEIMOSIA)
                and self._door_requested <= 25.0
            )
            else self._door_requested
        )
        tentacles_extending = any(
            t.state not in (TentacleState.DORMANT, TentacleState.RETRACTING)
            for t in self.tentacle_pool.tentacles
        )
        tentacles_clearing = any(
            t.state == TentacleState.RETRACTING and t.reveal > 0.16
            for t in self.tentacle_pool.tentacles
        )
        porta_extensao = (
            coreo.SAIDA_ESPIRRO.angulo_empurrao_graus
            if self.tentacle_director.burst
            else 92.0
        )
        self.tentacle_director._door_requested = max(
            self._door_requested,
            porta_extensao
            if tentacles_extending
            else (28.0 if tentacles_clearing else 0.0),
        )
        # The animation controller owns ambient timing. Keep updating the door
        # after the last limb is dormant, so it can finish closing smoothly.
        self.tentacle_director.update(dt, controller.idle_personality)
        self._posar_cobertura_roupa()
        self.tentacle_drips.update(dt, self.tentacle_pool.tentacles)
        self._tentacles_were_visible = visible
        door = self._rig_nodes.get("door")
        angulo_porta = (
            self.tentacle_director._door_current
            if (
                tentacles_active
                or self.tentacle_director.coreografia.fase
                is not coreo.FasePorta.FECHADA
            )
            else max(self.tentacle_director._door_current, self._door_requested)
        )
        if door:
            base_h, base_p, base_r = self._rig_base_hpr["door"]
            door.setHpr(base_h + angulo_porta, base_p, base_r)
            self._outline_nodes["door"].setHpr(door.getHpr())
        debug = self.showbase.debug_tools
        for tentacle in self.tentacle_pool.tentacles:
            tentacle_visible = (
                tentacle.state != TentacleState.DORMANT
                and tentacle.reveal > 0.015
                and (
                    abs(angulo_porta) >= 6.0
                    or tentacle is self.tentacle_director._atuador
                    or getattr(tentacle, "speaker_throw", False)
                )
            )
            if tentacle_visible:
                update_tentacle_render(tentacle)
            for index, axis in enumerate(tentacle.axis_nodes):
                shown = (
                    tentacle_visible
                    and debug
                    and debug.visible
                    and index / (len(tentacle.segments) - 1) <= tentacle.reveal
                )
                (axis.show if shown else axis.hide)()
            if tentacle.mesh_node:
                (
                    tentacle.mesh_node.show
                    if tentacle_visible
                    else tentacle.mesh_node.hide
                )()
                tentacle.mesh_node.setCollideMask(2 if tentacle_visible else 0)
            if tentacle.outline_mesh_node:
                (
                    tentacle.outline_mesh_node.show
                    if tentacle_visible
                    else tentacle.outline_mesh_node.hide
                )()
        self.fio_fone.atualizar(dt)

    def _normalizar_pivos_saida(self) -> None:
        if self._suspension_pivot is not None:
            self._suspension_pivot.setMat(Mat4.identMat())
            scale = float(self.model_np.getSz()) if self.model_np else 1.0
            self._suspension_pivot.setZ(self.lower_body.ground_offset * scale)
        if self._squash_pivot is not None:
            self._squash_pivot.setMat(Mat4.identMat())
        if self._body_facing is not None:
            self._body_facing.setHpr(0.0, 0.0, 0.0)
        for spring in (self._subida_palco, self._assento_palco, self._dance_stage_yaw):
            spring.value = 0.0
            spring.velocity = 0.0
        self._giro_corpo = type(self._giro_corpo)()

    def begin_exit_effect(self, style: str = "classic"):
        """Inicia o efeito visual de saída conforme ``style``."""
        from panda3d.core import Shader

        self.restore_exit_effect()
        self._normalizar_pivos_saida()
        if style == "classic":
            vertex = """#version 130
in vec4 p3d_Vertex; in vec2 p3d_MultiTexCoord0;
uniform mat4 p3d_ModelViewProjectionMatrix; out vec2 uv;
void main() { uv = p3d_MultiTexCoord0; gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex; }
"""
            fragment = f"""#version 130
uniform sampler2D p3d_Texture0; in vec2 uv; out vec4 fragColor;
void main() {{ if (texture(p3d_Texture0, uv).a < {CONTORNO_ALPHA_DISCARD}) discard; fragColor = vec4(100.0, 100.0, 100.0, 1.0); }}
"""
            self.model_np.setShader(Shader.make(Shader.SL_GLSL, vertex, fragment), 1001)
            self.outline_np.hide()
        self._exit_orig_anchor_parent = self.model_anchor.getParent()
        self._exit_orig_anchor_tf = self.model_anchor.getTransform()
        minimum, maximum = self.model_np.getTightBounds(self.showbase.render)
        self.exit_pivot = self.showbase.render.attachNewNode("exit-spin-center")
        self._exit_center = (
            (minimum + maximum) * 0.5
            if style == "classic"
            else Point3(
                (minimum.x + maximum.x) * 0.5,
                (minimum.y + maximum.y) * 0.5,
                minimum.z,
            )
        )
        self.exit_pivot.setPos(self._exit_center)
        self.model_anchor.wrtReparentTo(self.exit_pivot)
        self._lego_floor_world_z = float(minimum.z)

    def sync_exit_ground_offset(self, grounded: bool) -> None:
        """Mantém a sola alinhada ao chão durante poses de encerramento."""
        if self._suspension_pivot is None or self.model_np is None:
            return
        scale = float(self.model_np.getSz())
        if grounded:
            self._suspension_pivot.setZ(self.lower_body.ground_offset * scale)
        else:
            self._suspension_pivot.setZ(0.0)

    def set_exit_rotation(self, roll):
        """Define o roll do modelo durante a saída."""
        if getattr(self, "exit_pivot", None):
            self.exit_pivot.setR(roll)

    def set_post_effect(
        self,
        dissolve: float = 0.0,
        dissolve_mode: str = "uniform",
        tint: tuple[float, float, float] = (0.10, 0.65, 1.00),
        flash: float = 0.0,
    ) -> None:
        """Atualiza uniforms do shader de pós-processamento (dissolução e brilho)."""
        pipeline = getattr(self, "_pbr_pipeline", None)
        if pipeline is None:
            return
        quad = pipeline._post_process_quad
        quad.setShaderInput("u_dissolve", float(max(0.0, min(1.0, dissolve))))
        quad.setShaderInput(
            "u_dissolve_mode", 1.0 if dissolve_mode == "thanos" else 0.0
        )
        quad.setShaderInput("u_overlay_tint", tuple(float(c) for c in tint))
        quad.setShaderInput("u_overlay_flash", float(max(0.0, min(1.0, flash))))

    @staticmethod
    def _criar_bloco_fx(nome: str, raio: float, cor: tuple[float, float, float, float]):
        """Gera um cubo/octaedro leve procedural para fumaça, cinzas ou orbes."""
        from panda3d.core import (
            Geom,
            GeomNode,
            GeomTriangles,
            GeomVertexData,
            GeomVertexFormat,
            GeomVertexWriter,
            NodePath,
        )

        vdata = GeomVertexData(nome, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
        pos = GeomVertexWriter(vdata, "vertex")
        norm = GeomVertexWriter(vdata, "normal")
        col = GeomVertexWriter(vdata, "color")
        pts = [
            (0, 0, raio),
            (raio, 0, 0),
            (0, raio, 0),
            (-raio, 0, 0),
            (0, -raio, 0),
            (0, 0, -raio),
        ]
        faces = [
            (0, 1, 2),
            (0, 2, 3),
            (0, 3, 4),
            (0, 4, 1),
            (5, 2, 1),
            (5, 3, 2),
            (5, 4, 3),
            (5, 1, 4),
        ]
        tris = GeomTriangles(Geom.UHStatic)
        idx = 0
        for a_i, b_i, c_i in faces:
            a, b, c = Vec3(*pts[a_i]), Vec3(*pts[b_i]), Vec3(*pts[c_i])
            n = (b - a).cross(c - a)
            if n.lengthSquared() > 1e-8:
                n.normalize()
            for v, brilho in zip((a, b, c), (1.0, 0.92, 0.85), strict=True):
                pos.addData3f(v.x, v.y, v.z)
                norm.addData3f(n.x, n.y, n.z)
                col.addData4f(
                    min(1.0, cor[0] * brilho),
                    min(1.0, cor[1] * brilho),
                    min(1.0, cor[2] * brilho),
                    cor[3],
                )
            tris.addVertices(idx, idx + 1, idx + 2)
            idx += 3
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gnode = GeomNode(nome)
        gnode.addGeom(geom)
        np = NodePath(gnode)
        np.setShaderAuto()
        return np

    def _garantir_fx_root(self):
        if self._fx_root is None:
            self._fx_root = self.showbase.render.attachNewNode("companion-fx-root")
        return self._fx_root

    def _limpar_fx(self) -> None:
        for node in self._fx_smoke_nodes:
            node.removeNode()
        self._fx_smoke_nodes.clear()
        for node in self._fx_ash_nodes:
            node.removeNode()
        self._fx_ash_nodes.clear()
        for node in self._fx_blue_nodes:
            node.removeNode()
        self._fx_blue_nodes.clear()
        if self._fx_root is not None:
            self._fx_root.removeNode()
            self._fx_root = None

    def _atualizar_fumaca_ninja(self, burst: float, center_world: Vec3) -> None:
        if burst <= 0.01:
            for node in self._fx_smoke_nodes:
                node.hide()
            return
        root = self._garantir_fx_root()
        if not self._fx_smoke_nodes:
            for idx, _o in enumerate(_NINJA_SMOKE_OFFSETS):
                puff = self._criar_bloco_fx(
                    f"ninja-puff-{idx}", 1.0, (0.94, 0.96, 1.0, 1.0)
                )
                puff.reparentTo(root)
                self._fx_smoke_nodes.append(puff)
        expande = 1.0 - burst * 0.55
        scale_model = max(0.35, self.model_np.getSz() * 0.28)
        for idx, (puff, (ox, oy, oz, rad)) in enumerate(
            zip(self._fx_smoke_nodes, _NINJA_SMOKE_OFFSETS, strict=True)
        ):
            puff.show()
            drift = 0.65 + (1.0 - burst) * 1.15
            puff.setPos(
                center_world.x + ox * scale_model * drift,
                center_world.y + oy * scale_model,
                center_world.z + (oz + (1.0 - burst) * 0.75) * scale_model,
            )
            escala = rad * scale_model * (0.45 + 0.95 * burst)
            puff.setScale(escala)
            puff.setHpr(idx * 37 + expande * 90, idx * 23, idx * 19)

    def _garantir_flocos_thanos(self, count: int = 20) -> None:
        if self._fx_ash_nodes:
            return
        from panda3d.core import Material

        root = self._garantir_fx_root()
        mat_brasa = Material()
        mat_brasa.setEmission((1.0, 0.42, 0.08, 1.0))
        for idx in range(count):
            brasa = idx % 3 == 0
            cor = (0.98, 0.52, 0.16, 1.0) if brasa else (0.36, 0.30, 0.38, 1.0)
            flake = self._criar_bloco_fx(f"ash-flake-{idx}", 1.0, cor)
            if brasa:
                flake.setMaterial(mat_brasa)
            flake.reparentTo(root)
            self._fx_ash_nodes.append(flake)

    def _atualizar_cinzas_thanos(self, ash: float, center_world: Vec3) -> None:
        if ash <= 0.02:
            for node in self._fx_ash_nodes:
                node.hide()
            return
        count = 20
        self._garantir_flocos_thanos(count)
        s = max(0.35, self.model_np.getSz() * 0.18)
        for idx, flake in enumerate(self._fx_ash_nodes):
            delay = (idx / count) * 0.55
            local_p = max(0.0, min(1.0, (ash - delay * 0.6) / max(0.25, 1.0 - delay * 0.6)))
            if local_p <= 0.0 or local_p >= 0.98:
                flake.hide()
                continue
            flake.show()
            rx = ((idx * 37) % 11 - 5) * 0.34 * s
            rz = ((idx * 53) % 9 - 4) * 0.40 * s
            wind_x = local_p * (3.6 + (idx % 4) * 1.0) * s
            lift_z = local_p * (4.0 + (idx % 3) * 1.1) * s
            flake.setPos(
                center_world.x + rx + wind_x,
                center_world.y - 0.8 * s,
                center_world.z + rz + lift_z,
            )
            flake.setScale((0.34 - 0.18 * local_p) * s)
            flake.setHpr(local_p * 320 + idx * 41, local_p * 210, idx * 29)

    @staticmethod
    def _vertices_esfera_fx(
        raio: float,
        cor_base: tuple[float, float, float, float],
        cor_rachadura: tuple[float, float, float, float],
        aneis: int,
        segmentos: int,
    ) -> list[tuple[Vec3, tuple[float, float, float, float]]]:
        verts: list[tuple[Vec3, tuple[float, float, float, float]]] = []
        for i in range(aneis + 1):
            theta = (i / aneis) * math.pi
            sin_t, cos_t = math.sin(theta), math.cos(theta)
            for j in range(segmentos + 1):
                phi = (j / segmentos) * math.tau
                n = Vec3(sin_t * math.cos(phi), sin_t * math.sin(phi), cos_t)
                # Diagonal elétrica em zigue-zague bem visível na face frontal da esfera.
                zig = math.sin(phi * 3.5) * 0.16
                if abs(n.z - (0.42 * n.x + zig)) < 0.14:
                    c = cor_rachadura
                else:
                    sombra = 0.72 + 0.28 * max(0.0, -n.y * 0.7 + n.z * 0.4)
                    c = (
                        min(1.0, cor_base[0] * sombra),
                        min(1.0, cor_base[1] * sombra),
                        min(1.0, cor_base[2] * sombra),
                        cor_base[3],
                    )
                verts.append((n * raio, c))
        return verts

    @staticmethod
    def _criar_esfera_fx(
        nome: str,
        raio: float,
        cor_base: tuple[float, float, float, float],
        cor_rachadura: tuple[float, float, float, float],
        *,
        aneis: int = 12,
        segmentos: int = 18,
    ):
        """Gera uma esfera UV iluminada com fissura elétrica estilo FNF."""
        from panda3d.core import (
            Geom,
            GeomNode,
            GeomTriangles,
            GeomVertexData,
            GeomVertexFormat,
            GeomVertexWriter,
            NodePath,
        )

        vdata = GeomVertexData(nome, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
        pos, norm, col = (
            GeomVertexWriter(vdata, "vertex"),
            GeomVertexWriter(vdata, "normal"),
            GeomVertexWriter(vdata, "color"),
        )
        for pt, c in Panda3DRenderer._vertices_esfera_fx(
            raio, cor_base, cor_rachadura, aneis, segmentos
        ):
            n_dir = pt.normalized() if pt.lengthSquared() > 1e-8 else Vec3(0, 0, 1)
            pos.addData3f(pt.x, pt.y, pt.z)
            norm.addData3f(n_dir.x, n_dir.y, n_dir.z)
            col.addData4f(*c)
        tris = GeomTriangles(Geom.UHStatic)
        cols = segmentos + 1
        for i in range(aneis):
            for j in range(segmentos):
                a = i * cols + j
                tris.addVertices(a, a + cols, a + 1)
                tris.addVertices(a + 1, a + cols, a + cols + 1)
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gnode = GeomNode(nome)
        gnode.addGeom(geom)
        np = NodePath(gnode)
        np.setShaderAuto()
        return np

    def _atualizar_orbes_azuis(self, power: float, _center_world: Vec3) -> None:
        if power <= 0.02:
            for node in self._fx_blue_nodes:
                node.hide()
            return
        root = self._garantir_fx_root()
        if not self._fx_blue_nodes:
            from panda3d.core import Material

            mat_azul = Material()
            mat_azul.setEmission((0.18, 0.78, 1.0, 1.0))
            for idx, (cor_base, cor_fenda) in enumerate(
                (
                    ((0.08, 0.62, 1.0, 1.0), (0.85, 0.98, 1.0, 1.0)),
                    ((0.14, 0.72, 1.0, 1.0), (0.90, 1.0, 1.0, 1.0)),
                )
            ):
                orb = self._criar_esfera_fx(
                    f"fnf-blue-orb-{idx}", 0.36, cor_base, cor_fenda
                )
                orb.setMaterial(mat_azul)
                orb.reparentTo(root)
                self._fx_blue_nodes.append(orb)

        scale_ref = max(0.35, float(self.model_np.getSz()) * 0.20)
        pelvis_node = (
            self._rig_nodes.get("cintura")
            or self._rig_nodes.get("legs")
            or self.model_np
        )
        pelvis_pos = pelvis_node.getPos(self.showbase.render)
        # Duas esferas proporcionais exatamente no centro pélvico entre as mãos.
        for idx, orb in enumerate(self._fx_blue_nodes):
            orb.show()
            side = -1.0 if idx == 0 else 1.0
            orb.setPos(
                pelvis_pos.x + side * 0.28 * scale_ref,
                pelvis_pos.y - 0.72 * scale_ref,
                pelvis_pos.z - 0.34 * scale_ref,
            )
            pulse = 0.90 + 0.22 * power
            orb.setScale(pulse * scale_ref)
            orb.setHpr(side * 16.0 + (power - 0.8) * 24.0, -10.0, side * 12.0)

    def _iniciar_lego_scatter(self, world_floor_z: float | None = None) -> None:
        self._lego_snapshot.clear()
        if self._lego_root is not None:
            self._lego_root.removeNode()
            self._lego_root = None
        if getattr(self.lower_body, "pernas_tecido", None) is not None:
            self.lower_body.pernas_tecido.set_lego_mode(self, True)
        self.outline_np.hide()
        root = self.showbase.render.attachNewNode("lego-scatter-root")
        root.setPos(
            self.exit_pivot.getPos(self.showbase.render)
            if getattr(self, "exit_pivot", None) is not None
            else self.model_anchor.getPos(self.showbase.render)
        )
        self._lego_floor_z = (
            world_floor_z - float(root.getZ()) + 0.08
            if world_floor_z is not None
            else 0.08
        )
        self._lego_root = root
        for idx, name in enumerate(_LEGO_SCATTER_PARTS):
            node = self._rig_nodes.get(name)
            if node is None:
                continue
            orig_parent = node.getParent()
            orig_tf = node.getTransform()
            node.wrtReparentTo(root)
            start_pos = Point3(node.getPos())
            ang = idx * 1.95
            speed = 1.45 + (idx % 4) * 0.42
            vx = math.cos(ang) * speed
            vy = math.sin(ang * 0.7) * speed * 0.35 - 0.35
            vz = 2.15 + (idx % 5) * 0.52
            spin = Vec3(
                (170 + idx * 37) * (1 if idx % 2 == 0 else -1),
                125 + idx * 27,
                145 * (-1 if idx % 3 == 0 else 1),
            )
            self._lego_snapshot.append(
                (name, node, orig_parent, orig_tf, start_pos, Vec3(vx, vy, vz), spin)
            )

    def _atualizar_lego_scatter(self, explode: float) -> None:
        if not self._lego_snapshot:
            return
        t = max(0.0, min(1.0, explode)) * 1.15
        g = -7.8
        floor_z = self._lego_floor_z
        for _name, node, _op, _otf, p0, vel, spin in self._lego_snapshot:
            x = p0.x + vel.x * t
            y = p0.y + vel.y * t
            z = p0.z + vel.z * t + 0.5 * g * t * t
            if z < floor_z:
                pen = floor_z - z
                z = floor_z + pen * 0.38
            node.setPos(x, y, z)
            node.setHpr(spin.x * t, spin.y * t, spin.z * t)

    def _resolver_base_intro(self) -> Point3:
        if getattr(self.showbase, "desktop", None) is not None:
            return Point3(self.model_anchor.getPos())
        if self._intro_orig_anchor_pos is None:
            self._intro_orig_anchor_pos = Point3(self.model_anchor.getPos())
        return self._intro_orig_anchor_pos

    def apply_intro_effect(self, frame) -> None:
        """Aplica escala, deslocamento, dissolução Bayer e fumaça ninja da abertura."""
        if not self.model_anchor or not self.model_np:
            return
        if self._intro_orig_foot_local_z is None:
            bounds_local = self.model_np.getTightBounds(self.model_anchor)
            self._intro_orig_foot_local_z = (
                float(bounds_local[0].z) if bounds_local else -0.52
            )
        if frame.dissolve >= 0.96 and frame.smoke_burst > 0.05:
            self.model_np.hide()
            self.outline_np.hide()
            self.set_post_effect(dissolve=0.0)
        else:
            self.model_np.show()
            if self._outline_enabled:
                self.outline_np.show()
            self.set_post_effect(dissolve=frame.dissolve, dissolve_mode="uniform")
        base_pos = self._resolver_base_intro()
        scale = max(0.08, float(frame.scale))
        units = float(self._view_height / max(1, self.height))
        foot_comp = self._intro_orig_foot_local_z * (1.0 - scale)
        self.model_anchor.setPos(
            base_pos.x + frame.offset_x * units,
            base_pos.y,
            base_pos.z - frame.offset_y * units + foot_comp,
        )
        self.model_anchor.setScale(scale)
        self.model_anchor.setHpr(frame.yaw, frame.pitch, frame.roll)
        bounds = self.model_anchor.getTightBounds(self.showbase.render)
        center = (
            (bounds[0] + bounds[1]) * 0.5
            if bounds
            else self.model_anchor.getPos(self.showbase.render)
        )
        self._atualizar_fumaca_ninja(frame.smoke_burst, center)

    def restore_intro_effect(self) -> None:
        """Restaura câmera/escala/pós-efeito ao concluir ou cancelar abertura."""
        if self.model_np:
            self.model_np.show()
        if self.outline_np and self._outline_enabled:
            self.outline_np.show()
        if self.model_anchor:
            if self._intro_orig_anchor_pos is not None:
                self.model_anchor.setPos(self._intro_orig_anchor_pos)
            self.model_anchor.setScale(1.0)
            self.model_anchor.setHpr(0.0, 0.0, 0.0)
        self._intro_orig_anchor_pos = None
        self._intro_orig_foot_local_z = None
        self.set_post_effect(dissolve=0.0, flash=0.0)
        self._limpar_fx()

    def update_exit_effect(self, frame, origin: tuple[int, int], style: str) -> None:
        """Atualiza posição, rotação, partículas e dissolução da saída/morte."""
        if not getattr(self, "exit_pivot", None):
            return
        units = float(self._view_height / max(1, self.height))
        self.exit_pivot.setPos(
            self._exit_center.x + (frame.x - origin[0]) * units,
            self._exit_center.y,
            self._exit_center.z - (frame.y - origin[1]) * units,
        )
        self.exit_pivot.setHpr(frame.yaw, frame.pitch, frame.roll)
        self.exit_pivot.setScale(max(0.05, frame.scale))

        if style == "lego_disassemble" and frame.explode > 0.0:
            if not self._lego_snapshot:
                self._iniciar_lego_scatter(getattr(self, "_lego_floor_world_z", None))
            self._atualizar_lego_scatter(frame.explode)

        mode = "thanos" if style == "thanos_snap" else "uniform"
        if style == "fnf_blue_balls":
            shock = getattr(frame, "shock", 0.0)
            if shock > 0.02:
                tint = (0.30, 0.94, 1.0)
                flash = 0.25 + 0.58 * shock
            else:
                tint = (0.04, 0.14, 0.56)
                flash = 0.36 * (1.0 - min(1.0, frame.dissolve))
        else:
            tint = (0.08, 0.68, 1.0)
            flash = frame.blue_balls * 0.26
        self.set_post_effect(
            dissolve=frame.dissolve,
            dissolve_mode=mode,
            tint=tint,
            flash=flash,
        )
        center = self.exit_pivot.getPos(self.showbase.render)
        self._atualizar_cinzas_thanos(frame.ash, center)
        self._atualizar_orbes_azuis(frame.blue_balls, center)

    def _restaurar_ancora_saida(self) -> None:
        if self.model_anchor:
            parent = self._exit_orig_anchor_parent or self.showbase.render
            if not parent.isEmpty():
                self.model_anchor.reparentTo(parent)
            if self._exit_orig_anchor_tf is not None:
                self.model_anchor.setTransform(self._exit_orig_anchor_tf)
            else:
                self.model_anchor.setScale(1.0)
                self.model_anchor.setHpr(0.0, 0.0, 0.0)
        self._exit_orig_anchor_parent = None
        self._exit_orig_anchor_tf = None

    def restore_exit_effect(self) -> None:
        """Restaura integralmente nós, shaders e hierarquia após prévia de saída."""
        for _name, node, orig_parent, orig_tf, *_rest in reversed(self._lego_snapshot):
            if not node.isEmpty() and not orig_parent.isEmpty():
                node.reparentTo(orig_parent)
                node.setTransform(orig_tf)
        self._lego_snapshot.clear()
        if getattr(self.lower_body, "pernas_tecido", None) is not None:
            self.lower_body.pernas_tecido.set_lego_mode(self, False)
        if self._lego_root is not None:
            self._lego_root.removeNode()
            self._lego_root = None
        self._restaurar_ancora_saida()
        if getattr(self, "exit_pivot", None):
            self.exit_pivot.removeNode()
            self.exit_pivot = None
        if self.model_np:
            self.model_np.clearShader()
            self.model_np.show()
        if self.outline_np and self._outline_enabled:
            self.outline_np.show()
        self.set_post_effect(dissolve=0.0, flash=0.0)
        self._limpar_fx()
