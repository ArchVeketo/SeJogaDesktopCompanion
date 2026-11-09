"""Regressão de PIXEL dos braços no renderer real (câmera ortográfica frontal).

O que este teste PROVA e o que NÃO prova:
  - prova que, na tela frontal, o idle mantém as mãos FORA da silhueta do tronco
    e simétricas, e que o aceno ergue a mão direita sem mexer a esquerda;
  - NÃO prova profundidade (frente/trás): a câmera frontal não enxerga o eixo
    da câmera. A prova de eixo é a FK do grafo de cena
    (``tests/test_cinematica_oraculo.py``) e o anti-atravessamento é medido em
    ``tests/test_colisao_bracos.py``. A aparência final é do usuário na GPU.

Os limiares são regressão das medidas de hoje (comentadas), não verdade
anatômica. A "mão" é o topo da caixa do nó ``hand``: com o braço aberto ele fica
acima do pivô do ombro, por isso não se compara mão x ombro na vertical.

Sem GPU/offscreen (``RenderIndisponivel``), o módulo é PULADO.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from verificar_eixos import RenderIndisponivel, capturar

#: Quanto (px) cada mão fica mais afastada do centro que o ombro no idle.
#: Medido: ~91 px (mãos a ~118 px do centro, ombro a ~27 px).
MIN_AFASTAMENTO_MAO_PX = 50.0
#: Tolerância (px) de simetria em X das mãos no idle (medido: ~1 px).
TOL_SIMETRIA_IDLE_PX = 20.0
#: Subida mínima (px) da mão direita no pico do aceno vs idle (medido: ~59 px).
MIN_SUBIDA_WAVE_PX = 40.0
#: Quanto (px) a mão esquerda pode variar durante o aceno (medido: ~3 px).
TOL_ESQUERDA_WAVE_PX = 15.0


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


def test_idle_maos_fora_do_tronco_e_simetricas(amostras_idle):
    a = amostras_idle[-1]
    ombro = abs(a.ombro_dir[0] - a.centro[0])

    for nome, mao in (("direita", a.mao_dir), ("esquerda", a.mao_esq)):
        afastamento = abs(mao[0] - a.centro[0]) - ombro
        assert afastamento >= MIN_AFASTAMENTO_MAO_PX, (
            f"mão {nome} deveria ficar fora do tronco: afastamento={afastamento:.1f}px"
        )

    desvio = abs(a.mao_dir[0] + a.mao_esq[0] - 2.0 * a.centro[0])
    assert desvio <= TOL_SIMETRIA_IDLE_PX, f"mãos assimétricas em X: {desvio:.1f}px"


def test_wave_ergue_a_mao_direita(amostras_wave, amostras_idle):
    pico = _mao_mais_alta(amostras_wave)
    subida = amostras_idle[-1].mao_dir[1] - pico.mao_dir[1]  # y menor = mais alto

    assert subida >= MIN_SUBIDA_WAVE_PX, f"mão do aceno subiu só {subida:.1f}px"


def test_wave_esquerda_fica_em_repouso(amostras_wave, amostras_idle):
    pico = _mao_mais_alta(amostras_wave)
    variacao = abs(pico.mao_esq[1] - amostras_idle[-1].mao_esq[1])

    assert variacao <= TOL_ESQUERDA_WAVE_PX, f"mão esquerda mexeu {variacao:.1f}px no aceno"
