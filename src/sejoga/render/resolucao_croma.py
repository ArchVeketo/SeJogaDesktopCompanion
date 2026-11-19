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
uniform float u_visual_filter;
uniform float u_pixel_size;
uniform float u_filter_time;

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
    sample_marker = "vec4 tex_color = texture2D(tex, v_texcoord);"
    marker = "vec3 color = tex_color.rgb;"
    main_marker = "void main()"
    if sample_marker not in fragment or marker not in fragment or main_marker not in fragment:
        raise RuntimeError(
            "SimplePBR tonemap shader changed; chroma resolve needs review"
        )
    chroma = _glsl_vec3(derivar_chroma(colorkey_hex).rgb)
    sample_replacement = """
    vec2 sample_uv = v_texcoord;
    if (u_visual_filter > 0.5 && u_visual_filter < 1.5) {
        // Filtro Pixel (~1.75px fiel ao turntable.gif):
        // Com scene_tex em FTNearest, a quantizacao de UV amostra 1 texel puro
        // sem mistura bilinear com o chroma key (franja zero garantida!).
        vec2 px_grid = max(vec2(64.0), u_viewport_size / max(u_pixel_size, 1.0));
        sample_uv = (floor(v_texcoord * px_grid) + 0.5) / px_grid;
    }
    vec4 tex_color = texture2D(tex, sample_uv);
    """
    replacement = f"""
    // The clear pixel is the chroma color with zero alpha. Resolve partial
    // coverage into either a clean surface color or the exact chroma background.
    vec3 chroma_key = {chroma};
    float coverage = clamp(tex_color.a, 0.0, 1.0);
    bool is_chroma_bg = coverage < {COBERTURA_MINIMA};
    vec3 color = is_chroma_bg ? chroma_key
        : max(vec3(0.0), (tex_color.rgb - chroma_key*(1.0-coverage))/max(coverage, {COBERTURA_EPSILON}));
    // Despill: partial-coverage edge pixels still carry a fringe tinted toward
    // the chroma. Pull the chroma-dominant channels down toward the channels
    // the chroma leaves clean, proportional to how partial the coverage is.
    // Independent of the outline (origin fix). Validate on GPU.
    if (!is_chroma_bg && coverage < {DESPILL_COBERTURA_CHEIA}) {{
        float limpo = dot(color, 1.0 - chroma_key) / max(dot(1.0 - chroma_key, vec3(1.0)), {COBERTURA_EPSILON});
        float borda = (1.0 - coverage) * {DESPILL_FORCA};
        color = mix(color, min(color, mix(color, vec3(limpo), chroma_key)), borda);
    }}
    if (!is_chroma_bg) {{
        // Filtro 1: Pixel (~1.5px fiel ao turntable.gif: cores vivas e limpas sem borda rosa)
        if (u_visual_filter > 0.5 && u_visual_filter < 1.5) {{
            float luma_px = dot(color, vec3(0.299, 0.587, 0.114));
            color = mix(vec3(luma_px), color, 1.18);
            color = max(vec3(0.0), color * 1.10 + vec3(0.015));
        }} else if (u_visual_filter >= 1.5) {{
            // Filtro 2: Rascunho / Spider-Punk (hachuras 8 FPS nas sombras + contraste grafico)
            float luma_sk = dot(color, vec3(0.299, 0.587, 0.114));
            float step_t = floor(u_filter_time * 8.0);
            float jx = (_sj_hash12(vec2(step_t, 3.1)) - 0.5) * 2.2;
            float jy = (_sj_hash12(vec2(step_t, 7.7)) - 0.5) * 2.2;
            vec2 sk_xy = gl_FragCoord.xy + vec2(jx, jy);
            float hatch1 = step(0.76, fract((sk_xy.x + sk_xy.y) * 0.165));
            float hatch2 = step(0.80, fract((sk_xy.x - sk_xy.y) * 0.165));
            if (luma_sk < 0.28) {{
                color = mix(color, color * 0.44, max(hatch1, hatch2) * 0.68);
            }} else if (luma_sk < 0.48) {{
                color = mix(color, color * 0.68, hatch1 * 0.42);
            }}
            color = mix(vec3(luma_sk), color, 1.10);
        }}
        if (u_overlay_flash > 0.001) {{
            color = mix(color, u_overlay_tint, clamp(u_overlay_flash, 0.0, 0.86));
        }}
        if (u_dissolve > 0.001) {{
            if (u_dissolve_mode > 1.5) {{
                // Cyberpsicopata: desgaste holográfico em faixas finas ciano/carmesim.
                vec2 uv_norm = gl_FragCoord.xy / max(u_viewport_size, vec2(1.0));
                float scan = fract(gl_FragCoord.y * 0.18 + _sj_hash12(floor(gl_FragCoord.xy / 6.0)) * 0.45);
                float edge = mix(-0.12, 1.25, clamp(u_dissolve, 0.0, 1.0))
                    - (uv_norm.y * 0.55 + _sj_bayer4(gl_FragCoord.xy) * 0.45);
                if (edge > 0.09) {{
                    color = chroma_key;
                    is_chroma_bg = true;
                }} else if (edge > 0.0) {{
                    vec3 holo = mix(vec3(0.08, 0.96, 1.0), vec3(1.0, 0.14, 0.24), step(0.5, scan));
                    color = mix(color, holo, clamp(edge / 0.09, 0.0, 1.0));
                }}
            }} else if (u_dissolve_mode > 0.5) {{
                // Thanos: varredura de cinzas da base para cima com brasa na borda.
                vec2 uv_norm = gl_FragCoord.xy / max(u_viewport_size, vec2(1.0));
                float grain = _sj_bayer4(gl_FragCoord.xy) * 0.24
                    + _sj_hash12(floor(gl_FragCoord.xy / 3.0)) * 0.34;
                float band = (uv_norm.y * 0.62 + (1.0 - uv_norm.x) * 0.38) * 0.62
                    + grain * 0.72;
                float edge = mix(-0.15, 1.35, clamp(u_dissolve, 0.0, 1.0)) - band;
                if (edge > 0.085) {{
                    color = chroma_key;
                    is_chroma_bg = true;
                }} else if (edge > 0.0) {{
                    color = mix(color, vec3(1.25, 0.48, 0.14), clamp(edge / 0.085, 0.0, 1.0));
                }}
            }} else if (_sj_bayer4(gl_FragCoord.xy) <= clamp(u_dissolve, 0.0, 1.0)) {{
                color = chroma_key;
                is_chroma_bg = true;
            }}
        }}
        // Proteção anti-buraco no color key: nenhum pixel opaco do Mário (ex.: cabelo/luva rosa)
        // pode coincidir com o chroma_key após filtros ou despill.
        if (!is_chroma_bg && distance(color, chroma_key) < 0.09) {{
            vec3 safe_nudge = (1.0 - chroma_key) * 0.11;
            color = clamp(color + safe_nudge - chroma_key * 0.04, 0.0, 1.5);
        }}
    }}
    """
    patched_fragment = fragment.replace(main_marker, _POST_UNIFORMS_GLSL + "\n" + main_marker, 1)
    patched_fragment = patched_fragment.replace(sample_marker, sample_replacement, 1)
    patched_fragment = patched_fragment.replace(marker, replacement, 1)
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
    quad.setShaderInput("u_visual_filter", 0.0)
    quad.setShaderInput("u_pixel_size", 1.5)
    quad.setShaderInput("u_filter_time", 0.0)
