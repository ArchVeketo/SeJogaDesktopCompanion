"""VFX autorais do estilo ``spiderverse`` (12 FPS on twos, HQ rabiscada, halftone Ben-Day & misprint).

Fiel à prancha ``docs/referencias_vfx/ref_spiderverse.png``:
- Cadência stepped em 12 FPS (*on twos*) em todos os efeitos.
- Onomatopeias rabiscadas com aberração cromática ciano/vermelho e retícula Ben-Day
  (``BWOOM``, ``PONK!`` + 3 riscos secos na parede, ``KRACK`` nas antenas, ondas *spidey-sense*,
  laços rabiscados no rastro).
"""

from __future__ import annotations

from functools import cache
from math import cos, exp, floor, pi, sin
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
_INK = (0.05, 0.04, 0.07, 1.0)
_YELLOW = (1.00, 0.91, 0.10, 1.0)
_LIME = (0.40, 0.95, 0.16, 1.0)
_CYAN = (0.07, 0.85, 1.00, 1.0)
_RED = (1.00, 0.17, 0.24, 1.0)
_WHITE = (0.99, 0.98, 0.96, 1.0)


@cache
def _textura_sv() -> Texture:
    caminho = assets_dir() / "textures" / "vfx_spiderverse" / "spiderverse_hq.png"
    img = PNMImage()
    if not img.read(StringStream(caminho.read_bytes()), caminho.name):
        raise ValueError(f"Atlas inválido: {caminho}")
    tex = textura_pixel("spiderverse_hq_v1", img)
    tex.setFormat(Texture.FSrgbAlpha)
    return tex


@cache
def _textura_sv_letras() -> Texture:
    caminho = assets_dir() / "textures" / "vfx_spiderverse" / "spiderverse_letras.png"
    img = PNMImage()
    if not img.read(StringStream(caminho.read_bytes()), caminho.name):
        raise ValueError(f"Atlas inválido: {caminho}")
    tex = textura_pixel("spiderverse_letras_v1", img)
    tex.setFormat(Texture.FSrgbAlpha)
    return tex


def _hq(raiz: NodePath, nome: str, celula: int) -> NodePath:
    stage = TextureStage.getDefault()
    c = cartao_pixel(raiz, nome, _textura_sv())
    c.setTexScale(stage, 1.0 / _N_COLS, 1.0)
    c.setTexOffset(stage, celula / _N_COLS, 0.0)
    return c


def _letra_gigante(raiz: NodePath, nome: str, celula: int, *, atras: bool = False) -> NodePath:
    """Tipografia escultural 2:1 sem caixa (``BWOOM``, ``PONK!``, ``ZAPP!``, ``ZZT!``, ``ZIP!``)."""
    stage = TextureStage.getDefault()
    c = cartao_pixel(raiz, nome, _textura_sv_letras())
    c.setTexScale(stage, 0.20, 1.0)
    c.setTexOffset(stage, celula * 0.20, 0.0)
    if atras:
        c.setDepthTest(True)
        c.setDepthWrite(False)
        c.setBin("background", 14)
    return c


def _step_12fps(fase: float, ttl: float) -> float:
    """Quantiza a fase em 12 FPS (on twos) para estética autêntica Spider-Verse."""
    passos = max(3.0, round(ttl * 12.0))
    return min(0.999, floor(fase * passos) / passos)


def _registrar(mgr: GerenciadorEfeitosStreet, raiz: NodePath, pos: Vec3, nome: str, ttl: float, fn) -> None:
    def wrapped(fase: float) -> None:
        fn(_step_12fps(fase, ttl))

    mgr.emitir_3d(
        raiz,
        pos,
        tipo_mesh=f"{nome}_spiderverse",
        ttl=ttl,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=wrapped,
    )
    wrapped(0.0)


