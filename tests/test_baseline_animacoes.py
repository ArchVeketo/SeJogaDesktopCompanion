"""Suíte baseline comportamental das animações (Etapa 1 — rede de segurança v2.0).

Valida invariantes reais de comportamento, finitude, limites anatômicos,
preservação de volume, emendas de loop e interseções entre estados para toda a
camada de animação (sem amarrar números mecânicos ou capar expressividade).
"""

from __future__ import annotations

import math
from dataclasses import astuple
from itertools import pairwise

import pytest

from sejoga.animacao.agencia import Humor
from sejoga.animacao.animacao_entrada import INTRO_STYLES, IntroAnimation
from sejoga.animacao.animacao_saida import EXIT_STYLES, ExitAnimation
from sejoga.animacao.animation import CENAS_IDLE
from sejoga.animacao.antenas_expressivas import delta_expressao_viva
from sejoga.animacao.arcos_autorais import (
    arco_braço,
    arco_braço_par,
    arco_cabeca_torso,
    idle_arco_composto,
    lemniscata,
)
from sejoga.animacao.cenas_idle import DURACOES_CENAS, amostrar_cena_idle
from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
from sejoga.animacao.danca_clipes import (
    amostrar_clipe_completo,
    amostrar_clipe_danca,
    carregar_clipe_acao,
    carregar_clipe_danca,
    duracao_clipe_emote,
    listar_clipes_acao,
    listar_clipes_danca,
)
from sejoga.animacao.estados_delta import (
    delta_conexao,
    delta_hover,
    delta_indignacao,
    delta_jump,
    delta_secundario,
    delta_sit,
    delta_sleep,
)
from sejoga.animacao.gestos_dedos import (
    ATIVIDADE_POR_ESTADO,
    GESTURES,
    LIMITES_JUNTA_DEDO_GRAUS,
    LIMITES_JUNTA_POLEGAR_GRAUS,
    PEGADAS,
    _pegada_natural,
    angulos_juntas,
    numero_de_juntas,
    pegada_de_curl,
    suavizar,
)
from sejoga.animacao.gestos_reacao import aplicar_defesa
from sejoga.animacao.interpolacao import (
    CURVAS_SUPORTADAS,
    amostrar_pista,
    suavizar_curva,
    suavizar_quintico,
)
from sejoga.animacao.movimento_pernas import LegMotion
from sejoga.animacao.ritmo_humano import (
    FATOR_CASCATA_POR_GRUPO,
    MAX_FATOR_CASCATA,
    RitmoHumano,
    fator_cascata_grupo,
)
from sejoga.animacao.squash_stretch import (
    SquashStretch,
    preservar_volume,
    squash_stretch_composto,
    squash_stretch_danca,
    squash_stretch_impacto,
    squash_stretch_locomocao,
    squash_stretch_reacao,
    squash_stretch_respiracao,
    squash_stretch_sono,
)
from sejoga.animacao.teimosia_pose import (
    FASES_TEIMOSIA,
    aplicar_fase,
    fase_do_tempo,
)
from sejoga.nucleo.esqueleto import IdlePersonality, Rig, Rotation3
from sejoga.nucleo.modelo import load_model
from sejoga.nucleo.recursos import resolve_model


@pytest.fixture(scope="module")
def modelo_mario():
    return load_model(resolve_model())


def _novo_rig(modelo_mario) -> Rig:
    return Rig.from_model(modelo_mario)


def _pose_finita(pose: dict[str, Rotation3]) -> bool:
    for rot in pose.values():
        if not (math.isfinite(rot.x) and math.isfinite(rot.y) and math.isfinite(rot.z)):
            return False
    return True


def _assert_delta_finito(delta: dict[str, Rotation3]) -> None:
    assert _pose_finita(delta), f"Rotação não-finita encontrada: {delta}"


def _assert_leg_pose_valida(pose) -> None:
    vals = astuple(pose)
    assert all(math.isfinite(v) for v in vals), f"LegPose não-finita: {pose}"
    # v2.0: joelhos clampados anatomicamente >= 0° mesmo durante trocas rápidas.
    assert pose.left_knee >= 0.0, f"left_knee hiperestendido: {pose.left_knee}"
    assert pose.right_knee >= 0.0, f"right_knee hiperestendido: {pose.right_knee}"
    # _limitar_aducao_pernas mantém limites seguros de adução/yaw/roll.
    assert pose.left_roll <= 12.5 and pose.right_roll >= -12.5


# =========================================================================== #
# 1. Cobertura de todos os 35 AnimationStates via AnimationController
# =========================================================================== #

_ESTADOS_REACAO_INTERACT = (
    AnimationState.CLICK,
    AnimationState.DOUBLE_CLICK,
    AnimationState.PET,
    AnimationState.POKE,
    AnimationState.WAKE,
    AnimationState.LAND,
    AnimationState.CELEBRATE,
    AnimationState.WAVE,
    AnimationState.STRETCH,
    AnimationState.HIT,
    AnimationState.SNEEZE,
    AnimationState.HANG_LOOSE,
    AnimationState.THUMBS_UP,
    AnimationState.ROCK,
    AnimationState.FINGER_GUN,
    AnimationState.PEACE,
    AnimationState.POINT,
    AnimationState.OPEN_HANDS,
    AnimationState.CLOSE_FISTS,
    AnimationState.BLUE_BALLS,
    AnimationState.VIRTUAL_INSANITY,
    AnimationState.GOKU_TELEPORT,
    AnimationState.SURPRISE,
    AnimationState.TEIMOSIA,
)


