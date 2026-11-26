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
#: Rolagem do tronco: massa firme com balanço pesado.
MOLA_ROLL = MolaCorpo(frequencia=1.02, amortecimento=0.54)
#: Inclinação à frente/trás: um pouco mais firme que o roll.
MOLA_PITCH = MolaCorpo(frequencia=1.12, amortecimento=0.56)
#: Giro do tronco: firme e assentado.
MOLA_YAW = MolaCorpo(frequencia=1.15, amortecimento=0.76)
#: Pescoço acompanha o roll do tronco com um pouco de atraso.
MOLA_NECK_ROLL = MolaCorpo(frequencia=1.45, amortecimento=0.54)
#: Pescoço acompanha o pitch do tronco.
MOLA_NECK_PITCH = MolaCorpo(frequencia=1.55, amortecimento=0.56)
#: Compressão (agachar/encolher no impacto).
MOLA_COMPRESSION = MolaCorpo(frequencia=1.28, amortecimento=0.46)
#: Suspensão (pendurado no arrasto/queda): firme, com entrada orgânica de peso.
MOLA_SUSPENSION = MolaCorpo(frequencia=1.75, amortecimento=0.86)
#: Membros pendulares (braços/pernas) sob gravidade e arraste inercial: mais pesados.
MOLA_LIMBS = MolaCorpo(frequencia=0.74, amortecimento=0.34)


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
IMPULSO_IMPACTO_COMPRESSION = 11.0

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
#: Menor que antes para dar atraso físico de massa pesada ao puxar o armário.
PONTEIRO_SUAVIZACAO = 11.5


# --------------------------------------------------------------------------- #
# Alvos/clamps por estado: arrasto (drag) e pêndulo contínuo 360°+.
# --------------------------------------------------------------------------- #
#: Ganho da velocidade horizontal do ponteiro no roll do arrasto (inercial).
DRAG_ROLL_GANHO = 0.015
DRAG_ROLL = FaixaClamp(minimo=-28.0, maximo=28.0)
#: Offset de roll ao arrastar pelos pés (vira de cabeça para baixo).
DRAG_ROLL_PES = 175.0
#: Offset de roll ao arrastar por um braço.
DRAG_ROLL_BRACO = 28.0
#: Pitch-base com peso ao arrastar (peito cede para baixo).
DRAG_PITCH_BASE_CORPO = -11.5
DRAG_PITCH_BASE_OUTRO = -8.0
#: Ganho da velocidade vertical do ponteiro no pitch do arrasto.
DRAG_PITCH_GANHO = 0.021
DRAG_PITCH = FaixaClamp(minimo=-38.0, maximo=30.0)
#: Ganho da velocidade horizontal no yaw do arrasto.
DRAG_YAW_GANHO = 0.011
DRAG_YAW = FaixaClamp(minimo=-26.0, maximo=26.0)
#: Ganho da velocidade horizontal no balanço dos membros ao arrastar.
DRAG_LIMBS_GANHO = 0.046
DRAG_LIMBS = FaixaClamp(minimo=-54.0, maximo=54.0)

#: Pêndulo rígido contínuo com peso de gabinete sólido (~0.75–0.95 Hz natural).
PENDULO_GRAVIDADE_RAD_S2 = 16.0
PENDULO_ACEL_GANHO = 0.0024
PENDULO_ARRASTO_AR = 0.0105
PENDULO_AMORTECIMENTO = 2.65
PENDULO_ALAVANCA_MIN = 0.42
PENDULO_CURVA_TORQUE_GANHO = 0.00024
PENDULO_VEL_ANGULAR_MAX_RAD = 12.0
PENDULO_PASSO_MAX = 1.0 / 120.0
#: Raio efetivo padrão (px) para converter giro no soltar em velocidade de estilingue.
PENDULO_RAIO_ESTILINGUE_PX = 140.0
#: Limiar angular (graus/s) para preservar giro no salto/queda após soltar.
DRAG_VEL_ANGULAR_ARREMESSO_MIN = 35.0


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
QUEDA_ROLL_GANHO = 0.015
QUEDA_ROLL = FaixaClamp(minimo=-16.0, maximo=16.0)
QUEDA_PITCH_GANHO = 0.016
QUEDA_PITCH = FaixaClamp(minimo=-14.0, maximo=12.0)


