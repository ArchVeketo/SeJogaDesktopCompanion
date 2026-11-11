"""Constantes calibráveis do estado de sono (``delta_sleep``).

Tudo em graus e segundos. O sono precisa ser lento e legível: respiração perto
de 0,2 Hz, corpo que afunda aos poucos e um cochilo raro da cabeça, sem
nenhum movimento rápido (o crossfade de entrada vem de ``SONO_TRANSICAO_S``).
"""

from __future__ import annotations

#: Frequência da respiração de sono (Hz): uma inspiração a cada ~5 s.
SONO_RESPIRACAO_HZ = 0.2
#: Quanto o peito sobe e desce na respiração (graus em body.x).
SONO_RESPIRACAO_PEITO = 1.5
#: Quanto a cabeça acompanha a respiração (graus em head.x).
SONO_RESPIRACAO_CABECA = 0.4

#: Inclinação lateral fixa do corpo dormindo (graus em body.z).
SONO_CORPO_Z_BASE = -5.0
#: Afundamento extra e lento do corpo (graus em body.z) ao longo do sono.
SONO_AFUNDA_Z = -2.0
#: Período (s) do vai-e-vem do afundamento: bem lento para não ser notado.
SONO_AFUNDA_PERIODO_S = 40.0

#: Cabeça caída do sono (graus; x negativo = pende, como já confirmado).
SONO_CABECA_X_BASE = -15.0
SONO_CABECA_Z_BASE = -10.0
#: Cochilo raro: cabeça cai um pouco mais, segura e volta (graus em head.x).
SONO_COCHILO_GRAUS = -6.0
#: Período (s) do ciclo do cochilo e seus instantes (início, fundo, volta).
SONO_COCHILO_PERIODO_S = 23.0
SONO_COCHILO_INICIO_S = 14.0
SONO_COCHILO_FUNDO_S = 16.5
SONO_COCHILO_SOLTA_S = 17.5
SONO_COCHILO_VOLTA_S = 20.0

#: Ombros caídos: braços descem um pouco (graus em right-arm.z; o esquerdo
#: usa o sinal oposto pela lei de espelho).
SONO_OMBRO_CAIDO = 3.0

#: Curl dos dedos relaxados (graus em fingers.z; fingers2 usa o espelho).
SONO_DEDOS_CURL = 6.0
#: Quanto a respiração mexe nos dedos (graus).
SONO_DEDOS_RESPIRACAO = 0.5

#: Duração mínima (s) do crossfade na entrada do sono. O mínimo de 1,2 s evita
#: que o corpo "caia" de uma vez ao adormecer.
SONO_TRANSICAO_S = 1.2

# --------------------------------------------------------------------------- #
# Modos de Sono: "em_pe", "sentado", "deitado"
# --------------------------------------------------------------------------- #
# 1. Dormir sentado: pernas dobradas à frente, corpo ligeiramente curvado,
# braços apoiados no colo / coxas.
SONO_SENTADO_COXA_GRAUS = 68.0
SONO_SENTADO_CANELA_GRAUS = -72.0
SONO_SENTADO_CORPO_X = 8.0
SONO_SENTADO_CABECA_X = -18.0
SONO_SENTADO_CABECA_Z = -5.0
SONO_SENTADO_BRACO_Z = -30.0
SONO_SENTADO_ANTEBRACO_Z = 38.0

# 2. Dormir deitado: corpo tombado no chão/barra (roll ~82°), pernas
# relaxadas com leve flexão aconchegante, braços dobrados junto ao peito.
SONO_DEITADO_ROLL = -82.0
SONO_DEITADO_COXA_GRAUS = 24.0
SONO_DEITADO_CANELA_GRAUS = -32.0
SONO_DEITADO_BRACO_Z = -18.0
SONO_DEITADO_ANTEBRACO_Z = 36.0
