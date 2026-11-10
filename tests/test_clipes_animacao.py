"""Contratos dos clipes de locomoção descritos como deltas (graus)."""

import pytest

from sejoga.animacao import locomocao_tuning as loc
from sejoga.animacao.clipes_animacao import (
    CLIPES,
    amostrar_clipe,
    amostrar_clipe_rotacoes,
    ciclo_da_fase,
)
from sejoga.animacao.clipes_ocioso import sample_track

EPSILON_TEMPO = 0.0001
TOLERANCIA_GRAUS = 0.001


@pytest.mark.parametrize("nome", CLIPES)
def test_tracks_fecham_com_velocidade_continua(nome):
    clipe = CLIPES[nome]
    for keys in clipe.tracks.values():
        # Ciclo fecha no mesmo valor (sem descontinuidade de posição).
        assert keys[0][1] == keys[-1][1]
        tempos = [t for t, _ in keys]
        assert tempos == sorted(set(tempos))
        for t, value in keys:
            for eixo, centro in enumerate(value):
                antes = sample_track(keys, max(0, t - EPSILON_TEMPO))[eixo]
                depois = sample_track(keys, min(clipe.duracao, t + EPSILON_TEMPO))[eixo]
                assert abs(antes - centro) < TOLERANCIA_GRAUS
                assert abs(depois - centro) < TOLERANCIA_GRAUS


@pytest.mark.parametrize("nome", CLIPES)
def test_bracos_balancam_por_y_em_contrafase_no_ciclo(nome):
    frente = amostrar_clipe(nome, 0.0)
    tras = amostrar_clipe(nome, 0.5)
    # Os dois braços trocam de lado entre t=0 e t=0.5.
    assert frente["right-arm"][1] > 0 > tras["right-arm"][1]
    # Esquerdo é o espelho: o mesmo delta y significa braço no lado oposto.
    assert frente["left-arm"][1] == frente["right-arm"][1]
    # A torção (x) não é usada no balanço.
    assert frente["right-arm"][0] == 0.0
    assert tras["left-arm"][0] == 0.0


@pytest.mark.parametrize("nome", CLIPES)
def test_cotovelo_nunca_hiperestende(nome):
    for passo in range(101):
        pose = amostrar_clipe(nome, passo / 100)
        assert pose["ant-arm"][2] >= -TOLERANCIA_GRAUS
        assert pose["ant-arm2"][2] <= TOLERANCIA_GRAUS


def test_corrida_tem_mais_amplitude_que_caminhada():
    caminhada = amostrar_clipe("walk", 0.0)
    corrida = amostrar_clipe("run", 0.0)
    assert corrida["right-arm"][1] > caminhada["right-arm"][1]
    assert corrida["ant-arm"][2] > caminhada["ant-arm"][2]


def test_amostragem_e_ciclica_e_devolve_rotacoes():
    inicio = amostrar_clipe("walk", 0.0)
    ciclo = amostrar_clipe("walk", 1.0)
    assert inicio == ciclo
    rot = amostrar_clipe_rotacoes("walk", 0.25)
    assert rot["left-arm"].y == pytest.approx(
        amostrar_clipe("walk", 0.25)["left-arm"][1]
    )


def test_cabeca_soma_quique_e_contragiro_na_mesma_junta():
    pose = amostrar_clipe("walk", 0.0)
    assert pose["head"][0] == pytest.approx(loc.CABECA_QUIQUE_CAMINHADA)
    assert pose["head"][1] == pytest.approx(-loc.CABECA_CONTRAGIRO_CAMINHADA)


def test_pico_do_clipe_coincide_com_seno_da_perna():
    # Perna esquerda à frente (sin(fase)=+1) = braço direito no pico (t=0).
    from math import pi

    assert ciclo_da_fase(pi / 2) % 1.0 == pytest.approx(0.0, abs=1e-9)