# --------------------------------------------------------------------------- #
# Clamps e ganhos do snapshot de saída (BodyPose).
# --------------------------------------------------------------------------- #
SNAP_ROLL = FaixaClamp(minimo=-178.0, maximo=178.0)
SNAP_PITCH = FaixaClamp(minimo=-38.0, maximo=26.0)
SNAP_YAW = FaixaClamp(minimo=-26.0, maximo=26.0)
#: Cabeça = (pescoço - tronco) * ganho, clampado.
SNAP_HEAD_ROLL_GANHO = 0.65
SNAP_HEAD_ROLL = FaixaClamp(minimo=-14.0, maximo=14.0)
SNAP_HEAD_PITCH_GANHO = 0.6
#: Desconto do pitch da cabeça pela suspensão (olha para baixo ao pendurar com peso).
SNAP_HEAD_PITCH_SUSPENSAO = 9.5
SNAP_HEAD_PITCH = FaixaClamp(minimo=-16.0, maximo=14.0)
#: Atraso do braço = -velocidade do roll * ganho, clampado.
SNAP_ARM_LAG_GANHO = 0.058
SNAP_ARM_LAG = FaixaClamp(minimo=-36.0, maximo=36.0)
SNAP_COMPRESSION = FaixaClamp(minimo=-0.14, maximo=0.30)
SNAP_HANGING = FaixaClamp(minimo=0.0, maximo=1.0)
SNAP_LIMB_SWING = FaixaClamp(minimo=-46.0, maximo=46.0)
#: Estiramento ao arrastar: peso real alongando o corpo pela pega.
SNAP_STRETCH_PONTA = 0.135
SNAP_STRETCH_CORPO = 0.065
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
TRONCO_COMPRESSAO_DESCIDA = 0.015  # Mantém a camisa assentada sobre a cintura

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
PEITO_FATOR_PENDURADO = 0.52
#: Amplitude máxima (graus, por eixo) desse balanço extra do peito.
PEITO_PENDURADO_MAX_GRAUS = 18.0

# --------------------------------------------------------------------------- #
# Arraste pendurado (pega por braço/perna): membros pendem para baixo no mundo
# --------------------------------------------------------------------------- #
#: Fecha os braços perto do tronco sob ação da gravidade.
ARRASTE_PENDENTE_BRACO_Z = 7.5
#: Joga os braços "para baixo" no mundo (graus de ``right-arm.x``).
ARRASTE_PENDENTE_BRACO_X = 24.0
#: Cabeça pende com o peso, olhando para baixo no mundo (graus de ``head.x``).
ARRASTE_PENDENTE_CABECA_X = 26.0
#: Resíduo de balanço do membro pendurado.
ARRASTE_PENDENTE_OSCILACAO = 0.16

# --------------------------------------------------------------------------- #
# Giro em torno da pegada, cabeça ("meio peixe") e continuidade no arremesso.
# --------------------------------------------------------------------------- #
#: Ganho do torque de curva (produto vetorial da velocidade do ponteiro) no giro.
DRAG_CURVA_GIRO_GANHO = 0.00028
#: Amortecimento da velocidade angular do giro durante o arraste (1/s).
DRAG_GIRO_AMORTECIMENTO = 2.6
#: Limite do ângulo acumulado de giro durante curva no arraste (graus).
DRAG_GIRO_MAX_GRAUS = 145.0
#: Fator de decaimento do giro ao soltar no ar (orientação para a queda).
QUEDA_GIRO_RETORNO = 2.2
#: Limiar de velocidade do ponteiro (px/s) abaixo do qual a mão livre busca o cursor.
DRAG_ALCANCE_VEL_MAX = 180.0
#: Limiar de reversão brusca (px²/s²) para surpresa na pegada pela cabeça.
DRAG_CABECA_SURPRESA_LIMIAR = -90000.0
#: Duração (s) da sacudida curta de surpresa na pegada pela cabeça.
DRAG_CABECA_SURPRESA_DURACAO = 0.36
