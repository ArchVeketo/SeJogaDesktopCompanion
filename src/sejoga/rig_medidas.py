"""Pipeline de medição por parte do rig (Fase 2 do mapeamento).

Dada uma pose (``grupo -> Rotation3`` em radianos, igual ao que o renderizador
consome) e o ``Model`` lido do glTF, produz um ``EstadoParte`` COMPLETO para
cada ``Parte``: rotação (local/mundo/desvio/torção), direção classificada,
vetores no mundo e posição (origem/ponta/altura/distância ao eixo central).
Segue a seção 5 do documento
``docs/Mapeamento Completo do Corpo do Rig Detecção e Nomenclatura.md``.

FRONTEIRA (igual a ``model.py``/``rig.py``/``rig_debug.py``): este módulo é
Python puro. NÃO importa Panda3D, Qt nem Win32. Só depende de ``math`` e, do
próprio pacote, de ``model``, ``rig``, ``rig_mapa`` e ``rig_limiares``.

Convenção de rotação (fonte: ``renderer.apply_rig_pose`` e ``rig_debug.py``):
de ``Rotation3(x, y, z)`` em radianos o renderizador deriva ``H = y``,
``P = x``, ``R = z``, SOMADO ao HPR de repouso do nó e acumulado pela
hierarquia pai->filho. O Panda compõe ``H * P * R``. Reimplementamos essa mesma
composição em álgebra pura para que as medidas batam com o que é renderizado.

A álgebra 3x3 em linha-maior é DUPLICADA aqui (não importada de ``rig_debug``)
de propósito: a Fase 2 não toca ``rig_debug.py``. Na Fase 3 a fachada passa a
reexportar estes símbolos.

Eixos do mundo glTF: +X=direita, +Y=cima, +Z=frente (Y para cima).
"""

from __future__ import annotations

from math import acos, atan2, cos, degrees, sin, sqrt

from .model import Model, Quat
from .rig import Rotation3
from .rig_limiares import LIMIARES_PADRAO, Limiares, classificar_direcao
from .rig_mapa import (
  AlturaRelativa,
  Direcao,
  EstadoParte,
  Parte,
  ReferenciasCorpo,
  Vetor3,
  lado_de,
  pai_de,
)

# --------------------------------------------------------------------------- #
# Tipos de álgebra
# --------------------------------------------------------------------------- #
Mat3 = tuple[
  float, float, float,
  float, float, float,
  float, float, float,
]  # linha-maior: m[0..2]=linha 0, m[3..5]=linha 1, m[6..8]=linha 2


# --------------------------------------------------------------------------- #
# Álgebra pura (matrizes 3x3 em linha-maior) — espelha rig_debug.py
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


def _transposta3(m: Mat3) -> Mat3:
  """Transposta de uma 3x3 (inversa de uma rotação pura)."""
  return (
    m[0], m[3], m[6],
    m[1], m[4], m[7],
    m[2], m[5], m[8],
  )


def _aplicar3(m: Mat3, v: Vetor3) -> Vetor3:
  """Aplica a 3x3 ``m`` ao vetor coluna ``v``."""
  x, y, z = v

  return (
    m[0] * x + m[1] * y + m[2] * z,
    m[3] * x + m[4] * y + m[5] * z,
    m[6] * x + m[7] * y + m[8] * z,
  )


def _normalizar(v: Vetor3) -> Vetor3:
  """Devolve ``v`` normalizado; vetor nulo volta como nulo (fail-safe)."""
  comprimento = sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])

  if comprimento == 0.0:
    return (0.0, 0.0, 0.0)

  return (v[0] / comprimento, v[1] / comprimento, v[2] / comprimento)


def _produto_escalar(a: Vetor3, b: Vetor3) -> float:
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


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
  """Composição HPR do Panda3D em álgebra pura (radianos): ``H * P * R``."""
  return _mul3(_rot_y(h), _mul3(_rot_x(p), _rot_z(r)))


def matriz_hpr_de_rotacao(rot: Rotation3) -> Mat3:
  """HPR a partir de um ``Rotation3`` animado (radianos): H=y, P=x, R=z."""
  return matriz_hpr(rot.y, rot.x, rot.z)


