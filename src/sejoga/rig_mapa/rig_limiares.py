"""Limiares e classificadores genéricos do mapeamento do rig.

Centraliza todos os números que viram flags (seção 10 do documento
``docs/Mapeamento Completo do Corpo do Rig Detecção e Nomenclatura.md``).
Regra de ouro: nenhum número mágico dentro de ``classificar_*``; tudo vem de
``Limiares``. Python puro, sem engine.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import atan2, degrees, sqrt
from typing import TypeVar

from sejoga.rig_mapa.rig_mapa import Direcao, DirecaoMundo, Vetor3

E = TypeVar("E")


# --------------------------------------------------------------------------- #
# Limiares (seção 10.1)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Limiares:
  # Direção
  alinhamento_min_norm: float = 0.80
  margem_ambiguidade: float = 0.15
  norma_min: float = 1e-6
  # Flexão (graus)
  esticado_ate_graus: float = 15.0
  leve_ate_graus: float = 45.0
  dobrado_ate_graus: float = 110.0
  tolerancia_limite_graus: float = 2.0
  # Porta (graus)
  porta_fechada_ate: float = 5.0
  porta_fresta_ate: float = 15.0
  porta_entreaberta_ate: float = 45.0
  porta_aberta_ate: float = 100.0
  # Cabeça (graus)
  olhar_frente_graus: float = 15.0
  olhar_extremo_graus: float = 60.0
  olhar_nivel_graus: float = 10.0
  cabeca_reta_graus: float = 8.0
  alvo_olhar_graus: float = 25.0
  # Distâncias relativas à altura em pé
  mao_rosto_rel: float = 0.18
  maos_unidas_rel: float = 0.08
  tolerancia_chao_rel: float = 0.02
  # Dinâmica
  parado_entrar_graus_s: float = 5.0
  parado_sair_graus_s: float = 8.0
  suavizacao_velocidade: float = 0.30
  aceno_hz_min: float = 1.0
  aceno_hz_max: float = 4.0
  aceno_amplitude_graus: float = 20.0
  # Tronco
  tronco_inclinado_graus: float = 12.0
  agachado_norm: float = 0.25
  deitado_graus: float = 60.0


#: Instância com os valores propostos da seção 10.1.
LIMIARES_PADRAO = Limiares()


# --------------------------------------------------------------------------- #
# Limites de amplitude das articulações (seção 6.6)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LimiteJunta:
  """Amplitude calibrável de uma articulação, em graus de flexão assinada.

  ``minimo`` negativo admite hiperextensão; ``maximo`` é a dobra máxima natural.
  São os valores que o usuário calibra por junta (o quanto cada articulação do
  rig pode fletir antes de ``fora_do_limite``); ficam aqui, fora do catálogo de
  ``rig_articulacoes``, para serem ajustados sem mexer na lógica.
  """

  minimo: float
  maximo: float


#: Cotovelo (dobradiça braço->antebraço): quase esticado para trás (-10) até bem
#: dobrado para a frente (150). Igual nos dois lados.
LIMITE_COTOVELO = LimiteJunta(minimo=-10.0, maximo=150.0)

#: Ombro (esférica corpo->braço): recua um pouco atrás do tronco (-60) e sobe
#: até acima da cabeça (180). Igual nos dois lados.
LIMITE_OMBRO = LimiteJunta(minimo=-60.0, maximo=180.0)

#: Punho (esférica antebraço->mão): flexão/extensão do pulso (-70 a 80). Igual
#: nos dois lados.
LIMITE_PUNHO = LimiteJunta(minimo=-70.0, maximo=80.0)

#: Pescoço (pivô corpo->cabeça): giro simétrico para os dois lados (-80 a 80).
LIMITE_PESCOCO = LimiteJunta(minimo=-80.0, maximo=80.0)

#: Dobradiça da porta (cabeça->porta): só abre para a frente, de fechada (0) a
#: escancarada (120). O limite de velocidade de abertura é tratado na animação.
LIMITE_PORTA = LimiteJunta(minimo=0.0, maximo=120.0)


# --------------------------------------------------------------------------- #
# Classificadores genéricos (seção 10.3)
# --------------------------------------------------------------------------- #
def classificar_por_faixas(
  valor: float,
  faixas: Sequence[tuple[float, E]],  # (limite_superior, estado), em ordem crescente
  acima: E,
) -> E:
  """Retorna o estado da primeira faixa cujo limite cobre ``valor``.

  As faixas vêm em ordem crescente de limite; ``acima`` é o estado usado quando
  o valor ultrapassa todos os limites.
  """
  for limite, estado in faixas:
    if valor <= limite:
      return estado
  return acima


#: Eixos do mundo glTF e a direção correspondente (seção 2.4: +X=direita,
#: +Y=cima, +Z=frente).
_EIXOS_MUNDO: tuple[tuple[Vetor3, DirecaoMundo], ...] = (
  ((0.0, 1.0, 0.0), DirecaoMundo.CIMA),
  ((0.0, -1.0, 0.0), DirecaoMundo.BAIXO),
  ((0.0, 0.0, 1.0), DirecaoMundo.FRENTE),
  ((0.0, 0.0, -1.0), DirecaoMundo.TRAS),
  ((1.0, 0.0, 0.0), DirecaoMundo.DIREITA),
  ((-1.0, 0.0, 0.0), DirecaoMundo.ESQUERDA),
)


def classificar_direcao(vetor: Vetor3, limiares: Limiares) -> Direcao:
  """Classifica um vetor do mundo contra os seis eixos (seção 5.3/10.3).

  Escolhe o eixo de maior produto escalar como ``principal`` e o segundo como
  ``secundaria``; marca ``ambigua`` quando a diferença entre os dois maiores
  fica abaixo de ``margem_ambiguidade``. Vetor de norma quase nula vira
  ``INDEFINIDA``.
  """
  x, y, z = vetor
  norma = sqrt(x * x + y * y + z * z)

  if norma < limiares.norma_min:
    return Direcao(
      principal=DirecaoMundo.INDEFINIDA,
      secundaria=DirecaoMundo.INDEFINIDA,
      alinhamento_norm=0.0,
      ambigua=True,
      angulo_vertical_graus=0.0,
      azimute_graus=0.0,
    )

  ux, uy, uz = x / norma, y / norma, z / norma

  # Produto escalar com cada eixo, ordenado do mais alinhado ao menos.
  produtos = sorted(
    ((ex * ux + ey * uy + ez * uz, direcao) for (ex, ey, ez), direcao in _EIXOS_MUNDO),
    key=lambda par: par[0],
    reverse=True,
  )
  (melhor, principal), (segundo, secundaria) = produtos[0], produtos[1]

  ambigua = (melhor - segundo) < limiares.margem_ambiguidade
  if melhor < limiares.alinhamento_min_norm:
    ambigua = True

  # arccos(uy) sem importar math.acos extra: usa atan2 para estabilidade.
  angulo_vertical_graus = degrees(atan2(sqrt(ux * ux + uz * uz), uy))
  azimute_graus = degrees(atan2(ux, uz))

  return Direcao(
    principal=principal,
    secundaria=secundaria if segundo > 0.0 else DirecaoMundo.INDEFINIDA,
    alinhamento_norm=melhor,
    ambigua=ambigua,
    angulo_vertical_graus=angulo_vertical_graus,
    azimute_graus=azimute_graus,
  )
