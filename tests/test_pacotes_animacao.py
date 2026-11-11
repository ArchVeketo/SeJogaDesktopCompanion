"""Testes unitários das Fases 0 a 4 do plano de naturalidade e pacotes de animação."""

from __future__ import annotations

from math import isclose, radians
import pytest

from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
from sejoga.animacao.mola_critica import (
    avancar_mola_critica,
    meia_vida_para_amortecimento,
    suavizar_exato,
)
from sejoga.animacao.movimento_corpo import GiroCorpo, Spring, calcular_alvo_angular
from sejoga.animacao.pacotes_animacao import (
    ANGULO_POR_ORIENTACAO,
    DURACAO_TOTAL_OLHAR_TELA_S,
    ESCALA_POR_PROFUNDIDADE,
    AgendadorPacotes,
    EstadoProfundidade,
    ItemPacote,
    NivelProfundidade,
    OrientacaoCorpo,
    PacoteOlharTela,
)
from sejoga.animacao.resolvedor_poses import limitar_suave
from sejoga.animacao.ruido_procedural import (
    calcular_ruido,
    delta_micro_ruido_idle,
    distribuir_coluna_tronco,
)
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rig


def test_spring_valida_parametros_invalidos() -> None:
    """Fase 0.1: Spring rejeita damping fora de (0, 1) ou frequency <= 0."""
    with pytest.raises(ValueError):
        Spring(frequency=0.0, damping=0.5)
    with pytest.raises(ValueError):
        Spring(frequency=2.0, damping=1.0)
    with pytest.raises(ValueError):
        Spring(frequency=2.0, damping=0.0)


def test_mola_critica_converge_na_meia_vida() -> None:
    """Fase 0.3: Mola criticamente amortecida aproxima o alvo sem overshoot."""
    assert meia_vida_para_amortecimento(0.2) > 0.0
    x, v = 0.0, 0.0
    for _ in range(120):
        x, v = avancar_mola_critica(x, v, 10.0, 0.15, 1.0 / 60.0)
        assert x <= 10.0001
    assert isclose(x, 10.0, abs_tol=0.02)
    assert isclose(suavizar_exato(0.0, 10.0, 0.1, 0.1), 5.0, abs_tol=1e-3)


def test_limitar_suave_comprime_margem_e_respeita_teto() -> None:
    """Fase 0.5: limitar_suave preserva o centro linear e não passa dos extremos."""
    assert isclose(limitar_suave(0.0, -1.0, 1.0), 0.0, abs_tol=1e-9)
    assert isclose(limitar_suave(0.5, -1.0, 1.0), 0.5, abs_tol=1e-9)
    # Na borda extrema (ex.: 10.0 > 1.0), fica estritamente dentro de [-1, 1]
    valor_extremo = limitar_suave(10.0, -1.0, 1.0)
    assert 0.85 < valor_extremo <= 1.0


def test_ruido_procedural_e_distribuicao_coluna() -> None:
    """Fase 2.1 & 2.3: Ruído senoidal contínuo e distribuição na cadeia do tronco."""
    r1 = calcular_ruido(1.0, semente=2.0)
    r2 = calcular_ruido(1.001, semente=2.0)
    assert -1.0 <= r1 <= 1.0
    assert abs(r2 - r1) < 0.05

    micro = delta_micro_ruido_idle(2.5)
    for junta in (
        "cintura",
        "abdomen",
        "peitoral",
        "fones",
        "antena-direita",
        "antena-esquerda",
    ):
        assert junta in micro

    from sejoga.nucleo.esqueleto import Rotation3

    col = distribuir_coluna_tronco(Rotation3(10.0, 20.0, -5.0))
    assert isclose(
        col["cintura"].y + col["abdomen"].y + col["peitoral"].y, 20.0, abs_tol=1e-6
    )


def test_giro_corpo_menor_arco_e_costas_180() -> None:
    """Fase 3.1: calcular_alvo_angular evita volta longa e GiroCorpo atinge 180°."""
    alvo = calcular_alvo_angular(170.0, -170.0)
    assert isclose(alvo, 190.0, abs_tol=1e-6)

    giro = GiroCorpo()
    # Sem permitir_costas, satura no limite lateral (90°)
    for _ in range(120):
        ang = giro.update(1 / 60, angulo_pedido=180.0, permitir_costas=False)
    assert isclose(ang, 90.0, abs_tol=0.5)

    # Com permitir_costas=True, alcança 180° (de costas)
    for _ in range(180):
        ang = giro.update(1 / 60, angulo_pedido=180.0, permitir_costas=True)
    assert isclose(ang, 180.0, abs_tol=0.5)


