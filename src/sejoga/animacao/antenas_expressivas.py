"""Expressividade viva de antenas, fones, mangas, pelve e micro-sinais da porta (v2.0).

No Mário, as antenas funcionam como "orelhas expressivas" (alerta, curiosas,
relaxadas, deitadas na indignação/corrida), os fones pulsam no grave da música
com defasagem natural, as mangas (`shoulder`/`shoulder2`) acompanham a elevação
dos braços, a pelve dá gingado real ao cós da calça e a porta entreabre 2°–6°
como tique emocional discreto.

FRONTEIRA: Python puro, sem dependências de engine (Panda3D/Qt/Win32).
"""

from __future__ import annotations

from math import cos, degrees, radians, sin, tau

from sejoga.animacao.agencia import Humor
from sejoga.nucleo.esqueleto import Rotation3

# Ângulos base das antenas (graus) por humor: (pitch_x, yaw_y, roll_z_simetrico).
_HUMOR_ANTENAS: dict[Humor, tuple[float, float, float]] = {
    Humor.CALMO: (0.0, 0.0, 0.0),
    Humor.CURIOSO: (6.0, 3.5, 4.5),       # orelhas atentas e levemente inclinadas à frente
    Humor.BRINQUEDOIRO: (8.5, 0.0, 7.5),  # abertas e alegres
    Humor.TEDIOSO: (-10.0, 0.0, -7.0),    # caídas e pesadas
    Humor.INDIGNADO: (-14.0, -4.0, -8.5), # deitadas para trás (atitude!)
    Humor.TEIMOSO: (-16.0, -5.0, -9.0),   # bem firmes para trás
    Humor.DESCONFIADO: (-6.0, 5.0, -3.0), # assimetria desconfiada
}

# Postura sutil do tronco/cabeça por humor (graus): aplicada de forma orgânica em idle/walk.
_HUMOR_POSTURA: dict[Humor, tuple[float, float, float]] = {
    # (peitoral_pitch, head_pitch, head_roll)
    Humor.CALMO: (0.0, 0.0, 0.0),
    Humor.CURIOSO: (3.2, -3.0, 3.8),
    Humor.BRINQUEDOIRO: (-2.5, -2.0, 2.5),
    Humor.TEDIOSO: (5.5, 6.5, -3.0),
    Humor.INDIGNADO: (-4.0, 5.0, -1.5),
    Humor.TEIMOSO: (-5.0, 6.5, 0.0),
    Humor.DESCONFIADO: (2.0, 3.0, -4.0),
}


def _somar(destino: dict[str, Rotation3], grupo: str, rx: float, ry: float, rz: float) -> None:
    atual = destino.get(grupo, Rotation3())
    destino[grupo] = Rotation3(atual.x + rx, atual.y + ry, atual.z + rz)


