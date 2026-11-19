"""Arte procedural de pixel art nítida (32x32-40x40) para os efeitos de cena."""

from __future__ import annotations

import math
from itertools import pairwise

from panda3d.core import PNMImage, Texture

from sejoga.render.sprites_efeitos import textura_pixel

RGBA = tuple[float, float, float, float]

_INK: RGBA = (0.09, 0.09, 0.14, 1.0)
_WHITE: RGBA = (1.0, 1.0, 1.0, 1.0)


def _clamp_rgb_colorkey(c: RGBA) -> RGBA:
    """Impede magenta puro (214,0,214) que furaria a transparência Win32."""
    r, g, b, a = c
    if a > 0.1 and r > 0.55 and b > 0.55 and g < 0.24:
        g = 0.24
    return (r, g, b, a)


class CanvasPixel:
    """Buffer RGBA discreto com primitivas vetoriais e contorno pixelado automático."""

    def __init__(self, width: int, height: int) -> None:
        """Cria um buffer pixelado vazio de ``width`` por ``height``."""
        self.w = width
        self.h = height
        self._px: list[list[RGBA | None]] = [[None] * width for _ in range(height)]

    def set(self, x: int, y: int, cor: RGBA) -> None:
        """Pinta o pixel ``(x, y)`` protegendo contra a cor de transparência Win32."""
        if 0 <= x < self.w and 0 <= y < self.h:
            self._px[y][x] = _clamp_rgb_colorkey(cor)

    def disc(self, cx: float, cy: float, r: float, cor: RGBA) -> None:
        """Rasteriza um disco sólido centrado em ``(cx, cy)``."""
        r2 = r * r
        x0, x1 = max(0, int(cx - r - 1)), min(self.w - 1, int(cx + r + 1))
        y0, y1 = max(0, int(cy - r - 1)), min(self.h - 1, int(cy + r + 1))
        for y in range(y0, y1 + 1):
            dy = y - cy
            for x in range(x0, x1 + 1):
                dx = x - cx
                if dx * dx + dy * dy <= r2:
                    self.set(x, y, cor)

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, cor: RGBA) -> None:
        """Rasteriza uma elipse sólida com raios ``rx`` e ``ry``."""
        x0, x1 = max(0, int(cx - rx - 1)), min(self.w - 1, int(cx + rx + 1))
        y0, y1 = max(0, int(cy - ry - 1)), min(self.h - 1, int(cy + ry + 1))
        irx2 = 1.0 / max(1e-4, rx * rx)
        iry2 = 1.0 / max(1e-4, ry * ry)
        for y in range(y0, y1 + 1):
            dy = y - cy
            for x in range(x0, x1 + 1):
                dx = x - cx
                if dx * dx * irx2 + dy * dy * iry2 <= 1.0:
                    self.set(x, y, cor)

    def segment(self, x0: float, y0: float, x1: float, y1: float, r0: float, r1: float, cor: RGBA) -> None:
        """Traça uma cápsula cônica entre ``(x0, y0)`` e ``(x1, y1)``."""
        steps = max(4, int(math.hypot(x1 - x0, y1 - y0) * 2.2) + 2)
        for i in range(steps + 1):
            t = i / steps
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            self.disc(x, y, r0 + (r1 - r0) * t, cor)

    def star(self, cx: float, cy: float, r_ext: float, r_int: float, pontas: int, cor: RGBA, angle0: float = -math.pi / 2) -> None:
        """Rasteriza um polígono estrelado de ``pontas`` pontas."""
        verts: list[tuple[float, float]] = []
        total = pontas * 2
        for k in range(total):
            ang = angle0 + (k / total) * math.tau
            rad = r_ext if k % 2 == 0 else r_int
            verts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
        for y in range(max(0, int(cy - r_ext - 1)), min(self.h, int(cy + r_ext + 2))):
            for x in range(max(0, int(cx - r_ext - 1)), min(self.w, int(cx + r_ext + 2))):
                if _ponto_em_poligono(x + 0.25, y + 0.25, verts):
                    self.set(x, y, cor)

    def _tem_vizinho_opaco(
        self, x: int, y: int, offsets: tuple[tuple[int, int], ...]
    ) -> bool:
        return any(
            0 <= x + ox < self.w
            and 0 <= y + oy < self.h
            and self._px[y + oy][x + ox] is not None
            for ox, oy in offsets
        )

    def outline(self, cor: RGBA = _INK, diag: bool = False) -> None:
        """Contorna os pixels já pintados com borda de 1px na cor ``cor``."""
        offsets = ((-1, 0), (1, 0), (0, -1), (0, 1))
        if diag:
            offsets += ((-1, -1), (1, -1), (-1, 1), (1, 1))
        borda = [
            (x, y)
            for y in range(self.h)
            for x in range(self.w)
            if self._px[y][x] is None and self._tem_vizinho_opaco(x, y, offsets)
        ]
        for x, y in borda:
            self.set(x, y, cor)

    def para_textura(self, name: str) -> Texture:
        """Converte o buffer RGBA em textura Panda3D com filtro crispado."""
        pnm = PNMImage(self.w, self.h, 4)
        pnm.addAlpha()
        pnm.fill(0, 0, 0)
        pnm.alphaFill(0.0)
        for y in range(self.h):
            for x in range(self.w):
                cor = self._px[y][x]
                if cor is not None:
                    r, g, b, a = cor
                    pnm.setXel(x, y, r, g, b)
                    pnm.setAlpha(x, y, a)
        return textura_pixel(name, pnm)


