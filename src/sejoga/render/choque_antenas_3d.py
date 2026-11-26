"""Choque elétrico 3D nas esferas douradas das antenas (antecipação pré-porta)."""

from __future__ import annotations

import math
import random

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    NodePath,
    Point3,
    Vec3,
)

# Centro medido das esferas douradas no espaço local de antena-direita/esquerda.
_ESFERA_LOCAL_FALLBACK = (
    Vec3(0.109925, -0.068164, 0.148931),
    Vec3(-0.109925, -0.068164, 0.148931),
)
_COR_NUCLEO_OURO = (1.0, 0.98, 0.85, 1.0)
_COR_RAIO_CIANO = (0.16, 0.96, 1.0, 1.0)
# Opaco/alto alpha para 100% chroma-safe (zero halo magenta no LWA_COLORKEY).
_COR_COROA_EXT = (0.18, 0.94, 1.0, 0.92)
_COR_COROA_INT = (1.0, 0.96, 0.35, 0.98)

_ESTILOS_CHOQUE: dict[str, dict[str, tuple[float, float, float, float]]] = {
    "padrao": {
        "raio": _COR_RAIO_CIANO,
        "nucleo": _COR_NUCLEO_OURO,
        "ouro_int": (1.8, 1.72, 0.70, 1.0),
        "ouro_ext": (1.6, 1.45, 0.25, 0.92),
        "alt_int": (0.90, 1.90, 2.0, 1.0),
        "alt_ext": (0.20, 1.55, 1.95, 0.92),
    },
    "pixel": {
        "raio": (0.18, 0.98, 0.82, 1.0),
        "nucleo": (1.0, 0.96, 0.38, 1.0),
        "ouro_int": (1.7, 1.7, 0.45, 1.0),
        "ouro_ext": (1.4, 1.2, 0.20, 0.94),
        "alt_int": (0.35, 1.85, 1.55, 1.0),
        "alt_ext": (0.15, 1.40, 1.20, 0.94),
    },
    "rascunho": {
        "raio": (0.96, 0.24, 0.28, 1.0),
        "nucleo": (0.98, 0.96, 0.90, 1.0),
        "ouro_int": (1.8, 1.75, 1.65, 1.0),
        "ouro_ext": (1.45, 0.28, 0.32, 0.94),
        "alt_int": (1.6, 1.75, 1.9, 1.0),
        "alt_ext": (0.22, 0.75, 1.55, 0.94),
    },
    "hifi_comic": {
        "raio": (0.12, 0.90, 1.0, 1.0),
        "nucleo": (1.0, 0.88, 0.22, 1.0),
        "ouro_int": (1.85, 1.55, 0.35, 1.0),
        "ouro_ext": (1.65, 1.10, 0.15, 0.94),
        "alt_int": (0.35, 1.75, 2.0, 1.0),
        "alt_ext": (0.10, 1.25, 1.85, 0.94),
    },
    "cyberfunk": {
        "raio": (0.18, 0.98, 0.94, 1.0),
        "nucleo": (0.85, 0.42, 1.0, 1.0),
        "ouro_int": (1.45, 0.65, 2.0, 1.0),
        "ouro_ext": (1.05, 0.25, 1.75, 0.94),
        "alt_int": (0.30, 1.95, 1.85, 1.0),
        "alt_ext": (0.14, 1.65, 1.60, 0.94),
    },
    "anime": {
        "raio": (0.28, 0.90, 1.0, 1.0),
        "nucleo": (1.0, 0.98, 0.90, 1.0),
        "ouro_int": (1.85, 1.78, 1.32, 1.0),
        "ouro_ext": (0.45, 0.88, 1.75, 0.94),
        "alt_int": (0.95, 1.85, 2.0, 1.0),
        "alt_ext": (0.28, 1.35, 1.95, 0.94),
    },
    "lowpoly_block": {
        "raio": (0.14, 0.94, 0.74, 1.0),
        "nucleo": (1.0, 0.72, 0.18, 1.0),
        "ouro_int": (1.80, 1.30, 0.30, 1.0),
        "ouro_ext": (1.45, 0.85, 0.12, 0.94),
        "alt_int": (0.25, 1.75, 1.45, 1.0),
        "alt_ext": (0.12, 1.35, 1.15, 0.94),
    },
    "holograma": {
        "raio": (0.16, 0.96, 1.0, 1.0),
        "nucleo": (0.88, 1.0, 1.0, 1.0),
        "ouro_int": (0.85, 1.95, 2.0, 1.0),
        "ouro_ext": (0.18, 1.45, 1.95, 0.94),
        "alt_int": (0.55, 1.85, 2.0, 1.0),
        "alt_ext": (0.10, 1.25, 1.85, 0.94),
    },
    "gameboy": {
        "raio": (0.61, 0.74, 0.06, 1.0),
        "nucleo": (0.61, 0.74, 0.06, 1.0),
        "ouro_int": (1.15, 1.40, 0.12, 1.0),
        "ouro_ext": (0.72, 0.94, 0.12, 0.94),
        "alt_int": (0.42, 0.78, 0.28, 1.0),
        "alt_ext": (0.24, 0.48, 0.22, 0.94),
    },
    "manga_papel": {
        "raio": (0.96, 0.95, 0.91, 1.0),
        "nucleo": (0.98, 0.98, 0.96, 1.0),
        "ouro_int": (1.80, 1.78, 1.72, 1.0),
        "ouro_ext": (0.22, 0.22, 0.25, 0.94),
        "alt_int": (1.55, 1.55, 1.50, 1.0),
        "alt_ext": (0.12, 0.12, 0.16, 0.94),
    },
}


