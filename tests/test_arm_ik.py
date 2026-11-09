"""Testes do solver de IK 3D de braço (``sejoga.animacao.arm_ik``).

Verificam, contra a geometria REAL do modelo (FK pura de ``rig_debug``), que:
- para alvos conhecidos dentro do alcance, a ponta da mão resultante bate com o
  alvo pedido dentro de tolerância;
- alvo inatingível é clampado sem gerar NaN;
- o lado esquerdo é o espelho do direito;
- o módulo é Python puro (não puxa Panda3D/Qt).
"""

from math import isfinite

import pytest

from sejoga.animacao import arm_ik
from sejoga.animacao.arm_targets import ALVOS
from sejoga.nucleo.assets import resolve_model
from sejoga.nucleo.model import load_model

#: Tolerância de posição (unidades do modelo). O alcance do braço é ≈ 0.281.
TOLERANCIA = 0.02


@pytest.fixture(scope="module")
def modelo():
    return load_model(resolve_model())


def _dist(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5


@pytest.mark.parametrize(
    "alvo",
    [
        (0.075, -0.265, 0.02),   # mão ao lado do quadril (idle)
        (0.11, 0.235, 0.03),     # mão acima do ombro, à direita (wave)
        (0.16, 0.0, 0.16),       # mão à frente, na horizontal
        (0.05, -0.2, 0.1),       # mão baixa e um pouco à frente
    ],
)
def test_braco_para_coloca_a_mao_no_alvo(modelo, alvo):
    """Para alvos dentro do alcance, a ponta da mão bate com o alvo pedido."""
    hpr = arm_ik.braco_para(modelo, "right", alvo)
    pos = arm_ik.posicao_mao_para_hpr(modelo, "right", hpr["right-arm"], hpr["ant-arm"])

    assert _dist(pos, alvo) <= TOLERANCIA


def test_alvos_dos_gestos_sao_atingiveis(modelo):
    """Todos os alvos de gesto de ``arm_targets`` são atingidos dentro da tolerância."""
    for nome, alvo in ALVOS.items():
        hpr = arm_ik.braco_para(modelo, "right", alvo.alvo, alvo.polo)
        pos = arm_ik.posicao_mao_para_hpr(
            modelo, "right", hpr["right-arm"], hpr["ant-arm"]
        )

        assert _dist(pos, alvo.alvo) <= TOLERANCIA, nome


def test_alvo_inatingivel_e_clampado_sem_nan(modelo):
    """Alvo muito além do alcance é clampado (sem NaN) pelo solver planar."""
    hpr = arm_ik.braco_para(modelo, "right", (5.0, 5.0, 5.0))

    for rot in hpr.values():
        assert isfinite(rot.x) and isfinite(rot.y) and isfinite(rot.z)


def test_lado_esquerdo_e_espelho_do_direito(modelo):
    """Alvo espelhado em X no lado esquerdo coloca a mão na posição espelhada."""
    alvo_dir = (0.1, 0.2, 0.03)
    alvo_esq = (-0.1, 0.2, 0.03)

    hpr_dir = arm_ik.braco_para(modelo, "right", alvo_dir)
    hpr_esq = arm_ik.braco_para(modelo, "left", alvo_esq)

    pos_dir = arm_ik.posicao_mao_para_hpr(
        modelo, "right", hpr_dir["right-arm"], hpr_dir["ant-arm"]
    )
    pos_esq = arm_ik.posicao_mao_para_hpr(
        modelo, "left", hpr_esq["left-arm"], hpr_esq["ant-arm2"]
    )

    assert _dist(pos_dir, alvo_dir) <= TOLERANCIA
    assert _dist(pos_esq, alvo_esq) <= TOLERANCIA
    # O X tem sinal trocado; Y e Z coincidem (espelho no plano sagital).
    assert pos_dir[0] == pytest.approx(-pos_esq[0], abs=TOLERANCIA)
    assert pos_dir[1] == pytest.approx(pos_esq[1], abs=TOLERANCIA)


def test_comprimentos_lidos_do_modelo(modelo):
    """Os comprimentos vêm da cadeia real (upper 0.125, forearm 0.15625)."""
    upper, forearm = arm_ik.comprimentos_braco(modelo, "right")

    assert upper == pytest.approx(0.125, abs=1e-4)
    assert forearm == pytest.approx(0.15625, abs=1e-4)


def test_modulo_e_python_puro():
    """O solver não pode depender de engine (Panda3D/Qt).

    Verifica num interpretador LIMPO (subprocesso) que importar ``arm_ik`` não
    puxa Panda3D nem PySide6 — no processo compartilhado do pytest outros
    testes já carregam a engine, então a checagem precisa de um processo novo.
    """
    import subprocess
    import sys
    from pathlib import Path

    src = str(Path(__file__).resolve().parent.parent / "src")
    codigo = (
        "import sys; "
        f"sys.path.insert(0, {src!r}); "
        "import sejoga.animacao.arm_ik; "
        "assert 'panda3d' not in sys.modules, 'panda3d vazou'; "
        "assert 'PySide6' not in sys.modules, 'PySide6 vazou'"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True
    )

    assert resultado.returncode == 0, resultado.stderr
