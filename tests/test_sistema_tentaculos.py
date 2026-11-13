"""Prevent disappearing tentacles and doors closing before retraction."""

import random

import pytest
from PySide6 import QtCore  # noqa: F401  # Carrega Qt antes do Panda3D no Windows.

# isort: split
from panda3d.core import GeomVertexReader, NodePath, Vec3

from sejoga.nucleo.esqueleto import ALL_GROUPS, IdlePersonality, Rig, Rotation3
from sejoga.tentaculos.coreografia_porta import FasePorta
from sejoga.tentaculos.sistema_tentaculos import (
    TOTAL_ENXURRADA,
    TentacleDirector,
    TentaclePool,
    TentacleState,
    compressao_saida,
)


def scene(count=1):
    rig = Rig(rest={name: Rotation3() for name in ALL_GROUPS})
    root = NodePath("test-root")
    pool = TentaclePool(
        rig, root, root, [Vec3(0)] * count, rng=random.Random(1), unit_scale=0.004
    )
    director = TentacleDirector(pool, rig, root, root, None, rng=random.Random(2))
    return pool, director


def test_retraction_preserves_volume_then_reaches_dormant_without_restarting():
    pool, director = scene()
    director.trigger_curious()
    director._door_current = director._door_requested = 70
    for _ in range(120):
        director.update(1 / 60, IdlePersonality.CALM)
    limb = pool.tentacles[0]
    initial = (limb.visible_tip() - limb.anchor).length()
    assert initial > 0.1
    pool.release(limb)
    director.update(1 / 60, IdlePersonality.CALM)
    assert (limb.visible_tip() - limb.anchor).length() > initial * 0.99
    previous = limb.reveal
    for _ in range(110):
        # Repeated cancellation must not reset the easing clock.
        pool.release(limb)
        director.update(1 / 60, IdlePersonality.CALM)
        assert limb.reveal <= previous
        previous = limb.reveal
    assert limb.state == TentacleState.DORMANT
    assert previous == pytest.approx(0, abs=1e-6)


def test_emergence_waits_for_door_and_root_never_drifts():
    pool, director = scene()
    director.trigger_curious()
    limb = pool.tentacles[0]
    for _ in range(10):
        director.update(1 / 60, IdlePersonality.PLAYFUL)
    assert limb.state_time == 0
    director._door_current = 70
    director._door_requested = 70
    for _ in range(120):
        director.update(1 / 60, IdlePersonality.PLAYFUL)
        assert limb.segments[0].pos.almostEqual(limb.anchor, 1e-7)
    assert (limb.segments[-1].pos - limb.anchor).length() > 0.1


def test_door_closing_respects_speed_limit():
    _, director = scene()
    director._door_current = 48
    director._door_requested = 0
    for _ in range(240):
        before = director._door_current
        director.update(1 / 60, IdlePersonality.STREET)
        assert 0 <= before - director._door_current <= 38 / 60 + 1e-6
    assert director._door_current < 0.01


def test_speaker_throw_releases_limbs_and_allows_pool_reuse():
    _pool, director = scene()
    director.trigger_speaker_throw()
    limb = director.speaker_throw_limbs[0]
    limb.target = Vec3(1.4, 0.3, 0.1)
    director._door_current = director._door_requested = 100
    for _ in range(38):
        director.update(1 / 60, IdlePersonality.CALM)
    assert limb.reveal > 0.9
    assert (limb.visible_tip() - limb.anchor).length() > 0.7
    assert limb.speaker_throw
    for _ in range(150):
        director.update(1 / 60, IdlePersonality.CALM)
    assert not director.speaker_throw_limbs
    assert not limb.speaker_throw
    assert limb.state == TentacleState.DORMANT
    director.trigger_curious()
    assert limb.state == TentacleState.CURIOUS
    assert not limb.speaker_throw


def test_fim_da_espiada_preserva_puxador_ate_interrupcao():
    _, director = scene()
    (puxador,) = director._spawn_curious(1)
    director._atuador = puxador
    director.coreografia.fase = FasePorta.PUXANDO

    director.encerrar_espiada(interromper=False)
    assert director.coreografia.fase == FasePorta.PUXANDO
    assert puxador.state == TentacleState.CURIOUS

    director.encerrar_espiada(interromper=True)
    assert director.coreografia.fase == FasePorta.FECHADA
    assert puxador.state == TentacleState.RETRACTING


def test_porta_chama_puxador_depois_da_ejecao_musical():
    _, director = scene()
    director.music_ejection = True
    director._door_current = director._door_requested = 100
    director.update(1 / 60, IdlePersonality.CALM)
    director.music_ejection = False
    director._door_requested = 0
    fases = set()
    for _ in range(300):
        director.update(1 / 60, IdlePersonality.CALM)
        fases.add(director.coreografia.fase)
    assert {FasePorta.ALCANCANDO, FasePorta.PUXANDO, FasePorta.VOLTANDO} <= fases
    assert director.coreografia.fase is FasePorta.FECHADA
    assert director._door_current < 1



