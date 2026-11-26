"""VFX de transição estilo-cientes para as 7 aberturas e 10 encerramentos do Mário.

Todas as partículas e malhas usam ``shader_sprite_bayer`` ou geometria 3D opaca
sem franja de alpha suave, preservando 100% o chroma key ``#D600D6`` no desktop.
"""

from __future__ import annotations

from functools import cache
from math import cos, pi, sin
from typing import ClassVar

from panda3d.core import (
    GeomVertexWriter,
    NodePath,
    PNMImage,
    Texture,
    TextureStage,
    Vec3,
)

from sejoga.render.sprites_efeitos import cartao_pixel, textura_pixel
from sejoga.render.vfx.acao_blockbench import _emitir_segmento_dungeons
from sejoga.render.vfx.choque_blockbench import _criar_no_arco

_N_COLS = 8

_PALETAS: dict[str, tuple[tuple[float, float, float, float], ...]] = {
    "blockbench": (
        (0.14, 0.78, 1.00, 1.0),
        (1.00, 0.86, 0.24, 1.0),
        (0.95, 0.97, 1.00, 1.0),
        (0.06, 0.08, 0.14, 1.0),
    ),
    "street": (
        (1.00, 0.88, 0.13, 1.0),
        (0.07, 0.84, 1.00, 1.0),
        (0.65, 0.96, 0.12, 1.0),
        (0.05, 0.05, 0.08, 1.0),
    ),
    "anime": (
        (0.30, 0.82, 1.00, 1.0),
        (1.00, 0.88, 0.26, 1.0),
        (0.98, 0.99, 0.98, 1.0),
        (0.09, 0.09, 0.14, 1.0),
    ),
    "spiderverse": (
        (1.00, 0.20, 0.26, 1.0),
        (0.07, 0.85, 1.00, 1.0),
        (1.00, 0.91, 0.10, 1.0),
        (0.05, 0.04, 0.07, 1.0),
    ),
    "holograma": (
        (0.11, 0.91, 1.00, 1.0),
        (0.22, 0.96, 0.55, 1.0),
        (0.95, 1.00, 1.00, 1.0),
        (0.04, 0.14, 0.30, 1.0),
    ),
}

_ALIASES_ESTILO = {
    "padrao": "blockbench",
    "lowpoly_block": "blockbench",
    "pixel": "blockbench",
    "hifi_comic": "street",
    "cyberfunk": "street",
    "anime_impact": "anime",
    "manga_papel": "anime",
    "rascunho": "spiderverse",
    "gameboy": "holograma",
}


def _normalizar_estilo(estilo: str) -> str:
    chave = str(estilo or "blockbench").strip().lower()
    chave = _ALIASES_ESTILO.get(chave, chave)
    return chave if chave in _PALETAS else "blockbench"


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _pintar_feixe_e_puff(img: PNMImage, branco, preto) -> None:
    for y in range(2, 30):
        larg = 4 if 6 <= y <= 25 else 2
        for x in range(16 - larg, 16 + larg):
            img.setXelA(x, y, *(preto if x in (16 - larg, 15 + larg) else branco))
    for y in range(32):
        for x in range(32):
            d2 = (x - 16) ** 2 + (y - 16) ** 2
            if d2 <= 169:
                img.setXelA(32 + x, y, *(preto if d2 >= 121 else branco))


def _pintar_estrela_e_floco(img: PNMImage, branco) -> None:
    for y in range(2, 30):
        for x in range(2, 30):
            dx, dy = abs(x - 16), abs(y - 16)
            if (dx <= 2 and dy <= 13) or (dy <= 2 and dx <= 13) or (dx + dy <= 5):
                img.setXelA(64 + x, y, *branco)
    for y in range(11, 21):
        for x in range(11, 21):
            if abs(x - 16) + abs(y - 16) <= 5:
                img.setXelA(96 + x, y, *branco)


