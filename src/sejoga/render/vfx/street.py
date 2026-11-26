"""VFX autorais do estilo ``street`` (Graffiti Punk / Persona 5 / BRC + Raio-X).

Todos os eventos canônicos + 5 micro-VFX narrativos usam molduras gigantes de
pôster que abraçam a silhueta por trás (sem cobrir o rosto), tipografia rasgada
(``SMASH!``, ``DROP!``, ``BANG!``, ``ZAP!``, ``FAST>>``, ``HOLD!?!``, ``VIBE!``),
carinhas pichadas, coroas, respingos de spray e assinatura Raio-X no impacto.
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
_N_MOLDURAS = 6
_N_EXTRAS = 8
_INK = (0.05, 0.05, 0.08, 1.0)
_BRANCO = (0.99, 0.99, 0.97, 1.0)
_AMARELO = (1.00, 0.88, 0.13, 1.0)
_CIANO = (0.07, 0.84, 1.00, 1.0)
_LIMA = (0.65, 0.96, 0.12, 1.0)


@cache
def _carregar_atlas(subpasta: str, arquivo: str, chave: str) -> Texture:
    caminho = assets_dir() / "textures" / subpasta / arquivo
    img = PNMImage()
    if not img.read(StringStream(caminho.read_bytes()), caminho.name):
        raise ValueError(f"Atlas inválido: {caminho}")
    tex = textura_pixel(chave, img)
    tex.setFormat(Texture.FSrgbAlpha)
    return tex


def _textura_street() -> Texture:
    return _carregar_atlas("vfx_street", "street_stickers.png", "street_stickers_v2")


def _textura_molduras_street() -> Texture:
    return _carregar_atlas("vfx_street", "street_molduras.png", "street_molduras_v2")


def _textura_extras_street() -> Texture:
    return _carregar_atlas("vfx_street", "street_extras.png", "street_extras_v1")


def _carta_atlas(raiz: NodePath, nome: str, tex: Texture, n_cols: int, celula: int) -> NodePath:
    stage = TextureStage.getDefault()
    c = cartao_pixel(raiz, nome, tex)
    c.setTexScale(stage, 1.0 / n_cols, 1.0)
    c.setTexOffset(stage, celula / n_cols, 0.0)
    return c


def _sticker(raiz: NodePath, nome: str, celula: int) -> NodePath:
    return _carta_atlas(raiz, nome, _textura_street(), _N_COLS, celula)


def _extra(raiz: NodePath, nome: str, celula: int) -> NodePath:
    return _carta_atlas(raiz, nome, _textura_extras_street(), _N_EXTRAS, celula)


def _moldura_poster(raiz: NodePath, nome: str, celula: int) -> NodePath:
    """Moldura gigante de pôster atrás da silhueta do Mário (nunca cobre o rosto)."""
    c = _carta_atlas(raiz, nome, _textura_molduras_street(), _N_MOLDURAS, celula)
    c.setDepthTest(True)
    c.setDepthWrite(False)
    c.setBin("background", 12)
    return c


def _atualizar_moldura_poster(
    moldura: NodePath, offset_tronco: Vec3, fase: float, escala: float, rot: float = 0.0
) -> None:
    snap = 1.16 if fase < 0.16 else (1.0 if fase < 0.68 else max(0.0, (1.0 - fase) / 0.32))
    tam = 6.55 * escala * snap
    if tam <= 0.08:
        moldura.hide()
        return
    step10 = int(fase * 10.0)
    wobble = (step10 % 2 * 2 - 1) * 0.06 * escala
    rot_jitter = (step10 % 3 - 1) * 2.2
    moldura.show()
    moldura.setPos(offset_tronco + Vec3(wobble, 1.45, 0.92 * escala + wobble * 0.6))
    moldura.setR(rot + rot_jitter + (4.0 if fase < 0.16 else 0.0))
    moldura.setScale(tam, 1.0, tam * _N_MOLDURAS)
    moldura.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.20))


def _solicitar_xray(mgr: GerenciadorEfeitosStreet, duracao: float = 0.11) -> None:
    fn = getattr(mgr, "solicitar_flash_xray", None)
    if callable(fn):
        fn(duracao)


def _registrar(mgr: GerenciadorEfeitosStreet, raiz: NodePath, pos: Vec3, nome: str, ttl: float, fn) -> None:
    mgr.emitir_3d(
        raiz,
        pos,
        tipo_mesh=f"{nome}_street",
        ttl=ttl,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=fn,
    )
    fn(0.0)


def _atualizar_estilhacos(
    itens: list[tuple[NodePath, Vec3, float]], fase: float, escala: float, grav: float = 1.4
) -> None:
    u = min(1.0, fase / 0.92)
    for card, direcao, tam_b in itens:
        dist = (1.0 - exp(-4.5 * u)) * 1.55 * escala
        tam = tam_b * escala * min(1.0, (1.0 - u) / 0.28)
        if tam <= 0.03:
            card.hide()
            continue
        card.show()
        card.setPos(direcao * dist + Vec3(0.0, -0.10, -grav * u * u * escala))
        card.setR(u * 155.0 * (1.0 if direcao.x >= 0 else -1.0))
        card.setScale(tam, 1.0, tam * _N_COLS)
        card.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))


def _desenhar_anel_street(vdata, tris, fase: float, escala: float) -> None:
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    ab = 1.0 - (1.0 - min(1.0, fase / 0.52)) ** 3
    rx, esp = (0.85 + 2.15 * ab) * escala, max(0.035, 0.19 * escala * (1.0 - fase * 0.70))
    idx = 0
    for k in range(8):
        a0, a1 = (k / 8.0) * 2.0 * pi, ((k + 1) / 8.0) * 2.0 * pi
        p0 = Vec3(cos(a0) * rx, -0.06, 0.08 + sin(a0) * 0.28 * escala)
        p1 = Vec3(cos(a1) * rx, -0.06, 0.08 + sin(a1) * 0.28 * escala)
        idx = _emitir_segmento_dungeons(vw, cw, tris, idx, p0, p1, esp, esp, _INK, _AMARELO, _BRANCO)
    tris.closePrimitive()


def _atualizar_puffs_e_drop_street(
    puffs, drop: NodePath, tag_face: NodePath, stage: TextureStage, fase: float, escala: float, forca: float
) -> None:
    u = min(1.0, fase / 0.92)
    for pf, lado in puffs:
        tam = (1.00 + 0.80 * min(1.0, u * 4.5)) * escala * min(1.0, (1.0 - u) / 0.26)
        pf.setTexOffset(stage, (13 if u > 0.64 else 12) / _N_COLS, 0.0)
        pf.setPos(lado * (0.76 + (1.0 - exp(-4.5 * u)) * 1.85) * escala, -0.08, 0.44 * escala)
        pf.setScale(tam * lado, 1.0, tam * _N_COLS)
        pf.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))
    snap = 1.20 if fase < 0.18 else (1.0 if fase < 0.70 else max(0.0, (1.0 - fase) / 0.30))
    td = 1.62 * escala * snap
    (drop.hide if td <= 0.03 or forca < 0.92 else drop.show)()
    drop.setPos(1.75 * escala, -0.14, (0.92 + fase * 0.36) * escala)
    drop.setR(-8.0)
    drop.setScale(td, 1.0, td * _N_COLS)
    drop.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.20))
    tf = 1.05 * escala * snap
    (tag_face.hide if tf <= 0.03 else tag_face.show)()
    tag_face.setPos(-1.68 * escala, -0.12, (1.12 + sin(fase * pi) * 0.42) * escala)
    tag_face.setR(12.0 - fase * 18.0)
    tag_face.setScale(tf, 1.0, tf * _N_COLS)
    tag_face.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.20))


def emitir_impacto_chao(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Pouso Street punk: anel amarelo, puffs pichados, carinha ``x_x``, ``DROP!`` e moldura gigante."""
    del pos, vel, dir_x
    esq = anc.get("sola_esq", anc["pes"] + Vec3(-0.7, 0, 0))
    dir_ = anc.get("sola_dir", anc["pes"] + Vec3(0.7, 0, 0))
    centro = Vec3((esq.x + dir_.x) * 0.5, (esq.y + dir_.y) * 0.5, min(esq.z, dir_.z))
    escala = max(0.72, min(1.50, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("impacto_chao_street")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    puffs = [(_sticker(raiz, f"st_puff_{i}", 12), s) for i, s in enumerate((-1.0, 1.0))]
    drop = _sticker(raiz, "st_drop", 0)
    tag_face = _sticker(raiz, "st_face_chao", 13)
    moldura = _moldura_poster(raiz, "st_mold_chao", 5 if forca >= 1.25 else 0)
    off_tronco = Vec3(anc["tronco"]) - centro
    if forca >= 1.15:
        _solicitar_xray(mgr, 0.11)

    def atualizar(fase: float) -> None:
        if fase < 0.88:
            _desenhar_anel_street(vdata, tris, fase, escala)
            arco_np.node().markInternalBoundsStale()
            arco_np.show()
        else:
            arco_np.hide()
        _atualizar_puffs_e_drop_street(puffs, drop, tag_face, stage, fase, escala, forca)
        _atualizar_moldura_poster(moldura, off_tronco, fase, escala, rot=-4.0)

    _registrar(mgr, raiz, centro, "impacto_chao", 0.50, atualizar)


def emitir_impacto_parede(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Colisão na parede Street: sticker ``BANG!`` + cacos graffiti + moldura + flash Raio-X."""
    origem = Vec3(pos) if pos is not None else Vec3(anc.get("lado_dir", anc["tronco"]))
    normal = Vec3(vel.x, 0.0, vel.z) if vel is not None else Vec3(-dir_x, 0.0, 0.0)
    normal = normal.normalized() if normal.lengthSquared() > 1e-4 else Vec3(-dir_x, 0.0, 0.0)
    tang = Vec3(-normal.z, 0.0, normal.x)
    escala = max(0.72, min(1.45, float(forca)))
    raiz = NodePath("impacto_parede_street")
    bang = _sticker(raiz, "st_bang", 1)
    moldura = _moldura_poster(raiz, "st_mold_parede", 5 if forca >= 1.12 else 0)
    off_tronco = Vec3(anc["tronco"]) - origem
    if forca >= 1.12:
        _solicitar_xray(mgr, 0.10)
    cacos = [
        (_sticker(raiz, f"st_caco_{i}", 14 if i % 2 == 0 else 15), (normal * 0.8 + tang * s).normalized(), 0.72)
        for i, s in enumerate((-0.90, 0.15, 0.90))
    ]

    def atualizar(fase: float) -> None:
        snap = 1.20 if fase < 0.18 else (1.0 if fase < 0.68 else max(0.0, (1.0 - fase) / 0.32))
        tb = 1.98 * escala * snap
        (bang.hide if tb <= 0.03 else bang.show)()
        bang.setPos(normal * (0.42 * escala) + Vec3(0.0, -0.12, 0.0))
        bang.setR(-12.0 if normal.x < 0 else 12.0)
        bang.setScale(tb, 1.0, tb * _N_COLS)
        bang.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.22))
        _atualizar_estilhacos(cacos, fase, escala, grav=1.55)
        _atualizar_moldura_poster(moldura, off_tronco, fase, escala * 0.98, rot=6.0 if normal.x < 0 else -6.0)

    _registrar(mgr, raiz, origem, "impacto_parede", 0.42, atualizar)


def _desenhar_faixas_rastro(vdata, tris, d: Vec3, perp: Vec3, fase: float, escala: float) -> None:
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    comp = 3.85 * escala * (1.0 - min(0.84, fase * 1.05))
    esp = max(0.038, 0.23 * escala * (1.0 - fase * 0.65))
    idx = 0
    for off, cm in ((0.72, _LIMA), (-0.72, _AMARELO)):
        a = d * (0.72 * escala) + perp * (off * escala) + Vec3(0, -0.06, 0)
        idx = _emitir_segmento_dungeons(vw, cw, tris, idx, a, a + d * comp, esp, esp * 0.18, _INK, cm, _BRANCO)
    tris.closePrimitive()


def emitir_rastro(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Rastro Street: faixas wildstyle verde-lima + ``FAST>>`` + moldura diagonal."""
    origem = Vec3(pos) if pos is not None else Vec3(anc["tronco"])
    d = Vec3(vel.x, 0.0, vel.z) if vel is not None else Vec3(-dir_x, 0.0, 0.0)
    d = d.normalized() if d.lengthSquared() > 1e-4 else Vec3(-dir_x, 0.0, 0.0)
    perp = Vec3(-d.z, 0.0, d.x)
    escala = max(0.75, min(1.45, float(forca)))
    raiz = NodePath("rastro_street")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    fast = _sticker(raiz, "st_fast", 3)
    moldura = _moldura_poster(raiz, "st_mold_rastro", 2)

    def atualizar(fase: float) -> None:
        if fase < 0.90:
            _desenhar_faixas_rastro(vdata, tris, d, perp, fase, escala)
            arco_np.node().markInternalBoundsStale()
            arco_np.show()
        else:
            arco_np.hide()
        tf = 1.82 * escala * min(1.0, fase / 0.14) * min(1.0, (1.0 - fase) / 0.30)
        (fast.hide if tf <= 0.03 else fast.show)()
        fast.setPos(d * (1.85 * escala) + Vec3(0.0, -0.10, 0.24 * escala))
        fast.setScale(tf, 1.0, tf * _N_COLS)
        fast.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.25))
        _atualizar_moldura_poster(moldura, d * (0.45 * escala), fase, escala * 0.95, rot=-5.0)

    _registrar(mgr, raiz, origem, "rastro", 0.34, atualizar)


def _desenhar_corona_street(vdata, tris, p_d: Vec3, p_e: Vec3, step: int, dist: float, escala: float) -> None:
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    r_b = dist * (0.046 if step < 2 else 0.030) * escala
    idx = 0
    for orig, sx, perfis in ((p_d, -1.0, _CORONA_DIR[step]), (p_e, 1.0, _CORONA_ESQ[step])):
        for pf in perfis:
            pts = [orig + Vec3(dx * sx * dist * 1.25, dy * dist, dz * dist * 1.25) for dx, dy, dz in pf]
            for k in range(len(pts) - 1):
                idx = _emitir_segmento_dungeons(vw, cw, tris, idx, pts[k], pts[k + 1], r_b, r_b * 0.45, _INK, _AMARELO, _BRANCO)
    tris.closePrimitive()


def _atualizar_choque_street(
    mgr: GerenciadorEfeitosStreet,
    raiz: NodePath,
    fallback: tuple[Vec3, Vec3],
    arco_np: NodePath,
    vdata,
    tris,
    zap: NodePath,
    moldura: NodePath,
    off_tronco: Vec3,
    fase: float,
    escala: float,
) -> None:
    p_d, p_e = _pontos_antenas_vivos(mgr, raiz, fallback)
    dist = max(0.45, (p_e - p_d).length())
    step = 0 if fase < 0.28 else (1 if fase < 0.58 else (2 if fase < 0.82 else 3))
    if step < 3:
        _desenhar_corona_street(vdata, tris, p_d, p_e, step, dist, escala)
        arco_np.node().markInternalBoundsStale()
        arco_np.show()
    else:
        arco_np.hide()
    tz = 1.68 * escala * (1.16 if step == 0 else (1.0 if step < 3 else 0.0))
    (zap.hide if tz <= 0.03 else zap.show)()
    zap.setPos(p_e + Vec3(0.66 * escala, -0.14, 0.78 * escala))
    zap.setR(-10.0)
    zap.setScale(tz, 1.0, tz * _N_COLS)
    zap.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))
    _atualizar_moldura_poster(moldura, off_tronco, fase, escala, rot=step * 5.0 - 4.0)