def _proteger_cor_chroma(
    rgba: tuple[float, float, float, float], colorkey_hex: str
) -> tuple[float, float, float, float]:
    from sejoga.render.chroma_tuning import seguro_contra_chroma_255

    r, g, b, a = rgba
    ganho = max(1.0, r, g, b)
    rs, gs, bs = seguro_contra_chroma_255(
        int(round(max(0.0, min(1.0, r / ganho)) * 255.0)),
        int(round(max(0.0, min(1.0, g / ganho)) * 255.0)),
        int(round(max(0.0, min(1.0, b / ganho)) * 255.0)),
        colorkey_hex,
    )
    return (
        (rs / 255.0) * ganho,
        (gs / 255.0) * ganho,
        (bs / 255.0) * ganho,
        float(a),
    )


def _centro_esfera_antena(ant_np: NodePath, eh_direita: bool) -> Point3:
    esfera = ant_np.find("**/sphere")
    if not esfera.isEmpty():
        limites = esfera.getTightBounds(ant_np)
        if limites:
            return Point3((limites[0] + limites[1]) * 0.5)
    fallback = _ESFERA_LOCAL_FALLBACK[0 if eh_direita else 1]
    return Point3(fallback)


def _perp_dupla(direcao: Vec3) -> tuple[Vec3, Vec3]:
    ref = Vec3(0.0, 0.0, 1.0) if abs(direcao.z) < 0.85 else Vec3(1.0, 0.0, 0.0)
    u = direcao.cross(ref)
    if u.lengthSquared() < 1e-8:
        u = Vec3(1.0, 0.0, 0.0)
    u.normalize()
    v = direcao.cross(u).normalized()
    return u, v


