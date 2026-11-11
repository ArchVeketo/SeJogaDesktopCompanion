"""Funções delta para cada estado de animação.

Cada função retorna um delta (diferença) sobre a pose de repouso, não uma pose
absoluta. Isso permite composição aditiva via LayerStack.

O padrão "delta" resolve os problemas de valores inconsistentes (z=62, z=65,
z=68 em diferentes estados) e simplifica transições: em vez de crossfade entre
poses completas, as molas operam sobre deltas menores.
"""

from __future__ import annotations

from math import cos, degrees, radians, sin, tau

from sejoga.animacao import locomocao_tuning as loc
from sejoga.animacao import movimento_corpo_tuning as tune
from sejoga.animacao import sono_tuning as sono
from sejoga.animacao.braco_hpr import braco_hpr_graus
from sejoga.animacao.clipes_animacao import amostrar_clipe, ciclo_da_fase
from sejoga.animacao.clipes_ocioso import camada_respiracao, sample_idle
from sejoga.animacao.interpolacao import amostrar_pista
from sejoga.animacao.movimento_corpo import BodyPose
from sejoga.animacao.pose_repouso import REPOUSO
from sejoga.animacao.ruido_procedural import delta_micro_ruido_idle
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

    return _delta_dedos(amostrar_pista(chaves, max(0.0, tempo))[2])


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


def delta_walk(
    fase: float, run: bool = False, personalidade: str = "calm"
) -> dict[str, Rotation3]:
    """Delta aditivo do estado de caminhada/corrida com modulação por personalidade.

    Parameters
    ----------
    fase:
        Fase da passada (radianos), a MESMA de ``LegMotion.phase``: os braços
        balançam em contrafase às pernas porque partilham este relógio.
    run:
        Se True, corrida (mais amplitude).
    personalidade:
        Personalidade do idle ativa para variar o estilo de caminhada.

    Returns
    -------
    Delta em radianos a ser somado à pose de repouso.
    """
    clipe = amostrar_clipe("run" if run else "walk", ciclo_da_fase(fase), personalidade)

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


