"""VFX autorais do estilo Blockbench (padrão) — estética Minecraft Dungeons."""

from __future__ import annotations

from functools import cache
from math import exp
from typing import TYPE_CHECKING

import gltf
from panda3d.core import (
    NodePath,
    PNMImage,
    Shader,
    StringStream,
    Texture,
    TextureStage,
    Vec3,
)

from sejoga.nucleo.recursos import assets_dir
from sejoga.render.sprites_efeitos import cartao_pixel, textura_pixel
from sejoga.render.vfx.acao_blockbench import (
    emitir_acento_danca,
    emitir_impacto_parede,
    emitir_rastro,
)
from sejoga.render.vfx.choque_blockbench import emitir_choque
from sejoga.render.vfx.emocoes_blockbench import (
    emitir_carinho,
    emitir_irritado,
    emitir_sobressalto,
    emitir_sono,
)
from sejoga.render.vfx.narrativos_blockbench import (
    emitir_brilho_estilo,
    emitir_curiosidade,
    emitir_espirro,
    emitir_estalo_fone,
    emitir_poeira_passo,
    emitir_sinal_radio,
    emitir_suor,
    emitir_suspiro,
    emitir_tontura,
    emitir_tristeza,
)

if TYPE_CHECKING:
    from sejoga.render.efeitos_street import GerenciadorEfeitosStreet


@cache
def _ativos_pouso() -> tuple[NodePath, Texture]:
    pasta = assets_dir()
    anel = NodePath(gltf.load_model(str(pasta / "model" / "impacto_chao_anel.glb")))
    atlas = pasta / "textures" / "vfx_blockbench" / "impacto_chao.png"
    imagem = PNMImage()
    if not imagem.read(StringStream(atlas.read_bytes()), atlas.name):
        raise ValueError(f"Atlas inválido: {atlas}")
    textura = textura_pixel("impacto_chao", imagem)
    textura.setFormat(Texture.FSrgbAlpha)
    # A câmera ortográfica frontal vê o piso de perfil. Projetar a profundidade
    # dos arcos na vertical da imagem preserva as posições e a oclusão em 3D.
    shader = Shader.make(
        Shader.SL_GLSL,
        """#version 130
        uniform mat4 p3d_ModelViewProjectionMatrix, p3d_ProjectionMatrix;
        uniform vec2 plano;
        in vec4 p3d_Vertex, p3d_MultiTexCoord0;
        out vec2 uv;
        void main() {
            gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
            float profundidade = plano.x + plano.y * p3d_Vertex.y;
            gl_Position += p3d_ProjectionMatrix * vec4(0, profundidade * 0.19, 0, 0);
            uv = p3d_MultiTexCoord0.xy;
        }
        """,
        """#version 130
        uniform sampler2D p3d_Texture0;
        in vec2 uv;
        out vec4 cor;
        void main() { cor = vec4(texture(p3d_Texture0, uv).rgb, 1); }
        """,
    )
    anel.setShader(shader, 3)
    return anel, textura


def _montar_camadas_pouso(
    raiz: NodePath,
    textura: Texture,
    stage: TextureStage,
    solas: tuple[tuple[Vec3, int], ...],
    centro: Vec3,
    forca: float,
) -> tuple[list[tuple[NodePath, Vec3, int, int]], list[tuple[NodePath, Vec3, int, int, int]]]:
    puffs, lascas = [], []
    for i, (sola, lado) in enumerate(solas):
        for fundo in (-1, 1):
            origem = Vec3(sola.x - centro.x, sola.y - centro.y + fundo * 0.16, 0.0)
            cartao = cartao_pixel(raiz, "puff_poeira", textura)
            cartao.setTexScale(stage, 0.125, 1.0)
            puffs.append((cartao, origem, lado, fundo))
            if forca >= 1.2:
                lasca = cartao_pixel(raiz, "lasca_piso", textura)
                lasca.setTexScale(stage, 0.125, 1.0)
                lascas.append((lasca, origem, lado, fundo, i))
    return puffs, lascas


def _atualizar_arcos(
    arcos: list[tuple[NodePath, Vec3]],
    fase: float,
    raio: float,
    forca: float,
    escala: float,
) -> None:
    expansao = 1.0 - (1.0 - fase) ** 3
    abertura = raio + (0.92 + 0.50 * forca) * escala * expansao
    quebra = max(0.0, (fase - 0.45) / 0.55)
    for i, (arco, pos_arco) in enumerate(arcos):
        resto = max(0.0, 1.0 - quebra * (1.30 + 0.15 * (i % 3)))
        if resto <= 1e-4:
            arco.hide()
            continue
        arco.show()
        arco.setPos(pos_arco.x * abertura, pos_arco.y * abertura * 0.80, 0.008)
        arco.setScale(abertura * resto, abertura * 0.80 * resto, resto)
        arco.setShaderInput("plano", pos_arco.y * abertura * 0.80, abertura * 0.80 * resto)


