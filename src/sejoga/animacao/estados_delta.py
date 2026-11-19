"""Funções delta para cada estado de animação.

Cada função retorna um delta (diferença) sobre a pose de repouso, não uma pose
absoluta. Isso permite composição aditiva via LayerStack.

O padrão "delta" resolve os problemas de valores inconsistentes (z=62, z=65,
z=68 em diferentes estados) e simplifica transições: em vez de crossfade entre
poses completas, as molas operam sobre deltas menores.
"""

from __future__ import annotations

from math import cos, degrees, pi, radians, sin, tau

from sejoga.animacao import locomocao_tuning as loc
from sejoga.animacao import movimento_corpo_tuning as tune
from sejoga.animacao import sono_tuning as sono
from sejoga.animacao.arcos_autorais import idle_arco_composto
from sejoga.animacao.braco_hpr import braco_hpr_graus
from sejoga.animacao.clipes_animacao import amostrar_clipe, ciclo_da_fase
from sejoga.animacao.clipes_ocioso import camada_respiracao, sample_idle
from sejoga.animacao.dados_autorais import reacoes_ativas
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
    look_direction: float = 0.0,
    look_vertical: float = 0.0,
    torso_look_direction: float | None = None,
    torso_look_vertical: float | None = None,
) -> dict[str, Rotation3]:
    """Delta aditivo do estado idle sobre a pose de repouso.

    A base é ``rig_base.pose_repouso`` (IK do alvo de idle).
    Idle adiciona a oscilação própria da personalidade, respiração e olhar
    vivo com sobreposição (cabeça guia, peitoral/ombros acompanham depois).

    Parameters
    ----------
    t:
        Tempo do clock de idle (segundos).
    personality:
        Personalidade ativa do idle (calm, curious, playful, etc.).
    respiracao:
        Valor centrado (-1..1) da respiração. Default 0.
    look_direction, look_vertical:
        Direção do foco de atenção (-1..1) para cabeça em repouso.
    torso_look_direction, torso_look_vertical:
        Versão atrasada do foco para ação sobreposta do tronco superior.

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

    # Princípio 7 (Arcos): figura-8 lemniscata orgânica em cascata garante que nenhuma
    # personalidade congele em linha reta ou no trecho inicial de respiração.
    escala_arco = (
        0.28
        if personality in (IdlePersonality.CALM, IdlePersonality.SHY)
        else (
            0.52
            if personality in (IdlePersonality.PLAYFUL, IdlePersonality.VIBING, IdlePersonality.RHYTHM)
            else 0.40
        )
    )
    for grupo, (ax, ay, az) in idle_arco_composto(t, frequencia_base=0.18).items():
        base_delta = delta.get(grupo, Rotation3())
        delta[grupo] = Rotation3(
            base_delta.x + radians(ax * escala_arco),
            base_delta.y + radians(ay * escala_arco),
            base_delta.z + radians(az * escala_arco),
        )

    # Olhar em repouso: micro-pausa com vida, cabeça guia e peitoral/ombros seguem com atraso.
    dir_c = max(-1.0, min(1.0, look_direction))
    ver_c = max(-1.0, min(1.0, look_vertical))
    dir_t = dir_c if torso_look_direction is None else max(-1.0, min(1.0, torso_look_direction))
    ver_t = ver_c if torso_look_vertical is None else max(-1.0, min(1.0, torso_look_vertical))
    if abs(dir_c) > 1e-4 or abs(ver_c) > 1e-4 or abs(dir_t) > 1e-4 or abs(ver_t) > 1e-4:
        pulso_vida = 1.0 + 0.08 * sin(t * 0.9)
        acrescimos = {
            "head": (-ver_c * 13.0 * pulso_vida, dir_c * 20.0 * pulso_vida, dir_c * 2.5),
            "peitoral": (-ver_t * 2.2, dir_t * 3.8, dir_t * 1.2),
            "shoulder": (0.0, 0.0, -dir_t * 1.4),
            "shoulder2": (0.0, 0.0, -dir_t * 1.4),
        }
        for grupo, (ax, ay, az) in acrescimos.items():
            base_delta = delta.get(grupo, Rotation3())
            delta[grupo] = Rotation3(
                base_delta.x + radians(ax),
                base_delta.y + radians(ay),
                base_delta.z + radians(az),
            )

    # Respiração sobre a pose do estilo ativo.
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


def delta_hover(
    t: float,
    personality: IdlePersonality,
    respiracao: float = 0.0,
    look_direction: float = 0.0,
    look_vertical: float = 0.0,
    torso_look_direction: float | None = None,
    torso_look_vertical: float | None = None,
) -> dict[str, Rotation3]:
    """Delta aditivo do estado hover: base de idle + alcance direcional ao cursor."""
    delta = delta_idle(
        t,
        personality,
        respiracao,
        look_direction=look_direction,
        look_vertical=look_vertical,
        torso_look_direction=torso_look_direction,
        torso_look_vertical=torso_look_vertical,
    )
    dir_c = max(-1.0, min(1.0, look_direction))
    ver_c = max(-1.0, min(1.0, look_vertical))
    right_reach = max(0.0, -dir_c) ** 1.3
    left_reach = max(0.0, dir_c) ** 1.3
    down = max(0.0, ver_c)
    up = max(0.0, -ver_c)
    acrescimos = {
        "head": (-ver_c * 13.0, dir_c * 20.0, 0.0),
        "right-arm": (
            -3.0 - up * 10.0,
            0.0,
            -40.0 * right_reach - 18.0 * up + 10.0 * down,
        ),
        "left-arm": (
            -3.0 - up * 10.0,
            0.0,
            40.0 * left_reach + 18.0 * up - 10.0 * down,
        ),
        "ant-arm": (-5.0 - up * 12.0, 0.0, 54.0 * right_reach + 14.0 * up),
        "ant-arm2": (-5.0 - up * 12.0, 0.0, -54.0 * left_reach - 14.0 * up),
        "hand": (0.0, 0.0, -5.0 * right_reach),
        "hand2": (0.0, 0.0, 5.0 * left_reach),
        "fingers": (0.0, 0.0, -5.0 * right_reach),
        "fingers2": (0.0, 0.0, 5.0 * left_reach),
        "door": (0.0, 20.0, 0.0),
    }
    for grupo, (ax, ay, az) in acrescimos.items():
        base_delta = delta.get(grupo, Rotation3())
        delta[grupo] = Rotation3(
            base_delta.x + radians(ax),
            base_delta.y + radians(ay),
            base_delta.z + radians(az),
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


def misturar_deltas_seletivo(
    base: dict[str, Rotation3], alvo: dict[str, Rotation3], peso: float
) -> dict[str, Rotation3]:
    """Interpola apenas as juntas presentes em ``alvo``, preservando o resto de ``base``."""
    u = max(0.0, min(1.0, peso))
    if u <= 0.0 or not alvo:
        return dict(base)
    resultado = dict(base)
    for grupo, rot_alvo in alvo.items():
        resultado[grupo] = _misturar_rot(resultado.get(grupo, Rotation3()), rot_alvo, u)
    return resultado


def _misturar_rot(a: Rotation3, b: Rotation3, t: float) -> Rotation3:
    """Interpola linearmente duas rotações em radianos."""
    u = max(0.0, min(1.0, t))
    return Rotation3(
        a.x + (b.x - a.x) * u,
        a.y + (b.y - a.y) * u,
        a.z + (b.z - a.z) * u,
    )


def delta_absoluto_para_repouso(
    grupo: str, x_tot: float, y_tot: float, z_tot: float
) -> Rotation3:
    """Converte pose alvo em graus totais para delta aditivo sobre ``pose_repouso``."""
    bx, by, bz = _BASE_REPOUSO_GRAUS.get(grupo, (0.0, 0.0, 0.0))
    return Rotation3(
        radians(x_tot - bx),
        radians(y_tot - by),
        radians(z_tot - bz),
    )


_delta_absoluto_para_repouso = delta_absoluto_para_repouso


def _angulos_pendulo_braco(
    z_orientado: float, balanco_graus: float
) -> tuple[float, float, float, float]:
    """Calcula ``(z_eff, x_fwd, y_fwd, cotovelo)`` para o braço sob gravidade."""
    if z_orientado > 68.0:
        t = min(1.0, (z_orientado - 68.0) / 36.0)
        return (68.0 + 4.0 * t, -22.0 * t, -14.0 * t, 16.0 + 18.0 * t)
    if z_orientado < -75.0:
        t = min(1.0, (-75.0 - z_orientado) / 35.0)
        return (-75.0 - 35.0 * t, 40.0 * t, 50.0 * t, 14.0 + 14.0 * t)
    return (z_orientado, 0.0, 0.0, 14.0 + min(18.0, abs(balanco_graus) * 0.35))


def _braco_pendente_mundo(
    lado: str, roll_graus: float, pitch_graus: float, balanco_graus: float
) -> dict[str, Rotation3]:
    """Alinha o braço com a gravidade do mundo (0°..360°+), evitando atravessar peito e cabeça."""
    sinal = 1.0 if lado == "right" else -1.0
    grupo_braco = "right-arm" if lado == "right" else "left-arm"
    grupo_ante = "ant-arm" if lado == "right" else "ant-arm2"
    z_raw = ((74.0 * sinal - roll_graus + balanco_graus + 180.0) % 360.0) - 180.0
    z_eff, x_fwd, y_fwd, cotovelo = _angulos_pendulo_braco(sinal * z_raw, balanco_graus)
    pitch_clamped = max(-15.0, min(15.0, pitch_graus * 0.30))
    return {
        grupo_braco: _delta_absoluto_para_repouso(
            grupo_braco, x_fwd - pitch_clamped, sinal * y_fwd, sinal * z_eff
        ),
        grupo_ante: _delta_absoluto_para_repouso(
            grupo_ante, 0.0, 0.0, sinal * cotovelo
        ),
    }


def _delta_drag_braco_pego(
    delta: dict[str, Rotation3],
    motion: BodyPose,
    grab_part: str,
    fator_upe: float,
    atraso: float,
) -> None:
    """Pega por um braço: braço segurado estica, livre pende e busca o cursor."""
    pego_dir = grab_part == "right-arm"
    lado_livre = "left" if pego_dir else "right"
    sinal_pego = 1.0 if pego_dir else -1.0
    braco_pego = "right-arm" if pego_dir else "left-arm"
    ante_pego = "ant-arm" if pego_dir else "ant-arm2"
    braco_livre = "left-arm" if pego_dir else "right-arm"
    ante_livre = "ant-arm2" if pego_dir else "ant-arm"

    delta[braco_pego] = _delta_absoluto_para_repouso(
        braco_pego, -8.0 - motion.pitch * 0.20, -4.0 * sinal_pego, -64.0 * sinal_pego
    )
    delta[ante_pego] = _delta_absoluto_para_repouso(
        ante_pego, 0.0, 0.0, 8.0 * sinal_pego
    )
    delta.update(_braco_pendente_mundo(lado_livre, motion.roll, motion.pitch, atraso))

    t_alcance = max(0.0, min(1.0, getattr(motion, "reach_cursor", 0.0))) * max(
        0.0, fator_upe
    )
    if t_alcance > 0.01:
        alcance = _delta_braco_ik("drag_alcance")
        delta[braco_livre] = _misturar_rot(
            delta[braco_livre], alcance[braco_livre], t_alcance * 0.7
        )
        delta[ante_livre] = _misturar_rot(
            delta[ante_livre], alcance[ante_livre], t_alcance * 0.7
        )

    delta["head"] = Rotation3(
        radians(-8.0 * max(0.0, fator_upe) + 12.0 * max(0.0, -fator_upe)),
        radians(motion.yaw * 0.6),
        radians(motion.head_roll * 0.8 + motion.limb_swing * 0.12),
    )


def _delta_drag_cabeca(
    delta: dict[str, Rotation3],
    motion: BodyPose,
    roll_rad: float,
    atraso: float,
) -> None:
    """Pego pela cabeça: torso em S e braços livres pendendo com a gravidade."""
    jolt = getattr(motion, "surprise_jolt", 0.0)
    onda_s = motion.limb_swing * 0.65 + sin(roll_rad) * 14.0
    delta["head"] = Rotation3(
        radians(-8.0 + 14.0 * jolt),
        radians(motion.yaw * 0.9),
        radians(motion.head_roll * 1.4 - onda_s * 0.30),
    )
    delta["cintura"] = Rotation3(radians(motion.pitch * 0.30), 0.0, radians(-onda_s * 0.45))
    delta["abdomen"] = Rotation3(radians(motion.pitch * 0.15), 0.0, radians(-onda_s * 0.22))
    delta["peitoral"] = Rotation3(
        radians(-motion.pitch * 0.35 - 10.0 * jolt), 0.0, radians(onda_s * 0.55)
    )
    delta.update(_braco_pendente_mundo("right", motion.roll, motion.pitch, atraso * 0.85))
    delta.update(_braco_pendente_mundo("left", motion.roll, motion.pitch, atraso * 0.85))


def _delta_drag_bracos(motion: BodyPose, grab_part: str) -> dict[str, Rotation3]:
    """Braços, coluna e cabeça do arraste orientados pela gravidade global em 360°."""
    delta: dict[str, Rotation3] = {}
    roll_rad = radians(motion.roll)
    fator_upe = cos(roll_rad)
    atraso = motion.limb_swing * 0.65 + motion.arm_lag * 0.75

    if grab_part in ("right-arm", "left-arm"):
        _delta_drag_braco_pego(delta, motion, grab_part, fator_upe, atraso)
    elif grab_part in ("legs", "left-feet", "right-feet"):
        delta.update(_braco_pendente_mundo("right", motion.roll, motion.pitch, atraso * 0.6))
        delta.update(_braco_pendente_mundo("left", motion.roll, motion.pitch, atraso * 0.6))
        cabeca_x = tune.ARRASTE_PENDENTE_CABECA_X * max(0.0, -fator_upe) - 10.0 * max(0.0, fator_upe)
        delta["head"] = Rotation3(
            radians(cabeca_x),
            radians(motion.yaw * 0.45),
            radians(motion.head_roll * 0.7 + atraso * 0.25),
        )
    elif grab_part == "head":
        _delta_drag_cabeca(delta, motion, roll_rad, atraso)
    else:
        delta.update(_braco_pendente_mundo("right", motion.roll, motion.pitch, atraso))
        delta.update(_braco_pendente_mundo("left", motion.roll, motion.pitch, atraso))
        delta["head"] = Rotation3(
            radians(-10.0 * max(0.0, fator_upe) + 12.0 * max(0.0, -fator_upe) + motion.head_pitch * 0.5),
            radians(motion.yaw * 0.6),
            radians(motion.head_roll * 0.7 + motion.limb_swing * 0.12),
        )

    _aplicar_cadencia_arraste_tronco_maos(delta, motion, grab_part)
    return delta


def _somar_clamped(
    delta: dict[str, Rotation3],
    nome: str,
    dx_g: float,
    dy_g: float,
    dz_g: float,
) -> None:
    """Acumula rotação em graus ao nó sem sobrescrever ajustes específicos."""
    atual = delta.get(nome, Rotation3(0.0, 0.0, 0.0))
    delta[nome] = Rotation3(
        atual.x + radians(dx_g),
        atual.y + radians(dy_g),
        atual.z + radians(dz_g),
    )


def _aplicar_cadencia_arraste_tronco_maos(
    delta: dict[str, Rotation3],
    motion: BodyPose,
    grab_part: str,
) -> None:
    """Propagação procedural para coluna, braços, punhos e antenas no pêndulo com peso real."""
    roll_vel = getattr(motion, "roll_velocity", 0.0)
    susp = min(1.0, max(0.0, getattr(motion, "hanging", 0.0)))
    whip = max(-26.0, min(26.0, roll_vel * 1.25))
    centrifugo = min(1.0, max(0.0, (abs(roll_vel) - 40.0) / 160.0))
    pitch_sp = max(-16.0, min(16.0, motion.pitch * 0.36))
    yaw_sp = max(-18.0, min(18.0, motion.yaw * 0.42))
    roll_sp = max(-22.0, min(22.0, motion.limb_swing * 0.20 + whip * 0.62))
    # Coluna cede ao peso do corpo suspenso e propaga atraso da cintura ao peitoral.
    _somar_clamped(delta, "cintura", pitch_sp * 0.30 + 2.8 * susp, yaw_sp * 0.28, roll_sp * 0.32)
    _somar_clamped(delta, "abdomen", pitch_sp * 0.36 + 3.8 * susp, yaw_sp * 0.36, roll_sp * 0.38)
    _somar_clamped(delta, "peitoral", pitch_sp * 0.42 + 4.8 * susp, yaw_sp * 0.44, roll_sp * 0.44)
    punho_atraso = max(-30.0, min(30.0, motion.arm_lag * 0.56 + whip * 0.60))
    for braco, sh, ant, mao, sinal in (
        ("right-arm", "shoulder", "ant-arm", "hand", 1.0),
        ("left-arm", "shoulder2", "ant-arm2", "hand2", -1.0),
    ):
        if grab_part == braco:
            _somar_clamped(delta, sh, 0.0, 0.0, 14.0 * sinal * susp)
            continue
        ombro_z = (8.0 if grab_part == "body" else -6.0) * sinal * susp
        flare_z = -24.0 * sinal * centrifugo
        _somar_clamped(delta, braco, -pitch_sp * 0.28, yaw_sp * 0.24, roll_sp * 0.34 + ombro_z + flare_z)
        _somar_clamped(delta, sh, -2.5 * susp, 0.0, -ombro_z * 0.8 - 6.0 * sinal * centrifugo)
        _somar_clamped(delta, ant, 0.0, 0.0, -14.0 * sinal * centrifugo)
        _somar_clamped(delta, mao, pitch_sp * 0.34 + 10.0 * centrifugo, yaw_sp * 0.28, sinal * (punho_atraso + 10.0 * susp))
    _somar_clamped(delta, "fones", -pitch_sp * 0.18, 0.0, roll_sp * 0.24)
    for ant_nome, s_ant in (("antena-direita", -1.0), ("antena-esquerda", 1.0)):
        _somar_clamped(delta, ant_nome, -pitch_sp * 0.30, 0.0, roll_sp * 0.42 + s_ant * 10.0 * centrifugo)
    if grab_part == "head":
        _somar_clamped(delta, "head", -pitch_sp * 0.34 - 5.0 * susp, yaw_sp * 0.30, -roll_sp * 0.28)
    elif susp > 0.05:
        _somar_clamped(delta, "head", 4.5 * susp, 0.0, roll_sp * 0.16)


def _somar(
    rot: Rotation3, *, x: float = 0.0, y: float = 0.0, z: float = 0.0
) -> Rotation3:
    """Soma graus (convertidos) a um ``Rotation3`` em radianos."""
    return Rotation3(rot.x + radians(x), rot.y + radians(y), rot.z + radians(z))


def _somar_z(rot: Rotation3, z_graus: float) -> Rotation3:
    """Soma só o eixo Z (graus) a um ``Rotation3`` em radianos."""
    return Rotation3(rot.x, rot.y, rot.z + radians(z_graus))


def delta_walk(fase: float, run: bool = False) -> dict[str, Rotation3]:
    """Delta aditivo do estado de caminhada ou corrida.

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


