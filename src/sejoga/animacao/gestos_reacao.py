"""Gestos de reação procedurais: aceno, cutucar e alongar.

Os braços partem do repouso (IK do alvo ``idle``) e vão aos alvos de mão de
``alvos_bracos``; os termos aditivos (balanço, estocada, arco da coluna) vêm de
``gestos_tuning``. ``rig.pose_flourish`` e ``rig.pose_interaction`` delegam aqui.
"""

from __future__ import annotations

from math import exp, sin, tau

from sejoga.animacao import gestos_tuning as T
from sejoga.animacao.clipes_ocioso import sample_track
from sejoga.animacao.braco_hpr import braco_hpr_graus
from sejoga.nucleo.esqueleto import Rig

Trio = tuple[float, float, float]

#: Grupos do braço (ombro, cotovelo) por lado.
_GRUPOS_BRACO = {"right": ("right-arm", "ant-arm"), "left": ("left-arm", "ant-arm2")}


def _faixa(chaves: tuple[tuple[float, float], ...], instante: float) -> float:
    """Valor da faixa de chaves (easing quíntico) no ``instante``."""
    trio = tuple((quando, (valor, 0.0, 0.0)) for quando, valor in chaves)

    return sample_track(trio, instante)[0]


def _suave(fracao: float) -> float:
    """Degrau quíntico (0..1) com velocidade e aceleração nulas nas pontas."""
    fracao = max(0.0, min(1.0, fracao))

    return fracao**3 * (fracao * (fracao * 6.0 - 15.0) + 10.0)


def _entre(repouso: Trio, alvo: Trio, fator: float) -> Trio:
    """Interpola o HPR do repouso ao alvo."""
    return (
        repouso[0] + (alvo[0] - repouso[0]) * fator,
        repouso[1] + (alvo[1] - repouso[1]) * fator,
        repouso[2] + (alvo[2] - repouso[2]) * fator,
    )


def _balanco(instante: float) -> float:
    """Balanço amortecido do aceno em -1..1 (zero antes, depois e nas pontas)."""
    decorrido = instante - T.ACENO_BALANCO_INICIO_S
    duracao = T.ACENO_BALANCOS / T.ACENO_FREQUENCIA_HZ

    if decorrido <= 0.0 or decorrido >= duracao:
        return 0.0

    entrada = _suave(decorrido / T.ACENO_SUAVIZACAO_S)
    saida = _suave((duracao - decorrido) / T.ACENO_SUAVIZACAO_S)
    oscilacao = sin(tau * T.ACENO_FREQUENCIA_HZ * decorrido)

    return oscilacao * exp(-T.ACENO_AMORTECIMENTO * decorrido) * entrada * saida


def _entre_braco(lado: str, nome_alvo: str, fator: float, fator_cotovelo: float) -> dict[str, Trio]:
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


def _aplicar_braco(rig: Rig, lado: str, hpr: dict[str, Trio], cotovelo_extra: float = 0.0) -> None:
    """Grava ombro e cotovelo do ``lado``; o cotovelo nunca hiperestende."""
    ombro, cotovelo = _GRUPOS_BRACO[lado]
    x, y, z = hpr[ombro]
    rig.set_rotation(ombro, x=x, y=y, z=z)
    ex, ey, ez = hpr[cotovelo]
    ez += cotovelo_extra
    ez = max(0.0, ez) if lado == "right" else min(0.0, ez)
    rig.set_rotation(cotovelo, x=ex, y=ey, z=ez)


def aplicar_aceno(rig: Rig, t: float) -> None:
    """Aceno: antecipa, ergue o braço direito, balança o antebraço e desce."""
    elevacao = _faixa(T.ACENO_ELEVACAO_CHAVES, t)
    balanco = _balanco(t)
    balanco_cabeca = _balanco(t - T.ACENO_CABECA_ATRASO_S)
    # O centro do balanço fica mais estendido que o alvo: o punho não entra na cabeça.
    desvio = T.ACENO_ANTEBRACO_DESLOCAMENTO * elevacao + T.ACENO_ANTEBRACO_GRAUS * balanco
    _aplicar_braco(
        rig,
        "right",
        _entre_braco("right", "wave", elevacao, _faixa(T.ACENO_COTOVELO_CHAVES, t)),
        desvio,
    )
    # O braço esquerdo fica no repouso baixado (só o direito acena).
    _aplicar_braco(rig, "left", braco_hpr_graus("left", "idle"))
    rig.set_rotation("hand", x=T.ACENO_PULSO_GRAUS * balanco)
    rig.set_rotation("fingers", z=T.ACENO_DEDOS_GRAUS * elevacao)
    rig.set_rotation(
        "body", y=T.ACENO_CORPO_GIRO * elevacao, z=T.ACENO_CORPO_INCLINACAO * elevacao - balanco
    )
    rig.set_rotation(
        "head",
        y=T.ACENO_CABECA_GIRO * elevacao,
        z=T.ACENO_CABECA_INCLINACAO * elevacao + T.ACENO_CABECA_GRAUS * balanco_cabeca,
    )


