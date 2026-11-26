"""Gestos de reação procedurais: aceno, cutucar e alongar.

Os braços partem do repouso (IK do alvo ``idle``) e vão aos alvos de mão de
``alvos_bracos``; os termos aditivos (balanço, estocada, arco da coluna) vêm de
``gestos_tuning``. ``rig.pose_flourish`` e ``rig.pose_interaction`` delegam aqui.
"""

from __future__ import annotations

from math import exp, pi, sin, tau

from sejoga.animacao import gestos_tuning as tuning_gestos
from sejoga.animacao.braco_hpr import braco_hpr_graus
from sejoga.animacao.interpolacao import amostrar_pista, suavizar_quintico
from sejoga.nucleo.esqueleto import Rig

Trio = tuple[float, float, float]

#: Grupos do braço (ombro, cotovelo) por lado.
_GRUPOS_BRACO = {"right": ("right-arm", "ant-arm"), "left": ("left-arm", "ant-arm2")}


def _faixa(chaves: tuple[tuple[float, float], ...], instante: float) -> float:
    """Valor da faixa de chaves (easing quíntico) no ``instante``."""
    trio = tuple((quando, (valor, 0.0, 0.0)) for quando, valor in chaves)

    return amostrar_pista(trio, instante)[0]


def _entre(repouso: Trio, alvo: Trio, fator: float) -> Trio:
    """Interpola o HPR do repouso ao alvo."""
    return (
        repouso[0] + (alvo[0] - repouso[0]) * fator,
        repouso[1] + (alvo[1] - repouso[1]) * fator,
        repouso[2] + (alvo[2] - repouso[2]) * fator,
    )


def _balanco(instante: float) -> float:
    """Balanço amortecido do aceno em -1..1 (zero antes, depois e nas pontas)."""
    t_ac = tuning_gestos.aceno_tuning()
    inicio = float(t_ac.get("balanco_inicio_s", tuning_gestos.ACENO_BALANCO_INICIO_S))
    balancos = float(t_ac.get("balancos", tuning_gestos.ACENO_BALANCOS))
    freq = max(0.1, float(t_ac.get("frequencia_hz", tuning_gestos.ACENO_FREQUENCIA_HZ)))
    suav = max(1e-3, float(t_ac.get("suavizacao_s", tuning_gestos.ACENO_SUAVIZACAO_S)))
    amort = float(t_ac.get("amortecimento", tuning_gestos.ACENO_AMORTECIMENTO))
    decorrido = instante - inicio
    duracao = balancos / freq

    if decorrido <= 0.0 or decorrido >= duracao:
        return 0.0

    entrada = suavizar_quintico(decorrido / suav)
    saida = suavizar_quintico((duracao - decorrido) / suav)
    oscilacao = sin(tau * freq * decorrido)

    return oscilacao * exp(-amort * decorrido) * entrada * saida


def _entre_braco(
    lado: str, nome_alvo: str, fator: float, fator_cotovelo: float
) -> dict[str, Trio]:
    """HPR do braço entre o repouso e o alvo, com fator próprio para o cotovelo.

    O cotovelo tem faixa própria (sem recuo de antecipação): o recuo cruzaria
    zero, onde o cotovelo não pode hiperestender, e criaria uma quina na curva.
    """
    ombro, cotovelo = _GRUPOS_BRACO[lado]
    repouso = braco_hpr_graus(lado, "idle")
    alvo = braco_hpr_graus(lado, nome_alvo)

    return {
        ombro: _entre(repouso[ombro], alvo[ombro], fator),
        cotovelo: _entre(repouso[cotovelo], alvo[cotovelo], fator_cotovelo),
    }


def _aplicar_braco(
    rig: Rig, lado: str, hpr: dict[str, Trio], cotovelo_extra: float = 0.0
) -> None:
    """Grava ombro e cotovelo do ``lado``; o cotovelo nunca hiperestende."""
    ombro, cotovelo = _GRUPOS_BRACO[lado]
    x, y, z = hpr[ombro]
    rig.set_rotation(ombro, x=x, y=y, z=z)
    ex, ey, ez = hpr[cotovelo]
    ez += cotovelo_extra
    ez = max(0.0, ez) if lado == "right" else min(0.0, ez)
    rig.set_rotation(cotovelo, x=ex, y=ey, z=ez)


