"""Rig instrumentado — leitura em linguagem natural da pose do Mário.

Este módulo é o NÚCLEO do "rig debug": dada uma pose (o mesmo ``dict`` que o
renderizador consome, ``grupo -> Rotation3`` em radianos) e o ``Model`` lido do
glTF, ele diz em PORTUGUÊS para onde cada parte do corpo está apontando —
"a palma está para baixo", "o olhar está à direita", "a porta está entreaberta".

Serve de ponte para o verificador de gesto: em vez de só medir oscilação em um
eixo abstrato, podemos afirmar "durante um aceno a palma deve ficar virada para
FORA e os dedos para CIMA" e conferir contra o que o rig realmente produz.

FRONTEIRA (igual a model.py/rig.py/assets.py/config.py): este arquivo é Python
puro. NÃO importa Panda3D, Qt nem Win32. Só depende de ``math`` e, do próprio
pacote, de ``rig`` e ``model``.

Convenção de rotação (fonte de verdade: ``renderer.apply_rig_pose``,
``src/sejoga/renderer.py`` ~linhas 397-432):

    node.setHpr(base_h + degrees(y), base_p + degrees(x), base_r + degrees(z))

ou seja, de ``Rotation3(x, y, z)`` em radianos o renderizador deriva
``H = y`` (heading), ``P = x`` (pitch) e ``R = z`` (roll), SOMADO ao HPR de
repouso do nó e acumulado pela hierarquia pai->filho do Panda3D. Reimplementamos
essa mesma composição em álgebra pura (``matriz_hpr``) para que as flags batam
com o que é de fato renderizado.

Eixos do mundo (espaço do modelo glTF, Y para cima):

    +X = direita do observador    -X = esquerda
    +Y = cima                     -Y = baixo
    +Z = frente (em direção à tela/observador)   -Z = trás

Pista da palma (de ``rig.pose_flourish`` 'wave'): a normal de repouso da palma
aponta para DENTRO/baixo; só depois de um roll de 180° em X (eixo longo do
antebraço) a palma vira para FORA. Por isso ``VETORES_REFERENCIA['hand']`` usa
uma normal de repouso que, girada 180° em X, resulta em "palma para fora".
"""

from __future__ import annotations

from dataclasses import dataclass
from math import asin, degrees, radians, sin

from sejoga.nucleo.model import Model
from sejoga.nucleo.rig import ALL_GROUPS, Rotation3

# FACHADA: a álgebra 3x3 (matrizes HPR, produto, aplicação, normalização e as
# rotações por eixo) vive em ``rig_medidas`` desde a Fase 2. Este módulo passou
# a REEXPORTAR esses símbolos em vez de duplicá-los, sem mudar assinaturas nem o
# comportamento observável. As flags e dataclasses do console seguem aqui.
from sejoga.rig_mapa.rig_medidas import (
  Mat3,
  _aplicar3,
  _identidade3,
  _mul3,
  _normalizar,
  matriz_hpr,  # noqa: F401  # reexportado: API pública da fachada (seção 11.5)
  matriz_hpr_de_rotacao,
  matriz_rotacao_quat,
)

# --------------------------------------------------------------------------- #
# Tipos de álgebra
# --------------------------------------------------------------------------- #
#: Alias histórico; ``Mat3`` é reexportado de ``rig_medidas`` (mesma definição).
Vec3 = tuple[float, float, float]

# --------------------------------------------------------------------------- #
# Constantes nomeadas de limiar e eixos
# --------------------------------------------------------------------------- #

#: Acima deste ângulo (graus) entre o vetor e o eixo dominante, consideramos a
#: direção ainda "legível" como daquele eixo; serve só de referência semântica.
LIMIAR_DOMINANCIA_GRAUS = 45.0

#: Faixas de abertura da porta (graus de giro em H/heading = y).
PORTA_FECHADA_MAX = 5.0
PORTA_ENTREABERTA_MAX = 30.0
PORTA_ABERTA_MAX = 80.0

#: Punho: a partir deste ângulo (graus) de dobra dos dedos, consideramos fechado.
PUNHO_FECHADO_MIN_GRAUS = 20.0

#: Corpo: tolerância (graus) para considerar o tronco "ereto".
CORPO_ERETO_MAX_GRAUS = 8.0

#: Cabeça: tolerância (graus) para considerar olhar/inclinação "ao centro".
CABECA_CENTRO_MAX_GRAUS = 8.0

#: Cotovelo/joelho: a partir deste ângulo (graus) entre o segmento de cima e o
#: de baixo, consideramos a articulação "dobrada" (senão "estendida").
ARTICULACAO_DOBRADA_MIN_GRAUS = 20.0

#: Membro (braço/perna): tolerância (graus) para considerar o eixo longo ainda
#: "legível" como daquele eixo do mundo ao classificar a direção do membro.
MEMBRO_CENTRO_MAX_GRAUS = 30.0

#: Abertura lateral (graus de afastamento do tronco no eixo X): abaixo disto o
#: braço está praticamente COLADO ao corpo; acima, ABERTO ("boneco de posto").
#: Z=28 (repouso atual) dá ~28° — ainda um pouco aberto; Z=90 (T-pose) dá ~90°.
BRACO_ABERTURA_LATERAL_MIN_GRAUS = 20.0
BRACO_ABERTURA_LATERAL_MAX_GRAUS = 55.0

