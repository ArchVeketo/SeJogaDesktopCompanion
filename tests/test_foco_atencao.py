"""Testes da camada de olhar/atenção (sem GPU)."""

import random

from sejoga.animacao.foco_atencao import (
    PRIORIDADE_BORDA,
    PRIORIDADE_CURSOR,
    PRIORIDADE_FOCO,
    GateAtencao,
    GatilhoAtencao,
    ponto_para_direcao,
)

# --- Conversão ponto-global -> direção local --------------------------------


def test_cursor_a_direita_da_janela_gera_direcao_positiva():
    # Janela 200x200 com origem em (1000, 1000); ponto à direita do centro.
    direcao, _ = ponto_para_direcao((1300, 1100), (1000, 1000), 200, 200)
    assert direcao > 0


def test_cursor_a_esquerda_da_janela_gera_direcao_negativa():
    direcao, _ = ponto_para_direcao((800, 1100), (1000, 1000), 200, 200)
    assert direcao < 0


def test_ponto_abaixo_do_rosto_gera_vertical_positivo():
    _, vertical = ponto_para_direcao((1100, 1400), (1000, 1000), 200, 200)
    assert vertical > 0


def test_conversao_satura_em_menos_um_e_um():
    direcao, vertical = ponto_para_direcao((5000, 5000), (0, 0), 100, 100)
    assert direcao == 1.0
    assert vertical == 1.0


def test_janela_degenerada_nao_quebra():
    assert ponto_para_direcao((10, 10), (0, 0), 0, 0) == (0.0, 0.0)


# --- Gate: prioridade entre gatilhos concorrentes ---------------------------


def _gate():
    return GateAtencao(rng=random.Random(1))


def test_gate_escolhe_maior_prioridade_entre_concorrentes():
    gate = _gate()
    cursor = GatilhoAtencao("cursor", (1300, 1100), PRIORIDADE_CURSOR)
    foco = GatilhoAtencao("foco", (800, 1100), PRIORIDADE_FOCO)
    alvo = gate.atualizar(
        1 / 60,
        gatilhos=[cursor, foco],
        origem_janela=(1000, 1000),
        largura=200,
        altura=200,
    )
    # Foco tem prioridade maior que cursor: olha para a ESQUERDA (foco).
    assert alvo.fonte == "foco"
    assert alvo.direcao < 0


def test_gate_sem_gatilhos_e_ambiente_desligado_fica_neutro():
    gate = _gate()
    alvo = gate.atualizar(
        1 / 60,
        gatilhos=[],
        origem_janela=(0, 0),
        largura=200,
        altura=200,
        ambiente_habilitado=False,
    )
    assert alvo.fonte is None
    assert alvo.direcao == 0.0
    assert alvo.vertical == 0.0


def test_feature_desligada_nao_produz_movimento():
    gate = _gate()
    cursor = GatilhoAtencao("cursor", (1300, 1100), PRIORIDADE_CURSOR)
    alvo = gate.atualizar(
        1 / 60,
        gatilhos=[cursor],
        origem_janela=(1000, 1000),
        largura=200,
        altura=200,
        habilitado=False,
    )
    assert alvo.fonte is None
    assert alvo.direcao == 0.0
    assert alvo.vertical == 0.0
    assert not alvo.surpresa


# --- Gate: surpresa dispara em salto forte ----------------------------------


def test_surpresa_dispara_em_salto_forte_de_lado():
    gate = _gate()
    # Primeiro quadro: olhar firme para a direita (sem anterior => sem susto).
    direita = GatilhoAtencao("foco", (1300, 1100), PRIORIDADE_FOCO, forca=1.0)
    primeiro = gate.atualizar(
        1 / 60,
        gatilhos=[direita],
        origem_janela=(1000, 1000),
        largura=200,
        altura=200,
    )
    assert not primeiro.surpresa
    # Segundo quadro: alvo salta para a esquerda, gatilho forte => susto.
    esquerda = GatilhoAtencao("foco", (700, 1100), PRIORIDADE_FOCO, forca=1.0)
    segundo = gate.atualizar(
        1 / 60,
        gatilhos=[esquerda],
        origem_janela=(1000, 1000),
        largura=200,
        altura=200,
    )
    assert segundo.surpresa


def test_surpresa_nao_dispara_para_gatilho_fraco():
    gate = _gate()
    direita = GatilhoAtencao("beat", (1300, 1100), PRIORIDADE_BORDA, forca=0.2)
    gate.atualizar(
        1 / 60, gatilhos=[direita], origem_janela=(1000, 1000), largura=200, altura=200
    )
    esquerda = GatilhoAtencao("beat", (700, 1100), PRIORIDADE_BORDA, forca=0.2)
    alvo = gate.atualizar(
        1 / 60, gatilhos=[esquerda], origem_janela=(1000, 1000), largura=200, altura=200
    )
    assert not alvo.surpresa


# --- Gate: ambiente espontâneo ----------------------------------------------


def test_ambiente_espontaneo_acaba_produzindo_olhar_sem_gatilhos():
    gate = _gate()
    viu_ambiente = False
    for _ in range(3600):  # ~60 s a 60 fps: cobre o novo AMBIENTE_INTERVALO_MAX (40 s).
        alvo = gate.atualizar(
            1 / 60,
            gatilhos=[],
            origem_janela=(1000, 1000),
            largura=200,
            altura=200,
        )
        if alvo.fonte == "ambiente":
            viu_ambiente = True
            break
    assert viu_ambiente


def test_ambiente_desligado_nunca_produz_olhar_espontaneo():
    gate = _gate()
    for _ in range(3000):
        alvo = gate.atualizar(
            1 / 60,
            gatilhos=[],
            origem_janela=(1000, 1000),
            largura=200,
            altura=200,
            ambiente_habilitado=False,
        )
        assert alvo.fonte is None
