"""Passos de dança em quatro poses: amostrador, alvos de mão e segurança."""

from __future__ import annotations

import pytest

from sejoga.animacao import dance_tuning as tune
from sejoga.animacao.dance_poses import PassoDanca, PoseDanca, amostrar_passo
from sejoga.nucleo.rig import braco_hpr_graus

#: Tolerância (graus) de comparação entre amostras.
TOLERANCIA_GRAUS = 1e-6


def _passo_de_teste() -> PassoDanca:
    """Passo com nod no acento e o braço direito indo ao contrapeso."""
    return PassoDanca(
        (
            PoseDanca({"head": (-14.0, 0.0, 0.0)}, "idle", "idle"),
            PoseDanca({"head": (-4.0, 0.0, 2.0)}, "contrapeso", "idle"),
            PoseDanca({"head": (-2.0, 0.0, 0.0)}, "contrapeso", "idle"),
            PoseDanca({"head": (2.0, 0.0, 0.0)}, "idle", "idle"),
        )
    )


def test_amostrar_passo_no_onset_devolve_a_pose_de_acento():
    passo = _passo_de_teste()

    pose = amostrar_passo(passo, 0.0)

    assert pose["head"] == pytest.approx((-14.0, 0.0, 0.0), abs=TOLERANCIA_GRAUS)
    assert pose["right-arm"] == pytest.approx(braco_hpr_graus("right", "idle")["right-arm"])


def test_amostrar_passo_em_cada_pose_chave_devolve_a_pose_declarada():
    passo = _passo_de_teste()

    for u, pose_chave in zip(tune.U_POSES, passo.poses, strict=True):
        pose = amostrar_passo(passo, u)

        assert pose["head"] == pytest.approx(pose_chave.corpo["head"], abs=TOLERANCIA_GRAUS)
        esperado = braco_hpr_graus("right", pose_chave.braco_dir)["ant-arm"]
        assert pose["ant-arm"] == pytest.approx(esperado, abs=TOLERANCIA_GRAUS)


def test_amostrar_passo_fecha_no_acento_do_proximo_passo():
    passo = _passo_de_teste()
    proximo = PassoDanca(
        tuple(PoseDanca({"head": (-9.0, 3.0, 0.0)}, "contrapeso", "contrapeso") for _ in range(4))
    )

    final = amostrar_passo(passo, 1.0, proximo)
    inicio = amostrar_passo(proximo, 0.0)

    assert final.keys() == inicio.keys()
    for grupo, trio in final.items():
        assert trio == pytest.approx(inicio[grupo], abs=TOLERANCIA_GRAUS), grupo


def test_amostrar_passo_com_ganho_escala_so_a_cabeca_e_nao_os_bracos():
    passo = _passo_de_teste()

    cheio = amostrar_passo(passo, 0.0, ganho=1.0)
    metade = amostrar_passo(passo, 0.0, ganho=0.5)

    assert metade["head"][0] == pytest.approx(cheio["head"][0] / 2)
    assert metade["right-arm"] == cheio["right-arm"]


def test_amostrar_passo_continuo_nao_salta_entre_amostras_vizinhas():
    passo = _passo_de_teste()
    salto_maximo_graus = 4.0
    anterior = amostrar_passo(passo, 0.0)

    for i in range(1, 201):
        atual = amostrar_passo(passo, i / 200)
        for grupo, trio in atual.items():
            for a, b in zip(trio, anterior[grupo], strict=True):
                assert abs(a - b) < salto_maximo_graus, (grupo, i)
        anterior = atual


def test_u_poses_tem_quatro_instantes_crescentes_com_acento_no_onset():
    assert len(tune.U_POSES) == 4
    assert tune.U_POSES[0] == 0.0
    assert list(tune.U_POSES) == sorted(tune.U_POSES)
    assert tune.U_POSES[-1] < 1.0
