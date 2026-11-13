"""Arcos autorais para idle: lemniscata (figura de 8) em vez de senoides.

Manifesto §2.3 (Princípio 7 — Arcos):
"Cabeça e torso traçam uma suave lemniscata (arco em 'figura de 8'),
nunca um sobe-e-desce linear robótico."

Os braços descrevem arcos suaves, não oscilações lineares.

A lemniscata de Bernoulli é parametrizada por:
  x(t) = A * sin(t) / (1 + cos²(t))
  y(t) = A * sin(t) * cos(t) / (1 + cos²(t))

Mas para animação, usamos uma aproximação mais simples e controlável:
  x(t) = A_x * sin(f * t)
  y(t) = A_y * sin(2 * f * t + fase)

Que produz uma figura de 8 quando as frequências estão em razão 1:2.

FRONTEIRA: Python puro, sem engine.
"""

from __future__ import annotations

import math


def lemniscata(
    t: float,
    frequencia: float = 0.3,
    amplitude_x: float = 1.0,
    amplitude_y: float = 1.0,
    fase: float = 0.0,
) -> tuple[float, float]:
    """Devolve as coordenadas (x, y) de uma lemniscata suave.

    A curva traça uma figura de 8 contínua no plano XY. A frequência controla
    a velocidade do traçado; as amplitudes controlam o tamanho em cada eixo.

    Parameters
    ----------
    t:
        Tempo em segundos.
    frequencia:
        Frequência do traçado em Hz (ciclos por segundo).
    amplitude_x:
        Amplitude no eixo X (graus).
    amplitude_y:
        Amplitude no eixo Y (graus).
    fase:
        Deslocamento de fase em radianos.

    Returns
    -------
    (x, y) em graus.
    """
    theta = 2.0 * math.pi * frequencia * t + fase
    # Lemniscata: x usa frequência fundamental, y usa o dobro
    x = amplitude_x * math.sin(theta) / (1.0 + math.cos(theta) ** 2)
    y = amplitude_y * math.sin(theta) * math.cos(theta) / (1.0 + math.cos(theta) ** 2)
    return x, y


def arco_braço(
    t: float,
    frequencia: float = 0.3,
    amplitude: float = 1.0,
    fase: float = 0.0,
) -> float:
    """Devolve a posição de um braço descrevendo um arco suave.

    O braço não oscila linearmente — ele descreve um arco circular suave
    no espaço 3D, como um pêndulo natural.

    Parameters
    ----------
    t:
        Tempo em segundos.
    frequencia:
        Frequência do arco em Hz.
    amplitude:
        Amplitude do arco em graus.
    fase:
        Deslocamento de fase em radianos.

    Returns
    -------
    Posição do arco em graus.
    """
    theta = 2.0 * math.pi * frequencia * t + fase
    # Arco suave: seno com harmônicos para dar organicidade
    return (
        amplitude * math.sin(theta)
        + amplitude * 0.3 * math.sin(2.0 * theta + 0.5)
        + amplitude * 0.15 * math.sin(3.0 * theta + 1.2)
    )


def arco_cabeca_torso(
    t: float,
    frequencia: float = 0.25,
    amplitude_pitch: float = 2.0,
    amplitude_yaw: float = 3.0,
    amplitude_roll: float = 1.5,
    fase: float = 0.0,
) -> tuple[float, float, float]:
    """Devolve (pitch, yaw, roll) da cabeça/torso traçando lemniscata.

    A cabeça e o torso não sobem e descem linearmente — eles traçam uma
    suave figura de 8 no espaço 3D, combinando pitch e yaw em lemniscata
    e roll como harmônico suave.

    Parameters
    ----------
    t:
        Tempo em segundos.
    frequencia:
        Frequência do traçado em Hz.
    amplitude_pitch:
        Amplitude do pitch (inclinação frente/trás) em graus.
    amplitude_yaw:
        Amplitude do yaw (rotação lateral) em graus.
    amplitude_roll:
        Amplitude do roll (inclinação lateral) em graus.
    fase:
        Deslocamento de fase em radianos para defasagem em cascata.

    Returns
    -------
    (pitch, yaw, roll) em graus.
    """
    # Lemniscata no plano pitch-yaw com fase para cascata
    pitch, yaw = lemniscata(
        t,
        frequencia=frequencia,
        amplitude_x=amplitude_pitch,
        amplitude_y=amplitude_yaw,
        fase=fase,
    )
    # Roll como harmônico suave (metade da frequência, defasado)
    roll = amplitude_roll * math.sin(
        math.pi * frequencia * t + math.pi / 4 + fase
    )
    return pitch, yaw, roll


