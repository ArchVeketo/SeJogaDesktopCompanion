"""Constantes globais de animação (ângulos, tempos, amplitudes).

Centraliza todos os valores que controlam o comportamento geral da animação,
eliminando valores mágicos espalhados pelo código. Mudar um parâmetro aqui
afeta todo o sistema consistentemente.

Manifesto: §2.2 — Núcleo Soberano Padronizado.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Tempos de transição
# --------------------------------------------------------------------------- #
#: Tempo padrão de transição entre estados (segundos).
TRANSICAO_PADRAO_S = 0.3

#: Tempo mínimo de transição (segundos).
TRANSICAO_MINIMO_S = 0.1

#: Tempo máximo de transição (segundos).
TRANSICAO_MAXIMO_S = 2.0

# --------------------------------------------------------------------------- #
# Limites anatômicos
# --------------------------------------------------------------------------- #
#: Rotação máxima da cabeça em pitch (graus).
CABECA_PITCH_MAX = 30.0

#: Rotação máxima da cabeça em yaw (graus).
CABECA_YAW_MAX = 45.0

#: Rotação máxima da cabeça em roll (graus).
CABECA_ROLL_MAX = 15.0

#: Rotação máxima do tronco em pitch (graus).
TRONCO_PITCH_MAX = 20.0

#: Rotação máxima do tronco em yaw (graus).
TRONCO_YAW_MAX = 15.0

#: Rotação máxima do braço em pitch (graus).
BRACO_PITCH_MAX = 60.0

#: Rotação máxima do braço em yaw (graus).
BRACO_YAW_MAX = 30.0

# --------------------------------------------------------------------------- #
# Respiração
# --------------------------------------------------------------------------- #
#: Frequência da respiração em Hz (ciclo de 3.6s = ~16.7 RPM).
RESPIRACAO_FREQUENCIA_HZ = 1.0 / 3.6

#: Amplitude máxima da escala do peito na respiração (4.5%).
RESPIRACAO_ESCALA_MAX = 0.045

# --------------------------------------------------------------------------- #
# Porta mecânica (manifesto §3.3)
# --------------------------------------------------------------------------- #
#: Abertura máxima da porta em idle/sustentação (graus).
PORTA_IDLE_MAX = 38.0

#: Abertura máxima da porta em ejeção musical ou bote (graus).
PORTA_EJECAO_MAX = 48.0

#: Velocidade angular máxima da porta (graus/s).
PORTA_VELOCIDADE_MAX = 38.0

# --------------------------------------------------------------------------- #
# Cooldowns de interação
# --------------------------------------------------------------------------- #
#: Cooldown mínimo entre interações do mesmo tipo (segundos).
INTERACAO_COOLDOWN_MIN_S = 0.5

#: Cooldown padrão de reações curtas (clique, pet) (segundos).
REACAO_CURTA_S = 1.5

#: Cooldown de reações longas (espirro, peek) (segundos).
REACAO_LONGA_S = 9.0

# --------------------------------------------------------------------------- #
# Tentáculos
# --------------------------------------------------------------------------- #
#: Tempo de quietude para acionar tentáculos (segundos).
TENTACULOS_QUIETUDE_S = 180.0

#: Duração mínima dos tentáculos na tela (segundos).
TENTACULOS_DURACAO_MIN_S = 9.0

# --------------------------------------------------------------------------- #
# Teimosia (manifesto §1.4)
# --------------------------------------------------------------------------- #
#: Número de interrupções consecutivas para acionar teimosia.
TEIMOSIA_INTERRUPCOES = 3

#: Janela temporal para considerar interrupções "consecutivas" (segundos).
TEIMOSIA_JANELA_S = 15.0

#: Duração total da sequência de teimosia (segundos).
TEIMOSIA_DURACAO_S = 6.0

# --------------------------------------------------------------------------- #
# Dança
# --------------------------------------------------------------------------- #
#: BPM mínimo para dança.
DANCA_BPM_MIN = 55.0

#: BPM máximo para dança.
DANCA_BPM_MAX = 180.0

#: BPM padrão quando não há música detectada.
DANCA_BPM_PADRAO = 90.0

#: Tempo mínimo no estilo antes de trocar (segundos).
DANCA_DWELL_MINIMO_S = 3.0

# --------------------------------------------------------------------------- #
# Sono
# --------------------------------------------------------------------------- #
#: Tempo de idle antes de dormir (segundos). 0 = nunca dormir.
SONO_IDLE_TIMEOUT_S = 0

#: Tempo de transição para o sono (segundos).
SONO_TRANSICAO_S = 2.0
