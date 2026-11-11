"""Dedos em cadeia: recorte puro da malha, ângulos em cascata e FK x Panda.

Os testes de recorte usam uma lâmina-caixa sintética com UV linear no
comprimento (como o dedo do asset). Verde aqui NÃO prova o visual: a junta
dobrada só é validada no olho (recalibracao-gpu.md, C15 a C19).
"""

from __future__ import annotations

import contextlib
import importlib.util
from math import isclose, radians, tan
from pathlib import Path

import pytest

from sejoga.animacao import dedos_cascata as cascata
from sejoga.animacao import dedos_tuning as tuning_dedos
from sejoga.nucleo import malha_corte as mc

#: Lâmina sintética: comprimento (X), espessura (Z, eixo "cima") e largura (Y).
COMPRIMENTO, ESPESSURA, LARGURA = 0.146, 0.05, 0.073
#: UV ao longo do comprimento: u = U0 + GANHO_U * x (linear, como a face longa).
U0, GANHO_U = 0.25, 0.2
TOLERANCIA = 1e-9
FRACOES = tuning_dedos.FRACOES_SEGMENTOS_DEDO
DIRECAO = (1.0, 0.0, 0.0)
EIXO = mc.eixo_de_flexao(DIRECAO)


def _vertice(p, n):
    return (*p, *n, U0 + GANHO_U * p[0], 0.5 + p[1], *mc.TANGENTE_PADRAO)


def _caixa():
    """Caixa fechada [0, C] x [-L/2, L/2] x [-E/2, E/2], 12 triângulos para fora."""
    x0, x1 = 0.0, COMPRIMENTO
    y0, y1 = -LARGURA / 2, LARGURA / 2
    z0, z1 = -ESPESSURA / 2, ESPESSURA / 2
    faces = (
        ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (1, 0, 0)),
        ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (-1, 0, 0)),
        ((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (0, 1, 0)),
        ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0)),
        ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1)),
        ((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (0, 0, -1)),
    )
    triangulos = []

    for a, b, c, d, n in faces:
        triangulos.append((_vertice(a, n), _vertice(b, n), _vertice(c, n)))
        triangulos.append((_vertice(a, n), _vertice(c, n), _vertice(d, n)))

    return triangulos


def _area(t):
    return mc._area2(*t) ** 0.5 / 2


def _volume(triangulos):
    """Volume assinado (teorema da divergência): só bate se a malha é fechada."""
    total = 0.0

    for a, b, c in triangulos:
        total += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        ) / 6.0

    return total


def _cortar(angulo_projeto):
    return mc.cortar_cadeia(
        _caixa(),
        DIRECAO,
        EIXO,
        FRACOES,
        angulo_projeto,
        tuning_dedos.FRACAO_MAXIMA_SOBREPOSICAO,
        tuning_dedos.FRACAO_SECAO_DA_RAIZ,
    )


def _sem_tampas(triangulos):
    """Triângulos da superfície ORIGINAL (tampas têm normal ±direção e x interno)."""
    return [
        t
        for t in triangulos
        if not (
            abs(t[0][3]) == 1.0
            and all(TOLERANCIA < v[0] < COMPRIMENTO - TOLERANCIA for v in t)
        )
    ]


# --------------------------------------------------------------------------- #
# Recorte
# --------------------------------------------------------------------------- #
def test_recorte_sem_sobreposicao_preserva_area_e_volume():
    segmentos = _cortar(0.0)
    original = _caixa()

    assert len(segmentos) == len(FRACOES)

    area = sum(_area(t) for s in segmentos for t in _sem_tampas(s.triangulos))
    assert isclose(area, sum(_area(t) for t in original), rel_tol=1e-9)

    # Cada segmento é um sólido fechado (tampas no corte): volumes somam o da caixa.
    volumes = [_volume(s.triangulos) for s in segmentos]
    assert all(v > 0 for v in volumes)
    assert isclose(sum(volumes), _volume(original), rel_tol=1e-9)

    for fracao, volume in zip(FRACOES, volumes, strict=True):
        assert isclose(volume, fracao * COMPRIMENTO * LARGURA * ESPESSURA, rel_tol=1e-9)


