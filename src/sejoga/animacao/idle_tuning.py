"""Parâmetros centralizados de idle (amplitudes, frequências, tempos).

Centraliza todos os valores que controlam o comportamento dos idles,
eliminando a duplicação entre clipes_ocioso.py, respiracao_tuning.py
e poses_base.py.

Manifesto: §2.3 — 12 princípios aplicados no idle.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Respiração por personalidade
# --------------------------------------------------------------------------- #
#: Amplitude da respiração do peito (body.x) por personalidade.
#: 1.0 = amplitude padrão; valores > 1.0 são mais visíveis.
RESPIRACAO_AMPLITUDE = {
    "calm": 1.2,       # Respiração mais visível no calm
    "curious": 1.0,
    "playful": 0.8,    # Quique já dá movimento, respiração mais sutil
    "shy": 1.1,
    "confident": 1.0,
    "street": 1.0,
    "fighter": 0.9,    # Guarda tensa, respiração contida
    "rhythm": 0.7,     # Ritmo interno domina
    "stylish": 1.0,
    "brc_stance": 1.1, # Respiração visível no peito
    "vibing": 0.6,     # Groove interno domina
}

# --------------------------------------------------------------------------- #
# Micro-ruído orgânico
# --------------------------------------------------------------------------- #
#: Frequência do micro-ruído nos braços (Hz). Cria oscilação sutil que
#: impede o idle de parecer estático entre keyframes.
MICRO_RUIDO_FREQUENCIA = 0.78  # Hz — corresponde a ~47 BPM

#: Amplitude do micro-ruído nos punhos (graus).
MICRO_RUIDO_PUNHO_AMPLITUDE = 0.5

#: Amplitude do micro-ruído nos cotovelos (grados).
MICRO_RUIDO_COTOVELO_AMPLITUDE = 2.0

# --------------------------------------------------------------------------- #
# Follow-through (atraso em cascata)
# --------------------------------------------------------------------------- #
#: Atraso do follow-through por segmento (segundos).
#: Torso atinge o topo primeiro; pescoço chega depois; ombros e cotovelos
#: descem com atraso; pontas dos dedos assentam por último.
FOLLOW_THROUGH_ATRASO = {
    "torso": 0.0,       # Referência
    "pescoço": 0.15,
    "ombros": 0.25,
    "cotovelos": 0.35,
    "punhos": 0.45,
    "dedos": 0.55,
}

# --------------------------------------------------------------------------- #
# Tempos de keyframe
# --------------------------------------------------------------------------- #
#: Duração padrão do ciclo de idle (segundos).
IDLE_CICLO_DURACAO = 10.0

#: Tempo mínimo entre keyframes (segundos) para evitar jerk excessivo.
IDLE_KEYFRAME_MINIMO = 0.7

# --------------------------------------------------------------------------- #
# Calma (calm) — melhorias
# --------------------------------------------------------------------------- #
#: Amplitude de respiração do peito aumentada de 1.6° para 2.0°.
CALM_RESPIRACAO_PEITO = 2.0

#: Micro-ruído adicional nos punhos do calm (grados).
CALM_PUNHO_RUIDO = 1.5

# --------------------------------------------------------------------------- #
# Street — gingado BRC
# --------------------------------------------------------------------------- #
#: Rotação extra de cintura (body.y) para o gingado BRC (grados).
STREET_GINGADO_CINTURA = 1.5

#: Braços mais soltos: amplitude extra do follow-through nos punhos.
STREET_BRACO_SOLTO = 3.0

# --------------------------------------------------------------------------- #
# Fighter — micro-ajustes de guarda
# --------------------------------------------------------------------------- #
#: Oscilação da guarda (grados): 2° de variação sutil.
FIGHTER_GUARD_MICRO = 2.0

#: Frequência da oscilação da guarda (Hz).
FIGHTER_GUARD_FREQ = 2.3

#: Transferência de peso nos pés (grados).
FIGHTER_PESO_PES = 1.5

# --------------------------------------------------------------------------- #
# Playful — sincronização de antenas/fones
# --------------------------------------------------------------------------- #
#: Amplitude do balanço dos fones sincronizado com o quique (grados).
PLAYFUL_FONES_BALANCO = 3.0

#: Amplitude dos dedos abrindo/fechando com o quique (grados).
PLAYFUL_DEDO_AMPLITUDE = 6.0
