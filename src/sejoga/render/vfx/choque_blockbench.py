"""Emissor autoral de ``choque`` para o estilo ``blockbench`` (Minecraft Dungeons).

Estética limpa localizada **somente nas duas antenas** (sem arco cruzando a tiara):
1. ``coroa_antena_3d``: mini-raios 3D afiados (núcleo branco puro + casca ciano/azul
   elétrico + centelha dourada no pico) estalando para fora e ao redor de cada antena,
   assimétricos entre esquerda e direita e sem invadir o rosto ou o vão central.
2. ``pulso_esfera``: cubos emissivos Blockbench pulsando nas pontas das 2 antenas.
3. ``flash_antena``: cartões pixel-art chunky 24x24 (mesma densidade de ``impacto_chao``).
4. ``faiscas_voxel``: cubinhos e chispas zigue-zague com drag e gravidade real.
"""

from __future__ import annotations

from functools import cache
from math import exp
from typing import TYPE_CHECKING

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    NodePath,
    PNMImage,
    Point3,
    StringStream,
    Texture,
    TextureStage,
    TransparencyAttrib,
    Vec3,
)

from sejoga.nucleo.recursos import assets_dir
from sejoga.render.sprites_efeitos import cartao_pixel, textura_pixel

if TYPE_CHECKING:
    from sejoga.render.efeitos_street import GerenciadorEfeitosStreet

# Cores 100% chroma-safe (distância > 150 do magenta #D600D6)
_BRANCO = (0.99, 1.00, 1.00, 1.0)
_CIANO = (0.14, 0.90, 1.00, 1.0)
_AZUL_DEEP = (0.07, 0.44, 0.92, 1.0)
_OURO_BRILHO = (1.00, 0.90, 0.32, 1.0)

# Perfis locais de corona em cada antena (dx para FORA, dy frente -Y, dz cima +Z),
# multiplicados por dist_vao. Cada step tem 2 conjuntos (dir, esq) assimétricos!
_CORONA_DIR: tuple[tuple[tuple[tuple[float, float, float], ...], ...], ...] = (
    # Step 0: ignição explosiva para fora/cima + estalo inferior
    (
        ((0.00, 0.00, 0.00), (0.08, -0.04, 0.07), (0.05, -0.05, 0.15), (0.14, -0.06, 0.23)),
        ((0.00, 0.00, 0.00), (0.10, -0.04, 0.01), (0.16, -0.05, 0.06), (0.24, -0.06, 0.03)),
        ((0.00, 0.00, 0.00), (0.06, -0.04, -0.06), (0.13, -0.05, -0.09), (0.17, -0.05, -0.16)),
    ),
    # Step 1: inversão angular + chicote fino de bobina
    (
        ((0.00, 0.00, 0.00), (0.04, -0.04, 0.10), (0.12, -0.05, 0.14), (0.10, -0.06, 0.24)),
        ((0.00, 0.00, 0.00), (0.09, -0.04, -0.02), (0.17, -0.05, 0.03), (0.25, -0.06, -0.02)),
        ((0.00, 0.00, 0.00), (0.07, -0.04, -0.09), (0.04, -0.05, -0.15), (0.11, -0.05, -0.20)),
    ),
    # Step 2: pontas desconectadas (espaço negativo perto da esfera!)
    (
        ((0.07, -0.04, 0.09), (0.12, -0.05, 0.15), (0.17, -0.06, 0.22)),
        ((0.10, -0.04, -0.02), (0.17, -0.05, 0.02), (0.23, -0.05, -0.01)),
    ),
)

