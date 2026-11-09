"""Funções delta para cada estado de animação.

Cada função retorna um delta (diferença) sobre a pose de repouso, não uma pose
absoluta. Isso permite composição aditiva via LayerStack.

O padrão "delta" resolve os problemas de valores inconsistentes (z=62, z=65,
z=68 em diferentes estados) e simplifica transições: em vez de crossfade entre
poses completas, as molas operam sobre deltas menores.
"""

from __future__ import annotations

from math import cos, radians, sin, tau

from sejoga.animacao.body_motion import BodyPose
from sejoga.animacao.rig_base import REPOUSO
from sejoga.nucleo.rig import IdlePersonality, Rotation3, braco_hpr_graus


def _delta_braco_ik(nome_alvo: str) -> dict[str, Rotation3]:
    """Delta (radianos) dos quatro grupos de braço: alvo IK - repouso de idle.

    As poses de braço passaram a declarar ALVOS DE MÃO (ver ``arm_targets``). O
    delta aditivo sobre a pose de repouso é a diferença entre o HPR do alvo do
    gesto e o HPR do repouso (idle), ambos vindos do solver 3D (``arm_ik``) —
    assim a camada soma exatamente o que leva a mão do quadril até o alvo do
    gesto, sem reintroduzir ângulos diretos na convenção antiga.
    """
    repouso_r = braco_hpr_graus("right", "idle")
    repouso_l = braco_hpr_graus("left", "idle")
    alvo_r = braco_hpr_graus("right", nome_alvo)
    alvo_l = braco_hpr_graus("left", nome_alvo)

    delta: dict[str, Rotation3] = {}

    for base, alvo in ((repouso_r, alvo_r), (repouso_l, alvo_l)):
        for grupo in alvo:
            bx, by, bz = base[grupo]
            ax, ay, az = alvo[grupo]
            delta[grupo] = Rotation3(
                radians(ax - bx), radians(ay - by), radians(az - bz)
            )

    return delta


