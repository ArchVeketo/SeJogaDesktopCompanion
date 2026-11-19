"""Cartões pixelados para efeitos no cenário e nos tentáculos."""

from functools import cache

from panda3d.core import (
    AlphaTestAttrib,
    CardMaker,
    PNMImage,
    Shader,
    StringStream,
    Texture,
    TextureStage,
    TransparencyAttrib,
)

from sejoga.nucleo.recursos import assets_dir

_SHADER_BAYER_VERT = """#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_TextureMatrix[1];
in vec4 p3d_Vertex;
in vec4 p3d_MultiTexCoord0;
out vec2 uv;
void main() {
    uv = (p3d_TextureMatrix[0] * p3d_MultiTexCoord0).xy;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
"""

_SHADER_BAYER_FRAG = """#version 130
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform float u_fade;
in vec2 uv;
out vec4 fragColor;
float _sj_bayer(vec2 p) {
    vec2 m = floor(mod(p, 4.0));
    int i = int(m.x) + int(m.y) * 4;
    const float tbl[16] = float[16](
        0.0/16.0,  8.0/16.0,  2.0/16.0, 10.0/16.0,
       12.0/16.0,  4.0/16.0, 14.0/16.0,  6.0/16.0,
        3.0/16.0, 11.0/16.0,  1.0/16.0,  9.0/16.0,
       15.0/16.0,  7.0/16.0, 13.0/16.0,  5.0/16.0
    );
    return tbl[i];
}
void main() {
    vec4 tex = texture(p3d_Texture0, uv);
    float op = tex.a * p3d_ColorScale.a * clamp(u_fade, 0.0, 1.0);
    if (op < 0.14) discard;
    if (op < 0.99 && _sj_bayer(gl_FragCoord.xy) >= op) discard;
    vec3 rgb = tex.rgb * p3d_ColorScale.rgb;
    // Proteção anti-colorkey: evita qualquer pixel próximo do magenta (214, 0, 214).
    if (rgb.r > 0.68 && rgb.b > 0.68 && rgb.g < 0.26) {
        rgb.g = 0.28;
    }
    fragColor = vec4(rgb, 1.0);
}
"""


@cache
def shader_sprite_bayer() -> Shader:
    """Shader GLSL chroma-safe com fade Bayer 4x4 sem borda magenta."""
    return Shader.make(Shader.SL_GLSL, _SHADER_BAYER_VERT, _SHADER_BAYER_FRAG)


@cache
def atlas_gosma():
    """Carrega o atlas RGBA de quatro linhas por quatro colunas das partículas de gosma."""
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
    """Cria um cartão no plano XZ preservando a proporção dos pixels, sem hit-test."""
    card = CardMaker(name)
    w = max(1, int(texture.getXSize())) if texture is not None else 1
    h = max(1, int(texture.getYSize())) if texture is not None else 1
    maior = float(max(w, h))
    hx = 0.5 * (w / maior)
    hz = 0.5 * (h / maior)
    card.setFrame(-hx, hx, -hz, hz)
    node = parent.attachNewNode(card.generate())
    node.setTexture(texture)
    node.setTwoSided(True)
    node.setLightOff(1)
    node.setTransparency(TransparencyAttrib.MNone)
    node.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MGreater, 0.14))
    node.setShader(shader_sprite_bayer(), 2)
    node.setShaderInput("u_fade", 1.0)
    node.setCollideMask(0)
    return node


def quadro_gosma(node, linha, coluna):
    """Seleciona um sprite sem interpolar células adjacentes."""
    stage = TextureStage.getDefault()
    node.setTexScale(stage, 0.25, 0.25)
    node.setTexOffset(stage, coluna * 0.25, (3 - linha) * 0.25)
