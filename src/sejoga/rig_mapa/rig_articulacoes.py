"""Articulações do rig (Fase 3 do mapeamento).

Dobrado ou esticado não vive num vetor só: é a relação entre dois segmentos.
Este módulo define o catálogo estático ``ARTICULACOES`` (uma
``DefinicaoArticulacao`` por junta) e as medições da seção 6 do documento
``docs/Mapeamento Completo do Corpo do Rig Detecção e Nomenclatura.md``: flexão
assinada, plano de flexão, torção relativa (swing-twist), proporção
normalizada, estado por faixas e ``fora_do_limite``.

FRONTEIRA (igual a ``model.py``/``rig.py``/``rig_medidas.py``): este módulo é
Python puro. NÃO importa Panda3D, Qt nem Win32. Depende só de ``math`` e, do
próprio pacote, de ``rig_mapa``, ``rig_limiares`` e ``rig_medidas``.

Catálogo AJUSTADO à hierarquia real do GLTF
(``context.json.gltf_inventario.correcoes_ao_doc``):

* ``dobradica_porta`` tem pai REAL ``CABECA`` (não ``CORPO``): a porta é filha
  da cabeça no modelo. A abertura é medida pela rotação local de ``door`` em H,
  como o ``rig_debug`` sempre fez; o limite de velocidade (~38 graus/s) é
  respeitado na camada de animação, não aqui.
* NÃO existem ``joelho_*`` nem ``quadril_*``: as pernas são um bloco único
  (``legs``), sem coxa/canela separadas.
* NÃO existem ``tornozelo_*``: os pés (``left-feet``/``right-feet``) são filhos
  da RAIZ, não de ``legs``; não há parentesco ``legs -> feet`` para medir.
* NÃO há ``tentaculo_*`` nesta fase: tentáculos (cadeia) ficam para fases
  posteriores de descrição.
"""

from __future__ import annotations

from math import acos, atan2, degrees, sqrt

from sejoga.rig_mapa.rig_limiares import (
  LIMIARES_PADRAO,
  LIMITE_COTOVELO,
  LIMITE_OMBRO,
  LIMITE_PESCOCO,
  LIMITE_PORTA,
  LIMITE_PUNHO,
  Limiares,
  classificar_por_faixas,
)
from sejoga.rig_mapa.rig_mapa import (
  DefinicaoArticulacao,
  EstadoArticulacao,
  EstadoFlexao,
  Lado,
  Parte,
  PlanoFlexao,
  TipoArticulacao,
  Vetor3,
  lado_de,
)
from sejoga.rig_mapa.rig_medidas import EstadoParte

# --------------------------------------------------------------------------- #
# Catálogo estático de articulações (seção 6.4, ajustado ao GLTF)
# --------------------------------------------------------------------------- #
#: Eixo de dobra padrão dos membros no espaço de repouso. O cotovelo dobra em
#: torno de um eixo perpendicular ao segmento longo (-Y); usamos +X como eixo de
#: referência local da dobradiça, coerente com os eixos do mundo glTF.
_EIXO_DOBRA_PADRAO: Vetor3 = (1.0, 0.0, 0.0)

#: Eixo de giro da porta (dobradiça em Y/heading), ver seção 7.3 e rig_debug.
_EIXO_PORTA: Vetor3 = (0.0, 1.0, 0.0)

#: Eixo do pivô do pescoço (giro em torno do eixo vertical do corpo).
_EIXO_PESCOCO: Vetor3 = (0.0, 1.0, 0.0)

