"""Idles vivos: respiração + micro-movimento, suaves e distintos (FEAT-002).

Critério de produto (não o de clipe cíclico curto): os idles devem estar sempre
VIVOS (energia > 0, nenhuma personalidade congela), SUAVES (a camada de
respiração não introduz trancos) e DISTINTOS (as 9 personalidades mantêm
amplitude/ritmo próprios). O FECHAMENTO DE LOOP é verificado APENAS sobre a
camada de respiração, que é cíclica (oscilador + mola) e deve fechar sem pop.

A base procedural do idle é INTENCIONALMENTE APERIÓDICA (frequências
incomensuráveis + frases autorais de 4.8-14 s): em produção o clock só cresce e
o idle roda aberto para sempre. Por isso NÃO se aplica teste de fechamento de
loop ao idle inteiro — ele é analisado como ``loop=False`` em
``tests/analise_curvas.py``.

Sem GPU: tudo é medido sobre as curvas de ângulo em graus (reusa os detectores
de ``tests/analise_curvas.py`` e amostra ``rig.pose_idle`` num Rig em repouso).
"""

from __future__ import annotations

from math import degrees

import pytest

import analise_curvas as aa
from sejoga.animacao.idle_clips import camada_respiracao
from sejoga.animacao.respiracao import Respiracao
from sejoga.animacao.respiracao_tuning import RESPIRACAO_POR_PERSONALIDADE, parametros_de
from sejoga.nucleo.rig import ALL_GROUPS, IdlePersonality, Rig, Rotation3, pose_idle

FPS = 60.0
DT = 1.0 / FPS

#: Valor centrado de respiração usado onde um único instante basta (peito cheio).
_RESPIRACAO_ALTA = 0.85


def _amostrar_idle(personality: IdlePersonality, t: float, respiracao: float
                   ) -> dict[str, tuple[float, float, float]]:
    """Amostra o idle completo (Rig em repouso + pose_idle) em graus."""
    repouso = {g: Rotation3() for g in ALL_GROUPS}
    rig = Rig(rest=dict(repouso), current=dict(repouso))
    pose_idle(rig, t, personality, respiracao)

    return {g: (degrees(r.x), degrees(r.y), degrees(r.z)) for g, r in rig.pose().items()}


def _energia_total(personality: IdlePersonality, respiracao: float,
                   janela: float = 6.0) -> float:
    """Soma do deslocamento angular (graus) ao longo de uma janela: 0 = estático."""
    energia = 0.0
    anterior: dict[str, tuple[float, float, float]] | None = None
    n = round(janela / DT)

    for i in range(n):
        atual = _amostrar_idle(personality, i * DT, respiracao)

        if anterior is not None:
            for grupo, (x, y, z) in atual.items():
                px, py, pz = anterior.get(grupo, (0.0, 0.0, 0.0))
                energia += abs(x - px) + abs(y - py) + abs(z - pz)

        anterior = atual

    return energia


# --------------------------------------------------------------------------- #
# (a) VIVO / NÃO-ESTÁTICO — energia > 0 nas 9 personalidades.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("personality", list(IdlePersonality))
def test_idle_nunca_estatico_com_respiracao(personality: IdlePersonality) -> None:
    # Com respiração viva, nenhuma personalidade congela (energia bem acima de 0).
    energia = _energia_total(personality, _RESPIRACAO_ALTA)

    assert energia > 1.0, f"{personality.value} ficou estático demais: {energia:.3f}"


@pytest.mark.parametrize("personality", list(IdlePersonality))
def test_respiracao_adiciona_vida_ao_idle(personality: IdlePersonality) -> None:
    # A camada de respiração oscilante soma movimento perceptível ao peito.
    # Comparar com respiração parada (0) prova que a respiração é o que mantém o
    # idle vivo mesmo nos pontos de repouso das frases autorais.
    pose_sem = _amostrar_idle(personality, 0.0, 0.0)
    pose_com = _amostrar_idle(personality, 0.0, _RESPIRACAO_ALTA)

    peito_sem = pose_sem["body"][0]
    peito_com = pose_com["body"][0]

    assert peito_com != pytest.approx(peito_sem), (
        f"{personality.value}: respiração não alterou o peito"
    )


