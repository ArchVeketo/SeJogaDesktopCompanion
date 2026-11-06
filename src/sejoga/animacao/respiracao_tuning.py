"""Parâmetros de respiração por personalidade (engine-agnóstico).

Centraliza, em um único lugar, a "assinatura" da respiração de cada
personalidade de idle: com que frequência o peito infla, o quanto infla
(amplitude) e quanto balanço a mola deixa sobrar (bounce). Espelha o estilo de
``spring_tuning.py``: uma entrada por valor de ``rig.IdlePersonality``, com
``PADRAO`` de fallback e uma guarda que falha cedo se faltar cobertura.

Sem depender de Panda3D, Qt ou Win32. Este é o lugar para o usuário calibrar o
ritmo da respiração de cada personalidade.
"""

from __future__ import annotations

from dataclasses import dataclass

from sejoga.nucleo.rig import IdlePersonality


@dataclass(frozen=True, slots=True)
class ParametrosRespiracao:
  """Assinatura de respiração de uma personalidade.

  - ``frequencia``: ciclos por segundo do oscilador lento (maior = respira
    mais rápido/ofegante; menor = calmo).
  - ``amplitude``: 0..1; o quanto o peito infla a cada ciclo.
  - ``bounce``: 0..1; folga de oscilação da mola (menor = assenta seco,
    maior = sobra um balanço perceptível). Vira ``1 - amortecimento`` na mola.
  """

  frequencia: float
  amplitude: float
  bounce: float


#: Parâmetro de fallback para personalidade sem entrada explícita. Ritmo calmo
#: e discreto, igual ao default de ``Respiracao`` (0.25 Hz, amplitude cheia).
PADRAO = ParametrosRespiracao(frequencia=0.25, amplitude=1.0, bounce=0.15)


#: Uma entrada por valor de ``rig.IdlePersonality`` (as 9). Valores de PARTIDA;
#: este é o ponto de calibração do usuário. A ideia por trás dos números:
#: parado/tímido respira devagar e raso; agitado/ritmado respira mais rápido e
#: fundo, com um pouco mais de balanço.
RESPIRACAO_POR_PERSONALIDADE: dict[IdlePersonality, ParametrosRespiracao] = {
  # Calmo: respiração base, lenta e assentada.
  IdlePersonality.CALM: ParametrosRespiracao(frequencia=0.24, amplitude=0.9, bounce=0.12),
  # Curioso: um pouco mais atento, respiração levemente mais rápida.
  IdlePersonality.CURIOUS: ParametrosRespiracao(frequencia=0.30, amplitude=0.85, bounce=0.18),
  # Brincalhão: agitado, respira rápido e fundo com balanço.
  IdlePersonality.PLAYFUL: ParametrosRespiracao(frequencia=0.40, amplitude=1.0, bounce=0.28),
  # Tímido: encolhido, respiração curta e rasa.
  IdlePersonality.SHY: ParametrosRespiracao(frequencia=0.22, amplitude=0.7, bounce=0.10),
  # Confiante: peito estufado, respiração ampla e firme.
  IdlePersonality.CONFIDENT: ParametrosRespiracao(frequencia=0.26, amplitude=1.0, bounce=0.14),
  # Street: cadência descolada, média e com balanço leve.
  IdlePersonality.STREET: ParametrosRespiracao(frequencia=0.32, amplitude=0.9, bounce=0.22),
  # Fighter: pronto para ação, respiração rápida e controlada.
  IdlePersonality.FIGHTER: ParametrosRespiracao(frequencia=0.38, amplitude=0.95, bounce=0.16),
  # Rhythm: no compasso, respiração marcada e com balanço.
  IdlePersonality.RHYTHM: ParametrosRespiracao(frequencia=0.42, amplitude=0.9, bounce=0.30),
  # Stylish: posado e elegante, respiração ampla e tranquila.
  IdlePersonality.STYLISH: ParametrosRespiracao(frequencia=0.27, amplitude=0.95, bounce=0.15),
}


def parametros_de(personalidade: IdlePersonality | str) -> ParametrosRespiracao:
  """Devolve os parâmetros da personalidade, ou ``PADRAO`` se desconhecida."""
  try:
    chave = IdlePersonality(personalidade)
  except ValueError:
    return PADRAO

  return RESPIRACAO_POR_PERSONALIDADE.get(chave, PADRAO)


# Falha cedo se o rig ganhar uma personalidade sem entrada de respiração: a
# tabela precisa cobrir todas as personalidades de idle.
_faltando = tuple(p for p in IdlePersonality if p not in RESPIRACAO_POR_PERSONALIDADE)
if _faltando:
  raise RuntimeError(f"RESPIRACAO_POR_PERSONALIDADE sem entrada para: {_faltando}")