#: Catálogo estático, do mesmo jeito que ``VETORES_REFERENCIA`` vive hoje.
#:
#: ATENÇÃO às correções ao documento (ver docstring do módulo):
#: NÃO há ``joelho_*``, ``quadril_*``, ``tornozelo_*`` nem ``tentaculo_*`` —
#: o GLTF não expõe os nós/parentescos que essas juntas exigiriam.
ARTICULACOES: dict[str, DefinicaoArticulacao] = {
  "cotovelo_direito": DefinicaoArticulacao(
    nome="cotovelo_direito",
    tipo=TipoArticulacao.DOBRADICA,
    segmento_proximal=Parte.BRACO_DIREITO,
    segmento_distal=Parte.ANTEBRACO_DIREITO,
    angulo_min_graus=LIMITE_COTOVELO.minimo,
    angulo_max_graus=LIMITE_COTOVELO.maximo,
    sinal_natural=1.0,
    eixo=_EIXO_DOBRA_PADRAO,
  ),
  "cotovelo_esquerdo": DefinicaoArticulacao(
    nome="cotovelo_esquerdo",
    tipo=TipoArticulacao.DOBRADICA,
    segmento_proximal=Parte.BRACO_ESQUERDO,
    segmento_distal=Parte.ANTEBRACO_ESQUERDO,
    angulo_min_graus=LIMITE_COTOVELO.minimo,
    angulo_max_graus=LIMITE_COTOVELO.maximo,
    sinal_natural=1.0,
    eixo=_EIXO_DOBRA_PADRAO,
  ),
  "ombro_direito": DefinicaoArticulacao(
    nome="ombro_direito",
    tipo=TipoArticulacao.ESFERICA,
    segmento_proximal=Parte.CORPO,
    segmento_distal=Parte.BRACO_DIREITO,
    angulo_min_graus=LIMITE_OMBRO.minimo,
    angulo_max_graus=LIMITE_OMBRO.maximo,
    sinal_natural=1.0,
    eixo=_EIXO_DOBRA_PADRAO,
  ),
  "ombro_esquerdo": DefinicaoArticulacao(
    nome="ombro_esquerdo",
    tipo=TipoArticulacao.ESFERICA,
    segmento_proximal=Parte.CORPO,
    segmento_distal=Parte.BRACO_ESQUERDO,
    angulo_min_graus=LIMITE_OMBRO.minimo,
    angulo_max_graus=LIMITE_OMBRO.maximo,
    sinal_natural=1.0,
    eixo=_EIXO_DOBRA_PADRAO,
  ),
  "punho_direito": DefinicaoArticulacao(
    nome="punho_direito",
    tipo=TipoArticulacao.ESFERICA,
    segmento_proximal=Parte.ANTEBRACO_DIREITO,
    segmento_distal=Parte.MAO_DIREITA,
    angulo_min_graus=LIMITE_PUNHO.minimo,
    angulo_max_graus=LIMITE_PUNHO.maximo,
    sinal_natural=1.0,
    eixo=_EIXO_DOBRA_PADRAO,
  ),
  "punho_esquerdo": DefinicaoArticulacao(
    nome="punho_esquerdo",
    tipo=TipoArticulacao.ESFERICA,
    segmento_proximal=Parte.ANTEBRACO_ESQUERDO,
    segmento_distal=Parte.MAO_ESQUERDA,
    angulo_min_graus=LIMITE_PUNHO.minimo,
    angulo_max_graus=LIMITE_PUNHO.maximo,
    sinal_natural=1.0,
    eixo=_EIXO_DOBRA_PADRAO,
  ),
  "pescoco": DefinicaoArticulacao(
    nome="pescoco",
    tipo=TipoArticulacao.PIVO,
    segmento_proximal=Parte.CORPO,
    segmento_distal=Parte.CABECA,
    angulo_min_graus=LIMITE_PESCOCO.minimo,
    angulo_max_graus=LIMITE_PESCOCO.maximo,
    sinal_natural=1.0,
    eixo=_EIXO_PESCOCO,
  ),
  # Pai REAL = CABECA (a porta é filha da cabeça no GLTF, não do corpo). O
  # limite de velocidade (~38 graus/s) é respeitado na camada de animação; a
  # abertura é a rotação local de ``door`` em H, como o rig_debug mede.
  "dobradica_porta": DefinicaoArticulacao(
    nome="dobradica_porta",
    tipo=TipoArticulacao.DOBRADICA,
    segmento_proximal=Parte.CABECA,
    segmento_distal=Parte.PORTA,
    angulo_min_graus=LIMITE_PORTA.minimo,
    angulo_max_graus=LIMITE_PORTA.maximo,
    sinal_natural=1.0,
    eixo=_EIXO_PORTA,
  ),
  # joelho_direito / joelho_esquerdo: NÃO criados — pernas são bloco único.
  # quadril_direito / quadril_esquerdo: NÃO criados — sem nó de coxa/quadril.
  # tornozelo_direito / tornozelo_esquerdo: NÃO criados — pés filhos da raiz,
  #   sem parentesco legs -> feet para medir.
  # tentaculo_N_elo_K: NÃO criados nesta fase (cadeia fica para depois).
}


