"""Contratos da tabela de tensão por junta e seus helpers."""

from sejoga.rig import ALL_GROUPS
from sejoga.spring_tuning import (
    TENSAO_PADRAO,
    TENSAO_POR_JUNTA,
    amortecimento_de,
    frequencia_de,
    lag_de,
    tensao_de,
)


def test_todos_os_grupos_tem_entrada():
    for grupo in ALL_GROUPS:
        assert grupo in TENSAO_POR_JUNTA


def test_faixas_sas_por_junta():
    for tensao in TENSAO_POR_JUNTA.values():
        assert tensao.frequencia > 0
        assert 0 < tensao.amortecimento <= 1
        assert tensao.lag >= 0


def test_rigidez_decresce_da_ancora_para_a_ponta():
    assert (
        frequencia_de("body")
        >= frequencia_de("shoulder")
        >= frequencia_de("right-arm")
        >= frequencia_de("ant-arm")
        >= frequencia_de("hand")
        >= frequencia_de("fingers")
    )


def test_amortecimento_da_ancora_maior_que_o_da_ponta():
    assert amortecimento_de("body") >= amortecimento_de("fingers")


def test_lag_cresce_da_ancora_para_a_ponta():
    assert lag_de("body") <= lag_de("right-arm") <= lag_de("hand") <= lag_de("fingers")


def test_helpers_usam_fallback_para_grupo_desconhecido():
    assert tensao_de("grupo-inexistente") is TENSAO_PADRAO
    assert frequencia_de("grupo-inexistente") == TENSAO_PADRAO.frequencia
    assert amortecimento_de("grupo-inexistente") == TENSAO_PADRAO.amortecimento
    assert lag_de("grupo-inexistente") == TENSAO_PADRAO.lag