def arco_braço_par(
    t: float,
    frequencia: float = 0.25,
    amplitude_direito: float = 3.0,
    amplitude_esquerdo: float = 3.0,
    defasagem: float = math.pi / 2,
) -> tuple[float, float]:
    """Devolve as posições dos dois braços descrevendo arcos assimétricos.

    Os braços não oscilam em sincronia — eles descrevem arcos suaves com
    defasagem, como um corpo em repouso natural.

    Parameters
    ----------
    t:
        Tempo em segundos.
    frequencia:
        Frequência do arco em Hz.
    amplitude_direito:
        Amplitude do braço direito em graus.
    amplitude_esquerdo:
        Amplitude do braço esquerdo em graus.
    defasagem:
        Defasagem entre os braços em radianos.

    Returns
    -------
    (braço_direito, braço_esquerdo) em graus.
    """
    direito = arco_braço(t, frequencia, amplitude_direito, fase=0.0)
    esquerdo = arco_braço(t, frequencia, amplitude_esquerdo, fase=defasagem)
    return direito, esquerdo


def idle_arco_composto(
    t: float,
    frequencia_base: float = 0.20,
) -> dict[str, tuple[float, float, float]]:
    """Devolve deltas de rotação para todos os grupos do rig usando arcos autorais.

    Substitui as senoides simples do idle base por arcos suaves:
    - Cabeça e torso traçam lemniscata (figura de 8) contida e aterrada
    - Braços descrevem arcos assimétricos suaves com defasagem
    - Cotovelos acompanham com harmônicos

    Manifesto §2.3: todos os 12 princípios operam simultaneamente.
    Princípio 5 (Sobreposição): cascata de fase de torso → cabeça → braços → cotovelos.
    Princípio 7 (Arcos): lemniscata suave, mantendo equilíbrio aterrado.
    Princípio 10 (Exagero): amplitudes calibradas para peso vivo sem bamboleio excessivo.

    Parameters
    ----------
    t:
        Tempo do clock de idle (segundos).
    frequencia_base:
        Frequência base dos arcos em Hz.

    Returns
    -------
    Dicionário com deltas (pitch, yaw, roll) em graus por grupo do rig.
    """
    # ── Princípio 5: Sobreposição em cascata ──
    # Torso é a raiz do movimento; cada elo seguinte atrasa de forma natural.

    # Torso: lemniscata sutil e aterrada — peso estável sobre os pés
    body_pitch, body_yaw, body_roll = arco_cabeca_torso(
        t,
        frequencia=frequencia_base,
        amplitude_pitch=1.6,
        amplitude_yaw=2.2,
        amplitude_roll=1.4,
        fase=0.0,  # Torso é a referência (fase 0)
    )

    # Cabeça: lemniscata suave defasada do torso — follow-through vivo sem tombo
    head_pitch, head_yaw, head_roll = arco_cabeca_torso(
        t,
        frequencia=frequencia_base,
        amplitude_pitch=2.4,
        amplitude_yaw=3.2,
        amplitude_roll=1.8,
        fase=math.pi / 4,  # Atraso orgânico em relação ao torso
    )

    # Braços: arcos assimétricos contidos — balanço natural de repouso
    braço_dir, braço_esq = arco_braço_par(
        t,
        frequencia=frequencia_base,
        amplitude_direito=3.5,
        amplitude_esquerdo=2.8,
        defasagem=math.pi / 2,  # Braços opostos
    )

    # Cotovelos: harmônico dos braços — follow-through em cascata
    cotovelo_dir = arco_braço(
        t,
        frequencia=frequencia_base * 1.2,
        amplitude=3.2,
        fase=math.pi / 3,  # Atraso adicional
    )
    cotovelo_esq = arco_braço(
        t,
        frequencia=frequencia_base * 1.2,
        amplitude=3.2,
        fase=math.pi / 3 + math.pi / 2,
    )

    # Punhos: ação secundária (Princípio 8) — micro-movimento em cascata
    punho_dir = arco_braço(
        t,
        frequencia=frequencia_base * 1.4,
        amplitude=2.6,
        fase=math.pi / 2,
    )
    punho_esq = arco_braço(
        t,
        frequencia=frequencia_base * 1.4,
        amplitude=2.6,
        fase=math.pi / 2 + math.pi / 2,
    )

    return {
        "body": (body_pitch, body_yaw, body_roll),
        "head": (head_pitch, head_yaw, head_roll),
        "right-arm": (braço_dir, 0.0, 0.0),
        "left-arm": (braço_esq, 0.0, 0.0),
        "ant-arm": (cotovelo_dir, 0.0, 0.0),
        "ant-arm2": (cotovelo_esq, 0.0, 0.0),
        "hand": (0.0, 0.0, punho_dir),
        "hand2": (0.0, 0.0, punho_esq),
    }
