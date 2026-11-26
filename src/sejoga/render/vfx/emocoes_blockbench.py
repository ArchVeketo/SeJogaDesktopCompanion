"""Emissores Blockbench de emoção e estado (estética Minecraft Dungeons / Dungeons 2)."""

from __future__ import annotations

from functools import cache
from math import pi, sin
from typing import TYPE_CHECKING

from panda3d.core import (
    CardMaker,
    GeomTriangles,
    GeomVertexData,
    GeomVertexWriter,
    NodePath,
    Shader,
    TextureStage,
    TransparencyAttrib,
    Vec3,
)

from sejoga.render.vfx.acao_blockbench import (
    _AMBAR_FUNDO,
    _N_COLS,
    _cartao_celula,
    _cartao_puff_dungeons,
    _emitir_segmento_dungeons,
)
from sejoga.render.vfx.choque_blockbench import (
    _BRANCO,
    _CIANO,
    _OURO_BRILHO,
    _criar_cubo_voxel,
    _criar_no_arco,
)

if TYPE_CHECKING:
    from sejoga.render.efeitos_street import GerenciadorEfeitosStreet

_GELO_VOXEL = (0.72, 0.94, 1.00, 1.0)


def _atualizar_carinho(
    coracao: NodePath,
    mini: NodePath,
    cubos: tuple[NodePath, NodePath, NodePath],
    stage: TextureStage,
    fase: float,
    escala: float,
) -> None:
    pop = min(1.16, fase / 0.14) if fase < 0.14 else (1.16 - 0.16 * min(1.0, (fase - 0.14) / 0.12))
    estouro = fase >= 0.78
    coracao.setTexOffset(stage, (1 if estouro else 0) / _N_COLS, 0.0)
    tam = 1.15 * escala * pop * (1.0 + 0.22 * ((fase - 0.78) / 0.22) if estouro else 1.0)
    coracao.setPos(sin(fase * 2.0 * pi) * 0.20 * escala, -0.04, fase * 1.25 * escala)
    coracao.setR(sin(fase * 2.0 * pi) * 8.0)
    coracao.setScale(tam, 1.0, tam * _N_COLS)
    coracao.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))
    if fase < 0.16:
        mini.hide()
    else:
        u = min(1.0, (fase - 0.16) / 0.84)
        tm = 0.82 * escala * min(1.0, u / 0.18) * min(1.0, (1.0 - u) / 0.24)
        mini.show()
        mini.setPos((0.86 + sin(u * 2.0 * pi) * 0.14) * escala, -0.02, (0.28 + u * 1.18) * escala)
        mini.setR(-sin(u * 2.0 * pi) * 7.0)
        mini.setScale(tm, 1.0, tm * _N_COLS)
        mini.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.20))
    for i, cb in enumerate(cubos):
        pulso = max(0.0, sin((fase * 2.6 + i * 0.38) * pi))
        if pulso <= 0.12 or fase > 0.88:
            cb.hide()
            continue
        cb.show()
        pos_x = (-0.72, 0.76, -0.22)[i]
        cb.setPos(pos_x * escala, -0.06, (0.42 + fase * 1.05 + i * 0.22) * escala)
        cb.setHpr(45.0, 35.0, fase * 110.0 * (-1.0 if i == 0 else 1.0))
        cb.setScale(0.13 * escala * pulso)