def aplicar_defesa(
    rig: Rig, t: float, duracao: float, lado_toque: float, *,
    impacto: bool, firmeza: float,
) -> None:
    """Impacto joga o peso para trás. A cutucada recolhe o ombro tocado sem saltos."""
    fase = max(0.0, min(1.0, t / max(duracao, 0.01)))
    escala = 1.0 + firmeza * 0.25
    recuo = escala * _faixa(
        ((0.0, 0.0), (0.07, -0.18), (0.24, 1.04), (0.55, 0.42), (0.78, -0.12), (1.0, 0.0)),
        fase,
    )
    guarda = escala * _faixa(
        ((0.0, 0.0), (0.06, -0.08), (0.28, 1.04), (0.58, 0.80), (0.86, 0.04), (1.0, 0.0)),
        fase,
    )
    atraso = escala * _faixa(
        ((0.0, 0.0), (0.08, 0.0), (0.36, 1.08), (0.76, -0.10), (1.0, 0.0)),
        fase,
    )
    olhar = _faixa(((0.0, 0.0), (0.30, 1.0), (0.74, 0.92), (1.0, 0.0)), fase)
    for lado, sinal in (("right", 1.0), ("left", -1.0)):
        perto = sinal == lado_toque
        peso = guarda * (0.85 if perto else (0.58 if impacto else 0.16))
        fator_mao = 0.85 if perto else (0.65 if impacto else 0.30)
        alvo = "thrown" if impacto else "protecao"
        _aplicar_braco(rig, lado, _entre_braco(lado, alvo, peso, peso))
        rig.set_rotation("shoulder" if sinal > 0 else "shoulder2", x=-4.0 * peso, z=sinal * 6.0 * peso)
        rig.set_rotation("hand" if sinal > 0 else "hand2", x=18.0 * atraso * fator_mao, z=-sinal * 11.0 * atraso * fator_mao)
        rig.set_rotation("fingers" if sinal > 0 else "fingers2", z=sinal * (16.0 if impacto else 12.0) * peso)

    # Convenção canônica: +X joga tronco/cabeça para TRÁS no impacto; -X inclina à frente na guarda.
    rig.set_rotation("cintura", x=(4.0 if impacto else -2.0) * recuo, z=-lado_toque * 4.0 * recuo)
    rig.set_rotation("abdomen", x=(5.5 if impacto else -2.5) * recuo, y=-lado_toque * 6.0 * guarda)
    rig.set_rotation("body", x=(14.0 if impacto else -5.0) * recuo, z=-lado_toque * 13.0 * recuo)
    rig.set_rotation("peitoral", x=(5.5 if impacto else -2.0) * recuo, y=-lado_toque * (12.0 if impacto else 20.0) * guarda)
    rig.set_rotation(
        "head",
        x=(9.0 if impacto else -6.0) * guarda,
        y=lado_toque * 20.0 * olhar,
        z=lado_toque * 7.0 * recuo,
    )
    rig.set_rotation("fones", x=8.5 * atraso, z=-lado_toque * 5.5 * atraso)
    rig.set_rotation("antena-direita", x=14.0 * atraso, z=5.5 * atraso)
    rig.set_rotation("antena-esquerda", x=14.0 * atraso, z=-5.5 * atraso)
    rig.set_rotation("door", y=(16.0 if impacto else 4.0) * max(0.0, recuo))