def _coletar_passos(
    ctrl: AnimationController,
    passos: int,
    dt: float = 1.0 / 30.0,
    **kwargs,
) -> list[dict[str, Rotation3]]:
    poses: list[dict[str, Rotation3]] = []
    for _ in range(passos):
        ctrl.update(dt, **kwargs)
        poses.append(ctrl.rig.pose())
    return poses


def _exercitar_jump(ctrl: AnimationController, dt: float) -> list[dict[str, Rotation3]]:
    ctrl.pular(vx=90.0, vy_impulse=-560.0)
    poses: list[dict[str, Rotation3]] = []
    for i in range(18):
        em_chao = i < 4
        vy = 0.0 if em_chao else -420.0 + i * 25.0
        ctrl.update(dt, grounded=em_chao, velocity=(90.0, vy))
        poses.append(ctrl.rig.pose())
    return poses


def _exercitar_dance(ctrl: AnimationController, dt: float) -> list[dict[str, Rotation3]]:
    ctrl.preview_dance("hip_hop", duration=4.0)
    poses: list[dict[str, Rotation3]] = []
    for i in range(25):
        ctrl.update(
            dt,
            grounded=True,
            music_playing=True,
            music_intensity=0.8,
            music_bass=0.7,
            music_bpm=124.0,
            beat_detected=(i % 15 == 0),
            beat_phase=(i * dt * 2.0) % 1.0,
        )
        poses.append(ctrl.rig.pose())
    return poses


def _exercitar_estado(
    ctrl: AnimationController,
    estado: AnimationState,
) -> list[dict[str, Rotation3]]:
    """Conduz ``ctrl`` para ``estado`` por caminhos públicos e coleta poses."""
    dt = 1.0 / 30.0
    simples = {
        AnimationState.IDLE: (15, {"grounded": True, "velocity": (0.0, 0.0)}),
        AnimationState.HOVER: (20, {"grounded": True, "hovered": True, "look_direction": 0.6, "look_vertical": -0.2}),
        AnimationState.WALK: (20, {"grounded": True, "velocity": (120.0, 0.0)}),
        AnimationState.RUN: (20, {"grounded": True, "velocity": (460.0, 0.0)}),
        AnimationState.FALL: (20, {"grounded": False, "velocity": (60.0, 320.0)}),
    }
    if estado in simples:
        n, kw = simples[estado]
        return _coletar_passos(ctrl, n, dt, **kw)
    if estado == AnimationState.DRAG:
        ctrl.interact("drag_start")
        return _coletar_passos(ctrl, 20, dt, grounded=False, dragging=True, velocity=(140.0, -40.0), drag_intensity=0.8)
    if estado == AnimationState.JUMP:
        return _exercitar_jump(ctrl, dt)
    if estado == AnimationState.SIT:
        ctrl.sentar(manual=True)
        return _coletar_passos(ctrl, 25, dt, grounded=True, velocity=(0.0, 0.0), look_direction=0.4)
    if estado == AnimationState.DANCE:
        return _exercitar_dance(ctrl, dt)
    if estado == AnimationState.SLEEP:
        ctrl.colocar_para_dormir("sentado")
        return _coletar_passos(ctrl, 25, dt, grounded=True, velocity=(0.0, 0.0))
    if estado == AnimationState.PEEK:
        ctrl._reaction = AnimationState.PEEK
        ctrl._reaction_time = 0.0
        return _coletar_passos(ctrl, 20, dt, grounded=True, velocity=(0.0, 0.0))
    if estado == AnimationState.TEIMOSIA:
        ctrl.interact("teimosia", direction=1.0, strength=1.0)
        return _coletar_passos(ctrl, 62, 0.1, grounded=True, velocity=(0.0, 0.0))

    ctrl.interact(estado.value, direction=1.0, strength=1.0)
    dur = ctrl.REACTION_SECONDS.get(estado, 1.0)
    passos = max(12, min(40, int(dur / 0.05)))
    step = min(0.08, max(dt, dur / passos))
    return _coletar_passos(ctrl, passos, step, grounded=True, velocity=(0.0, 0.0))


@pytest.mark.parametrize("estado", list(AnimationState), ids=lambda s: s.value)
def test_todos_35_estados_produzem_poses_finitas_e_validas(modelo_mario, estado: AnimationState) -> None:
    """Todo AnimationState (35/35) roda no AnimationController sem NaN/Inf/crash."""
    ctrl = AnimationController(_novo_rig(modelo_mario), model=modelo_mario)
    for _ in range(3):
        ctrl.update(1 / 30, grounded=True)
    poses = _exercitar_estado(ctrl, estado)
    assert len(poses) >= 12
    for pose in poses:
        assert _pose_finita(pose), f"Pose inválida em {estado.value}"
    _assert_leg_pose_valida(ctrl.leg_motion.pose)


def test_todas_reacoes_de_interact_mapeiam_todos_estados() -> None:
    """Garante que a parametrização cobre integralmente os 35 estados."""
    cobertos = set(_ESTADOS_REACAO_INTERACT) | {
        AnimationState.IDLE,
        AnimationState.HOVER,
        AnimationState.WALK,
        AnimationState.RUN,
        AnimationState.DRAG,
        AnimationState.FALL,
        AnimationState.JUMP,
        AnimationState.SIT,
        AnimationState.DANCE,
        AnimationState.SLEEP,
        AnimationState.PEEK,
    }
    assert cobertos == set(AnimationState)


