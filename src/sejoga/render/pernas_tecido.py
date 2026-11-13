"""Malha contínua de calça em tecido low-poly para as pernas do rig."""

from __future__ import annotations

import math
from dataclasses import dataclass

from panda3d.core import (
    CullFaceAttrib,
    Geom,
    GeomEnums,
    GeomNode,
    GeomTriangles,
    GeomVertexArrayFormat,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexReader,
    GeomVertexWriter,
    InternalName,
    Mat4,
    NodePath,
    Point3,
    Quat,
    Vec2,
    Vec3,
)

from sejoga.animacao.movimento_corpo import Spring

_NAO_ESCONDER_FILHOS = frozenset(
    {
        "joelho-direito",
        "canela-direita",
        "joelho-esquerdo",
        "canela-esquerda",
    }
)
_UV_TECIDO_PADRAO = Vec2(0.23, 0.825)
_UV_SOMBRA_PADRAO = Vec2(0.41, 0.765)


def _ordenar_anel_ccw(
    pontos: list[Vec3], referencia: list[Vec3] | None = None
) -> list[Vec3]:
    """Ordena 4 cantos em sentido anti-horário no plano XY e alinha com `referencia`."""
    centro = sum(pontos, Vec3(0, 0, 0)) * (1.0 / max(1, len(pontos)))
    ordenados = sorted(pontos, key=lambda p: math.atan2(p.y - centro.y, p.x - centro.x))
    if referencia:
        melhor_rot = min(
            range(len(ordenados)),
            key=lambda shift: sum(
                (ordenados[(i + shift) % len(ordenados)] - referencia[i]).lengthSquared()
                for i in range(len(ordenados))
            ),
        )
        ordenados = [ordenados[(i + melhor_rot) % len(ordenados)] for i in range(len(ordenados))]
    return ordenados


def _acumular_vdata(
    gn: NodePath,
    vdata: GeomVertexData,
    legs: NodePath,
    unicos: list[Vec3],
    amostras: list[tuple[Vec3, Vec3, Vec2]],
) -> None:
    """Acumula vértices únicos e amostras `(pos, normal, uv)` de um `GeomVertexData`."""
    vr = GeomVertexReader(vdata, "vertex")
    nr = GeomVertexReader(vdata, "normal") if vdata.hasColumn("normal") else None
    uv_col = "texcoord.0" if vdata.hasColumn("texcoord.0") else "texcoord"
    uvr = GeomVertexReader(vdata, uv_col) if vdata.hasColumn(uv_col) else None
    while not vr.isAtEnd():
        pos = legs.getRelativePoint(gn, vr.getData3())
        normal = legs.getRelativeVector(gn, nr.getData3()) if nr else Vec3(0, -1, 0)
        uv = Vec2(uvr.getData2()) if uvr else Vec2(_UV_TECIDO_PADRAO)
        amostras.append((pos, normal, uv))
        if not any((pos - p).lengthSquared() < 1e-7 for p in unicos):
            unicos.append(pos)


def _pontos_unicos_em_legs(
    raiz_peca: NodePath, legs: NodePath
) -> tuple[list[Vec3], list[tuple[Vec3, Vec3, Vec2]]]:
    """Lê os vértices únicos e amostras `(pos, normal, uv)` da peça no espaço de `legs`."""
    unicos: list[Vec3] = []
    amostras: list[tuple[Vec3, Vec3, Vec2]] = []
    for child in raiz_peca.getChildren():
        if child.getName() in _NAO_ESCONDER_FILHOS:
            continue
        for gn in child.findAllMatches("**/+GeomNode"):
            node = gn.node()
            for gi in range(node.getNumGeoms()):
                _acumular_vdata(gn, node.getGeom(gi).getVertexData(), legs, unicos, amostras)
    return unicos, amostras


def _separar_topo_e_base(pontos: list[Vec3]) -> tuple[list[Vec3], list[Vec3]]:
    """Separa os 8 cantos em anel superior (4) e inferior (4) pareando os 4 pilares em XY."""
    restantes = list(pontos)
    topo: list[Vec3] = []
    base: list[Vec3] = []
    while len(restantes) >= 2:
        p0 = restantes.pop(0)
        j = min(
            range(len(restantes)),
            key=lambda idx: (
                (restantes[idx].x - p0.x) ** 2 + (restantes[idx].y - p0.y) ** 2
            ),
        )
        p1 = restantes.pop(j)
        if p0.z >= p1.z:
            topo.append(p0)
            base.append(p1)
        else:
            topo.append(p1)
            base.append(p0)
    return topo, base