def aplicar_aceno(rig: Rig, t: float) -> None:
    """Aceno orgânico (12 princípios): antecipação, arco amplo, follow-through e contrapeso vivo."""
    t_ac = tuning_gestos.aceno_tuning()
    elev_chaves = t_ac.get("elevacao_chaves", tuning_gestos.ACENO_ELEVACAO_CHAVES)
    cotov_chaves = t_ac.get("cotovelo_chaves", tuning_gestos.ACENO_COTOVELO_CHAVES)
    atraso_cab = float(t_ac.get("cabeca_atraso_s", tuning_gestos.ACENO_CABECA_ATRASO_S))
    elevacao = _faixa(elev_chaves, t)
    # Antecipação curta antes de erguer o braço (0..0.32s)
    antecip = sin(min(1.0, max(0.0, t / 0.34)) * pi) * (1.0 - min(1.0, elevacao * 1.4))
    # Balanço assimétrico com leve variação de cadência e follow-through no punho
    balanco = _balanco(t) * (1.0 + 0.14 * sin(t * 2.1))
    balanco_punho = _balanco(t - 0.09)
    balanco_cabeca = _balanco(t - atraso_cab)
    # O centro do balanço fica mais estendido que o alvo: o punho não entra na cabeça.
    desvio = (
        float(t_ac.get("antebraco_deslocamento", tuning_gestos.ACENO_ANTEBRACO_DESLOCAMENTO))
        * elevacao
        + float(t_ac.get("antebraco_graus", tuning_gestos.ACENO_ANTEBRACO_GRAUS)) * balanco
    )
    _aplicar_braco(
        rig,
        "right",
        _entre_braco("right", "wave", elevacao, _faixa(cotov_chaves, t)),
        desvio,
    )
    # Contrapeso vivo no braço esquerdo (acompanha o balanço do corpo, nunca estátua!)
    esq_base = braco_hpr_graus("left", "idle")
    esq_arm = esq_base["left-arm"]
    esq_ant = esq_base["ant-arm2"]
    rig.set_rotation(
        "left-arm",
        x=esq_arm[0] + 4.5 * elevacao - 3.0 * antecip,
        y=esq_arm[1] - 9.0 * elevacao + 4.0 * balanco_cabeca,
        z=esq_arm[2] + 9.5 * elevacao + 3.5 * balanco,
    )
    rig.set_rotation(
        "ant-arm2",
        x=esq_ant[0] - 4.0 * elevacao,
        y=esq_ant[1],
        z=esq_ant[2] - 14.0 * elevacao - 5.0 * balanco_cabeca,
    )
    rig.set_rotation("hand2", x=6.0 * elevacao, z=8.0 * elevacao + 4.0 * balanco_cabeca)
    rig.set_rotation("shoulder", x=-3.5 * elevacao + 2.5 * antecip, z=-5.0 * elevacao + 2.2 * balanco)
    rig.set_rotation("shoulder2", x=2.0 * elevacao, z=-3.5 * elevacao - 1.2 * balanco)
    rig.set_rotation(
        "hand",
        x=18.0 * elevacao + float(t_ac.get("pulso_graus", tuning_gestos.ACENO_PULSO_GRAUS)) * balanco_punho,
        y=6.0 * elevacao,
        z=-6.0 * elevacao + 8.0 * balanco_punho,
    )
    rig.set_rotation(
        "fingers",
        z=float(t_ac.get("dedos_graus", tuning_gestos.ACENO_DEDOS_GRAUS)) * elevacao + 4.5 * balanco_punho,
    )
    corpo_y = float(t_ac.get("corpo_giro", tuning_gestos.ACENO_CORPO_GIRO)) * elevacao
    corpo_z = float(t_ac.get("corpo_inclinacao", tuning_gestos.ACENO_CORPO_INCLINACAO)) * elevacao
    rig.set_rotation("cintura", x=-2.5 * antecip + 1.5 * elevacao, y=corpo_y * 0.4, z=corpo_z * 0.45 + 1.4 * balanco)
    rig.set_rotation("abdomen", x=-2.0 * antecip + 2.0 * elevacao, y=corpo_y * 0.55, z=corpo_z * 0.55 - 1.2 * balanco)
    rig.set_rotation("peitoral", x=-1.5 * antecip + 2.5 * elevacao, y=corpo_y * 0.75, z=corpo_z * 0.75 - 1.6 * balanco)
    rig.set_rotation(
        "body",
        x=-2.0 * antecip,
        y=corpo_y,
        z=corpo_z - 1.4 * balanco,
    )
    rig.set_rotation(
        "head",
        x=3.5 * elevacao - 3.0 * antecip + 2.0 * balanco_cabeca**2,
        y=float(t_ac.get("cabeca_giro", tuning_gestos.ACENO_CABECA_GIRO)) * elevacao + 3.5 * balanco_cabeca,
        z=float(t_ac.get("cabeca_inclinacao", tuning_gestos.ACENO_CABECA_INCLINACAO))
        * elevacao
        + float(t_ac.get("cabeca_graus", tuning_gestos.ACENO_CABECA_GRAUS))
        * balanco_cabeca,
    )
    rig.set_rotation("fones", x=-2.0 * elevacao, z=-3.5 * balanco_cabeca)
    rig.set_rotation("antena-direita", x=5.0 * elevacao, z=-5.5 * balanco_cabeca)
    rig.set_rotation("antena-esquerda", x=5.0 * elevacao, z=-5.5 * balanco_cabeca)


def _entre_extremos(golpe: float, no_recuo: float, na_estocada: float) -> float:
    """Valor que vale ``no_recuo`` em golpe=-1, ``na_estocada`` em +1 e 0 em 0 (suave)."""
    quadratico = (na_estocada + no_recuo) / 2.0

    return (na_estocada - no_recuo) / 2.0 * golpe + quadratico * golpe * golpe


