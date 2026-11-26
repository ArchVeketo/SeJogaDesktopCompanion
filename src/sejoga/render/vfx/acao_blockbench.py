"""Emissores Blockbench de física, ritmo e velocidade (estética Minecraft Dungeons / Dungeons 2)."""

from __future__ import annotations

from functools import cache
from math import cos, exp, pi, sin
from typing import TYPE_CHECKING

from panda3d.core import (
    GeomTriangles,
    GeomVertexData,
    GeomVertexWriter,
    NodePath,
    PNMImage,
    StringStream,
    Texture,
    TextureStage,
    Vec3,
)

from sejoga.nucleo.recursos import assets_dir
from sejoga.render.sprites_efeitos import cartao_pixel, textura_pixel
from sejoga.render.vfx.choque_blockbench import (
    _AZUL_DEEP,
    _BRANCO,
    _CIANO,
    _OURO_BRILHO,
    _criar_cubo_voxel,
    _criar_no_arco,
    _emitir_prisma_segmento,
)

if TYPE_CHECKING:
    from sejoga.render.efeitos_street import GerenciadorEfeitosStreet

_AMBAR = (0.96, 0.52, 0.12, 1.0)
_AMBAR_FUNDO = (0.72, 0.28, 0.06, 1.0)
_ESMERALDA = (0.21, 0.93, 0.53, 1.0)
_VERDE_FUNDO = (0.07, 0.54, 0.34, 1.0)
_N_COLS = 16


@cache
def _textura_blocos() -> Texture:
    caminho = assets_dir() / "textures" / "vfx_blockbench" / "blocos_emocoes.png"
    img = PNMImage()
    if not img.read(StringStream(caminho.read_bytes()), caminho.name):
        raise ValueError(f"Atlas inválido: {caminho}")
    tex = textura_pixel("blocos_emocoes_bb", img)
    tex.setFormat(Texture.FSrgbAlpha)
    return tex


@cache
def _textura_poeira_bb() -> Texture:
    caminho = assets_dir() / "textures" / "vfx_blockbench" / "impacto_chao.png"
    img = PNMImage()
    if not img.read(StringStream(caminho.read_bytes()), caminho.name):
        raise ValueError(f"Atlas inválido: {caminho}")
    tex = textura_pixel("poeira_dungeons_bb", img)
    tex.setFormat(Texture.FSrgbAlpha)
    return tex


def _cartao_celula(raiz: NodePath, nome: str, celula: int) -> NodePath:
    stage = TextureStage.getDefault()
    c = cartao_pixel(raiz, nome, _textura_blocos())
    c.setTexScale(stage, 1.0 / _N_COLS, 1.0)
    c.setTexOffset(stage, celula / _N_COLS, 0.0)
    return c


def _cartao_puff_dungeons(raiz: NodePath, nome: str) -> NodePath:
    stage = TextureStage.getDefault()
    c = cartao_pixel(raiz, nome, _textura_poeira_bb())
    c.setTexScale(stage, 0.125, 1.0)
    return c


def _emitir_segmento_dungeons(
    vw: GeomVertexWriter,
    cw: GeomVertexWriter,
    tris: GeomTriangles,
    idx: int,
    p0: Vec3,
    p1: Vec3,
    r0: float,
    r1: float,
    cor_borda: tuple[float, float, float, float],
    cor_meio: tuple[float, float, float, float],
    cor_nucleo: tuple[float, float, float, float] = _BRANCO,
) -> int:
    """Faixa 3D Minecraft Dungeons em 3 bandas sólidas (borda profunda -> meio vibrante -> núcleo branco)."""
    idx = _emitir_prisma_segmento(vw, cw, tris, idx, p0 + Vec3(0, 0.024, 0), p1 + Vec3(0, 0.024, 0), r0, r1, cor_borda)
    idx = _emitir_prisma_segmento(
        vw, cw, tris, idx, p0 + Vec3(0, 0.004, 0), p1 + Vec3(0, 0.004, 0), r0 * 0.72, r1 * 0.72, cor_meio
    )
    return _emitir_prisma_segmento(
        vw, cw, tris, idx, p0 + Vec3(0, -0.018, 0), p1 + Vec3(0, -0.018, 0), r0 * 0.38, r1 * 0.38, cor_nucleo
    )


