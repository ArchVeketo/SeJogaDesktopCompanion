"""Resolve MSAA coverage, visual style filters (post-tonemap), and binary alpha for Win32."""

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
uniform vec4 u_filter_fx;

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

vec3 _sj_filmic(vec3 c) {
    vec3 x = max(vec3(0.0), c - vec3(0.004));
    return (x * (vec3(6.2) * x + vec3(0.5))) / (x * (vec3(6.2) * x + vec3(1.7)) + vec3(0.06));
}

float _sj_luma(vec3 c) {
    return dot(c, vec3(0.299, 0.587, 0.114));
}
"""


def configurar_textura_cena_nearest(quad) -> None:
    """Mantém a textura de cena do SimplePBR em FTNearest (sem sangramento bilinear de borda)."""
    from panda3d.core import SamplerState, Texture

    tex_inp = quad.getShaderInput("tex")
    scene_tex = tex_inp.getTexture() if tex_inp else None
    if scene_tex is None:
        return
    scene_tex.setMinfilter(Texture.FTNearest)
    scene_tex.setMagfilter(Texture.FTNearest)
    sampler = SamplerState()
    sampler.setMinfilter(Texture.FTNearest)
    sampler.setMagfilter(Texture.FTNearest)
    sampler.setWrapU(SamplerState.WMClamp)
    sampler.setWrapV(SamplerState.WMClamp)
    quad.setShaderInput("tex", scene_tex, sampler)


def limpar_fbo_transparente(pipeline) -> None:
    """Limpa o FBO MSAA do SimplePBR em (0, 0, 0, 0) para unpremultiply puro sem franja."""
    filtermgr = getattr(pipeline, "_filtermgr", None)
    if filtermgr is not None and getattr(filtermgr, "buffers", None):
        buf0 = filtermgr.buffers[0]
        buf0.setClearColor((0.0, 0.0, 0.0, 0.0))
        buf0.setClearColorActive(True)


def install_chroma_resolve(pipeline, colorkey_hex: str = CHROMA_HEX_PADRAO):
    """Injeta resolução de cobertura, filtros pós-tonemap e alpha binário no SimplePBR.

    O FBO MSAA é limpo com ``(0, 0, 0, 0)`` para que ``tex_color.rgb / coverage``
    recupere a cor exata de borda sem contaminação do chroma key. Os filtros visuais
    rodam APÓS o tonemap Filmic em espaço sRGB calibrado, estritamente dentro da
    silhueta opaca (``!is_chroma_bg``), garantindo fundo limpo e zero borda indesejada.
    """
    from panda3d.core import Shader

    quad = pipeline._post_process_quad
    original = quad.getShader()
    fragment = original.getText(Shader.STFragment)
    sample_marker = "vec4 tex_color = texture2D(tex, v_texcoord);"
    marker = "vec3 color = tex_color.rgb;"
    main_marker = "void main()"
    output_marker = (
        "#ifdef USE_330\n"
        "    o_color = vec4(color, tex_color.a);\n"
        "#else\n"
        "    gl_FragColor = vec4(color, tex_color.a);\n"
        "#endif"
    )
    if (
        sample_marker not in fragment
        or marker not in fragment
        or main_marker not in fragment
        or output_marker not in fragment
    ):
        raise RuntimeError(
            "SimplePBR tonemap shader changed; chroma resolve needs review"
        )

    limpar_fbo_transparente(pipeline)
    configurar_textura_cena_nearest(quad)
    if hasattr(pipeline, "taskmgr") and not getattr(pipeline, "_sj_fbo_clear_hooked", False):
        pipeline._sj_fbo_clear_hooked = True

        def _manter_fbo_transparente(task):
            limpar_fbo_transparente(pipeline)
            return task.cont

        pipeline.taskmgr.add(_manter_fbo_transparente, "sejoga-fbo-clear-reset", sort=49)

    sample_replacement, pre_tonemap_replacement, post_tonemap_effects = _gerar_blocos_glsl(
        _glsl_vec3(derivar_chroma(colorkey_hex).rgb)
    )
    patched_fragment = (
        fragment.replace(main_marker, _POST_UNIFORMS_GLSL + "\n" + main_marker, 1)
        .replace(sample_marker, sample_replacement, 1)
        .replace(marker, pre_tonemap_replacement, 1)
        .replace(output_marker, post_tonemap_effects, 1)
    )
    quad.setShader(Shader.make(Shader.SL_GLSL, original.getText(Shader.STVertex), patched_fragment))
    _inicializar_uniforms_croma(quad)


def _inicializar_uniforms_croma(quad) -> None:
    for nome, val in (
        ("u_dissolve", 0.0),
        ("u_dissolve_mode", 0.0),
        ("u_overlay_tint", (0.1, 0.65, 1.0)),
        ("u_overlay_flash", 0.0),
        ("u_viewport_size", (480.0, 480.0)),
        ("u_visual_filter", 0.0),
        ("u_pixel_size", 3.0),
        ("u_filter_time", 0.0),
        ("u_filter_fx", (0.0, 0.0, 0.0, 0.0)),
    ):
        quad.setShaderInput(nome, val)


def _gerar_blocos_glsl(chroma: str) -> tuple[str, str, str]:
    sample_replacement = """
    vec2 sample_uv = v_texcoord;
    vec2 pixel_cell = gl_FragCoord.xy;
    if ((u_visual_filter > 0.5 && u_visual_filter < 1.5)
        || (u_visual_filter >= 7.5 && u_visual_filter < 8.5)) {
        // Pixel Art 16-bit / Game Boy: quantiza UV em grade fina sem interpolação bilinear.
        vec2 px_grid = max(vec2(96.0), u_viewport_size / max(u_pixel_size, 1.0));
        pixel_cell = floor(v_texcoord * px_grid);
        sample_uv = (pixel_cell + 0.5) / px_grid;
    } else if (u_visual_filter >= 5.5 && u_visual_filter < 6.5) {
        // Retro PS1 / CRT: grade sub-pixel controlada e nítida.
        vec2 lp_grid = max(vec2(128.0), u_viewport_size / max(u_pixel_size * 0.75, 1.0));
        pixel_cell = floor(v_texcoord * lp_grid);
        sample_uv = (pixel_cell + 0.5) / lp_grid;
    } else if (u_visual_filter >= 6.5 && u_visual_filter < 7.5) {
        // Holograma Glitch: rajada horizontal reativa a velocidade/impacto/ar sem perder contorno.
        float fx_inst = clamp(u_filter_fx.x + u_filter_fx.y * 1.4 + u_filter_fx.w * 0.85, 0.0, 1.5);
        float cycle = fract(u_filter_time * (0.45 + fx_inst * 0.55));
        float pulse = step(max(0.42, 0.84 - fx_inst * 0.28), cycle);
        float slice_id = floor(v_texcoord.y * 44.0);
        float slice_t = floor(u_filter_time * (18.0 + fx_inst * 12.0));
        float jitter = _sj_hash12(vec2(slice_id, slice_t)) - 0.5;
        float burst = step(0.62 - fx_inst * 0.16, abs(jitter) * 2.0) * pulse;
        if (burst > 0.0) {
            vec2 shift = vec2(jitter * (0.019 + fx_inst * 0.018), 0.0);
            vec2 shifted_uv = clamp(sample_uv + shift, vec2(0.0), vec2(1.0));
            if (min(texture2D(tex, sample_uv).a, texture2D(tex, shifted_uv).a) >= 0.95) {
                sample_uv = shifted_uv;
            }
        }
    }
    vec4 tex_color = texture2D(tex, sample_uv);
    """

    despill_block = ""
    if DESPILL_FORCA > 0.0:
        despill_block = f"""
    if (!is_chroma_bg && coverage < {DESPILL_COBERTURA_CHEIA}) {{
        float limpo = dot(color, 1.0 - chroma_key) / max(dot(1.0 - chroma_key, vec3(1.0)), {COBERTURA_EPSILON});
        float borda = (1.0 - coverage) * {DESPILL_FORCA};
        color = mix(color, min(color, mix(color, vec3(limpo), chroma_key)), borda);
    }}
        """

    pre_tonemap_replacement = f"""
    vec3 chroma_key = {chroma};
    float coverage = clamp(tex_color.a, 0.0, 1.0);
    bool is_chroma_bg = coverage < {COBERTURA_MINIMA};
    vec3 color = is_chroma_bg ? chroma_key
        : max(vec3(0.0), tex_color.rgb / max(coverage, {COBERTURA_EPSILON}));
    {despill_block}
    """

    post_tonemap_effects = f"""
    vec3 chroma_post = _sj_filmic(chroma_key * exposure);
    if (!is_chroma_bg) {{
        // 10 Filtros de Estilo calibrados pós-tonemap em sRGB [0, 1].
        if (u_visual_filter >= 0.5) {{
            vec2 texel = 1.0 / max(u_viewport_size, vec2(1.0));
            bool modo_bloco = (u_visual_filter < 1.5)
                || (u_visual_filter >= 7.5 && u_visual_filter < 8.5);
            vec2 edge_texel = modo_bloco ? (texel * max(u_pixel_size, 1.0)) : texel;
            vec4 sL = texture2D(tex, sample_uv - vec2(edge_texel.x, 0.0));
            vec4 sR = texture2D(tex, sample_uv + vec2(edge_texel.x, 0.0));
            vec4 sU = texture2D(tex, sample_uv + vec2(0.0, edge_texel.y));
            vec4 sD = texture2D(tex, sample_uv - vec2(0.0, edge_texel.y));
            bool interno = min(min(sL.a, sR.a), min(sU.a, sD.a)) >= {COBERTURA_MINIMA};
            float edge_s = 0.0;
            float nb_max_luma = 0.0;
            vec3 cL = color;
            vec3 cR = color;
            if (sL.a >= {COBERTURA_MINIMA}) {{
                cL = _sj_filmic(sL.rgb / max(sL.a, {COBERTURA_EPSILON}) * exposure);
                nb_max_luma = max(nb_max_luma, _sj_luma(cL));
            }}
            if (sR.a >= {COBERTURA_MINIMA}) {{
                cR = _sj_filmic(sR.rgb / max(sR.a, {COBERTURA_EPSILON}) * exposure);
                nb_max_luma = max(nb_max_luma, _sj_luma(cR));
            }}
            if (sU.a >= {COBERTURA_MINIMA}) {{
                vec3 cU = _sj_filmic(sU.rgb / max(sU.a, {COBERTURA_EPSILON}) * exposure);
                nb_max_luma = max(nb_max_luma, _sj_luma(cU));
                if (interno) {{
                    vec3 cD = _sj_filmic(sD.rgb / max(sD.a, {COBERTURA_EPSILON}) * exposure);
                    nb_max_luma = max(nb_max_luma, _sj_luma(cD));
                    edge_s = length(cR - cL) + length(cU - cD);
                }}
            }}
            if (sD.a >= {COBERTURA_MINIMA}) {{
                nb_max_luma = max(nb_max_luma, _sj_luma(_sj_filmic(sD.rgb / max(sD.a, {COBERTURA_EPSILON}) * exposure)));
            }}

            if (u_visual_filter < 1.5) {{
                // 1. Pixel Art 16-bit Coeso: luma em 6 degraus + croma neutra-segura (sem ruído verde no branco!).
                float l_px = _sj_luma(color);
                vec3 sat_px = clamp(mix(vec3(l_px), color, 1.22), 0.0, 1.0);
                float dith_px = (_sj_bayer4(pixel_cell) - 0.5) * 0.065;
                float l_q = floor(clamp(l_px + dith_px, 0.0, 0.99) * 5.0 + 0.5) / 5.0;
                vec3 croma_delta = sat_px - vec3(l_px);
                vec3 croma_q = floor(croma_delta * 5.0 + 0.5) / 5.0;
                vec3 pix = clamp(vec3(l_q) + croma_q, 0.0, 1.0);
                if (interno) {{
                    pix = mix(pix, vec3(0.05, 0.05, 0.09), step(0.32, edge_s) * 0.42);
                }}
                color = clamp(pix, 0.0, 1.0);
            }} else if (u_visual_filter < 2.5) {{
                // 2. Quadrinho / Spider-Verse: 3 faixas + hachuras 8 FPS + Ben-Day + CMYK reativo.
                float l_sk = _sj_luma(color);
                float step_t = floor(u_filter_time * 8.0);
                float jx = (_sj_hash12(vec2(step_t, 3.1)) - 0.5) * 1.3;
                float jy = (_sj_hash12(vec2(step_t, 7.7)) - 0.5) * 1.3;
                vec2 sk_xy = gl_FragCoord.xy + vec2(jx, jy);
                float h1 = step(0.74, fract((sk_xy.x + sk_xy.y) * 0.165));
                float h2 = step(0.78, fract((sk_xy.x - sk_xy.y) * 0.165));
                vec2 ht_cell = fract(gl_FragCoord.xy * 0.16) - 0.5;
                float dot_ht = step(length(ht_cell), 0.27);
                vec3 paper = clamp(mix(vec3(l_sk), color, 1.18) * vec3(1.03, 1.00, 0.94), 0.0, 1.0);
                if (l_sk < 0.28) {{
                    paper = mix(paper, paper * 0.36, max(h1, h2) * 0.78);
                }} else if (l_sk < 0.52) {{
                    paper = mix(paper, paper * 0.66, max(h1 * 0.45, dot_ht * 0.55));
                }}
                if (interno) {{
                    float ink = smoothstep(0.22, 0.50, edge_s);
                    paper = mix(paper, vec3(0.05, 0.04, 0.07), ink * 0.72);
                    float misprint = 0.14 + clamp(u_filter_fx.x * 0.18 + u_filter_fx.y * 0.24, 0.0, 0.34);
                    paper.r = clamp(paper.r + smoothstep(0.28, 0.58, length(cR - color)) * misprint, 0.0, 1.0);
                    paper.b = clamp(paper.b + smoothstep(0.28, 0.58, length(cL - color)) * misprint, 0.0, 1.0);
                }}
                color = paper;
            }} else if (u_visual_filter < 3.5) {{
                // 3. Street Punk / Hi-Fi Comic: 3 bandas cel-shaded duras + retícula pop + grão spray + tinta pesada.
                float l_hf = _sj_luma(color);
                float street_imp = clamp(u_filter_fx.y, 0.0, 1.0);
                vec3 vib = clamp(mix(vec3(l_hf), color, 1.32 + street_imp * 0.18), 0.0, 1.0);
                float t1 = smoothstep(0.25, 0.28, l_hf);
                float t2 = smoothstep(0.57, 0.60, l_hf);
                float target_l = mix(0.18, mix(0.60, 0.92, t2), t1);
                vec3 cel = vib * clamp(target_l / max(l_hf, 0.05), 0.35, 1.90);
                if (l_hf < 0.28) {{
                    cel = mix(cel, cel * vec3(0.72, 0.78, 1.18), 0.44);
                }}
                vec2 ht_p = fract(gl_FragCoord.xy * 0.185) - 0.5;
                float ht_dot = step(length(ht_p), 0.27);
                if (l_hf >= 0.19 && l_hf < 0.42) {{
                    cel = mix(cel, cel * 0.66, ht_dot * 0.56);
                }}
                float spray_n = (_sj_hash12(floor(gl_FragCoord.xy * 0.5) + floor(u_filter_time * 10.0)) - 0.5) * 0.05;
                cel = clamp(cel + vec3(spray_n) + vec3(street_imp * 0.09), 0.0, 1.0);
                if (interno) {{
                    float crease = smoothstep(0.20, 0.43, edge_s);
                    cel = mix(cel, vec3(0.03, 0.03, 0.05), crease * 0.78);
                }}
                color = clamp(cel, 0.0, 1.0);
            }} else if (u_visual_filter < 4.5) {{
                // 4. Cyberfunk / Jet Set Neon Rim: posterização vibrante + rim ciano/limão nas arestas.
                float l_cf = _sj_luma(color);
                vec3 sat_cf = clamp(mix(vec3(l_cf), color, 1.30), 0.0, 1.0);
                float b1 = smoothstep(0.22, 0.27, l_cf);
                float b2 = smoothstep(0.54, 0.59, l_cf);
                float target_cf = mix(l_cf, mix(0.16, mix(0.54, 0.89, b2), b1), 0.68);
                vec3 vib = sat_cf * clamp(target_cf / max(l_cf, 0.06), 0.45, 1.80);
                if (l_cf < 0.26) {{
                    vib = mix(vib, vib * vec3(0.45, 0.72, 1.25), 0.52);
                }}
                bool eh_sombra = (l_cf < 0.095 && nb_max_luma < 0.125);
                if (!interno && !eh_sombra) {{
                    float brilho_borda = mix(0.40, 0.65, smoothstep(0.08, 0.43, l_cf));
                    vib = mix(vib, vec3(0.58, 1.0, 0.22), brilho_borda);
                }} else if (interno && !eh_sombra) {{
                    float neon_edge = smoothstep(0.26, 0.50, edge_s);
                    float lado_iluminado = smoothstep(-0.03, 0.25, l_cf - _sj_luma(cL));
                    vib = mix(vib, vec3(0.10, 0.90, 1.0), neon_edge * lado_iluminado * 0.51);
                }} else if (eh_sombra) {{
                    vib = vec3(0.045, 0.042, 0.068);
                }}
                color = clamp(vib, 0.0, 1.0);
            }} else if (u_visual_filter < 5.5) {{
                // 5. Anime Cel-Shading Limpo + Drama JoJo (hachura/contraste quando u_filter_fx.z alto).
                float l_an = _sj_luma(color);
                float drama = clamp(u_filter_fx.z, 0.0, 1.0);
                vec3 sat_an = clamp(mix(vec3(l_an), color, 1.24 + drama * 0.20), 0.0, 1.0);
                float cut_sh = smoothstep(0.35, 0.37, l_an);
                vec3 sh_col = sat_an * mix(vec3(0.70, 0.73, 1.05), vec3(0.46, 0.44, 0.82), drama);
                vec3 mid_col = sat_an * (1.12 + drama * 0.08);
                vec3 an_col = mix(sh_col, mid_col, cut_sh);
                float spec_cut = smoothstep(0.68, 0.71, l_an);
                an_col = mix(an_col, mix(an_col * 1.22, vec3(1.0, 0.99, 0.94), 0.44), spec_cut);
                if (drama > 0.15 && l_an < 0.36) {{
                    float h_jojo = step(0.76, fract((gl_FragCoord.x + gl_FragCoord.y) * 0.14));
                    an_col = mix(an_col, an_col * 0.56, h_jojo * drama * 0.62);
                }}
                if (interno) {{
                    float line_an = smoothstep(0.25, 0.47, edge_s);
                    an_col = mix(an_col, vec3(0.10, 0.07, 0.16), line_an * (0.58 + drama * 0.22));
                }}
                color = clamp(an_col, 0.0, 1.0);
            }} else if (u_visual_filter < 6.5) {{
                // 6. Retro PS1 / CRT: dithering RGB555 Bayer 4x4 em sRGB + micro-scanline CRT.
                float l_lp = _sj_luma(color);
                vec3 retro = clamp(mix(vec3(l_lp), color, 1.16), 0.0, 1.0);
                float bayer_lp = (_sj_bayer4(pixel_cell) - 0.5) * 0.036;
                retro = floor(clamp(retro + vec3(bayer_lp), 0.0, 1.0) * 31.0 + 0.5) / 31.0;
                float scanline = (mod(floor(gl_FragCoord.y * 0.5), 2.0) < 0.5) ? 0.90 : 1.04;
                color = clamp(retro * scanline, 0.0, 1.0);
            }} else if (u_visual_filter < 7.5) {{
                // 7. Holograma Sci-Fi (Glitch): ciano elétrico + scanlines + feixe animado + Fresnel rim.
                float l_hg = _sj_luma(color);
                float scan_h = (mod(floor(gl_FragCoord.y * 0.5), 2.0) < 0.5) ? 0.86 : 1.02;
                float band_v = fract(gl_FragCoord.y / max(u_viewport_size.y, 1.0));
                float wave_pos = fract(u_filter_time * 0.42);
                float sweep_dist = abs(band_v - wave_pos);
                float sweep = exp(-min(sweep_dist, 1.0 - sweep_dist) * 24.0) * 0.30;
                vec3 holo_deep = vec3(0.025, 0.14, 0.32);
                vec3 holo_mid = vec3(0.08, 0.65, 0.83);
                vec3 holo_hi = vec3(0.86, 0.98, 1.0);
                vec3 holo = mix(holo_deep, holo_mid, smoothstep(0.06, 0.58, l_hg));
                holo = mix(holo, holo_hi, smoothstep(0.62, 0.95, l_hg));
                holo = holo * scan_h + vec3(0.18, 0.88, 1.0) * sweep * (1.0 - 0.55 * l_hg);
                float inst_col = clamp(u_filter_fx.x + u_filter_fx.y + u_filter_fx.w, 0.0, 1.2);
                if (interno && inst_col > 0.12) {{
                    holo.r = clamp(holo.r + length(cR - color) * 0.22 * inst_col, 0.0, 1.0);
                    holo.b = clamp(holo.b + length(cL - color) * 0.18 * inst_col, 0.0, 1.0);
                }}
                vec2 t2 = texel * 2.0;
                vec4 n2L = texture2D(tex, sample_uv - vec2(t2.x, 0.0));
                vec4 n2R = texture2D(tex, sample_uv + vec2(t2.x, 0.0));
                vec4 n2U = texture2D(tex, sample_uv + vec2(0.0, t2.y));
                vec4 n2D = texture2D(tex, sample_uv - vec2(0.0, t2.y));
                float rim2 = min(min(n2L.a, n2R.a), min(n2U.a, n2D.a));
                float nb2_luma = nb_max_luma;
                if (n2L.a >= {COBERTURA_MINIMA}) nb2_luma = max(nb2_luma, _sj_luma(_sj_filmic(n2L.rgb / n2L.a * exposure)));
                if (n2R.a >= {COBERTURA_MINIMA}) nb2_luma = max(nb2_luma, _sj_luma(_sj_filmic(n2R.rgb / n2R.a * exposure)));
                if (n2U.a >= {COBERTURA_MINIMA}) nb2_luma = max(nb2_luma, _sj_luma(_sj_filmic(n2U.rgb / n2U.a * exposure)));
                if (n2D.a >= {COBERTURA_MINIMA}) nb2_luma = max(nb2_luma, _sj_luma(_sj_filmic(n2D.rgb / n2D.a * exposure)));
                bool eh_sombra_hg = (l_hg < 0.095 && nb2_luma < 0.125);
                if (eh_sombra_hg) {{
                    holo = vec3(0.02, 0.14, 0.22);
                }} else if (!interno || rim2 < {COBERTURA_MINIMA}) {{
                    holo = mix(holo, vec3(0.53, 0.96, 1.0), 0.52);
                }} else {{
                    float reflexo = smoothstep(0.16, 0.65, l_hg);
                    holo += vec3(0.28, 0.84, 0.95) * smoothstep(0.22, 0.48, edge_s) * reflexo * 0.24;
                }}
                color = clamp(holo, 0.0, 1.0);
            }} else if (u_visual_filter < 8.5) {{
                // 8. Game Boy Clássico (4 Tons DMG): dithering Bayer 4x4 + paleta DMG + sub-grade LCD.
                float l_gb = _sj_luma(color);
                float dith_gb = (_sj_bayer4(pixel_cell) - 0.5) * 0.18;
                float lvl = clamp(l_gb * 1.06 + dith_gb, 0.0, 0.99);
                vec3 gb0 = vec3(0.059, 0.220, 0.059);
                vec3 gb1 = vec3(0.188, 0.384, 0.188);
                vec3 gb2 = vec3(0.545, 0.675, 0.059);
                vec3 gb3 = vec3(0.608, 0.737, 0.059);
                vec3 gb = (lvl < 0.24) ? gb0 : (lvl < 0.50) ? gb1 : (lvl < 0.76) ? gb2 : gb3;
                if (interno && edge_s > 0.42) {{
                    gb = gb0;
                }}
                float lcd = (mod(floor(gl_FragCoord.x), max(u_pixel_size, 2.0)) < 0.6
                    || mod(floor(gl_FragCoord.y), max(u_pixel_size, 2.0)) < 0.6) ? 0.92 : 1.02;
                color = clamp(gb * lcd, 0.0, 1.0);
            }} else if (u_visual_filter < 9.5) {{
                // 9. Mangá P&B (Screentone): papel branco, retícula 45 graus nos meios-tons, hachura e nanquim.
                float l_mg = _sj_luma(color);
                vec3 ink_col = vec3(0.05, 0.05, 0.07);
                vec3 paper_col = vec3(0.96, 0.95, 0.91);
                vec2 rot45 = vec2(gl_FragCoord.x + gl_FragCoord.y, gl_FragCoord.y - gl_FragCoord.x) * 0.7071;
                vec2 tone_uv = fract(rot45 * 0.165) - 0.5;
                float dot_sz = clamp((0.64 - l_mg) * 0.92, 0.12, 0.46);
                float tone = smoothstep(dot_sz - 0.06, dot_sz + 0.06, length(tone_uv));
                float hatch = step(0.68, fract((gl_FragCoord.x - gl_FragCoord.y) * 0.20));
                vec3 mg = paper_col;
                if (l_mg < 0.15) {{
                    mg = ink_col;
                }} else if (l_mg < 0.30) {{
                    mg = mix(ink_col, paper_col, hatch * 0.32);
                }} else if (l_mg < 0.63) {{
                    mg = mix(ink_col, paper_col, tone);
                }}
                if (interno) {{
                    float line_mg = smoothstep(0.20, 0.44, edge_s);
                    mg = mix(mg, ink_col, line_mg * 0.88);
                }}
                color = mg;
            }} else {{
                // Preserva a malha de texels no objeto; comprime a iluminação em patamares.
                float valor = max(color.r, max(color.g, color.b));
                float banda = floor(valor * 15. + .5) / 15.;
                color *= mix(1., banda / max(valor, .025), .68);
                color = clamp(mix(vec3(_sj_luma(color)), color, 1.07), 0., 1.);
            }}
        }}

        if (u_overlay_flash > 0.001) {{
            color = mix(color, u_overlay_tint, clamp(u_overlay_flash, 0.0, 0.86));
        }}
        if (u_dissolve > 0.001) {{
            if (u_dissolve_mode > 2.5) {{
                // Teleporte Anime / Transmissão Instantânea: faixas horizontais de energia.
                vec2 uv_norm = gl_FragCoord.xy / max(u_viewport_size, vec2(1.0));
                float band_id = floor(gl_FragCoord.y * 0.16);
                float j = _sj_hash12(vec2(band_id, 19.3));
                float thr = mix(-0.08, 1.18, clamp(u_dissolve, 0.0, 1.0));
                float edge = thr - (j * 0.72 + abs(uv_norm.x - 0.5) * 0.56);
                if (edge > 0.08) {{
                    color = chroma_post;
                    is_chroma_bg = true;
                }} else if (edge > 0.0) {{
                    color = mix(color, u_overlay_tint, 0.85);
                }}
            }} else if (u_dissolve_mode > 1.5) {{
                // Cyberpsicopata: desgaste holográfico em faixas finas ciano/carmesim.
                vec2 uv_norm = gl_FragCoord.xy / max(u_viewport_size, vec2(1.0));
                float scan = fract(gl_FragCoord.y * 0.18 + _sj_hash12(floor(gl_FragCoord.xy / 6.0)) * 0.45);
                float edge = mix(-0.12, 1.25, clamp(u_dissolve, 0.0, 1.0))
                    - (uv_norm.y * 0.55 + _sj_bayer4(gl_FragCoord.xy) * 0.45);
                if (edge > 0.09) {{
                    color = chroma_post;
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
                    color = chroma_post;
                    is_chroma_bg = true;
                }} else if (edge > 0.0) {{
                    color = mix(color, vec3(1.0, 0.54, 0.18), clamp(edge / 0.085, 0.0, 1.0));
                }}
            }} else if (_sj_bayer4(gl_FragCoord.xy) <= clamp(u_dissolve, 0.0, 1.0)) {{
                color = chroma_post;
                is_chroma_bg = true;
            }}
        }}
        // Proteção anti-buraco no color key após filtros em espaço sRGB.
        if (!is_chroma_bg && distance(color, chroma_post) < 0.08) {{
            vec3 safe_target = mix(vec3(1.0), vec3(0.0), step(vec3(0.5), chroma_post));
            color = mix(color, safe_target, 0.20);
        }}
    }}
    float out_alpha = is_chroma_bg ? 0.0 : 1.0;
    #ifdef USE_330
        o_color = vec4(color, out_alpha);
    #else
        gl_FragColor = vec4(color, out_alpha);
    #endif
    """
    return sample_replacement, pre_tonemap_replacement, post_tonemap_effects