def matriz_rotacao_quat(quat: Quat) -> Mat3:
  """Converte o quaternião de repouso de um ``Node`` glTF em 3x3 (linha-maior)."""
  x, y, z, w = quat
  xx, yy, zz = x * x, y * y, z * z
  xy, xz, yz = x * y, x * z, y * z
  wx, wy, wz = w * x, w * y, w * z

  return (
    1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy),
    2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx),
    2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy),
  )


def _hpr_de_matriz(m: Mat3) -> Vetor3:
  """Extrai (H, P, R) em graus de uma 3x3 construída como ``H * P * R``.

  Inverte ``matriz_hpr``: P vem de ``-m[5] = sin(P)`` no eixo da coluna Y; H e
  R saem das demais componentes. Trata o travamento (gimbal lock) quando o
  pitch chega perto de ±90°.
  """
  seno_p = max(-1.0, min(1.0, -m[5]))
  p = atan2(seno_p, sqrt(max(0.0, 1.0 - seno_p * seno_p)))
  cos_p = cos(p)

  if abs(cos_p) < 1e-6:
    # Travamento: H e R colapsam; fixa R=0 e resolve H.
    h = atan2(-m[2], m[0])
    r = 0.0
  else:
    h = atan2(m[2], m[8])
    r = atan2(m[3], m[4])

  return (degrees(h), degrees(p), degrees(r))


# --------------------------------------------------------------------------- #
# Vetores de repouso por parte (seção 5.3) e eixo longo dos membros
# --------------------------------------------------------------------------- #
#: Vetores de referência de REPOUSO no espaço local do nó (Y=cima, X=direita,
#: Z=frente). Reaproveita a mesma base de ``rig_debug.VETORES_REFERENCIA`` para
#: mão/cabeça/corpo/porta; os membros usam só o ``eixo_longo``, que em repouso
#: pende para BAIXO (-Y).
VETORES_REPOUSO: dict[Parte, dict[str, Vetor3]] = {
  Parte.MAO_DIREITA: {
    "normal_palma": (0.0, -1.0, 0.0),
    "dorso": (0.0, 1.0, 0.0),
    "direcao_dedos": (0.0, -1.0, 0.0),
  },
  Parte.MAO_ESQUERDA: {
    "normal_palma": (0.0, -1.0, 0.0),
    "dorso": (0.0, 1.0, 0.0),
    "direcao_dedos": (0.0, -1.0, 0.0),
  },
  Parte.CABECA: {
    "olhar": (0.0, 0.0, 1.0),
    "topo": (0.0, 1.0, 0.0),
  },
  Parte.CORPO: {
    "frente": (0.0, 0.0, 1.0),
    "cima": (0.0, 1.0, 0.0),
  },
  Parte.PORTA: {
    "normal": (0.0, 0.0, 1.0),
    "eixo_giro": (0.0, 1.0, 0.0),
  },
}

#: Eixo longo de repouso compartilhado por braços, antebraços, ombros, pernas e
#: pés: o segmento pende para BAIXO (-Y) e a ponta fica na extremidade inferior.
EIXO_LONGO_REPOUSO: Vetor3 = (0.0, -1.0, 0.0)

#: Partes cujo eixo longo é a medida direcional principal e cuja ponta usa
#: ``comprimento_u`` (membros). As demais (corpo, cabeça, porta) não têm ponta.
PARTES_MEMBRO: frozenset[Parte] = frozenset(
  {
    Parte.BRACO_DIREITO,
    Parte.BRACO_ESQUERDO,
    Parte.OMBRO_DIREITO,
    Parte.OMBRO_ESQUERDO,
    Parte.ANTEBRACO_DIREITO,
    Parte.ANTEBRACO_ESQUERDO,
    Parte.MAO_DIREITA,
    Parte.MAO_ESQUERDA,
    Parte.DEDOS_DIREITA,
    Parte.DEDOS_ESQUERDA,
    Parte.PERNAS,
    Parte.PE_ESQUERDO,
    Parte.PE_DIREITO,
  }
)


