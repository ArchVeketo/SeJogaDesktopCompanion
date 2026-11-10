"""Passos de dança em quatro poses: amostrador, alvos de mão e segurança."""

from __future__ import annotations

from math import radians

import pytest

from sejoga.animacao import braco_tuning as bt
from sejoga.animacao import colisao_bracos as cb
from sejoga.animacao import dance_tuning as tune
from sejoga.animacao.dance_frases_tuning import FRASES
from sejoga.animacao.dance_poses import PassoDanca, PoseDanca, amostrar_passo
from sejoga.nucleo.assets import resolve_model
from sejoga.nucleo.model import load_model
from sejoga.nucleo.rig import Rotation3, braco_hpr_graus

#: Tolerância (graus) de comparação entre amostras.
TOLERANCIA_GRAUS = 1e-6
#: Amostras por batida ao varrer uma frase.
AMOSTRAS_POR_BATIDA = 10
#: Folga (u) sobre a de colisão: a interpolação entre alvos livres pode raspar.
FOLGA_TRANSICAO_U = 0.02
#: Fração de batida antes do fim do passo usada para checar a emenda.
EPSILON_EMENDA = 1e-4
#: Maior diferença (graus) aceita na emenda entre dois passos (sem pop).
POP_MAXIMO_GRAUS = 0.5
GRUPOS_BRACO = ("right-arm", "left-arm", "ant-arm", "ant-arm2")


def _varrer(frase: tuple[PassoDanca, ...]) -> list[dict[str, tuple[float, float, float]]]:
    """Amostras da frase inteira, passo a passo, fechando no primeiro passo."""
    amostras = []
    for i, passo in enumerate(frase):
        proximo = frase[(i + 1) % len(frase)]
        for k in range(AMOSTRAS_POR_BATIDA):
            amostras.append(amostrar_passo(passo, k / AMOSTRAS_POR_BATIDA, proximo))
    amostras.append(amostrar_passo(frase[0], 0.0))

    return amostras


@pytest.fixture(scope="module")
def modelo():
    return load_model(resolve_model())


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


@pytest.mark.parametrize("estilo", sorted(FRASES))
def test_frase_tem_quatro_poses_por_passo(estilo):
    for passo in FRASES[estilo]:
        assert len(passo.poses) == 4


@pytest.mark.parametrize("estilo", sorted(FRASES))
def test_frase_fecha_o_laco_sem_pop_nas_emendas(estilo):
    frase = FRASES[estilo]

    for i, passo in enumerate(frase):
        proximo = frase[(i + 1) % len(frase)]
        fim = amostrar_passo(passo, 1.0 - EPSILON_EMENDA, proximo)
        inicio = amostrar_passo(proximo, 0.0)
        for grupo, trio in fim.items():
            for a, b in zip(trio, inicio[grupo], strict=True):
                assert abs(a - b) < POP_MAXIMO_GRAUS, (estilo, i, grupo)


@pytest.mark.parametrize("estilo", sorted(FRASES))
def test_frase_mantem_cotovelos_sem_hiperextensao(estilo):
    for amostra in _varrer(FRASES[estilo]):
        assert amostra["ant-arm"][2] >= -TOLERANCIA_GRAUS
        assert amostra["ant-arm2"][2] <= TOLERANCIA_GRAUS


@pytest.mark.parametrize("estilo", sorted(FRASES))
def test_frase_mantem_bracos_dentro_dos_clamps_do_resolvedor(estilo):
    for amostra in _varrer(FRASES[estilo]):
        for grupo in ("right-arm", "left-arm"):
            _, azimute, elevacao = amostra[grupo]
            assert bt.OMBRO_ELEVACAO_MIN_GRAUS <= elevacao <= bt.OMBRO_ELEVACAO_MAX_GRAUS
            assert bt.OMBRO_AZIMUTE_MIN_GRAUS <= azimute <= bt.OMBRO_AZIMUTE_MAX_GRAUS
        assert amostra["ant-arm"][2] <= bt.COTOVELO_MAX_GRAUS


@pytest.mark.parametrize("estilo", sorted(FRASES))
def test_frase_nao_atravessa_o_corpo_com_o_modelo_real(modelo, estilo):
    for amostra in _varrer(FRASES[estilo]):
        pose = {
            grupo: Rotation3(*(radians(v) for v in amostra[grupo])) for grupo in GRUPOS_BRACO
        }
        for lado in ("right", "left"):
            assert cb.penetracao_do_lado(modelo, lado, pose) <= (
                cb.FOLGA_PENETRACAO_U + FOLGA_TRANSICAO_U
            ), (estilo, lado)


def test_rock_no_acento_tem_braco_direito_em_chifre_e_esquerdo_baixo():
    pose = amostrar_passo(FRASES["rock"][0], 0.0)

    assert pose["right-arm"] == pytest.approx(braco_hpr_graus("right", "chifre")["right-arm"])
    assert pose["left-arm"] == pytest.approx(braco_hpr_graus("left", "idle")["left-arm"])


@pytest.mark.parametrize("passo", range(2))
def test_rock_marca_o_headbang_para_baixo_no_acento(passo):
    cabecas = [amostrar_passo(FRASES["rock"][passo], k / 20)["head"][0] for k in range(20)]

    assert cabecas[0] == min(cabecas)
    assert cabecas[0] < 0.0


def test_hip_hop_transfere_o_peso_para_lados_opostos_nas_duas_metades_da_frase():
    frase = FRASES["hip_hop"]
    primeira = amostrar_passo(frase[0], 0.0)["body"][2]
    segunda = amostrar_passo(frase[4], 0.0)["body"][2]

    assert len(frase) == 8
    assert primeira > 0.0 > segunda


def test_hip_hop_estende_o_braco_oposto_ao_lado_carregado():
    frase = FRASES["hip_hop"]
    esquerdo = amostrar_passo(frase[1], 0.0)
    direito = amostrar_passo(frase[5], 0.0)

    assert esquerdo["left-arm"] == pytest.approx(braco_hpr_graus("left", "contrapeso")["left-arm"])
    assert esquerdo["right-arm"] == pytest.approx(braco_hpr_graus("right", "idle")["right-arm"])
    assert direito["right-arm"] == pytest.approx(braco_hpr_graus("right", "contrapeso")["right-arm"])