def _parametros_voo_queda(
    t: float, velocity: tuple[float, float]
) -> tuple[float, float, float, float, float, float, float, float, float, float, float]:
    """Calcula parâmetros cinemáticos de pânico, flail e inclinação para ``delta_fall``."""
    vx, vy = velocity
    ascending = vy < 0

    u_onset = max(0.0, min(1.0, t / 0.28))
    e_onset = u_onset * u_onset * u_onset * (10.0 + u_onset * (-15.0 + 6.0 * u_onset))
    apice = sin(u_onset * pi)

    speed_norm = min(1.0, (abs(vx) * 0.6 + abs(vy)) / loc.QUEDA_VENTO_SATURACAO)
    # Ramp progressivo nos primeiros 0.28s suaviza a saída do arraste/pulo para a queda livre.
    panic = max(0.16, speed_norm) * (0.22 + 0.78 * e_onset)
    head_tilt = (
        -loc.QUEDA_CABECA_INCLINACAO * (0.5 + 0.5 * speed_norm)
        if ascending
        else loc.QUEDA_CABECA_INCLINACAO * (0.45 + 0.55 * speed_norm)
    ) * (0.30 + 0.70 * e_onset) - 8.0 * apice

    fase_dir = t * loc.QUEDA_FLAIL_VELOCIDADE
    fase_esq = fase_dir + 2.2
    flail_dir = sin(fase_dir) * loc.QUEDA_FLAIL_Z * panic
    flail_esq = sin(fase_esq) * loc.QUEDA_FLAIL_Z * panic
    flail_y_dir = cos(fase_dir) * loc.QUEDA_FLAIL_Z * loc.QUEDA_FLAIL_Y_FRACAO * panic
    flail_y_esq = cos(fase_esq) * loc.QUEDA_FLAIL_Z * loc.QUEDA_FLAIL_Y_FRACAO * panic
    cotovelo_dir = flail_dir**2 / loc.QUEDA_FLAIL_Z * loc.QUEDA_FLAIL_COTOVELO_FRACAO
    cotovelo_esq = flail_esq**2 / loc.QUEDA_FLAIL_Z * loc.QUEDA_FLAIL_COTOVELO_FRACAO
    tumble = max(
        -loc.QUEDA_TUMBLE_MAX_GRAUS,
        min(loc.QUEDA_TUMBLE_MAX_GRAUS, vx * loc.QUEDA_TUMBLE_GRAUS_POR_PX),
    ) * e_onset
    assimetria = (flail_dir - flail_esq) * 0.14
    arqueado = (-5.0 * (1.0 if ascending else -0.6) * panic) - 6.5 * apice
    return (
        head_tilt,
        flail_dir,
        flail_esq,
        flail_y_dir,
        flail_y_esq,
        cotovelo_dir,
        cotovelo_esq,
        tumble,
        assimetria,
        arqueado,
        apice,
    )


