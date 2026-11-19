"""Testes de integração e regressão para a Fase 1 do backlog (A1-A5 e E1-E7)."""

from __future__ import annotations

from math import degrees

import PySide6.QtWidgets  # noqa: F401 - evita conflito Qt vs Panda3D na mesma sessão pytest
from panda3d.core import NodePath, Vec3
from tests.fk_bracos import punho

from sejoga.animacao.alvos_bracos import ALVOS
from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
from sejoga.animacao.poses_base import pose_interaction
from sejoga.nucleo.esqueleto import Rig
from sejoga.nucleo.modelo import load_model
from sejoga.nucleo.recursos import resolve_model
from sejoga.render.efeitos_cena import MAX_PARTICULAS, GerenciadorEfeitosCena


def _novo_controlador() -> AnimationController:
    return AnimationController(Rig.from_model(load_model(resolve_model())))


def test_celebrate_comemora_erguendo_bracos_mantendo_porta_fechada_e_retorna_ao_idle() -> None:
    """'celebrate' ergue os braços em V assimétrico, mantém porta fechada, anima pernas e volta ao idle."""
    assert "celebrate" in ALVOS
    ctrl = _novo_controlador()
    antes_positivas = ctrl.agencia._interacoes_positivas
    ctrl.interact("celebrate", direction=0.4)

    pico_mao_y = -999.0
    max_porta = 0.0
    max_joelho = 0.0
    for _ in range(12):
        pose = ctrl.update(0.1, grounded=True)
        assert ctrl.state == AnimationState.CELEBRATE
        pico_mao_y = max(pico_mao_y, punho(pose, "right")[1], punho(pose, "left")[1])
        max_porta = max(max_porta, abs(degrees(pose["door"].y)))
        max_joelho = max(
            max_joelho,
            ctrl.leg_motion.pose.left_knee,
            ctrl.leg_motion.pose.right_knee,
        )

    assert pico_mao_y > 0.05
    assert max_porta <= 1.0
    assert max_joelho > 10.0
    assert ctrl.agencia._interacoes_positivas == antes_positivas + 1

    for _ in range(12):
        ctrl.update(0.1, grounded=True)
    assert ctrl.state == AnimationState.IDLE


def test_celebrate_nao_dispara_em_exploracao_trivial_e_premia_carinhos_seguidos() -> None:
    """Passeio casual não comemora; meta prioritária e 3 carinhos seguidos comemoram respeitando cooldown."""
    from sejoga.animacao.agencia import Meta, MetaTipo

    ctrl = _novo_controlador()
    passeio = Meta(tipo=MetaTipo.EXPLORAR_TELA, alvo_x=200.0, alvo_y=0.0, prioridade=0.9)
    assert not ctrl.agencia.consumir_vitoria_meta(passeio)

    missao_baixa = Meta(tipo=MetaTipo.PROCURAR_ATENCAO, alvo_x=200.0, alvo_y=0.0, prioridade=0.5)
    assert not ctrl.agencia.consumir_vitoria_meta(missao_baixa)

    missao_alta = Meta(tipo=MetaTipo.PROCURAR_ATENCAO, alvo_x=200.0, alvo_y=0.0, prioridade=0.85)
    assert ctrl.agencia.consumir_vitoria_meta(missao_alta)
    # Cooldown de 90s bloqueia spam imediato
    assert not ctrl.agencia.consumir_vitoria_meta(missao_alta)

    ctrl.agencia.atualizar(95.0)
    for _ in range(2):
        ctrl.interact("pet")
        assert ctrl._pending_intent is None
        for _ in range(15):
            ctrl.update(0.1, grounded=True)
    ctrl.interact("pet")
    assert ctrl._pending_intent is not None and ctrl._pending_intent[0] == "celebrate"


def test_reacao_diferenciada_por_parte_no_duplo_clique() -> None:
    """A5: double_click reage distinto em cabeça, braços, pernas, pés e tronco."""
    rig = Rig.from_model(load_model(resolve_model()))
    partes = ("body", "head", "right-arm", "left-arm", "legs", "left-feet", "right-feet")
    poses = {}
    for parte in partes:
        rig.reset()
        pose_interaction(rig, "double_click", 0.35, direction=0.5, vertical=0.0, part=parte)
        poses[parte] = {
            g: (round(degrees(r.x), 2), round(degrees(r.y), 2), round(degrees(r.z), 2))
            for g, r in rig.pose().items()
        }

    assert poses["head"]["head"] != poses["body"]["head"]
    assert poses["head"]["door"] != poses["body"]["door"]
    assert poses["right-arm"]["ant-arm"] != poses["left-arm"]["ant-arm"]
    assert poses["right-arm"]["peitoral"] != poses["left-arm"]["peitoral"]
    assert poses["legs"]["body"] != poses["body"]["body"]
    assert poses["left-feet"]["body"] != poses["right-feet"]["body"]

    # Controlador propaga a parte tocada para pernas e pós-pouso.
    ctrl = _novo_controlador()
    ctrl.interact("double_click", part="left-feet")
    for _ in range(5):
        ctrl.update(0.08, grounded=True)
    assert ctrl.state == AnimationState.DOUBLE_CLICK
    assert ctrl.leg_motion.pose.left_knee > 25.0
    assert ctrl.leg_motion.pose.right_knee < ctrl.leg_motion.pose.left_knee