#: Abertura frontal (graus de avanço do braço no eixo Z): a partir disto o
#: braço é considerado projetado À FRENTE (ou ATRÁS, se negativo).
BRACO_ABERTURA_FRONTAL_MIN_GRAUS = 20.0

#: Posição da mão: fração da meia-largura do modelo (``bounds``) usada como
#: limiar de afastamento lateral da ponta da mão em relação à raiz do corpo.
#: Abaixo -> MAO_JUNTO_AO_CORPO; acima -> MAO_AFASTADA.
MAO_AFASTAMENTO_LATERAL_FRAC = 0.4

#: Posição da mão: fração da meia-largura usada como limiar de avanço frontal
#: (eixo Z) da ponta da mão; acima disto a mão é reportada como MAO_A_FRENTE.
MAO_AVANCO_FRONTAL_FRAC = 0.35

#: Os seis eixos do mundo glTF, rotulados com a flag de direção correspondente.
#: (vetor_unitario, rotulo). Y é cima.
EIXOS_DO_MUNDO: tuple[tuple[Vec3, str], ...] = (
    ((1.0, 0.0, 0.0), "DIREITA"),
    ((-1.0, 0.0, 0.0), "ESQUERDA"),
    ((0.0, 1.0, 0.0), "CIMA"),
    ((0.0, -1.0, 0.0), "BAIXO"),
    ((0.0, 0.0, 1.0), "FRENTE"),
    ((0.0, 0.0, -1.0), "TRAS"),
)

#: Mapa de rótulo de eixo -> flag de palma (a palma usa vocabulário próprio).
_FLAG_PALMA = {
    "CIMA": "PALMA_PARA_CIMA",
    "BAIXO": "PALMA_PARA_BAIXO",
    "FRENTE": "PALMA_PARA_FRENTE",
    "TRAS": "PALMA_PARA_TRAS",
    "DIREITA": "PALMA_PARA_FORA",
    "ESQUERDA": "PALMA_PARA_DENTRO",
}

# A álgebra pura (``_identidade3``, ``_mul3``, ``_aplicar3``, ``_normalizar``,
# ``matriz_hpr``, ``matriz_hpr_de_rotacao``, ``matriz_rotacao_quat``) é
# importada de ``rig_medidas`` e reexportada acima: a definição é idêntica, só
# deixou de ser duplicada aqui.


# --------------------------------------------------------------------------- #
# Vetores de referência por parte (editável e documentado)
# --------------------------------------------------------------------------- #
#: Para cada parte do núcleo, os vetores de referência de REPOUSO no espaço
#: local do nó, antes de qualquer rotação. São girados pela rotação acumulada
#: (repouso do nó * HPR animado * cadeia do pai) para dizer para onde apontam.
#:
#: Eixos locais assumidos = eixos do mundo glTF em repouso (os nós do rig estão
#: praticamente em identidade, ver hierarquia lida de mario.gltf), com Y=cima,
#: X=direita, Z=frente.
VETORES_REFERENCIA: dict[str, dict[str, Vec3]] = {
  # MÃO DIREITA. A pista de rig.pose_flourish('wave') diz que a normal da palma
  # está "flipada" em torno do eixo longo do antebraço (X): em repouso a palma
  # aponta para DENTRO/baixo e só vira para FORA após roll de 180° em X.
  # Modelamos a normal de repouso como -X (para dentro, em direção ao corpo);
  # após roll 180° em X ela permanece ~ -X no plano YZ... por isso usamos a
  # componente dominante -Y/baixo (palma caída) como repouso, que ao rolar 180°
  # em X vira +Y (palma para cima) — coerente com o teste sintético.
  "hand": {
    "normal_palma": (0.0, -1.0, 0.0),   # repouso: palma para BAIXO  # A VALIDAR
    "dorso": (0.0, 1.0, 0.0),           # dorso oposto à palma (para cima)  # A VALIDAR
    "direcao_dedos": (0.0, -1.0, 0.0),  # dedos apontam para baixo em repouso (braço caído)
  },
  # MÃO ESQUERDA. Espelhada no eixo X em relação à direita.
  "hand2": {
    "normal_palma": (0.0, -1.0, 0.0),   # A VALIDAR
    "dorso": (0.0, 1.0, 0.0),           # A VALIDAR
    "direcao_dedos": (0.0, -1.0, 0.0),
  },
  # CABEÇA. "Olhar" = para onde o rosto aponta; em repouso, para a frente (+Z).
  # "Topo" = coroa da cabeça, para cima (+Y).
  "head": {
    "olhar": (0.0, 0.0, 1.0),   # rosto para a FRENTE em repouso
    "topo": (0.0, 1.0, 0.0),    # coroa para CIMA
  },
  # CORPO/tronco. "frente" = peito (+Z), "cima" = tronco ereto (+Y).
  "body": {
    "frente": (0.0, 0.0, 1.0),
    "cima": (0.0, 1.0, 0.0),
  },
  # PORTA (portinha do baú). Gira na dobradiça em H (y). O eixo de giro é Y;
  # medimos o ângulo de abertura diretamente de pose['door'].y (ver flag_porta).
  # A normal de repouso aponta para a frente (+Z) com a porta fechada.
  "door": {
    "normal": (0.0, 0.0, 1.0),   # A VALIDAR (sentido de abertura depende da dobradiça)
    "eixo_giro": (0.0, 1.0, 0.0),
  },
  # BRAÇOS, ANTEBRAÇOS, OMBROS, PERNAS, PÉS: todos compartilham a mesma ideia de
  # "eixo longo do segmento". Em repouso os membros pendem para BAIXO (-Y), com
  # os dedos/mãos/pés na ponta inferior. Rotações do rig giram esse eixo longo e
  # dizem se o membro está erguido (+Y), baixado (-Y), lateral (±X) ou à
  # frente/atrás (±Z). O ombro usa o mesmo eixo do braço que ele carrega.
  "eixo_longo_membro": {
    "longo": (0.0, -1.0, 0.0),   # repouso: segmento apontando para BAIXO
  },
}