# --------------------------------------------------------------------------- #
# Álgebra vetorial mínima (reaproveita a mesma convenção de rig_medidas)
# --------------------------------------------------------------------------- #
def _normalizar(v: Vetor3) -> Vetor3:
  """Devolve ``v`` normalizado; vetor nulo volta como nulo (fail-safe)."""
  comprimento = sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])

  if comprimento == 0.0:
    return (0.0, 0.0, 0.0)

  return (v[0] / comprimento, v[1] / comprimento, v[2] / comprimento)


def _produto_escalar(a: Vetor3, b: Vetor3) -> float:
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _produto_vetorial(a: Vetor3, b: Vetor3) -> Vetor3:
  return (
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  )


# --------------------------------------------------------------------------- #
# Medição de flexão (seção 6.2 / 6.6)
# --------------------------------------------------------------------------- #
def medir_flexao(
  longo_proximal_mundo: Vetor3,
  longo_distal_mundo: Vetor3,
  referencia_dobra_mundo: Vetor3,
) -> tuple[float, Vetor3]:
  """Flexão assinada (graus) e vetor de dobra no mundo (seção 6.2/6.6).

  O ângulo é ``arccos(l_prox . l_dist)`` entre os eixos longos normalizados; o
  sinal vem da projeção do vetor de dobra sobre ``referencia_dobra_mundo`` (o
  eixo natural da dobra): mesmo sentido -> positivo (dobra natural), sentido
  oposto -> negativo (hiperextensão). O vetor de dobra é a componente do eixo
  distal perpendicular ao proximal.
  """
  prox = _normalizar(longo_proximal_mundo)
  dist = _normalizar(longo_distal_mundo)

  if prox == (0.0, 0.0, 0.0) or dist == (0.0, 0.0, 0.0):
    return 0.0, (0.0, 0.0, 0.0)

  cosseno = max(-1.0, min(1.0, _produto_escalar(prox, dist)))
  magnitude = degrees(acos(cosseno))

  # Vetor de dobra = componente do distal perpendicular ao proximal.
  projecao = _produto_escalar(dist, prox)
  dobra = (
    dist[0] - projecao * prox[0],
    dist[1] - projecao * prox[1],
    dist[2] - projecao * prox[2],
  )
  dobra_unit = _normalizar(dobra)

  # Sinal: a favor do eixo natural de dobra -> positivo; contra -> negativo.
  ref = _normalizar(referencia_dobra_mundo)
  sinal = 1.0

  if ref != (0.0, 0.0, 0.0) and dobra_unit != (0.0, 0.0, 0.0):
    sinal = 1.0 if _produto_escalar(dobra_unit, ref) >= 0.0 else -1.0

  return sinal * magnitude, dobra_unit


def plano_de_flexao(
  longo_proximal_mundo: Vetor3,
  longo_distal_mundo: Vetor3,
  frente_corpo_mundo: Vetor3,
  cima_corpo_mundo: Vetor3,
) -> PlanoFlexao:
  """Classifica o vetor de dobra contra os eixos do CORPO (seção 6.2).

  "Para dentro"/"para fora" e "para frente"/"para trás" são medidos no
  referencial do corpo (não do mundo) para que valham igual nos dois lados.
  Eixo lateral do corpo = frente x cima.
  """
  _, dobra = medir_flexao(longo_proximal_mundo, longo_distal_mundo, frente_corpo_mundo)

  if dobra == (0.0, 0.0, 0.0):
    return PlanoFlexao.SEM_FLEXAO

  frente = _normalizar(frente_corpo_mundo)
  cima = _normalizar(cima_corpo_mundo)
  lateral = _normalizar(_produto_vetorial(frente, cima))

  comp_frente = _produto_escalar(dobra, frente)
  comp_lateral = _produto_escalar(dobra, lateral)

  if abs(comp_frente) >= abs(comp_lateral):
    return PlanoFlexao.PARA_FRENTE if comp_frente >= 0.0 else PlanoFlexao.PARA_TRAS

  # Lateral = frente x cima aponta para a DIREITA do corpo; dobra a favor dele
  # vai "para fora" do lado direito e "para dentro" do esquerdo. Classificamos
  # pela componente lateral crua (positiva = para fora à direita).
  return PlanoFlexao.PARA_FORA if comp_lateral >= 0.0 else PlanoFlexao.PARA_DENTRO