def _pintar_celulas_basicas(img: PNMImage) -> None:
    branco = (0.98, 0.98, 0.98, 1.0)
    preto = (0.06, 0.06, 0.10, 1.0)
    ouro = (1.0, 0.88, 0.20, 1.0)
    _pintar_feixe_e_puff(img, branco, preto)
    _pintar_estrela_e_floco(img, branco)
    for k in range(24):
        rx = 16 + (-4 if k % 12 < 6 else 4)
        for dx in range(-2, 3):
            img.setXelA(128 + rx + dx, 4 + k, *(preto if abs(dx) == 2 else branco))
    for y in range(32):
        for x in range(32):
            d = ((x - 16) ** 2 + (y - 16) ** 2) ** 0.5
            if 7.5 <= d <= 13.5:
                img.setXelA(160 + x, y, *(preto if d < 9.0 or d > 12.2 else ouro))


def _pintar_celulas_extras(img: PNMImage) -> None:
    branco = (0.98, 0.98, 0.98, 1.0)
    preto = (0.06, 0.06, 0.10, 1.0)
    # 6: fatia de vórtice / 7: traço diagonal de velocidade
    for y in range(32):
        for x in range(32):
            d = ((x - 16) ** 2 + (y - 16) ** 2) ** 0.5
            if 9.0 <= d <= 14.0 and x >= 12:
                img.setXelA(192 + x, y, *(preto if d < 10.2 or d > 13.0 else branco))
    for i in range(24):
        for t in range(-2, 3):
            img.setXelA(224 + 4 + i, max(2, min(29, 24 - i // 2 + t)), *(preto if abs(t) == 2 else branco))


@cache
def _textura_transicoes() -> Texture:
    img = PNMImage(32 * _N_COLS, 32, 4)
    img.fill(0.0, 0.0, 0.0)
    img.alphaFill(0.0)
    _pintar_celulas_basicas(img)
    _pintar_celulas_extras(img)
    tex = textura_pixel("vfx_transicoes_atlas_v1", img)
    tex.setFormat(Texture.FSrgbAlpha)
    return tex


class GerenciadorVfxTransicao:
    """Controla cartões e anéis 3D estilo-cientes em tempo real nas aberturas e saídas."""

    _POOL_SIZE: ClassVar[int] = 44

    def __init__(self, parent_node: NodePath, escala_global: float = 1.0) -> None:
        """Inicializa pool de cartões Bayer e geometria 3D das transições."""
        self.root = parent_node.attachNewNode("vfx-transicoes-root")
        self._escala = max(0.5, min(1.8, float(escala_global)))
        self._cards: list[NodePath] = []
        self._arco_np, self._vdata, self._tris = _criar_no_arco(self.root)
        self._arco_np.hide()

    def _garantir_cards(self, qtd: int) -> None:
        tex = _textura_transicoes()
        stage = TextureStage.getDefault()
        while len(self._cards) < min(self._POOL_SIZE, qtd):
            card = cartao_pixel(self.root, f"tvfx_{len(self._cards)}", tex)
            card.setTexScale(stage, 1.0 / _N_COLS, 1.0)
            card.hide()
            self._cards.append(card)

    def _ocultar_tudo(self) -> None:
        for c in self._cards:
            c.hide()
        self._arco_np.hide()

    def limpar(self) -> None:
        """Oculta imediatamente todas as partículas e arcos de transição."""
        self._ocultar_tudo()

    def _set_card(
        self,
        idx: int,
        celula: int,
        pos: Vec3,
        escala: float,
        cor: tuple[float, float, float, float],
        fade: float,
        *,
        rot: float = 0.0,
        aspecto_x: float = 1.0,
        atras: bool = False,
    ) -> None:
        if idx >= len(self._cards) or fade <= 0.04 or escala <= 0.02:
            return
        card = self._cards[idx]
        stage = TextureStage.getDefault()
        card.setTexOffset(stage, celula / _N_COLS, 0.0)
        card.setPos(pos)
        card.setR(rot)
        card.setScale(escala * aspecto_x, 1.0, escala * _N_COLS)
        card.setColorScale(*cor)
        card.setShaderInput("u_fade", _clamp01(fade))
        if atras:
            card.setBin("background", 14)
        else:
            card.clearBin()
        card.show()

    def _desenhar_anel(
        self,
        centro: Vec3,
        raio_x: float,
        raio_z: float,
        esp: float,
        cor_m: tuple[float, float, float, float],
        cor_b: tuple[float, float, float, float],
        cor_i: tuple[float, float, float, float],
        *,
        segs: int = 12,
        rot_ang: float = 0.0,
    ) -> None:
        self._vdata.uncleanSetNumRows(0)
        self._tris.clearVertices()
        vw = GeomVertexWriter(self._vdata, "vertex")
        cw = GeomVertexWriter(self._vdata, "color")
        idx = 0
        for k in range(segs):
            a0 = rot_ang + (k / segs) * 2.0 * pi
            a1 = rot_ang + ((k + 1) / segs) * 2.0 * pi
            p0 = centro + Vec3(cos(a0) * raio_x, -0.08, sin(a0) * raio_z)
            p1 = centro + Vec3(cos(a1) * raio_x, -0.08, sin(a1) * raio_z)
            idx = _emitir_segmento_dungeons(vw, cw, self._tris, idx, p0, p1, esp, esp, cor_b, cor_m, cor_i)
        self._tris.closePrimitive()
        self._arco_np.node().markInternalBoundsStale()
        self._arco_np.show()

    def _entrada_vertical(self, estilo_tr: str, p: float, pal, anc: dict[str, Vec3]) -> None:
        base = anc.get("pes", Vec3(0, -0.4, -1.5))
        topo = anc.get("cabeca_topo", Vec3(0, -0.4, 2.5))
        c1, c2, c3, ink = pal
        self._garantir_cards(14)
        if estilo_tr == "goku_teleport_in":
            env = sin(_clamp01(p / 0.58) * pi)
            if env > 0.05:
                self._set_card(0, 0, base + Vec3(0.0, -0.1, 1.4), 1.9 * env + 0.5, c1, env, aspecto_x=1.55)
                self._desenhar_anel(base, 0.35 + p * 2.4, 0.35, max(0.04, 0.22 * (1.0 - p)), c1, ink, c3)
            for i in range(4):
                u = _clamp01((p - 0.14 - i * 0.05) / 0.45)
                ang = i * pi * 0.5 + p * 4.0
                self._set_card(1 + i, 2, (base + topo) * 0.5 + Vec3(cos(ang) * 1.6 * u, -0.12, sin(ang) * 1.4 * u), 0.72 * sin(u * pi), c2, sin(u * pi))
            return
        # hero_drop_in: riscos de vento na descida + anel e puffs no pouso
        if p < 0.62:
            u = p / 0.62
            for i in range(4):
                sx = (-1.1 + i * 0.72) * self._escala
                self._set_card(i, 0, topo + Vec3(sx, -0.1, 0.6 - u * 1.2), 0.78, c3, sin(u * pi), aspecto_x=0.55)
        if p >= 0.48:
            u = _clamp01((p - 0.48) / 0.46)
            self._desenhar_anel(base, (0.62 + 2.35 * u) * self._escala, 0.30 * self._escala, max(0.035, 0.20 * (1.0 - u)), c1, ink, c3)
            for s_idx, lado in enumerate((-1.0, 1.0)):
                self._set_card(4 + s_idx, 1, base + Vec3(lado * (0.72 + 1.75 * u), -0.1, 0.38 + 0.52 * u), (0.95 + 0.48 * u) * (1.0 - u), c3, 1.0 - u)
            self._set_card(6, 2, base + Vec3(0.0, -0.14, 0.64 + 0.78 * u), 1.05 * sin(u * pi), c2, sin(u * pi))

    def _entrada_horizontal(self, estilo_tr: str, p: float, pal, anc: dict[str, Vec3]) -> None:
        tronco = anc.get("tronco", Vec3(0, -0.4, 0.5))
        base = anc.get("pes", Vec3(0, -0.4, -1.5))
        c1, c2, c3, ink = pal
        self._garantir_cards(14)
        if estilo_tr == "kagebunshin_in":
            u = _clamp01((p - 0.06) / 0.68)
            for i in range(6):
                ang = i * (pi / 3.0) + 0.4
                pos = tronco + Vec3(cos(ang) * (0.4 + 1.7 * u), -0.12, sin(ang) * (0.3 + 1.3 * u))
                self._set_card(i, 1, pos, 1.15 * sin(u * pi), c3 if i % 2 == 0 else c1, sin(u * pi))
            if 0.08 < u < 0.85:
                self._desenhar_anel(tronco, 0.4 + 2.2 * u, 0.35 + 1.5 * u, max(0.03, 0.16 * (1.0 - u)), c2, ink, c3)
        elif estilo_tr == "run_from_depth":
            for i in range(6):
                ang = i * (pi / 3.0)
                u = (p * 1.4) % 1.0
                pos = tronco + Vec3(cos(ang) * (0.5 + 2.0 * u), -0.1, sin(ang) * (0.4 + 1.4 * u))
                self._set_card(i, 7, pos, 0.80 * (1.0 - u), c1 if i % 2 == 0 else c2, (1.0 - p) * 0.95, rot=-45.0 * (i + 1))
        else:
            # fade_in, sandevistan_in, virtual_insanity_in
            cel = 2 if estilo_tr == "fade_in" else 7
            for i in range(6):
                u = _clamp01(p * 1.25 - i * 0.06)
                fade = sin(u * pi)
                dx = (-1.6 + i * 0.58) * (1.0 - u * 0.4)
                py = (base.z + 0.25 if estilo_tr == "virtual_insanity_in" else tronco.z + sin(i * 1.3) * 0.75)
                self._set_card(i, cel, Vec3(tronco.x + dx, -0.12, py), 0.72 * fade + 0.1, c1 if i % 2 == 0 else c2, fade, rot=-18.0)

    def atualizar_entrada(self, estilo: str, progresso: float, estilo_visual: str, anc: dict[str, Vec3]) -> None:
        """Atualiza partículas e anéis da abertura ativa (``progresso`` em ``[0, 1]``)."""
        self._ocultar_tudo()
        p = _clamp01(progresso)
        if p <= 0.0 or p >= 0.99 or estilo in ("padrao", ""):
            return
        pal = _PALETAS[_normalizar_estilo(estilo_visual)]
        if estilo in ("hero_drop_in", "goku_teleport_in"):
            self._entrada_vertical(estilo, p, pal, anc)
        else:
            self._entrada_horizontal(estilo, p, pal, anc)

    def _saida_espalhada(self, estilo_tr: str, p: float, pal, anc: dict[str, Vec3]) -> None:
        tronco = anc.get("tronco", Vec3(0, -0.4, 0.5))
        c1, c2, c3, _ = pal
        if estilo_tr == "thanos_snap":
            self._garantir_cards(40)
            u = _clamp01((p - 0.10) / 0.88)
            for i in range(40):
                seed = i * 1.731
                ui = _clamp01(u * 1.22 - (i % 7) * 0.04)
                pos = tronco + Vec3((-0.7 + (i % 8) * 0.20) + ui * (1.9 + 0.5 * sin(seed)), -0.10, (-0.9 + (i // 8) * 0.42) + ui * 1.55 + sin(ui * 5.0 + seed) * 0.24)
                self._set_card(i, 3, pos, 0.34 * (1.0 - ui), c2 if i % 5 == 0 else (c1 if i % 2 == 0 else c3), 1.0 - ui, rot=ui * 180.0)
            return
        if estilo_tr == "sonic_classic":
            self._garantir_cards(10)
            u = _clamp01((p - 0.08) / 0.88)
            ouro_anel = (1.0, 0.96, 0.80, 1.0)
            for i in range(8):
                ang = (i / 8.0) * 2.0 * pi + 0.25
                pos = tronco + Vec3(cos(ang) * (0.4 + 2.6 * u), -0.10, sin(ang) * 2.2 * u - 1.7 * u * u + 0.45)
                self._set_card(i, 5, pos, 0.70, ouro_anel, 1.0 - u * 0.75, rot=u * 300.0)
            return
        # lego_disassemble, classic, peace_fade_out, virtual_insanity_out
        self._garantir_cards(12)
        cel = 2 if estilo_tr == "peace_fade_out" else (7 if estilo_tr == "virtual_insanity_out" else 1)
        for i in range(8):
            ang = (i / 8.0) * 2.0 * pi
            u = _clamp01(p * 1.15 - (i % 3) * 0.05)
            pos = tronco + Vec3(cos(ang) * (0.3 + 1.8 * u), -0.12, sin(ang) * (0.3 + 1.5 * u) + (0.9 * u if estilo_tr == "peace_fade_out" else 0.0))
            self._set_card(i, cel, pos, 0.72 * sin(u * pi), c2 if i % 2 == 0 else c1, 1.0 - u, rot=u * 90.0)

    def _saida_energia(self, estilo_tr: str, p: float, pal, anc: dict[str, Vec3]) -> None:
        tronco = anc.get("tronco", Vec3(0, -0.4, 0.5))
        c1, c2, c3, ink = pal
        self._garantir_cards(18)
        if estilo_tr == "portal_pull_out":
            u = _clamp01((p - 0.06) / 0.90)
            rot_r = p * 8.0
            self._desenhar_anel(tronco + Vec3(0, 0.35, 0.35), (2.25 * (1.0 - u * 0.55)) * self._escala, (2.25 * (1.0 - u * 0.55)) * self._escala, 0.20, c1, ink, c2, segs=16, rot_ang=rot_r)
            for i in range(12):
                ang = (i / 12.0) * 2.0 * pi + p * 7.5
                dist = (2.15 - 1.95 * u) * self._escala
                self._set_card(i, 6, tronco + Vec3(cos(ang) * dist, 0.25, 0.35 + sin(ang) * dist), 0.72, c2 if i % 2 == 0 else c1, 1.0 - u * 0.5, rot=-ang * 57.3, atras=True)
            return
        if estilo_tr == "goku_teleport_out":
            u = _clamp01((p - 0.08) / 0.88)
            env = sin(u * pi)
            self._set_card(0, 0, tronco + Vec3(0.0, -0.12, 0.9), 2.1 * env + 0.2, c1, env, aspecto_x=1.4)
            self._set_card(1, 2, tronco + Vec3(0.0, -0.14, 0.4), 1.65 * (1.0 - u), c3, 1.0 - u)
            self._desenhar_anel(tronco + Vec3(0, 0, 0.2), max(0.18, 2.2 * (1.0 - u)), max(0.12, 0.6 * (1.0 - u)), 0.14, c2, ink, c3)
            return
        # fnf_blue_balls, cyberpsicopata_out
        ad, ae = anc.get("antena_d", tronco + Vec3(-0.9, -0.1, 1.6)), anc.get("antena_e", tronco + Vec3(0.9, -0.1, 1.6))
        self._desenhar_anel(tronco + Vec3(0, 0, 0.2), 0.6 + p * 1.9, 0.4 + p * 1.2, 0.14, c1, ink, c2)
        for i in range(8):
            orig = ad if i % 2 == 0 else ae
            ang = (i / 4.0) * pi + p * 9.0
            self._set_card(i, 4, orig + Vec3(cos(ang) * 0.85, -0.1, sin(ang) * 0.75), 0.85 * (1.0 - p * 0.5), c2 if i % 2 else c1, 1.0 - p * 0.6, rot=ang * 57.3)

    def atualizar_saida(self, estilo: str, progresso: float, estilo_visual: str, anc: dict[str, Vec3]) -> None:
        """Atualiza partículas e anéis da saída/morte ativa (``progresso`` em ``[0, 1]``)."""
        self._ocultar_tudo()
        p = _clamp01(progresso)
        if p <= 0.0 or p >= 0.99:
            return
        pal = _PALETAS[_normalizar_estilo(estilo_visual)]
        if estilo in ("portal_pull_out", "goku_teleport_out", "fnf_blue_balls", "cyberpsicopata_out"):
            self._saida_energia(estilo, p, pal, anc)
        else:
            self._saida_espalhada(estilo, p, pal, anc)
