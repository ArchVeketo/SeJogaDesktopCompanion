"""Casos que PROVAM a medição de articulações da Fase 3 (seção 6).

Monta poses conhecidas num ``Rig`` em repouso com ``rig.ALL_GROUPS``, carrega o
``Model`` real via ``sejoga.assets.resolve_model`` e confere que as articulações
são medidas e classificadas como deveriam: cotovelo esticado em repouso, flexão
crescendo ao girar o antebraço, fronteiras exatas do estado e ``fora_do_limite``.

As grandezas puras (``medir_flexao``, ``estado_flexao``, ``fora_do_limite``,
``plano_de_flexao``) são testadas isoladamente, sem engine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sejoga import rig_articulacoes as ra
from sejoga.assets import resolve_model
from sejoga.model import load_model
from sejoga.rig import ALL_GROUPS, Rig, Rotation3
from sejoga.rig_mapa import EstadoFlexao, Parte, PlanoFlexao, TipoArticulacao
from sejoga.rig_medidas import medir_todas_as_partes


@pytest.fixture(scope="module")
def model():
  return load_model(resolve_model())


@pytest.fixture
def rig():
  r = Rig()
  for grupo in ALL_GROUPS:
    r.rest[grupo] = Rotation3()
    r.current[grupo] = Rotation3()
  return r


# --------------------------------------------------------------------------- #
# Catálogo — ajustado ao GLTF (sem joelho/quadril/tornozelo)
# --------------------------------------------------------------------------- #
def test_catalogo_tem_cotovelos_ombros_punhos_pescoco_porta() -> None:
  assert set(ra.ARTICULACOES) == {
    "cotovelo_direito",
    "cotovelo_esquerdo",
    "ombro_direito",
    "ombro_esquerdo",
    "punho_direito",
    "punho_esquerdo",
    "pescoco",
    "dobradica_porta",
  }


def test_catalogo_nao_tem_joelho_quadril_tornozelo() -> None:
  for nome in ra.ARTICULACOES:
    assert "joelho" not in nome
    assert "quadril" not in nome
    assert "tornozelo" not in nome
    assert "tentaculo" not in nome


def test_dobradica_porta_tem_pai_real_cabeca() -> None:
  porta = ra.ARTICULACOES["dobradica_porta"]

  assert porta.segmento_proximal is Parte.CABECA
  assert porta.segmento_distal is Parte.PORTA
  assert porta.tipo is TipoArticulacao.DOBRADICA
  assert (porta.angulo_min_graus, porta.angulo_max_graus) == (0.0, 120.0)


def test_cotovelo_direito_faixa_proposta() -> None:
  cot = ra.ARTICULACOES["cotovelo_direito"]

  assert cot.tipo is TipoArticulacao.DOBRADICA
  assert (cot.angulo_min_graus, cot.angulo_max_graus) == (-10.0, 150.0)


# --------------------------------------------------------------------------- #
# Flexão assinada — grandeza pura (seção 6.2)
# --------------------------------------------------------------------------- #
def test_medir_flexao_segmentos_alinhados_da_zero() -> None:
  phi, _ = ra.medir_flexao((0.0, -1.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0))

  assert phi == pytest.approx(0.0, abs=1e-9)


def test_medir_flexao_90_graus() -> None:
  # Proximal para baixo, distal para frente: 90° entre eles.
  phi, dobra = ra.medir_flexao((0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0))

  assert abs(phi) == pytest.approx(90.0, abs=1e-6)
  assert dobra == pytest.approx((0.0, 0.0, 1.0), abs=1e-6)


def test_medir_flexao_sinal_inverte_com_referencia() -> None:
  positivo, _ = ra.medir_flexao((0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0))
  negativo, _ = ra.medir_flexao((0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, -1.0))

  assert positivo > 0.0
  assert negativo < 0.0
  assert positivo == pytest.approx(-negativo, abs=1e-6)


# --------------------------------------------------------------------------- #
# Estado por faixas — fronteiras exatas (seção 6.5)
# --------------------------------------------------------------------------- #
def test_estado_flexao_fronteira_esticado_leve() -> None:
  assert ra.estado_flexao(15.0) is EstadoFlexao.ESTICADO
  assert ra.estado_flexao(15.01) is EstadoFlexao.LEVE


def test_estado_flexao_demais_faixas() -> None:
  assert ra.estado_flexao(0.0) is EstadoFlexao.ESTICADO
  assert ra.estado_flexao(45.0) is EstadoFlexao.LEVE
  assert ra.estado_flexao(45.01) is EstadoFlexao.DOBRADO
  assert ra.estado_flexao(110.0) is EstadoFlexao.DOBRADO
  assert ra.estado_flexao(110.01) is EstadoFlexao.MUITO_DOBRADO
  assert ra.estado_flexao(-1.0) is EstadoFlexao.HIPEREXTENDIDO


# --------------------------------------------------------------------------- #
# fora_do_limite (seção 6.5)
# --------------------------------------------------------------------------- #
def test_fora_do_limite_respeita_tolerancia() -> None:
  cot = ra.ARTICULACOES["cotovelo_direito"]

  # Dentro do limite (com tolerância de 2°).
  assert not ra.fora_do_limite(150.0, cot)
  assert not ra.fora_do_limite(151.0, cot)
  # Passou do máximo + tolerância.
  assert ra.fora_do_limite(153.0, cot)
  # Passou do mínimo - tolerância.
  assert ra.fora_do_limite(-13.0, cot)


def test_proporcao_norm_extremos() -> None:
  cot = ra.ARTICULACOES["cotovelo_direito"]

  assert ra.proporcao_norm(-10.0, cot.angulo_min_graus, cot.angulo_max_graus) == pytest.approx(0.0)
  assert ra.proporcao_norm(150.0, cot.angulo_min_graus, cot.angulo_max_graus) == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# Pipeline completo com o Model real
# --------------------------------------------------------------------------- #
def test_cotovelo_em_repouso_esticado(rig, model) -> None:
  partes = medir_todas_as_partes(rig.pose(), model)
  estado = ra.analisar_articulacao(ra.ARTICULACOES["cotovelo_direito"], partes)

  assert estado.estado is EstadoFlexao.ESTICADO
  assert abs(estado.angulo_flexao_graus) == pytest.approx(0.0, abs=1.0)
  assert not estado.fora_do_limite


def test_cotovelo_flexao_cresce_ao_girar_antebraco(rig, model) -> None:
  repouso = ra.analisar_articulacao(
    ra.ARTICULACOES["cotovelo_direito"], medir_todas_as_partes(rig.pose(), model)
  )

  rig.set_rotation("ant-arm", z=90.0)
  dobrado = ra.analisar_articulacao(
    ra.ARTICULACOES["cotovelo_direito"], medir_todas_as_partes(rig.pose(), model)
  )

  assert abs(dobrado.angulo_flexao_graus) > abs(repouso.angulo_flexao_graus)
  assert dobrado.estado is not EstadoFlexao.ESTICADO


def test_analisar_articulacoes_cobre_todo_catalogo(rig, model) -> None:
  partes = medir_todas_as_partes(rig.pose(), model)
  estados = ra.analisar_articulacoes(partes)

  assert set(estados) == set(ra.ARTICULACOES)

  for nome, estado in estados.items():
    assert estado.nome == nome
    assert isinstance(estado.estado, EstadoFlexao)
    assert isinstance(estado.plano, PlanoFlexao)


def test_plano_de_flexao_frente_quando_dobra_para_frente() -> None:
  # Proximal para baixo, distal para a frente (+Z = frente do corpo).
  plano = ra.plano_de_flexao(
    (0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)
  )

  assert plano is PlanoFlexao.PARA_FRENTE


def test_plano_de_flexao_sem_flexao_quando_alinhados() -> None:
  plano = ra.plano_de_flexao(
    (0.0, -1.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)
  )

  assert plano is PlanoFlexao.SEM_FLEXAO


# --------------------------------------------------------------------------- #
# FRONTEIRA — Python puro, sem engine
# --------------------------------------------------------------------------- #
def test_rig_articulacoes_nao_importa_engine() -> None:
  import ast

  caminho = Path(ra.__file__)
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
