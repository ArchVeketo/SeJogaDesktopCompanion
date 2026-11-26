"""VFX autorais do estilo ``anime`` (Manpu Emocional, Line Art Fina, Sakuga & Drama JoJo).

Fiel à prancha ``docs/referencias_vfx/ref_anime.png``:
- Emoções sutis e imediatas em *manpu* (*kirakira*, cruzinhas *smug*, veia *ikari* + ``ゴゴゴ``,
  barras radiais de susto + zigue-zague amarelo de tremor, coração/Zzz/? com line art fina).
- Impactos físicos elegantes e contidos (poeira cel-shaded com espaço negativo, *speedlines* finas,
  flash nanquim P&B).
"""

from __future__ import annotations

from functools import cache
from math import cos, exp, pi, sin
from typing import TYPE_CHECKING

from panda3d.core import (
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
from sejoga.render.vfx.acao_blockbench import _emitir_segmento_dungeons
from sejoga.render.vfx.choque_blockbench import (
    _CORONA_DIR,
    _CORONA_ESQ,
    _criar_no_arco,
    _pontos_antenas_vivos,
)
from sejoga.render.vfx.emocoes_blockbench import _criar_rubor_cabeca

if TYPE_CHECKING:
    from sejoga.render.efeitos_street import GerenciadorEfeitosStreet

_N_COLS = 16
_LINE = (0.09, 0.09, 0.14, 1.0)
_WHITE = (0.99, 0.99, 0.98, 1.0)
_SKY = (0.30, 0.77, 1.00, 1.0)
_GOLD = (1.00, 0.88, 0.22, 1.0)
_CORAL = (0.95, 0.27, 0.31, 1.0)


@cache
def _textura_anime() -> Texture:
    caminho = assets_dir() / "textures" / "vfx_anime" / "anime_manpu.png"
    img = PNMImage()
    if not img.read(StringStream(caminho.read_bytes()), caminho.name):
        raise ValueError(f"Atlas inválido: {caminho}")
    tex = textura_pixel("anime_manpu_v1", img)
    tex.setFormat(Texture.FSrgbAlpha)
    return tex


def _manpu(raiz: NodePath, nome: str, celula: int) -> NodePath:
    stage = TextureStage.getDefault()
    c = cartao_pixel(raiz, nome, _textura_anime())
    c.setTexScale(stage, 1.0 / _N_COLS, 1.0)
    c.setTexOffset(stage, celula / _N_COLS, 0.0)
    return c


def _registrar(mgr: GerenciadorEfeitosStreet, raiz: NodePath, pos: Vec3, nome: str, ttl: float, fn) -> None:
    mgr.emitir_3d(
        raiz,
        pos,
        tipo_mesh=f"{nome}_anime",
        ttl=ttl,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=fn,
    )
    fn(0.0)


def _desenhar_anel_anime(vdata, tris, fase: float, escala: float) -> None:
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    ab = 1.0 - (1.0 - min(1.0, fase / 0.50)) ** 3
    rx, esp = (0.72 + 1.68 * ab) * escala, max(0.016, 0.075 * escala * (1.0 - fase * 0.76))
    idx = 0
    for k in range(10):
        a0, a1 = (k / 10.0) * 2.0 * pi, ((k + 1) / 10.0) * 2.0 * pi
        p0 = Vec3(cos(a0) * rx, -0.06, 0.06 + sin(a0) * 0.18 * escala)
        p1 = Vec3(cos(a1) * rx, -0.06, 0.06 + sin(a1) * 0.18 * escala)
        idx = _emitir_segmento_dungeons(vw, cw, tris, idx, p0, p1, esp, esp, _LINE, _WHITE, _WHITE)
    tris.closePrimitive()


def emitir_impacto_chao(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Pouso Sakuga: anel fino nanquim + 4 nuvens cel-shaded abrindo espaço negativo."""
    del pos, vel, dir_x
    esq = anc.get("sola_esq", anc["pes"] + Vec3(-0.7, 0, 0))
    dir_ = anc.get("sola_dir", anc["pes"] + Vec3(0.7, 0, 0))
    centro = Vec3((esq.x + dir_.x) * 0.5, (esq.y + dir_.y) * 0.5, min(esq.z, dir_.z))
    escala = max(0.70, min(1.40, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("impacto_chao_anime")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    puffs = [(_manpu(raiz, f"an_pf_{i}", 0), s, i * 0.06) for i, s in enumerate((-1.0, 1.0, -0.75, 0.75))]

    def atualizar(fase: float) -> None:
        if fase < 0.86:
            _desenhar_anel_anime(vdata, tris, fase, escala)
            arco_np.node().markInternalBoundsStale()
            arco_np.show()
        else:
            arco_np.hide()
        for pf, lado, at in puffs:
            u = max(0.0, (fase - at) / (1.0 - at))
            tam = (0.72 + 0.52 * min(1.0, u * 4.5)) * escala * min(1.0, (1.0 - u) / 0.25)
            (pf.hide if fase < at or tam <= 0.03 else pf.show)()
            pf.setTexOffset(stage, (1 if u > 0.56 else 0) / _N_COLS, 0.0)
            pf.setPos(lado * (0.65 + (1.0 - exp(-4.8 * u)) * 1.48) * escala, -0.08, (0.28 + u * 0.14) * escala)
            pf.setScale(tam * lado, 1.0, tam * _N_COLS)
            pf.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.20))

    _registrar(mgr, raiz, centro, "impacto_chao", 0.48, atualizar)


def _desenhar_linhas_parede_anime(vdata, tris, normal: Vec3, tang: Vec3, fase: float, escala: float) -> None:
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    ab = 1.0 - (1.0 - min(1.0, fase / 0.48)) ** 3
    ret = max(0.0, (fase - 0.50) / 0.38)
    esp = max(0.016, 0.068 * escala * (1.0 - ret * 0.7))
    idx = 0
    for ang_f in (-0.95, -0.52, -0.15, 0.18, 0.56, 0.95):
        d = (tang * ang_f + normal * 0.32).normalized()
        r0, r1 = (0.18 + 0.72 * ret) * escala, (0.58 + 1.15 * ab) * escala
        if r1 > r0 + 0.04:
            idx = _emitir_segmento_dungeons(vw, cw, tris, idx, d * r0, d * r1, esp * 0.65, esp * 0.12, _LINE, _WHITE, _WHITE)
    tris.closePrimitive()


def emitir_impacto_parede(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Colisão Sakuga na parede: flash nanquim P&B + 6 *speedlines* finas na normal."""
    origem = Vec3(pos) if pos is not None else Vec3(anc.get("lado_dir", anc["tronco"]))
    normal = Vec3(vel.x, 0.0, vel.z) if vel is not None else Vec3(-dir_x, 0.0, 0.0)
    normal = normal.normalized() if normal.lengthSquared() > 1e-4 else Vec3(-dir_x, 0.0, 0.0)
    tang = Vec3(-normal.z, 0.0, normal.x)
    escala = max(0.70, min(1.40, float(forca)))
    raiz = NodePath("impacto_parede_anime")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    flash = _manpu(raiz, "an_flash_p", 14)

    def atualizar(fase: float) -> None:
        if fase < 0.88:
            _desenhar_linhas_parede_anime(vdata, tris, normal, tang, fase, escala)
            arco_np.node().markInternalBoundsStale()
            arco_np.show()
        else:
            arco_np.hide()
        tf = 1.48 * escala * (1.0 - fase / 0.32) if fase < 0.30 else 0.0
        (flash.hide if tf <= 0.03 else flash.show)()
        flash.setPos(normal * (0.20 * escala) + Vec3(0, -0.10, 0))
        flash.setScale(tf, 1.0, tf * _N_COLS)
        flash.setShaderInput("u_fade", 1.0)

    _registrar(mgr, raiz, origem, "impacto_parede", 0.38, atualizar)


def emitir_rastro(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Rastro Sakuga: 4 *speedlines* finas e afiadas ficando para trás em ``-velocidade``."""
    origem = Vec3(pos) if pos is not None else Vec3(anc["tronco"])
    d = Vec3(vel.x, 0.0, vel.z) if vel is not None else Vec3(-dir_x, 0.0, 0.0)
    d = d.normalized() if d.lengthSquared() > 1e-4 else Vec3(-dir_x, 0.0, 0.0)
    perp = Vec3(-d.z, 0.0, d.x)
    escala = max(0.75, min(1.40, float(forca)))
    raiz = NodePath("rastro_anime")
    arco_np, vdata, tris = _criar_no_arco(raiz)

    def atualizar(fase: float) -> None:
        if fase >= 0.90:
            arco_np.hide()
            return
        vdata.uncleanSetNumRows(0)
        tris.clearVertices()
        vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
        comp = 3.50 * escala * (1.0 - min(0.86, fase * 1.08))
        esp = max(0.015, 0.068 * escala * (1.0 - fase * 0.65))
        idx = 0
        for off, f_len in ((-0.92, 0.95), (-0.34, 1.08), (0.34, 0.86), (0.92, 1.0)):
            a = d * (0.68 * escala) + perp * (off * escala) + Vec3(0, -0.06, 0)
            idx = _emitir_segmento_dungeons(vw, cw, tris, idx, a, a + d * (comp * f_len), esp, esp * 0.14, _LINE, _SKY, _WHITE)
        tris.closePrimitive()
        arco_np.node().markInternalBoundsStale()
        arco_np.show()

    _registrar(mgr, raiz, origem, "rastro", 0.32, atualizar)


def _desenhar_choque_anime(vdata, tris, p_d: Vec3, p_e: Vec3, step: int, dist: float, escala: float) -> None:
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    r_b = dist * (0.024 if step < 2 else 0.016) * escala
    idx = 0
    for orig, sx, perfis in ((p_d, -1.0, _CORONA_DIR[step]), (p_e, 1.0, _CORONA_ESQ[step])):
        for pf in perfis:
            pts = [orig + Vec3(dx * sx * dist * 1.15, dy * dist, dz * dist * 1.15) for dx, dy, dz in pf]
            for k in range(len(pts) - 1):
                idx = _emitir_segmento_dungeons(vw, cw, tris, idx, pts[k], pts[k + 1], r_b, r_b * 0.35, _LINE, _SKY, _WHITE)
    tris.closePrimitive()


def emitir_choque(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Choque Anime: raios finos afiados SOMENTE nas antenas + zigue-zagues amarelos de tremor."""
    del pos, vel, dir_x
    ad, ae = anc.get("antena_d"), anc.get("antena_e")
    if ad is None or ae is None:
        return
    centro = (ad + ae) * 0.5
    fallback = (ad - centro, ae - centro)
    escala = max(0.75, min(1.35, float(forca)))
    raiz = NodePath("choque_anime")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    zzs = (_manpu(raiz, "an_zz_d", 7), _manpu(raiz, "an_zz_e", 7))

    def atualizar(fase: float) -> None:
        p_d, p_e = _pontos_antenas_vivos(mgr, raiz, fallback)
        dist = max(0.45, (p_e - p_d).length())
        step = 0 if fase < 0.28 else (1 if fase < 0.58 else (2 if fase < 0.82 else 3))
        if step < 3:
            _desenhar_choque_anime(vdata, tris, p_d, p_e, step, dist, escala)
            arco_np.node().markInternalBoundsStale()
            arco_np.show()
        else:
            arco_np.hide()
        tz = 0.82 * escala * (1.0 if step < 3 else 0.0)
        for i, (zz, pt, s) in enumerate(zip(zzs, (p_d, p_e), (-1.0, 1.0), strict=True)):
            (zz.hide if tz <= 0.03 else zz.show)()
            zz.setPos(pt + Vec3(s * 0.42 * escala, -0.10, (0.12 if step % 2 == i else -0.12) * escala))
            zz.setScale(tz * s, 1.0, tz * _N_COLS)
            zz.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))

    _registrar(mgr, raiz, centro, "choque", 0.36, atualizar)


def emitir_irritado(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Irritado Anime/JoJo: veia *ikari* no templo + hachura vermelha + katakanas ``ゴゴゴ``."""
    del pos, vel, dir_x
    topo = Vec3(anc["cabeca_topo"])
    templo_rel = Vec3(anc.get("templo", topo + Vec3(0.95, 0.0, -0.45))) - topo
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("irritado_anime")
    rubor = _criar_rubor_cabeca(raiz)
    ikari = _manpu(raiz, "an_ikari", 4)
    gos = (
        (_manpu(raiz, "an_go_0", 5), Vec3(-1.58, 0.12, -0.35), 0.00, 1.15),
        (_manpu(raiz, "an_go_1", 5), Vec3(1.62, 0.12, 0.15), 0.12, 1.32),
        (_manpu(raiz, "an_go_2", 5), Vec3(-1.32, 0.12, 0.82), 0.24, 0.96),
    )

    def atualizar(fase: float) -> None:
        fr = min(1.0, fase / 0.16) * min(1.0, (1.0 - fase) / 0.26)
        rubor.setPos(0.0, -0.48, 0.0)
        rubor.setScale(escala, 1.0, escala)
        rubor.setShaderInput("u_forca", fr * 0.92)
        pulso = 1.0 + 0.18 * abs(sin(fase * 3.0 * pi))
        ti = 1.05 * escala * pulso * min(1.0, fase / 0.10) * min(1.0, (1.0 - fase) / 0.20)
        ikari.setPos(templo_rel + Vec3(0.72 * escala, -0.14, 0.22 * escala))
        ikari.setScale(ti, 1.0, ti * _N_COLS)
        ikari.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))
        for go, off, at, tb in gos:
            u = max(0.0, (fase - at) / (1.0 - at))
            tg = tb * escala * min(1.0, u / 0.18) * min(1.0, (1.0 - u) / 0.24)
            (go.hide if fase < at or tg <= 0.03 else go.show)()
            go.setPos(off * escala + Vec3(sin(u * 4.0 * pi) * 0.08 * escala, 0.0, u * 0.72 * escala))
            go.setR(-8.0 + sin(u * 3.0 * pi) * 5.0)
            go.setScale(tg, 1.0, tg * _N_COLS)
            go.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))

    _registrar(mgr, raiz, topo, "irritado", 0.92, atualizar)


def emitir_sobressalto(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Susto Manpu (Painel 3 da ref_anime): 5 barras radiais coral + 2 zigue-zagues de tremor."""
    del pos, vel, dir_x
    topo = Vec3(anc["cabeca_topo"])
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("sobressalto_anime")
    barras = [(_manpu(raiz, f"an_bar_{i}", 6), ang) for i, ang in enumerate((-62.0, -30.0, 0.0, 30.0, 62.0))]
    zzs = [(_manpu(raiz, f"an_szz_{i}", 7), s) for i, s in enumerate((-1.0, 1.0))]

    def atualizar(fase: float) -> None:
        snap = 1.18 if fase < 0.16 else (1.0 if fase < 0.72 else max(0.0, (1.0 - fase) / 0.28))
        for bar, ang in barras:
            rad = ang * pi / 180.0
            tb = 0.88 * escala * snap
            (bar.hide if tb <= 0.03 else bar.show)()
            bar.setPos(sin(rad) * 1.48 * escala * snap, -0.08, (0.28 + cos(rad) * 0.95 * snap) * escala)
            bar.setR(ang)
            bar.setScale(tb, 1.0, tb * _N_COLS)
            bar.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))
        for zz, s in zzs:
            tz = 0.78 * escala * snap
            (zz.hide if tz <= 0.03 else zz.show)()
            zz.setPos(s * 1.82 * escala, -0.08, (-0.35 + (0.08 if int(fase * 16) % 2 == 0 else -0.08)) * escala)
            zz.setScale(tz * s, 1.0, tz * _N_COLS)
            zz.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))

    _registrar(mgr, raiz, topo, "sobressalto", 0.34, atualizar)


