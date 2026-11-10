"""Sono: suave, dentro de limites e com dedos relaxados e espelhados."""

from __future__ import annotations

from math import degrees

import analise_curvas as aa
from sejoga.animacao import sono_tuning as sono
from sejoga.animacao.animation import AnimationController, AnimationState
from sejoga.animacao.delta_states import delta_sleep
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rig, Rotation3

#: Duração (s) que cobre mais de um ciclo de cochilo e de respiração.
_DURACAO_S = 60.0
#: Folga (graus) sobre a pose de sono para o limite de cabeça e corpo.
_LIMITE_CABECA_X = 30.0
_LIMITE_CORPO = 12.0


def _amostrar(t: float) -> dict[str, tuple[float, float, float]]:
    """Delta de sono em graus por grupo."""
    return {
        g: (degrees(r.x), degrees(r.y), degrees(r.z))
        for g, r in delta_sleep(t).items()
    }


def test_delta_sleep_sem_tranco_em_um_minuto() -> None:
    clipe = aa.ClipeAnalisavel(
        nome="sono", amostrar=_amostrar, duracao=_DURACAO_S, loop=False
    )
    trancos = [c for c in aa.analisar(clipe) if c.categoria == "SUAVIDADE"]

    assert trancos == [], "; ".join(f"{c.grupo}.{c.eixo} {c.metrica}" for c in trancos)


def test_delta_sleep_cabeca_e_corpo_dentro_de_limites() -> None:
    for i in range(round(_DURACAO_S * aa.FPS)):
        amostra = _amostrar(i / aa.FPS)
        cabeca_x = amostra["head"][0]
        corpo = amostra["body"]

        assert -_LIMITE_CABECA_X <= cabeca_x <= sono.SONO_CABECA_X_BASE + 1.0
        assert all(abs(v) <= _LIMITE_CORPO for v in corpo)


def test_delta_sleep_cochilo_derruba_a_cabeca_so_no_fundo() -> None:
    fora = _amostrar(0.0)["head"][0]
    fundo = _amostrar(sono.SONO_COCHILO_FUNDO_S)["head"][0]

    assert fundo < fora + sono.SONO_COCHILO_GRAUS / 2


def test_delta_sleep_dedos_relaxados_e_espelhados() -> None:
    for t in (0.0, 7.3, 31.0):
        amostra = _amostrar(t)
        direita = amostra["fingers"][2]
        esquerda = amostra["fingers2"][2]

        assert direita == -esquerda
        assert 0.0 < direita < sono.SONO_DEDOS_CURL * 2


def test_entrada_no_sono_usa_crossfade_longo() -> None:
    rig = Rig(rest={g: Rotation3() for g in ALL_GROUPS})
    controle = AnimationController(rig)
    controle.update(0.1, sleep_after_idle_seconds=1)
    controle.idle_time = 10.0
    controle.update(0.1, sleep_after_idle_seconds=1)

    assert controle.state == AnimationState.SLEEP
    assert controle._active_transition_seconds >= sono.SONO_TRANSICAO_S
