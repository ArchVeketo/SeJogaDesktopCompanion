"""Testes para cenas curtas de idle e aviso/passagem dos tentáculos."""

from __future__ import annotations

from time import monotonic

import pytest

from sejoga.animacao.agencia import Meta, MetaTipo
from sejoga.animacao.cenas_idle import DURACOES_CENAS, amostrar_cena_idle
from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
from sejoga.nucleo.esqueleto import Rig
from sejoga.nucleo.modelo import load_model
from sejoga.nucleo.recursos import resolve_model


def test_cenas_idle_amostram_sem_erro_e_terminam():
    for nome, duracao in DURACOES_CENAS.items():
        inicio = amostrar_cena_idle(nome, 0.05)
        meio = amostrar_cena_idle(nome, duracao * 0.5)
        fim = amostrar_cena_idle(nome, duracao + 0.05)
        assert inicio.ativa
        assert meio.ativa
        assert not fim.ativa

    estouro = amostrar_cena_idle("fone_com_problema", 4.1)
    assert estouro.estouro_fone
    sentado = amostrar_cena_idle("fone_com_problema", 5.2)
    assert sentado.pernas_graus is not None

    choque = amostrar_cena_idle("argolas_antena", 1.95)
    assert choque.choque_argolas
    assert choque.brilho_argolas > 0.5


def test_controlador_dispara_e_conclui_cena_idle():
    rig = Rig.from_model(load_model(resolve_model()))
    ctrl = AnimationController(rig)
    ctrl.interact("ajeitar_fone")
    for _ in range(10):
        ctrl.update(1 / 60, grounded=True)
    assert ctrl.state == AnimationState.IDLE
    assert ctrl.cena_idle_amostra.ativa
    assert ctrl.cena_idle_amostra.nome == "ajeitar_fone"

    for _ in range(320):
        ctrl.update(1 / 60, grounded=True)
    assert not ctrl.cena_idle_amostra.ativa


@pytest.fixture
def controlador(monkeypatch):
    ctrl = AnimationController(Rig.from_model(load_model(resolve_model())))
    monkeypatch.setattr(ctrl.agencia, "_gerar_desejo_espontaneo", lambda: None)
    ctrl.update(0.1)
    return ctrl


@pytest.mark.parametrize(
    ("intensidade", "cenas_validas"),
    [
        (
            0.2,
            (
                "batida_guardada",
                "bater_pe_ritmo",
                "groove_um_pe",
                "ajeitar_fone",
                "checar_walkman",
                "escutar_fone",
            ),
        ),
        (
            0.7,
            (
                "escutar_fone",
                "groove_um_pe",
                "bater_pe_ritmo",
                "solo_guitarra_ar",
                "checar_walkman",
            ),
        ),
    ],
)
def test_inicio_da_musica_encena_antes_da_danca(controlador, intensidade, cenas_validas):
    musica = {"music_playing": True, "music_intensity": intensidade, "music_bpm": 100}
    controlador.update(0.1, **musica)
    assert controlador.cena_idle_amostra.ativa
    cena = controlador.cena_idle_amostra.nome
    assert cena in cenas_validas
    assert controlador.state == AnimationState.IDLE

    for _ in range(int(DURACOES_CENAS[cena] * 14) + 5):
        controlador.update(0.1, **musica)
    assert not controlador.cena_idle_amostra.ativa
    assert controlador.state == AnimationState.DANCE


def test_cena_musical_respeita_cooldown_e_novo_inicio(controlador):
    musica = {"music_playing": True, "music_intensity": 0.7, "dance_chance": 0.0}
    controlador.update(0.1, **musica)
    assert controlador.cena_idle_amostra.ativa
    for _ in range(85):
        controlador.update(0.1, **musica)
    for _ in range(8):
        controlador.update(0.1)

    controlador.update(0.1, **musica)
    assert not controlador.cena_idle_amostra.ativa
    while controlador.clock < 60.5:
        controlador.update(0.1, **musica)
        assert not controlador.cena_idle_amostra.ativa

    for _ in range(8):
        controlador.update(0.1)
    controlador.update(0.1, **musica)
    assert controlador.cena_idle_amostra.ativa
    assert controlador.cena_idle_amostra.nome in DURACOES_CENAS


def test_disfarce_pede_o_retorno_do_cursor_apos_oito_segundos(controlador):
    for _ in range(79):
        controlador.update(0.1, pointer_position=(100, 100))
    controlador.update(0.1, pointer_position=(120, 100))
    assert not controlador.cena_idle_amostra.ativa

    for _ in range(81):
        controlador.update(0.1, pointer_position=(120, 100))
    assert not controlador.cena_idle_amostra.ativa
    controlador.update(0.1, pointer_position=(140, 100))
    assert controlador.cena_idle_amostra.ativa
    assert controlador.cena_idle_amostra.nome in (
        "finger_guns_camera",
        "disfarcar_olhar",
        "segurar_porta_timido",
        "conferir_estilo",
    )