def vetores_repouso_de(parte: Parte) -> dict[str, Vetor3]:
  """Vetores de referência de repouso da parte.

  Membros sem vetores próprios usam ``eixo_longo`` (o segmento apontando para
  baixo). Corpo/cabeça/porta trazem seus vetores nomeados.
  """
  if parte in VETORES_REPOUSO:
    return dict(VETORES_REPOUSO[parte])
  return {"eixo_longo": EIXO_LONGO_REPOUSO}


# --------------------------------------------------------------------------- #
# Hierarquia do modelo
# --------------------------------------------------------------------------- #
def _indice_por_nome(model: Model) -> dict[str, int]:
  """Primeiro índice de nó por nome (os grupos do rig são únicos no modelo)."""
  mapa: dict[str, int] = {}

  for node in model.nodes:
    if node.name and node.name not in mapa:
      mapa[node.name] = node.index

  return mapa


# --------------------------------------------------------------------------- #
# Rotação acumulada e vetor no mundo (seção 5.1)
# --------------------------------------------------------------------------- #
def resolver_rot_mundo(parte: Parte, pose: dict[str, Rotation3], model: Model) -> Mat3:
  """Rotação de mundo 3x3 acumulada da parte (repouso + HPR animado).

  Compõe, do nó raiz até a parte, a rotação de repouso do nó (quaternião do
  glTF) com a rotação HPR animada de ``pose`` (H=y, P=x, R=z), seguindo
  ``R_mundo(p) = R_mundo(pai) * R_repouso(p) * R_anim(p)``.
  """
  por_nome = _indice_por_nome(model)
  por_indice = {n.index: n for n in model.nodes}
  cache: dict[int, Mat3] = {}

  def acumulada(indice: int) -> Mat3:
    if indice in cache:
      return cache[indice]

    node = por_indice[indice]
    local_repouso = matriz_rotacao_quat(node.rotation)
    animada = _identidade3()

    if node.name in pose:
      animada = matriz_hpr_de_rotacao(pose[node.name])

    mundo_local = _mul3(local_repouso, animada)

    if node.parent is not None and node.parent in por_indice:
      resultado = _mul3(acumulada(node.parent), mundo_local)
    else:
      resultado = mundo_local

    cache[indice] = resultado

    return resultado

  indice = por_nome.get(parte.value)

  if indice is None:
    return _identidade3()

  return acumulada(indice)


def medir_vetor_mundo(matriz: Mat3, vetor_repouso: Vetor3) -> Vetor3:
  """Aplica a rotação de mundo ao vetor de repouso e normaliza (seção 5.3)."""
  return _normalizar(_aplicar3(matriz, vetor_repouso))


# --------------------------------------------------------------------------- #
# Posição acumulada (seção 5.4)
# --------------------------------------------------------------------------- #
def _origem_mundo(parte: Parte, model: Model) -> Vetor3:
  """Translação acumulada da origem do nó pela hierarquia (pose de repouso).

  A origem (base do segmento) é derivada das TRS dos nós, acumulada do nó raiz
  até a parte. Usa a rotação de repouso acumulada do pai para posicionar a
  translação local — suficiente para as referências do corpo em repouso.
  """
  por_nome = _indice_por_nome(model)
  por_indice = {n.index: n for n in model.nodes}

  indice = por_nome.get(parte.value)

  if indice is None:
    return (0.0, 0.0, 0.0)

  # Sobe até a raiz colecionando a cadeia de nós.
  cadeia: list[int] = []
  atual: int | None = indice

  while atual is not None and atual in por_indice:
    cadeia.append(atual)
    atual = por_indice[atual].parent

  cadeia.reverse()

  rot_acum = _identidade3()
  origem: Vetor3 = (0.0, 0.0, 0.0)

  for idx in cadeia:
    node = por_indice[idx]
    deslocado = _aplicar3(rot_acum, node.translation)
    origem = (origem[0] + deslocado[0], origem[1] + deslocado[1], origem[2] + deslocado[2])
    rot_acum = _mul3(rot_acum, matriz_rotacao_quat(node.rotation))

  return origem


