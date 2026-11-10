"""Calibração do corpo inercial dirigido pelo mouse (engine-agnóstico).

Centraliza, em um único lugar, os números que hoje viviam soltos em
``body_motion.BodyMotion``: as molas de cada eixo do corpo, os ganhos de
impulso por tipo de interação e os alvos/clamps de cada estado (arrasto,
hover, queda) além dos clamps do snapshot de saída. Espelha o estilo de
``mola_tuning.py``/``respiracao_tuning.py``: ``@dataclass(frozen=True,
slots=True)`` e constantes nomeadas em PT que explicam o PORQUÊ.

Os valores são EXATAMENTE os de hoje (apenas extraídos, sem alterar o
movimento). Este é o ponto de calibração do usuário para o peso/resposta do
corpo. Sem depender de Panda3D, Qt ou Win32.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MolaCorpo:
  """Tensão de uma mola de eixo do corpo (frequência e amortecimento).

  - ``frequencia``: rigidez da mola em Hz (maior = mais firme/rápido).
  - ``amortecimento``: 0..1; < 1 dá balanço, perto de 1 assenta seco.
  """

  frequencia: float
  amortecimento: float


# --------------------------------------------------------------------------- #
# Molas do corpo (uma por eixo/articulação de BodyMotion).
# --------------------------------------------------------------------------- #
#: Rolagem do tronco: rigidez média, bom balanço.
MOLA_ROLL = MolaCorpo(frequencia=1.15, amortecimento=0.58)
#: Inclinação à frente/trás: um pouco mais firme que o roll.
MOLA_PITCH = MolaCorpo(frequencia=1.25, amortecimento=0.60)
#: Giro do tronco: firme e assentado.
MOLA_YAW = MolaCorpo(frequencia=1.2, amortecimento=0.78)
#: Pescoço acompanha o roll do tronco com um pouco de atraso.
MOLA_NECK_ROLL = MolaCorpo(frequencia=1.65, amortecimento=0.58)
#: Pescoço acompanha o pitch do tronco.
MOLA_NECK_PITCH = MolaCorpo(frequencia=1.75, amortecimento=0.60)
#: Compressão (agachar/encolher no impacto).
MOLA_COMPRESSION = MolaCorpo(frequencia=1.6, amortecimento=0.52)
#: Suspensão (pendurado no arrasto/queda): firme, quase sem balanço.
MOLA_SUSPENSION = MolaCorpo(frequencia=2.1, amortecimento=0.9)
#: Balanço dos membros: solto, bastante balanço.
MOLA_LIMBS = MolaCorpo(frequencia=1.1, amortecimento=0.30)


# --------------------------------------------------------------------------- #
# Ganhos de impulso por tipo de interação (velocidade somada às molas).
# --------------------------------------------------------------------------- #
#: Direção padrão do roll quando o impulso não traz direção (``click``/``poke``
#: /``double_click`` empurram o tronco levemente para um lado).
IMPULSO_DIRECAO_PADRAO = 0.35
#: Roll de um toque (click/poke/double_click): empurra o tronco de lado.
IMPULSO_CLIQUE_ROLL = 38.0
#: Pitch de um toque: o tronco cede para frente.
IMPULSO_CLIQUE_PITCH = 25.0
#: Roll de carinho (``pet``): empurrão suave, só na direção informada.
IMPULSO_PET_ROLL = 16.0
#: Roll de pancada/aterrissagem (``hit``/``land``): empurrão forte.
IMPULSO_IMPACTO_ROLL = 48.0
#: Pitch de pancada/aterrissagem: o tronco cede bastante.
IMPULSO_IMPACTO_PITCH = 28.0
#: Compressão de pancada/aterrissagem: o corpo agacha no impacto.
IMPULSO_IMPACTO_COMPRESSION = 4.5

#: Limites de normalização dos parâmetros do impulso.
IMPULSO_DIRECAO_MIN = -1.0
IMPULSO_DIRECAO_MAX = 1.0
IMPULSO_FORCA_MIN = 0.0
IMPULSO_FORCA_MAX = 2.0


@dataclass(frozen=True, slots=True)
class FaixaClamp:
  """Faixa simétrica/assimétrica de clamp (mínimo e máximo)."""

  minimo: float
  maximo: float


# --------------------------------------------------------------------------- #
# Filtro da velocidade do ponteiro e estimativa de velocidade crua.
# --------------------------------------------------------------------------- #
#: dt é limitado a este teto por quadro (evita saltos após travadas/pausas).
DT_MAXIMO = 0.1
#: Clamp da velocidade crua do ponteiro (px/s) antes de suavizar.
VELOCIDADE_PONTEIRO = FaixaClamp(minimo=-2500.0, maximo=2500.0)
#: Taxa de suavização exponencial da velocidade do ponteiro (1 - e^(-k*dt)).
PONTEIRO_SUAVIZACAO = 18.0


# --------------------------------------------------------------------------- #
# Alvos/clamps por estado: arrasto (drag).
# --------------------------------------------------------------------------- #
#: Ganho da velocidade horizontal do ponteiro no roll do arrasto.
DRAG_ROLL_GANHO = 0.012
DRAG_ROLL = FaixaClamp(minimo=-23.0, maximo=23.0)
#: Offset de roll ao arrastar pelos pés (vira de cabeça para baixo).
DRAG_ROLL_PES = 155.0
#: Offset de roll ao arrastar por um braço.
DRAG_ROLL_BRACO = 45.0
#: Pitch-base ao arrastar pelo corpo e ao arrastar por outra parte.
DRAG_PITCH_BASE_CORPO = -26.0
DRAG_PITCH_BASE_OUTRO = -9.0
#: Ganho da velocidade vertical do ponteiro no pitch do arrasto.
DRAG_PITCH_GANHO = 0.009
DRAG_PITCH = FaixaClamp(minimo=-36.0, maximo=4.0)
#: Ganho da velocidade horizontal no yaw do arrasto.
DRAG_YAW_GANHO = 0.003
DRAG_YAW = FaixaClamp(minimo=-5.0, maximo=5.0)
#: Ganho da velocidade horizontal no balanço dos membros ao arrastar.
DRAG_LIMBS_GANHO = 0.021
DRAG_LIMBS = FaixaClamp(minimo=-30.0, maximo=30.0)


# --------------------------------------------------------------------------- #
# Alvos/clamps por estado: hover (passar o mouse por cima).
# --------------------------------------------------------------------------- #
HOVER_ROLL_GANHO_PONTEIRO = 0.003
HOVER_ROLL_GANHO_OLHAR = 3.8
HOVER_ROLL = FaixaClamp(minimo=-8.0, maximo=8.0)
HOVER_PITCH_GANHO_PONTEIRO = 0.002
HOVER_PITCH_GANHO_OLHAR = 3.2
HOVER_PITCH = FaixaClamp(minimo=-6.0, maximo=6.0)
HOVER_YAW_GANHO_OLHAR = 3.0


# --------------------------------------------------------------------------- #
# Alvos/clamps por estado: queda/no ar (not grounded).
# --------------------------------------------------------------------------- #
QUEDA_ROLL_GANHO = 0.004
QUEDA_ROLL = FaixaClamp(minimo=-9.0, maximo=9.0)
QUEDA_PITCH_GANHO = 0.002
QUEDA_PITCH = FaixaClamp(minimo=-4.0, maximo=4.0)


# --------------------------------------------------------------------------- #
# Clamps e ganhos do snapshot de saída (BodyPose).
# --------------------------------------------------------------------------- #
SNAP_ROLL = FaixaClamp(minimo=-178.0, maximo=178.0)
SNAP_PITCH = FaixaClamp(minimo=-38.0, maximo=16.0)
SNAP_YAW = FaixaClamp(minimo=-7.0, maximo=7.0)
#: Cabeça = (pescoço - tronco) * ganho, clampado.
SNAP_HEAD_ROLL_GANHO = 0.65
SNAP_HEAD_ROLL = FaixaClamp(minimo=-8.0, maximo=8.0)
SNAP_HEAD_PITCH_GANHO = 0.6
#: Desconto do pitch da cabeça pela suspensão (olha para baixo ao pendurar).
SNAP_HEAD_PITCH_SUSPENSAO = 5.0
SNAP_HEAD_PITCH = FaixaClamp(minimo=-12.0, maximo=6.0)
#: Atraso do braço = -velocidade do roll * ganho, clampado.
SNAP_ARM_LAG_GANHO = 0.035
SNAP_ARM_LAG = FaixaClamp(minimo=-6.0, maximo=6.0)
SNAP_COMPRESSION = FaixaClamp(minimo=-0.12, maximo=0.20)
SNAP_HANGING = FaixaClamp(minimo=0.0, maximo=1.0)
SNAP_LIMB_SWING = FaixaClamp(minimo=-30.0, maximo=30.0)
#: Estiramento ao arrastar: mais ao segurar por uma ponta que pelo corpo.
SNAP_STRETCH_PONTA = 0.08
SNAP_STRETCH_CORPO = 0.025
SNAP_SUSPENSAO = FaixaClamp(minimo=0.0, maximo=1.0)


# --------------------------------------------------------------------------- #
# Aplicação do movimento ao TRONCO na cena (req 4, Frente 3).
# --------------------------------------------------------------------------- #
# O movimento inercial (BodyMotion/GiroCorpo) é PURO; quem o aplica ao nó da
# coluna (``flexible_rig.spine``) é o renderer. Antes, os ganhos do tronco
# (0.6 no pitch, 0.55 no roll) e os SINAIS ficavam embutidos no renderer como
# literais. Foram extraídos para cá, nomeados, para o usuário calibrar o tronco
# sem mexer na lógica.
#
# DIREÇÃO DO TRONCO (Parte 3, MEDIDA): a causa do tronco ir para o lado trocado
# era de QUADRO, não de sinal. Os pivôs da coluna moravam em ``model_np``, sem o
# giro de frente do nó raiz do asset, e o arraste aplicava pitch/roll no quadro
# do mundo: pitch e roll saíam invertidos em relação às juntas do rig. Agora os
# dois caminhos (em pé: ``rig_flexivel``; pendurado: ``renderer.apply_body_motion``)
# usam o referencial de AUTORIA, onde (medido em tests/test_tronco_quadro.py):
#   pitch NEGATIVO  -> topo do tronco/cabeça vai para a FRENTE do mascote;
#   roll POSITIVO   -> topo tomba para a DIREITA do mascote;
#   yaw             -> gira em torno da vertical (igual ao heading da cabeça).
# É a semântica que body_motion já assume (clique: pitch -= ... "cede para a
# frente"; segurar o braço direito: roll += DRAG_ROLL_BRACO, tomba para ele).
# Os SINAIS abaixo ficam em +1 (convenção de autoria); só mudam se o usuário,
# na GPU, pedir o sentido oposto como decisão de produto (C5 do recalibracao).
#: Ganho do pitch do tronco (inclina à frente/trás com o ponteiro).
TRONCO_PITCH_GANHO = 0.6
#: Ganho do roll do tronco (tomba de lado com o ponteiro).
TRONCO_ROLL_GANHO = 0.55
#: Sinal do giro (yaw/heading) do tronco, no referencial de autoria.
TRONCO_YAW_SINAL = 1.0
#: Sinal do pitch do tronco (+1: pitch negativo = frente, ver acima).
TRONCO_PITCH_SINAL = 1.0
#: Sinal do roll do tronco (+1: roll positivo = topo para a direita).
TRONCO_ROLL_SINAL = 1.0
#: Sinal do giro do tronco em relação ao OLHAR (hover). -1 = o tronco contra-gira
#: (vai para o lado oposto da cabeça, que gira para o cursor); +1 = acompanha a
#: cabeça. -1 preserva o comportamento existente. Decisão de produto: C5(c).
TRONCO_OLHAR_YAW_SINAL = -1.0
#: Altura (u, referencial de autoria) do pivô da coluna: cintura do mascote.
TRONCO_PIVO_Z = 0.44  # A_CONFIRMAR (C5)
#: Quanto o pivô da coluna desce por unidade de compressão (agachar no impacto).
TRONCO_COMPRESSAO_DESCIDA = 0.06  # A_CONFIRMAR (C5)

# --------------------------------------------------------------------------- #
# Peito durante arrasto/pendurado (Parte 4).
# --------------------------------------------------------------------------- #
#: Acima desta suspensão o renderer gira o mascote INTEIRO no ponto de pega. É a
#: ÚNICA condição do regime: o renderer e ``delta_fisica`` usam a mesma (sem
#: ``dragging`` à parte), senão o peito gira em dobro no começo da pega.
PENDURADO_LIMIAR = 0.05
#: Fração do delta de física que o PEITO ainda recebe nesse regime. 1.0 = o
#: comportamento antigo (peito gira em dobro, DEFEITO); 0.0 = peito rígido, só
#: acompanha o corpo (o usuário achou duro). 0.3 dá um balanço próprio pequeno, em
#: fase com braços e pernas. Subir se o peito parecer duro; descer se passar por
#: cima dos braços ou dessincronizar. A_CONFIRMAR na GPU (recalibracao-gpu.md, C11).
PEITO_FATOR_PENDURADO = 0.3
#: Amplitude máxima (graus, por eixo) desse balanço extra do peito. Sem o limite,
#: pegar pela perna (roll ~155°) somaria dezenas de graus. Com ~0.28 u de peito
#: acima do pivô da coluna, 8° desloca o topo ~0.04 u, dentro da folga dos braços
#: no tronco (``FOLGA_EXTRA_CAIXA_U``): o peito não sobe por cima dos braços.
#: A_CONFIRMAR na GPU (C11).
PEITO_PENDURADO_MAX_GRAUS = 8.0
