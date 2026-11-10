"""Testa o IK do braço contra a FK do grafo de cena.

A FK de ``cinematica`` == Panda, provado em ``test_cinematica_oraculo``. Nada
aqui compara o IK com uma FK própria dele.
"""

from __future__ import annotations

from math import degrees, isfinite

import pytest

from sejoga.animacao import braco_tuning as tun
from sejoga.animacao import ik_bracos
from sejoga.animacao.alvos_bracos import ALVOS
from sejoga.animacao.pose_repouso import REPOUSO
from sejoga.nucleo import cinematica as cin
from sejoga.nucleo.modelo import load_model
from sejoga.nucleo.recursos import resolve_model

#: Tolerância (graus) entre ``REPOUSO`` e a saída do IK para ``ALVO_IDLE``.
TOLERANCIA_REPOUSO_GRAUS = 0.01


@pytest.fixture(scope="module")
def modelo():
    return load_model(resolve_model())


def _pose_do_lado(modelo, lado, alvo):
    alvo_lado = alvo.alvo if lado == "right" else alvo.alvo_espelhado()

    return alvo_lado, ik_bracos.braco_para(modelo, lado, alvo_lado, alvo.polo)


@pytest.mark.parametrize("lado", ["right", "left"])
@pytest.mark.parametrize("nome", sorted(ALVOS))
def test_punho_renderizado_chega_ao_alvo(modelo, lado, nome):
    alvo_lado, pose = _pose_do_lado(modelo, lado, ALVOS[nome])
    braco, antebraco = list(pose)
    punho = ik_bracos.posicao_mao_para_hpr(modelo, lado, pose[braco], pose[antebraco])

    assert punho == pytest.approx(alvo_lado, abs=ik_bracos.TOLERANCIA_PADRAO)


@pytest.mark.parametrize("nome", sorted(ALVOS))
def test_cotovelo_dentro_da_faixa_e_sem_hiperextensao(modelo, nome):
    _alvo, pose = _pose_do_lado(modelo, "right", ALVOS[nome])
    flexao = degrees(pose["ant-arm"].z)

    assert tun.COTOVELO_MIN_GRAUS <= flexao <= tun.COTOVELO_MAX_GRAUS


@pytest.mark.parametrize("nome", sorted(ALVOS))
def test_cotovelo_aponta_para_tras_do_punho(modelo, nome):
    """Polo anatômico: o cotovelo fica ATRÁS da linha ombro-punho (dobra à frente)."""
    alvo, pose = _pose_do_lado(modelo, "right", ALVOS[nome])
    ombro = cin.posicao_no(modelo, "right-arm", pose)
    cotovelo = cin.autoria_para_alvo(
        cin.subtrair(cin.posicao_no(modelo, "ant-arm", pose), ombro)
    )
    distancia = cin.norma(alvo)
    fracao = cin.produto_escalar(cotovelo, alvo) / (distancia * distancia)
    na_linha = cin.escalar(alvo, fracao)

    # Componente "frente" do cotovelo em relação à linha ombro-punho.
    assert cotovelo[2] - na_linha[2] < 0.0


def test_dobra_do_cotovelo_leva_a_mao_para_a_frente(modelo):
    """Torção-base do antebraço: flexão positiva move o punho para a FRENTE."""
    from math import radians

    from sejoga.nucleo.esqueleto import Rotation3

    reto = cin.posicao_no(modelo, "hand", {})
    dobrado = cin.posicao_no(
        modelo, "hand", {"ant-arm": Rotation3(0.0, 0.0, radians(45.0))}
    )

    assert dobrado[1] - reto[1] > 0.0  # +Y de autoria = frente


def test_lado_esquerdo_e_espelho_exato(modelo):
    for alvo in ALVOS.values():
        _a, dir_ = _pose_do_lado(modelo, "right", alvo)
        _b, esq = _pose_do_lado(modelo, "left", alvo)

        for grupo_esq, grupo_dir in (
            ("left-arm", "right-arm"),
            ("ant-arm2", "ant-arm"),
        ):
            espelho = cin.espelhar_rotacao(dir_[grupo_dir])
            obtido = esq[grupo_esq]
            assert (obtido.x, obtido.y, obtido.z) == pytest.approx(
                (espelho.x, espelho.y, espelho.z)
            )


def test_alvo_inatingivel_e_clampado_sem_nan(modelo):
    pose = ik_bracos.braco_para(modelo, "right", (5.0, 5.0, 5.0))

    for rot in pose.values():
        assert all(isfinite(v) for v in (rot.x, rot.y, rot.z))


def test_repouso_e_a_saida_do_ik_do_alvo_idle(modelo):
    pose = ik_bracos.pose_repouso_bracos(modelo)
    braco, antebraco = pose["right-arm"], pose["ant-arm"]

    assert degrees(braco.x) == pytest.approx(
        REPOUSO.BRACO_X, abs=TOLERANCIA_REPOUSO_GRAUS
    )
    assert degrees(braco.y) == pytest.approx(
        REPOUSO.BRACO_Y, abs=TOLERANCIA_REPOUSO_GRAUS
    )
    assert degrees(braco.z) == pytest.approx(
        REPOUSO.BRACO_Z, abs=TOLERANCIA_REPOUSO_GRAUS
    )
    assert degrees(antebraco.z) == pytest.approx(
        REPOUSO.ANTEBRACO_Z, abs=TOLERANCIA_REPOUSO_GRAUS
    )


def test_comprimentos_lidos_do_modelo(modelo):
    upper, forearm = ik_bracos.comprimentos_braco(modelo, "right")

    assert upper == pytest.approx(0.125, abs=1e-4)
    assert forearm == pytest.approx(0.15625, abs=1e-4)
