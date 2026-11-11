"""Testes da corda do fio do fone (lógica pura; o visual só a GPU confirma)."""

from __future__ import annotations

import math
import time
from itertools import pairwise

from sejoga.animacao import fio_tuning as tuning
from sejoga.animacao.fio_corda import (
    ORDEM_HASTE,
    FioFone,
    construir_tubo,
    empurrar_ponto_de_caixa,
    empurrar_ponto_de_capsula,
    indices_dos_tubos,
)
from sejoga.animacao.primitivas_colisao import CaixaOrientada, Capsula, dist_ponto_caixa

ANCORAS = ((-0.22, 0.0, 0.8), (0.22, 0.0, 0.8), (0.12, 0.0, 0.45))
BAIXO = (0.0, 0.0, -1.0)
EIXOS = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _distancia(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.dist(a, b)


def _assentada(caixas: list[CaixaOrientada] | None = None) -> FioFone:
    fio = FioFone(ANCORAS)
    fio.assentar(ANCORAS, BAIXO, caixas or [], [])
    return fio


def test_fio_fone_assentado_mantem_pontas_nas_ancoras_e_pende() -> None:
    fio = _assentada()

    assert fio.posicoes[0] == ANCORAS[0]
    assert fio.posicoes[tuning.SEGMENTOS_RAMO_ORELHA] == ANCORAS[1]
    assert fio.posicoes[-1] == ANCORAS[ORDEM_HASTE]
    assert fio.posicoes[2 * tuning.SEGMENTOS_RAMO_ORELHA][2] < ANCORAS[0][2] - 0.1


def test_fio_fone_assentado_respeita_comprimento_dos_segmentos() -> None:
    fio = _assentada()

    for cadeia in fio.cadeias:
        pontos = [fio.posicoes[i] for i in cadeia]
        total = sum(_distancia(a, b) for a, b in pairwise(pontos))
        esperado = (
            tuning.COMPRIMENTO_HASTE_U
            if cadeia[0] == 2 * tuning.SEGMENTOS_RAMO_ORELHA
            else tuning.COMPRIMENTO_RAMO_ORELHA_U
        )
        assert abs(total - esperado) < esperado * 0.1


def test_fio_fone_assentado_duas_vezes_fica_parado() -> None:
    fio = _assentada()
    fio.assentar(ANCORAS, BAIXO, [], [])
    antes = list(fio.posicoes)

    fio.atualizar(1 / 60, ANCORAS, BAIXO, [], [])

    assert (
        max(_distancia(a, b) for a, b in zip(antes, fio.posicoes, strict=True)) < 1e-3
    )


def test_fio_fone_com_caixa_no_caminho_nao_entra_na_caixa() -> None:
    caixa = CaixaOrientada(
        centro=(0.0, 0.0, 0.5), eixos=EIXOS, meias_dim=(0.08, 0.2, 0.1)
    )

    fio = _assentada([caixa])

    for ponto in fio.posicoes:
        assert dist_ponto_caixa(ponto, caixa) > -0.005


def test_fio_fone_salto_grande_de_ancora_reinicia_sem_explodir() -> None:
    fio = _assentada()
    longe = tuple((x + 5.0, y, z) for x, y, z in ANCORAS)

    fio.atualizar(1 / 60, longe, BAIXO, [], [])

    assert all(math.isfinite(c) for ponto in fio.posicoes for c in ponto)
    assert _distancia(fio.posicoes[0], longe[0]) < 1e-6


def test_fio_fone_atualizar_custa_pouco_por_quadro() -> None:
    fio = _assentada()
    inicio = time.perf_counter()

    for _ in range(100):
        fio.atualizar(1 / 60, ANCORAS, BAIXO, [], [])

    assert (time.perf_counter() - inicio) / 100 < 0.004


def test_ponto_no_eixo_da_capsula_sai_na_perpendicular():
    capsula = Capsula((0, 0, 0), (0, 0, 2), 0.2)
    x, y, z = empurrar_ponto_de_capsula((0, 0, 1), capsula, 0.05)
    assert x * x + y * y == 0.25 ** 2
    assert z == 1


def test_empurrar_ponto_de_capsula_ponto_dentro_sai_na_folga() -> None:
    capsula = Capsula(a=(0.0, 0.0, 0.0), b=(0.0, 0.0, 1.0), raio=0.1)

    saida = empurrar_ponto_de_capsula((0.05, 0.0, 0.5), capsula, 0.02)

    assert abs(saida[0] - 0.12) < 1e-9


def test_empurrar_ponto_de_caixa_ponto_dentro_sai_pela_face_mais_proxima() -> None:
    caixa = CaixaOrientada(
        centro=(0.0, 0.0, 0.0), eixos=EIXOS, meias_dim=(1.0, 1.0, 0.1)
    )

    saida = empurrar_ponto_de_caixa((0.2, 0.3, 0.05), caixa, 0.02)

    assert abs(saida[2] - 0.12) < 1e-9
    assert saida[:2] == (0.2, 0.3)


def test_empurrar_ponto_de_caixa_ponto_longe_nao_mexe() -> None:
    caixa = CaixaOrientada(
        centro=(0.0, 0.0, 0.0), eixos=EIXOS, meias_dim=(1.0, 1.0, 1.0)
    )

    assert empurrar_ponto_de_caixa((3.0, 0.0, 0.0), caixa, 0.02) == (3.0, 0.0, 0.0)


def test_construir_tubo_faces_apontam_para_fora_e_tem_triangulos_anti_horarios() -> (
    None
):
    pontos = [(0.0, 0.0, 1.0 - 0.1 * i) for i in range(4)]
    vertices, normais = construir_tubo(pontos, (0.0, -1.0, 0.0), 0.02)
    triangulos = indices_dos_tubos([len(pontos)])

    assert len(vertices) == (len(pontos) - 1) * 16
    assert len(triangulos) == (len(pontos) - 1) * 8

    for a, b, c in triangulos:
        ab = tuple(vertices[b][k] - vertices[a][k] for k in range(3))
        ac = tuple(vertices[c][k] - vertices[a][k] for k in range(3))
        normal = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        declarada = normais[a]
        assert sum(n * d for n, d in zip(normal, declarada, strict=True)) > 0.0
        # A face sai do eixo do tubo (x=y=0): normal alinhada com o centro da face.
        centro = tuple(sum(vertices[i][k] for i in (a, b, c)) / 3 for k in range(2))
        assert centro[0] * declarada[0] + centro[1] * declarada[1] > 0.0
