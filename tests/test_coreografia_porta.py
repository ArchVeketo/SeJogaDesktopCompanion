"""Coreografia tentáculos x porta: máquina de fases e tuning por temperamento (lógica pura)."""

from __future__ import annotations

from sejoga.nucleo.esqueleto import IdlePersonality
from sejoga.tentaculos import coreografia_porta as coreo

DT = 1 / 30
ANGULO_ABERTO = 85.0


def _rodar(coreografia, quadros, **entrada):
    passos = []
    for _ in range(quadros):
        passos.append(coreografia.avancar(DT, **entrada))
    return passos


def test_saida_cobre_todos_os_temperamentos_e_passa_do_limiar_de_saida():
    assert set(coreo.SAIDA_POR_TEMPERAMENTO) == set(IdlePersonality)
    for saida in coreo.SAIDA_POR_TEMPERAMENTO.values():
        assert saida.angulo_empurrao_graus > coreo.LIMIAR_SAIDA_PORTA_GRAUS


def test_calmo_mantem_a_temporizacao_anterior_e_agitado_e_mais_rapido():
    calma, agitada = coreo.SAIDA_CALMA, coreo.SAIDA_AGITADA
    assert (calma.duracao_s, calma.escalonamento_s) == (1.8, 0.48)
    assert agitada.duracao_s < calma.duracao_s
    assert agitada.angulo_empurrao_graus > calma.angulo_empurrao_graus


def test_angulo_empurrado_so_comeca_apos_o_contato_e_chega_ao_final():
    final = coreo.SAIDA_CALMA.angulo_empurrao_graus
    assert coreo.angulo_empurrado(coreo.REVELACAO_INICIO_CONTATO, final) == 0.0
    assert coreo.angulo_empurrado(coreo.REVELACAO_FIM_EMPURRAO, final) == final
    meio = (coreo.REVELACAO_INICIO_CONTATO + coreo.REVELACAO_FIM_EMPURRAO) / 2
    assert 0.0 < coreo.angulo_empurrado(meio, final) < final


def test_ciclo_completo_abrir_esquecer_puxar_fechar():  # noqa: PLR0915  # TODO convenção: teste de cenário longo; dividir em lote próprio
    coreografia = coreo.CoreografiaPorta()
    coreografia.iniciar_empurrao()
    final = coreo.SAIDA_CALMA.angulo_empurrao_graus
    passo = coreografia.avancar(
        DT,
        revelacao_atuador=coreo.REVELACAO_FIM_EMPURRAO,
        angulo_porta=0.0,
        ha_ativos=True,
        angulo_empurrao=final,
    )
    assert passo.fim_empurrao and passo.angulo_porta == final
    assert coreografia.fase is coreo.FasePorta.ABERTA

    # Com tentáculos fora a porta fica livre; ao entrarem todos, ela é esquecida aberta.
    assert (
        _rodar(
            coreografia,
            3,
            revelacao_atuador=0.0,
            angulo_porta=ANGULO_ABERTO,
            ha_ativos=True,
            angulo_empurrao=0.0,
        )[-1].angulo_porta
        is None
    )
    coreografia.avancar(
        DT,
        revelacao_atuador=0.0,
        angulo_porta=ANGULO_ABERTO,
        ha_ativos=False,
        angulo_empurrao=0.0,
    )
    assert coreografia.fase is coreo.FasePorta.ESQUECIDA

    quadros_esquecimento = int(coreo.ATRASO_ESQUECIMENTO_S / DT) + 2
    passos = _rodar(
        coreografia,
        quadros_esquecimento,
        revelacao_atuador=0.0,
        angulo_porta=ANGULO_ABERTO,
        ha_ativos=False,
        angulo_empurrao=0.0,
    )
    assert all(p.angulo_porta == ANGULO_ABERTO for p in passos)
    assert sum(p.chamar_puxador for p in passos) == 1
    assert coreografia.fase is coreo.FasePorta.ALCANCANDO

    _rodar(
        coreografia,
        int(coreo.TEMPO_ALCANCE_PUXAO_S / DT) + 2,
        revelacao_atuador=1.0,
        angulo_porta=ANGULO_ABERTO,
        ha_ativos=True,
        angulo_empurrao=0.0,
    )
    assert coreografia.fase is coreo.FasePorta.PUXANDO

    angulo = ANGULO_ABERTO
    soltou = False
    for _ in range(int(ANGULO_ABERTO / (coreo.VELOCIDADE_PUXAO_GRAUS_S * DT)) + 3):
        passo = coreografia.avancar(
            DT,
            revelacao_atuador=1.0,
            angulo_porta=angulo,
            ha_ativos=True,
            angulo_empurrao=0.0,
        )
        assert passo.angulo_porta < angulo
        angulo = passo.angulo_porta
        if passo.soltar_puxador:
            soltou = True
            break
    assert soltou and angulo <= coreo.ANGULO_SOLTAR_PUXAO_GRAUS
    assert coreografia.fase is coreo.FasePorta.VOLTANDO

    # A porta termina de fechar; a fase só acaba com o puxador já recolhido.
    for _ in range(
        int(
            coreo.ANGULO_SOLTAR_PUXAO_GRAUS
            / (coreo.VELOCIDADE_FECHAR_FINAL_GRAUS_S * DT)
        )
        + 3
    ):
        passo = coreografia.avancar(
            DT,
            revelacao_atuador=0.0,
            angulo_porta=angulo,
            ha_ativos=False,
            angulo_empurrao=0.0,
        )
        angulo = passo.angulo_porta if passo.angulo_porta is not None else 0.0
    assert coreografia.fase is coreo.FasePorta.FECHADA


def test_puxao_e_bem_mais_rapido_que_o_fechamento_final():
    assert coreo.VELOCIDADE_PUXAO_GRAUS_S > 4 * coreo.VELOCIDADE_FECHAR_FINAL_GRAUS_S


def test_cancelar_devolve_a_porta_ao_comportamento_normal():
    coreografia = coreo.CoreografiaPorta()
    coreografia.iniciar_empurrao()
    coreografia.cancelar()
    passo = coreografia.avancar(
        DT,
        revelacao_atuador=1.0,
        angulo_porta=0.0,
        ha_ativos=True,
        angulo_empurrao=60.0,
    )
    assert coreografia.fase is coreo.FasePorta.FECHADA
    assert passo.angulo_porta is None