def _ponto_em_poligono(px: float, py: float, verts: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(verts) - 1
    for i, (xi, yi) in enumerate(verts):
        xj, yj = verts[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / ((yj - yi) + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def tex_suor() -> Texture:
    """Gota de suor estilizada 32x32 em ciano com brilho especular."""
    c = CanvasPixel(32, 32)
    # Ponta superior (y pequeno no PNM = topo da textura) afinando até bulbo inferior.
    for i in range(18):
        t = i / 17.0
        y = 5.0 + t * 20.0
        r = 1.0 + math.sin(t * math.pi * 0.72) ** 0.85 * 6.8
        if t > 0.78:
            r *= max(0.35, 1.0 - (t - 0.78) * 1.9)
        c.disc(16.0, y, r, (0.14, 0.68, 0.98, 1.0))
    c.ellipse(15.5, 19.5, 5.2, 5.2, (0.34, 0.88, 1.0, 1.0))
    c.ellipse(13.8, 18.2, 2.0, 3.2, _WHITE)
    c.disc(16.0, 11.5, 1.2, (0.78, 0.97, 1.0, 1.0))
    c.outline(_INK, diag=False)
    return c.para_textura("fx-tex-suor")


def tex_tremor() -> Texture:
    """Linhas duplas de vibração/arrepio 28x32 nítidas."""
    c = CanvasPixel(28, 32)
    for shift, cor in ((0.0, (0.86, 0.94, 1.0, 1.0)), (7.0, (0.52, 0.82, 1.0, 1.0))):
        pts = ((9 + shift, 5), (6 + shift, 11), (10 + shift, 17), (6 + shift, 23), (9 + shift, 27))
        for p0, p1 in pairwise(pts):
            c.segment(p0[0], p0[1], p1[0], p1[1], 1.5, 1.5, cor)
    c.outline((0.12, 0.16, 0.24, 1.0))
    return c.para_textura("fx-tex-tremor")


def tex_raiva() -> Texture:
    """Marca clássica de veia de raiva 32x32 em vermelho vivo e contorno escuro."""
    c = CanvasPixel(32, 32)
    vermelho: RGBA = (1.0, 0.22, 0.30, 1.0)
    brilho: RGBA = (1.0, 0.58, 0.60, 1.0)
    cx, cy = 15.5, 15.5
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            # Cada quadrante curva para o centro deixando o clássico '+' vazado.
            arm_x = ((cx + sx * 10.5, cy + sy * 2.8), (cx + sx * 5.2, cy + sy * 3.5), (cx + sx * 2.8, cy + sy * 6.0), (cx + sx * 2.5, cy + sy * 10.5))
            for p0, p1 in pairwise(arm_x):
                c.segment(p0[0], p0[1], p1[0], p1[1], 1.7, 1.7, vermelho)
            c.disc(cx + sx * 4.5, cy + sy * 4.5, 1.1, brilho)
    c.outline(_INK, diag=False)
    return c.para_textura("fx-tex-raiva")


def tex_clarao() -> Texture:
    """Explosão estelar de impacto diagonal 40x40 com núcleo intenso e raios definidos."""
    c = CanvasPixel(40, 40)
    c.star(19.5, 19.5, 18.0, 3.8, 8, (1.0, 0.56, 0.14, 1.0), angle0=-math.pi / 8)
    c.star(19.5, 19.5, 14.0, 3.4, 8, (1.0, 0.92, 0.36, 1.0), angle0=-math.pi / 8)
    c.disc(19.5, 19.5, 5.2, _WHITE)
    c.outline((0.18, 0.12, 0.08, 1.0))
    return c.para_textura("fx-tex-clarao")


def tex_faisca() -> Texture:
    """Raio elétrico denteado 28x28 em ciano vibrante com núcleo branco (seguro para colorkey)."""
    c = CanvasPixel(28, 28)
    ciano: RGBA = (0.24, 0.90, 1.0, 1.0)
    pts = ((16.5, 3.5), (9.5, 12.0), (15.5, 13.5), (10.0, 23.5))
    for p0, p1 in pairwise(pts):
        c.segment(p0[0], p0[1], p1[0], p1[1], 2.2, 2.0, ciano)
        c.segment(p0[0], p0[1], p1[0], p1[1], 0.95, 0.95, _WHITE)
    c.outline((0.06, 0.14, 0.28, 1.0))
    return c.para_textura("fx-tex-faisca")


def tex_brilho() -> Texture:
    """Brilho estelar de 4 pontas 24x24 neutro para tingimento vivo por ColorScale."""
    c = CanvasPixel(24, 24)
    c.star(11.5, 11.5, 10.2, 2.2, 4, (0.86, 0.94, 1.0, 1.0), angle0=0.0)
    c.star(11.5, 11.5, 6.8, 1.8, 4, _WHITE, angle0=0.0)
    c.outline(_INK, diag=False)
    return c.para_textura("fx-tex-brilho")


def tex_estrela() -> Texture:
    """Estrela brilhante 32x32 em tons neutros para aceitar ColorScale sem sujar a cor."""
    c = CanvasPixel(32, 32)
    c.star(15.5, 16.0, 12.6, 5.4, 5, (0.76, 0.78, 0.84, 1.0))
    c.star(15.5, 15.2, 9.8, 4.2, 5, (0.96, 0.97, 1.0, 1.0))
    c.disc(13.8, 13.4, 2.2, _WHITE)
    c.outline(_INK)
    return c.para_textura("fx-tex-estrela")


def tex_z() -> Texture:
    """Letra 'Z' estilizada 32x32 azul-celeste para sono."""
    c = CanvasPixel(32, 32)
    azul: RGBA = (0.48, 0.78, 1.0, 1.0)
    topo: RGBA = (0.86, 0.95, 1.0, 1.0)
    c.segment(7.0, 8.0, 24.0, 8.0, 2.3, 2.3, topo)
    c.segment(23.5, 8.5, 7.5, 23.0, 2.2, 2.2, azul)
    c.segment(7.0, 23.5, 24.5, 23.5, 2.3, 2.3, azul)
    c.segment(8.0, 7.5, 22.0, 7.5, 1.0, 1.0, _WHITE)
    c.outline((0.10, 0.14, 0.28, 1.0))
    return c.para_textura("fx-tex-z")


def tex_nota_simples() -> Texture:
    """Colcheia musical estilizada 32x32 sombreada em branco para ColorScale vivo."""
    c = CanvasPixel(32, 32)
    claro: RGBA = (0.96, 0.98, 1.0, 1.0)
    sombra: RGBA = (0.74, 0.78, 0.86, 1.0)
    c.ellipse(11.0, 22.5, 4.9, 3.8, sombra)
    c.ellipse(10.5, 21.8, 3.8, 2.8, claro)
    c.disc(9.5, 20.8, 1.4, _WHITE)
    c.segment(14.5, 21.5, 14.5, 7.0, 1.8, 1.8, claro)
    c.segment(15.0, 7.2, 22.5, 10.2, 2.1, 1.3, claro)
    c.segment(15.0, 11.2, 21.0, 13.5, 1.4, 1.0, sombra)
    c.outline(_INK)
    return c.para_textura("fx-tex-nota-simples")


def tex_nota_dupla() -> Texture:
    """Nota musical dupla ligada 36x32 sombreada em branco para ColorScale vivo."""
    c = CanvasPixel(36, 32)
    claro: RGBA = (0.96, 0.98, 1.0, 1.0)
    sombra: RGBA = (0.74, 0.78, 0.86, 1.0)
    for cx, cy in ((9.5, 23.0), (23.5, 20.5)):
        c.ellipse(cx, cy, 4.4, 3.3, sombra)
        c.ellipse(cx - 0.4, cy - 0.5, 3.4, 2.4, claro)
        c.disc(cx - 1.2, cy - 1.2, 1.2, _WHITE)
    c.segment(12.5, 22.0, 12.5, 8.2, 1.6, 1.6, claro)
    c.segment(26.5, 19.5, 26.5, 6.2, 1.6, 1.6, claro)
    c.segment(12.5, 8.2, 26.5, 6.2, 2.2, 2.2, claro)
    c.segment(12.5, 12.2, 26.5, 10.2, 1.3, 1.3, sombra)
    c.outline(_INK)
    return c.para_textura("fx-tex-nota-dupla")


def tex_onda_sonora() -> Texture:
    """Arcos concêntricos de onda sonora 36x36."""
    c = CanvasPixel(36, 36)
    cx, cy = 8.0, 17.5
    for raio, esp, cor in ((11.5, 1.8, (0.30, 0.92, 1.0, 1.0)), (19.5, 2.0, (0.62, 0.98, 1.0, 1.0))):
        passos = 24
        for s in range(passos + 1):
            ang = -0.82 + (s / passos) * 1.64
            c.disc(cx + math.cos(ang) * raio, cy + math.sin(ang) * raio, esp, cor)
    c.outline((0.08, 0.16, 0.28, 1.0))
    return c.para_textura("fx-tex-onda-sonora")


def tex_poeira() -> Texture:
    """Nuvem fofa de poeira de pouso 36x28 em tons creme/bege."""
    c = CanvasPixel(36, 28)
    sombra: RGBA = (0.76, 0.72, 0.66, 0.95)
    creme: RGBA = (0.96, 0.94, 0.88, 0.95)
    for cx, cy, rx, ry in ((11.0, 17.0, 6.5, 5.0), (18.5, 14.0, 8.5, 6.5), (26.0, 17.5, 6.0, 4.5)):
        c.ellipse(cx, cy + 1.4, rx, ry, sombra)
        c.ellipse(cx - 0.5, cy - 0.6, rx * 0.88, ry * 0.82, creme)
    c.ellipse(17.5, 10.5, 4.8, 3.0, _WHITE)
    c.outline((0.20, 0.18, 0.16, 0.92))
    return c.para_textura("fx-tex-poeira")


def tex_poeira_fiapo() -> Texture:
    """Fiapo fino horizontal de poeira para deslize 32x16."""
    c = CanvasPixel(32, 16)
    creme: RGBA = (0.94, 0.92, 0.86, 0.92)
    c.segment(5.0, 9.0, 25.0, 8.0, 1.4, 3.2, (0.78, 0.74, 0.68, 0.90))
    c.ellipse(22.0, 7.2, 5.2, 2.8, creme)
    c.outline((0.22, 0.20, 0.18, 0.88))
    return c.para_textura("fx-tex-poeira-fiapo")


def tex_rastro_queda() -> Texture:
    """Linhas aerodinâmicas de velocidade vertical 24x40 (substitui as cruzes antigas)."""
    c = CanvasPixel(24, 40)
    for lx, y0, y1, esp in ((7.0, 4.0, 29.0, 1.6), (13.0, 8.0, 35.0, 2.1), (18.0, 5.0, 26.0, 1.4)):
        steps = int((y1 - y0) * 1.5)
        for s in range(steps + 1):
            t = s / max(1, steps)
            r = max(0.6, esp * (0.25 + 0.75 * t))
            cor = _WHITE if t > 0.55 else (0.62, 0.92, 1.0, 0.92)
            c.disc(lx, y0 + (y1 - y0) * t, r, cor)
    c.outline((0.12, 0.20, 0.34, 0.85))
    return c.para_textura("fx-tex-rastro-queda")


def tex_gosma() -> Texture:
    """Gota de gosma alienígena brilhante 28x28 segura para colorkey (G>=0.32)."""
    c = CanvasPixel(28, 28)
    sombra: RGBA = (0.68, 0.26, 0.44, 1.0)
    rosa: RGBA = (1.0, 0.36, 0.66, 1.0)
    c.ellipse(14.0, 15.5, 7.0, 7.5, sombra)
    c.disc(14.0, 8.0, 2.8, rosa)
    c.ellipse(13.5, 14.5, 5.8, 6.2, rosa)
    c.disc(11.5, 12.5, 1.8, (1.0, 0.82, 0.92, 1.0))
    c.outline((0.20, 0.06, 0.14, 1.0))
    return c.para_textura("fx-tex-gosma")