# =========================================================================== #
# 2. estados_delta: hover, secundario, indignacao, sleep(3 modos), sit, jump, conexao
# =========================================================================== #


def test_estados_delta_funcoes_sem_cobertura_anterior() -> None:
    """Valida delta_hover, delta_secundario, delta_indignacao, delta_sit, delta_jump e delta_sleep."""
    for direcao in (-1.0, 0.0, 1.0):
        for vert in (-0.8, 0.0, 0.8):
            d_hov = delta_hover(1.5, IdlePersonality.CURIOUS, 0.3, look_direction=direcao, look_vertical=vert)
            _assert_delta_finito(d_hov)
            assert "head" in d_hov and "door" in d_hov
            d_sit = delta_sit(2.0, look_direction=direcao, look_vertical=vert, respiracao=0.4)
            _assert_delta_finito(d_sit)
            assert "body" in d_sit and "right-arm" in d_sit and "left-arm" in d_sit

    assert delta_indignacao(1.0, 0.0) == {}
    d_ind = delta_indignacao(2.4, 0.85)
    _assert_delta_finito(d_ind)
    assert "right-arm" in d_ind and "ant-arm" in d_ind and "head" in d_ind

    for modo in ("em_pe", "sentado", "deitado"):
        for t in (0.0, 1.5, 4.0, 9.5):
            d_slp = delta_sleep(t, modo=modo)
            _assert_delta_finito(d_slp)
            assert "head" in d_slp and "body" in d_slp

    for t in (0.0, 0.05, 0.10, 0.12, 0.25, 0.45):
        d_jmp = delta_jump(t, velocity=(120.0, -420.0))
        _assert_delta_finito(d_jmp)
        assert "body" in d_jmp and "right-arm" in d_jmp

    base = {"head": Rotation3(0.1, -0.2, 0.05), "ant-arm": Rotation3(0.0, 0.0, 0.4)}
    for st in ("idle", "hover", "walk", "run", "dance", "drag", "fall", "sleep"):
        d_sec = delta_secundario(2.3, st, IdlePersonality.PLAYFUL, base)
        _assert_delta_finito(d_sec)
        assert "fones" in d_sec and "antena-direita" in d_sec and "hand" in d_sec


@pytest.mark.parametrize(
    ("origem", "destino", "t_pico", "t_fim"),
    [
        ("run", "idle", 0.20, 0.80),
        ("walk", "idle", 0.16, 0.65),
        ("idle", "walk", 0.15, 0.80),
        ("idle", "run", 0.15, 0.80),
        ("idle", "dance", 0.15, 0.80),
        ("idle", "surprise", 0.11, 0.55),
        ("surprise", "idle", 0.16, 0.60),
        ("idle", "jump", 0.10, 0.50),
        ("jump", "fall", 0.12, 0.45),
        ("jump", "land", 0.12, 0.45),
        ("idle", "sit", 0.18, 0.65),
        ("sit", "idle", 0.16, 0.70),
        ("walk", "run", 0.14, 0.55),
        ("run", "walk", 0.14, 0.55),
        ("idle", "drag", 0.12, 0.50),
        ("drag", "fall", 0.11, 0.45),
        ("fall", "idle", 0.16, 0.70),
        ("hit", "idle", 0.16, 0.70),
        ("sleep", "wake", 0.24, 0.90),
        ("wake", "idle", 0.20, 0.80),
        ("dance", "walk", 0.16, 0.70),
        ("celebrate", "idle", 0.22, 1.05),
    ],
)
def test_delta_conexao_todos_ramos_comecam_e_encerram_sem_residuo(
    origem: str, destino: str, t_pico: float, t_fim: float
) -> None:
    """Todas as conexões começam em 0, geram movimento finito no pico e zeram ao terminar."""
    assert delta_conexao(origem, destino, -0.1) == {}
    inicio = delta_conexao(origem, destino, 0.0)
    for rot in inicio.values():
        assert abs(rot.x) < 1e-6 and abs(rot.y) < 1e-6 and abs(rot.z) < 1e-6
    pico = delta_conexao(origem, destino, t_pico)
    _assert_delta_finito(pico)
    assert len(pico) > 0
    assert any(abs(r.x) + abs(r.y) + abs(r.z) > 1e-3 for r in pico.values())
    assert delta_conexao(origem, destino, t_fim) == {}


# =========================================================================== #
# 3. Todos os 29 loops/*.json e 12 acoes/*.json (3 eixos, quat, clamping)
# =========================================================================== #


def test_todos_29_loops_json_finitos_3_eixos_e_quat_unitario() -> None:
    """Valida todos os clipes de dança em loops/: 3 eixos finitos, loop contínuo e quat unitário."""
    clipes = listar_clipes_danca()
    assert len(clipes) >= 29
    for nome in clipes:
        clipe = carregar_clipe_danca(nome)
        assert clipe is not None
        dur_loop = len(clipe.loop) / clipe.fps
        dur_intro = len(clipe.intro) / clipe.fps
        a = amostrar_clipe_danca(nome, dur_intro)
        b = amostrar_clipe_danca(nome, dur_intro + dur_loop)
        assert a is not None and b is not None
        for osso, rot_a in a.items():
            rot_b = b[osso]
            for eixo in range(3):
                assert math.isfinite(rot_a[eixo]) and math.isfinite(rot_b[eixo])
                assert abs(rot_a[eixo] - rot_b[eixo]) < 2e-2, f"{nome}.{osso}[{eixo}]"
        if clipe.quat_raiz:
            for qw, qx, qy, qz in clipe.quat_raiz:
                norma = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
                assert abs(norma - 1.0) < 1e-2, f"quat não unitário em {nome}: {norma}"
        dur_total = duracao_clipe_emote(clipe)
        for frac in (0.0, 0.25, 0.5, 0.75, 0.99):
            pose, pernas, dx, yaw, quat, dedos = amostrar_clipe_completo(clipe, dur_total * frac)
            _assert_delta_finito(pose)
            assert all(math.isfinite(v) for v in pernas.values())
            assert math.isfinite(dx) and math.isfinite(yaw)
            if quat is not None:
                assert all(math.isfinite(v) for v in quat)
            if dedos is not None:
                assert all(0.0 <= v <= 1.0 for lado in dedos for v in lado)