def medir_referencias_corpo(model: Model) -> ReferenciasCorpo:
  """Alturas de referência medidas uma vez no repouso (seção 5.4).

  Deriva as alturas das origens dos nós do rig em repouso e dos limites do
  modelo (``bounds``). Valores robustos a troca de modelo ou de escala.
  """
  y_chao = model.bounds.minimum[1]
  y_topo = model.bounds.maximum[1]

  y_cabeca = _origem_mundo(Parte.CABECA, model)[1]
  y_ombro = _origem_mundo(Parte.OMBRO_DIREITO, model)[1]
  y_peito = _origem_mundo(Parte.CORPO, model)[1]
  y_cintura = _origem_mundo(Parte.PERNAS, model)[1]

  return ReferenciasCorpo(
    y_chao=y_chao,
    y_cintura=y_cintura,
    y_peito=y_peito,
    y_ombro=y_ombro,
    y_cabeca=y_cabeca,
    y_topo=y_topo,
  )


def _comprimento_repouso(parte: Parte, model: Model) -> float | None:
  """Comprimento do membro medido UMA vez no repouso (distância à ponta).

  Usa a distância entre a origem da parte e a origem do filho mais distante na
  cadeia do rig; sem filho medível, cai para a extensão vertical até o chão da
  origem. Partes sem eixo longo (corpo/cabeça/porta) devolvem ``None``.
  """
  if parte not in PARTES_MEMBRO:
    return None

  origem = _origem_mundo(parte, model)

  # Procura um filho direto conhecido como parte do rig para medir o segmento.
  filho = _parte_filha(parte)

  if filho is not None:
    ponta = _origem_mundo(filho, model)
    dx = ponta[0] - origem[0]
    dy = ponta[1] - origem[1]
    dz = ponta[2] - origem[2]
    comprimento = sqrt(dx * dx + dy * dy + dz * dz)

    if comprimento > 0.0:
      return comprimento

  # Sem filho medível: usa a distância da origem ao chão como estimativa.
  return abs(origem[1] - model.bounds.minimum[1]) or None


def _parte_filha(parte: Parte) -> Parte | None:
  """Primeira parte do rig cujo pai é ``parte`` (para medir o segmento)."""
  for candidata in Parte:
    if pai_de(candidata) is parte:
      return candidata
  return None


def _classificar_altura(y: float, refs: ReferenciasCorpo, limiares: Limiares) -> AlturaRelativa:
  """Classifica uma altura absoluta contra as referências do corpo.

  Escolhe a faixa de referência mais próxima; acima do topo da cabeça vira
  ``ACIMA_CABECA`` e no nível do chão (dentro da tolerância) vira
  ``NIVEL_CHAO``.
  """
  altura_em_pe = max(refs.y_topo - refs.y_chao, limiares.norma_min)
  tolerancia = limiares.tolerancia_chao_rel * altura_em_pe

  if y >= refs.y_cabeca + tolerancia:
    return AlturaRelativa.ACIMA_CABECA

  if y <= refs.y_chao + tolerancia:
    return AlturaRelativa.NIVEL_CHAO

  pares: tuple[tuple[float, AlturaRelativa], ...] = (
    (refs.y_cabeca, AlturaRelativa.NIVEL_CABECA),
    (refs.y_ombro, AlturaRelativa.NIVEL_OMBRO),
    (refs.y_peito, AlturaRelativa.NIVEL_PEITO),
    (refs.y_cintura, AlturaRelativa.NIVEL_CINTURA),
  )

  melhor = AlturaRelativa.NIVEL_CINTURA
  menor_dist = float("inf")

  for ref_y, nivel in pares:
    dist = abs(y - ref_y)

    if dist < menor_dist:
      menor_dist = dist
      melhor = nivel

  # Abaixo da cintura mas acima do chão.
  if y < refs.y_cintura - tolerancia and melhor is AlturaRelativa.NIVEL_CINTURA:
    return AlturaRelativa.ABAIXO_CINTURA

  return melhor


# --------------------------------------------------------------------------- #
# Grandezas de rotação (seção 5.2)
# --------------------------------------------------------------------------- #
def rot_local_graus(parte: Parte, pose: dict[str, Rotation3]) -> Vetor3:
  """HPR local animado da parte em graus (H=y, P=x, R=z)."""
  rot = pose.get(parte.value, Rotation3())
  return (degrees(rot.y), degrees(rot.x), degrees(rot.z))