# --------------------------------------------------------------------------- #
# (b) LOOP DA RESPIRAÇÃO — a camada cíclica fecha sem pop (pos E velocidade).
#     (O idle inteiro é aperiódico de propósito; só a respiração é cíclica.)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("personality", list(RESPIRACAO_POR_PERSONALIDADE))
def test_loop_da_camada_de_respiracao_fecha_sem_pop(personality: IdlePersonality) -> None:
    parametros = parametros_de(personality)
    respira = Respiracao(
        frequencia=parametros.frequencia,
        amplitude=parametros.amplitude,
        amortecimento=1.0 - parametros.bounce,
    )

    # Aquece até o regime permanente (a mola deixa de depender do transiente).
    for _ in range(round(20.0 / DT)):
        respira.atualizar(DT)

    # Amostra UM período completo do oscilador como um ClipeAnalisavel em loop:
    # a camada de respiração aplicada ao peito (body eixo x), em graus.
    periodo = 1.0 / parametros.frequencia
    valores = [respira.centrada]
    for _ in range(round(periodo / DT)):
        valores.append(respira.atualizar(DT))

    def amostrar(t: float) -> dict[str, tuple[float, float, float]]:
        indice = min(len(valores) - 1, round(t * FPS))
        return camada_respiracao(valores[indice], parametros.amplitude)

    clipe = aa.ClipeAnalisavel(
        nome=f"respiracao-{personality.value}",
        amostrar=amostrar,
        duracao=periodo,
        loop=True,
    )
    achados = aa.analisar(clipe)

    pops = [c for c in achados if c.categoria == "LOOP"]

    assert pops == [], (
        f"camada de respiração de {personality.value} não fecha: "
        + "; ".join(c.metrica for c in pops)
    )


# --------------------------------------------------------------------------- #
# (c) SUAVIDADE — a respiração não introduz trancos (jerk) novos no idle.
#     (Trancos autorais pré-existentes de rhythm/confident no eixo z não são da
#     respiração, que só atua no eixo x de peito/ombros/cabeça.)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("personality", list(IdlePersonality))
def test_respiracao_nao_introduz_tranco(personality: IdlePersonality) -> None:
    def amostrar_com(t: float) -> dict[str, tuple[float, float, float]]:
        return _amostrar_idle(personality, t, _RESPIRACAO_ALTA)

    def amostrar_sem(t: float) -> dict[str, tuple[float, float, float]]:
        return _amostrar_idle(personality, t, 0.0)

    com = aa.ClipeAnalisavel(nome="com", amostrar=amostrar_com, duracao=30.0, loop=False)
    sem = aa.ClipeAnalisavel(nome="sem", amostrar=amostrar_sem, duracao=30.0, loop=False)

    achados_com = aa.analisar(com)
    achados_sem = aa.analisar(sem)

    def chaves_tranco(achados: list[aa.Constatacao]) -> set[tuple[str, str | None]]:
        return {(c.grupo, c.eixo) for c in achados if c.categoria == "SUAVIDADE"}

    novos = chaves_tranco(achados_com) - chaves_tranco(achados_sem)

    assert novos == set(), (
        f"{personality.value}: respiração introduziu trancos novos em {novos}"
    )


# --------------------------------------------------------------------------- #
# (d) DISTINÇÃO — as 9 personalidades não achatam no mesmo movimento.
# --------------------------------------------------------------------------- #

def test_nove_personalidades_continuam_distintas() -> None:
    # Mesmo com a mesma respiração aplicada, as silhuetas de idle diferem.
    for t in (0.0, 2.5, 5.0):
        poses = [_amostrar_idle(p, t, _RESPIRACAO_ALTA) for p in IdlePersonality]
        assert all(
            a != b for i, a in enumerate(poses) for b in poses[i + 1:]
        ), f"personalidades achatadas em t={t}"