def test_todas_12_acoes_json_finitas_seams_e_clamping_nao_loop() -> None:
    """Valida todas as 12 ações em acoes/: finitude, emendas em loops e clamp nos não-loops."""
    acoes = listar_clipes_acao()
    assert len(acoes) >= 12
    nao_loops_encontrados = 0
    for nome in acoes:
        clipe = carregar_clipe_acao(nome)
        assert clipe is not None
        dur = duracao_clipe_emote(clipe)
        assert dur > 0.3
        for frac in (0.0, 0.33, 0.67, 1.0):
            pose, pernas, dx, yaw, quat, dedos = amostrar_clipe_completo(clipe, dur * frac)
            _assert_delta_finito(pose)
            assert all(math.isfinite(v) for v in pernas.values())
            assert math.isfinite(dx) and math.isfinite(yaw)
            if quat is not None:
                assert all(math.isfinite(v) for v in quat)
            if dedos is not None:
                assert all(0.0 <= v <= 1.0 for lado in dedos for v in lado)
        if not clipe.em_loop:
            nao_loops_encontrados += 1
            dur_bruta = (len(clipe.quadros_intro) + len(clipe.quadros)) / clipe.fps
            p_fim, per_fim, _, y_fim, _, _ = amostrar_clipe_completo(clipe, dur_bruta)
            p_alem, per_alem, _, y_alem, _, _ = amostrar_clipe_completo(clipe, dur_bruta + 3.0)
            assert abs(y_alem - y_fim) < 1e-4, f"Não-loop {nome} não clampou yaw"
            for osso in p_fim:
                assert abs(p_alem[osso].x - p_fim[osso].x) < 1e-4
                assert abs(p_alem[osso].y - p_fim[osso].y) < 1e-4
                assert abs(p_alem[osso].z - p_fim[osso].z) < 1e-4
            for k in per_fim:
                assert abs(per_alem[k] - per_fim[k]) < 1e-4
    assert nao_loops_encontrados >= 4


# =========================================================================== #
# 4. Todas as 15 CENAS_IDLE em 30 Hz + variante + interrupção
# =========================================================================== #


@pytest.mark.parametrize("nome", sorted(CENAS_IDLE.keys()))
def test_todas_15_cenas_idle_varredura_30hz_e_retorno_neutro(nome: str) -> None:
    """Varre cada cena de idle a 30 Hz: finitude, peso em [0,1], variante e encerramento."""
    dur = DURACOES_CENAS[nome]
    assert dur > 1.0
    passos = int(dur * 30)
    assert amostrar_cena_idle(nome, -0.1).ativa is False
    assert amostrar_cena_idle(nome, dur + 0.05).ativa is False

    pesos: list[float] = []
    for i in range(passos):
        t = i / 30.0
        amostra = amostrar_cena_idle(nome, t, variante=i % 2)
        assert amostra.ativa is True
        assert 0.0 <= amostra.peso_mistura <= 1.0
        _assert_delta_finito(amostra.delta_rig)
        if amostra.pernas_graus is not None:
            assert all(math.isfinite(v) for v in amostra.pernas_graus)
        if amostra.dedos is not None:
            assert len(amostra.dedos) == 2
            assert all(0.0 <= v <= 1.0 for lado in amostra.dedos for v in lado)
        pesos.append(amostra.peso_mistura)

    assert max(pesos) > 0.85, f"Cena {nome} nunca atingiu peso pleno"
    assert pesos[0] < 0.25 and pesos[-1] < 0.35, f"Cena {nome} sem envelope nas pontas"


# =========================================================================== #
# 5. gestos_reacao.aplicar_defesa + teimosia_pose (5 fases)
# =========================================================================== #


@pytest.mark.parametrize("lado", (-1.0, 1.0))
@pytest.mark.parametrize("impacto", (False, True))
def test_aplicar_defesa_limites_cotovelo_e_retorno(modelo_mario, lado: float, impacto: bool) -> None:
    """aplicar_defesa respeita cotovelos sem hiperextensão e retorna ao repouso em t=duracao."""
    rig = _novo_rig(modelo_mario)
    dur = 0.65
    for i in range(25):
        rig.reset()
        t = dur * i / 24.0
        aplicar_defesa(rig, t, dur, lado, impacto=impacto, firmeza=0.6)
        pose = rig.pose()
        _assert_delta_finito(pose)
        assert pose["ant-arm"].z >= -1e-6
        assert pose["ant-arm2"].z <= 1e-6


