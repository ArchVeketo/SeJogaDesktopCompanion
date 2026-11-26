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
import time
from functools import cache
from typing import Any

# Panda3D GLTF loader registers support for .gltf and .glb files.
import gltf
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AntialiasAttrib,
    Mat4,
    NodePath,
    Point3,
    Quat,
    Shader,
    TransformState,
    Vec3,
)

from sejoga.animacao import danca_tuning as _danca
from sejoga.animacao import movimento_corpo_tuning as _tune
from sejoga.animacao.controlador_animacao import AnimationState
from sejoga.animacao.danca_clipes import carregar_clipe_emote
from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.animacao.squash_stretch import squash_stretch_composto
from sejoga.nucleo.cinematica import BASE_ADICIONAL_GRAUS
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rig
from sejoga.nucleo.modelo import load_model
from sejoga.nucleo.recursos import resolve_model
from sejoga.render.dedos_malha import fatiar_dedos
from sejoga.render.dinamica_contorno import RespiracaoContorno, cor_contorno_viva
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


@cache
def _shader_sombra_contato() -> Shader:
    """Shader Bayer 4x4 em screen-space para sombra de contato nítida em qualquer escala."""
    vert = """#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
out vec2 v_local;
void main() {
    v_local = p3d_Vertex.xz * 2.0;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
"""
    frag = """#version 130
uniform float u_shadow_alpha;
in vec2 v_local;
out vec4 fragColor;
float _sj_sombra_bayer(vec2 p) {
    vec2 m = floor(mod(p, 4.0));
    int i = int(m.x) + int(m.y) * 4;
    const float tbl[16] = float[16](
        0.0/16.0,  8.0/16.0,  2.0/16.0, 10.0/16.0,
       12.0/16.0,  4.0/16.0, 14.0/16.0,  6.0/16.0,
        3.0/16.0, 11.0/16.0,  1.0/16.0,  9.0/16.0,
       15.0/16.0,  7.0/16.0, 13.0/16.0,  5.0/16.0
    );
    return tbl[i];
}
void main() {
    float r2 = dot(v_local, v_local);
    float radial = 1.0 - smoothstep(0.34, 1.0, r2);
    float alpha = clamp(radial * clamp(u_shadow_alpha, 0.0, 1.0), 0.0, 1.0);
    if (r2 > 1.0 || alpha <= _sj_sombra_bayer(gl_FragCoord.xy) + 0.015) discard;
    fragColor = vec4(0.010, 0.009, 0.016, 1.0);
}
"""
    return Shader.make(Shader.SL_GLSL, vert, frag)


_NINJA_SMOKE_OFFSETS = (
    (-1.05, -0.35, -0.25, 0.72),
    (1.02, -0.30, -0.18, 0.68),
    (-0.55, -0.48, 0.72, 0.78),
    (0.58, -0.45, 0.66, 0.74),
    (0.0, -0.58, 0.25, 0.90),
    (-1.30, -0.22, 0.35, 0.60),
    (1.28, -0.22, 0.40, 0.60),
    (0.0, -0.48, 1.08, 0.64),
    (-0.45, -0.38, -0.82, 0.62),
    (0.45, -0.38, -0.78, 0.62),
)

_SANDEVISTAN_CORES = (
    (0.08, 0.96, 1.0),
    (0.14, 0.98, 0.60),
    (0.32, 0.52, 1.0),
    (0.92, 0.20, 0.76),
    (1.0, 0.32, 0.24),
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
    "pelvis",
)


# ============================================================
# Panda3D Renderer
# ============================================================


