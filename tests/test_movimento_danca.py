"""Testa a coreografia da dança."""

from math import isfinite, tau

import pytest

from sejoga.animacao import danca_tuning as tune
from sejoga.animacao.danca_frases_tuning import FRASES
from sejoga.animacao.movimento_danca import DanceMotion
from sejoga.animacao.movimento_pernas import LegMotion
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rig, Rotation3

FPS = 60.0
#: Aquecimento (s) descartado: tempo, força e acento ainda convergem.
AQUECIMENTO_S = 4.0
#: Duração (s) analisada por estilo.
DURACAO_S = 24.0
#: Energia, grave e BPM da prévia de cada estilo (controlador_animacao.py).
AUDIO_DO_ESTILO = {
    "head_bob": (0.2, 0.03, 80.0),
    "hip_hop": (0.5, 0.3, 95.0),
    "rock": (0.6, 0.15, 135.0),
    "breakdance": (0.9, 0.6, 145.0),
    "street_groove": (0.65, 0.4, 108.0),
    "graffiti_dance": (0.55, 0.25, 100.0),
    "cyber_bounce": (0.75, 0.5, 124.0),
}


def _contribuicoes(estilo: str) -> list[dict[str, Rotation3]]:
    """Pose autoral de dança a 60 fps, com BPM e áudio fixos."""
    energia, grave, bpm = AUDIO_DO_ESTILO[estilo]
    danca = DanceMotion()
    danca.override = danca.style = estilo
    rig = Rig(rest={g: Rotation3() for g in ALL_GROUPS})
    quadros = []

    for _ in range(round((AQUECIMENTO_S + DURACAO_S) * FPS)):
        danca.update(1 / FPS, energia, grave, bpm)
        rig.reset()
        quadros.append(danca.contribuicao(rig))

    return quadros[round(AQUECIMENTO_S * FPS) :]


def test_styles_follow_sustained_energy_and_bass_not_single_peak():
    dance = DanceMotion()
    dance.update(0.02, 1, 1, 120, True)
    assert dance.style == "head_bob"

    for _ in range(600):
        dance.update(1 / 60, 0.5, 0.3, 95)
    assert dance.style == "hip_hop"
    for _ in range(600):
        dance.update(1 / 60, 0.95, 0.7, 150)
    assert dance.style == "breakdance"
    for _ in range(600):
        dance.update(1 / 60, 0.08, 0.01, 75)
    assert dance.style == "head_bob"


def test_shared_phase_keeps_leg_targets_independent_of_internal_clock():
    from sejoga.animacao.movimento_pernas import LegMotion

    first, second = LegMotion(), LegMotion()
    second.phase = 50
    for i in range(120):
        phase = i / 60 * 6.28
        a = first.update(1 / 60, "dance", dance_phase=phase, dance_strength=0.2)
        b = second.update(1 / 60, "dance", dance_phase=phase, dance_strength=0.2)
        assert a == b


@pytest.mark.parametrize("estilo", sorted(FRASES))
def test_danca_entrega_rotacoes_finitas_ao_rig(estilo):
    for pose in _contribuicoes(estilo):
        assert all(
            isfinite(eixo)
            for rotacao in pose.values()
            for eixo in (rotacao.x, rotacao.y, rotacao.z)
        )


def _passo_em(estilo: str, bpm: float, batidas: float) -> int:
    """Índice do passo da frase após ``batidas`` batidas inteiras no ``bpm``."""
    danca = DanceMotion()
    danca.style = estilo
    danca.tempo = bpm
    danca.style_beats = batidas
    danca.phase = batidas * tau

    return danca._posicao_na_frase(FRASES[estilo])[0]


def test_rock_acima_do_limite_de_bpm_troca_de_passo_a_cada_duas_batidas():
    bpm = tune.ROCK_MEIO_TEMPO_BPM + 10

    assert _passo_em("rock", bpm, 0) == _passo_em("rock", bpm, 1)
    assert _passo_em("rock", bpm, 0) != _passo_em("rock", bpm, 2)


def test_rock_abaixo_do_limite_de_bpm_troca_de_passo_a_cada_batida():
    bpm = tune.ROCK_MEIO_TEMPO_BPM - 10

    assert _passo_em("rock", bpm, 0) != _passo_em("rock", bpm, 1)


def test_rock_flexiona_os_joelhos_mais_no_onset_do_que_no_contratempo():
    def joelho_assentado(fase: float) -> float:
        pernas = LegMotion()
        for _ in range(120):
            pose = pernas.update(
                1 / FPS,
                "dance",
                dance_phase=fase,
                dance_strength=1.0,
                dance_style="rock",
            )

        return pose.left_knee

    assert joelho_assentado(0.0) > joelho_assentado(tau / 2) + 1.0
