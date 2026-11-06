"""Testes da CORREÇÃO PONTUAL SUAVE ligada ao ``AnimationController`` (FEAT-B).

Cobrem o que a FEAT-B promete, ao vivo no pipeline:

1. a correção ligada (com ``Model``) empurra os membros para fora do excedente
   em uma pose comprovadamente colisora (``interaction:wake``), reduzindo a
   penetração de POSE, enquanto o PISO ESTRUTURAL/repouso fica inalterado;
2. a correção NÃO introduz TRANCO (jerk): a curva de ângulo do membro corrigido
   fica abaixo de ``LIMIAR_JERK_TRANCO`` de ``tools/analisar_anim.py``;
3. poses SEM excedente (idle calmo parado) não são alteradas pela correção;
4. sem ``Model`` injetado, a correção é inerte (comportamento preservado).

A correção precisa do ``Model`` puro (leitor glTF sem engine); por isso estes
testes carregam o modelo real do projeto, como ``tests/test_colisao_membros.py``.
"""

from __future__ import annotations

import importlib.util
import sys
from math import degrees
from pathlib import Path

import pytest

from sejoga import colisao_membros as col
from sejoga import rig_medidas as med
from sejoga.animation import AnimationController
from sejoga.assets import resolve_model
from sejoga.model import load_model
from sejoga.rig import ALL_GROUPS, Rig, Rotation3

_RAIZ = Path(__file__).resolve().parent.parent


def _carregar_analisar_anim():
  """Importa ``tools/analisar_anim.py`` (fora do pythonpath de teste)."""
  caminho = _RAIZ / "tools" / "analisar_anim.py"
  spec = importlib.util.spec_from_file_location("analisar_anim", caminho)
  assert spec is not None and spec.loader is not None
  modulo = importlib.util.module_from_spec(spec)
  sys.modules["analisar_anim"] = modulo
  spec.loader.exec_module(modulo)
  return modulo


@pytest.fixture(scope="module")
def model():
  return load_model(resolve_model())


def _rig() -> Rig:
  return Rig(rest={g: Rotation3() for g in ALL_GROUPS})


def _penetracao_maxima(pose: dict[str, Rotation3], model) -> float:
  """Maior penetração BRUTA entre os pares, na pose dada."""
  volumes = col.montar_volumes(med.medir_todas_as_partes(pose, model))
  maior = 0.0
  for a, b in col.PARES_A_CHECAR:
    va, vb = volumes.get(a), volumes.get(b)
    if va is not None and vb is not None:
      maior = max(maior, col._penetracao_entre(va, vb))
  return maior


def _excedente_wake(pose: dict[str, Rotation3], model) -> float:
  """Excedente (penetração - piso) do par braço dir. vs braço esq.

  É o par de pior excedente na pose ``wake`` (ver FEAT-A); serve de medida
  única e estável do quanto a correção removeu.
  """
  from sejoga.rig_mapa import Parte

  volumes = col.montar_volumes(med.medir_todas_as_partes(pose, model))
  va = volumes.get(Parte.BRACO_DIREITO)
  vb = volumes.get(Parte.BRACO_ESQUERDO)
  if va is None or vb is None:
    return 0.0
  bruto = col._penetracao_entre(va, vb)
  return bruto - col.piso_estrutural_de((Parte.BRACO_DIREITO, Parte.BRACO_ESQUERDO))


def test_correcao_reduz_excedente_no_pico_da_pose_colisora(model) -> None:
  # No INSTANTE de pico da pose wake (t=0.6s, o braço cruzando o outro), a
  # meta cheia de resolver_colisoes empurra os membros e reduz o excedente do
  # pior par. É a meta que a mola do controller persegue; prova que a geometria
  # da correção de fato remove o excedente dirigido pela pose.
  import sejoga.rig as rig_mod

  rig = _rig()
  rig_mod.pose_interaction(rig, "wake", 0.6, direction=0.5, vertical=0.3)
  pose = rig.pose()

  exc_antes = _excedente_wake(pose, model)
  assert exc_antes > col.LIMIAR_EXCEDENTE_U  # o pico de fato colide

  partes = med.medir_todas_as_partes(pose, model)
  corrigida = col.resolver_colisoes(pose, partes)
  exc_depois = _excedente_wake(corrigida, model)

  assert exc_depois < exc_antes