@pytest.mark.parametrize("bloqueio", ["meta", "pacote"])
def test_cena_contextual_respeita_acao_ativa(controlador, bloqueio):
    if bloqueio == "meta":
        controlador.agencia.meta_ativa = Meta(
            MetaTipo.OLHAR_PONTO, 200, 200, criado_em=monotonic()
        )
    else:
        controlador.iniciar_pacote_olhar_tela(lado=-1.0)

    controlador.update(0.1, music_playing=True, music_intensity=0.7, dance_chance=0.0)
    assert controlador.agencia.tem_meta_ativa or controlador.pacote_olhar_tela.ativo
    assert not controlador.cena_idle_amostra.ativa


@pytest.mark.parametrize(
    ("entrada", "estado"),
    [
        ({"dragging": True}, AnimationState.DRAG),
        ({"grounded": False, "gravity_active": True}, AnimationState.FALL),
    ],
)
def test_arraste_e_queda_interrompem_cena_contextual(controlador, entrada, estado):
    musica = {"music_playing": True, "music_intensity": 0.7}
    controlador.update(0.1, **musica)
    assert controlador.cena_idle_amostra.ativa

    controlador.update(0.1, **musica, **entrada)
    assert controlador.state == estado
    assert not controlador.cena_idle_amostra.ativa


def test_choque_antenas_3d_tem_envelope_suave_e_ponte_intermitente():
    """Coroas fazem fade-out suave e ponte voltaica dispara em rajadas intermitentes."""
    from math import isfinite

    from panda3d.core import NodePath
    from PySide6 import QtCore  # noqa: F401

    from sejoga.render.choque_antenas_3d import ChoqueAntenas3D

    head = NodePath("head")
    ad = head.attachNewNode("ant-dir")
    ae = head.attachNewNode("ant-esq")
    ad.setPos(0.4, 0.0, 0.9)
    ae.setPos(-0.4, 0.0, 0.9)
    choque = ChoqueAntenas3D(head, ad, ae)

    ponte_visivel = 0
    for _ in range(180):
        choque.atualizar(1 / 60, aviso_antena=1.0, choque_argolas=True)
        if not choque._arco_np.isHidden():
            ponte_visivel += 1
    assert isfinite(choque._ganho_visivel)
    assert choque._ganho_visivel > 0.6
    assert not choque._pivos[0][0].isHidden()
    assert 0 < ponte_visivel < 72, f"duty-cycle esperado intermitente, obtido {ponte_visivel}/180"

    choque.atualizar(1 / 60, aviso_antena=0.0, choque_argolas=False)
    assert choque._ganho_visivel > 0.3
    assert not choque._pivos[0][0].isHidden()
    assert choque._arco_np.isHidden()

    for _ in range(30):
        choque.atualizar(1 / 60, aviso_antena=0.0, choque_argolas=False)
    assert choque._ganho_visivel == pytest.approx(0.0, abs=1e-3)
    assert choque._pivos[0][0].isHidden()
    assert choque._arco_np.isHidden()


def test_novos_idles_controlam_dedos_e_transicionam_sem_estalo(controlador):
    """Novos idles têm pernas, dedos individuais (quando aplicável) e retorno suave."""
    import math

    novos = (
        "conferir_luva",
        "pensar_gabinete",
        "segurar_porta_timido",
        "checar_walkman",
        "alongar_pescoco_ombros",
        "groove_um_pe",
    )
    for nome in novos:
        assert nome in DURACOES_CENAS
        controlador.interact(nome)
        dedos_vistos = []
        anterior = dict(controlador.update(1 / 60, grounded=True))
        pior = 0.0
        passos = int(DURACOES_CENAS[nome] * 78) + 25
        for _ in range(passos):
            atual = dict(controlador.update(1 / 60, grounded=True))
            if controlador.dedos_clipe_ativo is not None:
                dedos_vistos.append(controlador.dedos_clipe_ativo)
            pior = max(
                pior,
                max(
                    math.degrees(
                        max(
                            abs(a.x - anterior[k].x),
                            abs(a.y - anterior[k].y),
                            abs(a.z - anterior[k].z),
                        )
                    )
                    for k, a in atual.items()
                    if k in anterior
                ),
            )
            anterior = atual
        assert not controlador.cena_idle_amostra.ativa
        assert pior < 12.0, nome
        if nome in ("conferir_luva", "pensar_gabinete", "segurar_porta_timido", "checar_walkman"):
            assert len(set(dedos_vistos)) > 5, nome


def test_controlador_dispara_gesto_point_e_mao_esquerda_independente(controlador):
    controlador.interact("point", left_gesture="thumbs_up")
    controlador.update(1 / 60, grounded=True)
    assert controlador.state == AnimationState.POINT
    assert controlador.gesto_mao_esquerda == "thumbs_up"


def test_cenas_estacionarias_funcionam_sentado_sem_levantar_pernas(controlador):
    controlador.alternar_sentado()
    for _ in range(90):
        controlador.update(1 / 60, grounded=True, velocity=(0.0, 0.0))
    assert controlador.state == AnimationState.SIT
    controlador.interact("ajeitar_fone")
    for _ in range(15):
        controlador.update(1 / 60, grounded=True)
    assert controlador.state == AnimationState.SIT
    assert controlador.cena_idle_amostra.ativa
    assert controlador.cena_idle_amostra.nome == "ajeitar_fone"
    assert controlador.leg_motion.pose.left < -70.0
    assert controlador.leg_motion.pose.left_knee > 30.0
