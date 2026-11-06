"""Contratos dos clipes de locomoção descritos como dados."""
import pytest

from sejoga.animacao.anim_clips import CLIPES, amostrar_clipe, amostrar_clipe_rotacoes
from sejoga.animacao.idle_clips import sample_track


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
                antes = sample_track(keys, max(0, t - .0001))[eixo]
                depois = sample_track(keys, min(clipe.duracao, t + .0001))[eixo]
                assert abs(antes - centro) < .001
                assert abs(depois - centro) < .001


def test_walk_por_dados_alterna_bracos_ao_longo_do_ciclo():
    meio = amostrar_clipe("walk", 0.25)
    volta = amostrar_clipe("walk", 0.75)
    # A passada varia ao longo do ciclo (não fica parada).
    assert meio["left-arm"] != volta["left-arm"]
    assert meio["right-arm"] != volta["right-arm"]
    # Contrabalanço: a cada instante os braços têm balanço X oposto.
    assert meio["left-arm"][0] * meio["right-arm"][0] < 0
    assert volta["left-arm"][0] * volta["right-arm"][0] < 0
    # E o braço que lidera à frente troca entre meio e volta do ciclo.
    assert (meio["left-arm"][0] > 0) != (volta["left-arm"][0] > 0)


def test_amostragem_e_ciclica_e_devolve_rotacoes():
    inicio = amostrar_clipe("walk", 0.0)
    ciclo = amostrar_clipe("walk", 1.0)
    assert inicio == ciclo
    rot = amostrar_clipe_rotacoes("walk", 0.25)
    assert rot["left-arm"].z == pytest.approx(amostrar_clipe("walk", 0.25)["left-arm"][2])
