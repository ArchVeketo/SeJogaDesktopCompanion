"""Resolve MSAA coverage before tone mapping for Win32's binary color key."""

from sejoga.render.chroma_tuning import (
    CHROMA_MAGENTA_RGB,
    COBERTURA_EPSILON,
    COBERTURA_MINIMA,
)


def _glsl_vec3(rgb: tuple[float, float, float]) -> str:
    """Formata um RGB como literal GLSL ``vec3(r, g, b)``."""
    return "vec3({}, {}, {})".format(*rgb)


def install_chroma_resolve(pipeline):
    from panda3d.core import Shader
    quad = pipeline._post_process_quad
    original = quad.getShader()
    fragment = original.getText(Shader.STFragment)
    marker = 'vec3 color = tex_color.rgb;'
    if marker not in fragment:
        raise RuntimeError('SimplePBR tonemap shader changed; chroma resolve needs review')
    chroma = _glsl_vec3(CHROMA_MAGENTA_RGB)
    replacement = f'''
    // The clear pixel is magenta with zero alpha. Resolve partial coverage
    // into either a clean surface color or the exact chroma background.
    float coverage = clamp(tex_color.a, 0.0, 1.0);
    vec3 color = coverage < {COBERTURA_MINIMA} ? {chroma}
        : max(vec3(0.0), (tex_color.rgb - {chroma}*(1.0-coverage))/max(coverage, {COBERTURA_EPSILON}));
    '''
    quad.setShader(Shader.make(Shader.SL_GLSL,
        original.getText(Shader.STVertex), fragment.replace(marker, replacement)))
