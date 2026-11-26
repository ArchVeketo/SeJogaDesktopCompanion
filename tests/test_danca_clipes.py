"""Testes dos clipes de dança extraídos de emotes e integração no DanceMotion."""

from __future__ import annotations

import pytest

from sejoga.animacao.danca_clipes import (
    amostrar_clipe_danca,
    carregar_clipe_danca,
    listar_clipes_danca,
)
from sejoga.animacao.movimento_danca import DanceMotion
from sejoga.nucleo.esqueleto import Rig
from sejoga.nucleo.modelo import load_model
from sejoga.nucleo.recursos import resolve_model


def test_deslocamento_tem_trajeto_real_e_acompanha_a_fase():
    from sejoga.animacao.danca_clipes import (
        _catmull_rom_escalar,
        amostrar_deslocamento_emote,
        carregar_clipe_emote,
    )

    clipe = carregar_clipe_emote("jazz_dance")
    assert clipe is not None
    assert max(abs(x) for x, _ in clipe.deslocamento) > 0.15
    i = 35
    p0, p1, p2, p3 = clipe.deslocamento[i - 1 : i + 3]
    meio = amostrar_deslocamento_emote(clipe, (i + 0.5) / clipe.fps)
    esperado = (
        _catmull_rom_escalar(p0[0], p1[0], p2[0], p3[0], 0.5),
        _catmull_rom_escalar(p0[1], p1[1], p2[1], p3[1], 0.5),
    )
    assert meio == pytest.approx(esperado)


def test_clipes_emote_carregam_e_fazem_loop_continuo():
    clipes = listar_clipes_danca()
    assert "electro_swing" in clipes
    assert "boogie_down" in clipes

    for nome in clipes:
        clipe = carregar_clipe_danca(nome)
        assert clipe is not None
        assert len(clipe.loop) >= 60
        dur_loop = len(clipe.loop) / clipe.fps
        dur_intro = len(clipe.intro) / clipe.fps
        a = amostrar_clipe_danca(nome, dur_intro)
        b = amostrar_clipe_danca(nome, dur_intro + dur_loop)
        assert a is not None and b is not None
        for osso in a:
            assert abs(a[osso][0] - b[osso][0]) < 1e-3


def test_dance_motion_executa_clipe_emote():
    rig = Rig.from_model(load_model(resolve_model()))
    dm = DanceMotion()
    dm.style = "electro_swing"
    for _ in range(30):
        dm.update(1 / 60, level=0.8, bass=0.7, bpm=120.0, beat=True)
        dm.apply(rig)
    assert len(dm.pose) > 0


def test_velocidade_variavel_por_clipe_escala_avanco_temporal():
    lento = carregar_clipe_danca("aloa")
    rapido = carregar_clipe_danca("griddy")
    assert lento is not None and rapido is not None
    assert lento.fps == 30.0 and rapido.fps == 30.0
    assert rapido.velocidade > lento.velocidade

    dm_lento = DanceMotion()
    dm_lento.override = dm_lento.style = "aloa"
    dm_rapido = DanceMotion()
    dm_rapido.override = dm_rapido.style = "griddy"
    # Aquece até convergir ao BPM nativo e compara a taxa constante no regime.
    for _ in range(180):
        dm_lento.update(1 / 60, level=0.6, bass=0.4, bpm=lento.bpm_nativo)
        dm_rapido.update(1 / 60, level=0.6, bass=0.4, bpm=rapido.bpm_nativo)
    t0_l, t0_r = dm_lento.tempo_clipe, dm_rapido.tempo_clipe
    for _ in range(60):
        dm_lento.update(1 / 60, level=0.6, bass=0.4, bpm=lento.bpm_nativo)
        dm_rapido.update(1 / 60, level=0.6, bass=0.4, bpm=rapido.bpm_nativo)
    dl = dm_lento.tempo_clipe - t0_l
    dr = dm_rapido.tempo_clipe - t0_r
    assert dr > dl
    assert abs(dl - lento.velocidade) < 0.05
    assert abs(dr - rapido.velocidade) < 0.05


def test_clipes_emote_preservam_amplitude_membros_e_joelhos():
    from math import degrees

    # Poses extremas reais presentes nas coreografias de Fortnite:
    criss = carregar_clipe_danca("criss_cross")
    brk = carregar_clipe_danca("breakdance")
    es = carregar_clipe_danca("electro_swing")
    assert criss is not None and brk is not None and es is not None

    max_knee_brk = max(
        max(p.get("left_knee", 0.0), p.get("right_knee", 0.0))
        for p in brk.quadros_pernas
    )
    min_knee_es = min(
        min(p.get("left_knee", 99.0), p.get("right_knee", 99.0))
        for p in es.quadros_pernas
    )
    min_elbow_es = degrees(
        min(
            min(abs(q["ant-arm"].z), abs(q["ant-arm2"].z))
            for q in es.quadros
            if "ant-arm" in q and "ant-arm2" in q
        )
    )
    assert max_knee_brk >= 85.0  # pernas bem dobradas quando a coreografia agacha
    assert min_knee_es <= 12.0  # pernas esticadas nos passos estendidos
    assert min_elbow_es <= 15.0  # braços esticados quando estendidos
    assert brk.quat_raiz  # breakdance preserva rotação 3D completa do corpo
    up_z_brk = [qw * qw - qx * qx - qy * qy + qz * qz for qw, qx, qy, qz in brk.quat_raiz]
    assert min(up_z_brk) < 0.0  # inversões de cabeça para baixo preservadas
    seam_dot = abs(sum(a * b for a, b in zip(brk.quat_raiz[0], brk.quat_raiz[-1], strict=True)))
    assert seam_dot > 0.99  # emenda de loop 3D contínua sem salto
    for emote_giro in ("jazz_dance", "kpop_dance_03"):
        cl = carregar_clipe_danca(emote_giro)
        assert cl is not None and cl.raiz
        diff_seam = ((cl.raiz[-1][1] - cl.raiz[0][1] + 180.0) % 360.0) - 180.0
        assert abs(diff_seam) < 1.0  # emenda angular contínua após giro completo