def test_estado_profundidade_niveis_e_puxao_arraste() -> None:
    """Fase 4.3: Profundidade visual transita entre perto/médio/longe e volta ao arrastar."""
    prof = EstadoProfundidade()
    assert prof.nivel_alvo == NivelProfundidade.PERTO
    assert prof.avancar_fundo() == NivelProfundidade.MEDIO
    assert prof.avancar_fundo() == NivelProfundidade.LONGE

    for _ in range(120):
        escala, subida = prof.atualizar(1 / 60, arrastando=False)
    assert isclose(escala, ESCALA_POR_PROFUNDIDADE[NivelProfundidade.LONGE], abs_tol=0.01)
    assert subida > 0.10

    # Arrastar puxa o mascote de volta para PERTO (escala 1.0, subida 0.0)
    for _ in range(90):
        escala, subida = prof.atualizar(1 / 60, arrastando=True)
    assert prof.nivel_alvo == NivelProfundidade.PERTO
    assert isclose(escala, 1.0, abs_tol=0.01)
    assert isclose(subida, 0.0, abs_tol=0.01)


def test_pacote_olhar_tela_quatro_fases_completas() -> None:
    """Fase 3.2-3.4 & 4.2: Pacote 'Olhar a tela' percorre as 4 fases e encerra."""
    pacote = PacoteOlharTela()
    pacote.iniciar(lado=1.0)
    assert pacote.ativo

    # Fase 1: olhar por cima do ombro (torção na coluna + cabeça, corpo a 0°)
    amostra1 = pacote.atualizar(0.7)
    assert amostra1.ativo and amostra1.fase == "olhar_ombro"
    assert amostra1.angulo_giro_corpo == 0.0
    assert not amostra1.em_passo
    assert amostra1.delta_pose["cintura"].y > 0.0
    assert amostra1.delta_pose["abdomen"].y > amostra1.delta_pose["cintura"].y
    assert amostra1.delta_pose["peitoral"].y > amostra1.delta_pose["abdomen"].y
    assert amostra1.delta_pose["head"].y > radians(10.0)

    # Fase 2: virar de costas com passos
    amostra2 = pacote.atualizar(1.3)
    assert amostra2.ativo and amostra2.fase == "virar_costas"
    assert amostra2.em_passo
    assert 0.0 < (amostra2.angulo_giro_corpo or 0.0) <= 180.0

    # Fase 3: observar a tela de costas (180°)
    amostra3 = pacote.atualizar(2.0)
    assert amostra3.ativo and amostra3.fase == "observar_tela"
    assert isclose(amostra3.angulo_giro_corpo or 0.0, 180.0, abs_tol=1e-5)
    assert not amostra3.em_passo

    # Fase 4: voltar para a frente com passos
    amostra4 = pacote.atualizar(3.0)
    assert amostra4.ativo and amostra4.fase == "voltar_frente"
    assert amostra4.em_passo

    # Fim do pacote
    amostra_fim = pacote.atualizar(DURACAO_TOTAL_OLHAR_TELA_S)
    assert not amostra_fim.ativo and amostra_fim.fase == "inativo"


def test_agendador_pacotes_respeita_cooldown_e_nao_repete() -> None:
    """Fase 4.1: AgendadorPacotes sorteia sem repetição imediata e aplica cooldown."""
    ag = AgendadorPacotes(
        (
            ItemPacote("a", peso=1.0, resfriamento_s=10.0),
            ItemPacote("b", peso=1.0, resfriamento_s=10.0),
        ),
        intervalo_base_s=5.0,
        semente=42,
    )
    primeiro = ag.sortear()
    segundo = ag.sortear()
    assert primeiro in ("a", "b")
    assert segundo in ("a", "b")
    assert primeiro != segundo
    # Ambos em cooldown agora: sortear devolve None até o tempo avançar
    assert ag.sortear() is None
    ag.atualizar(12.0, elegivel=False)
    terceiro = ag.sortear()
    assert terceiro is not None and terceiro != segundo


def test_controlador_animacao_integra_pacotes_profundidade_e_orientacao() -> None:
    """Fase 4.4: AnimationController expõe e integra pacotes, profundidade e orientação."""
    from sejoga.nucleo.esqueleto import Rotation3

    rig = Rig({g: Rotation3() for g in ALL_GROUPS})
    ctrl = AnimationController(rig)

    ctrl.definir_profundidade("longe")
    ctrl.definir_orientacao("costas")
    ctrl.update(1 / 60, grounded=True, dragging=False)
    assert ctrl.permitir_giro_costas is True
    assert ctrl.angulo_giro_pedido == ANGULO_POR_ORIENTACAO[OrientacaoCorpo.COSTAS]

    ctrl.voltar_ao_plano()
    ctrl.update(1 / 60, grounded=True, dragging=False)
    assert ctrl.profundidade.nivel_alvo == NivelProfundidade.PERTO
    assert ctrl.orientacao_manual is None

    ctrl.iniciar_pacote_olhar_tela(lado=1.0)
    pose = ctrl.update(0.5, grounded=True, dragging=False)
    assert ctrl.pacote_olhar_tela.ativo
    assert ctrl.permitir_giro_costas is True
    assert "cintura" in pose and "peitoral" in pose and "fones" in pose