_CORONA_ESQ: tuple[tuple[tuple[tuple[float, float, float], ...], ...], ...] = (
    # Step 0: ângulos distintos da direita (sem twinning)
    (
        ((0.00, 0.00, 0.00), (0.05, -0.04, 0.09), (0.12, -0.05, 0.14), (0.16, -0.06, 0.24)),
        ((0.00, 0.00, 0.00), (0.09, -0.04, -0.03), (0.17, -0.05, 0.02), (0.23, -0.06, 0.07)),
        ((0.00, 0.00, 0.00), (0.07, -0.04, -0.08), (0.11, -0.05, -0.14), (0.18, -0.05, -0.17)),
    ),
    # Step 1
    (
        ((0.00, 0.00, 0.00), (0.09, -0.04, 0.06), (0.06, -0.05, 0.16), (0.13, -0.06, 0.22)),
        ((0.00, 0.00, 0.00), (0.11, -0.04, 0.02), (0.16, -0.05, -0.04), (0.24, -0.06, -0.05)),
        ((0.00, 0.00, 0.00), (0.05, -0.04, -0.08), (0.12, -0.05, -0.11), (0.09, -0.05, -0.19)),
    ),
    # Step 2: pontas quebradas com espaço negativo
    (
        ((0.06, -0.04, 0.08), (0.13, -0.05, 0.13), (0.18, -0.06, 0.20)),
        ((0.09, -0.04, 0.01), (0.16, -0.05, -0.03), (0.22, -0.05, 0.02)),
    ),
)

# Pequeno anel quebrado abraçando a esfera da antena no Step 1 (efeito bobina local)
_ARCO_BOBINA: tuple[tuple[float, float, float], ...] = (
    (0.05, -0.05, 0.08),
    (0.11, -0.06, 0.03),
    (0.09, -0.06, -0.05),
    (0.03, -0.05, -0.10),
)


@cache
def _textura_choque() -> Texture:
    caminho = assets_dir() / "textures" / "vfx_blockbench" / "choque.png"
    img = PNMImage()
    if not img.read(StringStream(caminho.read_bytes()), caminho.name):
        raise ValueError(f"Atlas inválido: {caminho}")
    tex = textura_pixel("choque_blockbench_v2", img)
    tex.setFormat(Texture.FSrgbAlpha)
    return tex


def _perp_ortonormal(eixo: Vec3) -> tuple[Vec3, Vec3]:
    ref = Vec3(0.0, 1.0, 0.0) if abs(eixo.y) < 0.85 else Vec3(0.0, 0.0, 1.0)
    n1 = eixo.cross(ref)
    if n1.lengthSquared() < 1e-8:
        n1 = Vec3(0.0, 0.0, 1.0)
    n1.normalize()
    return n1, eixo.cross(n1).normalized()


def _emitir_prisma_segmento(
    vw: GeomVertexWriter,
    cw: GeomVertexWriter,
    tris: GeomTriangles,
    idx: int,
    p0: Vec3,
    p1: Vec3,
    r0: float,
    r1: float,
    cor: tuple[float, float, float, float],
) -> int:
    """Emite fita 3D cruzada afilada (r0 -> r1) limpa e opaca, sem textura de serrote."""
    delta = p1 - p0
    if delta.lengthSquared() < 1e-8:
        return idx
    n1, n2 = _perp_ortonormal(delta.normalized())
    for ortho in (n1, n2):
        o0, o1 = ortho * r0, ortho * r1
        for pt in (p0 - o0, p0 + o0, p1 + o1, p1 - o1):
            vw.addData3(pt)
            cw.addData4(*cor)
        tris.addVertices(idx, idx + 1, idx + 2)
        tris.addVertices(idx, idx + 2, idx + 3)
        idx += 4
    return idx


def _emitir_segmento_duplo(
    vw: GeomVertexWriter,
    cw: GeomVertexWriter,
    tris: GeomTriangles,
    idx: int,
    p0: Vec3,
    p1: Vec3,
    r0: float,
    r1: float,
    cor_casca: tuple[float, float, float, float] = _CIANO,
    cor_nucleo: tuple[float, float, float, float] = _BRANCO,
) -> int:
    # Casca colorida um pouco atrás (+0.015 Y) e núcleo branco puro à frente (-0.015 Y)
    off_b, off_f = Vec3(0.0, 0.015, 0.0), Vec3(0.0, -0.015, 0.0)
    idx = _emitir_prisma_segmento(vw, cw, tris, idx, p0 + off_b, p1 + off_b, r0, r1, cor_casca)
    return _emitir_prisma_segmento(
        vw, cw, tris, idx, p0 + off_f, p1 + off_f, r0 * 0.48, r1 * 0.48, cor_nucleo
    )