def delta_fall(
    t: float, velocity: tuple[float, float] = (0, 0)
) -> dict[str, Rotation3]:
    """Delta aditivo do estado de queda.

    Passa por uma fase breve de soltura no ápice (hang-time) antes de evoluir
    para braços em moinho assimétrico e torção aérea proporcional à velocidade.
    """
    (
        head_tilt,
        flail_dir,
        flail_esq,
        flail_y_dir,
        flail_y_esq,
        cotovelo_dir,
        cotovelo_esq,
        tumble,
        assimetria,
        arqueado,
        apice,
    ) = _parametros_voo_queda(t, velocity)

    delta = _delta_braco_ik("fall")
    delta["head"] = Rotation3(
        radians(head_tilt),
        radians(-assimetria * 0.8),
        radians((flail_dir + flail_esq) * 0.3 * loc.QUEDA_FLAIL_CABECA_FRACAO),
    )
    delta["body"] = Rotation3(
        radians(arqueado * 0.5),
        radians(assimetria * 0.6),
        radians(tumble),
    )
    delta["cintura"] = Rotation3(radians(arqueado * 0.35), radians(assimetria * 0.45), 0.0)
    delta["abdomen"] = Rotation3(radians(arqueado * 0.35), radians(-assimetria * 0.35), 0.0)
    delta["peitoral"] = Rotation3(radians(arqueado * 0.4), radians(assimetria * 0.65), 0.0)
    # Espelho (x, -y, -z): fases desencontradas e atraso no ápice evitam transição seca.
    delta["right-arm"] = _somar(
        delta["right-arm"], y=flail_y_dir - 16.0 * apice, z=flail_dir - 22.0 * apice
    )
    delta["left-arm"] = _somar(
        delta["left-arm"], y=-flail_y_esq + 16.0 * apice, z=-flail_esq + 22.0 * apice
    )
    delta["ant-arm"] = _somar(delta.get("ant-arm", Rotation3()), z=cotovelo_dir + 12.0 * apice)
    delta["ant-arm2"] = _somar(delta.get("ant-arm2", Rotation3()), z=-cotovelo_esq - 12.0 * apice)
    delta["fones"] = Rotation3(radians(-head_tilt * 0.25 - 4.0 * apice), 0.0, radians(-assimetria * 0.35))
    delta["antena-direita"] = Rotation3(radians(-head_tilt * 0.45 - 8.0 * apice), 0.0, radians(-assimetria * 0.6))
    delta["antena-esquerda"] = Rotation3(radians(-head_tilt * 0.45 - 8.0 * apice), 0.0, radians(assimetria * 0.6))
    delta.update(_delta_dedos(loc.QUEDA_DEDOS_ABERTOS))

    return delta