def delta_idle(
    t: float,
    personality: IdlePersonality,
    respiracao: float = 0.0,
) -> dict[str, Rotation3]:
    """Delta aditivo do estado idle sobre a pose de repouso.

    A base (pose_repouso) já tem right-arm em x=-4°, z=68°.
    Idle só adiciona a oscilação própria da personalidade.

    Parameters
    ----------
    t:
        Tempo do clock de idle (segundos).
    personality:
        Personalidade ativa do idle (calm, curious, playful, etc.).
    respiracao:
        Valor centrado (-1..1) da respiração sob demanda. Default 0.

    Returns
    -------
    Delta em radianos a ser somado à pose de repouso.
    """
    from sejoga.animacao.idle_clips import (
        CLIPS,
        camada_respiracao,
        sample_idle,
    )

    delta: dict[str, Rotation3] = {}

    # Oscilação base presente em todas as personalidades
    sway_body_x = sin(t * 0.8) * 0.7
    sway_body_z = -1.5
    sway_head_y = sin(t * 0.36) * 2
    sway_head_z = 1.5

    if personality.value in CLIPS:
        # Personalidades com clips autorais: sample_idle devolve pose absoluta em
        # graus. Subtraímos a base de repouso para obter apenas o delta.
        pose_absoluta = sample_idle(personality.value, t, respiracao, 1.0)
        for grupo, (x, y, z) in pose_absoluta.items():
            # A base de repouso em graus para comparação
            if grupo == "right-arm":
                base = (REPOUSO.BRACO_X, REPOUSO.BRACO_Y, REPOUSO.BRACO_Z)
            elif grupo == "left-arm":
                base = (REPOUSO.BRACO_X, -REPOUSO.BRACO_Y, -REPOUSO.BRACO_Z)
            elif grupo == "ant-arm":
                base = (REPOUSO.ANTEBRACO_X, 0, REPOUSO.ANTEBRACO_Z)
            elif grupo == "ant-arm2":
                base = (REPOUSO.ANTEBRACO_X, 0, -REPOUSO.ANTEBRACO_Z)
            else:
                base = (0, 0, 0)

            # Delta = pose autorizada - base de repouso, em radianos
            delta[grupo] = Rotation3(
                radians(x - base[0]),
                radians(y - base[1]),
                radians(z - base[2]),
            )
    else:
        # Personalidades fallback (calm, curious, playful, shy, confident)
        # usam a lógica legada de pose_idle mas convertida em deltas.
        delta["body"] = Rotation3(radians(sway_body_x), 0, radians(sway_body_z))
        delta["head"] = Rotation3(0, radians(sway_head_y), radians(sway_head_z))

        # Oscilação sutil dos braços
        breath = sin(t * 0.72)
        sway = sin(t * 0.42)

        if personality == IdlePersonality.CURIOUS:
            look = sin(t * 0.43)
            tilt = sin(t * 0.31)
            delta["body"] = Rotation3(
                radians(breath * 0.9), radians(sway * 1.5), radians(tilt * 1.2)
            )
            delta["head"] = Rotation3(
                radians(-3.0 + sin(t * 0.62) * 1.5),
                radians(look * 16.0),
                radians(tilt * 8.0),
            )
            delta["door"] = Rotation3(0, radians(max(0.0, sin(t * 0.28)) * 3.0), 0)
            # Curiosa: um braço um pouco mais aberto (delta negativo no Z)
            delta["right-arm"] = Rotation3(
                radians(sin(t * 0.43) * 3.0), 0, radians(-20.0)
            )
            delta["left-arm"] = Rotation3(
                radians(-sin(t * 0.43 + 0.4) * 2.5), 0, 0
            )
            delta["ant-arm"] = Rotation3(
                radians(sin(t * 0.48) * 4.5), 0, radians(tilt * 5.0)
            )
            delta["ant-arm2"] = Rotation3(
                radians(-sin(t * 0.48 + 0.5) * 3.5), 0, radians(-tilt * 4.0)
            )
        elif personality == IdlePersonality.PLAYFUL:
            bounce = sin(t * 1.12)
            compression = (1.0 - sin(t * 2.24 + 1.5707963268)) * 0.5
            delta["body"] = Rotation3(
                radians(compression * 2.2),
                radians(sway * 2.2),
                radians(bounce * 2.2),
            )
            delta["head"] = Rotation3(
                radians(-compression * 1.8),
                radians(sin(t * 0.72) * 6.0),
                radians(bounce * 3.0),
            )
            delta["door"] = Rotation3(0, radians(max(0.0, sin(t * 0.28)) * 3.0), 0)
            arm_bounce = sin(t * 1.12 + 0.6)
            delta["right-arm"] = Rotation3(
                radians(bounce * 6.0), 0, radians(-14.0 + bounce * 5.0)
            )
            delta["left-arm"] = Rotation3(
                radians(-bounce * 6.0), 0, radians(2.0 - arm_bounce * 5.0)
            )

    # Respiração sob demanda (adicional sobre o delta de personalidade)
    if respiracao:
        camada_resp = camada_respiracao(respiracao, 1.0)
        for grupo, (ex, ey, ez) in camada_resp.items():
            base_delta = delta.get(grupo, Rotation3())
            delta[grupo] = Rotation3(
                base_delta.x + radians(ex),
                base_delta.y + radians(ey),
                base_delta.z + radians(ez),
            )

    return delta