def _construir_parede(
    vdata: GeomVertexData,
    tris: GeomTriangles,
    normal: Vec3,
    tang: Vec3,
    fase: float,
    escala: float,
) -> None:
    if fase >= 0.88:
        return
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    abertura = 1.0 - (1.0 - min(1.0, fase / 0.52)) ** 3
    retracao = max(0.0, (fase - 0.50) / 0.38)
    raio = (0.42 + 1.08 * abertura) * escala
    esp = max(0.024, 0.135 * escala * (1.0 - retracao * 0.70))
    idx = 0
    # Meia-lua Dungeons em 3 bandas (âmbar fundo -> ouro -> branco) afinando nas pontas
    segs = 8
    for k in range(segs):
        t0, t1 = k / segs, (k + 1) / segs
        a0, a1 = (-0.48 + t0 * 0.96) * pi, (-0.48 + t1 * 0.96) * pi
        w0 = max(0.18, sin(t0 * pi))
        w1 = max(0.18, sin(t1 * pi))
        p0 = normal * (0.08 + 0.30 * cos(a0) * abertura) * escala + tang * (sin(a0) * raio)
        p1 = normal * (0.08 + 0.30 * cos(a1) * abertura) * escala + tang * (sin(a1) * raio)
        idx = _emitir_segmento_dungeons(
            vw, cw, tris, idx, p0, p1, esp * w0, esp * w1, _AMBAR_FUNDO, _OURO_BRILHO, _BRANCO
        )
    # 4 raios secos em leque rente à parede
    for ang_f in (-0.92, -0.36, 0.36, 0.92):
        d = (tang * ang_f + normal * 0.38).normalized()
        r_ini = (0.16 + 0.58 * retracao) * escala
        r_fim = (0.50 + 0.95 * abertura) * escala
        if r_fim > r_ini + 0.05:
            idx = _emitir_segmento_dungeons(
                vw, cw, tris, idx, d * r_ini, d * r_fim, esp * 0.62, esp * 0.12, _AMBAR_FUNDO, _AMBAR, _BRANCO
            )
    tris.closePrimitive()


def _atualizar_puffs_e_cubos_parede(
    puffs: list[tuple[NodePath, float]],
    cubos: tuple[NodePath, NodePath],
    stage: TextureStage,
    normal: Vec3,
    tang: Vec3,
    u: float,
    escala: float,
) -> None:
    for puff, lado_t in puffs:
        dp = (1.0 - exp(-4.8 * u)) * 0.95 * escala
        tp = (0.42 + 0.38 * min(1.0, u * 5.0)) * escala * min(1.0, (1.0 - u) / 0.25)
        if tp <= 0.03:
            puff.hide()
            continue
        puff.show()
        puff.setPos(normal * (0.18 * escala) + tang * (lado_t * dp) + Vec3(0.0, -0.06, 0.0))
        puff.setScale(tp * lado_t, 1.0, tp * 7.6)
        puff.setTexOffset(stage, min(5, int(u * 6.0)) / 8.0, 0.0)
        puff.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.20))
    for i, cb in enumerate(cubos):
        sc = 0.14 * escala * max(0.0, 1.0 - u * 1.35)
        if sc <= 0.02:
            cb.hide()
            continue
        cb.show()
        s = -1.0 if i == 0 else 1.0
        cb.setPos(normal * (0.45 + 0.85 * u) * escala + tang * (s * 0.65 * u * escala) + Vec3(0, -0.12, 0))
        cb.setHpr(40.0 + u * 180.0, 30.0, u * 140.0 * s)
        cb.setScale(sc)


