"""Locomoção, arraste e queda: fase única, suavidade e anti-atravessamento."""

from __future__ import annotations

from itertools import pairwise
from math import degrees, tau

import pytest

import analise_curvas as aa
from sejoga.animacao import animation as modulo_animacao
from sejoga.animacao import colisao_bracos as cb
from sejoga.animacao.anim_clips import CLIPES
from sejoga.animacao.animation import AnimationController, AnimationState
from sejoga.animacao.body_motion import BodyPose
from sejoga.animacao.delta_states import delta_drag, delta_fall, delta_walk
from sejoga.animacao.leg_motion import FASE_CAMINHADA, FASE_CORRIDA
from sejoga.animacao.rig_base import pose_repouso
from sejoga.nucleo.assets import resolve_model
from sejoga.nucleo.model import load_model
from sejoga.nucleo.rig import ALL_GROUPS, Rig, Rotation3

FPS = 60.0
QUADROS_AQUECIMENTO = 30
AMOSTRAS_POR_CICLO = 48
#: Folga sobre o jerk analítico do easing quíntico (diferenças finitas a 60 fps).
MARGEM_JERK = 1.5
#: Pico de jerk do easing quíntico em um trecho: 60 * delta / duração^3.
COEFICIENTE_JERK_QUINTICO = 60.0
MODOS = (("walk", FASE_CAMINHADA, False), ("run", FASE_CORRIDA, True))


def _controlador() -> AnimationController:
    return AnimationController(Rig(rest={g: Rotation3() for g in ALL_GROUPS}))


def test_walk_usa_a_fase_de_passada_das_pernas(monkeypatch):
    animacao = _controlador()
    chamadas: list[tuple[float, float]] = []
    original = modulo_animacao.delta_walk

    def espiao(fase, run=False):
        chamadas.append((fase, animacao.leg_motion.phase))

        return original(fase, run)

    monkeypatch.setattr(modulo_animacao, "delta_walk", espiao)

    for _ in range(QUADROS_AQUECIMENTO):
        animacao.update(1 / FPS, velocity=(200, 0))

    assert animacao.state == AnimationState.WALK
    assert chamadas
    assert all(fase == pernas for fase, pernas in chamadas)
    assert chamadas[-1][0] > 0.0


def _trechos_do_clipe(nome: str, frequencia: float):
    """(grupo, eixo, pico de jerk quíntico) de cada trecho de cada track."""
    for chave, keys in CLIPES[nome].tracks.items():
        grupo = chave.split(":")[0]
        for (t0, v0), (t1, v1) in pairwise(keys):
            duracao = (t1 - t0) / frequencia
            for eixo, (a, b) in zip("xyz", zip(v0, v1, strict=True), strict=True):
                if a != b:
                    yield grupo, eixo, COEFICIENTE_JERK_QUINTICO * abs(b - a) / duracao**3


def _limite_de_jerk(nome: str, frequencia: float) -> dict[tuple[str, str], float]:
    limites: dict[tuple[str, str], float] = {}
    for grupo, eixo, jerk in _trechos_do_clipe(nome, frequencia):
        limites[grupo, eixo] = limites.get((grupo, eixo), 0.0) + jerk

    return limites


@pytest.mark.parametrize(("nome", "frequencia", "corrida"), MODOS)
def test_ciclo_de_passada_fecha_sem_pop_nem_tranco_alem_do_projeto(
    nome, frequencia, corrida
):
    # Duração em frames inteiros: o ciclo fecha exatamente na grade de 60 fps.
    duracao = round(FPS / frequencia) / FPS
    frequencia = 1.0 / duracao

    def amostrar(t: float):
        delta = delta_walk(t * frequencia * tau, run=corrida)

        return {g: (degrees(r.x), degrees(r.y), degrees(r.z)) for g, r in delta.items()}

    clipe = aa.ClipeAnalisavel(nome, amostrar, duracao=duracao, loop=True)
    achados = aa.analisar(clipe)
    limites = _limite_de_jerk(nome, frequencia)

    assert [c for c in achados if c.categoria == "LOOP"] == []
    # Um ciclo rápido excede LIMIAR_JERK_TRANCO por natureza (uma senóide de
    # 14 graus a 1,35 Hz já passa); aqui vale o limite do próprio easing.
    for grupo, trio in aa.amostrar_clipe(clipe).items():
        for eixo, serie in zip("xyz", trio, strict=True):
            pico = max(abs(j) for j in serie.jerk)
            teto = limites.get((grupo, eixo), 0.0) * MARGEM_JERK
            assert pico <= teto + 1e-6, f"{nome}.{grupo}.{eixo}: {pico:.0f} > {teto:.0f}"


def _compor(delta: dict[str, Rotation3]) -> dict[str, Rotation3]:
    return {
        g: Rotation3(
            r.x + delta.get(g, Rotation3()).x,
            r.y + delta.get(g, Rotation3()).y,
            r.z + delta.get(g, Rotation3()).z,
        )
        for g, r in pose_repouso().items()
    }


@pytest.fixture(scope="module")
def modelo():
    return load_model(resolve_model())


def _sem_atravessar(modelo, delta: dict[str, Rotation3]) -> None:
    pose = _compor(delta)
    for lado in ("right", "left"):
        assert cb.penetracao_do_lado(modelo, lado, pose) <= cb.FOLGA_PENETRACAO_U, lado


@pytest.mark.parametrize("corrida", [False, True])
def test_walk_e_run_nao_atravessam_o_corpo(modelo, corrida):
    for i in range(AMOSTRAS_POR_CICLO):
        _sem_atravessar(modelo, delta_walk(tau * i / AMOSTRAS_POR_CICLO, run=corrida))


@pytest.mark.parametrize("corrida", [False, True])
def test_walk_e_run_mantem_cotovelo_sem_hiperextensao(corrida):
    for i in range(AMOSTRAS_POR_CICLO):
        pose = _compor(delta_walk(tau * i / AMOSTRAS_POR_CICLO, run=corrida))
        assert pose["ant-arm"].z >= 0.0
        assert pose["ant-arm2"].z <= 0.0


@pytest.mark.parametrize("velocidade", [(0, -500), (0, 500), (400, 300)])
def test_queda_nao_atravessa_o_corpo(modelo, velocidade):
    for i in range(AMOSTRAS_POR_CICLO):
        _sem_atravessar(modelo, delta_fall(3.0 * i / AMOSTRAS_POR_CICLO, velocidade))


@pytest.mark.parametrize("parte", ["body", "right-arm", "left-arm", "legs"])
def test_arraste_nao_atravessa_o_corpo(modelo, parte):
    for i in range(AMOSTRAS_POR_CICLO):
        u = i / AMOSTRAS_POR_CICLO - 0.5
        movimento = BodyPose(roll=40 * u, pitch=20 * u, limb_swing=30 * u)
        _sem_atravessar(modelo, delta_drag(movimento, parte))

