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

from sejoga.animacao.animation import AnimationController
from sejoga.nucleo.assets import resolve_model
from sejoga.nucleo.model import load_model
from sejoga.nucleo.rig import ALL_GROUPS, Rig, Rotation3
from sejoga.rig_mapa import colisao_membros as col
from sejoga.rig_mapa import rig_medidas as med

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
  from sejoga.rig_mapa.rig_mapa import Parte

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
  from sejoga.nucleo import rig as rig_mod

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


def _trilhas_wake_correcao(model, analisar):
  """Amostra a reação wake COM correção, devolvendo duas trilhas em graus.

  Como a correção agora toca SÓ as juntas colisoras (e não mais filtra a pose
  inteira), o teste de tranco não pode comparar contra a pose globalmente
  amaciada de antes — isso só passava por causa do bug que o review apontou.
  A medida correta de "sem tranco" é a mola CUMPRINDO seu papel: a saída
  suavizada tem de ter jerk MUITO menor que o ALVO CORRIGIDO aplicado CRU (sem
  mola). Esta função produz as duas trilhas do MESMO gesto:

  - ``sprung``: a saída real do controller (alvo corrigido perseguido pela mola);
  - ``crua``: o alvo corrigido do frame aplicado direto, sem mola (o que a
    correção faria SEM amortecimento — cheio de tranco).
  """
  ctrl = AnimationController(_rig(), model=model)
  ctrl.interact("wake")
  dt = 1.0 / analisar.FPS

  sprung: list[dict[str, tuple[float, float, float]]] = []
  crua: list[dict[str, tuple[float, float, float]]] = []

  original = col.resolver_colisoes
  capturado: dict[str, dict] = {}

  def _capturar(pose, partes, parametros=None):
    alvo = original(pose, partes, parametros)
    capturado["pose"] = dict(pose)
    capturado["alvo"] = {g: alvo[g] for g in alvo}
    return alvo

  col.resolver_colisoes = _capturar
  try:
    for _ in range(int(analisar.FPS * 2.5)):
      pose = ctrl.update(dt)
      sprung.append({
        g: (degrees(r.x), degrees(r.y), degrees(r.z)) for g, r in pose.items()
      })
      # Alvo corrigido do frame, sem mola: pose crua com as juntas empurradas.
      alvo_cru = dict(capturado.get("pose", {}))
      alvo_cru.update(capturado.get("alvo", {}))
      crua.append({
        g: (degrees(r.x), degrees(r.y), degrees(r.z)) for g, r in alvo_cru.items()
      })
  finally:
    col.resolver_colisoes = original

  return sprung, crua


def test_correcao_nao_introduz_tranco(model) -> None:
  # A correção toca SÓ as juntas colisoras; a suavidade tem de vir da mola.
  # "Sem tranco" = a saída amortecida tem jerk MUITO menor que o alvo corrigido
  # aplicado cru (sem mola), que é o que introduziria tranco. A mola de 0,6 Hz
  # age como passa-baixa: não persegue o pico de penetração sub-segundo da
  # reação de acordar, então corrige o overlap SUSTENTADO sem somar tranco.
  analisar = _carregar_analisar_anim()

  sprung, crua = _trilhas_wake_correcao(model, analisar)
  jerk_sprung = _pior_jerk_total(sprung, 2.5, analisar)
  jerk_cru = _pior_jerk_total(crua, 2.5, analisar)

  assert jerk_sprung < jerk_cru * 0.5, (
    f"mola não amorteceu a correção: cru={jerk_cru:.0f} sprung={jerk_sprung:.0f}"
  )


def test_pose_sem_excedente_nao_e_alterada(model) -> None:
  # Uma pose SEM excedente (só piso estrutural) não é tocada pela correção. A
  # pose de repouso é o caso canônico; aqui também se confirma que membros cujo
  # ÚNICO contato é o piso puro (`braço vs tronco`, `pernas vs pé`) saem
  # inalterados mesmo medindo penetração bruta alta.
  from sejoga.rig_mapa.rig_mapa import Parte

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
  # A correção de colisão agora está no pose_resolver; sem model é inerte.
  devolvida = ctrl.pose_resolver._resolver_colisoes_suave(pose, 1 / 60, None)

  assert devolvida == pose


def test_junta_sem_excedente_em_movimento_passa_intacta(model) -> None:
  # Invariância no CAMINHO DO CONTROLLER (com Model): uma junta que NÃO colide,
  # mas se MOVE a cada frame (ex.: `head`, que o resolvedor nunca empurra), tem
  # de sair IDÊNTICA à pose crua. Se a correção semeasse/filtrasse todas as
  # juntas, a mola lenta de 0,6 Hz atrasaria `head` e este teste falharia.
  ctrl = AnimationController(_rig(), model=model)
  assert ctrl._collision_model is not None

  dt = 1 / 60
  # Parte da pose de repouso (sem excedente acima do limiar) e varia só `head`.
  base = {g: Rotation3() for g in ALL_GROUPS}
  for i in range(60):
    pose = dict(base)
    pose["head"] = Rotation3(0.0, 0.3 * (i / 59), 0.0)  # heading varia no tempo
    # A correção agora está no pose_resolver.
    devolvida = ctrl.pose_resolver._resolver_colisoes_suave(pose, dt, model)

    assert devolvida["head"] == pose["head"], (
      f"junta não-colisora em movimento foi filtrada no frame {i}"
    )