#: Eixo LONGO de repouso por grupo. Os BRAÇOS (e ombros) têm o eixo longo em +X
#: no renderer (direito) / -X (esquerdo, espelho) — medido em frames reais (ver
#: ``arm_ik``), NÃO em -Y como o modelo antigo supunha. Pernas/pés mantêm -Y.
#: Grupos fora deste mapa caem no padrão -Y.
_EIXO_LONGO_POR_GRUPO: dict[str, Vec3] = {
  "right-arm": (1.0, 0.0, 0.0),
  "ant-arm": (1.0, 0.0, 0.0),
  "shoulder": (1.0, 0.0, 0.0),
  "left-arm": (-1.0, 0.0, 0.0),
  "ant-arm2": (-1.0, 0.0, 0.0),
  "shoulder2": (-1.0, 0.0, 0.0),
}


def _eixo_longo_de(grupo: str) -> Vec3:
  """Eixo longo de repouso do grupo (+X/-X para braços; -Y para o resto)."""
  return _EIXO_LONGO_POR_GRUPO.get(
    grupo, VETORES_REFERENCIA["eixo_longo_membro"]["longo"]
  )


#: Grupos de membro cujo "eixo longo" é classificado com ``VETORES_REFERENCIA
#: ['eixo_longo_membro']`` e cujo repouso pende para -Y. Documentado por parte.
GRUPOS_MEMBRO: tuple[str, ...] = (
  "right-arm", "left-arm",      # braços (parte superior)
  "ant-arm", "ant-arm2",        # antebraços
  "shoulder", "shoulder2",      # ombros (acompanham o braço)
  "legs",                       # pernas/quadril (único nó de perna no rig)
  "left-feet", "right-feet",    # pés
)

#: Pares (segmento_de_cima, segmento_de_baixo) para medir flexão de articulação:
#: o ângulo entre os eixos longos acumulados diz COTOVELO/JOELHO dobrado ou não.
PARES_ARTICULACAO: dict[str, tuple[str, str]] = {
  "cotovelo_direito": ("right-arm", "ant-arm"),
  "cotovelo_esquerdo": ("left-arm", "ant-arm2"),
}

# --------------------------------------------------------------------------- #
# Classificação direcional
# --------------------------------------------------------------------------- #
def _angulo_entre(a: Vec3, b: Vec3) -> float:
  """Ângulo (graus) entre dois vetores; assume não-nulos (normaliza por garantia)."""
  ua, ub = _normalizar(a), _normalizar(b)
  produto = max(-1.0, min(1.0, ua[0] * ub[0] + ua[1] * ub[1] + ua[2] * ub[2]))
  from math import acos

  return degrees(acos(produto))


def classificar_direcao(
  vetor: Vec3,
  eixos: tuple[tuple[Vec3, str], ...] = EIXOS_DO_MUNDO,
) -> tuple[str, float]:
  """Flag do eixo do mundo dominante + ângulo (graus) contra esse eixo.

  Mede o ângulo de ``vetor`` contra cada eixo e devolve o rótulo do mais
  próximo (menor ângulo) junto do valor contínuo em graus.
  """
  melhor_rotulo = eixos[0][1]
  melhor_angulo = 180.0

  for eixo, rotulo in eixos:
    ang = _angulo_entre(vetor, eixo)

    if ang < melhor_angulo:
      melhor_angulo = ang
      melhor_rotulo = rotulo

  return melhor_rotulo, melhor_angulo


# --------------------------------------------------------------------------- #
# Estado acumulado da hierarquia
# --------------------------------------------------------------------------- #
def _indice_por_nome(model: Model) -> dict[str, int]:
  """Primeiro índice de nó por nome (os grupos do rig são únicos no modelo)."""
  mapa: dict[str, int] = {}

  for node in model.nodes:
    if node.name and node.name not in mapa:
      mapa[node.name] = node.index

  return mapa


def estado_acumulado(pose: dict[str, Rotation3], model: Model) -> dict[str, Mat3]:
  """Rotação de mundo 3x3 acumulada por grupo do rig (repouso + HPR animado).

  Para cada grupo de ``rig.ALL_GROUPS`` presente no modelo, compõe a rotação de
  repouso do nó (quaternião do glTF) com a rotação HPR animada derivada de
  ``pose[grupo]`` (H=y, P=x, R=z), acumulando pela cadeia pai->filho.
  """
  por_nome = _indice_por_nome(model)
  por_indice = {n.index: n for n in model.nodes}
  cache: dict[int, Mat3] = {}

  def acumulada_do_no(indice: int) -> Mat3:
    if indice in cache:
      return cache[indice]

    node = por_indice[indice]
    local_repouso = matriz_rotacao_quat(node.rotation)
    animada = _identidade3()

    if node.name in pose:
      animada = matriz_hpr_de_rotacao(pose[node.name])

    # repouso aplicado antes da animação (o renderer soma ao HPR de repouso):
    # mundo_local = repouso * animada
    mundo_local = _mul3(local_repouso, animada)

    if node.parent is not None and node.parent in por_indice:
      resultado = _mul3(acumulada_do_no(node.parent), mundo_local)
    else:
      resultado = mundo_local

    cache[indice] = resultado

    return resultado

  acumulado: dict[str, Mat3] = {}

  for grupo in ALL_GROUPS:
    if grupo in por_nome:
      acumulado[grupo] = acumulada_do_no(por_nome[grupo])

  return acumulado


