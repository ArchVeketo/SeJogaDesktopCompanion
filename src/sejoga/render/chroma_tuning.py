"""Calibração do color key / chroma do overlay (engine-agnóstico).

A janela layered usa color key binário do Win32: o pixel de fundo é limpo numa
cor de CHROMA com alpha zero, o shader de resolução (``resolucao_croma``) decide,
por cobertura de MSAA, se cada pixel vira superfície limpa ou o chroma exato, e
a calibração em ``janela.py`` lê o pixel limpo do framebuffer DEPOIS do tone
mapping do PBR para fechar a conta com o Win32.

A cor do chroma é CONFIGURÁVEL (``settings.window.colorkey_color``). Os defaults
abaixo reproduzem bit a bit o magenta histórico quando a cor não muda. Todos os
números aqui são CALIBRÁVEIS (validar por captura na GPU). Mantê-los fora da
lógica permite recalibrar o color key sem mexer no shader nem no Win32. Este
módulo é puro (sem Panda3D/Qt/Win32) para respeitar a fronteira do engine.
"""

from __future__ import annotations

from dataclasses import dataclass

# Cor do color key padrão em hex. É o magenta histórico (#FF00FF); o schema de
# config usa este mesmo valor como default de ``window.colorkey_color``.
CHROMA_HEX_PADRAO = "#FF00FF"

# Componente RGB (sem alpha) do chroma padrão, usado pelo shader: vec3(1,0,1).
CHROMA_MAGENTA_RGB: tuple[float, float, float] = (1.0, 0.0, 1.0)

# Cor do clear (RGBA), com alpha ZERO para preservar a cobertura MSAA que o
# chroma resolve usa. É a mesma cor que o shader escreve como chroma e a base
# do pixel que a calibração procura no framebuffer.
CHROMA_CLEAR_MAGENTA: tuple[float, float, float, float] = (1.0, 0.0, 1.0, 0.0)

# Cobertura mínima (alpha pós-MSAA) para o pixel contar como superfície; abaixo
# disso o pixel é resolvido para o chroma de fundo. 0.58 elimina a mini borda
# acinzentada/suja de pixels com cobertura muito baixa no LWA_COLORKEY binário.
COBERTURA_MINIMA = 0.58

# Epsilon que evita divisão por zero ao normalizar a cor pela cobertura parcial.
COBERTURA_EPSILON = 0.001

# Limiares de calibração do pixel de chroma no framebuffer (após o tone
# mapping), para o magenta padrão: vermelho e azul altos, verde quase nulo. Só
# esse pixel conhecido é adotado como color key.
CALIBRACAO_VERMELHO_MIN = 128
CALIBRACAO_VERDE_MAX = 20
CALIBRACAO_AZUL_MIN = 128

# DESPILL (remoção da contaminação do chroma na borda).
# Com o FBO MSAA limpo em (0, 0, 0, 0) em vez do chroma key, a divisão pela
# cobertura resolve a cor pura sem resíduo rosa/amarelo, dispensando despill.
DESPILL_FORCA = 0.0

# Cobertura acima da qual o pixel é considerado interior sólido e dispensa
# despill (evita alterar a cor do corpo longe da borda).
DESPILL_COBERTURA_CHEIA = 0.98


@dataclass(frozen=True)
class ChromaConfig:
    """Parâmetros derivados de uma cor de color key (puro, sem engine).

    Agrupa tudo que depende da cor escolhida: o RGB do chroma para o shader, o
    clear RGBA (alpha zero) e os limiares de calibração por canal usados em
    ``window._calibrate_background_key``.
    """

    rgb: tuple[float, float, float]
    clear_rgba: tuple[float, float, float, float]
    limites: tuple[tuple[int, int], ...]


def _hex_para_rgb(hex_cor: str) -> tuple[int, int, int]:
    """Converte ``#RRGGBB`` em inteiros 0-255 por canal (sem validar formato)."""
    limpo = hex_cor.lstrip("#")
    return tuple(int(limpo[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _limites_canal(valor: int) -> tuple[int, int]:
    if valor == 0:
        return 0, CALIBRACAO_VERDE_MAX - 1
    if valor == 255:
        return CALIBRACAO_VERMELHO_MIN + 1, 255
    # O tonemap e a conversão sRGB deslocam valores intermediários.
    return max(0, valor - 96), min(255, valor + 96)


def derivar_chroma(hex_cor: str = CHROMA_HEX_PADRAO) -> ChromaConfig:
    """Deriva o ``ChromaConfig`` de uma cor hex ``#RRGGBB``.

    Com a cor padrão (magenta), devolve exatamente os valores históricos:
    ``rgb=(1,0,1)``, ``clear_rgba=(1,0,1,0)`` e a calibração R>128/G<20/B>128.
    """
    r255, g255, b255 = _hex_para_rgb(hex_cor)
    rgb = (r255 / 255.0, g255 / 255.0, b255 / 255.0)
    return ChromaConfig(
        rgb=rgb,
        clear_rgba=(rgb[0], rgb[1], rgb[2], 0.0),
        limites=tuple(_limites_canal(valor) for valor in (r255, g255, b255))
    )


def pixel_e_chroma(rgb_255: tuple[int, int, int], config: ChromaConfig) -> bool:
    """Testa se um pixel 0-255 do framebuffer é o chroma calibrável.

    Para o magenta padrão equivale a ``R>128 and G<20 and B>128``.
    """
    return all(
        minimo <= valor <= maximo
        for valor, (minimo, maximo) in zip(rgb_255, config.limites, strict=True)
    )


def seguro_contra_chroma_255(
    r: int, g: int, b: int, colorkey_hex: str = CHROMA_HEX_PADRAO
) -> tuple[int, int, int]:
    """Afasta uma cor RGB 0-255 do color key pós-tonemap configurado."""
    cfg = derivar_chroma(colorkey_hex)
    kr, kg, kb = (round(c * 214) for c in cfg.rgb)
    # Verifica tanto colisão direta com o key pós-tonemap quanto a zona calibrável.
    dist_sq = (r - kr) ** 2 + (g - kg) ** 2 + (b - kb) ** 2
    if dist_sq >= 28 * 28 and not pixel_e_chroma((r, g, b), cfg):
        return (r, g, b)
    # Desloca prioritariamente o canal com menor presença no key configurado.
    canais = [r, g, b]
    idx_menor = min(range(3), key=lambda i: cfg.rgb[i])
    canais[idx_menor] = min(255, max(76, canais[idx_menor] + 68)) if canais[idx_menor] < 180 else max(0, canais[idx_menor] - 68)
    return (canais[0], canais[1], canais[2])
