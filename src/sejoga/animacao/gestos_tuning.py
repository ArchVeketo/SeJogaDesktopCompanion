"""Constantes calibráveis dos gestos de reação (aceno, cutucar e alongar).

Tudo em graus e segundos. Os braços partem do repouso baixado e vão a alvos de
mão resolvidos por IK (``arm_targets``); estas constantes só descrevem o tempo e
os termos aditivos por cima. Valores marcados A_CONFIRMAR só a GPU valida.

FRONTEIRA: Python puro, sem engine.
"""

from __future__ import annotations

Chaves = tuple[tuple[float, float], ...]

# --------------------------------------------------------------------------- #
# Aceno
# --------------------------------------------------------------------------- #
#: Duração total do aceno (s); ``AnimationController.REACTION_SECONDS`` usa o mesmo valor.
ACENO_DURACAO_S = 2.6
#: Subida do braço (0..1; o primeiro valor negativo é o recuo de antecipação),
#: sustentação e descida suave. Pares (instante em s, fração do repouso ao alvo).
ACENO_ELEVACAO_CHAVES: Chaves = (
    (0.0, 0.0),
    (0.15, -0.04),
    (0.75, 1.0),
    (2.0, 1.0),
    (2.6, 0.0),
)
#: Subida do cotovelo: igual à do ombro, mas sem o recuo de antecipação.
ACENO_COTOVELO_CHAVES: Chaves = (
    (0.0, 0.0),
    (0.15, 0.0),
    (0.75, 1.0),
    (2.0, 1.0),
    (2.6, 0.0),
)
#: Início do balanço (s), logo depois de o braço chegar ao alto.
ACENO_BALANCO_INICIO_S = 0.75
#: Número de balanços completos e frequência (Hz). Acima de ~1,8 Hz o antebraço
#: passa do que o ``PoseResolver`` consegue acompanhar.
ACENO_BALANCOS = 3
ACENO_FREQUENCIA_HZ = 1.8
#: Pico do balanço do antebraço (``ant-arm.z``, graus); decai com o amortecimento.
ACENO_ANTEBRACO_GRAUS = 22.0
#: Deslocamento do centro do balanço (``ant-arm.z``, graus; negativo = mais
#: estendido). Sem ele o punho entra na cabeça no pico de flexão. A_CONFIRMAR.
ACENO_ANTEBRACO_DESLOCAMENTO = -18.0
#: Decaimento exponencial do balanço (1/s): o último balanço fica ~40 % do primeiro.
ACENO_AMORTECIMENTO = 0.55
#: Tempo (s) de entrada e de saída suaves do balanço (sem velocidade inicial).
ACENO_SUAVIZACAO_S = 0.35
#: Pulso (``hand.x``, graus) acompanha o antebraço; palma segue para a frente (C7).
ACENO_PULSO_GRAUS = 15.0
#: Atraso (s) e pico (graus, ``head.z``) da cabeça acompanhando o balanço.
ACENO_CABECA_ATRASO_S = 0.12
ACENO_CABECA_GRAUS = 3.0
#: Termos fixos de cabeça/tronco/dedos ao acenar (graus, proporcionais à subida).
ACENO_CABECA_GIRO = 5.0
ACENO_CABECA_INCLINACAO = 4.0
ACENO_CORPO_GIRO = -3.0
ACENO_CORPO_INCLINACAO = -3.0
ACENO_DEDOS_GRAUS = -8.0

