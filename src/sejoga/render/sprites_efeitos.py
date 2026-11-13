"""Cartões pixelados para efeitos no cenário e nos tentáculos."""

from functools import cache

from panda3d.core import (
    AlphaTestAttrib,
    CardMaker,
    PNMImage,
    StringStream,
    Texture,
    TextureStage,
    TransparencyAttrib,
)

from sejoga.nucleo.recursos import assets_dir


@cache
def atlas_gosma():
    """Carrega o atlas RGBA de quatro linhas por quatro colunas."""
    path = assets_dir() / "textures" / "pink_slime_atlas.png"
    image = PNMImage()
    if not image.read(StringStream(path.read_bytes()), path.name):
        raise ValueError(f"Atlas de gosma inválido: {path}")
    texture = textura_pixel("pink-slime-atlas", image)
    texture.setFormat(Texture.FSrgbAlpha)
    return texture


def textura_pixel(name, image):
    """Preserva os pixels da textura ao ampliar o cartão."""
    texture = Texture(name)
    texture.load(image)
    texture.setMinfilter(Texture.FTNearest)
    texture.setMagfilter(Texture.FTNearest)
    return texture


def cartao_pixel(parent, name, texture):
    """Cria um cartão no plano XZ, com transparência e sem hit-test."""
    card = CardMaker(name)
    card.setFrame(-0.5, 0.5, -0.5, 0.5)
    node = parent.attachNewNode(card.generate())
    node.setTexture(texture)
    node.setTwoSided(True)
    node.setLightOff(1)
    node.setShaderOff(1)
    node.setTransparency(TransparencyAttrib.MAlpha)
    node.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MGreater, 0.14))
    node.setCollideMask(0)
    return node


def quadro_gosma(node, linha, coluna):
    """Seleciona um sprite sem interpolar células adjacentes."""
    stage = TextureStage.getDefault()
    node.setTexScale(stage, 0.25, 0.25)
    node.setTexOffset(stage, coluna * 0.25, (3 - linha) * 0.25)
