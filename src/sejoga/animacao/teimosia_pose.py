"""Pose de teimosia: sequência completa do manifesto §1.4.

Extraído de `controlador_animacao.py` para manter o módulo < 200 linhas.
Implementa as 5 fases da teimosia: resistência → repreensão → bote →
roubo do cursor → cospe.

Manifesto: §1.4 — Cena canônica do roubo do mouse.
"""

from __future__ import annotations

import math

from sejoga.animacao.pose_repouso import REPOUSO

#: Duração de cada fase da teimosia em segundos.
FASES_TEIMOSIA = {
    "resistencia": (0.0, 1.0),
    "repreensao": (1.0, 2.0),
    "bote": (2.0, 3.0),
    "roubo": (3.0, 5.0),
    "cospe": (5.0, 6.0),
}


def fase_do_tempo(tempo: float) -> str:
    """Retorna o nome da fase ativa no ``tempo`` dado."""
    for nome, (inicio, fim) in FASES_TEIMOSIA.items():
        if inicio <= tempo < fim:
            return nome
    return "cospe"  # fallback para o final


def aplicar_fase(
    rig,
    tempo: float,
    direcao_olhar: float = 0.0,
) -> None:
    """Aplica a pose da fase de teimosia no ``rig``.

    Parâmetros
    ----------
    rig : Rig
        O rig do Mário para aplicar as rotações.
    tempo : float
        Tempo desde o início da teimosia (segundos).
    direcao_olhar : float
        Direção do olhar normalizada (-1..1).
    """
    fase = fase_do_tempo(tempo)

    if fase == "resistencia":
        _fase_resistencia(rig, tempo, direcao_olhar)
    elif fase == "repreensao":
        _fase_repreensao(rig, tempo, direcao_olhar)
    elif fase == "bote":
        _fase_bote(rig, tempo, direcao_olhar)
    elif fase == "roubo":
        _fase_roubo(rig, tempo, direcao_olhar)
    else:
        _fase_cospe(rig, tempo, direcao_olhar)


def _fase_resistencia(rig, tempo: float, direcao_olhar: float) -> None:
    """Fase 1: Mário tensiona o corpo, pernas pedalam no ar."""
    rig.set_rotation("body", x=-10.0, y=direcao_olhar * 12.0, z=math.sin(tempo * 10.0) * 6.0)
    rig.set_rotation("head", x=-15.0, y=direcao_olhar * 30.0, z=5.0)
    rig.set_rotation(
        "right-arm",
        x=REPOUSO.BRACO_X - 20.0,
        y=REPOUSO.BRACO_Y,
        z=REPOUSO.BRACO_Z + 15.0,
    )
    rig.set_rotation(
        "left-arm",
        x=REPOUSO.BRACO_X - 20.0,
        y=-REPOUSO.BRACO_Y,
        z=-REPOUSO.BRACO_Z - 15.0,
    )
    pedal = math.sin(tempo * 14.0) * 22.0
    rig.set_rotation("coxa-direita", x=pedal)
    rig.set_rotation("coxa-esquerda", x=-pedal)
    rig.set_rotation("canela-direita", x=max(0.0, -pedal) * 1.4)
    rig.set_rotation("canela-esquerda", x=max(0.0, pedal) * 1.4)


def _fase_repreensao(rig, tempo: float, direcao_olhar: float) -> None:
    """Fase 2: Olhar de desafio para o cursor (pose forte + antecipação)."""
    u = min(1.0, max(0.0, tempo - 1.0))
    rig.set_rotation("body", x=4.0 * math.sin(u * math.pi), y=direcao_olhar * 15.0, z=-4.0)
    rig.set_rotation("head", x=-8.0, y=direcao_olhar * 45.0, z=-6.0)
    rig.set_rotation("door", y=4.0 * abs(math.sin(tempo * 8.0)))
    rig.set_rotation(
        "right-arm",
        x=REPOUSO.BRACO_X - 8.0,
        y=REPOUSO.BRACO_Y - 10.0,
        z=REPOUSO.BRACO_Z - 16.0,
    )
    rig.set_rotation(
        "left-arm",
        x=REPOUSO.BRACO_X - 8.0,
        y=-REPOUSO.BRACO_Y + 10.0,
        z=-REPOUSO.BRACO_Z + 16.0,
    )
    rig.set_rotation("ant-arm", x=0.0, y=0.0, z=REPOUSO.ANTEBRACO_Z + 32.0)
    rig.set_rotation("ant-arm2", x=0.0, y=0.0, z=-REPOUSO.ANTEBRACO_Z - 32.0)


