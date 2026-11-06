"""Testes da fundação de limiares e classificadores (``sejoga.rig_mapa.rig_limiares``).

Cobre: defaults da seção 10.1, classificação por faixas e classificação de
direção em casos analíticos conhecidos. Fronteira Python puro, sem engine.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from sejoga.rig_mapa import rig_limiares as rl
from sejoga.rig_mapa.rig_mapa import DirecaoMundo


# --------------------------------------------------------------------------- #
# Defaults da seção 10.1
# --------------------------------------------------------------------------- #
def test_limiares_padrao_direcao() -> None:
  lim = rl.LIMIARES_PADRAO
  assert lim.alinhamento_min_norm == 0.80
  assert lim.margem_ambiguidade == 0.15
  assert lim.norma_min == 1e-6


def test_limiares_padrao_flexao() -> None:
  lim = rl.Limiares()
  assert lim.esticado_ate_graus == 15.0
  assert lim.leve_ate_graus == 45.0
  assert lim.dobrado_ate_graus == 110.0
  assert lim.tolerancia_limite_graus == 2.0


def test_limiares_padrao_porta() -> None:
  lim = rl.Limiares()
  assert lim.porta_fechada_ate == 5.0
  assert lim.porta_fresta_ate == 15.0
  assert lim.porta_entreaberta_ate == 45.0
  assert lim.porta_aberta_ate == 100.0


def test_limiares_padrao_cabeca_distancias_dinamica_tronco() -> None:
  lim = rl.Limiares()
  assert lim.olhar_frente_graus == 15.0
  assert lim.cabeca_reta_graus == 8.0
  assert lim.mao_rosto_rel == 0.18
  assert lim.maos_unidas_rel == 0.08
  assert lim.parado_entrar_graus_s == 5.0
  assert lim.suavizacao_velocidade == 0.30
  assert lim.tronco_inclinado_graus == 12.0
  assert lim.agachado_norm == 0.25
  assert lim.deitado_graus == 60.0


# --------------------------------------------------------------------------- #
# classificar_por_faixas
# --------------------------------------------------------------------------- #
def test_classificar_por_faixas_fronteiras() -> None:
  faixas = ((15.0, "ESTICADO"), (45.0, "LEVE"), (110.0, "DOBRADO"))
  assert rl.classificar_por_faixas(0.0, faixas, "MUITO") == "ESTICADO"
  assert rl.classificar_por_faixas(15.0, faixas, "MUITO") == "ESTICADO"
  assert rl.classificar_por_faixas(15.01, faixas, "MUITO") == "LEVE"
  assert rl.classificar_por_faixas(45.0, faixas, "MUITO") == "LEVE"
  assert rl.classificar_por_faixas(200.0, faixas, "MUITO") == "MUITO"


# --------------------------------------------------------------------------- #
# classificar_direcao
# --------------------------------------------------------------------------- #
def test_classificar_direcao_cima() -> None:
  direcao = rl.classificar_direcao((0.0, 1.0, 0.0), rl.LIMIARES_PADRAO)
  assert direcao.principal is DirecaoMundo.CIMA
  assert direcao.alinhamento_norm == pytest.approx(1.0)
  assert direcao.angulo_vertical_graus == pytest.approx(0.0)


def test_classificar_direcao_frente() -> None:
  direcao = rl.classificar_direcao((0.0, 0.0, 1.0), rl.LIMIARES_PADRAO)
  assert direcao.principal is DirecaoMundo.FRENTE
  assert direcao.azimute_graus == pytest.approx(0.0)


def test_classificar_direcao_90_graus_do_eixo() -> None:
  # Vetor horizontal para frente: 90 graus do eixo vertical (cima).
  direcao = rl.classificar_direcao((0.0, 0.0, 1.0), rl.LIMIARES_PADRAO)
  assert direcao.angulo_vertical_graus == pytest.approx(90.0)


def test_classificar_direcao_vetor_nulo_e_indefinida() -> None:
  direcao = rl.classificar_direcao((0.0, 0.0, 0.0), rl.LIMIARES_PADRAO)
  assert direcao.principal is DirecaoMundo.INDEFINIDA
  assert direcao.ambigua is True


def test_classificar_direcao_diagonal_e_ambigua() -> None:
  direcao = rl.classificar_direcao((0.0, 1.0, 1.0), rl.LIMIARES_PADRAO)
  # Diagonal 45°: alinhamento ~0,707 fica abaixo do mínimo -> ambígua.
  assert direcao.ambigua is True


# --------------------------------------------------------------------------- #
# Fronteira — Python puro, sem engine
# --------------------------------------------------------------------------- #
def test_rig_limiares_nao_importa_engine() -> None:
  caminho = Path(rl.__file__)
  arvore = ast.parse(caminho.read_text(encoding="utf-8"))
  proibidos = ("panda3d", "pyside6", "pyqt5", "pyqt6", "win32", "pywin32", "win32gui")
  importados: list[str] = []

  for no in ast.walk(arvore):
    if isinstance(no, ast.Import):
      importados.extend(alias.name.lower() for alias in no.names)
    elif isinstance(no, ast.ImportFrom) and no.module:
      importados.append(no.module.lower())

  for modulo in importados:
    raiz = modulo.split(".")[0]
    assert raiz not in proibidos, f"import proibido: {modulo}"