def delta_sleep(t: float, modo: str = "em_pe") -> dict[str, Rotation3]:
    """Delta aditivo do estado de sono nos 3 modos: em_pe, sentado, deitado.

    Parameters
    ----------
    t:
        Tempo do clock (segundos).
    modo:
        "em_pe" (padrão), "sentado" ou "deitado".

    Returns
    -------
    Delta em radianos a ser somado à pose de repouso.
    """
    respiracao = sin(tau * sono.SONO_RESPIRACAO_HZ * t)
    afunda = 0.5 - 0.5 * cos(tau * t / sono.SONO_AFUNDA_PERIODO_S)
    curl = sono.SONO_DEDOS_CURL + respiracao * sono.SONO_DEDOS_RESPIRACAO

    if modo == "sentado":
        delta = {
            "body": Rotation3(
                radians(sono.SONO_SENTADO_CORPO_X + respiracao * sono.SONO_RESPIRACAO_PEITO),
                0,
                radians(-3.0),
            ),
            "cintura": Rotation3(radians(4.0), 0, 0),
            "abdomen": Rotation3(radians(6.0), 0, 0),
            "peitoral": Rotation3(radians(8.0), 0, 0),
            "head": Rotation3(
                radians(sono.SONO_SENTADO_CABECA_X + respiracao * sono.SONO_RESPIRACAO_CABECA + _cochilo(t)),
                0,
                radians(sono.SONO_SENTADO_CABECA_Z),
            ),
            "coxa-direita": Rotation3(radians(sono.SONO_SENTADO_COXA_GRAUS), 0, 0),
            "coxa-esquerda": Rotation3(radians(sono.SONO_SENTADO_COXA_GRAUS), 0, 0),
            "canela-direita": Rotation3(radians(sono.SONO_SENTADO_CANELA_GRAUS), 0, 0),
            "canela-esquerda": Rotation3(radians(sono.SONO_SENTADO_CANELA_GRAUS), 0, 0),
            "joelho-direito": Rotation3(radians(sono.SONO_SENTADO_CANELA_GRAUS * 0.5), 0, 0),
            "joelho-esquerdo": Rotation3(radians(sono.SONO_SENTADO_CANELA_GRAUS * 0.5), 0, 0),
            "right-arm": Rotation3(radians(-12.0), radians(6.0), radians(sono.SONO_SENTADO_BRACO_Z)),
            "left-arm": Rotation3(radians(-12.0), radians(-6.0), radians(-sono.SONO_SENTADO_BRACO_Z)),
            "ant-arm": Rotation3(radians(-8.0), 0, radians(sono.SONO_SENTADO_ANTEBRACO_Z)),
            "ant-arm2": Rotation3(radians(-8.0), 0, radians(-sono.SONO_SENTADO_ANTEBRACO_Z)),
        }
        delta.update(_delta_dedos(curl))
        return delta

    if modo == "deitado":
        delta = {
            "body": Rotation3(
                radians(respiracao * sono.SONO_RESPIRACAO_PEITO * 0.8),
                0,
                radians(sono.SONO_DEITADO_ROLL),
            ),
            "cintura": Rotation3(0, 0, radians(-4.0)),
            "head": Rotation3(
                radians(-6.0 + respiracao * sono.SONO_RESPIRACAO_CABECA),
                0,
                radians(-10.0),
            ),
            "coxa-direita": Rotation3(radians(sono.SONO_DEITADO_COXA_GRAUS), 0, radians(8.0)),
            "coxa-esquerda": Rotation3(radians(sono.SONO_DEITADO_COXA_GRAUS * 0.7), 0, radians(-6.0)),
            "canela-direita": Rotation3(radians(sono.SONO_DEITADO_CANELA_GRAUS), 0, 0),
            "canela-esquerda": Rotation3(radians(sono.SONO_DEITADO_CANELA_GRAUS * 0.8), 0, 0),
            "joelho-direito": Rotation3(radians(sono.SONO_DEITADO_CANELA_GRAUS * 0.5), 0, 0),
            "joelho-esquerdo": Rotation3(radians(sono.SONO_DEITADO_CANELA_GRAUS * 0.4), 0, 0),
            "right-arm": Rotation3(radians(-10.0), 0, radians(sono.SONO_DEITADO_BRACO_Z)),
            "left-arm": Rotation3(radians(-16.0), 0, radians(-sono.SONO_DEITADO_BRACO_Z * 0.8)),
            "ant-arm": Rotation3(0, 0, radians(sono.SONO_DEITADO_ANTEBRACO_Z)),
            "ant-arm2": Rotation3(0, 0, radians(-sono.SONO_DEITADO_ANTEBRACO_Z)),
        }
        delta.update(_delta_dedos(curl))
        return delta

    # Padrão: "em_pe" (dormir em pé)
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

    return amostrar_pista(chaves, t % sono.SONO_COCHILO_PERIODO_S)[0]


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

    bp = _peito(motion.pitch)
    by = _peito(motion.yaw)
    br = _peito(motion.roll)
    hp = radians(motion.head_pitch)
    hr = radians(motion.head_roll)

    return {
        "body": Rotation3(bp, by, br),
        "cintura": Rotation3(bp * 0.15, by * 0.15, br * 0.15),
        "abdomen": Rotation3(bp * 0.25, by * 0.25, br * 0.25),
        "peitoral": Rotation3(bp * 0.35, by * 0.35, br * 0.35),
        "head": Rotation3(hp, 0, hr),
        "fones": Rotation3(-hp * 0.18, 0.0, -hr * 0.22),
        "antena-direita": Rotation3(-hp * 0.35, 0.0, -hr * 0.40),
        "antena-esquerda": Rotation3(-hp * 0.35, 0.0, -hr * 0.40),
    }


def _pulso_idle(
    t: float,
    period: float,
    attack: float,
    hold: float,
    release: float,
    offset: float = 0.0,
) -> float:
    """Pulso suavizado por hermite para gestos de mão no idle."""
    phase = (t + offset) % period

    def ease(v: float) -> float:
        v = max(0.0, min(1.0, v))
        return v * v * (3.0 - 2.0 * v)

    if phase < attack:
        return ease(phase / attack)
    phase -= attack
    if phase < hold:
        return 1.0
    phase -= hold
    if phase < release:
        return 1.0 - ease(phase / release)
    return 0.0