def _atualizar_extras_parede(
    lascas: list[tuple[NodePath, float]],
    puffs: list[tuple[NodePath, float]],
    cubos: tuple[NodePath, NodePath],
    stage: TextureStage,
    normal: Vec3,
    tang: Vec3,
    fase: float,
    escala: float,
) -> None:
    u = min(1.0, fase / 0.95)
    for idx_l, (chip, spread) in enumerate(lascas):
        dist = (1.0 - exp(-4.2 * u)) * (1.35 + 0.26 * idx_l) * escala
        p = normal * dist + tang * (spread * dist * 0.65) + Vec3(0.0, -0.14, -1.75 * u * u * escala)
        tam = 0.30 * escala * min(1.0, (1.0 - u) / 0.28)
        if tam <= 0.02:
            chip.hide()
            continue
        chip.show()
        chip.setPos(p)
        chip.setR((1 if spread >= 0 else -1) * (25.0 + u * 120.0))
        chip.setScale(tam, 1.0, tam * _N_COLS)
        chip.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))
    _atualizar_puffs_e_cubos_parede(puffs, cubos, stage, normal, tang, u, escala)


def emitir_impacto_parede(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Colisão seca Minecraft Dungeons na parede/teto: meia-lua 3 bandas + puffs + lascas voxel."""
    origem = Vec3(pos) if pos is not None else Vec3(anc.get("lado_dir", anc["tronco"]))
    normal = Vec3(vel.x, 0.0, vel.z) if vel is not None else Vec3(-dir_x, 0.0, 0.0)
    if normal.lengthSquared() < 1e-4:
        normal = Vec3(anc["tronco"].x - origem.x, 0.0, anc["tronco"].z - origem.z)
    normal = normal.normalized() if normal.lengthSquared() > 1e-4 else Vec3(1.0, 0.0, 0.0)
    tang = Vec3(-normal.z, 0.0, normal.x)
    escala = max(0.65, min(1.45, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("impacto_parede_blockbench")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    lascas = [(_cartao_celula(raiz, f"lasca_p_{i}", 11), s) for i, s in enumerate((-0.75, 0.15, 0.82))]
    puffs = [(_cartao_puff_dungeons(raiz, f"puff_p_{i}"), s) for i, s in enumerate((-1.0, 1.0))]
    cubos = (_criar_cubo_voxel("spark_p0", _OURO_BRILHO), _criar_cubo_voxel("spark_p1", _BRANCO))
    for cb in cubos:
        cb.reparentTo(raiz)

    def atualizar(fase: float) -> None:
        _construir_parede(vdata, tris, normal, tang, fase, escala)
        arco_np.node().markInternalBoundsStale()
        (arco_np.hide if fase >= 0.88 else arco_np.show)()
        _atualizar_extras_parede(lascas, puffs, cubos, stage, normal, tang, fase, escala)

    mgr.emitir_3d(
        raiz,
        origem,
        tipo_mesh="impacto_parede_blockbench",
        ttl=0.40,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=atualizar,
    )
    atualizar(0.0)


def _construir_onda_grave(
    vdata: GeomVertexData,
    tris: GeomTriangles,
    dir_x: float,
    fase: float,
    escala: float,
) -> None:
    if fase >= 0.92:
        return
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    idx = 0
    # 2 arcos concêntricos Dungeons em 3 bandas (azul/verde fundo -> ciano/esmeralda -> branco)
    ondas = ((0.0, _AZUL_DEEP, _CIANO, 1.0), (0.14, _VERDE_FUNDO, _ESMERALDA, 0.82))
    for atraso, cor_b, cor_m, peso in ondas:
        if fase < atraso:
            continue
        u = min(1.0, (fase - atraso) / (1.0 - atraso))
        if u >= 0.94:
            continue
        exp_u = 1.0 - (1.0 - u) ** 3
        raio = (0.36 + 1.24 * exp_u) * escala * peso
        avanco = (0.18 + 1.02 * exp_u) * escala * dir_x
        esp = max(0.022, 0.118 * escala * peso * (1.0 - u * 0.72))
        segs = 8
        for k in range(segs):
            t0, t1 = k / segs, (k + 1) / segs
            a0, a1 = (-0.44 + t0 * 0.88) * pi, (-0.44 + t1 * 0.88) * pi
            w0, w1 = max(0.18, sin(t0 * pi)), max(0.18, sin(t1 * pi))
            p0 = Vec3(avanco + cos(a0) * raio * 0.44 * dir_x, -0.06, sin(a0) * raio)
            p1 = Vec3(avanco + cos(a1) * raio * 0.44 * dir_x, -0.06, sin(a1) * raio)
            idx = _emitir_segmento_dungeons(vw, cw, tris, idx, p0, p1, esp * w0, esp * w1, cor_b, cor_m, _BRANCO)
    tris.closePrimitive()


def _atualizar_extras_danca(
    notas: list[tuple[NodePath, float, float]],
    cubos: tuple[NodePath, NodePath, NodePath],
    lado: float,
    fase: float,
    escala: float,
) -> None:
    for nota, atraso, dz_off in notas:
        if fase < atraso:
            nota.hide()
            continue
        u = min(1.0, (fase - atraso) / (1.0 - atraso))
        tam = 0.64 * escala * min(1.0, u / 0.16) * min(1.0, (1.0 - u) / 0.25)
        if tam <= 0.02:
            nota.hide()
            continue
        nota.show()
        nota.setPos(lado * (0.44 + 0.82 * u) * escala, 0.16, (dz_off + 0.74 * u) * escala)
        nota.setR(sin(u * 2.0 * pi) * 10.0)
        nota.setScale(tam, 1.0, tam * _N_COLS)
        nota.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))
    # 3 cubinhos voxel estalando no beat
    for i, cb in enumerate(cubos):
        sc = 0.12 * escala * max(0.0, 1.0 - fase * 1.25)
        if sc <= 0.02:
            cb.hide()
            continue
        cb.show()
        ang = (-0.55 + i * 0.55) * pi * 0.5
        r_c = (0.35 + 1.15 * fase) * escala
        cb.setPos(lado * (0.28 + cos(ang) * r_c), -0.08, sin(ang) * r_c)
        cb.setHpr(45.0 + fase * 160.0, 35.0, fase * 120.0 * lado)
        cb.setScale(sc)


def emitir_acento_danca(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Pulso acústico Dungeons 3 bandas + notas chunky + cubinhos voxel no beat."""
    del vel
    lado = -1.0 if dir_x < 0 else 1.0
    fallback = anc.get("fone_esq" if lado > 0 else "fone_dir", anc["cabeca_topo"])
    origem = Vec3(pos) if pos is not None else Vec3(fallback)
    escala = max(0.68, min(1.38, float(forca)))
    raiz = NodePath("acento_danca_blockbench")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    notas = [(_cartao_celula(raiz, "nota_bb_0", 9), 0.0, 0.35)]
    if forca >= 1.1:
        notas.append((_cartao_celula(raiz, "nota_bb_1", 10), 0.14, 0.72))
    cubos = (
        _criar_cubo_voxel("beat_c0", _CIANO),
        _criar_cubo_voxel("beat_c1", _ESMERALDA),
        _criar_cubo_voxel("beat_c2", _OURO_BRILHO),
    )
    for cb in cubos:
        cb.reparentTo(raiz)

    def atualizar(fase: float) -> None:
        _construir_onda_grave(vdata, tris, lado, fase, escala)
        arco_np.node().markInternalBoundsStale()
        (arco_np.hide if fase >= 0.92 else arco_np.show)()
        _atualizar_extras_danca(notas, cubos, lado, fase, escala)

    mgr.emitir_3d(
        raiz,
        origem,
        tipo_mesh="acento_danca_blockbench",
        ttl=0.38,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=atualizar,
    )
    atualizar(0.0)


def _construir_rastro(
    vdata: GeomVertexData,
    tris: GeomTriangles,
    direcao: Vec3,
    perp: Vec3,
    fase: float,
    escala: float,
) -> None:
    if fase >= 0.92:
        return
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    # Fita curva volumétrica estilo Minecraft Dungeons (3 bandas: azul -> ciano -> branco)
    u_cauda = min(0.84, fase * 1.05)
    inicio = 0.72 * escala
    comp = 3.25 * escala * (1.0 - u_cauda)
    esp = max(0.026, 0.155 * escala * (1.0 - fase * 0.65))
    idx = 0
    fitas = (
        (0.55, 0.24, 1.00, _AZUL_DEEP, _CIANO),
        (-0.55, -0.22, 0.88, _AZUL_DEEP, _CIANO),
        (0.0, 0.14, 0.72, _AMBAR, _OURO_BRILHO),
    )
    segs = 6
    for off_p, amp_s, fator, cor_b, cor_m in fitas:
        pts = [
            direcao * (inicio + comp * fator * (k / segs))
            + perp * ((off_p + sin((k / segs) * 1.6 * pi) * amp_s) * escala)
            + Vec3(0.0, -0.06, 0.0)
            for k in range(segs + 1)
        ]
        for k in range(segs):
            w0 = 1.0 - (k / segs) * 0.82
            w1 = max(0.10, 1.0 - ((k + 1) / segs) * 0.90)
            idx = _emitir_segmento_dungeons(vw, cw, tris, idx, pts[k], pts[k + 1], esp * w0, esp * w1, cor_b, cor_m)
    tris.closePrimitive()


def _atualizar_extras_rastro(
    puffs: list[tuple[NodePath, float]],
    cubos: tuple[NodePath, NodePath, NodePath],
    stage: TextureStage,
    direcao: Vec3,
    perp: Vec3,
    fase: float,
    escala: float,
) -> None:
    for i, (puff, off) in enumerate(puffs):
        tp = (0.36 + 0.28 * min(1.0, fase * 4.0)) * escala * min(1.0, (1.0 - fase) / 0.28)
        if tp <= 0.03:
            puff.hide()
            continue
        puff.show()
        puff.setPos(direcao * (1.05 + 0.85 * fase + i * 0.55) * escala + perp * (off * escala) + Vec3(0, -0.04, 0))
        puff.setScale(tp * (1.0 if i == 0 else -1.0), 1.0, tp * 7.6)
        puff.setTexOffset(stage, min(5, int(fase * 6.0) + i) / 8.0, 0.0)
        puff.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.24))
    for i, cb in enumerate(cubos):
        sc = 0.13 * escala * max(0.0, 1.0 - fase * 1.18)
        if sc <= 0.02:
            cb.hide()
            continue
        cb.show()
        off_c = (-0.78, 0.12, 0.82)[i]
        cb.setPos(direcao * (0.95 + (1.35 + i * 0.45) * fase) * escala + perp * (off_c * escala) + Vec3(0, -0.10, 0))
        cb.setHpr(30.0 + fase * 180.0, 40.0, fase * 150.0 * (1 if i % 2 == 0 else -1))
        cb.setScale(sc)