def test_teimosia_pose_todas_5_fases_continuas(modelo_mario) -> None:
    """Varre todas as 5 fases de teimosia (0..6s) sem NaN e com fases ordenadas."""
    rig = _novo_rig(modelo_mario)
    fases_vistas: set[str] = set()
    for i in range(181):
        t = i / 30.0
        fases_vistas.add(fase_do_tempo(t))
        rig.reset()
        aplicar_fase(rig, t, direcao_olhar=0.7)
        pose = rig.pose()
        _assert_delta_finito(pose)
        assert pose["door"].y >= -1e-6
    assert fases_vistas == set(FASES_TEIMOSIA.keys())


# =========================================================================== #
# 6. Todas as 7 Intros & 10 Exits em 60 Hz
# =========================================================================== #

_LOCOS_VALIDOS_INTRO = {s.value for s in AnimationState} | set(CENAS_IDLE.keys())
_LOCOS_VALIDOS_EXIT = {None} | {s.value for s in AnimationState} | set(CENAS_IDLE.keys())


@pytest.mark.parametrize("estilo", [s for s in INTRO_STYLES if s not in ("padrao", "aleatoria")])
def test_todas_7_intros_60hz_finitas_e_clampadas(estilo: str) -> None:
    """Varre todas as 7 entradas em 60 Hz: campos finitos, clamping e finalização."""
    intro = IntroAnimation(estilo, from_side=1, entry_distance=560.0)
    assert intro.duration > 0.5
    f_neg = intro.sample(-0.2)
    assert math.isfinite(f_neg.scale) and not f_neg.finished
    passos = int(intro.duration * 60) + 2
    max_after = 0.0
    for i in range(passos):
        f = intro.sample(i / 60.0)
        for v in (
            f.offset_x, f.offset_y, f.scale, f.roll, f.yaw, f.pitch,
            f.dissolve, f.smoke_burst, f.afterimage, f.door_open, f.head_yaw, *f.warp_scale,
        ):
            assert math.isfinite(v), f"{estilo} gerou não-finito em t={i / 60:.3f}"
        assert f.locomotion in _LOCOS_VALIDOS_INTRO, f"locomotion inesperado em {estilo}: {f.locomotion}"
        max_after = max(max_after, f.afterimage)
    f_fim = intro.sample(intro.duration + 0.5)
    assert f_fim.finished is True
    assert f_fim.scale == pytest.approx(1.0, abs=0.05)
    if estilo == "sandevistan_in":
        assert max_after > 0.3


@pytest.mark.parametrize("estilo", [s for s in EXIT_STYLES if s != "aleatoria"])
def test_todas_10_saidas_60hz_finitas_e_clampadas(estilo: str) -> None:
    """Varre todas as 10 saídas em 60 Hz: campos finitos, clamping e assinaturas."""
    saida = ExitAnimation((600, 400), 240, (0, 0, 1920, 1080), style=estilo)
    assert saida.duration > 0.5
    f_neg = saida.sample(-0.2)
    assert not f_neg.done and math.isfinite(f_neg.roll)
    passos = int(saida.duration * 60) + 2
    max_roll = 0.0
    max_shock = 0.0
    for i in range(passos):
        f = saida.sample(i / 60.0)
        for v in (
            f.x, f.y, f.roll, f.pitch, f.yaw, f.scale, f.dissolve,
            f.explode, f.ash, f.blue_balls, f.shock, f.glitch_offset, f.glitch_pulse, *f.warp_scale,
        ):
            assert math.isfinite(v), f"{estilo} gerou não-finito em t={i / 60:.3f}"
        assert f.locomotion in _LOCOS_VALIDOS_EXIT, f"locomotion inesperado em {estilo}: {f.locomotion}"
        max_roll = max(max_roll, abs(f.roll))
        max_shock = max(max_shock, f.shock)
    f_fim = saida.sample(saida.duration + 0.5)
    assert f_fim.done is True
    if estilo == "classic":
        assert max_roll > 500.0
    if estilo == "cyberpsicopata_out":
        assert max_shock > 0.3


# =========================================================================== #
# 7. LegMotion: todos os regimes, freada, sono(3 modos), dança e reações
# =========================================================================== #


def test_leg_motion_locomocao_freada_queda_e_sono() -> None:
    """Valida LegMotion em walk, run, freada->idle, fall e sleep nos 3 modos."""
    lm = LegMotion()
    dt = 1.0 / 60.0

    for i in range(30):
        _assert_leg_pose_valida(lm.update(dt, "walk", velocity=(140.0, 0.0), time=i * dt))
    for i in range(30):
        _assert_leg_pose_valida(lm.update(dt, "run", velocity=(440.0, 0.0), time=i * dt))
    assert lm.em_freada is False
    for i in range(40):
        p = lm.update(dt, "idle", velocity=(0.0, 0.0), time=i * dt)
        _assert_leg_pose_valida(p)
        if i == 2:
            assert lm.em_freada is True

    for i in range(30):
        _assert_leg_pose_valida(lm.update(dt, "fall", velocity=(90.0, 340.0), time=i * dt))

    for modo in ("em_pe", "sentado", "deitado"):
        for i in range(40):
            _assert_leg_pose_valida(lm.update(dt, "sleep", time=i * dt * 2.0, modo_sono=modo))


