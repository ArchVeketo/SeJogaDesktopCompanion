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

from dataclasses import dataclass, field
from math import cos, degrees, radians, sin, sqrt

from .model import Model, Quat
from .rig import ALL_GROUPS, Rotation3

# --------------------------------------------------------------------------- #
# Tipos de álgebra
# --------------------------------------------------------------------------- #
Vec3 = tuple[float, float, float]
Mat3 = tuple[
    float, float, float,
    float, float, float,
    float, float, float,
]  # linha-maior: m[0..2]=linha 0, m[3..5]=linha 1, m[6..8]=linha 2

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

# --------------------------------------------------------------------------- #
# Álgebra pura (matrizes 3x3 em linha-maior)
# --------------------------------------------------------------------------- #
def _identidade3() -> Mat3:
  return (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def _mul3(a: Mat3, b: Mat3) -> Mat3:
  """Produto de duas 3x3 em linha-maior (``a`` aplicada depois de ``b``)."""
  out = [0.0] * 9

  for linha in range(3):
    for col in range(3):
      out[linha * 3 + col] = sum(a[linha * 3 + k] * b[k * 3 + col] for k in range(3))

  return tuple(out)  # type: ignore[return-value]


def _aplicar3(m: Mat3, v: Vec3) -> Vec3:
  """Aplica a 3x3 ``m`` ao vetor coluna ``v``."""
  x, y, z = v

  return (
    m[0] * x + m[1] * y + m[2] * z,
    m[3] * x + m[4] * y + m[5] * z,
    m[6] * x + m[7] * y + m[8] * z,
  )


def _normalizar(v: Vec3) -> Vec3:
  """Devolve ``v`` normalizado; vetor nulo volta como nulo (fail-safe)."""
  comprimento = sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])

  if comprimento == 0.0:
    return (0.0, 0.0, 0.0)

  return (v[0] / comprimento, v[1] / comprimento, v[2] / comprimento)


def _rot_x(ang: float) -> Mat3:
  """Rotação em torno de +X (radianos). Pitch do renderer (P)."""
  c, s = cos(ang), sin(ang)

  return (
    1.0, 0.0, 0.0,
    0.0, c, -s,
    0.0, s, c,
  )


def _rot_y(ang: float) -> Mat3:
  """Rotação em torno de +Y (radianos). Heading do renderer (H)."""
  c, s = cos(ang), sin(ang)

  return (
    c, 0.0, s,
    0.0, 1.0, 0.0,
    -s, 0.0, c,
  )


def _rot_z(ang: float) -> Mat3:
  """Rotação em torno de +Z (radianos). Roll do renderer (R)."""
  c, s = cos(ang), sin(ang)

  return (
    c, -s, 0.0,
    s, c, 0.0,
    0.0, 0.0, 1.0,
  )


def matriz_hpr(h: float, p: float, r: float) -> Mat3:
  """Reimplementa a composição HPR do Panda3D em álgebra pura (radianos).

  O Panda aplica, de forma intrínseca, roll (R) primeiro, depois pitch (P),
  depois heading (H). Como a última rotação aplicada ao vetor é a que fica mais
  à direita no produto de matrizes, isso vira ``H * P * R`` (R multiplica o
  vetor primeiro).

  Mapa vindo de ``renderer.apply_rig_pose``: ``H=y``, ``P=x``, ``R=z``.
  """
  return _mul3(_rot_y(h), _mul3(_rot_x(p), _rot_z(r)))


def matriz_hpr_de_rotacao(rot: Rotation3) -> Mat3:
  """HPR a partir de um ``Rotation3`` animado (radianos): H=y, P=x, R=z."""
  return matriz_hpr(rot.y, rot.x, rot.z)


def matriz_rotacao_quat(quat: Quat) -> Mat3:
  """Converte o quaternião de repouso de um ``Node`` glTF em 3x3 (linha-maior).

  Mesma fórmula do ``model._trs``, só a parte rotacional.
  """
  x, y, z, w = quat
  xx, yy, zz = x * x, y * y, z * z
  xy, xz, yz = x * y, x * z, y * z
  wx, wy, wz = w * x, w * y, w * z

  return (
    1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy),
    2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx),
    2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy),
  )


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