def _s(cfg: dict[str, object], chave: str, padrao: float) -> float:
    val = cfg.get(chave, padrao)
    return float(val) if isinstance(val, (int, float)) else padrao


def _delta_sleep_sentado(
    t: float,
    cfg: dict[str, object],
    respiracao: float,
    curl: float,
) -> dict[str, Rotation3]:
    coxa = _s(cfg, "sentado_coxa_graus", sono.SONO_SENTADO_COXA_GRAUS)
    canela = _s(cfg, "sentado_canela_graus", sono.SONO_SENTADO_CANELA_GRAUS)
    braco_z = _s(cfg, "sentado_braco_z", sono.SONO_SENTADO_BRACO_Z)
    ant_z = _s(cfg, "sentado_antebraco_z", sono.SONO_SENTADO_ANTEBRACO_Z)
    r_peito = _s(cfg, "respiracao_peito", sono.SONO_RESPIRACAO_PEITO)
    r_cab = _s(cfg, "respiracao_cabeca", sono.SONO_RESPIRACAO_CABECA)
    delta = {
        "body": Rotation3(
            radians(_s(cfg, "sentado_corpo_x", sono.SONO_SENTADO_CORPO_X) + respiracao * r_peito),
            0,
            radians(-3.0),
        ),
        "cintura": Rotation3(radians(4.0), 0, 0),
        "abdomen": Rotation3(radians(6.0), 0, 0),
        "peitoral": Rotation3(radians(8.0), 0, 0),
        "head": Rotation3(
            radians(_s(cfg, "sentado_cabeca_x", sono.SONO_SENTADO_CABECA_X) + respiracao * r_cab + _cochilo(t)),
            0,
            radians(_s(cfg, "sentado_cabeca_z", sono.SONO_SENTADO_CABECA_Z)),
        ),
        "coxa-direita": Rotation3(radians(coxa), 0, 0),
        "coxa-esquerda": Rotation3(radians(coxa), 0, 0),
        "canela-direita": Rotation3(radians(canela), 0, 0),
        "canela-esquerda": Rotation3(radians(canela), 0, 0),
        "joelho-direito": Rotation3(radians(canela * 0.5), 0, 0),
        "joelho-esquerdo": Rotation3(radians(canela * 0.5), 0, 0),
        "right-arm": Rotation3(radians(-12.0), radians(6.0), radians(braco_z)),
        "left-arm": Rotation3(radians(-12.0), radians(-6.0), radians(-braco_z)),
        "ant-arm": Rotation3(radians(-8.0), 0, radians(ant_z)),
        "ant-arm2": Rotation3(radians(-8.0), 0, radians(-ant_z)),
    }
    delta.update(_delta_dedos(curl))
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
    cfg = reacoes_ativas().get("sono", {})
    respiracao = sin(tau * _s(cfg, "respiracao_hz", sono.SONO_RESPIRACAO_HZ) * t)
    afunda = 0.5 - 0.5 * cos(tau * t / max(1.0, _s(cfg, "afunda_periodo_s", sono.SONO_AFUNDA_PERIODO_S)))
    curl = _s(cfg, "dedos_curl", sono.SONO_DEDOS_CURL) + respiracao * _s(
        cfg, "dedos_respiracao", sono.SONO_DEDOS_RESPIRACAO
    )
    if modo == "sentado":
        return _delta_sleep_sentado(t, cfg, respiracao, curl)
    r_peito = _s(cfg, "respiracao_peito", sono.SONO_RESPIRACAO_PEITO)
    r_cab = _s(cfg, "respiracao_cabeca", sono.SONO_RESPIRACAO_CABECA)
    if modo == "deitado":
        d_coxa = _s(cfg, "deitado_coxa_graus", sono.SONO_DEITADO_COXA_GRAUS)
        d_can = _s(cfg, "deitado_canela_graus", sono.SONO_DEITADO_CANELA_GRAUS)
        d_br = _s(cfg, "deitado_braco_z", sono.SONO_DEITADO_BRACO_Z)
        d_ant = _s(cfg, "deitado_antebraco_z", sono.SONO_DEITADO_ANTEBRACO_Z)
        delta = {
            "body": Rotation3(radians(respiracao * r_peito * 0.8), 0, 0),
            "cintura": Rotation3(0, 0, radians(-4.0)),
            "head": Rotation3(radians(-6.0 + respiracao * r_cab), 0, radians(-10.0)),
            "coxa-direita": Rotation3(radians(d_coxa), 0, radians(8.0)),
            "coxa-esquerda": Rotation3(radians(d_coxa * 0.7), 0, radians(-6.0)),
            "canela-direita": Rotation3(radians(d_can), 0, 0),
            "canela-esquerda": Rotation3(radians(d_can * 0.8), 0, 0),
            "joelho-direito": Rotation3(radians(d_can * 0.5), 0, 0),
            "joelho-esquerdo": Rotation3(radians(d_can * 0.4), 0, 0),
            "right-arm": Rotation3(radians(-10.0), 0, radians(d_br)),
            "left-arm": Rotation3(radians(-16.0), 0, radians(-d_br * 0.8)),
            "ant-arm": Rotation3(0, 0, radians(d_ant)),
            "ant-arm2": Rotation3(0, 0, radians(-d_ant)),
        }
        delta.update(_delta_dedos(curl))
        return delta

    delta = _delta_braco_ik("sleep")
    ombro_c = _s(cfg, "ombro_caido", sono.SONO_OMBRO_CAIDO)
    delta["right-arm"] = _somar_z(delta["right-arm"], ombro_c)
    delta["left-arm"] = _somar_z(delta["left-arm"], -ombro_c)
    delta["body"] = Rotation3(
        radians(respiracao * r_peito),
        0,
        radians(_s(cfg, "corpo_z_base", sono.SONO_CORPO_Z_BASE) + afunda * _s(cfg, "afunda_z", sono.SONO_AFUNDA_Z)),
    )
    delta["head"] = Rotation3(
        radians(_s(cfg, "cabeca_x_base", sono.SONO_CABECA_X_BASE) + respiracao * r_cab + _cochilo(t)),
        0,
        radians(_s(cfg, "cabeca_z_base", sono.SONO_CABECA_Z_BASE)),
    )
    delta.update(_delta_dedos(curl))
    return delta


