"""Contratos das molas por junta e da cadeia de atraso."""
from math import isfinite

import pytest

from sejoga.joint_springs import CADEIA_DIREITA, JointSpring, LagChain, SpringPose
from sejoga.rig import Rotation3


def test_joint_spring_response_is_frame_rate_independent():
    resultados = []
    for rate in (30, 60, 120):
        mola = JointSpring(1.65, .52)
        for _ in range(rate):
            mola.atualizar(1 / rate, Rotation3(17, -11, 5))
        for _ in range(rate * 2):
            mola.atualizar(1 / rate, Rotation3())
        valor = mola.valor()
        resultados.append((valor.x, valor.y, valor.z,
                           mola.x.velocity, mola.y.velocity, mola.z.velocity))
    for resultado in resultados[1:]:
        assert resultado == pytest.approx(resultados[0], abs=1e-10)


def test_lag_chain_hand_trails_the_arm_on_a_step():
    cadeia = LagChain(CADEIA_DIREITA)
    alvo = {grupo: Rotation3() for grupo in CADEIA_DIREITA}
    # Degrau no braço; os elos seguintes devem acompanhar com atraso crescente.
    alvo["right-arm"] = Rotation3(40, 0, 0)
    poses = [cadeia.atualizar(1 / 60, alvo) for _ in range(6)]
    final = poses[-1]
    # Braço lidera, antebraço atrás dele, mão atrás do antebraço, dedos por último.
    assert final["right-arm"].x > final["ant-arm"].x > final["hand"].x > final["fingers"].x
    assert final["fingers"].x >= 0


def test_lag_chain_converges_to_target_and_stays_finite():
    cadeia = LagChain(CADEIA_DIREITA)
    alvo = {grupo: Rotation3(25, 10, -15) for grupo in CADEIA_DIREITA}
    for _ in range(600):
        pose = cadeia.atualizar(1 / 60, alvo)
    for grupo in CADEIA_DIREITA:
        rotacao = pose[grupo]
        for eixo in (rotacao.x, rotacao.y, rotacao.z):
            assert isfinite(eixo)
        assert rotacao.x == pytest.approx(25, abs=.5)
        assert rotacao.z == pytest.approx(-15, abs=.5)


def test_spring_pose_follows_per_joint_targets_and_can_be_reset():
    pose_molas = SpringPose()
    alvos = {"body": Rotation3(5, 0, 2), "head": Rotation3(-3, 8, 0)}
    for _ in range(600):
        pose = pose_molas.atualizar(1 / 60, alvos)
    assert pose["body"].x == pytest.approx(5, abs=.5)
    assert pose["head"].y == pytest.approx(8, abs=.5)
    pose_molas.definir({"body": Rotation3(90, 0, 0)})
    assert pose_molas.pose()["body"].x == pytest.approx(90)
    assert pose_molas.molas["body"].x.velocity == 0.0