def _criar_cubo_voxel(nome: str, cor: tuple[float, float, float, float]) -> NodePath:
    """Cubo sólido Blockbench (8 vértices, 12 triângulos) para flash nas esferas."""
    vdata = GeomVertexData(nome, GeomVertexFormat.getV3c4(), Geom.UHStatic)
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    for x in (-0.5, 0.5):
        for y in (-0.5, 0.5):
            for z in (-0.5, 0.5):
                vw.addData3(x, y, z)
                cw.addData4(*cor)
    tris = GeomTriangles(Geom.UHStatic)
    faces = (
        (0, 2, 3, 1),
        (4, 5, 7, 6),
        (0, 1, 5, 4),
        (2, 6, 7, 3),
        (0, 4, 6, 2),
        (1, 3, 7, 5),
    )
    for a, b, c, d in faces:
        tris.addVertices(a, b, c)
        tris.addVertices(a, c, d)
    tris.closePrimitive()
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode(nome)
    gn.addGeom(geom)
    no = NodePath(gn)
    no.setLightOff(1)
    no.setShaderOff(1)
    no.setTransparency(TransparencyAttrib.MNone)
    no.setCollideMask(0)
    return no


def _criar_no_arco(raiz: NodePath) -> tuple[NodePath, GeomVertexData, GeomTriangles]:
    vdata = GeomVertexData("arco-bb-v2", GeomVertexFormat.getV3c4(), Geom.UHDynamic)
    tris = GeomTriangles(Geom.UHDynamic)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode("arco-voltaico-blockbench")
    gn.addGeom(geom)
    no = raiz.attachNewNode(gn)
    no.setTwoSided(True)
    no.setLightOff(1)
    no.setShaderOff(1)
    no.setDepthWrite(False)
    no.setTransparency(TransparencyAttrib.MNone)
    no.setCollideMask(0)
    return no, vdata, tris


def _centro_no_em(espaco: NodePath, no: NodePath | None) -> Vec3 | None:
    if no is None or no.isEmpty() or espaco.isEmpty():
        return None
    lim = no.getTightBounds(espaco)
    if lim:
        return Vec3((lim[0] + lim[1]) * 0.5)
    return Vec3(espaco.getRelativePoint(no, Point3(0)))


def _pontos_antenas_vivos(
    mgr: GerenciadorEfeitosStreet, espaco: NodePath, fallback: tuple[Vec3, Vec3]
) -> tuple[Vec3, Vec3]:
    cd = _centro_no_em(espaco, getattr(mgr, "_antena_dir_node", None))
    ce = _centro_no_em(espaco, getattr(mgr, "_antena_esq_node", None))
    return (cd, ce) if (cd is not None and ce is not None) else fallback


