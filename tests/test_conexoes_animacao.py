"""Contratos de integração das conexões; qualidade de movimento é verificada na janela."""
from math import isfinite
from types import SimpleNamespace

import pytest

from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
from sejoga.animacao.movimento_corpo import GiroCorpo
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rig, Rotation3


def controller():
    return AnimationController(Rig(rest={g: Rotation3() for g in ALL_GROUPS}))


def test_troca_danca_no_mesmo_estado_inicia_transicao_sem_rebobinar_estado():
    ctrl = controller()
    ctrl.preview_dance("hip_hop")
    for _ in range(60):
        ctrl.update(1 / 30)
    tempo = ctrl.state_time
    ctrl.preview_dance("rock")
    assert ctrl.pose_resolver._state_time == 0
    ctrl.update(1 / 30)
    assert ctrl.state == AnimationState.DANCE
    assert ctrl.state_time > tempo
    assert ctrl.pose_resolver._state_time == pytest.approx(1 / 30)


def test_acordar_passa_pela_reacao_de_despertar():
    ctrl = controller()
    ctrl.colocar_para_dormir("sentado")
    ctrl.acordar()
    ctrl.update(1 / 30)
    assert ctrl.state == AnimationState.WAKE
    assert not ctrl._sleep_locked


def test_giro_renderizado_volta_das_costas_ao_idle_sem_salto():
    from panda3d.core import NodePath, Quat

    from sejoga.render.renderizador import Panda3DRenderer

    renderer = Panda3DRenderer.__new__(Panda3DRenderer)
    ctrl = controller()
    renderer.showbase = SimpleNamespace(animation_controller=ctrl)
    renderer._giro_corpo = GiroCorpo()
    renderer._body_facing = NodePath("body-facing")
    renderer.model_np = renderer._body_facing.attachNewNode("model")
    ctrl.state = AnimationState.DANCE
    ctrl.permitir_giro_costas = True
    for _ in range(120):
        renderer._aplicar_giro_corpo(1 / 60, 0.0, 160.0, False)
    antes = renderer._body_facing.getQuat()
    assert renderer._giro_corpo.angulo == pytest.approx(160.0, abs=0.1)

    ctrl.state = AnimationState.IDLE
    ctrl.permitir_giro_costas = False
    for frame in range(120):
        renderer._aplicar_giro_corpo(1 / 60, 0.0, None, False)
        depois = renderer._body_facing.getQuat()
        if frame == 0:
            assert abs(depois.dot(antes)) > 0.999
        assert isfinite(renderer._giro_corpo.angulo)
    assert abs(depois.dot(Quat.identQuat())) == pytest.approx(1, abs=1e-6)


def test_arraste_no_meio_da_reacao_nao_estala_o_antebraco():
    """O atraso tátil das cadeias entra por rampa: sem salto de dezenas de graus."""
    import math

    from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
    from sejoga.nucleo.esqueleto import Rig
    from sejoga.nucleo.modelo import load_model
    from sejoga.nucleo.recursos import resolve_model

    ctrl = AnimationController(Rig.from_model(load_model(resolve_model())))
    ctrl.update(0.1)
    ctrl.interact("poke", direction=1.0)
    for _ in range(15):
        anterior = dict(ctrl.update(1 / 60, grounded=True))
    pior = 0.0
    for _ in range(30):
        atual = dict(ctrl.update(1 / 60, dragging=True))
        pior = max(pior, max(
            math.degrees(max(abs(a.x - anterior[k].x), abs(a.y - anterior[k].y), abs(a.z - anterior[k].z)))
            for k, a in atual.items() if k in anterior
        ))
        anterior = atual
    assert ctrl.state == AnimationState.DRAG
    assert pior < 14.0


