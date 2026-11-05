"""Modelo de dados do mapeamento do rig: Enums e dataclasses imutáveis.

Fundação das Fases 1 a 3 do documento
``docs/Mapeamento Completo do Corpo do Rig Detecção e Nomenclatura.md``
(seções 2, 4, 6.1 e 11.5/12.4). Python puro: não importa Panda3D, Qt nem
Win32, seguindo a fronteira de ``model.py``/``rig.py``/``assets.py`` do
``AGENTS.md``.

Princípios herdados do documento:

* Medir primeiro, classificar depois, descrever por último. O número nunca é
  perdido ao virar flag.
* O valor de ``Parte`` é o nome do grupo no GLTF; não renomear o valor.
* Dataclasses ``frozen=True`` para que um frame não contamine o seguinte.

Correções ao documento, confirmadas pela hierarquia real do GLTF
(``context.json.gltf_inventario``):

* ``door`` é filho de ``head``, não de ``body`` como o documento assumia. A
  abertura da porta é medida pela rotação local de ``door``.
* ``left-feet``/``right-feet`` são filhos da RAIZ, não de ``legs`` nem de
  ``body``. Não existe relação ``legs -> feet``: não há ``tornozelo_*``.
* O braço esquerdo EXISTE (``left-arm`` e cadeia), simétrico ao direito; o que
  o documento marcava como ``A_CONFIRMAR`` fica CONFIRMADO.
* Não há nó de polegar: ``fingers``/``fingers2`` são cuboides genéricos.
  ``eixo_polegar`` não é medido; gestos de polegar são derivados.
* As pernas são um bloco único (``legs``): não há ``joelho_*``/``quadril_*``/
  coxa/canela.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

Vetor3 = tuple[float, float, float]


# --------------------------------------------------------------------------- #
# Enums base (seção 4.1)
# --------------------------------------------------------------------------- #
class Lado(Enum):
  DIREITA = "direita"
  ESQUERDA = "esquerda"
  CENTRO = "centro"


class Parte(Enum):
  """Valor = nome do grupo no GLTF. Não renomear o valor.

  Cobre os 16 nós nomeados do rig (``context.json.gltf_inventario``).
  """

  CORPO = "body"
  CABECA = "head"
  PORTA = "door"
  BRACO_DIREITO = "right-arm"
  OMBRO_DIREITO = "shoulder"
  ANTEBRACO_DIREITO = "ant-arm"
  MAO_DIREITA = "hand"
  DEDOS_DIREITA = "fingers"
  BRACO_ESQUERDO = "left-arm"
  OMBRO_ESQUERDO = "shoulder2"
  ANTEBRACO_ESQUERDO = "ant-arm2"
  MAO_ESQUERDA = "hand2"
  DEDOS_ESQUERDA = "fingers2"
  PERNAS = "legs"
  PE_ESQUERDO = "left-feet"
  PE_DIREITO = "right-feet"


class DirecaoMundo(Enum):
  CIMA = "cima"
  BAIXO = "baixo"
  FRENTE = "frente"
  TRAS = "tras"
  DIREITA = "direita"
  ESQUERDA = "esquerda"
  INDEFINIDA = "indefinida"  # vetor nulo ou ambíguo demais


class EstadoFlexao(Enum):
  ESTICADO = "esticado"
  LEVE = "leve"
  DOBRADO = "dobrado"
  MUITO_DOBRADO = "muito_dobrado"
  HIPEREXTENDIDO = "hiperextendido"


class PlanoFlexao(Enum):
  PARA_FRENTE = "para_frente"
  PARA_TRAS = "para_tras"
  PARA_DENTRO = "para_dentro"  # em direção à linha central
  PARA_FORA = "para_fora"
  SEM_FLEXAO = "sem_flexao"


class AlturaRelativa(Enum):
  ACIMA_CABECA = "acima_cabeca"
  NIVEL_CABECA = "nivel_cabeca"
  NIVEL_OMBRO = "nivel_ombro"
  NIVEL_PEITO = "nivel_peito"
  NIVEL_CINTURA = "nivel_cintura"
  ABAIXO_CINTURA = "abaixo_cintura"
  NIVEL_CHAO = "nivel_chao"


class SentidoMovimento(Enum):
  PARADO = "parado"
  SUBINDO = "subindo"
  DESCENDO = "descendo"
  ABRINDO = "abrindo"
  FECHANDO = "fechando"
  GIRANDO_HORARIO = "girando_horario"
  GIRANDO_ANTIHORARIO = "girando_antihorario"


class Validacao(Enum):
  CONFIRMADO = "confirmado"  # visto na calibração visual
  A_VALIDAR = "a_validar"  # deduzido por matemática


class TipoArticulacao(Enum):
  """Tipos de articulação (seção 6.1)."""

  DOBRADICA = "dobradica"  # 1 grau de liberdade: cotovelo, joelho, porta
  ESFERICA = "esferica"  # 3 graus: ombro, quadril
  PIVO = "pivo"  # giro em torno do eixo longo: pescoço, antebraço
  CADEIA = "cadeia"  # sequência de elos: tentáculos
  FIXA = "fixa"  # sem movimento próprio


# --------------------------------------------------------------------------- #
# Enums de direção usados pelos aliases (seções 7.1, 7.2, 7.3)
# --------------------------------------------------------------------------- #
class DirecaoPalma(Enum):
  PARA_CIMA = "para_cima"
  PARA_BAIXO = "para_baixo"
  PARA_FRENTE = "para_frente"
  PARA_TRAS = "para_tras"
  PARA_DENTRO = "para_dentro"  # em direção à linha central do corpo
  PARA_FORA = "para_fora"
  DIAGONAL = "diagonal"


class DirecaoDedos(Enum):
  CIMA = "cima"
  BAIXO = "baixo"
  FRENTE = "frente"
  TRAS = "tras"
  DENTRO = "dentro"
  FORA = "fora"
  DIAGONAL = "diagonal"


class EstadoPorta(Enum):
  FECHADA = "fechada"  # abaixo de 5 graus
  FRESTA = "fresta"  # 5 a 15
  ENTREABERTA = "entreaberta"  # 15 a 45
  ABERTA = "aberta"  # 45 a 100
  ESCANCARADA = "escancarada"  # acima de 100


class OlharHorizontal(Enum):
  FRENTE = "frente"
  DIREITA = "direita"
  ESQUERDA = "esquerda"
  DIREITA_EXTREMA = "direita_extrema"
  ESQUERDA_EXTREMA = "esquerda_extrema"


class InclinacaoCabeca(Enum):
  RETA = "reta"
  DIREITA = "direita"
  ESQUERDA = "esquerda"


# --------------------------------------------------------------------------- #
# Hierarquia real e lado de cada parte
# --------------------------------------------------------------------------- #
#: Pai REAL de cada parte no GLTF (``None`` = filho da raiz).
#:
#: Correções ao documento: ``PORTA -> CABECA`` (não ``CORPO``); pés filhos da
#: raiz (``None``); ``PERNAS`` sem relação com os pés.
PAI_DE: dict[Parte, Parte | None] = {
  Parte.CORPO: None,
  Parte.CABECA: None,
  Parte.PORTA: Parte.CABECA,
  Parte.BRACO_DIREITO: None,
  Parte.OMBRO_DIREITO: Parte.BRACO_DIREITO,
  Parte.ANTEBRACO_DIREITO: Parte.BRACO_DIREITO,
  Parte.MAO_DIREITA: Parte.ANTEBRACO_DIREITO,
  Parte.DEDOS_DIREITA: Parte.MAO_DIREITA,
  Parte.BRACO_ESQUERDO: None,
  Parte.OMBRO_ESQUERDO: Parte.BRACO_ESQUERDO,
  Parte.ANTEBRACO_ESQUERDO: Parte.BRACO_ESQUERDO,
  Parte.MAO_ESQUERDA: Parte.ANTEBRACO_ESQUERDO,
  Parte.DEDOS_ESQUERDA: Parte.MAO_ESQUERDA,
  Parte.PERNAS: None,
  Parte.PE_ESQUERDO: None,
  Parte.PE_DIREITO: None,
}

#: Lado de cada parte, do ponto de vista do personagem (não da tela).
LADO_DE: dict[Parte, Lado] = {
  Parte.CORPO: Lado.CENTRO,
  Parte.CABECA: Lado.CENTRO,
  Parte.PORTA: Lado.CENTRO,
  Parte.BRACO_DIREITO: Lado.DIREITA,
  Parte.OMBRO_DIREITO: Lado.DIREITA,
  Parte.ANTEBRACO_DIREITO: Lado.DIREITA,
  Parte.MAO_DIREITA: Lado.DIREITA,
  Parte.DEDOS_DIREITA: Lado.DIREITA,
  Parte.BRACO_ESQUERDO: Lado.ESQUERDA,
  Parte.OMBRO_ESQUERDO: Lado.ESQUERDA,
  Parte.ANTEBRACO_ESQUERDO: Lado.ESQUERDA,
  Parte.MAO_ESQUERDA: Lado.ESQUERDA,
  Parte.DEDOS_ESQUERDA: Lado.ESQUERDA,
  Parte.PERNAS: Lado.CENTRO,
  Parte.PE_ESQUERDO: Lado.ESQUERDA,
  Parte.PE_DIREITO: Lado.DIREITA,
}


def pai_de(parte: Parte) -> Parte | None:
  """Pai real da parte no GLTF (``None`` se filho da raiz)."""
  return PAI_DE[parte]


def lado_de(parte: Parte) -> Lado:
  """Lado do personagem a que a parte pertence."""
  return LADO_DE[parte]


# --------------------------------------------------------------------------- #
# Direção classificada (seção 4.2)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Direcao:
  principal: DirecaoMundo  # eixo mais alinhado
  secundaria: DirecaoMundo  # segundo mais alinhado, ou INDEFINIDA
  alinhamento_norm: float  # cos do ângulo com o eixo principal, 0,0 a 1,0
  ambigua: bool  # True se principal e secundária quase empatam
  angulo_vertical_graus: float  # 0 = cima, 90 = horizontal, 180 = baixo
  azimute_graus: float  # giro no plano horizontal, 0 = frente, +90 = direita


# --------------------------------------------------------------------------- #
# Estado de uma parte (seção 4.3)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EstadoParte:
  parte: Parte
  lado: Lado
  pai: Parte | None
  validacao: Validacao

  # Rotação
  rot_local_graus: Vetor3  # HPR relativo ao pai
  rot_mundo_graus: Vetor3  # HPR absoluto
  desvio_repouso_graus: float  # ângulo total entre repouso e pose atual
  torcao_graus: float  # giro em torno do eixo longo

  # Vetores (um por entrada de VETORES_REFERENCIA)
  vetores_mundo: dict[str, Vetor3]
  direcoes: dict[str, Direcao]
  flags: dict[str, Enum]  # ex.: {"normal_palma": DirecaoPalma.PARA_CIMA}

  # Posição (campos sem família aceitam None)
  origem_mundo: Vetor3
  ponta_mundo: Vetor3 | None  # extremidade do membro
  comprimento_u: float | None
  altura_relativa: AlturaRelativa
  distancia_ao_eixo_central_u: float


# --------------------------------------------------------------------------- #
# Estado de uma articulação (seção 4.4)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EstadoArticulacao:
  nome: str  # "cotovelo_direito"
  lado: Lado
  segmento_proximal: Parte
  segmento_distal: Parte
  angulo_flexao_graus: float  # 0 = esticado
  angulo_min_graus: float
  angulo_max_graus: float
  proporcao_norm: float  # posição dentro de [min, max]
  estado: EstadoFlexao
  plano: PlanoFlexao
  torcao_graus: float  # giro relativo entre os dois segmentos
  fora_do_limite: bool  # True se passou de min ou max


# --------------------------------------------------------------------------- #
# Dinâmica, relações, postura e relatório (seção 4.5)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DinamicaParte:
  parte: Parte
  velocidade_angular_graus_s: float
  velocidade_linear_u_s: float
  aceleracao_angular_graus_s2: float
  sentido_vertical: SentidoMovimento
  sentido_giro: SentidoMovimento
  parado_ha_s: float  # tempo sem mover acima do ruído
  fase_ciclo_norm: float | None  # 0,0 a 1,0 em movimentos periódicos


@dataclass(frozen=True)
class Relacao:
  nome: str  # "distancia_mao_direita_cabeca"
  valor: float | bool
  unidade: str  # "u", "graus", "bool"
  partes: tuple[Parte, ...]


@dataclass(frozen=True)
class Postura:
  """Resumo do corpo todo (seção 8.3).

  Fundação: só os campos estruturais usados pelas Fases 1-3. Campos de gesto e
  tentáculos entram nas fases posteriores, por isso aceitam None aqui.
  """

  tronco_inclinacao_cabeca: InclinacaoCabeca
  estado_porta: EstadoPorta
  simetria_norm: float | None = None
  expansao_norm: float | None = None
  equilibrio_norm: float | None = None
  energia_norm: float | None = None


@dataclass(frozen=True)
class RelatorioRig:
  t_s: float
  pose: str
  partes: dict[Parte, EstadoParte]
  articulacoes: dict[str, EstadoArticulacao]
  dinamica: dict[Parte, DinamicaParte]
  relacoes: dict[str, Relacao]
  postura: Postura  # resumo do corpo todo (seção 8)
  descricao: str  # frase em linguagem natural


# --------------------------------------------------------------------------- #
# Referências do corpo e definição de articulação (seções 5.4 e 6.6)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ReferenciasCorpo:
  """Alturas de referência medidas uma vez no repouso (seção 5.4)."""

  y_chao: float
  y_cintura: float
  y_peito: float
  y_ombro: float
  y_cabeca: float
  y_topo: float


@dataclass(frozen=True)
class DefinicaoArticulacao:
  """Registro estático de uma articulação (seção 6.6)."""

  nome: str
  tipo: TipoArticulacao
  segmento_proximal: Parte
  segmento_distal: Parte
  angulo_min_graus: float
  angulo_max_graus: float
  sinal_natural: float  # +1 ou -1: sentido natural da dobra
  eixo: Vetor3  # eixo local da dobra (dobradiça/pivô)


# --------------------------------------------------------------------------- #
# Aliases das flags antigas (seções 11.5 e 12.4)
# --------------------------------------------------------------------------- #
#: Mapa das flags de texto antigas para os Enums novos. Mantém compatibilidade
#: com saídas e testes atuais durante a migração.
ALIASES_FLAG: dict[str, Enum] = {
  # Palma (seção 7.1 / 12.4)
  "PALMA_PARA_CIMA": DirecaoPalma.PARA_CIMA,
  "PALMA_PARA_BAIXO": DirecaoPalma.PARA_BAIXO,
  "PALMA_PARA_FRENTE": DirecaoPalma.PARA_FRENTE,
  "PALMA_PARA_TRAS": DirecaoPalma.PARA_TRAS,
  "PALMA_PARA_DENTRO": DirecaoPalma.PARA_DENTRO,
  "PALMA_PARA_FORA": DirecaoPalma.PARA_FORA,
  # Dedos (seção 7.1 / 12.4)
  "DEDOS_CIMA": DirecaoDedos.CIMA,
  "DEDOS_BAIXO": DirecaoDedos.BAIXO,
  "DEDOS_FRENTE": DirecaoDedos.FRENTE,
  "DEDOS_TRAS": DirecaoDedos.TRAS,
  "DEDOS_DENTRO": DirecaoDedos.DENTRO,
  "DEDOS_FORA": DirecaoDedos.FORA,
  "DEDOS_ESQUERDA": DirecaoDedos.DENTRO,  # vira relativo ao corpo
  # Porta (seção 7.3 / 12.4)
  "PORTA_FECHADA": EstadoPorta.FECHADA,
  "PORTA_FRESTA": EstadoPorta.FRESTA,
  "PORTA_ENTREABERTA": EstadoPorta.ENTREABERTA,
  "PORTA_ABERTA": EstadoPorta.ABERTA,
  "PORTA_ESCANCARADA": EstadoPorta.ESCANCARADA,
  # Olhar da cabeça (seção 7.2 / 12.4)
  "OLHAR_FRENTE": OlharHorizontal.FRENTE,
  "OLHAR_DIREITA": OlharHorizontal.DIREITA,
  "OLHAR_ESQUERDA": OlharHorizontal.ESQUERDA,
  # Inclinação da cabeça (seção 7.2 / 12.4)
  "TOPO_CIMA": InclinacaoCabeca.RETA,
  "TOPO_DIREITA": InclinacaoCabeca.DIREITA,
  "TOPO_ESQUERDA": InclinacaoCabeca.ESQUERDA,
}


def resolver_alias(texto: str) -> Enum:
  """Resolve uma flag antiga para o Enum novo correspondente.

  Raises:
      KeyError: se a flag for desconhecida (mensagem com o texto recebido).
  """
  try:
    return ALIASES_FLAG[texto]
  except KeyError as erro:
    raise KeyError(f"flag antiga desconhecida: {texto!r}") from erro
