"""Os 6 Idles Base Canônicos do Mário 2.0 (loops contínuos de 10 s com silhueta marcante).

Usa o solver analítico de IK 3D (``ik_bracos.braco_para``) cacheado por alvo de mão
para garantir posições de punho exatas no espaço do rig (x=dir, y=cima, z=frente),
eliminando eixos invertidos e atravessamentos no gabinete/bermuda.

Módulo puro: sem dependências de Panda3D, Qt ou Win32.
"""

from __future__ import annotations

from functools import cache
from math import cos, degrees, exp, sin, tau

from sejoga.animacao import ik_bracos
from sejoga.animacao.braco_hpr import _modelo_ik
from sejoga.animacao.braco_tuning import POLO_COTOVELO_ANATOMICO

DURACAO_LOOP: float = 10.0

IDLES_AUTORAIS_CANONICOS: tuple[str, ...] = (
    "brc_malandro",
    "frenetico_groove",
    "espreita_armario",
    "jojo_exibido",
    "boxeador_pronto",
    "derretido_sono",
)

MIGRACAO_IDLE_LEGADO: dict[str, str] = {
    "calm": "brc_malandro",
    "confident": "brc_malandro",
    "street": "brc_malandro",
    "brc_stance": "brc_malandro",
    "stylish": "brc_malandro",
    "rhythm": "frenetico_groove",
    "vibing": "frenetico_groove",
    "playful": "frenetico_groove",
    "curious": "espreita_armario",
    "shy": "espreita_armario",
    "fighter": "boxeador_pronto",
}

PoseGraus = dict[str, tuple[float, float, float]]
Vec3 = tuple[float, float, float]
Dedos5 = tuple[float, float, float, float, float]


def normalizar_idle_legado(valor: str) -> str:
    """Converte chaves antigas de personalidade para um dos 6 idles canônicos."""
    return MIGRACAO_IDLE_LEGADO.get(valor, valor)


def _pulso_gaussiano(u: float, centro: float, largura: float) -> float:
    """Pulso suave periódico em [0, 1) com pico 1.0 em ``centro``."""
    d = ((u - centro + 0.5) % 1.0) - 0.5
    return exp(-((d / largura) ** 2))


@cache
def _ik_braco(
    lado: str,
    alvo: Vec3,
    polo: Vec3 = POLO_COTOVELO_ANATOMICO,
) -> tuple[Vec3, Vec3]:
    """Resolve e cacheia ``(ombro_graus, antebraco_graus)`` via IK real do rig."""
    res = ik_bracos.braco_para(_modelo_ik(), lado, alvo, polo)
    arm_key = "right-arm" if lado == "right" else "left-arm"
    ant_key = "ant-arm" if lado == "right" else "ant-arm2"
    ra, rf = res[arm_key], res[ant_key]
    return (
        (degrees(ra.x), degrees(ra.y), degrees(ra.z)),
        (degrees(rf.x), degrees(rf.y), degrees(rf.z)),
    )


