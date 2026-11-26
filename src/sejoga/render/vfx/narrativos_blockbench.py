"""VFX narrativos e de movimento Blockbench: ``poeira_passo``, ``tontura``, ``sinal_radio``, ``curiosidade``, ``brilho_estilo``."""

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
    Texture,
    TextureStage,
    Vec3,
)

from sejoga.render.sprites_efeitos import cartao_pixel, textura_pixel
from sejoga.render.vfx.acao_blockbench import (
    _ESMERALDA,
    _N_COLS,
    _VERDE_FUNDO,
    _cartao_celula,
    _cartao_puff_dungeons,
    _emitir_segmento_dungeons,
)
from sejoga.render.vfx.choque_blockbench import (
    _AZUL_DEEP,
    _BRANCO,
    _CIANO,
    _OURO_BRILHO,
    _criar_cubo_voxel,
    _criar_no_arco,
)

if TYPE_CHECKING:
    from sejoga.render.efeitos_street import GerenciadorEfeitosStreet


def _atualizar_poeira_passo(
    puffs: tuple[tuple[NodePath, float, float, float], ...],
    cubo: NodePath,
    stage: TextureStage,
    lado: float,
    fase: float,
    escala: float,
) -> None:
    for i, (pf, atraso, tam_b, elev) in enumerate(puffs):
        if fase < atraso:
            pf.hide()
            continue
        u = min(1.0, (fase - atraso) / (1.0 - atraso))
        dist = (1.0 - exp(-4.4 * u)) * (0.85 + 0.34 * i) * escala
        tam = tam_b * escala * (0.58 + 0.56 * min(1.0, u * 4.0)) * min(1.0, (1.0 - u) / 0.26)
        if tam <= 0.03:
            pf.hide()
            continue
        pf.show()
        pf.setPos(lado * (0.98 + dist), -0.16 + i * 0.06, (0.24 + u * elev) * escala)
        pf.setR(-lado * (14.0 + u * 18.0 + i * 5.0))
        pf.setScale(tam * lado, 1.0, tam * 10.0)
        pf.setTexOffset(stage, min(5, int(u * 5.8)) / 8.0, 0.0)
        pf.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))
    sc = 0.13 * escala * max(0.0, 1.0 - fase * 1.25)
    if sc <= 0.015:
        cubo.hide()
    else:
        cubo.show()
        cubo.setPos(lado * (1.05 + 1.05 * fase) * escala, -0.18, (0.42 * sin(fase * pi)) * escala)
        cubo.setHpr(fase * 180.0, 35.0, fase * 140.0)
        cubo.setScale(sc)