def test_acoes_mixamo_catalogo_e_clamping_nao_loop() -> None:
    from sejoga.animacao.danca_clipes import (
        amostrar_clipe_completo,
        carregar_clipe_acao,
        duracao_clipe_emote,
        listar_clipes_acao,
    )

    esperados = {
        "arm_stretching",
        "baseball_hit",
        "boxing",
        "cover_to_stand",
        "dodging_right",
        "drop_kick",
        "run_mixamo",
        "swimming",
        "walk_standard",
        "walk_strafe_left",
        "walk_strafe_right",
        "walk_strafe_slow",
    }
    disponiveis = set(listar_clipes_acao())
    assert esperados <= disponiveis
    for nome in esperados:
        clipe = carregar_clipe_acao(nome)
        assert clipe is not None and duracao_clipe_emote(clipe) > 0.4

    nao_loop = carregar_clipe_acao("cover_to_stand")
    assert nao_loop is not None and nao_loop.em_loop is False
    dur = duracao_clipe_emote(nao_loop)
    pose_fim, _, _, yaw_fim, _, _ = amostrar_clipe_completo(nao_loop, dur)
    pose_alem, _, _, yaw_alem, _, _ = amostrar_clipe_completo(nao_loop, dur + 2.5)
    assert abs(yaw_alem - yaw_fim) < 1e-4
    assert abs(pose_alem["right-arm"].z - pose_fim["right-arm"].z) < 1e-4


def test_amostragem_dedos_e_espelho_clipe_completo() -> None:
    from sejoga.animacao.danca_clipes import (
        amostrar_clipe_completo,
        amostrar_dedos_emote,
        carregar_clipe_acao,
    )

    swim = carregar_clipe_acao("swimming")
    walk = carregar_clipe_acao("walk_standard")
    assert swim is not None and walk is not None
    dedos = amostrar_dedos_emote(swim, 0.5)
    assert dedos is not None and len(dedos) == 2
    assert len(dedos[0]) == 5 and len(dedos[1]) == 5
    assert all(0.0 <= v <= 1.0 for lado in dedos for v in lado)

    _p0, pernas0, _, yaw0, _, _ = amostrar_clipe_completo(walk, 0.25, espelhar=False)
    _p1, pernas1, _, yaw1, _, _ = amostrar_clipe_completo(walk, 0.25, espelhar=True)
    assert abs(pernas0["left"] - pernas1["right"]) < 1e-4
    assert abs(pernas0["left_knee"] - pernas1["right_knee"]) < 1e-4
    assert abs(yaw0 + yaw1) < 1e-4


def test_deduplicacao_loop_catmull_wrap_e_antispike_em_loops() -> None:
    import math

    from sejoga.animacao.danca_clipes import (
        _catmull_rom_ang,
        carregar_clipe_acao,
    )

    jazz = carregar_clipe_danca("jazz_dance")
    run_clipe = carregar_clipe_acao("run_mixamo")
    strafe = carregar_clipe_acao("walk_strafe_slow")
    brk = carregar_clipe_danca("breakdance")
    assert jazz is not None and run_clipe is not None and strafe is not None and brk is not None
    # Loop deduplicado mantém quadros únicos (sem duplicar o quadro final no inicial) e run_mixamo mantém ciclo denso.
    assert len(jazz.quadros) >= 200
    assert len(run_clipe.quadros) >= 12
    assert jazz.quadros[0] != jazz.quadros[-1] or len(jazz.quadros) > 1
    # Wrap Catmull-Rom em torno de ±pi interpola pelo menor arco sem atravessar zero.
    curva = _catmull_rom_ang(math.pi - 0.15, math.pi - 0.05, -math.pi + 0.05, -math.pi + 0.15, 0.5)
    assert abs(abs(curva) - math.pi) < 0.05
    # Anti-spike em loops e pernas evita saltos bruscos de punho/perna.
    pior_punho = max(
        math.degrees(abs(((brk.quadros[i][g].z - brk.quadros[i - 1][g].z + math.pi) % math.tau) - math.pi))
        for i in range(1, len(brk.quadros))
        for g in ("hand", "hand2")
        if g in brk.quadros[i] and g in brk.quadros[i - 1]
    )
    assert pior_punho < 25.0
    pior_reverso_perna = max(
        min(abs(cur[k] - ant[k]), abs(seg[k] - cur[k]))
        for ant, cur, seg in zip(strafe.quadros_pernas, strafe.quadros_pernas[1:], strafe.quadros_pernas[2:], strict=False)
        for k in cur
        if (cur[k] - ant.get(k, 0.0)) * (seg.get(k, 0.0) - cur[k]) < 0.0
    )
    assert pior_reverso_perna <= 22.0