def _emitir_corona_antena(
    vw: GeomVertexWriter,
    cw: GeomVertexWriter,
    tris: GeomTriangles,
    idx: int,
    origem: Vec3,
    sinal_x: float,
    raios: tuple[tuple[tuple[float, float, float], ...], ...],
    dist: float,
    step: int,
    r_base: float,
) -> int:
    """Emite mini-raios 3D afilados estalando somente ao redor de uma antena."""
    cor_c = _CIANO if step != 2 else _AZUL_DEEP
    for perfil in raios:
        pts = [origem + Vec3(dx * sinal_x * dist, dy * dist, dz * dist) for dx, dy, dz in perfil]
        n_seg = len(pts) - 1
        for k in range(n_seg):
            f0 = 1.0 - (k / max(1, n_seg)) * 0.72
            f1 = max(0.14, 1.0 - ((k + 1) / max(1, n_seg)) * 0.86)
            idx = _emitir_segmento_duplo(vw, cw, tris, idx, pts[k], pts[k + 1], r_base * f0, r_base * f1, cor_c, _BRANCO)
    if step == 1:
        # Centelha dourada fina abraçando a lateral externa da bobina
        pts_b = [origem + Vec3(dx * sinal_x * dist, dy * dist, dz * dist) for dx, dy, dz in _ARCO_BOBINA]
        for k in range(len(pts_b) - 1):
            idx = _emitir_segmento_duplo(
                vw, cw, tris, idx, pts_b[k], pts_b[k + 1], r_base * 0.56, r_base * 0.42, _OURO_BRILHO, _BRANCO
            )
    return idx


def _reconstruir_arco(
    vdata: GeomVertexData,
    tris: GeomTriangles,
    p_dir: Vec3,
    p_esq: Vec3,
    step: int,
    dist: float,
    escala: float,
) -> None:
    if step >= 3:
        return
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    r_base = dist * (0.025 if step == 0 else (0.021 if step == 1 else 0.016)) * escala
    idx = _emitir_corona_antena(vw, cw, tris, 0, p_dir, -1.0, _CORONA_DIR[step], dist, step, r_base)
    _emitir_corona_antena(vw, cw, tris, idx, p_esq, 1.0, _CORONA_ESQ[step], dist, step, r_base)
    tris.closePrimitive()


def _montar_pecas_antena(
    raiz: NodePath, tex: Texture, stage: TextureStage
) -> tuple[tuple[NodePath, NodePath], tuple[NodePath, NodePath], list[tuple[NodePath, int, Vec3, int]]]:
    flashes = (cartao_pixel(raiz, "flash_d", tex), cartao_pixel(raiz, "flash_e", tex))
    for fl in flashes:
        fl.setTexScale(stage, 0.125, 1.0)
    cubos = (
        _criar_cubo_voxel("pulso_esfera_d", _BRANCO),
        _criar_cubo_voxel("pulso_esfera_e", _BRANCO),
    )
    for cb in cubos:
        cb.reparentTo(raiz)
    # 6 faíscas: 2 chispas zigue-zague + 2 cubinhos ciano + 2 cubinhos ouro
    especs = (
        (0, Vec3(-0.82, -0.10, 0.68), 4),
        (1, Vec3(0.82, -0.10, 0.64), 4),
        (0, Vec3(-0.66, -0.12, 0.25), 5),
        (1, Vec3(0.68, -0.12, 0.28), 5),
        (0, Vec3(-0.48, -0.12, -0.25), 6),
        (1, Vec3(0.50, -0.12, -0.22), 7),
    )
    faiscas = []
    for lado_idx, dir_v, cel in especs:
        c = cartao_pixel(raiz, "faisca_bb", tex)
        c.setTexScale(stage, 0.125, 1.0)
        c.setTexOffset(stage, cel / 8.0, 0.0)
        faiscas.append((c, lado_idx, dir_v, cel))
    return flashes, cubos, faiscas


def _atualizar_flashes_antena(
    flashes: tuple[NodePath, NodePath],
    cubos: tuple[NodePath, NodePath],
    stage: TextureStage,
    pontas: tuple[Vec3, Vec3],
    fase: float,
    step: int,
    dist_vao: float,
    escala: float,
) -> None:
    quadro = min(3, step)
    tam_fl = dist_vao * (0.28, 0.32, 0.34, 0.26)[quadro] * escala
    fade_fl = 1.0 if fase < 0.82 else max(0.0, (1.0 - fase) / 0.18)
    for idx_c, (fl, cb) in enumerate(zip(flashes, cubos, strict=True)):
        fl.setPos(pontas[idx_c] + Vec3(0.0, -0.14, 0.0))
        fl.setScale(tam_fl * (-1.0 if idx_c == 1 else 1.0), 1.0, tam_fl * 8.0)
        fl.setTexOffset(stage, quadro / 8.0, 0.0)
        fl.setShaderInput("u_fade", fade_fl)
        if fase < 0.56:
            cb.show()
            cb.setPos(pontas[idx_c] + Vec3(0.0, -0.05, 0.0))
            cb.setHpr(45.0 + step * 35.0, 30.0, 20.0 * (1 if idx_c == 0 else -1))
            cb.setScale(dist_vao * (0.095 if step == 0 else 0.068) * escala)
        else:
            cb.hide()


