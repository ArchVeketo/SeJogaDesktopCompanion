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


def install_chroma_resolve(pipeline, colorkey_hex: str = CHROMA_HEX_PADRAO):
    """Injeta a resolução de cobertura + despill no tonemap do SimplePBR.

    ``colorkey_hex`` (``#RRGGBB``) é a cor do color key configurada; o default
    reproduz o magenta histórico. A correção da franja vive AQUI, na origem, e
    NÃO depende do contorno — a outline só mascara, o despill limpa a borda com
    e sem ela.
    """
    from panda3d.core import Shader

    quad = pipeline._post_process_quad
    original = quad.getShader()
    fragment = original.getText(Shader.STFragment)
    marker = "vec3 color = tex_color.rgb;"
    if marker not in fragment:
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
    """
    quad.setShader(
        Shader.make(
            Shader.SL_GLSL,
            original.getText(Shader.STVertex),
            fragment.replace(marker, replacement),
        )
    )
