"""Funções delta para cada estado de animação.

Cada função retorna um delta (diferença) sobre a pose de repouso, não uma pose
absoluta. Isso permite composição aditiva via LayerStack.

O padrão "delta" resolve os problemas de valores inconsistentes (z=62, z=65,
z=68 em diferentes estados) e simplifica transições: em vez de crossfade entre
poses completas, as molas operam sobre deltas menores.
"""

from __future__ import annotations

from math import cos, radians, sin, tau

from sejoga.animacao import body_motion_tuning as tune
from sejoga.animacao.body_motion import BodyPose
from sejoga.animacao.idle_clips import camada_respiracao, sample_idle
from sejoga.animacao.rig_base import REPOUSO
from sejoga.nucleo.rig import IdlePersonality, Rotation3, braco_hpr_graus

#: Base de repouso (graus) dos grupos de braço, a mesma que ``sample_idle``
#: usa por baixo das frases; subtraída para obter o delta do idle.
_BASE_REPOUSO_GRAUS = {
    "right-arm": (REPOUSO.BRACO_X, REPOUSO.BRACO_Y, REPOUSO.BRACO_Z),
    "left-arm": (REPOUSO.BRACO_X, -REPOUSO.BRACO_Y, -REPOUSO.BRACO_Z),
    "ant-arm": (REPOUSO.ANTEBRACO_X, 0.0, REPOUSO.ANTEBRACO_Z),
    "ant-arm2": (REPOUSO.ANTEBRACO_X, 0.0, -REPOUSO.ANTEBRACO_Z),
}


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

    A base é ``rig_base.pose_repouso`` (IK do alvo de idle).
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
    # sample_idle devolve pose absoluta em graus; subtraímos a base de repouso
    # para obter só o delta. A respiração entra uma única vez, abaixo.
    pose_absoluta = sample_idle(personality.value, t, 0.0, 1.0)
    delta: dict[str, Rotation3] = {}

    for grupo, (x, y, z) in pose_absoluta.items():
        base = _BASE_REPOUSO_GRAUS.get(grupo, (0.0, 0.0, 0.0))
        delta[grupo] = Rotation3(
            radians(x - base[0]),
            radians(y - base[1]),
            radians(z - base[2]),
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
    # Espelho: a torção (x) tem o MESMO sinal nos dois lados; a elevação inverte.
    delta["left-arm"] = _somar(delta["left-arm"], x=flail, z=abs(flail) * 0.5)
    delta["ant-arm"] = _somar(delta.get("ant-arm", Rotation3()), x=flail * 0.5)
    delta["ant-arm2"] = _somar(delta.get("ant-arm2", Rotation3()), x=flail * 0.5)

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
    # Pendurado/arrastado, o renderer já gira o mascote INTEIRO (pivô rígido no
    # ponto de pega). Somar a mesma rotação só no peito o giraria em dobro,
    # dessincronizado de braços e pernas: nesse regime o peito recebe só um
    # balanço pequeno e limitado (a condição é a mesma do renderer).
    pendurado = motion.hanging > tune.PENDURADO_LIMIAR
    fator_peito = tune.PEITO_FATOR_PENDURADO if pendurado else 1.0
    limite = tune.PEITO_PENDURADO_MAX_GRAUS if pendurado else None

    def _peito(graus: float) -> float:
        graus *= fator_peito

        return radians(graus if limite is None else max(-limite, min(limite, graus)))

    return {
        "body": Rotation3(_peito(motion.pitch), _peito(motion.yaw), _peito(motion.roll)),
        "head": Rotation3(
            radians(motion.head_pitch),
            0,
            radians(motion.head_roll),
        ),
    }