def _desenhar_anel_sv(vdata, tris, fase: float, escala: float) -> None:
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    ab = 1.0 - (1.0 - min(1.0, fase / 0.50)) ** 3
    rx, esp = (0.78 + 1.85 * ab) * escala, max(0.025, 0.14 * escala * (1.0 - fase * 0.7))
    idx = 0
    for k in range(8):
        a0, a1 = (k / 8.0) * 2.0 * pi, ((k + 1) / 8.0) * 2.0 * pi
        p0 = Vec3(cos(a0) * rx, -0.06, 0.08 + sin(a0) * 0.24 * escala)
        p1 = Vec3(cos(a1) * rx, -0.06, 0.08 + sin(a1) * 0.24 * escala)
        idx = _emitir_segmento_dungeons(vw, cw, tris, idx, p0, p1, esp, esp, _INK, _LIME, _YELLOW)
    tris.closePrimitive()


def _atualizar_puffs_bwoom_sv(
    puffs, bwoom: NodePath, off_tronco: Vec3, stage: TextureStage, fase: float, escala: float
) -> None:
    u = min(1.0, fase / 0.92)
    for pf, lado in puffs:
        tam = (0.88 + 0.65 * min(1.0, u * 4.0)) * escala * min(1.0, (1.0 - u) / 0.26)
        pf.setTexOffset(stage, (12 if u > 0.56 else 11) / _N_COLS, 0.0)
        pf.setPos(lado * (0.72 + (1.0 - exp(-4.5 * u)) * 1.65) * escala, -0.08, 0.38 * escala)
        pf.setScale(tam * lado, 1.0, tam * _N_COLS)
        pf.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))
    # BWOOM gigante SEM CAIXA arqueando por trás da silhueta do Mário (Painel 3 da ref!)
    snap = 1.14 if fase < 0.20 else (1.0 if fase < 0.72 else max(0.0, (1.0 - fase) / 0.28))
    wb = 6.20 * escala * snap
    (bwoom.hide if wb <= 0.08 else bwoom.show)()
    bwoom.setPos(off_tronco + Vec3(0.0, 1.35, (0.55 + fase * 0.22) * escala))
    bwoom.setR(-4.0)
    bwoom.setScale(wb, 1.0, wb * 5.0)
    bwoom.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.22))


