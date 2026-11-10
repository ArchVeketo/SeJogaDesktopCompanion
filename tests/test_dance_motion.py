from itertools import pairwise
from math import degrees

import pytest

import analise_curvas as aa
from sejoga.animacao.dance_frases_tuning import FRASES
from sejoga.animacao.dance_motion import DanceMotion
from sejoga.nucleo.rig import ALL_GROUPS, Rig, Rotation3

FPS = 60.0
#: Aquecimento (s) descartado: tempo, força e acento ainda convergem.
AQUECIMENTO_S = 4.0
#: Duração (s) analisada por estilo.
DURACAO_S = 24.0
#: Energia, grave e BPM da prévia de cada estilo (animation.py).
AUDIO_DO_ESTILO = {
    "head_bob": (0.2, 0.03, 80.0),
    "hip_hop": (0.5, 0.3, 95.0),
    "rock": (0.6, 0.15, 135.0),
    "breakdance": (0.9, 0.6, 145.0),
}
#: Teto de jerk (graus/s^3) por estilo. O limiar global (8000) não vale para o
#: acento no onset da batida: o nod/headbang é um golpe por projeto e as molas de
#: 4,5 Hz só o amortecem. O teto fica abaixo do pior caso do código anterior
#: (rock 227 mil, hip hop 146 mil, break 60 mil) e protege contra saltos novos.
TETO_JERK = {"head_bob": 1.0e5, "hip_hop": 1.5e5, "rock": 2.3e5, "breakdance": 1.5e5}
#: Maior variação (graus) de um eixo entre dois quadros de 60 fps.
SALTO_MAXIMO_GRAUS = 6.0


def _contribuicoes(estilo: str) -> list[dict[str, Rotation3]]:
    """Pose de dança suavizada (molas) a 60 fps, com BPM e áudio fixos."""
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
    dance.update(.02, 1, 1, 120, True)
    assert dance.style == 'head_bob'

    for _ in range(600):
        dance.update(1/60, .5, .3, 95)
    assert dance.style == 'hip_hop'
    for _ in range(600):
        dance.update(1/60, .95, .7, 150)
    assert dance.style == 'breakdance'
    for _ in range(600):
        dance.update(1/60, .08, .01, 75)
    assert dance.style == 'head_bob'


def test_shared_phase_keeps_leg_targets_independent_of_internal_clock():
    from sejoga.animacao.leg_motion import LegMotion
    first, second = LegMotion(), LegMotion()
    second.phase = 50
    for i in range(120):
        phase = i/60*6.28
        a = first.update(1/60, 'dance', dance_phase=phase, dance_strength=.2)
        b = second.update(1/60, 'dance', dance_phase=phase, dance_strength=.2)
        assert a == b


@pytest.mark.parametrize("estilo", sorted(FRASES))
def test_danca_por_passos_nao_passa_do_teto_de_jerk_do_estilo(estilo):
    quadros = _contribuicoes(estilo)

    def amostrar(t: float):
        quadro = quadros[min(len(quadros) - 1, round(t * FPS))]

        return {g: (degrees(r.x), degrees(r.y), degrees(r.z)) for g, r in quadro.items()}

    clipe = aa.ClipeAnalisavel(estilo, amostrar, duracao=DURACAO_S - 0.1, loop=False)
    for grupo, trio in aa.amostrar_clipe(clipe).items():
        for eixo, serie in zip("xyz", trio, strict=True):
            pico = max(abs(j) for j in serie.jerk)
            assert pico <= TETO_JERK[estilo], f"{estilo}.{grupo}.{eixo}: {pico:.0f}"


@pytest.mark.parametrize("estilo", sorted(FRASES))
def test_danca_por_passos_nao_tem_salto_entre_quadros(estilo):
    quadros = _contribuicoes(estilo)

    for anterior, atual in pairwise(quadros):
        for grupo, rot in atual.items():
            for eixo in "xyz":
                delta = degrees(abs(getattr(rot, eixo) - getattr(anterior[grupo], eixo)))
                assert delta < SALTO_MAXIMO_GRAUS, f"{estilo}.{grupo}.{eixo}: {delta:.1f}"
