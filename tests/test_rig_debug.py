"""Casos sintéticos que PROVAM cada classificação do núcleo do rig instrumentado.

Montamos poses conhecidas instanciando um ``Rig`` em repouso com
``rig.ALL_GROUPS`` (como ``tools/verificar_gesto.py:_carregar_wave_producao``),
carregamos o ``Model`` real via ``sejoga.nucleo.assets.resolve_model`` e conferimos que
``rig_debug.estado_rig`` classifica cada parte do corpo como deveria.

Cobre o caso do usuário: palma para baixo vs. para cima (roll 180° no eixo do
antebraço), olhar para a direita/esquerda, corpo pendurado de cabeça para baixo,
porta em várias aberturas, e punho aberto vs. fechado.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sejoga.nucleo.assets import resolve_model
from sejoga.nucleo.model import load_model
from sejoga.nucleo.rig import ALL_GROUPS, Rig, Rotation3
from sejoga.rig_mapa import rig_debug as rd


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
def test_palma_em_repouso_aponta_para_frente(rig, model) -> None:
  # Parte 3: a torção-base do antebraço (braco_tuning) põe a dobradiça do
  # cotovelo à frente; no T-pose a palma fica virada para a FRENTE.
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.mao_direita.palma_flag == "PALMA_PARA_FRENTE"


def test_torcao_180_na_mao_vira_palma_para_tras(rig, model) -> None:
  rig.set_rotation("hand", x=180.0)
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.mao_direita.palma_flag == "PALMA_PARA_TRAS"


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
  assert estado.mao_esquerda.palma_flag == "PALMA_PARA_FRENTE"


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
# NOTA DE CONVENÇÃO (MEDIDA no grafo de cena, não em pixels de tela — ver arm_ik): o eixo longo do
# braço é +X (não -Y) e a ELEVAÇÃO na tela é o ROLL (Z), não o heading. Com a
# pose zero o braço fica LATERAL (T-pose, elevação 0); erguer = Z NEGATIVO,
# baixar = Z positivo; a profundidade (avanço/recuo) é o heading (Y). rig_debug
# sobrescreve a geometria dos braços pela FK do renderer para bater com a tela.
def test_braco_em_repouso_fica_baixado(rig, model) -> None:
  # "Baixado" agora é elevação Z positiva (Z=+80 = quase reto para baixo).
  rig.set_rotation("right-arm", z=80.0)
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.membros["right-arm"].direcao_flag == "BAIXADO"
  assert estado.membros["right-arm"].elevacao_graus < 0.0


def test_braco_erguido_pela_rotacao_em_z(rig, model) -> None:
  # Elevação por ROLL (Z) NEGATIVO ergue o braço (eixo longo +X vira +Y).
  rig.set_rotation("right-arm", z=-80.0)
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.membros["right-arm"].direcao_flag == "ERGUIDO"
  assert estado.membros["right-arm"].elevacao_graus > 0.0


def test_membro_lateral_pela_rotacao_em_z(rig, model) -> None:
  # Pose zero = braço LATERAL (T-pose, eixo longo +X na horizontal).
  estado = rd.estado_rig(rig.pose(), model)

  assert estado.membros["right-arm"].direcao_flag == "LATERAL"


# --------------------------------------------------------------------------- #
# ABERTURA/ELEVAÇÃO DO BRAÇO — medido no grafo de cena: elevação é o roll Z (z negativo ergue)
# --------------------------------------------------------------------------- #
def test_abertura_lateral_cresce_com_z(rig, model) -> None:
  # Elevação Z=+55 vs Z=+85: ambos BAIXADOS, mas Z=+85 está mais reto p/ baixo.
  rig.set_rotation("right-arm", z=55.0)
  aberto_55 = rd.estado_rig(rig.pose(), model).membros["right-arm"]

  rig.set_rotation("right-arm", z=85.0)
  aberto_85 = rd.estado_rig(rig.pose(), model).membros["right-arm"]

  assert aberto_55.direcao_flag == "BAIXADO"
  assert aberto_85.direcao_flag == "BAIXADO"
  # Mais elevação (Z maior) = mais baixo (elevação menor, mais negativa).
  assert aberto_85.elevacao_graus < aberto_55.elevacao_graus - 20.0


def test_abertura_flag_colado_semiaberto_aberto(rig, model) -> None:
  # A abertura lateral cresce conforme o braço se aproxima da horizontal (Z→0).
  rig.set_rotation("right-arm", z=85.0)
  assert rd.estado_rig(rig.pose(), model).membros["right-arm"].abertura_flag == "COLADO"

  rig.set_rotation("right-arm", z=55.0)
  assert rd.estado_rig(rig.pose(), model).membros["right-arm"].abertura_flag == "SEMIABERTO"

  rig.set_rotation("right-arm", z=5.0)
  assert rd.estado_rig(rig.pose(), model).membros["right-arm"].abertura_flag == "ABERTO"


def test_abertura_frontal_cresce_ao_projetar_eixo_longo_a_frente(rig, model) -> None:
  # Medido no grafo de cena (tools/oraculo_cena.py --eixos): heading (Y)
  # POSITIVO leva o braço direito para a FRENTE; a abertura frontal sobe ~45°.
  rig.set_rotation("right-arm", y=0.0)
  reto = rd.estado_rig(rig.pose(), model).membros["right-arm"]

  rig.set_rotation("right-arm", y=45.0)
  frente = rd.estado_rig(rig.pose(), model).membros["right-arm"]

  assert frente.abertura_frontal_graus > reto.abertura_frontal_graus + 20.0


# --------------------------------------------------------------------------- #
# POSIÇÃO DA MÃO — ponta da cadeia braço->antebraço->mão relativa ao corpo
# --------------------------------------------------------------------------- #
def test_posicao_mao_afasta_lateralmente_conforme_pose(rig, model) -> None:
  # Medido no grafo de cena: com o braço LATERAL (elevação Z=0) a mão fica BEM afastada no eixo
  # X; baixando o braço (Z=+80) a mão recolhe para perto da linha do corpo.
  rig.set_rotation("right-arm", z=0.0)
  espalhado = rd.estado_rig(rig.pose(), model).mao_direita

  rig.set_rotation("right-arm", z=80.0)
  recolhido = rd.estado_rig(rig.pose(), model).mao_direita

  assert abs(espalhado.posicao_offset[0]) > abs(recolhido.posicao_offset[0])
  assert espalhado.posicao_flag == "MAO_AFASTADA"
  assert recolhido.posicao_flag == "MAO_JUNTO_AO_CORPO"


def test_posicao_mao_offset_bate_com_cadeia_propagada(rig, model) -> None:
  # A posição da ponta da mão vem da FK do renderer (arm_ik): o offset ao corpo
  # é a ponta-relativa-ao-ombro somada à origem do ombro, menos a origem do
  # corpo. Confere a consistência interna do override de braços do rig_debug.
  from sejoga.animacao import arm_ik

  rig.set_rotation("right-arm", z=40.0)
  pose = rig.pose()
  estado = rd.estado_rig(pose, model)

  posicoes = rd.posicao_acumulada(pose, model)
  medido = arm_ik.medir_braco_render(model, "right", pose)
  ponta_rel = medido["ponta_mao_rel_ombro"]
  ombro = posicoes["right-arm"]
  corpo = posicoes["body"]
  esperado = tuple(ombro[i] + ponta_rel[i] - corpo[i] for i in range(3))

  assert estado.mao_direita.posicao_offset == pytest.approx(esperado)


def test_posicao_mao_a_frente_quando_braco_projeta_para_frente(rig, model) -> None:
  # Braço na horizontal girado para a frente (H=+70, medido no grafo de cena)
  # leva a mão para +Z (frente) — a posição 3D real, não o eixo abstrato. (Com
  # R=-80 o braço fica quase vertical e o H só o gira em torno de si.)
  rig.set_rotation("right-arm", y=70.0)
  estado = rd.estado_rig(rig.pose(), model).mao_direita

  assert estado.posicao_offset[2] > 0.0
  assert "MAO_A_FRENTE" in estado.posicao_flag


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