def emitir_choque(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Choque Street: raios com borda preta nas antenas + ``ZAP!`` + moldura ``BZZT``."""
    del pos, vel, dir_x
    ad, ae = anc.get("antena_d"), anc.get("antena_e")
    if ad is None or ae is None:
        return
    centro = (ad + ae) * 0.5
    fallback = (ad - centro, ae - centro)
    escala = max(0.72, min(1.40, float(forca)))
    raiz = NodePath("choque_street")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    zap = _sticker(raiz, "st_zap", 2)
    moldura = _moldura_poster(raiz, "st_mold_choque", 1)
    off_tronco = Vec3(anc["tronco"]) - centro
    _solicitar_xray(mgr, 0.09)

    def atualizar(fase: float) -> None:
        _atualizar_choque_street(mgr, raiz, fallback, arco_np, vdata, tris, zap, moldura, off_tronco, fase, escala)

    _registrar(mgr, raiz, centro, "choque", 0.38, atualizar)


def _emitir_placa_calma(
    mgr: GerenciadorEfeitosStreet,
    origem: Vec3,
    nome: str,
    celula: int,
    ttl: float,
    escala: float,
    *,
    dx_fim: float = 0.0,
    dz_fim: float = 1.15,
    amp_x: float = 0.18,
    rot_amp: float = 9.0,
    tam_base: float = 1.82,
    usar_extras: bool = False,
) -> None:
    raiz = NodePath(f"{nome}_street")
    n_cols = _N_EXTRAS if usar_extras else _N_COLS
    card = _extra(raiz, f"st_{nome}", celula) if usar_extras else _sticker(raiz, f"st_{nome}", celula)

    def atualizar(fase: float) -> None:
        pop = min(1.16, fase / 0.14) if fase < 0.14 else (1.16 - 0.16 * min(1.0, (fase - 0.14) / 0.12))
        fim = min(1.0, (1.0 - fase) / 0.22)
        tam = tam_base * escala * pop * fim
        (card.hide if tam <= 0.03 else card.show)()
        card.setPos((dx_fim * fase + sin(fase * 2.0 * pi) * amp_x) * escala, -0.10, (0.24 + dz_fim * fase) * escala)
        card.setR(sin(fase * 2.0 * pi) * rot_amp)
        card.setScale(tam, 1.0, tam * n_cols)
        card.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, origem, nome, ttl, atualizar)


def emitir_carinho(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Coração graffiti com coroa acima da cabeça + tag punk feliz."""
    del vel, dir_x
    escala = max(0.75, min(1.35, float(forca)))
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.06, 0.36)
    _emitir_placa_calma(mgr, orig, "carinho", 5, 0.88, escala, dz_fim=1.20)