def delta_expressao_viva(
    t: float,
    estado: str,
    humor: Humor,
    pose_base: dict[str, Rotation3],
    *,
    look_direction: float = 0.0,
    look_vertical: float = 0.0,
    music_playing: bool = False,
    beat_phase: float = 0.0,
    music_bass: float = 0.0,
    music_energy: float = 0.0,
    reacao_tempo: float = 0.0,
    tontura: float = 0.0,
    esforco: float = 0.0,
) -> dict[str, Rotation3]:
    """Calcula a camada viva v2.0 para antenas, fones, ombros, pelve e micro-porta."""
    saida: dict[str, Rotation3] = {}
    dir_c = max(-1.0, min(1.0, look_direction))
    ver_c = max(-1.0, min(1.0, look_vertical))

    # ── 1. Antenas como "orelhas expressivas" ────────────────────────────
    ant_x, ant_y, ant_z = _HUMOR_ANTENAS.get(humor, (0.0, 0.0, 0.0))

    # Modulação por estado atual
    if estado == "sleep":
        ant_x -= 14.0
        ant_z -= 8.0
    elif estado == "run":
        ant_x -= 18.0
        ant_z -= 6.0
    elif estado == "walk":
        ant_x -= 5.0
    elif estado in ("celebrate", "pet"):
        ant_x += 9.0 + 4.5 * sin(t * 7.5)
        ant_z += 7.0 + 3.0 * cos(t * 6.0)
    elif estado in ("surprise", "hit", "poke"):
        pulso_susto = max(0.0, 1.0 - reacao_tempo * 3.5)
        ant_x += 18.0 * pulso_susto
        ant_z += 14.0 * pulso_susto
    elif estado == "hover":
        ant_x += 5.5
        ant_z += 4.0

    # "Orelha atenta" assimétrica para o lado do cursor/foco
    assimetria_olhar = dir_c * 7.5
    # Micro-tique periódico de orelha viva (a cada ~7.3 s, curto e natural)
    fase_tique = (t % 7.3)
    tique_dir = 0.0
    tique_esq = 0.0
    if estado in ("idle", "hover") and fase_tique < 0.28:
        pico = sin((fase_tique / 0.28) * 3.14159)
        tique_dir = 8.5 * pico
    elif estado in ("idle", "hover") and 3.6 < fase_tique < 3.86:
        pico = sin(((fase_tique - 3.6) / 0.26) * 3.14159)
        tique_esq = 7.0 * pico

    # Balanço musical nos fones e nas antenas quando há música ativa
    pulso_beat = 0.0
    pulso_bass = 0.0
    if music_playing:
        onda = cos(tau * beat_phase)
        pulso_beat = onda * (0.35 + 0.65 * music_energy)
        pulso_bass = max(0.0, onda) ** 2 * max(0.25, music_bass)

    # Tontura (pós-sacudida / impacto pesado): espiral suave nas antenas
    tontura_x = 11.0 * tontura * sin(t * 6.8)
    tontura_z = 13.0 * tontura * cos(t * 6.8)

    for lado, nome_fone, nome_antena, tique in (
        (1.0, "fone-direito", "antena-direita", tique_dir),
        (-1.0, "fone-esquerdo", "antena-esquerda", tique_esq),
    ):
        # Lado voltado ao cursor empina mais a antena
        bonus_lado = max(0.0, -lado * assimetria_olhar)
        fone_roll = lado * (pulso_bass * 5.2 + pulso_beat * 2.1)
        fone_pitch = pulso_beat * 2.8 + esforco * 1.8 * sin(t * 5.0)
        if estado == "pet":
            fone_roll += lado * 3.2 * sin(t * 5.2)

        _somar(
            saida,
            nome_fone,
            radians(fone_pitch),
            radians(-dir_c * 2.5),
            radians(fone_roll),
        )
        _somar(
            saida,
            nome_antena,
            radians(ant_x + bonus_lado * 0.65 - ver_c * 5.0 + pulso_beat * 6.5 + tontura_x),
            radians(lado * ant_y + dir_c * 4.0),
            radians(lado * (ant_z + bonus_lado + tique) + lado * pulso_bass * 9.0 + tontura_z),
        )

    # ── 2. Mangas / Ombros (shoulder / shoulder2) reativos aos braços ────
    for lado, nome_braco, nome_ombro in (
        (1.0, "right-arm", "shoulder"),
        (-1.0, "left-arm", "shoulder2"),
    ):
        r_braco = pose_base.get(nome_braco, Rotation3())
        elevacao = max(0.0, (-lado * degrees(r_braco.z)) - 15.0) / 85.0
        elevacao = min(1.0, elevacao)
        encolhimento = elevacao * 11.0 + esforco * 2.5 * sin(t * 5.0)
        if estado in ("surprise", "hit"):
            encolhimento += 7.0 * max(0.0, 1.0 - reacao_tempo * 3.0)
        elif estado == "pet":
            encolhimento -= 3.5
        _somar(
            saida,
            nome_ombro,
            radians(-elevacao * 5.0),
            0.0,
            radians(-lado * encolhimento),
        )

    # ── 3. Pelve viva (gingado no cós da calça e transferência de peso) ──
    if estado in ("idle", "hover"):
        pelvis_y = 2.6 * sin(t * 0.72) + dir_c * 3.2
        pelvis_z = 1.8 * sin(t * 0.72 - 0.5)
        if music_playing:
            pelvis_y += 5.5 * sin(tau * beat_phase * 0.5) * (0.4 + 0.6 * music_energy)
            pelvis_z += 3.8 * pulso_beat
        _somar(saida, "pelvis", radians(esforco * 1.5 * sin(t * 5.0)), radians(pelvis_y), radians(pelvis_z))
    elif estado == "dance":
        pelvis_x = -3.5 * pulso_bass
        pelvis_y = 8.0 * sin(tau * beat_phase * 0.5) * (0.5 + 0.5 * music_energy)
        pelvis_z = 6.0 * pulso_beat
        _somar(saida, "pelvis", radians(pelvis_x), radians(pelvis_y), radians(pelvis_z))
    elif estado in ("walk", "run"):
        amp_p = 7.0 if estado == "run" else 4.2
        _somar(saida, "pelvis", 0.0, radians(amp_p * sin(t * 6.0)), radians(amp_p * 0.45 * cos(t * 6.0)))
    elif estado == "pet":
        _somar(saida, "pelvis", radians(-2.0), radians(4.0 * sin(t * 3.6)), radians(2.8 * cos(t * 3.6)))

    # ── 4. Postura sutil por humor + Idle Groove ao vivo (quando há música) ─
    if estado in ("idle", "hover", "walk", "run"):
        peso_humor = 0.55 if estado in ("walk", "run") else 1.0
        hp_x, hh_x, hh_z = _HUMOR_POSTURA.get(humor, (0.0, 0.0, 0.0))
        _somar(saida, "peitoral", radians(hp_x * peso_humor), 0.0, 0.0)
        _somar(saida, "head", radians(hh_x * peso_humor), 0.0, radians(hh_z * peso_humor))

        # Idle Groove: quando toca música e Mário está em idle/hover, ele já entra
        # discretamente na batida antes mesmo de abrir o palco completo.
        if music_playing and estado in ("idle", "hover"):
            groove_head = 5.2 * pulso_beat
            groove_chest = 2.8 * pulso_beat
            _somar(saida, "head", radians(groove_head), radians(2.5 * sin(tau * beat_phase * 0.5)), 0.0)
            _somar(saida, "peitoral", radians(groove_chest), 0.0, radians(1.6 * sin(tau * beat_phase * 0.5)))

    # ── 5. Micro-sinal emocional na portinha do armário (2°–7°) ──────────
    # Respeita a dobradiça e nunca atrapalha aberturas maiores (tentáculos/espirro).
    porta_extra = 0.0
    if estado == "pet":
        porta_extra = 4.2 + 2.2 * sin(t * 8.0)
    elif estado == "celebrate":
        porta_extra = 6.5 * max(0.0, sin(t * 6.0))
    elif estado == "dance" and pulso_bass > 0.35:
        porta_extra = (pulso_bass - 0.35) * 10.5
    elif estado in ("surprise", "hit"):
        porta_extra = 7.0 * max(0.0, 1.0 - reacao_tempo * 3.2)
    elif estado == "idle" and humor == Humor.CURIOSO:
        porta_extra = 2.2 + 1.2 * sin(t * 1.6)
    elif estado == "idle" and humor == Humor.INDIGNADO:
        porta_extra = 3.0 * max(0.0, sin(t * 4.5))

    if porta_extra > 0.1:
        _somar(saida, "door", 0.0, radians(min(8.5, porta_extra)), 0.0)

    return saida
