"""Constantes calibráveis da caminhada e da corrida (balanço de braços e tronco).

Tudo em graus e como DELTA sobre ``rig_base.REPOUSO``. A fase da passada é a
mesma de ``LegMotion`` (``leg_motion.phase``): braços e pernas nunca se
dessincronizam. Valores marcados A_CONFIRMAR só a GPU valida.

FRONTEIRA: Python puro, sem engine.
"""

from __future__ import annotations

#: Sentido da contrafase braço x perna: +1 = braço direito à frente quando a
#: perna ESQUERDA vai à frente (marcha humana). Provado no grafo de cena do
#: Panda: ``setP(+a)`` no nó ``left-hip-pivot`` leva o pé para +Y (frente de
#: autoria) e ``LegPose.left = +sin(fase)``; o braço direito vai à frente com
#: ``y`` positivo. Se na GPU o braço vier junto da perna, trocar para -1.
#: A_CONFIRMAR (C42).
SINAL_BRACO_COM_PERNA = 1.0

#: Deslocamento (ciclos) que alinha o pico do clipe (t=0) ao seno da perna:
#: ``sin(fase) = cos(fase - pi/2)``.
CICLO_DESLOCAMENTO_SENO = 0.25
#: Meio ciclo: soma-se quando a contrafase é invertida (``SINAL`` = -1).
CICLO_MEIO = 0.5

# --------------------------------------------------------------------------- #
# Amplitudes (graus, valor de pico) por modo
# --------------------------------------------------------------------------- #
#: Balanço do braço para frente/trás (azimute, ``y``). A_CONFIRMAR.
BRACO_AZIMUTE_CAMINHADA = 14.0
BRACO_AZIMUTE_CORRIDA = 26.0
#: Elevação do braço (``z``): sobe ao ir para a frente, desce ao voltar.
BRACO_ELEVACAO_CAMINHADA = 4.0
BRACO_ELEVACAO_CORRIDA = 8.0
#: Flexão extra do cotovelo (``ant-arm.z``) quando o braço está à frente. Nunca
#: negativa: o cotovelo não hiperestende.
COTOVELO_CAMINHADA = 12.0
COTOVELO_CORRIDA = 30.0
#: Contra-rotação do tronco (``body.y``); o ombro do braço à frente acompanha.
TRONCO_GIRO_CAMINHADA = 3.0
TRONCO_GIRO_CORRIDA = 5.0
#: Inclinação constante do tronco para a frente (``body.x``).
TRONCO_INCLINACAO_CAMINHADA = 0.0
TRONCO_INCLINACAO_CORRIDA = 4.0
#: Quique da cabeça (``head.x``), duas vezes por ciclo: afunda a cada apoio.
CABECA_QUIQUE_CAMINHADA = 1.5
CABECA_QUIQUE_CORRIDA = 2.5
#: Contra-giro da cabeça (``head.y``): mantém o olhar à frente.
CABECA_CONTRAGIRO_CAMINHADA = 1.5
CABECA_CONTRAGIRO_CORRIDA = 2.5

# --------------------------------------------------------------------------- #
# Arraste: dedos agarrando (graus em ``fingers.z``; ``fingers2`` usa o espelho)
# --------------------------------------------------------------------------- #
#: Curl mínimo dos dedos enquanto é arrastado (mesmo valor da pose legada).
ARRASTE_DEDOS_BASE = 8.0
#: Curl extra proporcional à intensidade do arraste (0..1).
ARRASTE_DEDOS_GRIP = 24.0

# --------------------------------------------------------------------------- #
# Soltura: ao largar, os dedos abrem além do ponto e assentam (aditivo)
# --------------------------------------------------------------------------- #
#: Duração total da soltura (s); depois dela o delta some, sem salto.
SOLTURA_DURACAO_S = 0.9
#: Instante (s) e curl (graus) da abertura máxima: overshoot aberto (negativo).
SOLTURA_ABERTURA_S = 0.22
SOLTURA_ABERTURA_GRAUS = -22.0
#: Instante (s) e curl (graus) do assentamento, antes de voltar a zero.
SOLTURA_ASSENTO_S = 0.6
SOLTURA_ASSENTO_GRAUS = 4.0

# --------------------------------------------------------------------------- #
# Queda: flail em z/y (nunca em torção x) e dedos abertos
# --------------------------------------------------------------------------- #
#: Velocidade angular do flail (rad/s) e amplitudes (graus) em z (elevação).
QUEDA_FLAIL_VELOCIDADE = 8.0
QUEDA_FLAIL_Z = 10.0
#: Fração do flail em y (azimute), com o sinal de espelho (y inverte).
QUEDA_FLAIL_Y_FRACAO = 0.5
#: Flexão extra do cotovelo (fração de flail^2/pico): oscila a 2x a frequência do
#: flail, então fica pequena para não passar do limiar de jerk.
QUEDA_FLAIL_COTOVELO_FRACAO = 0.3
#: Fração do flail que balança a cabeça (z).
QUEDA_FLAIL_CABECA_FRACAO = 0.3
#: Velocidade (px/s) em que o vento satura (efeito 1.0) e inclinação da cabeça.
QUEDA_VENTO_SATURACAO = 1000.0
QUEDA_CABECA_INCLINACAO = 8.0
#: Dedos abertos na queda (curl negativo; ``fingers2`` usa o espelho).
QUEDA_DEDOS_ABERTOS = -10.0
#: Tumble leve do corpo por velocidade horizontal (graus por px/s, em body.z).
QUEDA_TUMBLE_GRAUS_POR_PX = 0.004
QUEDA_TUMBLE_MAX_GRAUS = 4.0
