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

# Arraste — stretch gravitacional pendurado + stretch proporcional à velocidade
ARRASTE_STRETCH_PESO_Z = 0.046
ARRASTE_STRETCH_Z = 0.085
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
        Fase da passada em radianos. Os apoios ocorrem em 0 e pi.
    run:
        Se True, corrida (amplitude maior).

    Returns
    -------
    Escala multiplicativa.
    """
    multi = LOCOMOCAO_CORRIDA_MULTIPLICADOR if run else 1.0

    # O corpo afunda duas vezes por ciclo (a cada apoio de pé)
    # cos(2*fase) dá dois picos por ciclo: +1 no apoio, -1 na passagem.
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
        cauda = 1.0 - t_rec * t_rec * (3.0 - 2.0 * t_rec)
        envelope = math.exp(-3.2 * t_rec * t_rec) * math.cos(math.pi * 1.5 * t_rec) * cauda

    # Squash vertical suave (evita achatar o peito contra as pernas; máx ~13%).
    sz = max(0.87, 1.0 - envelope * min(IMPACTO_SQUASH_Z_MAX, 0.13))

    sx, sy, _ = preservar_volume(1.0, 1.0, sz)
    return SquashStretch(sx, sy, sz)


def squash_stretch_arraste(
    velocidade: tuple[float, float] = (0.0, 0.0),
    intensidade: float = 0.0,
    *,
    hanging: float = 0.0,
) -> SquashStretch:
    """Squash & Stretch durante arraste.

    Alongamento gravitacional sutil quando pendurado parado (sensação de peso
    real puxando o gabinete para baixo), reforçado pelo vetor de velocidade do
    mouse; achatamento lateral compensatório preservando volume.
    """
    susp = max(0.0, min(1.0, hanging))
    if intensidade <= 0.0 and susp <= 0.01:
        return SquashStretch()

    # Peso gravitacional contínuo enquanto está suspenso na mão do usuário
    peso_parado = susp * ARRASTE_STRETCH_PESO_Z

    # Velocidade vertical determina stretch extra com transição contínua (sem degrau em vy=40).
    vy = velocidade[1] if len(velocidade) > 1 else 0.0
    velocidade_mag = math.hypot(*velocidade) if velocidade else 0.0
    vel_norm = min(1.0, velocidade_mag / 950.0)
    fator_vel = max(intensidade, susp * 0.65)
    t_queda_vel = max(0.0, min(1.0, (vy + 40.0) / 120.0))
    t_queda_vel = t_queda_vel * t_queda_vel * (3.0 - 2.0 * t_queda_vel)
    sinal_vel = 1.0 - 1.55 * t_queda_vel
    delta_vel = vel_norm * fator_vel * ARRASTE_STRETCH_Z * sinal_vel

    sz = max(0.92, min(1.14, 1.0 + peso_parado + delta_vel))
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

    # Stretch vertical na queda com preservação real de volume (Sx * Sy * Sz ≈ 1.0).
    sz = 1.0 + vel_norm * QUEDA_STRETCH_Z
    tumble = min(1.0, abs(vx) / 600.0)
    fator_x = 1.0 - tumble * QUEDA_SQUASH_X
    base_xy = math.sqrt(1.0 / sz)
    sx = base_xy * fator_x
    sy = 1.0 / max(1e-4, sx * sz)
    return SquashStretch(sx, sy, sz)


def squash_stretch_sono(
    respiracao: float = 0.0,
    modo: str = "em_pe",
    *,
    entrada: float = 1.0,
) -> SquashStretch:
    """Squash & Stretch no sono.

    Achatamento relaxado contra a superfície de apoio (suavizado por ``entrada``);
    expansão profunda e pesada na respiração do sono.
    """
    fator_entrada = max(0.0, min(1.0, entrada))
    base_squash = SONO_SQUASH_Z * fator_entrada
    resp_amplitude = RESPIRACAO_ESCALA_Z * (
        1.0 + (SONO_RESPIRACAO_MULTIPLICADOR - 1.0) * fator_entrada
    )

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

    # Bass reforça o squash no downbeat de forma contínua (sem salto em beat_pulse == 0.5).
    if bass > 0.3 and beat_pulse > 0.5:
        sz -= (bass - 0.3) * 0.05 * min(1.0, (beat_pulse - 0.5) * 2.0)

    sx, sy, _ = preservar_volume(1.0, 1.0, sz)
    return SquashStretch(sx, sy, sz)


def squash_stretch_reacao(
    estado: str,
    tempo: float,
    duracao: float = 0.65,
) -> SquashStretch:
    """Squash & Stretch autoral para reações (Manifesto §2.3 — 12 princípios em tudo).

    Cada reação segue antecipação → pico elástico → assentamento amortecido com
    preservação de volume real (Sx * Sy * Sz ≈ 1.0).
    """
    if tempo < 0.0 or duracao <= 1e-4:
        return SquashStretch()
    u = min(1.0, tempo / duracao)

    if estado == "celebrate":
        # Agacha na antecipação (0..0.18) -> salta esticando (0.18..0.58) -> pouso e bomba C1 contínuos
        if u < 0.18:
            sz = 1.0 - 0.11 * math.sin((u / 0.18) * math.pi)
        elif u < 0.58:
            p = (u - 0.18) / 0.40
            sz = 1.0 + 0.13 * math.sin(p * math.pi)
        else:
            p = (u - 0.58) / 0.42
            sz = 1.0 - 0.11 * math.exp(-3.6 * p) * math.sin(math.pi * 2.0 * p)
    elif estado == "sneeze":
        # Sincronizado com pose_sneeze (9.0s -> explosão exata em t=3.68s, u=0.409).
        if u < 0.395:
            p = u / 0.395
            pulso_in = math.sin(p * math.pi * 0.5)
            sz = 1.0 + 0.085 * pulso_in
        elif u < 0.465:
            p = (u - 0.395) / 0.070
            sz = 1.085 - 0.215 * math.sin(p * math.pi * 0.5)
        elif u < 0.62:
            p = (u - 0.465) / 0.155
            sz = 1.0 - 0.13 * (1.0 - p * (2.0 - p))
        else:
            p = (u - 0.62) / 0.38
            sz = 1.0 - 0.03 * math.sin(p * math.pi * 3.0) * math.exp(-3.2 * p)
    elif estado in ("surprise", "wake"):
        # Estiramento súbito no susto seguido de recolhimento
        sz = 1.0 + 0.11 * math.exp(-3.8 * u) * math.sin(math.pi * min(1.0, u * 2.8))
    elif estado in ("hit", "poke", "double_click"):
        # Ataque elástico vivo a partir de 1.0 seguido de rebote dinâmico
        amp = 0.12 if estado == "hit" else (0.11 if estado == "double_click" else 0.10)
        ataque = math.sin(min(1.0, u / 0.11) * math.pi * 0.5)
        sz = 1.0 - amp * ataque * math.exp(-3.6 * u) * math.cos(math.pi * 2.0 * max(0.0, u - 0.05))
    elif estado == "pet":
        # Aconchego macio e rítmico ao receber carinho
        sz = 1.0 - 0.042 * math.sin(u * math.pi) + 0.014 * math.sin(u * math.pi) * math.sin(tempo * 6.0)
    elif estado == "click":
        # Quique ágil de atenção partindo suavemente de 1.0
        ataque = math.sin(min(1.0, u / 0.12) * math.pi * 0.5)
        sz = 1.0 - 0.055 * ataque * math.exp(-4.6 * u) * math.cos(math.pi * 1.8 * max(0.0, u - 0.05))
    elif estado == "wave":
        # Leve alongamento convidativo no aceno com balanço elástico suave
        env = math.sin(u * math.pi)
        sz = 1.0 + 0.032 * env + 0.012 * env * math.sin(tempo * 5.4)
    elif estado == "stretch":
        # Espreguiçar: comprime brevemente na antecipação, estica alto no ápice e assenta
        if u < 0.18:
            p = u / 0.18
            sz = 1.0 - 0.045 * math.sin(p * math.pi)
        elif u < 0.72:
            p = (u - 0.18) / 0.54
            sz = 1.0 + 0.095 * math.sin(p * math.pi)
        else:
            p = (u - 0.72) / 0.28
            sz = 1.0 - 0.035 * math.sin(p * math.pi) * (1.0 - p * 0.4)
    elif estado == "blue_balls":
        # Choque breve -> encolhimento pulsante contínuo com retorno suave no fim
        choque = math.sin(min(1.0, u / 0.16) * math.pi)
        encolhe = math.sin(max(0.0, (u - 0.12) / 0.88) * math.pi)
        pulso = 0.5 - 0.5 * math.cos(tempo * 9.0)
        sz = 1.0 + 0.065 * choque - (0.075 + 0.025 * pulso) * encolhe
    elif estado == "goku_teleport":
        # Pulso vertical rápido de chegada/concentração e assentamento elástico
        sz = 1.0 + 0.08 * math.sin(min(1.0, u / 0.24) * math.pi) - 0.03 * math.sin(max(0.0, (u - 0.24) / 0.76) * math.pi)
    elif estado == "virtual_insanity":
        # Base firme rebaixada com leve pulsação de groove
        env = math.sin(u * math.pi)
        sz = 1.0 - 0.038 * env + 0.012 * env * math.sin(tempo * 4.4)
    elif estado == "teimosia":
        # Tensão elástica pulsante com ataque suave e cauda de encerramento limpa
        ataque = math.sin(min(1.0, tempo / 0.18) * math.pi * 0.5)
        cauda = 1.0 - max(0.0, (u - 0.84) / 0.16) ** 2 * (3.0 - 2.0 * max(0.0, (u - 0.84) / 0.16))
        sz = 1.0 - 0.045 * ataque * cauda * math.sin(tempo * 7.5)
    else:
        return SquashStretch()

    sz = max(0.84, min(1.16, sz))
    sx, sy, _ = preservar_volume(1.0, 1.0, sz)
    return SquashStretch(sx, sy, sz)


def squash_stretch_postura(
    flexao_joelhos_graus: float = 0.0,
    pitch_tronco_graus: float = 0.0,
) -> SquashStretch:
    """Micro-squash/stretch orgânico acoplado à flexão dos joelhos e arco da coluna.

    Agachar/absorver impacto nos joelhos ou curvar o tronco pra frente comprime
    sutilmente o volume vertical; estufar o peito / esticar as pernas alonga.
    """
    excesso_joelho = max(-4.0, flexao_joelhos_graus - 7.0)
    delta_joelho = -max(-0.015, min(0.058, excesso_joelho * 0.0017))
    delta_tronco = max(-0.038, min(0.044, pitch_tronco_graus * 0.0020))
    sz = max(0.91, min(1.08, 1.0 + delta_joelho + delta_tronco))
    if abs(sz - 1.0) < 1e-4:
        return SquashStretch()
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
    reacao_tempo: float = 0.0,
    reacao_duracao: float = 0.65,
    arraste_hanging: float = 0.0,
    sono_entrada: float = 1.0,
    flexao_joelhos_graus: float = 0.0,
    pitch_tronco_graus: float = 0.0,
) -> SquashStretch:
    """Calcula o squash & stretch composto para o estado atual."""
    base = squash_stretch_respiracao(respiracao)
    postura = squash_stretch_postura(flexao_joelhos_graus, pitch_tronco_graus)

    if estado in ("idle", "hover"):
        return _compor_escalas(base, postura)

    if estado in ("walk", "run"):
        loco = squash_stretch_locomocao(fase_locomocao, run=run)
        return _compor_escalas(base, loco)

    if estado == "drag":
        drag = squash_stretch_arraste(
            arraste_velocidade, arraste_intensidade, hanging=arraste_hanging
        )
        return _compor_escalas(base, drag)

    if estado == "fall":
        fall = squash_stretch_queda(queda_velocidade, queda_tempo)
        return _compor_escalas(base, fall)

    if estado == "sleep":
        return squash_stretch_sono(respiracao, sono_modo, entrada=sono_entrada)

    if estado == "dance":
        dance = squash_stretch_danca(danca_fase_beat, danca_intensidade, danca_bass)
        return _compor_escalas(base, dance)

    if estado == "land":
        land = squash_stretch_impacto(impacto_tempo, impacto_duracao)
        return _compor_escalas(base, land)

    if estado == "jump":
        vy = queda_velocidade[1] if len(queda_velocidade) > 1 else -400.0
        sz_voo = min(1.13, 1.04 + abs(min(0.0, vy)) / 2400.0)
        if reacao_tempo <= 0.11:
            u_c = max(0.0, min(1.0, reacao_tempo / 0.11))
            u_c = u_c * u_c * u_c * (10.0 + u_c * (-15.0 + 6.0 * u_c))
            sz = 1.0 - 0.11 * u_c
        else:
            u_v = max(0.0, min(1.0, (reacao_tempo - 0.11) / 0.14))
            u_v = u_v * u_v * u_v * (10.0 + u_v * (-15.0 + 6.0 * u_v))
            sz = 0.89 + (sz_voo - 0.89) * u_v
        sx, sy, _ = preservar_volume(1.0, 1.0, sz)
        return _compor_escalas(base, SquashStretch(sx, sy, sz))

    if estado == "sit":
        return base

    reacao = squash_stretch_reacao(estado, reacao_tempo, reacao_duracao)
    if reacao != SquashStretch():
        return _compor_escalas(base, reacao)

    return base


def _compor_escalas(
    a: SquashStretch,
    b: SquashStretch,
) -> SquashStretch:
    """Compõe duas escalas preservando volume exatamente UMA vez (Sx * Sy * Sz == 1.0)."""
    sz = max(0.80, min(1.22, a.z * b.z))
    # Preserva eventual assimetria X/Y (como na queda lateral) sem duplicar compensação.
    razao_xy = (a.x / max(1e-4, a.y)) * (b.x / max(1e-4, b.y))
    area_xy = 1.0 / sz
    sx = math.sqrt(area_xy * razao_xy)
    sy = area_xy / max(1e-4, sx)
    return SquashStretch(sx, sy, sz)
