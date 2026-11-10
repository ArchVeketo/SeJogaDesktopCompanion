"""Calibração da dança guiada por áudio (engine-agnóstico).

Centraliza os limiares de seleção de estilo (energia/grave/tempo), os tempos de
dwell e de compasso, as forças-alvo por estilo e os envelopes de lean/floor/spin.
Os graus de cada pose vivem em ``danca_frases_tuning``. Espelha o estilo de
``mola_tuning.py``: constantes em PT que explicam o PORQUÊ. Sem depender de
Panda3D, Qt ou Win32.
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

# --------------------------------------------------------------------------- #
# Forças-alvo por estilo.
# --------------------------------------------------------------------------- #
FORCA_HEAD_BOB = 0.22
FORCA_HIP_HOP = 0.65
FORCA_PADRAO = 1.0


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
#: Roll (graus, lei de autoria: positivo tomba o topo para a direita) do corpo
#: deitado no chão do breakdance. Equivale ao antigo setHpr(.., -65) no mundo.
FLOOR_ROLL_GRAUS = 65.0
#: Altura (u) do quadril, pivô do giro do breakdance (mesmo pivô do giro de corpo).
PIVO_QUADRIL_Z = 0.44
SPIN_INICIO = 8
SPIN_SUBIDA = 4
SPIN_GRAUS = 360
