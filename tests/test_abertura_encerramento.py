"""Testa animações de abertura/encerramento, continuidade pós-queda e Rain World."""

from __future__ import annotations

import math
import random

from sejoga import configuracao
from sejoga.animacao.animacao_entrada import (
    _RANDOM_POOL,
    INTRO_STYLES,
    IntroAnimation,
)
from sejoga.animacao.animacao_saida import (
    _RANDOM_DEATH_POOL,
    EXIT_STYLES,
    ExitAnimation,
)
from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
from sejoga.animacao.foco_atencao import (
    PRIORIDADE_CURSOR,
    GateAtencao,
    GatilhoAtencao,
)
from sejoga.animacao.movimento_pernas import LegMotion
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rig, Rotation3


def _controller() -> AnimationController:
    return AnimationController(Rig(rest={group: Rotation3() for group in ALL_GROUPS}))


def test_intro_styles_sample_finite_and_complete():
    padrao = IntroAnimation("padrao")
    padrao_frame = padrao.sample(0.0)
    assert padrao_frame.finished is True
    assert padrao_frame.scale == 1.0
    assert padrao_frame.dissolve == 0.0

    aleatoria = IntroAnimation("aleatoria", rng=random.Random(7))
    assert aleatoria.style in _RANDOM_POOL

    for style in INTRO_STYLES:
        if style in ("padrao", "aleatoria"):
            continue
        anim = IntroAnimation(style, from_side=1)
        early = anim.sample(0.05)
        mid = anim.sample(anim.duration * 0.5)
        end = anim.sample(anim.duration)
        assert early.finished is False
        assert end.finished is True
        for frame in (early, mid, end):
            assert frame.scale > 0.0
            assert 0.0 <= frame.dissolve <= 1.0
            assert 0.0 <= frame.smoke_burst <= 1.0
            values = (
                frame.offset_x,
                frame.offset_y,
                frame.roll,
                frame.yaw,
                frame.pitch,
            )
            assert all(math.isfinite(val) for val in values)


def test_intro_style_signatures():
    fade = IntroAnimation("fade_in")
    assert fade.sample(0.05).dissolve > 0.8
    assert fade.sample(fade.duration).dissolve == 0.0

    vi = IntroAnimation("virtual_insanity_in", from_side=1)
    assert vi.sample(0.25).locomotion == "virtual_insanity"
    assert vi.sample(0.25).offset_x > 0.0

    run_in = IntroAnimation("run_from_depth")
    assert run_in.sample(0.1).locomotion == "run"
    assert run_in.sample(run_in.duration * 0.9).scale > run_in.sample(0.05).scale

    ninja = IntroAnimation("kagebunshin_in")
    assert ninja.sample(0.12).smoke_burst > 0.5

    goku_in = IntroAnimation("goku_teleport_in")
    goku_early = goku_in.sample(0.05)
    goku_hold = goku_in.sample(goku_in.duration * 0.45)
    assert goku_early.locomotion == "goku_teleport"
    assert goku_early.dissolve_mode == 3.0
    assert goku_early.warp_scale[0] < 0.7 and goku_early.warp_scale[2] > 1.2
    assert goku_hold.locomotion == "goku_teleport"
    assert goku_hold.dissolve == 0.0

    hero = IntroAnimation("hero_drop_in")
    assert hero.sample(0.05).offset_y < -100.0
    assert hero.sample(hero.duration * 0.40).warp_scale[2] < 0.92

    for style in (
        "fade_in",
        "virtual_insanity_in",
        "run_from_depth",
        "kagebunshin_in",
        "goku_teleport_in",
    ):
        anim = IntroAnimation(style)
        for frac in (0.05, 0.25, 0.55, 0.85, 1.0):
            assert abs(anim.sample(anim.duration * frac).offset_y) <= 25.0


def test_hero_drop_fecha_porta_antes_de_terminar_o_olhar():
    hero = IntroAnimation("hero_drop_in")
    porta = hero.sample(hero.duration * 0.47)
    olhar = hero.sample(hero.duration * 0.76)
    assert porta.door_open > 30 and porta.head_yaw == 0
    assert olhar.door_open == 0 and olhar.head_yaw > 15
    final = hero.sample(hero.duration)
    assert final.finished and final.door_open == 0
    assert math.isclose(final.head_yaw, 0, abs_tol=1e-9)


def test_corridas_de_entrada_preservam_transformacao_ao_comecar_a_freada():
    for style, fase in (("run_from_depth", 0.64), ("sandevistan_in", 0.60)):
        intro = IntroAnimation(style)
        tempo = intro.duration * fase
        antes = intro.sample(tempo - 1e-6)
        depois = intro.sample(tempo + 1e-6)
        assert (antes.locomotion, depois.locomotion) == ("run", "land")
        for eixo in ("offset_x", "offset_y", "scale", "roll", "yaw", "pitch"):
            assert math.isclose(getattr(antes, eixo), getattr(depois, eixo), abs_tol=0.004)


