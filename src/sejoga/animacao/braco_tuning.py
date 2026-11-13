"""Constantes nomeadas da cadeia do braço (ombro → cotovelo → mão).

Fonte única para o IK (``ik_bracos``), a FK (``nucleo.cinematica``), o renderer e os
clamps do ``PoseResolver``. Valores marcados A_CONFIRMAR são pontos de partida
anatômicos: só o usuário, vendo o mascote na GPU, confirma se estão confortáveis
(ver ``.agents/tasks/frente3-animacao/recalibracao-gpu.md``).

FRONTEIRA: Python puro, sem engine.
"""

from __future__ import annotations

from sejoga.nucleo.cinematica_const import (
    EPSILON_DEGENERADO as EPSILON_DEGENERADO,
)
from sejoga.nucleo.cinematica_const import (
    TORCAO_BASE_ANTEBRACO_GRAUS as TORCAO_BASE_ANTEBRACO_GRAUS,
)

# --------------------------------------------------------------------------- #
# Osso base do cotovelo
# --------------------------------------------------------------------------- #
#: ``TORCAO_BASE_ANTEBRACO_GRAUS`` vem de ``nucleo/cinematica_const.py`` (ver
#: o import no topo): a FK de ``nucleo`` não importa ``animacao``.

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
#: Fração de cada extremo da faixa onde o clamp suave (tanh) amortece a chegada
#: antes do limite rígido final, evitando parada seca em gestos amplos sem
#: comprimir os 70% centrais da faixa (docs/ESTUDO_ANIMACAO_PROCEDURAL.md §4.7).
FRACAO_MARGEM_CLAMP_SUAVE = 0.15

# --------------------------------------------------------------------------- #
# IK
# --------------------------------------------------------------------------- #
#: Distância (unidades do modelo) aceitável entre a mão resultante e o alvo.
TOLERANCIA_PADRAO = 0.01
#: Sobra mínima (fração do alcance) para não esticar o braço até a singularidade.
FOLGA_ALCANCE = 1e-4
#: ``EPSILON_DEGENERADO`` também vem de ``nucleo/cinematica_const.py``.
#: Direção para onde o COTOVELO aponta, em ``alvos_bracos`` (direita, cima,
#: frente): para trás, para baixo e levemente para fora, como o cotovelo humano.
#: O antebraço dobra para a frente em torno dessa direção. A_CONFIRMAR (C2).
POLO_COTOVELO_ANATOMICO = (0.38, -0.62, -0.65)

# --------------------------------------------------------------------------- #
# Anti-atravessamento (consumido por `animacao.colisao_bracos`)
# --------------------------------------------------------------------------- #
#: Fração da meia-espessura que conta como NÚCLEO do membro. "Atravessar" = o
#: núcleo entrar num volume do corpo; encostar a casca não conta. Com a espessura
#: cheia (fração 1) só o T-pose fica livre: braço+mão (≈0.61) são do tamanho do
#: corpo e qualquer mão à frente encosta no tronco. Menor = braços mais baixos e
#: gestos mais soltos, porém mais casca dentro do corpo. A_CONFIRMAR (C4/C6).
#: Medido (gerar_oraculo_cena --sugerir): baixar só esta fração quase não solta o braço,
#: porque o limite é a caixa do tronco/quadril; a folga por caixa abaixo é a
#: alavanca que relaxa o braço. Por isso fica no valor original.
FRACAO_NUCLEO_BRACO = 0.5
#: Penetração EXTRA tolerada (u, além de ``FOLGA_PENETRACAO_U``) do núcleo do braço
#: em cada caixa do corpo. Só as caixas "moles" (camiseta e short, AABBs mais
#: largas que o tecido) têm folga; cabeça, fone e o outro braço seguem
#: estritos (folga 0).
FOLGA_EXTRA_CAIXA_U = {
    "tronco": 0.068,
    "quadril": 0.045,
    "pe_direito": 0.035,
    "pe_esquerdo": 0.035,
}
#: Passos (graus) da busca em cada grau de liberdade: finos e progressivos para
#: evitar trancos de 9°-27° num único quadro e ainda contornar mínimos locais.
PASSOS_BUSCA_GRAUS = (0.75, 2.5, 8.0)