def posicao_acumulada(pose: dict[str, Rotation3], model: Model) -> dict[str, Vec3]:
  """Posição 3D de mundo da ORIGEM de cada grupo do rig, propagando TRS.

  Para cada grupo de ``rig.ALL_GROUPS`` presente no modelo, acumula do nó raiz
  até o grupo a translação local de cada nó (``node.translation``) rotacionada
  pela rotação de mundo acumulada do pai — ou seja, propaga translações E
  rotações (repouso + HPR animado) pela cadeia pai->filho. É assim que se chega
  à posição real da ponta da mão (``hand``/``hand2``) via a cadeia
  ``right-arm -> ant-arm -> hand`` lida do glTF (ver ``tools/inspect_model.py``).
  """
  por_nome = _indice_por_nome(model)
  por_indice = {n.index: n for n in model.nodes}
  cache: dict[int, Vec3] = {}

  def posicao_do_no(indice: int) -> Vec3:
    if indice in cache:
      return cache[indice]

    node = por_indice[indice]
    # Translação local posicionada pela rotação de mundo do PAI (a origem do nó
    # está no espaço do pai, antes de aplicar a rotação do próprio nó).
    if node.parent is not None and node.parent in por_indice:
      rot_pai = estado_acumulado_pai(node.parent)
      base = posicao_do_no(node.parent)
    else:
      rot_pai = _identidade3()
      base = (0.0, 0.0, 0.0)

    deslocado = _aplicar3(rot_pai, node.translation)
    resultado = (base[0] + deslocado[0], base[1] + deslocado[1], base[2] + deslocado[2])
    cache[indice] = resultado

    return resultado

  acumulado_rot = estado_acumulado(pose, model)
  rot_por_indice: dict[int, Mat3] = {}

  for grupo, matriz in acumulado_rot.items():
    if grupo in por_nome:
      rot_por_indice[por_nome[grupo]] = matriz

  def estado_acumulado_pai(indice_pai: int) -> Mat3:
    # Rotação de mundo acumulada do pai: usa o acumulado por grupo quando o pai
    # é um grupo do rig; senão identidade (nós intermediários sem pose).
    return rot_por_indice.get(indice_pai, _identidade3())

  posicoes: dict[str, Vec3] = {}

  for grupo in ALL_GROUPS:
    if grupo in por_nome:
      posicoes[grupo] = posicao_do_no(por_nome[grupo])

  return posicoes


# --------------------------------------------------------------------------- #
# Flags do núcleo
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class EstadoMao:
  """Como uma mão está orientada e ONDE a ponta dela termina no espaço."""

  palma_flag: str
  palma_graus: float
  dorso_flag: str
  dorso_graus: float
  dedos_flag: str
  dedos_graus: float
  punho_flag: str      # PUNHO_ABERTO | PUNHO_FECHADO
  punho_graus: float
  #: Offset 3D (x, y, z) da ponta da mão relativo à raiz do corpo (unidades do
  #: modelo). x+ = para a direita, y+ = para cima, z+ = para a frente.
  posicao_offset: Vec3
  #: Flag legível do afastamento da mão: MAO_JUNTO_AO_CORPO | MAO_AFASTADA
  #: (lateral) combinada com MAO_A_FRENTE quando projetada para a frente.
  posicao_flag: str


@dataclass(frozen=True, slots=True)
class EstadoCabeca:
  """Para onde a cabeça olha e como está inclinada."""

  olhar_flag: str      # OLHAR_ESQUERDA/DIREITA/CIMA/BAIXO/FRENTE/TRAS
  olhar_graus: float
  topo_flag: str
  topo_graus: float
  inclinacao_graus: float   # pitch (P=x) em graus; + para baixo
  tilt_graus: float         # roll (R=z) em graus


@dataclass(frozen=True, slots=True)
class EstadoCorpo:
  """Inclinação, torção e rolagem do tronco."""

  inclinacao_flag: str      # A_FRENTE | ATRAS | ERETO
  inclinacao_graus: float   # pitch
  torcao_graus: float       # heading (H=y)
  rolagem_flag: str         # TOMBADO_ESQUERDA | TOMBADO_DIREITA | APRUMADO
  rolagem_graus: float      # roll (R=z)
  orientacao_flag: str      # DE_PE | DE_CABECA_PARA_BAIXO | DEITADO (via vetor "cima")


@dataclass(frozen=True, slots=True)
class EstadoPorta:
  """Quanto a portinha está aberta."""

  flag: str   # PORTA_FECHADA | PORTA_ENTREABERTA | PORTA_ABERTA | PORTA_ESCANCARADA
  graus: float


def _graus(rot: Rotation3) -> tuple[float, float, float]:
  """(pitch, heading, roll) em graus a partir de um Rotation3 em radianos."""
  return (degrees(rot.x), degrees(rot.y), degrees(rot.z))