def aplicar_cutucar(
    rig: Rig, t: float, ombro: Trio, cotovelo: tuple[float, float]
) -> None:
    """Cutucar: recuo, estocada, sustentação e recuperação do braço direito.

    ``ombro`` é o HPR-base de ``right-arm`` e ``cotovelo`` é ``(x, z)`` de ``ant-arm``.
    """
    tc = tuning_gestos.cutucar_tuning()
    recuo = float(tc.get("recuo_s", tuning_gestos.CUTUCAR_RECUO_S))
    estocada = recuo + float(tc.get("estocada_s", tuning_gestos.CUTUCAR_ESTOCADA_S))
    sustentacao = estocada + float(tc.get("sustentacao_s", tuning_gestos.CUTUCAR_SUSTENTACAO_S))
    dur = max(sustentacao + 0.01, float(tuning_gestos.duracoes_reacoes().get("poke", tuning_gestos.CUTUCAR_DURACAO_S)))
    chaves = (
        (0.0, 0.0),
        (recuo, -1.0),
        (estocada, 1.0),
        (sustentacao, 1.0),
        (dur, 0.0),
    )
    golpe = _faixa(chaves, t)
    golpe_atraso = _faixa(chaves, max(0.0, t - 0.055))
    # Polinômios C∞ suaves em golpe ∈ [-1, 1]: avanco (0→1 na estocada) e recuo_f (0→1 no recuo).
    avanco = (golpe * golpe + golpe) / 2.0
    recuo_f = (golpe * golpe - golpe) / 2.0
    avanco_atraso = (golpe_atraso * golpe_atraso + golpe_atraso) / 2.0
    bx, by, bz = ombro
    rig.set_rotation(
        "right-arm",
        x=bx,
        y=by
        + _entre_extremos(
            golpe,
            float(tc.get("ombro_recuo", tuning_gestos.CUTUCAR_OMBRO_RECUO)),
            float(tc.get("ombro_estocada", tuning_gestos.CUTUCAR_OMBRO_ESTOCADA)),
        ),
        z=bz
        - float(tc.get("ombro_elevacao", tuning_gestos.CUTUCAR_OMBRO_ELEVACAO)) * avanco
        - 3.0 * recuo_f,
    )
    rig.set_rotation(
        "ant-arm",
        x=cotovelo[0],
        z=cotovelo[1]
        * (1.0 - float(tc.get("cotovelo_extensao", tuning_gestos.CUTUCAR_COTOVELO_EXTENSAO)) * avanco),
    )
    # Contrapeso discreto no braço esquerdo para equilibrar a estocada
    esq_base = braco_hpr_graus("left", "idle")
    la_x, la_y, la_z = esq_base["left-arm"]
    le_x, _le_y, le_z = esq_base["ant-arm2"]
    rig.set_rotation("left-arm", x=la_x + 4.0 * avanco, y=la_y + 7.0 * golpe, z=la_z + 8.0 * avanco)
    rig.set_rotation("ant-arm2", x=le_x, z=min(0.0, le_z - 10.0 * avanco_atraso))
    rig.set_rotation("hand2", x=-6.0 * golpe_atraso, z=6.0 * avanco_atraso)
    # Convenção canônica: +X = recuo para trás, -X = estocada à frente.
    tronco_x = -_entre_extremos(
        golpe,
        float(tc.get("tronco_recuo", tuning_gestos.CUTUCAR_TRONCO_RECUO)),
        float(tc.get("tronco_estocada", tuning_gestos.CUTUCAR_TRONCO_ESTOCADA)),
    )
    rig.set_rotation("cintura", x=tronco_x * 0.45, y=-4.0 * golpe)
    rig.set_rotation("abdomen", x=tronco_x * 0.55, y=-3.0 * golpe)
    rig.set_rotation("peitoral", x=tronco_x * 0.70, y=-5.0 * golpe)
    rig.set_rotation("body", x=tronco_x)
    rig.set_rotation(
        "head",
        x=-_entre_extremos(
            golpe_atraso,
            float(tc.get("cabeca_recuo", tuning_gestos.CUTUCAR_CABECA_RECUO)),
            float(tc.get("cabeca_estocada", tuning_gestos.CUTUCAR_CABECA_ESTOCADA)),
        ),
        z=float(tc.get("cabeca_roll", tuning_gestos.CUTUCAR_CABECA_ROLL)) * avanco_atraso,
    )
    rig.set_rotation("shoulder", x=-3.5 * avanco, z=-4.5 * avanco)
    rig.set_rotation("shoulder2", x=2.0 * avanco, z=-2.5 * avanco)
    rig.set_rotation("hand", x=10.0 * golpe_atraso, z=-8.0 * avanco_atraso)
    rig.set_rotation("fones", x=-4.5 * golpe_atraso, z=-3.0 * avanco_atraso)
    rig.set_rotation("antena-direita", x=-8.0 * golpe_atraso, z=4.0 * avanco_atraso)
    rig.set_rotation("antena-esquerda", x=-8.0 * golpe_atraso, z=-4.0 * avanco_atraso)
    rig.set_rotation(
        "door",
        y=float(tc.get("porta_graus", tuning_gestos.CUTUCAR_PORTA_GRAUS)) * avanco,
    )
    rig.set_rotation(
        "fingers",
        z=float(tc.get("dedos_graus", tuning_gestos.CUTUCAR_DEDOS_GRAUS)) * avanco,
    )