def emitir_carinho(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Coração chunky pixel-art + mini-coração + cubinhos Dungeons cintilantes."""
    del vel, dir_x
    origem = (Vec3(pos) if pos is not None else Vec3(anc["cabeca_topo"])) + Vec3(0.0, -0.10, 0.42)
    escala = max(0.75, min(1.30, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("carinho_blockbench")
    coracao = _cartao_celula(raiz, "coracao_bb", 0)
    mini = _cartao_celula(raiz, "mini_coracao_bb", 2)
    cubos = (
        _criar_cubo_voxel("brilho_c0", _OURO_BRILHO),
        _criar_cubo_voxel("brilho_c1", _BRANCO),
        _criar_cubo_voxel("brilho_c2", _OURO_BRILHO),
    )
    for cb in cubos:
        cb.reparentTo(raiz)

    def atualizar(fase: float) -> None:
        _atualizar_carinho(coracao, mini, cubos, stage, fase, escala)

    mgr.emitir_3d(
        raiz,
        origem,
        tipo_mesh="carinho_blockbench",
        ttl=0.86,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=atualizar,
    )
    atualizar(0.0)


def _atualizar_sono(
    letras: tuple[tuple[NodePath, float, float, float], ...],
    motes: tuple[NodePath, NodePath],
    fase: float,
    escala: float,
) -> None:
    for card, atraso, tam_base, dx_ini in letras:
        if fase < atraso:
            card.hide()
            continue
        u = min(1.0, (fase - atraso) / (1.0 - atraso))
        cresc = min(1.0, u / 0.20)
        encolhe = min(1.0, (1.0 - u) / 0.24)
        tam = tam_base * escala * cresc * encolhe
        if tam <= 0.02:
            card.hide()
            continue
        card.show()
        x_s = (dx_ini + u * 0.62 + sin(u * 2.0 * pi) * 0.22) * escala
        z_s = (u * 1.48) * escala
        card.setPos(x_s, -0.05, z_s)
        card.setR(sin(u * 2.0 * pi) * 10.0)
        card.setScale(tam, 1.0, tam * _N_COLS)
        card.setShaderInput("u_fade", encolhe)
    # 2 cubinhos voxel gelo flutuando bem devagar na mesma onda S
    for i, cb in enumerate(motes):
        u_m = max(0.0, (fase - i * 0.22) / (1.0 - i * 0.22))
        sc = 0.095 * escala * min(1.0, u_m / 0.20) * min(1.0, (1.0 - u_m) / 0.28)
        if fase < i * 0.22 or sc <= 0.015:
            cb.hide()
            continue
        cb.show()
        cb.setPos((0.18 + i * 0.48 + u_m * 0.55 + sin(u_m * 2.0 * pi) * 0.16) * escala, -0.04, (0.32 + u_m * 1.35) * escala)
        cb.setHpr(45.0, 35.0, u_m * 45.0)
        cb.setScale(sc)


def emitir_sono(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Sequência escalonada ``z`` -> ``Z`` + cubinhos gelo lentos em curva S ao lado do visor."""
    del vel, dir_x
    origem = (Vec3(pos) if pos is not None else Vec3(anc["visor_lado"])) + Vec3(0.32, -0.08, 0.22)
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("sono_blockbench")
    letras = (
        (_cartao_celula(raiz, "sono_z_bb", 3), 0.0, 0.76, 0.08),
        (_cartao_celula(raiz, "sono_Z_bb", 4), 0.26, 1.05, 0.46),
    )
    motes = (_criar_cubo_voxel("sono_m0", _GELO_VOXEL), _criar_cubo_voxel("sono_m1", _CIANO))
    for cb in motes:
        cb.reparentTo(raiz)

    def atualizar(fase: float) -> None:
        _atualizar_sono(letras, motes, fase, escala)

    mgr.emitir_3d(
        raiz,
        origem,
        tipo_mesh="sono_blockbench",
        ttl=1.12,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=atualizar,
    )
    atualizar(0.0)


@cache
def _shader_rubor_raiva() -> Shader:
    """Rubor de raiva na testa: degradê vermelho + hachura vertical estilizada (chroma-safe)."""
    return Shader.make(
        Shader.SL_GLSL,
        """#version 130
        uniform mat4 p3d_ModelViewProjectionMatrix;
        in vec4 p3d_Vertex, p3d_MultiTexCoord0;
        out vec2 uv;
        void main() {
            gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
            uv = p3d_MultiTexCoord0.xy;
        }
        """,
        """#version 130
        uniform float u_forca;
        in vec2 uv;
        out vec4 cor;
        void main() {
            float dx = abs(uv.x - 0.5) * 2.0;
            float borda_x = 1.0 - smoothstep(0.76, 1.0, dx);
            // Comprimento orgânico por coluna (hachura vertical descendo da testa)
            float col = floor(uv.x * 18.0);
            float var_alt = 0.14 * sin(col * 3.7 + 0.8) + 0.08 * cos(col * 7.1);
            float y_eff = clamp((uv.y - (0.14 + var_alt)) / 0.86, 0.0, 1.0);
            // Linhas verticais levemente inclinadas para fora como no anime/cartoon
            float inclin = uv.x + (1.0 - uv.y) * (uv.x - 0.5) * 0.18;
            float faixa = abs(fract(inclin * 15.0) - 0.5);
            float linha = 1.0 - smoothstep(0.14, 0.24, faixa);
            float base_grad = pow(clamp(uv.y, 0.0, 1.0), 1.65) * 0.52;
            float hachura = linha * pow(y_eff, 0.85) * 0.78;
            float alpha = clamp((base_grad + hachura) * borda_x * u_forca, 0.0, 0.86);
            if (alpha < 0.04) discard;
            vec3 vermelho_base = vec3(0.84, 0.12, 0.12);
            vec3 vermelho_escuro = vec3(0.56, 0.05, 0.09);
            vec3 rgb = mix(vermelho_base, vermelho_escuro, clamp(linha * 0.75 + uv.y * 0.25, 0.0, 1.0));
            cor = vec4(rgb, alpha);
        }
        """,
    )


def _criar_rubor_cabeca(raiz: NodePath) -> NodePath:
    cm = CardMaker("rubor_raiva_bb")
    # Encaixado estritamente dentro da frente do gabinete (abaixo da tiara, nunca vaza pro chroma)
    cm.setFrame(-0.70, 0.70, -1.68, -0.48)
    card = raiz.attachNewNode(cm.generate())
    card.setLightOff(1)
    card.setDepthWrite(False)
    card.setTransparency(TransparencyAttrib.MAlpha)
    card.setCollideMask(0)
    card.setBin("fixed", 42)
    card.setShader(_shader_rubor_raiva(), 3)
    card.setShaderInput("u_forca", 0.0)
    return card


def _atualizar_irritado(
    puffs: tuple[tuple[NodePath, float, float, float], ...],
    rubor: NodePath,
    marca: NodePath,
    templo_rel: Vec3,
    stage: TextureStage,
    fase: float,
    escala: float,
) -> None:
    # 1) Degradê vermelho contido dentro da cabeça/rosto (sem vazar acima da tiara)
    forca_r = min(1.0, fase / 0.16) * min(1.0, (1.0 - fase) / 0.26)
    rubor.setPos(0.0, -0.48, 0.0)
    rubor.setScale(escala, 1.0, escala)
    rubor.setShaderInput("u_forca", forca_r * (0.85 + 0.15 * abs(sin(fase * 3.0 * pi))))
    # 2) 4 nuvenzinhas chunky em 2 pares escalonados subindo volumosas da cabeça (estilo chaleira!)
    for pf, lado, atraso, peso in puffs:
        if fase < atraso:
            pf.hide()
            continue
        u = min(1.0, (fase - atraso) / (1.0 - atraso))
        tam = (0.58 + 0.52 * min(1.0, u * 3.8)) * peso * escala * min(1.0, (1.0 - u) / 0.24)
        if tam <= 0.03:
            pf.hide()
            continue
        pf.show()
        pf.setPos(lado * (0.52 + u * 0.88) * escala, -0.06, (0.26 + u * 1.38) * escala)
        pf.setR(-lado * (22.0 + u * 16.0))
        pf.setScale(tam * lado, 1.0, tam * 10.2)
        pf.setTexOffset(stage, min(5, int(u * 5.8)) / 8.0, 0.0)
        pf.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.22))
    # 3) Marca de raiva pulsando no templo
    pulso = 1.0 + 0.16 * abs(sin(fase * 3.0 * pi))
    tam_m = 0.86 * escala * pulso * min(1.0, fase / 0.10) * min(1.0, (1.0 - fase) / 0.18)
    if tam_m <= 0.02:
        marca.hide()
        return
    marca.show()
    marca.setPos(templo_rel + Vec3(0.68 * escala, -0.14, 0.18 * escala))
    marca.setScale(tam_m, 1.0, tam_m * _N_COLS)
    marca.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))