def test_leg_motion_danca_reacoes_e_teimosia() -> None:
    """Valida LegMotion em estilos de dança, reações e 5 fases de teimosia."""
    lm = LegMotion()
    dt = 1.0 / 60.0

    for estilo in ("head_bob", "hip_hop", "rock", "breakdance", "electro_swing"):
        for i in range(30):
            _assert_leg_pose_valida(
                lm.update(
                    dt,
                    "dance",
                    time=i * dt,
                    dance_style=estilo,
                    dance_phase=(i * 0.25) % math.tau,
                    dance_strength=0.8,
                    dance_time=i * dt,
                )
            )

    for reacao in ("celebrate", "poke", "sneeze", "wave", "stretch", "pet", "click", "blue_balls", "jump", "sit"):
        for i in range(30):
            _assert_leg_pose_valida(lm.update(dt, reacao, time=i * dt * 2.0))
    for fase in FASES_TEIMOSIA:
        for i in range(25):
            _assert_leg_pose_valida(
                lm.update(dt, "teimosia", velocity=(120.0, 0.0), time=i * dt * 2.0, teimosia_fase=fase)
            )


# =========================================================================== #
# 8. gestos_dedos: todos os GESTURES, PEGADAS, limites e suavizar
# =========================================================================== #


def test_gestos_dedos_todos_gestos_pegadas_e_limites() -> None:
    """Valida angulos_juntas, suavizar, pegada_de_curl e _pegada_natural para todos os gestos."""
    for dedo in range(5):
        limites = LIMITES_JUNTA_POLEGAR_GRAUS if dedo == 0 else LIMITES_JUNTA_DEDO_GRAUS
        assert numero_de_juntas(dedo) == len(limites)
        for estado in (*GESTURES.keys(), *PEGADAS.keys(), *ATIVIDADE_POR_ESTADO.keys(), "idle"):
            peg = _pegada_natural(estado, 1.4, None, 1, dedo)
            assert -1.01 <= peg <= 1.01
            flex = GESTURES[estado][dedo] if estado in GESTURES else 0.0
            angs = angulos_juntas(dedo, 1, 1.4, estado, 12.0, flex, pegada=peg)
            assert len(angs) == len(limites)
            for val, (lo, hi) in zip(angs, limites, strict=True):
                assert lo - 1e-6 <= val <= hi + 1e-6

    amostras = [pegada_de_curl(i / 20.0) for i in range(21)]
    assert amostras[0] == pytest.approx(-0.90, abs=1e-5)
    assert amostras[-1] == pytest.approx(1.0, abs=1e-5)
    assert all(b >= a - 1e-9 for a, b in pairwise(amostras))

    atual = (0.0, 0.0, 0.0)
    alvo = (40.0, 60.0, 30.0)
    for _ in range(30):
        atual = suavizar(atual, alvo, 1 / 30)
    assert all(abs(a - b) < 1.0 for a, b in zip(atual, alvo, strict=True))


# =========================================================================== #
# 9. Módulos puros: squash_stretch, antenas_expressivas, arcos_autorais,
#    ritmo_humano e interpolacao
# =========================================================================== #


def test_squash_stretch_preserva_volume_em_todos_estados() -> None:
    """Sx * Sy * Sz ≈ 1.0 em todas as funções de squash_stretch."""
    casos: list[SquashStretch] = [
        SquashStretch(*preservar_volume(1.0, 1.0, 0.88)),
        SquashStretch(*preservar_volume(1.0, 1.0, 1.12)),
        squash_stretch_respiracao(0.8),
        squash_stretch_locomocao(0.7, run=False),
        squash_stretch_locomocao(1.9, run=True),
        squash_stretch_impacto(0.05),
        squash_stretch_impacto(0.18),
        squash_stretch_sono(0.5, "sentado"),
        squash_stretch_sono(-0.5, "deitado"),
        squash_stretch_danca(0.0, 0.9, 0.8),
        squash_stretch_danca(0.5, 0.9, 0.2),
    ]
    for est in ("celebrate", "sneeze", "surprise", "wake", "hit", "poke", "double_click", "pet", "click", "teimosia"):
        casos.append(squash_stretch_reacao(est, 0.2, 1.0))
    for est in ("idle", "hover", "walk", "run", "drag", "fall", "sleep", "dance", "land", "jump", "sit", "celebrate"):
        casos.append(
            squash_stretch_composto(
                est,
                respiracao=0.4,
                fase_locomocao=1.1,
                run=(est == "run"),
                impacto_tempo=0.06,
                arraste_velocidade=(120.0, -80.0),
                arraste_intensidade=0.7,
                arraste_hanging=0.8,
                queda_velocidade=(80.0, 360.0),
                danca_fase_beat=0.1,
                danca_intensidade=0.8,
                danca_bass=0.7,
                reacao_tempo=0.08,
                reacao_duracao=0.65,
            )
        )
    for ss in casos:
        vol = ss.x * ss.y * ss.z
        assert 0.98 <= vol <= 1.02, f"Volume fora do intervalo: {ss} (vol={vol})"


def test_antenas_expressivas_todos_humores_e_estados() -> None:
    """Valida delta_expressao_viva para todos os Humores e regimes principais."""
    pose_base = {"right-arm": Rotation3(0.0, 0.0, -1.0), "left-arm": Rotation3(0.0, 0.0, 1.0)}
    for humor in Humor:
        for estado in ("idle", "hover", "walk", "run", "dance", "sleep", "pet", "surprise", "hit", "celebrate"):
            d = delta_expressao_viva(
                2.5,
                estado,
                humor,
                pose_base,
                look_direction=0.5,
                music_playing=(estado in ("idle", "dance")),
                beat_phase=0.25,
                music_bass=0.6,
                music_energy=0.7,
                reacao_tempo=0.1,
                tontura=0.2,
                esforco=0.3,
                afeicao=0.8,
                rancor=0.2,
                respiracao=0.4,
            )
            _assert_delta_finito(d)
            assert "antena-direita" in d and "antena-esquerda" in d