def emitir_poeira_passo(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Fumaça volumosa chunky atrás do tênis ao correr ou derrapar."""
    del vel
    lado = -1.0 if dir_x >= 0 else 1.0
    origem = Vec3(pos) if pos is not None else Vec3(anc.get("pes", anc["tronco"]))
    escala = max(0.60, min(1.30, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("poeira_passo_blockbench")
    puffs = (
        (_cartao_puff_dungeons(raiz, "passo_p0"), 0.00, 0.72, 0.56),
        (_cartao_puff_dungeons(raiz, "passo_p1"), 0.08, 0.58, 0.82),
        (_cartao_puff_dungeons(raiz, "passo_p2"), 0.18, 0.46, 0.44),
    )
    cubo = _criar_cubo_voxel("passo_c0", _OURO_BRILHO)
    cubo.reparentTo(raiz)

    def atualizar(fase: float) -> None:
        _atualizar_poeira_passo(puffs, cubo, stage, lado, fase, escala)

    mgr.emitir_3d(
        raiz,
        origem,
        tipo_mesh="poeira_passo_blockbench",
        ttl=0.40,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=atualizar,
    )
    atualizar(0.0)


def _atualizar_tontura(
    estrelas: tuple[NodePath, ...],
    cubos: tuple[NodePath, NodePath],
    fase: float,
    escala: float,
) -> None:
    env = min(1.0, fase / 0.14) * min(1.0, (1.0 - fase) / 0.20)
    rx, rz = 1.28 * escala, 0.26 * escala
    for i, st in enumerate(estrelas):
        ang = fase * 3.6 * pi + i * (2.0 * pi / 3.0)
        tam = 0.64 * escala * env * (0.88 + 0.18 * sin(ang))
        if tam <= 0.02:
            st.hide()
            continue
        st.show()
        st.setPos(cos(ang) * rx, sin(ang) * 0.35 - 0.06, sin(ang) * rz)
        st.setR(sin(ang) * 18.0)
        st.setScale(tam, 1.0, tam * _N_COLS)
        st.setShaderInput("u_fade", env)
    for i, cb in enumerate(cubos):
        ang = -fase * 4.2 * pi + i * pi
        sc = 0.11 * escala * env
        if sc <= 0.015:
            cb.hide()
            continue
        cb.show()
        cb.setPos(cos(ang) * rx * 0.78, sin(ang) * 0.25 - 0.06, sin(ang) * rz * 0.9 + 0.14 * escala)
        cb.setHpr(ang * 55.0, 35.0, ang * 40.0)
        cb.setScale(sc)


def emitir_tontura(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """3 estrelas chunky + cubinhos orbitando em elipse acima da cabeça após chacoalhar."""
    del vel, dir_x
    origem = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, 0.0, 0.58)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("tontura_blockbench")
    estrelas = tuple(_cartao_celula(raiz, f"tontura_st_{i}", 15) for i in range(3))
    cubos = (_criar_cubo_voxel("tont_c0", _CIANO), _criar_cubo_voxel("tont_c1", _OURO_BRILHO))
    for cb in cubos:
        cb.reparentTo(raiz)

    def atualizar(fase: float) -> None:
        _atualizar_tontura(estrelas, cubos, fase, escala)

    mgr.emitir_3d(
        raiz,
        origem,
        tipo_mesh="tontura_blockbench",
        ttl=1.05,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=atualizar,
    )
    atualizar(0.0)


def _construir_ondas_radio(
    vdata: GeomVertexData,
    tris: GeomTriangles,
    rel_d: Vec3,
    rel_e: Vec3,
    fase: float,
    escala: float,
) -> None:
    if fase >= 0.94:
        return
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    idx = 0
    for origem, sinal in ((rel_d, -1.0), (rel_e, 1.0)):
        for atraso, cor_b, cor_m in ((0.0, _AZUL_DEEP, _CIANO), (0.22, _VERDE_FUNDO, _ESMERALDA)):
            if fase < atraso:
                continue
            u = min(1.0, (fase - atraso) / (1.0 - atraso))
            if u >= 0.92:
                continue
            raio = (0.24 + 0.82 * u) * escala
            esp = max(0.016, 0.068 * escala * (1.0 - u * 0.72))
            for k in range(5):
                t0, t1 = k / 5.0, (k + 1) / 5.0
                a0, a1 = (-0.36 + t0 * 0.72) * pi, (-0.36 + t1 * 0.72) * pi
                p0 = origem + Vec3(sinal * (0.14 + cos(a0) * raio), -0.06, 0.14 + sin(a0) * raio)
                p1 = origem + Vec3(sinal * (0.14 + cos(a1) * raio), -0.06, 0.14 + sin(a1) * raio)
                idx = _emitir_segmento_dungeons(vw, cw, tris, idx, p0, p1, esp, esp * 0.9, cor_b, cor_m, _BRANCO)
    tris.closePrimitive()


def emitir_sinal_radio(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Ondinhas de sintonia saindo das duas antenas (reação a áudio / busca de sinal)."""
    del pos, vel, dir_x
    ad, ae = anc.get("antena_d"), anc.get("antena_e")
    if ad is None or ae is None:
        return
    centro = (ad + ae) * 0.5
    rel_d, rel_e = ad - centro, ae - centro
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("sinal_radio_blockbench")
    arco_np, vdata, tris = _criar_no_arco(raiz)

    def atualizar(fase: float) -> None:
        _construir_ondas_radio(vdata, tris, rel_d, rel_e, fase, escala)
        arco_np.node().markInternalBoundsStale()
        (arco_np.hide if fase >= 0.94 else arco_np.show)()

    mgr.emitir_3d(
        raiz,
        centro,
        tipo_mesh="sinal_radio_blockbench",
        ttl=0.58,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=atualizar,
    )
    atualizar(0.0)


def _atualizar_curiosidade(interr: NodePath, brilho: NodePath, fase: float, escala: float) -> None:
    pop = min(1.14, fase / 0.15) if fase < 0.15 else (1.14 - 0.14 * min(1.0, (fase - 0.15) / 0.14))
    fim = min(1.0, (1.0 - fase) / 0.22)
    tam = 0.96 * escala * pop * fim
    if tam <= 0.02:
        interr.hide()
    else:
        interr.show()
        interr.setPos(0.0, -0.04, (0.12 + fase * 0.48) * escala)
        interr.setR(sin(fase * 2.5 * pi) * 9.0)
        interr.setScale(tam, 1.0, tam * _N_COLS)
        interr.setShaderInput("u_fade", fim)
    pulso = max(0.0, sin((fase * 2.0) * pi))
    tb = 0.52 * escala * pulso
    if tb <= 0.02:
        brilho.hide()
    else:
        brilho.show()
        brilho.setPos(0.62 * escala, -0.06, (0.58 + fase * 0.32) * escala)
        brilho.setScale(tb, 1.0, tb * _N_COLS)
        brilho.setShaderInput("u_fade", pulso)


def emitir_curiosidade(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """``?`` chunky + 2 brilhos sutis ao lado do visor (sem cobrir o rosto)."""
    del vel, dir_x
    origem = (Vec3(pos) if pos is not None else Vec3(anc["visor_lado"])) + Vec3(0.55, -0.08, 0.42)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("curiosidade_blockbench")
    interr = _cartao_celula(raiz, "curiosidade_q_bb", 12)
    brilho = _cartao_celula(raiz, "curiosidade_sp_bb", 13)

    def atualizar(fase: float) -> None:
        _atualizar_curiosidade(interr, brilho, fase, escala)

    mgr.emitir_3d(
        raiz,
        origem,
        tipo_mesh="curiosidade_blockbench",
        ttl=0.68,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=atualizar,
    )
    atualizar(0.0)


def _atualizar_brilho_estilo(
    estrelas: tuple[tuple[NodePath, Vec3, float, float], ...],
    cubos: tuple[NodePath, NodePath],
    fase: float,
    escala: float,
) -> None:
    for st, off, atraso, tam_b in estrelas:
        if fase < atraso:
            st.hide()
            continue
        u = min(1.0, (fase - atraso) / (1.0 - atraso))
        pulso = sin(u * pi) ** 0.72
        tam = tam_b * escala * pulso
        if tam <= 0.02:
            st.hide()
            continue
        st.show()
        st.setPos(off * escala + Vec3(0.0, 0.0, u * 0.28 * escala))
        st.setR(u * 24.0)
        st.setScale(tam, 1.0, tam * _N_COLS)
        st.setShaderInput("u_fade", pulso)
    for i, cb in enumerate(cubos):
        pulso = max(0.0, sin((fase * 2.4 + i * 0.4) * pi))
        if pulso <= 0.12:
            cb.hide()
            continue
        cb.show()
        cb.setPos(((-0.42, 0.52)[i]) * escala, -0.08, (0.52 + fase * 0.55) * escala)
        cb.setHpr(45.0, 35.0, fase * 160.0)
        cb.setScale(0.12 * escala * pulso)


def emitir_brilho_estilo(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """3 estrelinhas *sparkle* de 4 pontas + cubinho dourado (orgulho, estilo, vitória)."""
    del vel, dir_x
    origem = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.10, 0.40)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("brilho_estilo_blockbench")
    estrelas = (
        (_cartao_celula(raiz, "estilo_s0", 13), Vec3(-0.78, -0.06, 0.18), 0.00, 0.82),
        (_cartao_celula(raiz, "estilo_s1", 13), Vec3(0.84, -0.06, 0.42), 0.16, 0.96),
        (_cartao_celula(raiz, "estilo_s2", 13), Vec3(0.06, -0.06, 0.78), 0.30, 0.70),
    )
    cubos = (_criar_cubo_voxel("estilo_c0", _OURO_BRILHO), _criar_cubo_voxel("estilo_c1", _BRANCO))
    for cb in cubos:
        cb.reparentTo(raiz)

    def atualizar(fase: float) -> None:
        _atualizar_brilho_estilo(estrelas, cubos, fase, escala)

    mgr.emitir_3d(
        raiz,
        origem,
        tipo_mesh="brilho_estilo_blockbench",
        ttl=0.72,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=atualizar,
    )
    atualizar(0.0)


def _desenhar_gota_bb(img, x0: int) -> None:
    ink, cyan, white = (0.08, 0.12, 0.22, 1.0), (0.14, 0.85, 1.0, 1.0), (0.94, 0.99, 1.0, 1.0)
    for y in range(2, 14):
        larg = min(4, (y - 1) // 2 if y < 10 else (14 - y))
        for dx in range(-larg, larg + 1):
            is_edge = abs(dx) == larg or y in (2, 13)
            col = ink if is_edge else (white if dx == -1 and y in (7, 8, 9) else cyan)
            img.setXelA(x0 + 8 + dx, y, *col)


def _desenhar_nuvem_gloom_bb(img, x0: int) -> None:
    ink, slate, rain = (0.08, 0.12, 0.20, 1.0), (0.28, 0.45, 0.62, 1.0), (0.45, 0.82, 0.98, 1.0)
    for y in range(7, 13):
        for x in range(2, 14):
            borda = y in (7, 12) or x in (2, 13) or (y >= 11 and x in (3, 12))
            img.setXelA(x0 + x, y, *(ink if borda else slate))
    for rx in (4, 8, 11):
        for ry in (2, 3, 4, 5):
            img.setXelA(x0 + rx, ry, *rain)


def _textura_micro_bb() -> Texture:
    return _cache_textura_micro_bb()


@cache
def _cache_textura_micro_bb() -> Texture:
    img = PNMImage(64, 16, 4)
    img.fill(0.0, 0.0, 0.0)
    img.alphaFill(0.0)
    _desenhar_gota_bb(img, 0)
    _desenhar_nuvem_gloom_bb(img, 16)
    ink, gold, white, lime = (0.09, 0.10, 0.14, 1.0), (1.0, 0.86, 0.18, 1.0), (0.98, 0.98, 0.95, 1.0), (0.46, 0.94, 0.30, 1.0)
    for px, py in ((8, 3), (8, 12), (3, 8), (12, 8), (5, 5), (10, 5), (5, 10), (10, 10)):
        img.setXelA(32 + px, py, *(white if (px + py) % 2 == 0 else gold))
    for x in range(3, 14):
        for y in range(4, 12):
            if abs(y - 8) <= (x - 2) // 2:
                img.setXelA(48 + x, y, *(ink if abs(y - 8) == (x - 2) // 2 or x == 13 else lime))
    tex = textura_pixel("micro_vfx_bb_v1", img)
    tex.setFormat(Texture.FSrgbAlpha)
    return tex


def _micro_bb_card(raiz: NodePath, nome: str, celula: int) -> NodePath:
    stage = TextureStage.getDefault()
    c = cartao_pixel(raiz, nome, _textura_micro_bb())
    c.setTexScale(stage, 0.25, 1.0)
    c.setTexOffset(stage, celula * 0.25, 0.0)
    return c


def _registrar_bb(mgr: GerenciadorEfeitosStreet, raiz: NodePath, origem: Vec3, nome: str, ttl: float, fn) -> None:
    mgr.emitir_3d(
        raiz,
        origem,
        tipo_mesh=f"{nome}_blockbench",
        ttl=ttl,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=fn,
    )
    fn(0.0)


def emitir_suor(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Gota voxel Blockbench descendo na têmpora (esforço / susto)."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    origem = Vec3(pos) if pos is not None else Vec3(anc.get("templo", anc["visor_lado"])) + Vec3(0.42 * lado, -0.08, 0.24)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("suor_blockbench")
    gota = _micro_bb_card(raiz, "bb_suor", 0)

    def atualizar(fase: float) -> None:
        fim = min(1.0, (1.0 - fase) / 0.24)
        tam = 0.88 * escala * min(1.0, fase / 0.16) * fim
        (gota.hide if tam <= 0.03 else gota.show)()
        gota.setPos(0.14 * lado * escala, -0.10, (0.18 - fase * 0.72) * escala)
        gota.setScale(tam, 1.0, tam * 4.0)
        gota.setShaderInput("u_fade", fim)

    _registrar_bb(mgr, raiz, origem, "suor", 0.60, atualizar)


def emitir_suspiro(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Puff cúbico de suspiro saindo ao lado do visor no modo Blockbench."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    origem = Vec3(pos) if pos is not None else Vec3(anc.get("visor_lado", anc["cabeca_topo"])) + Vec3(0.45 * lado, -0.08, 0.05)
    escala = max(0.75, min(1.30, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("suspiro_blockbench")
    puff = _cartao_puff_dungeons(raiz, "bb_suspiro")

    def atualizar(fase: float) -> None:
        fim = min(1.0, (1.0 - fase) / 0.28)
        tam = 0.78 * escala * min(1.0, fase / 0.16) * fim
        (puff.hide if tam <= 0.03 else puff.show)()
        puff.setTexOffset(stage, min(5, int(fase * 5.8)) / 8.0, 0.0)
        puff.setPos(lado * (0.25 + fase * 0.85) * escala, -0.10, -fase * 0.24 * escala)
        puff.setScale(tam * lado, 1.0, tam * 10.0)
        puff.setShaderInput("u_fade", fim)

    _registrar_bb(mgr, raiz, origem, "suspiro", 0.66, atualizar)


def emitir_tristeza(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Nuvem chuvosa Blockbench pairando suavemente acima da cabeça."""
    del vel, dir_x
    origem = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.08, 0.76)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("tristeza_blockbench")
    nuvem = _micro_bb_card(raiz, "bb_tristeza", 1)

    def atualizar(fase: float) -> None:
        env = min(1.0, fase / 0.18) * min(1.0, (1.0 - fase) / 0.24)
        tam = 1.28 * escala * env
        (nuvem.hide if tam <= 0.03 else nuvem.show)()
        nuvem.setPos(sin(fase * 2.0 * pi) * 0.12 * escala, -0.10, 0.15 * escala)
        nuvem.setScale(tam, 1.0, tam * 4.0)
        nuvem.setShaderInput("u_fade", env)

    _registrar_bb(mgr, raiz, origem, "tristeza", 0.95, atualizar)


def emitir_estalo_fone(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Estalo sonoro dourado na concha do fone ao ajustar ou dar toque."""
    del vel
    chave = "fone_dir" if dir_x >= 0 else "fone_esq"
    origem = (Vec3(pos) if pos is not None else Vec3(anc.get(chave, anc["cabeca_topo"]))) + Vec3(0.30 * (1.0 if dir_x >= 0 else -1.0), -0.10, 0.12)
    escala = max(0.70, min(1.30, float(forca)))
    raiz = NodePath("estalo_fone_blockbench")
    spark = _micro_bb_card(raiz, "bb_estalo", 2)

    def atualizar(fase: float) -> None:
        snap = 1.18 if fase < 0.26 else max(0.0, (1.0 - fase) / 0.74)
        tam = 0.96 * escala * snap
        (spark.hide if tam <= 0.03 else spark.show)()
        spark.setR(fase * 90.0)
        spark.setScale(tam, 1.0, tam * 4.0)
        spark.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.26))

    _registrar_bb(mgr, raiz, origem, "estalo_fone", 0.28, atualizar)


def emitir_espirro(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Espirro Blockbench: cone esmeralda + cubo de poeira projetado da frente."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    origem = Vec3(pos) if pos is not None else Vec3(anc.get("porta", anc.get("visor_lado", anc["tronco"])))
    escala = max(0.75, min(1.35, float(forca)))
    raiz = NodePath("espirro_blockbench")
    cone = _micro_bb_card(raiz, "bb_espirro", 3)

    def atualizar(fase: float) -> None:
        u = 1.0 - (1.0 - fase) ** 2
        fim = min(1.0, (1.0 - fase) / 0.24)
        tam = 1.18 * escala * min(1.0, fase / 0.14) * fim
        (cone.hide if tam <= 0.03 else cone.show)()
        cone.setPos(lado * (0.45 + u * 0.95) * escala, -0.12, (0.10 - u * 0.16) * escala)
        cone.setScale(tam * lado, 1.0, tam * 4.0)
        cone.setShaderInput("u_fade", fim)

    _registrar_bb(mgr, raiz, origem, "espirro", 0.42, atualizar)