class Panda3DRenderer:
    """Encapsula Panda3D render e modelo."""

    FRAME_FILL = 0.66

    def __init__(self, showbase: ShowBase, hwnd: int, width: int, height: int, *, use_chroma_resolve: bool = True):  # noqa: PLR0915
        """Monta a cena, o modelo, o contorno e os pivôs do rig."""
        self.showbase = showbase
        self._use_chroma_resolve = use_chroma_resolve
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
        self._squash_atual = (1.0, 1.0, 1.0)
        self._pick_node_name = "body"
        self._shadow_np = None
        self._floor_screen_y: float | None = None
        self._height_above_floor_px: float = 0.0
        self._ambient_light = None
        self._dir_light = None
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
        self._outline_base_thickness = 0.0
        self._outline_breath = 0.0
        self._outline_enabled = True
        self._outline_color_rgba = (0.0, 0.0, 0.0, 1.0)
        self._outline_respiracao = RespiracaoContorno()
        self._user_scale = 1.0
        self._escala_profundidade = 1.0
        self._subida_profundidade = 0.0
        self._pbr_pipeline = None
        self._fx_root = None
        self._fx_smoke_nodes: list = []
        self._fx_ash_nodes: list = []
        self._fx_blue_nodes: list = []
        self._fx_ghost_nodes: list = []
        self._fx_ghost_shader = None
        self._sandevistan_stamps: list[dict] = []
        self._fnf_skeleton = None
        self._argolas_antena: list = []
        self._argolas_fx: list = []
        self._brilho_halo_atual: float = 0.0
        self._deslocamento_danca = Vec3(0)
        self._choque_antenas_3d = None
        self.efeitos_street = None
        self._album_colors: tuple[tuple[float, float, float], ...] = ()
        self._last_music_bass: float | None = None
        self._visual_filter = "padrao"
        self._vfx_enabled = True
        self._filter_clock = 0.0
        self._sv_step_acc = 0.0
        self._sv_allow_pose_step = True
        self._street_xray_ativo = False
        self._vfx_transicoes = None
        self._transicao_intro_estilo = ""
        self._transicao_intro_prog: float | None = None
        self._transicao_saida_prog: float | None = None
        self._paineis_armario: tuple = ()
        self._raiz_tilt_rad = 0.0
        self._lego_snapshot: list = []
        self._lego_root = None
        self._lego_floor_z = -0.5
        self._intro_pivot = None
        self._exit_orig_anchor_parent = None
        self._exit_orig_anchor_tf = None
        self._intro_orig_anchor_pos = None
        self._sono_deitado_peso = 0.0
        self._sono_sentado_peso = 0.0
        self._breakdance_chao_peso = 0.0
        self._ultimo_breakdance_pose: tuple[float, float] = (0.0, 0.0)
        self._ultimo_quat_raiz: Any = None
        self._peso_saida_quat = 0.0
        self._dz_extra_atual = 0.0
        self._squash_ref_z: float | None = None
        self._anim_air_px_suave = 0.0
        self._intro_orig_foot_local_z: float | None = None

        self._setup_scene()
        self._load_model()
        from sejoga.render.corpo_inferior import LowerBody
        from sejoga.render.prop_cuspido import PropCuspidoCena

        self.lower_body = LowerBody(self)
        self.prop_cuspido = PropCuspidoCena(self)
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
        forro = self.model_np.find("**/fundo-interno-armario")
        if forro:
            forro.setCollideMask(0)
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
            self._pick_node_name = "body"
            while not picked.isEmpty() and picked != self.model_np:
                name = picked.getName()
                if self._pick_node_name == "body" and name in self._rig_nodes:
                    self._pick_node_name = name
                if "tentacle" in name.lower():
                    self._pick_part = "tentacle"
                    break
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
        self._ambient_light = ambient
        ambient_np = self.showbase.render.attachNewNode(ambient)
        self.showbase.render.setLight(ambient_np)

        dirlight = DirectionalLight("dirlight")
        dirlight.setColor((0.8, 0.8, 0.8, 1))
        self._dir_light = dirlight
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

            if self._use_chroma_resolve:
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

    @staticmethod
    def _separar_painel_armario(modelo: NodePath) -> None:
        """Substitui o tampo frontal fechado do armário por uma moldura de 8 triângulos."""
        from panda3d.core import (
            Geom,
            GeomNode,
            GeomTriangles,
            GeomVertexData,
            GeomVertexReader,
            GeomVertexWriter,
        )

        head = modelo.find("**/head")
        gabinete = head.find("**/Armario/+GeomNode")
        if gabinete.isEmpty() or not gabinete.find("moldura-armario").isEmpty():
            return
        no = gabinete.node()
        original = no.getGeom(0)
        dados = original.getVertexData()
        leitor = GeomVertexReader(dados, "vertex")
        pontos_local = []
        pontos_head = []
        while not leitor.isAtEnd():
            pt = leitor.getData3()
            pontos_local.append(pt)
            pontos_head.append(head.getRelativePoint(gabinete, pt))
        frente = max(p.y for p in pontos_head)
        paredes = GeomTriangles(Geom.UHStatic)
        removidos: list[tuple[int, int, int]] = []
        for original_prim in original.getPrimitives():
            prim = original_prim.decompose()
            for i in range(0, prim.getNumVertices(), 3):
                indices = tuple(prim.getVertex(j) for j in range(i, i + 3))
                vertices = [pontos_head[j] for j in indices]
                if all(abs(v.y - frente) < 1e-5 and v.z > 0 for v in vertices):
                    removidos.append(indices)
                else:
                    paredes.addVertices(*indices)
        if not removidos:
            return
        paredes.closePrimitive()
        corpo = no.modifyGeom(0)
        corpo.clearPrimitives()
        corpo.addPrimitive(paredes)

        # Mapeia os 4 cantos do retângulo frontal removido para interpolar UV/normal.
        uniq = sorted({idx for tri in removidos for idx in tri})
        ox0 = min(pontos_head[i].x for i in uniq)
        ox1 = max(pontos_head[i].x for i in uniq)
        oz0 = min(pontos_head[i].z for i in uniq)
        oz1 = max(pontos_head[i].z for i in uniq)
        if ox1 - ox0 <= 1e-5 or oz1 - oz0 <= 1e-5:
            return

        def _canto(cx: float, cz: float) -> int:
            return min(uniq, key=lambda i: (pontos_head[i].x - cx) ** 2 + (pontos_head[i].z - cz) ** 2)

        c00, c10, c01, c11 = _canto(ox0, oz0), _canto(ox1, oz0), _canto(ox0, oz1), _canto(ox1, oz1)
        colunas = [
            (arr.getColumn(c).getName(), arr.getColumn(c).getNumComponents())
            for arr in dados.getFormat().getArrays()
            for c in range(arr.getNumColumns())
        ]
        # Amostra os 4 cantos por coluna antes de gravar, evitando múltiplos writers simultâneos.
        cantos_val: dict[str, tuple[tuple[float, ...], ...]] = {}
        for nome, _comp in colunas:
            rd = GeomVertexReader(dados, nome)
            vals = []
            for idx in (c00, c10, c01, c11):
                rd.setRow(idx)
                vals.append(tuple(rd.getData4f()))
            cantos_val[str(nome)] = tuple(vals)

        ix0 = ox0 + (ox1 - ox0) * (5.0 / 64.0)
        ix1 = ox1 - (ox1 - ox0) * (5.0 / 64.0)
        iz0 = oz0 + (oz1 - oz0) * (6.5 / 72.0)
        iz1 = oz1 - (oz1 - oz0) * (5.0 / 72.0)
        faixas = (
            (ox0, ox1, iz1, oz1),  # faixa superior
            (ox0, ox1, oz0, iz0),  # faixa inferior
            (ox0, ix0, iz0, iz1),  # faixa esquerda
            (ix1, ox1, iz0, iz1),  # faixa direita
        )
        pontos_uv: list[tuple[float, float]] = []
        tris = GeomTriangles(Geom.UHStatic)
        for ax0, ax1, az0, az1 in faixas:
            base = len(pontos_uv)
            for x_h, z_h in ((ax0, az0), (ax1, az0), (ax1, az1), (ax0, az1)):
                u = max(0.0, min(1.0, (x_h - ox0) / (ox1 - ox0)))
                v = max(0.0, min(1.0, (z_h - oz0) / (oz1 - oz0)))
                pontos_uv.append((u, v))
            tris.addVertices(base, base + 2, base + 1)
            tris.addVertices(base, base + 3, base + 2)
        tris.closePrimitive()

        v_moldura = GeomVertexData("moldura-armario", dados.getFormat(), Geom.UHStatic)
        v_moldura.setNumRows(len(pontos_uv))
        for nome, n_comp in colunas:
            v00, v10, v01, v11 = cantos_val[str(nome)]
            wr = GeomVertexWriter(v_moldura, nome)
            for u, v in pontos_uv:
                interp = tuple(
                    (v00[k] * (1.0 - u) + v10[k] * u) * (1.0 - v)
                    + (v01[k] * (1.0 - u) + v11[k] * u) * v
                    for k in range(4)
                )
                if str(nome) == "normal":
                    n = Vec3(interp[0], interp[1], interp[2])
                    if n.lengthSquared() > 1e-8:
                        n.normalize()
                    wr.setData3f(n)
                elif n_comp == 2:
                    wr.setData2f(interp[0], interp[1])
                elif n_comp == 4:
                    wr.setData4f(*interp)
                else:
                    wr.setData3f(interp[0], interp[1], interp[2])
        moldura_geom = Geom(v_moldura)
        moldura_geom.addPrimitive(tris)
        no_moldura = GeomNode("moldura-armario")
        no_moldura.addGeom(moldura_geom, no.getGeomState(0))
        gabinete.attachNewNode(no_moldura)

    @staticmethod
    def _escurecer_fundo_interno(modelo: NodePath) -> None:
        """Reveste as 5 paredes internas da cabeça voltadas para dentro com textura e sombra profundas."""
        from panda3d.core import (
            Geom,
            GeomNode,
            GeomTriangles,
            GeomVertexData,
            GeomVertexReader,
            GeomVertexWriter,
            Vec3,
        )

        head = modelo.find("**/head")
        gabinete = head.find("**/Armario/+GeomNode")
        if gabinete.isEmpty() or not gabinete.find("fundo-interno-armario").isEmpty():
            return
        no = gabinete.node()
        original = no.getGeom(0)
        dados_orig = original.getVertexData()
        leitor = GeomVertexReader(dados_orig, "vertex")
        pontos = []
        while not leitor.isAtEnd():
            pontos.append(head.getRelativePoint(gabinete, leitor.getData3()))
        frente_y = max(p.y for p in pontos)
        centro_cabeca = Vec3(0, 0, 0.17)

        dados_fundo = GeomVertexData("fundo-interno-armario", dados_orig.getFormat(), Geom.UHStatic)
        dados_fundo.setNumRows(dados_orig.getNumRows())
        for arr_idx in range(dados_orig.getFormat().getNumArrays()):
            arr_fmt = dados_orig.getFormat().getArray(arr_idx)
            for col_idx in range(arr_fmt.getNumColumns()):
                col = arr_fmt.getColumn(col_idx)
                name = col.getName()
                n_comp = col.getNumComponents()
                rd = GeomVertexReader(dados_orig, name)
                wr = GeomVertexWriter(dados_fundo, name)
                while not rd.isAtEnd():
                    if n_comp == 4:
                        wr.setData4f(rd.getData4f())
                    elif n_comp == 3:
                        wr.setData3f(rd.getData3f())
                    elif n_comp == 2:
                        wr.setData2f(rd.getData2f())

        faces = GeomTriangles(Geom.UHStatic)
        normais_inward: dict[int, Vec3] = {}
        for primitive in original.getPrimitives():
            prim = primitive.decompose()
            for i in range(0, prim.getNumVertices(), 3):
                a, b, c = (prim.getVertex(j) for j in range(i, i + 3))
                tri_pts = [pontos[j] for j in (a, b, c)]
                if all(v.z > 0.005 for v in tri_pts) and not all(abs(v.y - frente_y) < 1e-5 for v in tri_pts):
                    n = (tri_pts[1] - tri_pts[0]).cross(tri_pts[2] - tri_pts[0])
                    c_tri = (tri_pts[0] + tri_pts[1] + tri_pts[2]) / 3
                    if n.dot(centro_cabeca - c_tri) < 0:
                        b, c = c, b
                        n = -n
                    n.normalize()
                    faces.addVertices(a, b, c)
                    for v_idx in (a, b, c):
                        normais_inward[v_idx] = n

        if not faces.getNumPrimitives():
            return
        faces.closePrimitive()

        wr_norm = GeomVertexWriter(dados_fundo, "normal")
        wr_uv = GeomVertexWriter(dados_fundo, "texcoord.0")
        for v_idx, n in normais_inward.items():
            wr_norm.setRow(v_idx)
            n_gab = gabinete.getRelativeVector(head, n)
            wr_norm.setData3f(n_gab)
            wr_uv.setRow(v_idx)
            wr_uv.setData2f(0.03125, 0.7000)

        geom = Geom(dados_fundo)
        geom.addPrimitive(faces)
        node = GeomNode("fundo-interno-armario")
        node.addGeom(geom, no.getGeomState(0))
        fundo = gabinete.attachNewNode(node)
        fundo.setTwoSided(False, 1)
        fundo.setDepthOffset(1)
        fundo.setColorScale(0.20, 0.12, 0.42, 1.0)
        fundo.setCollideMask(0)

    def _revestir_interior_porta(self, modelo: NodePath) -> None:
        """Fecha o verso da porta do armário com textura própria interna.

        A malha ``Porta`` do glTF só tem a face frontal e as 4 bordas laterais
        (com ``doubleSided=True``), o que fazia o interior exibir a textura da
        frente espelhada quando a porta abria. Este quad opaco no plano traseiro
        (normal -Y) oclui o verso sem alterar a frente nem o contorno.
        """
        from panda3d.core import (
            Filename,
            Geom,
            GeomNode,
            GeomTriangles,
            GeomVertexData,
            GeomVertexFormat,
            GeomVertexWriter,
            SamplerState,
        )

        from sejoga.nucleo.recursos import assets_dir

        porta = modelo.find("**/door/Porta/+GeomNode")
        if porta.isEmpty():
            porta = modelo.find("**/door/**/+GeomNode")
        if porta.isEmpty():
            return
        head = modelo.find("**/head")
        if head.isEmpty():
            return
        # Cantos exatos do verso da folha da porta no espaço de ``head`` -> local de ``porta``.
        cantos_head = (
            Point3(-0.1216, 0.1160, 0.0313),
            Point3(0.1221, 0.1160, 0.0313),
            Point3(0.1221, 0.1160, 0.3242),
            Point3(-0.1216, 0.1160, 0.3242),
        )
        uvs = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
        normal_local = porta.getRelativeVector(head, Vec3(0.0, -1.0, 0.0))
        if normal_local.lengthSquared() > 1e-8:
            normal_local.normalize()

        vdata = GeomVertexData("interior-porta", GeomVertexFormat.getV3n3t2(), Geom.UHStatic)
        vdata.setNumRows(4)
        wv = GeomVertexWriter(vdata, "vertex")
        wn = GeomVertexWriter(vdata, "normal")
        wt = GeomVertexWriter(vdata, "texcoord")
        for pt_h, (u, v) in zip(cantos_head, uvs, strict=True):
            pt_local = porta.getRelativePoint(head, pt_h)
            wv.addData3f(pt_local)
            wn.addData3f(normal_local)
            wt.addData2f(u, v)

        tris = GeomTriangles(Geom.UHStatic)
        # Winding CCW visto pelo lado -Y (interior da porta aberta)
        tris.addVertices(0, 1, 2)
        tris.addVertices(0, 2, 3)
        tris.closePrimitive()

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gnode = GeomNode("interior-porta-armario")
        gnode.addGeom(geom)
        interior = porta.attachNewNode(gnode)
        interior.setTwoSided(False, 1)
        interior.setCollideMask(0)

        tex_path = assets_dir() / "textures" / "porta_interior.png"
        if tex_path.exists():
            tex = self.showbase.loader.loadTexture(Filename.fromOsSpecific(str(tex_path)))
            if tex is not None:
                tex.setMagfilter(SamplerState.FTNearest)
                tex.setMinfilter(SamplerState.FTNearest)
                tex.setWrapU(SamplerState.WMClamp)
                tex.setWrapV(SamplerState.WMClamp)
                interior.setTexture(tex, 1)
        else:
            interior.setColorScale(0.18, 0.14, 0.34, 1.0)

    @staticmethod
    def _tile_bounds_px(
        w: int, h: int, u_min: float, u_max: float, v_min: float, v_max: float
    ) -> tuple[int, int, int, int]:
        return (
            max(0, round(u_min * w)),
            min(w, round(u_max * w)),
            max(0, round((1.0 - v_max) * h)),
            min(h, round((1.0 - v_min) * h)),
        )

    @staticmethod
    def _eixo_maior_anel_na_textura(
        tex, u_min: float, u_max: float, v_min: float, v_max: float
    ) -> str | None:
        """Indica 'u' ou 'v' se o anel desenhado no tile tiver eixo maior distinto."""
        if tex is None:
            return None
        from panda3d.core import PNMImage

        pnm = PNMImage()
        if not tex.store(pnm):
            return None
        w, h = pnm.getXSize(), pnm.getYSize()
        if w <= 0 or h <= 0:
            return None
        x0, x1, y0, y1 = Panda3DRenderer._tile_bounds_px(w, h, u_min, u_max, v_min, v_max)
        xs = [x for y in range(y0, y1) for x in range(x0, x1) if pnm.getAlpha(x, y) > 0.5]
        ys = [y for y in range(y0, y1) for x in range(x0, x1) if pnm.getAlpha(x, y) > 0.5]
        if not xs or not ys:
            return None
        span_u = max(xs) - min(xs) + 1
        span_v = max(ys) - min(ys) + 1
        return "u" if span_u > span_v else ("v" if span_v > span_u else None)

    @staticmethod
    def _isolar_textura_argola(
        nome: str, ta, tex, u_min: float, u_max: float, v_min: float, v_max: float
    ):
        """Extrai o tile da argola com borda transparente e WMClamp contra MSAA."""
        if ta is None or tex is None or ta.getNumOnStages() <= 0:
            return None
        from panda3d.core import PNMImage, Texture

        pnm = PNMImage()
        if not tex.store(pnm):
            return None
        w, h = pnm.getXSize(), pnm.getYSize()
        if w <= 0 or h <= 0:
            return None
        x0, x1, y0, y1 = Panda3DRenderer._tile_bounds_px(w, h, u_min, u_max, v_min, v_max)
        tw, th = max(1, x1 - x0), max(1, y1 - y0)
        tile = PNMImage(tw + 2, th + 2, 4)
        tile.addAlpha()
        tile.fill(0, 0, 0)
        tile.alphaFill(0.0)
        tile.copySubImage(pnm, 1, 1, x0, y0, tw, th)
        ntex = Texture(f"argola-tile-{nome}")
        ntex.load(tile)
        ntex.setFormat(tex.getFormat())
        ntex.setMinfilter(Texture.FTNearest)
        ntex.setMagfilter(Texture.FTNearest)
        ntex.setWrapU(Texture.WMClamp)
        ntex.setWrapV(Texture.WMClamp)
        stage = ta.getOnStage(0)
        return ta.removeOnStage(stage).addOnStage(stage, ntex), (w, h, x0, y1, tw, th)

    @staticmethod
    def _deve_inverter_uv_argola(pts, uvs, tex, limites_uv) -> bool:
        eixo_maior = Panda3DRenderer._eixo_maior_anel_na_textura(tex, *limites_uv)
        if eixo_maior not in ("u", "v"):
            return False
        e01, e03 = pts[1] - pts[0], pts[3] - pts[0]
        h01, h03 = math.hypot(e01.x, e01.y), math.hypot(e03.x, e03.y)
        if abs(h01 - h03) <= 1e-4:
            return False
        u_em_01 = abs(uvs[1].x - uvs[0].x) >= abs(uvs[1].y - uvs[0].y)
        quer_01 = u_em_01 if eixo_maior == "u" else (not u_em_01)
        return (h03 > h01) if quer_01 else (h01 > h03)

    @staticmethod
    def _ajustar_uv_geom_argola(
        np: NodePath, gn, gi: int, ref_np: NodePath, alpha_attr, trans_attr
    ) -> None:
        from panda3d.core import GeomVertexReader, GeomVertexWriter, TextureAttrib

        state = gn.getGeomState(gi)
        vdata = gn.modifyGeom(gi).modifyVertexData()
        uv_col = "texcoord.0" if vdata.hasColumn("texcoord.0") else (
            "texcoord" if vdata.hasColumn("texcoord") else None
        )
        if uv_col is None or not vdata.hasColumn("vertex"):
            gn.setGeomState(gi, state.addAttrib(alpha_attr).addAttrib(trans_attr))
            return
        vr, uvr = GeomVertexReader(vdata, "vertex"), GeomVertexReader(vdata, uv_col)
        pts, uvs = [], []
        while not vr.isAtEnd() and not uvr.isAtEnd():
            pts.append(ref_np.getRelativePoint(np, vr.getData3f()))
            uvs.append(uvr.getData2f())
        if len(pts) != 4 or len(uvs) != 4:
            gn.setGeomState(gi, state.addAttrib(alpha_attr).addAttrib(trans_attr))
            return

        u_min, u_max = min(float(uv.x) for uv in uvs), max(float(uv.x) for uv in uvs)
        v_min, v_max = min(float(uv.y) for uv in uvs), max(float(uv.y) for uv in uvs)
        inset = 1.5 / 1024.0
        tem_folga = (u_max - u_min) > 3.0 * inset and (v_max - v_min) > 3.0 * inset
        u0, u1 = (u_min + inset, u_max - inset) if tem_folga else (u_min, u_max)
        v0, v1 = (v_min + inset, v_max - inset) if tem_folga else (v_min, v_max)

        ta = state.getAttrib(TextureAttrib)
        tex = ta.getTexture() if ta is not None else np.findTexture("*")
        swap_uv = Panda3DRenderer._deve_inverter_uv_argola(
            pts, uvs, tex, (u_min, u_max, v_min, v_max)
        )
        isolado = Panda3DRenderer._isolar_textura_argola(
            np.getName(), ta, tex, u_min, u_max, v_min, v_max
        )
        new_state = state.addAttrib(alpha_attr).addAttrib(trans_attr)
        if isolado is not None:
            new_state = new_state.addAttrib(isolado[0])
        gn.setGeomState(gi, new_state)

        wr = GeomVertexWriter(vdata, uv_col)
        for uv in uvs:
            fu = 0 if abs(uv.x - u_min) <= abs(uv.x - u_max) else 1
            fv = 0 if abs(uv.y - v_min) <= abs(uv.y - v_max) else 1
            if swap_uv:
                fu, fv = fv, fu
            uu, vv = (u0 if fu == 0 else u1), (v0 if fv == 0 else v1)
            if isolado is not None:
                w, h, x0, y1, tw, th = isolado[1]
                uu = (1.0 + (uu * w - x0)) / (tw + 2)
                vv = (1.0 + (vv * h - (h - y1))) / (th + 2)
            wr.setData2f(uu, vv)

    @staticmethod
    def _corrigir_uv_argola_antena(
        cand: NodePath, raiz_np: NodePath | None = None
    ) -> None:
        """Elimina sangramento de tile vizinho nos quads das argolas e ajusta alfa."""
        from panda3d.core import AlphaTestAttrib, ColorBlendAttrib, TransparencyAttrib

        if cand is None or cand.isEmpty():
            return
        ref_np = raiz_np if (raiz_np is not None and not raiz_np.isEmpty()) else cand.getParent()
        alpha_attr = AlphaTestAttrib.make(AlphaTestAttrib.MGreater, 0.5)
        trans_attr = TransparencyAttrib.make(TransparencyAttrib.MAlpha)
        blend_attr = ColorBlendAttrib.make(
            ColorBlendAttrib.MAdd,
            ColorBlendAttrib.OIncomingAlpha,
            ColorBlendAttrib.OOneMinusIncomingAlpha,
            ColorBlendAttrib.MAdd,
            ColorBlendAttrib.OOne,
            ColorBlendAttrib.OOneMinusIncomingAlpha,
        )

        vistos: set[int] = set()
        for np in [cand, *cand.findAllMatches("**/+GeomNode")]:
            if np.isEmpty() or not np.node().isGeomNode():
                continue
            gn = np.node()
            if id(gn) in vistos:
                continue
            vistos.add(id(gn))
            for gi in range(gn.getNumGeoms()):
                Panda3DRenderer._ajustar_uv_geom_argola(
                    np, gn, gi, ref_np, alpha_attr, trans_attr
                )

        cand.setAttrib(alpha_attr, 1)
        cand.setAttrib(trans_attr, 1)
        cand.setAttrib(blend_attr, 10)

    def _registrar_argolas_antenas(self, head_r_ant, head_l_ant, out_r_ant, out_l_ant) -> None:
        self._argolas_antena = []
        for eh_outline, raiz_np, r_ant, l_ant in (
            (False, self.model_np, head_r_ant, head_l_ant),
            (True, self.outline_np, out_r_ant, out_l_ant),
        ):
            if raiz_np is None:
                continue
            aneis = [
                cand for cand in raiz_np.findAllMatches("**/circ*") if "antena" in cand.getName()
            ]
            for cand in aneis:
                if not eh_outline:
                    self._corrigir_uv_argola_antena(cand, raiz_np)
                bm = cand.getTightBounds(raiz_np)
                cx = (bm[0].x + bm[1].x) * 0.5 if bm else 0.0
                eh_direita = cx < 0.0
                ant_alvo = r_ant if eh_direita else l_ant
                if ant_alvo is not None and not ant_alvo.isEmpty():
                    cand.wrtReparentTo(ant_alvo)
                b_local = cand.getTightBounds(cand.getParent())
                centro = (b_local[0] + b_local[1]) * 0.5 if b_local else cand.getPos()
                eixo = Vec3(0.559 if eh_direita else -0.559, -0.425, 0.711)
                self._argolas_antena.append(
                    (cand, Point3(cand.getPos()), Vec3(cand.getScale()), centro, eixo, eh_outline)
                )
                if eh_outline:
                    cand.hide()
                    cand.stash()

    def _configurar_antenas_e_adornos(self, head_node) -> None:
        from sejoga.render.choque_antenas_3d import ChoqueAntenas3D
        from sejoga.render.efeitos_street import GerenciadorEfeitosStreet

        win_cfg = self.showbase.settings.window
        self.efeitos_street = GerenciadorEfeitosStreet(
            self.model_anchor,
            head_node=head_node,
            model_node=self.model_np,
            paleta=getattr(win_cfg, "vfx_palette", "auto"),
            escala_global=float(getattr(win_cfg, "vfx_scale", 1.0)),
            habilitado=bool(getattr(win_cfg, "vfx_enabled", True)),
            colorkey_hex=str(getattr(win_cfg, "colorkey_color", "#FF00FF")),
        )
        self._vfx_enabled = bool(getattr(win_cfg, "vfx_enabled", True))
        self._argolas_fx = []
        head_r_ant = head_node.find("**/antena-direita")
        head_l_ant = head_node.find("**/antena-esquerda")
        out_head = self.outline_np.find("**/head") if self.outline_np is not None else None
        out_r_ant = (
            out_head.find("**/antena-direita")
            if out_head is not None and not out_head.isEmpty()
            else None
        )
        out_l_ant = (
            out_head.find("**/antena-esquerda")
            if out_head is not None and not out_head.isEmpty()
            else None
        )
        self._registrar_argolas_antenas(head_r_ant, head_l_ant, out_r_ant, out_l_ant)
        self._criar_argolas_energia_fx(head_r_ant, head_l_ant)
        self._choque_antenas_3d = ChoqueAntenas3D(head_node, head_r_ant, head_l_ant)

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
        self._separar_painel_armario(model_np)
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
        self._escurecer_fundo_interno(model_np)
        self._revestir_interior_porta(model_np)
        self._setup_shadow()
        self.set_visual_scale(self.showbase.settings.window.scale)

        self._apply_rig_to_model()
        from sejoga.render.rig_flexivel import FlexibleRig

        self.flexible_rig = FlexibleRig(self)

        # Normaliza ``unit_scale`` pela altura de referência (480px) para que os
        # tentáculos tenham exatamente o mesmo alcance em janelas de 480, 900 ou 1200px!
        unit_scale = float(self._view_height / 480.0 / self._fit_scale)
        head_node = self._rig_nodes["head"]
        # Âncoras centralizadas no meio do vão e avançadas para frente (y=0.07..0.095)
        # evitando que os tentáculos nasçam colados na lateral ou presos no fundo do armário.
        spawn_points = [
            self.model_np.getRelativePoint(head_node, Vec3(0.005, 0.085, 0.145)),
            self.model_np.getRelativePoint(head_node, Vec3(-0.015, 0.088, 0.175)),
            self.model_np.getRelativePoint(head_node, Vec3(0.020, 0.082, 0.120)),
            self.model_np.getRelativePoint(head_node, Vec3(-0.020, 0.084, 0.105)),
            self.model_np.getRelativePoint(head_node, Vec3(0.000, 0.092, 0.195)),
            self.model_np.getRelativePoint(head_node, Vec3(0.022, 0.078, 0.165)),
            self.model_np.getRelativePoint(head_node, Vec3(-0.008, 0.080, 0.130)),
            self.model_np.getRelativePoint(head_node, Vec3(0.015, 0.075, 0.190)),
            self.model_np.getRelativePoint(head_node, Vec3(-0.022, 0.076, 0.150)),
            self.model_np.getRelativePoint(head_node, Vec3(0.008, 0.086, 0.098)),
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
        from sejoga.render.gestos_dedos import FingerGestures

        self.finger_gestures = FingerGestures(self)
        from sejoga.musica.caixa_som import MusicSpeaker

        self.music_speaker = MusicSpeaker(self, self.showbase.settings.music.speaker_style)
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
        self._configurar_antenas_e_adornos(head_node)
        self.set_outline_settings(self.showbase.settings.window)
        self.set_visual_filter(
            getattr(self.showbase.settings.window, "visual_filter", "padrao")
        )
        self.set_vfx_settings(self.showbase.settings.window)
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
            if getattr(self, "_outline_enabled", False) and hasattr(self, "_outline_width_px"):
                self._atualizar_espessura_contorno(resetar=False)

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
    def _criar_textura_sombra(size: int = 96):
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
                opaque = r2 <= 0.62 or (r2 <= 0.88 and (x + y) % 2 == 0)
                img.setXelA(x, y, 0.06, 0.05, 0.10, 1.0 if opaque else 0.0)
        tex = Texture("mascot-contact-shadow")
        tex.load(img)
        tex.setMinfilter(Texture.FTNearest)
        tex.setMagfilter(Texture.FTNearest)
        return tex

    def _setup_shadow(self) -> None:
        """Cria sombra de contato estilizada no plano do chão, independente dos pés."""
        from panda3d.core import CardMaker, TransparencyAttrib

        card = CardMaker("mascot-shadow-card")
        card.setFrame(-0.5, 0.5, -0.5, 0.5)
        shadow = self.showbase.render.attachNewNode(card.generate())
        shadow.setHpr(0.0, -82.0, 0.0)
        shadow.setTwoSided(True)
        shadow.setLightOff(1)
        shadow.setShader(_shader_sombra_contato(), 1000)
        shadow.setShaderInput("u_shadow_alpha", 1.0)
        shadow.setDepthWrite(False)
        shadow.setTransparency(TransparencyAttrib.MNone)
        shadow.setCollideMask(0)
        shadow.setBin("background", 10)
        self._shadow_np = shadow

    @staticmethod
    def _suavizar_normais_contorno(outline_np: NodePath) -> None:
        """Solda normais por posição nas malhas do contorno para eliminar frestas de cubo."""
        from panda3d.core import GeomVertexReader, GeomVertexWriter

        for np in outline_np.findAllMatches("**/+GeomNode"):
            gn = np.node()
            for gi in range(gn.getNumGeoms()):
                geom = gn.modifyGeom(gi)
                vdata = geom.modifyVertexData()
                if not vdata.hasColumn("vertex") or not vdata.hasColumn("normal"):
                    continue
                vr = GeomVertexReader(vdata, "vertex")
                nr = GeomVertexReader(vdata, "normal")
                chaves: list[tuple[float, float, float]] = []
                unicas: dict[tuple[float, float, float], dict[tuple[float, float, float], Vec3]] = {}
                while not vr.isAtEnd():
                    pos = vr.getData3()
                    norm = Vec3(nr.getData3())
                    if norm.lengthSquared() > 1e-10:
                        norm.normalize()
                    chave = (round(float(pos.x), 4), round(float(pos.y), 4), round(float(pos.z), 4))
                    chaves.append(chave)
                    n_key = (round(float(norm.x), 3), round(float(norm.y), 3), round(float(norm.z), 3))
                    unicas.setdefault(chave, {})[n_key] = norm
                medias: dict[tuple[float, float, float], Vec3] = {}
                for chave, bucket in unicas.items():
                    soma = Vec3(0.0, 0.0, 0.0)
                    for vec in bucket.values():
                        soma += vec
                    if soma.lengthSquared() > 1e-10:
                        soma.normalize()
                    else:
                        soma = Vec3(0.0, -1.0, 0.0)
                    medias[chave] = soma
                nw = GeomVertexWriter(vdata, "normal")
                for chave in chaves:
                    nw.setData3(medias[chave])

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
uniform mat3 p3d_NormalMatrix;
// Espessura efetiva do frame (respiração). Cai para outline_thickness quando
// o render não atualiza o runtime, preservando o comportamento estático.
uniform float outline_thickness;
uniform float outline_thickness_runtime;
uniform float u_sketch_mode;
uniform float u_sketch_time;
float _sj_vhash(vec3 p) {
    return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453);
}
void main() {
    outline_uv = p3d_MultiTexCoord0;
    float thickness = outline_thickness_runtime > 0.0
        ? outline_thickness_runtime : outline_thickness;
    // Linha "desenhada": faces de perfil (normal perpendicular ao olhar ortográfico)
    // ganham um pouco mais de espessura que as frontais.
    vec3 view_normal = normalize(p3d_NormalMatrix * p3d_Normal);
    float facing = abs(dot(view_normal, vec3(0.0, 0.0, 1.0)));
    float orientacao = mix(1.15, 0.9, clamp(facing, 0.0, 1.0));
    vec3 normal_n = normalize(p3d_Normal);
    vec3 offset = normal_n * thickness * orientacao;
    if (u_sketch_mode > 0.5) {
        // Modo Rascunho / Spider-Punk: contorno fervendo a 8 FPS com traço irregular!
        float st = floor(u_sketch_time * 8.0);
        float h1 = (_sj_vhash(floor(p3d_Vertex.xyz * 14.0) + vec3(st * 0.37)) - 0.5) * 2.0;
        float h2 = (_sj_vhash(floor(p3d_Vertex.yzx * 14.0) + vec3(st * 0.71)) - 0.5) * 2.0;
        offset = normal_n * thickness * orientacao * (1.35 + 0.48 * h1)
            + vec3(h1, 0.0, h2) * thickness * 0.42;
    }
    gl_Position = p3d_ModelViewProjectionMatrix * (p3d_Vertex + vec4(offset, 0.0));
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
        for m in self.outline_np.findAllMatches("**/moldura-armario"):
            m.removeNode()
        for f in self.outline_np.findAllMatches("**/fundo-interno-armario"):
            f.removeNode()

        # Garante que Armario seja um sólido 3D fechado no contorno para não projetar
        # arestas internas na abertura da boca nem criar contorno duplo quando fechado.
        out_arm = self.outline_np.find("**/Armario/+GeomNode")
        if not out_arm.isEmpty():
            geom = out_arm.node().modifyGeom(0)
            prim = geom.modifyPrimitive(0)
            prim.addVertices(20, 21, 22)
            prim.addVertices(20, 22, 23)

        # Fecha a face traseira da porta no contorno para que a folha seja um sólido 3D
        # fechado, e mantém o contorno da porta oculto para não projetar aresta interna amarela na boca.
        out_door = self.outline_np.find("**/door/**/+GeomNode")
        if not out_door.isEmpty():
            geom_d = out_door.node().modifyGeom(0)
            prim_d = geom_d.modifyPrimitive(0)
            prim_d.addVertices(6, 10, 21)
            prim_d.addVertices(6, 21, 18)
            out_door.hide()
        self._suavizar_normais_contorno(self.outline_np)
        self.outline_np.setShader(Shader.make(Shader.SL_GLSL, vertex, fragment), 1000)
        self.outline_np.setAttrib(
            CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise), 1000
        )
        self.outline_np.setLightOff(1000)
        self.outline_np.setCollideMask(0)
        # Runtime 0 => shader usa a espessura estática até a respiração começar.
        self.outline_np.setShaderInput("outline_thickness_runtime", 0.0)
        self.outline_np.setShaderInput("u_sketch_mode", 0.0)
        self.outline_np.setShaderInput("u_sketch_time", 0.0)

    def set_outline_settings(self, settings) -> None:
        """Aplica as configurações do contorno respeitando a escolha do usuário."""
        if not self.outline_np:
            return
        filtro = getattr(self, "_visual_filter", "blockbench")
        habilitar = bool(getattr(settings, "outline_enabled", True)) and filtro != "blockbench"
        self._outline_enabled = habilitar
        self.outline_np.setShaderInput("outline_enabled", self._outline_enabled)
        self.outline_np.setShaderInput(
            "u_sketch_mode", 1.0 if filtro in ("spiderverse", "rascunho", "street") else 0.0
        )
        if not habilitar:
            # Desliga contorno no modelo e nos tentáculos: borda 100% invisível.
            self.outline_np.hide()
            self.outline_np.stash()
            if self.tentacle_pool:
                for tentacle in self.tentacle_pool.tentacles:
                    if tentacle.outline_mesh_node:
                        tentacle.outline_mesh_node.hide()
            return
        self.outline_np.unstash()
        self.outline_np.show()
        color = settings.outline_color.lstrip("#")
        # Converte sRGB -> linear (pow 2.2) antes do FBO HDR do SimplePBR para
        # evitar cores lavadas/acinzentadas após o tonemap Filmic.
        rgb = tuple(
            (int(color[index : index + 2], 16) / 255.0) ** 2.2
            for index in (0, 2, 4)
        )
        self._outline_color_rgba = (*rgb, 1.0)
        self.outline_np.setShaderInput("outline_color", self._outline_color_rgba)
        if self.tentacle_pool:
            colorkey_hex = str(getattr(settings, "colorkey_color", "#FF00FF"))
            self.tentacle_pool.aplicar_estilo(
                filtro,
                True,
                self._outline_color_rgba,
                colorkey_hex,
            )
        # Espessura invariante ao resize 2x/3x do canvas e escala de profundidade.
        self._outline_width_px = float(getattr(settings, "outline_width", 2.5))
        self._outline_breath = float(getattr(settings, "outline_breath", 0.0))
        self._atualizar_espessura_contorno(resetar=True)

    def _atualizar_espessura_contorno(self, *, resetar: bool = False) -> None:
        if not self.outline_np or not self.model_np:
            return
        largura = float(getattr(self, "_outline_width_px", 2.5))
        if getattr(self, "_visual_filter", "blockbench") == "street":
            largura *= 1.20
        model_scale = max(1e-4, float(self.model_np.getScale().z))
        units_per_px = float(self._view_height) / max(1.0, float(self.height))
        thickness = largura * units_per_px / model_scale
        self.outline_np.setShaderInput("outline_thickness", thickness)
        self._outline_base_thickness = thickness
        if resetar or self._outline_breath <= 0.0:
            self._outline_respiracao.reset(thickness)
            self.outline_np.setShaderInput("outline_thickness_runtime", thickness)
            self._last_outline_thickness_sent = thickness

    def set_visual_filter(self, filter_name: str) -> None:
        """Alterna o filtro visual ao vivo entre os 5 estilos canônicos."""
        from sejoga.configuracao import normalizar_filtro_visual

        codigos = {
            "blockbench": 10.0,
            "street": 3.0,
            "anime": 5.0,
            "spiderverse": 2.0,
            "holograma": 7.0,
        }
        iluminacao = {
            "blockbench": ((0.58, 0.56, 0.53, 1.0), (0.64, 0.67, 0.72, 1.0)),
            "street": ((0.36, 0.37, 0.42, 1.0), (0.88, 0.86, 0.82, 1.0)),
            "anime": ((0.48, 0.48, 0.52, 1.0), (0.86, 0.85, 0.84, 1.0)),
            "spiderverse": ((0.46, 0.45, 0.44, 1.0), (0.84, 0.82, 0.78, 1.0)),
            "holograma": ((0.44, 0.48, 0.54, 1.0), (0.84, 0.90, 0.96, 1.0)),
        }
        escolhido = normalizar_filtro_visual(filter_name)
        self._visual_filter = escolhido
        self._sv_step_acc = 0.0
        self._sv_allow_pose_step = True
        if getattr(self, "_street_xray_ativo", False):
            self._limpar_xray_street()
        efeitos = getattr(self, "efeitos_street", None)
        if efeitos is not None:
            efeitos.configurar(filtro=escolhido)
        codigo = codigos[escolhido]
        amb_col, dir_col = iluminacao[escolhido]
        if self._ambient_light is not None:
            self._ambient_light.setColor(amb_col)
        if self._dir_light is not None:
            self._dir_light.setColor(dir_col)
        if self._pbr_pipeline is not None:
            from sejoga.render.resolucao_croma import configurar_textura_cena_nearest

            quad = self._pbr_pipeline._post_process_quad
            win = getattr(self.showbase, "win", None)
            vw = float(win.getXSize()) if win else float(self.width)
            vh = float(win.getYSize()) if win else float(self.height)
            quad.setShaderInput("u_viewport_size", (vw, vh))
            quad.setShaderInput("u_visual_filter", codigo)
            quad.setShaderInput("u_pixel_size", float(max(2.0, round(vh / 240.0))))
            configurar_textura_cena_nearest(quad)
        win_cfg = self.showbase.settings.window
        colorkey_hex = str(getattr(win_cfg, "colorkey_color", "#FF00FF"))
        if getattr(self, "tentacle_drips", None) is not None:
            self.tentacle_drips.aplicar_estilo(escolhido, colorkey_hex)
        if getattr(self, "_choque_antenas_3d", None) is not None:
            self._choque_antenas_3d.aplicar_estilo(
                escolhido,
                str(getattr(win_cfg, "vfx_palette", "auto")),
                colorkey_hex,
            )
        self.set_outline_settings(win_cfg)

    def set_vfx_settings(self, settings) -> None:
        """Atualiza estado, paleta e escala dos efeitos street-punk ao vivo."""
        self._vfx_enabled = bool(getattr(settings, "vfx_enabled", True))
        if not self._vfx_enabled and getattr(self, "tentacle_drips", None) is not None:
            self.tentacle_drips.limpar()
        paleta = str(getattr(settings, "vfx_palette", "auto"))
        colorkey_hex = str(getattr(settings, "colorkey_color", "#FF00FF"))
        if self.efeitos_street is not None:
            self.efeitos_street.configurar(
                habilitado=self._vfx_enabled,
                paleta=paleta,
                escala_global=float(getattr(settings, "vfx_scale", 1.0)),
                colorkey_hex=colorkey_hex,
            )
        if self._choque_antenas_3d is not None:
            self._choque_antenas_3d.aplicar_estilo(
                getattr(self, "_visual_filter", "padrao"),
                paleta,
                colorkey_hex,
            )
            if not self._vfx_enabled:
                self._choque_antenas_3d.ocultar()

    def disparar_pouso_entrada(self) -> None:
        """Dispara o pulso de contato da Queda Heroica."""
        if self.efeitos_street is not None and self._vfx_enabled:
            self.efeitos_street.disparar_pouso_entrada()

    def disparar_impacto_chao(self, forca: float = 1.0) -> None:
        """Dispara impacto street-ink rente aos tênis no pouso/queda."""
        if self.efeitos_street is not None and self._vfx_enabled:
            self.efeitos_street.disparar_impacto_chao(forca)

    def disparar_impacto_parede(
        self, kind: str, velocity: tuple[float, float], forca: float = 1.0
    ) -> None:
        """Dispara impacto street-ink direcional ao bater na parede ou teto."""
        if self.efeitos_street is not None and self._vfx_enabled:
            self.efeitos_street.disparar_impacto_parede(kind, velocity, forca)

    def disparar_carinho(self) -> None:
        """Dispara coração street-ink saindo do topo da cabeça no carinho real."""
        if self.efeitos_street is not None and self._vfx_enabled:
            self.efeitos_street.disparar_carinho()

    def disparar_flash_impacto(self, forca: float = 0.45) -> None:
        """Mantido por compatibilidade; o feedback visual de impacto agora vive nos efeitos street."""
        del forca

    def set_album_colors(
        self,
        colors: tuple[tuple[float, float, float], ...] | list[tuple[float, float, float]] | None,
    ) -> None:
        """Recebe a paleta extraída da capa do álbum para o palco e Cyber-Ink."""
        self._album_colors = tuple(colors or ())
        speaker = getattr(self, "music_speaker", None)
        if speaker is not None and hasattr(speaker, "set_album_colors"):
            speaker.set_album_colors(self._album_colors)

    def _update_outline_breath(self, dt, motion) -> None:
        """Modula espessura pela respiração e cor do contorno via Cyber-Ink vivo."""
        if (
            not self.outline_np
            or not self._outline_enabled
            or self.outline_np.isHidden()
        ):
            return
        if self._outline_base_thickness > 0.0 and self._outline_breath > 0.0:
            compression = float(getattr(motion, "compression", 0.0))
            thickness = self._outline_respiracao.update(
                dt, self._outline_base_thickness, compression, self._outline_breath
            )
            ultimo_t = getattr(self, "_last_outline_thickness_sent", None)
            if ultimo_t is None or abs(thickness - ultimo_t) > 1e-5:
                self._last_outline_thickness_sent = thickness
                self.outline_np.setShaderInput("outline_thickness_runtime", thickness)

        base_rgba = getattr(self, "_outline_color_rgba", (0.0, 0.0, 0.0, 1.0))
        ctrl = getattr(self.showbase, "animation_controller", None)
        estado = (
            ctrl.state.value
            if (ctrl is not None and getattr(ctrl, "state", None) is not None)
            else "idle"
        )
        dance_m = getattr(ctrl, "dance_motion", None)
        bass_raw = getattr(self, "_last_music_bass", None)
        if bass_raw is not None:
            bass = float(bass_raw)
        elif ctrl is not None and getattr(ctrl, "music_active", False):
            bass = float(getattr(dance_m, "bass", 0.0) or 0.0)
        else:
            bass = 0.0
        choque = bool(
            self._choque_antenas_3d is not None
            and getattr(self._choque_antenas_3d, "_ganho_visivel", 0.0) > 0.08
        )
        carinho = bool(
            ctrl is not None
            and (
                getattr(ctrl, "_reaction", None) == AnimationState.PET
                or estado in ("pet", "celebrate")
            )
        )
        impacto = float(getattr(motion, "impact", 0.0) or 0.0)
        album_cores = getattr(self, "_album_colors", ())
        album_lin = (
            tuple(max(0.0, min(1.0, float(c))) ** 2.2 for c in album_cores[0])
            if album_cores
            else None
        )
        rgb_viva = cor_contorno_viva(
            base_rgba[:3],
            estado,
            bass=bass,
            choque=choque,
            carinho=carinho,
            impacto=impacto,
            album_rgb=album_lin,
        )
        nova_cor = (
            float(rgb_viva[0]),
            float(rgb_viva[1]),
            float(rgb_viva[2]),
            float(base_rgba[3]),
        )
        cor_ant = getattr(self, "_last_outline_color_sent", None)
        if cor_ant is None or max(abs(a - b) for a, b in zip(nova_cor, cor_ant, strict=True)) > 1e-4:
            self._last_outline_color_sent = nova_cor
            self.outline_np.setShaderInput("outline_color", nova_cor)
            if (
                self.tentacle_pool is not None
                and getattr(self, "_visual_filter", "padrao") == "padrao"
            ):
                for tentacle in self.tentacle_pool.tentacles:
                    if tentacle.outline_mesh_node is not None and not tentacle.outline_mesh_node.isHidden():
                        tentacle.outline_mesh_node.setShaderInput("outline_color", nova_cor)

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
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        if getattr(self, "_pbr_pipeline", None) is not None:
            quad = self._pbr_pipeline._post_process_quad
            quad.setShaderInput(
                "u_viewport_size", (float(self.width), float(self.height))
            )
            quad.setShaderInput("u_pixel_size", float(max(2.0, round(self.height / 240.0))))
        lens = self.showbase.cam.node().getLens()
        if hasattr(lens, "setAspectRatio"):
            lens.setAspectRatio(self.width / self.height)
        self._update_view_dimensions()

    @property
    def pixels_per_unit(self) -> float:
        """Fator atual de pixels por unidade do modelo com escala e profundidade."""
        view_h = max(1e-6, float(getattr(self, "_view_height", 1.0) or 1.0))
        h_px = max(1.0, float(getattr(self, "height", 1) or 1))
        fit = float(getattr(self, "_fit_scale", 1.0) or 1.0)
        user = float(getattr(self, "_user_scale", 1.0) or 1.0)
        prof = float(getattr(self, "_escala_profundidade", 1.0) or 1.0)
        return max(20.0, (h_px / view_h) * fit * user * prof)

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
        if (
            getattr(self, "_visual_filter", "blockbench") == "spiderverse"
            and not getattr(self, "_sv_allow_pose_step", True)
        ):
            return
        self._ultima_pose = pose_dict
        self._door_requested = 0.0
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
            # A torção-base do cotovelo é a mesma usada pela FK da correção.
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
                if group_name == "door":
                    outline_node.hide()
        if getattr(self.showbase, "animation_controller", None) is None:
            self._aplicar_squash_stretch()
            if self._floor_screen_y is None:
                self.atualizar_sombra_contato()

    def set_ground_projection(
        self, floor_screen_y: float | None, height_above_floor_px: float = 0.0
    ) -> None:
        """Registra a projeção do chão abaixo do mascote para desacoplar a sombra do pé."""
        self._floor_screen_y = floor_screen_y
        self._height_above_floor_px = max(0.0, float(height_above_floor_px))

    def _pesos_pose_sombra(self, controller) -> tuple[float, float]:
        """Retorna pesos suaves (deitado, sentado) para a projeção da sombra."""
        peso_deitado = float(getattr(self, "_sono_deitado_peso", 0.0))
        peso_sentado = float(getattr(self, "_sono_sentado_peso", 0.0))
        if controller is not None:
            st = getattr(controller, "state", None)
            t_est = float(getattr(controller, "state_time", 0.0))
            if st == AnimationState.SLEEP:
                modo = getattr(controller, "modo_sono", "")
                ent = suavizar_quintico(max(0.0, min(1.0, (t_est - 0.15) / 1.85)))
                if modo == "deitado" and peso_deitado <= 0.0 and t_est > 0.2:
                    peso_deitado = ent
                elif modo == "sentado" and peso_sentado <= 0.0 and t_est > 0.2:
                    peso_sentado = ent
            elif st is not None and st.value == "sit" and peso_sentado <= 0.0:
                peso_sentado = suavizar_quintico(max(0.0, min(1.0, t_est / 0.45)))
        return max(0.0, min(1.0, peso_deitado)), max(0.0, min(1.0, peso_sentado))

    def _alcance_aereo_sombra(
        self,
        controller,
        dt: float,
        units_z: float,
        anchor_scale: Vec3,
        peso_deitado: float,
        peso_sentado: float,
    ) -> float:
        """Calcula o fator de encolhimento/opacidade aérea suavizado (0..1)."""
        em_chao_deitado = (
            float(getattr(self, "_breakdance_chao_peso", 0.0)) > 0.05
            or peso_deitado > 0.05
            or peso_sentado > 0.05
        )
        anim_air_raw = 0.0
        if (
            not em_chao_deitado
            and self._height_above_floor_px <= 1.0
            and self._suspension_pivot is not None
        ):
            susp_z = float(self._suspension_pivot.getZ())
            solo_base = (
                float(getattr(self.lower_body, "ground_offset", 0.0))
                * float(self.model_np.getSz())
            )
            anim_air_raw = (
                max(0.0, susp_z - max(0.0, solo_base))
                * float(anchor_scale.z)
                / max(1e-6, units_z)
            )
        alpha_air = 1.0 - math.exp(-18.0 * dt)
        self._anim_air_px_suave += (anim_air_raw - self._anim_air_px_suave) * alpha_air
        intro_air_px = 0.0
        if (
            self.model_anchor is not None
            and getattr(self, "_intro_orig_anchor_pos", None) is not None
        ):
            foot_loc = float(
                self._intro_orig_foot_local_z
                if getattr(self, "_intro_orig_foot_local_z", None) is not None
                else -0.52
            )
            foot_comp_z = foot_loc * (1.0 - float(anchor_scale.z))
            intro_dz = (
                float(self.model_anchor.getZ()) - foot_comp_z
            ) - float(self._intro_orig_anchor_pos.z)
            intro_air_px = max(0.0, intro_dz / max(1e-6, units_z))
        altura_total_px = self._height_above_floor_px + self._anim_air_px_suave + intro_air_px
        altura_max_px = max(340.0, float(self._model_radius_px) * 10.0)
        h_norm = max(0.0, min(1.0, altura_total_px / altura_max_px))
        return (1.0 - h_norm) ** 1.25

    def atualizar_sombra_contato(self) -> None:
        """Posiciona e escala a sombra projetada no plano do chão, independente dos pés."""
        if self._shadow_np is None or self.model_np is None:
            return
        if getattr(self, "exit_pivot", None) is not None or self.model_np.isHidden():
            self._shadow_np.hide()
            return
        controller = getattr(self.showbase, "animation_controller", None)
        speaker = getattr(self, "music_speaker", None)
        dancing_stage = bool(
            controller
            and controller.state == AnimationState.DANCE
            and speaker
            and speaker.visibility > 0.1
            and not speaker.compact
            and controller.dance_motion.style != "breakdance"
            and speaker.jump_progress > 0.18
            and self._subida_palco.value > 0.15
        )
        intro_dissolve = (
            float(self._last_post_effect[1])
            if getattr(self, "_last_post_effect", None) is not None
            else 0.0
        )
        if dancing_stage or intro_dissolve > 0.72:
            self._last_shadow_sig = None
            self._shadow_np.hide()
            return

        dt_raw = float(getattr(controller, "delta_time", 1.0 / 60.0)) if controller else 1.0 / 60.0
        dt = max(1e-4, min(0.1, dt_raw if dt_raw > 0.0 else 1.0 / 60.0))
        units_z = float(self._view_height) / max(1.0, float(self.height))
        elevacao_z = (
            self._subida_profundidade
            * float(self._model_dimensions.z)
            * self._fit_scale
            * self._user_scale
        )
        anchor_scale = (
            self.model_anchor.getScale(self.showbase.render)
            if self.model_anchor is not None
            else Vec3(1.0, 1.0, 1.0)
        )
        peso_deitado, peso_sentado = self._pesos_pose_sombra(controller)
        fator_ar = self._alcance_aereo_sombra(
            controller, dt, units_z, anchor_scale, peso_deitado, peso_sentado
        )
        if fator_ar <= 0.06:
            self._last_shadow_sig = None
            self._shadow_np.hide()
            return
        if self._shadow_np.isHidden():
            self._shadow_np.show()
            self._last_shadow_sig = None

        cintura = self._rig_nodes.get("cintura") or self._rig_nodes.get("pelvis")
        if cintura is not None and not cintura.isEmpty():
            x_centro = float(cintura.getPos(self.showbase.render).x)
        else:
            x_centro = float(self.model_anchor.getX()) if self.model_anchor else 0.0
        peso_plano = max(peso_deitado, float(getattr(self, "_breakdance_chao_peso", 0.0)))
        if peso_plano > 0.05:
            limites = self.model_np.getTightBounds(self.showbase.render)
            if limites:
                x_bounds = (float(limites[0].x) + float(limites[1].x)) * 0.5
                x_centro = x_centro * (1.0 - peso_plano) + x_bounds * peso_plano

        canvas_origin = getattr(self.showbase, "_canvas_origin", None)
        if self._floor_screen_y is not None and canvas_origin is not None:
            floor_y_local = float(self._floor_screen_y) - float(canvas_origin[1])
            world_z_floor = (
                float(self._view_target_z)
                + (float(self.height) * 0.5 - floor_y_local) * units_z
                + elevacao_z
            )
        else:
            orig_anchor = getattr(self, "_intro_orig_anchor_pos", None)
            anchor_z = (
                float(orig_anchor.z)
                if orig_anchor is not None
                else (float(self.model_anchor.getZ()) if self.model_anchor else 0.0)
            )
            world_z_floor = anchor_z - float(self._model_radius_px) * units_z + elevacao_z

        sx = float(self._squash_pivot.getSx()) if self._squash_pivot is not None else 1.0
        sy = float(self._squash_pivot.getSy()) if self._squash_pivot is not None else 1.0
        yaw_deg = float(self._giro_corpo.angulo) + float(self._dance_stage_yaw.value)
        yaw_rad = math.radians(yaw_deg)
        dim_x = float(self._model_dimensions.x)
        dim_y = float(self._model_dimensions.y)
        dim_z = float(self._model_dimensions.z)
        dim_rot_x = math.hypot(dim_x * math.cos(yaw_rad), dim_y * math.sin(yaw_rad))
        dim_rot_y = math.hypot(dim_y * math.cos(yaw_rad), dim_x * math.sin(yaw_rad))
        dim_eff_x = dim_rot_x * (1.0 - peso_deitado) + max(dim_rot_x, dim_z * 0.92) * peso_deitado
        escala_x = float(self.model_np.getSx()) * float(anchor_scale.x)
        escala_y = float(self.model_np.getSy()) * min(1.25, float(anchor_scale.y))
        fator_sent_w = 1.0 + 0.12 * peso_sentado
        fator_sent_d = 1.0 + 0.34 * peso_sentado
        # Encolhimento suave sem colapsar a elipse para <2px antes do dither Bayer dissipar.
        fator_escala = 0.42 + 0.58 * fator_ar
        base_w = max(0.24, dim_eff_x * escala_x * 0.78) * sx * fator_escala * fator_sent_w
        base_d = (
            max(0.18, dim_rot_y * max(0.05, escala_y) * 0.72) * sy * fator_escala * fator_sent_d
        )
        z_min_view = float(self._view_target_z) - 0.5 * float(self._view_height)
        half_proj_z = 0.5 * base_d * abs(math.cos(math.radians(82.0))) + 3.0 * units_z
        z_sombra = max(world_z_floor - 0.008, z_min_view + half_proj_z)
        shadow_alpha = max(0.0, min(1.0, fator_ar * (1.0 - intro_dissolve * 0.95)))
        sig_sombra = (
            round(x_centro, 4),
            round(z_sombra, 4),
            round(base_w, 4),
            round(base_d, 4),
            round(shadow_alpha, 4),
        )
        if sig_sombra != getattr(self, "_last_shadow_sig", None):
            self._last_shadow_sig = sig_sombra
            self._shadow_np.setPos(x_centro, 0.04, z_sombra)
            self._shadow_np.setHpr(0.0, -82.0, 0.0)
            # CardMaker gera o cartão em XZ; sob setP(-82), o eixo Z local controla a profundidade.
            self._shadow_np.setScale(base_w, 1.0, base_d)
            self._shadow_np.setShaderInput("u_shadow_alpha", shadow_alpha)

    _atualizar_sombra_contato = atualizar_sombra_contato

    def _parametros_squash_stretch(self, controller) -> dict[str, Any]:
        estado = controller.state.value if controller.state else "idle"
        dragging = controller.state == AnimationState.DRAG
        dancing = controller.state == AnimationState.DANCE
        dance = controller.dance_motion if dancing else None
        reacao_dur = float(
            controller.REACTION_SECONDS.get(controller._reaction, 0.65)
            if getattr(controller, "_reaction", None) is not None
            else 0.65
        )
        sono_entrada = (
            suavizar_quintico(max(0.0, min(1.0, controller.state_time / 2.2)))
            if controller.state == AnimationState.SLEEP
            else 1.0
        )
        leg_p = getattr(controller.leg_motion, "pose", None)
        flexao_joelhos = (
            0.5 * (float(leg_p.left_knee) + float(leg_p.right_knee))
            if leg_p is not None
            else 0.0
        )
        pose_rig = getattr(getattr(controller, "rig", None), "current", None) or {}
        pitch_tronco = math.degrees(
            float(getattr(pose_rig.get("body"), "x", 0.0))
            + float(getattr(pose_rig.get("peitoral"), "x", 0.0))
        )
        return {
            "estado": estado,
            "respiracao": getattr(controller, "respiracao_valor", 0.0) or 0.0,
            "fase_locomocao": getattr(controller.leg_motion, "phase", 0.0),
            "run": controller.state == AnimationState.RUN,
            "impacto_tempo": (
                controller.state_time if controller.state == AnimationState.LAND else 0.0
            ),
            "impacto_duracao": 0.35,
            "arraste_velocidade": (
                getattr(controller.body_motion, "pointer_velocity", (0.0, 0.0))
                if dragging
                else (0.0, 0.0)
            ),
            "arraste_intensidade": (
                getattr(controller, "drag_intensity", 0.0) if dragging else 0.0
            ),
            "arraste_hanging": (
                float(getattr(controller.body_motion.snapshot, "hanging", 0.0))
                if dragging
                else 0.0
            ),
            "queda_velocidade": self._physics_velocity,
            "queda_tempo": (
                controller.state_time if controller.state == AnimationState.FALL else 0.0
            ),
            "sono_modo": getattr(controller, "modo_sono", "em_pe"),
            "sono_entrada": sono_entrada,
            "danca_fase_beat": ((dance.phase / math.tau) % 1.0) if dance else 0.0,
            "danca_intensidade": dance.strength if dance else 0.5,
            "danca_bass": dance.bass if dance else 0.0,
            "reacao_tempo": float(getattr(controller, "_reaction_time", 0.0)),
            "reacao_duracao": reacao_dur,
            "flexao_joelhos_graus": flexao_joelhos,
            "pitch_tronco_graus": pitch_tronco,
        }

    def _aplicar_squash_stretch(self, dt: float | None = None) -> None:
        """Aplica Squash & Stretch (princípio 1) no corpo inteiro, preservando volume."""
        if self._squash_pivot is None or self.model_np is None:
            return
        controller = getattr(self.showbase, "animation_controller", None)
        if controller is None:
            return
        alvo = squash_stretch_composto(**self._parametros_squash_stretch(controller))
        dt_eff = (
            float(dt)
            if dt is not None
            else float(getattr(controller, "delta_time", 1.0 / 60.0))
        )
        # Suavização exponencial elimina saltos/quicadas bruscas de 1 frame entre estados.
        estado = controller.state.value if controller.state else "idle"
        cena_ativa = bool(getattr(getattr(controller, "cena_idle_amostra", None), "ativa", False))
        vel = (
            22.0
            if estado in ("land", "hit", "poke", "click", "surprise")
            else (15.5 if cena_ativa else 11.5)
        )
        if dt_eff > 0.0:
            alpha = 1.0 - math.exp(-vel * min(dt_eff, 0.08))
            ax, ay, az = self._squash_atual
            sx = ax + (alvo.x - ax) * alpha
            sy = ay + (alvo.y - ay) * alpha
            sz = az + (alvo.z - az) * alpha
        else:
            sx, sy, sz = alvo.x, alvo.y, alvo.z
        self._squash_atual = (sx, sy, sz)

        ref_alvo = float(self._model_min_z) if self._is_grounded else 0.48
        if self._squash_ref_z is None or dt_eff <= 0.0:
            self._squash_ref_z = ref_alvo
        else:
            alpha_ref = 1.0 - math.exp(-16.0 * min(dt_eff, 0.08))
            self._squash_ref_z += (ref_alvo - self._squash_ref_z) * alpha_ref
        pivot_z = float(
            self._squash_pivot.getRelativePoint(
                self.model_np, Point3(0, 0, self._squash_ref_z)
            ).z
        )
        mat = (
            Mat4.translateMat(0.0, 0.0, -pivot_z)
            * Mat4.scaleMat(sx, sy, sz)
            * Mat4.translateMat(0.0, 0.0, pivot_z)
        )
        self._squash_pivot.setMat(mat)

    def _posicionar_sono_sentado(self, entrada: float) -> None:
        """Alinha quadril e calcanhares à linha exata do piso no modo sentado."""
        floor = self.music_speaker.floor_z
        pelvis = self._rig_nodes.get("pelvis")
        b_pelvis = pelvis.getTightBounds(self.model_np) if pelvis is not None else None
        z_apoio = float(b_pelvis[0].z) - 0.015 if b_pelvis else 0.34
        for nome_pe in ("left-feet", "right-feet"):
            no_pe = self._rig_nodes.get(nome_pe)
            b_pe = (
                no_pe.getTightBounds(self.model_np)
                if no_pe is not None and not no_pe.isEmpty()
                else None
            )
            if b_pe:
                z_apoio = min(z_apoio, float(b_pe[0].z))
        offset_sentado = floor - z_apoio
        offset_atual = (
            self.lower_body.ground_offset * (1.0 - entrada) + offset_sentado * entrada
        )
        self._suspension_pivot.setZ(offset_atual * self.model_np.getSz())

    def _posicionar_sono(self, modo: str, peso: float | None = None) -> bool:
        controller = getattr(self.showbase, "animation_controller", None)
        if peso is None:
            t_sono = float(getattr(controller, "state_time", 2.6)) if controller else 2.6
            entrada = suavizar_quintico(max(0.0, min(1.0, (t_sono - 0.15) / 1.85)))
        else:
            entrada = max(0.0, min(1.0, float(peso)))
        if modo == "deitado":
            ground = self.model_np.getTightBounds(self.model_anchor)[0].z
            self._suspension_pivot.setMat(self._giro_no_quadril(0, 0, 85.0 * entrada))
            moved = self.model_np.getTightBounds(self.model_anchor)[0].z
            self._suspension_pivot.setZ(
                self._suspension_pivot.getZ() + (ground - moved)
            )
            return True
        if modo == "sentado":
            self._posicionar_sono_sentado(entrada)
            return True
        return False

    @staticmethod
    def _adicionar_segmento_aro(tris, b0: int, b1: int) -> None:
        for p, q in ((0, 2), (2, 3), (3, 1), (1, 0)):
            tris.addVertices(b0 + p, b0 + q, b1 + q)
            tris.addVertices(b0 + p, b1 + q, b1 + p)

    @classmethod
    def _geom_aro_scifi(
        cls,
        nome: str,
        raio: float,
        espessura: float,
        profundidade: float,
        arcos: int = 3,
        cobertura: float = 0.72,
        segs_arco: int = 7,
    ):
        from panda3d.core import (
            Geom,
            GeomTriangles,
            GeomVertexData,
            GeomVertexFormat,
            GeomVertexWriter,
        )

        vdata = GeomVertexData(nome, GeomVertexFormat.getV3c4(), Geom.UHStatic)
        writer_v = GeomVertexWriter(vdata, "vertex")
        writer_c = GeomVertexWriter(vdata, "color")
        tris = GeomTriangles(Geom.UHStatic)
        r_in = max(0.004, raio - espessura * 0.5)
        r_out = raio + espessura * 0.5
        hz = profundidade * 0.5
        arco_passo = math.tau / max(1, arcos)
        arco_span = arco_passo * max(0.18, min(1.0, cobertura))
        fechado = cobertura >= 0.99
        v_idx = 0
        for a_i in range(max(1, arcos)):
            a_ini = a_i * arco_passo
            n_pts = segs_arco if fechado else segs_arco + 1
            for s_i in range(n_pts):
                ang = a_ini + (s_i / max(1, segs_arco)) * arco_span
                ca, sa = math.cos(ang), math.sin(ang)
                for r, dz in ((r_in, -hz), (r_in, hz), (r_out, -hz), (r_out, hz)):
                    writer_v.addData3(ca * r, sa * r, dz)
                    writer_c.addData4(1.0, 1.0, 1.0, 1.0)
            for s_i in range(segs_arco):
                nxt = (s_i + 1) % segs_arco if fechado else s_i + 1
                cls._adicionar_segmento_aro(tris, v_idx + s_i * 4, v_idx + nxt * 4)
            if not fechado:
                for cap_base in (v_idx, v_idx + segs_arco * 4):
                    tris.addVertices(cap_base, cap_base + 1, cap_base + 3)
                    tris.addVertices(cap_base, cap_base + 3, cap_base + 2)
            v_idx += n_pts * 4
        tris.closePrimitive()
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        return geom

    @staticmethod
    def _anexar_aro_fx(pivot_np, nome_node: str, geom):
        from panda3d.core import GeomNode

        gn = GeomNode(nome_node)
        gn.addGeom(geom)
        np = pivot_np.attachNewNode(gn)
        np.setLightOff(1)
        np.setShaderOff(1)
        np.setTwoSided(True)
        np.setCollideMask(0)
        np.hide()
        return np

    def _criar_argolas_energia_fx(self, ant_direita, ant_esquerda) -> None:
        """Mantém apenas as argolas físicas do modelo sem anéis/orbes adicionais."""
        del ant_direita, ant_esquerda
        self._argolas_fx = []

    @staticmethod
    def _atualizar_argola_fisica(
        item,
        argolas_ativas: bool,
        amostra,
        pulso_t: float,
        idx_arg: int,
        modo_musical: bool = False,
        beat_phase: float = 0.0,
        choque_ativo: bool = False,
        _cache: dict | None = None,
    ) -> None:
        np, pos_orig, esc_orig, centro, eixo, eh_outline = item
        chave_cache = (idx_arg, eh_outline)
        if eh_outline:
            if _cache is not None and _cache.get(chave_cache) == ("hide",):
                return
            if _cache is not None:
                _cache[chave_cache] = ("hide",)
            np.hide()
            return
        eh_sup = "sup" in np.getName() or abs(centro.z) > 0.086
        if not argolas_ativas and not modo_musical and not choque_ativo:
            # Levitação ambiente viva + brilho emissivo sutil pulsante nas argolas!
            fase_amb = pulso_t * 2.1 + idx_arg * 1.15
            dz_amb = math.sin(fase_amb) * (0.006 if eh_sup else -0.005)
            pulso_brilho = 0.5 + 0.5 * math.sin(pulso_t * 3.0 + idx_arg * 0.9)
            sig = ("amb", round(dz_amb, 4), round(pulso_brilho, 3))
            if _cache is not None and _cache.get(chave_cache) == sig:
                return
            if _cache is not None:
                _cache[chave_cache] = sig
            np.show()
            np.setPos(pos_orig + eixo * dz_amb)
            np.setScale(esc_orig)
            # Modo emissivo leve (setLightOff) faz as argolas brilharem de verdade!
            np.setLightOff(1)
            np.setColorScale(
                1.18 + 0.28 * pulso_brilho,
                1.08 + 0.24 * pulso_brilho,
                0.78 + 0.20 * pulso_brilho,
                1.0,
            )
            return
        if argolas_ativas:
            dz = amostra.deslocamento_argola_sup if eh_sup else amostra.deslocamento_argola_inf
            s = max(0.01, amostra.escala_argolas)
            brilho = max(0.35, float(amostra.brilho_argolas))
        elif choque_ativo:
            fase_ch = pulso_t * 14.0 + idx_arg * 1.3
            dz = math.sin(fase_ch) * (0.018 if eh_sup else -0.016)
            s = 1.0 + 0.14 * abs(math.sin(fase_ch))
            brilho = 1.0
        else:
            # No modo música, move em direções opostas e pulsa forte na batida.
            onda = math.sin(beat_phase)
            mag = (abs(onda) ** 0.75) * ((0.032 if eh_sup else -0.040) if onda >= 0.0 else (-0.014 if eh_sup else 0.014))
            dz = mag
            beat_peak = max(0.0, math.sin(beat_phase)) ** 4
            s = 1.0 + 0.14 * beat_peak
            brilho = 0.25 + beat_peak * 0.95
        flash = bool(choque_ativo and (int(pulso_t * 12.0) + idx_arg) % 2 == 1)
        sig = ("act", round(dz, 4), round(s, 4), round(brilho, 3), flash)
        if _cache is not None and _cache.get(chave_cache) == sig:
            return
        if _cache is not None:
            _cache[chave_cache] = sig
        np.setPos(centro + (pos_orig - centro) * s + eixo * dz)
        np.setScale(esc_orig * s)
        (np.hide if s < 0.05 else np.show)()
        if brilho > 0.05:
            np.setLightOff(1)
            if flash:
                # Flash ciano elétrico estilo anime no pico do choque!
                np.setColorScale(0.65, 1.85, 2.10, 1.0)
            else:
                np.setColorScale(
                    1.25 + 0.95 * brilho,
                    1.10 + 0.85 * brilho,
                    0.45 + 0.55 * brilho,
                    1.0,
                )
        else:
            np.clearLight()
            np.clearColorScale()

    @staticmethod
    def _atualizar_item_halo_rgb(
        registro, argolas_ativas: bool, amostra, pulso_t: float, choque: bool, brilho_alvo: float
    ) -> None:
        eh_direita, eixo, ancora, pivot_np, halo_np, halo_in_np, orbe_a, orbe_b = registro
        nos = (halo_np, halo_in_np, orbe_a, orbe_b)
        if brilho_alvo <= 0.01:
            for no in nos:
                no.hide()
            return
        for no in nos:
            no.show()
        fase = pulso_t * (11.0 if choque else 5.2) + (0.0 if eh_direita else math.pi * 0.5)
        dz_fx = (
            (amostra.deslocamento_argola_sup + amostra.deslocamento_argola_inf) * 0.45
            if argolas_ativas
            else 0.008 * math.sin(fase)
        )
        pivot_np.setPos(ancora + eixo * dz_fx)
        sinal = 1.0 if eh_direita else -1.0
        ganho = min(1.0, max(0.0, brilho_alvo / 0.15))
        shimmer = 0.5 + 0.5 * math.sin(fase * 2.1)
        flare = 1.25 if choque else 1.0

        halo_np.setHpr(math.degrees(fase * 0.75) * sinal, 12.0 * math.sin(fase * 0.5), 0.0)
        halo_np.setScale((0.92 + 0.22 * brilho_alvo + (0.14 * math.sin(fase * 2.0) if choque else 0.05 * math.sin(fase))) * flare)
        halo_np.setColorScale(
            1.0 * ganho,
            (0.76 + 0.14 * shimmer) * ganho,
            (0.12 + 0.14 * shimmer) * ganho,
            0.90 * ganho,
        )

        halo_in_np.setPos(0.0, 0.0, 0.006 * math.sin(fase * 1.3))
        halo_in_np.setHpr(-math.degrees(fase * 1.15) * sinal, -14.0 * math.cos(fase * 0.6), 10.0 * math.sin(fase * 0.4))
        halo_in_np.setScale((0.90 + 0.18 * brilho_alvo - 0.04 * math.sin(fase * 1.4)) * flare)
        halo_in_np.setColorScale(
            1.0 * ganho,
            (0.94 + 0.06 * shimmer) * ganho,
            (0.42 + 0.26 * shimmer) * ganho,
            0.96 * ganho,
        )

        r_orb = 0.066 * (0.94 + 0.16 * brilho_alvo)
        for orb, escala_r, vel_f, dz_o, g_col, b_col, roll_o in (
            (orbe_a, 1.0, 1.0, 0.005 * math.sin(fase * 2.0), 0.94, 0.34, 35.0),
            (orbe_b, -0.78, 1.35, 0.011 * math.cos(fase * 1.8), 0.74, 0.12, -25.0),
        ):
            orb.setPos(r_orb * escala_r * math.cos(fase * vel_f), r_orb * escala_r * math.sin(fase * vel_f), dz_o)
            orb.setHpr(math.degrees(fase * vel_f) * (1.0 if escala_r > 0 else -1.0), roll_o, 0.0)
            orb.setScale(0.86 + 0.28 * brilho_alvo)
            orb.setColorScale(1.0 * ganho, g_col * ganho, b_col * ganho, 1.0)

    def _atualizar_efeitos_e_argolas(self, dt: float, motion, grounded: bool) -> None:
        ctrl = getattr(self.showbase, "animation_controller", None)
        if ctrl is None or self._lego_snapshot:
            return
        amostra = getattr(ctrl, "cena_idle_amostra", None)
        argolas_ativas = bool(
            amostra is not None and amostra.ativa and amostra.nome == "argolas_antena"
        )
        pulso_t = float(getattr(ctrl, "clock", 0.0))
        dancing = bool(ctrl.state == AnimationState.DANCE)
        choque = bool(argolas_ativas and getattr(amostra, "choque_argolas", False))
        cena_musical = bool(
            amostra is not None
            and amostra.ativa
            and amostra.nome in ("escutar_fone", "batida_guardada", "groove_um_pe", "checar_walkman")
        )
        modo_musical = dancing or cena_musical
        beat_phase = float(getattr(ctrl.dance_motion, "phase", pulso_t * 4.5)) if dancing else pulso_t * 4.5
        aviso_antena = float(getattr(self.tentacle_director, "aviso_antena_tempo", 0.0)) if self.tentacle_director else 0.0
        estouro_fone = bool(amostra is not None and amostra.ativa and getattr(amostra, "estouro_fone", False))
        choque_eletrico = bool(choque or aviso_antena > 0.02 or estouro_fone)
        argola_cache = getattr(self, "_argola_cache", None)
        if argola_cache is None:
            argola_cache = {}
            self._argola_cache = argola_cache
        for idx_arg, item in enumerate(getattr(self, "_argolas_antena", ())):
            self._atualizar_argola_fisica(
                item,
                argolas_ativas,
                amostra,
                pulso_t,
                idx_arg,
                modo_musical=modo_musical,
                beat_phase=beat_phase,
                choque_ativo=choque_eletrico,
                _cache=argola_cache,
            )

        brilho_desejado = (
            float(amostra.brilho_argolas)
            if argolas_ativas
            else (0.72 if dancing else (0.58 if cena_musical else 0.0))
        )
        brilho_atual = getattr(self, "_brilho_halo_atual", 0.0)
        brilho_atual += (brilho_desejado - brilho_atual) * min(1.0, dt * 8.0)
        self._brilho_halo_atual = brilho_atual
        brilho_alvo = brilho_atual
        for registro in getattr(self, "_argolas_fx", ()):
            self._atualizar_item_halo_rgb(registro, argolas_ativas, amostra, pulso_t, choque, brilho_alvo)

        # Atualiza relógio e reatividade dos shaders de estilo.
        self._filter_clock += max(0.0, min(0.05, float(dt)))
        filtro_atual = getattr(self, "_visual_filter", "blockbench")
        self._atualizar_reatividade_filtro(dt, filtro_atual, ctrl, motion, grounded)

        params = None
        # Efeitos Street-Punk / Presets desenhados à mão (ancorados anatomicamente ao rig).
        efeitos_street = getattr(self, "efeitos_street", None)
        if efeitos_street is not None:
            if self._vfx_enabled:
                params = self._coletar_parametros_efeitos(ctrl, motion, amostra, grounded)
                efeitos_street.atualizar(dt, params)
            else:
                efeitos_street.limpar()
        self._atualizar_xray_street(filtro_atual, efeitos_street)

        if self._choque_antenas_3d is not None:
            from sejoga.render.vfx import EMISSORES_POR_ESTILO

            choque_migrado = "choque" in EMISSORES_POR_ESTILO.get(
                getattr(self, "_visual_filter", "padrao"), {}
            )
            if self._vfx_enabled and not choque_migrado:
                if params is None:
                    params = self._coletar_parametros_efeitos(ctrl, motion, amostra, grounded)
                aviso_val = float(params["aviso_antena"])
                permitir_ponte = bool(
                    params["choque_argolas"]
                    or params["estouro_fone"]
                    or aviso_val > 0.16
                )
                self._choque_antenas_3d.atualizar(
                    dt,
                    aviso_antena=aviso_val,
                    choque_argolas=bool(
                        params["choque_argolas"]
                        or params["estouro_fone"]
                    ),
                    permitir_ponte=permitir_ponte,
                )
            else:
                self._choque_antenas_3d.ocultar()

    def _atualizar_reatividade_filtro(
        self, dt: float, filtro_atual: str, ctrl, motion, grounded: bool
    ) -> None:
        vel = getattr(ctrl, "_last_velocity", (0.0, 0.0)) if ctrl else (0.0, 0.0)
        speed = min(1.0, math.hypot(float(vel[0]), float(vel[1])) / 900.0)
        impact = min(1.0, float(getattr(motion, "impact", 0.0) or 0.0))
        est_val = str(ctrl.state.value if (ctrl and hasattr(ctrl.state, "value")) else "")
        reac = getattr(ctrl, "_reaction", None) if ctrl else None
        drama = (
            1.0
            if est_val in ("angry", "surprise", "celebrate", "teimosia")
            or reac in (AnimationState.SURPRISE, AnimationState.CELEBRATE, AnimationState.TEIMOSIA)
            else (0.35 if est_val == "dance" else 0.0)
        )
        airborne = 0.0 if grounded else 1.0
        if self._pbr_pipeline is not None:
            quad = self._pbr_pipeline._post_process_quad
            if filtro_atual in ("spiderverse", "street", "holograma", "anime"):
                quad.setShaderInput("u_filter_time", self._filter_clock)
            quad.setShaderInput("u_filter_fx", (speed, impact, drama, airborne))
        if self.outline_np is not None and filtro_atual in ("spiderverse", "street"):
            self.outline_np.setShaderInput("u_sketch_time", self._filter_clock)
        if filtro_atual == "spiderverse":
            intervalo = 1.0 / (24.0 if (speed > 0.45 or impact > 0.20) else 12.0)
            self._sv_step_acc += max(0.0, float(dt))
            if self._sv_step_acc >= intervalo:
                self._sv_step_acc %= intervalo
                self._sv_allow_pose_step = True
            else:
                self._sv_allow_pose_step = False
        else:
            self._sv_allow_pose_step = True

    def _limpar_xray_street(self) -> None:
        if self._fnf_skeleton is not None:
            self._fnf_skeleton.atualizar(0.0, self.showbase.render)
        if self.model_np is not None:
            self.model_np.setShaderInput("u_fnf_shade", 0.006)
        self._street_xray_ativo = False

    def _atualizar_xray_street(self, filtro_atual: str, efeitos_street) -> None:
        power = (
            efeitos_street.xray_flash_intensidade()
            if (filtro_atual == "street" and self._vfx_enabled and efeitos_street is not None)
            else 0.0
        )
        if power > 0.01 and self.model_np is not None:
            if self._fnf_skeleton is None:
                from sejoga.render.esqueleto_fnf import EsqueletoFnf

                self._fnf_skeleton = EsqueletoFnf(self.showbase.render, self._rig_nodes)
            self._fnf_skeleton.atualizar(power, self.showbase.render)
            self.model_np.setShaderInput("u_fnf_shade", 0.008 + 0.055 * power)
            self._street_xray_ativo = True
        elif getattr(self, "_street_xray_ativo", False):
            self._limpar_xray_street()

    def _coletar_caixas_som_pos(self, estado: str) -> tuple[Vec3, ...]:
        speaker = getattr(self, "music_speaker", None)
        if estado != "dance" or speaker is None or speaker.root.isHidden():
            return ()
        referencia = (
            self.efeitos_street.root
            if getattr(self, "efeitos_street", None) is not None
            else self.model_anchor
        )
        if referencia is None:
            return ()
        caixas_pos: list[Vec3] = []
        for box, emissor in zip(speaker.boxes, speaker.emissores_graves, strict=True):
            if box.isHidden():
                continue
            p = emissor.getPos(referencia)
            caixas_pos.append(Vec3(p.x, p.y - 0.12, p.z))
        return tuple(sorted(caixas_pos, key=lambda p: p.x))

    def _coletar_parametros_efeitos(
        self, ctrl, motion, amostra, grounded: bool
    ) -> dict[str, Any]:
        """Consolida os gatilhos dos efeitos visuais 2D pixelados E1-E7 no frame."""
        estado = str(ctrl.state.value if hasattr(ctrl.state, "value") else ctrl.state)
        vel = getattr(ctrl, "_last_velocity", (0.0, 0.0))
        diretor = getattr(self, "tentacle_director", None)
        aviso = getattr(diretor, "aviso_antena_tempo", 0.0) if diretor else 0.0
        heavy_land = bool(getattr(ctrl, "_land_heavy", False))
        caixas_pos = self._coletar_caixas_som_pos(estado)
        gosma = bool(
            (diretor is not None and (diretor.burst or diretor.swallowing))
            or (estado == "teimosia" and getattr(ctrl, "_teimosia_fase", "") == "cospe")
        )
        return {
            "estado": estado,
            "tempo_estado": getattr(ctrl, "state_time", 0.0),
            "grounded": grounded,
            "velocidade": vel,
            "medo": bool(getattr(motion, "surprise_jolt", 0.0) > 0.65),
            "tremor": bool(
                getattr(motion, "surprise_jolt", 0.0) > 0.55
                or estado == "surprise"
            ),
            "susto": bool(
                ctrl._reaction == AnimationState.SURPRISE
                or getattr(motion, "surprise_jolt", 0.0) > 0.78
                or (
                    ctrl._reaction in (AnimationState.POKE, AnimationState.DOUBLE_CLICK)
                    and getattr(ctrl, "_reaction_time", 1.0) < 0.22
                )
            ),
            "raiva": bool(
                (ctrl._reaction == AnimationState.TEIMOSIA or estado == "teimosia")
                and getattr(ctrl, "_teimosia_fase", "") in ("repreensao", "bote")
            ),
            "tontura": bool(
                getattr(ctrl, "tontura", 0.0) > 0.12
                or (
                    ctrl._reaction == AnimationState.LAND
                    and heavy_land
                    and getattr(ctrl, "_reaction_time", 0.0) < 0.85
                )
            ),
            "sono": bool(ctrl.state == AnimationState.SLEEP),
            "aviso_antena": aviso,
            "estouro_fone": bool(amostra and amostra.estouro_fone),
            "choque_argolas": bool(amostra and amostra.choque_argolas),
            "acento_danca": bool(
                ctrl.state == AnimationState.DANCE
                and getattr(ctrl.dance_motion, "acento", 0.0) > 0.36
            ),
            "dancando": bool(ctrl.state == AnimationState.DANCE),
            "andando": bool(grounded and estado in ("walk", "run")),
            "correndo": bool(grounded and estado == "run"),
            "forca_impacto": max(
                1.45 if heavy_land else 0.9, float(getattr(motion, "impact", 0.0))
            ),
            "deslizando": bool(
                estado == "virtual_insanity"
                or (grounded and estado not in ("walk", "run") and abs(vel[0]) > 500.0)
            ),
            "comemorando": bool(ctrl._reaction == AnimationState.CELEBRATE or estado == "celebrate"),
            "som_fones": bool(
                estado == "dance"
                or (
                    amostra is not None
                    and amostra.ativa
                    and amostra.nome in ("escutar_fone", "batida_guardada", "groove_um_pe", "checar_walkman")
                )
            ),
            "caixas_som_pos": caixas_pos,
            "gosma_evento": gosma,
            "carinho": bool(
                ctrl._reaction == AnimationState.PET or estado == "pet"
            ),
            "dragging": bool(getattr(self.showbase, "_drag_active", False)),
            "humor": str(getattr(ctrl, "humor", "") or ""),
            "cena_nome": str(amostra.nome) if (amostra is not None and amostra.ativa) else "",
            "cena_tempo": float(getattr(ctrl, "_cena_idle_tempo", 0.0))
            if (amostra is not None and amostra.ativa)
            else 0.0,
        }

    def projetar_ponto_grupo_cliente(
        self, grupo: str, offset_local: tuple[float, float, float] = (0.0, 0.0, 0.0)
    ) -> tuple[float, float] | None:
        """Projeta um ponto local de ``grupo`` para pixels ``(x, y)`` da área cliente."""
        if not self.model_np:
            return None
        no = self._rig_nodes.get(grupo) if grupo != "__model__" else self.model_np
        if no is None or no.isEmpty():
            return None
        wp = self.showbase.render.getRelativePoint(no, Point3(*offset_local))
        vw = max(1e-4, float(self._view_width))
        vh = max(1e-4, float(self._view_height))
        cx = float(self.width) * (0.5 + float(wp.x) / vw)
        cy = float(self.height) * (0.5 - (float(wp.z) - float(self._view_target_z)) / vh)
        return (cx, cy)

    def ponto_local_no_grupo(self, grupo: str, ponto_modelo: Vec3) -> Vec3 | None:
        """Converte um ponto no espaço de ``model_np`` para o nó local do grupo dado."""
        if not self.model_np or grupo not in self._rig_nodes:
            return None
        return Vec3(self._rig_nodes[grupo].getRelativePoint(self.model_np, ponto_modelo))

    def apply_body_motion(  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        self,
        motion,
        grab_point=None,
        *,
        grounded=True,
        dragging=False,
        direcao_olhar=0.0,
        angulo_giro_pedido=None,
        grab_part="body",
        drag_direction=None,
        drag_intensity=0.0,
        grab_anchor_local=None,
        grab_node_name=None,
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
        self._is_grounded = bool(grounded and not dragging)
        controller = getattr(self.showbase, "animation_controller", None)
        dt_raw = float(getattr(controller, "delta_time", 1.0 / 60.0))
        dt = max(1e-4, min(0.1, dt_raw if dt_raw > 0.0 else 1.0 / 60.0))
        atenuacao_flex = 1.0
        if controller is not None:
            st_atual = getattr(controller, "state", None)
            if (
                st_atual == AnimationState.GOKU_TELEPORT
                or (st_atual == AnimationState.SLEEP and getattr(controller, "modo_sono", "") == "deitado")
                or getattr(controller, "raiz_quat_ativa", None) is not None
            ):
                atenuacao_flex = 0.0
        self._atualizar_efeitos_e_argolas(dt, motion, grounded)
        self._update_outline_breath(dt, motion)
        self.flexible_rig.update(
            dt,
            motion,
            grounded=grounded,
            dragging=dragging,
            atenuacao=atenuacao_flex,
        )
        if self._suspension_pivot is None:
            self._suspension_pivot = self.model_anchor.attachNewNode("suspension-pivot")
            self._squash_pivot = self._suspension_pivot.attachNewNode("squash-pivot")
            # body_facing fica ENTRE o pivô de squash e a malha: gira o corpo
            # sem tocar no setH(180) base (model_np) nem no tilt de voo.
            self._body_facing = self._squash_pivot.attachNewNode("body-facing")
            self.model_np.reparentTo(self._body_facing)
            self.outline_np.reparentTo(self._body_facing)
        self._suspension_pivot.setMat(Mat4.identMat())
        if (
            angulo_giro_pedido is None and controller
            and controller.state == AnimationState.SLEEP and controller.modo_sono == "sentado"
        ):
            angulo_giro_pedido = -22.0
        self._aplicar_giro_corpo(dt, direcao_olhar, angulo_giro_pedido, dragging)
        speaker = self.music_speaker
        dancing = bool(controller and controller.state == AnimationState.DANCE)
        style = controller.dance_motion.style if controller else "head_bob"
        eh_emote_clipe = bool(
            dancing and carregar_clipe_emote(style) is not None
        )
        yaw = speaker.turn if (dancing and not eh_emote_clipe) else 0.0
        self._dance_stage_yaw.update(dt, yaw)
        scale = self.model_np.getSz()
        if eh_emote_clipe and grounded and not dragging:
            dx, dy = controller.dance_motion.deslocamento_emote
            self._deslocamento_danca.set(-dx, -dy, 0)
        elif grounded and not dragging:
            self._deslocamento_danca *= max(0.0, 1 - dt * 12)
        else:
            self._deslocamento_danca.set(0, 0, 0)
        if grounded and not dragging:
            self._suspension_pivot.setPos(self._deslocamento_danca * scale)
            dz_extra = 0.0
            if eh_emote_clipe:
                dz_extra += getattr(controller.dance_motion, "dz_pelvis_emote", 0.0)
            elif controller is not None:
                dz_extra += getattr(controller, "dz_clipe_ativo", 0.0)
            if (
                controller
                and getattr(controller, "cena_idle_amostra", None) is not None
                and controller.cena_idle_amostra.ativa
            ):
                dz_extra += controller.cena_idle_amostra.deslocamento_z
            if (
                controller
                and controller.state == AnimationState.CELEBRATE
                and not getattr(controller, "acao_clipe_ativa", None)
            ):
                u_cel = min(1.0, max(0.0, float(getattr(controller, "_reaction_time", 0.0)) / 2.0))
                if 0.18 <= u_cel <= 0.64:
                    dz_extra += 0.17 * math.sin(((u_cel - 0.18) / 0.46) * math.pi)
            if (
                controller
                and controller.state == AnimationState.LAND
                and getattr(controller, "_land_heavy", False)
                and not getattr(controller, "acao_clipe_ativa", None)
            ):
                t_land = controller._reaction_time
                if t_land < 0.14:
                    u_sent = t_land / 0.14
                elif t_land < 0.95:
                    u_sent = 1.0
                else:
                    u_sent = max(0.0, 1.0 - (t_land - 0.95) / 0.45)
                dz_extra -= 0.13 * u_sent
            alpha_dz = 1.0 - math.exp(-22.0 * dt)
            self._dz_extra_atual += (dz_extra - self._dz_extra_atual) * alpha_dz
            tilt_rad = float(getattr(self, "_raiz_tilt_rad", 0.0))
            peso_solo = max(0.0, 1.0 - min(1.0, tilt_rad / 0.60))
            base_solo = self.lower_body.ground_offset * peso_solo
            self._suspension_pivot.setZ((base_solo + self._dz_extra_atual) * scale)
        else:
            self._dz_extra_atual += (0.0 - self._dz_extra_atual) * (1.0 - math.exp(-18.0 * dt))
        subir = (
            dancing
            and not dragging
            and not speaker.compact
            and style != "breakdance"
            and not eh_emote_clipe
        )
        self._subida_palco.update(dt, float(subir))
        self._assento_palco.update(dt, float(subir and style == "head_bob"))
        if not dragging and self._subida_palco.value > 0.005 and not speaker.compact:
            self._posicionar_no_palco(speaker, subir)

        em_breakdance = bool(
            not dragging
            and grounded
            and controller
            and controller.state == AnimationState.DANCE
            and controller.dance_motion.style == "breakdance"
            and not eh_emote_clipe
            and speaker.jump_progress >= 1.0
            and self._subida_palco.value < 0.01
        )
        if em_breakdance:
            dance = controller.dance_motion
            self._ultimo_breakdance_pose = (
                float(dance.floor_spin),
                float(_danca.FLOOR_ROLL_GRAUS * dance.floor_amount),
            )
            self._breakdance_chao_peso += (1.0 - self._breakdance_chao_peso) * (
                1.0 - math.exp(-24.0 * dt)
            )
        else:
            vel_break = 18.0 if (dragging or not grounded) else 9.0
            self._breakdance_chao_peso += (0.0 - self._breakdance_chao_peso) * (
                1.0 - math.exp(-vel_break * dt)
            )
            if self._breakdance_chao_peso < 0.005:
                self._breakdance_chao_peso = 0.0

        em_sono = bool(not dragging and controller and controller.state == AnimationState.SLEEP)
        modo_sono = getattr(controller, "modo_sono", "") if controller else ""
        t_sono = float(getattr(controller, "state_time", 0.0)) if controller else 0.0
        ent_sono = suavizar_quintico(max(0.0, min(1.0, (t_sono - 0.15) / 1.85)))
        em_sit = bool(
            not dragging
            and grounded
            and controller
            and getattr(controller, "state", None) is not None
            and controller.state.value == "sit"
        )
        alvo_deitado = ent_sono if (em_sono and modo_sono == "deitado") else 0.0
        alvo_sentado = (
            ent_sono
            if (em_sono and modo_sono == "sentado")
            else (suavizar_quintico(max(0.0, min(1.0, t_sono / 0.45))) if em_sit else 0.0)
        )
        taxa_deitado = 24.0 if alvo_deitado > 0.0 else (16.0 if (dragging or not grounded) else 7.5)
        taxa_sentado = 16.0 if (dragging or not grounded) else 8.5
        self._sono_deitado_peso += (alvo_deitado - self._sono_deitado_peso) * (
            1.0 - math.exp(-taxa_deitado * dt)
        )
        self._sono_sentado_peso += (alvo_sentado - self._sono_sentado_peso) * (
            1.0 - math.exp(-taxa_sentado * dt)
        )
        if self._sono_deitado_peso < 0.003 and alvo_deitado == 0.0:
            self._sono_deitado_peso = 0.0
        if self._sono_sentado_peso < 0.003 and alvo_sentado == 0.0:
            self._sono_sentado_peso = 0.0

        if not dragging and grounded and self._breakdance_chao_peso > 0.005:
            spin_bd, roll_bd = self._ultimo_breakdance_pose
            ground = self.model_np.getTightBounds(self.model_anchor)[0].z
            # shortcut: mão não fica fixa no cenário durante o giro; upgrade quando
            # houver contatos de cena (guia 7.1).
            self._suspension_pivot.setMat(
                self._giro_no_quadril(spin_bd, 0.0, roll_bd * self._breakdance_chao_peso)
            )
            moved = self.model_np.getTightBounds(self.model_anchor)[0].z
            self._suspension_pivot.setZ(
                self._suspension_pivot.getZ() + (ground - moved)
            )
            self._aplicar_squash_stretch(dt)
            if self._floor_screen_y is None:
                self.atualizar_sombra_contato()
            return
        if (
            not dragging
            and grounded
            and self._sono_deitado_peso > 0.005
            and self._posicionar_sono("deitado", self._sono_deitado_peso)
        ):
            self._aplicar_squash_stretch(dt)
            if self._floor_screen_y is None:
                self.atualizar_sombra_contato()
            return
        if (
            not dragging
            and grounded
            and self._sono_sentado_peso > 0.005
            and self._posicionar_sono("sentado", self._sono_sentado_peso)
        ):
            self._aplicar_squash_stretch(dt)
            if self._floor_screen_y is None:
                self.atualizar_sombra_contato()
            return
        if dragging and motion.hanging > _tune.PENDURADO_LIMIAR:
            peso_susp = suavizar_quintico(
                max(0.0, min(1.0, (motion.hanging - _tune.PENDURADO_LIMIAR) / 0.16))
            )
            point_orig = Vec3(grab_point) if grab_point is not None else Vec3(0, 0, 0.6)
            pivot_orig = self._suspension_pivot.getRelativePoint(self.model_np, point_orig)
            # Ao segurar por um braço, acompanha o ponto atual no nó articulado do braço
            # para que a mão/braço fique ancorado ao mouse enquanto o tronco pende abaixo.
            pivot_atual = pivot_orig
            if grab_part in ("right-arm", "left-arm"):
                no_nome = grab_node_name or grab_part
                no_pega = self._rig_nodes.get(no_nome) or self._rig_nodes.get(grab_part)
                if no_pega is not None and grab_anchor_local is not None:
                    p_din = self._suspension_pivot.getRelativePoint(no_pega, Vec3(grab_anchor_local))
                    peso_din = suavizar_quintico(min(1.0, max(0.0, motion.hanging)))
                    pivot_atual = pivot_orig + (p_din - pivot_orig) * (peso_din * peso_susp)
            rotation = self._rotacao_no_quadro_de_autoria(
                motion.yaw * peso_susp,
                motion.pitch * peso_susp,
                motion.roll * peso_susp,
            )
            # Mantém o ponto atual da pega sobre ``pivot_orig`` (posição do mouse no clique)
            # com leve afundamento gravitacional para transmitir peso físico real.
            peso_queda_z = -0.045 * scale * min(1.0, max(0.0, motion.hanging)) * peso_susp
            self._suspension_pivot.setMat(
                Mat4.translateMat(-pivot_atual)
                * rotation
                * Mat4.translateMat(pivot_orig + Vec3(0.0, 0.0, peso_queda_z))
            )
            self._aplicar_squash_stretch(dt)
            if self._floor_screen_y is None:
                self.atualizar_sombra_contato()
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
            self._aplicar_squash_stretch(dt)
            if self._floor_screen_y is None:
                self.atualizar_sombra_contato()
            return
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
        self._aplicar_squash_stretch(dt)
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
        if self._floor_screen_y is None:
            self.atualizar_sombra_contato()

    def _posicionar_no_palco(self, speaker, dancing):
        """Segue o arco até o tampo e alinha o apoio com a geometria."""
        if getattr(speaker, "compact", False) or getattr(speaker, "seat", None) is None:
            return
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
        origem_palco = self.model_anchor.getRelativePoint(speaker.root, Point3(0))
        diferenca = origem_palco - self.model_np.getPos()
        self._suspension_pivot.setPos(
            (diferenca.x + apoio_x * scale) * blend,
            (diferenca.y + profundidade * scale) * blend,
            self._suspension_pivot.getZ() * (1 - blend)
            + (diferenca.z * blend) + (altura + arco) * scale,
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

    def _aplicar_rotacao_raiz_clipe(
        self, dt: float, quat_raiz, pedido, controller
    ) -> None:
        qw, qx, qy, qz = quat_raiz
        # ``node90`` interno gira o rig em -180° ao redor de Z dentro de ``model_np``;
        # conjugar por Rz(180°) alinha a inclinação ao eixo real de cabeça e braços.
        q = Quat(qw, -qx, -qy, qz)
        q.normalize()
        peso_quat = (
            max(0.0, min(1.0, controller.dance_motion.style_beats))
            if controller.state == AnimationState.DANCE
            else max(0.0, min(1.0, getattr(controller, "acao_clipe_tempo", 1.0) / 0.28))
        )
        if peso_quat < 1.0:
            q_prev = getattr(self, "_ultimo_quat_raiz", None)
            peso_prev = float(getattr(self, "_peso_saida_quat", 0.0))
            q_ref = (
                Quat(q_prev)
                if (q_prev is not None and peso_prev > 0.01)
                else Quat.identQuat()
            )
            if q.dot(q_ref) < 0.0:
                q = -q
            q = q_ref * (1.0 - peso_quat) + q * peso_quat
            q.normalize()
        self._ultimo_quat_raiz = Quat(q)
        self._peso_saida_quat = 1.0
        self._giro_corpo.update(
            dt, direcao_olhar=0.0, angulo_pedido=pedido, permitir_costas=True
        )
        pivot = self._body_facing.getRelativePoint(self.model_np, Point3(0, 0, 0.44))
        rotacao = Mat4()
        q.extractToMatrix(rotacao)
        up_z = max(-1.0, min(1.0, rotacao.getRow3(2).z))
        self._raiz_tilt_rad = math.acos(up_z)
        self._body_facing.setMat(
            Mat4.translateMat(-pivot) * rotacao * Mat4.translateMat(pivot)
        )

    def _aplicar_saida_quat_raiz(self, dt: float, angulo: float, pivot: Point3, dragging: bool) -> bool:
        """Slerp suave de saída ao encerrar clipe com rotação 3D de raiz."""
        q_ant_raw = getattr(self, "_ultimo_quat_raiz", None)
        peso_saida = float(getattr(self, "_peso_saida_quat", 0.0))
        if q_ant_raw is None or peso_saida <= 0.005:
            return False
        taxa_saida = 1.0 / 0.14 if dragging else 1.0 / 0.28
        peso_saida = max(0.0, peso_saida - dt * taxa_saida)
        self._peso_saida_quat = peso_saida
        u_q = suavizar_quintico(peso_saida)
        q_base = (
            TransformState.makeHpr(Vec3(angulo, 0.0, 0.0)).getQuat()
            if abs(angulo) >= 0.01
            else Quat.identQuat()
        )
        q_ant = Quat(q_ant_raw)
        if q_ant.dot(q_base) < 0.0:
            q_ant = -q_ant
        q_mix = q_base * (1.0 - u_q) + q_ant * u_q
        q_mix.normalize()
        rotacao = Mat4()
        q_mix.extractToMatrix(rotacao)
        up_z = max(-1.0, min(1.0, rotacao.getRow3(2).z))
        self._raiz_tilt_rad = math.acos(up_z)
        self._body_facing.setMat(
            Mat4.translateMat(-pivot) * rotacao * Mat4.translateMat(pivot)
        )
        if peso_saida <= 0.005:
            self._ultimo_quat_raiz = None
            self._raiz_tilt_rad = 0.0
        return True

    def _aplicar_giro_corpo(self, dt, direcao_olhar, angulo_pedido, dragging):
        """Aplica o GIRO DE CORPO LIMITADO ao nó dedicado ``body_facing``.

        O giro é suavizado e clampado em ``GiroCorpo`` (até ~±90°). Gira em
        torno do eixo vertical pelo centro do corpo (mesma estratégia do
        ``_dance_stage_yaw``), para o mascote virar de lado NO LUGAR, sem
        orbitar nem sair do envelope da janela dinâmica. Durante o arraste o
        giro relaxa para 0: o arraste já reorienta o corpo pelo pivô de grip.
        """
        if self._body_facing is None:
            return
        olhar = 0.0 if dragging else direcao_olhar
        pedido = None if dragging else angulo_pedido
        controller = getattr(self.showbase, "animation_controller", None)
        quat_raiz = None
        if (
            not dragging
            and controller is not None
            and controller.state == AnimationState.DANCE
        ):
            quat_raiz = getattr(controller.dance_motion, "raiz_quat_emote", None)
        if quat_raiz is None and controller is not None:
            quat_raiz = getattr(controller, "raiz_quat_ativa", None)
        if quat_raiz is not None:
            self._aplicar_rotacao_raiz_clipe(dt, quat_raiz, pedido, controller)
            return
        permitir_costas = bool(
            not dragging and getattr(controller, "permitir_giro_costas", False)
        )
        angulo = self._giro_corpo.update(
            dt,
            direcao_olhar=olhar,
            angulo_pedido=pedido,
            permitir_costas=permitir_costas,
        )
        pivot = self._body_facing.getRelativePoint(self.model_np, Point3(0, 0, 0.44))
        if self._aplicar_saida_quat_raiz(dt, angulo, pivot, dragging):
            return
        self._ultimo_quat_raiz = None
        self._peso_saida_quat = 0.0
        self._raiz_tilt_rad = 0.0
        if abs(angulo) < 0.01:
            self._body_facing.setMat(Mat4.identMat())
            return
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
            thickness = 0.042
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
            if mesh == cabinet or mesh.getName().startswith(
                ("procedural-tentacle", "tentacle-joint-", "moldura-armario", "painel-frontal-armario", "fundo-interno-armario")
            ):
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
        up = self.model_np.getRelativeVector(head, Vec3(0, 0, 1)).normalized()
        for tentacle, local_anchor in zip(
            self.tentacle_pool.tentacles, self._tentacle_anchor_local, strict=True
        ):
            anchor = self.model_np.getRelativePoint(head, local_anchor)
            self.tentacle_director.sincronizar_ancora_e_frente(
                tentacle, anchor, front, up
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
        # A curva cobre a frente do tronco no espaço atual da cabeça (mesmo se girada).
        head = self._rig_nodes.get("head")
        for index, limb in enumerate(self._cobertura_roupa):
            if limb.state != TentacleState.CURIOUS:
                continue
            lado = -1 if index == 0 else 1
            if head is not None and not head.isEmpty():
                c1 = Vec3(self.model_np.getRelativePoint(head, Point3(lado * 0.68, 0.64, -0.07)))
                c2 = Vec3(self.model_np.getRelativePoint(head, Point3(-lado * 0.58, 0.62, -0.29)))
                c3 = Vec3(self.model_np.getRelativePoint(head, Point3(lado * 0.27, 0.47, -0.53)))
            else:
                c1 = Vec3(lado * 0.68, -0.64, 0.68)
                c2 = Vec3(-lado * 0.58, -0.62, 0.46)
                c3 = Vec3(lado * 0.27, -0.47, 0.22)
            curva = (limb.anchor, c1, c2, c3)
            for j, segmento in enumerate(limb.segments):
                u = j / (len(limb.segments) - 1)
                v = 1 - u
                segmento.pos = (
                    curva[0] * v**3 + curva[1] * (3 * v*v*u)
                    + curva[2] * (3 * v*u*u) + curva[3] * u**3
                )

    def _sincronizar_porta_para_contatos(self, angulo_porta: float) -> None:
        """Aplica o ângulo real da porta antes de montar as caixas de contato."""
        door = self._rig_nodes.get("door")
        if door is None or door.isEmpty():
            return
        base_h, base_p, base_r = self._rig_base_hpr["door"]
        door.setHpr(base_h + angulo_porta, base_p, base_r)

    def _interromper_cobertura_roupa(self) -> None:
        if self._tempo_cobertura <= 0 and not self._cobertura_roupa:
            return
        self._tempo_cobertura = 0.0
        for limb in self._cobertura_roupa:
            self.tentacle_pool.release(limb)
        self._cobertura_roupa.clear()

    def _disparar_tentaculos_cena_curta(
        self, count: int, *, escala_comp: float = 1.15, escala_esp: float = 1.15, rev_s: float = 0.28, rec_s: float = 0.34, frente_extra: float = 0.0, baixo_extra: float = 0.0, porta_imediata: float = 0.0
    ) -> None:
        td = self.tentacle_director
        if porta_imediata > 0.0:
            td._door_current = max(td._door_current, porta_imediata)
            td._door_requested = max(td._door_requested, porta_imediata)
            td._atraso_abertura_porta = 0.0
            self._sincronizar_porta_para_contatos(td._door_current)
        limbs = td._spawn_curious(count, coreografar=False)
        for idx, limb in enumerate(limbs):
            limb.length_scale = escala_comp
            limb.girth_scale = escala_esp
            limb.duracao_revelacao_s = rev_s
            limb.duracao_recolher_s = rec_s
            limb.state_time = 0.0
            limb.mola_forcada = (240.0, 22.0)
            for seg in limb.segments:
                seg.length = seg.length * (escala_comp / 1.08)
            if limb.target is not None and (frente_extra != 0.0 or baixo_extra != 0.0):
                limb.target = limb.target + limb.reference_front * frente_extra - limb.reference_up * baixo_extra

    def _sincronizar_tentaculos_cena(self, controller, bloqueado: bool) -> None:
        amostra = getattr(controller, "cena_idle_amostra", None)
        if bloqueado or amostra is None or not amostra.ativa:
            self._cena_tentaculo_chave = None
            return
        nome = amostra.nome
        t_c = float(getattr(controller, "_cena_idle_tempo", 0.0))
        td = self.tentacle_director
        chave_ant = getattr(self, "_cena_tentaculo_chave", None)
        if nome == "tentaculo_fujao":
            if 0.42 <= t_c <= 2.25 and chave_ant != ("fujao", 1):
                self._cena_tentaculo_chave = ("fujao", 1)
                self._disparar_tentaculos_cena_curta(1, escala_comp=1.12, escala_esp=1.10, rev_s=0.34, rec_s=0.34, porta_imediata=42.0)
            elif t_c > 2.25 and chave_ant == ("fujao", 1):
                self._cena_tentaculo_chave = ("fujao", 2)
                td.pool.release_all()
            if t_c >= 3.04:
                td._door_current = min(td._door_current, 1.5)
        elif nome == "roubo_cursor_tentaculo":
            if 0.64 <= t_c <= 1.12 and chave_ant != ("roubo", 1):
                self._cena_tentaculo_chave = ("roubo", 1)
                self._disparar_tentaculos_cena_curta(1, escala_comp=1.45, escala_esp=1.22, rev_s=0.14, rec_s=0.20, frente_extra=0.18, baixo_extra=0.10, porta_imediata=96.0)
            elif 1.12 < t_c < 3.26 and chave_ant == ("roubo", 1):
                self._cena_tentaculo_chave = ("roubo", 2)
                td.pool.release_all()
            elif 3.26 <= t_c <= 3.78 and chave_ant != ("roubo", 3):
                self._cena_tentaculo_chave = ("roubo", 3)
                self._disparar_tentaculos_cena_curta(2, escala_comp=1.35, escala_esp=1.18, rev_s=0.14, rec_s=0.24, frente_extra=0.16, baixo_extra=0.08, porta_imediata=98.0)
                if self._vfx_enabled:
                    self.tentacle_drips.spray(self.tentacle_pool.tentacles)
            elif t_c > 3.78 and chave_ant == ("roubo", 3):
                self._cena_tentaculo_chave = ("roubo", 4)
                td.pool.release_all()
            if 1.38 <= t_c <= 2.95:
                for limb in td.pool.tentacles:
                    limb.reveal = 0.0
                td._door_current = min(td._door_current, 3.5)
        elif nome == "cuspir_item":
            if 0.54 <= t_c <= 1.42 and chave_ant != ("cuspir", 1):
                self._cena_tentaculo_chave = ("cuspir", 1)
                self._disparar_tentaculos_cena_curta(2, escala_comp=1.50, escala_esp=1.30, rev_s=0.16, rec_s=0.30, frente_extra=0.20, baixo_extra=0.18, porta_imediata=98.0)
                if self._vfx_enabled:
                    self.tentacle_drips.spray(self.tentacle_pool.tentacles)
            elif t_c > 1.42 and chave_ant == ("cuspir", 1):
                self._cena_tentaculo_chave = ("cuspir", 2)
                td.pool.release_all()
            if t_c >= 1.92:
                td._door_current = min(td._door_current, 1.5)

    def _sincronizar_bloqueio_apendices(self, controller, visible: bool) -> tuple[bool, bool]:
        """Garante recolhimento e devolução da porta em drag/fall/sleep."""
        bloqueado = controller.state in (
            AnimationState.DRAG,
            AnimationState.FALL,
            AnimationState.SLEEP,
        )
        if not bloqueado:
            return False, visible
        self.tentacle_director.music_ejection = False
        self._interromper_cobertura_roupa()
        ha_restos = (
            self._tentacles_were_visible
            or self.tentacle_director.coreografia_ativa
            or self.tentacle_director.speaker_throw_remaining > 0
            or self.tentacle_director.burst
            or self.tentacle_director.frenzy_mode
            or self.tentacle_director.swallowing
            or any(
                t.state not in (TentacleState.DORMANT, TentacleState.RETRACTING)
                for t in self.tentacle_pool.tentacles
            )
        )
        if ha_restos:
            self.tentacle_director.encerrar_espiada(interromper=True)
        return True, False

    def update_appendages(self, dt, visible=True):  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        """Atualiza os apêndices (porta, tentáculos, caixa) no frame."""
        if not self.tentacle_director:
            return
        controller = self.showbase.animation_controller
        bloqueado, visible = self._sincronizar_bloqueio_apendices(controller, visible)
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
            dedos_clipe=getattr(controller, "dedos_clipe_ativo", None),
            gesto_esquerda=getattr(controller, "gesto_mao_esquerda", None),
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
        eh_emote_clipe = bool(
            dancing and carregar_clipe_emote(dance.style) is not None
        )
        if eh_emote_clipe and self.music_speaker.age < self.music_speaker.start_jump + 0.4:
            self.music_speaker.age = self.music_speaker.start_jump + 0.4
        self.music_speaker.update(
            dt, speaker_active, dance.phase, dance.energy, dance.bass
        )
        self._sync_tentacle_anchors_and_front()

        speaker = self.music_speaker
        throw_index = -1 if bloqueado else speaker.throw_index
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
        self.tentacle_director.music_ejection = False if bloqueado else speaker.ejecting
        if speaker.ejecting and not bloqueado:
            self._door_requested = max(self._door_requested, 110)
        if dancing and not eh_emote_clipe and speaker.age < speaker.start_jump + 0.35:
            age = speaker.age
            olhar = suavizar_quintico((age - speaker.end_throws) / 0.33)
            olhar *= 1 - suavizar_quintico((age - speaker.start_jump) / 0.35)
            shot = sum(
                math.exp(-(((age - at) / 0.13) ** 2)) for at in speaker.throw_beats
            )
            head = self._rig_nodes["head"]
            head.setH(head.getH() - 17 * shot + 62 * olhar)
            head.setP(head.getP() - 24 * shot)
            self._outline_nodes["head"].setHpr(head.getHpr())
            self._sync_tentacle_anchors_and_front()

        sneezing = controller.state is not None and controller.state.value == "sneeze"
        if (
            sneezing
            and controller._reaction_time >= 3.6
            and not self.tentacle_director.burst
        ):
            self.tentacle_director.trigger_sneeze()
            if self._vfx_enabled:
                self.tentacle_drips.spray(self.tentacle_pool.tentacles)
        if not sneezing and not any(
            t.state != TentacleState.DORMANT for t in self.tentacle_pool.tentacles
        ):
            self.tentacle_director.burst = False
        self._sincronizar_tentaculos_cena(controller, bloqueado)
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
            # Aplica o ângulo aberto atual antes de coletar caixas para não esmagar na porta em 0°.
            self._sincronizar_porta_para_contatos(self.tentacle_director._door_current)
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
            else 105.0
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
        if self._vfx_enabled:
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
            if tentacles_active:
                self._update_tentacle_contacts()
                self.tentacle_director.reprojetar_portas()
            out_door = self._outline_nodes.get("door")
            if out_door:
                out_door.hide()
        debug = getattr(self.showbase, "debug_tools", None)
        for tentacle in self.tentacle_pool.tentacles:
            tentacle_visible = (
                tentacle.state != TentacleState.DORMANT
                and tentacle.reveal > 0.015
                and (
                    abs(angulo_porta) >= 14.0
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
                    if tentacle_visible and getattr(self, "_outline_enabled", True)
                    else tentacle.outline_mesh_node.hide
                )()
        self.fio_fone.atualizar(dt)
        if getattr(self, "prop_cuspido", None) is not None:
            self.prop_cuspido.atualizar(dt, controller, interromper=bloqueado)

    def trocar_caixa_de_som(self, estilo: str) -> None:
        """Recria o palco com a seleção atual e libera os nós da seleção anterior."""
        from sejoga.musica.caixa_som import MusicSpeaker

        anterior = self.music_speaker
        self.music_speaker = MusicSpeaker(self, estilo)
        self.music_speaker.set_album_colors(getattr(self, "_album_colors", ()))
        anterior.root.removeNode()
        self._speaker_throw_index = -1

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
        if self._shadow_np is not None:
            self._shadow_np.hide()
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
        elif style == "fnf_blue_balls":
            vertex = """#version 130
in vec4 p3d_Vertex; in vec2 p3d_MultiTexCoord0;
uniform mat4 p3d_ModelViewProjectionMatrix; out vec2 uv;
void main() { uv = p3d_MultiTexCoord0; gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex; }
"""
            fragment = f"""#version 130
uniform sampler2D p3d_Texture0; uniform float u_fnf_shade; in vec2 uv; out vec4 fragColor;
void main() {{
    if (texture(p3d_Texture0, uv).a < {CONTORNO_ALPHA_DISCARD}) discard;
    fragColor = vec4(u_fnf_shade, u_fnf_shade * 1.03, u_fnf_shade * 1.15, 1.0);
}}
"""
            self.model_np.setShader(Shader.make(Shader.SL_GLSL, vertex, fragment), 1001)
            self.model_np.setShaderInput("u_fnf_shade", 0.008)
            if self.outline_np is not None:
                self.outline_np.setShaderInput("outline_color", (0.0, 0.0, 0.0, 1.0))
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

    def _paleta_transicao_estilo(self) -> dict[str, tuple[float, float, float]]:
        """Devolve a paleta de abertura/encerramento adaptada aos 5 estilos canônicos."""
        from sejoga.configuracao import normalizar_filtro_visual

        filtro = normalizar_filtro_visual(getattr(self, "_visual_filter", "blockbench"))
        paletas: dict[str, dict[str, tuple[float, float, float]]] = {
            "blockbench": {
                "primaria": (0.14, 0.78, 1.0),
                "secundaria": (1.0, 0.86, 0.24),
                "fumaca": (0.94, 0.96, 1.0),
            },
            "street": {
                "primaria": (1.0, 0.88, 0.13),
                "secundaria": (0.07, 0.84, 1.0),
                "fumaca": (0.65, 0.96, 0.12),
            },
            "anime": {
                "primaria": (0.36, 0.88, 1.0),
                "secundaria": (1.0, 0.84, 0.34),
                "fumaca": (0.95, 0.96, 1.0),
            },
            "spiderverse": {
                "primaria": (1.0, 0.20, 0.26),
                "secundaria": (0.07, 0.85, 1.0),
                "fumaca": (1.0, 0.91, 0.10),
            },
            "holograma": {
                "primaria": (0.11, 0.91, 1.0),
                "secundaria": (0.22, 0.96, 0.55),
                "fumaca": (0.95, 1.0, 1.0),
            },
        }
        return paletas[filtro]

    def set_post_effect(
        self,
        dissolve: float = 0.0,
        dissolve_mode: str | float = "uniform",
        tint: tuple[float, float, float] = (0.10, 0.65, 1.00),
        flash: float = 0.0,
    ) -> None:
        """Atualiza uniforms do shader de pós-processamento (dissolução e brilho)."""
        pipeline = getattr(self, "_pbr_pipeline", None)
        if pipeline is None or not self._use_chroma_resolve:
            return
        quad = pipeline._post_process_quad
        dissolve_val = float(max(0.0, min(1.0, dissolve)))
        if isinstance(dissolve_mode, (int, float)):
            mode_val = float(dissolve_mode)
        elif dissolve_mode == "goku":
            mode_val = 3.0
        elif dissolve_mode == "cyberpsicopata":
            mode_val = 2.0
        elif dissolve_mode == "thanos":
            mode_val = 1.0
        else:
            mode_val = 0.0
        tint_val = (float(tint[0]), float(tint[1]), float(tint[2]))
        flash_val = float(max(0.0, min(1.0, flash)))
        state = (quad, dissolve_val, mode_val, tint_val, flash_val)
        if getattr(self, "_last_post_effect", None) == state:
            return
        self._last_post_effect = state
        quad.setShaderInput("u_dissolve", dissolve_val)
        quad.setShaderInput("u_dissolve_mode", mode_val)
        quad.setShaderInput("u_overlay_tint", tint_val)
        quad.setShaderInput("u_overlay_flash", flash_val)

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
        for node in self._fx_ghost_nodes:
            node.removeNode()
        self._fx_ghost_nodes.clear()
        self._sandevistan_stamps.clear()
        if self._fnf_skeleton is not None:
            self._fnf_skeleton.limpar()
            self._fnf_skeleton = None
        if self._fx_root is not None:
            self._fx_root.removeNode()
            self._fx_root = None

    def _garantir_shader_silhueta(self):
        if self._fx_ghost_shader is not None:
            return self._fx_ghost_shader
        try:
            from panda3d.core import Shader
        except ImportError:
            return None
        vertex = """#version 130
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
uniform mat4 p3d_ModelViewProjectionMatrix;
out vec2 uv;
void main() {
    uv = p3d_MultiTexCoord0;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
"""
        fragment = f"""#version 130
uniform sampler2D p3d_Texture0;
uniform vec4 ghost_color;
uniform float u_ghost_dissolve;
in vec2 uv;
out vec4 fragColor;
float _sj_g_bayer(vec2 p) {{
    vec2 m = floor(mod(p, 4.0));
    int i = int(m.x) + int(m.y) * 4;
    const float tbl[16] = float[16](
        0.0/16.0,  8.0/16.0,  2.0/16.0, 10.0/16.0,
       12.0/16.0,  4.0/16.0, 14.0/16.0,  6.0/16.0,
        3.0/16.0, 11.0/16.0,  1.0/16.0,  9.0/16.0,
       15.0/16.0,  7.0/16.0, 13.0/16.0,  5.0/16.0
    );
    return tbl[i];
}}
void main() {{
    if (texture(p3d_Texture0, uv).a < {CONTORNO_ALPHA_DISCARD}) discard;
    if (u_ghost_dissolve > 0.001 && _sj_g_bayer(gl_FragCoord.xy) <= clamp(u_ghost_dissolve, 0.0, 1.0)) discard;
    fragColor = ghost_color;
}}
"""
        self._fx_ghost_shader = Shader.make(Shader.SL_GLSL, vertex, fragment)
        return self._fx_ghost_shader

    def _cache_rig_ghost(self, ghost) -> dict[str, Any]:
        cached = ghost.getPythonTag("rig_nodes") if hasattr(ghost, "getPythonTag") else None
        if cached is not None:
            return cached
        mapping = {}
        for nome in self._rig_nodes:
            sub = ghost.find("**/" + nome)
            if not sub.isEmpty():
                mapping[nome] = sub
        if hasattr(ghost, "setPythonTag"):
            ghost.setPythonTag("rig_nodes", mapping)
        return mapping

    def _copiar_pose_ghost(self, ghost, _origem=None) -> None:
        dest_nodes = self._cache_rig_ghost(ghost)
        for nome, dest in dest_nodes.items():
            orig = self._rig_nodes.get(nome)
            if orig is not None and not orig.isEmpty():
                dest.setHpr(orig.getHpr())

    def _aplicar_pose_ghost(
        self,
        ghost,
        freeze_pose: dict[str, tuple[float, float, float]] | None,
        *,
        stamp_id: int | None = None,
    ) -> None:
        if not freeze_pose:
            self._copiar_pose_ghost(ghost)
            return
        if stamp_id is not None and hasattr(ghost, "getPythonTag"):
            if ghost.getPythonTag("stamp_id") == stamp_id:
                return
            ghost.setPythonTag("stamp_id", stamp_id)
        dest_nodes = self._cache_rig_ghost(ghost)
        for nome_g, hpr_g in freeze_pose.items():
            sub = dest_nodes.get(nome_g)
            if sub is not None:
                sub.setHpr(*hpr_g)

    def _garantir_pool_silhuetas(self, count: int, root, shader) -> None:
        while len(self._fx_ghost_nodes) < count:
            ghost = self.model_np.copyTo(root)
            ghost.setLightOff(1001)
            ghost.setCollideMask(0)
            for tampa in ghost.findAllMatches("**/*-tampa"):
                tampa.removeNode()
            for sub_gn in ghost.findAllMatches("**/+GeomNode"):
                sub_gn.clearShader()
            if shader is not None:
                ghost.setShader(shader, 1001)
                ghost.setShaderInput("u_ghost_dissolve", 0.0)
            else:
                ghost.setTextureOff(1)
            self._cache_rig_ghost(ghost)
            ghost.hide()
            self._fx_ghost_nodes.append(ghost)

    def _atualizar_silhuetas_fx(
        self,
        ativo: bool,
        posicoes_cores: list[tuple],
        *,
        freeze_poses: list[dict[str, tuple[float, float, float]]] | None = None,
        stamp_ids: list[int] | None = None,
    ) -> None:
        if (
            not ativo
            or not posicoes_cores
            or self.model_np is None
            or not hasattr(self.model_np, "copyTo")
        ):
            for node in self._fx_ghost_nodes:
                node.hide()
            return
        root = self._garantir_fx_root()
        shader = self._garantir_shader_silhueta()
        self._garantir_pool_silhuetas(len(posicoes_cores), root, shader)
        for idx, ghost in enumerate(self._fx_ghost_nodes):
            if idx >= len(posicoes_cores):
                ghost.hide()
                continue
            item = posicoes_cores[idx]
            pos, hpr, cor, scale = item[0], item[1], item[2], item[3]
            dissolve = float(item[4]) if len(item) > 4 else 0.0
            ghost.show()
            ghost.setPos(pos)
            ghost.setHpr(hpr[0], hpr[1], hpr[2])
            ghost.setScale(scale)
            ghost.setColor(cor[0], cor[1], cor[2], 1.0)
            fp = freeze_poses[idx] if freeze_poses and idx < len(freeze_poses) else None
            sid = stamp_ids[idx] if stamp_ids and idx < len(stamp_ids) else None
            self._aplicar_pose_ghost(ghost, fp, stamp_id=sid)
            if shader is not None:
                ghost.setShaderInput("ghost_color", (cor[0], cor[1], cor[2], 1.0))
                ghost.setShaderInput("u_ghost_dissolve", dissolve)

    def _garantir_vfx_transicoes(self):
        if self._vfx_transicoes is None:
            from sejoga.render.vfx.transicoes import GerenciadorVfxTransicao

            ef = getattr(self, "efeitos_street", None)
            pai = ef.root if ef is not None else self.showbase.render
            escala = float(getattr(ef, "_escala_global", 1.0)) if ef is not None else 1.0
            self._vfx_transicoes = GerenciadorVfxTransicao(pai, escala_global=escala)
        return self._vfx_transicoes

    def _ancoras_transicao(self) -> dict[str, Vec3]:
        ef = getattr(self, "efeitos_street", None)
        if ef is not None:
            return ef._calcular_ancoras()
        pos, _, _ = self._pose_mundo_modelo()
        return {
            "tronco": Vec3(pos.x, pos.y, pos.z + 0.4),
            "pes": Vec3(pos.x, pos.y, pos.z - 1.1),
            "cabeca_topo": Vec3(pos.x, pos.y, pos.z + 2.2),
            "antena_d": Vec3(pos.x - 0.8, pos.y, pos.z + 2.1),
            "antena_e": Vec3(pos.x + 0.8, pos.y, pos.z + 2.1),
        }

    def definir_contexto_entrada(self, estilo: str, progresso: float) -> None:
        """Registra estilo e progresso [0..1] da abertura para os VFX dedicados."""
        self._transicao_intro_estilo = str(estilo or "")
        self._transicao_intro_prog = max(0.0, min(1.0, float(progresso)))

    def definir_progresso_saida(self, progresso: float) -> None:
        """Registra progresso [0..1] da saída/morte para os VFX dedicados."""
        self._transicao_saida_prog = max(0.0, min(1.0, float(progresso)))

    def prewarm_intro_effects(self, style: str) -> None:
        """Pré-aloca nós/shaders pesados da abertura para evitar engasgos no frame 1."""
        self._transicao_intro_estilo = str(style or "")
        if self.model_np is None:
            return
        self._garantir_vfx_transicoes()
        if style == "sandevistan_in" and hasattr(self.model_np, "copyTo"):
            root = self._garantir_fx_root()
            shader = self._garantir_shader_silhueta()
            self._garantir_pool_silhuetas(8, root, shader)
        elif style == "kagebunshin_in" and not self._fx_smoke_nodes:
            root = self._garantir_fx_root()
            for idx, _o in enumerate(_NINJA_SMOKE_OFFSETS):
                puff = self._criar_bloco_fx(
                    f"ninja-puff-{idx}", 1.0, (0.94, 0.96, 1.0, 1.0)
                )
                puff.hide()
                puff.reparentTo(root)
                self._fx_smoke_nodes.append(puff)

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
        cor_fumaca = self._paleta_transicao_estilo()["fumaca"]
        for idx, (puff, (ox, oy, oz, rad)) in enumerate(
            zip(self._fx_smoke_nodes, _NINJA_SMOKE_OFFSETS, strict=True)
        ):
            puff.show()
            puff.setColorScale(cor_fumaca[0], cor_fumaca[1], cor_fumaca[2], 1.0)
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

    def _atualizar_cinzas_thanos(
        self, ash: float, center_world: Vec3, *, paleta: str = "thanos"
    ) -> None:
        if ash <= 0.02:
            for node in self._fx_ash_nodes:
                node.hide()
            return
        count = 20
        self._garantir_flocos_thanos(count)
        s = max(0.35, self.model_np.getSz() * 0.18)
        pal_estilo = self._paleta_transicao_estilo()
        for idx, flake in enumerate(self._fx_ash_nodes):
            delay = (idx / count) * 0.55
            local_p = max(0.0, min(1.0, (ash - delay * 0.6) / max(0.25, 1.0 - delay * 0.6)))
            if local_p <= 0.0 or local_p >= 0.98:
                flake.hide()
                continue
            flake.show()
            if paleta == "cyber":
                c_a = pal_estilo["secundaria"]
                c_b = pal_estilo["primaria"]
                cor = (*c_a, 1.0) if idx % 2 == 0 else (*c_b, 1.0)
                flake.setColorScale(*cor)
            elif paleta == "portal":
                c_a = pal_estilo["primaria"]
                c_b = pal_estilo["secundaria"]
                cor = (*c_a, 1.0) if idx % 2 == 0 else (*c_b, 1.0)
                flake.setColorScale(*cor)
            else:
                flake.clearColorScale()
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
            for idx, (cor_base, cor_fenda) in enumerate(
                (
                    ((0.03, 0.34, 1.0, 1.0), (0.62, 0.94, 1.0, 1.0)),
                    ((0.06, 0.42, 1.0, 1.0), (0.68, 0.96, 1.0, 1.0)),
                )
            ):
                orb = self._criar_esfera_fx(
                    f"fnf-blue-orb-{idx}", 0.27, cor_base, cor_fenda
                )
                orb.setShaderOff(1001)
                orb.setLightOff(1001)
                orb.setBin("fixed", 60)
                orb.setDepthTest(False)
                orb.setDepthWrite(False)
                halo = self._criar_esfera_fx(
                    f"fnf-blue-halo-{idx}",
                    0.34,
                    (0.02, 0.28, 0.96, 0.28),
                    (0.24, 0.70, 1.0, 0.34),
                )
                from panda3d.core import ColorBlendAttrib

                halo.setTransparency(1)
                halo.setAttrib(
                    ColorBlendAttrib.make(
                        ColorBlendAttrib.MAdd,
                        ColorBlendAttrib.OIncomingAlpha,
                        ColorBlendAttrib.OOneMinusIncomingAlpha,
                        ColorBlendAttrib.MAdd,
                        ColorBlendAttrib.OOne,
                        ColorBlendAttrib.OOneMinusIncomingAlpha,
                    ),
                    10,
                )
                halo.setBin("fixed", 59)
                halo.setDepthTest(False)
                halo.setDepthWrite(False)
                halo.reparentTo(orb)
                orb.reparentTo(root)
                self._fx_blue_nodes.append(orb)

        scale_ref = max(0.35, float(self.model_np.getSz()) * 0.20)
        pelvis_node = (
            self._rig_nodes.get("cintura")
            or self._rig_nodes.get("legs")
            or self.model_np
        )
        pelvis_pos = pelvis_node.getPos(self.showbase.render)
        for idx, orb in enumerate(self._fx_blue_nodes):
            orb.show()
            side = -1.0 if idx == 0 else 1.0
            orb.setPos(
                pelvis_pos.x + side * 0.22 * scale_ref,
                pelvis_pos.y - 0.56 * scale_ref,
                pelvis_pos.z - 0.26 * scale_ref,
            )
            pulse = (0.86 + 0.26 * power) * scale_ref
            orb.setScale(pulse)
            orb.setHpr(side * 16.0 + (power - 0.8) * 26.0, -10.0, side * 12.0)

    def _ocultar_halos_antena(self) -> None:
        if getattr(self, "_choque_antenas_3d", None) is not None:
            self._choque_antenas_3d.ocultar()
        for _d, _e, _a, _pivot_np, halo_np, halo_in_np, orbe_a, orbe_b in getattr(
            self, "_argolas_fx", ()
        ):
            for node in (halo_np, halo_in_np, orbe_a, orbe_b):
                if not node.isEmpty():
                    node.hide()

    def _definir_acessorios_lego_visiveis(self, visivel: bool) -> None:
        if getattr(self, "fio_fone", None) is not None:
            self.fio_fone.definir_visivel(visivel)
        for item in getattr(self, "_argolas_antena", ()):
            np = item[0]
            eh_outline = item[5]
            if not np.isEmpty() and not eh_outline:
                (np.show if visivel else np.hide)()
        if not visivel:
            self._ocultar_halos_antena()

    def _iniciar_lego_scatter(self, world_floor_z: float | None = None) -> None:
        self._lego_snapshot.clear()
        if self._lego_root is not None:
            self._lego_root.removeNode()
            self._lego_root = None
        if getattr(self.lower_body, "pernas_tecido", None) is not None:
            self.lower_body.pernas_tecido.set_lego_mode(self, True)
        self._definir_acessorios_lego_visiveis(False)
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

    def _capturar_poses_rig(self) -> dict[str, tuple[float, float, float]]:
        return {
            nome: (float(no.getH()), float(no.getP()), float(no.getR()))
            for nome, no in self._rig_nodes.items()
            if not no.isEmpty()
        }

    def _registrar_stamp_sandevistan(
        self,
        now: float,
        desktop_pos: tuple[int, int] | None,
        world_pos: Point3,
        world_hpr: tuple[float, float, float],
        scale_ref,
        units: float,
    ) -> None:
        precisa_novo = not self._sandevistan_stamps
        if not precisa_novo:
            ultimo = self._sandevistan_stamps[-1]
            dt_stamp = now - ultimo["born"]
            dx_px = (
                abs(desktop_pos[0] - ultimo["desktop_x"])
                if desktop_pos is not None and ultimo["desktop_x"] is not None
                else abs(world_pos.x - ultimo["world_pos"].x) / max(1e-5, units)
            )
            precisa_novo = dt_stamp >= 0.024 or dx_px >= 12.0
        if not precisa_novo:
            return
        idx = (self._sandevistan_stamps[-1]["idx"] + 1) if self._sandevistan_stamps else 0
        self._sandevistan_stamps.append(
            {
                "idx": idx,
                "born": now,
                "desktop_x": desktop_pos[0] if desktop_pos is not None else None,
                "world_pos": Point3(world_pos),
                "world_hpr": world_hpr,
                "scale": scale_ref,
                "bone_hprs": self._capturar_poses_rig(),
                "color": _SANDEVISTAN_CORES[idx % len(_SANDEVISTAN_CORES)],
            }
        )
        if len(self._sandevistan_stamps) > 6:
            del self._sandevistan_stamps[:-6]

    def _atualizar_sandevistan_intro(
        self,
        afterimage: float,
        desktop_pos: tuple[int, int] | None,
        units: float,
    ) -> None:
        now = time.perf_counter()
        world_pos, world_hpr, scale_ref = self._pose_mundo_modelo()
        if afterimage > 0.02:
            self._registrar_stamp_sandevistan(
                now, desktop_pos, world_pos, world_hpr, scale_ref, units
            )
        vida_s = 0.42
        self._sandevistan_stamps = [
            st for st in self._sandevistan_stamps if (now - st["born"]) < vida_s
        ]
        if not self._sandevistan_stamps:
            self._atualizar_silhuetas_fx(False, [])
            return
        self.set_post_effect(dissolve=0.0, dissolve_mode="uniform", flash=0.0)
        silhuetas: list[tuple] = []
        freeze_poses: list[dict[str, tuple[float, float, float]]] = []
        stamp_ids: list[int] = []
        total = len(self._sandevistan_stamps)
        for ordem, st in enumerate(self._sandevistan_stamps):
            age_u = (now - st["born"]) / vida_s
            dissolve = max(0.18, min(0.96, 0.18 + age_u * 0.78))
            wx = (
                world_pos.x + (st["desktop_x"] - desktop_pos[0]) * units
                if desktop_pos is not None and st["desktop_x"] is not None
                else st["world_pos"].x
            )
            wy = world_pos.y + 0.08 * (total - ordem)
            silhuetas.append(
                (Point3(wx, wy, st["world_pos"].z), st["world_hpr"], st["color"], st["scale"], dissolve)
            )
            freeze_poses.append(st["bone_hprs"])
            stamp_ids.append(st["idx"])
        self._atualizar_silhuetas_fx(
            True, silhuetas, freeze_poses=freeze_poses, stamp_ids=stamp_ids
        )

    def _centro_efeito_intro(self) -> Vec3:
        bounds = self.model_anchor.getTightBounds(self.showbase.render)
        return (
            (bounds[0] + bounds[1]) * 0.5
            if bounds
            else self.model_anchor.getPos(self.showbase.render)
        )

    def _aplicar_visibilidade_e_dissolve_intro(self, frame) -> None:
        d_mode = float(getattr(frame, "dissolve_mode", 0.0))
        pal = self._paleta_transicao_estilo()
        if frame.dissolve >= 0.96 and frame.smoke_burst > 0.05 and d_mode < 2.5:
            self.model_np.hide()
            self.outline_np.hide()
            self.set_post_effect(dissolve=0.0)
            return
        self.model_np.show()
        if self._outline_enabled:
            self.outline_np.show()
        tint = pal["secundaria"] if d_mode >= 2.5 else pal["primaria"]
        flash = (0.48 * frame.dissolve) if d_mode >= 2.5 else 0.0
        self.set_post_effect(
            dissolve=frame.dissolve,
            dissolve_mode=d_mode,
            tint=tint,
            flash=flash,
        )

    def apply_intro_effect(
        self,
        frame,
        *,
        desktop_pos: tuple[int, int] | None = None,
        apply_horizontal_offset: bool = True,
    ) -> None:
        """Aplica escala, deslocamento, dissolução Bayer e fumaça ninja da abertura."""
        if not self.model_anchor or not self.model_np:
            return
        if self._intro_orig_foot_local_z is None:
            bounds_local = self.model_np.getTightBounds(self.model_anchor)
            self._intro_orig_foot_local_z = (
                float(bounds_local[0].z) if bounds_local else -0.52
            )
        self._aplicar_visibilidade_e_dissolve_intro(frame)
        base_pos = self._resolver_base_intro()
        scale = max(0.08, float(frame.scale))
        warp = getattr(frame, "warp_scale", (1.0, 1.0, 1.0))
        units = float(self._view_height / max(1, self.height))
        foot_comp = self._intro_orig_foot_local_z * (1.0 - scale * float(warp[2]))
        offset_x_u = frame.offset_x * units if apply_horizontal_offset else 0.0
        self.model_anchor.setPos(
            base_pos.x + offset_x_u,
            base_pos.y,
            base_pos.z - frame.offset_y * units + foot_comp,
        )
        self.model_anchor.setScale(
            scale * float(warp[0]),
            scale * float(warp[1]),
            scale * float(warp[2]),
        )
        self.model_anchor.setHpr(frame.yaw, frame.pitch, frame.roll)
        self._atualizar_fumaca_ninja(frame.smoke_burst, self._centro_efeito_intro())
        afterimage = float(getattr(frame, "afterimage", 0.0))
        d_mode = float(getattr(frame, "dissolve_mode", 0.0))
        if d_mode >= 2.5 and afterimage > 0.02 and self.model_np is not None:
            pal = self._paleta_transicao_estilo()
            world_pos, world_hpr, scale_ref = self._pose_mundo_modelo()
            silhuetas_goku = [
                (
                    Point3(world_pos.x - 0.045, world_pos.y + 0.12, world_pos.z + 0.06),
                    world_hpr,
                    pal["secundaria"],
                    scale_ref,
                    0.35,
                ),
                (
                    Point3(world_pos.x + 0.045, world_pos.y + 0.18, world_pos.z - 0.06),
                    world_hpr,
                    pal["primaria"],
                    scale_ref,
                    0.45,
                ),
            ]
            self._atualizar_silhuetas_fx(True, silhuetas_goku)
        elif (afterimage > 0.02 or self._sandevistan_stamps) and self.model_np is not None:
            self._atualizar_sandevistan_intro(afterimage, desktop_pos, units)
        else:
            self._atualizar_silhuetas_fx(False, [])
        if self._vfx_enabled:
            estilo_in = self._transicao_intro_estilo or (
                "goku_teleport_in"
                if d_mode >= 2.5
                else (
                    "kagebunshin_in"
                    if getattr(frame, "smoke_burst", 0.0) > 0.01
                    else ("hero_drop_in" if getattr(frame, "locomotion", "") in ("fall", "land") else "fade_in")
                )
            )
            prog_in = (
                self._transicao_intro_prog
                if self._transicao_intro_prog is not None
                else max(0.05, 1.0 - float(getattr(frame, "dissolve", 0.0)))
            )
            self._garantir_vfx_transicoes().atualizar_entrada(
                estilo_in, prog_in, getattr(self, "_visual_filter", "blockbench"), self._ancoras_transicao()
            )

    def _pose_mundo_modelo(self):
        pos = self.model_np.getPos(self.showbase.render)
        hpr = self.model_np.getHpr(self.showbase.render)
        scale = self.model_np.getScale(self.showbase.render)
        return pos, (float(hpr.x), float(hpr.y), float(hpr.z)), scale

    def restore_intro_effect(self) -> None:
        """Restaura câmera/escala/pós-efeito ao concluir ou cancelar abertura."""
        if self.model_np:
            self.model_np.show()
        if self.outline_np and self._outline_enabled:
            self.outline_np.setShaderInput(
                "outline_color",
                getattr(self, "_outline_color_rgba", (0.0, 0.0, 0.0, 1.0)),
            )
            self.outline_np.show()
        if self.model_anchor:
            if (
                self._intro_orig_anchor_pos is not None
                and getattr(self.showbase, "desktop", None) is None
            ):
                self.model_anchor.setPos(self._intro_orig_anchor_pos)
            self.model_anchor.setScale(1.0)
            self.model_anchor.setHpr(0.0, 0.0, 0.0)
        self._intro_orig_anchor_pos = None
        self._intro_orig_foot_local_z = None
        self._anim_air_px_suave = 0.0
        self._sandevistan_stamps.clear()
        self._transicao_intro_estilo = ""
        self._transicao_intro_prog = None
        if self._vfx_transicoes is not None:
            self._vfx_transicoes.limpar()
        self.set_post_effect(dissolve=0.0, flash=0.0)
        self._transicao_saida_prog = None
        if self._vfx_transicoes is not None:
            self._vfx_transicoes.limpar()
        self._limpar_fx()
        self.atualizar_sombra_contato()

    def _fx_saida_fnf(self, frame) -> tuple[tuple[float, float, float], float]:
        shock = float(getattr(frame, "shock", 0.0))
        blue_balls = float(getattr(frame, "blue_balls", 0.0))
        dissolve = min(1.0, float(getattr(frame, "dissolve", 0.0)))
        if self._fnf_skeleton is None and self.model_np is not None:
            from sejoga.render.esqueleto_fnf import EsqueletoFnf

            self._fnf_skeleton = EsqueletoFnf(self.showbase.render, self._rig_nodes)
        skel_power = max(shock, blue_balls) * (1.0 - dissolve)
        if self._fnf_skeleton is not None:
            self._fnf_skeleton.atualizar(skel_power, self.showbase.render)
        if self.model_np is not None:
            shade = (0.008 + 0.055 * shock) if shock > 0.02 else 0.006
            self.model_np.setShaderInput("u_fnf_shade", shade)
        if self.outline_np is not None:
            self.outline_np.setShaderInput("outline_color", (0.0, 0.0, 0.0, 1.0))
        # Mantém flash=0.0 para nunca escurecer o magenta do colorkey no desktop.
        return (0.0, 0.0, 0.0), 0.0

    def _fx_saida_cyberpsicopata(
        self, frame, units: float
    ) -> tuple[tuple[float, float, float], float, list[tuple]]:
        # Split cromático nítido (ciano / carmesim) sem borrão de múltiplas camadas.
        glitch_pulse = float(getattr(frame, "glitch_pulse", 0.0))
        glitch_offset = float(getattr(frame, "glitch_offset", 0.0))
        passo = int(glitch_pulse * 12.0 + float(frame.dissolve) * 10.0)
        spike = passo % 4 == 0
        tint = (1.0, 0.12, 0.28) if passo % 2 else (0.06, 0.96, 1.0)
        flash = (0.10 + glitch_pulse * 0.22) if spike else 0.0
        silhuetas: list[tuple] = []
        if abs(glitch_offset) > 0.25 and frame.dissolve < 0.92 and self.model_np is not None:
            world_pos, world_hpr, scale_ref = self._pose_mundo_modelo()
            amp = max(0.50, glitch_offset) * (7.5 + 9.0 * glitch_pulse)
            camadas = (
                (-1.0, 0.14, 3.0, (0.06, 0.96, 1.0), 0.24),
                (1.0, 0.22, -3.0, (1.0, 0.10, 0.28), 0.34),
            )
            for mult, wy_off, dz_px, cor, diss in camadas:
                silhuetas.append(
                    (
                        Point3(
                            world_pos.x + mult * amp * units,
                            world_pos.y + wy_off,
                            world_pos.z + dz_px * glitch_pulse * units,
                        ),
                        world_hpr,
                        cor,
                        scale_ref,
                        diss,
                    )
                )
        return tint, flash, silhuetas

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
        s = max(0.05, float(frame.scale))
        warp = getattr(frame, "warp_scale", (1.0, 1.0, 1.0))
        self.exit_pivot.setScale(
            s * float(warp[0]),
            s * float(warp[1]),
            s * float(warp[2]),
        )

        if style == "lego_disassemble" and frame.explode > 0.0:
            if not self._lego_snapshot:
                self._iniciar_lego_scatter(getattr(self, "_lego_floor_world_z", None))
            self._atualizar_lego_scatter(frame.explode)

        pal = self._paleta_transicao_estilo()
        d_mode_frame = float(getattr(frame, "dissolve_mode", 0.0))
        mode: str | float = (
            "goku"
            if (style == "goku_teleport_out" or d_mode_frame >= 2.5)
            else (
                "cyberpsicopata"
                if style == "cyberpsicopata_out"
                else (
                    "thanos"
                    if style in ("thanos_snap", "portal_pull_out")
                    else "uniform"
                )
            )
        )
        silhuetas_saida: list[tuple] = []
        if style == "fnf_blue_balls":
            tint, flash = self._fx_saida_fnf(frame)
        elif style == "cyberpsicopata_out":
            tint, flash, silhuetas_saida = self._fx_saida_cyberpsicopata(frame, units)
        elif style == "goku_teleport_out" or d_mode_frame >= 2.5:
            tint = pal["secundaria"]
            flash = min(0.55, float(getattr(frame, "shock", 0.0)) * 0.48)
            if 0.05 < frame.dissolve < 0.96 and self.model_np is not None:
                world_pos, world_hpr, scale_ref = self._pose_mundo_modelo()
                silhuetas_saida = [
                    (
                        Point3(world_pos.x - 0.045, world_pos.y + 0.12, world_pos.z + 0.06),
                        world_hpr,
                        pal["secundaria"],
                        scale_ref,
                        0.32,
                    ),
                    (
                        Point3(world_pos.x + 0.045, world_pos.y + 0.18, world_pos.z - 0.06),
                        world_hpr,
                        pal["primaria"],
                        scale_ref,
                        0.42,
                    ),
                ]
        elif style == "portal_pull_out":
            tint = pal["primaria"]
            flash = min(0.45, float(getattr(frame, "shock", 0.0)) * 0.42)
        else:
            tint = pal["primaria"]
            flash = frame.blue_balls * 0.26
        self._atualizar_silhuetas_fx(bool(silhuetas_saida), silhuetas_saida)
        self.set_post_effect(
            dissolve=frame.dissolve,
            dissolve_mode=mode,
            tint=tint,
            flash=flash,
        )
        center = self.exit_pivot.getPos(self.showbase.render)
        self._atualizar_cinzas_thanos(
            frame.ash,
            center,
            paleta=(
                "cyber"
                if style == "cyberpsicopata_out"
                else ("portal" if style == "portal_pull_out" else "thanos")
            ),
        )
        self._atualizar_orbes_azuis(frame.blue_balls, center)
        if self._vfx_enabled:
            prog_out = (
                self._transicao_saida_prog
                if self._transicao_saida_prog is not None
                else max(0.08, float(frame.dissolve), float(frame.explode))
            )
            self._garantir_vfx_transicoes().atualizar_saida(
                style, prog_out, getattr(self, "_visual_filter", "blockbench"), self._ancoras_transicao()
            )

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
        self._definir_acessorios_lego_visiveis(True)
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
            self.outline_np.setShaderInput(
                "outline_color",
                getattr(self, "_outline_color_rgba", (0.0, 0.0, 0.0, 1.0)),
            )
            self.outline_np.show()
        self.set_post_effect(dissolve=0.0, flash=0.0)
        self._transicao_saida_prog = None
        if self._vfx_transicoes is not None:
            self._vfx_transicoes.limpar()
        self._limpar_fx()
        self.atualizar_sombra_contato()