def delta_secundario(
    t: float,
    state: str,
    personality: IdlePersonality,
    delta_estado: dict[str, Rotation3],
) -> dict[str, Rotation3]:
    """Delta aditivo da camada secundária (FOLLOW_THROUGH) para o LayerStack.

    Garante que nos estados migrados (``idle``, ``walk``, ``run``, ``drag``,
    ``fall``, ``sleep``) os nós de coluna (``cintura``, ``abdomen``,
    ``peitoral``), acessórios (``fones``, ``fone-direito/esquerdo``,
    ``antena-direita/esquerda``), clavículas (``shoulder``, ``shoulder2``),
    cotovelos (``ant-arm``, ``ant-arm2``), punhos (``hand``, ``hand2``) e dedos
    recebam o follow-through orgânico que antes era descartado pelo LayerStack.
    """
    escala_ruido = 1.0 if state in ("idle", "hover") else 0.45
    micro = delta_micro_ruido_idle(t, escala=escala_ruido)
    cabeca = delta_estado.get("head", Rotation3())
    corpo = delta_estado.get("body", Rotation3())
    head_x, head_y, head_z = degrees(cabeca.x), degrees(cabeca.y), degrees(cabeca.z)
    body_x, body_y, body_z = degrees(corpo.x), degrees(corpo.y), degrees(corpo.z)

    saida: dict[str, Rotation3] = {}

    # 1. Coluna distribuída (cintura -> abdomen -> peitoral) + micro-ruído
    for nome, fracao in (
        ("cintura", 0.22),
        ("abdomen", 0.32),
        ("peitoral", 0.44),
    ):
        r_micro = micro.get(nome, Rotation3())
        saida[nome] = Rotation3(
            radians(body_x * fracao) + r_micro.x,
            radians(body_y * fracao) + r_micro.y,
            radians(body_z * fracao) + r_micro.z,
        )

    # 2. Fones e antenas com contra-balanço em relação à cabeça + micro-ruído
    r_fones = micro.get("fones", Rotation3())
    saida["fones"] = Rotation3(
        radians(-head_x * 0.14) + r_fones.x,
        radians(-head_y * 0.10) + r_fones.y,
        radians(-head_z * 0.18) + r_fones.z,
    )
    for lado_sinal, nome_fone, nome_antena in (
        (1.0, "fone-direito", "antena-direita"),
        (-1.0, "fone-esquerdo", "antena-esquerda"),
    ):
        saida[nome_fone] = Rotation3(
            radians(-head_x * 0.10),
            radians(-head_y * 0.08),
            radians(-head_z * 0.20 + lado_sinal * sin(t * 1.1) * 0.6),
        )
        r_ant = micro.get(nome_antena, Rotation3())
        saida[nome_antena] = Rotation3(
            radians(-head_x * 0.32) + r_ant.x,
            radians(-head_y * 0.24) + r_ant.y,
            radians(-head_z * 0.42) + r_ant.z,
        )

    # 3. Ombros, cotovelos, punhos e dedos (follow-through secundário)
    sway_scale = {
        "idle": 2.4,
        "hover": 2.8,
        "walk": 4.2,
        "run": 5.8,
        "dance": 5.5,
        "drag": 2.5,
        "fall": 2.5,
        "sleep": 0.4,
    }.get(state, 1.8)

    for forearm, shoulder, hand, fingers, side in (
        ("ant-arm", "shoulder", "hand", "fingers", 1),
        ("ant-arm2", "shoulder2", "hand2", "fingers2", -1),
    ):
        base_rep = _BASE_REPOUSO_GRAUS[forearm]
        delta_arm = delta_estado.get(forearm, Rotation3())
        arm_x = base_rep[0] + degrees(delta_arm.x)
        arm_z = base_rep[2] + degrees(delta_arm.z)

        saida[shoulder] = Rotation3(
            radians(max(-4.0, min(4.0, arm_x * 0.14)) + sin(t * 0.9 - side * 0.4) * 1.1),
            0.0,
            radians(side * sin(t * 0.75 - side * 0.5) * 1.4),
        )
        if state in ("idle", "hover"):
            saida[forearm] = Rotation3(
                radians(sin(t * 0.8 - side * 0.45) * 2.2),
                0.0,
                radians(side * sin(t * 0.8 - side * 0.6) * 3.4),
            )
        wrist_follow = max(-10.0, min(10.0, -arm_z * 0.22))
        hand_sway = sin(t * 0.58 - side * 0.35) * sway_scale
        wrist_pitch = -arm_x * 0.24 + sin(t * 0.52 - side * 0.3) * 2.4
        idle_wrist = 0.0
        amplitude = (
            7.5
            if personality in (IdlePersonality.CURIOUS, IdlePersonality.PLAYFUL)
            else 5.0
        )
        curl = 12.0 + sin(t * 0.62 - side * 0.3) * amplitude + wrist_follow * 0.3
        if state == "idle":
            if personality == IdlePersonality.CURIOUS and side == 1:
                reach = _pulso_idle(t, 7.8, 0.65, 0.55, 0.9, offset=1.0)
                idle_wrist += 15.0 * reach
                curl -= 5.0 * reach
            elif personality == IdlePersonality.PLAYFUL and side == 1:
                flick = _pulso_idle(t, 4.8, 0.18, 0.08, 0.35, offset=0.7)
                idle_wrist += 10.0 * flick
                curl -= 8.0 * flick
            elif personality == IdlePersonality.SHY:
                fidget = _pulso_idle(t, 6.2, 0.5, 0.2, 0.6, offset=side * 0.8)
                idle_wrist += side * 4.5 * fidget
        saida[hand] = Rotation3(
            radians(wrist_pitch),
            0.0,
            radians(wrist_follow + side * hand_sway + idle_wrist),
        )
        if state not in ("drag", "fall", "sleep"):
            saida[fingers] = Rotation3(0.0, 0.0, radians(side * curl))

    return saida