def _flag_posicao_mao(offset: Vec3, meia_largura: float) -> str:
  """Flag legível da posição da ponta da mão a partir do offset ao corpo.

  Combina o afastamento lateral (eixo X) com o avanço frontal (eixo Z). A base
  é a meia-largura do modelo (``bounds``), para a leitura ser robusta à escala:

  - lateral abaixo de ``MAO_AFASTAMENTO_LATERAL_FRAC`` -> MAO_JUNTO_AO_CORPO;
  - lateral acima -> MAO_AFASTADA;
  - avanço frontal acima de ``MAO_AVANCO_FRONTAL_FRAC`` acrescenta MAO_A_FRENTE.
  """
  limiar_lateral = MAO_AFASTAMENTO_LATERAL_FRAC * meia_largura
  limiar_frontal = MAO_AVANCO_FRONTAL_FRAC * meia_largura

  flag = "MAO_AFASTADA" if abs(offset[0]) >= limiar_lateral else "MAO_JUNTO_AO_CORPO"

  if offset[2] >= limiar_frontal:
    flag = f"{flag}+MAO_A_FRENTE"
  elif offset[2] <= -limiar_frontal:
    flag = f"{flag}+MAO_ATRAS"

  return flag


def flag_mao(
  grupo: str,
  acumulado: dict[str, Mat3],
  pose: dict[str, Rotation3],
  posicoes: dict[str, Vec3],
  model: Model,
) -> EstadoMao:
  """Classifica a orientação de ``hand``/``hand2``, o punho e a POSIÇÃO da mão.

  A posição da ponta da mão vem de ``posicoes`` (propagação de translações +
  rotações pela cadeia ``braço -> antebraço -> mão``), relativa à raiz do corpo
  (``body``). O offset é reportado cru (x, y, z) e também como flag legível.
  """
  ref = VETORES_REFERENCIA[grupo]
  m = acumulado.get(grupo, _identidade3())

  palma = _aplicar3(m, ref["normal_palma"])
  dorso = _aplicar3(m, ref["dorso"])
  dedos = _aplicar3(m, ref["direcao_dedos"])

  rotulo_palma, graus_palma = classificar_direcao(palma)
  palma_flag = _FLAG_PALMA[rotulo_palma]
  dorso_flag, graus_dorso = classificar_direcao(dorso)
  dedos_flag, graus_dedos = classificar_direcao(dedos)

  # Punho: dobra dos dedos. fingers/fingers2 giram em Z (roll) na pose.
  grupo_dedos = "fingers" if grupo == "hand" else "fingers2"
  dobra = 0.0

  if grupo_dedos in pose:
    dobra = abs(degrees(pose[grupo_dedos].z))

  punho_flag = "PUNHO_FECHADO" if dobra >= PUNHO_FECHADO_MIN_GRAUS else "PUNHO_ABERTO"

  # Posição da ponta da mão relativa à raiz do corpo (offset no espaço do
  # modelo). Sem o grupo no modelo, cai para offset nulo (mão na raiz).
  mao_pos = posicoes.get(grupo, (0.0, 0.0, 0.0))
  corpo_pos = posicoes.get("body", (0.0, 0.0, 0.0))
  offset = (
    mao_pos[0] - corpo_pos[0],
    mao_pos[1] - corpo_pos[1],
    mao_pos[2] - corpo_pos[2],
  )
  meia_largura = max(model.bounds.size[0] / 2.0, 1e-6)
  posicao_flag = _flag_posicao_mao(offset, meia_largura)

  return EstadoMao(
    palma_flag=palma_flag,
    palma_graus=graus_palma,
    dorso_flag=f"DORSO_{dorso_flag}",
    dorso_graus=graus_dorso,
    dedos_flag=f"DEDOS_{dedos_flag}",
    dedos_graus=graus_dedos,
    punho_flag=punho_flag,
    punho_graus=dobra,
    posicao_offset=offset,
    posicao_flag=posicao_flag,
  )


def flag_cabeca(acumulado: dict[str, Mat3], pose: dict[str, Rotation3]) -> EstadoCabeca:
  """Classifica olhar, topo e inclinação/tilt da cabeça."""
  ref = VETORES_REFERENCIA["head"]
  m = acumulado.get("head", _identidade3())

  olhar = _normalizar(_aplicar3(m, ref["olhar"]))
  topo = _aplicar3(m, ref["topo"])

  _, graus_olhar = classificar_direcao(olhar)
  topo_flag, graus_topo = classificar_direcao(topo)

  pitch, _, roll = _graus(pose.get("head", Rotation3()))

  # O olhar lê melhor pelo desvio do rosto do que pelo eixo nuclear: mesmo um
  # giro de 30° (ainda mais perto de +Z do que de +X) já é "olhar de lado".
  # Decidimos esquerda/direita/cima/baixo pela maior componente lateral do
  # vetor de olhar; se nenhuma for relevante, é FRENTE (ou TRAS, se virou de costas).
  desvio_x, desvio_y, desvio_z = olhar
  limiar = sin(radians(CABECA_CENTRO_MAX_GRAUS))

  if abs(desvio_x) < limiar and abs(desvio_y) < limiar:
    olhar_flag = "OLHAR_FRENTE" if desvio_z >= 0.0 else "OLHAR_TRAS"
  elif abs(desvio_x) >= abs(desvio_y):
    olhar_flag = "OLHAR_DIREITA" if desvio_x > 0.0 else "OLHAR_ESQUERDA"
  else:
    olhar_flag = "OLHAR_CIMA" if desvio_y > 0.0 else "OLHAR_BAIXO"

  return EstadoCabeca(
    olhar_flag=olhar_flag,
    olhar_graus=graus_olhar,
    topo_flag=f"TOPO_{topo_flag}",
    topo_graus=graus_topo,
    inclinacao_graus=pitch,
    tilt_graus=roll,
  )


