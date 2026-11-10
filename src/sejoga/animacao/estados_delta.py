"""Funções delta para cada estado de animação.

Cada função retorna um delta (diferença) sobre a pose de repouso, não uma pose
absoluta. Isso permite composição aditiva via LayerStack.

O padrão "delta" resolve os problemas de valores inconsistentes (z=62, z=65,
z=68 em diferentes estados) e simplifica transições: em vez de crossfade entre
poses completas, as molas operam sobre deltas menores.
"""

from __future__ import annotations

from math import cos, radians, sin, tau

from sejoga.animacao import locomocao_tuning as loc
from sejoga.animacao import movimento_corpo_tuning as tune
from sejoga.animacao import sono_tuning as sono
from sejoga.animacao.braco_hpr import braco_hpr_graus
from sejoga.animacao.clipes_animacao import amostrar_clipe, ciclo_da_fase
from sejoga.animacao.clipes_ocioso import camada_respiracao, sample_idle, sample_track
from sejoga.animacao.movimento_corpo import BodyPose
from sejoga.animacao.pose_repouso import REPOUSO
from sejoga.nucleo.esqueleto import IdlePersonality, Rotation3

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

    As poses de braço passaram a declarar ALVOS DE MÃO (ver ``alvos_bracos``). O
    delta aditivo sobre a pose de repouso é a diferença entre o HPR do alvo do
    gesto e o HPR do repouso (idle), ambos vindos do solver 3D (``ik_bracos``) —
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


def delta_drag(
    motion: BodyPose, grab_part: str = "body", drag_intensity: float = 0.0
) -> dict[str, Rotation3]:
    """Delta aditivo do estado de arraste.

    Braços reagem à física (pitch, roll, limb_swing), partindo da base de
    repouso (z=68). O delta DIMINUI ou AUMENTA z conforme a física pede. Os
    dedos fecham em garra conforme ``drag_intensity``.

    Parameters
    ----------
    motion:
        Snapshot do BodyMotion com roll, pitch, limb_swing etc.
    grab_part:
        Parte sendo arrastada: 'body', 'right-arm', 'left-arm', 'legs', etc.
    drag_intensity:
        Intensidade do arraste suavizada (0..1); controla o curl dos dedos.

    Returns
    -------
    Delta em radianos a ser somado à pose de repouso.
    """
    delta = _delta_drag_bracos(motion, grab_part)
    delta.update(
        _delta_dedos(
            loc.ARRASTE_DEDOS_BASE
            + loc.ARRASTE_DEDOS_GRIP * max(0.0, min(1.0, drag_intensity))
        )
    )

    return delta


def _delta_dedos(curl: float) -> dict[str, Rotation3]:
    """Curl (graus) em ``fingers``; ``fingers2`` usa o sinal de espelho."""
    return {
        "fingers": Rotation3(0, 0, radians(curl)),
        "fingers2": Rotation3(0, 0, radians(-curl)),
    }


def delta_soltura(tempo: float, aperto: float) -> dict[str, Rotation3]:
    """Dedos que abrem além do ponto ao largar e assentam (aditivo, fecha em 0).

    Parameters
    ----------
    tempo:
        Segundos desde que o mascote foi solto.
    aperto:
        Intensidade do arraste no instante da soltura (0..1).

    Returns
    -------
    Delta dos dedos em radianos; vazio fora da janela de soltura.
    """
    if tempo >= loc.SOLTURA_DURACAO_S:
        return {}

    inicio = loc.ARRASTE_DEDOS_BASE + loc.ARRASTE_DEDOS_GRIP * max(
        0.0, min(1.0, aperto)
    )
    chaves = (
        (0.0, (0.0, 0.0, inicio)),
        (loc.SOLTURA_ABERTURA_S, (0.0, 0.0, loc.SOLTURA_ABERTURA_GRAUS)),
        (loc.SOLTURA_ASSENTO_S, (0.0, 0.0, loc.SOLTURA_ASSENTO_GRAUS)),
        (loc.SOLTURA_DURACAO_S, (0.0, 0.0, 0.0)),
    )

    return _delta_dedos(sample_track(chaves, max(0.0, tempo))[2])


