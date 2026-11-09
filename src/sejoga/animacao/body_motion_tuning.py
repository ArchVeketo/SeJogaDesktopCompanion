"""Calibração do corpo inercial dirigido pelo mouse (engine-agnóstico).

Centraliza, em um único lugar, os números que hoje viviam soltos em
``body_motion.BodyMotion``: as molas de cada eixo do corpo, os ganhos de
impulso por tipo de interação e os alvos/clamps de cada estado (arrasto,
hover, queda) além dos clamps do snapshot de saída. Espelha o estilo de
``spring_tuning.py``/``respiracao_tuning.py``: ``@dataclass(frozen=True,
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