def emitir_sono(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Tag azul pichada ``ZZZ`` flutuando devagar ao lado do visor."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["visor_lado"])) + Vec3(0.60, -0.06, 0.28)
    _emitir_placa_calma(mgr, orig, "sono", 6, 1.12, max(0.75, min(1.30, float(forca))), dx_fim=0.55, dz_fim=1.35)


def emitir_curiosidade(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Placa pichada amarela ``?`` ao lado do visor."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["visor_lado"])) + Vec3(0.62, -0.06, 0.42)
    _emitir_placa_calma(mgr, orig, "curiosidade", 8, 0.70, max(0.75, min(1.30, float(forca))), dz_fim=0.58, tam_base=1.22)


def _atualizar_puffs_raiva_street(puffs, stage: TextureStage, fase: float, escala: float) -> None:
    for pf, lado, at in puffs:
        if fase < at:
            pf.hide()
            continue
        u = min(1.0, (fase - at) / (1.0 - at))
        tp = (0.92 + 0.65 * min(1.0, u * 4.0)) * escala * min(1.0, (1.0 - u) / 0.25)
        pf.show()
        pf.setTexOffset(stage, (13 if u > 0.64 else 12) / _N_COLS, 0.0)
        pf.setPos(lado * (0.72 + u * 1.14) * escala, -0.06, (0.36 + u * 1.50) * escala)
        pf.setR(-lado * (16.0 + u * 18.0))
        pf.setScale(tp * lado, 1.0, tp * _N_COLS)
        pf.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))