def _entre_extremos(golpe: float, no_recuo: float, na_estocada: float) -> float:
    """Valor que vale ``no_recuo`` em golpe=-1, ``na_estocada`` em +1 e 0 em 0 (suave)."""
    quadratico = (na_estocada + no_recuo) / 2.0

    return (na_estocada - no_recuo) / 2.0 * golpe + quadratico * golpe * golpe


def aplicar_cutucar(rig: Rig, t: float, ombro: Trio, cotovelo: tuple[float, float]) -> None:
    """Cutucar: recuo, estocada, sustentação e recuperação do braço direito.

    ``ombro`` é o HPR-base de ``right-arm`` e ``cotovelo`` é ``(x, z)`` de ``ant-arm``.
    """
    recuo = T.CUTUCAR_RECUO_S
    estocada = recuo + T.CUTUCAR_ESTOCADA_S
    sustentacao = estocada + T.CUTUCAR_SUSTENTACAO_S
    chaves = (
        (0.0, 0.0),
        (recuo, -1.0),
        (estocada, 1.0),
        (sustentacao, 1.0),
        (T.CUTUCAR_DURACAO_S, 0.0),
    )
    golpe = _faixa(chaves, t)
    # 0 no recuo e em repouso, 1 na estocada: abre porta, estende cotovelo, fecha dedos.
    avanco = (golpe * golpe + golpe) / 2.0
    bx, by, bz = ombro
    rig.set_rotation(
        "right-arm",
        x=bx,
        y=by + _entre_extremos(golpe, T.CUTUCAR_OMBRO_RECUO, T.CUTUCAR_OMBRO_ESTOCADA),
        z=bz - T.CUTUCAR_OMBRO_ELEVACAO * golpe,
    )
    rig.set_rotation(
        "ant-arm", x=cotovelo[0], z=cotovelo[1] * (1.0 - T.CUTUCAR_COTOVELO_EXTENSAO * avanco)
    )
    rig.set_rotation(
        "body", x=_entre_extremos(golpe, T.CUTUCAR_TRONCO_RECUO, T.CUTUCAR_TRONCO_ESTOCADA)
    )
    rig.set_rotation(
        "head",
        x=_entre_extremos(golpe, T.CUTUCAR_CABECA_RECUO, T.CUTUCAR_CABECA_ESTOCADA),
        z=T.CUTUCAR_CABECA_ROLL * avanco,
    )
    rig.set_rotation("door", y=T.CUTUCAR_PORTA_GRAUS * avanco)
    rig.set_rotation("fingers", z=T.CUTUCAR_DEDOS_GRAUS * avanco)


def aplicar_alongar(rig: Rig, t: float) -> None:
    """Alongar: respira, sobe os dois braços, arqueia a coluna, boceja e solta."""
    elevacao = _faixa(T.ALONGAR_ELEVACAO_CHAVES, t)
    respiro = _faixa(T.ALONGAR_RESPIRO_CHAVES, t)
    queda = _faixa(T.ALONGAR_QUEDA_CHAVES, t)
    cotovelo = _faixa(T.ALONGAR_COTOVELO_CHAVES, t)
    bocejo = _faixa(T.ALONGAR_BOCEJO_CHAVES, t)

    for lado in ("right", "left"):
        _aplicar_braco(rig, lado, _entre_braco(lado, "stretch", elevacao, cotovelo))

    rig.set_rotation("body", x=-T.ALONGAR_ARCO_GRAUS * elevacao + T.ALONGAR_RESPIRO_GRAUS * respiro)
    rig.set_rotation("head", x=-T.ALONGAR_CABECA_GRAUS * elevacao)
    rig.set_rotation("door", y=T.ALONGAR_PORTA_GRAUS * bocejo)
    rig.set_rotation("shoulder", x=T.ALONGAR_OMBRO_QUEDA_GRAUS * queda)
    rig.set_rotation("shoulder2", x=-T.ALONGAR_OMBRO_QUEDA_GRAUS * queda)