def torcao_relativa(
  longo_proximal_mundo: Vetor3,
  longo_distal_mundo: Vetor3,
  eixo_longo_mundo: Vetor3,
) -> float:
  """Giro (-180 a 180) de um segmento sobre o outro em torno do eixo longo.

  Decomposição swing-twist simplificada: projeta a rotação de alinhamento entre
  os eixos longos sobre o eixo comum. Para dobradiças puras (cotovelo) a torção
  é ~0; serve de métrica de giro axial das juntas de pivô/esférica.
  """
  prox = _normalizar(longo_proximal_mundo)
  dist = _normalizar(longo_distal_mundo)
  eixo = _normalizar(eixo_longo_mundo)

  if eixo == (0.0, 0.0, 0.0) or prox == (0.0, 0.0, 0.0) or dist == (0.0, 0.0, 0.0):
    return 0.0

  # Componentes dos segmentos perpendiculares ao eixo comum.
  perp_prox = (
    prox[0] - _produto_escalar(prox, eixo) * eixo[0],
    prox[1] - _produto_escalar(prox, eixo) * eixo[1],
    prox[2] - _produto_escalar(prox, eixo) * eixo[2],
  )
  perp_dist = (
    dist[0] - _produto_escalar(dist, eixo) * eixo[0],
    dist[1] - _produto_escalar(dist, eixo) * eixo[1],
    dist[2] - _produto_escalar(dist, eixo) * eixo[2],
  )
  perp_prox = _normalizar(perp_prox)
  perp_dist = _normalizar(perp_dist)

  if perp_prox == (0.0, 0.0, 0.0) or perp_dist == (0.0, 0.0, 0.0):
    return 0.0

  cosseno = max(-1.0, min(1.0, _produto_escalar(perp_prox, perp_dist)))
  seno = _produto_escalar(_produto_vetorial(perp_prox, perp_dist), eixo)

  return degrees(atan2(seno, cosseno))


# --------------------------------------------------------------------------- #
# Proporção, estado e limite (seções 6.2 e 6.5)
# --------------------------------------------------------------------------- #
def proporcao_norm(phi: float, angulo_min: float, angulo_max: float) -> float:
  """Posição normalizada de ``phi`` dentro de ``[min, max]`` (0,0 a 1,0)."""
  faixa = angulo_max - angulo_min

  if faixa == 0.0:
    return 0.0

  return (phi - angulo_min) / faixa


def estado_flexao(phi: float, limiares: Limiares = LIMIARES_PADRAO) -> EstadoFlexao:
  """Classifica a flexão assinada em ``EstadoFlexao`` (seção 6.5).

  Fronteiras exatas: ``<= 15`` -> ESTICADO, ``> 15`` começa LEVE, ``> 45``
  DOBRADO, ``> 110`` MUITO_DOBRADO; valor negativo (hiperextensão) ->
  HIPEREXTENDIDO.
  """
  if phi < 0.0:
    return EstadoFlexao.HIPEREXTENDIDO

  faixas: tuple[tuple[float, EstadoFlexao], ...] = (
    (limiares.esticado_ate_graus, EstadoFlexao.ESTICADO),
    (limiares.leve_ate_graus, EstadoFlexao.LEVE),
    (limiares.dobrado_ate_graus, EstadoFlexao.DOBRADO),
  )

  return classificar_por_faixas(phi, faixas, EstadoFlexao.MUITO_DOBRADO)