def _expandir_octogono_tecido(corners: list[Vec3], chanfro_meio: float = 0.0) -> list[Vec3]:
    """Converte 4 cantos em anel de 8 vértices (cantos + costuras centrais)."""
    centro = sum(corners, Vec3(0, 0, 0)) * 0.25
    anel: list[Vec3] = []
    for i in range(4):
        c0 = corners[i]
        c1 = corners[(i + 1) % 4]
        anel.append(c0)
        meio = (c0 + c1) * 0.5
        if chanfro_meio != 0.0:
            radial = Vec3(meio.x - centro.x, meio.y - centro.y, 0.0)
            if radial.lengthSquared() > 1e-10:
                radial.normalize()
                meio += radial * chanfro_meio
        anel.append(meio)
    return anel


def _interpolar_anel(a: list[Vec3], b: list[Vec3], t: float) -> list[Vec3]:
    return [pa * (1.0 - t) + pb * t for pa, pb in zip(a, b, strict=True)]


def _encolher_e_deslocar(
    anel: list[Vec3], escala_xy: float, dz: float
) -> list[Vec3]:
    centro = sum(anel, Vec3(0, 0, 0)) * (1.0 / len(anel))
    return [
        Vec3(
            centro.x + (p.x - centro.x) * escala_xy,
            centro.y + (p.y - centro.y) * escala_xy,
            p.z + dz,
        )
        for p in anel
    ]


def _extrair_uvs_tecido(amostras: list[tuple[Vec3, Vec3, Vec2]]) -> tuple[Vec2, Vec2]:
    """Retorna UVs limpas do roxo principal da calça e do roxo escuro de sombra/dobra."""
    _ = amostras
    return Vec2(_UV_TECIDO_PADRAO), Vec2(_UV_SOMBRA_PADRAO)


def _formato_vertice_tecido(uv_name: str) -> GeomVertexFormat:
    arr = GeomVertexArrayFormat()
    arr.addColumn(InternalName.getVertex(), 3, GeomEnums.NTFloat32, GeomEnums.CPoint)
    arr.addColumn(InternalName.getNormal(), 3, GeomEnums.NTFloat32, GeomEnums.CNormal)
    arr.addColumn(InternalName.make(uv_name), 2, GeomEnums.NTFloat32, GeomEnums.CTexcoord)
    fmt = GeomVertexFormat()
    fmt.addArray(arr)
    return GeomVertexFormat.registerFormat(fmt)


def _formato_vertice_contorno(uv_name: str) -> GeomVertexFormat:
    return _formato_vertice_tecido(uv_name)


def _mat_para_dq(mat: Mat4, ref_r: Quat | None = None) -> tuple[Quat, Quat]:
    """Converte transformação rígida `Mat4` do Panda3D em Dual Quaternion `(q_r, q_d)`."""
    q_r = Quat()
    q_r.setFromMatrix(mat.getUpper3())
    q_r.normalize()
    if ref_r is not None and q_r.dot(ref_r) < 0.0:
        q_r = -q_r
    t = mat.getRow3(3)
    q_d = Quat(0.0, t.x, t.y, t.z) * q_r * 0.5
    return q_r, q_d


def _dq_blend_mat(
    dqs: tuple[tuple[Quat, Quat], ...],
    pesos: tuple[float, float, float, float],
) -> Mat4:
    """Mistura até 4 ossos via Dual Quaternion Skinning preservando 100% do volume."""
    sum_r = Quat(0.0, 0.0, 0.0, 0.0)
    sum_d = Quat(0.0, 0.0, 0.0, 0.0)
    ref: Quat | None = None
    for (qr, qd), w in zip(dqs, pesos, strict=True):
        if w <= 1e-6:
            continue
        if ref is None:
            ref = qr
        elif qr.dot(ref) < 0.0:
            qr = -qr
            qd = -qd
        sum_r += qr * w
        sum_d += qd * w
    norm_r = sum_r.length()
    if norm_r <= 1e-8:
        return Mat4.identMat()
    inv_len = 1.0 / norm_r
    qr_n = sum_r * inv_len
    qd_n = sum_d * inv_len
    # Garante ortogonalidade Plücker (qr · qd = 0) para translação rígida exata.
    qd_n -= qr_n * qr_n.dot(qd_n)
    t_q = (qd_n * 2.0) * qr_n.conjugate()
    out = Mat4()
    qr_n.extractToMatrix(out)
    out.setRow(3, Vec3(t_q.getI(), t_q.getJ(), t_q.getK()))
    return out