def flag_corpo(acumulado: dict[str, Mat3], pose: dict[str, Rotation3]) -> EstadoCorpo:
  """Classifica inclinação (pitch), torção (heading), rolagem (roll) do tronco."""
  ref = VETORES_REFERENCIA["body"]
  m = acumulado.get("body", _identidade3())

  cima = _aplicar3(m, ref["cima"])
  rotulo_cima, _ = classificar_direcao(cima)

  pitch, heading, roll = _graus(pose.get("body", Rotation3()))

  if pitch > CORPO_ERETO_MAX_GRAUS:
    inclinacao_flag = "A_FRENTE"
  elif pitch < -CORPO_ERETO_MAX_GRAUS:
    inclinacao_flag = "ATRAS"
  else:
    inclinacao_flag = "ERETO"

  if roll > CORPO_ERETO_MAX_GRAUS:
    rolagem_flag = "TOMBADO_ESQUERDA"
  elif roll < -CORPO_ERETO_MAX_GRAUS:
    rolagem_flag = "TOMBADO_DIREITA"
  else:
    rolagem_flag = "APRUMADO"

  # Orientação global do tronco pelo vetor "cima" acumulado.
  if rotulo_cima == "CIMA":
    orientacao_flag = "DE_PE"
  elif rotulo_cima == "BAIXO":
    orientacao_flag = "DE_CABECA_PARA_BAIXO"
  else:
    orientacao_flag = "DEITADO"

  return EstadoCorpo(
    inclinacao_flag=inclinacao_flag,
    inclinacao_graus=pitch,
    torcao_graus=heading,
    rolagem_flag=rolagem_flag,
    rolagem_graus=roll,
    orientacao_flag=orientacao_flag,
  )


def flag_porta(pose: dict[str, Rotation3]) -> EstadoPorta:
  """Classifica a abertura da portinha pelo giro em H (y)."""
  _, heading, _ = _graus(pose.get("door", Rotation3()))
  abertura = abs(heading)

  if abertura < PORTA_FECHADA_MAX:
    flag = "PORTA_FECHADA"
  elif abertura < PORTA_ENTREABERTA_MAX:
    flag = "PORTA_ENTREABERTA"
  elif abertura < PORTA_ABERTA_MAX:
    flag = "PORTA_ABERTA"
  else:
    flag = "PORTA_ESCANCARADA"

  return EstadoPorta(flag=flag, graus=abertura)


# --------------------------------------------------------------------------- #
# Flags de membro (braços, antebraços, ombros, pernas, pés) e articulações
# --------------------------------------------------------------------------- #
#: Rótulo do eixo do mundo -> flag de direção de um membro. O eixo longo em
#: repouso aponta para BAIXO; conforme ele gira, o membro fica ERGUIDO (+Y),
#: BAIXADO (-Y), LATERAL (±X) ou À FRENTE/ATRÁS (±Z).
_FLAG_MEMBRO = {
  "CIMA": "ERGUIDO",
  "BAIXO": "BAIXADO",
  "DIREITA": "LATERAL",
  "ESQUERDA": "LATERAL",
  "FRENTE": "A_FRENTE",
  "TRAS": "ATRAS",
}


@dataclass(frozen=True, slots=True)
class EstadoMembro:
  """Direção do eixo longo de um braço/antebraço/ombro/perna/pé."""

  grupo: str
  direcao_flag: str   # ERGUIDO | BAIXADO | LATERAL | A_FRENTE | ATRAS
  direcao_graus: float   # ângulo (graus) contra o eixo do mundo dominante
  eixo_flag: str      # rótulo cru do eixo do mundo (CIMA/BAIXO/DIREITA/...)
  elevacao_graus: float   # ângulo (graus) do eixo longo acima da horizontal
  #: Abertura lateral: afastamento do eixo longo do plano sagital (eixo X), em
  #: graus. Separado da elevação — um braço BAIXADO ainda pode estar bem aberto.
  abertura_lateral_graus: float
  #: Abertura frontal: avanço do eixo longo no eixo Z, em graus (+ = à frente).
  abertura_frontal_graus: float
  #: Flag legível da abertura lateral: COLADO | SEMIABERTO | ABERTO.
  abertura_flag: str


@dataclass(frozen=True, slots=True)
class EstadoArticulacao:
  """Flexão de uma articulação (cotovelo/joelho) pelo ângulo entre segmentos."""

  nome: str
  flag: str   # DOBRADO | ESTENDIDO
  graus: float   # ângulo (graus) entre o eixo longo de cima e o de baixo


def _flag_abertura(abertura_lateral_graus: float) -> str:
  """Classifica a abertura lateral de um braço em COLADO/SEMIABERTO/ABERTO."""
  abertura = abs(abertura_lateral_graus)

  if abertura < BRACO_ABERTURA_LATERAL_MIN_GRAUS:
    return "COLADO"

  if abertura < BRACO_ABERTURA_LATERAL_MAX_GRAUS:
    return "SEMIABERTO"

  return "ABERTO"


