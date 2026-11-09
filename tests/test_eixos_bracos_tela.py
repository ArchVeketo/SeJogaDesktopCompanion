"""Trava de regressão do eixo de braço pelo ORÁCULO CERTO: pixels de tela.

A convenção de elevação do braço foi provada capturando frames do renderer
REAL (não números). Este teste reusa o helper de projeção de
``tools/verificar_eixos.py`` para subir o renderer offscreen, disparar idle e
wave, e AFIRMAR em PIXELS DE TELA:

  - wave: a ponta da mão direita no pico SOBE em relação ao idle (y_px menor)
    e fica ACIMA do ombro;
  - idle: ambas as mãos ficam ABAIXO do ombro (y_px maior) e simétricas em X.

Sem GPU/offscreen (``RenderIndisponivel``), o módulo é PULADO — o render real é
requisito do oráculo, igual ao padrão offscreen de ``tools/preview_anim.py``.
NÃO medimos ângulos abstratos: o eixo é o pixel.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from verificar_eixos import RenderIndisponivel, capturar

#: Elevação mínima (px) que a mão do wave precisa subir em relação ao idle.
MIN_SUBIDA_WAVE_PX = 80.0
#: Tolerância (px) de simetria em X das mãos no idle.
TOL_SIMETRIA_IDLE_PX = 20.0
#: Folga (px) para a mão ficar inequivocamente abaixo/acima do ombro.
FOLGA_OMBRO_PX = 10.0


@pytest.fixture(scope="module")
def amostras_idle():
    try:
        return capturar("idle", frames=6, camera="frente", salvar=False, prefixo="test-idle")
    except RenderIndisponivel as exc:
        pytest.skip(f"render offscreen indisponível: {exc}")


@pytest.fixture(scope="module")
def amostras_wave():
    try:
        return capturar("wave", frames=50, camera="frente", salvar=False, prefixo="test-wave")
    except RenderIndisponivel as exc:
        pytest.skip(f"render offscreen indisponível: {exc}")


def _mao_mais_alta(amostras):
    """Amostra em que a mão DIREITA está mais alta na tela (menor y_px)."""
    return min(amostras, key=lambda a: a.mao_dir[1])


def test_idle_maos_abaixo_do_ombro_e_simetricas(amostras_idle):
    """Idle: as duas mãos ficam ABAIXO do ombro e simétricas em X (pixels)."""
    a = amostras_idle[-1]

    assert a.mao_dir[1] > a.ombro_dir[1] + FOLGA_OMBRO_PX, (
        f"mão direita deveria estar abaixo do ombro (y maior): "
        f"mao={a.mao_dir[1]:.1f} ombro={a.ombro_dir[1]:.1f}"
    )
    assert a.mao_esq[1] > a.ombro_dir[1] + FOLGA_OMBRO_PX, (
        f"mão esquerda deveria estar abaixo do ombro (y maior): "
        f"mao={a.mao_esq[1]:.1f} ombro={a.ombro_dir[1]:.1f}"
    )

    # Simetria em X: as mãos equidistantes do centro do corpo.
    desvio = abs(a.mao_dir[0] + a.mao_esq[0] - 2.0 * a.centro[0])
    assert desvio <= TOL_SIMETRIA_IDLE_PX, (
        f"mãos deveriam ser simétricas em X: dir={a.mao_dir[0]:.1f} "
        f"esq={a.mao_esq[0]:.1f} centro={a.centro[0]:.1f} desvio={desvio:.1f}px"
    )


def test_wave_ergue_mao_acima_do_ombro(amostras_wave, amostras_idle):
    """Wave: a mão direita no pico SOBE em relação ao idle e passa do ombro."""
    pico = _mao_mais_alta(amostras_wave)
    repouso = amostras_idle[-1]

    subida = repouso.mao_dir[1] - pico.mao_dir[1]  # y menor = mais alto
    assert subida >= MIN_SUBIDA_WAVE_PX, (
        f"mão do wave deveria subir >= {MIN_SUBIDA_WAVE_PX}px vs idle: "
        f"pico_y={pico.mao_dir[1]:.1f} idle_y={repouso.mao_dir[1]:.1f} "
        f"subida={subida:.1f}px"
    )
    assert pico.mao_dir[1] < pico.ombro_dir[1] - FOLGA_OMBRO_PX, (
        f"mão do wave deveria ficar acima do ombro (y menor): "
        f"mao={pico.mao_dir[1]:.1f} ombro={pico.ombro_dir[1]:.1f}"
    )


def test_wave_esquerda_fica_em_repouso(amostras_wave):
    """Wave: a mão ESQUERDA permanece abaixo do ombro (só o direito acena)."""
    pico = _mao_mais_alta(amostras_wave)

    assert pico.mao_esq[1] > pico.ombro_dir[1], (
        f"mão esquerda deveria ficar em repouso (abaixo do ombro): "
        f"mao={pico.mao_esq[1]:.1f} ombro={pico.ombro_dir[1]:.1f}"
    )
