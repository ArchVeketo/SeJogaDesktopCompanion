"""Constantes nomeadas da cadeia do braço (ombro → cotovelo → mão).

Fonte única para o IK (``arm_ik``), a FK (``nucleo.cinematica``), o renderer e os
clamps do ``PoseResolver``. Valores marcados A_CONFIRMAR são pontos de partida
anatômicos: só o usuário, vendo o mascote na GPU, confirma se estão confortáveis
(ver ``.agents/tasks/frente3-animacao/recalibracao-gpu.md``).

FRONTEIRA: Python puro, sem engine.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Osso base do cotovelo
# --------------------------------------------------------------------------- #
#: Torção fixa (graus, em P/``Rotation3.x``) do antebraço em relação ao braço.
#: O nó do braço tem o eixo longo em ±X; a dobradiça do cotovelo é o ROLL (R) do
#: antebraço, que, sem torção, gira em torno do eixo frente-trás e abre o
#: antebraço PARA OS LADOS (para dentro do tronco). Com 90° de torção a dobradiça
#: passa a ser lateral e o antebraço dobra para a FRENTE (flexão anatômica) para
#: qualquer elevação lateral do ombro. Os gestos continuam escrevendo deltas em
#: ``ant-arm.x`` em torno desta base (somada pelo renderer e pela FK).
TORCAO_BASE_ANTEBRACO_GRAUS = 90.0

# --------------------------------------------------------------------------- #
# Limites do cotovelo (dobradiça de 1 grau de liberdade)
# --------------------------------------------------------------------------- #
#: Cotovelo reto: sem hiperextensão.
COTOVELO_MIN_GRAUS = 0.0
#: Flexão máxima do cotovelo. A_CONFIRMAR (C2).
COTOVELO_MAX_GRAUS = 145.0

# --------------------------------------------------------------------------- #
# Limites do ombro (clamps finais do PoseResolver, em graus)
# --------------------------------------------------------------------------- #
#: Elevação (R): erguido (negativo) até um pouco além de reto para baixo.
#: A_CONFIRMAR (C2/C4): faixas de partida anatômicas, não medidas na GPU.
OMBRO_ELEVACAO_MIN_GRAUS = -120.0
OMBRO_ELEVACAO_MAX_GRAUS = 110.0
#: Azimute (H): faixa ampla, contém só deriva extrema.
OMBRO_AZIMUTE_MIN_GRAUS = -120.0
OMBRO_AZIMUTE_MAX_GRAUS = 120.0

# --------------------------------------------------------------------------- #
# IK
# --------------------------------------------------------------------------- #
#: Distância (unidades do modelo) aceitável entre a mão resultante e o alvo.
TOLERANCIA_PADRAO = 0.01
#: Sobra mínima (fração do alcance) para não esticar o braço até a singularidade.
FOLGA_ALCANCE = 1e-4
#: Norma abaixo da qual um vetor é tratado como nulo (direção degenerada).
EPSILON_DEGENERADO = 1e-9
#: Direção para onde o COTOVELO aponta, em ``arm_targets`` (direita, cima,
#: frente): para trás, para baixo e levemente para fora, como o cotovelo humano.
#: O antebraço dobra para a frente em torno dessa direção. A_CONFIRMAR (C2).
POLO_COTOVELO_ANATOMICO = (0.3, -0.6, -0.75)

# --------------------------------------------------------------------------- #
# Anti-atravessamento (consumido por `animacao.colisao_bracos`)
# --------------------------------------------------------------------------- #
#: Fração da meia-espessura que conta como NÚCLEO do membro. "Atravessar" = o
#: núcleo entrar num volume do corpo; encostar a casca não conta. Com a espessura
#: cheia (fração 1) só o T-pose fica livre: braço+mão (≈0.61) são do tamanho do
#: corpo e qualquer mão à frente encosta no tronco. Menor = braços mais baixos e
#: gestos mais soltos, porém mais casca dentro do corpo. A_CONFIRMAR (C4/C6).
#: Medido (oraculo_cena --sugerir): baixar só esta fração quase não solta o braço,
#: porque o limite é a caixa do tronco/quadril; a folga por caixa abaixo é a
#: alavanca que relaxa o braço. Por isso fica no valor original.
FRACAO_NUCLEO_BRACO = 0.5
#: Penetração EXTRA tolerada (u, além de ``FOLGA_PENETRACAO_U``) do núcleo do braço
#: em cada caixa do corpo. Só as caixas "moles" (camiseta e short, AABBs mais
#: largas que o tecido) têm folga; cabeça, fone, pés e o outro braço seguem
#: estritos (folga 0). Medido com núcleo 0.5: sem folga 133 alvos livres e punho
#: no máximo 0.06 u abaixo do ombro; com tronco 0.03 / quadril 0.03, 733 alvos e
#: 0.18 u abaixo (braço pendente). Maior = braço mais solto e mais braço dentro
#: do tecido. A_CONFIRMAR na GPU (recalibracao-gpu.md, C13).
FOLGA_EXTRA_CAIXA_U = {"tronco": 0.03, "quadril": 0.03}
#: Passos (graus) da busca em cada grau de liberdade: o fino ajusta, os grossos
#: saltam mínimos locais (ex.: antebraço dobrado contra o peito). Cada passo é o
#: triplo do anterior, o bastante para sair de um mínimo local em 3 tentativas.
PASSOS_BUSCA_GRAUS = (3.0, 9.0, 27.0)