def test_exit_styles_sample_finite_and_complete():
    origin = (600, 500)
    bounds = (0, 0, 1920, 1080)
    aleatoria = ExitAnimation(
        origin, 260, bounds, style="aleatoria", rng=random.Random(3)
    )
    assert aleatoria.style in _RANDOM_DEATH_POOL

    for style in EXIT_STYLES:
        if style == "aleatoria":
            continue
        anim = ExitAnimation(origin, 260, bounds, style=style)
        start = anim.sample(0.0)
        mid = anim.sample(anim.duration * 0.6)
        end = anim.sample(anim.duration)
        assert end.done is True
        for frame in (start, mid, end):
            assert 0.0 <= frame.dissolve <= 1.0
            assert 0.0 <= frame.explode <= 1.0
            assert 0.0 <= frame.ash <= 1.0
            assert 0.0 <= frame.blue_balls <= 1.0
            assert frame.scale > 0.0
            assert all(math.isfinite(val) for val in (frame.roll, frame.yaw, frame.pitch))


def test_exit_death_signatures():
    origin = (600, 500)
    bounds = (0, 0, 1920, 1080)
    fnf = ExitAnimation(origin, 260, bounds, style="fnf_blue_balls")
    fnf_shock = fnf.sample(fnf.duration * 0.10)
    fnf_clutch = fnf.sample(fnf.duration * 0.50)
    assert fnf_shock.locomotion == "blue_balls"
    assert fnf_shock.shock > 0.2
    assert fnf_clutch.locomotion == "blue_balls"
    assert fnf_clutch.blue_balls > 0.6
    assert fnf_clutch.pitch == 0.0
    assert fnf_clutch.roll == 0.0

    vi = ExitAnimation(origin, 260, bounds, style="virtual_insanity_out")
    vi_mid = vi.sample(vi.duration * 0.45)
    assert vi_mid.locomotion == "virtual_insanity"
    assert vi_mid.x < origin[0]  # origin=600 < 960 -> desliza à esquerda
    assert abs(vi_mid.pitch) <= 4.0 and abs(vi_mid.roll) <= 8.0

    lego = ExitAnimation(origin, 260, bounds, style="lego_disassemble")
    assert lego.sample(lego.duration * 0.85).explode > 0.8

    thanos = ExitAnimation(origin, 260, bounds, style="thanos_snap")
    assert thanos.sample(thanos.duration * 0.95).ash > 0.8
    assert thanos.sample(thanos.duration * 0.95).dissolve > 0.8

    peace = ExitAnimation(origin, 260, bounds, style="peace_fade_out")
    assert peace.sample(0.3).locomotion == "peace"
    assert peace.sample(peace.duration).dissolve > 0.9

    goku_out = ExitAnimation(origin, 260, bounds, style="goku_teleport_out")
    goku_focus = goku_out.sample(goku_out.duration * 0.35)
    goku_vanish = goku_out.sample(goku_out.duration * 0.75)
    assert goku_focus.locomotion == "goku_teleport"
    assert goku_focus.dissolve == 0.0
    assert goku_vanish.dissolve_mode == 3.0
    assert goku_vanish.warp_scale[0] < 0.7 and goku_vanish.warp_scale[2] > 1.2
    assert goku_out.sample(goku_out.duration).dissolve == 1.0

    portal = ExitAnimation(origin, 260, bounds, style="portal_pull_out")
    assert portal.sample(portal.duration * 0.85).dissolve > 0.5
    assert abs(portal.sample(portal.duration * 0.85).yaw) > 150.0


def test_sonic_exit_vertical_arc():
    origin = (600, 500)
    bounds = (0, 0, 1920, 1080)
    sonic = ExitAnimation(origin, 260, bounds, style="sonic_classic")
    assert abs(sonic.sample(sonic.duration * 0.05).y - origin[1]) <= 12
    assert sonic.sample(sonic.duration * 0.35).y < origin[1]
    assert sonic.sample(sonic.duration).y > origin[1]


def test_exits_grounded_preserve_vertical_height():
    origin = (600, 500)
    bounds = (0, 0, 1920, 1080)
    for grounded_style in (
        "fnf_blue_balls",
        "lego_disassemble",
        "thanos_snap",
        "peace_fade_out",
        "virtual_insanity_out",
        "goku_teleport_out",
    ):
        anim = ExitAnimation(origin, 260, bounds, style=grounded_style)
        for frac in (0.05, 0.30, 0.60, 0.90):
            assert abs(anim.sample(anim.duration * frac).y - origin[1]) <= 12


