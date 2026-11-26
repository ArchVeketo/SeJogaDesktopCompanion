"""VFX autorais do estilo ``holograma`` (Projeção de Dados Instável & CRT Analógico).

Fiel à prancha ``docs/referencias_vfx/ref_holograma.png``:
- Linhas de varredura CRT + fósforo RGB (ciano + verde + laranja/vermelho, 100% chroma-safe).
- Anéis sonar no piso, *horizontal sync tear* na parede, sobrecarga ``OVLD`` / ``VOLT`` nos dois
  lados das antenas, ecos de scanlines desfiadas no rastro, HUD técnico ``EXT3`` / ``STRESS`` / ``[!]``.
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
_BLUE = (0.10, 0.42, 1.00, 1.0)
_CYAN = (0.11, 0.91, 1.00, 1.0)
_GREEN = (0.22, 0.96, 0.55, 1.0)
_ORANGE = (1.00, 0.35, 0.14, 1.0)
_WHITE = (0.95, 1.00, 1.00, 1.0)


@cache
def _textura_crt() -> Texture:
    caminho = assets_dir() / "textures" / "vfx_holograma" / "holograma_crt.png"
    img = PNMImage()
    if not img.read(StringStream(caminho.read_bytes()), caminho.name):
        raise ValueError(f"Atlas inválido: {caminho}")
    tex = textura_pixel("holograma_crt_v1", img)
    tex.setFormat(Texture.FSrgbAlpha)
    return tex


def _crt(raiz: NodePath, nome: str, celula: int) -> NodePath:
    stage = TextureStage.getDefault()
    c = cartao_pixel(raiz, nome, _textura_crt())
    c.setTexScale(stage, 1.0 / _N_COLS, 1.0)
    c.setTexOffset(stage, celula / _N_COLS, 0.0)
    return c


def _jitter_crt(fase: float, amp: float = 0.08) -> float:
    return amp if int(fase * 24.0) % 2 == 0 else -amp


def _registrar(mgr: GerenciadorEfeitosStreet, raiz: NodePath, pos: Vec3, nome: str, ttl: float, fn) -> None:
    mgr.emitir_3d(
        raiz,
        pos,
        tipo_mesh=f"{nome}_holograma",
        ttl=ttl,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=fn,
    )
    fn(0.0)


def _desenhar_sonar_crt(vdata, tris, fase: float, escala: float) -> None:
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    idx = 0
    for atraso, cor_m in ((0.0, _CYAN), (0.18, _GREEN)):
        if fase < atraso:
            continue
        u = min(1.0, (fase - atraso) / (1.0 - atraso))
        rx = (0.72 + 1.88 * (1.0 - (1.0 - u) ** 3)) * escala
        esp = max(0.016, 0.082 * escala * (1.0 - u * 0.74))
        for k in range(10):
            if k % 3 == 2 and u > 0.55:
                continue
            a0, a1 = (k / 10.0) * 2.0 * pi, ((k + 1) / 10.0) * 2.0 * pi
            p0 = Vec3(cos(a0) * rx, -0.06, 0.08 + sin(a0) * 0.22 * escala)
            p1 = Vec3(cos(a1) * rx, -0.06, 0.08 + sin(a1) * 0.22 * escala)
            idx = _emitir_segmento_dungeons(vw, cw, tris, idx, p0, p1, esp, esp, _BLUE, cor_m, _WHITE)
    tris.closePrimitive()


def _atualizar_scan_piso(scans, sync_hud: NodePath, stage: TextureStage, fase: float, escala: float) -> None:
    u = min(1.0, fase / 0.92)
    for pf, lado in scans:
        tam = (0.82 + 0.62 * min(1.0, u * 4.0)) * escala * min(1.0, (1.0 - u) / 0.26)
        pf.setTexOffset(stage, (13 if u > 0.55 else 12) / _N_COLS, 0.0)
        pf.setPos(lado * (0.70 + (1.0 - exp(-4.5 * u)) * 1.58) * escala, -0.08, 0.36 * escala)
        pf.setScale(tam * lado, 1.0, tam * _N_COLS)
        pf.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))
    ts = 1.24 * escala * min(1.0, fase / 0.14) * min(1.0, (1.0 - fase) / 0.24)
    (sync_hud.hide if ts <= 0.03 else sync_hud.show)()
    sync_hud.setPos((1.42 + _jitter_crt(fase, 0.05)) * escala, -0.14, (0.72 + fase * 0.24) * escala)
    sync_hud.setScale(ts, 1.0, ts * _N_COLS)
    sync_hud.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.20))


def emitir_impacto_chao(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Pouso Holograma: duplo anel sonar CRT no piso + fragmentos de scanline + HUD ``SYNC``."""
    del pos, vel, dir_x
    esq = anc.get("sola_esq", anc["pes"] + Vec3(-0.7, 0, 0))
    dir_ = anc.get("sola_dir", anc["pes"] + Vec3(0.7, 0, 0))
    centro = Vec3((esq.x + dir_.x) * 0.5, (esq.y + dir_.y) * 0.5, min(esq.z, dir_.z))
    escala = max(0.70, min(1.45, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("impacto_chao_holograma")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    scans = [(_crt(raiz, f"hl_sc_{i}", 12), s) for i, s in enumerate((-1.0, 1.0))]
    sync_hud = _crt(raiz, "hl_sync", 0)

    def atualizar(fase: float) -> None:
        if fase < 0.88:
            _desenhar_sonar_crt(vdata, tris, fase, escala)
            arco_np.node().markInternalBoundsStale()
            arco_np.show()
        else:
            arco_np.hide()
        _atualizar_scan_piso(scans, sync_hud, stage, fase, escala)

    _registrar(mgr, raiz, centro, "impacto_chao", 0.48, atualizar)


def emitir_impacto_parede(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Parede Holograma (Painel 9): *horizontal sync tear* RGB + ``ERR!`` + blocos de dado."""
    origem = Vec3(pos) if pos is not None else Vec3(anc.get("lado_dir", anc["tronco"]))
    normal = Vec3(vel.x, 0.0, vel.z) if vel is not None else Vec3(-dir_x, 0.0, 0.0)
    normal = normal.normalized() if normal.lengthSquared() > 1e-4 else Vec3(-dir_x, 0.0, 0.0)
    escala = max(0.70, min(1.40, float(forca)))
    raiz = NodePath("impacto_parede_holograma")
    err, shard0, shard1 = _crt(raiz, "hl_err", 1), _crt(raiz, "hl_sh0", 15), _crt(raiz, "hl_sh1", 15)

    def atualizar(fase: float) -> None:
        snap = 1.16 if fase < 0.18 else (1.0 if fase < 0.72 else max(0.0, (1.0 - fase) / 0.28))
        te = 1.62 * escala * snap
        (err.hide if te <= 0.03 else err.show)()
        err.setPos(normal * (0.36 * escala) + Vec3(_jitter_crt(fase, 0.09) * escala, -0.14, 0.0))
        err.setScale(te, 1.0, te * _N_COLS)
        err.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.20))
        for i, sh in enumerate((shard0, shard1)):
            ts = 0.62 * escala * max(0.0, 1.0 - fase * 1.15)
            (sh.hide if ts <= 0.03 else sh.show)()
            s = -1.0 if i == 0 else 1.0
            sh.setPos(normal * (0.45 + fase * 1.55) * escala + Vec3(0, -0.10, (s * 0.55 - 1.2 * fase * fase) * escala))
            sh.setScale(ts, 1.0, ts * _N_COLS)
            sh.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.20))

    _registrar(mgr, raiz, origem, "impacto_parede", 0.40, atualizar)


def emitir_rastro(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Rastro Holograma (Painel 4): ecos de scanlines horizontais desfiadas em ``-velocidade``."""
    origem = Vec3(pos) if pos is not None else Vec3(anc["tronco"])
    d = Vec3(vel.x, 0.0, vel.z) if vel is not None else Vec3(-dir_x, 0.0, 0.0)
    d = d.normalized() if d.lengthSquared() > 1e-4 else Vec3(-dir_x, 0.0, 0.0)
    escala = max(0.75, min(1.40, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("rastro_holograma")
    ecos = [(_crt(raiz, f"hl_eco_{i}", 12), i * 0.14) for i in range(3)]

    def atualizar(fase: float) -> None:
        for i, (ec, at) in enumerate(ecos):
            u = max(0.0, (fase - at) / (1.0 - at))
            te = (1.68 - i * 0.22) * escala * min(1.0, u / 0.14) * min(1.0, (1.0 - u) / 0.26)
            (ec.hide if fase < at or te <= 0.03 else ec.show)()
            ec.setTexOffset(stage, (13 if u > 0.56 else 12) / _N_COLS, 0.0)
            ec.setPos(d * (1.15 + i * 0.85 + u * 0.45) * escala + Vec3(_jitter_crt(fase + i * 0.1, 0.08) * escala, -0.08, (0.16 - i * 0.22) * escala))
            ec.setScale(te * (1.0 if d.x < 0 else -1.0), 1.0, te * _N_COLS)
            ec.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))

    _registrar(mgr, raiz, origem, "rastro", 0.36, atualizar)


def _desenhar_choque_crt(vdata, tris, p_d: Vec3, p_e: Vec3, step: int, dist: float, escala: float) -> None:
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    r_b = dist * (0.030 if step < 2 else 0.020) * escala
    idx = 0
    for orig, sx, perfis in ((p_d, -1.0, _CORONA_DIR[step]), (p_e, 1.0, _CORONA_ESQ[step])):
        for pf in perfis:
            pts = [orig + Vec3(dx * sx * dist * 1.18, dy * dist, dz * dist * 1.18) for dx, dy, dz in pf]
            for k in range(len(pts) - 1):
                cor_m = _ORANGE if (k + step) % 2 == 1 else _CYAN
                idx = _emitir_segmento_dungeons(vw, cw, tris, idx, pts[k], pts[k + 1], r_b, r_b * 0.42, _BLUE, cor_m, _WHITE)
    tris.closePrimitive()


def _atualizar_hud_choque_crt(
    ovld: NodePath, volt: NodePath, p_d: Vec3, p_e: Vec3, step: int, fase: float, escala: float
) -> None:
    t_e = 1.48 * escala * (1.14 if step == 0 else (1.0 if step < 3 else 0.0))
    t_d = 1.42 * escala * (1.14 if step == 1 else (0.96 if step < 3 else 0.0))
    jit = _jitter_crt(fase, 0.08) * escala
    (ovld.hide if t_e <= 0.03 else ovld.show)()
    ovld.setPos(p_e + Vec3(0.75 * escala + jit, -0.14, 0.68 * escala))
    ovld.setScale(t_e, 1.0, t_e * _N_COLS)
    ovld.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))
    (volt.hide if t_d <= 0.03 else volt.show)()
    volt.setPos(p_d + Vec3(-0.75 * escala - jit, -0.14, 0.64 * escala))
    volt.setScale(t_d, 1.0, t_d * _N_COLS)
    volt.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))