def _cochilo(t: float) -> float:
    """Queda rara e suave da cabeça (graus em head.x); 0 fora do cochilo."""
    cfg = reacoes_ativas().get("sono", {})
    periodo = max(1.0, _s(cfg, "cochilo_periodo_s", sono.SONO_COCHILO_PERIODO_S))
    graus = _s(cfg, "cochilo_graus", sono.SONO_COCHILO_GRAUS)
    chaves = (
        (0.0, (0.0, 0.0, 0.0)),
        (_s(cfg, "cochilo_inicio_s", sono.SONO_COCHILO_INICIO_S), (0.0, 0.0, 0.0)),
        (_s(cfg, "cochilo_fundo_s", sono.SONO_COCHILO_FUNDO_S), (graus, 0.0, 0.0)),
        (_s(cfg, "cochilo_solta_s", sono.SONO_COCHILO_SOLTA_S), (graus, 0.0, 0.0)),
        (_s(cfg, "cochilo_volta_s", sono.SONO_COCHILO_VOLTA_S), (0.0, 0.0, 0.0)),
        (periodo, (0.0, 0.0, 0.0)),
    )

    return amostrar_pista(chaves, t % periodo)[0]


def delta_fisica(motion: BodyPose, *, pendurado: bool | None = None) -> dict[str, Rotation3]:
    """Delta da camada de física (roll, pitch, compression do BodyMotion).

    Esta camada representa a resposta física pura do corpo à inércia e
    movimento, independente do estado de animação.
    """
    # Pendurado/arrastado, o renderer já gira o mascote INTEIRO (pivô rígido no
    # ponto de pega). Somar a mesma rotação só no peito o giraria em dobro,
    # dessincronizado de braços e pernas: nesse regime o peito recebe só um
    # balanço pequeno e limitado. Na queda livre (`pendurado=False`), o tronco
    # articula completo com a coluna flexível.
    if pendurado is None:
        pendurado = motion.hanging > tune.PENDURADO_LIMIAR
    if pendurado:
        fator_peito = tune.PEITO_FATOR_PENDURADO
        limite = tune.PEITO_PENDURADO_MAX_GRAUS

        def _peito(graus: float) -> float:
            graus *= fator_peito
            return radians(max(-limite, min(limite, graus)))

        bp = _peito(motion.pitch)
        by = _peito(motion.yaw)
        br = _peito(motion.roll)
        body_rot = Rotation3(bp * 0.35, by * 0.35, br * 0.35)
        cint_rot = Rotation3(bp * 0.20, by * 0.20, br * 0.20)
        abd_rot = Rotation3(bp * 0.22, by * 0.22, br * 0.22)
        pei_rot = Rotation3(bp * 0.23, by * 0.23, br * 0.23)
    else:
        # Em pé, apply_body_motion já gira soft-spine-pivot com yaw/pitch/roll;
        # evita multiplicar a mesma rotação em body + cintura + abdomen + peitoral.
        bp = radians(motion.pitch)
        br = radians(motion.roll)
        body_rot = Rotation3()
        cint_rot = Rotation3(bp * 0.06, 0.0, br * 0.06)
        abd_rot = Rotation3(bp * 0.10, 0.0, br * 0.08)
        pei_rot = Rotation3(bp * 0.12, 0.0, br * 0.10)

    hp = radians(motion.head_pitch)
    hr = radians(motion.head_roll)

    return {
        "body": body_rot,
        "cintura": cint_rot,
        "abdomen": abd_rot,
        "peitoral": pei_rot,
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


def _gesto_punho_idle(t, personality, side, curl):
    idle_wrist = 0.0
    if personality == IdlePersonality.CURIOUS and side == 1:
        reach = _pulso_idle(t, 7.8, 0.65, 0.55, 0.9, offset=1.0)
        idle_wrist = 15.0 * reach
        curl -= 5.0 * reach
    elif personality == IdlePersonality.PLAYFUL and side == 1:
        flick = _pulso_idle(t, 4.8, 0.18, 0.08, 0.35, offset=0.7)
        idle_wrist = 10.0 * flick
        curl -= 8.0 * flick
    elif personality == IdlePersonality.SHY:
        fidget = _pulso_idle(t, 6.2, 0.5, 0.2, 0.6, offset=side * 0.8)
        idle_wrist = side * 4.5 * fidget
    return idle_wrist, curl


def _delta_bracos_secundarios(saida, state, delta_estado, t, personality):
    sway_scale = {
        "idle": 1.2,
        "hover": 2.4,
        "walk": 4.2,
        "run": 5.8,
        "dance": 5.5,
        "drag": 2.5,
        "fall": 2.5,
        "sleep": 0.4,
    }.get(state, 1.8)

    for upper_arm, forearm, shoulder, hand, fingers, side in (
        ("right-arm", "ant-arm", "shoulder", "hand", "fingers", 1),
        ("left-arm", "ant-arm2", "shoulder2", "hand2", "fingers2", -1),
    ):
        base_rep = _BASE_REPOUSO_GRAUS[forearm]
        delta_arm = delta_estado.get(forearm, Rotation3())
        arm_x = base_rep[0] + degrees(delta_arm.x)
        arm_z = base_rep[2] + degrees(delta_arm.z)

        saida[shoulder] = Rotation3(
            radians(max(-4.0, min(4.0, arm_x * 0.14)) + sin(t * 0.9 - side * 0.4) * 0.7),
            0.0,
            radians(side * sin(t * 0.75 - side * 0.5) * 0.8),
        )
        fase_braco = t * 1.15 - side * 0.85
        amp_ombro = 3.2 if state == "idle" else 7.5
        amp_cot = 3.0 if state == "idle" else 7.5
        if state in ("idle", "hover"):
            # Heading no ombro avança o braço; roll no antebraço dobra o cotovelo.
            saida[upper_arm] = Rotation3(0.0, radians(side * amp_ombro * sin(fase_braco)), 0.0)
            saida[forearm] = Rotation3(
                radians((1.4 if state == "idle" else 2.8) * sin(fase_braco - 0.35)),
                0.0,
                radians(side * (2.0 + amp_cot * sin(fase_braco - 0.55))),
            )
        wrist_follow = max(-10.0, min(10.0, -arm_z * 0.22))
        hand_sway = sin(t * 0.58 - side * 0.35) * sway_scale
        wrist_pitch = -arm_x * 0.24 + sin(t * 0.52 - side * 0.3) * (1.4 if state == "idle" else 2.4)
        if state in ("idle", "hover"):
            wrist_pitch += (2.5 if state == "idle" else 6.0) * sin(fase_braco - 0.85)
        idle_wrist = 0.0
        amplitude = (
            7.5
            if personality in (IdlePersonality.CURIOUS, IdlePersonality.PLAYFUL)
            else 5.0
        )
        curl = 3.0 + sin(t * 0.62 - side * 0.3) * amplitude + wrist_follow * 0.3
        if state == "idle":
            idle_wrist, curl = _gesto_punho_idle(t, personality, side, curl)
        saida[hand] = Rotation3(
            radians(wrist_pitch),
            0.0,
            radians(wrist_follow + side * hand_sway + idle_wrist),
        )
        if state not in ("drag", "fall", "sleep"):
            saida[fingers] = Rotation3(0.0, 0.0, radians(side * curl))


def _delta_antenas(saida, micro, t, head_x, head_y, head_z):
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


def _delta_coluna(saida, micro, corpo):
    del corpo  # clipes já animam cintura/peitoral; não multiplicar body na coluna
    for nome in ("cintura", "abdomen", "peitoral"):
        r_micro = micro.get(nome)
        if r_micro is not None:
            saida[nome] = Rotation3(r_micro.x, r_micro.y, r_micro.z)


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
    saida: dict[str, Rotation3] = {}

    _delta_coluna(saida, micro, corpo)

    # 2. Fones e antenas com contra-balanço em relação à cabeça + micro-ruído
    r_fones = micro.get("fones", Rotation3())
    saida["fones"] = Rotation3(
        radians(-head_x * 0.14) + r_fones.x,
        radians(-head_y * 0.10) + r_fones.y,
        radians(-head_z * 0.18) + r_fones.z,
    )
    _delta_antenas(saida, micro, t, head_x, head_y, head_z)
    _delta_bracos_secundarios(saida, state, delta_estado, t, personality)
    return saida


def _amostrar_trilhas_conexao(
    trilhas: dict[str, tuple[tuple[float, tuple[float, float, float]], ...]],
    tempo: float,
) -> dict[str, Rotation3]:
    """Amostra trilhas de conexão em graus e devolve ``Rotation3`` em radianos."""
    return {
        grupo: Rotation3(*(radians(v) for v in amostrar_pista(chaves, tempo)))
        for grupo, chaves in trilhas.items()
    }


def _trilhas_freada_run(duracao: float) -> dict[str, tuple[tuple[float, tuple[float, float, float]], ...]]:
    return {
        "cintura": ((0.0, (0.0, 0.0, 0.0)), (0.13, (-4.5, 0.0, -1.5)), (0.34, (4.2, 0.0, 1.2)), (0.52, (-1.2, 0.0, 0.0)), (duracao, (0.0, 0.0, 0.0))),
        "abdomen": ((0.0, (0.0, 0.0, 0.0)), (0.14, (-5.5, 0.0, 1.0)), (0.35, (5.5, 0.0, -0.8)), (0.54, (-1.5, 0.0, 0.0)), (duracao, (0.0, 0.0, 0.0))),
        "peitoral": ((0.0, (0.0, 0.0, 0.0)), (0.15, (-7.0, 0.0, 1.8)), (0.36, (7.8, 0.0, -1.5)), (0.55, (-2.0, 0.0, 0.0)), (duracao, (0.0, 0.0, 0.0))),
        "shoulder": ((0.0, (0.0, 0.0, 0.0)), (0.16, (-4.0, -2.5, 5.5)), (0.38, (2.5, 1.5, -2.5)), (0.56, (-0.8, 0.0, 0.8)), (duracao, (0.0, 0.0, 0.0))),
        "shoulder2": ((0.0, (0.0, 0.0, 0.0)), (0.16, (-4.0, 2.5, -5.5)), (0.38, (2.5, -1.5, 2.5)), (0.56, (-0.8, 0.0, -0.8)), (duracao, (0.0, 0.0, 0.0))),
        "right-arm": ((0.0, (0.0, 0.0, 0.0)), (0.16, (4.0, -6.5, -16.0)), (0.38, (-2.5, 7.5, 3.5)), (0.56, (0.8, -2.0, -1.0)), (duracao, (0.0, 0.0, 0.0))),
        "left-arm": ((0.0, (0.0, 0.0, 0.0)), (0.16, (4.0, 6.5, 16.0)), (0.38, (-2.5, -7.5, -3.5)), (0.56, (0.8, 2.0, 1.0)), (duracao, (0.0, 0.0, 0.0))),
        "ant-arm": ((0.0, (0.0, 0.0, 0.0)), (0.18, (0.0, 0.0, 16.0)), (0.42, (0.0, 0.0, -2.5)), (duracao, (0.0, 0.0, 0.0))),
        "ant-arm2": ((0.0, (0.0, 0.0, 0.0)), (0.18, (0.0, 0.0, -16.0)), (0.42, (0.0, 0.0, 2.5)), (duracao, (0.0, 0.0, 0.0))),
        "hand": ((0.0, (0.0, 0.0, 0.0)), (0.24, (11.0, -7.0, 10.0)), (0.48, (-6.5, 4.0, -5.0)), (duracao, (0.0, 0.0, 0.0))),
        "hand2": ((0.0, (0.0, 0.0, 0.0)), (0.24, (11.0, 7.0, -10.0)), (0.48, (-6.5, -4.0, 5.0)), (duracao, (0.0, 0.0, 0.0))),
        "head": ((0.0, (0.0, 0.0, 0.0)), (0.16, (5.5, 0.0, -1.5)), (0.38, (-4.5, 0.0, 1.2)), (0.55, (1.2, 0.0, 0.0)), (duracao, (0.0, 0.0, 0.0))),
        "fones": ((0.0, (0.0, 0.0, 0.0)), (0.24, (-7.5, 0.0, 2.5)), (0.48, (5.0, 0.0, -1.8)), (duracao, (0.0, 0.0, 0.0))),
        "antena-direita": ((0.0, (0.0, 0.0, 0.0)), (0.26, (-13.0, 0.0, 5.0)), (0.50, (8.0, 0.0, -3.5)), (duracao, (0.0, 0.0, 0.0))),
        "antena-esquerda": ((0.0, (0.0, 0.0, 0.0)), (0.26, (-13.0, 0.0, -5.0)), (0.50, (8.0, 0.0, 3.5)), (duracao, (0.0, 0.0, 0.0))),
    }


def _trilhas_freada_walk(duracao: float) -> dict[str, tuple[tuple[float, tuple[float, float, float]], ...]]:
    return {
        "cintura": ((0.0, (0.0, 0.0, 0.0)), (0.12, (-2.2, 0.0, 0.0)), (0.29, (2.0, 0.0, 0.0)), (duracao, (0.0, 0.0, 0.0))),
        "abdomen": ((0.0, (0.0, 0.0, 0.0)), (0.13, (-2.8, 0.0, 0.0)), (0.31, (2.6, 0.0, 0.0)), (duracao, (0.0, 0.0, 0.0))),
        "peitoral": ((0.0, (0.0, 0.0, 0.0)), (0.14, (-3.6, 0.0, 0.0)), (0.32, (3.4, 0.0, 0.0)), (duracao, (0.0, 0.0, 0.0))),
        "shoulder": ((0.0, (0.0, 0.0, 0.0)), (0.15, (-2.5, -1.5, 3.2)), (0.34, (1.2, 0.8, -1.2)), (duracao, (0.0, 0.0, 0.0))),
        "shoulder2": ((0.0, (0.0, 0.0, 0.0)), (0.15, (-2.5, 1.5, -3.2)), (0.34, (1.2, -0.8, 1.2)), (duracao, (0.0, 0.0, 0.0))),
        "right-arm": ((0.0, (0.0, 0.0, 0.0)), (0.15, (2.5, -4.5, -10.0)), (0.36, (-1.2, 3.5, 2.0)), (duracao, (0.0, 0.0, 0.0))),
        "left-arm": ((0.0, (0.0, 0.0, 0.0)), (0.15, (2.5, 4.5, 10.0)), (0.36, (-1.2, -3.5, -2.0)), (duracao, (0.0, 0.0, 0.0))),
        "ant-arm": ((0.0, (0.0, 0.0, 0.0)), (0.16, (0.0, 0.0, 9.5)), (0.38, (0.0, 0.0, -1.5)), (duracao, (0.0, 0.0, 0.0))),
        "ant-arm2": ((0.0, (0.0, 0.0, 0.0)), (0.16, (0.0, 0.0, -9.5)), (0.38, (0.0, 0.0, 1.5)), (duracao, (0.0, 0.0, 0.0))),
        "hand": ((0.0, (0.0, 0.0, 0.0)), (0.21, (6.0, -3.5, 5.5)), (0.40, (-2.8, 1.5, -2.2)), (duracao, (0.0, 0.0, 0.0))),
        "hand2": ((0.0, (0.0, 0.0, 0.0)), (0.21, (6.0, 3.5, -5.5)), (0.40, (-2.8, -1.5, 2.2)), (duracao, (0.0, 0.0, 0.0))),
        "head": ((0.0, (0.0, 0.0, 0.0)), (0.16, (2.6, 0.0, 0.0)), (0.34, (-2.0, 0.0, 0.0)), (duracao, (0.0, 0.0, 0.0))),
        "fones": ((0.0, (0.0, 0.0, 0.0)), (0.21, (-3.8, 0.0, 1.2)), (0.40, (2.2, 0.0, -0.8)), (duracao, (0.0, 0.0, 0.0))),
        "antena-direita": ((0.0, (0.0, 0.0, 0.0)), (0.23, (-6.5, 0.0, 2.5)), (0.42, (3.6, 0.0, -1.5)), (duracao, (0.0, 0.0, 0.0))),
        "antena-esquerda": ((0.0, (0.0, 0.0, 0.0)), (0.23, (-6.5, 0.0, -2.5)), (0.42, (3.6, 0.0, 1.5)), (duracao, (0.0, 0.0, 0.0))),
    }


def _trilhas_arranque(destino: str, duracao: float) -> dict[str, tuple[tuple[float, tuple[float, float, float]], ...]]:
    forca = 5.0 if destino == "run" else 4.0
    cotov = 8.0 if destino == "run" else 5.0
    return {
        "cintura": ((0.0, (0.0, 0.0, 0.0)), (0.13, (-forca * 0.50, 0.0, 0.0)), (0.35, (forca * 0.25, 0.0, 0.0)), (duracao, (0.0, 0.0, 0.0))),
        "abdomen": ((0.0, (0.0, 0.0, 0.0)), (0.13, (-forca * 0.70, 0.0, 0.0)), (0.35, (forca * 0.35, 0.0, 0.0)), (duracao, (0.0, 0.0, 0.0))),
        "peitoral": ((0.0, (0.0, 0.0, 0.0)), (0.13, (-forca, 0.0, 0.0)), (0.35, (forca * 0.50, 0.0, 0.0)), (duracao, (0.0, 0.0, 0.0))),
        "shoulder": ((0.0, (0.0, 0.0, 0.0)), (0.14, (2.2, -1.8, -2.5)), (0.36, (-2.5, 2.0, 2.8)), (duracao, (0.0, 0.0, 0.0))),
        "shoulder2": ((0.0, (0.0, 0.0, 0.0)), (0.14, (2.2, 1.8, 2.5)), (0.36, (-2.5, -2.0, -2.8)), (duracao, (0.0, 0.0, 0.0))),
        "ant-arm": ((0.0, (0.0, 0.0, 0.0)), (0.15, (0.0, 0.0, cotov * 0.70)), (0.38, (0.0, 0.0, cotov)), (duracao, (0.0, 0.0, 0.0))),
        "ant-arm2": ((0.0, (0.0, 0.0, 0.0)), (0.15, (0.0, 0.0, -cotov * 0.70)), (0.38, (0.0, 0.0, -cotov)), (duracao, (0.0, 0.0, 0.0))),
        "head": ((0.0, (0.0, 0.0, 0.0)), (0.15, (forca * 0.60, 0.0, 0.0)), (0.38, (-forca * 0.35, 0.0, 0.0)), (duracao, (0.0, 0.0, 0.0))),
        "fones": ((0.0, (0.0, 0.0, 0.0)), (0.20, (3.2, 0.0, 0.0)), (0.45, (-2.0, 0.0, 0.0)), (duracao, (0.0, 0.0, 0.0))),
        "antena-direita": ((0.0, (0.0, 0.0, 0.0)), (0.22, (6.0, 0.0, -2.2)), (0.46, (-3.5, 0.0, 1.5)), (duracao, (0.0, 0.0, 0.0))),
        "antena-esquerda": ((0.0, (0.0, 0.0, 0.0)), (0.22, (6.0, 0.0, 2.2)), (0.46, (-3.5, 0.0, -1.5)), (duracao, (0.0, 0.0, 0.0))),
    }


def _curva_conexao_simples(
    origem: str, destino: str
) -> tuple[float, tuple[tuple[float, tuple[float, float, float]], ...]] | None:
    repousos = ("idle", "hover")
    if origem in ("drag", *repousos, "walk", "run") and destino == "fall":
        return 0.32, ((0.0, (0.0, 0.0, 0.0)), (0.11, (-4.5, 0.0, 0.0)), (0.23, (3.2, 0.0, 0.0)), (0.32, (0.0, 0.0, 0.0)))
    if origem == "fall" and destino in (*repousos, "wake"):
        return 0.55, ((0.0, (0.0, 0.0, 0.0)), (0.16, (5.5, 0.0, 0.0)), (0.38, (-2.0, 0.0, 0.0)), (0.55, (0.0, 0.0, 0.0)))
    if origem in ("hit", "poke", "land", "teimosia") and destino in (*repousos, "walk", "run", "dance"):
        return 0.56, ((0.0, (0.0, 0.0, 0.0)), (0.16, (5.0, 0.0, 0.0)), (0.35, (-1.8, 0.0, 0.0)), (0.56, (0.0, 0.0, 0.0)))
    if origem == "sleep" and destino in ("wake", *repousos):
        return 0.78, ((0.0, (0.0, 0.0, 0.0)), (0.24, (4.5, 0.0, 0.0)), (0.54, (-2.2, 0.0, 0.0)), (0.78, (0.0, 0.0, 0.0)))
    if origem == "wake" and destino in (*repousos, "walk", "dance"):
        return 0.64, ((0.0, (0.0, 0.0, 0.0)), (0.20, (-3.5, 0.0, 0.0)), (0.42, (1.4, 0.0, 0.0)), (0.64, (0.0, 0.0, 0.0)))
    if origem == "dance" and destino in ("walk", "run"):
        return 0.55, ((0.0, (0.0, 0.0, 0.0)), (0.16, (-4.0, 0.0, 0.0)), (0.36, (2.2, 0.0, 0.0)), (0.55, (0.0, 0.0, 0.0)))
    if destino in repousos and origem not in (*repousos, ""):
        return 0.90, ((0.0, (0.0, 0.0, 0.0)), (0.22, (3.0, 0.0, 0.0)), (0.52, (-0.9, 0.0, 0.0)), (0.90, (0.0, 0.0, 0.0)))
    return None


def delta_conexao(origem: str, destino: str, tempo: float) -> dict[str, Rotation3]:
    """Preparação e assentamento entre ações, encerrados sem resíduo na pose."""
    if tempo < 0.0:
        return {}
    repousos = ("idle", "hover")
    if origem == "run" and destino in repousos:
        return {} if tempo >= 0.68 else _amostrar_trilhas_conexao(_trilhas_freada_run(0.68), tempo)
    if origem == "walk" and destino in repousos:
        return {} if tempo >= 0.52 else _amostrar_trilhas_conexao(_trilhas_freada_walk(0.52), tempo)
    if origem in repousos and destino in ("walk", "run", "dance"):
        return {} if tempo >= 0.65 else _amostrar_trilhas_conexao(_trilhas_arranque(destino, 0.65), tempo)
    simples = _curva_conexao_simples(origem, destino)
    if simples is None or tempo >= simples[0]:
        return {}
    pitch = radians(amostrar_pista(simples[1], tempo)[0])
    return {
        "cintura": Rotation3(pitch * 0.45, 0.0, 0.0),
        "peitoral": Rotation3(pitch, 0.0, 0.0),
        "head": Rotation3(-pitch * 0.6, 0.0, 0.0),
    }