def _atualizar_faiscas_antena(
    faiscas: list[tuple[NodePath, int, Vec3, int]],
    pontas: tuple[Vec3, Vec3],
    fase: float,
    dist_vao: float,
    escala: float,
) -> None:
    alcance = max(0.35, dist_vao * 0.42) * escala
    for c_f, lado_idx, dir_v, cel in faiscas:
        if fase < 0.06:
            c_f.hide()
            continue
        u = min(1.0, (fase - 0.06) / 0.94)
        avanco = (1.0 - exp(-4.8 * u)) * alcance
        queda_z = (-0.28 if cel >= 5 else -0.06) * dist_vao * (u * u) * escala
        tam_f = dist_vao * (0.20 if cel == 4 else 0.11) * escala * min(1.0, (1.0 - u) / 0.28)
        if tam_f <= 0.025:
            c_f.hide()
            continue
        c_f.show()
        c_f.setPos(pontas[lado_idx] + dir_v * avanco + Vec3(0.0, -0.16, queda_z))
        c_f.setR((-28.0 if lado_idx == 0 else 28.0) + (0.0 if cel == 4 else u * 65.0))
        c_f.setScale(tam_f * (-1.0 if lado_idx == 1 else 1.0), 1.0, tam_f * 8.0)
        c_f.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))


def emitir_choque(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Descarga elétrica Blockbench biponto entre ``antena_d`` e ``antena_e``."""
    del pos, vel, dir_x
    ad_ini, ae_ini = anc.get("antena_d"), anc.get("antena_e")
    if ad_ini is None or ae_ini is None:
        return
    escala = max(0.65, min(1.40, float(forca)))
    centro, tex, stage = (ad_ini + ae_ini) * 0.5, _textura_choque(), TextureStage.getDefault()
    raiz = NodePath("choque_blockbench")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    flashes, cubos, faiscas = _montar_pecas_antena(raiz, tex, stage)
    fallback_local = (ad_ini - centro, ae_ini - centro)
    estado = {"step": -1, "p0": Vec3(0), "p1": Vec3(0)}

    def atualizar(fase: float) -> None:
        p_d, p_e = _pontos_antenas_vivos(mgr, raiz, fallback_local)
        dist_vao = max(0.45, (p_e - p_d).length())
        step = 0 if fase < 0.26 else (1 if fase < 0.56 else (2 if fase < 0.80 else 3))
        mudou = (p_d - estado["p0"]).lengthSquared() > 1e-4 or (p_e - estado["p1"]).lengthSquared() > 1e-4
        if step != estado["step"] or mudou:
            estado["step"], estado["p0"], estado["p1"] = step, Vec3(p_d), Vec3(p_e)
            _reconstruir_arco(vdata, tris, p_d, p_e, step, dist_vao, escala)
            arco_np.node().markInternalBoundsStale()
        (arco_np.hide if step >= 3 else arco_np.show)()
        _atualizar_flashes_antena(flashes, cubos, stage, (p_d, p_e), fase, step, dist_vao, escala)
        _atualizar_faiscas_antena(faiscas, (p_d, p_e), fase, dist_vao, escala)

    mgr.emitir_3d(
        raiz,
        centro,
        tipo_mesh="choque_blockbench",
        ttl=0.36,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=atualizar,
    )
    atualizar(0.0)