@dataclass(slots=True)
class _VerticeTecido:
    pos_rest: Vec3
    pesos_ossos: tuple[float, float, float, float]  # (torso, coxa, joelho, canela)
    ring_idx: int
    ring_side: int
    hem_weight: float
    knee_front_weight: float
    knee_back_weight: float
    hip_fold_weight: float
    pleat_offset: Vec3


@dataclass
class _PernaMalha:
    lado: str
    coxa_nome: str
    joelho_nome: str
    canela_nome: str
    origem_em_legs: Point3
    t_rest_inv: dict[str, Mat4]
    rings_verts: list[list[_VerticeTecido]]  # 10 anéis x 8 vértices
    top_center: _VerticeTecido
    bot_center: _VerticeTecido
    vis_vdata: GeomVertexData
    out_vdata: GeomVertexData | None
    uv_cloth: Vec2
    uv_shadow: Vec2
    quad_indices: list[tuple[int, int]]  # índice linear de cada anel/lado nos quads
    hem_pitch_spring: Spring
    hem_roll_spring: Spring
    prev_shin_pitch: float = 0.0
    prev_knee_deg: float = 0.0
    vis_node: NodePath | None = None
    out_node: NodePath | None = None


class PernasTecido:
    """Substitui blocos abertos da calça por mangas contínuas fechadas com dobra e balanço de tecido."""

    def __init__(self, renderer, lados: list[dict]) -> None:
        """Constrói as duas mangas de tecido a partir dos grupos inferiores do rig."""
        self._legs = renderer.model_np.find("**/legs")
        self._outline_legs = (
            renderer.outline_np.find("**/legs")
            if getattr(renderer, "outline_np", None) is not None
            else None
        )
        self._pernas: list[_PernaMalha] = []
        if self._legs.isEmpty():
            return
        for dados in lados:
            perna = self._construir_perna(renderer, dados)
            if perna is not None:
                self._pernas.append(perna)
                self._esconder_blocos_rigidos(renderer, dados["nomes"][:3])

    @staticmethod
    def _ler_estado_base_geom(n_coxa: NodePath):
        """Extrai RenderState e nome da coluna de UV da geometria original da coxa."""
        for child in n_coxa.getChildren():
            if child.getName() in _NAO_ESCONDER_FILHOS:
                continue
            for gn in child.findAllMatches("**/+GeomNode"):
                orig_state = gn.node().getGeomState(0)
                vd = gn.node().getGeom(0).getVertexData()
                uv_col_name = "texcoord.0" if vd.hasColumn("texcoord.0") else "texcoord"
                return orig_state, uv_col_name
        return None, "texcoord.0"

    @staticmethod
    def _especificar_aneis_tecido(
        pts_coxa: list[Vec3], pts_joelho: list[Vec3], pts_canela: list[Vec3]
    ) -> list[tuple[list[Vec3], tuple[float, float, float, float], float]]:
        """Constrói os 10 anéis octogonais do quadril até a dobra interna da barra."""
        coxa_top_raw, _ = _separar_topo_e_base(pts_coxa)
        joelho_top_raw, joelho_bot_raw = _separar_topo_e_base(pts_joelho)
        _, canela_bot_raw = _separar_topo_e_base(pts_canela)

        r_hip = _ordenar_anel_ccw(coxa_top_raw)
        r_k_top = _ordenar_anel_ccw(joelho_top_raw, r_hip)
        r_k_bot = _ordenar_anel_ccw(joelho_bot_raw, r_k_top)
        r_cuff = _ordenar_anel_ccw(canela_bot_raw, r_k_bot)

        return [
            (_expandir_octogono_tecido(_encolher_e_deslocar(r_hip, 0.86, +0.024), chanfro_meio=0.002), (0.45, 0.55, 0.00, 0.00), 0.00),
            (_expandir_octogono_tecido(_encolher_e_deslocar(r_hip, 0.96, -0.006), chanfro_meio=0.003), (0.12, 0.88, 0.00, 0.00), 0.00),
            (_expandir_octogono_tecido(_interpolar_anel(r_hip, r_k_top, 0.36), chanfro_meio=0.005), (0.00, 0.78, 0.22, 0.00), 0.00),
            (_expandir_octogono_tecido(_interpolar_anel(r_hip, r_k_top, 0.70), chanfro_meio=0.004), (0.00, 0.42, 0.56, 0.02), 0.00),
            (_expandir_octogono_tecido(_interpolar_anel(r_k_top, r_k_bot, 0.50), chanfro_meio=0.006), (0.00, 0.08, 0.72, 0.20), 0.00),
            (_expandir_octogono_tecido(_interpolar_anel(r_k_bot, r_cuff, 0.24), chanfro_meio=0.004), (0.00, 0.00, 0.46, 0.54), 0.10),
            (_expandir_octogono_tecido(_interpolar_anel(r_k_bot, r_cuff, 0.52), chanfro_meio=0.005), (0.00, 0.00, 0.15, 0.85), 0.34),
            (_expandir_octogono_tecido(_interpolar_anel(r_k_bot, r_cuff, 0.78), chanfro_meio=0.005), (0.00, 0.00, 0.00, 1.00), 0.70),
            (_expandir_octogono_tecido(r_cuff, chanfro_meio=0.004), (0.00, 0.00, 0.00, 1.00), 1.00),
            (_expandir_octogono_tecido(_encolher_e_deslocar(r_cuff, 0.46, +0.030), chanfro_meio=0.0), (0.00, 0.00, 0.00, 1.00), 0.85),
        ]

    @staticmethod
    def _criar_vertices_anel(
        specs: list[tuple[list[Vec3], tuple[float, float, float, float], float]],
        origem: Point3,
    ) -> tuple[list[list[_VerticeTecido]], _VerticeTecido, _VerticeTecido]:
        """Converte especificações de anéis em `_VerticeTecido` e cria centros das tampas."""
        rings_verts: list[list[_VerticeTecido]] = []
        for r_idx, (pts, pesos, hem_w) in enumerate(specs):
            centro_xy = sum(pts, Vec3(0, 0, 0)) * (1.0 / len(pts))
            knee_band = max(0.0, 1.0 - abs(r_idx - 4.2) / 2.6)
            hip_band = max(0.0, 1.0 - abs(r_idx - 1.2) / 1.4)
            linha: list[_VerticeTecido] = []
            for s_idx, pt in enumerate(pts):
                dir_xy = Vec3(pt.x - centro_xy.x, pt.y - centro_xy.y, 0.0)
                if dir_xy.lengthSquared() > 1e-10:
                    dir_xy.normalize()
                pleat_amp = (
                    (0.0038 if (r_idx % 2 == 0) else -0.0032) * (1.0 if s_idx % 2 == 1 else -0.35)
                    if 2 <= r_idx <= 7
                    else 0.0
                )
                linha.append(
                    _VerticeTecido(
                        pos_rest=pt - Vec3(origem),
                        pesos_ossos=pesos,
                        ring_idx=r_idx,
                        ring_side=s_idx,
                        hem_weight=hem_w,
                        knee_front_weight=knee_band * max(0.0, dir_xy.y),
                        knee_back_weight=knee_band * max(0.0, -dir_xy.y),
                        hip_fold_weight=hip_band * max(0.0, dir_xy.y),
                        pleat_offset=Vec3(dir_xy.x * pleat_amp, dir_xy.y * pleat_amp, 0.0),
                    )
                )
            rings_verts.append(linha)

        top_pt = sum(specs[0][0], Vec3(0, 0, 0)) * (1.0 / 8.0) - Vec3(origem)
        bot_pt = sum(specs[-1][0], Vec3(0, 0, 0)) * (1.0 / 8.0) - Vec3(origem)
        top_center = _VerticeTecido(
            pos_rest=top_pt, pesos_ossos=(0.45, 0.55, 0.00, 0.00), ring_idx=0, ring_side=-1,
            hem_weight=0.0, knee_front_weight=0.0, knee_back_weight=0.0, hip_fold_weight=0.0, pleat_offset=Vec3(0, 0, 0),
        )
        bot_center = _VerticeTecido(
            pos_rest=bot_pt, pesos_ossos=(0.00, 0.00, 0.00, 1.00), ring_idx=9, ring_side=-1,
            hem_weight=0.85, knee_front_weight=0.0, knee_back_weight=0.0, hip_fold_weight=0.0, pleat_offset=Vec3(0, 0, 0),
        )
        return rings_verts, top_center, bot_center

    def _criar_malha_visivel(
        self, lado: str, orig_state, uv_col_name: str, origem: Point3, n_strips: int, n_sides: int
    ) -> tuple[GeomVertexData, list[tuple[int, int]], NodePath]:
        """Monta o `GeomNode` visível facetado da perna com culling horário preservado."""
        vis_fmt = _formato_vertice_tecido(uv_col_name)
        vis_vdata = GeomVertexData(f"perna-tecido-{lado}", vis_fmt, Geom.UHDynamic)
        vis_vdata.uncleanSetNumRows(n_strips * n_sides * 4 + 2 * n_sides * 3)
        vis_tris = GeomTriangles(Geom.UHStatic)
        quad_indices: list[tuple[int, int]] = []
        v_cursor = 0
        for r_idx in range(n_strips):
            for s_idx in range(n_sides):
                vis_tris.addVertices(v_cursor, v_cursor + 1, v_cursor + 2)
                vis_tris.addVertices(v_cursor, v_cursor + 2, v_cursor + 3)
                quad_indices.append((r_idx, s_idx))
                v_cursor += 4
        for _ in range(n_sides * 2):
            vis_tris.addVertices(v_cursor, v_cursor + 1, v_cursor + 2)
            v_cursor += 3
        vis_tris.closePrimitive()
        vis_geom = Geom(vis_vdata)
        vis_geom.addPrimitive(vis_tris)
        vis_state = orig_state.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullClockwise))
        vis_gn = GeomNode(f"perna-tecido-{lado}")
        vis_gn.addGeom(vis_geom, vis_state)
        vis_node = self._legs.attachNewNode(vis_gn)
        vis_node.setPos(origem)
        return vis_vdata, quad_indices, vis_node

    @staticmethod
    def _obter_estado_contorno(renderer, coxa_nome: str):
        """Extrai o RenderState do contorno original da coxa sem atributo de cull."""
        out_coxa = renderer._outline_nodes.get(coxa_nome)
        if out_coxa is None or out_coxa.isEmpty():
            return None
        for child in out_coxa.getChildren():
            if child.getName() in _NAO_ESCONDER_FILHOS:
                continue
            for gnode_np in child.findAllMatches("**/+GeomNode"):
                return gnode_np.node().getGeomState(0).removeAttrib(CullFaceAttrib.getClassType())
        return None

    def _criar_malha_contorno(
        self, renderer, lado: str, coxa_nome: str, uv_col_name: str, origem: Point3, n_sides: int
    ) -> tuple[GeomVertexData | None, NodePath | None]:
        """Cria a malha suave auxiliar para o passe de silhueta da calça."""
        if self._outline_legs is None or self._outline_legs.isEmpty():
            return None, None
        out_rings = 8  # índices 1..8
        out_vdata = GeomVertexData(f"perna-tecido-{lado}-out", _formato_vertice_contorno(uv_col_name), Geom.UHDynamic)
        out_vdata.uncleanSetNumRows(out_rings * n_sides)
        out_tris = GeomTriangles(Geom.UHStatic)
        for r_idx in range(out_rings - 1):
            for s_idx in range(n_sides):
                nxt = (s_idx + 1) % n_sides
                a, b = r_idx * n_sides + s_idx, (r_idx + 1) * n_sides + s_idx
                c, d = (r_idx + 1) * n_sides + nxt, r_idx * n_sides + nxt
                out_tris.addVertices(a, b, c)
                out_tris.addVertices(a, c, d)
        out_tris.closePrimitive()
        out_geom = Geom(out_vdata)
        out_geom.addPrimitive(out_tris)
        out_gn = GeomNode(f"perna-tecido-{lado}-outline")
        out_state = self._obter_estado_contorno(renderer, coxa_nome)
        out_gn.addGeom(out_geom, out_state) if out_state is not None else out_gn.addGeom(out_geom)
        out_node = self._outline_legs.attachNewNode(out_gn)
        out_node.setPos(origem)
        return out_vdata, out_node

    def _construir_perna(self, renderer, dados: dict) -> _PernaMalha | None:
        """Constrói toda a malha e o estado dinâmico de uma perna de tecido."""
        coxa_nome, joelho_nome, canela_nome, _ = dados["nomes"]
        r_nodes = renderer._rig_nodes
        n_coxa, n_joelho, n_canela = r_nodes.get(coxa_nome), r_nodes.get(joelho_nome), r_nodes.get(canela_nome)
        if any(n is None or n.isEmpty() for n in (n_coxa, n_joelho, n_canela)):
            return None

        pts_coxa, amostras_coxa = _pontos_unicos_em_legs(n_coxa, self._legs)
        pts_joelho, _ = _pontos_unicos_em_legs(n_joelho, self._legs)
        pts_canela, _ = _pontos_unicos_em_legs(n_canela, self._legs)
        if len(pts_coxa) < 8 or len(pts_joelho) < 8 or len(pts_canela) < 8:
            return None

        orig_state, uv_col_name = self._ler_estado_base_geom(n_coxa)
        if orig_state is None:
            return None

        uv_cloth, uv_shadow = _extrair_uvs_tecido(amostras_coxa)
        specs = self._especificar_aneis_tecido(pts_coxa, pts_joelho, pts_canela)
        origem = Point3(n_coxa.getPos(self._legs))
        t_rest_inv: dict[str, Mat4] = {}
        for nome, np_node in ((coxa_nome, n_coxa), (joelho_nome, n_joelho), (canela_nome, n_canela)):
            inv = Mat4(np_node.getMat(self._legs))
            inv.invertInPlace()
            t_rest_inv[nome] = inv

        rings_verts, top_center, bot_center = self._criar_vertices_anel(specs, origem)
        vis_vdata, quad_indices, vis_node = self._criar_malha_visivel(
            dados["lado"], orig_state, uv_col_name, origem, len(rings_verts) - 1, 8
        )
        out_vdata, out_node = self._criar_malha_contorno(
            renderer, dados["lado"], coxa_nome, uv_col_name, origem, 8
        )
        perna = _PernaMalha(
            lado=dados["lado"], coxa_nome=coxa_nome, joelho_nome=joelho_nome, canela_nome=canela_nome,
            origem_em_legs=origem, t_rest_inv=t_rest_inv, rings_verts=rings_verts, top_center=top_center,
            bot_center=bot_center, vis_vdata=vis_vdata, out_vdata=out_vdata, uv_cloth=uv_cloth,
            uv_shadow=uv_shadow, quad_indices=quad_indices, hem_pitch_spring=Spring(frequency=4.4, damping=0.52),
            hem_roll_spring=Spring(frequency=4.0, damping=0.58), vis_node=vis_node, out_node=out_node,
        )
        self._escrever_uvs_iniciais(perna, uv_col_name)
        self._atualizar_perna(renderer, perna, 0.0, 0.0, 0.0, 0.0, 0.0)
        return perna

    def _escrever_uvs_iniciais(self, perna: _PernaMalha, uv_col_name: str) -> None:
        uvw = GeomVertexWriter(perna.vis_vdata, uv_col_name)
        n_strips = len(perna.rings_verts) - 1
        for r_idx in range(n_strips):
            # A faixa mais baixa (8 -> cuff para dobra interna) usa tom de sombra interno.
            uv = perna.uv_shadow if r_idx == n_strips - 1 else perna.uv_cloth
            for _ in range(8 * 4):
                uvw.setData2(uv)
        for _ in range(8 * 3 * 2):
            uvw.setData2(perna.uv_shadow)
        if perna.out_vdata is not None:
            ouvw = GeomVertexWriter(perna.out_vdata, uv_col_name)
            for _ in range(8 * 8):
                ouvw.setData2(perna.uv_cloth)

    @staticmethod
    def _ocultar_geoms_no(no: NodePath | None) -> None:
        """Oculta os nós de geometria filhos preservando a hierarquia articular."""
        if no is None or no.isEmpty():
            return
        for child in no.getChildren():
            if child.getName() not in _NAO_ESCONDER_FILHOS:
                child.stash()

    def _esconder_blocos_rigidos(
        self, renderer, nomes_perna: tuple[str, str, str]
    ) -> None:
        for base in (renderer._rig_nodes, renderer._outline_nodes):
            for nome in nomes_perna:
                self._ocultar_geoms_no(base.get(nome))

    def set_lego_mode(self, renderer, ativo: bool) -> None:
        """Alterna entre as mangas de tecido e os blocos rígidos do modo LEGO."""
        for perna in self._pernas:
            for node in (perna.vis_node, perna.out_node):
                if node is not None and not node.isEmpty():
                    node.hide() if ativo else node.show()
            nomes = (perna.coxa_nome, perna.joelho_nome, perna.canela_nome)
            if ativo:
                self._mostrar_blocos_rigidos(renderer, nomes)
            else:
                self._esconder_blocos_rigidos(renderer, nomes)

    @staticmethod
    def _mostrar_blocos_rigidos(
        renderer, nomes_perna: tuple[str, str, str]
    ) -> None:
        for base in (renderer._rig_nodes, renderer._outline_nodes):
            for nome in nomes_perna:
                no = base.get(nome)
                if no is None or no.isEmpty():
                    continue
                for child in list(no.getStashedChildren()):
                    child.unstash()

    def apply(self, renderer, pose, dt: float) -> None:
        """Atualiza skinning e dinâmica de dobra/barra de tecido para as duas pernas."""
        dt_safe = max(0.0, min(0.05, dt))
        for perna in self._pernas:
            hip_deg = float(getattr(pose, perna.lado, 0.0))
            knee_deg = float(getattr(pose, f"{perna.lado}_knee", 0.0))
            roll_deg = float(getattr(pose, f"{perna.lado}_roll", 0.0))
            self._atualizar_perna(
                renderer, perna, hip_deg, knee_deg, roll_deg, dt_safe,
                float(getattr(pose, f"{perna.lado}_lift", 0.0)),
            )

    @staticmethod
    def _atualizar_molas_barra(
        perna: _PernaMalha, hip_deg: float, knee_deg: float, roll_deg: float, dt: float
    ) -> tuple[float, float]:
        """Atualiza o atraso elástico da barra da calça pela aceleração da canela."""
        shin_pitch = hip_deg + knee_deg
        if dt > 1e-5:
            vel_shin = max(-360.0, min(360.0, (shin_pitch - perna.prev_shin_pitch) / dt))
            alvo_lag_p = max(-8.5, min(8.5, -vel_shin * 0.022))
            alvo_lag_r = max(-5.0, min(5.0, roll_deg * 0.14))
            hem_lag_p = perna.hem_pitch_spring.update(dt, alvo_lag_p)
            hem_lag_r = perna.hem_roll_spring.update(dt, alvo_lag_r)
        else:
            hem_lag_p = perna.hem_pitch_spring.value
            hem_lag_r = perna.hem_roll_spring.value
        perna.prev_shin_pitch = shin_pitch
        perna.prev_knee_deg = knee_deg
        return hem_lag_p, hem_lag_r

    def _calcular_dqs_perna(
        self, r_nodes, perna: _PernaMalha, orig_v: Vec3
    ) -> tuple[tuple[Quat, Quat], ...]:
        """Calcula os quatérnios duais locais para coxa, joelho e canela."""
        def _delta_local(nome: str) -> Mat4:
            cur = r_nodes[nome].getMat(self._legs)
            return Mat4.translateMat(orig_v) * (perna.t_rest_inv[nome] * cur) * Mat4.translateMat(-orig_v)

        dq_id = (Quat.identQuat(), Quat(0.0, 0.0, 0.0, 0.0))
        dq_coxa = _mat_para_dq(_delta_local(perna.coxa_nome), dq_id[0])
        dq_joelho = _mat_para_dq(_delta_local(perna.joelho_nome), dq_coxa[0])
        dq_canela = _mat_para_dq(_delta_local(perna.canela_nome), dq_joelho[0])
        return (dq_id, dq_coxa, dq_joelho, dq_canela)

    @staticmethod
    def _deformar_vertice_tecido(
        v: _VerticeTecido,
        mat_ring: Mat4,
        m_hem: Mat4,
        canela_piv: Vec3,
        knee_rad: float,
        hip_fwd_rad: float,
        billow: float,
    ) -> Point3:
        """Aplica pregas de dobra, blend por dual quaternion e balanço da barra."""
        p = Point3(v.pos_rest) + v.pleat_offset
        if v.knee_front_weight > 0.0 and knee_rad > 0.01:
            p.y += 0.018 * v.knee_front_weight * math.sin(knee_rad * 0.85)
        if v.knee_back_weight > 0.0 and knee_rad > 0.01:
            p.y += 0.095 * v.knee_back_weight * math.sin(knee_rad * 0.90)
        if v.hip_fold_weight > 0.0 and hip_fwd_rad > 0.02:
            p.y -= 0.012 * v.hip_fold_weight * math.sin(hip_fwd_rad * 0.85)

        ps = mat_ring.xformPoint(p)
        if v.hem_weight > 0.0:
            ps = ps * (1.0 - v.hem_weight) + m_hem.xformPoint(ps) * v.hem_weight
            f_rad = 1.0 + (billow - 1.0) * v.hem_weight
            ps = Point3(
                canela_piv.x + (ps.x - canela_piv.x) * f_rad,
                canela_piv.y + (ps.y - canela_piv.y) * f_rad,
                ps.z,
            )
        return ps

    @staticmethod
    def _escrever_tampas_visiveis(
        vw: GeomVertexWriter,
        nw: GeomVertexWriter,
        top_c: Point3,
        ring_0: list[Point3],
        bot_c: Point3,
        ring_last: list[Point3],
    ) -> None:
        """Grava as tampas fechadas do topo da coxa e do interior da barra."""
        n_top = Vec3(0, 0, 1)
        for s_idx in range(8):
            nxt = (s_idx + 1) % 8
            for pt in (top_c, ring_0[s_idx], ring_0[nxt]):
                vw.setData3(pt)
                nw.setData3(n_top)
        n_bot = Vec3(0, 0, -1)
        for s_idx in range(8):
            nxt = (s_idx + 1) % 8
            for pt in (bot_c, ring_last[nxt], ring_last[s_idx]):
                vw.setData3(pt)
                nw.setData3(n_bot)

    @classmethod
    def _escrever_malha_visivel(
        cls,
        perna: _PernaMalha,
        deformados: list[list[Point3]],
        top_c: Point3,
        bot_c: Point3,
    ) -> None:
        """Atualiza vértices e normais por face da malha visível e das tampas."""
        vw = GeomVertexWriter(perna.vis_vdata, "vertex")
        nw = GeomVertexWriter(perna.vis_vdata, "normal")
        for r_idx in range(len(deformados) - 1):
            r_up, r_dn = deformados[r_idx], deformados[r_idx + 1]
            for s_idx in range(8):
                nxt = (s_idx + 1) % 8
                a, b, c, d = r_up[s_idx], r_dn[s_idx], r_dn[nxt], r_up[nxt]
                n = (b - a).cross(c - a)
                if n.lengthSquared() < 1e-12:
                    n = (c - a).cross(d - a)
                n = n.normalized() if n.lengthSquared() > 1e-12 else Vec3(0, -1, 0)
                for pt in (a, b, c, d):
                    vw.setData3(pt)
                    nw.setData3(n)
        cls._escrever_tampas_visiveis(vw, nw, top_c, deformados[0], bot_c, deformados[-1])

    @staticmethod
    def _escrever_malha_contorno(
        perna: _PernaMalha, deformados: list[list[Point3]]
    ) -> None:
        """Atualiza vértices e normais radiais da malha auxiliar de silhueta."""
        if perna.out_vdata is None:
            return
        ovw = GeomVertexWriter(perna.out_vdata, "vertex")
        onw = GeomVertexWriter(perna.out_vdata, "normal")
        centros = [sum(pts, Point3(0, 0, 0)) * (1.0 / 8.0) for pts in deformados]
        for r_idx in range(1, 9):
            centro = centros[r_idx]
            tang = centros[min(8, r_idx + 1)] - centros[max(0, r_idx - 1)]
            tang = tang.normalized() if tang.lengthSquared() > 1e-12 else Vec3(0, 0, -1)
            for pt in deformados[r_idx]:
                radial = pt - centro
                radial -= tang * radial.dot(tang)
                radial = radial.normalized() if radial.lengthSquared() > 1e-12 else Vec3(0, -1, 0)
                ovw.setData3(pt)
                onw.setData3(radial)

    def _atualizar_perna(
        self,
        renderer,
        perna: _PernaMalha,
        hip_deg: float,
        knee_deg: float,
        roll_deg: float,
        dt: float,
        lift: float,
    ) -> None:
        """Deforma e reescreve a malha de tecido e contorno da perna para o quadro."""
        hem_lag_p, hem_lag_r = self._atualizar_molas_barra(perna, hip_deg, knee_deg, roll_deg, dt)
        r_nodes = renderer._rig_nodes
        orig_v = Vec3(perna.origem_em_legs)
        dqs = self._calcular_dqs_perna(r_nodes, perna, orig_v)
        mats_anel = [_dq_blend_mat(dqs, anel[0].pesos_ossos) for anel in perna.rings_verts]
        mat_top = _dq_blend_mat(dqs, perna.top_center.pesos_ossos)
        mat_bot = _dq_blend_mat(dqs, perna.bot_center.pesos_ossos)

        knee_rad = math.radians(max(0.0, min(115.0, knee_deg)))
        hip_fwd_rad = math.radians(max(0.0, min(95.0, -hip_deg)))
        billow = 1.0 + min(0.055, abs(hem_lag_p) * 0.005 + lift * 0.8)
        canela_piv = r_nodes[perna.canela_nome].getPos(self._legs) - orig_v
        m_hem = (
            Mat4.translateMat(-canela_piv)
            * Mat4.rotateMat(hem_lag_p, Vec3(1, 0, 0))
            * Mat4.rotateMat(hem_lag_r, Vec3(0, 1, 0))
            * Mat4.translateMat(canela_piv)
        )
        deformados = [
            [
                self._deformar_vertice_tecido(v, mats_anel[r_idx], m_hem, canela_piv, knee_rad, hip_fwd_rad, billow)
                for v in anel
            ]
            for r_idx, anel in enumerate(perna.rings_verts)
        ]
        top_c = self._deformar_vertice_tecido(perna.top_center, mat_top, m_hem, canela_piv, knee_rad, hip_fwd_rad, billow)
        bot_c = self._deformar_vertice_tecido(perna.bot_center, mat_bot, m_hem, canela_piv, knee_rad, hip_fwd_rad, billow)
        self._escrever_malha_visivel(perna, deformados, top_c, bot_c)
        self._escrever_malha_contorno(perna, deformados)