def emitir_rastro(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Fita curva luminosa Minecraft Dungeons (3 bandas) + puffs chunky + cubinhos voxel."""
    origem = Vec3(pos) if pos is not None else Vec3(anc["tronco"])
    direcao = Vec3(vel.x, 0.0, vel.z) if vel is not None else Vec3(-dir_x, 0.0, 0.0)
    direcao = direcao.normalized() if direcao.lengthSquared() > 1e-4 else Vec3(-dir_x, 0.0, 0.0)
    perp = Vec3(-direcao.z, 0.0, direcao.x)
    escala = max(0.70, min(1.40, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("rastro_blockbench")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    puffs = [(_cartao_puff_dungeons(raiz, f"rastro_puff_{i}"), off) for i, off in enumerate((-0.45, 0.48))]
    cubos = (
        _criar_cubo_voxel("rastro_c0", _CIANO),
        _criar_cubo_voxel("rastro_c1", _BRANCO),
        _criar_cubo_voxel("rastro_c2", _OURO_BRILHO),
    )
    for cb in cubos:
        cb.reparentTo(raiz)

    def atualizar(fase: float) -> None:
        _construir_rastro(vdata, tris, direcao, perp, fase, escala)
        arco_np.node().markInternalBoundsStale()
        (arco_np.hide if fase >= 0.92 else arco_np.show)()
        _atualizar_extras_rastro(puffs, cubos, stage, direcao, perp, fase, escala)

    mgr.emitir_3d(
        raiz,
        origem,
        tipo_mesh="rastro_blockbench",
        ttl=0.34,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=atualizar,
    )
    atualizar(0.0)