def rot_mundo_graus(matriz: Mat3) -> Vetor3:
  """HPR (graus) extraído da rotação de mundo acumulada."""
  return _hpr_de_matriz(matriz)


def desvio_repouso_graus(rot_repouso: Mat3, rot_mundo: Mat3) -> float:
  """Ângulo total (0 a 180) entre a pose de repouso e a atual (seção 5.2).

  ``theta = arccos((tr(R_rel) - 1) / 2)`` com ``R_rel = R_repouso^T * R_mundo``,
  com o argumento preso em [-1, 1] por segurança numérica.
  """
  r_rel = _mul3(_transposta3(rot_repouso), rot_mundo)
  traco = r_rel[0] + r_rel[4] + r_rel[8]
  cosseno = max(-1.0, min(1.0, (traco - 1.0) / 2.0))

  return degrees(acos(cosseno))


def torcao_graus(rot_repouso: Mat3, rot_mundo: Mat3, eixo_longo: Vetor3) -> float:
  """Giro (-180 a 180) em torno do eixo longo (decomposição swing-twist).

  Decompõe a rotação relativa ``R_rel = R_repouso^T * R_mundo`` em balanço
  (swing) e torção (twist); devolve só a torção, o giro em torno de
  ``eixo_longo`` no espaço de repouso.
  """
  r_rel = _mul3(_transposta3(rot_repouso), rot_mundo)
  eixo = _normalizar(eixo_longo)

  if eixo == (0.0, 0.0, 0.0):
    return 0.0

  # Vetor do quaternião da rotação relativa (parte imaginária).
  traco = r_rel[0] + r_rel[4] + r_rel[8]
  w = sqrt(max(0.0, traco + 1.0)) / 2.0

  if w < 1e-9:
    # Rotação de ~180°: usa o eixo dominante da matriz simétrica.
    qx = sqrt(max(0.0, (r_rel[0] + 1.0) / 2.0))
    qy = sqrt(max(0.0, (r_rel[4] + 1.0) / 2.0))
    qz = sqrt(max(0.0, (r_rel[8] + 1.0) / 2.0))
  else:
    qx = (r_rel[7] - r_rel[5]) / (4.0 * w)
    qy = (r_rel[2] - r_rel[6]) / (4.0 * w)
    qz = (r_rel[3] - r_rel[1]) / (4.0 * w)

  # Projeção da parte vetorial do quaternião sobre o eixo longo (twist).
  projecao = qx * eixo[0] + qy * eixo[1] + qz * eixo[2]
  angulo = 2.0 * atan2(projecao, w)

  # Normaliza para (-180, 180].
  graus = degrees(angulo)

  while graus > 180.0:
    graus -= 360.0

  while graus <= -180.0:
    graus += 360.0

  return graus


