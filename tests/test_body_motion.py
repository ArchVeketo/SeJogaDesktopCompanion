from math import isfinite

import pytest

from sejoga.animacao.body_motion import BodyMotion, GiroCorpo, Spring


def test_spring_response_is_frame_rate_independent():
    results = []
    for rate in (30, 60, 120):
        spring = Spring(1.65, .52)
        for _ in range(rate):
            spring.update(1 / rate, 17)
        for _ in range(rate * 2):
            spring.update(1 / rate, 0)
        results.append((spring.value, spring.velocity))
    for result in results[1:]:
        assert result == pytest.approx(results[0], abs=1e-10)


def test_drag_sways_on_velocity_reversal_and_settles_after_release():
    body = BodyMotion()
    for frame in range(60):
        pose = body.update(1 / 60, pointer=(frame * 12, 0), dragging=True)
    right = pose.roll
    assert right > 4
    for frame in range(60):
        pose = body.update(1 / 60, pointer=(720 - frame * 12, 0), dragging=True)
    assert pose.roll < -4
    before = pose.roll
    pose = body.update(1 / 60, pointer=(0, 0))
    assert abs(pose.roll - before) < 3
    for _ in range(300):
        pose = body.update(1 / 60, pointer=(0, 0))
    assert abs(pose.roll) < .01 and pose.hanging < .001


def test_entering_hover_after_external_mouse_movement_does_not_kick_body():
    body = BodyMotion()
    body.update(.016, pointer=(0, 0))
    pose = body.update(.016, pointer=(2000, 1000), hovered=True)
    assert pose.roll == pose.pitch == 0
    assert body.pointer_velocity == (0, 0)


def _assentar(giro, *, direcao_olhar=0.0, angulo_pedido=None, frames=240):
    for _ in range(frames):
        giro.update(1 / 60, direcao_olhar=direcao_olhar, angulo_pedido=angulo_pedido)
    return giro.angulo


def test_giro_zero_sem_estimulo_mantem_corpo_de_frente():
    giro = GiroCorpo()
    for _ in range(120):
        assert giro.update(1 / 60) == 0.0
    assert giro.angulo == 0.0


def test_giro_na_zona_morta_nao_vira_o_corpo():
    giro = GiroCorpo()
    # Olhar sutil (abaixo da zona morta) não deve mover o corpo.
    assert _assentar(giro, direcao_olhar=GiroCorpo.ZONA_MORTA_OLHAR) == 0.0


def test_giro_acompanha_olhar_para_o_lado():
    direita = GiroCorpo()
    esquerda = GiroCorpo()
    assert _assentar(direita, direcao_olhar=1.0) > 10
    assert _assentar(esquerda, direcao_olhar=-1.0) < -10


def test_giro_fica_clampado_no_limite():
    giro = GiroCorpo()
    # Pedido muito além do teto deve ser clampado em ±LIMITE_GRAUS.
    assert _assentar(giro, angulo_pedido=10_000) == pytest.approx(GiroCorpo.LIMITE_GRAUS)
    oposto = GiroCorpo()
    assert _assentar(oposto, angulo_pedido=-10_000) == pytest.approx(-GiroCorpo.LIMITE_GRAUS)
    # Mesmo no transiente da mola o ângulo nunca passa do limite.
    outra = GiroCorpo()
    for _ in range(240):
        valor = outra.update(1 / 60, angulo_pedido=10_000)
        assert abs(valor) <= GiroCorpo.LIMITE_GRAUS


def test_giro_suaviza_sem_saltar():
    giro = GiroCorpo()
    # No primeiro quadro o corpo não teleporta para o alvo; a mola suaviza.
    primeiro = giro.update(1 / 60, angulo_pedido=GiroCorpo.LIMITE_GRAUS)
    assert 0.0 < primeiro < GiroCorpo.LIMITE_GRAUS * 0.5
    # Converge para o alvo após assentar.
    assert _assentar(giro, angulo_pedido=GiroCorpo.LIMITE_GRAUS) == pytest.approx(
        GiroCorpo.LIMITE_GRAUS, abs=1e-6
    )


def test_angulo_pedido_tem_precedencia_sobre_o_olhar():
    giro = GiroCorpo()
    # Olhar para a direita, mas um estado pede giro para a esquerda.
    assert _assentar(giro, direcao_olhar=1.0, angulo_pedido=-60) == pytest.approx(-60, abs=1e-6)


def test_giro_resposta_independe_da_taxa_de_quadros():
    resultados = []
    for rate in (30, 60, 120):
        giro = GiroCorpo()
        for _ in range(rate * 2):
            giro.update(1 / rate, angulo_pedido=45)
        resultados.append(giro.angulo)
    for resultado in resultados[1:]:
        assert resultado == pytest.approx(resultados[0], abs=1e-9)


def test_impacts_keep_finite_bounded_motion_and_a_delayed_neck():
    body = BodyMotion()
    body.impulse('hit', direction=1, strength=2)
    frames = [body.update(1 / 60) for _ in range(40)]
    assert any(abs(frame.head_roll) > .1 for frame in frames)
    assert any(frame.compression > .01 for frame in frames)
    for frame in frames:
        assert all(isfinite(value) for value in vars(frame).values())
        assert abs(frame.roll) <= 28 and abs(frame.pitch) <= 16