def direcao_membro(grupo: str, acumulado: dict[str, Mat3]) -> EstadoMembro:
  """Classifica a direção, a elevação e a ABERTURA do eixo longo de um membro.

  Além do eixo dominante (baixo/lateral/cima), separa a **abertura lateral**
  (afastamento do tronco no eixo X) e a **abertura frontal** (avanço no eixo Z)
  da elevação (componente Y). Assim um braço pode ser BAIXADO e, ainda assim,
  bem ABERTO para fora — o que o eixo dominante sozinho não revela.
  """
  longo_repouso = _eixo_longo_de(grupo)
  m = acumulado.get(grupo, _identidade3())

  longo = _normalizar(_aplicar3(m, longo_repouso))
  rotulo, graus = classificar_direcao(longo)

  # Elevação: quanto o eixo longo está acima (+) ou abaixo (-) da horizontal.
  # Componente Y do vetor normalizado dá o seno do ângulo de elevação.
  elevacao = degrees(asin(max(-1.0, min(1.0, longo[1]))))

  # Abertura lateral/frontal: os senos das componentes X e Z dão, em graus, o
  # afastamento do eixo longo em relação ao plano sagital (X) e o avanço (Z).
  abertura_lateral = degrees(asin(max(-1.0, min(1.0, longo[0]))))
  abertura_frontal = degrees(asin(max(-1.0, min(1.0, longo[2]))))

  return EstadoMembro(
    grupo=grupo,
    direcao_flag=_FLAG_MEMBRO[rotulo],
    direcao_graus=graus,
    eixo_flag=rotulo,
    elevacao_graus=elevacao,
    abertura_lateral_graus=abertura_lateral,
    abertura_frontal_graus=abertura_frontal,
    abertura_flag=_flag_abertura(abertura_lateral),
  )


def flag_articulacao(
  nome: str,
  acumulado: dict[str, Mat3],
) -> EstadoArticulacao:
  """Mede a flexão de uma articulação pelo ângulo entre os eixos longos.

  Usa ``PARES_ARTICULACAO[nome]`` = (segmento_de_cima, segmento_de_baixo). Em
  repouso os dois eixos longos coincidem (ângulo ~0 = ESTENDIDO); ao dobrar, o
  ângulo cresce.
  """
  cima_grupo, baixo_grupo = PARES_ARTICULACAO[nome]

  m_cima = acumulado.get(cima_grupo, _identidade3())
  m_baixo = acumulado.get(baixo_grupo, _identidade3())

  # Cada segmento usa seu próprio eixo longo de repouso (braços em ±X).
  eixo_cima = _aplicar3(m_cima, _eixo_longo_de(cima_grupo))
  eixo_baixo = _aplicar3(m_baixo, _eixo_longo_de(baixo_grupo))
  graus = _angulo_entre(eixo_cima, eixo_baixo)

  flag = "DOBRADO" if graus >= ARTICULACAO_DOBRADA_MIN_GRAUS else "ESTENDIDO"

  return EstadoArticulacao(nome=nome, flag=flag, graus=graus)


# --------------------------------------------------------------------------- #
# Orientação GLOBAL do personagem
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class EstadoGlobal:
  """Orientação geral do personagem derivada do vetor 'cima' do corpo."""

  flag: str   # EM_PE | DE_CABECA_PRA_BAIXO | DEITADO | INCLINADO
  desvio_graus: float   # ângulo (graus) entre o 'cima' do corpo e o +Y do mundo


def flag_global(acumulado: dict[str, Mat3]) -> EstadoGlobal:
  """Classifica a orientação geral pelo vetor 'cima' acumulado do corpo.

  Compara o eixo 'cima' do tronco contra +Y do mundo e decide pelo EIXO do
  mundo mais próximo (mesma lógica de ``classificar_direcao`` usada em
  ``EstadoCorpo.orientacao_flag``), para manter a leitura consistente:
  - 'cima' ainda aponta ~CIMA e dentro da tolerância de ereto -> EM_PE;
  - 'cima' aponta para BAIXO (invertido, ex.: corpo rolado ~155°) -> DE_CABECA_PRA_BAIXO;
  - 'cima' caiu para a horizontal (DIREITA/ESQUERDA/FRENTE/TRAS) -> DEITADO;
  - caso o desvio seja pequeno mas acima da tolerância de ereto -> INCLINADO.
  """
  cima_repouso = VETORES_REFERENCIA["body"]["cima"]
  m = acumulado.get("body", _identidade3())

  cima = _aplicar3(m, cima_repouso)
  desvio = _angulo_entre(cima, (0.0, 1.0, 0.0))
  rotulo, _ = classificar_direcao(cima)

  if rotulo == "CIMA":
    flag = "EM_PE" if desvio <= CORPO_ERETO_MAX_GRAUS else "INCLINADO"
  elif rotulo == "BAIXO":
    flag = "DE_CABECA_PRA_BAIXO"
  else:
    flag = "DEITADO"

  return EstadoGlobal(flag=flag, desvio_graus=desvio)


# --------------------------------------------------------------------------- #
# Agregador
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class EstadoRig:
  """Leitura completa do rig: mãos, cabeça, corpo, porta, membros e GLOBAL."""

  mao_direita: EstadoMao
  mao_esquerda: EstadoMao
  cabeca: EstadoCabeca
  corpo: EstadoCorpo
  porta: EstadoPorta
  #: Direção do eixo longo por grupo de membro (ver ``GRUPOS_MEMBRO``).
  membros: dict[str, EstadoMembro]
  #: Flexão por articulação (ver ``PARES_ARTICULACAO``).
  articulacoes: dict[str, EstadoArticulacao]
  #: Orientação geral do personagem.
  orientacao_global: EstadoGlobal


