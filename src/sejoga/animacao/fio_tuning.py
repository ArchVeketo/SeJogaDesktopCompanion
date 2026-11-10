"""Constantes calibráveis da corda do fio do fone (ver ``fio_corda``).

Unidades em ``u`` (unidades do modelo). Coordenadas ``ANCORA_*`` estão no
referencial LOCAL do nó do GLTF (x, y, z do asset, y para cima), medidas nos
vértices da peça rígida original (``mesh18``, fone) e do aparelho (``mesh21``).
Cada constante diz o efeito de subir e de descer o valor; o checklist de GPU
(``docs/RECALIBRACAO_GPU.md``, itens C33 em diante) indica o que olhar.

FRONTEIRA: Python puro, sem engine.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Forma da corda
# --------------------------------------------------------------------------- #
#: Segmentos de cada ramo que sai de uma orelha até a junção no peito. Subir
#: deixa a dobra mais suave e custa mais cálculo; descer deixa a corda facetada.
SEGMENTOS_RAMO_ORELHA = 4
#: Segmentos da haste que vai da junção até o aparelho de música na cintura.
SEGMENTOS_HASTE = 7
#: Comprimento de cada ramo de orelha (u). A distância reta orelha-peito mede
#: ~0.30 u: subir deixa folga (corda cai mais), descer estica o ramo.
COMPRIMENTO_RAMO_ORELHA_U = 0.34
#: Comprimento da haste junção-aparelho (u). Subir faz o laço pender mais
#: baixo (até apoiar no quadril); descer deixa a haste esticada.
COMPRIMENTO_HASTE_U = 0.34
#: Meia largura visual da corda (u). Subir engrossa o fio; descer afina.
RAIO_VISUAL_FIO_U = 0.014
#: Cor do fio (RGBA 0..1), mesma cor da textura do fio original (#0B0044).
COR_FIO = (0.043, 0.0, 0.267, 1.0)

# --------------------------------------------------------------------------- #
# Âncoras (referencial local do nó do GLTF)
# --------------------------------------------------------------------------- #
#: Saída do fio na orelha, no nó ``head``: embaixo do fone, a meia distância
#: da espessura do fone. O sinal de x escolhe a orelha.
ANCORA_ORELHA_U = (0.225, 0.04, 0.0)
#: Entrada do fio no aparelho, no nó ``body``: face de cima do aparelho.
ANCORA_APARELHO_U = (0.117, 0.025, -0.1465)

# --------------------------------------------------------------------------- #
# Física
# --------------------------------------------------------------------------- #
#: Aceleração da gravidade sobre a corda (u/s²). Subir faz o fio cair e
#: balançar mais rápido (parece mais pesado); descer deixa-o flutuando.
GRAVIDADE_FIO_U = 7.0
#: Fração da velocidade que sobra após 1 s. Subir mantém o balanço por mais
#: tempo; descer assenta a corda mais depressa (parece imersa em óleo).
VELOCIDADE_RESTANTE_POR_SEGUNDO = 0.12
#: Iterações do solver de comprimento por quadro. Subir deixa a corda menos
#: elástica (mais cara); descer a deixa esticar nas puxadas.
ITERACOES_FIO = 8
#: Passo fixo da simulação (s). Passo fixo deixa a corda igual em qualquer taxa
#: de quadros. Subir deixa a corda mais mole e mais barata; descer, mais precisa
#: e mais cara.
PASSO_FIO_S = 1.0 / 60.0
#: Maior tempo de um quadro que ainda é simulado (s). Quadros mais longos são
#: cortados para a corda não disparar após um engasgo.
TEMPO_MAXIMO_QUADRO_FIO_S = 0.05
#: Salto de âncora (u) entre dois quadros que reinicia a corda em vez de
#: simular (teletransporte, troca de monitor). Subir tolera arrastos rápidos.
SALTO_REINICIO_FIO_U = 0.8
#: Fração do comprimento reto de 2 segmentos abaixo da qual a corda não
#: dobra mais (rigidez de dobra). Subir deixa a corda mais dura; descer
#: permite dobras fechadas, como um barbante.
FRACAO_MINIMA_DOBRA = 0.55
#: Quanto da correção de dobra é aplicada por iteração (0 a 1). Subir
#: endurece a dobra; 0 desliga a rigidez.
RIGIDEZ_DOBRA = 0.25
#: Assentamento inicial: iterações de simulação antes do primeiro quadro, para
#: a corda já nascer caída e não se esticar na tela.
PASSOS_ASSENTAMENTO_FIO = 150

# --------------------------------------------------------------------------- #
# Colisão (só o corpo: tronco, cabeça, quadril e braços)
# --------------------------------------------------------------------------- #
#: Raio de colisão do fio (u): folga mínima entre o centro da corda e o corpo.
#: Subir afasta o fio do tecido; descer deixa o fio colado ao corpo.
RAIO_COLISAO_FIO_U = 0.02
#: Raio das cápsulas dos braços para o fio (u). Meia espessura medida do cubo
#: do braço (0.1135) mais uma folga pequena.
RAIO_BRACO_PARA_FIO_U = 0.115
