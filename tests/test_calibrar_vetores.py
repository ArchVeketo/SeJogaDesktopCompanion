"""Casos puros (sem GPU) da ferramenta de calibração de vetores.

Exercita a parte NÃO-engine de ``tools/calibrar_vetores.py``: carregamento de
pose, catálogo de setas por parte e o mapa de flag que cada seta estampa. O
render offscreen (Panda3D) NÃO é tocado aqui — ``RenderizadorCalibracao`` só
importa o engine dentro do ``__init__``, então importar o módulo e chamar estas
funções não exige GPU.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _carregar(nome: str, caminho: Path):
  spec = importlib.util.spec_from_file_location(nome, caminho)
  assert spec is not None and spec.loader is not None
  modulo = importlib.util.module_from_spec(spec)
  sys.modules[nome] = modulo
  spec.loader.exec_module(modulo)

  return modulo


cv = _carregar("calibrar_vetores", RAIZ / "tools" / "calibrar_vetores.py")

from sejoga import rig_debug as rd  # noqa: E402
from sejoga.assets import resolve_model  # noqa: E402
from sejoga.model import load_model  # noqa: E402


def _estado(pose_nome: str) -> rd.EstadoRig:
  t = cv._INSTANTE_PADRAO[pose_nome]
  pose = cv._carregar_pose(pose_nome, t)
  model = load_model(resolve_model())

  return rd.estado_rig(pose, model)


def test_carregar_pose_devolve_todos_os_grupos() -> None:
  from sejoga.rig import ALL_GROUPS

  pose = cv._carregar_pose("idle", 1.0)

  for grupo in ALL_GROUPS:
    assert grupo in pose


def test_parte_all_cobre_todas_as_juntas() -> None:
  estado = _estado("idle")
  setas = cv.montar_setas("all", estado)
  grupos = {s.grupo for s in setas}

  assert grupos == {"hand", "hand2", "head", "door", "right-feet", "left-feet"}


def test_parte_hand_so_tem_maos_com_tres_vetores_cada() -> None:
  estado = _estado("idle")
  setas = cv.montar_setas("hand", estado)

  assert {s.grupo for s in setas} == {"hand", "hand2"}
  assert len([s for s in setas if s.grupo == "hand"]) == 3
  nomes = {s.nome_vetor for s in setas if s.grupo == "hand"}
  assert nomes == {"normal_palma", "dorso", "direcao_dedos"}


def test_toda_seta_referencia_vetor_existente() -> None:
  estado = _estado("idle")

  for seta in cv.montar_setas("all", estado):
    assert seta.nome_vetor in rd.VETORES_REFERENCIA[seta.chave_ref]


def test_rotulo_traz_a_flag_do_rig_debug() -> None:
  estado = _estado("idle")
  por_grupo = {s.grupo: s for s in cv.montar_setas("hand", estado)}
  palma_direita = next(
    s for s in cv.montar_setas("hand", estado)
    if s.grupo == "hand" and s.nome_vetor == "normal_palma"
  )

  assert palma_direita.rotulo.endswith(estado.mao_direita.palma_flag)
  assert "hand" in por_grupo


def test_wave_reporta_palma_para_cima_na_mao_direita() -> None:
  # Regressão do bug observado: no aceno, a mão direita sai PALMA_PARA_CIMA — é
  # exatamente o que a calibração visual deve ajudar a confirmar/refutar.
  estado = _estado("wave")

  assert estado.mao_direita.palma_flag == "PALMA_PARA_CIMA"