#: Grupos do braço cuja geometria é medida pela FK do RENDERER (``arm_ik``) em
#: vez do modelo Y-up deste módulo. O modelo Y-up supõe o eixo longo do membro
#: em -Y e a elevação no roll; medindo frames reais, o renderer tem o eixo longo
#: em +X e a elevação no heading (ver ``arm_ik``). Para os braços baterem com o
#: que é renderizado, sobrescrevemos a rotação de mundo e a posição da mão desses
#: grupos com a FK do renderer (os demais grupos seguem o modelo deste módulo).
_GRUPOS_BRACO_RENDER = {
  "right": ("right-arm", "ant-arm", "hand"),
  "left": ("left-arm", "ant-arm2", "hand2"),
}


def _sobrescrever_bracos_render(
  pose: dict[str, Rotation3],
  model: Model,
  acumulado: dict[str, Mat3],
  posicoes: dict[str, Vec3],
) -> None:
  """Substitui, in-place, a rotação/posição dos grupos de braço pela FK real.

  Usa ``arm_ik.medir_braco_render`` (validado contra o renderer) para as
  rotações de mundo de braço/antebraço/mão e para a POSIÇÃO da ponta da mão
  (relativa ao ombro, somada à origem do ombro já medida neste módulo). Mantém a
  origem do ombro deste módulo (translação pura, independente da rotação do
  braço). Tudo nos eixos declarados do rig (+X dir, +Y cima, +Z frente).
  """
  from sejoga.animacao import arm_ik

  for lado, (braco, antebraco, mao) in _GRUPOS_BRACO_RENDER.items():
    if braco not in acumulado:
      continue

    medido = arm_ik.medir_braco_render(model, lado, pose)
    acumulado[braco] = medido[braco]  # type: ignore[assignment]
    acumulado[antebraco] = medido[antebraco]  # type: ignore[assignment]
    acumulado[mao] = medido[mao]  # type: ignore[assignment]

    ombro = posicoes.get(braco)
    ponta_rel = medido["ponta_mao_rel_ombro"]

    if ombro is not None:
      posicoes[mao] = (
        ombro[0] + ponta_rel[0],  # type: ignore[index]
        ombro[1] + ponta_rel[1],  # type: ignore[index]
        ombro[2] + ponta_rel[2],  # type: ignore[index]
      )


def estado_rig(pose: dict[str, Rotation3], model: Model) -> EstadoRig:
  """Agrega as flags de TODO o rig para uma pose completa.

  ``pose`` é o mesmo ``dict`` que o renderizador consome (``grupo -> Rotation3``
  em radianos). ``model`` é o ``Model`` lido do glTF (``model.load_model``).

  Os grupos de braço têm a rotação/posição corrigidas pela FK do renderer
  (``arm_ik``): o modelo Y-up deste módulo não bate com o renderer para braços.
  """
  acumulado = estado_acumulado(pose, model)
  posicoes = posicao_acumulada(pose, model)
  _sobrescrever_bracos_render(pose, model, acumulado, posicoes)

  membros = {
    grupo: direcao_membro(grupo, acumulado)
    for grupo in GRUPOS_MEMBRO
    if grupo in acumulado
  }
  articulacoes = {
    nome: flag_articulacao(nome, acumulado)
    for nome in PARES_ARTICULACAO
  }

  return EstadoRig(
    mao_direita=flag_mao("hand", acumulado, pose, posicoes, model),
    mao_esquerda=flag_mao("hand2", acumulado, pose, posicoes, model),
    cabeca=flag_cabeca(acumulado, pose),
    corpo=flag_corpo(acumulado, pose),
    porta=flag_porta(pose),
    membros=membros,
    articulacoes=articulacoes,
    orientacao_global=flag_global(acumulado),
  )


# --------------------------------------------------------------------------- #
# ESBOÇO (não implementado): overlay on-screen consumindo estado_rig
# --------------------------------------------------------------------------- #
# Um overlay de depuração que mostra as flags EM CIMA do mascote viveria na
# camada de engine (window.py/renderer.py) e NÃO aqui — este módulo é puro de
# propósito. O desenho fica do lado de lá; o texto vem daqui. Esboço do laço:
#
#   # dentro do renderer, a cada frame, com a MESMA pose já aplicada aos nós:
#   from sejoga import rig_debug
#   estado = rig_debug.estado_rig(rig.pose(), self._model)
#   linhas = [
#     f"palma D: {estado.mao_direita.palma_flag}",
#     f"olhar:   {estado.cabeca.olhar_flag}",
#     f"braço D: {estado.membros['right-arm'].direcao_flag}",
#     f"cotovelo D: {estado.articulacoes['cotovelo_direito'].flag}",
#     f"global:  {estado.orientacao_global.flag}",
#   ]
#   # self._texto_overlay seria um OnscreenText do Panda (ou um QLabel do Qt):
#   self._texto_overlay.setText("\n".join(linhas))
#
# Só a construção das 'linhas' depende deste módulo; o widget/nó de texto e o
# posicionamento ficam na camada de engine, preservando a fronteira.