def test_gate_atencao_cursor_novelty_decays_when_still_and_recovers_on_move():
    gate = GateAtencao(rng=random.Random(1))
    still_cursor = GatilhoAtencao("cursor", (900.0, 500.0), PRIORIDADE_CURSOR)
    for _ in range(120):  # ~4s parado (> limiar de 2s)
        gate.atualizar(
            1 / 30,
            gatilhos=[still_cursor],
            origem_janela=(100.0, 100.0),
            largura=480.0,
            altura=480.0,
            ambiente_habilitado=False,
        )
    decayed = gate._cursor_novidade
    assert decayed < 0.6

    moved_cursor = GatilhoAtencao("cursor", (980.0, 520.0), PRIORIDADE_CURSOR)
    gate.atualizar(
        1 / 30,
        gatilhos=[moved_cursor],
        origem_janela=(100.0, 100.0),
        largura=480.0,
        altura=480.0,
        ambiente_habilitado=False,
    )
    assert gate._cursor_novidade > decayed + 0.3


def test_leg_motion_couples_stride_to_speed_and_settles_to_idle():
    slow = LegMotion()
    fast = LegMotion()
    for _ in range(18):
        slow.update(1 / 60, "walk", velocity=(70.0, 0.0))
        fast.update(1 / 60, "walk", velocity=(240.0, 0.0))
    assert fast.phase > slow.phase

    fast.phase = math.pi / 2
    for t in range(30):
        fast.update(1 / 60, "idle", velocity=(0.0, 0.0), time=t / 60)
    assert abs(fast.pose.left) < 12.0


def test_animation_controller_queues_intent_across_fall_and_supports_peace():
    controller = _controller()
    controller.update(0.05, grounded=False, gravity_active=True, velocity=(0.0, 350.0))
    assert controller.state == AnimationState.FALL

    controller.interact("wave", direction=0.5, strength=1.0)
    assert controller._pending_intent is not None
    assert controller._reaction is None

    # Pouso dispara LAND e só depois retoma a intenção pendente
    for _ in range(4):
        controller.update(0.05, grounded=True, gravity_active=False, velocity=(0.0, 0.0))
    for _ in range(14):
        controller.update(0.05, grounded=True, gravity_active=False, velocity=(0.0, 0.0))

    assert controller._pending_intent is None
    assert controller._reaction == AnimationState.WAVE

    peace_controller = _controller()
    peace_controller.interact("peace")
    pose = peace_controller.update(0.05)
    assert peace_controller.state == AnimationState.PEACE
    assert pose

    fnf_ctrl = _controller()
    fnf_ctrl.interact("blue_balls")
    for _ in range(12):
        fnf_pose = fnf_ctrl.update(0.05)
    assert fnf_ctrl.state == AnimationState.BLUE_BALLS
    # Em vez de deitar para trás (pitch > 0), dobra para a frente (body.x < 0).
    assert fnf_pose["body"].x < 0.0

    vi_ctrl = _controller()
    vi_ctrl.interact("virtual_insanity", direction=1.0)
    for _ in range(3):
        vi_pose = vi_ctrl.update(0.06)
    assert vi_ctrl.state == AnimationState.VIRTUAL_INSANITY
    assert abs(vi_pose["body"].y) > 0.15


def test_window_settings_persist_intro_and_exit_styles(tmp_path):
    path = tmp_path / "perfil.toml"
    settings = configuracao.Settings()
    settings.window.intro_animation = "kagebunshin_in"
    settings.window.exit_animation = "thanos_snap"
    configuracao.save_settings(settings, path)

    loaded = configuracao.load_settings(path)
    assert loaded.window.intro_animation == "kagebunshin_in"
    assert loaded.window.exit_animation == "thanos_snap"


def test_intros_refined_durations_and_clean_settle():
    for style in INTRO_STYLES:
        if style in ("padrao", "aleatoria"):
            continue
        anim = IntroAnimation(style, from_side=1)
        assert anim.duration >= 1.5
        end = anim.sample(anim.duration)
        assert end.finished is True
        assert end.dissolve == 0.0
        assert end.afterimage == 0.0
        assert abs(end.offset_x) < 1e-6
        assert abs(end.scale - 1.0) < 1e-6