def test_enxurrada_escala_curvas_e_reutiliza_pool():
    pool, director = scene(TOTAL_ENXURRADA)
    director.trigger_curious(TOTAL_ENXURRADA)
    assert len({limb.perfil for limb in pool.tentacles}) == 3
    assert all(limb.enxurrada for limb in pool.tentacles)
    (scale,) = {limb.length_scale for limb in pool.tentacles}
    assert scale > 1.0
    assert {limb.girth_scale for limb in pool.tentacles} == {scale}
    limb = pool.tentacles[0]
    assert compressao_saida(limb, limb.anchor) < compressao_saida(
        limb, limb.anchor + limb.reference_front * 0.5
    )
    for _ in range(480):
        director.update(1 / 60, IdlePersonality.CALM)
    assert all(t.state == TentacleState.DORMANT for t in pool.tentacles)
    (reused,) = pool.get_available(1)
    assert reused is limb
    assert not reused.enxurrada
    assert reused.length_scale == reused.girth_scale == 1.0


def test_morfologias_autorais_e_burst_limpa_ao_recolher():
    from sejoga.tentaculos.sistema_tentaculos import TENTACLE_MORPHOLOGIES

    pool, director = scene(TOTAL_ENXURRADA)
    morphs = {limb.morfologia for limb in pool.tentacles}
    assert morphs == set(TENTACLE_MORPHOLOGIES)

    director.trigger_sneeze()
    assert director.burst is True
    for _ in range(420):
        director.update(1 / 60, IdlePersonality.CALM)
    assert director.burst is False
    assert all(limb.state == TentacleState.DORMANT for limb in pool.tentacles)


def test_sincronizar_ancora_atualiza_alvo_com_cabeca_e_vence_obstaculo():
    from panda3d.core import Mat4, Vec3

    from sejoga.tentaculos.restricoes_tentaculos import ObstacleBox, TentacleContacts

    pool, director = scene(TOTAL_ENXURRADA)
    # Simula peitoral e paredes laterais bloqueando lados sem barrar o corredor frontal.
    contatos = TentacleContacts()
    contatos.boxes = [
        ObstacleBox(
            "chest",
            Vec3(-0.32, -0.32, -0.80),
            Vec3(0.32, 0.35, -0.02),
            Mat4.ident_mat(),
            Mat4.ident_mat(),
        ),
        ObstacleBox(
            "cabinet-left",
            Vec3(-0.22, -0.18, -0.15),
            Vec3(-0.14, 0.18, 0.35),
            Mat4.ident_mat(),
            Mat4.ident_mat(),
        ),
    ]
    for limb in pool.tentacles:
        limb.contacts = contatos
        limb.reference_front = Vec3(0.0, 0.707, -0.707)

    director.trigger_sneeze()
    # Cabeça volta ao horizonte logo após o tranco do espirro.
    for _ in range(90):
        for limb in pool.tentacles:
            director.sincronizar_ancora_e_frente(
                limb, Vec3(limb.anchor), Vec3(0.0, 1.0, 0.0)
            )
        director.update(1 / 60, IdlePersonality.CALM)

    front_extents = [
        max((seg.pos - limb.anchor).dot(limb.reference_front) for seg in limb.segments)
        for limb in pool.tentacles
        if limb.state != TentacleState.DORMANT
    ]
    assert front_extents
    assert min(front_extents) > 0.35


def test_cores_dos_tentaculos_preservam_tons_de_rosa():
    from sejoga.tentaculos.sistema_tentaculos import create_tentacle_geometry

    root = NodePath("palette-check")
    pool, _director = scene(4)
    for limb in pool.tentacles:
        create_tentacle_geometry(limb, root, root)
        reader = GeomVertexReader(limb.mesh_vdata, "color")
        while not reader.isAtEnd():
            r, g, b, _a = reader.getData4()
            assert r > b > g, f"cor saiu do rosa em {limb.morfologia}: {(r, g, b)}"
            assert g >= 0.08


def test_coreografia_puxador_alcance_curto():
    pool, director = scene(4)
    for idx, limb in enumerate(pool.tentacles):
        limb.anchor = Vec3(-0.02 * idx, 0.0, 0.9)
    director.trigger_curious(count=2)
    director._door_current = 52.0
    director.coreografia.assumir_aberta()

    fases_vistas: list[FasePorta] = []
    for _ in range(720):
        director.update(1 / 60, IdlePersonality.CALM)
        if not fases_vistas or fases_vistas[-1] is not director.coreografia.fase:
            fases_vistas.append(director.coreografia.fase)
        if director.coreografia.fase is FasePorta.ALCANCANDO:
            assert director.coreografia_ativa is True
            assert director._atuador is not None
            assert director._atuador.length_scale <= 0.6
        if director.coreografia.fase is FasePorta.FECHADA and director._door_current < 1.0:
            break

    assert FasePorta.ALCANCANDO in fases_vistas
    assert FasePorta.PUXANDO in fases_vistas
    assert FasePorta.VOLTANDO in fases_vistas
    assert director.coreografia.fase is FasePorta.FECHADA
    assert director.coreografia_ativa is False