def emitir_irritado(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Irritação / raiva: degradê vermelho na cabeça + fumaça volumosa chunky + marca no templo."""
    del pos, vel, dir_x
    topo = Vec3(anc["cabeca_topo"])
    templo_rel = Vec3(anc.get("templo", topo + Vec3(0.95, 0.0, -0.45))) - topo
    escala = max(0.75, min(1.30, float(forca)))
    stage = TextureStage.getDefault()
    raiz = NodePath("irritado_blockbench")
    rubor = _criar_rubor_cabeca(raiz)
    puffs = (
        (_cartao_puff_dungeons(raiz, "raiva_puff_d0"), -1.0, 0.00, 1.00),
        (_cartao_puff_dungeons(raiz, "raiva_puff_e0"), 1.0, 0.08, 1.00),
        (_cartao_puff_dungeons(raiz, "raiva_puff_d1"), -0.82, 0.22, 0.78),
        (_cartao_puff_dungeons(raiz, "raiva_puff_e1"), 0.82, 0.30, 0.78),
    )
    marca = _cartao_celula(raiz, "raiva_marca", 14)

    def atualizar(fase: float) -> None:
        _atualizar_irritado(puffs, rubor, marca, templo_rel, stage, fase, escala)

    mgr.emitir_3d(
        raiz,
        topo,
        tipo_mesh="irritado_blockbench",
        ttl=0.84,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=atualizar,
    )
    atualizar(0.0)


emitir_calor = emitir_irritado


def _construir_coroa_susto(
    vdata: GeomVertexData,
    tris: GeomTriangles,
    rel_d: Vec3,
    rel_e: Vec3,
    fase: float,
    escala: float,
) -> None:
    if fase >= 0.94:
        return
    vdata.uncleanSetNumRows(0)
    tris.clearVertices()
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    snap = 1.18 if fase < 0.16 else 1.0
    retrac = max(0.0, (fase - 0.66) / 0.28)
    esp = 0.095 * escala * (1.0 - retrac * 0.55)
    idx = 0
    barras = (
        (rel_d, Vec3(-0.78, -0.06, 0.64)),
        (rel_d, Vec3(-0.98, -0.06, 0.12)),
        (rel_e, Vec3(0.78, -0.06, 0.64)),
        (rel_e, Vec3(0.98, -0.06, 0.12)),
    )
    for base, d in barras:
        r0 = (0.28 + 0.62 * retrac) * escala * snap
        r1 = 1.04 * escala * snap
        if r1 > r0 + 0.04:
            idx = _emitir_segmento_dungeons(
                vw, cw, tris, idx, base + d * r0, base + d * r1, esp * 0.35, esp, _AMBAR_FUNDO, _OURO_BRILHO, _BRANCO
            )
    tris.closePrimitive()


def _atualizar_susto_extras(exclam: NodePath, losango: NodePath, fase: float, escala: float) -> None:
    snap = 1.18 if fase < 0.16 else (1.0 if fase < 0.72 else max(0.0, (1.0 - fase) / 0.28))
    tam = 1.12 * escala * snap
    if tam <= 0.03:
        exclam.hide()
    else:
        exclam.show()
        exclam.setPos(0.0, -0.10, (0.76 + (0.14 if fase < 0.16 else 0.0)) * escala)
        exclam.setScale(tam, 1.0, tam * _N_COLS)
        exclam.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.16))
    if fase < 0.28:
        losango.show()
        losango.setPos(0.0, -0.02, 0.80 * escala)
        losango.setHpr(45.0, 35.0, 45.0)
        losango.setScale(0.32 * escala * (1.0 - fase / 0.34))
    else:
        losango.hide()


def emitir_sobressalto(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Reação seca Dungeons de susto: snap em 1 frame, losango voxel, hold e corte seco."""
    del pos, vel, dir_x
    topo = Vec3(anc["cabeca_topo"])
    rel_d = Vec3(anc.get("fone_dir", topo + Vec3(-1.3, 0.0, -0.6))) - topo
    rel_e = Vec3(anc.get("fone_esq", topo + Vec3(1.3, 0.0, -0.6))) - topo
    escala = max(0.75, min(1.30, float(forca)))
    raiz = NodePath("sobressalto_blockbench")
    arco_np, vdata, tris = _criar_no_arco(raiz)
    exclam = _cartao_celula(raiz, "susto_excl_bb", 8)
    losango = _criar_cubo_voxel("susto_flash_bb", _OURO_BRILHO)
    losango.reparentTo(raiz)

    def atualizar(fase: float) -> None:
        _construir_coroa_susto(vdata, tris, rel_d, rel_e, fase, escala)
        arco_np.node().markInternalBoundsStale()
        (arco_np.hide if fase >= 0.94 else arco_np.show)()
        _atualizar_susto_extras(exclam, losango, fase, escala)

    mgr.emitir_3d(
        raiz,
        topo,
        tipo_mesh="sobressalto_blockbench",
        ttl=0.30,
        scale_x=1.0 / max(0.05, float(mgr._escala_global)),
        atualizar_fase=atualizar,
    )
    atualizar(0.0)