def _emitir_segmento_fita3d(
    v_wr: GeomVertexWriter,
    n_wr: GeomVertexWriter,
    c_wr: GeomVertexWriter,
    tris: GeomTriangles,
    idx_base: int,
    p0: Vec3,
    p1: Vec3,
    r0: float,
    r1: float,
    cor: tuple[float, float, float, float],
) -> int:
    """Emite dois planos ortogonais formando um segmento 3D visível de qualquer ângulo."""
    eixo = p1 - p0
    if eixo.lengthSquared() < 1e-10:
        return idx_base
    u, v = _perp_dupla(eixo.normalized())
    n_dummy = Vec3(0.0, -1.0, 0.0)
    for ortho in (u, v):
        o0 = ortho * r0
        o1 = ortho * r1
        for pt in (p0 - o0, p0 + o0, p1 + o1, p1 - o1):
            v_wr.addData3(pt)
            n_wr.addData3(n_dummy)
            c_wr.addData4(*cor)
        tris.addVertices(idx_base, idx_base + 1, idx_base + 2)
        tris.addVertices(idx_base, idx_base + 2, idx_base + 3)
        tris.addVertices(idx_base, idx_base + 2, idx_base + 1)
        tris.addVertices(idx_base, idx_base + 3, idx_base + 2)
        idx_base += 4
    return idx_base


def _criar_casco_coroa(nome: str, raio: float, cor: tuple[float, float, float, float]) -> NodePath:
    """Octaedro subdividido translúcido envolvendo a bolinha dourada em 3D."""
    vdata = GeomVertexData(nome, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
    writer = GeomVertexWriter(vdata, "vertex")
    n_wr = GeomVertexWriter(vdata, "normal")
    c_wr = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)

    polos = (Vec3(0, 0, 1), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(-1, 0, 0), Vec3(0, -1, 0), Vec3(0, 0, -1))
    faces = (
        (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
        (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4),
    )
    pts: list[Vec3] = []
    idx_tri: list[tuple[int, int, int]] = []
    for a, b, c in faces:
        p0, p1, p2 = polos[a], polos[b], polos[c]
        m01 = (p0 + p1).normalized()
        m12 = (p1 + p2).normalized()
        m20 = (p2 + p0).normalized()
        base = len(pts)
        pts.extend((p0, p1, p2, m01, m12, m20))
        idx_tri.extend((
            (base, base + 3, base + 5),
            (base + 3, base + 1, base + 4),
            (base + 5, base + 4, base + 2),
            (base + 3, base + 4, base + 5),
        ))
    for pt in pts:
        writer.addData3(pt * raio)
        n_wr.addData3(pt)
        c_wr.addData4(*cor)
    for a, b, c in idx_tri:
        tris.addVertices(a, b, c)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gnode = GeomNode(nome)
    gnode.addGeom(geom)
    return NodePath(gnode)


def _emitir_segmento_duplo(
    v_wr: GeomVertexWriter,
    n_wr: GeomVertexWriter,
    c_wr: GeomVertexWriter,
    tris: GeomTriangles,
    idx: int,
    p0: Vec3,
    p1: Vec3,
    r0: float,
    r1: float,
    rn0: float,
    rn1: float,
    cor_ext: tuple[float, float, float, float] = _COR_RAIO_CIANO,
    cor_nucleo: tuple[float, float, float, float] = _COR_NUCLEO_OURO,
) -> int:
    """Emite camada externa e núcleo brilhante sobre o mesmo segmento 3D."""
    idx = _emitir_segmento_fita3d(v_wr, n_wr, c_wr, tris, idx, p0, p1, r0, r1, cor_ext)
    return _emitir_segmento_fita3d(v_wr, n_wr, c_wr, tris, idx, p0, p1, rn0, rn1, cor_nucleo)


def _emitir_raios_radiais(
    rng: random.Random,
    v_wr: GeomVertexWriter,
    n_wr: GeomVertexWriter,
    c_wr: GeomVertexWriter,
    tris: GeomTriangles,
    idx: int,
) -> int:
    for b in range(9):
        theta = (b / 9.0) * math.tau + rng.uniform(-0.20, 0.20)
        phi = rng.uniform(-0.95, 0.95)
        d = Vec3(
            math.cos(phi) * math.cos(theta),
            math.cos(phi) * math.sin(theta),
            math.sin(phi),
        ).normalized()
        u, v = _perp_dupla(d)
        cur = d * 0.024
        for passo in range(3):
            t_seg = (passo + 1) / 3.0
            dist = 0.024 + t_seg * rng.uniform(0.042, 0.068)
            jitter = (u * rng.uniform(-1.0, 1.0) + v * rng.uniform(-1.0, 1.0)) * (
                0.015 * (1.0 - 0.35 * t_seg)
            )
            nxt = d * dist + jitter
            r0 = 0.0044 * (1.0 - 0.45 * passo / 3.0)
            r1 = 0.0030 * (1.0 - 0.55 * t_seg)
            idx = _emitir_segmento_duplo(
                v_wr, n_wr, c_wr, tris, idx, cur, nxt, r0, r1, r0 * 0.52, r1 * 0.48
            )
            cur = nxt
    return idx


def _emitir_arcos_superficie(
    rng: random.Random,
    v_wr: GeomVertexWriter,
    n_wr: GeomVertexWriter,
    c_wr: GeomVertexWriter,
    tris: GeomTriangles,
    idx: int,
) -> int:
    for _ in range(4):
        normal = Vec3(
            rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0)
        )
        if normal.lengthSquared() < 1e-4:
            normal = Vec3(0.0, 1.0, 0.0)
        e1, e2 = _perp_dupla(normal.normalized())
        ang0 = rng.uniform(0.0, math.tau)
        cur = (e1 * math.cos(ang0) + e2 * math.sin(ang0)) * 0.031
        for passo in range(5):
            ang = ang0 + (passo + 1) * 0.52
            raio_orb = 0.031 + rng.uniform(-0.003, 0.007)
            nxt = (
                e1 * math.cos(ang)
                + e2 * math.sin(ang)
                + normal.normalized() * rng.uniform(-0.008, 0.008)
            ) * raio_orb
            idx = _emitir_segmento_duplo(
                v_wr, n_wr, c_wr, tris, idx, cur, nxt, 0.0034, 0.0030, 0.0017, 0.0015
            )
            cur = nxt
    return idx