def _fase_bote(rig, tempo: float, direcao_olhar: float) -> None:
    """Fase 3: Agachar e escancarar porta até 48° (manifesto §3.3)."""
    agachar = min(1.0, max(0.0, tempo - 2.0))
    # Curva quíntica na antecipação do bote
    suave = agachar * agachar * agachar * (agachar * (agachar * 6.0 - 15.0) + 10.0)
    rig.set_rotation("body", x=18.0 * suave, y=direcao_olhar * 10.0, z=0.0)
    rig.set_rotation("head", x=-28.0 * suave, y=direcao_olhar * 20.0, z=0.0)
    # Porta abre até 48° (em graus, respeitando convenção do Rig)
    porta_abertura = 48.0 * suave
    rig.set_rotation("door", y=porta_abertura)
    rig.set_rotation(
        "right-arm",
        x=REPOUSO.BRACO_X - 42.0 * suave,
        y=REPOUSO.BRACO_Y,
        z=REPOUSO.BRACO_Z - 14.0 * suave,
    )
    rig.set_rotation(
        "left-arm",
        x=REPOUSO.BRACO_X - 42.0 * suave,
        y=-REPOUSO.BRACO_Y,
        z=-REPOUSO.BRACO_Z + 14.0 * suave,
    )


def _fase_roubo(rig, tempo: float, direcao_olhar: float) -> None:
    """Fase 4: Roubo do mouse — cursor oculto (Win32 ShowCursor)."""
    dt_roubo = max(0.0, tempo - 3.0)
    correr = math.sin(dt_roubo * 10.0) * 10.0
    rig.set_rotation("body", x=8.0, y=correr * 0.5, z=math.cos(dt_roubo * 10.0) * 4.0)
    rig.set_rotation("head", x=-10.0, y=correr, z=0.0)
    rig.set_rotation("door", y=18.0 + math.sin(dt_roubo * 12.0) * 4.0)
    rig.set_rotation(
        "right-arm",
        x=REPOUSO.BRACO_X - 28.0 + correr * 1.6,
        y=REPOUSO.BRACO_Y,
        z=REPOUSO.BRACO_Z,
    )
    rig.set_rotation(
        "left-arm",
        x=REPOUSO.BRACO_X - 28.0 - correr * 1.6,
        y=-REPOUSO.BRACO_Y,
        z=-REPOUSO.BRACO_Z,
    )


def _fase_cospe(rig, tempo: float, direcao_olhar: float) -> None:
    """Fase 5: Cospe o cursor de volta com quique elástico."""
    cospe_t = min(1.0, max(0.0, tempo - 5.0))
    quique = math.sin(cospe_t * math.pi * 3.0) * (1.0 - cospe_t) * 20.0
    porta = 48.0 * math.sin(min(1.0, cospe_t * 2.0) * math.pi)
    rig.set_rotation("body", x=-12.0 * (1.0 - cospe_t), y=direcao_olhar * 15.0, z=0.0)
    rig.set_rotation("head", x=quique, y=direcao_olhar * 30.0, z=0.0)
    rig.set_rotation("door", y=max(0.0, porta))
    rig.set_rotation(
        "right-arm",
        x=REPOUSO.BRACO_X - 10.0,
        y=REPOUSO.BRACO_Y,
        z=REPOUSO.BRACO_Z - 18.0 * (1.0 - cospe_t),
    )
    rig.set_rotation(
        "left-arm",
        x=REPOUSO.BRACO_X - 10.0,
        y=-REPOUSO.BRACO_Y,
        z=-REPOUSO.BRACO_Z + 18.0 * (1.0 - cospe_t),
    )