def emitir_carinho(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Carinho Anime: coração delicado + 2 cruzinhas amarelas *smug*/satisfação (Painel 8)."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.08, 0.42)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("carinho_anime")
    cor = _manpu(raiz, "an_cor", 8)
    smugs = [(_manpu(raiz, f"an_smug_{i}", 3), s) for i, s in enumerate((-1.0, 1.0))]

    def atualizar(fase: float) -> None:
        pop = min(1.14, fase / 0.14) if fase < 0.14 else (1.14 - 0.14 * min(1.0, (fase - 0.14) / 0.12))
        fim = min(1.0, (1.0 - fase) / 0.22)
        tc = 1.12 * escala * pop * fim
        (cor.hide if tc <= 0.03 else cor.show)()
        cor.setPos(sin(fase * 2.0 * pi) * 0.18 * escala, -0.04, fase * 1.18 * escala)
        cor.setR(sin(fase * 2.0 * pi) * 8.0)
        cor.setScale(tc, 1.0, tc * _N_COLS)
        cor.setShaderInput("u_fade", fim)
        for sm, s in smugs:
            p = max(0.0, sin((fase * 2.2 + (0.0 if s < 0 else 0.35)) * pi))
            ts = 0.72 * escala * p
            (sm.hide if ts <= 0.03 else sm.show)()
            sm.setPos(s * 1.08 * escala, -0.06, (0.35 + fase * 0.65) * escala)
            sm.setScale(ts, 1.0, ts * _N_COLS)
            sm.setShaderInput("u_fade", p)

    _registrar(mgr, raiz, orig, "carinho", 0.88, atualizar)


def emitir_sono(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Sono Anime: ``z`` -> ``Z`` delicados subindo em curva S suave ao lado do visor."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["visor_lado"])) + Vec3(0.45, -0.06, 0.24)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("sono_anime")
    zs = ((_manpu(raiz, "an_z0", 9), 0.0, 0.76, 0.0), (_manpu(raiz, "an_z1", 9), 0.28, 1.08, 0.42))

    def atualizar(fase: float) -> None:
        for z, at, tb, dx in zs:
            u = max(0.0, (fase - at) / (1.0 - at))
            env = min(1.0, u / 0.20) * min(1.0, (1.0 - u) / 0.24)
            tam = tb * escala * env
            (z.hide if fase < at or tam <= 0.03 else z.show)()
            z.setPos((dx + u * 0.62 + sin(u * 2.0 * pi) * 0.20) * escala, -0.05, u * 1.48 * escala)
            z.setR(sin(u * 2.0 * pi) * 10.0)
            z.setScale(tam, 1.0, tam * _N_COLS)
            z.setShaderInput("u_fade", env)

    _registrar(mgr, raiz, orig, "sono", 1.12, atualizar)


def emitir_curiosidade(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Curiosidade Anime: ``?`` limpo + *kirakira* sutil ao lado do visor."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["visor_lado"])) + Vec3(0.56, -0.06, 0.42)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("curiosidade_anime")
    q, kk = _manpu(raiz, "an_q", 10), _manpu(raiz, "an_kk", 2)

    def atualizar(fase: float) -> None:
        fim = min(1.0, (1.0 - fase) / 0.22)
        tq = 1.06 * escala * min(1.14, fase / 0.14) * fim
        (q.hide if tq <= 0.03 else q.show)()
        q.setPos(0.0, -0.05, (0.12 + fase * 0.52) * escala)
        q.setR(sin(fase * 2.5 * pi) * 8.0)
        q.setScale(tq, 1.0, tq * _N_COLS)
        q.setShaderInput("u_fade", fim)
        p = max(0.0, sin(fase * 2.0 * pi))
        tk = 0.58 * escala * p
        (kk.hide if tk <= 0.03 else kk.show)()
        kk.setPos(0.62 * escala, -0.06, (0.58 + fase * 0.28) * escala)
        kk.setScale(tk, 1.0, tk * _N_COLS)
        kk.setShaderInput("u_fade", p)

    _registrar(mgr, raiz, orig, "curiosidade", 0.68, atualizar)


def emitir_brilho_estilo(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Empolgação / orgulho Anime: 3 *kirakira* amarelos 4 pontas (Painel 1 da ref_anime)."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.08, 0.42)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("brilho_estilo_anime")
    stars = (
        (_manpu(raiz, "an_kk0", 2), Vec3(-0.96, -0.06, 0.18), 0.00, 0.92),
        (_manpu(raiz, "an_kk1", 2), Vec3(0.98, -0.06, 0.44), 0.14, 1.12),
        (_manpu(raiz, "an_kk2", 2), Vec3(0.02, -0.06, 0.86), 0.28, 0.82),
    )

    def atualizar(fase: float) -> None:
        for st, off, at, tb in stars:
            u = max(0.0, (fase - at) / (1.0 - at))
            p = sin(u * pi) ** 0.70 if fase >= at else 0.0
            tam = tb * escala * p
            (st.hide if tam <= 0.03 else st.show)()
            st.setPos(off * escala + Vec3(0, 0, u * 0.24 * escala))
            st.setScale(tam, 1.0, tam * _N_COLS)
            st.setShaderInput("u_fade", p)

    _registrar(mgr, raiz, orig, "brilho_estilo", 0.74, atualizar)


def _desenhar_arco_musica_anime(vdata, tris, lado: float, fase: float, escala: float) -> None:
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    raio, av = (0.38 + 1.18 * fase) * escala, (0.20 + 0.96 * fase) * escala * lado
    esp = max(0.014, 0.062 * escala * (1.0 - fase * 0.74))
    idx = 0
    for k in range(6):
        a0, a1 = (-0.40 + (k / 6.0) * 0.80) * pi, (-0.40 + ((k + 1) / 6.0) * 0.80) * pi
        p0 = Vec3(av + cos(a0) * raio * 0.40 * lado, -0.06, sin(a0) * raio)
        p1 = Vec3(av + cos(a1) * raio * 0.40 * lado, -0.06, sin(a1) * raio)
        idx = _emitir_segmento_dungeons(vw, cw, tris, idx, p0, p1, esp, esp, _LINE, _SKY, _WHITE)
    tris.closePrimitive()


def emitir_musica(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Música Anime: nota ``♪`` limpa + arco fino cel-shaded fora do rosto."""
    del vel
    lado = -1.0 if dir_x < 0 else 1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("fone_esq" if lado > 0 else "fone_dir", anc["cabeca_topo"]))
    escala = max(0.70, min(1.35, float(forca)))
    raiz = NodePath("musica_anime")
    nota = _manpu(raiz, "an_nota", 11)
    arco_np, vdata, tris = _criar_no_arco(raiz)

    def atualizar(fase: float) -> None:
        if fase < 0.88:
            _desenhar_arco_musica_anime(vdata, tris, lado, fase, escala)
            arco_np.node().markInternalBoundsStale()
            arco_np.show()
        else:
            arco_np.hide()
        tn = 0.96 * escala * min(1.0, fase / 0.16) * min(1.0, (1.0 - fase) / 0.24)
        (nota.hide if tn <= 0.03 else nota.show)()
        nota.setPos(lado * (0.56 + 0.84 * fase) * escala, 0.12, (0.44 + 0.82 * fase) * escala)
        nota.setR(sin(fase * 2.0 * pi) * 10.0)
        nota.setScale(tn, 1.0, tn * _N_COLS)
        nota.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.22))

    _registrar(mgr, raiz, orig, "musica", 0.42, atualizar)


def emitir_sinal_radio(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Sinal de rádio Anime: ondas finas limpas saindo das antenas."""
    del pos, vel, dir_x
    ad, ae = anc.get("antena_d"), anc.get("antena_e")
    if ad is None or ae is None:
        return
    centro = (ad + ae) * 0.5
    rel_d, rel_e = ad - centro, ae - centro
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("sinal_radio_anime")
    arco_np, vdata, tris = _criar_no_arco(raiz)

    def atualizar(fase: float) -> None:
        if fase >= 0.92:
            arco_np.hide()
            return
        vdata.uncleanSetNumRows(0)
        tris.clearVertices()
        vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
        idx = 0
        for orig, s in ((rel_d, -1.0), (rel_e, 1.0)):
            raio, esp = (0.24 + 0.86 * fase) * escala, max(0.014, 0.056 * escala * (1.0 - fase * 0.7))
            for k in range(5):
                a0, a1 = (-0.36 + (k / 5.0) * 0.72) * pi, (-0.36 + ((k + 1) / 5.0) * 0.72) * pi
                p0 = orig + Vec3(s * (0.14 + cos(a0) * raio), -0.06, 0.14 + sin(a0) * raio)
                p1 = orig + Vec3(s * (0.14 + cos(a1) * raio), -0.06, 0.14 + sin(a1) * raio)
                idx = _emitir_segmento_dungeons(vw, cw, tris, idx, p0, p1, esp, esp, _LINE, _SKY, _WHITE)
        tris.closePrimitive()
        arco_np.node().markInternalBoundsStale()
        arco_np.show()

    _registrar(mgr, raiz, centro, "sinal_radio", 0.56, atualizar)


def emitir_tontura(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Tontura Anime: espirais + *kirakira* orbitando acima da cabeça."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, 0.0, 0.62)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("tontura_anime")
    itens = (_manpu(raiz, "an_sp0", 12), _manpu(raiz, "an_sp1", 2), _manpu(raiz, "an_sp2", 12))

    def atualizar(fase: float) -> None:
        env = min(1.0, fase / 0.14) * min(1.0, (1.0 - fase) / 0.20)
        for i, it in enumerate(itens):
            ang = fase * 3.6 * pi + i * (2.0 * pi / 3.0)
            tam = 0.82 * escala * env * (0.88 + 0.18 * sin(ang))
            (it.hide if tam <= 0.03 else it.show)()
            it.setPos(cos(ang) * 1.32 * escala, sin(ang) * 0.35 - 0.06, sin(ang) * 0.28 * escala)
            it.setR(fase * 260.0)
            it.setScale(tam, 1.0, tam * _N_COLS)
            it.setShaderInput("u_fade", env)

    _registrar(mgr, raiz, orig, "tontura", 1.05, atualizar)


def emitir_poeira_passo(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Poeira Sakuga cel-shaded com espaço negativo atrás do tênis ao correr/derrapar."""
    del vel
    lado = -1.0 if dir_x >= 0 else 1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("pes", anc["tronco"]))
    escala = max(0.65, min(1.30, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("poeira_passo_anime")
    puffs = [(_manpu(raiz, f"an_pp_{i}", 0), i * 0.10, 0.88 - i * 0.14) for i in range(2)]

    def atualizar(fase: float) -> None:
        for i, (pf, at, tb) in enumerate(puffs):
            u = max(0.0, (fase - at) / (1.0 - at))
            tam = tb * escala * (0.58 + 0.52 * min(1.0, u * 4.0)) * min(1.0, (1.0 - u) / 0.26)
            (pf.hide if fase < at or tam <= 0.03 else pf.show)()
            pf.setTexOffset(stage, (1 if u > 0.58 else 0) / _N_COLS, 0.0)
            pf.setPos(lado * (0.98 + (1.0 - exp(-4.4 * u)) * (0.92 + i * 0.35)) * escala, -0.14, (0.28 + u * 0.68) * escala)
            pf.setR(-lado * (14.0 + u * 18.0))
            pf.setScale(tam * lado, 1.0, tam * _N_COLS)
            pf.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))

    _registrar(mgr, raiz, orig, "poeira_passo", 0.40, atualizar)


def emitir_suor(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Gota de suor anime clássico escorrendo pela têmpora."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("templo", anc["visor_lado"])) + Vec3(0.42 * lado, -0.08, 0.24)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("suor_anime")
    gotas = (_manpu(raiz, "an_suor_0", 1), _manpu(raiz, "an_suor_1", 15))

    def atualizar(fase: float) -> None:
        fim = min(1.0, (1.0 - fase) / 0.24)
        for i, gt in enumerate(gotas):
            tam = (0.95 if i == 0 else 0.55) * escala * min(1.0, fase / 0.14) * fim
            (gt.hide if tam <= 0.03 else gt.show)()
            gt.setPos((0.14 + i * 0.12) * lado * escala, -0.10, (0.20 - fase * 0.80 - i * 0.18) * escala)
            gt.setScale(tam, 1.0, tam * _N_COLS)
            gt.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, "suor", 0.62, atualizar)


def emitir_suspiro(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Suspiro anime com espaço negativo escapando lentamente do visor."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("visor_lado", anc["cabeca_topo"])) + Vec3(0.45 * lado, -0.08, 0.04)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("suspiro_anime")
    puff = _manpu(raiz, "an_suspiro", 0)

    def atualizar(fase: float) -> None:
        fim = min(1.0, (1.0 - fase) / 0.28)
        tam = 0.86 * escala * min(1.0, fase / 0.16) * fim
        (puff.hide if tam <= 0.03 else puff.show)()
        puff.setPos(lado * (0.28 + fase * 0.85) * escala, -0.10, -fase * 0.22 * escala)
        puff.setScale(tam * lado, 1.0, tam * _N_COLS)
        puff.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, "suspiro", 0.68, atualizar)


def emitir_tristeza(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Riscos verticais *gloom* anime pairando sobre a silhueta."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.55, -0.08, 0.66)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("tristeza_anime")
    linhas = _manpu(raiz, "an_gloom", 13)

    def atualizar(fase: float) -> None:
        env = min(1.0, fase / 0.18) * min(1.0, (1.0 - fase) / 0.24)
        tam = 1.42 * escala * env
        (linhas.hide if tam <= 0.03 else linhas.show)()
        linhas.setPos(0.0, -0.10, -fase * 0.16 * escala)
        linhas.setScale(tam, 1.0, tam * _N_COLS)
        linhas.setShaderInput("u_fade", env)

    _registrar(mgr, raiz, orig, "tristeza", 0.96, atualizar)


def emitir_estalo_fone(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """*Kirakira* nítido no fone ao dar ajuste rápido."""
    del vel
    chave = "fone_dir" if dir_x >= 0 else "fone_esq"
    orig = (Vec3(pos) if pos is not None else Vec3(anc.get(chave, anc["cabeca_topo"]))) + Vec3(0.28 * (1.0 if dir_x >= 0 else -1.0), -0.10, 0.12)
    escala = max(0.70, min(1.30, float(forca)))
    raiz = NodePath("estalo_fone_anime")
    kira = _manpu(raiz, "an_estalo", 14)

    def atualizar(fase: float) -> None:
        snap = 1.16 if fase < 0.25 else max(0.0, (1.0 - fase) / 0.75)
        tam = 1.05 * escala * snap
        (kira.hide if tam <= 0.03 else kira.show)()
        kira.setR(fase * 65.0)
        kira.setScale(tam, 1.0, tam * _N_COLS)
        kira.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.25))

    _registrar(mgr, raiz, orig, "estalo_fone", 0.28, atualizar)


def emitir_espirro(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Espirro Anime: jato puff + gotículas sakuga projetadas da frente."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("porta", anc.get("visor_lado", anc["tronco"])))
    escala = max(0.75, min(1.35, float(forca)))
    raiz = NodePath("espirro_anime")
    puff, gotas = _manpu(raiz, "an_esp_p", 0), _manpu(raiz, "an_esp_g", 1)

    def atualizar(fase: float) -> None:
        u = 1.0 - (1.0 - fase) ** 2
        fim = min(1.0, (1.0 - fase) / 0.24)
        tp = 1.12 * escala * min(1.0, fase / 0.14) * fim
        (puff.hide if tp <= 0.03 else puff.show)()
        puff.setPos(lado * (0.42 + u * 0.92) * escala, -0.12, 0.10 * escala)
        puff.setScale(tp * lado, 1.0, tp * _N_COLS)
        puff.setShaderInput("u_fade", fim)
        gotas.setPos(lado * (0.68 + u * 1.24) * escala, -0.10, (0.04 - u * 0.24) * escala)
        gotas.setScale(tp * 0.85, 1.0, tp * 0.85 * _N_COLS)
        gotas.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, "espirro", 0.42, atualizar)


EMISSORES_ANIME = {
    "impacto_chao": emitir_impacto_chao,
    "impacto_parede": emitir_impacto_parede,
    "rastro": emitir_rastro,
    "poeira_passo": emitir_poeira_passo,
    "tontura": emitir_tontura,
    "choque": emitir_choque,
    "musica": emitir_musica,
    "sinal_radio": emitir_sinal_radio,
    "carinho": emitir_carinho,
    "sono": emitir_sono,
    "sobressalto": emitir_sobressalto,
    "irritado": emitir_irritado,
    "curiosidade": emitir_curiosidade,
    "brilho_estilo": emitir_brilho_estilo,
    "suor": emitir_suor,
    "suspiro": emitir_suspiro,
    "tristeza": emitir_tristeza,
    "estalo_fone": emitir_estalo_fone,
    "espirro": emitir_espirro,
    "acento_danca": emitir_musica,
    "calor": emitir_irritado,
}