def _criar_gaiola_raios(nome: str, semente: int) -> NodePath:
    """Constrói coroa radial e arcos tangenciais 3D de raios ao redor da bolinha."""
    rng = random.Random(semente)
    vdata = GeomVertexData(nome, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
    v_wr = GeomVertexWriter(vdata, "vertex")
    n_wr = GeomVertexWriter(vdata, "normal")
    c_wr = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)
    idx = _emitir_raios_radiais(rng, v_wr, n_wr, c_wr, tris, 0)
    _emitir_arcos_superficie(rng, v_wr, n_wr, c_wr, tris, idx)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gnode = GeomNode(nome)
    gnode.addGeom(geom)
    return NodePath(gnode)


# Cadência da descarga, duração relativa da ponte, largura e altura da coroa.
_DESCARGAS = {
    "padrao": (12., 1., 1., 1.),
    "pixel": (9., .75, 1.1, .80),
    "rascunho": (8., .58, 1.28, .84),
    "hifi_comic": (14., 1.25, .80, 1.45),
    "cyberfunk": (18., .68, 1.65, .59),
    "anime": (12., .44, .70, 1.65),
    "blockbench": (11., .82, .92, 1.10),
    "lowpoly_block": (10., 1.12, .92, 1.23),
    "holograma": (16., 1.50, 1.48, .70),
    "gameboy": (6., 1.7, .86, .86),
    "manga_papel": (9., .52, .59, 1.8),
}


