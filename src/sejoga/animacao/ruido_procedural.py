"""Ruído senoidal incomensurável e micro-movimentos para dar vida ao rig (sem engine).

Implementa o oscilador de soma de senos com frequências irracionais entre si
(``docs/ESTUDO_ANIMACAO_PROCEDURAL.md`` §4.5) e a distribuição de torção/inclinação
pelos novos nós do rig (``cintura``, ``abdomen``, ``peitoral``, ``fones``,
``fone-direito``, ``fone-esquerdo``, ``antena-direita``, ``antena-esquerda``).
"""

from __future__ import annotations

from math import radians, sin, tau

from sejoga.nucleo.esqueleto import Rotation3

#: Razões incomensuráveis entre si: o padrão não repete cedo (estudo §4.5).
RAZOES_RUIDO: tuple[float, float, float] = (1.0, 2.3, 4.1)
#: Pesos decrescentes por harmônico inarmônico.
PESOS_RUIDO: tuple[float, float, float] = (1.0, 0.5, 0.25)
_SOMA_PESOS_RUIDO: float = sum(PESOS_RUIDO)

#: Frequência base (Hz) do micro-movimento orgânico no idle.
FREQUENCIA_BASE_MICRO_HZ = 0.22

#: Sementes fixas e distintas por junta/eixo para evitar sincronismo robótico.
SEMENTE_CINTURA = 1.13
SEMENTE_ABDOMEN = 2.47
SEMENTE_PEITORAL = 3.89
SEMENTE_CABECA = 5.21
SEMENTE_FONES = 6.73
SEMENTE_ANTENA_DIR = 8.17
SEMENTE_ANTENA_ESQ = 9.61

#: Amplitudes máximas (graus) do micro-ruído no estado idle.
AMP_MICRO_CINTURA_GRAUS = (0.35, 0.55, 0.30)
AMP_MICRO_ABDOMEN_GRAUS = (0.45, 0.70, 0.40)
AMP_MICRO_PEITORAL_GRAUS = (0.60, 0.90, 0.50)
AMP_MICRO_FONES_GRAUS = (0.30, 0.25, 0.35)
AMP_MICRO_ANTENA_GRAUS = (1.40, 0.90, 1.80)

#: Frações de distribuição da torção/inclinação do tronco pelos 3 segmentos
#: internos (``cintura -> abdomen -> peitoral``) para curvar a coluna suavemente.
FRACAO_COLUNA_CINTURA = 0.20
FRACAO_COLUNA_ABDOMEN = 0.35
FRACAO_COLUNA_PEITORAL = 0.45


def calcular_ruido(tempo: float, semente: float) -> float:
    """Ruído suave em ``[-1, 1]`` por soma de senos incomensuráveis (estudo §4.5)."""
    total = sum(
        peso * sin(tau * razao * tempo + semente * (indice + 1))
        for indice, (razao, peso) in enumerate(
            zip(RAZOES_RUIDO, PESOS_RUIDO, strict=True)
        )
    )
    return total / _SOMA_PESOS_RUIDO


def _ruido_3d_rad(
    tempo_escalado: float,
    semente: float,
    amplitudes_graus: tuple[float, float, float],
) -> Rotation3:
    ax, ay, az = amplitudes_graus
    return Rotation3(
        radians(ax * calcular_ruido(tempo_escalado, semente)),
        radians(ay * calcular_ruido(tempo_escalado, semente + 1.7)),
        radians(az * calcular_ruido(tempo_escalado, semente + 3.3)),
    )


def delta_micro_ruido_idle(
    tempo: float, escala: float = 1.0
) -> dict[str, Rotation3]:
    """Calcula micro-oscilações orgânicas (radianos) para a coluna, fones e antenas."""
    if escala <= 0.0:
        return {}
    t_freq = tempo * FREQUENCIA_BASE_MICRO_HZ
    escala_lim = max(0.0, min(2.0, escala))

    def _amp(base: tuple[float, float, float]) -> tuple[float, float, float]:
        return (base[0] * escala_lim, base[1] * escala_lim, base[2] * escala_lim)

    return {
        "cintura": _ruido_3d_rad(t_freq, SEMENTE_CINTURA, _amp(AMP_MICRO_CINTURA_GRAUS)),
        "abdomen": _ruido_3d_rad(t_freq, SEMENTE_ABDOMEN, _amp(AMP_MICRO_ABDOMEN_GRAUS)),
        "peitoral": _ruido_3d_rad(t_freq, SEMENTE_PEITORAL, _amp(AMP_MICRO_PEITORAL_GRAUS)),
        "fones": _ruido_3d_rad(t_freq, SEMENTE_FONES, _amp(AMP_MICRO_FONES_GRAUS)),
        "antena-direita": _ruido_3d_rad(
            t_freq * 1.35, SEMENTE_ANTENA_DIR, _amp(AMP_MICRO_ANTENA_GRAUS)
        ),
        "antena-esquerda": _ruido_3d_rad(
            t_freq * 1.35, SEMENTE_ANTENA_ESQ, _amp(AMP_MICRO_ANTENA_GRAUS)
        ),
    }


def distribuir_coluna_tronco(rot_tronco: Rotation3) -> dict[str, Rotation3]:
    """Distribui um giro/inclinação em ``cintura``, ``abdomen`` e ``peitoral``."""
    return {
        "cintura": Rotation3(
            rot_tronco.x * FRACAO_COLUNA_CINTURA,
            rot_tronco.y * FRACAO_COLUNA_CINTURA,
            rot_tronco.z * FRACAO_COLUNA_CINTURA,
        ),
        "abdomen": Rotation3(
            rot_tronco.x * FRACAO_COLUNA_ABDOMEN,
            rot_tronco.y * FRACAO_COLUNA_ABDOMEN,
            rot_tronco.z * FRACAO_COLUNA_ABDOMEN,
        ),
        "peitoral": Rotation3(
            rot_tronco.x * FRACAO_COLUNA_PEITORAL,
            rot_tronco.y * FRACAO_COLUNA_PEITORAL,
            rot_tronco.z * FRACAO_COLUNA_PEITORAL,
        ),
    }
