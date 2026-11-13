"""Squash & Stretch por estado, com preservação de volume.

Manifesto §2.3: todos os 12 princípios operam simultaneamente. O Squash &
Stretch (princípio 1) é aplicado via escala anisotrópica não-uniforme nos nós
mestres (`body`, `head`, `pelvis`) do rig.

Regra de Ouro da Preservação de Volume: Sx * Sy * Sz ≈ 1.0
Ao comprimir o eixo vertical (Sz < 1), os eixos horizontais compensam
expandendo (Sx = Sy ≈ sqrt(1 / Sz)).

FRONTEIRA: Python puro, sem engine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SquashStretch:
    """Escala anisotrópica por eixo (multiplicativa sobre a escala base)."""

    x: float = 1.0
    y: float = 1.0
    z: float = 1.0


# --------------------------------------------------------------------------- #
# Parâmetros calibráveis (validar visualmente na GPU)
# --------------------------------------------------------------------------- #

# Respiração: amplitude de escala vertical — sutil e orgânica
RESPIRACAO_ESCALA_Z = 0.025

# Locomoção (caminhada/corrida) — squash & stretch equilibrado
# Compressão corporal ao absorver impacto na descida (down)
LOCOMOCAO_SQUASH_Z = 0.045
# Extensão e ganho de altura na passagem (up)
LOCOMOCAO_STRETCH_Z = 0.038
# Corrida tem amplitude maior sem virar borracha
LOCOMOCAO_CORRIDA_MULTIPLICADOR = 1.6

# Impacto / pouso (LAND) — squash firme e absorvido
IMPACTO_SQUASH_Z_MAX = 0.22

# Arraste — stretch proporcional à velocidade
ARRASTE_STRETCH_Z = 0.08
ARRASTE_SQUASH_XY = 0.04

# Queda — stretch aerodinâmico controlado
QUEDA_STRETCH_Z = 0.16
QUEDA_SQUASH_X = 0.06

# Sono — achatamento relaxado
SONO_SQUASH_Z = 0.045
SONO_RESPIRACAO_MULTIPLICADOR = 1.5

# Dança — compressão rítmica natural no downbeat
DANCA_SQUASH_Z = 0.052
DANCA_STRETCH_Z = 0.042


def preservar_volume(sx: float, sy: float, sz: float) -> tuple[float, float, float]:
    """Ajusta Sx e Sy para que Sx * Sy * Sz ≈ 1.0.

    Se Sz < 1 (squash vertical), Sx e Sy expandem.
    Se Sz > 1 (stretch vertical), Sx e Sy comprimem.
    """
    if sz <= 0:
        return 1.0, 1.0, 1.0
    # Sx * Sy = 1 / Sz  =>  Sx = Sy = sqrt(1 / Sz)
    compensacao = math.sqrt(1.0 / sz)
    return sx * compensacao, sy * compensacao, sz


def squash_stretch_respiracao(respiracao: float) -> SquashStretch:
    """Squash & Stretch da respiração autoral.

    Torso expande verticalmente (+2%) e afina nas laterais (-1%) ao inalar;
    afunda e alarga suavemente ao exalar.

    Parameters
    ----------
    respiracao:
        Valor centrado (-1..1) da respiração.

    Returns
    -------
    Escala multiplicativa (sobre a escala base do nó).
    """
    # respiracao > 0 = inalando (stretch Z, squash XY)
    # respiracao < 0 = exalando (squash Z, stretch XY)
    sz = 1.0 + respiracao * RESPIRACAO_ESCALA_Z
    sx, sy, _ = preservar_volume(1.0, 1.0, sz)
    return SquashStretch(sx, sy, sz)


def squash_stretch_locomocao(
    fase: float,
    run: bool = False,
) -> SquashStretch:
    """Squash & Stretch da locomoção (caminhada/corrida).

    Compressão corporal ao absorver impacto na descida (down);
    extensão e ganho de altura na passagem (up).

    Parameters
    ----------
    fase:
        Fase da passada (radianos). sin(fase) > 0 = perna subindo (up/stretch),
        sin(fase) < 0 = perna descendo (down/squash).
    run:
        Se True, corrida (amplitude maior).

    Returns
    -------
    Escala multiplicativa.
    """
    multi = LOCOMOCAO_CORRIDA_MULTIPLICADOR if run else 1.0

    # O corpo afunda duas vezes por ciclo (a cada apoio de pé)
    # cos(2*fase) dá dois picos por ciclo: -1 = impacto (squash), +1 = topo (stretch)
    impacto = math.cos(2.0 * fase)

    if impacto > 0:
        # Descendo: squash vertical
        sz = 1.0 - impacto * LOCOMOCAO_SQUASH_Z * multi
    else:
        # Subindo: stretch vertical
        sz = 1.0 + abs(impacto) * LOCOMOCAO_STRETCH_Z * multi

    sx, sy, _ = preservar_volume(1.0, 1.0, sz)
    return SquashStretch(sx, sy, sz)


def squash_stretch_impacto(tempo: float, duracao: float = 0.28) -> SquashStretch:
    """Squash no impacto/pouso (LAND).

    Achatamento de até 15% na vertical com alargamento lateral.
    Ataque rápido no contato (~50ms) seguido de recuperação elástica amortecida.

    Parameters
    ----------
    tempo:
        Tempo desde o impacto (segundos).
    duracao:
        Duração total do squash (segundos).

    Returns
    -------
    Escala multiplicativa.
    """
    if tempo <= 0:
        return SquashStretch()

    fase = tempo / duracao
    if fase >= 1.0:
        return SquashStretch()

    pico_fase = 0.18
    if fase <= pico_fase:
        envelope = math.sin((fase / pico_fase) * (math.pi * 0.5))
    else:
        t_rec = (fase - pico_fase) / (1.0 - pico_fase)
        envelope = math.exp(-3.2 * t_rec) * math.cos(math.pi * 1.5 * t_rec)

    # Squash vertical suave (evita achatar o peito contra as pernas; máx ~13%).
    sz = max(0.87, 1.0 - envelope * min(IMPACTO_SQUASH_Z_MAX, 0.13))

    sx, sy, _ = preservar_volume(1.0, 1.0, sz)
    return SquashStretch(sx, sy, sz)


def squash_stretch_arraste(
    velocidade: tuple[float, float] = (0.0, 0.0),
    intensidade: float = 0.0,
) -> SquashStretch:
    """Squash & Stretch durante arraste.

    Alongamento corporal ao longo do vetor de velocidade rápida do mouse (stretch);
    achatamento lateral compensatório.

    Parameters
    ----------
    velocidade:
        Velocidade do cursor (vx, vy) em px/s.
    intensidade:
        Intensidade do arraste suavizada (0..1).

    Returns
    -------
    Escala multiplicativa.
    """
    if intensidade <= 0.0:
        return SquashStretch()

    # Velocidade vertical determina stretch: arrastando para cima = stretch Z
    vy = velocidade[1] if len(velocidade) > 1 else 0.0
    velocidade_mag = math.hypot(*velocidade) if velocidade else 0.0

    # Normaliza velocidade (satura a ~1000 px/s)
    vel_norm = min(1.0, velocidade_mag / 1000.0)

    # Stretch vertical proporcional à velocidade e intensidade
    sz = 1.0 + vel_norm * intensidade * ARRASTE_STRETCH_Z

    # Se arrastando para baixo, inverte para squash
    if vy > 0:
        sz = 1.0 - vel_norm * intensidade * ARRASTE_STRETCH_Z * 0.5

    sx, sy, _ = preservar_volume(1.0, 1.0, sz)
    return SquashStretch(sx, sy, sz)


def squash_stretch_queda(
    velocidade: tuple[float, float] = (0.0, 0.0),
    tempo: float = 0.0,
) -> SquashStretch:
    """Squash & Stretch durante queda livre.

    Stretch vertical durante queda, squash horizontal pelo vento.

    Parameters
    ----------
    velocidade:
        Velocidade (vx, vy) em px/s.
    tempo:
        Tempo de queda (segundos).

    Returns
    -------
    Escala multiplicativa.
    """
    vy = velocidade[1] if len(velocidade) > 1 else 0.0
    vx = velocidade[0] if len(velocidade) > 0 else 0.0

    # Velocidade vertical determina stretch: mais rápido = mais esticado
    vel_norm = min(1.0, abs(vy) / 560.0)

    # Stretch vertical na queda
    sz = 1.0 + vel_norm * QUEDA_STRETCH_Z

    # Tumble horizontal afeta escala X
    tumble = min(1.0, abs(vx) / 600.0)
    sx = 1.0 - tumble * QUEDA_SQUASH_X

    sy, _, _ = preservar_volume(sx, 1.0, sz)
    return SquashStretch(sx, sy, sz)


def squash_stretch_sono(
    respiracao: float = 0.0,
    modo: str = "em_pe",
) -> SquashStretch:
    """Squash & Stretch no sono.

    Achatamento relaxado contra a superfície de apoio;
    expansão profunda e pesada na respiração do sono.

    Parameters
    ----------
    respiracao:
        Valor centrado (-1..1) da respiração lenta do sono.
    modo:
        "em_pe", "sentado" ou "deitado".

    Returns
    -------
    Escala multiplicativa.
    """
    # Base relaxada: leve squash vertical constante
    base_squash = SONO_SQUASH_Z

    # Respiração mais profunda no sono
    resp_amplitude = RESPIRACAO_ESCALA_Z * SONO_RESPIRACAO_MULTIPLICADOR

    # Deitado: mais squash (peso morto relaxado)
    if modo == "deitado":
        base_squash *= 1.5
    elif modo == "sentado":
        base_squash *= 1.2

    sz = 1.0 - base_squash + respiracao * resp_amplitude
    sx, sy, _ = preservar_volume(1.0, 1.0, sz)
    return SquashStretch(sx, sy, sz)


def squash_stretch_danca(
    fase_beat: float,
    intensidade: float = 0.5,
    bass: float = 0.0,
) -> SquashStretch:
    """Squash & Stretch na dança.

    Compressão rítmica no downbeat dando peso à batida;
    estiramento ágil no upbeat.

    Parameters
    ----------
    fase_beat:
        Fase dentro da batida (0..1). 0 = downbeat, 0.5 = upbeat.
    intensidade:
        Intensidade da música (0..1).
    bass:
        Intensidade do bass (0..1).

    Returns
    -------
    Escala multiplicativa.
    """
    # Downbeat (fase ~0): squash pesado
    # Upbeat (fase ~0.5): stretch ágil
    beat_pulse = math.cos(2.0 * math.pi * fase_beat)

    if beat_pulse > 0:
        # Downbeat: squash
        sz = 1.0 - beat_pulse * DANCA_SQUASH_Z * intensidade
    else:
        # Upbeat: stretch
        sz = 1.0 + abs(beat_pulse) * DANCA_STRETCH_Z * intensidade

    # Bass reforça o squash no downbeat
    if bass > 0.3 and beat_pulse > 0.5:
        sz -= (bass - 0.3) * 0.05

    sx, sy, _ = preservar_volume(1.0, 1.0, sz)
    return SquashStretch(sx, sy, sz)


def squash_stretch_composto(
    estado: str,
    respiracao: float = 0.0,
    fase_locomocao: float = 0.0,
    run: bool = False,
    impacto_tempo: float = 0.0,
    impacto_duracao: float = 0.45,
    arraste_velocidade: tuple[float, float] = (0.0, 0.0),
    arraste_intensidade: float = 0.0,
    queda_velocidade: tuple[float, float] = (0.0, 0.0),
    queda_tempo: float = 0.0,
    sono_modo: str = "em_pe",
    danca_fase_beat: float = 0.0,
    danca_intensidade: float = 0.5,
    danca_bass: float = 0.0,
) -> SquashStretch:
    """Calcula o squash & stretch composto para o estado atual.

    Combina a respiração base com o squash & stretch específico do estado.
    A respiração é sempre aplicada como camada base; o estado adiciona por cima.

    Parameters
    ----------
    estado:
        Nome do estado de animação ("idle", "walk", "run", "drag", "fall",
        "sleep", "dance", "land", etc.).
    respiracao:
        Valor centrado (-1..1) da respiração.
    fase_locomocao:
        Fase da passada (radianos).
    run:
        Se True, corrida.
    impacto_tempo:
        Tempo desde o impacto (segundos).
    impacto_duracao:
        Duração do squash de impacto.
    arraste_velocidade:
        Velocidade do cursor durante arraste.
    arraste_intensidade:
        Intensidade do arraste (0..1).
    queda_velocidade:
        Velocidade durante queda.
    queda_tempo:
        Tempo de queda.
    sono_modo:
        Modo de sono ("em_pe", "sentado", "deitado").
    danca_fase_beat:
        Fase dentro da batida (0..1).
    danca_intensidade:
        Intensidade da música (0..1).
    danca_bass:
        Intensidade do bass (0..1).

    Returns
    -------
    Escala multiplicativa composta.
    """
    # Camada base: respiração (sempre presente, mesmo em ação)
    base = squash_stretch_respiracao(respiracao)

    if estado in ("idle", "hover"):
        # Idle: só respiração
        return base

    if estado in ("walk", "run"):
        loco = squash_stretch_locomocao(fase_locomocao, run=run)
        return _compor_escalas(base, loco)

    if estado == "drag":
        drag = squash_stretch_arraste(arraste_velocidade, arraste_intensidade)
        return _compor_escalas(base, drag)

    if estado == "fall":
        fall = squash_stretch_queda(queda_velocidade, queda_tempo)
        return _compor_escalas(base, fall)

    if estado == "sleep":
        sleep = squash_stretch_sono(respiracao, sono_modo)
        return sleep  # Sono substitui a respiração base

    if estado == "dance":
        dance = squash_stretch_danca(danca_fase_beat, danca_intensidade, danca_bass)
        return _compor_escalas(base, dance)

    if estado == "land":
        land = squash_stretch_impacto(impacto_tempo, impacto_duracao)
        return _compor_escalas(base, land)

    # Estados sem squash & stretch específico
    return base


def _compor_escalas(
    a: SquashStretch,
    b: SquashStretch,
) -> SquashStretch:
    """Compor duas escalas multiplicativas.

    A composição multiplica os desvios de 1.0 de cada escala,
    preservando a intenção de ambas.
    """
    # Desvio de cada escala
    da_x = a.x - 1.0
    da_y = a.y - 1.0
    da_z = a.z - 1.0
    db_x = b.x - 1.0
    db_y = b.y - 1.0
    db_z = b.z - 1.0

    # Soma os desvios (composição aditiva de desvios)
    sx = 1.0 + da_x + db_x
    sy = 1.0 + da_y + db_y
    sz = 1.0 + da_z + db_z

    # Reaplica preservação de volume no resultado composto
    sx, sy, sz = preservar_volume(sx, sy, sz)

    return SquashStretch(sx, sy, sz)