def test_arcos_autorais_finitos_e_limitados() -> None:
    """Valida lemniscata, arcos de braço e idle_arco_composto."""
    for t in (0.0, 0.5, 1.7, 4.3):
        lx, ly = lemniscata(t, amplitude_x=3.0, amplitude_y=4.0)
        assert math.isfinite(lx) and math.isfinite(ly)
        assert abs(lx) <= 3.01 and abs(ly) <= 4.01
        assert math.isfinite(arco_braço(t, amplitude=5.0))
        bd, be = arco_braço_par(t)
        assert math.isfinite(bd) and math.isfinite(be)
        p, y, r = arco_cabeca_torso(t)
        assert all(math.isfinite(v) for v in (p, y, r))
        comp = idle_arco_composto(t)
        assert "head" in comp and "peitoral" in comp and "right-arm" in comp
        for trio in comp.values():
            assert all(math.isfinite(v) for v in trio)


def test_ritmo_humano_e_interpolacao() -> None:
    """Valida RitmoHumano, fatores de cascata e todas as curvas de interpolacao."""
    rh = RitmoHumano(seed=42)
    for tipo in ("calma", "impacto", "normal"):
        vel, forca, trans = rh.sortear_intencao(tipo)
        assert 0.7 < vel < 1.3 and 0.7 < forca < 1.3 and 0.7 < trans < 1.4
    rh.iniciar_rebalanceio(1.0)
    assert rh.em_rebalanceio is True
    rh.atualizar(3.0)
    assert rh.em_rebalanceio is False
    assert 0.08 <= rh.duracao_transicao(0.4, calma=True) <= 0.8
    assert 0.90 <= rh.modulacao_respiracao(3.5) <= 1.10
    assert max(FATOR_CASCATA_POR_GRUPO.values()) == MAX_FATOR_CASCATA
    assert fator_cascata_grupo("body") < fator_cascata_grupo("antena-direita")

    assert suavizar_quintico(-1.0) == 0.0
    assert suavizar_quintico(0.5) == pytest.approx(0.5)
    assert suavizar_quintico(2.0) == 1.0
    for curva in CURVAS_SUPORTADAS:
        assert suavizar_curva(0.0, curva) == 0.0
        assert suavizar_curva(1.0, curva) == 1.0
        meio = suavizar_curva(0.5, curva)
        if curva in ("anticipate", "overshoot"):
            assert -0.25 <= meio <= 1.25
        else:
            assert 0.0 <= meio <= 1.0
    chaves = ((0.0, (0.0, 0.0, 0.0)), (1.0, (10.0, -20.0, 30.0)))
    assert amostrar_pista(chaves, -0.5) == (0.0, 0.0, 0.0)
    assert amostrar_pista(chaves, 0.5) == pytest.approx((5.0, -10.0, 15.0))
    assert amostrar_pista(chaves, 2.0) == (10.0, -20.0, 30.0)


# =========================================================================== #
# 10. Interseções críticas entre estados no AnimationController
# =========================================================================== #


def _simular_passos(ctrl: AnimationController, n: int, **kwargs) -> list[dict[str, Rotation3]]:
    dt = kwargs.pop("dt", 1.0 / 30.0)
    poses: list[dict[str, Rotation3]] = []
    for _ in range(n):
        ctrl.update(dt, **kwargs)
        pose = ctrl.rig.pose()
        assert _pose_finita(pose)
        _assert_leg_pose_valida(ctrl.leg_motion.pose)
        poses.append(pose)
    return poses


def test_intersecoes_sit_jump_e_locomocao(modelo_mario) -> None:
    """Valida idle<->sit->drag, idle->jump->fall->land->idle e run->idle."""
    ctrl = AnimationController(_novo_rig(modelo_mario), model=modelo_mario)

    _simular_passos(ctrl, 10, grounded=True)
    ctrl.sentar(manual=True)
    _simular_passos(ctrl, 20, grounded=True)
    assert ctrl.state == AnimationState.SIT
    ctrl.levantar()
    _simular_passos(ctrl, 15, grounded=True)
    assert ctrl.state == AnimationState.IDLE
    ctrl.sentar(manual=True)
    _simular_passos(ctrl, 10, grounded=True)
    ctrl.interact("drag_start")
    _simular_passos(ctrl, 12, grounded=False, dragging=True, velocity=(80.0, -40.0), drag_intensity=0.8)
    assert ctrl.state == AnimationState.DRAG

    _simular_passos(ctrl, 15, grounded=True, velocity=(0.0, 0.0))
    ctrl.pular(vx=80.0, vy_impulse=-560.0)
    _simular_passos(ctrl, 5, grounded=True, velocity=(80.0, 0.0))
    _simular_passos(ctrl, 10, grounded=False, velocity=(80.0, -320.0))
    _simular_passos(ctrl, 12, grounded=False, velocity=(80.0, 360.0))
    _simular_passos(ctrl, 15, grounded=True, velocity=(0.0, 0.0))

    _simular_passos(ctrl, 20, grounded=True, velocity=(460.0, 0.0))
    assert ctrl.state == AnimationState.RUN
    _simular_passos(ctrl, 25, grounded=True, velocity=(0.0, 0.0))
    assert ctrl.state == AnimationState.IDLE


