"""Testes da matemática do contorno vivo (sem engine)."""

from __future__ import annotations

import pytest

from sejoga.outline_dynamics import (
    COMPRESSION_MAX,
    COMPRESSION_MIN,
    RespiracaoContorno,
    espessura_efetiva,
)

BASE = 0.05


def test_repouso_igual_a_base():
    # Sem compressão e com intensidade default, a espessura é a própria base.
    assert espessura_efetiva(BASE, 0.0, 0.4) == pytest.approx(BASE)


def test_intensidade_zero_devolve_base_exata():
    # Intensidade 0 = comportamento estático anterior, em qualquer compressão.
    assert espessura_efetiva(BASE, COMPRESSION_MAX, 0.0) == BASE
    assert espessura_efetiva(BASE, COMPRESSION_MIN, 0.0) == BASE


def test_compressao_positiva_engrossa_dentro_do_limite():
    valor = espessura_efetiva(BASE, COMPRESSION_MAX, 1.0)
    assert valor > BASE
    assert valor <= BASE * (1.0 + 0.35)


def test_compressao_negativa_afina_dentro_do_limite():
    valor = espessura_efetiva(BASE, COMPRESSION_MIN, 1.0)
    assert valor < BASE
    assert valor >= BASE * (1.0 - 0.35)


def test_nunca_negativa_mesmo_com_base_zero():
    assert espessura_efetiva(0.0, COMPRESSION_MIN, 1.0) >= 0.0
    assert espessura_efetiva(0.0, COMPRESSION_MAX, 1.0) >= 0.0


def test_compressao_fora_da_faixa_e_limitada():
    acima = espessura_efetiva(BASE, 10.0, 1.0)
    abaixo = espessura_efetiva(BASE, -10.0, 1.0)
    assert acima == pytest.approx(espessura_efetiva(BASE, COMPRESSION_MAX, 1.0))
    assert abaixo == pytest.approx(espessura_efetiva(BASE, COMPRESSION_MIN, 1.0))


def test_spring_converge_para_o_alvo():
    respiracao = RespiracaoContorno()
    respiracao.reset(BASE)
    alvo = espessura_efetiva(BASE, COMPRESSION_MAX, 1.0)
    valor = BASE
    for _ in range(600):
        valor = respiracao.update(1 / 60, BASE, COMPRESSION_MAX, 1.0)
    assert valor == pytest.approx(alvo, abs=1e-3)


def test_reset_fixa_repouso_sem_inercia():
    respiracao = RespiracaoContorno()
    respiracao.reset(BASE)
    # Imediatamente após o reset, um passo sem compressão permanece na base.
    assert respiracao.update(1 / 60, BASE, 0.0, 0.4) == pytest.approx(BASE, abs=1e-6)


def test_update_nunca_negativo():
    respiracao = RespiracaoContorno()
    respiracao.reset(0.0)
    assert respiracao.update(1 / 60, 0.0, COMPRESSION_MIN, 1.0) >= 0.0
