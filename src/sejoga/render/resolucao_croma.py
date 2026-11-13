"""Resolve MSAA coverage before tone mapping for Win32's binary color key."""

from sejoga.render.chroma_tuning import (
    CHROMA_HEX_PADRAO,
    COBERTURA_EPSILON,
    COBERTURA_MINIMA,
    DESPILL_COBERTURA_CHEIA,
    DESPILL_FORCA,
    derivar_chroma,
)


def _glsl_vec3(rgb: tuple[float, float, float]) -> str:
    """Formata um RGB como literal GLSL ``vec3(r, g, b)``."""
    return "vec3({}, {}, {})".format(*rgb)


_POST_UNIFORMS_GLSL = """
uniform float u_dissolve;
uniform float u_dissolve_mode;
uniform vec3 u_overlay_tint;
uniform float u_overlay_flash;
uniform vec2 u_viewport_size;

float _sj_bayer4(vec2 frag_xy) {
    vec2 p = floor(mod(floor(frag_xy * 0.5), 4.0));
    float v = 0.0;
    if (p.y < 0.5) {
        v = (p.x < 0.5) ? 0.0 : (p.x < 1.5) ? 8.0 : (p.x < 2.5) ? 2.0 : 10.0;
    } else if (p.y < 1.5) {
        v = (p.x < 0.5) ? 12.0 : (p.x < 1.5) ? 4.0 : (p.x < 2.5) ? 14.0 : 6.0;
    } else if (p.y < 2.5) {
        v = (p.x < 0.5) ? 3.0 : (p.x < 1.5) ? 11.0 : (p.x < 2.5) ? 1.0 : 9.0;
    } else {
        v = (p.x < 0.5) ? 15.0 : (p.x < 1.5) ? 7.0 : (p.x < 2.5) ? 13.0 : 5.0;
    }
    return (v + 0.5) / 16.0;
}

float _sj_hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}
"""


def install_chroma_resolve(pipeline, colorkey_hex: str = CHROMA_HEX_PADRAO):
    """Injeta a resolução de cobertura + despill + efeitos de tela no tonemap do SimplePBR.

    ``colorkey_hex`` (``#RRGGBB``) é a cor do color key configurada; o default
    reproduz o magenta histórico. A correção da franja vive AQUI, na origem, e
    NÃO depende do contorno — a outline só mascara, o despill limpa a borda com
    e sem ela. Os efeitos de dissolução usam dither Bayer binário para nunca gerar
    franja magenta no color key Win32.
    """
    from panda3d.core import Shader

    quad = pipeline._post_process_quad
    original = quad.getShader()
    fragment = original.getText(Shader.STFragment)
    marker = "vec3 color = tex_color.rgb;"
    main_marker = "void main()"
    if marker not in fragment or main_marker not in fragment:
        raise RuntimeError(
            "SimplePBR tonemap shader changed; chroma resolve needs review"
        )
    chroma = _glsl_vec3(derivar_chroma(colorkey_hex).rgb)
    replacement = f"""
    // The clear pixel is the chroma color with zero alpha. Resolve partial
    // coverage into either a clean surface color or the exact chroma background.
    vec3 chroma_key = {chroma};
    float coverage = clamp(tex_color.a, 0.0, 1.0);
    vec3 color = coverage < {COBERTURA_MINIMA} ? chroma_key
        : max(vec3(0.0), (tex_color.rgb - chroma_key*(1.0-coverage))/max(coverage, {COBERTURA_EPSILON}));
    // Despill: partial-coverage edge pixels still carry a fringe tinted toward
    // the chroma. Pull the chroma-dominant channels down toward the channels
    // the chroma leaves clean, proportional to how partial the coverage is.
    // Independent of the outline (origin fix). Validate on GPU.
    if (coverage > {COBERTURA_MINIMA} && coverage < {DESPILL_COBERTURA_CHEIA}) {{
        float limpo = dot(color, 1.0 - chroma_key) / max(dot(1.0 - chroma_key, vec3(1.0)), {COBERTURA_EPSILON});
        float borda = (1.0 - coverage) * {DESPILL_FORCA};
        color = mix(color, min(color, mix(color, vec3(limpo), chroma_key)), borda);
    }}
    if (coverage >= {COBERTURA_MINIMA}) {{
        if (u_overlay_flash > 0.001) {{
            color = mix(color, u_overlay_tint, clamp(u_overlay_flash, 0.0, 0.86));
        }}
        if (u_dissolve > 0.001) {{
            if (u_dissolve_mode > 0.5) {{
                // Thanos: varredura de cinzas da base para cima com brasa na borda.
                vec2 uv_norm = gl_FragCoord.xy / max(u_viewport_size, vec2(1.0));
                float grain = _sj_bayer4(gl_FragCoord.xy) * 0.24
                    + _sj_hash12(floor(gl_FragCoord.xy / 3.0)) * 0.34;
                float band = (uv_norm.y * 0.62 + (1.0 - uv_norm.x) * 0.38) * 0.62
                    + grain * 0.72;
                float edge = mix(-0.15, 1.35, clamp(u_dissolve, 0.0, 1.0)) - band;
                if (edge > 0.085) {{
                    color = chroma_key;
                }} else if (edge > 0.0) {{
                    color = mix(color, vec3(1.25, 0.48, 0.14), clamp(edge / 0.085, 0.0, 1.0));
                }}
            }} else if (_sj_bayer4(gl_FragCoord.xy) <= clamp(u_dissolve, 0.0, 1.0)) {{
                color = chroma_key;
            }}
        }}
    }}
    """
    patched_fragment = fragment.replace(main_marker, _POST_UNIFORMS_GLSL + "\n" + main_marker, 1)
    patched_fragment = patched_fragment.replace(marker, replacement)
    quad.setShader(
        Shader.make(
            Shader.SL_GLSL,
            original.getText(Shader.STVertex),
            patched_fragment,
        )
    )
    quad.setShaderInput("u_dissolve", 0.0)
    quad.setShaderInput("u_dissolve_mode", 0.0)
    quad.setShaderInput("u_overlay_tint", (0.1, 0.65, 1.0))
    quad.setShaderInput("u_overlay_flash", 0.0)
    quad.setShaderInput("u_viewport_size", (480.0, 480.0))