def delta_drag(motion: BodyPose, grab_part: str = "body") -> dict[str, Rotation3]:
    """Delta aditivo do estado de arraste.

    Braços reagem à física (pitch, roll, limb_swing), partindo da base de
    repouso (z=68). O delta DIMINUI ou AUMENTA z conforme a física pede.

    Parameters
    ----------
    motion:
        Snapshot do BodyMotion com roll, pitch, limb_swing etc.
    grab_part:
        Parte sendo arrastada: 'body', 'right-arm', 'left-arm', 'legs', etc.

    Returns
    -------
    Delta em radianos a ser somado à pose de repouso.
    """
    delta: dict[str, Rotation3] = {}

    if grab_part in ("legs", "left-feet", "right-feet"):
        # Pego pela perna/pé: braços e cabeça pendem a favor da gravidade. O
        # alvo da mão (``drag_perna``) recolhe os braços para junto do corpo,
        # ainda mais baixos que o repouso; a oscilação entra aditiva por cima.
        _CABECA_PENDENTE_X = 22.0
        _OSCILACAO_PENDENTE = 0.18

        delta.update(_delta_braco_ik("drag_perna"))
        delta["head"] = Rotation3(
            radians(_CABECA_PENDENTE_X),
            0,
            radians(motion.limb_swing * _OSCILACAO_PENDENTE * 0.4),
        )
        delta["right-arm"] = _somar_z(
            delta["right-arm"], motion.limb_swing * _OSCILACAO_PENDENTE
        )
        delta["left-arm"] = _somar_z(
            delta["left-arm"], motion.limb_swing * _OSCILACAO_PENDENTE
        )
    elif grab_part == "right-arm":
        # Pego pelo braço direito: a mão vai para a frente/baixo, puxada.
        ik = _delta_braco_ik("drag")
        delta["right-arm"] = ik["right-arm"]
        delta["ant-arm"] = ik["ant-arm"]
    elif grab_part == "left-arm":
        # Pego pelo braço esquerdo.
        ik = _delta_braco_ik("drag")
        delta["left-arm"] = ik["left-arm"]
        delta["ant-arm2"] = ik["ant-arm2"]
    elif grab_part == "body":
        # Pego pelo corpo: braços à frente, equilibrando. Base vinda do alvo de
        # arraste; a física (pitch) e a oscilação somam por cima.
        delta.update(_delta_braco_ik("drag"))
        delta["head"] = Rotation3(
            radians(-12), 0, radians(motion.limb_swing * 0.08)
        )
        delta["right-arm"] = _somar(
            delta["right-arm"], x=-motion.pitch * 0.9, z=motion.limb_swing * 0.25
        )
        delta["left-arm"] = _somar(
            delta["left-arm"], x=-motion.pitch * 0.9, z=motion.limb_swing * 0.25
        )
    else:
        # Arraste genérico: base no alvo de arraste; física modula por cima.
        delta.update(_delta_braco_ik("drag"))
        delta["right-arm"] = _somar(
            delta["right-arm"],
            x=-motion.pitch * 0.55,
            z=-motion.roll * 0.55 + motion.limb_swing * 0.45,
        )
        delta["left-arm"] = _somar(
            delta["left-arm"],
            x=-motion.pitch * 0.55,
            z=-motion.roll * 0.55 + motion.limb_swing * 0.4,
        )

    return delta


