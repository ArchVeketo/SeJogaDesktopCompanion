"""Gerador procedural dos 7 estilos gráficos de VFX realmente originais.

Cada preset possui silhuetas, símbolos e composições desenhadas do zero
exclusivamente para sua estética (zero recolorização homogênea):

- ``spider_verse``: Onomatopeias HQ (POW!, BAM!, BOP!, ZAP!, GRR!, BOOM!, YEAH!),
  Spidey-Sense 3 ondas, balão de pensamento, offset CMYK e retícula Ben-Day real.
- ``hifi_rush``: Equalizador 5 bandas, vinil girando, setas arcade de ritmo, gauge
  Overdrive, badge ``+1♥``, pausa lo-fi ``||`` e ondas de subwoofer.
- ``anime_sakuga``: Pétalas de sakura, gota de suor gigante, bolha de sono anime,
  cubos Yutapon, cross-flare anamórfico, vapor de raiva e aura de Ki.
- ``colorido``: Coroa estêncil, explosão splatter com escorrido vertical de tinta,
  bubble-tag, raio wildstyle e fita cassete grafite.
- ``lowpoly_3d``: Gemas octaedros, blocos voxel, prismas estrela e anéis
  hexagonais facetados em 3 planos de luz (combinados com malhas 3D em cena).
- ``pb_escuro``: Mangá Shonen com katakana (ドン!, ゴゴゴ, ビリ!), linhas de foco
  (shūchūsen), marcas de choque verticais (ガーン), pincel sumi-e e screentone.
- ``pb_claro``: Caderno Vivo / Sketchbook Doodle com fita cassete rabiscada,
  lâmpada de ideia, lua crescente, novelo furioso e aviãozinho de papel.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from panda3d.core import Texture
from PIL import Image, ImageDraw, ImageFilter

from sejoga.render.chroma_tuning import (
    CHROMA_HEX_PADRAO,
    derivar_chroma,
    seguro_contra_chroma_255,
)

TAMANHO_QUADRO = 256
QUADROS_POR_EFEITO = 4

PERFIS_MOVIMENTO_VFX: dict[str, dict[str, float]] = {
    "spider_verse": {"fps": 12.0, "jitter_pos": 0.022, "jitter_rot": 2.8, "pop": 1.22},
    "hifi_rush": {"fps": 12.0, "jitter_pos": 0.010, "jitter_rot": 1.4, "pop": 1.26},
    "anime_sakuga": {"fps": 24.0, "jitter_pos": 0.008, "jitter_rot": 1.1, "pop": 1.30},
    "colorido": {"fps": 15.0, "jitter_pos": 0.018, "jitter_rot": 2.2, "pop": 1.18},
    "lowpoly_3d": {"fps": 24.0, "jitter_pos": 0.004, "jitter_rot": 0.5, "pop": 1.14},
    "pb_escuro": {"fps": 10.0, "jitter_pos": 0.015, "jitter_rot": 1.8, "pop": 1.18},
    "pb_claro": {"fps": 8.0, "jitter_pos": 0.024, "jitter_rot": 2.6, "pop": 1.14},
}

_CORES_BASE_ESTILO: dict[str, dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]]] = {
    "spider_verse": {
        "musica": ((255, 224, 24), (0, 228, 255)),
        "choque": ((255, 236, 36), (0, 232, 255)),
        "raiva": ((255, 44, 68), (255, 224, 24)),
        "impacto": ((255, 224, 24), (255, 48, 72)),
        "queda_chao": ((248, 244, 228), (255, 58, 76)),
        "linhas_queda": ((0, 232, 255), (255, 224, 24)),
        "carinho": ((255, 58, 92), (255, 224, 32)),
        "susto": ((255, 228, 28), (255, 44, 72)),
        "tontura": ((255, 226, 28), (0, 230, 255)),
        "sono": ((244, 248, 255), (0, 228, 255)),
        "respingo": ((0, 232, 255), (255, 224, 24)),
        "assinatura": ((255, 226, 28), (0, 232, 255)),
    },
    "hifi_rush": {
        "musica": ((36, 236, 255), (255, 198, 20)),
        "choque": ((36, 236, 255), (255, 224, 36)),
        "raiva": ((255, 46, 56), (255, 164, 28)),
        "impacto": ((255, 198, 18), (255, 88, 28)),
        "queda_chao": ((36, 236, 255), (255, 168, 48)),
        "linhas_queda": ((255, 92, 32), (255, 214, 24)),
        "carinho": ((255, 76, 140), (255, 218, 72)),
        "susto": ((255, 218, 24), (255, 62, 32)),
        "tontura": ((42, 46, 62), (255, 198, 24)),
        "sono": ((92, 186, 255), (255, 234, 120)),
        "respingo": ((255, 212, 24), (36, 238, 255)),
        "assinatura": ((64, 244, 148), (255, 208, 24)),
    },
    "anime_sakuga": {
        "musica": ((84, 240, 255), (255, 232, 92)),
        "choque": ((255, 232, 48), (64, 236, 255)),
        "raiva": ((255, 42, 62), (255, 152, 42)),
        "impacto": ((255, 198, 42), (82, 238, 255)),
        "queda_chao": ((186, 236, 255), (108, 188, 248)),
        "linhas_queda": ((96, 240, 255), (242, 252, 255)),
        "carinho": ((255, 156, 198), (255, 224, 238)),
        "susto": ((96, 218, 255), (255, 224, 48)),
        "tontura": ((255, 228, 64), (96, 240, 255)),
        "sono": ((156, 222, 255), (86, 174, 248)),
        "respingo": ((88, 242, 255), (255, 228, 84)),
        "assinatura": ((255, 214, 44), (64, 238, 255)),
    },
    "colorido": {
        "musica": ((255, 214, 24), (38, 234, 255)),
        "choque": ((255, 228, 28), (176, 255, 38)),
        "raiva": ((255, 48, 52), (255, 152, 24)),
        "impacto": ((255, 126, 24), (176, 255, 38)),
        "queda_chao": ((176, 255, 38), (38, 234, 255)),
        "linhas_queda": ((38, 234, 255), (176, 255, 38)),
        "carinho": ((255, 76, 146), (255, 206, 64)),
        "susto": ((255, 224, 34), (255, 92, 32)),
        "tontura": ((38, 234, 255), (176, 255, 38)),
        "sono": ((134, 168, 255), (38, 234, 255)),
        "respingo": ((176, 255, 38), (255, 126, 24)),
        "assinatura": ((255, 214, 28), (38, 234, 255)),
    },
    "lowpoly_3d": {
        "musica": ((112, 244, 82), (48, 188, 228)),
        "choque": ((64, 228, 255), (255, 212, 48)),
        "raiva": ((242, 62, 62), (255, 168, 42)),
        "impacto": ((255, 198, 48), (64, 228, 255)),
        "queda_chao": ((214, 228, 244), (84, 192, 238)),
        "linhas_queda": ((120, 232, 255), (56, 158, 214)),
        "carinho": ((255, 92, 148), (255, 216, 86)),
        "susto": ((255, 224, 52), (255, 118, 32)),
        "tontura": ((88, 234, 255), (255, 206, 56)),
        "sono": ((138, 178, 255), (78, 220, 248)),
        "respingo": ((255, 212, 56), (92, 234, 255)),
        "assinatura": ((64, 242, 212), (255, 214, 56)),
    },
}

_GLIFOS: dict[str, tuple[tuple[tuple[float, float], ...], ...]] = {
    "P": (((0.16, 0.94), (0.16, 0.06), (0.76, 0.06), (0.86, 0.28), (0.72, 0.50), (0.16, 0.50)),),
    "O": (((0.50, 0.06), (0.82, 0.16), (0.88, 0.50), (0.82, 0.84), (0.50, 0.94), (0.18, 0.84), (0.12, 0.50), (0.18, 0.16), (0.50, 0.06)),),
    "W": (((0.06, 0.06), (0.26, 0.94), (0.50, 0.36), (0.74, 0.94), (0.94, 0.06)),),
    "B": (
        ((0.16, 0.94), (0.16, 0.06), (0.72, 0.06), (0.82, 0.25), (0.68, 0.48), (0.16, 0.48)),
        ((0.68, 0.48), (0.86, 0.70), (0.74, 0.94), (0.16, 0.94)),
    ),
    "A": (((0.12, 0.94), (0.50, 0.06), (0.88, 0.94)), ((0.26, 0.64), (0.74, 0.64))),
    "M": (((0.10, 0.94), (0.12, 0.06), (0.50, 0.60), (0.88, 0.06), (0.90, 0.94)),),
    "Z": (((0.14, 0.08), (0.86, 0.08), (0.14, 0.92), (0.86, 0.92)),),
    "G": (((0.84, 0.20), (0.52, 0.06), (0.20, 0.20), (0.14, 0.50), (0.22, 0.84), (0.54, 0.94), (0.84, 0.80), (0.84, 0.52), (0.52, 0.52)),),
    "R": (
        ((0.16, 0.94), (0.16, 0.06), (0.72, 0.06), (0.84, 0.26), (0.70, 0.50), (0.16, 0.50)),
        ((0.50, 0.50), (0.86, 0.94)),
    ),
    "Y": (((0.14, 0.06), (0.50, 0.50), (0.86, 0.06)), ((0.50, 0.50), (0.50, 0.94))),
    "E": (((0.84, 0.08), (0.18, 0.08), (0.18, 0.92), (0.84, 0.92)), ((0.18, 0.50), (0.72, 0.50))),
    "H": (((0.18, 0.06), (0.18, 0.94)), ((0.82, 0.06), (0.82, 0.94)), ((0.18, 0.50), (0.82, 0.50))),
    "X": (((0.14, 0.08), (0.86, 0.92)), ((0.86, 0.08), (0.14, 0.92))),
    "!": (((0.50, 0.05), (0.48, 0.64)), ((0.48, 0.86), (0.48, 0.94))),
    "?": (((0.20, 0.24), (0.42, 0.06), (0.74, 0.12), (0.82, 0.34), (0.50, 0.52), (0.50, 0.66)), ((0.50, 0.86), (0.50, 0.94))),
    "+": (((0.50, 0.18), (0.50, 0.82)), ((0.18, 0.50), (0.82, 0.50))),
    "1": (((0.26, 0.26), (0.54, 0.06), (0.54, 0.92)), ((0.24, 0.92), (0.82, 0.92))),
    "ド": (((0.34, 0.06), (0.34, 0.94)), ((0.34, 0.42), (0.74, 0.60)), ((0.64, 0.08), (0.76, 0.24)), ((0.84, 0.06), (0.94, 0.22))),
    "ン": (((0.16, 0.18), (0.38, 0.34)), ((0.18, 0.88), (0.58, 0.62), (0.88, 0.18))),
    "ゴ": (((0.14, 0.20), (0.68, 0.20), (0.68, 0.80)), ((0.14, 0.80), (0.70, 0.80)), ((0.78, 0.08), (0.88, 0.24)), ((0.92, 0.14), (0.98, 0.30))),
    "ビ": (((0.20, 0.12), (0.20, 0.86), (0.78, 0.80)), ((0.20, 0.44), (0.68, 0.34)), ((0.70, 0.08), (0.80, 0.22)), ((0.86, 0.06), (0.96, 0.20))),
    "リ": (((0.24, 0.14), (0.24, 0.56)), ((0.74, 0.10), (0.74, 0.58), (0.42, 0.92))),
}


def _coord_grade() -> tuple[np.ndarray, np.ndarray]:
    coords = np.arange(TAMANHO_QUADRO, dtype=np.float32)
    yy, xx = np.meshgrid(coords, coords, indexing="ij")
    return xx, yy


_XX, _YY = _coord_grade()


@dataclass
class _TelaCamadas:
    im_fill: Image.Image
    df: ImageDraw.ImageDraw
    im_acc: Image.Image
    da: ImageDraw.ImageDraw
    im_hi: Image.Image
    dh: ImageDraw.ImageDraw
    f_idx: int


def _nova_tela(f_idx: int) -> _TelaCamadas:
    im_fill = Image.new("L", (TAMANHO_QUADRO, TAMANHO_QUADRO), 0)
    im_acc = Image.new("L", (TAMANHO_QUADRO, TAMANHO_QUADRO), 0)
    im_hi = Image.new("L", (TAMANHO_QUADRO, TAMANHO_QUADRO), 0)
    return _TelaCamadas(
        im_fill=im_fill,
        df=ImageDraw.Draw(im_fill),
        im_acc=im_acc,
        da=ImageDraw.Draw(im_acc),
        im_hi=im_hi,
        dh=ImageDraw.Draw(im_hi),
        f_idx=f_idx,
    )


def _dilatar(mask: np.ndarray, raio: int) -> np.ndarray:
    if raio <= 0 or not np.any(mask):
        return mask
    img = Image.fromarray((mask.astype(np.uint8)) * 255, mode="L")
    out = img
    restante = max(3, raio * 2 + 1)
    while restante > 9:
        out = out.filter(ImageFilter.MaxFilter(9))
        restante -= 8
    out = out.filter(ImageFilter.MaxFilter(max(3, restante | 1)))
    return np.asarray(out, dtype=np.uint8) >= 128


def _deslocar(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(mask, dtype=bool)
    h, w = mask.shape
    sx0, sx1 = max(0, -dx), min(w, w - dx)
    sy0, sy1 = max(0, -dy), min(h, h - dy)
    dx0, dx1 = max(0, dx), min(w, w + dx)
    dy0, dy1 = max(0, dy), min(h, h + dy)
    if sx1 > sx0 and sy1 > sy0:
        out[dy0:dy1, dx0:dx1] = mask[sy0:sy1, sx0:sx1]
    return out


def _pts_estrela(
    cx: float, cy: float, r_out: float, r_in: float, pontas: int, rot: float = 0.0, jitter: float = 0.0
) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for i in range(pontas * 2):
        ang = rot + i * math.pi / pontas
        r = r_out if i % 2 == 0 else r_in
        if jitter > 0.0 and i % 2 == 0:
            r *= 1.0 + jitter * math.sin(i * 2.7 + rot * 3.1)
        pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
    return pts


def _polilinha(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]], width: int) -> None:
    if len(pts) < 2:
        return
    draw.line(pts, fill=255, width=width, joint="curve")
    r = max(1, width // 2)
    for x, y in pts:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=255)


def _desenhar_palavra(
    draw: ImageDraw.ImageDraw,
    texto: str,
    centro: tuple[float, float],
    tamanho: tuple[float, float],
    rot_rad: float = 0.0,
    espessura: int = 10,
) -> None:
    """Desenha tipografia vetorial grossa centrada para onomatopeias HQ e mangá."""
    if not texto:
        return
    cx, cy = centro
    larg, alt = tamanho
    n = len(texto)
    passo = larg / max(1.0, n)
    gw = passo * 0.78
    ca, sa = math.cos(rot_rad), math.sin(rot_rad)
    for idx, ch in enumerate(texto):
        tracos = _GLIFOS.get(ch)
        if not tracos:
            continue
        bx = -larg * 0.5 + (idx + 0.5) * passo
        for traco in tracos:
            pts: list[tuple[float, float]] = []
            for gx, gy in traco:
                lx = bx + (gx - 0.5) * gw + (0.5 - gy) * alt * 0.14
                ly = (gy - 0.5) * alt
                pts.append((cx + lx * ca - ly * sa, cy + lx * sa + ly * ca))
            _polilinha(draw, pts, espessura)


def _desenhar_coracao(draw: ImageDraw.ImageDraw, cx: float, cy: float, escala: float) -> None:
    pts: list[tuple[float, float]] = []
    for step in range(44):
        t = (step / 44.0) * math.tau
        px = 16.0 * (math.sin(t) ** 3)
        py = -(13.0 * math.cos(t) - 5.0 * math.cos(2.0 * t) - 2.0 * math.cos(3.0 * t) - math.cos(4.0 * t))
        pts.append((cx + px * escala, cy + py * escala))
    draw.polygon(pts, fill=255)


def _desenhar_z(draw: ImageDraw.ImageDraw, cx: float, cy: float, w: float, h: float, thick: int) -> None:
    _polilinha(
        draw,
        [(cx - w * 0.45, cy - h * 0.45), (cx + w * 0.45, cy - h * 0.45), (cx - w * 0.45, cy + h * 0.45), (cx + w * 0.45, cy + h * 0.45)],
        thick,
    )


def _desenhar_cassete(draw_fill: ImageDraw.ImageDraw, draw_acc: ImageDraw.ImageDraw, cx: float, cy: float, w: float, h: float, tilt: float) -> None:
    ca, sa = math.cos(tilt), math.sin(tilt)

    def _p(lx: float, ly: float) -> tuple[float, float]:
        return (cx + lx * ca - ly * sa, cy + lx * sa + ly * ca)

    corpo = [_p(-w * 0.5, -h * 0.5), _p(w * 0.5, -h * 0.5), _p(w * 0.5, h * 0.5), _p(-w * 0.5, h * 0.5)]
    _polilinha(draw_fill, [*corpo, corpo[0]], 9)
    faixa = [_p(-w * 0.34, -h * 0.14), _p(w * 0.34, -h * 0.14), _p(w * 0.34, h * 0.14), _p(-w * 0.34, h * 0.14)]
    _polilinha(draw_acc, [*faixa, faixa[0]], 6)
    for sx in (-w * 0.22, w * 0.22):
        px, py = _p(sx, 0.0)
        draw_acc.ellipse((px - 14, py - 14, px + 14, py + 14), outline=255, width=7)


def _desenhar_cubo_iso(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, rot: float = 0.0) -> None:
    pts = [
        (cx + math.cos(rot + k * math.tau / 6.0 - math.pi * 0.5) * r, cy + math.sin(rot + k * math.tau / 6.0 - math.pi * 0.5) * r)
        for k in range(6)
    ]
    draw.polygon(pts, fill=255)


# ---------------------------------------------------------------------------
# 1. SPIDER-VERSE: Onomatopeias HQ (POW!/BOP!/ZAP!/GRR!/BOOM!/YEAH!) + Spidey-Sense
# ---------------------------------------------------------------------------


def _sv_impacto(c: _TelaCamadas) -> None:
    esc = (0.76, 1.00, 1.04, 0.88)[c.f_idx]
    c.df.polygon(_pts_estrela(128, 128, 108 * esc, 56 * esc, 10, rot=c.f_idx * 0.14, jitter=0.20), fill=255)
    c.da.polygon(_pts_estrela(128, 128, 80 * esc, 40 * esc, 8, rot=-c.f_idx * 0.18), fill=255)
    palavra = "POW!" if c.f_idx < 2 else "BAM!"
    _desenhar_palavra(c.dh, palavra, (128, 128), (156 * esc, 62 * esc), -0.14, max(8, int(11 * esc)))


def _sv_musica(c: _TelaCamadas) -> None:
    dy = (-4.0, 0.0, 4.0, -2.0)[c.f_idx]
    c.df.polygon(_pts_estrela(126, 128 + dy, 96, 54, 9, rot=0.18 * c.f_idx, jitter=0.14), fill=255)
    _desenhar_palavra(c.da, "BOP!", (129, 127 + dy), (144, 58), -0.16, 14)
    _desenhar_palavra(c.dh, "BOP!", (126, 124 + dy), (144, 58), -0.16, 9)
    c.dh.ellipse((48, 42 + dy, 80, 66 + dy), fill=255)
    _polilinha(c.dh, [(72, 56 + dy), (72, 18 + dy), (100, 14 + dy)], 8)


def _sv_choque(c: _TelaCamadas) -> None:
    flip = 1.0 if c.f_idx % 2 == 0 else -1.0
    _polilinha(c.df, [(34, 46 + 10 * flip), (92, 92), (56, 128), (112, 168)], 14)
    _polilinha(c.df, [(148, 36), (198, 86 - 10 * flip), (168, 122), (218, 174)], 14)
    _desenhar_palavra(c.da, "ZAP!", (131, 137), (164, 68), 0.12 * flip, 15)
    _desenhar_palavra(c.dh, "ZAP!", (128, 134), (164, 68), 0.12 * flip, 9)


def _sv_susto(c: _TelaCamadas) -> None:
    jitter = (-5.0, 0.0, 5.0, -3.0)[c.f_idx]
    for raio_base, w_arc, alvo in ((46.0, 14, c.df), (82.0, 13, c.da), (114.0, 10, c.df)):
        pts = [
            (
                128.0 + math.cos(math.radians(-145.0 + (i / 10.0) * 110.0 + c.f_idx * 4.0)) * (raio_base + (13.0 if i % 2 == 0 else -13.0)),
                168.0 + jitter + math.sin(math.radians(-145.0 + (i / 10.0) * 110.0 + c.f_idx * 4.0)) * (raio_base + (13.0 if i % 2 == 0 else -13.0)),
            )
            for i in range(11)
        ]
        _polilinha(alvo, pts, w_arc)
    _desenhar_palavra(c.dh, "!", (128, 206), (34, 52), 0.0, 9)


def _sv_raiva(c: _TelaCamadas) -> None:
    c.df.polygon(_pts_estrela(128, 128, 104, 64, 11, rot=c.f_idx * 0.2, jitter=0.22), fill=255)
    _desenhar_palavra(c.da, "GRR!", (131, 131), (156, 62), -0.10, 15)
    _desenhar_palavra(c.dh, "GRR!", (128, 128), (156, 62), -0.10, 9)
    _desenhar_palavra(c.dh, "!", (206, 56), (32, 48), 0.20, 8)


def _sv_carinho(c: _TelaCamadas) -> None:
    esc = (4.2, 4.9, 5.1, 4.4)[c.f_idx]
    _desenhar_coracao(c.df, 128, 138, esc)
    _desenhar_coracao(c.da, 58, 56, 1.9)
    _desenhar_coracao(c.da, 202, 66, 1.6)
    c.dh.arc((74, 76, 126, 128), 190, 275, fill=255, width=10)


def _sv_tontura(c: _TelaCamadas) -> None:
    rot = c.f_idx * (math.pi * 0.25)
    c.da.arc((34, 64, 222, 192), 15 + c.f_idx * 35, 165 + c.f_idx * 35, fill=255, width=12)
    c.da.arc((34, 64, 222, 192), 195 + c.f_idx * 35, 345 + c.f_idx * 35, fill=255, width=12)
    for ang_o in (rot, rot + math.pi):
        sx, sy = 128.0 + math.cos(ang_o) * 80.0, 128.0 + math.sin(ang_o) * 44.0
        c.df.polygon(_pts_estrela(sx, sy, 34, 14, 5, rot=ang_o), fill=255)
    _desenhar_palavra(c.dh, "?!", (128, 128), (74, 52), 0.12, 8)


def _sv_sono(c: _TelaCamadas) -> None:
    dy = (-3, 0, 3, -2)[c.f_idx]
    for cx, cy, r in ((88, 108 + dy, 46), (132, 96 + dy, 54), (176, 112 + dy, 44), (130, 142 + dy, 48)):
        c.df.ellipse((cx - r, cy - r * 0.78, cx + r, cy + r * 0.78), fill=255)
    c.df.ellipse((54, 182, 82, 210), fill=255)
    c.df.ellipse((32, 218, 50, 236), fill=255)
    _desenhar_z(c.da, 102, 120 + dy, 38, 42, 10)
    _desenhar_z(c.da, 152, 104 + dy, 48, 52, 12)


def _sv_queda_chao(c: _TelaCamadas) -> None:
    spread = (0.82, 1.0, 1.06, 1.12)[c.f_idx]
    c.df.polygon(_pts_estrela(128, 154, 114 * spread, 58 * spread, 12, rot=0.1, jitter=0.18), fill=255)
    _desenhar_palavra(c.da, "BOOM!", (128, 154), (176 * spread, 56 * spread), -0.06, 10)
    _desenhar_palavra(c.dh, "!", (212, 110), (30, 44), 0.18, 7)


def _sv_linhas_queda(c: _TelaCamadas) -> None:
    off = (c.f_idx * 18) % 44
    for i, lx in enumerate((38, 78, 128, 178, 216)):
        alvo = c.df if i % 2 == 0 else c.da
        y0 = 20 + (off if i % 2 else 0)
        alvo.polygon([(lx - 10, y0), (lx + 10, y0), (lx + 2, 232), (lx - 2, 232)], fill=255)
        _polilinha(c.dh, [(lx, y0 + 12), (lx, 188)], 4)


def _sv_respingo(c: _TelaCamadas) -> None:
    esc = (0.78, 1.0, 0.96, 0.65)[c.f_idx]
    c.df.polygon(_pts_estrela(128, 128, 66 * esc, 24 * esc, 6, rot=c.f_idx * 0.25), fill=255)
    c.da.ellipse((54, 68, 84, 98), fill=255)
    c.dh.ellipse((116, 116, 140, 140), fill=255)


def _sv_assinatura(c: _TelaCamadas) -> None:
    esc = (0.80, 1.02, 1.05, 0.90)[c.f_idx]
    c.df.polygon(_pts_estrela(128, 128, 110 * esc, 62 * esc, 12, rot=-c.f_idx * 0.16, jitter=0.16), fill=255)
    palavra = "YEAH!" if c.f_idx % 2 == 0 else "POP!"
    _desenhar_palavra(c.da, palavra, (131, 131), (174 * esc, 62 * esc), -0.10, 15)
    _desenhar_palavra(c.dh, palavra, (128, 128), (174 * esc, 62 * esc), -0.10, 9)


# ---------------------------------------------------------------------------
# 2. HI-FI RUSH / ARCADE RHYTHM: Equalizador, Setas Arcade, Vinil, +1♥, Overdrive
# ---------------------------------------------------------------------------


def _hf_musica(c: _TelaCamadas) -> None:
    # Equalizador gráfico animado de 5 bandas + barra base
    alturas_quadros = (
        (64, 124, 166, 98, 140),
        (110, 174, 122, 162, 86),
        (152, 92, 178, 134, 156),
        (84, 144, 108, 170, 116),
    )[c.f_idx]
    base_y = 212
    c.da.rectangle((28, base_y + 8, 228, base_y + 20), fill=255)
    for idx, h_val in enumerate(alturas_quadros):
        x0 = 32 + idx * 40
        alvo = c.df if idx % 2 == 0 else c.da
        alvo.rectangle((x0, base_y - h_val, x0 + 28, base_y), fill=255)
        c.dh.rectangle((x0 + 4, base_y - h_val + 6, x0 + 24, base_y - h_val + 20), fill=255)


def _hf_seta(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, ang_rad: float) -> None:
    ca, sa = math.cos(ang_rad), math.sin(ang_rad)
    brutos = ((0.0, -r), (r * 0.85, 0.0), (r * 0.34, 0.0), (r * 0.34, r * 0.9), (-r * 0.34, r * 0.9), (-r * 0.34, 0.0), (-r * 0.85, 0.0))
    draw.polygon([(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in brutos], fill=255)


def _hf_impacto(c: _TelaCamadas) -> None:
    esc = (0.76, 1.00, 1.06, 0.92)[c.f_idx]
    c.df.ellipse((128 - 94 * esc, 128 - 94 * esc, 128 + 94 * esc, 128 + 94 * esc), outline=255, width=16)
    c.da.ellipse((128 - 54 * esc, 128 - 54 * esc, 128 + 54 * esc, 128 + 54 * esc), outline=255, width=12)
    for ang in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):
        _hf_seta(c.da, 128 + math.sin(ang) * 90 * esc, 128 - math.cos(ang) * 90 * esc, 24 * esc, ang)
    c.dh.polygon(_pts_estrela(128, 128, 34 * esc, 14 * esc, 4), fill=255)


def _hf_choque(c: _TelaCamadas) -> None:
    shift = (-8, 0, 8, -4)[c.f_idx]
    for off_y, alvo in ((-44, c.df), (0, c.da), (44, c.df)):
        _polilinha(alvo, [(46, 108 + off_y + shift), (98, 76 + off_y), (128, 114 + off_y), (164, 72 + off_y), (210, 104 + off_y - shift)], 15)
    _polilinha(c.dh, [(68, 104), (128, 114), (192, 100)], 6)


def _hf_susto(c: _TelaCamadas) -> None:
    esc = (0.86, 1.00, 1.04, 0.92)[c.f_idx]
    pts = [(128, 128 - 92 * esc), (128 + 96 * esc, 128 + 78 * esc), (128 - 96 * esc, 128 + 78 * esc)]
    _polilinha(c.df, [*pts, pts[0]], 16)
    c.da.polygon(pts, fill=255)
    _desenhar_palavra(c.dh, "!", (128, 146), (48 * esc, 74 * esc), 0.0, 12)


def _hf_raiva(c: _TelaCamadas) -> None:
    # Overdrive tachometer arc pegged in red + needle shaking at max
    c.df.arc((36, 52, 220, 236), 195, 355, fill=255, width=28)
    _polilinha(c.da, [(128, 166), (206, 98 + (-8, 6, -10, 4)[c.f_idx])], 14)
    c.dh.ellipse((110, 148, 146, 184), fill=255)
    _desenhar_palavra(c.dh, "!", (196, 54), (30, 42), 0.16, 8)


def _hf_carinho(c: _TelaCamadas) -> None:
    dy = (-4, 0, 4, -2)[c.f_idx]
    _desenhar_palavra(c.da, "+1", (78, 128 + dy), (86, 74), -0.06, 11)
    _desenhar_coracao(c.df, 174, 134 + dy, 3.2)
    c.dh.arc((142, 92 + dy, 174, 124 + dy), 190, 275, fill=255, width=8)


def _hf_tontura(c: _TelaCamadas) -> None:
    # Disco de vinil girando com brilho rotativo e agulha
    ang = c.f_idx * (math.pi * 0.35)
    c.df.ellipse((34, 34, 222, 222), fill=255)
    c.da.ellipse((94, 94, 162, 162), fill=255)
    c.dh.arc((50, 50, 206, 206), math.degrees(ang), math.degrees(ang) + 55, fill=255, width=10)
    c.dh.arc((50, 50, 206, 206), math.degrees(ang) + 180, math.degrees(ang) + 235, fill=255, width=10)
    _polilinha(c.da, [(204, 42), (178, 134), (154, 152)], 12)


def _hf_sono(c: _TelaCamadas) -> None:
    pulse = (0.88, 1.00, 1.04, 0.92)[c.f_idx]
    w, h = 28 * pulse, 92 * pulse
    c.df.rectangle((92 - w * 0.5, 128 - h * 0.5, 92 + w * 0.5, 128 + h * 0.5), fill=255)
    c.df.rectangle((164 - w * 0.5, 128 - h * 0.5, 164 + w * 0.5, 128 + h * 0.5), fill=255)
    _desenhar_z(c.da, 206, 60 - c.f_idx * 4, 38, 40, 10)
    c.dh.rectangle((86, 90, 96, 124), fill=255)
    c.dh.rectangle((158, 90, 168, 124), fill=255)


def _hf_queda_chao(c: _TelaCamadas) -> None:
    spread = (0.72, 0.94, 1.08, 1.16)[c.f_idx]
    c.df.arc((128 - 110 * spread, 124, 128 + 110 * spread, 212), 185, 355, fill=255, width=14)
    c.da.arc((128 - 76 * spread, 144, 128 + 76 * spread, 204), 185, 355, fill=255, width=11)
    _polilinha(c.dh, [(42, 186), (214, 186)], 8)


def _hf_linhas_queda(c: _TelaCamadas) -> None:
    for i, lx in enumerate((48, 92, 164, 208)):
        alvo = c.df if i % 2 == 0 else c.da
        for seg in range(3):
            y0 = 24 + seg * 72 + (c.f_idx * 14) % 36
            _polilinha(alvo, [(lx, y0), (lx, min(238, y0 + 44))], 12)


def _hf_respingo(c: _TelaCamadas) -> None:
    esc = (0.80, 1.00, 0.94, 0.68)[c.f_idx]
    _hf_seta(c.df, 128, 128, 56 * esc, c.f_idx * 0.4)
    c.da.polygon(_pts_estrela(74, 72, 22, 9, 4), fill=255)
    c.dh.ellipse((118, 118, 138, 138), fill=255)


def _hf_assinatura(c: _TelaCamadas) -> None:
    esc = (0.78, 1.00, 1.06, 0.90)[c.f_idx]
    pts_hex = _pts_estrela(128, 128, 98 * esc, 98 * esc, 3, rot=c.f_idx * 0.2)
    _polilinha(c.df, [*pts_hex, pts_hex[0]], 14)
    c.da.polygon(_pts_estrela(128, 128, 58 * esc, 18 * esc, 4, rot=math.pi * 0.25 + c.f_idx * 0.3), fill=255)
    for k in range(4):
        ang = k * math.pi * 0.5 + math.pi * 0.25
        _hf_seta(c.da, 128 + math.sin(ang) * 96 * esc, 128 - math.cos(ang) * 96 * esc, 20 * esc, ang)
    c.dh.polygon(_pts_estrela(128, 128, 30 * esc, 10 * esc, 4), fill=255)


# ---------------------------------------------------------------------------
# 3. ANIME SAKUGA: Cross-flare + Cubos Yutapon, Gota Suor, Bolha Sono, Sakura, Aura Ki
# ---------------------------------------------------------------------------


def _ak_impacto(c: _TelaCamadas) -> None:
    esc = (0.74, 1.00, 1.04, 0.90)[c.f_idx]
    rot = (-0.20, 0.08, 0.22, 0.38)[c.f_idx]
    c.df.polygon(_pts_estrela(128, 128, 114 * esc, 12 * esc, 4, rot=rot), fill=255)
    c.da.polygon(_pts_estrela(128, 128, 76 * esc, 10 * esc, 4, rot=rot + math.pi * 0.25), fill=255)
    for k, dist_c in enumerate((76, 94, 88, 102)):
        ang = rot + k * math.pi * 0.5 + 0.38
        _desenhar_cubo_iso(c.da, 128 + math.cos(ang) * dist_c * esc, 128 + math.sin(ang) * dist_c * esc, 18 * esc, ang)
    c.dh.polygon(_pts_estrela(128, 128, 48 * esc, 13 * esc, 4, rot=rot), fill=255)


def _ak_musica(c: _TelaCamadas) -> None:
    dy = (-5, 0, 5, -2)[c.f_idx]
    _polilinha(c.df, [(36, 174 + dy), (92, 126 + dy), (158, 152 - dy), (218, 92 - dy)], 11)
    c.da.polygon(_pts_estrela(104, 88 + dy, 38, 10, 4, rot=c.f_idx * 0.15), fill=255)
    c.df.polygon(_pts_estrela(186, 162 - dy, 28, 8, 4, rot=-c.f_idx * 0.15), fill=255)
    c.dh.polygon(_pts_estrela(104, 88 + dy, 22, 5, 4), fill=255)


def _ak_choque(c: _TelaCamadas) -> None:
    flip = 1.0 if c.f_idx % 2 == 0 else -1.0
    whip = [(48, 200), (104, 146 + 8 * flip), (82, 112), (148, 50), (132, 98), (206, 62 - 8 * flip)]
    _polilinha(c.df, whip, 14)
    _polilinha(c.da, [(82, 112), (44, 72)], 9)
    _polilinha(c.da, [(132, 98), (192, 166)], 9)
    _polilinha(c.dh, whip, 5)


def _ak_susto(c: _TelaCamadas) -> None:
    # Gota de suor gigante clássica de anime + risquinhos de choque!
    dy = (-4, 2, 8, 12)[c.f_idx]
    pts: list[tuple[float, float]] = [(128.0, 34.0 + dy)]
    for i in range(1, 25):
        u = i / 25.0
        ang = u * math.pi
        rx = 52.0 * math.sin(ang) * (0.65 + 0.35 * u)
        pts.append((128.0 + rx, 44.0 + dy + u * 168.0))
    for i in range(24, 0, -1):
        u = i / 25.0
        ang = u * math.pi
        rx = 52.0 * math.sin(ang) * (0.65 + 0.35 * u)
        pts.append((128.0 - rx, 44.0 + dy + u * 168.0))
    c.df.polygon(pts, fill=255)
    c.dh.arc((90, 122 + dy, 128, 184 + dy), 115, 220, fill=255, width=10)
    for ang_d in (-150, -30):
        r = math.radians(ang_d)
        _polilinha(c.da, [(128 + math.cos(r) * 76, 86 + math.sin(r) * 76), (128 + math.cos(r) * 108, 86 + math.sin(r) * 108)], 9)


def _ak_raiva(c: _TelaCamadas) -> None:
    # Veia anime + dois jatos de vapor subindo (Classic Anime Steam!)
    esc = (0.86, 1.0, 1.08, 0.94)[c.f_idx]
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        _polilinha(c.df, [(128 + sx * 48 * esc, 146 + sy * 14 * esc), (128 + sx * 14 * esc, 146 + sy * 14 * esc), (128 + sx * 14 * esc, 146 + sy * 48 * esc)], 14)
    dy_v = (-8, 0, 8, -4)[c.f_idx]
    for px in (66, 190):
        c.da.ellipse((px - 22, 46 + dy_v, px + 22, 92 + dy_v), fill=255)
        c.da.ellipse((px - 14, 78 + dy_v, px + 14, 114 + dy_v), fill=255)
        c.dh.ellipse((px - 8, 56 + dy_v, px + 4, 70 + dy_v), fill=255)


def _desenhar_petala_sakura(draw: ImageDraw.ImageDraw, cx: float, cy: float, esc: float, ang: float) -> None:
    ca, sa = math.cos(ang), math.sin(ang)
    brutos = ((0, 26), (-18, 6), (-22, -16), (-8, -26), (0, -14), (8, -26), (22, -16), (18, 6))
    draw.polygon([(cx + (x * ca - y * sa) * esc, cy + (x * sa + y * ca) * esc) for x, y in brutos], fill=255)


def _ak_carinho(c: _TelaCamadas) -> None:
    drift = (-8, 0, 8, 16)[c.f_idx]
    _desenhar_petala_sakura(c.df, 118 + drift * 0.4, 118 + drift * 0.4, 1.85, -0.35 + c.f_idx * 0.12)
    _desenhar_petala_sakura(c.da, 186 - drift * 0.3, 178 + drift * 0.3, 1.15, 0.55 - c.f_idx * 0.14)
    c.dh.polygon(_pts_estrela(64, 66, 26, 7, 4), fill=255)
    c.dh.polygon(_pts_estrela(192, 62, 18, 5, 4), fill=255)


def _ak_tontura(c: _TelaCamadas) -> None:
    rot = c.f_idx * (math.pi * 0.25)
    c.da.arc((36, 70, 220, 186), 10 + c.f_idx * 40, 170 + c.f_idx * 40, fill=255, width=10)
    c.da.arc((36, 70, 220, 186), 195 + c.f_idx * 40, 345 + c.f_idx * 40, fill=255, width=10)
    for ang_o in (rot, rot + math.pi):
        c.df.polygon(_pts_estrela(128 + math.cos(ang_o) * 78, 128 + math.sin(ang_o) * 44, 30, 8, 4, rot=ang_o), fill=255)


def _ak_sono(c: _TelaCamadas) -> None:
    # Clássica bolha de sono de anime (鼻提灯) pulsando!
    esc = (0.68, 0.94, 1.06, 0.80)[c.f_idx]
    cx, cy, r = 134, 134, 68 * esc
    c.df.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    c.da.ellipse((cx - r, cy - r, cx + r, cy + r), outline=255, width=10)
    c.dh.arc((cx - r * 0.65, cy - r * 0.65, cx + r * 0.25, cy + r * 0.25), 185, 275, fill=255, width=9)


def _ak_queda_chao(c: _TelaCamadas) -> None:
    spread = (0.76, 1.00, 1.08, 1.14)[c.f_idx]
    _polilinha(c.df, [(128 - 22 * spread, 178), (128 - 76 * spread, 168), (128 - 108 * spread, 132)], 18)
    _polilinha(c.df, [(128 + 22 * spread, 178), (128 + 76 * spread, 168), (128 + 108 * spread, 132)], 18)
    _polilinha(c.da, [(128 - 106 * spread, 186), (128 + 106 * spread, 186)], 10)
    _desenhar_cubo_iso(c.dh, 128 - 94 * spread, 124, 12)
    _desenhar_cubo_iso(c.dh, 128 + 94 * spread, 124, 12)


def _ak_linhas_queda(c: _TelaCamadas) -> None:
    for i, (lx, w) in enumerate(((42, 7), (78, 11), (128, 14), (178, 11), (214, 7))):
        alvo = c.df if i % 2 == 0 else c.da
        y0 = 16 + ((c.f_idx * 22 + i * 13) % 40)
        _polilinha(alvo, [(lx, y0), (lx, min(244, y0 + 178))], w)
        _polilinha(c.dh, [(lx, y0 + 16), (lx, min(220, y0 + 128))], max(3, w // 3))


def _ak_respingo(c: _TelaCamadas) -> None:
    esc = (0.80, 1.00, 0.94, 0.66)[c.f_idx]
    _desenhar_cubo_iso(c.df, 128, 128, 42 * esc, c.f_idx * 0.4)
    c.da.polygon(_pts_estrela(74, 76, 22, 6, 4), fill=255)
    c.dh.polygon(_pts_estrela(128, 128, 22 * esc, 5 * esc, 4), fill=255)


def _ak_assinatura(c: _TelaCamadas) -> None:
    # Super Aura Ki subindo em línguas afiadas + brilhos cruzados
    sw = (-8, 0, 8, -4)[c.f_idx]
    _polilinha(c.df, [(64, 226), (52 + sw, 140), (88, 96), (76 - sw, 36)], 22)
    _polilinha(c.df, [(128, 232), (118 - sw, 118), (138 + sw, 26)], 24)
    _polilinha(c.df, [(192, 226), (204 - sw, 140), (168, 96), (180 + sw, 36)], 22)
    _desenhar_cubo_iso(c.da, 48, 82, 16, 0.4)
    _desenhar_cubo_iso(c.da, 208, 86, 16, -0.4)
    c.dh.polygon(_pts_estrela(128, 112, 42, 10, 4), fill=255)


# ---------------------------------------------------------------------------
# 4. COLORIDO / STREET GRAFFITI: Coroas Estêncil, Splatters, Wildstyle, Bubble-Tag
# ---------------------------------------------------------------------------


def _gf_coroa(draw: ImageDraw.ImageDraw, cx: float, cy: float, w: float, h: float, tilt: float) -> None:
    ca, sa = math.cos(tilt), math.sin(tilt)
    brutos = (
        (-w * 0.46, h * 0.42), (-w * 0.50, -h * 0.34), (-w * 0.22, h * 0.04),
        (0.0, -h * 0.48), (w * 0.22, h * 0.04), (w * 0.50, -h * 0.34), (w * 0.46, h * 0.42),
    )
    draw.polygon([(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in brutos], fill=255)


def _gf_musica(c: _TelaCamadas) -> None:
    # Bico/lata de spray soltando jato + arcos sonoros wildstyle (distinto da coroa)
    dy = (-4, 0, 4, -2)[c.f_idx]
    c.df.polygon([(46, 170 + dy), (92, 124 + dy), (124, 156 + dy), (78, 202 + dy)], fill=255)
    _hf_seta(c.da, 136, 112 + dy, 28, 0.72)
    c.da.arc((126, 48, 224, 146), -65, 35, fill=255, width=12)
    c.df.arc((148, 34, 240, 132), -60, 30, fill=255, width=10)
    c.dh.ellipse((68, 150 + dy, 92, 174 + dy), fill=255)


def _gf_impacto(c: _TelaCamadas) -> None:
    esc = (0.76, 1.00, 1.06, 0.90)[c.f_idx]
    c.df.polygon(_pts_estrela(128, 128, 102 * esc, 42 * esc, 9, rot=c.f_idx * 0.25, jitter=0.32), fill=255)
    for ang, dist_s in ((0.4, 96), (1.8, 108), (3.4, 94), (5.0, 104)):
        px, py = 128 + math.cos(ang) * dist_s * esc, 128 + math.sin(ang) * dist_s * esc
        c.da.ellipse((px - 14, py - 14, px + 14, py + 14), fill=255)
    c.dh.ellipse((128 - 26 * esc, 128 - 26 * esc, 128 + 26 * esc, 128 + 26 * esc), fill=255)


def _gf_choque(c: _TelaCamadas) -> None:
    # Seta/raio wildstyle com cabeça dupla
    flip = 1.0 if c.f_idx % 2 == 0 else -1.0
    pts = [(54, 198), (112, 134 + 10 * flip), (84, 112), (168, 42), (182, 92)]
    _polilinha(c.df, pts[:-1], 18)
    _hf_seta(c.da, 184, 52, 34, 0.65)
    _polilinha(c.dh, pts[:-1], 6)


def _gf_susto(c: _TelaCamadas) -> None:
    off = (-4, 0, 4, -2)[c.f_idx]
    _desenhar_palavra(c.df, "!", (96 + off, 126), (52, 146), -0.18, 18)
    _desenhar_palavra(c.da, "!", (166 - off, 134), (48, 132), 0.16, 16)
    c.dh.ellipse((78 + off, 66, 92 + off, 88), fill=255)


def _gf_raiva(c: _TelaCamadas) -> None:
    _gf_coroa(c.df, 128, 134, 134, 88, 0.08 * (1 if c.f_idx % 2 == 0 else -1))
    _polilinha(c.da, [(60, 74), (196, 174)], 13)
    _polilinha(c.da, [(196, 74), (60, 174)], 13)
    c.dh.polygon(_pts_estrela(128, 128, 22, 9, 4), fill=255)


def _gf_carinho(c: _TelaCamadas) -> None:
    esc = (4.1, 4.9, 5.1, 4.3)[c.f_idx]
    _desenhar_coracao(c.df, 128, 130, esc)
    c.da.polygon(_pts_estrela(194, 58, 28, 11, 5), fill=255)
    c.dh.arc((74, 72, 124, 122), 190, 275, fill=255, width=11)


def _gf_tontura(c: _TelaCamadas) -> None:
    rot = c.f_idx * (math.pi * 0.25)
    c.da.arc((38, 66, 218, 190), 15 + c.f_idx * 45, 165 + c.f_idx * 45, fill=255, width=14)
    c.da.arc((38, 66, 218, 190), 195 + c.f_idx * 45, 345 + c.f_idx * 45, fill=255, width=14)
    for ang_o in (rot, rot + math.pi):
        _gf_coroa(c.df, 128 + math.cos(ang_o) * 78, 128 + math.sin(ang_o) * 44, 48, 36, ang_o)


def _gf_sono(c: _TelaCamadas) -> None:
    _desenhar_cassete(c.df, c.da, 122, 146, 132, 82, -0.10)
    _desenhar_z(c.da, 186, 62 - c.f_idx * 4, 44, 46, 12)


def _gf_queda_chao(c: _TelaCamadas) -> None:
    spread = (0.78, 1.0, 1.08, 1.14)[c.f_idx]
    for dx, rx, ry in ((-64, 34, 24), (0, 56, 34), (66, 36, 26)):
        c.df.ellipse((128 + dx * spread - rx, 168 - ry, 128 + dx * spread + rx, 168 + ry), fill=255)
    _polilinha(c.da, [(28, 190), (228, 190)], 12)
    c.dh.ellipse((98, 146, 146, 166), fill=255)


def _gf_linhas_queda(c: _TelaCamadas) -> None:
    for i, lx in enumerate((40, 82, 128, 174, 214)):
        alvo = c.df if i % 2 == 0 else c.da
        _polilinha(alvo, [(lx, 24 + i * 6), (lx, 224 - i * 4)], 12)


def _gf_respingo(c: _TelaCamadas) -> None:
    esc = (0.80, 1.00, 0.94, 0.68)[c.f_idx]
    c.df.ellipse((128 - 44 * esc, 128 - 38 * esc, 128 + 44 * esc, 128 + 38 * esc), fill=255)
    c.da.ellipse((166, 158, 198, 190), fill=255)
    c.dh.ellipse((106, 108, 130, 128), fill=255)


def _gf_assinatura(c: _TelaCamadas) -> None:
    esc = (0.80, 1.02, 1.06, 0.90)[c.f_idx]
    _gf_coroa(c.df, 128, 122, 148 * esc, 108 * esc, (-0.16, 0.04, 0.14, -0.06)[c.f_idx])
    c.da.polygon(_pts_estrela(60, 58, 24, 9, 5), fill=255)
    c.da.polygon(_pts_estrela(198, 62, 22, 8, 5), fill=255)
    _polilinha(c.dh, [(74, 146), (182, 146)], 9)


# ---------------------------------------------------------------------------
# 5. LOWPOLY 3D: Cristais, Voxels e Prismas em 3 Planos (2D + Malha 3D Real!)
# ---------------------------------------------------------------------------


def _lp_musica(c: _TelaCamadas) -> None:
    dy = (-4, 0, 4, -2)[c.f_idx]
    _desenhar_cubo_iso(c.df, 78, 184 + dy, 32, 0.52)
    _desenhar_cubo_iso(c.df, 172, 162 - dy * 0.5, 32, 0.52)
    c.df.polygon([(92, 174 + dy), (108, 174 + dy), (108, 60 + dy), (92, 60 + dy)], fill=255)
    c.df.polygon([(186, 152 - dy * 0.5), (202, 152 - dy * 0.5), (202, 42 - dy * 0.5), (186, 42 - dy * 0.5)], fill=255)
    c.da.polygon([(92, 54 + dy), (202, 34 - dy * 0.5), (202, 62 - dy * 0.5), (92, 82 + dy)], fill=255)


def _lp_impacto(c: _TelaCamadas) -> None:
    esc = (0.76, 1.00, 1.05, 0.90)[c.f_idx]
    _desenhar_cubo_iso(c.df, 128, 128, 92 * esc, c.f_idx * 0.35)
    c.da.polygon(_pts_estrela(128, 128, 98 * esc, 38 * esc, 6, rot=c.f_idx * 0.4), fill=255)
    c.dh.polygon(_pts_estrela(128, 128, 44 * esc, 20 * esc, 6, rot=c.f_idx * 0.4), fill=255)


def _lp_choque(c: _TelaCamadas) -> None:
    flip = 1.0 if c.f_idx % 2 == 0 else -1.0
    c.df.polygon([(146 - 12 * flip, 28), (94, 118), (134, 122), (82, 224), (168, 130), (126, 126)], fill=255)
    _desenhar_cubo_iso(c.da, 198, 84, 24, 0.5)
    c.dh.polygon([(136, 52), (108, 110), (126, 112), (104, 166)], fill=255)


def _lp_susto(c: _TelaCamadas) -> None:
    jitter = (-4, 0, 4, -2)[c.f_idx]
    c.df.polygon([(104, 40 + jitter), (152, 40 + jitter), (138, 152 + jitter), (118, 152 + jitter)], fill=255)
    _desenhar_cubo_iso(c.da, 128, 196 + jitter, 24, 0.0)
    c.dh.polygon([(120, 56 + jitter), (134, 56 + jitter), (130, 128 + jitter), (124, 128 + jitter)], fill=255)


def _lp_raiva(c: _TelaCamadas) -> None:
    esc = (0.86, 1.00, 1.08, 0.92)[c.f_idx]
    for dx in (-44, 44):
        c.df.rectangle((128 + dx - 16 * esc, 64, 128 + dx + 16 * esc, 192), fill=255)
    for dy in (-44, 44):
        c.da.rectangle((64, 128 + dy - 16 * esc, 192, 128 + dy + 16 * esc), fill=255)
    _desenhar_cubo_iso(c.dh, 128, 128, 28 * esc, 0.78)


def _lp_carinho(c: _TelaCamadas) -> None:
    esc = (0.86, 1.00, 1.06, 0.92)[c.f_idx]
    pts = ((128, 92), (96, 58), (52, 68), (44, 118), (128, 210), (212, 118), (204, 68), (160, 58))
    c.df.polygon([(128 + (x - 128) * esc, 128 + (y - 128) * esc) for x, y in pts], fill=255)
    _desenhar_cubo_iso(c.da, 198, 56, 18, 0.4)
    c.dh.polygon([(82, 82), (104, 72), (116, 98), (74, 112)], fill=255)


def _lp_tontura(c: _TelaCamadas) -> None:
    rot = c.f_idx * (math.pi * 0.25)
    pts = _pts_estrela(128, 128, 92, 92, 3, rot=rot * 0.5)
    _polilinha(c.da, [*pts, pts[0]], 12)
    for ang_o in (rot, rot + math.pi):
        _desenhar_cubo_iso(c.df, 128 + math.cos(ang_o) * 76, 128 + math.sin(ang_o) * 44, 28, ang_o)


def _lp_sono(c: _TelaCamadas) -> None:
    dy = (-4, 0, 4, 8)[c.f_idx]
    _desenhar_z(c.da, 74, 184 - dy * 0.4, 44, 46, 13)
    _desenhar_z(c.df, 128, 128 - dy * 0.7, 62, 64, 16)
    _desenhar_z(c.df, 182, 68 - dy, 74, 78, 18)


def _lp_queda_chao(c: _TelaCamadas) -> None:
    spread = (0.78, 1.0, 1.08, 1.15)[c.f_idx]
    for dx, ry, r in ((-70, 168, 32), (-24, 152, 42), (24, 150, 44), (70, 166, 32)):
        _desenhar_cubo_iso(c.df, 128 + dx * spread, ry, r, 0.25)
    c.da.rectangle((34, 188, 222, 202), fill=255)


def _lp_linhas_queda(c: _TelaCamadas) -> None:
    for i, lx in enumerate((40, 82, 128, 174, 214)):
        alvo = c.df if i % 2 == 0 else c.da
        alvo.rectangle((lx - 6, 22, lx + 6, 224), fill=255)


def _lp_respingo(c: _TelaCamadas) -> None:
    esc = (0.78, 1.0, 0.96, 0.65)[c.f_idx]
    _desenhar_cubo_iso(c.df, 128, 128, 52 * esc, c.f_idx * 0.3)
    c.dh.polygon([(128, 128 - 28 * esc), (128 + 28 * esc, 128), (128, 128), (128 - 28 * esc, 128)], fill=255)


def _lp_assinatura(c: _TelaCamadas) -> None:
    esc = (0.80, 1.02, 1.06, 0.90)[c.f_idx]
    _desenhar_cubo_iso(c.df, 128, 128, 86 * esc, c.f_idx * 0.45)
    c.da.polygon(_pts_estrela(128, 128, 102 * esc, 42 * esc, 6, rot=c.f_idx * 0.35), fill=255)
    c.dh.polygon([(128, 128 - 54 * esc), (128 + 46 * esc, 128), (128, 128), (128 - 46 * esc, 128)], fill=255)


# ---------------------------------------------------------------------------
# 6. PB ESCURO / MANGÁ SHONEN: Katakana (ドン!, ゴゴゴ, ビリ!), Enso Sumi-e, Shocklines
# ---------------------------------------------------------------------------


def _mg_impacto(c: _TelaCamadas) -> None:
    esc = (0.76, 1.0, 1.04, 0.88)[c.f_idx]
    for k in range(14):
        ang = c.f_idx * 0.18 + k * (math.tau / 14.0)
        _polilinha(c.da, [(128 + math.cos(ang) * 74, 128 + math.sin(ang) * 74), (128 + math.cos(ang) * 118, 128 + math.sin(ang) * 118)], 7)
    _desenhar_palavra(c.df, "ドン!", (128, 128), (168 * esc, 78 * esc), -0.10, 14)
    _desenhar_palavra(c.dh, "ドン!", (128, 128), (164 * esc, 72 * esc), -0.10, 5)


def _mg_musica(c: _TelaCamadas) -> None:
    rot = c.f_idx * 18
    c.df.arc((40, 40, 216, 216), 30 + rot, 325 + rot, fill=255, width=22)
    c.da.arc((64, 64, 192, 192), 60 - rot, 270 - rot, fill=255, width=10)
    c.dh.ellipse((114, 114, 142, 142), fill=255)


def _mg_choque(c: _TelaCamadas) -> None:
    flip = 1.0 if c.f_idx % 2 == 0 else -1.0
    _polilinha(c.df, [(38, 186), (92, 122 + 8 * flip), (124, 140), (196, 52)], 15)
    _desenhar_palavra(c.da, "ビリ!", (128, 128), (168, 74), -0.14 * flip, 11)
    _polilinha(c.dh, [(54, 174), (178, 70)], 5)


def _mg_susto(c: _TelaCamadas) -> None:
    # Clássicas linhas verticais de desespero/choque do mangá (ガーン)
    for idx, x in enumerate((42, 68, 94, 162, 188, 214)):
        top = 24 + ((idx + c.f_idx) % 3) * 14
        _polilinha(c.df if idx % 2 == 0 else c.da, [(x, top), (x, 224)], 11)
    _desenhar_palavra(c.dh, "!", (128, 126), (48, 134), 0.0, 14)


def _mg_raiva(c: _TelaCamadas) -> None:
    # Icônico ゴゴゴ (Menacing / JoJo!)
    dy = (-6, 0, 6, -3)[c.f_idx]
    _desenhar_palavra(c.df, "ゴ", (74, 166 + dy), (68, 68), -0.16, 12)
    _desenhar_palavra(c.df, "ゴ", (128, 118 - dy * 0.5), (76, 76), -0.14, 13)
    _desenhar_palavra(c.da, "ゴ", (184, 70 + dy), (84, 84), -0.12, 14)


def _mg_carinho(c: _TelaCamadas) -> None:
    rot = c.f_idx * 0.14
    for ang in (0, math.pi * 0.5, math.pi, math.pi * 1.5):
        px, py = 128 + math.cos(ang + rot) * 34, 128 + math.sin(ang + rot) * 34
        c.df.ellipse((px - 34, py - 34, px + 34, py + 34), fill=255)
    c.dh.polygon(_pts_estrela(128, 128, 44, 10, 4, rot=rot), fill=255)
    c.da.polygon(_pts_estrela(194, 62, 24, 6, 4), fill=255)


def _mg_tontura(c: _TelaCamadas) -> None:
    pts: list[tuple[float, float]] = []
    for k in range(36):
        ang = k * 0.45 + c.f_idx * 0.8
        r = 12 + k * 2.5
        pts.append((128 + math.cos(ang) * r, 128 + math.sin(ang) * r * 0.72))
    _polilinha(c.df, pts, 11)
    c.dh.polygon(_pts_estrela(198, 86, 20, 7, 4), fill=255)


def _mg_sono(c: _TelaCamadas) -> None:
    dy = (-4, 0, 4, 6)[c.f_idx]
    c.da.ellipse((54, 118 - dy * 0.3, 186, 206 - dy * 0.3), fill=255)
    _desenhar_z(c.df, 128, 128 - dy * 0.6, 56, 60, 14)
    _desenhar_z(c.dh, 182, 68 - dy, 66, 70, 14)


def _mg_queda_chao(c: _TelaCamadas) -> None:
    spread = (0.78, 1.0, 1.08, 1.14)[c.f_idx]
    _polilinha(c.df, [(128 - 114 * spread, 178), (128 - 54 * spread, 146), (128, 166), (128 + 54 * spread, 146), (128 + 114 * spread, 178)], 22)
    _polilinha(c.da, [(38, 198), (218, 198)], 11)


def _mg_linhas_queda(c: _TelaCamadas) -> None:
    for i, lx in enumerate((38, 76, 128, 178, 216)):
        _polilinha(c.df if i % 2 == 0 else c.da, [(lx, 18), (lx, 236)], 11)


def _mg_respingo(c: _TelaCamadas) -> None:
    esc = (0.80, 1.0, 0.94, 0.66)[c.f_idx]
    c.df.polygon(_pts_estrela(128, 128, 58 * esc, 18 * esc, 5, rot=c.f_idx * 0.3), fill=255)
    c.dh.ellipse((116, 116, 140, 140), fill=255)


def _mg_assinatura(c: _TelaCamadas) -> None:
    # Shūchūsen circular com corte diagonal e estrela mangá branca no centro
    rot = c.f_idx * 0.22
    for k in range(16):
        ang = rot + k * (math.tau / 16.0)
        r0 = 62.0 if k % 2 == 0 else 76.0
        _polilinha(c.da, [(128 + math.cos(ang) * r0, 128 + math.sin(ang) * r0), (128 + math.cos(ang) * 118, 128 + math.sin(ang) * 118)], 7)
    _polilinha(c.df, [(34, 196), (128, 118), (222, 60)], 24)
    c.dh.polygon(_pts_estrela(128, 128, 52, 14, 4, rot=rot), fill=255)


# ---------------------------------------------------------------------------
# 7. PB CLARO / CADERNO VIVO (SKETCHBOOK DOODLE): Cassete, Lâmpada, Novelo, Aviãozinho
# ---------------------------------------------------------------------------


def _sk_musica(c: _TelaCamadas) -> None:
    _desenhar_cassete(c.df, c.da, 128, 132, 152, 92, (-0.10, -0.04, 0.08, -0.02)[c.f_idx])
    _polilinha(c.dh, [(52, 56), (92, 34), (144, 52), (192, 28)], 7)


def _sk_impacto(c: _TelaCamadas) -> None:
    esc = (0.76, 1.00, 1.06, 0.90)[c.f_idx]
    pts = _pts_estrela(128, 128, 96 * esc, 52 * esc, 8, rot=c.f_idx * 0.18, jitter=0.18)
    _polilinha(c.df, [*pts, pts[0]], 12)
    for k in range(4):
        ang = k * math.pi * 0.5 + 0.4
        _hf_seta(c.da, 128 + math.cos(ang) * 86 * esc, 128 + math.sin(ang) * 86 * esc, 20, ang + math.pi * 0.5)
    c.dh.polygon(_pts_estrela(128, 128, 36 * esc, 16 * esc, 5), fill=255)


def _sk_choque(c: _TelaCamadas) -> None:
    # Mola em zigue-zague / bobina rabiscada à mão
    flip = 1.0 if c.f_idx % 2 == 0 else -1.0
    pts = [(62 + (46 if k % 2 else -46) * flip, 36 + k * 30) for k in range(7)]
    _polilinha(c.df, [(128 + x - 62, y) for x, y in pts], 12)
    c.da.polygon(_pts_estrela(194, 72, 20, 7, 4), fill=255)
    c.dh.polygon(_pts_estrela(60, 184, 18, 6, 4), fill=255)


def _sk_susto(c: _TelaCamadas) -> None:
    # Lâmpada rabiscada + raios de ideia/susto
    esc = (0.88, 1.02, 1.04, 0.92)[c.f_idx]
    c.df.ellipse((128 - 54 * esc, 114 - 54 * esc, 128 + 54 * esc, 114 + 54 * esc), fill=255)
    c.da.rectangle((106, 162, 150, 198), fill=255)
    for ang_d in (-145, -110, -70, -35):
        r = math.radians(ang_d)
        _polilinha(c.df, [(128 + math.cos(r) * 76, 114 + math.sin(r) * 76), (128 + math.cos(r) * 108, 114 + math.sin(r) * 108)], 9)
    _desenhar_palavra(c.dh, "!", (128, 112), (34, 62), 0.0, 9)


def _sk_raiva(c: _TelaCamadas) -> None:
    # Icônico novelo de rabisco furioso (tangled scribble)
    pts = [
        (
            128 + math.cos(k * 0.72 + c.f_idx * 0.5) * (32 + 54 * abs(math.sin(k * 1.15))),
            128 + math.sin(k * 0.95 + c.f_idx * 0.4) * (32 + 54 * abs(math.cos(k * 0.85))),
        )
        for k in range(18)
    ]
    _polilinha(c.df, pts, 11)


def _sk_carinho(c: _TelaCamadas) -> None:
    esc = (4.0, 4.7, 4.9, 4.3)[c.f_idx]
    _desenhar_coracao(c.df, 128, 134, esc)
    c.da.polygon(_pts_estrela(64, 62, 22, 9, 5), fill=255)
    c.da.polygon(_pts_estrela(194, 66, 20, 8, 5), fill=255)


def _sk_tontura(c: _TelaCamadas) -> None:
    _mg_tontura(c)


def _sk_sono(c: _TelaCamadas) -> None:
    # Lua crescente + estrelas rabiscadas
    rot = (-0.1, 0.0, 0.1, -0.05)[c.f_idx]
    pts: list[tuple[float, float]] = []
    for k in range(18):
        ang = math.radians(-115 + k * (230 / 17.0)) + rot
        pts.append((124 + math.cos(ang) * 74, 128 + math.sin(ang) * 74))
    for k in range(17, -1, -1):
        ang = math.radians(-115 + k * (230 / 17.0)) + rot
        pts.append((150 + math.cos(ang) * 52, 124 + math.sin(ang) * 52))
    c.df.polygon(pts, fill=255)
    _desenhar_z(c.da, 188, 66 - c.f_idx * 4, 42, 44, 11)
    c.dh.polygon(_pts_estrela(64, 70, 18, 7, 5), fill=255)


def _sk_queda_chao(c: _TelaCamadas) -> None:
    spread = (0.78, 1.0, 1.06, 1.12)[c.f_idx]
    for dx, ry, r in ((-68, 166, 32), (-20, 152, 42), (32, 152, 44), (72, 166, 32)):
        cx = 128 + dx * spread
        c.df.arc((cx - r, ry - r * 0.75, cx + r, ry + r * 0.75), 180, 360, fill=255, width=12)
    _polilinha(c.da, [(32, 188), (224, 188)], 9)


def _sk_linhas_queda(c: _TelaCamadas) -> None:
    for i, lx in enumerate((44, 86, 128, 170, 212)):
        _polilinha(c.df, [(lx, 24 + (i % 2) * 16), (lx, 216)], 8)


def _sk_respingo(c: _TelaCamadas) -> None:
    esc = (0.80, 1.0, 0.94, 0.66)[c.f_idx]
    pts = _pts_estrela(128, 128, 52 * esc, 18 * esc, 5, rot=c.f_idx * 0.2)
    _polilinha(c.df, [*pts, pts[0]], 9)


def _sk_assinatura(c: _TelaCamadas) -> None:
    # Aviãozinho de papel rabiscado voando em loop!
    dy = (-6, 0, 6, 0)[c.f_idx]
    c.df.polygon([(48, 154 + dy), (212, 74 + dy), (128, 182 + dy)], fill=255)
    c.da.polygon([(48, 154 + dy), (212, 74 + dy), (104, 128 + dy)], fill=255)
    _polilinha(c.df, [(26, 206), (62, 186), (92, 198)], 8)
    c.dh.polygon(_pts_estrela(202, 54, 18, 7, 4), fill=255)


_TABELA_FORMAS: dict[str, dict[str, Callable[[_TelaCamadas], None]]] = {
    "spider_verse": {
        "impacto": _sv_impacto, "musica": _sv_musica, "choque": _sv_choque, "susto": _sv_susto,
        "raiva": _sv_raiva, "carinho": _sv_carinho, "tontura": _sv_tontura, "sono": _sv_sono,
        "queda_chao": _sv_queda_chao, "linhas_queda": _sv_linhas_queda, "respingo": _sv_respingo, "assinatura": _sv_assinatura,
    },
    "hifi_rush": {
        "impacto": _hf_impacto, "musica": _hf_musica, "choque": _hf_choque, "susto": _hf_susto,
        "raiva": _hf_raiva, "carinho": _hf_carinho, "tontura": _hf_tontura, "sono": _hf_sono,
        "queda_chao": _hf_queda_chao, "linhas_queda": _hf_linhas_queda, "respingo": _hf_respingo, "assinatura": _hf_assinatura,
    },
    "anime_sakuga": {
        "impacto": _ak_impacto, "musica": _ak_musica, "choque": _ak_choque, "susto": _ak_susto,
        "raiva": _ak_raiva, "carinho": _ak_carinho, "tontura": _ak_tontura, "sono": _ak_sono,
        "queda_chao": _ak_queda_chao, "linhas_queda": _ak_linhas_queda, "respingo": _ak_respingo, "assinatura": _ak_assinatura,
    },
    "colorido": {
        "impacto": _gf_impacto, "musica": _gf_musica, "choque": _gf_choque, "susto": _gf_susto,
        "raiva": _gf_raiva, "carinho": _gf_carinho, "tontura": _gf_tontura, "sono": _gf_sono,
        "queda_chao": _gf_queda_chao, "linhas_queda": _gf_linhas_queda, "respingo": _gf_respingo, "assinatura": _gf_assinatura,
    },
    "lowpoly_3d": {
        "impacto": _lp_impacto, "musica": _lp_musica, "choque": _lp_choque, "susto": _lp_susto,
        "raiva": _lp_raiva, "carinho": _lp_carinho, "tontura": _lp_tontura, "sono": _lp_sono,
        "queda_chao": _lp_queda_chao, "linhas_queda": _lp_linhas_queda, "respingo": _lp_respingo, "assinatura": _lp_assinatura,
    },
    "pb_escuro": {
        "impacto": _mg_impacto, "musica": _mg_musica, "choque": _mg_choque, "susto": _mg_susto,
        "raiva": _mg_raiva, "carinho": _mg_carinho, "tontura": _mg_tontura, "sono": _mg_sono,
        "queda_chao": _mg_queda_chao, "linhas_queda": _mg_linhas_queda, "respingo": _mg_respingo, "assinatura": _mg_assinatura,
    },
    "pb_claro": {
        "impacto": _sk_impacto, "musica": _sk_musica, "choque": _sk_choque, "susto": _sk_susto,
        "raiva": _sk_raiva, "carinho": _sk_carinho, "tontura": _sk_tontura, "sono": _sk_sono,
        "queda_chao": _sk_queda_chao, "linhas_queda": _sk_linhas_queda, "respingo": _sk_respingo, "assinatura": _sk_assinatura,
    },
}


def _benday_pontos(passo: float = 17.5) -> np.ndarray:
    u = (_XX + _YY) * 0.70710678
    v = (_YY - _XX) * 0.70710678
    du = np.mod(u, passo) - passo * 0.5
    dv = np.mod(v, passo) - passo * 0.5
    dist = np.hypot(du, dv)
    grad = np.clip((_XX + _YY - 120.0) / 210.0, 0.20, 0.95)
    return dist <= (passo * 0.43) * grad


def _reticula_manga() -> np.ndarray:
    return (np.mod((_XX + _YY).astype(np.int32), 11)) < 4


def _grao_giz() -> np.ndarray:
    h = np.sin(_XX * 12.9898 + _YY * 78.233) * 43758.5453
    return (h - np.floor(h)) > 0.22


_MASKS_ESTILO_BEN = _benday_pontos()
_MASK_MANGA = _reticula_manga()
_MASK_GIZ = _grao_giz()


def _pintar(rgba: np.ndarray, mask: np.ndarray, rgb: tuple[int, int, int]) -> None:
    if np.any(mask):
        rgba[mask, 0] = rgb[0]
        rgba[mask, 1] = rgb[1]
        rgba[mask, 2] = rgb[2]
        rgba[mask, 3] = 255


def _compor_spider_verse(
    fill: np.ndarray, acc: np.ndarray, hi: np.ndarray, cor_a: tuple[int, int, int], cor_b: tuple[int, int, int], f_idx: int
) -> np.ndarray:
    rgba = np.zeros((TAMANHO_QUADRO, TAMANHO_QUADRO, 4), dtype=np.uint8)
    uniao = fill | acc | hi
    tinta = _dilatar(uniao, 7)
    off = 6 if f_idx % 2 == 0 else 8
    _pintar(rgba, _deslocar(tinta, -off, -max(4, off - 2)) & ~tinta, (0, 232, 255))
    _pintar(rgba, _deslocar(tinta, off, max(4, off - 2)) & ~tinta, (255, 36, 68))
    _pintar(rgba, tinta, (14, 14, 22))
    _pintar(rgba, fill, cor_a)
    _pintar(rgba, fill & _MASKS_ESTILO_BEN, (20, 18, 28) if cor_a[0] > 200 and cor_a[1] > 180 else (255, 226, 28))
    _pintar(rgba, acc, cor_b)
    _pintar(rgba, acc & _MASKS_ESTILO_BEN, (14, 14, 22))
    _pintar(rgba, hi, (250, 248, 242))
    return rgba


def _compor_hifi_rush(
    fill: np.ndarray, acc: np.ndarray, hi: np.ndarray, cor_a: tuple[int, int, int], cor_b: tuple[int, int, int]
) -> np.ndarray:
    rgba = np.zeros((TAMANHO_QUADRO, TAMANHO_QUADRO, 4), dtype=np.uint8)
    uniao = fill | acc | hi
    tinta = _dilatar(uniao, 6)
    _pintar(rgba, _deslocar(tinta, 5, 5) & ~tinta, (28, 22, 36))
    _pintar(rgba, tinta, (12, 12, 18))
    _pintar(rgba, fill, cor_a)
    corte_sombra = fill & ((_XX + _YY) > 276.0)
    _pintar(rgba, corte_sombra, (max(12, int(cor_a[0] * 0.72)), max(12, int(cor_a[1] * 0.68)), max(16, int(cor_a[2] * 0.75))))
    _pintar(rgba, acc, cor_b)
    _pintar(rgba, hi, (252, 252, 250))
    return rgba


def _compor_anime_sakuga(
    fill: np.ndarray, acc: np.ndarray, hi: np.ndarray, cor_a: tuple[int, int, int], cor_b: tuple[int, int, int]
) -> np.ndarray:
    rgba = np.zeros((TAMANHO_QUADRO, TAMANHO_QUADRO, 4), dtype=np.uint8)
    uniao = fill | acc | hi
    _pintar(rgba, _dilatar(uniao, 8), cor_b)
    _pintar(rgba, _dilatar(fill, 4), cor_a)
    _pintar(rgba, fill, (252, 254, 255))
    _pintar(rgba, acc & ~fill, cor_a)
    _pintar(rgba, hi, (255, 255, 255))
    return rgba


def _compor_colorido_grafite(
    fill: np.ndarray, acc: np.ndarray, hi: np.ndarray, cor_a: tuple[int, int, int], cor_b: tuple[int, int, int], f_idx: int
) -> np.ndarray:
    rgba = np.zeros((TAMANHO_QUADRO, TAMANHO_QUADRO, 4), dtype=np.uint8)
    uniao = fill | acc | hi
    anel_spray = _dilatar(uniao, 18) & ~_dilatar(uniao, 7)
    ruido_spray = np.sin(_XX * (17.3 + f_idx) + _YY * 41.7) * 9123.7
    nevoa = anel_spray & ((ruido_spray - np.floor(ruido_spray)) > 0.84) & ((_XX.astype(int) + _YY.astype(int)) % 3 == 0)
    escorrido = (_deslocar(fill, 0, 12) | _deslocar(fill, 0, 22)) & ((np.mod(_XX.astype(int) + 7, 37)) < 7) & (_YY > 150) & ~uniao
    tinta = _dilatar(uniao | escorrido, 6)
    _pintar(rgba, nevoa, cor_b)
    _pintar(rgba, tinta, (14, 16, 22))
    _pintar(rgba, fill | escorrido, cor_a)
    _pintar(rgba, acc, cor_b)
    _pintar(rgba, hi, (248, 252, 240))
    return rgba


def _compor_lowpoly_3d(
    fill: np.ndarray, acc: np.ndarray, hi: np.ndarray, cor_a: tuple[int, int, int], cor_b: tuple[int, int, int]
) -> np.ndarray:
    rgba = np.zeros((TAMANHO_QUADRO, TAMANHO_QUADRO, 4), dtype=np.uint8)
    uniao = fill | acc | hi
    extrude = _deslocar(uniao, 9, 10)
    _pintar(rgba, _dilatar(uniao | extrude, 4), (18, 22, 34))
    escuro = (max(12, int(cor_a[0] * 0.45)), max(12, int(cor_a[1] * 0.45)), max(12, int(cor_a[2] * 0.45)))
    medio = (max(16, int(cor_a[0] * 0.78)), max(16, int(cor_a[1] * 0.78)), max(16, int(cor_a[2] * 0.78)))
    claro = (min(255, int(cor_a[0] * 1.12)), min(255, int(cor_a[1] * 1.12)), min(255, int(cor_a[2] * 1.12)))
    _pintar(rgba, extrude & ~uniao, escuro)
    _pintar(rgba, fill, claro)
    _pintar(rgba, fill & (_XX > 128), medio)
    _pintar(rgba, fill & (_YY > 138) & (_XX > 106), escuro)
    _pintar(rgba, acc, cor_b)
    _pintar(rgba, hi, (248, 250, 255))
    return rgba


def _compor_pb_escuro_manga(fill: np.ndarray, acc: np.ndarray, hi: np.ndarray) -> np.ndarray:
    rgba = np.zeros((TAMANHO_QUADRO, TAMANHO_QUADRO, 4), dtype=np.uint8)
    uniao = fill | acc | hi
    _pintar(rgba, _dilatar(uniao, 9), (244, 244, 240))
    _pintar(rgba, _dilatar(uniao, 5), (14, 14, 18))
    _pintar(rgba, fill, (244, 244, 240))
    _pintar(rgba, fill & _MASK_MANGA & ((_XX + _YY) > 220), (24, 24, 30))
    _pintar(rgba, acc, (24, 24, 30))
    _pintar(rgba, acc & _MASK_MANGA, (236, 236, 232))
    _pintar(rgba, hi, (252, 252, 248))
    return rgba


def _compor_pb_claro_giz(fill: np.ndarray, acc: np.ndarray, hi: np.ndarray) -> np.ndarray:
    rgba = np.zeros((TAMANHO_QUADRO, TAMANHO_QUADRO, 4), dtype=np.uint8)
    uniao = fill | acc | hi
    _pintar(rgba, _dilatar(uniao, 4), (22, 24, 30))
    _pintar(rgba, (fill | acc) & _MASK_GIZ, (242, 240, 232))
    _pintar(rgba, hi, (252, 252, 248))
    return rgba


def _proteger_chroma(rgba: np.ndarray, colorkey_hex: str) -> None:
    mask = rgba[..., 3] >= 128
    if not np.any(mask):
        return
    cfg = derivar_chroma(colorkey_hex)
    kr, kg, kb = (round(c * 214) for c in cfg.rgb)
    r, g, b = rgba[..., 0].astype(np.int32), rgba[..., 1].astype(np.int32), rgba[..., 2].astype(np.int32)
    dist_sq = (r - kr) ** 2 + (g - kg) ** 2 + (b - kb) ** 2
    lim = cfg.limites
    in_bounds = (r >= lim[0][0]) & (r <= lim[0][1]) & (g >= lim[1][0]) & (g <= lim[1][1]) & (b >= lim[2][0]) & (b <= lim[2][1])
    risco = mask & ((dist_sq < 28 * 28) | in_bounds)
    if np.any(risco):
        ys, xs = np.nonzero(risco)
        for y, x in zip(ys.tolist(), xs.tolist(), strict=True):
            rr, gg, bb = seguro_contra_chroma_255(int(rgba[y, x, 0]), int(rgba[y, x, 1]), int(rgba[y, x, 2]), colorkey_hex)
            rgba[y, x, 0], rgba[y, x, 1], rgba[y, x, 2] = rr, gg, bb


def _camadas_do_estilo(nome: str, paleta: str, f_idx: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    tabela = _TABELA_FORMAS.get(paleta, _TABELA_FORMAS["pb_escuro"])
    fn = tabela.get(nome, tabela["respingo"])
    tela = _nova_tela(f_idx)
    fn(tela)
    return (
        np.asarray(tela.im_fill, dtype=np.uint8) >= 128,
        np.asarray(tela.im_acc, dtype=np.uint8) >= 128,
        np.asarray(tela.im_hi, dtype=np.uint8) >= 128,
    )


def construir_quadros_estilo_rgba(
    nome: str,
    paleta: str,
    colorkey_hex: str = CHROMA_HEX_PADRAO,
) -> list[np.ndarray]:
    """Gera 4 matrizes RGBA (256x256, uint8) distintas e originais para ``(nome, paleta)``."""
    cores_mapa = _CORES_BASE_ESTILO.get(paleta, {})
    cor_a, cor_b = cores_mapa.get(nome, ((255, 224, 24), (0, 232, 255)))
    cor_a = seguro_contra_chroma_255(*cor_a, colorkey_hex)
    cor_b = seguro_contra_chroma_255(*cor_b, colorkey_hex)

    quadros: list[np.ndarray] = []
    for f_idx in range(QUADROS_POR_EFEITO):
        fill, acc, hi = _camadas_do_estilo(nome, paleta, f_idx)
        if paleta == "spider_verse":
            rgba = _compor_spider_verse(fill, acc, hi, cor_a, cor_b, f_idx)
        elif paleta == "hifi_rush":
            rgba = _compor_hifi_rush(fill, acc, hi, cor_a, cor_b)
        elif paleta == "anime_sakuga":
            rgba = _compor_anime_sakuga(fill, acc, hi, cor_a, cor_b)
        elif paleta == "colorido":
            rgba = _compor_colorido_grafite(fill, acc, hi, cor_a, cor_b, f_idx)
        elif paleta == "lowpoly_3d":
            rgba = _compor_lowpoly_3d(fill, acc, hi, cor_a, cor_b)
        elif paleta == "pb_claro":
            rgba = _compor_pb_claro_giz(fill, acc, hi)
        else:
            rgba = _compor_pb_escuro_manga(fill, acc, hi)
        _proteger_chroma(rgba, colorkey_hex)
        quadros.append(rgba)
    return quadros


def construir_banco_estilo_vfx(
    paleta: str,
    *,
    nomes: tuple[str, ...],
    colorkey_hex: str = CHROMA_HEX_PADRAO,
) -> dict[str, tuple[Texture, ...]]:
    """Constrói todas as texturas Panda3D ``256x256`` RGBA da paleta solicitada."""
    banco: dict[str, tuple[Texture, ...]] = {}
    for nome in nomes:
        quadros_rgba = construir_quadros_estilo_rgba(nome, paleta, colorkey_hex=colorkey_hex)
        texturas: list[Texture] = []
        for idx, rgba in enumerate(quadros_rgba):
            tex = Texture(f"vfx-{paleta}-{nome}-{idx}")
            tex.setup2dTexture(TAMANHO_QUADRO, TAMANHO_QUADRO, Texture.TUnsignedByte, Texture.FRgba)
            tex.setRamImageAs(np.ascontiguousarray(rgba[::-1]).tobytes(), "RGBA")
            tex.setWrapU(Texture.WMClamp)
            tex.setWrapV(Texture.WMClamp)
            tex.setMinfilter(Texture.FTNearest)
            tex.setMagfilter(Texture.FTNearest)
            texturas.append(tex)
        banco[nome] = tuple(texturas)
    return banco


__all__: tuple[str, ...] = (
    "PERFIS_MOVIMENTO_VFX",
    "construir_banco_estilo_vfx",
    "construir_quadros_estilo_rgba",
)
