"""Carregamento e cartões 2D dos oito efeitos de grafite em folha 2x2 RGBA."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from panda3d.core import (
    AlphaTestAttrib,
    CardMaker,
    PNMImage,
    StringStream,
    Texture,
    TransparencyAttrib,
)

from sejoga.nucleo.recursos import assets_dir

FOLHAS_VFX_GRAFITE: tuple[str, ...] = (
    "derrapagem",
    "estouro_fone",
    "choque_argolas",
    "pouso",
    "batida",
    "gosma",
    "susto",
    "comemoracao",
)

_ORDEM_QUADRANTES: tuple[tuple[int, int], ...] = (
    (0, 0),
    (1, 0),
    (0, 1),
    (1, 1),
)
_ALPHA_CORTE = 96


@dataclass(frozen=True, slots=True)
class SequenciaGrafite:
    """Quatro quadros RGBA fatiados de uma folha 2x2 de ``vfx_grafite``."""

    nome: str
    frames: tuple[Texture, ...]
    largura: int
    altura: int
    aspecto: float


def _dilatar_rgb_borda(rgba, passos: int = 2):
    """Espalha RGB opaco para vizinhos transparentes, evitando halo no filtro linear."""
    import numpy as np

    out = rgba.copy()
    mask = out[..., 3] >= _ALPHA_CORTE
    rgb = out[..., :3]
    for _ in range(passos):
        novo_rgb = rgb.copy()
        nova_mask = mask.copy()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            sy0 = max(0, -dy)
            sy1 = rgb.shape[0] - max(0, dy)
            sx0 = max(0, -dx)
            sx1 = rgb.shape[1] - max(0, dx)
            dy0 = max(0, dy)
            dy1 = rgb.shape[0] - max(0, -dy)
            dx0 = max(0, dx)
            dx1 = rgb.shape[1] - max(0, -dx)
            preencher = (~nova_mask[dy0:dy1, dx0:dx1]) & mask[sy0:sy1, sx0:sx1]
            if np.any(preencher):
                destino = novo_rgb[dy0:dy1, dx0:dx1]
                origem = rgb[sy0:sy1, sx0:sx1]
                destino[preencher] = origem[preencher]
                nova_mask[dy0:dy1, dx0:dx1] |= preencher
        rgb = novo_rgb
        mask = nova_mask
    out[..., :3] = rgb
    return out


def _limpar_quadro_para_croma(quad):
    """Prepara RGBA contra halo preto, despill de rosa e colorkey RGB(214,0,214)."""
    limpo = _dilatar_rgb_borda(quad, passos=2)
    alpha = limpo[..., 3]
    opacos = alpha >= _ALPHA_CORTE
    alpha[opacos] = 255
    alpha[~opacos] = 0
    near_key = opacos & (limpo[..., 0] > 140) & (limpo[..., 2] > 140) & (limpo[..., 1] < 62)
    limpo[..., 1][near_key] = 62
    return limpo


def _configurar_textura_grafite(tex: Texture) -> Texture:
    tex.setMinfilter(Texture.FTLinear)
    tex.setMagfilter(Texture.FTLinear)
    tex.setWrapU(Texture.WMClamp)
    tex.setWrapV(Texture.WMClamp)
    return tex


def _fatiar_com_numpy(nome: str, caminho) -> tuple[tuple[Texture, ...], int, int]:
    import numpy as np
    from PIL import Image

    with Image.open(caminho) as im:
        rgba = np.asarray(im.convert("RGBA"), dtype=np.uint8)
    alt, larg = rgba.shape[:2]
    qw, qh = larg // 2, alt // 2
    frames: list[Texture] = []
    for col, row in _ORDEM_QUADRANTES:
        fatia = rgba[row * qh : (row + 1) * qh, col * qw : (col + 1) * qw]
        limpa = _limpar_quadro_para_croma(fatia)
        tex = Texture(f"fx-grafite-{nome}-{row * 2 + col}")
        tex.setup2dTexture(qw, qh, Texture.TUnsignedByte, Texture.FSrgbAlpha)
        tex.setRamImageAs(np.ascontiguousarray(limpa[::-1]).tobytes(), "RGBA")
        frames.append(_configurar_textura_grafite(tex))
    return tuple(frames), qw, qh


def _fatiar_com_pnm(nome: str, caminho) -> tuple[tuple[Texture, ...], int, int]:
    sheet = PNMImage()
    if not sheet.read(StringStream(caminho.read_bytes()), caminho.name):
        raise ValueError(f"Folha de VFX inválida: {caminho}")
    qw, qh = sheet.getXSize() // 2, sheet.getYSize() // 2
    frames: list[Texture] = []
    for col, row in _ORDEM_QUADRANTES:
        quad = PNMImage(qw, qh, 4)
        quad.addAlpha()
        quad.copySubImage(sheet, 0, 0, col * qw, row * qh, qw, qh)
        tex = Texture(f"fx-grafite-{nome}-{row * 2 + col}")
        tex.load(quad)
        tex.setFormat(Texture.FSrgbAlpha)
        frames.append(_configurar_textura_grafite(tex))
    return tuple(frames), qw, qh


@cache
def carregar_sequencia_grafite(nome: str) -> SequenciaGrafite:
    """Carrega e fatia uma folha 2x2 de ``assets/textures/vfx_grafite`` em 4 quadros."""
    caminho = assets_dir() / "textures" / "vfx_grafite" / f"{nome}.png"
    if not caminho.is_file():
        raise FileNotFoundError(f"Folha de efeito grafite ausente: {caminho}")
    try:
        frames, qw, qh = _fatiar_com_numpy(nome, caminho)
    except ImportError:
        frames, qw, qh = _fatiar_com_pnm(nome, caminho)
    return SequenciaGrafite(
        nome=nome,
        frames=frames,
        largura=qw,
        altura=qh,
        aspecto=float(qw) / max(1.0, float(qh)),
    )


def carregar_banco_grafite() -> dict[str, SequenciaGrafite]:
    """Carrega as oito sequências oficiais em ``vfx_grafite``."""
    return {nome: carregar_sequencia_grafite(nome) for nome in FOLHAS_VFX_GRAFITE}


def cartao_grafite(parent, name: str, sequencia: SequenciaGrafite):
    """Cria cartão XZ para sprite de grafite sem blending/despill magenta."""
    card = CardMaker(name)
    maior = float(max(1, sequencia.largura, sequencia.altura))
    hx = 0.5 * (sequencia.largura / maior)
    hz = 0.5 * (sequencia.altura / maior)
    card.setFrame(-hx, hx, -hz, hz)
    node = parent.attachNewNode(card.generate())
    node.setTexture(sequencia.frames[0])
    node.setTwoSided(True)
    node.setLightOff(1)
    node.setShaderOff(1)
    node.setTransparency(TransparencyAttrib.MNone)
    node.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MGreater, 0.48))
    node.setDepthWrite(False)
    node.setBin("transparent", 0)
    node.setCollideMask(0)
    return node