def test_sobreposicao_avanca_sobre_o_vizinho_com_volume_extra_exato():
    angulo = tuning_dedos.ANGULO_PROJETO_SOBREPOSICAO_GRAUS
    segmentos = _cortar(angulo)
    e = (ESPESSURA / 2) * tan(radians(angulo) / 2)
    volumes = [_volume(s.triangulos) for s in segmentos]
    secao = LARGURA * ESPESSURA

    # Os segmentos 0 e 1 avançam ``e`` além da junta; a ponta não.
    for k, fracao in enumerate(FRACOES):
        extra = e if k < len(FRACOES) - 1 else 0.0
        assert isclose(volumes[k], (fracao * COMPRIMENTO + extra) * secao, rel_tol=1e-9)


def test_uv_continua_no_plano_de_corte():
    """Todo vértice de superfície criado no corte mantém a UV linear da original."""
    for segmento in _cortar(tuning_dedos.ANGULO_PROJETO_SOBREPOSICAO_GRAUS):
        for t in _sem_tampas(segmento.triangulos):
            for v in t:
                assert isclose(v[6], U0 + GANHO_U * v[0], abs_tol=1e-9)
                assert isclose(v[7], 0.5 + v[1], abs_tol=1e-9)


def test_sobreposicao_tampa_a_cunha_externa_ate_o_angulo_de_projeto():
    """Ao dobrar θ, as faces externas se cruzam a (t/2)·tan(θ/2) da junta."""
    for graus in (20.0, 45.0, tuning_dedos.ANGULO_PROJETO_SOBREPOSICAO_GRAUS):
        theta = radians(graus)
        meia = ESPESSURA / 2
        # Face externa do vizinho girado: reta pelo ponto (s, cima) = (meia·sen, meia·cos)
        # com direção (cos θ, -sen θ); cruza cima = meia em s = meia·tan(θ/2).
        from math import cos, sin

        p_s, p_c = meia * sin(theta), meia * cos(theta)
        passo = (p_c - meia) / sin(theta)
        cruzamento = p_s + passo * cos(theta)
        e = mc.sobreposicao(
            ESPESSURA, graus, 1.0, tuning_dedos.FRACAO_MAXIMA_SOBREPOSICAO
        )
        assert isclose(cruzamento, meia * tan(theta / 2), abs_tol=1e-12)
        assert e >= cruzamento - 1e-12


def test_pivos_ficam_no_centro_da_secao_de_cada_junta():
    segmentos = _cortar(tuning_dedos.ANGULO_PROJETO_SOBREPOSICAO_GRAUS)
    juntas = [
        tuning_dedos.FRACAO_SECAO_DA_RAIZ * COMPRIMENTO,
        FRACOES[0] * COMPRIMENTO,
        (FRACOES[0] + FRACOES[1]) * COMPRIMENTO,
    ]

    for segmento, s in zip(segmentos, juntas, strict=True):
        assert segmento.pivo == pytest.approx((s, 0.0, 0.0), abs=1e-9)


def test_eixo_principal_e_flexao_espelhada():
    pontos = [(v[0], v[1], v[2]) for t in _caixa() for v in t]
    eixo = mc.orientar_para_ponta(mc.eixo_principal(pontos), pontos, (-1.0, 0.0, 0.0))
    assert eixo == pytest.approx(DIRECAO, abs=1e-6)
    assert mc.eixo_de_flexao((1.0, 0.0, 0.0)) == pytest.approx((0.0, 1.0, 0.0))
    assert mc.eixo_de_flexao((-1.0, 0.0, 0.0)) == pytest.approx((0.0, -1.0, 0.0))


# --------------------------------------------------------------------------- #
# Ângulos em cascata
# --------------------------------------------------------------------------- #
def test_numero_de_juntas():
    assert cascata.numero_de_juntas(0) == 2
    assert all(cascata.numero_de_juntas(d) == 3 for d in range(1, 5))


@pytest.mark.parametrize("dedo", range(5))
def test_gesto_fecha_todas_as_juntas_dentro_dos_limites(dedo):
    limites = (
        tuning_dedos.LIMITES_JUNTA_POLEGAR_GRAUS
        if dedo == 0
        else tuning_dedos.LIMITES_JUNTA_DEDO_GRAUS
    )
    aberto = cascata.angulos_juntas(dedo, 1, 0.0, "idle", 0.0, 0.0)
    fechado = cascata.angulos_juntas(dedo, 1, 0.0, "thumbs_up", 0.0, 80.0)

    assert all(f > a for f, a in zip(fechado, aberto, strict=True))
    for angulo, (minimo, maximo) in zip(fechado, limites, strict=True):
        assert minimo <= angulo <= maximo