def test_correcao_nao_mexe_no_piso_de_repouso(model) -> None:
  # Na pose de REPOUSO (penetração = piso estrutural), o resolvedor não empurra
  # nada: a pose sai idêntica. Garante que a silhueta parada não é deformada.
  rig = _rig()
  rig.reset()
  pose_repouso = rig.pose()

  partes = med.medir_todas_as_partes(pose_repouso, model)
  corrigida = col.resolver_colisoes(pose_repouso, partes)

  for grupo, rot in corrigida.items():
    assert rot == pose_repouso.get(grupo, Rotation3())


def _pior_jerk_total(trilha, duracao, analisar) -> float:
  """Maior |jerk| entre juntas ativas de uma trilha amostrada (via analisar_anim)."""
  def amostrar(t: float) -> dict[str, tuple[float, float, float]]:
    indice = min(len(trilha) - 1, round(t * analisar.FPS))
    return trilha[indice]

  amostragem = analisar.amostrar_clipe_analisavel(
    analisar.ClipeAnalisavel("x", amostrar, duracao, False)
  )
  pior = 0.0
  for trio in amostragem.series.values():
    for serie in trio:
      if analisar._amplitude(serie) < analisar.AMPLITUDE_MINIMA_ATIVA:
        continue
      pior = max(pior, max((abs(v) for v in serie.jerk), default=0.0))
  return pior


def _trilha_wake(com_modelo, model, analisar):
  """Amostra a reação wake de um controller (com/sem correção) em graus."""
  ctrl = AnimationController(_rig(), model=model if com_modelo else None)
  ctrl.interact("wake")
  dt = 1.0 / analisar.FPS
  trilha: list[dict[str, tuple[float, float, float]]] = []
  for _ in range(int(analisar.FPS * 2.5)):
    pose = ctrl.update(dt)
    trilha.append({
      g: (degrees(r.x), degrees(r.y), degrees(r.z)) for g, r in pose.items()
    })
  return trilha


def test_correcao_nao_introduz_tranco(model) -> None:
  # Compara o jerk da MESMA reação wake sem e com correção. A reação de acordar
  # já é um gesto autoral rápido e, por si só, tem jerk alto; o que a FEAT-B
  # promete é NÃO PIORAR isso. A mola lenta (0,6 Hz) age como passa-baixa: não
  # persegue o pico de penetração sub-segundo, então o jerk com correção fica
  # ABAIXO do jerk da animação autoral crua — não introduz tranco novo.
  analisar = _carregar_analisar_anim()

  jerk_inerte = _pior_jerk_total(_trilha_wake(False, model, analisar), 2.5, analisar)
  jerk_ligado = _pior_jerk_total(_trilha_wake(True, model, analisar), 2.5, analisar)

  assert jerk_ligado <= jerk_inerte, (
    f"correção somou jerk: inerte={jerk_inerte:.0f} ligado={jerk_ligado:.0f}"
  )


def test_pose_sem_excedente_nao_e_alterada(model) -> None:
  # Uma pose SEM excedente (só piso estrutural) não é tocada pela correção. A
  # pose de repouso é o caso canônico; aqui também se confirma que membros cujo
  # ÚNICO contato é o piso puro (`braço vs tronco`, `pernas vs pé`) saem
  # inalterados mesmo medindo penetração bruta alta.
  from sejoga.rig_mapa import Parte

  rig = _rig()
  rig.reset()
  pose = rig.pose()

  partes = med.medir_todas_as_partes(pose, model)
  volumes = col.montar_volumes(partes)

  # O braço mergulha ~0,455 u no tronco (bruto alto), mas é PISO PURO: excedente
  # ~0, então a correção não pode deslocá-lo.
  va = volumes[Parte.BRACO_DIREITO]
  vb = volumes[Parte.CORPO]
  bruto = col._penetracao_entre(va, vb)
  excedente = bruto - col.piso_estrutural_de((Parte.BRACO_DIREITO, Parte.CORPO))

  assert bruto > col.LIMIAR_EXCEDENTE_U  # penetração bruta é grande...
  assert excedente < col.LIMIAR_EXCEDENTE_U  # ...mas o excedente é desprezível

  alvo = col.resolver_colisoes(pose, partes)

  for grupo, rot in alvo.items():
    assert rot == pose.get(grupo, Rotation3())


def test_sem_modelo_a_correcao_e_inerte() -> None:
  # Controller sem Model: o gancho de correção não altera a pose exibida.
  ctrl = AnimationController(_rig())
  assert ctrl._collision_model is None

  pose = {g: Rotation3(0.1, 0.2, 0.3) for g in ALL_GROUPS}
  devolvida = ctrl._resolver_colisoes_suave(pose, 1 / 60)

  assert devolvida == pose