def emitir_choque(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Choque Holograma: sobrecarga CRT ``OVLD`` e ``VOLT`` nos DOIS lados + arcos nas antenas."""
    del pos, vel, dir_x
    ad, ae = anc.get("antena_d"), anc.get("antena_e")
    if ad is None or ae is None:
        return
    centro = (ad + ae) * 0.5
    fallback = (ad - centro, ae - centro)
    escala = max(0.75, min(1.35, float(forca)))
    raiz = NodePath("choque_holograma")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    ovld, volt = _crt(raiz, "hl_ovld", 2), _crt(raiz, "hl_volt", 3)

    def atualizar(fase: float) -> None:
        p_d, p_e = _pontos_antenas_vivos(mgr, raiz, fallback)
        dist = max(0.45, (p_e - p_d).length())
        step = 0 if fase < 0.28 else (1 if fase < 0.58 else (2 if fase < 0.82 else 3))
        if step < 3:
            _desenhar_choque_crt(vdata, tris, p_d, p_e, step, dist, escala)
            arco_np.node().markInternalBoundsStale()
            arco_np.show()
        else:
            arco_np.hide()
        _atualizar_hud_choque_crt(ovld, volt, p_d, p_e, step, fase, escala)

    _registrar(mgr, raiz, centro, "choque", 0.36, atualizar)


def emitir_sobressalto(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Susto Holograma: alerta HUD ``[!]`` + faixas laterais de *sync tear* em 1 frame."""
    del pos, vel, dir_x
    topo = Vec3(anc["cabeca_topo"])
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("sobressalto_holograma")
    alerta = _crt(raiz, "hl_alerta", 4)
    tears = [(_crt(raiz, f"hl_tear_{i}", 15), s) for i, s in enumerate((-1.0, 1.0))]

    def atualizar(fase: float) -> None:
        snap = 1.18 if fase < 0.16 else (1.0 if fase < 0.72 else max(0.0, (1.0 - fase) / 0.28))
        ta = 1.48 * escala * snap
        (alerta.hide if ta <= 0.03 else alerta.show)()
        alerta.setPos(_jitter_crt(fase, 0.06) * escala, -0.10, (0.94 + (0.14 if fase < 0.16 else 0.0)) * escala)
        alerta.setScale(ta, 1.0, ta * _N_COLS)
        alerta.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.16))
        for tr, s in tears:
            tt = 0.88 * escala * snap
            (tr.hide if tt <= 0.03 else tr.show)()
            tr.setPos(s * (1.72 + _jitter_crt(fase, 0.14)) * escala, -0.08, 0.15 * escala)
            tr.setScale(tt * s, 1.0, tt * _N_COLS)
            tr.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.16))

    _registrar(mgr, raiz, topo, "sobressalto", 0.32, atualizar)


