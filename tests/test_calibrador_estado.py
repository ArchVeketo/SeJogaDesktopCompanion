"""Testes do estado puro do calibrador interativo (sem GPU, sem engine)."""
from __future__ import annotations

import ast
import json
from math import radians
from pathlib import Path

import pytest

from sejoga.rig_mapa import calibrador_estado as ce
from sejoga.rig_mapa.calibrador_estado import Direcao, Eixo, EstadoCalibrador

JUNTAS_MINI = {"ombro": "right-arm", "cabeca": "head"}


def _estado() -> EstadoCalibrador:
  return EstadoCalibrador(JUNTAS_MINI)


def test_pose_em_radianos_so_para_juntas_giradas():
  e = _estado()
  assert e.pose() == {}
  e.selecionar_eixo(Eixo.Z)
  e.definir_valor(-30.0)
  pose = e.pose()
  assert set(pose) == {"right-arm"}
  assert pose["right-arm"].z == pytest.approx(radians(-30.0))
  assert pose["right-arm"].x == 0.0


def test_girar_respeita_limite():
  e = _estado()
  e.girar(ce.LIMITE_GRAUS * 3)
  assert e.valor == ce.LIMITE_GRAUS
  e.girar(-ce.LIMITE_GRAUS * 5)
  assert e.valor == -ce.LIMITE_GRAUS


def test_alternar_teste_cicla_mais_menos_zero():
  e = _estado()
  assert e.alternar_teste() == ce.ANGULO_TESTE_GRAUS
  assert e.alternar_teste() == -ce.ANGULO_TESTE_GRAUS
  assert e.alternar_teste() == 0.0


def test_marcar_sem_giro_nao_registra():
  e = _estado()
  assert e.marcar(Direcao.SOBE) is False
  assert e.total_marcado() == 0
  assert "Gire" in e.mensagem


def test_marcar_usa_sinal_do_valor_e_substitui():
  e = _estado()
  e.selecionar_eixo(Eixo.Z)
  e.definir_valor(-45.0)
  assert e.marcar(Direcao.SOBE)
  e.definir_valor(45.0)
  assert e.marcar(Direcao.DESCE)
  assert e.marcar(Direcao.DENTRO)
  m = e.marcacoes
  assert m[("ombro", Eixo.Z, "-")].direcao is Direcao.SOBE
  assert m[("ombro", Eixo.Z, "+")].direcao is Direcao.DENTRO
  assert e.total_marcado() == 2


def test_desmarcar_remove_combinacao_ativa():
  e = _estado()
  e.definir_valor(10.0)
  e.marcar(Direcao.FRENTE)
  assert e.desmarcar() is True
  assert e.total_marcado() == 0
  assert e.desmarcar() is False


def test_proximo_pendente_pula_marcados_e_termina():
  e = _estado()
  assert e.ir_para_proximo_pendente(incluir_atual=True)
  assert (e.junta, e.eixo, e.valor) == ("ombro", Eixo.X, ce.ANGULO_TESTE_GRAUS)
  e.marcar(Direcao.SOBE)
  assert e.ir_para_proximo_pendente()
  assert (e.junta, e.eixo, e.valor) == ("ombro", Eixo.X, -ce.ANGULO_TESTE_GRAUS)
  assert e.pose()["right-arm"].x == pytest.approx(radians(-ce.ANGULO_TESTE_GRAUS))
  for _ in range(e.total_possivel()):
    if e.valor == 0.0:
      e.definir_valor(ce.ANGULO_TESTE_GRAUS)
    e.marcar(Direcao.NENHUM)
    e.ir_para_proximo_pendente()
  assert e.total_marcado() == e.total_possivel()
  assert e.ir_para_proximo_pendente() is False


def test_guiado_zera_as_outras_juntas():
  e = _estado()
  e.selecionar_junta("cabeca")
  e.definir_valor(20.0)
  e.ir_para_proximo_pendente(incluir_atual=True)
  assert list(e.pose()) == ["head"]
  e.selecionar_junta("ombro")
  e.ir_para_proximo_pendente()
  assert len(e.pose()) == 1


def test_json_roundtrip_e_inverso(tmp_path: Path):
  e = _estado()
  e.selecionar_eixo(Eixo.Z)
  e.definir_valor(-45.0)
  e.marcar(Direcao.SOBE)
  e.definir_valor(45.0)
  e.marcar(Direcao.DESCE)
  dados = json.loads(e.para_json())
  assert dados["marcacoes"]["ombro"]["-z"] == {"direcao": "sobe", "graus": -45.0}
  assert dados["inverso"]["ombro"]["sobe"] == [{"eixo": "z", "sinal": "-"}]
  assert dados["inverso"]["ombro"]["desce"] == [{"eixo": "z", "sinal": "+"}]

  destino = tmp_path / "pasta" / "mapa.json"
  e.salvar(destino, destino.with_suffix(".md"))
  outro = _estado()
  assert outro.carregar(destino) == 2
  assert outro.marcacoes == e.marcacoes
  assert "| ombro | `right-arm` | -z | sobe |" in destino.with_suffix(".md").read_text("utf-8")


def test_arquivos_salvos_sem_bom_e_com_lf(tmp_path: Path):
  e = _estado()
  e.definir_valor(5.0)
  e.marcar(Direcao.FORA)
  destino = tmp_path / "m.json"
  e.salvar(destino, tmp_path / "m.md")
  for arq in (destino, tmp_path / "m.md"):
    bruto = arq.read_bytes()
    assert not bruto.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in bruto


def test_carregar_ignora_lixo_e_rejeita_versao():
  e = _estado()
  aplicadas = e.carregar_dict({
    "versao": ce.VERSAO_ARQUIVO,
    "marcacoes": {
      "ombro": {
        "+x": {"direcao": "sobe", "graus": 5},
        "*x": {"direcao": "sobe", "graus": 5},
        "+q": {"direcao": "sobe", "graus": 5},
        "-y": {"direcao": "voa", "graus": 5},
      },
      "inexistente": {"+x": {"direcao": "sobe", "graus": 5}},
    },
  })
  assert aplicadas == 1
  with pytest.raises(ValueError):
    e.carregar_dict({"versao": ce.VERSAO_ARQUIVO + 1})


def test_hud_mostra_junta_eixo_sinal_valor_e_marcacao():
  e = _estado()
  e.selecionar_eixo(Eixo.Y)
  e.definir_valor(-15.0)
  e.marcar(Direcao.ESQUERDA)
  texto = "\n".join(e.linhas_hud())
  assert "ombro" in texto and "EIXO Y" in texto and "sinal -" in texto
  assert "-15.0" in texto and "esquerda" in texto


def test_modulo_nao_importa_engine():
  fonte = Path(ce.__file__).read_text(encoding="utf-8")
  proibidos = {"panda3d", "direct", "PySide6", "win32gui", "win32con", "win32api"}
  for no in ast.walk(ast.parse(fonte)):
    if isinstance(no, ast.Import):
      assert not proibidos & {a.name.split(".")[0] for a in no.names}
    elif isinstance(no, ast.ImportFrom):
      assert (no.module or "").split(".")[0] not in proibidos
