"""Gestos de reação: aceno, cutucar e alongar (amplitude, fases e segurança)."""

from __future__ import annotations

from itertools import pairwise
from math import atan2, ceil, degrees, floor, hypot

import pytest

import analise_curvas as aa
from sejoga.animacao import colisao_bracos as cb
from sejoga.animacao import gestos_tuning as tuning_gestos
from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
from sejoga.nucleo import cinematica as cin
from sejoga.nucleo.recursos import resolve_model
from sejoga.nucleo.modelo import load_model
from sejoga.animacao.braco_hpr import braco_hpr_graus
from sejoga.animacao.poses_base import pose_flourish, pose_interaction
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rig, Rotation3

FPS = 60.0
#: Tolerância (graus) de retorno ao repouso no fim do gesto.
TOLERANCIA_RETORNO_GRAUS = 1.0
#: Amplitude pico a pico mínima do antebraço no aceno (graus).
ACENO_PICO_A_PICO_MINIMO = 30.0
#: Janela (s) em que só o balanço mexe no antebraço (braço já no alto).
ACENO_JANELA = (0.9, 1.9)
#: Deslocamento mínimo do ombro no cutucar (graus).
CUTUCAR_DESLOCAMENTO_MINIMO = 35.0
#: Elevação mínima dos dois braços acima do repouso no alongar (graus).
ALONGAR_ELEVACAO_MINIMA = 40.0
#: Crossfade padrão do controlador (s): o gesto deve durar mais que isso.
CROSSFADE_PADRAO_S = 0.55
#: Teto de jerk (graus/s^3) por gesto. O limite global (8000) não vale para
#: gestos rápidos: um quíntico de 45 graus em 0,12 s já chega a milhões, e o
#: PoseResolver suaviza o resultado. Estes tetos protegem contra saltos novos.
TETO_JERK = {"wave": 6.0e4, "poke": 2.5e6, "stretch": aa.LIMIAR_JERK_TRANCO, "wake": 1.2e4}
GESTOS = {
    "wave": (tuning_gestos.ACENO_DURACAO_S, "flourish"),
    "poke": (tuning_gestos.CUTUCAR_DURACAO_S, "interaction"),
    "stretch": (tuning_gestos.ALONGAR_DURACAO_S, "flourish"),
    "wake": (1.2, "interaction"),
}


def _novo_rig() -> Rig:
    rig = Rig(rest={g: Rotation3() for g in ALL_GROUPS})
    rig.reset()

    return rig


def _aplicar(rig: Rig, gesto: str, t: float) -> None:
    if GESTOS[gesto][1] == "flourish":
        pose_flourish(rig, gesto, t)
    else:
        pose_interaction(rig, gesto, t)


def _amostrar(gesto: str) -> list[dict[str, Rotation3]]:
    """Pose do gesto em cada quadro de 60 fps, inclusive o instante final."""
    rig = _novo_rig()
    quadros = []
    for i in range(round(GESTOS[gesto][0] * FPS) + 1):
        _aplicar(rig, gesto, i / FPS)
        quadros.append(rig.pose())

    return quadros


def _serie(quadros: list[dict[str, Rotation3]], grupo: str, eixo: str) -> list[float]:
    return [degrees(getattr(q[grupo], eixo)) for q in quadros]


@pytest.fixture(scope="module")
def modelo():
    return load_model(resolve_model())


@pytest.fixture(scope="module", params=sorted(GESTOS))
def gesto(request):
    return request.param


def test_aceno_balanca_o_antebraco_pelo_menos_trinta_graus_pico_a_pico():
    z = _serie(_amostrar("wave"), "ant-arm", "z")
    inicio, fim = (round(s * FPS) for s in ACENO_JANELA)
    janela = z[inicio:fim]

    assert max(janela) - min(janela) >= ACENO_PICO_A_PICO_MINIMO


def test_aceno_nao_hiperestende_o_cotovelo_em_nenhum_quadro():
    quadros = _amostrar("wave")

    assert min(_serie(quadros, "ant-arm", "z")) >= 0.0
    assert max(_serie(quadros, "ant-arm2", "z")) <= 0.0


def test_cutucar_tem_quatro_fases_em_ordem():
    y = _serie(_amostrar("poke"), "right-arm", "y")
    recuo = round(tuning_gestos.CUTUCAR_RECUO_S * FPS)
    estocada = ceil((tuning_gestos.CUTUCAR_RECUO_S + tuning_gestos.CUTUCAR_ESTOCADA_S) * FPS)
    fim_sustentacao = floor((tuning_gestos.CUTUCAR_DURACAO_S - tuning_gestos.CUTUCAR_RECUPERACAO_S) * FPS)

    assert y[recuo] == pytest.approx(min(y))
    assert y[estocada] == pytest.approx(max(y))
    assert max(y) - min(y) >= CUTUCAR_DESLOCAMENTO_MINIMO
    assert _monotono(y[: recuo + 1], -1)
    assert _monotono(y[recuo : estocada + 1], 1)
    assert max(y[estocada : fim_sustentacao + 1]) - min(y[estocada : fim_sustentacao + 1]) < 1e-6
    assert _monotono(y[fim_sustentacao:], -1)


