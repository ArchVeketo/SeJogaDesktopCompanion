"""Calibração da dança guiada por áudio (engine-agnóstico).

Centraliza os números que viviam soltos em ``dance_motion.DanceMotion``: os
limiares de seleção de estilo (energia/grave/tempo), os tempos de dwell e de
compasso, as forças-alvo por estilo e os graus autorais de cada pose de dança
(head_bob/rock/hip_hop/breakdance), expostos como dados nomeados por junta.

Os valores são EXATAMENTE os de hoje (apenas extraídos; o movimento resultante
é bit a bit o mesmo). Espelha o estilo de ``spring_tuning.py``: constantes em
PT que explicam o PORQUÊ. Sem depender de Panda3D, Qt ou Win32.
"""

from __future__ import annotations

from math import tau

# --------------------------------------------------------------------------- #
# Suavização dos sinais de áudio e do tempo.
# --------------------------------------------------------------------------- #
#: Taxa de suavização (1 - e^(-k*dt)) da energia e do grave do áudio.
SUAVIZACAO_AUDIO = 3.0
#: Taxa de suavização do tempo (BPM) estimado.
SUAVIZACAO_TEMPO = 2.0
#: Taxa de suavização da força-alvo do estilo.
SUAVIZACAO_FORCA = 4.0
#: Taxa de suavização do acento do downbeat.
SUAVIZACAO_ACENTO = 9.0

#: BPM assumido quando o detector não informa (fallback).
TEMPO_PADRAO = 90.0
#: Faixa válida de BPM (clamp do tempo).
TEMPO_MIN = 55.0
TEMPO_MAX = 180.0
#: Faixa de rock por BPM (seleção de estilo).
TEMPO_ROCK_MIN = 110.0
TEMPO_ROCK_MAX = 170.0

#: Correção suave de fase a cada batida (fração do erro absorvida).
CORRECAO_FASE = 0.25

# --------------------------------------------------------------------------- #
# Limiares de seleção de estilo (energia/grave).
# --------------------------------------------------------------------------- #
BREAK_ENERGIA_MIN = 0.65
BREAK_GRAVE_MIN = 0.30
ROCK_ENERGIA_MIN = 0.35
ROCK_GRAVE_MAX = 0.22
HIPHOP_GRAVE_MIN = 0.12
HIPHOP_ENERGIA_MIN = 0.25

# --------------------------------------------------------------------------- #
# Dwell / fraseado por compasso.
# --------------------------------------------------------------------------- #
#: Segundos mínimos no estilo atual antes de aceitar a troca.
DWELL_MINIMO = 3.0
#: Batidas por "frase longa" usada em lean/floor (um ciclo de 16 batidas).
FRASE_BATIDAS = 16
#: Batidas por compasso (quatro tempos).
BATIDAS_POR_COMPASSO = 4
#: Comprimento do compasso em radianos de fase (4 batidas * tau).
COMPASSO_FASE = BATIDAS_POR_COMPASSO * tau

# --------------------------------------------------------------------------- #
# Passos de quatro poses (dance_poses).
# --------------------------------------------------------------------------- #
#: Fração da batida em que cai cada pose: acento (onset), sustentação,
#: recuperação e preparação. Depois da preparação o passo segue para o acento
#: do próximo (u = 1).
U_POSES = (0.0, 0.35, 0.70, 0.82)
#: Ganho de cabeça/tronco = base + energia * ganho (a energia escala o passo).
GANHO_PASSO_BASE = 0.7
GANHO_PASSO_ENERGIA = 0.3
#: Acima deste BPM o rock passa a meio-tempo: um passo a cada duas batidas.
ROCK_MEIO_TEMPO_BPM = 150.0

# --------------------------------------------------------------------------- #
# Envelope de acento por batida.
# --------------------------------------------------------------------------- #
#: Peso extra do downbeat sobre o acento da batida.
ACENTO_DOWNBEAT = 0.6
#: Base e ganho de energia do acento suavizado.
ACENTO_BASE = 0.4
ACENTO_GANHO_ENERGIA = 0.6
#: Posição da fase local (0..1) até onde há pulso senoidal cru.
PULSO_LARGURA = 0.42

# --------------------------------------------------------------------------- #
# Forças-alvo por estilo.
# --------------------------------------------------------------------------- #
FORCA_HEAD_BOB = 0.22
FORCA_HIP_HOP = 0.65
FORCA_PADRAO = 1.0

#: Amplitude base da pose (``amount = AMOUNT_BASE + energia * AMOUNT_ENERGIA``).
AMOUNT_BASE = 0.4
AMOUNT_ENERGIA = 0.6
#: Potência extra do breakdance sobre os estilos hip_hop/breakdance.
POTENCIA_BREAKDANCE = 1.6
POTENCIA_PADRAO = 1.0