def test_troca_fone_com_problema_para_outra_cena_sem_salto():
    """Interromper fone_com_problema sentado transiciona pernas sem salto seco."""
    import math

    from sejoga.nucleo.modelo import load_model
    from sejoga.nucleo.recursos import resolve_model

    ctrl = AnimationController(Rig.from_model(load_model(resolve_model())))
    ctrl.agencia._gerar_desejo_espontaneo = lambda: None
    ctrl.update(0.1)
    ctrl.interact("fone_com_problema")
    for _ in range(315):
        ctrl.update(1 / 60, grounded=True)
    assert ctrl.cena_idle_amostra.ativa
    assert ctrl.cena_idle_amostra.pernas_graus is not None

    anterior = dict(ctrl.update(1 / 60, grounded=True))
    ctrl.interact("ajeitar_fone")
    pior = 0.0
    for _ in range(30):
        atual = dict(ctrl.update(1 / 60, grounded=True))
        for k, a in atual.items():
            assert isfinite(a.x) and isfinite(a.y) and isfinite(a.z)
            if k in anterior:
                pior = max(
                    pior,
                    math.degrees(
                        max(
                            abs(a.x - anterior[k].x),
                            abs(a.y - anterior[k].y),
                            abs(a.z - anterior[k].z),
                        )
                    ),
                )
        anterior = atual
    assert pior < 10.0


def test_walk_para_run_transiciona_suavemente():
    """Troca walk_standard -> run_mixamo usa rampa de colisão e blend sem coice."""
    import math

    from sejoga.nucleo.modelo import load_model
    from sejoga.nucleo.recursos import resolve_model

    ctrl = AnimationController(Rig.from_model(load_model(resolve_model())))
    ctrl.agencia._gerar_desejo_espontaneo = lambda: None
    ctrl.update(0.1)
    for _ in range(45):
        anterior = dict(ctrl.update(1 / 60, grounded=True, velocity=(260.0, 0.0)))
    assert ctrl.acao_clipe_ativa == "walk_standard"

    pior = 0.0
    for _ in range(45):
        atual = dict(ctrl.update(1 / 60, grounded=True, velocity=(900.0, 0.0)))
        for k, a in atual.items():
            if k in anterior:
                pior = max(
                    pior,
                    math.degrees(
                        max(
                            abs(a.x - anterior[k].x),
                            abs(a.y - anterior[k].y),
                            abs(a.z - anterior[k].z),
                        )
                    ),
                )
        anterior = atual
    assert ctrl.state == AnimationState.RUN
    assert ctrl.acao_clipe_ativa == "run_mixamo"
    assert pior < 16.0


def test_arm_stretching_sem_inversao_brusca_de_punho():
    """Filtro de clipes autorais remove flips de gimbal nos punhos."""
    import math

    from sejoga.animacao.danca_clipes import carregar_clipe_acao

    clipe = carregar_clipe_acao("arm_stretching")
    assert clipe is not None
    quadros = clipe.quadros
    pior_punho = max(
        math.degrees(
            max(
                abs(quadros[i][g].x - quadros[i - 1][g].x),
                abs(quadros[i][g].y - quadros[i - 1][g].y),
                abs(quadros[i][g].z - quadros[i - 1][g].z),
            )
        )
        for i in range(1, len(quadros))
        for g in ("hand", "hand2")
        if g in quadros[i] and g in quadros[i - 1]
    )
    assert pior_punho < 20.0


def test_teimosia_e_espirro_articulam_pernas_sem_cortes():
    """Teimosia articula base/joelhos e espirro percorre 9s sem salto abrupto."""
    import math

    from sejoga.animacao.movimento_pernas import LegMotion
    from sejoga.animacao.teimosia_pose import FASES_TEIMOSIA
    from sejoga.nucleo.modelo import load_model
    from sejoga.nucleo.recursos import resolve_model

    leg_motion = LegMotion()
    joelhos = []
    for fase in FASES_TEIMOSIA:
        leg_motion.update(0.25, AnimationState.TEIMOSIA, time=0.4, teimosia_fase=fase)
        joelhos.append(leg_motion.pose.right_knee)
    assert min(joelhos) > 4.0

    ctrl = AnimationController(Rig.from_model(load_model(resolve_model())))
    ctrl.agencia._gerar_desejo_espontaneo = lambda: None
    ctrl.update(0.1)
    anterior = dict(ctrl.update(1 / 60, grounded=True))
    ctrl.interact("sneeze")
    pior = 0.0
    for _ in range(560):
        atual = dict(ctrl.update(1 / 60, grounded=True))
        for k, a in atual.items():
            if k in anterior:
                pior = max(
                    pior,
                    math.degrees(
                        max(
                            abs(a.x - anterior[k].x),
                            abs(a.y - anterior[k].y),
                            abs(a.z - anterior[k].z),
                        )
                    ),
                )
        anterior = atual
    assert pior < 18.0
