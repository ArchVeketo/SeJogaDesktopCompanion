"""Testes do módulo de detecção de colisão (``sejoga.colisao_membros``).

Cobre: (a) a MATEMÁTICA sintética (cápsula-cápsula, cápsula-caixa, distância
segmento-segmento em casos conhecidos, tangência); (b) uma VARREDURA que roda a
detecção nas mesmas poses da ferramenta sem levantar exceção e com saída bem
formada; (c) a fronteira Python puro, sem engine. Segue o estilo de
``tests/test_rig_medidas.py`` e ``tests/test_rig_articulacoes.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from sejoga import colisao_membros as col
from sejoga import rig as rig_mod
from sejoga import rig_medidas as med
from sejoga.assets import resolve_model
from sejoga.model import load_model
from sejoga.rig_mapa import Parte


@pytest.fixture(scope="module")
def model():
  return load_model(resolve_model())


# --------------------------------------------------------------------------- #
# (a) Matemática sintética — cápsula-cápsula
# --------------------------------------------------------------------------- #
def test_capsulas_sobrepostas_tem_penetracao_positiva() -> None:
  # Dois segmentos paralelos a 0,1 u de distância, raios somando 0,4.
  ca = col.Capsula(a=(0.0, 0.0, 0.0), b=(1.0, 0.0, 0.0), raio=0.2)
  cb = col.Capsula(a=(0.0, 0.1, 0.0), b=(1.0, 0.1, 0.0), raio=0.2)

  profundidade = col.penetracao_capsula_capsula(ca, cb)

  assert profundidade == pytest.approx(0.3, abs=1e-9)


def test_capsulas_separadas_tem_penetracao_zero() -> None:
  ca = col.Capsula(a=(0.0, 0.0, 0.0), b=(1.0, 0.0, 0.0), raio=0.1)
  cb = col.Capsula(a=(0.0, 5.0, 0.0), b=(1.0, 5.0, 0.0), raio=0.1)

  assert col.penetracao_capsula_capsula(ca, cb) == 0.0


def test_capsulas_tangentes_dao_penetracao_quase_zero() -> None:
  # Distância entre eixos = 0,4 = soma dos raios: contato tangente.
  ca = col.Capsula(a=(0.0, 0.0, 0.0), b=(1.0, 0.0, 0.0), raio=0.2)
  cb = col.Capsula(a=(0.0, 0.4, 0.0), b=(1.0, 0.4, 0.0), raio=0.2)

  assert col.penetracao_capsula_capsula(ca, cb) == pytest.approx(0.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# (a) Matemática sintética — cápsula-caixa
# --------------------------------------------------------------------------- #
def _caixa_unitaria() -> col.CaixaOrientada:
  """Caixa centrada na origem, eixos do mundo, meias-dimensões 0,5."""
  return col.CaixaOrientada(
    centro=(0.0, 0.0, 0.0),
    eixos=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    meias_dim=(0.5, 0.5, 0.5),
  )


def test_capsula_dentro_da_caixa_tem_penetracao_positiva() -> None:
  # Segmento com a ponta no centro da caixa (amostra i=0 cai no centro):
  # profundidade = meia-dim (0,5) + raio (0,1).
  cap = col.Capsula(a=(0.0, 0.0, 0.0), b=(0.4, 0.0, 0.0), raio=0.1)

  profundidade = col.penetracao_capsula_caixa(cap, _caixa_unitaria())

  assert profundidade > 0.0
  # No centro a distância assinada é -0,5 (folga até a face); + raio 0,1.
  assert profundidade == pytest.approx(0.6, abs=1e-6)


def test_capsula_longe_da_caixa_nao_penetra() -> None:
  cap = col.Capsula(a=(5.0, 5.0, 5.0), b=(6.0, 5.0, 5.0), raio=0.1)

  assert col.penetracao_capsula_caixa(cap, _caixa_unitaria()) == 0.0


def test_dist_ponto_caixa_sinal_dentro_e_fora() -> None:
  caixa = _caixa_unitaria()

  # Dentro: distância assinada negativa (folga até a face mais próxima).
  assert col.dist_ponto_caixa((0.0, 0.0, 0.0), caixa) == pytest.approx(-0.5, abs=1e-9)

  # Fora, a 0,5 u de uma face: distância positiva.
  assert col.dist_ponto_caixa((1.0, 0.0, 0.0), caixa) == pytest.approx(0.5, abs=1e-9)


# --------------------------------------------------------------------------- #
# (a) Matemática sintética — distância segmento-segmento
# --------------------------------------------------------------------------- #
def test_segmentos_paralelos_deslocados() -> None:
  # Paralelos no eixo X, separados 2 u em Y.
  d = col.dist_segmento_segmento((0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                                 (0.0, 2.0, 0.0), (1.0, 2.0, 0.0))
  assert d == pytest.approx(2.0, abs=1e-9)


def test_segmentos_cruzados_perpendiculares() -> None:
  # Um em X no plano z=0, outro em Y no plano z=1: distância = 1 (em Z).
  d = col.dist_segmento_segmento((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                                 (0.0, -1.0, 1.0), (0.0, 1.0, 1.0))
  assert d == pytest.approx(1.0, abs=1e-9)


def test_segmento_degenerado_vira_ponto_segmento() -> None:
  # Segmento 2 é um ponto (a == b); distância do ponto à reta do segmento 1.
  d = col.dist_segmento_segmento((0.0, 0.0, 0.0), (2.0, 0.0, 0.0),
                                 (1.0, 3.0, 0.0), (1.0, 3.0, 0.0))
  assert d == pytest.approx(3.0, abs=1e-9)


def test_ambos_degenerados_e_distancia_entre_pontos() -> None:
  d = col.dist_segmento_segmento((0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
                                 (3.0, 4.0, 0.0), (3.0, 4.0, 0.0))
  assert d == pytest.approx(5.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# (b) Varredura nas poses reais
# --------------------------------------------------------------------------- #
def _poses_de_producao() -> dict[str, object]:
  """Mesmas poses da ferramenta (idle, locomoção, drag, fall, dance, etc.)."""
  poses: dict[str, object] = {}

  for personalidade in rig_mod.IdlePersonality:
    poses[f"idle:{personalidade.value}"] = (
      lambda rig, t, p=personalidade: rig_mod.pose_idle(rig, t, p, respiracao=0.6)
    )

  poses["walk"] = lambda rig, t: rig_mod.pose_walk(rig, t, run=False)
  poses["run"] = lambda rig, t: rig_mod.pose_walk(rig, t, run=True)
  poses["drag"] = lambda rig, t: rig_mod.pose_drag(rig, t, direction=1.0, drag_intensity=1.0)
  poses["fall"] = lambda rig, t: rig_mod.pose_thrown(rig, t)
  poses["dance"] = lambda rig, t: rig_mod.pose_dance(rig, t)
  poses["sleep"] = lambda rig, t: rig_mod.pose_sleep(rig, t)

  for kind in ("wave", "stretch", "peek"):
    poses[f"flourish:{kind}"] = lambda rig, t, k=kind: rig_mod.pose_flourish(rig, k, t)

  for kind in ("hover", "click", "double_click", "pet", "poke", "land", "wake"):
    poses[f"interaction:{kind}"] = (
      lambda rig, t, k=kind: rig_mod.pose_interaction(rig, k, t, direction=0.5, vertical=0.3)
    )

  return poses


def _rig_repouso() -> rig_mod.Rig:
  repouso = {g: rig_mod.Rotation3() for g in rig_mod.ALL_GROUPS}
  return rig_mod.Rig(rest=dict(repouso), current=dict(repouso))


def test_detectar_colisao_roda_todas_as_poses(model) -> None:
  poses = _poses_de_producao()
  instantes = (0.0, 0.6, 1.5)

  for nome_pose, aplicador in poses.items():
    for t in instantes:
      rig = _rig_repouso()
      aplicador(rig, t)  # type: ignore[operator]
      partes = med.medir_todas_as_partes(rig.pose(), model)

      colisoes = col.detectar_colisoes(partes, nome_pose, t)

      assert isinstance(colisoes, list)

      for colisao in colisoes:
        assert isinstance(colisao, col.Colisao)
        assert colisao.pose == nome_pose
        assert colisao.t_s == t
        assert colisao.profundidade_u >= col.LIMIAR_PENETRACAO_U
        assert len(colisao.par) == 2
        assert all(isinstance(p, Parte) for p in colisao.par)


def test_montar_volumes_classifica_membro_e_bloco(model) -> None:
  partes = med.medir_todas_as_partes(_rig_repouso().pose(), model)
  volumes = col.montar_volumes(partes)

  assert isinstance(volumes[Parte.MAO_DIREITA], col.Capsula)
  assert isinstance(volumes[Parte.CORPO], col.CaixaOrientada)
  assert isinstance(volumes[Parte.CABECA], col.CaixaOrientada)


# --------------------------------------------------------------------------- #
# (c) Fronteira — Python puro, sem engine
# --------------------------------------------------------------------------- #
def test_colisao_membros_nao_importa_engine() -> None:
  arvore = ast.parse(Path(col.__file__).read_text(encoding="utf-8"))
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
