"""Gerador procedural dos atlas Punk/Graffiti do estilo ``street``.

Cria três planilhas RGBA de alta nitidez (borda externa quantizada para evitar
franja de chroma key ``#D600D6``):
- ``street_molduras.png`` (6 células 512x512): molduras gigantes de pôster que
  emolduram o mascote sem cobrir o visor central.
- ``street_stickers.png`` (16 células 256x256): stickers e placas rasgadas com
  tipografia pichada, carinhas, coroas e estilhaços.
- ``street_extras.png`` (8 células 256x256): micro-VFX (``suor``, ``suspiro``,
  ``tristeza``, ``estalo_fone``, ``espirro``) e tags punk extras.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

INK = (13, 14, 20, 255)
WHITE = (250, 250, 238, 255)
YELLOW = (255, 225, 34, 255)
RED = (255, 36, 56, 255)
CYAN = (18, 214, 255, 255)
LIME = (166, 245, 30, 255)
ORANGE = (255, 107, 26, 255)
BLUE = (32, 118, 255, 255)
TEAL_GLOOM = (58, 102, 138, 255)
SKY_GLOOM = (110, 198, 230, 255)

_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "textures" / "vfx_street"


def _carregar_fonte(tamanho: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Carrega fonte pesada de impacto disponível no Windows ou fallback."""
    candidatos = (
        Path("C:/Windows/Fonts/impact.ttf"),
        Path("C:/Windows/Fonts/ariblk.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    )
    for caminho in candidatos:
        if caminho.exists():
            return ImageFont.truetype(str(caminho), tamanho)
    return ImageFont.load_default()


def _quantizar_alfa_borda(img: Image.Image) -> Image.Image:
    """Remove semitransparência na borda externa para evitar halo no chroma key."""
    px = img.load()
    larg, alt = img.size
    for y in range(alt):
        for x in range(larg):
            r, g, b, a = px[x, y]
            if a < 128:
                px[x, y] = (0, 0, 0, 0)
            else:
                px[x, y] = (r, g, b, 255)
    return img


def _jagged_poly(
    pts: list[tuple[float, float]], rng: random.Random, amp: float
) -> list[tuple[float, float]]:
    """Aplica leve tremor artesanal nos vértices para estética rascunhada."""
    return [(x + rng.uniform(-amp, amp), y + rng.uniform(-amp, amp)) for x, y in pts]


def _draw_punk_poly(
    draw: ImageDraw.ImageDraw,
    pts: list[tuple[float, float]],
    fill: tuple[int, int, int, int],
    *,
    ink_width: int = 8,
    shadow: tuple[int, int] = (7, 7),
) -> None:
    """Desenha polígono com sombra dura preta e contorno grosso rascunhado."""
    if shadow != (0, 0):
        sx, sy = shadow
        draw.polygon([(x + sx, y + sy) for x, y in pts], fill=INK)
    draw.polygon(pts, fill=fill, outline=INK, width=ink_width)
    # Segundo traço deslocado para sensação de pincel/canetão duplo
    extra = [(x + 1.5, y - 1.5) for x, y in pts] + [(pts[0][0] + 1.5, pts[0][1] - 1.5)]
    draw.line(extra, fill=INK, width=max(2, ink_width // 3))


def _draw_spray_splats(
    draw: ImageDraw.ImageDraw,
    rng: random.Random,
    cx: float,
    cy: float,
    count: int,
    spread: float,
    color: tuple[int, int, int, int],
    radius_range: tuple[float, float] = (3.0, 9.0),
) -> None:
    """Espalha gotas e respingos de spray com contorno fino de tinta."""
    for _ in range(count):
        ang = rng.uniform(0.0, math.tau)
        dist = rng.uniform(spread * 0.25, spread)
        px = cx + math.cos(ang) * dist
        py = cy + math.sin(ang) * dist
        r = rng.uniform(*radius_range)
        draw.ellipse((px - r - 2, py - r - 2, px + r + 2, py + r + 2), fill=INK)
        draw.ellipse((px - r, py - r, px + r, py + r), fill=color)


def _draw_drips(
    draw: ImageDraw.ImageDraw,
    rng: random.Random,
    xs: list[float],
    y0: float,
    color: tuple[int, int, int, int],
    length_range: tuple[float, float] = (14.0, 34.0),
) -> None:
    """Desenha escorridos de tinta vertical abaixo de tags e placas."""
    for x in xs:
        comp = rng.uniform(*length_range)
        w = rng.uniform(3.5, 6.0)
        draw.line([(x, y0), (x, y0 + comp)], fill=INK, width=int(w * 2 + 5))
        draw.ellipse((x - w - 2, y0 + comp - w - 2, x + w + 2, y0 + comp + w + 2), fill=INK)
        draw.line([(x, y0), (x, y0 + comp)], fill=color, width=int(w * 2))
        draw.ellipse((x - w, y0 + comp - w, x + w, y0 + comp + w), fill=color)


def _draw_graffiti_text(
    base: Image.Image,
    text: str,
    center: tuple[float, float],
    size: int,
    fill: tuple[int, int, int, int],
    angle: float,
    *,
    stroke: int = 8,
    shadow_off: tuple[int, int] = (7, 8),
) -> None:
    """Renderiza letra garrafal inclinada com sombra deslocada e contorno pesado."""
    fonte = _carregar_fonte(size)
    tmp = Image.new("RGBA", (base.width, base.height), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    cx, cy = tmp.width // 2, tmp.height // 2
    d.text(
        (cx + shadow_off[0], cy + shadow_off[1]),
        text,
        font=fonte,
        fill=INK,
        anchor="mm",
        stroke_width=stroke,
        stroke_fill=INK,
    )
    d.text(
        (cx, cy),
        text,
        font=fonte,
        fill=fill,
        anchor="mm",
        stroke_width=stroke,
        stroke_fill=INK,
    )
    rot = tmp.rotate(angle, resample=Image.Resampling.NEAREST, center=(cx, cy))
    dx = int(center[0] - cx)
    dy = int(center[1] - cy)
    base.alpha_composite(rot, dest=(dx, dy))


def _draw_crown(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    scale: float,
    fill: tuple[int, int, int, int],
    tilt: float = -0.18,
) -> None:
    """Coroa de 3 pontas estilo Basquiat/graffiti com pontas gordinhas."""
    pts = [
        (-34, 18),
        (-42, -20),
        (-16, 2),
        (0, -32),
        (16, 2),
        (42, -20),
        (34, 18),
    ]
    ct, st = math.cos(tilt), math.sin(tilt)
    poly = [(cx + (x * ct - y * st) * scale, cy + (x * st + y * ct) * scale) for x, y in pts]
    _draw_punk_poly(draw, poly, fill, ink_width=max(4, int(6 * scale)), shadow=(4, 5))


def _draw_punk_face(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    radius: float,
    fill: tuple[int, int, int, int],
    mood: str = "x_x",
) -> None:
    """Desenha carinha pichada/punk (``x_x``, ``happy``, ``angry``)."""
    r = radius
    draw.ellipse((cx - r + 5, cy - r + 6, cx + r + 5, cy + r + 6), fill=INK)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill, outline=INK, width=6)
    ex = r * 0.36
    ey = cy - r * 0.14
    w_eye = max(4, int(r * 0.11))
    if mood == "x_x":
        for sx in (-1.0, 1.0):
            ox = cx + sx * ex
            d = r * 0.16
            draw.line([(ox - d, ey - d), (ox + d, ey + d)], fill=INK, width=w_eye)
            draw.line([(ox - d, ey + d), (ox + d, ey - d)], fill=INK, width=w_eye)
    elif mood == "angry":
        for sx in (-1.0, 1.0):
            ox = cx + sx * ex
            draw.line([(ox - r * 0.2, ey - r * 0.12 * sx), (ox + r * 0.2, ey + r * 0.08 * sx)], fill=INK, width=w_eye)
            draw.ellipse((ox - 5, ey + 2, ox + 5, ey + 12), fill=INK)
    else:
        for sx in (-1.0, 1.0):
            ox = cx + sx * ex
            draw.arc((ox - 10, ey - 9, ox + 10, ey + 9), 185, 355, fill=INK, width=w_eye)
    # Sorriso punk com dentes em zigue-zague
    my = cy + r * 0.34
    mw = r * 0.56
    draw.arc((cx - mw, my - r * 0.28, cx + mw, my + r * 0.25), 10, 170, fill=INK, width=w_eye)
    for tooth in (-0.28, 0.0, 0.28):
        tx = cx + tooth * mw
        draw.line([(tx, my + 2), (tx + 3, my + 11)], fill=INK, width=max(3, w_eye - 1))


def _draw_wild_arrow(
    draw: ImageDraw.ImageDraw,
    pts: list[tuple[float, float]],
    head_dir: tuple[float, float],
    fill: tuple[int, int, int, int],
    width: float = 16.0,
) -> None:
    """Desenha seta wildstyle curvada com ponta angular grande."""
    for dx, dy, col in ((6, 6, INK), (0, 0, INK)):
        draw.line([(x + dx, y + dy) for x, y in pts], fill=col, width=int(width) + 12, joint="curve")
    draw.line(pts, fill=fill, width=int(width), joint="curve")
    hx, hy = pts[-1]
    ux, uy = head_dir
    mag = math.hypot(ux, uy) or 1.0
    ux, uy = ux / mag, uy / mag
    px, py = -uy, ux
    tip = (hx + ux * width * 1.9, hy + uy * width * 1.9)
    p1 = (hx + px * width * 1.35, hy + py * width * 1.35)
    p2 = (hx - px * width * 1.35, hy - py * width * 1.35)
    _draw_punk_poly(draw, [tip, p1, p2], fill, ink_width=6, shadow=(5, 5))


def _burst_polygon(
    cx: float, cy: float, r_in: float, r_out: float, spikes: int, rng: random.Random
) -> list[tuple[float, float]]:
    """Gera polígono estrelado assimétrico para explosões punk."""
    pts: list[tuple[float, float]] = []
    for i in range(spikes * 2):
        ang = (i / (spikes * 2)) * math.tau + rng.uniform(-0.08, 0.08)
        base = r_out if i % 2 == 0 else r_in
        r = base * rng.uniform(0.84, 1.16)
        pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
    return pts


def _cell_moldura_0_impacto(rng: random.Random) -> Image.Image:
    """Célula 0 (512x512): Impacto chão SMASH!/DROP! moldura punk aberta no centro."""
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Arcos e chapas assimétricas nas bordas preservando o miolo [155..357, 130..390]
    _draw_punk_poly(d, [(24, 390), (146, 360), (168, 452), (48, 476)], ORANGE, ink_width=9)
    _draw_punk_poly(d, [(352, 366), (484, 386), (464, 472), (344, 444)], RED, ink_width=9)
    _draw_punk_poly(d, [(32, 86), (164, 34), (178, 126), (52, 162)], CYAN, ink_width=8)
    _draw_wild_arrow(d, [(48, 224), (84, 310), (138, 368)], (0.8, 0.6), YELLOW, width=15)
    _draw_wild_arrow(d, [(464, 232), (428, 316), (374, 372)], (-0.8, 0.6), LIME, width=15)
    _draw_crown(d, 412, 92, 1.25, YELLOW, tilt=0.22)
    _draw_punk_face(d, 96, 200, 42, YELLOW, mood="x_x")
    _draw_spray_splats(d, rng, 110, 420, 12, 70, RED)
    _draw_spray_splats(d, rng, 405, 420, 12, 70, CYAN)
    _draw_drips(d, rng, [66, 98, 132], 144, CYAN, (18, 42))
    _draw_graffiti_text(img, "SMASH!", (155, 86), 62, YELLOW, 11, stroke=8)
    _draw_graffiti_text(img, "DROP!", (366, 442), 62, WHITE, -9, stroke=8)
    return _quantizar_alfa_borda(img)


def _cell_moldura_1_choque(rng: random.Random) -> Image.Image:
    """Célula 1 (512x512): Moldura elétrica ZAP!/VOLT com raios rasgados nas bordas."""
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    raios = [
        ([(48, 52), (144, 138), (94, 166), (172, 248), (108, 232), (56, 152), (96, 126)], CYAN),
        ([(464, 62), (372, 148), (424, 178), (350, 260), (412, 234), (456, 156), (410, 134)], YELLOW),
        ([(44, 446), (124, 366), (82, 344), (154, 286), (118, 360), (152, 384)], LIME),
        ([(468, 452), (376, 372), (420, 346), (354, 284), (392, 356), (356, 382)], ORANGE),
    ]
    for pts, col in raios:
        _draw_punk_poly(d, _jagged_poly(pts, rng, 5.0), col, ink_width=8)
    _draw_punk_face(d, 412, 108, 40, CYAN, mood="x_x")
    _draw_spray_splats(d, rng, 88, 300, 10, 62, YELLOW)
    _draw_spray_splats(d, rng, 424, 300, 10, 62, CYAN)
    _draw_graffiti_text(img, "ZAP!", (134, 88), 72, YELLOW, 14, stroke=9)
    _draw_graffiti_text(img, "BZZT", (358, 440), 58, CYAN, -11, stroke=8)
    return _quantizar_alfa_borda(img)


def _cell_moldura_2_rastro(rng: random.Random) -> Image.Image:
    """Célula 2 (512x512): Rastro cinético FAST>>> + faixas e setas graffiti."""
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    faixas = [
        ([(28, 128), (218, 66), (234, 110), (42, 172)], LIME),
        ([(20, 268), (170, 218), (182, 256), (32, 308)], ORANGE),
        ([(310, 358), (484, 304), (496, 346), (322, 400)], CYAN),
        ([(286, 428), (470, 382), (482, 416), (298, 464)], YELLOW),
    ]
    for pts, col in faixas:
        _draw_punk_poly(d, _jagged_poly(pts, rng, 4.0), col, ink_width=8)
    _draw_wild_arrow(d, [(320, 86), (402, 114), (456, 152)], (0.8, 0.5), LIME, width=16)
    _draw_wild_arrow(d, [(54, 418), (118, 444), (176, 440)], (0.95, 0.0), YELLOW, width=14)
    _draw_spray_splats(d, rng, 100, 160, 10, 60, ORANGE)
    _draw_spray_splats(d, rng, 410, 220, 10, 60, LIME)
    _draw_graffiti_text(img, "FAST>", (152, 86), 68, WHITE, 15, stroke=9)
    _draw_graffiti_text(img, "ZOOM!", (378, 434), 54, YELLOW, -10, stroke=8)
    return _quantizar_alfa_borda(img)


def _cell_moldura_3_sobressalto(rng: random.Random) -> Image.Image:
    """Célula 3 (512x512): Sobressalto HOLD UP! / ?! com pontas radiais externas."""
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pontas = [
        ([(22, 114), (154, 148), (132, 186)], RED),
        ([(56, 32), (168, 122), (124, 142)], YELLOW),
        ([(486, 98), (356, 144), (376, 184)], YELLOW),
        ([(448, 32), (344, 122), (384, 142)], CYAN),
        ([(26, 376), (146, 336), (166, 376)], YELLOW),
        ([(486, 382), (364, 338), (348, 382)], RED),
    ]
    for pts, col in pontas:
        _draw_punk_poly(d, _jagged_poly(pts, rng, 5.0), col, ink_width=8)
    _draw_punk_face(d, 416, 418, 40, RED, mood="angry")
    _draw_crown(d, 96, 418, 1.15, YELLOW, tilt=-0.2)
    _draw_spray_splats(d, rng, 84, 248, 10, 54, WHITE)
    _draw_graffiti_text(img, "HOLD!", (148, 74), 62, WHITE, 10, stroke=9)
    _draw_graffiti_text(img, "?!", (390, 82), 84, YELLOW, -14, stroke=9)
    return _quantizar_alfa_borda(img)


def _cell_moldura_4_musica(rng: random.Random) -> Image.Image:
    """Célula 4 (512x512): Moldura Groove/VIBE! com carinha feliz, coroa e notas."""
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _draw_crown(d, 256, 56, 1.45, YELLOW, tilt=-0.06)
    _draw_punk_face(d, 96, 116, 44, LIME, mood="happy")
    _draw_punk_face(d, 416, 396, 40, CYAN, mood="happy")
    _draw_punk_poly(d, _jagged_poly([(20, 200), (96, 176), (112, 234), (32, 258)], rng, 5.0), CYAN, ink_width=8)
    _draw_punk_poly(d, _jagged_poly([(404, 248), (492, 224), (484, 286), (398, 298)], rng, 5.0), YELLOW, ink_width=8)
    _draw_wild_arrow(d, [(48, 290), (88, 380), (146, 428)], (0.85, 0.5), ORANGE, width=15)
    _draw_wild_arrow(d, [(464, 210), (432, 130), (378, 86)], (-0.8, -0.5), LIME, width=15)
    _draw_spray_splats(d, rng, 110, 390, 12, 62, YELLOW)
    _draw_spray_splats(d, rng, 408, 148, 12, 62, ORANGE)
    _draw_graffiti_text(img, "VIBE!", (388, 84), 60, LIME, -11, stroke=8)
    _draw_graffiti_text(img, "YEAH!", (134, 444), 56, YELLOW, 9, stroke=8)
    return _quantizar_alfa_borda(img)


def _cell_moldura_5_xray(rng: random.Random) -> Image.Image:
    """Célula 5 (512x512): Impacto Raio-X inspirado no painel 8 (BANG! amarelo/ciano)."""
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    raios_bg = _burst_polygon(256, 256, 168, 248, 14, rng)
    _draw_punk_poly(d, raios_bg, YELLOW, ink_width=8, shadow=(0, 0))
    miolo = _burst_polygon(256, 256, 86, 116, 11, rng)
    d.polygon(miolo, fill=(0, 0, 0, 0), outline=INK, width=7)
    _draw_punk_poly(d, [(42, 42), (168, 88), (112, 168)], CYAN, ink_width=8)
    _draw_punk_poly(d, [(468, 448), (344, 404), (396, 336)], RED, ink_width=8)
    _draw_spray_splats(d, rng, 96, 404, 14, 66, CYAN)
    _draw_spray_splats(d, rng, 412, 108, 14, 66, ORANGE)
    _draw_graffiti_text(img, "BANG!", (152, 82), 70, CYAN, 18, stroke=9)
    _draw_graffiti_text(img, "KRAK!", (370, 434), 62, ORANGE, -12, stroke=9)
    return _quantizar_alfa_borda(img)


def _cell_sticker_placa(
    rng: random.Random,
    text: str,
    fill_bg: tuple[int, int, int, int],
    fill_txt: tuple[int, int, int, int],
    size: int = 62,
    angle: float = 9.0,
    drips: bool = True,
) -> Image.Image:
    """Sticker de placa rasgada assimétrica + letras pichadas + gotas."""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = _jagged_poly([(24, 72), (222, 46), (236, 174), (32, 198)], rng, 11.0)
    _draw_punk_poly(d, pts, fill_bg, ink_width=9, shadow=(8, 8))
    if drips:
        _draw_drips(d, rng, [68, 144, 196], 184, fill_bg, (16, 36))
    _draw_spray_splats(d, rng, 128, 122, 7, 102, YELLOW if fill_bg != YELLOW else CYAN, (3.0, 6.0))
    _draw_graffiti_text(img, text, (128, 122), size, fill_txt, angle, stroke=8)
    return _quantizar_alfa_borda(img)


def _cell_sticker_explosao(
    rng: random.Random,
    text: str,
    fill_bg: tuple[int, int, int, int],
    fill_txt: tuple[int, int, int, int],
    size: int = 58,
) -> Image.Image:
    """Sticker estrelado caótico estilo comic/punk com letra torta."""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = _burst_polygon(126, 124, 62, 108, 10, rng)
    _draw_punk_poly(d, pts, fill_bg, ink_width=8, shadow=(7, 8))
    _draw_spray_splats(d, rng, 128, 128, 6, 108, WHITE, (3.0, 6.0))
    _draw_graffiti_text(img, text, (126, 124), size, fill_txt, rng.uniform(-12, 12), stroke=8)
    return _quantizar_alfa_borda(img)


def _cell_sticker_fast(rng: random.Random) -> Image.Image:
    """Célula 3: Letras FAST> que viram seta de movimento e rastro."""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = _jagged_poly([(18, 92), (176, 62), (240, 114), (186, 184), (24, 188)], rng, 7.0)
    _draw_punk_poly(d, pts, LIME, ink_width=8, shadow=(7, 7))
    _draw_drips(d, rng, [52, 118], 178, LIME, (14, 30))
    _draw_graffiti_text(img, "FAST>>", (124, 124), 52, WHITE, 10, stroke=8)
    return _quantizar_alfa_borda(img)


def _cell_sticker_coracao(rng: random.Random) -> Image.Image:
    """Célula 5: Coração pichado com gotas e brilho."""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts: list[tuple[float, float]] = []
    for i in range(28):
        t = (i / 28.0) * math.tau
        hx = 16.0 * math.sin(t) ** 3
        hy = -(13.0 * math.cos(t) - 5.0 * math.cos(2 * t) - 2.0 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((126 + hx * 4.9 + rng.uniform(-3, 3), 122 + hy * 4.9 + rng.uniform(-3, 3)))
    _draw_punk_poly(d, pts, RED, ink_width=8, shadow=(7, 8))
    _draw_drips(d, rng, [126], 188, RED, (16, 28))
    d.arc((68, 70, 116, 114), 190, 275, fill=WHITE, width=7)
    _draw_crown(d, 174, 58, 0.72, YELLOW, tilt=0.28)
    return _quantizar_alfa_borda(img)


def _cell_sticker_brilho_nota_estrela(rng: random.Random, tipo: str) -> Image.Image:
    """Células 9 (faísca), 10 (nota musical), 11 (estrela tonta), 12 (puff)."""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if tipo == "faisca":
        pts = _burst_polygon(128, 128, 28, 106, 4, rng)
        _draw_punk_poly(d, pts, YELLOW, ink_width=8)
        _draw_punk_poly(d, _burst_polygon(128, 128, 14, 54, 4, rng), WHITE, ink_width=4, shadow=(0, 0))
    elif tipo == "nota":
        _draw_punk_poly(d, _burst_polygon(128, 128, 74, 104, 7, rng), CYAN, ink_width=8)
        d.ellipse((68, 142, 124, 188), fill=YELLOW, outline=INK, width=7)
        d.rectangle((108, 62, 126, 160), fill=YELLOW, outline=INK, width=6)
        _draw_punk_poly(d, [(112, 62), (186, 44), (186, 82), (112, 96)], LIME, ink_width=6, shadow=(0, 0))
    elif tipo == "estrela":
        pts = _burst_polygon(128, 128, 44, 102, 5, rng)
        _draw_punk_poly(d, pts, YELLOW, ink_width=8)
        d.ellipse((104, 104, 152, 152), fill=ORANGE, outline=INK, width=5)
    else:
        bolhas = [(86, 134, 42), (128, 108, 48), (170, 132, 40), (126, 150, 44)]
        for bx, by, br in bolhas:
            d.ellipse((bx - br + 6, by - br + 7, bx + br + 6, by + br + 7), fill=INK)
        for bx, by, br in bolhas:
            d.ellipse((bx - br, by - br, bx + br, by + br), fill=INK)
        for bx, by, br in bolhas:
            r2 = br - 8
            d.ellipse((bx - r2, by - r2, bx + r2, by + r2), fill=WHITE)
        d.arc((98, 94, 152, 142), 20, 210, fill=CYAN, width=6)
    return _quantizar_alfa_borda(img)


def _cell_sticker_caco(rng: random.Random, cor: tuple[int, int, int, int], modo: str) -> Image.Image:
    """Células 13 (carinha punk), 14 e 15 (estilhaços ciano e laranja)."""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if modo == "face":
        _draw_punk_face(d, 126, 134, 72, YELLOW, mood="x_x")
        _draw_crown(d, 126, 46, 0.85, RED, tilt=-0.1)
    else:
        pts = _jagged_poly([(128, 30), (218, 118), (138, 224), (42, 128)], rng, 14.0)
        _draw_punk_poly(d, pts, cor, ink_width=9, shadow=(7, 8))
        _draw_spray_splats(d, rng, 128, 128, 5, 88, WHITE, (3.0, 6.0))
    return _quantizar_alfa_borda(img)


def _extra_suor(rng: random.Random, img: Image.Image, d: ImageDraw.ImageDraw) -> None:
    pts = [(128, 32), (178, 132), (172, 188), (128, 216), (84, 188), (78, 132)]
    _draw_punk_poly(d, _jagged_poly(pts, rng, 5.0), CYAN, ink_width=9, shadow=(7, 8))
    d.line([(106, 136), (112, 178)], fill=WHITE, width=9)
    _draw_spray_splats(d, rng, 128, 92, 4, 58, WHITE, (3.0, 5.5))


def _extra_suspiro(_rng: random.Random, _img: Image.Image, d: ImageDraw.ImageDraw) -> None:
    for off, col in ((0, WHITE), (28, CYAN)):
        d.arc((36, 74 + off, 174, 174 + off), 195, 355, fill=INK, width=22)
        d.arc((36, 74 + off, 174, 174 + off), 195, 355, fill=col, width=9)
    d.ellipse((158, 118, 216, 174), fill=WHITE, outline=INK, width=8)
    d.arc((170, 130, 204, 162), 20, 260, fill=CYAN, width=6)


def _extra_tristeza(_rng: random.Random, _img: Image.Image, d: ImageDraw.ImageDraw) -> None:
    for bx, by, br in ((82, 112, 38), (126, 92, 44), (172, 112, 36)):
        d.ellipse((bx - br - 6, by - br - 6, bx + br + 6, by + br + 6), fill=INK)
    for bx, by, br in ((82, 112, 38), (126, 92, 44), (172, 112, 36)):
        d.ellipse((bx - br, by - br, bx + br, by + br), fill=TEAL_GLOOM)
    for rx in (86, 128, 168):
        d.line([(rx, 152), (rx - 10, 206)], fill=INK, width=12)
        d.line([(rx, 152), (rx - 10, 206)], fill=SKY_GLOOM, width=5)


def _extra_estalo(rng: random.Random, img: Image.Image, d: ImageDraw.ImageDraw) -> None:
    _draw_punk_poly(d, _burst_polygon(128, 128, 52, 102, 8, rng), YELLOW, ink_width=8)
    _draw_graffiti_text(img, "POP!", (128, 128), 54, CYAN, -12, stroke=7)


def _extra_espirro(rng: random.Random, img: Image.Image, d: ImageDraw.ImageDraw) -> None:
    _draw_punk_poly(d, [(32, 128), (196, 48), (222, 118), (196, 198)], LIME, ink_width=8)
    _draw_spray_splats(d, rng, 194, 124, 10, 62, CYAN, (4.0, 8.0))
    _draw_graffiti_text(img, "ATCH!", (124, 124), 46, WHITE, 8, stroke=7)


def _cell_extra(rng: random.Random, idx: int) -> Image.Image:
    """Constrói uma das 8 células 256x256 de ``street_extras.png``."""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    builders = {
        0: _extra_suor,
        1: _extra_suspiro,
        2: _extra_tristeza,
        3: _extra_estalo,
        4: _extra_espirro,
    }
    if idx in builders:
        builders[idx](rng, img, d)
    elif idx == 5:
        _draw_punk_face(d, 128, 130, 74, YELLOW, mood="happy")
    elif idx == 6:
        _draw_crown(d, 128, 134, 1.95, YELLOW, tilt=-0.12)
    else:
        _draw_punk_poly(d, _jagged_poly([(26, 78), (226, 54), (232, 174), (34, 192)], rng, 10), LIME, ink_width=8)
        _draw_graffiti_text(img, "YEAH!", (128, 124), 56, ORANGE, -10, stroke=8)
    return _quantizar_alfa_borda(img)


def gerar_atlas_street() -> tuple[Path, Path, Path]:
    """Gera os três arquivos PNG em ``assets/textures/vfx_street``."""
    _ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261125)

    molduras = Image.new("RGBA", (3072, 512), (0, 0, 0, 0))
    construtores_m = (
        _cell_moldura_0_impacto,
        _cell_moldura_1_choque,
        _cell_moldura_2_rastro,
        _cell_moldura_3_sobressalto,
        _cell_moldura_4_musica,
        _cell_moldura_5_xray,
    )
    for i, fn in enumerate(construtores_m):
        molduras.paste(fn(rng), (i * 512, 0))

    stickers_cells = (
        _cell_sticker_placa(rng, "DROP!", YELLOW, RED, 58, 9.0),
        _cell_sticker_explosao(rng, "BANG!", RED, YELLOW, 54),
        _cell_sticker_explosao(rng, "ZAP!", CYAN, YELLOW, 64),
        _cell_sticker_fast(rng),
        _cell_sticker_explosao(rng, "!", YELLOW, RED, 96),
        _cell_sticker_coracao(rng),
        _cell_sticker_placa(rng, "ZZZ", BLUE, WHITE, 70, -10.0),
        _cell_sticker_explosao(rng, "#?!", RED, YELLOW, 64),
        _cell_sticker_placa(rng, "?", YELLOW, WHITE, 96, 11.0),
        _cell_sticker_brilho_nota_estrela(rng, "faisca"),
        _cell_sticker_brilho_nota_estrela(rng, "nota"),
        _cell_sticker_brilho_nota_estrela(rng, "estrela"),
        _cell_sticker_brilho_nota_estrela(rng, "puff"),
        _cell_sticker_caco(rng, YELLOW, "face"),
        _cell_sticker_caco(rng, CYAN, "caco"),
        _cell_sticker_caco(rng, ORANGE, "caco"),
    )
    stickers = Image.new("RGBA", (4096, 256), (0, 0, 0, 0))
    for i, cel in enumerate(stickers_cells):
        stickers.paste(cel, (i * 256, 0))

    extras = Image.new("RGBA", (2048, 256), (0, 0, 0, 0))
    for i in range(8):
        extras.paste(_cell_extra(rng, i), (i * 256, 0))

    p_m = _ASSETS_DIR / "street_molduras.png"
    p_s = _ASSETS_DIR / "street_stickers.png"
    p_e = _ASSETS_DIR / "street_extras.png"
    molduras.save(p_m)
    stickers.save(p_s)
    extras.save(p_e)
    return p_m, p_s, p_e


if __name__ == "__main__":
    caminhos = gerar_atlas_street()
    for p in caminhos:
        print(f"Gerado: {p}")