def _somar(rot: Rotation3, *, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Rotation3:
    """Soma graus (convertidos) a um ``Rotation3`` em radianos."""
    return Rotation3(rot.x + radians(x), rot.y + radians(y), rot.z + radians(z))


def _somar_z(rot: Rotation3, z_graus: float) -> Rotation3:
    """Soma só o eixo Z (graus) a um ``Rotation3`` em radianos."""
    return Rotation3(rot.x, rot.y, rot.z + radians(z_graus))


def delta_walk(t: float, run: bool = False) -> dict[str, Rotation3]:
    """Delta aditivo do estado de caminhada/corrida.

    Parameters
    ----------
    t:
        Tempo do clock (segundos).
    run:
        Se True, corrida (mais amplitude).

    Returns
    -------
    Delta em radianos a ser somado à pose de repouso.
    """
    # Frequência e amplitude dependem se caminhando ou correndo
    freq = 5.0 if run else 3.0
    amp = 1.5 if run else 1.0

    phase = t * freq
    arm_swing = sin(phase) * 15 * amp
    body_sway = sin(phase) * 2 * amp
    head_bob = sin(phase * 2) * 1.5 * amp

    return {
        "body": Rotation3(radians(head_bob * 0.5), radians(body_sway), 0),
        "head": Rotation3(radians(head_bob), 0, 0),
        "right-arm": Rotation3(radians(arm_swing), 0, 0),
        "left-arm": Rotation3(radians(-arm_swing), 0, 0),
    }


def delta_dance(
    t: float, intensity: float = 0.5, bass: float = 0.0, bpm: float = 120.0
) -> dict[str, Rotation3]:
    """Delta aditivo do estado de dança.

    A dança é tratada separadamente pelo DanceMotion, então este delta é
    apenas um placeholder que pode ser usado quando DanceMotion não está ativo.

    Parameters
    ----------
    t:
        Tempo do clock (segundos).
    intensity:
        Intensidade da música (0..1).
    bass:
        Intensidade do bass (0..1).
    bpm:
        Batidas por minuto.

    Returns
    -------
    Delta em radianos a ser somado à pose de repouso.
    """
    beat_phase = (t * bpm / 60) * tau
    bounce = (1 - cos(beat_phase)) * 0.5 * intensity
    sway = sin(beat_phase * 0.5) * 8 * intensity

    return {
        "body": Rotation3(radians(bounce * 3), radians(sway), 0),
        "head": Rotation3(radians(-bounce * 2), radians(sway * 0.5), 0),
        "right-arm": Rotation3(0, 0, radians(-bounce * 15)),
        "left-arm": Rotation3(0, 0, radians(bounce * 15)),
    }


def delta_fall(t: float, velocity: tuple[float, float] = (0, 0)) -> dict[str, Rotation3]:
    """Delta aditivo do estado de queda.

    Parameters
    ----------
    t:
        Tempo no estado de queda (segundos).
    velocity:
        Velocidade (vx, vy) em pixels/segundo.

    Returns
    -------
    Delta em radianos a ser somado à pose de repouso.
    """
    vx, vy = velocity
    # Velocidade vertical determina se está subindo ou descendo
    ascending = vy < 0

    wind_effect = min(1.0, (abs(vx) + abs(vy)) / 1000)
    head_tilt = -8 if ascending else 8

    # Flailing dos braços na queda (termo aditivo sobre a base de IK da queda).
    flail = sin(t * 8) * 10 * wind_effect

    # Base: mãos abertas para fora (silhueta aérea), vinda do alvo de queda.
    delta = _delta_braco_ik("fall")
    delta["head"] = Rotation3(radians(head_tilt), 0, radians(flail * 0.3))
    delta["right-arm"] = _somar(delta["right-arm"], x=flail, z=-abs(flail) * 0.5)
    delta["left-arm"] = _somar(delta["left-arm"], x=-flail, z=abs(flail) * 0.5)
    delta["ant-arm"] = _somar(delta.get("ant-arm", Rotation3()), x=flail * 0.5)
    delta["ant-arm2"] = _somar(delta.get("ant-arm2", Rotation3()), x=-flail * 0.5)

    return delta


def delta_sleep(t: float) -> dict[str, Rotation3]:
    """Delta aditivo do estado de sono.

    Parameters
    ----------
    t:
        Tempo do clock (segundos).

    Returns
    -------
    Delta em radianos a ser somado à pose de repouso.
    """
    # Respiração lenta de sono
    breath = sin(t * 0.4) * 2

    # Braços relaxados junto ao corpo, baixos: vêm do alvo de mão de sono (IK).
    delta = _delta_braco_ik("sleep")
    delta["body"] = Rotation3(radians(breath), 0, radians(-5))
    delta["head"] = Rotation3(radians(-15 + breath * 0.5), 0, radians(-10))

    return delta


def delta_fisica(motion: BodyPose) -> dict[str, Rotation3]:
    """Delta da camada de física (roll, pitch, compression do BodyMotion).

    Esta camada representa a resposta física pura do corpo à inércia e
    movimento, independente do estado de animação.

    Parameters
    ----------
    motion:
        Snapshot do BodyMotion.

    Returns
    -------
    Delta em radianos a ser aplicado sobre a pose composta.
    """
    return {
        "body": Rotation3(
            radians(motion.pitch),
            radians(motion.yaw),
            radians(motion.roll),
        ),
        "head": Rotation3(
            radians(motion.head_pitch),
            0,
            radians(motion.head_roll),
        ),
    }