def emitir_irritado(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Irritado Street: rubor na testa + nuvens pichadas + placa ``#?!``."""
    del pos, vel, dir_x
    topo = Vec3(anc["cabeca_topo"])
    templo_rel = Vec3(anc.get("templo", topo + Vec3(0.95, 0.0, -0.45))) - topo
    escala = max(0.75, min(1.35, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("irritado_street")
    rubor = _criar_rubor_cabeca(raiz)
    placa = _sticker(raiz, "st_raiva", 7)
    puffs = [(_sticker(raiz, f"st_rpf_{i}", 12), s, 0.04 + i * 0.08) for i, s in enumerate((-1.0, 1.0))]

    def atualizar(fase: float) -> None:
        fr = min(1.0, fase / 0.16) * min(1.0, (1.0 - fase) / 0.26)
        rubor.setPos(0.0, -0.48, 0.0)
        rubor.setScale(escala, 1.0, escala)
        rubor.setShaderInput("u_forca", fr * 0.92)
        _atualizar_puffs_raiva_street(puffs, stage, fase, escala)
        tm = 1.68 * escala * (1.0 + 0.14 * abs(sin(fase * 3.0 * pi))) * min(1.0, (1.0 - fase) / 0.20)
        placa.setPos(templo_rel + Vec3(0.95 * escala, -0.14, 0.30 * escala))
        placa.setScale(tm, 1.0, tm * _N_COLS)
        placa.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))

    _registrar(mgr, raiz, topo, "irritado", 0.84, atualizar)


def emitir_sobressalto(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Susto Punk: ``!`` grande + estilhaços + coroa + moldura ``HOLD!?!``."""
    del pos, vel, dir_x
    topo = Vec3(anc["cabeca_topo"])
    escala = max(0.75, min(1.35, float(forca)))
    raiz = NodePath("sobressalto_street")
    excl = _sticker(raiz, "st_excl", 4)
    moldura = _moldura_poster(raiz, "st_mold_susto", 3)
    off_tronco = Vec3(anc["tronco"]) - topo
    cacos = [
        (_sticker(raiz, f"st_sc_{i}", 14 if i % 2 == 0 else 15), Vec3(dx, -0.06, dz).normalized(), 0.72)
        for i, (dx, dz) in enumerate(((-0.92, 0.45), (0.92, 0.45)))
    ]

    def atualizar(fase: float) -> None:
        snap = 1.20 if fase < 0.16 else (1.0 if fase < 0.72 else max(0.0, (1.0 - fase) / 0.28))
        tam = 1.82 * escala * snap
        (excl.hide if tam <= 0.03 else excl.show)()
        excl.setPos(0.0, -0.10, (1.02 + (0.18 if fase < 0.16 else 0.0)) * escala)
        excl.setScale(tam, 1.0, tam * _N_COLS)
        excl.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.16))
        _atualizar_estilhacos(cacos, fase, escala, grav=0.1)
        _atualizar_moldura_poster(moldura, off_tronco, fase, escala * 0.98, rot=4.0)

    _registrar(mgr, raiz, topo, "sobressalto", 0.34, atualizar)


def _desenhar_arco_musica_street(vdata, tris, lado: float, fase: float, escala: float) -> None:
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    raio, av = (0.50 + 1.56 * fase) * escala, (0.26 + 1.24 * fase) * escala * lado
    esp = max(0.034, 0.18 * escala * (1.0 - fase * 0.72))
    idx = 0
    for k in range(6):
        a0, a1 = (-0.42 + (k / 6.0) * 0.84) * pi, (-0.42 + ((k + 1) / 6.0) * 0.84) * pi
        p0 = Vec3(av + cos(a0) * raio * 0.42 * lado, -0.06, sin(a0) * raio)
        p1 = Vec3(av + cos(a1) * raio * 0.42 * lado, -0.06, sin(a1) * raio)
        idx = _emitir_segmento_dungeons(vw, cw, tris, idx, p0, p1, esp, esp, _INK, _CIANO, _LIMA)
    tris.closePrimitive()


def _atualizar_musica_street(
    nota: NodePath,
    tag_yeah: NodePath,
    moldura: NodePath | None,
    off_tronco: Vec3,
    lado: float,
    fase: float,
    escala: float,
) -> None:
    tn = 1.50 * escala * min(1.0, fase / 0.16) * min(1.0, (1.0 - fase) / 0.24)
    (nota.hide if tn <= 0.03 else nota.show)()
    nota.setPos(lado * (0.68 + 1.04 * fase) * escala, -0.10, (0.56 + 0.98 * fase) * escala)
    nota.setR(sin(fase * 2.0 * pi) * 14.0)
    nota.setScale(tn, 1.0, tn * _N_COLS)
    nota.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.22))
    ty = 0.95 * escala * min(1.0, fase / 0.16) * min(1.0, (1.0 - fase) / 0.24)
    (tag_yeah.hide if ty <= 0.03 else tag_yeah.show)()
    tag_yeah.setPos(-lado * (0.72 + 0.65 * fase) * escala, -0.08, (0.88 + 0.45 * sin(fase * pi)) * escala)
    tag_yeah.setR(-lado * 10.0)
    tag_yeah.setScale(ty, 1.0, ty * _N_EXTRAS)
    tag_yeah.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.22))
    if moldura is not None:
        _atualizar_moldura_poster(moldura, off_tronco, fase, escala * 0.85, rot=lado * 3.0)


def emitir_musica(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Música Street: arcos ciano/lima + nota graffiti + moldura ``VIBE!`` nos acentos."""
    del vel
    lado = -1.0 if dir_x < 0 else 1.0
    origem = Vec3(pos) if pos is not None else Vec3(anc.get("fone_esq" if lado > 0 else "fone_dir", anc["cabeca_topo"]))
    escala = max(0.70, min(1.40, float(forca)))
    raiz = NodePath("musica_street")
    nota = _sticker(raiz, "st_nota", 10)
    tag_yeah = _extra(raiz, "st_mus_yeah", 7 if lado > 0 else 5)
    arco_np, vdata, tris = _criar_no_arco(raiz)
    moldura = _moldura_poster(raiz, "st_mold_mus", 4) if forca >= 0.92 else None
    off_tronco = Vec3(anc["tronco"]) - origem

    def atualizar(fase: float) -> None:
        if fase < 0.90:
            _desenhar_arco_musica_street(vdata, tris, lado, fase, escala)
            arco_np.node().markInternalBoundsStale()
            arco_np.show()
        else:
            arco_np.hide()
        _atualizar_musica_street(nota, tag_yeah, moldura, off_tronco, lado, fase, escala)

    _registrar(mgr, raiz, origem, "musica", 0.44, atualizar)


def emitir_sinal_radio(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Sinal de rádio Street: ondas angulares preto/ciano/amarelo nas duas antenas."""
    del pos, vel, dir_x
    ad, ae = anc.get("antena_d"), anc.get("antena_e")
    if ad is None or ae is None:
        return
    centro = (ad + ae) * 0.5
    rel_d, rel_e = ad - centro, ae - centro
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("sinal_radio_street")
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
            raio, esp = (0.28 + 0.90 * fase) * escala, max(0.018, 0.09 * escala * (1.0 - fase * 0.7))
            for k in range(5):
                a0, a1 = (-0.36 + (k / 5.0) * 0.72) * pi, (-0.36 + ((k + 1) / 5.0) * 0.72) * pi
                p0 = orig + Vec3(s * (0.14 + cos(a0) * raio), -0.06, 0.14 + sin(a0) * raio)
                p1 = orig + Vec3(s * (0.14 + cos(a1) * raio), -0.06, 0.14 + sin(a1) * raio)
                idx = _emitir_segmento_dungeons(vw, cw, tris, idx, p0, p1, esp, esp, _INK, _CIANO, _AMARELO)
        tris.closePrimitive()
        arco_np.node().markInternalBoundsStale()
        arco_np.show()

    _registrar(mgr, raiz, centro, "sinal_radio", 0.56, atualizar)


def emitir_brilho_estilo(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Estrelas 4 pontas + coroa graffiti acima da cabeça (sem cobrir o rosto)."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.08, 0.44)
    escala = max(0.75, min(1.35, float(forca)))
    raiz = NodePath("brilho_estilo_street")
    stars = (
        (_sticker(raiz, "st_sp0", 9), Vec3(-0.88, -0.06, 0.22), 0.00, 1.02, _N_COLS),
        (_sticker(raiz, "st_sp1", 9), Vec3(0.92, -0.06, 0.48), 0.15, 1.15, _N_COLS),
        (_extra(raiz, "st_crown", 6), Vec3(0.02, -0.06, 0.76), 0.18, 0.96, _N_EXTRAS),
    )

    def atualizar(fase: float) -> None:
        for st, off, at, tb, ncols in stars:
            if fase < at:
                st.hide()
                continue
            u = min(1.0, (fase - at) / (1.0 - at))
            p = sin(u * pi) ** 0.70
            tam = tb * escala * p
            (st.hide if tam <= 0.03 else st.show)()
            st.setPos(off * escala + Vec3(0, 0, u * 0.26 * escala))
            st.setR(sin(u * pi) * 18.0)
            st.setScale(tam, 1.0, tam * ncols)
            st.setShaderInput("u_fade", p)

    _registrar(mgr, raiz, orig, "brilho_estilo", 0.74, atualizar)


def emitir_tontura(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Estrelas tontas + carinha ``x_x`` Street orbitando acima da cabeça."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, 0.0, 0.62)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("tontura_street")
    stars = tuple(_sticker(raiz, f"st_tont_{i}", 11 if i != 1 else 13) for i in range(3))

    def atualizar(fase: float) -> None:
        env = min(1.0, fase / 0.14) * min(1.0, (1.0 - fase) / 0.20)
        for i, st in enumerate(stars):
            ang = fase * 3.6 * pi + i * (2.0 * pi / 3.0)
            tam = 0.86 * escala * env * (0.88 + 0.18 * sin(ang))
            (st.hide if tam <= 0.03 else st.show)()
            st.setPos(cos(ang) * 1.38 * escala, sin(ang) * 0.35 - 0.06, sin(ang) * 0.30 * escala)
            st.setR(sin(ang) * 22.0)
            st.setScale(tam, 1.0, tam * _N_COLS)
            st.setShaderInput("u_fade", env)

    _registrar(mgr, raiz, orig, "tontura", 1.05, atualizar)


def emitir_poeira_passo(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Fumaça Street recortada atrás do tênis ao correr/derrapar."""
    del vel
    lado = -1.0 if dir_x >= 0 else 1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("pes", anc["tronco"]))
    escala = max(0.65, min(1.30, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("poeira_passo_street")
    puffs = [(_sticker(raiz, f"st_pp_{i}", 12), i * 0.10, 0.90 - i * 0.14) for i in range(2)]

    def atualizar(fase: float) -> None:
        for i, (pf, at, tb) in enumerate(puffs):
            if fase < at:
                pf.hide()
                continue
            u = min(1.0, (fase - at) / (1.0 - at))
            tam = tb * escala * (0.60 + 0.50 * min(1.0, u * 4.0)) * min(1.0, (1.0 - u) / 0.26)
            (pf.hide if tam <= 0.03 else pf.show)()
            pf.setTexOffset(stage, (13 if u > 0.64 else 12) / _N_COLS, 0.0)
            pf.setPos(lado * (0.98 + (1.0 - exp(-4.4 * u)) * (0.92 + i * 0.35)) * escala, -0.14, (0.28 + u * 0.68) * escala)
            pf.setR(-lado * (14.0 + u * 20.0))
            pf.setScale(tam * lado, 1.0, tam * _N_COLS)
            pf.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))

    _registrar(mgr, raiz, orig, "poeira_passo", 0.40, atualizar)


def emitir_suor(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Gota de suor ciano punk escorrendo na têmpora (esforço / susto / nervoso)."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("templo", anc["visor_lado"])) + Vec3(0.42 * lado, -0.08, 0.24)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("suor_street")
    gota = _extra(raiz, "st_suor", 0)

    def atualizar(fase: float) -> None:
        pop = min(1.18, fase / 0.14) if fase < 0.14 else 1.0
        fim = min(1.0, (1.0 - fase) / 0.22)
        tam = 1.10 * escala * pop * fim
        (gota.hide if tam <= 0.03 else gota.show)()
        gota.setPos(0.18 * lado * escala, -0.10, (0.20 - fase * 0.85) * escala)
        gota.setR(-8.0 * lado)
        gota.setScale(tam, 1.0, tam * _N_EXTRAS)
        gota.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, "suor", 0.62, atualizar)


def emitir_suspiro(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Puff de alívio pichado saindo ao lado do visor no suspiro pesado."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("visor_lado", anc["cabeca_topo"])) + Vec3(0.48 * lado, -0.08, 0.05)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("suspiro_street")
    puff = _extra(raiz, "st_suspiro", 1)

    def atualizar(fase: float) -> None:
        fim = min(1.0, (1.0 - fase) / 0.26)
        tam = 1.24 * escala * min(1.0, fase / 0.16) * fim
        (puff.hide if tam <= 0.03 else puff.show)()
        puff.setPos(lado * (0.28 + fase * 0.92) * escala, -0.10, -fase * 0.28 * escala)
        puff.setR(-lado * 12.0 * fase)
        puff.setScale(tam * lado, 1.0, tam * _N_EXTRAS)
        puff.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, "suspiro", 0.68, atualizar)


def emitir_tristeza(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Nuvem cinza-azulada graffiti com chuva rabiscada sobre a cabeça."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.08, 0.78)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("tristeza_street")
    nuvem = _extra(raiz, "st_tristeza", 2)

    def atualizar(fase: float) -> None:
        env = min(1.0, fase / 0.18) * min(1.0, (1.0 - fase) / 0.24)
        tam = 1.48 * escala * env
        (nuvem.hide if tam <= 0.03 else nuvem.show)()
        nuvem.setPos(sin(fase * 2.0 * pi) * 0.14 * escala, -0.10, 0.16 * escala)
        nuvem.setScale(tam, 1.0, tam * _N_EXTRAS)
        nuvem.setShaderInput("u_fade", env)

    _registrar(mgr, raiz, orig, "tristeza", 0.96, atualizar)


def emitir_estalo_fone(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Estalo sonoro ``POP!`` ao ajustar ou tocar a concha do fone."""
    del vel
    chave = "fone_dir" if dir_x >= 0 else "fone_esq"
    orig = (Vec3(pos) if pos is not None else Vec3(anc.get(chave, anc["cabeca_topo"]))) + Vec3(0.32 * (1.0 if dir_x >= 0 else -1.0), -0.10, 0.14)
    escala = max(0.70, min(1.30, float(forca)))
    raiz = NodePath("estalo_fone_street")
    pop_tag = _extra(raiz, "st_estalo", 3)

    def atualizar(fase: float) -> None:
        snap = 1.22 if fase < 0.25 else max(0.0, (1.0 - fase) / 0.75)
        tam = 1.25 * escala * snap
        (pop_tag.hide if tam <= 0.03 else pop_tag.show)()
        pop_tag.setR(12.0 if dir_x >= 0 else -12.0)
        pop_tag.setScale(tam, 1.0, tam * _N_EXTRAS)
        pop_tag.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.25))

    _registrar(mgr, raiz, orig, "estalo_fone", 0.28, atualizar)


def emitir_espirro(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Espirro graffiti ``ATCH!`` com gotículas ciano/lima à frente do gabinete."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("porta", anc.get("visor_lado", anc["tronco"])))
    escala = max(0.75, min(1.35, float(forca)))
    raiz = NodePath("espirro_street")
    jato = _extra(raiz, "st_espirro", 4)

    def atualizar(fase: float) -> None:
        u = 1.0 - (1.0 - fase) ** 2
        fim = min(1.0, (1.0 - fase) / 0.24)
        tam = 1.48 * escala * min(1.0, fase / 0.14) * fim
        (jato.hide if tam <= 0.03 else jato.show)()
        jato.setPos(lado * (0.58 + u * 1.18) * escala, -0.14, (0.52 - u * 0.18) * escala)
        jato.setR(-lado * 10.0)
        jato.setScale(tam * lado, 1.0, tam * _N_EXTRAS)
        jato.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, "espirro", 0.42, atualizar)


EMISSORES_STREET = {
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
