"""Testes do pipeline de medição por parte (``sejoga.rig_medidas``).

Cobre: (a) medições analíticas de ângulo e classificação de direção; (b)
invariante de corpo rígido (vetores perpendiculares seguem perpendiculares sob
rotação); (c) simetria no repouso entre braço direito e esquerdo; (d)
``medir_todas_as_partes`` cobre TODA ``Parte`` com ``EstadoParte`` não-nulo;
(e) fronteira Python puro, sem engine.
"""

from __future__ import annotations

import ast
from math import radians
from pathlib import Path

import pytest

from sejoga import rig_medidas as med
from sejoga.assets import resolve_model
from sejoga.model import load_model
from sejoga.rig import Rig
from sejoga.rig_limiares import LIMIARES_PADRAO
from sejoga.rig_mapa import AlturaRelativa, Direcao, DirecaoMundo, EstadoParte, Parte


@pytest.fixture(scope="module")
def model():
  return load_model(resolve_model())


def _norma(v) -> float:
  return (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5


# --------------------------------------------------------------------------- #
# (a) Medições analíticas
# --------------------------------------------------------------------------- #
def test_angulo_entre_vetores_perpendiculares_e_90() -> None:
  a = med.medir_vetor_mundo(med.matriz_hpr(0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
  b = (0.0, 1.0, 0.0)
  produto = med._produto_escalar(a, b)
  assert abs(produto) < 1e-9  # cos(90) = 0


def test_desvio_repouso_de_90_e_180() -> None:
  identidade = med.matriz_hpr(0.0, 0.0, 0.0)
  giro_90 = med.matriz_hpr(radians(90.0), 0.0, 0.0)
  giro_180 = med.matriz_hpr(radians(180.0), 0.0, 0.0)

  assert med.desvio_repouso_graus(identidade, giro_90) == pytest.approx(90.0, abs=1e-6)
  assert med.desvio_repouso_graus(identidade, giro_180) == pytest.approx(180.0, abs=1e-6)


def test_classificar_direcao_cima() -> None:
  direcao = med.classificar_direcao((0.0, 1.0, 0.0), LIMIARES_PADRAO)
  assert direcao.principal is DirecaoMundo.CIMA
  assert direcao.alinhamento_norm == pytest.approx(1.0, abs=1e-9)
  assert not direcao.ambigua


def test_classificar_direcao_diagonal_marca_ambigua() -> None:
  # Vetor a 45° entre CIMA e FRENTE: nenhum eixo domina com folga.
  direcao = med.classificar_direcao((0.0, 1.0, 1.0), LIMIARES_PADRAO)
  assert direcao.principal in (DirecaoMundo.CIMA, DirecaoMundo.FRENTE)
  assert direcao.secundaria in (DirecaoMundo.CIMA, DirecaoMundo.FRENTE)
  assert direcao.ambigua


# --------------------------------------------------------------------------- #
# (b) Invariante de corpo rígido
# --------------------------------------------------------------------------- #
def test_perpendicularidade_sobrevive_a_rotacao(model) -> None:
  rig = Rig.from_model(model)
  rig.set_rotation("right-arm", x=35.0, y=-20.0, z=50.0)

  matriz = med.resolver_rot_mundo(Parte.BRACO_DIREITO, rig.pose(), model)
  a = med.medir_vetor_mundo(matriz, (1.0, 0.0, 0.0))
  b = med.medir_vetor_mundo(matriz, (0.0, 1.0, 0.0))

  assert med._produto_escalar(a, b) == pytest.approx(0.0, abs=1e-9)
  assert _norma(a) == pytest.approx(1.0, abs=1e-9)
  assert _norma(b) == pytest.approx(1.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# (c) Simetria no repouso
# --------------------------------------------------------------------------- #
def test_simetria_bracos_no_repouso(model) -> None:
  rig = Rig.from_model(model)
  estados = med.medir_todas_as_partes(rig.pose(), model)

  direito = estados[Parte.BRACO_DIREITO]
  esquerdo = estados[Parte.BRACO_ESQUERDO]

  assert direito.desvio_repouso_graus == pytest.approx(0.0, abs=1e-6)
  assert esquerdo.desvio_repouso_graus == pytest.approx(0.0, abs=1e-6)
  assert direito.desvio_repouso_graus == pytest.approx(esquerdo.desvio_repouso_graus, abs=1e-6)


# --------------------------------------------------------------------------- #
# (d) Cobertura total das partes
# --------------------------------------------------------------------------- #
def test_medir_todas_as_partes_cobre_toda_parte(model) -> None:
  rig = Rig.from_model(model)
  estados = med.medir_todas_as_partes(rig.pose(), model)

  assert set(estados) == set(Parte)

  for parte, estado in estados.items():
    assert isinstance(estado, EstadoParte)
    assert estado.parte is parte
    assert estado.vetores_mundo  # pelo menos um vetor medido
    for direcao in estado.direcoes.values():
      assert isinstance(direcao, Direcao)
    assert isinstance(estado.altura_relativa, AlturaRelativa)


def test_membros_tem_ponta_e_comprimento_corpo_nao(model) -> None:
  rig = Rig.from_model(model)
  estados = med.medir_todas_as_partes(rig.pose(), model)

  mao = estados[Parte.MAO_DIREITA]
  assert mao.comprimento_u is not None
  assert mao.ponta_mundo is not None

  corpo = estados[Parte.CORPO]
  assert corpo.comprimento_u is None
  assert corpo.ponta_mundo is None


def test_referencias_corpo_crescem_do_chao_ao_topo(model) -> None:
  refs = med.medir_referencias_corpo(model)
  assert refs.y_chao <= refs.y_topo


# --------------------------------------------------------------------------- #
# (e) Fronteira — Python puro, sem engine
# --------------------------------------------------------------------------- #
def test_rig_medidas_nao_importa_engine() -> None:
  arvore = ast.parse(Path(med.__file__).read_text(encoding="utf-8"))
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
