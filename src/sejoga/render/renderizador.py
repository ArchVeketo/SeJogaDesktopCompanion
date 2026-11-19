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
    TransformState,
    Vec3,
)

from sejoga.animacao import danca_tuning as _danca
from sejoga.animacao import movimento_corpo_tuning as _tune
from sejoga.animacao.controlador_animacao import AnimationState
from sejoga.animacao.danca_clipes import carregar_clipe_emote
from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.animacao.squash_stretch import squash_stretch_composto
from sejoga.musica.caixa_som import BATIDAS_ARREMESSO_S
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
        self.efeitos_cena = None
        self._paineis_armario: tuple = ()
        self._raiz_tilt_rad = 0.0
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
            while not picked.isEmpty() and picked != self.model_np:
                name = picked.getName()
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
        fundo_y = min(p.y for p in pontos)
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
        from panda3d.core import AlphaTestAttrib, TransparencyAttrib

        if cand is None or cand.isEmpty():
            return
        ref_np = raiz_np if (raiz_np is not None and not raiz_np.isEmpty()) else cand.getParent()
        alpha_attr = AlphaTestAttrib.make(AlphaTestAttrib.MGreater, 0.5)
        trans_attr = TransparencyAttrib.make(TransparencyAttrib.MAlpha)

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
        from sejoga.render.efeitos_cena import GerenciadorEfeitosCena

        self.efeitos_cena = GerenciadorEfeitosCena(
            self.model_anchor,
            head_node=head_node,
            model_node=self.model_np,
        )
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
        """Cria sombra de contato estilizada no chão, compatível com color key."""
        from panda3d.core import AlphaTestAttrib, CardMaker, TransparencyAttrib

        card = CardMaker("mascot-shadow-card")
        card.setFrame(-0.5, 0.5, -0.5, 0.5)
        shadow = self.model_anchor.attachNewNode(card.generate())
        shadow.setP(-82.0)
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
        self._outline_color_rgba = (*rgb, 1.0)
        self.outline_np.setShaderInput("outline_color", self._outline_color_rgba)
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

    def disparar_flash_impacto(self, forca: float = 0.45) -> None:
        """Gancho de flash de impacto (desligado até a redefinição de VFX v2.0)."""
        del forca

    def _update_outline_breath(self, dt, motion) -> None:
        """Modula apenas a espessura do contorno pela respiração do tórax, por frame."""
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
                if group_name == "door":
                    outline_node.hide()
        self._aplicar_squash_stretch()
        self._atualizar_sombra_contato()

    def _atualizar_sombra_contato(self) -> None:
        """Posiciona e escala a sombra de contato no chão conforme apoio e pose."""
        if self._shadow_np is None or self.model_np is None:
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
            and self._subida_palco.value > 0.12
        )
        sleeping_lying = bool(
            controller
            and controller.state == AnimationState.SLEEP
            and getattr(controller, "modo_sono", "") == "deitado"
        )
        if dancing_stage or sleeping_lying:
            self._shadow_np.hide()
            return
        # v2.0: sombra encolhe suavemente no ar em vez de sumir num corte seco!
        fator_ar = 1.0 if self._is_grounded else max(0.0, 1.0 - abs(self._physics_velocity[1]) / 1200.0) * 0.62
        if fator_ar <= 0.08:
            self._shadow_np.hide()
            return
        self._shadow_np.show()
        scale = self.model_np.getSz()
        left_foot = self._rig_nodes.get("left-feet")
        right_foot = self._rig_nodes.get("right-feet")
        b_left = left_foot.getTightBounds(self.model_anchor) if left_foot else None
        b_right = right_foot.getTightBounds(self.model_anchor) if right_foot else None
        if b_left and b_right:
            z_sola = min(b_left[0].z, b_right[0].z)
            x_centro = 0.5 * (
                (b_left[0].x + b_left[1].x) * 0.5 + (b_right[0].x + b_right[1].x) * 0.5
            )
            largura_pes = max(b_left[1].x, b_right[1].x) - min(b_left[0].x, b_right[0].x)
        else:
            b_mod = self.model_np.getTightBounds(self.model_anchor)
            z_sola = b_mod[0].z if b_mod else (self._model_min_z * scale)
            x_centro = 0.0
            largura_pes = float(self._model_dimensions.x) * scale * 0.55

        # Acompanha squash lateral se ativo
        sx = self._squash_pivot.getSx() if self._squash_pivot is not None else 1.0
        sy = self._squash_pivot.getSy() if self._squash_pivot is not None else 1.0
        base_w = max(0.42, largura_pes * 1.28) * sx * fator_ar
        base_d = max(0.24, float(self._model_dimensions.y) * scale * 0.72) * sy * fator_ar
        self._shadow_np.setPos(x_centro, -0.02, z_sola - 0.012)
        # CardMaker gera o cartão em XZ; sob setP(-82), o eixo Z local controla a profundidade.
        self._shadow_np.setScale(base_w, 1.0, base_d)

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
            "reacao_tempo": float(getattr(controller, "_reaction_time", 0.0)),
            "reacao_duracao": reacao_dur,
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
    ) -> None:
        np, pos_orig, esc_orig, centro, eixo, eh_outline = item
        if eh_outline:
            np.hide()
            return
        if not argolas_ativas and not modo_musical:
            # v2.0: levitação ambiente sutil nas argolas (sempre vivas, nunca congeladas!)
            eh_sup = "sup" in np.getName() or abs(centro.z) > 0.086
            fase_amb = pulso_t * 2.1 + idx_arg * 1.15
            dz_amb = math.sin(fase_amb) * (0.006 if eh_sup else -0.005)
            np.show()
            np.setPos(pos_orig + eixo * dz_amb)
            np.setScale(esc_orig)
            np.clearColorScale()
            return
        eh_sup = "sup" in np.getName() or abs(centro.z) > 0.086
        if argolas_ativas:
            dz = amostra.deslocamento_argola_sup if eh_sup else amostra.deslocamento_argola_inf
            s = max(0.01, amostra.escala_argolas)
            brilho = amostra.brilho_argolas
        else:
            # No modo música, move em direções opostas e só brilha nos picos da batida.
            onda = math.sin(beat_phase)
            mag = (abs(onda) ** 0.75) * ((0.032 if eh_sup else -0.040) if onda >= 0.0 else (-0.014 if eh_sup else 0.014))
            dz = mag
            beat_peak = max(0.0, math.sin(beat_phase)) ** 4
            s = 1.0 + 0.14 * beat_peak
            brilho = beat_peak * 0.95
        np.setPos(centro + (pos_orig - centro) * s + eixo * dz)
        np.setScale(esc_orig * s)
        (np.hide if s < 0.05 else np.show)()
        if brilho > 0.05:
            np.setColorScale(
                1.0 + 1.15 * brilho,
                1.0 + 0.94 * brilho,
                1.0 + 0.14 * brilho,
                1.0,
            )
        else:
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
        dancing = bool(getattr(ctrl, "music_active", False))
        choque = bool(argolas_ativas and getattr(amostra, "choque_argolas", False))
        cena_musical = bool(
            amostra is not None
            and amostra.ativa
            and amostra.nome in ("escutar_fone", "batida_guardada", "groove_um_pe", "checar_walkman")
        )
        modo_musical = dancing or cena_musical
        beat_phase = float(getattr(ctrl.dance_motion, "phase", pulso_t * 4.5)) if dancing else pulso_t * 4.5
        for idx_arg, item in enumerate(getattr(self, "_argolas_antena", ())):
            self._atualizar_argola_fisica(
                item,
                argolas_ativas,
                amostra,
                pulso_t,
                idx_arg,
                modo_musical=modo_musical,
                beat_phase=beat_phase,
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
        # Todos os efeitos de cena (2D/grafite/choque) limpos para redefinição do zero na v2.0.
        efeitos = getattr(self, "efeitos_cena", None)
        if efeitos is not None:
            efeitos.limpar()
        if self._choque_antenas_3d is not None:
            self._choque_antenas_3d.ocultar()

    def _coletar_caixas_som_pos(self, estado: str) -> tuple[Vec3, ...]:
        speaker = getattr(self, "music_speaker", None)
        if estado != "dance" or speaker is None or speaker.root.isHidden():
            return ()
        caixas_pos: list[Vec3] = []
        for box, (low, high) in zip(speaker.boxes, speaker.bounds, strict=True):
            if box.isHidden():
                continue
            mid_z = (low.z + high.z) * 0.55
            offsets_x = (
                (low.x, high.x)
                if (high.x - low.x) > 1.0
                else ((low.x + high.x) * 0.5,)
            )
            for ox in offsets_x:
                p = self.efeitos_cena.root.getRelativePoint(box, Vec3(ox, low.y, mid_z))
                p.y = -2.20
                caixas_pos.append(p)
        return tuple(caixas_pos)

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
                and getattr(ctrl.dance_motion, "strength", 0.0) > 1.15
            ),
            "forca_impacto": max(
                1.45 if heavy_land else 0.9, float(getattr(motion, "impact", 0.0))
            ),
            "deslizando": bool(
                estado == "virtual_insanity" or (grounded and abs(vel[0]) > 500.0)
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
        }

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
        self._atualizar_efeitos_e_argolas(dt, motion, grounded)
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
            tilt_rad = float(getattr(self, "_raiz_tilt_rad", 0.0))
            peso_solo = max(0.0, 1.0 - min(1.0, tilt_rad / 0.60))
            base_solo = self.lower_body.ground_offset * peso_solo
            self._suspension_pivot.setZ((base_solo + dz_extra) * scale)
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
        if (
            not dragging
            and controller
            and controller.state == AnimationState.DANCE
            and controller.dance_motion.style == "breakdance"
            and not eh_emote_clipe
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
            q_id = Quat.identQuat()
            if q.dot(q_id) < 0.0:
                q = -q
            q = q_id * (1.0 - peso_quat) + q * peso_quat
            q.normalize()
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
        self._raiz_tilt_rad = 0.0
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

    def _interromper_cobertura_roupa(self) -> None:
        if self._tempo_cobertura <= 0 and not self._cobertura_roupa:
            return
        self._tempo_cobertura = 0.0
        for limb in self._cobertura_roupa:
            self.tentacle_pool.release(limb)
        self._cobertura_roupa.clear()

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
            out_door = self._outline_nodes.get("door")
            if out_door:
                out_door.hide()
        debug = getattr(self.showbase, "debug_tools", None)
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

    def trocar_caixa_de_som(self, estilo: str) -> None:
        """Recria o palco com a seleção atual e libera os nós da seleção anterior."""
        from sejoga.musica.caixa_som import MusicSpeaker

        anterior = self.music_speaker
        self.music_speaker = MusicSpeaker(self, estilo)
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

    def set_post_effect(
        self,
        dissolve: float = 0.0,
        dissolve_mode: str = "uniform",
        tint: tuple[float, float, float] = (0.10, 0.65, 1.00),
        flash: float = 0.0,
    ) -> None:
        """Atualiza uniforms do shader de pós-processamento (dissolução e brilho)."""
        pipeline = getattr(self, "_pbr_pipeline", None)
        if pipeline is None or not self._use_chroma_resolve:
            return
        quad = pipeline._post_process_quad
        dissolve_val = float(max(0.0, min(1.0, dissolve)))
        mode_val = (
            2.0
            if dissolve_mode == "cyberpsicopata"
            else (1.0 if dissolve_mode == "thanos" else 0.0)
        )
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

    def prewarm_intro_effects(self, style: str) -> None:
        """Pré-aloca nós/shaders pesados da abertura para evitar engasgos no frame 1."""
        if self.model_np is None:
            return
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
        for idx, flake in enumerate(self._fx_ash_nodes):
            delay = (idx / count) * 0.55
            local_p = max(0.0, min(1.0, (ash - delay * 0.6) / max(0.25, 1.0 - delay * 0.6)))
            if local_p <= 0.0 or local_p >= 0.98:
                flake.hide()
                continue
            flake.show()
            if paleta == "cyber":
                cor = (0.98, 0.16, 0.28, 1.0) if idx % 2 == 0 else (0.10, 0.96, 1.0, 1.0)
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
                halo.setTransparency(1)
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
        if frame.dissolve >= 0.96 and frame.smoke_burst > 0.05:
            self.model_np.hide()
            self.outline_np.hide()
            self.set_post_effect(dissolve=0.0)
            return
        self.model_np.show()
        if self._outline_enabled:
            self.outline_np.show()
        self.set_post_effect(dissolve=frame.dissolve, dissolve_mode="uniform")

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
        units = float(self._view_height / max(1, self.height))
        foot_comp = self._intro_orig_foot_local_z * (1.0 - scale)
        offset_x_u = frame.offset_x * units if apply_horizontal_offset else 0.0
        self.model_anchor.setPos(
            base_pos.x + offset_x_u,
            base_pos.y,
            base_pos.z - frame.offset_y * units + foot_comp,
        )
        self.model_anchor.setScale(scale)
        self.model_anchor.setHpr(frame.yaw, frame.pitch, frame.roll)
        self._atualizar_fumaca_ninja(frame.smoke_burst, self._centro_efeito_intro())
        afterimage = float(getattr(frame, "afterimage", 0.0))
        if (afterimage > 0.02 or self._sandevistan_stamps) and self.model_np is not None:
            self._atualizar_sandevistan_intro(afterimage, desktop_pos, units)
        else:
            self._atualizar_silhuetas_fx(False, [])

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
            if self._intro_orig_anchor_pos is not None:
                self.model_anchor.setPos(self._intro_orig_anchor_pos)
            self.model_anchor.setScale(1.0)
            self.model_anchor.setHpr(0.0, 0.0, 0.0)
        self._intro_orig_anchor_pos = None
        self._intro_orig_foot_local_z = None
        self._sandevistan_stamps.clear()
        self.set_post_effect(dissolve=0.0, flash=0.0)
        self._limpar_fx()

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
        self.exit_pivot.setScale(max(0.05, frame.scale))

        if style == "lego_disassemble" and frame.explode > 0.0:
            if not self._lego_snapshot:
                self._iniciar_lego_scatter(getattr(self, "_lego_floor_world_z", None))
            self._atualizar_lego_scatter(frame.explode)

        mode = (
            "cyberpsicopata"
            if style == "cyberpsicopata_out"
            else ("thanos" if style == "thanos_snap" else "uniform")
        )
        silhuetas_saida: list[tuple] = []
        if style == "fnf_blue_balls":
            tint, flash = self._fx_saida_fnf(frame)
        elif style == "cyberpsicopata_out":
            tint, flash, silhuetas_saida = self._fx_saida_cyberpsicopata(frame, units)
        else:
            tint = (0.08, 0.68, 1.0)
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
            paleta="cyber" if style == "cyberpsicopata_out" else "thanos",
        )
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
        self._limpar_fx()