# --------------------------------------------------------------------------- #
# Lean / floor / spin (envelopes por posição na frase de 16 batidas).
# --------------------------------------------------------------------------- #
LEAN_HEADBOB_BATIDAS = 2.0
LEAN_JANELA_INICIO = 7
LEAN_JANELA_FIM = 15
FLOOR_INICIO = 4
FLOOR_SUBIDA = 2
FLOOR_DESCIDA = 3
FLOOR_FIM = 15
SPIN_INICIO = 8
SPIN_SUBIDA = 4
SPIN_GRAUS = 360

# --------------------------------------------------------------------------- #
# Poses autorais por estilo (graus). Dados nomeados consumidos por
# dance_motion._montar_alvo. Os nomes seguem <ESTILO>_<JUNTA>_<EIXO>.
# Partes com movimento (sin/pulse/floor) guardam aqui só os coeficientes em
# graus; a forma da oscilação continua em dance_motion (Frente 3 redesenha).
# --------------------------------------------------------------------------- #

# head_bob: balanço de cabeça, braços abertos simétricos.
HEADBOB_HEAD_X_BASE = -4.0
HEADBOB_HEAD_X_PULSO = 7.0
HEADBOB_HEAD_Y = 12.0
HEADBOB_HEAD_Z_BASE = 4.0
HEADBOB_HEAD_Z_SIN = 3.0
HEADBOB_BODY_X = -2.0
HEADBOB_BODY_Y = 8.0
HEADBOB_BODY_Z = 5.0
HEADBOB_RARM_X = 24.0
HEADBOB_RARM_Z = 62.0
HEADBOB_LARM_X = 18.0
HEADBOB_LARM_Z = -62.0
HEADBOB_RANT_X = 28.0
HEADBOB_RANT_Z = 75.0
HEADBOB_LANT_X = 20.0
HEADBOB_LANT_Z = -70.0
HEADBOB_RHAND_X = -8.0
HEADBOB_RHAND_Z = -8.0
HEADBOB_LHAND_X = -8.0
HEADBOB_LHAND_Z = 8.0

# rock: cabeçada forte, braços caídos.
ROCK_HEAD_X_BASE = -8.0
ROCK_HEAD_X_PULSO = 25.0
ROCK_HEAD_Z = 4.0
ROCK_BODY_X_PULSO = 6.0
ROCK_BODY_Z = 2.0
ROCK_RARM_X = -10.0
ROCK_RARM_Z = -42.0
ROCK_RANT_X = -8.0
ROCK_RANT_Z = -30.0
ROCK_RHAND_X = 180.0
ROCK_LARM_X = -4.0
ROCK_LARM_Z = -62.0
ROCK_LANT_Z = 15.0

# hip_hop / breakdance (base comum): corpo gingando, braços alternados.
GROOVE_BODY_X_PULSO = 7.0
GROOVE_BODY_Z_SIN = 10.0
GROOVE_BODY_Y_SIN = 14.0
GROOVE_HEAD_X_PULSO = 10.0
GROOVE_HEAD_Z_SIN = 6.0
GROOVE_RARM_X_SIN = 16.0
GROOVE_RARM_Z_BASE = 48.0
GROOVE_RARM_Z_PULSO = 24.0
GROOVE_LARM_X_SIN = 16.0
GROOVE_LARM_Z_BASE = -48.0
GROOVE_LARM_Z_PULSO = 24.0
#: Fase lenta do corpo (sin(p * GROOVE_FASE_LENTA)).
GROOVE_FASE_LENTA = 0.5

# Antebraços cruzados do groove (aplicados em hip_hop e breakdance).
GROOVE_RANT_Z_BASE = -20.0
GROOVE_RANT_Z_PULSO = 12.0
GROOVE_LANT_Z_BASE = 20.0
GROOVE_LANT_Z_PULSO = 12.0

# breakdance: apoio no chão (modulado por floor_amount).
BREAK_RARM_X_FLOOR = -5.0
BREAK_RARM_Z_BASE = 45.0
BREAK_RANT_X_FLOOR = -3.0
BREAK_RANT_Z_BASE = -12.0
BREAK_RANT_Z_FLOOR = 5.0
BREAK_LARM_X_FLOOR = -20.0
BREAK_LARM_Z_BASE = -48.0
BREAK_LARM_Z_FLOOR = 32.0
BREAK_LANT_Z_BASE = 20.0
BREAK_LANT_Z_FLOOR = 35.0
BREAK_HEAD_X_BASE = -8.0
BREAK_HEAD_X_FLOOR = -12.0
BREAK_HEAD_Z_FLOOR = 5.0
