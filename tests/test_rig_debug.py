"""Casos sintéticos que PROVAM cada classificação do núcleo do rig instrumentado.

Montamos poses conhecidas instanciando um ``Rig`` em repouso com
``rig.ALL_GROUPS`` (como ``tools/verificar_gesto.py:_carregar_wave_producao``),
carregamos o ``Model`` real via ``sejoga.assets.resolve_model`` e conferimos que
``rig_debug.estado_rig`` classifica cada parte do corpo como deveria.

Cobre o caso do usuário: palma para baixo vs. para cima (roll 180° no eixo do
antebraço), olhar para a direita/esquerda, corpo pendurado de cabeça para baixo,
porta em várias aberturas, e punho aberto vs. fechado.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sejoga import rig_debug as rd
from sejoga.assets import resolve_model
from sejoga.model import load_model
from sejoga.rig import ALL_GROUPS, Rig, Rotation3


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
# Núcleo de álgebra — convenção HPR do renderer (H=y, P=x, R=z)
# --------------------------------------------------------------------------- #
def test_matriz_hpr_identidade_para_rotacao_nula() -> None:
  assert rd.matriz_hpr(0.0, 0.0, 0.0) == pytest.approx(rd._identidade3())


def test_classificar_direcao_eixos_do_mundo() -> None:
  assert rd.classificar_direcao((0.0, 1.0, 0.0))[0] == "CIMA"
  assert rd.classificar_direcao((0.0, -1.0, 0.0))[0] == "BAIXO"
  assert rd.classificar_direcao((1.0, 0.0, 0.0))[0] == "DIREITA"
  assert rd.classificar_direcao((-1.0, 0.0, 0.0))[0] == "ESQUERDA"
  assert rd.classificar_direcao((0.0, 0.0, 1.0))[0] == "FRENTE"
  assert rd.classificar_direcao((0.0, 0.0, -1.0))[0] == "TRAS"


# --------------------------------------------------------------------------- #
# MÃO — palma para baixo vs. roll 180° -> palma para cima
# --------------------------------------------------------------------------- #
def test_palma_em_repouso_aponta_para_baixo(rig, model) -> None:
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.mao_direita.palma_flag == "PALMA_PARA_BAIXO"


def test_roll_180_na_mao_vira_palma_para_cima(rig, model) -> None:
  rig.set_rotation("hand", x=180.0)
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.mao_direita.palma_flag == "PALMA_PARA_CIMA"


def test_punho_aberto_vs_fechado(rig, model) -> None:
  aberto = rd.estado_rig(rig.pose(), model)
  assert aberto.mao_direita.punho_flag == "PUNHO_ABERTO"

  rig.set_rotation("fingers", z=40.0)
  fechado = rd.estado_rig(rig.pose(), model)
  assert fechado.mao_direita.punho_flag == "PUNHO_FECHADO"


def test_mao_esquerda_tambem_classifica(rig, model) -> None:
  rig.set_rotation("fingers2", z=40.0)
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.mao_esquerda.punho_flag == "PUNHO_FECHADO"
  assert estado.mao_esquerda.palma_flag == "PALMA_PARA_BAIXO"


# --------------------------------------------------------------------------- #
# CABEÇA — olhar para os lados pelo sinal do heading (y)
# --------------------------------------------------------------------------- #
def test_cabeca_heading_positivo_olha_direita(rig, model) -> None:
  rig.set_rotation("head", y=30.0)
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.cabeca.olhar_flag == "OLHAR_DIREITA"


def test_cabeca_heading_negativo_olha_esquerda(rig, model) -> None:
  rig.set_rotation("head", y=-30.0)
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.cabeca.olhar_flag == "OLHAR_ESQUERDA"


def test_cabeca_em_repouso_olha_para_frente(rig, model) -> None:
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.cabeca.olhar_flag == "OLHAR_FRENTE"
  assert estado.cabeca.topo_flag == "TOPO_CIMA"


# --------------------------------------------------------------------------- #
# CORPO — pendurado de cabeça para baixo (roll ~155) e inclinação
# --------------------------------------------------------------------------- #
def test_corpo_rolado_155_fica_de_cabeca_para_baixo(rig, model) -> None:
  rig.set_rotation("body", z=155.0)
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.corpo.orientacao_flag == "DE_CABECA_PARA_BAIXO"
  assert estado.corpo.rolagem_flag == "TOMBADO_ESQUERDA"


def test_corpo_inclina_a_frente_e_atras(rig, model) -> None:
  rig.set_rotation("body", x=30.0)
  assert rd.estado_rig(rig.pose(), model).corpo.inclinacao_flag == "A_FRENTE"

  rig.set_rotation("body", x=-30.0)
  assert rd.estado_rig(rig.pose(), model).corpo.inclinacao_flag == "ATRAS"


def test_corpo_em_repouso_fica_ereto_e_de_pe(rig, model) -> None:
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.corpo.inclinacao_flag == "ERETO"
  assert estado.corpo.orientacao_flag == "DE_PE"
  assert estado.corpo.rolagem_flag == "APRUMADO"


# --------------------------------------------------------------------------- #
# PORTA — faixas de abertura pelo giro em H (y)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
  "angulo, esperado",
  [
    (0.0, "PORTA_FECHADA"),
    (10.0, "PORTA_ENTREABERTA"),
    (50.0, "PORTA_ABERTA"),
    (100.0, "PORTA_ESCANCARADA"),
  ],
)
def test_porta_classifica_por_faixa(rig, model, angulo, esperado) -> None:
  rig.set_rotation("door", y=angulo)
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.porta.flag == esperado
  assert estado.porta.graus == pytest.approx(angulo, abs=1e-6)


# --------------------------------------------------------------------------- #
# MEMBROS — braço erguido vs. baixado; elevação
# --------------------------------------------------------------------------- #
def test_braco_em_repouso_fica_baixado(rig, model) -> None:
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.membros["right-arm"].direcao_flag == "BAIXADO"
  assert estado.membros["right-arm"].elevacao_graus < 0.0


def test_braco_erguido_pela_rotacao_em_z(rig, model) -> None:
  # Roll de +180° em Z gira o eixo longo de BAIXO (-Y) para CIMA (+Y).
  rig.set_rotation("right-arm", z=180.0)
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.membros["right-arm"].direcao_flag == "ERGUIDO"
  assert estado.membros["right-arm"].elevacao_graus > 0.0


def test_membro_lateral_pela_rotacao_em_z(rig, model) -> None:
  rig.set_rotation("right-arm", z=90.0)
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.membros["right-arm"].direcao_flag == "LATERAL"


# --------------------------------------------------------------------------- #
# ARTICULAÇÕES — cotovelo estendido vs. dobrado
# --------------------------------------------------------------------------- #
def test_cotovelo_em_repouso_estendido(rig, model) -> None:
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.articulacoes["cotovelo_direito"].flag == "ESTENDIDO"


def test_cotovelo_dobra_quando_antebraco_gira(rig, model) -> None:
  # O antebraço gira em relação ao braço -> ângulo entre os eixos longos cresce.
  rig.set_rotation("ant-arm", z=90.0)
  estado = rd.estado_rig(rig.pose(), model)

  art = estado.articulacoes["cotovelo_direito"]
  assert art.flag == "DOBRADO"
  assert art.graus >= rd.ARTICULACAO_DOBRADA_MIN_GRAUS


# --------------------------------------------------------------------------- #
# ORIENTAÇÃO GLOBAL — em pé vs. de cabeça para baixo
# --------------------------------------------------------------------------- #
def test_global_em_repouso_fica_em_pe(rig, model) -> None:
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.orientacao_global.flag == "EM_PE"


def test_global_corpo_rolado_155_fica_de_cabeca_pra_baixo(rig, model) -> None:
  rig.set_rotation("body", z=155.0)
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.orientacao_global.flag == "DE_CABECA_PRA_BAIXO"


def test_global_corpo_tombado_90_fica_deitado(rig, model) -> None:
  rig.set_rotation("body", z=90.0)
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.orientacao_global.flag == "DEITADO"


# --------------------------------------------------------------------------- #
# FRONTEIRA — Python puro, sem engine
# --------------------------------------------------------------------------- #
def test_rig_debug_nao_importa_engine() -> None:
  import ast

  caminho = Path(rd.__file__)
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
