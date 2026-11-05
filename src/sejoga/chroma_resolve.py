"""Resolve MSAA coverage before tone mapping for Win32's binary color key."""


def install_chroma_resolve(pipeline):
    from panda3d.core import Shader
    quad = pipeline._post_process_quad
    original = quad.getShader()
    fragment = original.getText(Shader.STFragment)
    marker = 'vec3 color = tex_color.rgb;'
    if marker not in fragment:
        raise RuntimeError('SimplePBR tonemap shader changed; chroma resolve needs review')
    replacement = '''
    // The clear pixel is magenta with zero alpha. Resolve partial coverage
    // into either a clean surface color or the exact chroma background.
    float coverage = clamp(tex_color.a, 0.0, 1.0);
    vec3 color = coverage < 0.5 ? vec3(1.0, 0.0, 1.0)
        : max(vec3(0.0), (tex_color.rgb - vec3(1.0, 0.0, 1.0)*(1.0-coverage))/max(coverage, 0.001));
    '''
    quad.setShader(Shader.make(Shader.SL_GLSL,
        original.getText(Shader.STVertex), fragment.replace(marker, replacement)))