def _atualizar_puffs(
    puffs: list[tuple[NodePath, Vec3, int, int]],
    stage: TextureStage,
    fase: float,
    forca: float,
    escala: float,
) -> None:
    for cartao, origem, lado, fundo in puffs:
        atraso = 0.07 if fundo > 0 else 0.0
        u = max(0.0, (fase - atraso) / (1.0 - atraso))
        impulso = 1.06 + 0.35 * fundo - 0.12 * lado
        distancia = (1.0 - exp(-4.5 * u)) * impulso * forca * escala
        tamanho = (0.64 + 0.65 * min(1.0, u * 6.0)) * escala * (1.0 - 0.15 * fundo)
        cartao.setPos(origem + Vec3(lado * distancia, fundo * distancia * 0.40, tamanho * 0.36))
        cartao.setScale(tamanho * lado, 1.0, tamanho * 7.2)
        cartao.setTexOffset(stage, min(5, int(u * 6.0)) / 8.0, 0.0)
        cartao.setShaderInput("u_fade", min(1.0, (1.0 - fase) / 0.18))


def _atualizar_lascas(
    lascas: list[tuple[NodePath, Vec3, int, int, int]],
    stage: TextureStage,
    fase: float,
    escala: float,
) -> None:
    for lasca, origem, lado, fundo, i in lascas:
        if fase < 0.08:
            lasca.hide()
            continue
        u = max(0.0, (fase - 0.08) / 0.92)
        lasca.show()
        toque = 0.54 + 0.06 * fundo
        v = u if u < toque else u - toque
        salto = v * (toque - v) * 6.8 if u < toque else v * (1.0 - toque - v) * 2.0
        tamanho = max(0.01, (0.28 + i * 0.045) * escala * min(1.0, (1.0 - u) / 0.23))
        lasca.setPos(
            origem + Vec3(lado * u * (2.05 + fundo * 0.40), fundo * u * 0.42, salto + tamanho * 0.28)
        )
        lasca.setR(lado * (18.0 + u * 94.0))
        lasca.setScale(tamanho, 1.0, tamanho * 8.0)
        lasca.setTexOffset(stage, (6 + int(u * 7.0) % 2) / 8.0, 0.0)
        lasca.setShaderInput("u_fade", min(1.0, (1.0 - u) / 0.17))


def emitir_impacto_chao(
    mgr: GerenciadorEfeitosStreet,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Pouso rasante Blockbench: anel 3D no piso + puffs chunky + lascas de pedra."""
    del pos, vel, dir_x
    esq = anc.get("sola_esq")
    dir_ = anc.get("sola_dir")
    if esq is None or dir_ is None:
        return
    centro = (esq + dir_) * 0.5
    centro.z = min(esq.z, dir_.z)
    raio = max(0.40, (dir_.x - esq.x) * 0.5)
    escala = max(0.05, float(mgr._escala_global))
    raiz = NodePath("impacto_chao_blockbench")
    molde, textura = _ativos_pouso()
    anel = molde.copyTo(raiz)
    arcos = [(no, no.getPos()) for no in anel.findAllMatches("**/arco_*")]
    stage = TextureStage.getDefault()
    puffs, lascas = _montar_camadas_pouso(
        raiz, textura, stage, ((esq, -1), (dir_, 1)), centro, forca
    )

    def atualizar(fase: float) -> None:
        _atualizar_arcos(arcos, fase, raio, forca, escala)
        _atualizar_puffs(puffs, stage, fase, forca, escala)
        _atualizar_lascas(lascas, stage, fase, escala)

    mgr.emitir_3d(
        raiz,
        centro,
        tipo_mesh="impacto_chao_blockbench",
        ttl=0.50,
        scale_x=1.0 / escala,
        atualizar_fase=atualizar,
    )
    atualizar(0.0)


EMISSORES_BLOCKBENCH = {
    # 14 VFX oficiais do catálogo canônico
    "impacto_chao": emitir_impacto_chao,
    "impacto_parede": emitir_impacto_parede,
    "rastro": emitir_rastro,
    "poeira_passo": emitir_poeira_passo,
    "tontura": emitir_tontura,
    "choque": emitir_choque,
    "musica": emitir_acento_danca,
    "sinal_radio": emitir_sinal_radio,
    "carinho": emitir_carinho,
    "sono": emitir_sono,
    "sobressalto": emitir_sobressalto,
    "irritado": emitir_irritado,
    "curiosidade": emitir_curiosidade,
    "brilho_estilo": emitir_brilho_estilo,
    # 5 micro-VFX narrativos
    "suor": emitir_suor,
    "suspiro": emitir_suspiro,
    "tristeza": emitir_tristeza,
    "estalo_fone": emitir_estalo_fone,
    "espirro": emitir_espirro,
    # Aliases legados mantidos por compatibilidade
    "acento_danca": emitir_acento_danca,
    "calor": emitir_irritado,
}