# --------------------------------------------------------------------------- #
# Flags do núcleo
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class EstadoMao:
  """Como uma mão está orientada."""

  palma_flag: str
  palma_graus: float
  dorso_flag: str
  dorso_graus: float
  dedos_flag: str
  dedos_graus: float
  punho_flag: str      # PUNHO_ABERTO | PUNHO_FECHADO
  punho_graus: float


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


def flag_mao(
  grupo: str,
  acumulado: dict[str, Mat3],
  pose: dict[str, Rotation3],
) -> EstadoMao:
  """Classifica a orientação de ``hand``/``hand2`` e o estado do punho."""
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

  return EstadoMao(
    palma_flag=palma_flag,
    palma_graus=graus_palma,
    dorso_flag=f"DORSO_{dorso_flag}",
    dorso_graus=graus_dorso,
    dedos_flag=f"DEDOS_{dedos_flag}",
    dedos_graus=graus_dedos,
    punho_flag=punho_flag,
    punho_graus=dobra,
  )


def flag_cabeca(acumulado: dict[str, Mat3], pose: dict[str, Rotation3]) -> EstadoCabeca:
  """Classifica olhar, topo e inclinação/tilt da cabeça."""
  ref = VETORES_REFERENCIA["head"]
  m = acumulado.get("head", _identidade3())

  olhar = _normalizar(_aplicar3(m, ref["olhar"]))
  topo = _aplicar3(m, ref["topo"])

  rotulo_olhar, graus_olhar = classificar_direcao(olhar)
  topo_flag, graus_topo = classificar_direcao(topo)

  pitch, heading, roll = _graus(pose.get("head", Rotation3()))

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


@dataclass(frozen=True, slots=True)
class EstadoArticulacao:
  """Flexão de uma articulação (cotovelo/joelho) pelo ângulo entre segmentos."""

  nome: str
  flag: str   # DOBRADO | ESTENDIDO
  graus: float   # ângulo (graus) entre o eixo longo de cima e o de baixo


def direcao_membro(grupo: str, acumulado: dict[str, Mat3]) -> EstadoMembro:
  """Classifica a direção do eixo longo acumulado de um membro."""
  longo_repouso = VETORES_REFERENCIA["eixo_longo_membro"]["longo"]
  m = acumulado.get(grupo, _identidade3())

  longo = _normalizar(_aplicar3(m, longo_repouso))
  rotulo, graus = classificar_direcao(longo)

  # Elevação: quanto o eixo longo está acima (+) ou abaixo (-) da horizontal.
  # Componente Y do vetor normalizado dá o seno do ângulo de elevação.
  from math import asin

  elevacao = degrees(asin(max(-1.0, min(1.0, longo[1]))))

  return EstadoMembro(
    grupo=grupo,
    direcao_flag=_FLAG_MEMBRO[rotulo],
    direcao_graus=graus,
    eixo_flag=rotulo,
    elevacao_graus=elevacao,
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
  longo_repouso = VETORES_REFERENCIA["eixo_longo_membro"]["longo"]

  m_cima = acumulado.get(cima_grupo, _identidade3())
  m_baixo = acumulado.get(baixo_grupo, _identidade3())

  eixo_cima = _aplicar3(m_cima, longo_repouso)
  eixo_baixo = _aplicar3(m_baixo, longo_repouso)
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


def estado_rig(pose: dict[str, Rotation3], model: Model) -> EstadoRig:
  """Agrega as flags de TODO o rig para uma pose completa.

  ``pose`` é o mesmo ``dict`` que o renderizador consome (``grupo -> Rotation3``
  em radianos). ``model`` é o ``Model`` lido do glTF (``model.load_model``).
  """
  acumulado = estado_acumulado(pose, model)

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
    mao_direita=flag_mao("hand", acumulado, pose),
    mao_esquerda=flag_mao("hand2", acumulado, pose),
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
