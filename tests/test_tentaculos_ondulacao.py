"""Ondulação dos tentáculos: onda da base à ponta, por temperamento."""

import math
import random

import pytest
from panda3d.core import NodePath, Vec3

from sejoga.nucleo.esqueleto import ALL_GROUPS, IdlePersonality, Rig, Rotation3
from sejoga.tentaculos.ondulacao import (
    ONDULACAO_AGITADA,
    ONDULACAO_CALMA,
    ONDULACAO_POR_TEMPERAMENTO,
    atraso_de_fase_por_segmento,
    deslocamento_ondulante,
)
from sejoga.tentaculos.sistema_tentaculos import (
    DEFAULT_SEGMENTS,
    TentacleDirector,
    TentaclePool,
    TentacleState,
    _base_frente,
)

ESCALA = 0.004
QUADROS_MEDICAO = 270  # 4,5 s, dentro dos 4,8 s do estado curioso
QUADROS_ASSENTAR = 90  # descarta o crescimento inicial
QUADROS_ANTES_DE_RECOLHER = 120  # 2 s, menos que os 4,8 s do estado curioso
QUADROS_BURST = 30  # 0,5 s, menos que os 0,95 s do espirro
PASSO = 1 / 60
POSICAO_TESTE = 0.7
TEMPO_TESTE = 1.3
TOLERANCIA = 1e-9
PITCH_FRENTE = Vec3(0, 0.6, 0.8)
FRENTE_PARA_CIMA = Vec3(0, 0, 1)


FRENTE_PADRAO = Vec3(0, 1, 0)


def _diretor(frente=FRENTE_PADRAO, semente=1):
    rig = Rig(rest={name: Rotation3() for name in ALL_GROUPS})
    raiz = NodePath("raiz")
    pool = TentaclePool(
        rig, raiz, raiz, [Vec3(0)], rng=random.Random(semente), unit_scale=ESCALA
    )
    diretor = TentacleDirector(
        pool, rig, raiz, raiz, None, rng=random.Random(semente + 1)
    )
    for tentaculo in pool.tentacles:
        tentaculo.reference_front = Vec3(frente)
    return diretor, pool


def test_todos_os_temperamentos_tem_tuning():
    assert set(ONDULACAO_POR_TEMPERAMENTO) == set(IdlePersonality)


def test_agitado_e_mais_rapido_e_amplo_que_o_calmo():
    assert ONDULACAO_AGITADA.frequencia_hz > ONDULACAO_CALMA.frequencia_hz
    assert ONDULACAO_AGITADA.amplitude_lateral_px > ONDULACAO_CALMA.amplitude_lateral_px
    assert ONDULACAO_AGITADA.amplitude_cima_px > ONDULACAO_CALMA.amplitude_cima_px


def test_base_nao_se_move():
    assert deslocamento_ondulante(ONDULACAO_AGITADA, 0.0, TEMPO_TESTE) == (0.0, 0.0)


def test_onda_viaja_da_base_para_a_ponta():
    tuning = ONDULACAO_AGITADA
    atraso = POSICAO_TESTE / (tuning.frequencia_hz * tuning.comprimento_onda)
    envelope = POSICAO_TESTE**tuning.expoente_envelope
    na_base = math.sin(math.tau * tuning.frequencia_hz * TEMPO_TESTE)
    lateral, _ = deslocamento_ondulante(tuning, POSICAO_TESTE, TEMPO_TESTE + atraso)
    assert lateral == pytest.approx(
        tuning.amplitude_lateral_px * envelope * na_base, abs=TOLERANCIA
    )


def test_atraso_de_fase_por_segmento_soma_o_comprimento_de_onda():
    tuning = ONDULACAO_CALMA
    total = atraso_de_fase_por_segmento(tuning, DEFAULT_SEGMENTS) * (
        DEFAULT_SEGMENTS - 1
    )
    assert total == pytest.approx(math.tau / tuning.comprimento_onda)


@pytest.mark.parametrize(
    "frente", [Vec3(0, 1, 0), Vec3(0, -1, 0), PITCH_FRENTE, FRENTE_PARA_CIMA]
)
def test_base_da_frente_e_ortonormal(frente):
    _, pool = _diretor(frente)
    lateral, f, cima = _base_frente(pool.tentacles[0])
    for eixo in (lateral, f, cima):
        assert eixo.length() == pytest.approx(1.0)
    assert lateral.dot(f) == pytest.approx(0.0, abs=TOLERANCIA)
    assert lateral.dot(cima) == pytest.approx(0.0, abs=TOLERANCIA)
    assert f.dot(cima) == pytest.approx(0.0, abs=TOLERANCIA)


def _amplitude_lateral_da_ponta(personalidade):
    diretor, pool = _diretor()
    diretor.trigger_curious()
    pontas = []
    for quadro in range(QUADROS_MEDICAO):
        diretor.update(PASSO, 0, personalidade)
        for tentaculo in pool.tentacles:
            tentaculo.impulse_chance = 0.0
        if quadro > QUADROS_ASSENTAR:
            pontas.append(pool.tentacles[0].segments[-1].pos.x)
    return max(pontas) - min(pontas)


def test_agitado_balanca_mais_a_ponta_que_o_calmo():
    assert _amplitude_lateral_da_ponta(
        IdlePersonality.PLAYFUL
    ) > _amplitude_lateral_da_ponta(IdlePersonality.CALM)


def test_personalidade_troca_o_tuning_do_tentaculo():
    diretor, pool = _diretor()
    diretor.update(PASSO, 0, IdlePersonality.PLAYFUL)
    assert pool.tentacles[0].ondulacao is ONDULACAO_AGITADA


def test_corpo_continua_ondulando_ao_recolher():
    diretor, pool = _diretor()
    diretor.trigger_curious()
    for _ in range(QUADROS_ANTES_DE_RECOLHER):
        diretor.update(PASSO, 0, IdlePersonality.PLAYFUL)
    ativo = next(t for t in pool.tentacles if t.state == TentacleState.CURIOUS)
    pool.release(ativo)
    antes = [Vec3(s.pos) for s in ativo.segments]
    diretor.update(PASSO, 0, IdlePersonality.PLAYFUL)
    assert ativo.state == TentacleState.RETRACTING
    assert any(
        (a - s.pos).lengthSquared() > 0
        for a, s in zip(antes, ativo.segments, strict=True)
    )


def test_ramo_burst_espirra_sem_erro_e_passa_da_porta():
    diretor, pool = _diretor(PITCH_FRENTE)
    diretor.trigger_sneeze()
    for _ in range(QUADROS_BURST):
        diretor.update(PASSO, 0, IdlePersonality.CALM)
    ativos = [t for t in pool.tentacles if t.state != TentacleState.DORMANT]
    assert ativos
    for tentaculo in ativos:
        assert all(math.isfinite(c) for s in tentaculo.segments for c in s.pos)
        assert (tentaculo.visible_tip() - tentaculo.anchor).dot(PITCH_FRENTE) > 0