def somar_deltas(
    base: dict[str, Rotation3], extra: dict[str, Rotation3]
) -> dict[str, Rotation3]:
    """Soma dois deltas junta a junta (cópia; os argumentos não mudam)."""
    soma = dict(base)

    for grupo, rot in extra.items():
        atual = soma.get(grupo, Rotation3())
        soma[grupo] = Rotation3(atual.x + rot.x, atual.y + rot.y, atual.z + rot.z)

    return soma


def _delta_drag_bracos(motion: BodyPose, grab_part: str) -> dict[str, Rotation3]:
    """Braços e cabeça do arraste por parte pega (termos confirmados na GPU)."""
    delta: dict[str, Rotation3] = {}

    if grab_part in ("legs", "left-feet", "right-feet"):
        # Pego pela perna/pé: braços e cabeça pendem a favor da gravidade. O
        # alvo da mão (``drag_perna``) recolhe os braços para junto do corpo,
        # ainda mais baixos que o repouso; a oscilação entra aditiva por cima.

        delta.update(_delta_braco_ik("drag_perna"))
        delta["head"] = Rotation3(
            radians(tune.ARRASTE_PENDENTE_CABECA_X),
            0,
            radians(motion.limb_swing * tune.ARRASTE_PENDENTE_OSCILACAO * 0.4),
        )
        delta["right-arm"] = _somar_z(
            delta["right-arm"], motion.limb_swing * tune.ARRASTE_PENDENTE_OSCILACAO
        )
        delta["left-arm"] = _somar_z(
            delta["left-arm"], motion.limb_swing * tune.ARRASTE_PENDENTE_OSCILACAO
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
        delta["head"] = Rotation3(radians(-12), 0, radians(motion.limb_swing * 0.08))
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


def _somar(
    rot: Rotation3, *, x: float = 0.0, y: float = 0.0, z: float = 0.0
) -> Rotation3:
    """Soma graus (convertidos) a um ``Rotation3`` em radianos."""
    return Rotation3(rot.x + radians(x), rot.y + radians(y), rot.z + radians(z))


def _somar_z(rot: Rotation3, z_graus: float) -> Rotation3:
    """Soma só o eixo Z (graus) a um ``Rotation3`` em radianos."""
    return Rotation3(rot.x, rot.y, rot.z + radians(z_graus))


def delta_walk(fase: float, run: bool = False) -> dict[str, Rotation3]:
    """Delta aditivo do estado de caminhada/corrida.

    Parameters
    ----------
    fase:
        Fase da passada (radianos), a MESMA de ``LegMotion.phase``: os braços
        balançam em contrafase às pernas porque partilham este relógio.
    run:
        Se True, corrida (mais amplitude).

    Returns
    -------
    Delta em radianos a ser somado à pose de repouso.
    """
    clipe = amostrar_clipe("run" if run else "walk", ciclo_da_fase(fase))

    return {
        grupo: Rotation3(radians(x), radians(y), radians(z))
        for grupo, (x, y, z) in clipe.items()
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


def delta_fall(
    t: float, velocity: tuple[float, float] = (0, 0)
) -> dict[str, Rotation3]:
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

    wind_effect = min(1.0, (abs(vx) + abs(vy)) / loc.QUEDA_VENTO_SATURACAO)
    head_tilt = (
        -loc.QUEDA_CABECA_INCLINACAO if ascending else loc.QUEDA_CABECA_INCLINACAO
    )

    # Flail dos braços em z (elevação) e y (azimute), nunca em x (torção). Base:
    # mãos abertas para fora (silhueta aérea), vinda do alvo de queda.
    flail = sin(t * loc.QUEDA_FLAIL_VELOCIDADE) * loc.QUEDA_FLAIL_Z * wind_effect
    flail_y = flail * loc.QUEDA_FLAIL_Y_FRACAO
    # Quadrado: sempre >= 0 e sem a quina de abs() (que daria tranco).
    cotovelo = flail**2 / loc.QUEDA_FLAIL_Z * loc.QUEDA_FLAIL_COTOVELO_FRACAO
    tumble = max(
        -loc.QUEDA_TUMBLE_MAX_GRAUS,
        min(loc.QUEDA_TUMBLE_MAX_GRAUS, vx * loc.QUEDA_TUMBLE_GRAUS_POR_PX),
    )

    delta = _delta_braco_ik("fall")
    delta["head"] = Rotation3(
        radians(head_tilt), 0, radians(flail * loc.QUEDA_FLAIL_CABECA_FRACAO)
    )
    delta["body"] = Rotation3(0, 0, radians(tumble))
    # Espelho (x, -y, -z): y e z invertem no braço esquerdo; x ficaria igual.
    delta["right-arm"] = _somar(delta["right-arm"], y=flail_y, z=flail)
    delta["left-arm"] = _somar(delta["left-arm"], y=-flail_y, z=-flail)
    # Cotovelo só flexiona mais (direito z+, esquerdo z-): sem hiperextensão.
    delta["ant-arm"] = _somar(delta.get("ant-arm", Rotation3()), z=cotovelo)
    delta["ant-arm2"] = _somar(delta.get("ant-arm2", Rotation3()), z=-cotovelo)
    delta.update(_delta_dedos(loc.QUEDA_DEDOS_ABERTOS))

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
    respiracao = sin(tau * sono.SONO_RESPIRACAO_HZ * t)
    afunda = 0.5 - 0.5 * cos(tau * t / sono.SONO_AFUNDA_PERIODO_S)
    curl = sono.SONO_DEDOS_CURL + respiracao * sono.SONO_DEDOS_RESPIRACAO

    # Braços relaxados junto ao corpo, baixos: vêm do alvo de mão de sono (IK).
    delta = _delta_braco_ik("sleep")
    delta["right-arm"] = _somar_z(delta["right-arm"], sono.SONO_OMBRO_CAIDO)
    delta["left-arm"] = _somar_z(delta["left-arm"], -sono.SONO_OMBRO_CAIDO)
    delta["body"] = Rotation3(
        radians(respiracao * sono.SONO_RESPIRACAO_PEITO),
        0,
        radians(sono.SONO_CORPO_Z_BASE + afunda * sono.SONO_AFUNDA_Z),
    )
    delta["head"] = Rotation3(
        radians(
            sono.SONO_CABECA_X_BASE
            + respiracao * sono.SONO_RESPIRACAO_CABECA
            + _cochilo(t)
        ),
        0,
        radians(sono.SONO_CABECA_Z_BASE),
    )
    delta.update(_delta_dedos(curl))

    return delta


def _cochilo(t: float) -> float:
    """Queda rara e suave da cabeça (graus em head.x); 0 fora do cochilo."""
    chaves = (
        (0.0, (0.0, 0.0, 0.0)),
        (sono.SONO_COCHILO_INICIO_S, (0.0, 0.0, 0.0)),
        (sono.SONO_COCHILO_FUNDO_S, (sono.SONO_COCHILO_GRAUS, 0.0, 0.0)),
        (sono.SONO_COCHILO_SOLTA_S, (sono.SONO_COCHILO_GRAUS, 0.0, 0.0)),
        (sono.SONO_COCHILO_VOLTA_S, (0.0, 0.0, 0.0)),
        (sono.SONO_COCHILO_PERIODO_S, (0.0, 0.0, 0.0)),
    )

    return sample_track(chaves, t % sono.SONO_COCHILO_PERIODO_S)[0]


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
        "body": Rotation3(
            _peito(motion.pitch), _peito(motion.yaw), _peito(motion.roll)
        ),
        "head": Rotation3(
            radians(motion.head_pitch),
            0,
            radians(motion.head_roll),
        ),
    }