def test_double_click_na_queda_preserva_parte_apos_pouso() -> None:
    """A5 + Rain World: intenção adiada na queda conserva a parte clicada."""
    ctrl = _novo_controlador()
    ctrl.update(0.05, grounded=False, velocity=(0.0, 320.0))
    ctrl.interact("double_click", part="head")
    assert ctrl._pending_intent is not None
    assert ctrl._pending_intent_part == "head"
    for _ in range(25):
        ctrl.update(0.05, grounded=True, velocity=(0.0, 0.0))
    assert ctrl._reaction_part == "head"


def test_sono_automatico_varia_entre_tres_modos_e_sono_manual_fixa() -> None:
    """A2/A3/A4: sono automático alterna entre em_pe, sentado e deitado sem repetir seguido."""
    ctrl = _novo_controlador()
    modos_vistos: list[str] = []
    for _ in range(3):
        for _ in range(15):
            ctrl.update(0.1, sleep_after_idle_seconds=1)
        assert ctrl.state == AnimationState.SLEEP
        modos_vistos.append(ctrl.modo_sono)
        ctrl.interact("click")
        for _ in range(15):
            ctrl.update(0.1, sleep_after_idle_seconds=1)
        assert ctrl.state == AnimationState.IDLE

    assert set(modos_vistos) == {"em_pe", "sentado", "deitado"}
    assert modos_vistos[0] != modos_vistos[1]
    assert modos_vistos[1] != modos_vistos[2]

    ctrl.colocar_para_dormir("deitado")
    ctrl.update(0.1)
    assert ctrl.modo_sono == "deitado"
    assert ctrl.state == AnimationState.SLEEP


def _nomes_particulas(fx: GerenciadorEfeitosCena) -> set[str]:
    return {p.node.getName() for p in fx._particulas}


def test_sistema_particulas_pixeladas_cobre_e1_a_e7() -> None:
    """Sistema reutilizável 2D emite E1-E7 (notas, ondas, poeiras, Zzz e gosma)."""
    raiz = NodePath("teste-efeitos")
    fx = GerenciadorEfeitosCena(raiz)

    # E1 (notas) + E2 (ondas de fones e caixas de som) + comemoração
    fx.atualizar(
        0.05,
        estado="dance",
        tempo_estado=0.5,
        grounded=True,
        acento_danca=True,
        comemorando=True,
        som_fones=True,
        caixas_som_pos=(Vec3(0.4, -0.22, 0.0),),
    )
    nomes = _nomes_particulas(fx)
    assert {"fx-nota-p", "fx-onda-p", "fx-luz-p"} <= nomes
    assert "fx-poeira-p" not in nomes

    # E3 pouso + E4 deslize + E5 queda
    fx.atualizar(0.05, estado="fall", tempo_estado=0.2, grounded=False, velocidade=(0.0, 460.0))
    assert "fx-queda-p" in _nomes_particulas(fx)

    fx.atualizar(0.05, estado="idle", tempo_estado=0.1, grounded=True, velocidade=(280.0, 0.0), deslizando=True)
    assert {"fx-poeira-p", "fx-deslize-p"} <= _nomes_particulas(fx)

    # E6 Zzz no sono + E7 gosma rosa com arco gravitacional
    fx.atualizar(0.05, estado="sleep", tempo_estado=0.5, grounded=True, sono=True, gosma_evento=True)
    nomes_fx = _nomes_particulas(fx)
    assert {"fx-z-p", "fx-gosma-p"} <= nomes_fx

    gosma = next(p for p in fx._particulas if p.node.getName() == "fx-gosma-p")
    vz_inicial = gosma.vel.z
    fx.atualizar(0.1, estado="idle", tempo_estado=0.0, grounded=True)
    assert gosma.vel.z < vz_inicial


def test_sistema_particulas_respeita_pool_e_expira_sem_vazar() -> None:
    """Pool respeita limite MAX_PARTICULAS, expira após TTL e limpa sob demanda."""
    raiz = NodePath("teste-efeitos-pool")
    fx = GerenciadorEfeitosCena(raiz)
    for _ in range(30):
        fx.emitir_gosma(Vec3(0.0, -0.24, 0.0), quantidade=5)
    assert fx.total_particulas <= MAX_PARTICULAS

    for _ in range(40):
        fx.atualizar(0.1, estado="idle", tempo_estado=0.0, grounded=True)
    assert fx.total_particulas == 0

    fx.emitir_notas_musicais(Vec3(0.0, -0.24, 0.0), quantidade=3)
    assert fx.total_particulas > 0
    fx.limpar()
    assert fx.total_particulas == 0