def test_loading_splash_preenche_banner_transparente(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from sejoga.desktop.carregamento import BRAND_PALETTES, LoadingSplash

    app = QApplication.instance() or QApplication([])
    splash = LoadingSplash(configuracao.Settings(), state_dir=tmp_path)
    assert splash.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert splash.windowFlags() & Qt.WindowType.WindowTransparentForInput
    assert splash.geometry().center() == splash.screen().geometry().center()
    vazio = splash.grab().toImage()
    for nivel in (0.35, 0.75, 1.0):
        splash.atualizar(nivel)
        img = splash.grab().toImage()
        assert img.pixelColor(0, 0).alpha() == 0
        assert any(img.pixelColor(x, 120).alpha() > 0 for x in range(img.width()))
    # Avança até encher completamente e confere diferença visual clara na cavidade.
    for _ in range(15):
        splash.atualizar(1.0)
    cheio = splash.grab().toImage()
    assert cheio.pixelColor(0, 0).alpha() == 0
    assert max(cheio.pixelColor(x, 120).alpha() for x in range(cheio.width())) == 255
    assert max(vazio.pixelColor(x, 120).alpha() for x in range(vazio.width())) > 0
    # Interior de uma letra ("ARMARIO"): cheio deve ser claramente mais luminoso que vazio.
    brilho_vazio = max(
        vazio.pixelColor(x, 165).red() + vazio.pixelColor(x, 165).green() + vazio.pixelColor(x, 165).blue()
        for x in range(60, 320, 8)
    )
    brilho_cheio = max(
        cheio.pixelColor(x, 165).red() + cheio.pixelColor(x, 165).green() + cheio.pixelColor(x, 165).blue()
        for x in range(60, 320, 8)
    )
    assert brilho_cheio > brilho_vazio + 80
    splash.close()

    # Alternância sequencial entre todas as cores da brand sem repetir.
    cores_abertura = []
    for _ in range(len(BRAND_PALETTES)):
        s = LoadingSplash(configuracao.Settings(), state_dir=tmp_path)
        cores_abertura.append(s._paleta.nome)
        s.close()
    assert len(set(cores_abertura)) == len(BRAND_PALETTES)
    app.processEvents()


def test_entrada_mantem_progresso_ate_o_overlay_assumir(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from sejoga import __main__ as entry
    from sejoga.desktop import carregamento
    from sejoga.render import janela

    eventos = []
    progresso = SimpleNamespace(value=0.0)

    @contextmanager
    def abertura(settings):
        eventos.append("splash")
        yield progresso
        eventos.append("finish")

    def overlay(settings, loading_progress):
        assert loading_progress is progresso
        assert progresso.value == 0.18
        return SimpleNamespace(run=lambda: eventos.append("run"))

    monkeypatch.setattr(carregamento, "animacao_de_abertura", abertura)
    monkeypatch.setattr(janela, "OverlayApp", overlay)
    assert entry.run() == 0
    assert eventos == ["splash", "run", "finish"]


def test_chroma_key_inicial_e_msaa_overlay_wgl():
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from sejoga.render.janela import _chroma_inicial_bgr
    from sejoga.render.sobreposicao_win32 import FRAMEBUFFER_MULTISAMPLES

    assert FRAMEBUFFER_MULTISAMPLES == 4
    assert _chroma_inicial_bgr("#FF00FF") == 0x00D600D6
    assert _chroma_inicial_bgr("#FFFF00") == 0x0000D6D6


def test_intros_borda_desktop_e_esqueleto_sem_cranio():
    from panda3d.core import NodePath

    from sejoga.render.esqueleto_fnf import EsqueletoFnf

    for style in ("virtual_insanity_in", "sandevistan_in"):
        anim = IntroAnimation(style, from_side=-1, entry_distance=980.0)
        assert anim.duration >= 2.1
        start = anim.sample(0.0)
        assert start.offset_x <= -950.0

    raiz = NodePath("teste-rig")
    nomes = (
        "head",
        "peitoral",
        "abdomen",
        "cintura",
        "pelvis",
        "right-arm",
        "ant-arm",
        "hand",
        "left-arm",
        "ant-arm2",
        "hand2",
        "coxa-direita",
        "joelho-direito",
        "canela-direita",
        "right-feet",
        "coxa-esquerda",
        "joelho-esquerdo",
        "canela-esquerda",
        "left-feet",
    )
    rig_nodes = {nome: raiz.attachNewNode(nome) for nome in nomes}
    rig_nodes["hand"].setPos(0.3, 0.0, 0.0)
    rig_nodes["right-feet"].setPos(0.0, 0.0, -0.4)
    skel = EsqueletoFnf(raiz, rig_nodes)
    assert all(peca.alvo_rig != rig_nodes["head"] for peca in skel._pecas)
    assert any(peca.alvo_rig == rig_nodes["peitoral"] for peca in skel._pecas)
    skel.atualizar(0.85, raiz)
    assert not skel.root.isHidden()
    skel.limpar()
