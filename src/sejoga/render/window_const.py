"""Constantes estruturais da janela overlay/input (``OverlayApp``).

Reúne os literais de agendamento de tarefas, margens de canto, geometria de
spawn físico, tilt de queda, timeouts da bandeja e parâmetros de input de mouse
que antes ficavam soltos em ``window.py``. São constantes do próprio módulo de
janela (lado engine Win32/Panda3D), nomeadas para dar sentido ao PORQUE sem
alterar nenhum valor. Não há dependência de Panda3D/Qt/Win32 aqui.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Agendamento de tarefas pós-inicialização (segundos).
# ---------------------------------------------------------------------------
# Pequenos delays para o Panda aplicar as propriedades de janela antes de
# reordenar o Z e calibrar o color key no framebuffer já renderizado.
DELAY_RESTAURAR_Z_ORDER = 0.15
DELAY_CALIBRAR_COLOR_KEY = 0.2

# ---------------------------------------------------------------------------
# Posição inicial no canto inferior direito (px de margem da tela).
# ---------------------------------------------------------------------------
# Folga horizontal/vertical da janela até as bordas quando não há posição
# salva (a vertical é maior para não encostar na barra de tarefas).
MARGEM_CANTO_HORIZONTAL = 32
MARGEM_CANTO_VERTICAL = 72

# ---------------------------------------------------------------------------
# Geometria de spawn na física (px).
# ---------------------------------------------------------------------------
# Deslocamento vertical do ponto de apoio dentro da janela: posiciona os pés do
# mascote acima da borda inferior (abaixo do raio de colisão).
OFFSET_APOIO_FISICO = 35

# ---------------------------------------------------------------------------
# Tilt de voo / queda (sincroniza modelo 3D com a física).
# ---------------------------------------------------------------------------
# Só inclina quando está no ar e a velocidade passa deste piso (px/s).
TILT_VELOCIDADE_MINIMA = 80
# Inclinação máxima (graus) e divisor que converte velocidade horizontal em
# ângulo de tilt.
TILT_GRAUS_MAXIMO = 20.0
TILT_DIVISOR_VELOCIDADE = 80.0
# Normalizadores da reação a colisão: direção pela velocidade horizontal e
# força pela magnitude do impacto.
COLISAO_DIVISOR_DIRECAO = 1000.0
COLISAO_DIVISOR_FORCA = 1200.0

# ---------------------------------------------------------------------------
# Notificações da bandeja (ms).
# ---------------------------------------------------------------------------
# Duração padrão dos balões de notificação do system tray.
TRAY_NOTIFICACAO_MS = 4000
# Avisos mais longos: mudanças que só valem no reinício, e atalho indisponível.
TRAY_NOTIFICACAO_REINICIO_MS = 5000
TRAY_NOTIFICACAO_ATALHO_MS = 6000

# ---------------------------------------------------------------------------
# Framebuffer da janela Panda3D.
# ---------------------------------------------------------------------------
# Bits por componente alpha/profundidade/stencil e amostras de MSAA do
# framebuffer. O alpha preserva a cobertura usada pelo chroma resolve.
FRAMEBUFFER_ALPHA_BITS = 8
FRAMEBUFFER_DEPTH_BITS = 24
FRAMEBUFFER_STENCIL_BITS = 8
FRAMEBUFFER_MULTISAMPLES = 4

# ---------------------------------------------------------------------------
# Input de mouse.
# ---------------------------------------------------------------------------
# Distância mínima (px) do duplo clique: metade da métrica do sistema, com piso
# para telas/temas que reportam um valor muito pequeno.
DOUBLE_CLICK_DISTANCIA_MINIMA = 4
# Divisor que converte a métrica do sistema (diâmetro) em raio de duplo clique.
DOUBLE_CLICK_DIVISOR_METRICA = 2
# Converte GetDoubleClickTime() (ms) em segundos.
MILISSEGUNDOS_POR_SEGUNDO = 1000.0
# Normalizadores do arraste: direção pela componente horizontal e intensidade
# pela distância percorrida (px).
DRAG_DIVISOR_DIRECAO = 80.0
DRAG_DIVISOR_INTENSIDADE = 160.0