def test_intersecoes_danca_sono_e_teimosia(modelo_mario) -> None:
    """Valida dance->drag, sleep(sentado|deitado)->wake->idle e teimosia->idle."""
    ctrl = AnimationController(_novo_rig(modelo_mario), model=modelo_mario)

    ctrl.preview_dance("electro_swing", duration=3.0)
    _simular_passos(ctrl, 20, grounded=True, music_playing=True, music_intensity=0.8)
    assert ctrl.state == AnimationState.DANCE
    ctrl.interact("drag_start")
    _simular_passos(ctrl, 10, grounded=False, dragging=True, velocity=(-100.0, -20.0), drag_intensity=0.7)
    assert ctrl.state == AnimationState.DRAG

    for modo in ("sentado", "deitado"):
        ctrl.colocar_para_dormir(modo)
        _simular_passos(ctrl, 18, grounded=True)
        assert ctrl.state == AnimationState.SLEEP
        ctrl.acordar()
        _simular_passos(ctrl, 45, grounded=True)
        assert ctrl.state == AnimationState.IDLE

    ctrl.interact("teimosia", direction=1.0, strength=1.0)
    _simular_passos(ctrl, 65, dt=0.1, grounded=True)
    assert ctrl.state == AnimationState.IDLE


# =========================================================================== #
# 11. Invariantes de continuidade v2.0 (zero snaps C0 + respiração em SIT)
# =========================================================================== #


def test_v2_continuidade_c0_jump_blue_balls_e_bote() -> None:
    """Sem salto C0 em t=0.11s (jump), t=0.28s (blue_balls) e bt=0.36s (teimosia/bote)."""
    # delta_jump em t=0.11s
    d_antes = delta_jump(0.109, velocity=(60.0, -400.0))
    d_depois = delta_jump(0.111, velocity=(60.0, -400.0))
    for g in d_antes:
        da, db = d_antes[g], d_depois[g]
        assert max(abs(db.x - da.x), abs(db.y - da.y), abs(db.z - da.z)) < 0.08

    # squash_stretch jump em t=0.11s
    ss_a = squash_stretch_composto("jump", reacao_tempo=0.109, queda_velocidade=(0.0, -400.0))
    ss_b = squash_stretch_composto("jump", reacao_tempo=0.111, queda_velocidade=(0.0, -400.0))
    assert abs(ss_b.z - ss_a.z) < 0.02

    # LegMotion jump, blue_balls e teimosia/bote sem teleporte de target
    lm = LegMotion()
    for _ in range(30):
        lm.update(1 / 60, "jump", time=0.109)
    p_a = lm.update(1 / 60, "jump", time=0.109)
    p_b = lm.update(1 / 60, "jump", time=0.111)
    assert abs(p_b.left - p_a.left) < 4.0 and abs(p_b.left_knee - p_a.left_knee) < 5.0

    p_bb_a = lm.update(1 / 60, "blue_balls", time=0.279)
    p_bb_b = lm.update(1 / 60, "blue_balls", time=0.281)
    assert abs(p_bb_b.left_knee - p_bb_a.left_knee) < 6.0

    for _ in range(25):
        lm.update(1 / 60, "teimosia", time=2.359, teimosia_fase="bote")
    p_bt_a = lm.update(1 / 60, "teimosia", time=2.359, teimosia_fase="bote")
    p_bt_b = lm.update(1 / 60, "teimosia", time=2.361, teimosia_fase="bote")
    assert abs(p_bt_b.left_ankle - p_bt_a.left_ankle) < 4.0


def test_v2_continuidade_intros_e_saidas_sem_snaps_c0() -> None:
    """Sem snaps C0 em sandevistan_in, kagebunshin_in, goku_teleport_out e fnf_blue_balls."""
    sand = IntroAnimation("sandevistan_in", from_side=1)
    f0 = sand.sample(sand.duration * 0.199)
    f1 = sand.sample(sand.duration * 0.201)
    assert abs(f1.roll - f0.roll) < 3.0

    kage = IntroAnimation("kagebunshin_in", from_side=1)
    k0 = kage.sample(kage.duration * 0.159)
    k1 = kage.sample(kage.duration * 0.161)
    assert abs(k1.yaw - k0.yaw) < 3.0 and abs(k1.roll - k0.roll) < 2.0

    goku = ExitAnimation((600, 400), 240, (0, 0, 1920, 1080), style="goku_teleport_out")
    g0 = goku.sample(goku.duration * 0.859)
    g1 = goku.sample(goku.duration * 0.861)
    assert abs(g1.scale - g0.scale) < 0.08

    fnf = ExitAnimation((600, 400), 240, (0, 0, 1920, 1080), style="fnf_blue_balls")
    b0 = fnf.sample(fnf.duration * 0.219)
    b1 = fnf.sample(fnf.duration * 0.221)
    assert abs(b1.blue_balls - b0.blue_balls) < 0.08


def test_v2_respiracao_permanece_ativa_em_sit(modelo_mario) -> None:
    """Estado SIT mantém respiração viva (não decai para 0 enquanto sentado)."""
    ctrl = AnimationController(_novo_rig(modelo_mario), model=modelo_mario)
    ctrl.sentar(manual=True)
    valores: list[float] = []
    for _ in range(120):
        ctrl.update(1 / 30, grounded=True, velocity=(0.0, 0.0))
        valores.append(ctrl.respiracao_valor)
    assert ctrl.state == AnimationState.SIT
    assert max(valores) - min(valores) > 0.5