def emitir_impacto_chao(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Pouso Spider-Verse: ``BWOOM`` gigante sem caixa atrás do Mário + puffs Ben-Day."""
    del pos, vel, dir_x
    esq = anc.get("sola_esq", anc["pes"] + Vec3(-0.7, 0, 0))
    dir_ = anc.get("sola_dir", anc["pes"] + Vec3(0.7, 0, 0))
    centro = Vec3((esq.x + dir_.x) * 0.5, (esq.y + dir_.y) * 0.5, min(esq.z, dir_.z))
    off_tronco = Vec3(anc["tronco"]) - centro
    escala = max(0.70, min(1.45, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("impacto_chao_spiderverse")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    puffs = [(_hq(raiz, f"sv_pf_{i}", 11), s) for i, s in enumerate((-1.0, 1.0))]
    bwoom = _letra_gigante(raiz, "sv_bwoom", 0, atras=True)

    def atualizar(fase: float) -> None:
        if fase < 0.86:
            _desenhar_anel_sv(vdata, tris, fase, escala)
            arco_np.node().markInternalBoundsStale()
            arco_np.show()
        else:
            arco_np.hide()
        _atualizar_puffs_bwoom_sv(puffs, bwoom, off_tronco, stage, fase, escala)

    _registrar(mgr, raiz, centro, "impacto_chao", 0.50, atualizar)


def _atualizar_parede_sv(ponk: NodePath, caco: NodePath, normal: Vec3, fase: float, escala: float) -> None:
    snap = 1.16 if fase < 0.18 else (1.0 if fase < 0.70 else max(0.0, (1.0 - fase) / 0.30))
    wp = 3.25 * escala * snap
    (ponk.hide if wp <= 0.05 else ponk.show)()
    s_flip = 1.0 if normal.x <= 0 else -1.0
    ponk.setPos(normal * (-0.32 * escala) + Vec3(0.0, -0.14, 0.25 * escala))
    ponk.setR(-12.0 * s_flip)
    ponk.setScale(wp, 1.0, wp * 5.0)
    ponk.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.22))
    tc = 0.62 * escala * max(0.0, 1.0 - fase * 1.15)
    (caco.hide if tc <= 0.03 else caco.show)()
    caco.setPos(normal * (0.35 + fase * 1.45) * escala + Vec3(0, -0.10, (0.35 - 1.45 * fase * fase) * escala))
    caco.setR(fase * 160.0)
    caco.setScale(tc, 1.0, tc * _N_COLS)
    caco.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.20))


def emitir_impacto_parede(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Parede Spider-Verse (Painel 4): ``PONK!`` gigante em perspectiva sem caixa + 3 riscos secos."""
    origem = Vec3(pos) if pos is not None else Vec3(anc.get("lado_dir", anc["tronco"]))
    normal = Vec3(vel.x, 0.0, vel.z) if vel is not None else Vec3(-dir_x, 0.0, 0.0)
    normal = normal.normalized() if normal.lengthSquared() > 1e-4 else Vec3(-dir_x, 0.0, 0.0)
    escala = max(0.70, min(1.40, float(forca)))
    raiz = NodePath("impacto_parede_spiderverse")
    ponk, caco = _letra_gigante(raiz, "sv_ponk", 1), _hq(raiz, "sv_caco", 15)

    def atualizar(fase: float) -> None:
        _atualizar_parede_sv(ponk, caco, normal, fase, escala)

    _registrar(mgr, raiz, origem, "impacto_parede", 0.42, atualizar)


def emitir_rastro(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Rastro Spider-Verse: ``ZIP!`` esticado sem caixa virando laços rabiscados de tinta."""
    origem = Vec3(pos) if pos is not None else Vec3(anc["tronco"])
    d = Vec3(vel.x, 0.0, vel.z) if vel is not None else Vec3(-dir_x, 0.0, 0.0)
    d = d.normalized() if d.lengthSquared() > 1e-4 else Vec3(-dir_x, 0.0, 0.0)
    escala = max(0.75, min(1.40, float(forca)))
    raiz = NodePath("rastro_spiderverse")
    zip_card = _letra_gigante(raiz, "sv_zip", 4)

    def atualizar(fase: float) -> None:
        w = 3.85 * escala * min(1.0, fase / 0.14) * min(1.0, (1.0 - fase) / 0.28)
        (zip_card.hide if w <= 0.06 else zip_card.show)()
        zip_card.setPos(d * (1.85 + fase * 0.45) * escala + Vec3(0.0, -0.08, 0.12 * escala))
        zip_card.setR(-10.0 if d.x < 0 else 10.0)
        zip_card.setScale(w * (1.0 if d.x < 0 else -1.0), 1.0, w * 5.0)
        zip_card.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.24))

    _registrar(mgr, raiz, origem, "rastro", 0.36, atualizar)


def _desenhar_choque_sv(vdata, tris, p_d: Vec3, p_e: Vec3, step: int, dist: float, escala: float) -> None:
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    r_b = dist * (0.036 if step < 2 else 0.024) * escala
    idx = 0
    for orig, sx, perfis in ((p_d, -1.0, _CORONA_DIR[step]), (p_e, 1.0, _CORONA_ESQ[step])):
        for pf in perfis:
            pts = [orig + Vec3(dx * sx * dist * 1.2, dy * dist, dz * dist * 1.2) for dx, dy, dz in pf]
            for k in range(len(pts) - 1):
                idx = _emitir_segmento_dungeons(vw, cw, tris, idx, pts[k], pts[k + 1], r_b, r_b * 0.4, _INK, _CYAN, _YELLOW)
    tris.closePrimitive()


def _atualizar_palavras_choque_sv(
    zapp: NodePath, zzt: NodePath, p_d: Vec3, p_e: Vec3, step: int, fase: float, escala: float
) -> None:
    w_e = 2.65 * escala * (1.16 if step == 0 else (1.0 if step < 3 else 0.0))
    w_d = 2.35 * escala * (1.14 if step == 1 else (0.96 if step < 3 else 0.0))
    (zapp.hide if w_e <= 0.05 else zapp.show)()
    zapp.setPos(p_e + Vec3(0.85 * escala, -0.14, 0.72 * escala))
    zapp.setR(-11.0 + step * 3.0)
    zapp.setScale(w_e, 1.0, w_e * 5.0)
    zapp.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))
    (zzt.hide if w_d <= 0.05 else zzt.show)()
    zzt.setPos(p_d + Vec3(-0.82 * escala, -0.14, 0.66 * escala))
    zzt.setR(12.0 - step * 3.0)
    zzt.setScale(w_d, 1.0, w_d * 5.0)
    zzt.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))


def emitir_choque(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Choque Spider-Verse: letras-raio ``ZAPP!`` e ``ZZT!`` nos DOIS lados + corona nas antenas."""
    del pos, vel, dir_x
    ad, ae = anc.get("antena_d"), anc.get("antena_e")
    if ad is None or ae is None:
        return
    centro = (ad + ae) * 0.5
    fallback = (ad - centro, ae - centro)
    escala = max(0.75, min(1.35, float(forca)))
    raiz = NodePath("choque_spiderverse")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    zapp, zzt = _letra_gigante(raiz, "sv_zapp", 2), _letra_gigante(raiz, "sv_zzt", 3)

    def atualizar(fase: float) -> None:
        p_d, p_e = _pontos_antenas_vivos(mgr, raiz, fallback)
        dist = max(0.45, (p_e - p_d).length())
        step = 0 if fase < 0.28 else (1 if fase < 0.58 else (2 if fase < 0.82 else 3))
        if step < 3:
            _desenhar_choque_sv(vdata, tris, p_d, p_e, step, dist, escala)
            arco_np.node().markInternalBoundsStale()
            arco_np.show()
        else:
            arco_np.hide()
        _atualizar_palavras_choque_sv(zapp, zzt, p_d, p_e, step, fase, escala)

    _registrar(mgr, raiz, centro, "choque", 0.36, atualizar)


def emitir_sobressalto(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Susto Spider-Verse: ondas icônicas de *spidey-sense* rabiscadas ao redor da cabeça."""
    del pos, vel, dir_x
    topo = Vec3(anc["cabeca_topo"])
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("sobressalto_spiderverse")
    ondas = [
        (_hq(raiz, f"sv_spidey_{i}", 3), ang, s)
        for i, (ang, s) in enumerate(((-52.0, -1.0), (-20.0, -1.0), (20.0, 1.0), (52.0, 1.0)))
    ]

    def atualizar(fase: float) -> None:
        snap = 1.18 if fase < 0.18 else (1.0 if fase < 0.72 else max(0.0, (1.0 - fase) / 0.28))
        for ond, ang, s in ondas:
            rad = ang * pi / 180.0
            to = 1.12 * escala * snap
            (ond.hide if to <= 0.03 else ond.show)()
            ond.setPos(sin(rad) * 1.68 * escala * snap, -0.08, (0.36 + cos(rad) * 1.02 * snap) * escala)
            ond.setR(ang + (6.0 if int(fase * 12) % 2 == 0 else -6.0))
            ond.setScale(to * s, 1.0, to * _N_COLS)
            ond.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))

    _registrar(mgr, raiz, topo, "sobressalto", 0.36, atualizar)


def _atualizar_puffs_raiva_sv(puffs, stage: TextureStage, fase: float, escala: float) -> None:
    for pf, lado, at in puffs:
        u = max(0.0, (fase - at) / (1.0 - at))
        tp = (0.78 + 0.56 * min(1.0, u * 4.0)) * escala * min(1.0, (1.0 - u) / 0.25)
        (pf.hide if fase < at or tp <= 0.03 else pf.show)()
        pf.setTexOffset(stage, (12 if u > 0.60 else 11) / _N_COLS, 0.0)
        pf.setPos(lado * (0.62 + u * 1.02) * escala, -0.06, (0.32 + u * 1.38) * escala)
        pf.setR(-lado * (18.0 + u * 18.0))
        pf.setScale(tp * lado, 1.0, tp * _N_COLS)
        pf.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))


def emitir_irritado(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Irritado Spider-Verse: hachura vermelha na testa + puffs Ben-Day + ``#@!`` rabiscado."""
    del pos, vel, dir_x
    topo = Vec3(anc["cabeca_topo"])
    templo_rel = Vec3(anc.get("templo", topo + Vec3(0.95, 0.0, -0.45))) - topo
    escala = max(0.75, min(1.30, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("irritado_spiderverse")
    rubor, placa = _criar_rubor_cabeca(raiz), _hq(raiz, "sv_raiva", 6)
    puffs = [(_hq(raiz, f"sv_rpf_{i}", 11), s, 0.04 + i * 0.08) for i, s in enumerate((-1.0, 1.0))]

    def atualizar(fase: float) -> None:
        fr = min(1.0, fase / 0.16) * min(1.0, (1.0 - fase) / 0.26)
        rubor.setPos(0.0, -0.48, 0.0)
        rubor.setScale(escala, 1.0, escala)
        rubor.setShaderInput("u_forca", fr * 0.92)
        _atualizar_puffs_raiva_sv(puffs, stage, fase, escala)
        tm = 1.32 * escala * (1.0 + 0.16 * abs(sin(fase * 3.0 * pi))) * min(1.0, (1.0 - fase) / 0.20)
        placa.setPos(templo_rel + Vec3(0.84 * escala, -0.14, 0.26 * escala))
        placa.setScale(tm, 1.0, tm * _N_COLS)
        placa.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))

    _registrar(mgr, raiz, topo, "irritado", 0.84, atualizar)


def _emitir_flutuante_sv(mgr, orig: Vec3, nome: str, celula: int, ttl: float, escala: float, dx: float = 0.0, dz: float = 1.15, tb: float = 1.32) -> None:
    raiz = NodePath(f"{nome}_spiderverse")
    c = _hq(raiz, f"sv_{nome}", celula)

    def atualizar(fase: float) -> None:
        fim = min(1.0, (1.0 - fase) / 0.22)
        tam = tb * escala * min(1.14, fase / 0.14) * fim
        (c.hide if tam <= 0.03 else c.show)()
        c.setPos((dx * fase + sin(fase * 2.0 * pi) * 0.20) * escala, -0.08, (0.24 + dz * fase) * escala)
        c.setR(sin(fase * 2.0 * pi) * 10.0)
        c.setScale(tam, 1.0, tam * _N_COLS)
        c.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, nome, ttl, atualizar)


def emitir_carinho(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Coração rabiscado com halftone Ben-Day e misprint ciano."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.06, 0.36)
    _emitir_flutuante_sv(mgr, orig, "carinho", 4, 0.86, max(0.75, min(1.30, float(forca))))


def emitir_sono(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """``ZzZ`` rabiscado em misprint flutuando em 12 FPS ao lado do visor."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["visor_lado"])) + Vec3(0.55, -0.06, 0.24)
    _emitir_flutuante_sv(mgr, orig, "sono", 5, 1.12, max(0.75, min(1.30, float(forca))), dx=0.55, dz=1.35)


def emitir_curiosidade(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """``?`` rabiscado com aberração cromática ao lado do visor."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["visor_lado"])) + Vec3(0.58, -0.06, 0.42)
    _emitir_flutuante_sv(mgr, orig, "curiosidade", 7, 0.68, max(0.75, min(1.30, float(forca))), dz=0.52, tb=1.22)


def emitir_brilho_estilo(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """3 estrelas 4 pontas rabiscadas com misprint ciano/amarelo."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.08, 0.42)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("brilho_estilo_spiderverse")
    stars = (
        (_hq(raiz, "sv_st0", 8), Vec3(-0.92, -0.06, 0.18), 0.00, 1.05),
        (_hq(raiz, "sv_st1", 8), Vec3(0.96, -0.06, 0.46), 0.15, 1.22),
        (_hq(raiz, "sv_st2", 8), Vec3(0.04, -0.06, 0.86), 0.28, 0.92),
    )

    def atualizar(fase: float) -> None:
        for st, off, at, tb in stars:
            u = max(0.0, (fase - at) / (1.0 - at))
            p = sin(u * pi) ** 0.70 if fase >= at else 0.0
            tam = tb * escala * p
            (st.hide if tam <= 0.03 else st.show)()
            st.setPos(off * escala + Vec3(0, 0, u * 0.26 * escala))
            st.setR(u * 28.0)
            st.setScale(tam, 1.0, tam * _N_COLS)
            st.setShaderInput("u_fade", p)

    _registrar(mgr, raiz, orig, "brilho_estilo", 0.74, atualizar)


def emitir_musica(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Nota musical rabiscada misprint + arco verde-ácido em 12 FPS."""
    del vel
    lado = -1.0 if dir_x < 0 else 1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("fone_esq" if lado > 0 else "fone_dir", anc["cabeca_topo"]))
    _emitir_flutuante_sv(mgr, orig, "musica", 9, 0.46, max(0.70, min(1.35, float(forca))), dx=lado * 1.15, dz=0.88, tb=1.22)


def emitir_sinal_radio(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Ondas de sintonia rabiscadas ciano/amarelo saindo das duas antenas."""
    del pos, vel, dir_x
    ad, ae = anc.get("antena_d"), anc.get("antena_e")
    if ad is None or ae is None:
        return
    centro = (ad + ae) * 0.5
    rel_d, rel_e = ad - centro, ae - centro
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("sinal_radio_spiderverse")
    arco_np, vdata, tris = _criar_no_arco(raiz)

    def atualizar(fase: float) -> None:
        if fase >= 0.90:
            arco_np.hide()
            return
        vdata.uncleanSetNumRows(0)
        tris.clearVertices()
        vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
        idx = 0
        for orig, s in ((rel_d, -1.0), (rel_e, 1.0)):
            raio, esp = (0.26 + 0.88 * fase) * escala, max(0.02, 0.08 * escala * (1.0 - fase * 0.7))
            for k in range(5):
                a0, a1 = (-0.36 + (k / 5.0) * 0.72) * pi, (-0.36 + ((k + 1) / 5.0) * 0.72) * pi
                p0 = orig + Vec3(s * (0.14 + cos(a0) * raio), -0.06, 0.14 + sin(a0) * raio)
                p1 = orig + Vec3(s * (0.14 + cos(a1) * raio), -0.06, 0.14 + sin(a1) * raio)
                idx = _emitir_segmento_dungeons(vw, cw, tris, idx, p0, p1, esp, esp, _INK, _CYAN, _YELLOW)
        tris.closePrimitive()
        arco_np.node().markInternalBoundsStale()
        arco_np.show()

    _registrar(mgr, raiz, centro, "sinal_radio", 0.56, atualizar)


def emitir_tontura(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """3 estrelas rabiscadas misprint orbitando em 12 FPS acima da cabeça."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, 0.0, 0.62)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("tontura_spiderverse")
    stars = tuple(_hq(raiz, f"sv_tont_{i}", 10) for i in range(3))

    def atualizar(fase: float) -> None:
        env = min(1.0, fase / 0.14) * min(1.0, (1.0 - fase) / 0.20)
        for i, st in enumerate(stars):
            ang = fase * 3.6 * pi + i * (2.0 * pi / 3.0)
            tam = 0.86 * escala * env * (0.88 + 0.18 * sin(ang))
            (st.hide if tam <= 0.03 else st.show)()
            st.setPos(cos(ang) * 1.35 * escala, sin(ang) * 0.35 - 0.06, sin(ang) * 0.28 * escala)
            st.setR(sin(ang) * 24.0)
            st.setScale(tam, 1.0, tam * _N_COLS)
            st.setShaderInput("u_fade", env)

    _registrar(mgr, raiz, orig, "tontura", 1.05, atualizar)


def emitir_poeira_passo(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Puffs halftone Ben-Day saindo atrás do tênis em 12 FPS ao correr/derrapar."""
    del vel
    lado = -1.0 if dir_x >= 0 else 1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("pes", anc["tronco"]))
    escala = max(0.65, min(1.30, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("poeira_passo_spiderverse")
    puffs = [(_hq(raiz, f"sv_pp_{i}", 11), i * 0.10, 0.90 - i * 0.14) for i in range(2)]

    def atualizar(fase: float) -> None:
        for i, (pf, at, tb) in enumerate(puffs):
            u = max(0.0, (fase - at) / (1.0 - at))
            tam = tb * escala * (0.58 + 0.52 * min(1.0, u * 4.0)) * min(1.0, (1.0 - u) / 0.26)
            (pf.hide if fase < at or tam <= 0.03 else pf.show)()
            pf.setTexOffset(stage, (12 if u > 0.58 else 11) / _N_COLS, 0.0)
            pf.setPos(lado * (0.98 + (1.0 - exp(-4.4 * u)) * (0.92 + i * 0.35)) * escala, -0.14, (0.28 + u * 0.68) * escala)
            pf.setR(-lado * (16.0 + u * 20.0))
            pf.setScale(tam * lado, 1.0, tam * _N_COLS)
            pf.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))

    _registrar(mgr, raiz, orig, "poeira_passo", 0.42, atualizar)


def _fase_step12(fase: float, ttl: float) -> float:
    quadros = max(3.0, round(ttl * 12.0))
    return min(0.99, floor(fase * quadros) / quadros)


def emitir_suor(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Gota Ben-Day em 12 FPS escorrendo na têmpora com leve misprint."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("templo", anc["visor_lado"])) + Vec3(0.44 * lado, -0.08, 0.24)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("suor_spiderverse")
    gota = _hq(raiz, "sv_suor", 15)

    def atualizar(fase: float) -> None:
        f = _fase_step12(fase, 0.62)
        fim = min(1.0, (1.0 - f) / 0.24)
        tam = 0.72 * escala * min(1.0, f / 0.16 + 0.3) * fim
        (gota.hide if tam <= 0.03 else gota.show)()
        gota.setPos(0.16 * lado * escala, -0.10, (0.18 - f * 0.78) * escala)
        gota.setR(-12.0 * lado)
        gota.setScale(tam * 0.7, 1.0, tam * 1.25 * _N_COLS)
        gota.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, "suor", 0.62, atualizar)


def emitir_suspiro(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Nuvem Ben-Day + traços amarelos em 12 FPS saindo ao lado do visor."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("visor_lado", anc["cabeca_topo"])) + Vec3(0.48 * lado, -0.08, 0.04)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("suspiro_spiderverse")
    puff, riscos = _hq(raiz, "sv_susp_p", 11), _hq(raiz, "sv_susp_r", 14)

    def atualizar(fase: float) -> None:
        f = _fase_step12(fase, 0.68)
        fim = min(1.0, (1.0 - f) / 0.26)
        tam = 1.02 * escala * min(1.0, f / 0.16 + 0.25) * fim
        (puff.hide if tam <= 0.03 else puff.show)()
        puff.setPos(lado * (0.28 + f * 0.88) * escala, -0.10, -f * 0.22 * escala)
        puff.setScale(tam * lado, 1.0, tam * _N_COLS)
        puff.setShaderInput("u_fade", fim)
        riscos.setPos(lado * (0.15 + f * 0.65) * escala, -0.11, -f * 0.16 * escala)
        riscos.setScale(tam * 0.8 * lado, 1.0, tam * 0.8 * _N_COLS)
        riscos.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, "suspiro", 0.68, atualizar)


def emitir_tristeza(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Rabisco melancólico em 12 FPS pairando sobre a cabeça."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.08, 0.78)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("tristeza_spiderverse")
    rabisco = _hq(raiz, "sv_gloom", 13)

    def atualizar(fase: float) -> None:
        f = _fase_step12(fase, 0.96)
        env = min(1.0, (f + 0.08) / 0.20) * min(1.0, (1.0 - f) / 0.24)
        tam = 1.28 * escala * env
        (rabisco.hide if tam <= 0.03 else rabisco.show)()
        rabisco.setPos(sin(f * 2.0 * pi) * 0.14 * escala, -0.10, 0.12 * escala)
        rabisco.setR((floor(f * 12.0) % 2 * 2 - 1) * 7.0)
        rabisco.setScale(tam, 1.0, tam * _N_COLS)
        rabisco.setShaderInput("u_fade", env)

    _registrar(mgr, raiz, orig, "tristeza", 0.96, atualizar)


def emitir_estalo_fone(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Sparkle misprint na concha do fone em 12 FPS."""
    del vel
    chave = "fone_dir" if dir_x >= 0 else "fone_esq"
    orig = (Vec3(pos) if pos is not None else Vec3(anc.get(chave, anc["cabeca_topo"]))) + Vec3(0.30 * (1.0 if dir_x >= 0 else -1.0), -0.10, 0.12)
    escala = max(0.70, min(1.30, float(forca)))
    raiz = NodePath("estalo_fone_spiderverse")
    spark = _hq(raiz, "sv_estalo", 8)

    def atualizar(fase: float) -> None:
        snap = 1.22 if fase < 0.30 else max(0.0, (1.0 - fase) / 0.70)
        tam = 1.12 * escala * snap
        (spark.hide if tam <= 0.03 else spark.show)()
        spark.setR(18.0 if fase < 0.5 else -14.0)
        spark.setScale(tam, 1.0, tam * _N_COLS)
        spark.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.25))

    _registrar(mgr, raiz, orig, "estalo_fone", 0.28, atualizar)


def emitir_espirro(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Espirro HQ 12 FPS com rajada Ben-Day e estilhaços."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("porta", anc.get("visor_lado", anc["tronco"])))
    escala = max(0.75, min(1.35, float(forca)))
    raiz = NodePath("espirro_spiderverse")
    puff, debris = _hq(raiz, "sv_esp_p", 11), _hq(raiz, "sv_esp_d", 12)

    def atualizar(fase: float) -> None:
        f = _fase_step12(fase, 0.42)
        u = 1.0 - (1.0 - f) ** 2
        fim = min(1.0, (1.0 - f) / 0.24)
        tp = 1.18 * escala * min(1.0, (f + 0.1) / 0.20) * fim
        (puff.hide if tp <= 0.03 else puff.show)()
        puff.setPos(lado * (0.44 + u * 0.96) * escala, -0.12, 0.12 * escala)
        puff.setScale(tp * lado, 1.0, tp * _N_COLS)
        puff.setShaderInput("u_fade", fim)
        debris.setPos(lado * (0.72 + u * 1.28) * escala, -0.10, -u * 0.22 * escala)
        debris.setScale(tp * 0.85, 1.0, tp * 0.85 * _N_COLS)
        debris.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, "espirro", 0.42, atualizar)


EMISSORES_SPIDERVERSE = {
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