def _somar3(a: Vec3, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> Vec3:
    return (a[0] + dx, a[1] + dy, a[2] + dz)


def _brc_malandro(t: float) -> PoseGraus:
    """Malandro de rua: lean back, mão esquerda no quadril/Walkman, direito solto no swing."""
    w = tau * (t / DURACAO_LOOP)
    ginga = sin(w * 2.0)
    swing = sin(w * 2.0 - 0.35)
    contra = cos(w * 2.0)
    # Esquerdo apoiado no quadril/Walkman (mão baixa junto ao cinto, cotovelo pra fora)
    l_arm, l_ant = _ik_braco("left", (-0.175, -0.170, 0.085), (-0.65, -0.45, -0.55))
    # Direito relaxado ao lado do corpo balançando no swing
    r_arm, r_ant = _ik_braco("right", (0.160, -0.220, 0.055), (0.15, -0.82, -0.48))
    return {
        "pelvis": (4.0, -9.0 + ginga * 5.0, 6.5 + ginga * 3.2),
        "cintura": (4.5, -5.0 + ginga * 3.0, 3.0),
        "abdomen": (2.5, 3.0 - ginga * 2.0, -2.0),
        "peitoral": (2.5, 5.5 - ginga * 2.5, -2.0),
        "body": (6.5 + contra * 1.6, -13.0 + ginga * 4.0, 3.8 + ginga * 2.4),
        "head": (-2.5 + sin(w * 4.0 - 0.3) * 2.8, 15.0 - ginga * 3.5, -4.5 + swing * 2.2),
        "fones": (1.5, 0.0, -2.0 + swing * 3.0),
        "antena-direita": (4.0 + swing * 5.5, 0.0, -6.0 - ginga * 4.5),
        "antena-esquerda": (2.0 - swing * 4.5, 0.0, 7.0 - ginga * 4.0),
        "shoulder2": (2.0, -4.0, 6.0),
        "left-arm": _somar3(l_arm, dy=-ginga * 2.5, dz=-contra * 1.5),
        "ant-arm2": l_ant,
        "hand2": (8.0, 8.0, -14.0),
        "fingers2": (0.0, 0.0, -18.0),
        "shoulder": (-2.0, 2.0, -4.0),
        "right-arm": _somar3(r_arm, dy=swing * 14.0, dz=-contra * 3.0),
        "ant-arm": _somar3(r_ant, dz=max(0.0, swing) * 10.0),
        "hand": (4.0 + swing * 7.0, -6.0, 6.0),
        "fingers": (0.0, 0.0, 10.0 + contra * 4.0),
        "door": (0.0, 2.0 + max(0.0, contra) * 1.5, 0.0),
    }


def _frenetico_groove(t: float) -> PoseGraus:
    """FNF x Hi-Fi Rush: bounce elástico, mão direita perto do fone, esquerda no beat."""
    w = tau * (t / DURACAO_LOOP)
    beat = w * 10.0
    bounce = (1.0 - cos(beat)) * 0.5
    bounce_snap = bounce * bounce
    sway = sin(beat * 0.5)
    atraso = sin(beat * 0.5 - 0.45)
    # Direito erguido por fora perto da concha do fone (alvo validado sem colisão)
    r_arm, r_ant = _ik_braco("right", (0.205, 0.140, 0.115), (0.35, -0.68, -0.58))
    # Esquerdo aberto pro lado/frente marcando o beat no ar (longe do peito)
    l_arm, l_ant = _ik_braco("left", (-0.205, -0.055, 0.145), (-0.30, -0.75, -0.52))
    return {
        "pelvis": (-3.5 - bounce_snap * 5.0, sway * 7.5, sway * 5.0),
        "cintura": (-2.0 - bounce_snap * 3.5, sway * 4.0, -sway * 2.5),
        "abdomen": (-1.5 - bounce * 2.2, -sway * 3.0, sway * 2.0),
        "peitoral": (1.5 - bounce * 2.0, sway * 3.2, -sway * 1.8),
        "body": (-3.5 - bounce_snap * 5.5, sway * 6.5, sway * 4.0),
        "head": (2.5 - (1.0 - cos(beat - 0.35)) * 7.5, -sway * 5.5, atraso * 5.0),
        "fones": (1.5 - bounce_snap * 4.0, 0.0, atraso * 5.5),
        "antena-direita": (5.0 - bounce_snap * 10.0, 0.0, -8.0 + atraso * 7.5),
        "antena-esquerda": (5.0 - bounce_snap * 10.0, 0.0, 8.0 + atraso * 7.5),
        "shoulder": (-5.0, 3.0, -6.0),
        "right-arm": _somar3(r_arm, dz=bounce_snap * 7.0),
        "ant-arm": _somar3(r_ant, dz=bounce * 8.0),
        "hand": (6.0 + atraso * 7.0, -8.0, 12.0),
        "fingers": (0.0, 0.0, 14.0 + bounce * 6.0),
        "shoulder2": (-3.0, -3.0, 5.0),
        "left-arm": _somar3(l_arm, dy=-sway * 6.0, dz=-bounce_snap * 11.0),
        "ant-arm2": _somar3(l_ant, dz=-bounce_snap * 14.0),
        "hand2": (-6.0 + bounce_snap * 14.0, 8.0, -10.0),
        "fingers2": (0.0, 0.0, -10.0 - bounce_snap * 16.0),
        "door": (0.0, 1.5 + bounce_snap * 4.5, 0.0),
    }


def _espreita_armario(t: float) -> PoseGraus:
    """Segredo vivo: curvado de lado, mão direita perto da porta, esquerdo recolhido baixo."""
    w = tau * (t / DURACAO_LOOP)
    u = (t % DURACAO_LOOP) / DURACAO_LOOP
    fuga = _pulso_gaussiano(u, 0.25, 0.05) + _pulso_gaussiano(u, 0.72, 0.055)
    tremor_porta = sin(w * 24.0) * 2.5 * fuga
    olhada = sin(w * 1.0) * 9.0 + _pulso_gaussiano(u, 0.28, 0.05) * 10.0
    # Mão direita na frente/lateral da porta pronta para segurar (livre do gabinete)
    r_arm, r_ant = _ik_braco("right", (0.115, 0.015, 0.205), (0.55, -0.64, -0.52))
    # Braço esquerdo relaxado baixo junto ao corpo (nada de T-pose!)
    l_arm, l_ant = _ik_braco("left", (-0.155, -0.220, 0.045), (-0.15, -0.82, -0.48))
    return {
        "pelvis": (-6.0, 12.0, -4.0),
        "cintura": (-4.5, 6.0, -2.0),
        "abdomen": (-3.5, 4.0, 0.0),
        "peitoral": (-2.5, 3.0, 1.0),
        "body": (-10.0 - sin(w * 2.0) * 1.8 + fuga * 3.5, 16.0, -3.5),
        "head": (5.0 - fuga * 7.5, -22.0 + olhada, 5.0 - fuga * 4.0),
        "fones": (-1.5, 0.0, -2.5 + fuga * 3.5),
        "antena-direita": (-7.0 + fuga * 13.0, 0.0, -4.0 - fuga * 6.0),
        "antena-esquerda": (-7.0 + fuga * 13.0, 0.0, 4.0 + fuga * 6.0),
        "shoulder": (-3.0, 5.0, -5.0),
        "right-arm": _somar3(r_arm, dy=fuga * 8.0, dz=-fuga * 6.0),
        "ant-arm": _somar3(r_ant, dz=fuga * 12.0),
        "hand": (-6.0, -10.0, 10.0),
        "fingers": (0.0, 0.0, 4.0),
        "shoulder2": (2.0, -2.0, 3.0),
        "left-arm": _somar3(l_arm, dy=sin(w * 2.0) * 4.0),
        "ant-arm2": l_ant,
        "hand2": (5.0, 4.0, -6.0),
        "fingers2": (0.0, 0.0, -8.0),
        "door": (0.0, max(0.0, 3.5 + fuga * 16.0 + tremor_porta), 0.0),
    }


def _jojo_exibido(t: float) -> PoseGraus:
    """Teatral / Ego Gigante (JoJo x Persona): contraposto extremo e pose escultural."""
    w = tau * (t / DURACAO_LOOP)
    respiro = sin(w * 1.0)
    pausa = sin(w * 2.0) * 0.5
    # Direito erguido em pose angular dramática ao lado do queixo/fone (sem cobrir o visor)
    r_arm, r_ant = _ik_braco("right", (0.185, 0.135, 0.155), (0.45, -0.62, -0.58))
    # Esquerdo aberto estilizado pro lado/baixo com palma aberta
    l_arm, l_ant = _ik_braco("left", (-0.235, -0.085, 0.075), (-0.20, -0.78, -0.52))
    return {
        "pelvis": (4.5, -14.0 + respiro * 3.0, -10.0 + pausa * 2.0),
        "cintura": (3.5, -8.0, 6.0),
        "abdomen": (2.0, 6.0, 5.0),
        "peitoral": (2.5, 10.0, 4.5),
        "body": (6.5 + respiro * 1.8, -22.0 + respiro * 3.5, 9.0 - pausa * 1.5),
        "head": (7.5 + respiro * 1.8, 25.0 - respiro * 3.0, -8.0 + pausa * 2.0),
        "fones": (2.0, 0.0, 3.0),
        "antena-direita": (7.0 + respiro * 3.5, 0.0, -12.0),
        "antena-esquerda": (5.0 - respiro * 3.5, 0.0, 14.0),
        "shoulder": (-8.0, 5.0, -8.0),
        "right-arm": _somar3(r_arm, dz=respiro * 3.0),
        "ant-arm": _somar3(r_ant, dz=pausa * 5.0),
        "hand": (-12.0 + respiro * 4.0, -14.0, 14.0),
        "fingers": (0.0, 0.0, -6.0),
        "shoulder2": (4.0, -4.0, 6.0),
        "left-arm": _somar3(l_arm, dz=-respiro * 4.0),
        "ant-arm2": l_ant,
        "hand2": (-14.0, 12.0, -18.0),
        "fingers2": (0.0, 0.0, 6.0),
        "door": (0.0, 1.5 + max(0.0, respiro) * 2.0, 0.0),
    }


def _boxeador_pronto(t: float) -> PoseGraus:
    """Marrento de Arcade: guarda fechada separada + bob & weave + antenas radar."""
    w = tau * (t / DURACAO_LOOP)
    ginga = sin(w * 6.0)
    quique = (1.0 - cos(w * 12.0)) * 0.5
    # Guarda direita (gancho) recolhida e esquerda (jab) mais avançada — sem se tocarem
    r_arm, r_ant = _ik_braco("right", (0.145, 0.025, 0.175), (0.50, -0.65, -0.55))
    l_arm, l_ant = _ik_braco("left", (-0.135, 0.035, 0.215), (-0.45, -0.65, -0.55))
    return {
        "pelvis": (-5.0, -16.0 + ginga * 5.5, ginga * 4.5),
        "cintura": (-3.5, -6.0 + ginga * 3.2, ginga * 2.5),
        "abdomen": (-2.5, 4.0, -ginga * 2.0),
        "peitoral": (-2.0, 4.0, -ginga * 1.5),
        "body": (-8.0 - quique * 2.8, -18.0 + ginga * 6.5, ginga * 5.2),
        "head": (-5.5 + quique * 1.5, 18.0 - ginga * 5.0, -ginga * 4.2),
        "fones": (-1.5, 0.0, -ginga * 3.5),
        "antena-direita": (-14.0 - quique * 4.5, 0.0, -4.0 - ginga * 4.5),
        "antena-esquerda": (-14.0 - quique * 4.5, 0.0, 4.0 - ginga * 4.5),
        "shoulder": (-5.0, 5.0, -5.0),
        "right-arm": _somar3(r_arm, dy=ginga * 6.0, dz=quique * 5.0),
        "ant-arm": _somar3(r_ant, dz=quique * 5.0),
        "hand": (4.0, -6.0, 10.0),
        "fingers": (0.0, 0.0, 34.0),
        "shoulder2": (-6.0, -6.0, 5.0),
        "left-arm": _somar3(l_arm, dy=ginga * 6.0, dz=-quique * 5.0),
        "ant-arm2": _somar3(l_ant, dz=-quique * 5.0),
        "hand2": (4.0, 6.0, -10.0),
        "fingers2": (0.0, 0.0, -34.0),
        "door": (0.0, 0.5, 0.0),
    }


def _derretido_sono(t: float) -> PoseGraus:
    """Bateria em 1%: pendurado lento + cabeça pescando de sono e dando tranco de susto."""
    w = tau * (t / DURACAO_LOOP)
    u = (t % DURACAO_LOOP) / DURACAO_LOOP
    pesca = _pulso_gaussiano(u, 0.38, 0.08) + _pulso_gaussiano(u, 0.88, 0.08)
    tranco = _pulso_gaussiano(u, 0.45, 0.022) + _pulso_gaussiano(u, 0.95, 0.022)
    pendulo = sin(w * 1.0)
    # Braços bem pendurados soltos ao lado do corpo (validado sem entrar na bermuda)
    r_arm, r_ant = _ik_braco("right", (0.145, -0.240, 0.055), (0.12, -0.86, -0.45))
    l_arm, l_ant = _ik_braco("left", (-0.145, -0.240, 0.055), (-0.12, -0.86, -0.45))
    return {
        "pelvis": (-4.0, pendulo * 4.5, pendulo * 3.2),
        "cintura": (-4.5, pendulo * 2.5, pendulo * 2.0),
        "abdomen": (-4.0, 0.0, pendulo * 1.5),
        "peitoral": (-3.5, 0.0, 0.0),
        "body": (-12.0 - pesca * 5.0 + tranco * 10.0, pendulo * 4.5, pendulo * 4.8),
        "head": (-10.0 - pesca * 22.0 + tranco * 24.0, pendulo * 5.0, 6.0 * pendulo - tranco * 5.0),
        "fones": (-2.0 - pesca * 3.5 + tranco * 5.0, 0.0, pendulo * 3.0),
        "antena-direita": (-12.0 + tranco * 22.0, 0.0, -24.0 + tranco * 18.0),
        "antena-esquerda": (-12.0 + tranco * 22.0, 0.0, 24.0 - tranco * 18.0),
        "shoulder": (6.0 - tranco * 9.0, 0.0, 4.0),
        "shoulder2": (6.0 - tranco * 9.0, 0.0, -4.0),
        "right-arm": _somar3(r_arm, dy=pendulo * 4.0, dz=-tranco * 14.0),
        "left-arm": _somar3(l_arm, dy=pendulo * 4.0, dz=tranco * 14.0),
        "ant-arm": _somar3(r_ant, dz=tranco * 18.0),
        "ant-arm2": _somar3(l_ant, dz=-tranco * 18.0),
        "hand": (8.0, 0.0, 4.0),
        "hand2": (8.0, 0.0, -4.0),
        "fingers": (0.0, 0.0, 4.0),
        "fingers2": (0.0, 0.0, -4.0),
        "door": (0.0, max(0.0, 4.5 + pesca * 5.0 - tranco * 6.5), 0.0),
    }


_AMOSTRADORES: dict[str, object] = {
    "brc_malandro": _brc_malandro,
    "frenetico_groove": _frenetico_groove,
    "espreita_armario": _espreita_armario,
    "jojo_exibido": _jojo_exibido,
    "boxeador_pronto": _boxeador_pronto,
    "derretido_sono": _derretido_sono,
}


#: Atraso (s) por elo da cadeia: coluna lidera, cabeça/braços/mãos/antenas seguem.
_CASCATA_IDLE: tuple[tuple[float, tuple[str, ...]], ...] = (
    (0.06, ("head", "fones", "shoulder", "shoulder2")),
    (0.09, ("right-arm", "left-arm")),
    (0.13, ("ant-arm", "ant-arm2", "hand", "hand2")),
    (0.17, ("fingers", "fingers2", "antena-direita", "antena-esquerda")),
)


def _fraseado_assimetrico(pose: PoseGraus, t: float) -> None:
    """Soma frases lentas em harmônicos 3 e 7 do loop (periódicas, mas fora do pulso base)."""
    w = tau * ((t % DURACAO_LOOP) / DURACAO_LOOP)
    a = sin(w * 3.0 + 0.7)
    b = sin(w * 7.0 + 2.1) * max(0.0, sin(w * 1.0 + 0.4))
    for grupo, (ax, ay, az) in (
        ("body", (0.9 * a, 1.4 * b, 0.6 * a)),
        ("head", (1.6 * b, 2.2 * a, -1.1 * b)),
        ("antena-direita", (2.4 * a, 0.0, -2.0 * b)),
        ("antena-esquerda", (-1.8 * b, 0.0, 2.6 * a)),
    ):
        if grupo in pose:
            x, y, z = pose[grupo]
            pose[grupo] = (x + ax, y + ay, z + az)


def amostrar_idle_autoral(estilo: str, tempo: float) -> PoseGraus | None:
    """Devolve a pose em graus de um idle canônico com overlap real e fraseado vivo.

    Cada elo da cadeia cinemática é amostrado num instante atrasado do mesmo loop,
    então cabeça, punhos e antenas chegam DEPOIS da coluna (follow-through real)
    em vez de todos os grupos baterem no mesmo quadro.
    """
    fn = _AMOSTRADORES.get(estilo)
    if fn is None:
        return None
    pose: PoseGraus = dict(fn(tempo % DURACAO_LOOP))  # type: ignore[operator]
    for atraso, grupos in _CASCATA_IDLE:
        atrasada = fn((tempo - atraso) % DURACAO_LOOP)  # type: ignore[operator]
        for grupo in grupos:
            if grupo in atrasada:
                pose[grupo] = atrasada[grupo]
    _fraseado_assimetrico(pose, tempo)
    return pose


def pernas_idle_autoral(
    estilo: str,
    tempo: float,
    respiracao: float = 0.0,
) -> tuple[float, ...] | None:
    """Devolve 12 canais de perna distintos para cada um dos 6 idles canônicos."""
    if estilo not in _AMOSTRADORES:
        return None
    w = tau * ((tempo % DURACAO_LOOP) / DURACAO_LOOP)
    resp = max(0.0, 0.5 + 0.5 * float(respiracao))
    if estilo == "brc_malandro":
        # Peso na esquerda, pé direito avançado batendo claramente a ponta no calcanhar
        tapa = (1.0 - cos(w * 8.0)) * 0.5
        return (-4.0, -14.0, 10.0 + resp * 2.0, 18.0, 6.0, -14.0, -4.0, 6.0, -5.0, -24.0 * tapa, 0.0, 0.0)
    if estilo == "frenetico_groove":
        b = ((1.0 - cos(w * 10.0)) * 0.5) ** 2
        s = sin(w * 5.0)
        return (-8.0 - b * 12.0, -8.0 - b * 12.0, 14.0 + b * 24.0, 14.0 + b * 24.0, 10.0, -10.0, -5.0 + s * 2.0, 5.0 + s * 2.0, -8.0 - b * 10.0, -8.0 - b * 10.0, 0.0, 0.0)
    if estilo == "espreita_armario":
        return (-12.0, -10.0, 24.0 + resp * 3.0, 20.0 + resp * 3.0, 8.0, -12.0, -3.0, 4.0, -11.0, -9.0, 0.0, 0.0)
    if estilo == "jojo_exibido":
        return (-5.0, -14.0, 8.0 + resp * 2.0, 22.0, 14.0, -18.0, -6.0, 7.0, -4.0, -10.0, 0.0, 0.0)
    if estilo == "boxeador_pronto":
        q = sin(w * 6.0)
        j_e = 20.0 + max(0.0, q) * 10.0
        j_d = 20.0 + max(0.0, -q) * 10.0
        return (-12.0 - max(0.0, q) * 4.0, -8.0 - max(0.0, -q) * 4.0, j_e, j_d, 12.0, -16.0, -5.0, 6.0, -10.0, -8.0, 0.0, 0.0)
    p = sin(w * 1.0)
    return (-5.0 + p * 3.0, -7.0 - p * 3.0, 12.0 + resp * 3.0, 15.0 + resp * 3.0, 4.0, -6.0, -3.0 + p * 2.0, 3.0 + p * 2.0, -6.0, -7.0, 0.0, 0.0)


def dedos_idle_autoral(estilo: str, tempo: float) -> tuple[Dedos5, Dedos5] | None:
    """Devolve flexão individual ``(dir_5, esq_5)`` em ``0..1`` (1.0 = punho fechado)."""
    if estilo not in _AMOSTRADORES:
        return None
    if estilo == "boxeador_pronto":
        punho = (0.96, 1.0, 1.0, 1.0, 1.0)
        return (punho, punho)
    if estilo == "brc_malandro":
        return ((0.26, 0.30, 0.38, 0.46, 0.54), (0.76, 0.85, 0.90, 0.94, 0.96))
    if estilo == "frenetico_groove":
        w = tau * ((tempo % DURACAO_LOOP) / DURACAO_LOOP)
        b = ((1.0 - cos(w * 10.0)) * 0.5) ** 2
        esq = (0.28 + b * 0.45, 0.12 + b * 0.65, 0.18 + b * 0.62, 0.24 + b * 0.58, 0.30 + b * 0.55)
        return ((0.58, 0.68, 0.78, 0.84, 0.88), esq)
    if estilo == "espreita_armario":
        return ((0.06, 0.04, 0.06, 0.08, 0.10), (0.34, 0.38, 0.44, 0.48, 0.52))
    if estilo == "jojo_exibido":
        return ((0.35, 0.04, 0.06, 0.78, 0.85), (0.08, 0.02, 0.04, 0.06, 0.08))
    mole = (0.22, 0.26, 0.30, 0.34, 0.38)
    return (mole, mole)
