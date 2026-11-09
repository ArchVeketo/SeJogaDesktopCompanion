"""Constantes nomeadas da articulação dos dedos (3 juntas por dedo, 2 no polegar).

Cada dedo do asset é um bloco único. O renderer o fatia em código (``render.
dedos_malha``) numa cadeia base → meio → ponta; aqui moram os números que
decidem quanto cada junta dobra e como ela se mexe sozinha. Ângulo POSITIVO =
dedo FECHANDO (a ponta desce com a palma para baixo), para os dois lados.
Valores marcados A_CONFIRMAR dependem de ver o mascote na GPU (ver
``.agents/tasks/frente3-animacao/recalibracao-gpu.md``, itens C15 a C19).

FRONTEIRA: Python puro, sem engine.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Malha: quais blocos viram cadeia e como são cortados
# --------------------------------------------------------------------------- #
#: Índice 0 = polegar; 1..4 = indicador, médio, anelar, mindinho (nomes ``meshN``).
MESH_DEDOS_DIREITA = (25, 26, 27, 28, 29)
MESH_DEDOS_ESQUERDA = (38, 39, 40, 41, 42)
#: Fração do comprimento de cada segmento, da raiz à ponta (soma 1). Falange
#: proximal maior que a distal, como na mão humana.
FRACOES_SEGMENTOS_DEDO = (0.40, 0.33, 0.27)
FRACOES_SEGMENTOS_POLEGAR = (0.55, 0.45)
#: Ângulo de projeto (graus) da sobreposição que tampa a cunha externa da junta:
#: ``e = (espessura/2) * tan(θ/2)``. Maior tampa dobras fortes, mas deixa uma
#: aba maior no lado interno. A_CONFIRMAR na GPU (C16).
ANGULO_PROJETO_SOBREPOSICAO_GRAUS = 55.0
#: Fração máxima do segmento vizinho que a sobreposição pode invadir.
FRACAO_MAXIMA_SOBREPOSICAO = 0.9
#: Quanto (fração do comprimento) para dentro da raiz se mede a seção que fixa o
#: pivô da primeira junta: na face da raiz o corte oblíquo do polegar é uma lasca.
FRACAO_SECAO_DA_RAIZ = 0.05

# --------------------------------------------------------------------------- #
# Distribuição da flexão entre as juntas
# --------------------------------------------------------------------------- #
#: Peso de cada junta na flexão total pedida (soma 1). O meio dobra mais.
PESOS_FLEXAO_DEDO = (0.34, 0.40, 0.26)
PESOS_FLEXAO_POLEGAR = (0.50, 0.50)
#: Limites (graus) de cada junta: (extensão máxima negativa, flexão máxima).
LIMITES_JUNTA_DEDO_GRAUS = ((-20.0, 95.0), (0.0, 105.0), (0.0, 80.0))
LIMITES_JUNTA_POLEGAR_GRAUS = ((-15.0, 70.0), (0.0, 80.0))
#: O bloco todo (nó ``fingers``) já gira com a pose; este ganho soma a dobra em
#: cascata proporcional a esse giro, para o dedo curvar em vez de girar duro.
GANHO_CASCATA_DO_BLOCO = 1.0
#: Os gestos (``FingerGestures``) pedem a flexão total do dedo em graus; a mão
#: fechada humana soma bem mais que um único pivô.
FATOR_FLEXAO_GESTO = 2.0
#: Flexão de gesto (graus) em que o movimento secundário some por completo.
FLEXAO_GESTO_REFERENCIA_GRAUS = 60.0

# --------------------------------------------------------------------------- #
# Repouso natural (mão relaxada, nunca reta como régua)
# --------------------------------------------------------------------------- #
#: Flexão de repouso (graus) por junta, antes da variação por dedo.
CURL_REPOUSO_DEDO_GRAUS = (7.0, 11.0, 7.0)
CURL_REPOUSO_POLEGAR_GRAUS = (5.0, 4.0)
#: Multiplicador do repouso por dedo (polegar, indicador ... mindinho): a mão
#: relaxada fecha um pouco mais para o lado do mindinho.
VARIACAO_REPOUSO_POR_DEDO = (0.6, 0.8, 1.0, 1.15, 1.3)

# --------------------------------------------------------------------------- #
# Movimento secundário (onda base → ponta)
# --------------------------------------------------------------------------- #
#: Frequência base (Hz) da respiração dos dedos no idle.
FREQUENCIA_SECUNDARIA_HZ = 0.35
#: Amplitude (graus) por junta com atividade 1.
AMPLITUDE_SECUNDARIA_DEDO_GRAUS = (2.5, 3.5, 3.0)
AMPLITUDE_SECUNDARIA_POLEGAR_GRAUS = (2.0, 2.5)
#: Atraso de fase (rad) de cada junta em relação à anterior: a onda sobe pelo dedo.
ATRASO_FASE_JUNTA_RAD = 0.75
#: Atraso de fase (rad) entre dedos vizinhos: a mão "ondula" como um todo.
ATRASO_FASE_DEDO_RAD = 0.55
#: Deslocamento de fase (rad) entre as mãos, para não baterem em uníssono.
DESLOCAMENTO_FASE_LADO_RAD = 0.9
#: Multiplicadores por estado (``AnimationState.value``). Ausente = 1.0.
ATIVIDADE_POR_ESTADO = {
    "sleep": 0.4, "drag": 0.7, "walk": 1.5, "run": 2.0, "fall": 2.2,
    "dance": 2.5, "wave": 3.2, "stretch": 1.8, "peek": 1.5, "hit": 1.5,
}
FREQUENCIA_POR_ESTADO = {
    "sleep": 0.6, "walk": 1.5, "run": 2.2, "fall": 1.8, "dance": 2.6,
    "wave": 3.0, "stretch": 1.2, "hit": 2.0,
}
#: Rapidez (1/s) com que o ângulo de cada junta persegue o alvo: absorve trocas
#: de estado sem salto. Maior = mais seco.
SUAVIZACAO_ANGULOS_POR_S = 14.0
#: Passo máximo de tempo (s) usado na suavização, contra quadros longos.
PASSO_MAXIMO_S = 0.05
ATIVIDADE_PADRAO = 1.0
FREQUENCIA_PADRAO = 1.0