def aplicar_alongar(rig: Rig, t: float) -> None:
    """Alongar: respira, sobe os dois braços, arqueia a coluna, boceja e solta."""
    ta = tuning_gestos.alongar_tuning()
    elev_chaves = ta.get("elevacao_chaves", tuning_gestos.ALONGAR_ELEVACAO_CHAVES)
    elevacao = _faixa(elev_chaves, t)
    elev_atraso = _faixa(elev_chaves, max(0.0, t - 0.11))
    respiro = _faixa(ta.get("respiro_chaves", tuning_gestos.ALONGAR_RESPIRO_CHAVES), t)
    queda = _faixa(ta.get("queda_chaves", tuning_gestos.ALONGAR_QUEDA_CHAVES), t)
    cotovelo = _faixa(ta.get("cotovelo_chaves", tuning_gestos.ALONGAR_COTOVELO_CHAVES), t)
    bocejo = _faixa(ta.get("bocejo_chaves", tuning_gestos.ALONGAR_BOCEJO_CHAVES), t)
    # Assimetria orgânica via torção de tronco, cabeça e punhos (mantendo elevação sincronizada dos braços)
    torcao = sin(t * 2.2) * 4.5 * elevacao

    _aplicar_braco(rig, "right", _entre_braco("right", "stretch", elevacao, cotovelo))
    _aplicar_braco(rig, "left", _entre_braco("left", "stretch", elevacao, cotovelo))

    arco = float(ta.get("arco_graus", tuning_gestos.ALONGAR_ARCO_GRAUS))
    resp = float(ta.get("respiro_graus", tuning_gestos.ALONGAR_RESPIRO_GRAUS))
    # Convenção canônica: +X arqueia coluna/cabeça para trás e cima ao espreguiçar.
    rig.set_rotation("cintura", x=arco * 0.35 * elevacao - resp * 0.4 * respiro, y=torcao * 0.4, z=torcao * 0.35)
    rig.set_rotation("abdomen", x=arco * 0.45 * elevacao - resp * 0.5 * respiro, y=torcao * 0.6, z=torcao * 0.45)
    rig.set_rotation("peitoral", x=arco * 0.55 * elevacao - resp * 0.6 * respiro, y=torcao * 0.85, z=torcao * 0.55)
    rig.set_rotation("body", x=arco * 0.75 * elevacao - resp * respiro, y=torcao * 0.5)
    rig.set_rotation(
        "head",
        x=float(ta.get("cabeca_graus", tuning_gestos.ALONGAR_CABECA_GRAUS)) * 0.8 * elev_atraso,
        y=-torcao * 0.4,
        z=torcao * 0.6,
    )
    rig.set_rotation(
        "door",
        y=float(ta.get("porta_graus", tuning_gestos.ALONGAR_PORTA_GRAUS)) * bocejo,
    )
    ombro_q = float(ta.get("ombro_queda_graus", tuning_gestos.ALONGAR_OMBRO_QUEDA_GRAUS))
    rig.set_rotation("shoulder", x=ombro_q * queda, z=-4.0 * elevacao)
    rig.set_rotation("shoulder2", x=ombro_q * queda, z=4.0 * elevacao)
    rig.set_rotation("hand", x=-12.0 * elev_atraso, z=-8.0 * elev_atraso)
    rig.set_rotation("hand2", x=-12.0 * elev_atraso, z=8.0 * elev_atraso)
    rig.set_rotation("fingers", z=-10.0 * elev_atraso + 6.0 * queda)
    rig.set_rotation("fingers2", z=10.0 * elev_atraso - 6.0 * queda)
    rig.set_rotation("fones", x=4.0 * elev_atraso, z=-torcao * 0.45)
    rig.set_rotation("antena-direita", x=7.0 * elev_atraso, z=-3.0 * elev_atraso - torcao * 0.5)
    rig.set_rotation("antena-esquerda", x=7.0 * elev_atraso, z=3.0 * elev_atraso - torcao * 0.5)
