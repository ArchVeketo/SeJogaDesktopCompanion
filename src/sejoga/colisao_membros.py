"""Detecção de interpenetração entre membros, tronco, cabeça e porta.

Monta um VOLUME de colisão por parte do rig a partir do estado medido na Fase 2
(``rig_medidas.medir_todas_as_partes``): cada membro vira uma CÁPSULA (segmento
``origem_mundo`` -> ``ponta_mundo`` com raio) e o tronco/cabeça viram CAIXAS
ORIENTADAS centradas na origem da parte. Com isso dá para medir, em unidades do
modelo (``u``), QUANTO dois volumes se interpenetram em cada pose.

Esta é a etapa de DETECÇÃO (FEAT-001): produz a EVIDÊNCIA numérica de onde os
membros se atravessam, sem corrigir nada. A correção (mover o alvo da pose sem
saltar o ângulo) é o FEAT-002, guiado pelos números do relatório.

FRONTEIRA (igual a ``rig_mapa.py``/``rig_medidas.py``/``rig_articulacoes.py``):
este módulo é Python puro. NÃO importa Panda3D, Qt nem Win32. Depende só de
``math`` + ``dataclasses`` e, do próprio pacote, de ``rig_mapa`` e
``rig_medidas``. A álgebra de ``Vetor3`` é reescrita aqui em tuplas, espelhando
``rig_medidas`` (o precedente ``tentacle_constraints`` usa Panda3D e por isso
não é reaproveitado).

Eixos do mundo glTF: +X=direita, +Y=cima, +Z=frente.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from .rig_mapa import Parte, Vetor3
from .rig_medidas import PARTES_MEMBRO, EstadoParte

# --------------------------------------------------------------------------- #
# PARÂMETROS calibráveis — raios, meias-dimensões e limiar de colisão.
#
# Todos em UNIDADES DO MODELO (``u``), a mesma escala de ``comprimento_u`` e
# ``origem_mundo`` de ``rig_medidas``. São valores de PARTIDA, transparentes e
# ajustáveis: o relatório (docs/RELATORIO_COLISAO_MEMBROS.md) mostra o efeito
# deles nas poses reais e o FEAT-002 recalibra conforme a correção exigir.
# --------------------------------------------------------------------------- #

#: Raio da cápsula de cada membro (meia-espessura do "tubo" ao redor do osso).
#: Os segmentos mais grossos (braços) recebem raio maior; mãos/dedos, menor.
#: Membros ausentes deste mapa caem para ``RAIO_MEMBRO_PADRAO``.
RAIOS_MEMBRO: dict[Parte, float] = {
  Parte.BRACO_DIREITO: 0.16,
  Parte.BRACO_ESQUERDO: 0.16,
  Parte.OMBRO_DIREITO: 0.16,
  Parte.OMBRO_ESQUERDO: 0.16,
  Parte.ANTEBRACO_DIREITO: 0.13,
  Parte.ANTEBRACO_ESQUERDO: 0.13,
  Parte.MAO_DIREITA: 0.11,
  Parte.MAO_ESQUERDA: 0.11,
  Parte.DEDOS_DIREITA: 0.09,
  Parte.DEDOS_ESQUERDA: 0.09,
  Parte.PERNAS: 0.20,
  Parte.PE_ESQUERDO: 0.12,
  Parte.PE_DIREITO: 0.12,
}

#: Raio usado para qualquer membro fora de ``RAIOS_MEMBRO`` (fail-safe).
RAIO_MEMBRO_PADRAO: float = 0.12

#: Meias-dimensões (half-extents) da CAIXA ORIENTADA do tronco, nos eixos
#: locais (lateral/X, vertical/Y, frente-trás/Z). O tronco é largo e alto.
MEIA_DIM_TRONCO: Vetor3 = (0.42, 0.55, 0.30)

#: Meias-dimensões da CAIXA ORIENTADA da cabeça (bloco mais cúbico que o tronco).
MEIA_DIM_CABECA: Vetor3 = (0.30, 0.30, 0.30)

#: Meias-dimensões da CAIXA ORIENTADA da porta (painel fino na frente da cabeça).
MEIA_DIM_PORTA: Vetor3 = (0.24, 0.24, 0.05)

#: Quantidade de pontos amostrados ao longo do segmento da cápsula ao medir
#: penetração contra uma caixa. Mais pontos = profundidade mais fiel, mais custo.
AMOSTRAS_CAPSULA_CAIXA: int = 12

#: Profundidade mínima (``u``) para um contato CONTAR como colisão. Abaixo disso
#: é toque de casca/ruído de medição e é descartado. Calibrável: subir reduz
#: falsos positivos; descer flagra roçadas leves.
LIMIAR_PENETRACAO_U: float = 0.02


# --------------------------------------------------------------------------- #
# Volumes de colisão (dataclasses imutáveis, como em rig_mapa).
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Capsula:
  """Segmento ``a``->``b`` com raio: o "tubo" de um membro."""

  a: Vetor3
  b: Vetor3
  raio: float


@dataclass(frozen=True)
class CaixaOrientada:
  """Caixa centrada em ``centro``, com três ``eixos`` ortonormais e meias-dimensões.

  ``eixos`` é a tripla (eixo_x, eixo_y, eixo_z) no mundo; ``meias_dim`` são as
  meias-extensões ao longo de cada eixo. Montada a partir de um ``EstadoParte``:
  o centro é a origem da parte e os eixos saem da rotação de mundo dela (ou dos
  eixos do mundo, se a parte não expõe uma base própria).
  """

  centro: Vetor3
  eixos: tuple[Vetor3, Vetor3, Vetor3]
  meias_dim: Vetor3


Volume = Capsula | CaixaOrientada


# --------------------------------------------------------------------------- #
# Álgebra pura de Vetor3 — espelha rig_medidas (tuplas, sem dependências).
# --------------------------------------------------------------------------- #
def _sub(a: Vetor3, b: Vetor3) -> Vetor3:
  return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _soma(a: Vetor3, b: Vetor3) -> Vetor3:
  return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _escala(v: Vetor3, k: float) -> Vetor3:
  return (v[0] * k, v[1] * k, v[2] * k)


def _dot(a: Vetor3, b: Vetor3) -> float:
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norma(v: Vetor3) -> float:
  return sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _normalizar(v: Vetor3) -> Vetor3:
  """Devolve ``v`` normalizado; vetor nulo volta como nulo (fail-safe)."""
  comprimento = _norma(v)

  if comprimento == 0.0:
    return (0.0, 0.0, 0.0)

  return (v[0] / comprimento, v[1] / comprimento, v[2] / comprimento)


def _clamp(valor: float, minimo: float, maximo: float) -> float:
  return max(minimo, min(maximo, valor))


# --------------------------------------------------------------------------- #
# Distância segmento-segmento (base da penetração cápsula-cápsula).
# --------------------------------------------------------------------------- #
def dist_segmento_segmento(p1: Vetor3, q1: Vetor3, p2: Vetor3, q2: Vetor3) -> float:
  """Menor distância entre os segmentos ``[p1,q1]`` e ``[p2,q2]``.

  Algoritmo clássico (Ericson, *Real-Time Collision Detection*): acha os
  parâmetros ``s`` e ``t`` em ``[0,1]`` dos pontos mais próximos e devolve a
  distância entre eles. Trata segmentos degenerados (ponto) e paralelos sem
  divisão por zero, prendendo ``s`` e ``t`` ao intervalo ``[0,1]``.
  """
  d1 = _sub(q1, p1)  # direção do segmento 1
  d2 = _sub(q2, p2)  # direção do segmento 2
  r = _sub(p1, p2)

  a = _dot(d1, d1)  # comprimento² do segmento 1
  e = _dot(d2, d2)  # comprimento² do segmento 2
  f = _dot(d2, r)

  epsilon = 1e-12

  # Ambos os segmentos degeneram em pontos.
  if a <= epsilon and e <= epsilon:
    return _norma(_sub(p1, p2))

  if a <= epsilon:
    # Segmento 1 é um ponto.
    s = 0.0
    t = _clamp(f / e, 0.0, 1.0)
  else:
    c = _dot(d1, r)

    if e <= epsilon:
      # Segmento 2 é um ponto.
      t = 0.0
      s = _clamp(-c / a, 0.0, 1.0)
    else:
      # Caso geral (3D).
      b = _dot(d1, d2)
      denominador = a * e - b * b

      # Paralelos (denominador ~0): escolhe s=0 e resolve t.
      s = _clamp((b * f - c * e) / denominador, 0.0, 1.0) if denominador > epsilon else 0.0

      t = (b * s + f) / e

      # Se t saiu de [0,1], prende e recalcula s para o t preso.
      if t < 0.0:
        t = 0.0
        s = _clamp(-c / a, 0.0, 1.0)
      elif t > 1.0:
        t = 1.0
        s = _clamp((b - c) / a, 0.0, 1.0)

  ponto1 = _soma(p1, _escala(d1, s))
  ponto2 = _soma(p2, _escala(d2, t))

  return _norma(_sub(ponto1, ponto2))


# --------------------------------------------------------------------------- #
# Distância ponto-caixa (base da penetração cápsula-caixa).
# --------------------------------------------------------------------------- #
def dist_ponto_caixa(ponto: Vetor3, caixa: CaixaOrientada) -> float:
  """Distância ASSINADA de ``ponto`` à caixa (negativa DENTRO, positiva fora).

  Projeta o ponto nos eixos locais da caixa. Fora: distância euclidiana ao ponto
  mais próximo na casca. Dentro: menos a menor folga até uma face (a penetração
  mínima para sair da caixa), que serve de profundidade com sinal.
  """
  rel = _sub(ponto, caixa.centro)
  ex, ey, ez = caixa.eixos
  hx, hy, hz = caixa.meias_dim

  # Coordenadas locais (projeção nos eixos ortonormais).
  locais = (_dot(rel, ex), _dot(rel, ey), _dot(rel, ez))
  meias = (hx, hy, hz)

  fora_quadrado = 0.0
  dentro = True
  menor_folga = float("inf")

  for coord, meia in zip(locais, meias, strict=True):
    excesso = abs(coord) - meia

    if excesso > 0.0:
      dentro = False
      fora_quadrado += excesso * excesso
    else:
      # Folga até a face mais próxima nesse eixo (valor não-negativo).
      menor_folga = min(menor_folga, -excesso)

  if dentro:
    return -menor_folga

  return sqrt(fora_quadrado)


# --------------------------------------------------------------------------- #
# Penetração entre volumes (profundidade em u; 0.0 = sem contato).
# --------------------------------------------------------------------------- #
def penetracao_capsula_capsula(ca: Capsula, cb: Capsula) -> float:
  """Profundidade de interpenetração entre duas cápsulas (0.0 se separadas).

  ``max(0, (ra + rb) - dist_eixos)``: a soma dos raios menos a distância entre
  os eixos. Positivo quando os tubos se atravessam.
  """
  distancia = dist_segmento_segmento(ca.a, ca.b, cb.a, cb.b)

  return max(0.0, (ca.raio + cb.raio) - distancia)


def penetracao_capsula_caixa(cap: Capsula, caixa: CaixaOrientada) -> float:
  """Profundidade de interpenetração entre cápsula e caixa (0.0 se separadas).

  Amostra ``AMOSTRAS_CAPSULA_CAIXA`` pontos ao longo do eixo da cápsula e, em
  cada um, mede ``raio - dist_ponto_caixa``; devolve a MAIOR profundidade. A
  distância assinada entra negativa dentro da caixa, então o ponto mais fundo
  gera a penetração máxima. Aproxima o contato sem booleana exata de sólidos.
  """
  maior = 0.0
  passos = max(2, AMOSTRAS_CAPSULA_CAIXA)
  direcao = _sub(cap.b, cap.a)

  for i in range(passos):
    fracao = i / (passos - 1)
    ponto = _soma(cap.a, _escala(direcao, fracao))
    distancia = dist_ponto_caixa(ponto, caixa)
    profundidade = cap.raio - distancia

    if profundidade > maior:
      maior = profundidade

  return maior


# --------------------------------------------------------------------------- #
# Pares plausíveis de colisão (NÃO todos-contra-todos).
# --------------------------------------------------------------------------- #
#: Só os pares que de fato podem se atravessar numa pose do companion: braços e
#: suas pontas contra o CORPO; mãos/antebraços contra CABECA e PORTA; os dois
#: braços (e antebraços/mãos) cruzando a linha central; pernas e pés entre si.
#: A ordem (A, B) não importa para a matemática; é só a lista a varrer.
PARES_A_CHECAR: tuple[tuple[Parte, Parte], ...] = (
  # Braço/antebraço/mão de cada lado contra o TRONCO.
  (Parte.BRACO_DIREITO, Parte.CORPO),
  (Parte.ANTEBRACO_DIREITO, Parte.CORPO),
  (Parte.MAO_DIREITA, Parte.CORPO),
  (Parte.BRACO_ESQUERDO, Parte.CORPO),
  (Parte.ANTEBRACO_ESQUERDO, Parte.CORPO),
  (Parte.MAO_ESQUERDA, Parte.CORPO),
  # Mão/antebraço de cada lado contra a CABECA.
  (Parte.ANTEBRACO_DIREITO, Parte.CABECA),
  (Parte.MAO_DIREITA, Parte.CABECA),
  (Parte.ANTEBRACO_ESQUERDO, Parte.CABECA),
  (Parte.MAO_ESQUERDA, Parte.CABECA),
  # Mão/antebraço de cada lado contra a PORTA (painel na frente da cabeça).
  (Parte.ANTEBRACO_DIREITO, Parte.PORTA),
  (Parte.MAO_DIREITA, Parte.PORTA),
  (Parte.ANTEBRACO_ESQUERDO, Parte.PORTA),
  (Parte.MAO_ESQUERDA, Parte.PORTA),
  # Braços cruzando a linha central (um lado contra o outro).
  (Parte.BRACO_DIREITO, Parte.BRACO_ESQUERDO),
  (Parte.ANTEBRACO_DIREITO, Parte.ANTEBRACO_ESQUERDO),
  (Parte.ANTEBRACO_DIREITO, Parte.MAO_ESQUERDA),
  (Parte.MAO_DIREITA, Parte.ANTEBRACO_ESQUERDO),
  (Parte.MAO_DIREITA, Parte.MAO_ESQUERDA),
  # Pernas e pés entre si.
  (Parte.PERNAS, Parte.PE_ESQUERDO),
  (Parte.PERNAS, Parte.PE_DIREITO),
  (Parte.PE_ESQUERDO, Parte.PE_DIREITO),
)

#: Partes representadas por CAIXA ORIENTADA (as demais relevantes são cápsulas).
PARTES_CAIXA: dict[Parte, Vetor3] = {
  Parte.CORPO: MEIA_DIM_TRONCO,
  Parte.CABECA: MEIA_DIM_CABECA,
  Parte.PORTA: MEIA_DIM_PORTA,
}

#: Eixos do mundo glTF, usados como base da caixa quando a parte não oferece uma
#: base própria medida. +X=direita, +Y=cima, +Z=frente.
_EIXOS_MUNDO: tuple[Vetor3, Vetor3, Vetor3] = (
  (1.0, 0.0, 0.0),
  (0.0, 1.0, 0.0),
  (0.0, 0.0, 1.0),
)


# --------------------------------------------------------------------------- #
# Montagem de volumes a partir do estado medido do rig.
# --------------------------------------------------------------------------- #
def _raio_de(parte: Parte) -> float:
  """Raio da cápsula do membro (padrão para membros fora do mapa)."""
  return RAIOS_MEMBRO.get(parte, RAIO_MEMBRO_PADRAO)


def _eixos_da_caixa(estado: EstadoParte) -> tuple[Vetor3, Vetor3, Vetor3]:
  """Base ortonormal da caixa de uma parte-bloco (tronco/cabeça/porta).

  Prefere os vetores de mundo da parte (``frente``/``cima`` do corpo,
  ``olhar``/``topo`` da cabeça, ``normal``/``eixo_giro`` da porta); completa a
  base com produto vetorial. Sem vetores utilizáveis, cai para os eixos do
  mundo glTF.
  """
  vetores = estado.vetores_mundo

  frente = vetores.get("frente") or vetores.get("olhar") or vetores.get("normal")
  cima = vetores.get("cima") or vetores.get("topo") or vetores.get("eixo_giro")

  if frente is None or cima is None:
    return _EIXOS_MUNDO

  eixo_z = _normalizar(frente)
  eixo_y = _normalizar(cima)

  # eixo_x = cima x frente (direita do corpo); reortogonaliza o y em seguida.
  eixo_x = _normalizar(_produto_vetorial(eixo_y, eixo_z))

  if eixo_x == (0.0, 0.0, 0.0) or eixo_z == (0.0, 0.0, 0.0):
    return _EIXOS_MUNDO

  eixo_y = _normalizar(_produto_vetorial(eixo_z, eixo_x))

  return (eixo_x, eixo_y, eixo_z)


def _produto_vetorial(a: Vetor3, b: Vetor3) -> Vetor3:
  return (
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  )


def montar_volumes(partes: dict[Parte, EstadoParte]) -> dict[Parte, Volume]:
  """Monta o volume de colisão de cada parte relevante.

  Membros (``PARTES_MEMBRO``) com ponta medida viram ``Capsula`` do segmento
  ``origem_mundo``->``ponta_mundo``; tronco/cabeça/porta viram ``CaixaOrientada``
  centrada na origem. Partes sem dado utilizável ficam de fora do dicionário.
  """
  volumes: dict[Parte, Volume] = {}

  for parte, estado in partes.items():
    if parte in PARTES_MEMBRO:
      ponta = estado.ponta_mundo

      if ponta is not None:
        volumes[parte] = Capsula(a=estado.origem_mundo, b=ponta, raio=_raio_de(parte))

    elif parte in PARTES_CAIXA:
      volumes[parte] = CaixaOrientada(
        centro=estado.origem_mundo,
        eixos=_eixos_da_caixa(estado),
        meias_dim=PARTES_CAIXA[parte],
      )

  return volumes


# --------------------------------------------------------------------------- #
# Colisão detectada e varredura de pares.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Colisao:
  """Uma interpenetração encontrada em uma pose/instante.

  ``profundidade_u`` é quanto os volumes se atravessam, em unidades do modelo.
  """

  par: tuple[Parte, Parte]
  profundidade_u: float
  pose: str
  t_s: float


def _penetracao_entre(a: Volume, b: Volume) -> float:
  """Penetração entre dois volumes, escolhendo a matemática do par de tipos."""
  if isinstance(a, Capsula) and isinstance(b, Capsula):
    return penetracao_capsula_capsula(a, b)

  if isinstance(a, Capsula) and isinstance(b, CaixaOrientada):
    return penetracao_capsula_caixa(a, b)

  if isinstance(a, CaixaOrientada) and isinstance(b, Capsula):
    return penetracao_capsula_caixa(b, a)

  # Caixa-caixa não ocorre em PARES_A_CHECAR; sem matemática dedicada aqui.
  return 0.0


def detectar_colisoes(
  partes: dict[Parte, EstadoParte],
  pose_nome: str,
  t_s: float,
) -> list[Colisao]:
  """Varre ``PARES_A_CHECAR`` e devolve as colisões ``>= LIMIAR_PENETRACAO_U``.

  Monta os volumes uma vez, calcula a penetração do tipo certo em cada par e
  guarda só os contatos acima do limiar. Pares sem volume montado (parte
  ausente do modelo) são ignorados sem erro.
  """
  volumes = montar_volumes(partes)
  colisoes: list[Colisao] = []

  for parte_a, parte_b in PARES_A_CHECAR:
    vol_a = volumes.get(parte_a)
    vol_b = volumes.get(parte_b)

    if vol_a is None or vol_b is None:
      continue

    profundidade = _penetracao_entre(vol_a, vol_b)

    if profundidade >= LIMIAR_PENETRACAO_U:
      colisoes.append(
        Colisao(par=(parte_a, parte_b), profundidade_u=profundidade, pose=pose_nome, t_s=t_s)
      )

  return colisoes


__all__ = [
  "AMOSTRAS_CAPSULA_CAIXA",
  "LIMIAR_PENETRACAO_U",
  "MEIA_DIM_CABECA",
  "MEIA_DIM_PORTA",
  "MEIA_DIM_TRONCO",
  "PARES_A_CHECAR",
  "PARTES_CAIXA",
  "RAIOS_MEMBRO",
  "RAIO_MEMBRO_PADRAO",
  "CaixaOrientada",
  "Capsula",
  "Colisao",
  "Volume",
  "detectar_colisoes",
  "dist_ponto_caixa",
  "dist_segmento_segmento",
  "montar_volumes",
  "penetracao_capsula_caixa",
  "penetracao_capsula_capsula",
]
