"""Limiares calibráveis da física de tela (sem engine/Win32).

Centraliza os números que um humano calibra "no olho" da física de arremesso,
quique e apoio em prateleiras, separados da lógica em ``fisica.py``. Os valores
são os de hoje (não mudar o comportamento): este módulo apenas dá nome e um só
lugar ao que estava inline.

Divisão de responsabilidade:

- ``configuracao.py`` já é a fonte de ``gravity``, ``mass``, ``bounce``, ``friction``,
  ``throw_multiplier``, ``mascot_radius`` e ``wall_thickness``. Não duplicar
  aqui: ``fisica.py`` consome do ``settings``.
- Constantes estruturais já nomeadas no topo de ``fisica.py`` (``FIXED_DT``,
  ``MAX_SUBSTEPS``, ``MAX_VELOCITY``, ``DEFAULT_GRAVITY``, ``DRAG``,
  ``WALL_THICKNESS``, ``SHELF_CACHE_TTL``, ``SHELF_REFRESH_DISTANCE``, ``CAT_*``,
  ``DWMWA_*``) ficam lá.
- Aqui moram os LIMIARES calibráveis que estavam como literais soltos nos
  solvers de colisão, no estado de apoio e na estimativa de arremesso.

Módulo puro: não importa Panda3D, Qt nem Win32, para poder ser calibrado e
testado sem janela real.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FisicaTuning:
    """Tabela de limiares calibráveis da física de tela.

    Todos em unidades de tela (px, px/s) ou segundos, salvo indicação. Os nomes
    explicam o PORQUÊ do valor, não só o quê.
    """

    # --- Pass-through das prateleiras (one-way, só a aresta superior) -----
    #: Velocidade vertical mínima (px/s) para considerar o corpo "não descendo":
    #: subindo ou quase parado atravessa a prateleira de baixo para cima.
    #: vy >= este valor (negativo = subindo na tela y-para-baixo) → passa.
    PASSAGEM_VY_SUBINDO: float = -1.0
    #: Folga (px) abaixo da aresta da prateleira em que o corpo ainda é
    #: considerado "por cima": evita grudar quando aflora pela borda.
    PASSAGEM_FOLGA_TOPO: float = 6.0

    # --- Resposta de impacto (restituição e evento sonoro) ---------------
    #: Abaixo desta velocidade (px/s) o contato não quica (restituição zero):
    #: assenta seco em vez de tremer em micro-saltos.
    IMPACTO_VELOCIDADE_SEM_QUIQUE: float = 160.0
    #: Acima desta velocidade (px/s) o contato dispara o evento "impact".
    IMPACTO_VELOCIDADE_EVENTO: float = 200.0
    #: Janela mínima (s) entre dois eventos de impacto: evita spam sonoro.
    IMPACTO_COOLDOWN: float = 0.2

    # --- Elasticidade/atrito das bordas estáticas (tela e prateleiras) ----
    #: Restituição das arestas estáticas; quique discreto nas bordas.
    BORDA_ELASTICIDADE: float = 0.25
    #: Atrito das arestas estáticas; segura o corpo ao assentar.
    BORDA_ATRITO: float = 1.0

    # --- Estado de apoio (grounded) --------------------------------------
    #: Componente vertical mínima da normal de contato (0..1) para o contato
    #: contar como "apoio por baixo"; abaixo disso é toque lateral.
    APOIO_NORMAL_MINIMA: float = 0.65
    #: Velocidade vertical (px/s) abaixo da qual o corpo pode ser considerado
    #: apoiado: acima disso ainda está caindo/subindo.
    APOIO_VY_MAXIMA: float = 60.0

    # --- Assentamento no apoio (freia o deslize residual) ----------------
    #: Abaixo desta velocidade horizontal (px/s) o corpo apoiado trava em 0:
    #: elimina o micro-deslize eterno no chão.
    ASSENTAMENTO_VX_MINIMA: float = 5.0
    #: Fator que multiplica o atrito no decaimento exponencial da velocidade
    #: horizontal quando apoiado (quanto maior, mais rápido assenta).
    ASSENTAMENTO_FATOR_ATRITO: float = 8.0

    # --- Estimativa de velocidade do arremesso ---------------------------
    #: Janela (s) de amostras recentes usada para estimar a velocidade do
    #: arremesso: segurar parado antes de soltar zera o arremesso.
    ARREMESSO_JANELA_AMOSTRAS: float = 0.06
    #: Nº máximo de amostras (t, x, y) guardadas durante o arraste.
    ARREMESSO_MAX_AMOSTRAS: int = 10

    # --- Integração temporal ---------------------------------------------
    #: Teto do dt (s) por frame antes de acumular passos fixos: evita um salto
    #: gigante de simulação após um stall da aplicação.
    DT_MAXIMO: float = 0.05


#: Instância única consumida por ``fisica.py``.
FISICA = FisicaTuning()
