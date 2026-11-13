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

    for style in ("fade_in", "virtual_insanity_in", "run_from_depth", "kagebunshin_in"):
        anim = IntroAnimation(style)
        for frac in (0.05, 0.25, 0.55, 0.85, 1.0):
            assert anim.sample(anim.duration * frac).offset_y == 0.0


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
    assert vi_mid.pitch == 0.0 and vi_mid.roll == 0.0

    lego = ExitAnimation(origin, 260, bounds, style="lego_disassemble")
    assert lego.sample(lego.duration * 0.85).explode > 0.8

    thanos = ExitAnimation(origin, 260, bounds, style="thanos_snap")
    assert thanos.sample(thanos.duration * 0.95).ash > 0.8
    assert thanos.sample(thanos.duration * 0.95).dissolve > 0.8

    peace = ExitAnimation(origin, 260, bounds, style="peace_fade_out")
    assert peace.sample(0.3).locomotion == "peace"
    assert peace.sample(peace.duration).dissolve > 0.9


def test_sonic_exit_vertical_arc():
    origin = (600, 500)
    bounds = (0, 0, 1920, 1080)
    sonic = ExitAnimation(origin, 260, bounds, style="sonic_classic")
    assert sonic.sample(sonic.duration * 0.05).y == origin[1]
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
    ):
        anim = ExitAnimation(origin, 260, bounds, style=grounded_style)
        for frac in (0.05, 0.30, 0.60, 0.90):
            assert anim.sample(anim.duration * frac).y == origin[1]


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