def fora_do_limite(
  phi: float,
  definicao: DefinicaoArticulacao,
  limiares: Limiares = LIMIARES_PADRAO,
) -> bool:
  """``True`` se ``phi`` passa de ``angulo_min``/``angulo_max`` com tolerância."""
  tolerancia = limiares.tolerancia_limite_graus

  return (
    phi < definicao.angulo_min_graus - tolerancia
    or phi > definicao.angulo_max_graus + tolerancia
  )


# --------------------------------------------------------------------------- #
# Análise de articulação a partir dos EstadoParte (FEAT-002)
# --------------------------------------------------------------------------- #
def _eixo_longo_de(estado: EstadoParte) -> Vetor3:
  """Eixo longo no mundo de uma parte; membros usam ``eixo_longo``.

  Partes sem eixo longo (corpo/cabeça/porta) caem para o vetor que melhor
  representa seu "para onde aponta": ``cima`` do corpo, ``olhar`` da cabeça,
  ``normal`` da porta.
  """
  vetores = estado.vetores_mundo

  for chave in ("eixo_longo", "cima", "olhar", "normal"):
    if chave in vetores:
      return vetores[chave]

  # Sem vetor conhecido: devolve o primeiro disponível ou um eixo nulo.
  for vetor in vetores.values():
    return vetor

  return (0.0, 0.0, 0.0)


def _lado_da_articulacao(definicao: DefinicaoArticulacao) -> Lado:
  """Lado da junta = lado do segmento distal (centro para porta/pescoço)."""
  return lado_de(definicao.segmento_distal)


def analisar_articulacao(
  definicao: DefinicaoArticulacao,
  partes: dict[Parte, EstadoParte],
) -> EstadoArticulacao:
  """Produz um ``EstadoArticulacao`` completo a partir dos ``EstadoParte``.

  Lê os eixos longos dos segmentos proximal e distal já medidos na Fase 2,
  calcula flexão assinada, plano, torção, proporção, estado e ``fora_do_limite``.
  """
  proximal = partes[definicao.segmento_proximal]
  distal = partes[definicao.segmento_distal]

  longo_prox = _eixo_longo_de(proximal)
  longo_dist = _eixo_longo_de(distal)

  # Eixo de dobra de referência: o eixo local da definição levado ao mundo pela
  # orientação do segmento proximal seria o ideal; na ausência da matriz aqui,
  # usamos a frente do corpo como referência de sinal (dobra para a frente
  # conta como positiva), coerente com o plano de flexão.
  corpo = partes[Parte.CORPO]
  frente_corpo = corpo.vetores_mundo.get("frente", (0.0, 0.0, 1.0))
  cima_corpo = corpo.vetores_mundo.get("cima", (0.0, 1.0, 0.0))

  phi, _ = medir_flexao(longo_prox, longo_dist, frente_corpo)
  plano = plano_de_flexao(longo_prox, longo_dist, frente_corpo, cima_corpo)
  torcao = torcao_relativa(longo_prox, longo_dist, longo_prox)

  return EstadoArticulacao(
    nome=definicao.nome,
    lado=_lado_da_articulacao(definicao),
    segmento_proximal=definicao.segmento_proximal,
    segmento_distal=definicao.segmento_distal,
    angulo_flexao_graus=phi,
    angulo_min_graus=definicao.angulo_min_graus,
    angulo_max_graus=definicao.angulo_max_graus,
    proporcao_norm=proporcao_norm(phi, definicao.angulo_min_graus, definicao.angulo_max_graus),
    estado=estado_flexao(phi),
    plano=plano,
    torcao_graus=torcao,
    fora_do_limite=fora_do_limite(phi, definicao),
  )


def analisar_articulacoes(
  partes: dict[Parte, EstadoParte],
) -> dict[str, EstadoArticulacao]:
  """Analisa TODAS as articulações do catálogo para as partes medidas."""
  return {nome: analisar_articulacao(definicao, partes) for nome, definicao in ARTICULACOES.items()}


__all__ = [
  "ARTICULACOES",
  "analisar_articulacao",
  "analisar_articulacoes",
  "estado_flexao",
  "fora_do_limite",
  "medir_flexao",
  "plano_de_flexao",
  "proporcao_norm",
  "torcao_relativa",
]
