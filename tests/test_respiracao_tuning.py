"""Contratos da tabela de respiração por personalidade e seus helpers."""

import sejoga.respiracao_tuning as tuning
from sejoga.respiracao_tuning import (
    PADRAO,
    RESPIRACAO_POR_PERSONALIDADE,
    parametros_de,
)
from sejoga.rig import IdlePersonality


def test_todas_as_personalidades_tem_entrada():
    for personalidade in IdlePersonality:
        assert personalidade in RESPIRACAO_POR_PERSONALIDADE


def test_faixas_por_personalidade():
    for parametros in RESPIRACAO_POR_PERSONALIDADE.values():
        assert parametros.frequencia > 0
        assert 0.0 < parametros.amplitude <= 1.0
        assert 0.0 <= parametros.bounce <= 1.0


def test_parametros_de_personalidade_conhecida():
    esperado = RESPIRACAO_POR_PERSONALIDADE[IdlePersonality.CALM]
    assert parametros_de(IdlePersonality.CALM) is esperado
    assert parametros_de("calm") is esperado


def test_parametros_de_personalidade_desconhecida_usa_padrao():
    assert parametros_de("inexistente") is PADRAO


def test_guarda_de_cobertura_existe():
    assert hasattr(tuning, "_faltando")
    assert tuning._faltando == ()