# --------------------------------------------------------------------------- #
# Medição completa de uma parte (seção 5)
# --------------------------------------------------------------------------- #
def medir_parte(
  parte: Parte,
  pose: dict[str, Rotation3],
  model: Model,
  refs: ReferenciasCorpo,
  limiares: Limiares = LIMIARES_PADRAO,
) -> EstadoParte:
  """Produz um ``EstadoParte`` COMPLETO para ``parte`` na ``pose`` dada.

  Campos sem família para a parte ficam ``None`` (nunca inventados). Membros
  recebem ``ponta_mundo``/``comprimento_u``; corpo/cabeça/porta não têm ponta.
  """
  por_nome = _indice_por_nome(model)
  rot_mundo = resolver_rot_mundo(parte, pose, model)
  rot_repouso = (
    resolver_rot_mundo(parte, {}, model) if parte.value in por_nome else _identidade3()
  )

  repouso_vetores = vetores_repouso_de(parte)
  vetores_mundo: dict[str, Vetor3] = {}
  direcoes: dict[str, Direcao] = {}

  for nome, vetor in repouso_vetores.items():
    vm = medir_vetor_mundo(rot_mundo, vetor)
    vetores_mundo[nome] = vm
    direcoes[nome] = classificar_direcao(vm, limiares)

  eixo_longo = repouso_vetores.get("eixo_longo", EIXO_LONGO_REPOUSO)

  origem = _origem_mundo(parte, model)
  comprimento = _comprimento_repouso(parte, model)

  ponta: Vetor3 | None = None

  if parte in PARTES_MEMBRO and comprimento is not None:
    direcao_longa = medir_vetor_mundo(rot_mundo, eixo_longo)
    ponta = (
      origem[0] + direcao_longa[0] * comprimento,
      origem[1] + direcao_longa[1] * comprimento,
      origem[2] + direcao_longa[2] * comprimento,
    )

  # Altura relativa usa a ponta do membro quando há; senão, a origem.
  y_ref = ponta[1] if ponta is not None else origem[1]
  altura = _classificar_altura(y_ref, refs, limiares)

  x_central = model.bounds.center[0]
  distancia_eixo = abs(origem[0] - x_central)

  return EstadoParte(
    parte=parte,
    lado=lado_de(parte),
    pai=pai_de(parte),
    validacao=_validacao_de(parte),
    rot_local_graus=rot_local_graus(parte, pose),
    rot_mundo_graus=rot_mundo_graus(rot_mundo),
    desvio_repouso_graus=desvio_repouso_graus(rot_repouso, rot_mundo),
    torcao_graus=torcao_graus(rot_repouso, rot_mundo, eixo_longo),
    vetores_mundo=vetores_mundo,
    direcoes=direcoes,
    flags={},
    origem_mundo=origem,
    ponta_mundo=ponta,
    comprimento_u=comprimento,
    altura_relativa=altura,
    distancia_ao_eixo_central_u=distancia_eixo,
  )


def _validacao_de(parte: Parte):
  """Validação de uma parte (seção 5.6).

  Partes vistas na calibração visual (corpo, cabeça, porta, mãos, braços) são
  ``CONFIRMADO``; as deduzidas por matemática (ombros, dedos, pernas, pés)
  ficam ``A_VALIDAR``.
  """
  from .rig_mapa import Validacao

  confirmadas = {
    Parte.CORPO,
    Parte.CABECA,
    Parte.PORTA,
    Parte.BRACO_DIREITO,
    Parte.BRACO_ESQUERDO,
    Parte.ANTEBRACO_DIREITO,
    Parte.ANTEBRACO_ESQUERDO,
    Parte.MAO_DIREITA,
    Parte.MAO_ESQUERDA,
  }

  return Validacao.CONFIRMADO if parte in confirmadas else Validacao.A_VALIDAR


def medir_todas_as_partes(
  pose: dict[str, Rotation3],
  model: Model,
  limiares: Limiares = LIMIARES_PADRAO,
) -> dict[Parte, EstadoParte]:
  """Mede TODA ``Parte`` para a ``pose`` dada (seção 5).

  Garante um ``EstadoParte`` não-nulo por parte; partes ausentes do modelo
  caem para a identidade (origem na raiz), sem quebrar.
  """
  refs = medir_referencias_corpo(model)

  return {parte: medir_parte(parte, pose, model, refs, limiares) for parte in Parte}


# --------------------------------------------------------------------------- #
# Direção classificada reexportada (seção 5.3)
# --------------------------------------------------------------------------- #
# ``classificar_direcao`` vem de ``rig_limiares``; reexportado aqui para que a
# Fase 3 e os consumidores achem o pipeline inteiro em ``rig_medidas``.
__all__ = [
  "EIXO_LONGO_REPOUSO",
  "PARTES_MEMBRO",
  "VETORES_REPOUSO",
  "classificar_direcao",
  "desvio_repouso_graus",
  "matriz_hpr",
  "matriz_hpr_de_rotacao",
  "matriz_rotacao_quat",
  "medir_parte",
  "medir_referencias_corpo",
  "medir_todas_as_partes",
  "medir_vetor_mundo",
  "resolver_rot_mundo",
  "rot_local_graus",
  "rot_mundo_graus",
  "torcao_graus",
  "vetores_repouso_de",
]