class ChoqueAntenas3D:
    """Choque elétrico 3D ancorado diretamente nas duas esferas douradas."""

    def __init__(self, head_np: NodePath, ant_direita: NodePath, ant_esquerda: NodePath) -> None:
        """Anexa os pivôs de choque às antenas e prepara a ponte 3D entre elas."""
        self._descarga = _DESCARGAS["padrao"]
        self._head = head_np
        self._relogio = 0.0
        self._ganho_visivel = 0.0
        self._ponte_timer = 0.0
        self._ponte_ativa = False
        self._ponte_semente = 0
        self._ponte_rng = random.Random(1337)
        self._cor_raio = _COR_RAIO_CIANO
        self._cor_nucleo = _COR_NUCLEO_OURO
        self._cor_ouro_int = (1.8, 1.72, 0.70, 1.0)
        self._cor_ouro_ext = (1.6, 1.45, 0.25, 0.92)
        self._cor_alt_int = (0.90, 1.90, 2.0, 1.0)
        self._cor_alt_ext = (0.20, 1.55, 1.95, 0.92)
        self._pivos: list[tuple[NodePath, NodePath, NodePath, list[NodePath]]] = []
        for idx, (ant_np, eh_dir) in enumerate(((ant_direita, True), (ant_esquerda, False))):
            if ant_np is not None and not ant_np.isEmpty():
                self._pivos.append(self._criar_pivo_antena(idx, ant_np, eh_dir))
        self._arco_vdata = GeomVertexData("choque-arco-ponte", GeomVertexFormat.getV3n3c4(), Geom.UHDynamic)
        self._arco_tris = GeomTriangles(Geom.UHDynamic)
        self._arco_np = self._criar_arco_ponte_np(head_np, self._arco_vdata, self._arco_tris)

    def aplicar_estilo(
        self,
        filtro: str = "padrao",
        vfx_palette: str = "pb_escuro",
        colorkey_hex: str = "#FF00FF",
    ) -> None:
        """Ajusta a silhueta das coroas, a cadência do arco e a tinta da descarga."""
        del vfx_palette
        filtro_norm = "anime" if filtro == "anime_impact" else filtro
        self._descarga = _DESCARGAS.get(filtro_norm, _DESCARGAS["padrao"])
        paleta = _ESTILOS_CHOQUE.get(filtro_norm, _ESTILOS_CHOQUE["padrao"])
        self._cor_raio = _proteger_cor_chroma(paleta["raio"], colorkey_hex)
        self._cor_nucleo = _proteger_cor_chroma(paleta["nucleo"], colorkey_hex)
        self._cor_ouro_int = _proteger_cor_chroma(paleta["ouro_int"], colorkey_hex)
        self._cor_ouro_ext = _proteger_cor_chroma(paleta["ouro_ext"], colorkey_hex)
        self._cor_alt_int = _proteger_cor_chroma(paleta["alt_int"], colorkey_hex)
        self._cor_alt_ext = _proteger_cor_chroma(paleta["alt_ext"], colorkey_hex)

    @staticmethod
    def _criar_pivo_antena(
        idx: int, ant_np: NodePath, eh_dir: bool
    ) -> tuple[NodePath, NodePath, NodePath, list[NodePath]]:
        suf = "d" if eh_dir else "e"
        pivo = ant_np.attachNewNode(f"fx-choque-esfera-{suf}")
        pivo.setPos(_centro_esfera_antena(ant_np, eh_dir))
        pivo.setLightOff(1001)
        pivo.setShaderOff(1001)
        pivo.setBin("fixed", 52)
        pivo.setCollideMask(0)

        coroa_int = _criar_casco_coroa(f"choque-coroa-int-{suf}", 0.029, _COR_COROA_INT)
        coroa_ext = _criar_casco_coroa(f"choque-coroa-ext-{suf}", 0.039, _COR_COROA_EXT)
        from panda3d.core import ColorBlendAttrib

        blend_chroma = ColorBlendAttrib.make(
            ColorBlendAttrib.MAdd,
            ColorBlendAttrib.OIncomingAlpha,
            ColorBlendAttrib.OOneMinusIncomingAlpha,
            ColorBlendAttrib.MAdd,
            ColorBlendAttrib.OOne,
            ColorBlendAttrib.OOneMinusIncomingAlpha,
        )
        for cas in (coroa_int, coroa_ext):
            cas.setTransparency(1)
            cas.setAttrib(blend_chroma, 10)
            cas.setDepthWrite(False)
            cas.reparentTo(pivo)

        gaiolas = []
        for frame_idx in range(3):
            g = _criar_gaiola_raios(
                f"choque-raios-{suf}-{frame_idx}", semente=410 + idx * 97 + frame_idx * 31
            )
            g.reparentTo(pivo)
            g.hide()
            gaiolas.append(g)
        pivo.hide()
        return pivo, coroa_int, coroa_ext, gaiolas

    @staticmethod
    def _criar_arco_ponte_np(
        head_np: NodePath, vdata: GeomVertexData, tris: GeomTriangles
    ) -> NodePath:
        arco_geom = Geom(vdata)
        arco_geom.addPrimitive(tris)
        gnode = GeomNode("fx-choque-ponte-antenas")
        gnode.addGeom(arco_geom)
        arco_np = head_np.attachNewNode(gnode)
        arco_np.setLightOff(1001)
        arco_np.setShaderOff(1001)
        arco_np.setBin("fixed", 53)
        arco_np.setCollideMask(0)
        arco_np.hide()
        return arco_np

    def _atualizar_ponte(self, p0: Vec3, p1: Vec3, passo_quadro: int, ganho: float) -> None:
        """Constrói relâmpago quebrado por deslocamento recursivo em arco frontal-superior."""
        chave_ponte = (
            passo_quadro,
            self._ponte_semente,
            ganho >= 0.65,
            round(float(p0.x), 4),
            round(float(p0.y), 4),
            round(float(p0.z), 4),
            round(float(p1.x), 4),
            round(float(p1.y), 4),
            round(float(p1.z), 4),
            self._cor_raio,
            self._cor_nucleo,
        )
        if chave_ponte == getattr(self, "_ponte_cache_chave", None):
            return
        self._ponte_cache_chave = chave_ponte
        self._arco_vdata.uncleanSetNumRows(0)
        self._arco_tris.clearVertices()
        v_wr = GeomVertexWriter(self._arco_vdata, "vertex")
        n_wr = GeomVertexWriter(self._arco_vdata, "normal")
        c_wr = GeomVertexWriter(self._arco_vdata, "color")
        rng = random.Random(901 + self._ponte_semente * 97 + passo_quadro * 19)
        cor_ext = self._cor_raio
        cor_nuc = self._cor_nucleo
        idx = 0

        def subdividir_raio(
            a: Vec3, b: Vec3, elev_z: float, front_y: float, jitter_max: float
        ) -> list[Vec3]:
            pts = [a, b]
            amp = jitter_max
            for nivel in range(3):
                novos = [pts[0]]
                for k in range(len(pts) - 1):
                    pa, pb = pts[k], pts[k + 1]
                    meio = (pa + pb) * 0.5
                    eixo = pb - pa
                    if eixo.lengthSquared() > 1e-8:
                        u_perp, v_perp = _perp_dupla(eixo.normalized())
                    else:
                        u_perp, v_perp = Vec3(0, 1, 0), Vec3(0, 0, 1)
                    if nivel == 0:
                        # Arco pronunciado para CIMA (+Z) e para FRENTE (+Y em head).
                        meio += Vec3(
                            rng.uniform(-0.025, 0.025),
                            front_y,
                            elev_z,
                        )
                    meio += (
                        u_perp * rng.uniform(-amp, amp)
                        + v_perp * rng.uniform(-amp, amp)
                    )
                    novos.append(meio)
                    novos.append(pb)
                pts = novos
                amp *= 0.54
            return pts

        ramos = ((0.20 + rng.uniform(-0.03, 0.05), 0.072 + rng.uniform(-0.010, 0.018), 0.055, 0.0050),)
        if ganho >= 0.65:
            ramos = ramos + (
                (0.14 + rng.uniform(-0.03, 0.04), 0.054 + rng.uniform(-0.008, 0.014), 0.042, 0.0030),
            )
        for elev_z, front_y, j_max, raio_base in ramos:
            pontos = subdividir_raio(p0, p1, elev_z, front_y, j_max)
            n_seg = len(pontos) - 1
            for s in range(n_seg):
                t0 = (s + 0.2) / n_seg
                t1 = (s + 0.8) / n_seg
                r0 = raio_base * (0.45 + 0.85 * math.sin(math.pi * min(1.0, t0))) * (0.65 + 0.45 * ganho)
                r1 = raio_base * (0.45 + 0.85 * math.sin(math.pi * min(1.0, t1))) * (0.65 + 0.45 * ganho)
                idx = _emitir_segmento_duplo(
                    v_wr,
                    n_wr,
                    c_wr,
                    self._arco_tris,
                    idx,
                    pontos[s],
                    pontos[s + 1],
                    r0,
                    r1,
                    r0 * 0.48,
                    r1 * 0.48,
                    cor_ext=cor_ext,
                    cor_nucleo=cor_nuc,
                )
            # 1–2 ramificações laterais soltas nos vértices centrais do raio.
            for idx_no in (2, 5):
                if idx_no == 5 and ganho < 0.55:
                    continue
                tronco = pontos[idx_no]
                meio_f = tronco + Vec3(
                    rng.uniform(-0.042, 0.042),
                    rng.uniform(0.012, 0.036),
                    rng.uniform(0.025, 0.058),
                )
                ponta_f = meio_f + Vec3(
                    rng.uniform(-0.035, 0.035),
                    rng.uniform(0.006, 0.028),
                    rng.uniform(0.015, 0.042),
                )
                r_f = raio_base * 0.62
                idx = _emitir_segmento_duplo(
                    v_wr,
                    n_wr,
                    c_wr,
                    self._arco_tris,
                    idx,
                    tronco,
                    meio_f,
                    r_f,
                    r_f * 0.65,
                    r_f * 0.46,
                    r_f * 0.30,
                    cor_ext=cor_ext,
                    cor_nucleo=cor_nuc,
                )
                idx = _emitir_segmento_duplo(
                    v_wr,
                    n_wr,
                    c_wr,
                    self._arco_tris,
                    idx,
                    meio_f,
                    ponta_f,
                    r_f * 0.65,
                    r_f * 0.25,
                    r_f * 0.30,
                    r_f * 0.14,
                    cor_ext=cor_ext,
                    cor_nucleo=cor_nuc,
                )
        self._arco_tris.closePrimitive()
        self._arco_np.node().markInternalBoundsStale()

    def _atualizar_pivo(
        self,
        idx: int,
        pivo: NodePath,
        coroa_int: NodePath,
        coroa_ext: NodePath,
        gaiolas: list[NodePath],
        passo: int,
        intensidade: float,
        pulso: float,
        relogio: float,
    ) -> None:
        pivo.show()
        escala_base = (0.96 + 0.44 * intensidade) * pulso
        coroa_int.setScale(0.92 + 0.44 * pulso)
        coroa_ext.setScale(escala_base * 1.06)
        coroa_int.setHpr(relogio * 460.0 + idx * 45.0, relogio * 260.0, relogio * 195.0)
        coroa_ext.setHpr(-relogio * 310.0, relogio * 330.0, idx * 60.0)
        eh_ouro = (passo + idx) % 2 == 0
        if eh_ouro:
            coroa_int.setColorScale(*self._cor_ouro_int)
            coroa_ext.setColorScale(*self._cor_ouro_ext)
        else:
            coroa_int.setColorScale(*self._cor_alt_int)
            coroa_ext.setColorScale(*self._cor_alt_ext)
        ativa = (passo + idx) % len(gaiolas)
        for g_i, g in enumerate(gaiolas):
            if g_i == ativa:
                g.show()
                g.setHpr(
                    (passo * 89 + idx * 67) % 360,
                    ((passo * 47) % 120) - 60,
                    ((passo * 73) % 160) - 80,
                )
                g.setScale(escala_base * (1.14 if eh_ouro else 1.04))
                if eh_ouro:
                    g.setColorScale(*self._cor_ouro_int[:3], 1.0)
                else:
                    g.setColorScale(*self._cor_alt_int[:3], 1.0)
            else:
                g.hide()

    def atualizar(
        self,
        dt: float,
        aviso_antena: float,
        choque_argolas: bool,
        *,
        permitir_ponte: bool | None = None,
    ) -> None:
        """Atualiza animação de choque elétrico com ponte voltaica intermitente em rajadas."""
        dt_c = max(0.0, dt)
        if permitir_ponte is None:
            permitir_ponte = bool(choque_argolas or aviso_antena > 0.16)
        alvo_ativo = aviso_antena > 0.0 or choque_argolas
        if alvo_ativo:
            alvo_intens = min(1.0, max(0.65 if choque_argolas else 0.0, aviso_antena / 0.32))
            passo_sub = dt_c / 0.032 if dt_c > 0.0 else 1.0
            self._ganho_visivel += min(passo_sub, max(0.0, alvo_intens - self._ganho_visivel))
        else:
            passo_des = dt_c / 0.18 if dt_c > 0.0 else 1.0
            self._ganho_visivel = max(0.0, self._ganho_visivel - passo_des)
        if self._ganho_visivel <= 1e-4:
            self.ocultar()
            return
        self._relogio += dt_c
        fps, duracao_arco, largura, altura = self._descarga
        passo = int(self._relogio * fps)
        pop_onset = 1.0 + 0.18 * math.sin(min(1.0, self._ganho_visivel / 0.55) * math.pi)
        intensidade = self._ganho_visivel
        pulso = (0.90 + 0.28 * abs(math.sin(passo * 1.7))) * pop_onset
        for idx, (pivo, coroa_int, coroa_ext, gaiolas) in enumerate(self._pivos):
            pivo.setScale(largura, 1., altura)
            self._atualizar_pivo(
                idx, pivo, coroa_int, coroa_ext, gaiolas, passo, intensidade, pulso, self._relogio
            )
        # Máquina de rajadas intermitentes para a ponte entre antenas (0.06-0.11s ON / 0.22-0.42s OFF).
        if intensidade >= 0.40 and permitir_ponte and len(self._pivos) >= 2:
            self._ponte_timer -= dt_c
            if self._ponte_timer <= 0.0:
                self._ponte_ativa = not self._ponte_ativa
                if self._ponte_ativa:
                    self._ponte_semente += 1
                    self._ponte_timer = self._ponte_rng.uniform(0.06, 0.11) * duracao_arco
                else:
                    self._ponte_timer = self._ponte_rng.uniform(0.22, 0.42)
            if self._ponte_ativa:
                p0 = Vec3(self._pivos[0][0].getPos(self._head))
                p1 = Vec3(self._pivos[1][0].getPos(self._head))
                self._atualizar_ponte(p0, p1, passo, intensidade)
                self._arco_np.show()
            else:
                self._arco_np.hide()
        else:
            self._ponte_ativa = False
            self._ponte_timer = 0.0
            self._arco_np.hide()

    def ocultar(self) -> None:
        """Oculta as coroas, gaiolas de raios e a ponte elétrica entre antenas."""
        self._ganho_visivel = 0.0
        self._ponte_ativa = False
        self._ponte_timer = 0.0
        self._ponte_cache_chave = None
        for pivo, *_ in self._pivos:
            pivo.hide()
        self._arco_np.hide()