def _monotono(valores: list[float], sentido: int) -> bool:
    """Verdadeiro se a série nunca anda contra o ``sentido`` (+1 sobe, -1 desce)."""
    return all(sentido * (b - a) >= -1e-6 for a, b in pairwise(valores))


def _elevacao_da_mao(modelo, quadro: dict[str, Rotation3], lado: str) -> float:
    """Ângulo (graus) da mão acima do plano horizontal do ombro, pela FK."""
    ombro, mao = ("right-arm", "hand") if lado == "right" else ("left-arm", "hand2")
    dx, dy, dz = cin.subtrair(
        cin.posicao_no(modelo, mao, quadro), cin.posicao_no(modelo, ombro, quadro)
    )

    return degrees(atan2(dz, hypot(dx, dy)))


def test_alongar_ergue_os_dois_bracos_acima_do_repouso(modelo):
    quadros = _amostrar("stretch")

    for lado in ("right", "left"):
        elevacoes = [_elevacao_da_mao(modelo, q, lado) for q in quadros[::3]]

        assert max(elevacoes) - elevacoes[0] >= ALONGAR_ELEVACAO_MINIMA, lado


def test_alongar_sobe_os_dois_bracos_ao_mesmo_tempo():
    quadros = _amostrar("stretch")
    direito = _serie(quadros, "right-arm", "z")
    esquerdo = _serie(quadros, "left-arm", "z")
    pico_direito = max(range(len(direito)), key=lambda i: abs(direito[i] - direito[0]))
    pico_esquerdo = max(range(len(esquerdo)), key=lambda i: abs(esquerdo[i] - esquerdo[0]))

    assert abs(pico_direito - pico_esquerdo) <= 1


def test_alongar_abre_a_porta_no_maximo_vinte_e_cinco_graus():
    porta = _serie(_amostrar("stretch"), "door", "y")

    assert 0.0 < max(porta) <= 25.0


def test_gesto_termina_no_repouso(gesto):
    quadros = _amostrar(gesto)

    for grupo, final in quadros[-1].items():
        inicial = quadros[0][grupo]
        for eixo in "xyz":
            delta = abs(degrees(getattr(final, eixo) - getattr(inicial, eixo)))
            assert delta < TOLERANCIA_RETORNO_GRAUS, f"{gesto}.{grupo}.{eixo}: {delta:.2f}"


def test_gesto_nao_tem_salto_acima_do_projeto(gesto):
    quadros = _amostrar(gesto)

    def amostrar(t: float):
        quadro = quadros[min(len(quadros) - 1, round(t * FPS))]

        return {g: (degrees(r.x), degrees(r.y), degrees(r.z)) for g, r in quadro.items()}

    clipe = aa.ClipeAnalisavel(gesto, amostrar, duracao=GESTOS[gesto][0], loop=False)
    borda = 5
    for grupo, trio in aa.amostrar_clipe(clipe).items():
        for eixo, serie in zip("xyz", trio, strict=True):
            pico = max(abs(j) for j in serie.jerk[borda:-borda])
            assert pico <= TETO_JERK[gesto], f"{gesto}.{grupo}.{eixo}: {pico:.0f}"


def test_gesto_mantem_cotovelos_sem_hiperextensao(gesto):
    quadros = _amostrar(gesto)

    assert min(_serie(quadros, "ant-arm", "z")) >= 0.0
    assert max(_serie(quadros, "ant-arm2", "z")) <= 0.0


def test_gesto_nao_atravessa_o_corpo(modelo, gesto):
    for quadro in _amostrar(gesto)[::3]:
        for lado in ("right", "left"):
            assert cb.penetracao_do_lado(modelo, lado, quadro) <= cb.FOLGA_PENETRACAO_U, (
                f"{gesto}.{lado}"
            )


def test_gesto_dura_mais_que_o_crossfade_do_estado(gesto):
    duracao = AnimationController.REACTION_SECONDS[AnimationState(gesto)]

    assert duracao == GESTOS[gesto][0]
    assert duracao > CROSSFADE_PADRAO_S


def test_aceno_parte_do_repouso_do_idle():
    inicio = _amostrar("wave")[0]
    repouso = braco_hpr_graus("right", "idle")["right-arm"]

    assert degrees(inicio["right-arm"].z) == pytest.approx(repouso[2], abs=TOLERANCIA_RETORNO_GRAUS)
