"""Testes de fechamento dos achados do roadmap e integração limpa entre camadas."""

from __future__ import annotations

from math import hypot
from types import SimpleNamespace

import PySide6.QtCore  # noqa: F401  # importa Qt antes do Panda3D no processo

from sejoga.animacao.agencia import Agencia, Meta
from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
from sejoga.animacao.poses_base import Rig, pose_repouso
from sejoga.animacao.selecao_estado import escolher_estado
from sejoga.configuracao import MusicSettings, Settings
from sejoga.desktop.integracao_desktop import DesktopIntegration
from sejoga.render import janela as janela_mod


def test_agencia_direcao_meta_normalizada_negativo_e_distancia_zero():
    agencia = Agencia(seed=1)
    agencia.meta_ativa = Meta(tipo="curiosidade", alvo_x=-640.0, alvo_y=0.0)
    agencia.definir_posicao_corpo(-340.0, 400.0)
    direcao = agencia.direcao_meta
    assert direcao is not None
    assert hypot(*direcao) == 1.0 or abs(hypot(*direcao) - 1.0) < 1e-6
    assert abs(direcao[0] - (-0.6)) < 1e-6
    assert abs(direcao[1] - (-0.8)) < 1e-6

    agencia.definir_posicao_corpo(-640.0, 0.0)
    assert agencia.direcao_meta is None


def test_agencia_pontos_interesse_deduplicados_e_limitados():
    agencia = Agencia(seed=2)
    agencia.adicionar_ponto_interesse(100.0, 100.0)
    agencia.adicionar_ponto_interesse(110.0, 105.0)
    assert len(agencia._pontos_interesse) == 1
    for idx in range(25):
        agencia.adicionar_ponto_interesse(float(idx * 60), 200.0)
    assert len(agencia._pontos_interesse) == 16


def test_selecao_estado_unificada_com_histerese():
    s_novo = escolher_estado(
        speed=380.0,
        grounded=True,
        gravity_active=False,
        dragging=False,
        music_playing=False,
        music_intensity=0.0,
        current_state=AnimationState.WALK,
    )
    s_continua = escolher_estado(
        speed=380.0,
        grounded=True,
        gravity_active=False,
        dragging=False,
        music_playing=False,
        music_intensity=0.0,
        current_state=AnimationState.RUN,
    )
    assert s_novo == AnimationState.WALK
    assert s_continua == AnimationState.RUN
    assert s_continua == AnimationController._choose_state(
        speed=380.0,
        grounded=True,
        gravity_active=False,
        dragging=False,
        music_playing=False,
        music_intensity=0.0,
        current_state=AnimationState.RUN,
    )


def test_show_cursor_unico_e_restaurado_na_saida(monkeypatch):
    chamadas: list[bool] = []
    monkeypatch.setattr(janela_mod.win32api, "ShowCursor", chamadas.append)

    ctrl = SimpleNamespace(
        _teimosia_fase="roubo",
        _cursor_oculto=False,
        state=AnimationState.TEIMOSIA,
    )
    app = janela_mod.OverlayApp.__new__(janela_mod.OverlayApp)
    app.animation_controller = ctrl

    app._sincronizar_cursor_teimosia()
    app._sincronizar_cursor_teimosia()
    assert chamadas == [False]
    assert ctrl._cursor_oculto is True

    ctrl.state = AnimationState.DRAG
    app._sincronizar_cursor_teimosia()
    app._sincronizar_cursor_teimosia()
    assert chamadas == [False, True]
    assert ctrl._cursor_oculto is False

    ctrl.state = AnimationState.TEIMOSIA
    app._sincronizar_cursor_teimosia()
    app.taskMgr = SimpleNamespace(remove=lambda *args: None)
    app.desktop = app.music_listener = app.debug_tools = app.hotkey_manager = None
    app._persist_settings = lambda: None
    monkeypatch.setattr(janela_mod.ShowBase, "userExit", lambda self: None)
    app._finish_exit()
    assert chamadas == [False, True, False, True]
    assert ctrl._cursor_oculto is False


def test_griddy_e_migracao_griddle_para_griddy():
    assert DesktopIntegration.DANCE_COMMANDS[0x1FD0] == "griddy"
    assert "griddle" not in MusicSettings.model_fields["dance_style"].annotation.__args__
    migrated = Settings.model_validate({"music": {"dance_style": "griddle"}})
    assert migrated.music.dance_style == "griddy"


def test_controlador_encaminha_body_position_e_beat_phase():
    ctrl = AnimationController(Rig(pose_repouso()))
    ctrl.agencia.meta_ativa = Meta(
        tipo="exploracao",
        alvo_x=300.0,
        alvo_y=0.0,
        criado_em=ctrl.agencia._agora,
    )
    ctrl.update(
        1 / 60,
        music_playing=True,
        music_intensity=0.7,
        music_bass=0.5,
        music_bpm=120.0,
        beat_phase=0.25,
        music_updated_at=5.0,
        now=5.05,
        body_position=(0.0, 0.0),
    )
    assert ctrl.agencia.direcao_meta == (1.0, 0.0)


def test_menu_bugs_frente3_acoes_manuais_e_orientacao():
    from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
    from sejoga.animacao.pose_repouso import pose_repouso
    from sejoga.nucleo.esqueleto import Rig

    ctrl = AnimationController(Rig(pose_repouso()))
    ctrl.colocar_para_dormir("sentado")
    assert ctrl.state == AnimationState.SLEEP
    ctrl.preview_dance("rock")
    ctrl.update(1 / 60, grounded=True)
    assert ctrl.state == AnimationState.DANCE

    ctrl.alternar_sentado()
    ctrl.update(1 / 60, grounded=True)
    assert ctrl.state == AnimationState.SIT
    ctrl.iniciar_pacote_olhar_tela()
    ctrl.update(1 / 60, grounded=True)
    assert ctrl.state != AnimationState.SIT

    ctrl.definir_orientacao("costas")
    assert ctrl.orientacao_manual is not None
    ctrl.definir_orientacao("frente")
    assert ctrl.orientacao_manual is None


def test_menu_bugs_frente3_pulo_sem_mouse_e_caminhada_bounds():
    from types import SimpleNamespace

    from sejoga.animacao.controlador_animacao import AnimationController
    from sejoga.animacao.pose_repouso import pose_repouso
    from sejoga.configuracao import Settings
    from sejoga.nucleo.esqueleto import Rig
    from sejoga.render.janela import OverlayApp

    ctrl = AnimationController(Rig(pose_repouso()))
    app = OverlayApp.__new__(OverlayApp)
    app.settings = Settings()
    app._drag_active = False
    app._mouse_screen = None
    app.animation_controller = ctrl
    chamadas_pulo = []
    ctrl.pular = lambda vx, vy: chamadas_pulo.append((vx, vy))
    app.physics = SimpleNamespace(
        bounds=(100.0, 0.0, 900.0, 700.0),
        get_state=lambda: SimpleNamespace(grounded=True, position=(400.0, 500.0)),
        get_shelf_above=lambda _px, _py: None,
    )
    assert app.pular_mascote() is True
    assert len(chamadas_pulo) == 1
    app.caminhar_destino_aleatorio()
    assert 100.0 <= app._destino_caminhada_x <= 900.0
