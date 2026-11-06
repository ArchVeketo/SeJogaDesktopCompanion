"""Contratos das molas por junta e da cadeia de atraso."""
from math import isfinite

import pytest

from sejoga.animacao.joint_springs import CADEIA_DIREITA, JointSpring, LagChain, SpringPose
from sejoga.animacao.spring_tuning import amortecimento_de, frequencia_de
from sejoga.nucleo.rig import Rotation3


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


def _tensoes_por_junta():
    grupos = ("head", "body", "hand", "fingers")
    return {g: (frequencia_de(g), amortecimento_de(g)) for g in grupos}


def test_spring_pose_por_junta_e_independente_de_framerate():
    tensoes = _tensoes_por_junta()
    alvos = {
        "head": Rotation3(17, -11, 5),
        "body": Rotation3(8, 3, -6),
        "hand": Rotation3(-12, 20, 9),
        "fingers": Rotation3(25, -7, 14),
    }
    resultados = []
    for rate in (30, 60, 120):
        pose_molas = SpringPose(tensoes=tensoes)
        for _ in range(rate):
            pose_molas.atualizar(1 / rate, alvos)
        for _ in range(rate * 2):
            pose_molas.atualizar(1 / rate, {g: Rotation3() for g in alvos})
        amostra = []
        for grupo in alvos:
            mola = pose_molas.molas[grupo]
            amostra.extend((
                mola.x.value, mola.y.value, mola.z.value,
                mola.x.velocity, mola.y.velocity, mola.z.velocity,
            ))
        resultados.append(amostra)
    for resultado in resultados[1:]:
        assert resultado == pytest.approx(resultados[0], abs=1e-10)


def test_ponta_solta_tem_mais_velocidade_que_a_ancora_apos_degrau():
    tensoes = _tensoes_por_junta()
    pose_molas = SpringPose(tensoes=tensoes)
    alvos = {"body": Rotation3(40, 0, 0), "fingers": Rotation3(40, 0, 0)}
    # Após o degrau e uma breve acomodação, a âncora firme (body) já assentou
    # enquanto a ponta solta (fingers) ainda balança: no mesmo instante ela
    # carrega mais velocidade.
    for _ in range(20):
        pose_molas.atualizar(1 / 60, alvos)
    corpo = pose_molas.molas["body"]
    dedos = pose_molas.molas["fingers"]
    assert abs(dedos.x.velocity) > abs(corpo.x.velocity)
