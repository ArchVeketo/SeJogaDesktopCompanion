"""Mola criticamente amortecida parametrizada por meia-vida.

Implementa a solução exata de uma mola com amortecimento crítico (zeta = 1),
onde o único parâmetro de ajuste é a **meia-vida** — o tempo para cobrir metade
da distância restante. É mais intuitivo que frequência + zeta e não oscila.

Referência: ``docs/ESTUDO_ANIMACAO_PROCEDURAL.md``, seções 2.5 e 2.7.
Convenção Daniel Holden (Spring-It-On, GDC 2022).

FRONTEIRA: Python puro, sem engine.
"""

from __future__ import annotations

from math import exp, isfinite, log

# Valor mínimo somado à meia-vida para evitar divisão por zero quando
# ``meia_vida`` é exatamente 0.0. Suficientemente pequeno para não alterar
# o comportamento em valores práticos (> 0.001 s).
EPSILON_MEIA_VIDA: float = 1e-5


def meia_vida_para_amortecimento(meia_vida: float) -> float:
    """Converte meia-vida (s) no coeficiente de amortecimento da mola crítica.

    O coeficiente devolvido é ``d = 4 ln(2) / (meia_vida + ε)``, onde
    ``ε = EPSILON_MEIA_VIDA`` protege contra meia-vida zero.
    """
    return (4.0 * log(2.0)) / (meia_vida + EPSILON_MEIA_VIDA)


def avancar_mola_critica(
    valor: float,
    velocidade: float,
    alvo: float,
    meia_vida: float,
    dt: float,
) -> tuple[float, float]:
    """Avança uma mola criticamente amortecida pela solução exata.

    Devolve ``(novo_valor, nova_velocidade)``. Sem overshoot por construção.

    A solução é ``x(t) = (j0 + j1·t)·e^(-y·t) + alvo`` com
    ``j0 = valor - alvo`` e ``j1 = velocidade + j0·y``, logo
    ``v(t) = e^(-y·t)·(velocidade - j1·y·t)``.

    Parâmetros
    ----------
    valor:
        Posição atual da mola.
    velocidade:
        Velocidade atual da mola.
    alvo:
        Valor-alvo que a mola persegue.
    meia_vida:
        Tempo (s) para cobrir metade da distância restante.
    dt:
        Delta time em segundos. Se ``<= 0``, devolve ``(valor, velocidade)``
        sem avançar.
    """
    if not isfinite(dt) or dt <= 0:
        return valor, velocidade
    y = meia_vida_para_amortecimento(meia_vida) / 2.0
    j0 = valor - alvo
    j1 = velocidade + j0 * y
    decaimento = exp(-y * dt)
    novo_valor = decaimento * (j0 + j1 * dt) + alvo
    nova_velocidade = decaimento * (velocidade - j1 * y * dt)
    return novo_valor, nova_velocidade


def suavizar_exato(valor: float, alvo: float, meia_vida: float, dt: float) -> float:
    """Aproxima o valor do alvo por decaimento exponencial, igual em qualquer FPS.

    Equivale a um ``lerp(valor, alvo, fator)`` cujo ``fator`` é derivado da
    meia-vida e do dt, sem depender do framerate. Não mantém velocidade
    própria — muda de sentido imediatamente quando o alvo inverte.

    Use ``avancar_mola_critica`` quando precisar de continuidade de
    velocidade (olhar, cursor, membros).

    Parâmetros
    ----------
    valor:
        Valor atual.
    alvo:
        Valor-alvo.
    meia_vida:
        Tempo (s) para cobrir metade da distância restante.
    dt:
        Delta time em segundos. Se ``<= 0``, devolve ``valor`` sem avançar.
    """
    if not isfinite(dt) or dt <= 0:
        return valor
    fator = 1.0 - exp(-(log(2.0) * dt) / (meia_vida + EPSILON_MEIA_VIDA))
    return valor + (alvo - valor) * fator
