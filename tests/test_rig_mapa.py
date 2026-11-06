"""Testes da fundação do mapeamento do rig (``sejoga.rig_mapa``).

Cobre: (a) todo nó nomeado do rig presente no modelo real tem uma ``Parte``
com valor igual; (b) aliases de flags antigas resolvem para os Enums novos;
(c) fronteira Python puro, sem engine.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from sejoga.nucleo.assets import resolve_model
from sejoga.nucleo.model import load_model
from sejoga.nucleo.rig import ALL_GROUPS
from sejoga.rig_mapa import rig_mapa as rm


@pytest.fixture(scope="module")
def model():
  return load_model(resolve_model())


# --------------------------------------------------------------------------- #
# (a) Cobertura do modelo: toda Parte casa com um grupo do GLTF
# --------------------------------------------------------------------------- #
def test_parte_cobre_todos_os_nos_nomeados_do_rig(model) -> None:
  nomeados = model.named_set()
  grupos_do_rig = {g for g in ALL_GROUPS if g in nomeados}
  valores_parte = {parte.value for parte in rm.Parte}

  faltando = grupos_do_rig - valores_parte
  assert not faltando, f"grupos do rig sem entrada em Parte: {sorted(faltando)}"


def test_cada_parte_aponta_para_grupo_existente(model) -> None:
  nomeados = model.named_set()
  for parte in rm.Parte:
    assert parte.value in nomeados, f"Parte.{parte.name} sem nó no modelo"


def test_hierarquia_e_lado_cobrem_todas_as_partes() -> None:
  for parte in rm.Parte:
    assert parte in rm.PAI_DE
    assert parte in rm.LADO_DE


def test_porta_e_filha_da_cabeca() -> None:
  # Correção ao documento: door é filho de head, não de body.
  assert rm.pai_de(rm.Parte.PORTA) is rm.Parte.CABECA


def test_pes_sao_filhos_da_raiz() -> None:
  assert rm.pai_de(rm.Parte.PE_ESQUERDO) is None
  assert rm.pai_de(rm.Parte.PE_DIREITO) is None


def test_lado_de_braco_esquerdo_e_direito() -> None:
  assert rm.lado_de(rm.Parte.BRACO_DIREITO) is rm.Lado.DIREITA
  assert rm.lado_de(rm.Parte.BRACO_ESQUERDO) is rm.Lado.ESQUERDA


# --------------------------------------------------------------------------- #
# (b) Aliases das flags antigas
# --------------------------------------------------------------------------- #
def test_resolver_alias_palma_para_cima() -> None:
  assert rm.resolver_alias("PALMA_PARA_CIMA") is rm.DirecaoPalma.PARA_CIMA


def test_resolver_alias_casos_variados() -> None:
  assert rm.resolver_alias("PALMA_PARA_BAIXO") is rm.DirecaoPalma.PARA_BAIXO
  assert rm.resolver_alias("PORTA_FECHADA") is rm.EstadoPorta.FECHADA
  assert rm.resolver_alias("PORTA_ENTREABERTA") is rm.EstadoPorta.ENTREABERTA
  assert rm.resolver_alias("OLHAR_FRENTE") is rm.OlharHorizontal.FRENTE
  assert rm.resolver_alias("TOPO_CIMA") is rm.InclinacaoCabeca.RETA
  assert rm.resolver_alias("DEDOS_CIMA") is rm.DirecaoDedos.CIMA


def test_resolver_alias_desconhecido_levanta_keyerror() -> None:
  with pytest.raises(KeyError):
    rm.resolver_alias("FLAG_INEXISTENTE")


# --------------------------------------------------------------------------- #
# (c) Fronteira — Python puro, sem engine
# --------------------------------------------------------------------------- #
def test_rig_mapa_nao_importa_engine() -> None:
  _assertar_sem_engine(Path(rm.__file__))


def _assertar_sem_engine(caminho: Path) -> None:
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