def emitir_irritado(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Irritado Holograma (Painel 5): ``STRESS`` RGB + hachura vermelha + barras estáticas."""
    del pos, vel, dir_x
    topo = Vec3(anc["cabeca_topo"])
    templo_rel = Vec3(anc.get("templo", topo + Vec3(0.95, 0.0, -0.45))) - topo
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("irritado_holograma")
    rubor, stress = _criar_rubor_cabeca(raiz), _crt(raiz, "hl_stress", 5)
    estaticas = [(_crt(raiz, f"hl_est_{i}", 14), s, 0.04 + i * 0.08) for i, s in enumerate((-1.0, 1.0))]

    def atualizar(fase: float) -> None:
        fr = min(1.0, fase / 0.16) * min(1.0, (1.0 - fase) / 0.26)
        rubor.setPos(0.0, -0.48, 0.0)
        rubor.setScale(escala, 1.0, escala)
        rubor.setShaderInput("u_forca", fr * 0.92)
        for es, lado, at in estaticas:
            u = max(0.0, (fase - at) / (1.0 - at))
            te = (0.82 + 0.46 * min(1.0, u * 4.0)) * escala * min(1.0, (1.0 - u) / 0.24)
            (es.hide if fase < at or te <= 0.03 else es.show)()
            es.setPos(lado * (0.64 + u * 0.96) * escala + _jitter_crt(fase, 0.08) * escala, -0.06, (0.34 + u * 1.25) * escala)
            es.setScale(te * lado, 1.0, te * _N_COLS)
            es.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))
        ts = 1.46 * escala * (1.0 + 0.14 * abs(sin(fase * 3.0 * pi))) * min(1.0, (1.0 - fase) / 0.20)
        stress.setPos(templo_rel + Vec3(0.92 * escala + _jitter_crt(fase, 0.06) * escala, -0.14, 0.26 * escala))
        stress.setScale(ts, 1.0, ts * _N_COLS)
        stress.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))

    _registrar(mgr, raiz, topo, "irritado", 0.84, atualizar)


def _emitir_hud_flutuante(mgr, orig: Vec3, nome: str, celula: int, ttl: float, escala: float, dx: float = 0.0, dz: float = 1.15, tb: float = 1.32) -> None:
    raiz = NodePath(f"{nome}_holograma")
    c = _crt(raiz, f"hl_{nome}", celula)

    def atualizar(fase: float) -> None:
        fim = min(1.0, (1.0 - fase) / 0.22)
        tam = tb * escala * min(1.12, fase / 0.14) * fim
        (c.hide if tam <= 0.03 else c.show)()
        c.setPos((dx * fase + sin(fase * 2.0 * pi) * 0.16 + _jitter_crt(fase, 0.03)) * escala, -0.08, (0.24 + dz * fase) * escala)
        c.setScale(tam, 1.0, tam * _N_COLS)
        c.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, nome, ttl, atualizar)


def emitir_carinho(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Coração holográfico CRT com borda RGB subindo acima da cabeça."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.06, 0.36)
    _emitir_hud_flutuante(mgr, orig, "carinho", 6, 0.86, max(0.75, min(1.30, float(forca))))


def emitir_sono(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """HUD monoespaçado ``ZZZ / IDLE`` flutuando devagar ao lado do visor."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["visor_lado"])) + Vec3(0.55, -0.06, 0.26)
    _emitir_hud_flutuante(mgr, orig, "sono", 7, 1.12, max(0.75, min(1.30, float(forca))), dx=0.52, dz=1.32)


def emitir_curiosidade(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """HUD monoespaçado ``[?]`` CRT ao lado do visor."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["visor_lado"])) + Vec3(0.58, -0.06, 0.42)
    _emitir_hud_flutuante(mgr, orig, "curiosidade", 8, 0.68, max(0.75, min(1.30, float(forca))), dz=0.52, tb=1.24)


def emitir_brilho_estilo(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """3 brilhos 4 pontas fósforo RGB cintilando acima da cabeça."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.08, 0.42)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("brilho_estilo_holograma")
    stars = (
        (_crt(raiz, "hl_st0", 9), Vec3(-0.92, -0.06, 0.18), 0.00, 1.04),
        (_crt(raiz, "hl_st1", 9), Vec3(0.96, -0.06, 0.46), 0.15, 1.20),
        (_crt(raiz, "hl_st2", 9), Vec3(0.04, -0.06, 0.86), 0.28, 0.92),
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


def emitir_musica(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Equalizador osciloscópio CRT + ondas de sinal verde/ciano fora do rosto."""
    del vel
    lado = -1.0 if dir_x < 0 else 1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("fone_esq" if lado > 0 else "fone_dir", anc["cabeca_topo"]))
    _emitir_hud_flutuante(mgr, orig, "musica", 10, 0.46, max(0.70, min(1.35, float(forca))), dx=lado * 1.15, dz=0.82, tb=1.28)


def emitir_sinal_radio(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Ondas sonar CRT verde/ciano irradiando das duas antenas."""
    del pos, vel, dir_x
    ad, ae = anc.get("antena_d"), anc.get("antena_e")
    if ad is None or ae is None:
        return
    centro = (ad + ae) * 0.5
    rel_d, rel_e = ad - centro, ae - centro
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("sinal_radio_holograma")
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
            raio, esp = (0.26 + 0.90 * fase) * escala, max(0.016, 0.068 * escala * (1.0 - fase * 0.7))
            for k in range(5):
                a0, a1 = (-0.36 + (k / 5.0) * 0.72) * pi, (-0.36 + ((k + 1) / 5.0) * 0.72) * pi
                p0 = orig + Vec3(s * (0.14 + cos(a0) * raio), -0.06, 0.14 + sin(a0) * raio)
                p1 = orig + Vec3(s * (0.14 + cos(a1) * raio), -0.06, 0.14 + sin(a1) * raio)
                idx = _emitir_segmento_dungeons(vw, cw, tris, idx, p0, p1, esp, esp, _BLUE, _GREEN, _WHITE)
        tris.closePrimitive()
        arco_np.node().markInternalBoundsStale()
        arco_np.show()

    _registrar(mgr, raiz, centro, "sinal_radio", 0.56, atualizar)


def emitir_tontura(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """3 retículas de perda de sinal CRT orbitando acima da cabeça."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, 0.0, 0.62)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("tontura_holograma")
    reticulas = tuple(_crt(raiz, f"hl_ret_{i}", 11) for i in range(3))

    def atualizar(fase: float) -> None:
        env = min(1.0, fase / 0.14) * min(1.0, (1.0 - fase) / 0.20)
        for i, rt in enumerate(reticulas):
            ang = fase * 3.6 * pi + i * (2.0 * pi / 3.0)
            tam = 0.86 * escala * env * (0.88 + 0.18 * sin(ang))
            (rt.hide if tam <= 0.03 else rt.show)()
            rt.setPos(cos(ang) * 1.35 * escala, sin(ang) * 0.35 - 0.06, sin(ang) * 0.28 * escala)
            rt.setR(fase * 180.0)
            rt.setScale(tam, 1.0, tam * _N_COLS)
            rt.setShaderInput("u_fade", env)

    _registrar(mgr, raiz, orig, "tontura", 1.05, atualizar)


def emitir_poeira_passo(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Fragmentos de scanlines horizontais rasantes atrás do tênis ao correr/derrapar."""
    del vel
    lado = -1.0 if dir_x >= 0 else 1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("pes", anc["tronco"]))
    escala = max(0.65, min(1.30, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("poeira_passo_holograma")
    scans = [(_crt(raiz, f"hl_pp_{i}", 12), i * 0.10, 0.92 - i * 0.14) for i in range(2)]

    def atualizar(fase: float) -> None:
        for i, (pf, at, tb) in enumerate(scans):
            u = max(0.0, (fase - at) / (1.0 - at))
            tam = tb * escala * (0.58 + 0.52 * min(1.0, u * 4.0)) * min(1.0, (1.0 - u) / 0.26)
            (pf.hide if fase < at or tam <= 0.03 else pf.show)()
            pf.setTexOffset(stage, (13 if u > 0.56 else 12) / _N_COLS, 0.0)
            pf.setPos(lado * (0.98 + (1.0 - exp(-4.4 * u)) * (0.95 + i * 0.35)) * escala, -0.14, (0.28 + u * 0.62) * escala)
            pf.setScale(tam * lado, 1.0, tam * _N_COLS)
            pf.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))

    _registrar(mgr, raiz, orig, "poeira_passo", 0.40, atualizar)


def emitir_suor(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Barrinha CRT térmica piscando junto à têmpora."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("templo", anc["visor_lado"])) + Vec3(0.44 * lado, -0.08, 0.24)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("suor_holograma")
    barra = _crt(raiz, "hl_suor", 14)

    def atualizar(fase: float) -> None:
        fim = min(1.0, (1.0 - fase) / 0.24)
        tam = 0.88 * escala * min(1.0, fase / 0.14) * fim
        (barra.hide if tam <= 0.03 else barra.show)()
        barra.setPos(_jitter_crt(fase, 0.05) + 0.14 * lado * escala, -0.10, (0.18 - fase * 0.72) * escala)
        barra.setScale(tam * 0.75, 1.0, tam * 1.15 * _N_COLS)
        barra.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, "suor", 0.62, atualizar)


def emitir_suspiro(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Exaustão de scanlines horizontais escapando na frente do visor."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("visor_lado", anc["cabeca_topo"])) + Vec3(0.46 * lado, -0.08, 0.04)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("suspiro_holograma")
    vent = _crt(raiz, "hl_suspiro", 12)

    def atualizar(fase: float) -> None:
        fim = min(1.0, (1.0 - fase) / 0.26)
        tam = 1.18 * escala * min(1.0, fase / 0.16) * fim
        (vent.hide if tam <= 0.03 else vent.show)()
        vent.setPos(lado * (0.28 + fase * 0.86) * escala + _jitter_crt(fase, 0.04), -0.10, -fase * 0.22 * escala)
        vent.setScale(tam * lado, 1.0, tam * _N_COLS)
        vent.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, "suspiro", 0.68, atualizar)


def emitir_tristeza(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """HUD ``IDLE`` opaco com queda de sinal CRT acima da cabeça."""
    del vel, dir_x
    orig = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.08, 0.78)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("tristeza_holograma")
    hud = _crt(raiz, "hl_tristeza", 7)

    def atualizar(fase: float) -> None:
        env = min(1.0, fase / 0.18) * min(1.0, (1.0 - fase) / 0.24)
        tam = 1.32 * escala * env
        (hud.hide if tam <= 0.03 else hud.show)()
        hud.setPos(_jitter_crt(fase, 0.03), -0.10, (0.14 - fase * 0.12) * escala)
        hud.setScale(tam, 1.0, tam * _N_COLS)
        hud.setShaderInput("u_fade", env * 0.85)

    _registrar(mgr, raiz, orig, "tristeza", 0.96, atualizar)


def emitir_estalo_fone(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Retícula rápida + flash áudio-sync no fone."""
    del vel
    chave = "fone_dir" if dir_x >= 0 else "fone_esq"
    orig = (Vec3(pos) if pos is not None else Vec3(anc.get(chave, anc["cabeca_topo"]))) + Vec3(0.30 * (1.0 if dir_x >= 0 else -1.0), -0.10, 0.12)
    escala = max(0.70, min(1.30, float(forca)))
    raiz = NodePath("estalo_fone_holograma")
    spark = _crt(raiz, "hl_estalo", 9)

    def atualizar(fase: float) -> None:
        snap = 1.18 if fase < 0.25 else max(0.0, (1.0 - fase) / 0.75)
        tam = 1.08 * escala * snap
        (spark.hide if tam <= 0.03 else spark.show)()
        spark.setScale(tam, 1.0, tam * _N_COLS)
        spark.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.25))

    _registrar(mgr, raiz, orig, "estalo_fone", 0.28, atualizar)


def emitir_espirro(mgr, anc, *, pos=None, vel=None, dir_x=1.0, forca=1.0) -> None:
    """Rajada de pacotes CRT fragmentados saindo à frente do gabinete."""
    del vel
    lado = 1.0 if dir_x >= 0 else -1.0
    orig = Vec3(pos) if pos is not None else Vec3(anc.get("porta", anc.get("visor_lado", anc["tronco"])))
    escala = max(0.75, min(1.35, float(forca)))
    raiz = NodePath("espirro_holograma")
    frag = _crt(raiz, "hl_espirro", 13)

    def atualizar(fase: float) -> None:
        u = 1.0 - (1.0 - fase) ** 2
        fim = min(1.0, (1.0 - fase) / 0.24)
        tam = 1.32 * escala * min(1.0, fase / 0.14) * fim
        (frag.hide if tam <= 0.03 else frag.show)()
        frag.setPos(lado * (0.44 + u * 1.05) * escala + _jitter_crt(fase, 0.06), -0.12, (0.08 - u * 0.16) * escala)
        frag.setScale(tam * lado, 1.0, tam * _N_COLS)
        frag.setShaderInput("u_fade", fim)

    _registrar(mgr, raiz, orig, "espirro", 0.42, atualizar)


EMISSORES_HOLOGRAMA = {
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