# --------------------------------------------------------------------------- #
# Cutucar
# --------------------------------------------------------------------------- #
#: Fases (s): recuo, estocada, sustentação e recuperação.
CUTUCAR_RECUO_S = 0.15
CUTUCAR_ESTOCADA_S = 0.12
CUTUCAR_SUSTENTACAO_S = 0.25
CUTUCAR_RECUPERACAO_S = 0.38
#: Duração total (s); ``AnimationController.REACTION_SECONDS`` usa o mesmo valor.
CUTUCAR_DURACAO_S = (
    CUTUCAR_RECUO_S + CUTUCAR_ESTOCADA_S + CUTUCAR_SUSTENTACAO_S + CUTUCAR_RECUPERACAO_S
)
#: Ombro (``right-arm.y``): quanto vai para trás no recuo e para a frente na estocada.
CUTUCAR_OMBRO_RECUO = -20.0
CUTUCAR_OMBRO_ESTOCADA = 30.0
#: Elevação do ombro (``right-arm.z``): z+ baixa a mão no recuo, z- a ergue na estocada.
CUTUCAR_OMBRO_ELEVACAO = 6.0
#: Fração do cotovelo (``ant-arm.z``) que se estende na estocada (1 = reto).
CUTUCAR_COTOVELO_EXTENSAO = 0.8
#: Tronco (``body.x``): recua no recuo e se inclina um pouco na estocada.
CUTUCAR_TRONCO_RECUO = -8.0
CUTUCAR_TRONCO_ESTOCADA = 4.0
#: Cabeça (``head.x``): inclina para trás no recuo e acompanha a estocada.
CUTUCAR_CABECA_RECUO = -10.0
CUTUCAR_CABECA_ESTOCADA = 6.0
#: Inclinação lateral da cabeça (``head.z``) na estocada.
CUTUCAR_CABECA_ROLL = 8.0
#: Porta (``door.y``) abre na estocada; dedos (``fingers.z``) fecham no punho.
CUTUCAR_PORTA_GRAUS = 35.0
CUTUCAR_DEDOS_GRAUS = 25.0

# --------------------------------------------------------------------------- #
# Alongar
# --------------------------------------------------------------------------- #
#: Duração total (s); ``AnimationController.REACTION_SECONDS`` usa o mesmo valor.
ALONGAR_DURACAO_S = 3.2
#: Subida dos DOIS braços (fração do repouso ao alvo): respiro, subida, sustentação
#: de ~0,8 s e descida.
ALONGAR_ELEVACAO_CHAVES: Chaves = (
    (0.0, 0.0),
    (0.4, -0.05),
    (1.3, 1.0),
    (2.1, 1.0),
    (3.0, 0.0),
    (3.2, 0.0),
)
#: Subida do cotovelo: igual à do ombro, mas sem o recuo de respiro.
ALONGAR_COTOVELO_CHAVES: Chaves = (
    (0.0, 0.0),
    (0.4, 0.0),
    (1.3, 1.0),
    (2.1, 1.0),
    (3.0, 0.0),
    (3.2, 0.0),
)
#: Respiração ao redor do alongamento: inspira ao preparar, solta ao soltar.
ALONGAR_RESPIRO_CHAVES: Chaves = (
    (0.0, 0.0),
    (0.4, -1.0),
    (2.1, -1.0),
    (2.6, 1.0),
    (3.2, 0.0),
)
#: Queda dos ombros ao soltar (fração, 0..1).
ALONGAR_QUEDA_CHAVES: Chaves = (
    (0.0, 0.0),
    (2.1, 0.0),
    (2.6, 1.0),
    (3.2, 0.0),
)
#: Bocejo: porta abre durante a sustentação e fecha antes de soltar.
ALONGAR_BOCEJO_CHAVES: Chaves = (
    (0.0, 0.0),
    (1.1, 0.0),
    (1.7, 1.0),
    (2.0, 1.0),
    (2.6, 0.0),
    (3.2, 0.0),
)
#: Arco da coluna (``body.x``, negativo = para trás) e cabeça para trás (``head.x``).
ALONGAR_ARCO_GRAUS = 10.0
ALONGAR_CABECA_GRAUS = 14.0
#: Porta aberta no bocejo (graus; limite 25 para não conflitar com os tentáculos).
ALONGAR_PORTA_GRAUS = 20.0
#: Respiração do tronco (``body.x``, graus) e queda dos ombros (``shoulder.x``).
ALONGAR_RESPIRO_GRAUS = 2.5
ALONGAR_OMBRO_QUEDA_GRAUS = 6.0
