"""Calibração do color key / chroma do overlay (engine-agnóstico).

A janela layered usa color key binário do Win32: o pixel de fundo é limpo numa
cor MAGENTA com alpha zero, o shader de resolução (``chroma_resolve``) decide,
por cobertura de MSAA, se cada pixel vira superfície limpa ou o chroma exato, e
a calibração em ``window.py`` lê o pixel limpo do framebuffer DEPOIS do tone
mapping do PBR para fechar a conta com o Win32.

Todos os números aqui são CALIBRÁVEIS (validar por captura na GPU). Mantê-los
fora da lógica permite recalibrar o color key sem mexer no shader nem no Win32.
Este módulo é puro (sem Panda3D/Qt/Win32) para respeitar a fronteira do engine.
"""

from __future__ import annotations

# Cor magenta do clear (RGBA), com alpha ZERO para preservar a cobertura MSAA
# que o chroma resolve usa. É a mesma cor que o shader escreve como chroma e a
# base do pixel que a calibração procura no framebuffer.
CHROMA_CLEAR_MAGENTA: tuple[float, float, float, float] = (1.0, 0.0, 1.0, 0.0)

# Componente RGB (sem alpha) do chroma, usado pelo shader: vec3(1,0,1).
CHROMA_MAGENTA_RGB: tuple[float, float, float] = (1.0, 0.0, 1.0)

# Cobertura mínima (alpha pós-MSAA) para o pixel contar como superfície; abaixo
# disso o pixel é resolvido para o chroma de fundo.
COBERTURA_MINIMA = 0.5

# Epsilon que evita divisão por zero ao normalizar a cor pela cobertura parcial.
COBERTURA_EPSILON = 0.001

# Limiares de calibração do pixel magenta no framebuffer (após o tone mapping):
# o pixel limpo tem vermelho e azul altos e verde quase nulo. Só esse pixel
# conhecido é adotado como color key.
CALIBRACAO_VERMELHO_MIN = 128
CALIBRACAO_VERDE_MAX = 20
CALIBRACAO_AZUL_MIN = 128