def test_movimento_secundario_vivo_no_idle_e_some_com_gesto_firme():
    def amostras(flexao):
        return {
            cascata.angulos_juntas(2, 1, t / 10, "idle", 0.0, flexao) for t in range(40)
        }

    assert len(amostras(0.0)) > 1
    assert len(amostras(tuning_dedos.FLEXAO_GESTO_REFERENCIA_GRAUS)) == 1


def test_maos_nao_batem_em_unissono():
    direita = cascata.angulos_juntas(1, 1, 1.3, "idle", 0.0)
    esquerda = cascata.angulos_juntas(1, -1, 1.3, "idle", 0.0)
    assert direita != esquerda


def test_suavizar_converge_sem_salto():
    atual, alvo = (0.0, 0.0, 0.0), (30.0, 40.0, 20.0)
    passo = cascata.suavizar(atual, alvo, tuning_dedos.PASSO_MAXIMO_S)
    assert all(0 < p < a for p, a in zip(passo, alvo, strict=True))

    for _ in range(200):
        atual = cascata.suavizar(atual, alvo, tuning_dedos.PASSO_MAXIMO_S)

    assert atual == pytest.approx(alvo, abs=1e-3)


# --------------------------------------------------------------------------- #
# FK pura x pivôs reais (Panda headless)
# --------------------------------------------------------------------------- #
with contextlib.suppress(ImportError):
    import PySide6.QtWidgets  # noqa: F401


def _oraculo():
    caminho = Path(__file__).resolve().parents[1] / "tools" / "gerar_oraculo_cena.py"
    spec = importlib.util.spec_from_file_location("oraculo_cena_teste", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    return modulo


def test_recorte_do_asset_real_fecha_cada_segmento_sem_buraco():
    """Dedos reais do mario.gltf: sem sobreposição, volumes dos segmentos somam o original."""
    core = pytest.importorskip("panda3d.core", reason="Panda3D indisponível")
    gltf = pytest.importorskip("gltf", reason="panda3d-gltf indisponível")
    from sejoga.nucleo.recursos import resolve_model
    from sejoga.render import dedos_malha as dm

    core.loadPrcFileData("", "window-type none\naudio-library-name null")
    raiz = core.NodePath(gltf.load_model(str(resolve_model())))

    for dedo, mesh in enumerate(
        tuning_dedos.MESH_DEDOS_DIREITA + tuning_dedos.MESH_DEDOS_ESQUERDA
    ):
        triangulos = dm._ler_triangulos(raiz.find(f"**/mesh{mesh}").node())
        pontos = [(v[0], v[1], v[2]) for t in triangulos for v in t]
        direcao = mc.eixo_principal(pontos)
        fracoes = tuning_dedos.FRACOES_SEGMENTOS_POLEGAR if dedo % 5 == 0 else FRACOES
        segmentos = mc.cortar_cadeia(
            triangulos,
            direcao,
            mc.eixo_de_flexao(direcao),
            fracoes,
            0.0,
            tuning_dedos.FRACAO_MAXIMA_SOBREPOSICAO,
            tuning_dedos.FRACAO_SECAO_DA_RAIZ,
        )
        volumes = [abs(_volume(s.triangulos)) for s in segmentos]
        assert all(v > 0 for v in volumes), mesh
        assert isclose(sum(volumes), abs(_volume(triangulos)), rel_tol=1e-4), mesh


def test_fk_da_cadeia_iguala_o_panda_e_espelha():
    pytest.importorskip("panda3d.core", reason="Panda3D indisponível")
    pytest.importorskip("gltf", reason="panda3d-gltf indisponível")
    from sejoga.nucleo.modelo import load_model
    from sejoga.nucleo.recursos import resolve_model

    medidas = _oraculo().medir_dedos(load_model(resolve_model()))
    assert len(medidas) == 10
    assert max(m["erro"] for m in medidas) < 1e-4

    por_lado = {(m["grupo"], m["dedo"]): m["deslocamento"] for m in medidas}

    for dedo in range(5):
        dx, dy, dz = por_lado[("fingers", dedo)]
        assert por_lado[("fingers2", dedo)] == pytest.approx((-dx, dy, dz), abs=0.02)
