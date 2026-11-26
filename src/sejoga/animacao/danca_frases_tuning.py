"""Frases de dança por estilo: um passo por batida, quatro poses ZZZ 3D por passo.

Cada passo articula a cadeia completa (`cintura -> abdomen -> peitoral -> body ->
head -> fones/antenas`, braços por IK, punhos `hand`/`hand2` e dedos grandes
`fingers`/`fingers2`) na ordem de ``danca_tuning.U_POSES``: acento (onset),
sustentação, recuperação e preparação com antecipação e follow-through.
Python puro, sem engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from sejoga.animacao import animation as _anim_padrao
from sejoga.animacao import danca_tuning as tune
from sejoga.animacao.braco_hpr import braco_hpr_graus
from sejoga.animacao.dados_autorais import danca_ativa
from sejoga.animacao.interpolacao import amostrar_pista

Trio = tuple[float, float, float]

#: Grupos de cada braço: (ombro, cotovelo).
GRUPOS_BRACO = {"right": ("right-arm", "ant-arm"), "left": ("left-arm", "ant-arm2")}
_TODOS_GRUPOS_BRACO = frozenset(g for par in GRUPOS_BRACO.values() for g in par)
_ZERO: Trio = (0.0, 0.0, 0.0)
#: Grupos escalados pelo ganho (energia); mãos e dedos entram como declarados.
GRUPOS_COM_GANHO = frozenset({"head", "body"})


@dataclass(frozen=True)
class PoseDanca:
    """Uma pose-chave: deltas de cabeça/tronco e alvos de mão de cada braço."""

    corpo: dict[str, Trio] = field(default_factory=dict)
    braco_dir: str = "idle"
    braco_esq: str = "idle"


@dataclass(frozen=True)
class PassoDanca:
    """Um passo de uma batida com as quatro poses, na ordem de ``U_POSES``."""

    poses: tuple[PoseDanca, PoseDanca, PoseDanca, PoseDanca]


def _trio_do_grupo(pose: PoseDanca, grupo: str) -> Trio:
    for lado, par in GRUPOS_BRACO.items():
        if grupo in par:
            nome = pose.braco_dir if lado == "right" else pose.braco_esq
            return braco_hpr_graus(lado, nome)[grupo]
    return pose.corpo.get(grupo, _ZERO)


def _grupos_das_poses(poses: list[PoseDanca]) -> set[str]:
    grupos = set(_TODOS_GRUPOS_BRACO)
    for pose in poses:
        grupos.update(pose.corpo)
    return grupos


def _catmull_trio(p0: Trio, p1: Trio, p2: Trio, p3: Trio, u: float) -> Trio:
    """Spline Catmull-Rom contínua por eixo para fluxo fluido entre sub-poses da batida."""
    u2 = u * u
    u3 = u2 * u
    return (
        0.5 * ((2.0 * p1[0]) + (-p0[0] + p2[0]) * u + (2.0 * p0[0] - 5.0 * p1[0] + 4.0 * p2[0] - p3[0]) * u2 + (-p0[0] + 3.0 * p1[0] - 3.0 * p2[0] + p3[0]) * u3),
        0.5 * ((2.0 * p1[1]) + (-p0[1] + p2[1]) * u + (2.0 * p0[1] - 5.0 * p1[1] + 4.0 * p2[1] - p3[1]) * u2 + (-p0[1] + 3.0 * p1[1] - 3.0 * p2[1] + p3[1]) * u3),
        0.5 * ((2.0 * p1[2]) + (-p0[2] + p2[2]) * u + (2.0 * p0[2] - 5.0 * p1[2] + 4.0 * p2[2] - p3[2]) * u2 + (-p0[2] + 3.0 * p1[2] - 3.0 * p2[2] + p3[2]) * u3),
    )


def _amostrar_faixa_danca(faixa: tuple[tuple[float, Trio], ...], u: float) -> Trio:
    """Mistura fluxo Catmull-Rom com acento quíntico no onset sem 4 micro-paradas por batida."""
    if u <= faixa[0][0]:
        return faixa[0][1]
    if u >= faixa[-1][0]:
        return faixa[-1][1]
    n = len(faixa)
    for i in range(n - 1):
        t0, v1 = faixa[i]
        t1, v2 = faixa[i + 1]
        if u <= t1:
            dur = t1 - t0
            frac = (u - t0) / dur if dur > 1e-9 else 1.0
            if i == 0:
                # Preserva impacto nítido do onset (pose 0 -> pose 1)
                return amostrar_pista(((0.0, v1), (1.0, v2)), frac)
            v0 = faixa[max(0, i - 1)][1]
            v3 = faixa[min(n - 1, i + 2)][1]
            # Mistura suave 70% Catmull-Rom + 30% quíntico: elimina paradas mortas mantendo acento
            cr = _catmull_trio(v0, v1, v2, v3, frac)
            qt = amostrar_pista(((0.0, v1), (1.0, v2)), frac)
            return (
                cr[0] * 0.70 + qt[0] * 0.30,
                cr[1] * 0.70 + qt[1] * 0.30,
                cr[2] * 0.70 + qt[2] * 0.30,
            )
    return faixa[-1][1]


def amostrar_passo(
    passo: PassoDanca,
    u: float,
    proximo: PassoDanca | None = None,
    ganho: float = 1.0,
) -> dict[str, Trio]:
    """Pose (graus) do ``passo`` na fração ``u`` (0..1) da batida."""
    destino = (proximo or passo).poses[0]
    u_poses = tune.parametros_danca().get("u_poses", tune.U_POSES)
    chaves = [*zip(u_poses, passo.poses, strict=True), (1.0, destino)]
    saida: dict[str, Trio] = {}
    for grupo in _grupos_das_poses([pose for _, pose in chaves]):
        faixa = tuple((quando, _trio_do_grupo(pose, grupo)) for quando, pose in chaves)
        trio = _amostrar_faixa_danca(faixa, u)
        saida[grupo] = (
            (trio[0] * ganho, trio[1] * ganho, trio[2] * ganho)
            if grupo in GRUPOS_COM_GANHO
            else trio
        )
    return saida

Quatro = tuple[Trio, Trio, Trio, Trio]
NomesBraco = str | tuple[str, str, str, str]

_ZERO4: Quatro = ((0.0, 0.0, 0.0),) * 4


def _por_pose(valor: NomesBraco) -> tuple[str, str, str, str]:
    """Repete o nome do alvo nas quatro poses quando for um só."""
    return (valor, valor, valor, valor) if isinstance(valor, str) else valor


def _escalar_quatro(q: Quatro, sx: float, sy: float, sz: float) -> Quatro:
    """Deriva cadeia secundária escalada com contraste suave."""
    return tuple((vx * sx, vy * sy, vz * sz) for vx, vy, vz in q)  # type: ignore[return-value]


def _atrasar_quatro(q: Quatro, ganho: float = 1.0, offset_x: float = 0.0) -> Quatro:
    """Cria atraso de follow-through em 1 sub-pose para punhos, fones e antenas."""
    ordem = (q[3], q[0], q[1], q[2])
    return tuple(
        (offset_x + vx * ganho, vy * ganho, vz * ganho) for vx, vy, vz in ordem
    )  # type: ignore[return-value]


def _passo(
    cabeca: Quatro,
    tronco: Quatro,
    braco_dir: NomesBraco = "idle",
    braco_esq: NomesBraco = "idle",
    extras: dict[str, Trio] | None = None,
    *,
    cintura: Quatro | None = None,
    abdomen: Quatro | None = None,
    peitoral: Quatro | None = None,
    hand: Quatro | None = None,
    hand2: Quatro | None = None,
    fingers: Quatro | None = None,
    fingers2: Quatro | None = None,
    fones: Quatro | None = None,
    ant_dir: Quatro | None = None,
    ant_esq: Quatro | None = None,
) -> PassoDanca:
    """Monta um passo articulado em cadeia completa (12 princípios em 3D)."""
    dirs = _por_pose(braco_dir)
    esqs = _por_pose(braco_esq)
    cint_q = cintura if cintura is not None else _escalar_quatro(tronco, 0.65, -0.8, 0.75)
    abd_q = abdomen if abdomen is not None else _escalar_quatro(tronco, 0.75, 0.5, 0.65)
    pei_q = peitoral if peitoral is not None else _escalar_quatro(tronco, 0.9, 1.1, -0.7)
    fon_q = fones if fones is not None else _atrasar_quatro(cabeca, 0.28)
    ad_q = ant_dir if ant_dir is not None else _atrasar_quatro(cabeca, 0.55)
    ae_q = ant_esq if ant_esq is not None else tuple(
        (x * 0.55, y * 0.35, -z * 0.55) for x, y, z in _atrasar_quatro(cabeca, 1.0)
    )
    h_r = hand if hand is not None else _atrasar_quatro(tronco, 0.85)
    h_l = hand2 if hand2 is not None else tuple(
        (x * 0.85, -y * 0.85, -z * 0.85) for x, y, z in _atrasar_quatro(tronco, 1.0)
    )
    f_r = fingers if fingers is not None else tuple(
        (0.0, 0.0, x * 0.65 - z * 0.45) for x, _y, z in _atrasar_quatro(tronco, 1.0)
    )
    f_l = fingers2 if fingers2 is not None else tuple(
        (0.0, 0.0, -x * 0.65 - z * 0.45) for x, _y, z in _atrasar_quatro(tronco, 1.0)
    )
    poses = tuple(
        PoseDanca(
            {
                "head": cabeca[i],
                "body": tronco[i],
                "cintura": cint_q[i],
                "abdomen": abd_q[i],
                "peitoral": pei_q[i],
                "hand": h_r[i],
                "hand2": h_l[i],
                "fingers": f_r[i],
                "fingers2": f_l[i],
                "fones": fon_q[i],
                "antena-direita": ad_q[i],
                "antena-esquerda": ae_q[i],
                **(extras or {}),
            },
            dirs[i],
            esqs[i],
        )
        for i in range(4)
    )

    return PassoDanca(poses)  # type: ignore[arg-type]


def _fixo(trio: Trio) -> Quatro:
    """Repete o mesmo trio nas quatro poses."""
    return (trio, trio, trio, trio)


#: Inclinação do tronco no head bob sentado no topo da caixa (graus).
HEADBOB_TRONCO_TRAS = 2.0
_HB_TRONCO: Trio = (HEADBOB_TRONCO_TRAS, 0.0, 0.0)

#: Head bob: 4 batidas. Groove sentado em arco figura-8 estilo FNF com
#: acento para baixo + rebote alegre para cima, mãos apoiadas na caixa e no colo.
HEAD_BOB: tuple[PassoDanca, ...] = (
    _passo(
        ((-14.0, 6.0, 13.0), (-6.0, 7.0, 12.0), (1.0, 4.0, 6.0), (6.5, 1.5, 2.0)),
        ((-4.0, 4.0, 4.5), (-1.5, 4.0, 3.5), (1.5, 2.0, 2.0), (4.0, 0.0, 1.0)),
        braco_dir=("colo", "contrapeso", "colo", "colo"),
        braco_esq="apoio_caixa",
        hand=((-6.0, 12.0, -12.0), (-12.0, 20.0, -16.0), (-4.0, 10.0, -8.0), (4.0, 0.0, 6.0)),
        hand2=((4.0, -8.0, 8.0), (6.0, -10.0, 10.0), (4.0, -8.0, 8.0), (2.0, -6.0, 6.0)),
        fingers=((0.0, 0.0, -10.0), (0.0, 0.0, -16.0), (0.0, 0.0, 8.0), (0.0, 0.0, 6.0)),
        fingers2=((0.0, 0.0, 8.0), (0.0, 0.0, 10.0), (0.0, 0.0, 8.0), (0.0, 0.0, 6.0)),
    ),
    _passo(
        ((-10.0, 2.0, 6.0), (-3.0, 0.0, 2.0), (2.0, -2.0, -3.0), (6.5, -4.0, -6.0)),
        ((-2.0, 2.0, 2.0), (0.5, 0.0, 0.0), (2.0, -2.0, -1.5), (3.5, -3.0, -2.5)),
        braco_dir=("colo", "contrapeso", "colo", "colo"),
        braco_esq="apoio_caixa",
        hand=((6.0, -8.0, 8.0), (-10.0, 18.0, -16.0), (-2.0, 6.0, -6.0), (4.0, -6.0, 6.0)),
        hand2=((2.0, -6.0, 6.0), (5.0, -10.0, 10.0), (2.0, -6.0, 6.0), (0.0, -4.0, 4.0)),
        fingers=((0.0, 0.0, 8.0), (0.0, 0.0, -14.0), (0.0, 0.0, 8.0), (0.0, 0.0, 4.0)),
        fingers2=((0.0, 0.0, 8.0), (0.0, 0.0, 10.0), (0.0, 0.0, 6.0), (0.0, 0.0, 4.0)),
    ),
    _passo(
        ((-14.0, -6.0, -13.0), (-6.0, -7.0, -12.0), (1.0, -4.0, -6.0), (6.5, -1.5, -2.0)),
        ((-4.0, -4.0, -4.5), (-1.5, -4.0, -3.5), (1.5, -2.0, -2.0), (4.0, 0.0, -1.0)),
        braco_dir="apoio_caixa",
        braco_esq=("colo", "contrapeso", "colo", "colo"),
        hand=((4.0, 8.0, -8.0), (6.0, 10.0, -10.0), (4.0, 8.0, -8.0), (2.0, 6.0, -6.0)),
        hand2=((-6.0, -12.0, 12.0), (-12.0, -20.0, 16.0), (-4.0, -10.0, 8.0), (4.0, 0.0, -6.0)),
        fingers=((0.0, 0.0, 8.0), (0.0, 0.0, 10.0), (0.0, 0.0, 8.0), (0.0, 0.0, 6.0)),
        fingers2=((0.0, 0.0, -10.0), (0.0, 0.0, -16.0), (0.0, 0.0, 8.0), (0.0, 0.0, 6.0)),
    ),
    _passo(
        ((-10.0, -2.0, -6.0), (-3.0, 0.0, -2.0), (2.0, 2.0, 3.0), (6.5, 4.0, 6.0)),
        ((-2.0, -2.0, -2.0), (0.5, 0.0, 0.0), (2.0, 2.0, 1.5), (3.5, 3.0, 2.5)),
        braco_dir="apoio_caixa",
        braco_esq=("colo", "contrapeso", "colo", "colo"),
        hand=((2.0, 6.0, -6.0), (5.0, 10.0, -10.0), (2.0, 6.0, -6.0), (0.0, 4.0, -4.0)),
        hand2=((6.0, 8.0, -8.0), (-10.0, -18.0, 16.0), (-2.0, -6.0, 6.0), (4.0, 6.0, -6.0)),
        fingers=((0.0, 0.0, 8.0), (0.0, 0.0, 10.0), (0.0, 0.0, 6.0), (0.0, 0.0, 4.0)),
        fingers2=((0.0, 0.0, 8.0), (0.0, 0.0, -14.0), (0.0, 0.0, 8.0), (0.0, 0.0, 4.0)),
    ),
)

#: Torção do punho direito no rock (graus): mantém palma do chifre legível no onset.
_ROCK_PUNHO = {"hand": (0.0, 0.0, 0.0)}

#: Rock: 2 batidas. Headbang com chicote largo de coluna (+10° -> -24°), mão direita no chifre
#: alto longe do fone e mão esquerda marcando o grave em power-chord ativo.
ROCK: tuple[PassoDanca, ...] = (
    _passo(
        ((-24.0, -4.0, 6.0), (-11.0, 4.0, 3.0), (1.0, 2.0, 1.0), (10.0, -2.0, -2.0)),
        ((-9.5, 3.0, 3.0), (-3.5, 2.0, 1.5), (1.5, 0.0, 0.5), (6.5, -2.0, -2.0)),
        braco_dir="chifre",
        braco_esq=("idle", "street_attitude", "cyber_baixo", "street_solto"),
        extras=_ROCK_PUNHO,
        hand2=((6.0, -8.0, 8.0), (-10.0, -18.0, 16.0), (-6.0, -14.0, 12.0), (2.0, -6.0, 6.0)),
        fingers=((0.0, 0.0, -12.0), (0.0, 0.0, -16.0), (0.0, 0.0, -14.0), (0.0, 0.0, -10.0)),
        fingers2=((0.0, 0.0, -18.0), (0.0, 0.0, -26.0), (0.0, 0.0, -24.0), (0.0, 0.0, -16.0)),
    ),
    _passo(
        ((-22.0, 5.0, -6.0), (-9.0, -3.0, -3.0), (2.0, -1.0, -1.0), (10.0, 2.0, 2.0)),
        ((-8.0, -3.0, -3.0), (-2.5, -2.0, -1.5), (2.0, 0.0, -0.5), (6.5, 2.0, 2.0)),
        braco_dir="chifre",
        braco_esq=("contrapeso", "cyber_baixo", "street_attitude", "idle"),
        extras=_ROCK_PUNHO,
        hand2=((6.0, -8.0, 8.0), (-12.0, -20.0, 18.0), (-8.0, -14.0, 14.0), (2.0, -6.0, 6.0)),
        fingers=((0.0, 0.0, -12.0), (0.0, 0.0, -16.0), (0.0, 0.0, -14.0), (0.0, 0.0, -10.0)),
        fingers2=((0.0, 0.0, -18.0), (0.0, 0.0, -28.0), (0.0, 0.0, -22.0), (0.0, 0.0, -16.0)),
    ),
)

#: Hip hop: 8 batidas. Groove boom-bap com cabeçada forte (-15° -> +6.5°),
#: braços soltos/alternados no beat e isolação firme de cintura e peitoral.
HIP_HOP: tuple[PassoDanca, ...] = (
    _passo(
        ((-15.0, 4.0, 6.0), (-6.0, 4.5, 4.0), (0.0, 1.0, 1.0), (6.5, -2.0, -1.5)),
        ((-7.5, -3.5, 7.5), (-3.0, -2.0, 5.5), (1.0, 0.0, 3.0), (4.5, 2.0, 2.0)),
        braco_dir=("street_solto", "dance", "street_solto", "idle"),
        braco_esq=("idle", "street_attitude", "contrapeso", "contrapeso"),
        cintura=((5.5, 6.5, -5.5), (3.0, 5.0, -4.0), (0.0, 2.0, -2.0), (-2.5, -2.0, 2.0)),
        peitoral=((-6.5, -6.5, 5.5), (-3.0, -5.0, 4.0), (0.0, -2.0, 2.0), (3.5, 3.0, -2.0)),
        hand=((6.0, 8.0, -8.0), (-8.0, 16.0, -14.0), (-12.0, 20.0, -16.0), (4.0, -8.0, 8.0)),
        hand2=((6.0, -8.0, 8.0), (-8.0, -16.0, 14.0), (-14.0, -22.0, 18.0), (4.0, 8.0, -8.0)),
        fingers=((0.0, 0.0, 14.0), (0.0, 0.0, 18.0), (0.0, 0.0, -16.0), (0.0, 0.0, 10.0)),
        fingers2=((0.0, 0.0, -14.0), (0.0, 0.0, -18.0), (0.0, 0.0, 16.0), (0.0, 0.0, -10.0)),
    ),
    _passo(
        ((-12.0, 4.5, 4.0), (-4.0, 3.0, 2.5), (1.5, 1.0, 0.0), (6.0, 0.0, 0.0)),
        ((-4.5, -2.0, 5.5), (-1.5, -1.5, 4.5), (1.0, 0.0, 3.0), (3.5, 1.0, 2.0)),
        braco_dir=("idle", "street_attitude", "graffiti_arco", "street_solto"),
        braco_esq=("contrapeso", "street_solto", "contrapeso", "street_attitude"),
        cintura=((4.5, 5.0, -4.0), (2.0, 4.0, -3.0), (0.0, 2.0, -2.0), (-2.0, 0.0, 0.0)),
        peitoral=((-5.5, -5.0, 4.0), (-2.0, -3.5, 3.0), (0.0, -1.5, 1.5), (3.0, 1.0, -1.0)),
        hand=((-6.0, 14.0, -12.0), (-10.0, 18.0, -16.0), (-4.0, 8.0, -8.0), (4.0, -6.0, 6.0)),
        hand2=((-12.0, -22.0, 18.0), (-8.0, -16.0, 14.0), (-4.0, -10.0, 10.0), (4.0, 6.0, -6.0)),
        fingers=((0.0, 0.0, -14.0), (0.0, 0.0, 14.0), (0.0, 0.0, -10.0), (0.0, 0.0, 8.0)),
        fingers2=((0.0, 0.0, 18.0), (0.0, 0.0, 12.0), (0.0, 0.0, -14.0), (0.0, 0.0, -8.0)),
    ),
    _passo(
        ((-13.0, 0.0, 2.0), (-5.0, 0.0, 0.5), (1.0, -2.0, -1.0), (5.5, -4.0, -2.0)),
        ((-6.0, -1.0, 2.5), (-2.0, 0.0, 1.5), (1.5, 1.5, 0.0), (4.0, 2.5, -1.0)),
        braco_dir=("street_solto", "dance", "street_attitude", "idle"),
        braco_esq=("contrapeso", "graffiti_arco", "street_solto", "idle"),
        cintura=((3.5, 3.0, -2.0), (1.0, 1.0, -1.0), (-1.0, -1.5, 1.0), (-2.5, -3.0, 2.0)),
        peitoral=((-4.5, -3.0, 2.0), (-1.5, -1.0, 1.0), (1.0, 2.0, -1.0), (3.0, 3.0, -2.0)),
        hand=((-8.0, 14.0, -12.0), (-12.0, 20.0, -16.0), (-4.0, 10.0, -8.0), (2.0, 0.0, 4.0)),
        hand2=((-8.0, -16.0, 14.0), (-6.0, -12.0, 10.0), (4.0, 8.0, -8.0), (2.0, 4.0, -4.0)),
        fingers=((0.0, 0.0, -12.0), (0.0, 0.0, 16.0), (0.0, 0.0, -10.0), (0.0, 0.0, 6.0)),
        fingers2=((0.0, 0.0, 14.0), (0.0, 0.0, -12.0), (0.0, 0.0, -8.0), (0.0, 0.0, 6.0)),
    ),
    _passo(
        ((-9.0, -2.0, 0.0), (-3.0, 0.0, 0.0), (2.0, 2.0, -1.0), (6.0, 4.0, -2.0)),
        ((-3.5, 0.0, 0.0), (-0.5, 0.0, 0.0), (2.0, 2.0, -1.5), (4.5, 3.5, -3.0)),
        braco_dir=("street_solto", "dance", "street_solto", "street_solto"),
        braco_esq=("idle", "street_attitude", "idle", "idle"),
        cintura=((2.5, 0.0, 0.0), (0.0, 0.0, 0.0), (-2.0, -2.0, 2.0), (-3.5, -4.0, 3.5)),
        peitoral=((-2.5, 0.0, 0.0), (0.0, 0.0, 0.0), (2.0, 2.5, -2.0), (3.5, 4.0, -3.0)),
        hand=((-6.0, 12.0, -10.0), (0.0, 0.0, 0.0), (6.0, -10.0, 10.0), (8.0, -12.0, 12.0)),
        hand2=((-6.0, -12.0, 10.0), (0.0, 0.0, 0.0), (6.0, 10.0, -10.0), (8.0, 12.0, -12.0)),
        fingers=((0.0, 0.0, -10.0), (0.0, 0.0, 4.0), (0.0, 0.0, 14.0), (0.0, 0.0, 18.0)),
        fingers2=((0.0, 0.0, 10.0), (0.0, 0.0, -4.0), (0.0, 0.0, -14.0), (0.0, 0.0, -18.0)),
    ),
    _passo(
        ((-15.0, -4.0, -6.0), (-6.0, -4.5, -4.0), (0.0, -1.0, -1.0), (6.5, 2.0, 1.5)),
        ((-7.5, 3.5, -7.5), (-3.0, 2.0, -5.5), (1.0, 0.0, -3.0), (4.5, -2.0, -2.0)),
        braco_dir=("idle", "street_attitude", "contrapeso", "contrapeso"),
        braco_esq=("street_solto", "dance", "street_solto", "idle"),
        cintura=((5.5, -6.5, 5.5), (3.0, -5.0, 4.0), (0.0, -2.0, 2.0), (-2.5, 2.0, -2.0)),
        peitoral=((-6.5, 6.5, -5.5), (-3.0, 5.0, -4.0), (0.0, 2.0, -2.0), (3.5, -3.0, 2.0)),
        hand=((6.0, 8.0, -8.0), (-8.0, 16.0, -14.0), (-14.0, 22.0, -18.0), (4.0, -8.0, 8.0)),
        hand2=((6.0, -8.0, 8.0), (-8.0, -16.0, 14.0), (-12.0, -20.0, 16.0), (4.0, 8.0, -8.0)),
        fingers=((0.0, 0.0, 14.0), (0.0, 0.0, 18.0), (0.0, 0.0, -16.0), (0.0, 0.0, 10.0)),
        fingers2=((0.0, 0.0, -14.0), (0.0, 0.0, -18.0), (0.0, 0.0, 16.0), (0.0, 0.0, -10.0)),
    ),
    _passo(
        ((-12.0, 9.0, -4.0), (-4.0, 7.0, -2.5), (1.5, 4.0, 0.0), (6.0, 1.0, 0.0)),
        ((-5.5, 2.0, -5.5), (-1.5, 1.5, -4.5), (1.0, 0.0, -3.0), (3.5, -1.0, -2.0)),
        braco_dir=("contrapeso", "street_solto", "contrapeso", "street_attitude"),
        braco_esq=("idle", "street_attitude", "graffiti_arco", "street_solto"),
        cintura=((4.5, -5.0, 4.0), (2.0, -4.0, 3.0), (0.0, -2.0, 2.0), (-2.0, 0.0, 0.0)),
        peitoral=((-5.5, 5.0, -4.0), (-2.0, 3.5, -3.0), (0.0, 1.5, -1.5), (3.0, -1.0, 1.0)),
        hand=((-12.0, 22.0, -18.0), (-8.0, 16.0, -14.0), (-4.0, 10.0, -10.0), (4.0, -6.0, 6.0)),
        hand2=((-6.0, -14.0, 12.0), (-10.0, -18.0, 16.0), (-4.0, -8.0, 8.0), (4.0, 6.0, -6.0)),
        fingers=((0.0, 0.0, -18.0), (0.0, 0.0, -12.0), (0.0, 0.0, 14.0), (0.0, 0.0, 8.0)),
        fingers2=((0.0, 0.0, 14.0), (0.0, 0.0, -14.0), (0.0, 0.0, 10.0), (0.0, 0.0, -8.0)),
    ),
    _passo(
        ((-13.0, 0.0, -2.0), (-5.0, 0.0, -0.5), (1.0, 2.0, 1.0), (5.5, 4.0, 2.0)),
        ((-6.0, 1.0, -2.5), (-2.0, 0.0, -1.5), (1.5, -1.5, 0.0), (4.0, -2.5, 1.0)),
        braco_dir=("contrapeso", "graffiti_arco", "street_solto", "idle"),
        braco_esq=("street_solto", "dance", "street_attitude", "idle"),
        cintura=((3.5, -3.0, 2.0), (1.0, -1.0, 1.0), (-1.0, 1.5, -1.0), (-2.5, 3.0, -2.0)),
        peitoral=((-4.5, 3.0, -2.0), (-1.5, 1.0, -1.0), (1.0, -2.0, 1.0), (3.0, -3.0, 2.0)),
        hand=((-8.0, 16.0, -14.0), (-6.0, 12.0, -10.0), (4.0, -8.0, 8.0), (2.0, -4.0, 4.0)),
        hand2=((-8.0, -14.0, 12.0), (-12.0, -20.0, 16.0), (-4.0, -10.0, 8.0), (2.0, 0.0, -4.0)),
        fingers=((0.0, 0.0, -14.0), (0.0, 0.0, 12.0), (0.0, 0.0, 8.0), (0.0, 0.0, -6.0)),
        fingers2=((0.0, 0.0, 12.0), (0.0, 0.0, -16.0), (0.0, 0.0, 10.0), (0.0, 0.0, -6.0)),
    ),
    _passo(
        ((-9.0, 2.0, 0.0), (-3.0, 0.0, 0.0), (2.0, -2.0, 1.0), (6.0, -4.0, 2.0)),
        ((-3.5, 0.0, 0.0), (-0.5, 0.0, 0.0), (2.0, -2.0, 1.5), (4.5, -3.5, 3.0)),
        braco_dir=("idle", "street_attitude", "idle", "street_solto"),
        braco_esq=("street_solto", "dance", "street_solto", "idle"),
        cintura=((2.5, 0.0, 0.0), (0.0, 0.0, 0.0), (-2.0, 2.0, -2.0), (-3.5, 4.0, -3.5)),
        peitoral=((-2.5, 0.0, 0.0), (0.0, 0.0, 0.0), (2.0, -2.5, 2.0), (3.5, -4.0, 3.0)),
        hand=((-6.0, 12.0, -10.0), (0.0, 0.0, 0.0), (6.0, -10.0, 10.0), (8.0, -12.0, 12.0)),
        hand2=((-6.0, -12.0, 10.0), (0.0, 0.0, 0.0), (6.0, 10.0, -10.0), (8.0, 12.0, -12.0)),
        fingers=((0.0, 0.0, -10.0), (0.0, 0.0, 4.0), (0.0, 0.0, 14.0), (0.0, 0.0, 18.0)),
        fingers2=((0.0, 0.0, 10.0), (0.0, 0.0, -4.0), (0.0, 0.0, -14.0), (0.0, 0.0, -18.0)),
    ),
)

#: Tronco inclinado para a frente no chão do breakdance (graus em ``body.x``).
BREAK_TRONCO_CHAO = -10.0
_BR_TRONCO_CHAO: Trio = (BREAK_TRONCO_CHAO, 0.0, 0.0)
#: Roll do tronco (graus) que alterna o lado a cada passo de footwork.
BREAK_TRONCO_ROLL = 4.0


def _passo_de_chao(giro: float) -> PassoDanca:
    """Passo de footwork: mãos plantadas no apoio com torção forte de cintura/peito."""
    sinal = 1.0 if giro > 0 else -1.0
    cabeca = (
        (-16.0, sinal * 6.0, giro),
        (-11.0, sinal * 4.0, giro),
        (-10.0, sinal * 2.0, giro),
        (-13.0, -sinal * 2.0, giro),
    )
    roll = BREAK_TRONCO_ROLL * sinal
    tronco = (BREAK_TRONCO_CHAO, sinal * 5.0, roll)
    return _passo(
        cabeca,
        _fixo(tronco),
        "apoio_chao",
        "apoio_chao",
        cintura=_fixo((4.0, -sinal * 8.0, -roll * 1.2)),
        peitoral=_fixo((-5.0, sinal * 8.0, roll)),
        hand=_fixo((-18.0, sinal * 14.0, -sinal * 12.0)),
        hand2=_fixo((-18.0, -sinal * 14.0, sinal * 12.0)),
        fingers=_fixo((0.0, 0.0, -18.0)),
        fingers2=_fixo((0.0, 0.0, 18.0)),
    )


def _sem_bracos(passo: PassoDanca) -> PassoDanca:
    """Cópia do ``passo`` mantendo braços soltos no toprock (``idle``)."""
    return PassoDanca(
        tuple(replace(pose, braco_dir="idle", braco_esq="idle") for pose in passo.poses)  # type: ignore[arg-type]
    )


#: Breakdance: 16 batidas (toprock, descida antecipada, footwork com torque, freeze ZZZ, pop-up).
BREAKDANCE: tuple[PassoDanca, ...] = (
    *(_sem_bracos(passo) for passo in HIP_HOP[:4]),
    _passo(
        ((-12.0, 0.0, 0.0), (-15.0, 3.0, 4.0), (-15.0, 3.0, 6.0), (-13.0, 2.0, 5.0)),
        ((-8.0, 0.0, 0.0), _BR_TRONCO_CHAO, _BR_TRONCO_CHAO, _BR_TRONCO_CHAO),
        ("idle", "idle", "apoio_chao", "apoio_chao"),
        ("idle", "idle", "apoio_chao", "apoio_chao"),
        hand=((0.0, 0.0, 0.0), (-10.0, 8.0, -8.0), (-18.0, 12.0, -10.0), (-18.0, 12.0, -10.0)),
        hand2=((0.0, 0.0, 0.0), (-10.0, -8.0, 8.0), (-18.0, -12.0, 10.0), (-18.0, -12.0, 10.0)),
        fingers=_fixo((0.0, 0.0, -14.0)),
        fingers2=_fixo((0.0, 0.0, 14.0)),
    ),
    _passo(
        _fixo((-13.0, 4.0, 6.0)),
        _fixo(_BR_TRONCO_CHAO),
        "apoio_chao",
        "apoio_chao",
        hand=_fixo((-18.0, 12.0, -10.0)),
        hand2=_fixo((-18.0, -12.0, 10.0)),
        fingers=_fixo((0.0, 0.0, -18.0)),
        fingers2=_fixo((0.0, 0.0, 18.0)),
    ),
    _passo_de_chao(6.0),
    _passo_de_chao(-6.0),
    _passo_de_chao(6.0),
    _passo_de_chao(-6.0),
    _passo_de_chao(6.0),
    _passo_de_chao(-6.0),
    _passo_de_chao(6.0),
    _passo(
        ((-12.0, -8.0, 14.0), (-10.0, -8.0, 14.0), (-10.0, -8.0, 14.0), (-12.0, -6.0, 12.0)),
        _fixo((BREAK_TRONCO_CHAO, 8.0, 6.0)),
        "apoio_chao",
        "apoio_chao",
        cintura=_fixo((5.0, -10.0, -6.0)),
        peitoral=_fixo((-6.0, 10.0, 6.0)),
        hand=_fixo((-20.0, 16.0, -14.0)),
        hand2=_fixo((-20.0, -16.0, 14.0)),
        fingers=_fixo((0.0, 0.0, -22.0)),
        fingers2=_fixo((0.0, 0.0, 22.0)),
    ),
    _passo(
        ((-10.0, 0.0, 6.0), (-6.0, 0.0, 3.0), (-2.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        ((BREAK_TRONCO_CHAO, 0.0, 0.0), (-6.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        ("apoio_chao", "apoio_chao", "idle", "idle"),
        ("apoio_chao", "apoio_chao", "idle", "idle"),
        hand=((-18.0, 12.0, -10.0), (-12.0, 8.0, -6.0), (-4.0, 4.0, -4.0), (2.0, 0.0, 2.0)),
        hand2=((-18.0, -12.0, 10.0), (-12.0, -8.0, 6.0), (-4.0, -4.0, 4.0), (2.0, 0.0, -2.0)),
        fingers=((-0.0, 0.0, -16.0), (0.0, 0.0, -10.0), (0.0, 0.0, -4.0), (0.0, 0.0, 6.0)),
        fingers2=((0.0, 0.0, 16.0), (0.0, 0.0, 10.0), (0.0, 0.0, 4.0), (0.0, 0.0, -6.0)),
    ),
    _passo(
        ((-4.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        _fixo((0.0, 0.0, 0.0)),
        "idle",
        "idle",
    ),
)

# ============================================================================
# Danças inspiradas em Bomb Rush Cyberfunk (BRC) / ZZZ
# ============================================================================

#: BRC Street groove: 8 batidas com torção oposta cintura/peito, estalos de punho
#: e alternância expressiva de palmas grandes.
STREET_GROOVE: tuple[PassoDanca, ...] = (
    _passo(
        ((-6.0, 7.0, 7.0), (-3.0, 6.0, 6.0), (-1.0, 4.0, 4.0), (2.0, 2.0, 2.0)),
        ((-3.5, 5.0, 5.5), (-2.0, 4.5, 4.5), (-0.5, 3.0, 3.5), (1.5, 1.5, 2.0)),
        braco_dir=("street_solto", "dance", "street_solto", "street_attitude"),
        braco_esq=("street_attitude", "street_attitude", "street_solto", "street_solto"),
        cintura=((4.0, -7.0, -5.0), (2.5, -6.0, -4.5), (1.0, -4.0, -3.0), (-1.5, -2.0, -1.5)),
        peitoral=((-4.0, 7.0, 5.0), (-2.5, 6.0, 4.0), (-1.0, 3.5, 3.0), (1.5, 1.5, 1.5)),
        hand=((-10.0, 18.0, -16.0), (-14.0, 24.0, -20.0), (-6.0, 12.0, -10.0), (4.0, -8.0, 8.0)),
        hand2=((6.0, -12.0, 12.0), (-8.0, -16.0, 14.0), (-12.0, -20.0, 18.0), (2.0, -8.0, 8.0)),
        fingers=((0.0, 0.0, -16.0), (0.0, 0.0, -20.0), (0.0, 0.0, 12.0), (0.0, 0.0, 14.0)),
        fingers2=((0.0, 0.0, 16.0), (0.0, 0.0, 12.0), (0.0, 0.0, -16.0), (0.0, 0.0, -10.0)),
    ),
    _passo(
        ((-3.0, 3.0, 3.0), (-1.5, 1.0, 1.0), (0.5, -1.5, -2.0), (2.5, -3.5, -4.0)),
        ((-1.5, 2.5, 3.0), (0.0, 1.0, 1.5), (1.0, -1.5, -1.5), (2.5, -3.0, -3.0)),
        braco_dir=("street_attitude", "street_attitude", "street_solto", "street_solto"),
        braco_esq=("street_solto", "graffiti_arco", "street_solto", "street_attitude"),
        cintura=((2.5, -3.0, -2.5), (0.5, -1.0, -1.0), (-1.0, 2.0, 2.0), (-2.5, 4.0, 3.5)),
        peitoral=((-2.0, 2.5, 2.0), (0.0, 1.0, 1.0), (1.0, -2.0, -2.0), (2.5, -4.0, -3.5)),
        hand=((-8.0, 14.0, -12.0), (-10.0, 18.0, -16.0), (4.0, -8.0, 8.0), (6.0, -10.0, 10.0)),
        hand2=((-8.0, -16.0, 14.0), (-14.0, -22.0, 18.0), (4.0, 8.0, -8.0), (-6.0, -12.0, 10.0)),
        fingers=((0.0, 0.0, 14.0), (0.0, 0.0, -14.0), (0.0, 0.0, 10.0), (0.0, 0.0, 12.0)),
        fingers2=((0.0, 0.0, -14.0), (0.0, 0.0, 18.0), (0.0, 0.0, -10.0), (0.0, 0.0, -12.0)),
    ),
    _passo(
        ((-6.0, -7.0, -7.0), (-3.0, -6.0, -6.0), (-1.0, -4.0, -4.0), (2.0, -2.0, -2.0)),
        ((-3.5, -5.0, -5.5), (-2.0, -4.5, -4.5), (-0.5, -3.0, -3.5), (1.5, -1.5, -2.0)),
        braco_dir=("street_attitude", "street_attitude", "street_solto", "street_solto"),
        braco_esq=("street_solto", "dance", "street_solto", "street_attitude"),
        cintura=((4.0, 7.0, 5.0), (2.5, 6.0, 4.5), (1.0, 4.0, 3.0), (-1.5, 2.0, 1.5)),
        peitoral=((-4.0, -7.0, -5.0), (-2.5, -6.0, -4.0), (-1.0, -3.5, -3.0), (1.5, -1.5, -1.5)),
        hand=((6.0, 12.0, -12.0), (-8.0, 16.0, -14.0), (-12.0, 20.0, -18.0), (2.0, 8.0, -8.0)),
        hand2=((-10.0, -18.0, 16.0), (-14.0, -24.0, 20.0), (-6.0, -12.0, 10.0), (4.0, 8.0, -8.0)),
        fingers=((0.0, 0.0, 16.0), (0.0, 0.0, 12.0), (0.0, 0.0, -16.0), (0.0, 0.0, -10.0)),
        fingers2=((0.0, 0.0, -16.0), (0.0, 0.0, -20.0), (0.0, 0.0, 12.0), (0.0, 0.0, 14.0)),
    ),
    _passo(
        ((-3.0, -3.0, -3.0), (-1.5, -1.0, -1.0), (0.5, 1.5, 2.0), (2.5, 3.5, 4.0)),
        ((-1.5, -2.5, -3.0), (0.0, -1.0, -1.5), (1.0, 1.5, 1.5), (2.5, 3.0, 3.0)),
        braco_dir=("street_solto", "graffiti_arco", "street_solto", "street_attitude"),
        braco_esq=("street_attitude", "street_attitude", "street_solto", "street_solto"),
        cintura=((2.5, 3.0, 2.5), (0.5, 1.0, 1.0), (-1.0, -2.0, -2.0), (-2.5, -4.0, -3.5)),
        peitoral=((-2.0, -2.5, -2.0), (0.0, -1.0, -1.0), (1.0, 2.0, 2.0), (2.5, 4.0, 3.5)),
        hand=((-8.0, 16.0, -14.0), (-14.0, 22.0, -18.0), (4.0, -8.0, 8.0), (-6.0, 12.0, -10.0)),
        hand2=((-8.0, -14.0, 12.0), (-10.0, -18.0, 16.0), (4.0, 8.0, -8.0), (6.0, 10.0, -10.0)),
        fingers=((0.0, 0.0, -14.0), (0.0, 0.0, -18.0), (0.0, 0.0, 10.0), (0.0, 0.0, -12.0)),
        fingers2=((0.0, 0.0, 14.0), (0.0, 0.0, 14.0), (0.0, 0.0, -10.0), (0.0, 0.0, -12.0)),
    ),
    _passo(
        ((-8.0, 7.0, 7.0), (-4.0, 6.0, 6.0), (-1.5, 4.0, 4.0), (2.0, 2.0, 2.0)),
        ((-4.5, 5.5, 6.0), (-2.5, 4.5, 4.5), (-0.5, 3.0, 3.5), (1.5, 1.5, 2.0)),
        braco_dir=("street_solto", "chifre", "street_solto", "street_attitude"),
        braco_esq=("street_attitude", "street_attitude", "street_solto", "street_solto"),
        cintura=((4.5, -7.0, -5.0), (2.5, -6.0, -4.5), (1.0, -4.0, -3.0), (-1.5, -2.0, -1.5)),
        peitoral=((-4.5, 7.0, 5.0), (-2.5, 6.0, 4.0), (-1.0, 3.5, 3.0), (1.5, 1.5, 1.5)),
        hand=((-12.0, 20.0, -18.0), (-14.0, 24.0, -20.0), (-6.0, 12.0, -10.0), (4.0, -8.0, 8.0)),
        hand2=((6.0, -12.0, 12.0), (-8.0, -16.0, 14.0), (-12.0, -20.0, 18.0), (2.0, -8.0, 8.0)),
        fingers=((0.0, 0.0, -18.0), (0.0, 0.0, -16.0), (0.0, 0.0, 12.0), (0.0, 0.0, 14.0)),
        fingers2=((0.0, 0.0, 16.0), (0.0, 0.0, 12.0), (0.0, 0.0, -16.0), (0.0, 0.0, -10.0)),
    ),
    _passo(
        ((-4.0, 3.0, 3.0), (-1.5, 1.0, 1.0), (0.5, -1.5, -2.0), (2.5, -3.5, -4.0)),
        ((-2.0, 2.5, 3.0), (0.0, 1.0, 1.5), (1.0, -1.5, -1.5), (2.5, -3.0, -3.0)),
        braco_dir=("street_attitude", "street_attitude", "street_solto", "street_solto"),
        braco_esq=("street_solto", "cyber_angular", "street_solto", "street_attitude"),
        cintura=((2.5, -3.0, -2.5), (0.5, -1.0, -1.0), (-1.0, 2.0, 2.0), (-2.5, 4.0, 3.5)),
        peitoral=((-2.0, 2.5, 2.0), (0.0, 1.0, 1.0), (1.0, -2.0, -2.0), (2.5, -4.0, -3.5)),
        hand=((-8.0, 14.0, -12.0), (-10.0, 18.0, -16.0), (4.0, -8.0, 8.0), (6.0, -10.0, 10.0)),
        hand2=((-8.0, -16.0, 14.0), (-14.0, -22.0, 18.0), (4.0, 8.0, -8.0), (-6.0, -12.0, 10.0)),
        fingers=((0.0, 0.0, 14.0), (0.0, 0.0, -14.0), (0.0, 0.0, 10.0), (0.0, 0.0, 12.0)),
        fingers2=((0.0, 0.0, -14.0), (0.0, 0.0, 18.0), (0.0, 0.0, -10.0), (0.0, 0.0, -12.0)),
    ),
    _passo(
        ((-8.0, -7.0, -7.0), (-4.0, -6.0, -6.0), (-1.5, -4.0, -4.0), (2.0, -2.0, -2.0)),
        ((-4.5, -5.5, -6.0), (-2.5, -4.5, -4.5), (-0.5, -3.0, -3.5), (1.5, -1.5, -2.0)),
        braco_dir=("street_attitude", "street_attitude", "street_solto", "street_solto"),
        braco_esq=("street_solto", "chifre", "street_solto", "street_attitude"),
        cintura=((4.5, 7.0, 5.0), (2.5, 6.0, 4.5), (1.0, 4.0, 3.0), (-1.5, 2.0, 1.5)),
        peitoral=((-4.5, -7.0, -5.0), (-2.5, -6.0, -4.0), (-1.0, -3.5, -3.0), (1.5, -1.5, -1.5)),
        hand=((6.0, 12.0, -12.0), (-8.0, 16.0, -14.0), (-12.0, 20.0, -18.0), (2.0, 8.0, -8.0)),
        hand2=((-12.0, -20.0, 18.0), (-14.0, -24.0, 20.0), (-6.0, -12.0, 10.0), (4.0, 8.0, -8.0)),
        fingers=((0.0, 0.0, 16.0), (0.0, 0.0, 12.0), (0.0, 0.0, -16.0), (0.0, 0.0, -10.0)),
        fingers2=((0.0, 0.0, -18.0), (0.0, 0.0, -16.0), (0.0, 0.0, 12.0), (0.0, 0.0, 14.0)),
    ),
    _passo(
        ((-4.0, -3.0, -3.0), (-2.0, -1.5, -1.5), (-0.5, 0.0, 0.0), (1.5, 2.0, 2.0)),
        ((-2.0, -2.0, -2.5), (-1.0, -1.0, -1.5), (0.0, 0.0, 0.0), (1.0, 1.5, 1.5)),
        braco_dir="street_solto",
        braco_esq="street_solto",
        cintura=((2.0, 3.0, 2.0), (1.0, 1.5, 1.0), (0.0, 0.0, 0.0), (-1.0, -2.0, -2.0)),
        peitoral=((-2.0, -3.0, -2.0), (-1.0, -1.5, -1.0), (0.0, 0.0, 0.0), (1.0, 2.0, 2.0)),
        hand=((-6.0, 12.0, -10.0), (0.0, 0.0, 0.0), (4.0, -6.0, 6.0), (2.0, -4.0, 4.0)),
        hand2=((-6.0, -12.0, 10.0), (0.0, 0.0, 0.0), (4.0, 6.0, -6.0), (2.0, 4.0, -4.0)),
        fingers=((0.0, 0.0, -12.0), (0.0, 0.0, 4.0), (0.0, 0.0, 10.0), (0.0, 0.0, 6.0)),
        fingers2=((0.0, 0.0, 12.0), (0.0, 0.0, -4.0), (0.0, 0.0, -10.0), (0.0, 0.0, -6.0)),
    ),
)

#: BRC Graffiti dance: 8 batidas. Traços largos de spray com rotação de quadril/peito,
#: torção rítmica do pulso simulando bico da lata e follow-through na cabeça/antenas.
GRAFFITI_DANCE: tuple[PassoDanca, ...] = (
    _passo(
        ((-6.0, 5.0, 8.0), (-4.0, 3.0, 6.0), (-2.0, 1.5, 4.0), (1.0, 0.5, 2.0)),
        ((-4.0, 4.0, 6.0), (-3.0, 3.0, 5.0), (-1.5, 1.5, 3.5), (1.0, 0.5, 2.0)),
        braco_dir=("graffiti_spray", "graffiti_arco", "graffiti_spray", "graffiti_arco"),
        braco_esq=("graffiti_arco", "cyber_baixo", "graffiti_arco", "graffiti_spray"),
        cintura=((3.5, -6.0, -5.0), (2.0, -5.0, -4.0), (1.0, -3.0, -2.5), (-1.0, -1.0, -1.0)),
        peitoral=((-4.0, 6.0, 5.0), (-3.0, 5.0, 4.0), (-1.5, 2.5, 2.5), (1.0, 1.0, 1.0)),
        hand=((-16.0, 20.0, -18.0), (-10.0, 26.0, -22.0), (-14.0, 14.0, -12.0), (4.0, -6.0, 8.0)),
        hand2=((6.0, -10.0, 10.0), (-8.0, -14.0, 12.0), (-12.0, -20.0, 16.0), (4.0, 6.0, -6.0)),
        fingers=((0.0, 0.0, 14.0), (0.0, 0.0, 22.0), (0.0, 0.0, 12.0), (0.0, 0.0, -12.0)),
        fingers2=((0.0, 0.0, -14.0), (0.0, 0.0, 14.0), (0.0, 0.0, -18.0), (0.0, 0.0, 10.0)),
    ),
    _passo(
        ((-4.0, 3.0, 6.0), (-2.0, 1.5, 4.0), (-1.0, 0.5, 2.0), (1.0, -1.0, -1.0)),
        ((-3.0, 2.5, 5.0), (-2.0, 1.5, 3.5), (-1.0, 0.5, 2.5), (0.5, -1.0, 1.0)),
        braco_dir=("graffiti_arco", "dance", "graffiti_arco", "graffiti_spray"),
        braco_esq=("graffiti_spray", "graffiti_spray", "graffiti_arco", "graffiti_arco"),
        hand=((-12.0, 24.0, -20.0), (-16.0, 26.0, -22.0), (-8.0, 16.0, -14.0), (4.0, -8.0, 8.0)),
        hand2=((-14.0, -20.0, 18.0), (-16.0, -22.0, 18.0), (-8.0, -14.0, 12.0), (4.0, 8.0, -8.0)),
        fingers=((0.0, 0.0, -18.0), (0.0, 0.0, -20.0), (0.0, 0.0, 14.0), (0.0, 0.0, 10.0)),
        fingers2=((0.0, 0.0, 18.0), (0.0, 0.0, 20.0), (0.0, 0.0, -14.0), (0.0, 0.0, -10.0)),
    ),
    _passo(
        ((-6.0, -5.0, -8.0), (-4.0, -3.0, -6.0), (-2.0, -1.5, -4.0), (1.0, -0.5, -2.0)),
        ((-4.0, -4.0, -6.0), (-3.0, -3.0, -5.0), (-1.5, -1.5, -3.5), (1.0, -0.5, -2.0)),
        braco_dir=("graffiti_arco", "cyber_baixo", "graffiti_arco", "graffiti_spray"),
        braco_esq=("graffiti_spray", "graffiti_arco", "graffiti_spray", "graffiti_arco"),
        cintura=((3.5, 6.0, 5.0), (2.0, 5.0, 4.0), (1.0, 3.0, 2.5), (-1.0, 1.0, 1.0)),
        peitoral=((-4.0, -6.0, -5.0), (-3.0, -5.0, -4.0), (-1.5, -2.5, -2.5), (1.0, -1.0, -1.0)),
        hand=((6.0, 10.0, -10.0), (-8.0, 14.0, -12.0), (-12.0, 20.0, -16.0), (4.0, -6.0, 6.0)),
        hand2=((-16.0, -20.0, 18.0), (-10.0, -26.0, 22.0), (-14.0, -14.0, 12.0), (4.0, 6.0, -8.0)),
        fingers=((0.0, 0.0, 14.0), (0.0, 0.0, -14.0), (0.0, 0.0, 18.0), (0.0, 0.0, -10.0)),
        fingers2=((0.0, 0.0, -14.0), (0.0, 0.0, -22.0), (0.0, 0.0, -12.0), (0.0, 0.0, 12.0)),
    ),
    _passo(
        ((-4.0, -3.0, -6.0), (-2.0, -1.5, -4.0), (-1.0, -0.5, -2.0), (1.0, 1.0, 1.0)),
        ((-3.0, -2.5, -5.0), (-2.0, -1.5, -3.5), (-1.0, -0.5, -2.5), (0.5, 1.0, -1.0)),
        braco_dir=("graffiti_spray", "graffiti_spray", "graffiti_arco", "graffiti_arco"),
        braco_esq=("graffiti_arco", "dance", "graffiti_arco", "graffiti_spray"),
        hand=((-14.0, 20.0, -18.0), (-16.0, 22.0, -18.0), (-8.0, 14.0, -12.0), (4.0, -8.0, 8.0)),
        hand2=((-12.0, -24.0, 20.0), (-16.0, -26.0, 22.0), (-8.0, -16.0, 14.0), (4.0, 8.0, -8.0)),
        fingers=((0.0, 0.0, -18.0), (0.0, 0.0, -20.0), (0.0, 0.0, 14.0), (0.0, 0.0, 10.0)),
        fingers2=((0.0, 0.0, 18.0), (0.0, 0.0, 20.0), (0.0, 0.0, -14.0), (0.0, 0.0, -10.0)),
    ),
    _passo(
        ((-7.0, 0.0, 4.0), (-3.5, 0.0, 3.0), (-1.5, 0.0, 1.5), (1.5, 0.0, 0.0)),
        ((-5.0, 0.0, 3.0), (-3.0, 0.0, 2.5), (-1.5, 0.0, 1.5), (1.0, 0.0, 0.0)),
        braco_dir="graffiti_spray",
        braco_esq="graffiti_spray",
        hand=((-14.0, 18.0, -16.0), (-10.0, 14.0, -12.0), (-6.0, 10.0, -8.0), (4.0, -6.0, 6.0)),
        hand2=((-14.0, -18.0, 16.0), (-10.0, -14.0, 12.0), (-6.0, -10.0, 8.0), (4.0, 6.0, -6.0)),
        fingers=((0.0, 0.0, 18.0), (0.0, 0.0, 14.0), (0.0, 0.0, -12.0), (0.0, 0.0, 8.0)),
        fingers2=((0.0, 0.0, -18.0), (0.0, 0.0, -14.0), (0.0, 0.0, 12.0), (0.0, 0.0, -8.0)),
    ),
    _passo(
        ((-5.0, 0.0, 3.0), (-2.5, 0.0, 2.0), (-1.0, 0.0, 1.0), (1.5, 2.0, 1.5)),
        ((-4.0, 0.0, 2.5), (-2.0, 0.0, 1.5), (-0.5, 0.0, 0.5), (1.5, 1.5, 1.5)),
        braco_dir=("graffiti_arco", "graffiti_spray", "graffiti_arco", "graffiti_spray"),
        braco_esq=("graffiti_arco", "street_attitude", "graffiti_arco", "graffiti_spray"),
        hand=((-10.0, 22.0, -18.0), (-14.0, 24.0, -20.0), (-6.0, 12.0, -10.0), (2.0, 4.0, -4.0)),
        hand2=((-10.0, -22.0, 18.0), (-14.0, -24.0, 20.0), (-6.0, -12.0, 10.0), (2.0, -4.0, 4.0)),
        fingers=((0.0, 0.0, -18.0), (0.0, 0.0, -20.0), (0.0, 0.0, -12.0), (0.0, 0.0, 10.0)),
        fingers2=((0.0, 0.0, 18.0), (0.0, 0.0, 20.0), (0.0, 0.0, 12.0), (0.0, 0.0, -10.0)),
    ),
    _passo(
        ((-9.0, 6.0, 10.0), (-5.0, 4.0, 7.0), (-2.5, 2.0, 4.0), (0.0, 1.0, 2.0)),
        ((-6.0, 4.5, 7.0), (-3.5, 3.0, 5.0), (-1.5, 1.5, 3.0), (0.5, 0.5, 1.0)),
        braco_dir=("graffiti_spray", "dance", "graffiti_arco", "idle"),
        braco_esq=("graffiti_arco", "graffiti_arco", "cyber_baixo", "idle"),
        cintura=((4.5, -7.0, -6.0), (2.5, -5.0, -4.0), (1.0, -2.5, -2.0), (0.0, 0.0, 0.0)),
        peitoral=((-5.0, 7.0, 6.0), (-3.0, 5.0, 4.0), (-1.0, 2.5, 2.0), (0.0, 0.0, 0.0)),
        hand=((-18.0, 24.0, -22.0), (-14.0, 22.0, -18.0), (-6.0, 10.0, -8.0), (0.0, 0.0, 0.0)),
        hand2=((6.0, -10.0, 10.0), (-10.0, -16.0, 14.0), (4.0, 6.0, -6.0), (0.0, 0.0, 0.0)),
        fingers=((0.0, 0.0, 20.0), (0.0, 0.0, -18.0), (0.0, 0.0, 10.0), (0.0, 0.0, 0.0)),
        fingers2=((0.0, 0.0, -14.0), (0.0, 0.0, 16.0), (0.0, 0.0, -8.0), (0.0, 0.0, 0.0)),
    ),
    _passo(
        ((-4.0, 2.0, 3.0), (-2.0, 1.0, 1.5), (-0.5, 0.5, 0.5), (0.0, 0.0, 0.0)),
        ((-2.5, 1.5, 2.0), (-1.0, 1.0, 1.0), (-0.3, 0.5, 0.3), (0.0, 0.0, 0.0)),
        braco_dir="idle",
        braco_esq="idle",
    ),
)

#: BRC Cyber bounce: 4 batidas. Squash profundo no chão seguido de estirão em V
#: cibernético, estalos angulares de punho e vibração elástica de antenas.
CYBER_BOUNCE: tuple[PassoDanca, ...] = (
    _passo(
        ((-12.0, 4.0, 4.0), (-6.0, 3.0, 2.0), (-2.0, 1.0, 0.0), (4.0, -2.0, -2.0)),
        ((-8.0, 3.0, 3.0), (-4.0, 2.0, 1.5), (-1.5, 0.5, 0.0), (4.0, -1.5, -1.5)),
        braco_dir=("cyber_baixo", "street_solto", "cyber_angular", "street_solto"),
        braco_esq=("cyber_baixo", "street_solto", "cyber_angular", "street_solto"),
        cintura=((6.0, -5.0, -4.0), (3.5, -3.5, -3.0), (1.0, -1.5, -1.0), (-3.0, 2.0, 2.0)),
        peitoral=((-6.0, 5.0, 4.0), (-3.0, 3.5, 2.5), (-1.0, 1.5, 1.0), (3.5, -2.0, -2.0)),
        hand=((8.0, -10.0, 10.0), (4.0, -6.0, 6.0), (-12.0, 20.0, -18.0), (6.0, -8.0, 8.0)),
        hand2=((8.0, 10.0, -10.0), (4.0, 6.0, -6.0), (-12.0, -20.0, 18.0), (6.0, 8.0, -8.0)),
        fingers=((0.0, 0.0, 20.0), (0.0, 0.0, 14.0), (0.0, 0.0, -18.0), (0.0, 0.0, 16.0)),
        fingers2=((0.0, 0.0, -20.0), (0.0, 0.0, -14.0), (0.0, 0.0, 18.0), (0.0, 0.0, -16.0)),
    ),
    _passo(
        ((-5.0, -4.0, -4.0), (-2.0, -2.0, -2.0), (0.0, 0.0, 0.0), (3.0, 3.0, 3.0)),
        ((-4.0, -3.0, -3.0), (-1.5, -1.5, -1.5), (0.5, 0.5, 0.5), (3.0, 2.5, 2.5)),
        braco_dir=("cyber_angular", "chifre", "cyber_angular", "cyber_angular"),
        braco_esq=("cyber_angular", "chifre", "cyber_angular", "cyber_angular"),
        hand=((-12.0, 22.0, -18.0), (-16.0, 26.0, -22.0), (-10.0, 18.0, -14.0), (4.0, -8.0, 8.0)),
        hand2=((-12.0, -22.0, 18.0), (-16.0, -26.0, 22.0), (-10.0, -18.0, 14.0), (4.0, 8.0, -8.0)),
        fingers=((0.0, 0.0, -18.0), (0.0, 0.0, -22.0), (0.0, 0.0, -16.0), (0.0, 0.0, 12.0)),
        fingers2=((0.0, 0.0, 18.0), (0.0, 0.0, 22.0), (0.0, 0.0, 16.0), (0.0, 0.0, -12.0)),
    ),
    _passo(
        ((-3.0, 5.0, 5.0), (-1.5, 3.0, 3.0), (0.0, 1.0, 1.0), (2.0, -1.0, -1.0)),
        ((-2.5, 4.0, 4.0), (-1.0, 2.5, 2.5), (0.0, 1.0, 1.0), (2.0, -1.0, -1.0)),
        braco_dir=("cyber_angular", "dance", "cyber_angular", "cyber_baixo"),
        braco_esq=("cyber_angular", "graffiti_arco", "cyber_angular", "cyber_baixo"),
        hand=((-14.0, 22.0, -20.0), (-16.0, 24.0, -22.0), (-10.0, 16.0, -14.0), (6.0, -8.0, 8.0)),
        hand2=((-14.0, -22.0, 20.0), (-16.0, -24.0, 22.0), (-10.0, -16.0, 14.0), (6.0, 8.0, -8.0)),
        fingers=((0.0, 0.0, -18.0), (0.0, 0.0, -20.0), (0.0, 0.0, 12.0), (0.0, 0.0, 16.0)),
        fingers2=((0.0, 0.0, 18.0), (0.0, 0.0, 20.0), (0.0, 0.0, -12.0), (0.0, 0.0, -16.0)),
    ),
    _passo(
        ((-1.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (-5.0, 0.0, 0.0), (-9.0, 2.0, 2.0)),
        ((-1.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (-4.0, 1.5, 1.5), (-6.5, 2.5, 2.5)),
        braco_dir="cyber_baixo",
        braco_esq="cyber_baixo",
        hand=((6.0, -8.0, 8.0), (4.0, -6.0, 6.0), (6.0, -8.0, 8.0), (8.0, -10.0, 10.0)),
        hand2=((6.0, 8.0, -8.0), (4.0, 6.0, -6.0), (6.0, 8.0, -8.0), (8.0, 10.0, -10.0)),
        fingers=((0.0, 0.0, 16.0), (0.0, 0.0, 12.0), (0.0, 0.0, 16.0), (0.0, 0.0, 20.0)),
        fingers2=((0.0, 0.0, -16.0), (0.0, 0.0, -12.0), (0.0, 0.0, -16.0), (0.0, 0.0, -20.0)),
    ),
)

#: Funk Glide v2.0 (Jet Set / Bomb Rush Cyberfunk): 4 tempos.
#: Deslize lateral estiloso com ombros soltos, mão no fone, apontada rítmica e rebolado.
FUNK_GLIDE: tuple[PassoDanca, ...] = (
    _passo(
        ((-5.0, -10.0, -7.0), (-3.0, -6.0, -4.0), (0.0, -2.0, -1.0), (3.0, 4.0, 3.0)),
        ((-3.5, 11.0, 5.0), (-1.5, 7.0, 3.0), (0.0, 2.0, 1.0), (2.5, -5.0, -3.0)),
        braco_dir=("street_solto", "dance", "street_solto", "cyber_baixo"),
        braco_esq=("graffiti_arco", "street_solto", "cyber_angular", "street_solto"),
        cintura=((3.0, -10.0, -6.0), (1.5, -6.0, -3.5), (0.0, -2.0, -1.0), (-2.0, 5.0, 3.0)),
        peitoral=((-4.0, 12.0, 5.0), (-2.0, 7.0, 3.0), (0.0, 2.0, 1.0), (2.5, -6.0, -3.0)),
        hand=((-14.0, 18.0, -16.0), (-10.0, 14.0, -12.0), (-4.0, 6.0, -6.0), (6.0, -8.0, 8.0)),
        hand2=((6.0, -12.0, 12.0), (-10.0, -16.0, 14.0), (-6.0, -10.0, 10.0), (4.0, 6.0, -6.0)),
        fingers=((0.0, 0.0, -16.0), (0.0, 0.0, 12.0), (0.0, 0.0, -14.0), (0.0, 0.0, 16.0)),
        fingers2=((0.0, 0.0, 14.0), (0.0, 0.0, -16.0), (0.0, 0.0, 12.0), (0.0, 0.0, -10.0)),
    ),
    _passo(
        ((-5.0, 10.0, 7.0), (-3.0, 6.0, 4.0), (0.0, 2.0, 1.0), (3.0, -4.0, -3.0)),
        ((-3.5, -11.0, -5.0), (-1.5, -7.0, -3.0), (0.0, -2.0, -1.0), (2.5, 5.0, 3.0)),
        braco_dir=("graffiti_arco", "street_solto", "cyber_angular", "street_solto"),
        braco_esq=("street_solto", "dance", "street_solto", "cyber_baixo"),
        cintura=((3.0, 10.0, 6.0), (1.5, 6.0, 3.5), (0.0, 2.0, 1.0), (-2.0, -5.0, -3.0)),
        peitoral=((-4.0, -12.0, -5.0), (-2.0, -7.0, -3.0), (0.0, -2.0, -1.0), (2.5, 6.0, 3.0)),
        hand=((6.0, 12.0, -12.0), (-10.0, 16.0, -14.0), (-6.0, 10.0, -10.0), (4.0, -6.0, 6.0)),
        hand2=((-14.0, -18.0, 16.0), (-10.0, -14.0, 12.0), (-4.0, -6.0, 6.0), (6.0, 8.0, -8.0)),
        fingers=((0.0, 0.0, 14.0), (0.0, 0.0, -16.0), (0.0, 0.0, 12.0), (0.0, 0.0, -10.0)),
        fingers2=((0.0, 0.0, -16.0), (0.0, 0.0, 12.0), (0.0, 0.0, -14.0), (0.0, 0.0, 16.0)),
    ),
    _passo(
        ((-8.0, -4.0, -4.0), (-4.0, -2.0, -2.0), (1.0, 0.0, 0.0), (5.0, 4.0, 3.0)),
        ((-6.0, 6.0, 4.0), (-3.0, 3.0, 2.0), (1.0, 0.0, 0.0), (4.0, -4.0, -2.0)),
        braco_dir=("cyber_angular", "chifre", "cyber_angular", "street_solto"),
        braco_esq=("street_solto", "cyber_baixo", "street_solto", "graffiti_arco"),
        cintura=((5.0, -6.0, -4.0), (2.5, -3.0, -2.0), (-1.0, 0.0, 0.0), (-3.0, 4.0, 2.5)),
        peitoral=((-5.0, 8.0, 4.0), (-2.5, 4.0, 2.0), (1.0, 0.0, 0.0), (3.5, -5.0, -2.5)),
        hand=((-16.0, 24.0, -20.0), (-12.0, 18.0, -16.0), (-6.0, 10.0, -8.0), (4.0, -6.0, 6.0)),
        hand2=((6.0, 8.0, -8.0), (8.0, 10.0, -10.0), (4.0, 6.0, -6.0), (-8.0, -12.0, 10.0)),
    ),
    _passo(
        ((-7.0, 5.0, 5.0), (-3.5, 2.5, 2.5), (1.0, 0.0, 0.0), (4.0, -3.0, -2.0)),
        ((-5.0, -6.0, -4.0), (-2.5, -3.0, -2.0), (0.5, 0.0, 0.0), (3.5, 3.5, 2.0)),
        braco_dir=("street_solto", "cyber_baixo", "street_solto", "graffiti_arco"),
        braco_esq=("cyber_angular", "chifre", "cyber_angular", "street_solto"),
        cintura=((4.5, 6.0, 4.0), (2.0, 3.0, 2.0), (-1.0, 0.0, 0.0), (-3.0, -4.0, -2.5)),
        peitoral=((-4.5, -8.0, -4.0), (-2.0, -4.0, -2.0), (1.0, 0.0, 0.0), (3.5, 5.0, 2.5)),
        hand=((6.0, -8.0, 8.0), (8.0, -10.0, 10.0), (4.0, -6.0, 6.0), (-8.0, 12.0, -10.0)),
        hand2=((-16.0, -24.0, 20.0), (-12.0, -18.0, 16.0), (-6.0, -10.0, 8.0), (4.0, 6.0, -6.0)),
    ),
)

#: Cyber Skank v2.0 (Hi-Fi Rush / energia alta): 4 tempos com congelamento angular e punch seco.
CYBER_SKANK: tuple[PassoDanca, ...] = (
    _passo(
        ((-14.0, -12.0, -8.0), (-12.0, -10.0, -7.0), (2.0, 2.0, 1.0), (6.0, 8.0, 5.0)),
        ((-10.0, 14.0, 7.0), (-9.0, 12.0, 6.0), (2.0, -2.0, -1.0), (5.0, -8.0, -5.0)),
        braco_dir=("cyber_angular", "cyber_angular", "cyber_baixo", "chifre"),
        braco_esq=("cyber_baixo", "cyber_baixo", "cyber_angular", "dance"),
        cintura=((7.0, -10.0, -6.0), (6.0, -9.0, -5.0), (-1.0, 2.0, 1.0), (-4.0, 7.0, 4.0)),
        peitoral=((-8.0, 12.0, 6.0), (-7.0, 11.0, 5.0), (2.0, -2.0, -1.0), (5.0, -8.0, -4.0)),
        hand=((-18.0, 26.0, -24.0), (-18.0, 26.0, -24.0), (6.0, -8.0, 8.0), (-14.0, 20.0, -18.0)),
        hand2=((10.0, 12.0, -12.0), (10.0, 12.0, -12.0), (-14.0, -20.0, 18.0), (-12.0, -18.0, 16.0)),
        fingers=((0.0, 0.0, -22.0), (0.0, 0.0, -22.0), (0.0, 0.0, 18.0), (0.0, 0.0, -18.0)),
        fingers2=((0.0, 0.0, -18.0), (0.0, 0.0, -18.0), (0.0, 0.0, 20.0), (0.0, 0.0, 18.0)),
    ),
    _passo(
        ((-14.0, 12.0, 8.0), (-12.0, 10.0, 7.0), (2.0, -2.0, -1.0), (6.0, -8.0, -5.0)),
        ((-10.0, -14.0, -7.0), (-9.0, -12.0, -6.0), (2.0, 2.0, 1.0), (5.0, 8.0, 5.0)),
        braco_dir=("cyber_baixo", "cyber_baixo", "cyber_angular", "dance"),
        braco_esq=("cyber_angular", "cyber_angular", "cyber_baixo", "chifre"),
        cintura=((7.0, 10.0, 6.0), (6.0, 9.0, 5.0), (-1.0, -2.0, -1.0), (-4.0, -7.0, -4.0)),
        peitoral=((-8.0, -12.0, -6.0), (-7.0, -11.0, -5.0), (2.0, 2.0, 1.0), (5.0, 8.0, 4.0)),
        hand=((10.0, -12.0, 12.0), (10.0, -12.0, 12.0), (-14.0, 20.0, -18.0), (-12.0, 18.0, -16.0)),
        hand2=((-18.0, -26.0, 24.0), (-18.0, -26.0, 24.0), (6.0, 8.0, -8.0), (-14.0, -20.0, 18.0)),
        fingers=((0.0, 0.0, 18.0), (0.0, 0.0, 18.0), (0.0, 0.0, -20.0), (0.0, 0.0, -18.0)),
        fingers2=((0.0, 0.0, 22.0), (0.0, 0.0, 22.0), (0.0, 0.0, -18.0), (0.0, 0.0, 18.0)),
    ),
    _passo(
        ((-11.0, 0.0, -5.0), (-5.0, 0.0, -2.0), (4.0, 0.0, 2.0), (9.0, 0.0, 5.0)),
        ((-9.0, 0.0, 5.0), (-4.0, 0.0, 2.0), (3.0, 0.0, -2.0), (7.0, 0.0, -4.0)),
        braco_dir=("chifre", "cyber_angular", "dance", "cyber_baixo"),
        braco_esq=("chifre", "cyber_angular", "dance", "cyber_baixo"),
        cintura=((6.5, 0.0, -3.5), (3.0, 0.0, -1.5), (-2.0, 0.0, 1.5), (-5.0, 0.0, 3.0)),
        peitoral=((-7.5, 0.0, 3.5), (-3.5, 0.0, 1.5), (2.5, 0.0, -1.5), (6.0, 0.0, -3.0)),
    ),
    _passo(
        ((-10.0, 6.0, 4.0), (-6.0, 3.0, 2.0), (2.0, -2.0, -1.0), (-6.0, -5.0, -3.0)),
        ((-8.0, -6.0, -4.0), (-4.5, -3.0, -2.0), (2.0, 2.0, 1.0), (-4.5, 5.0, 3.0)),
        braco_dir=("dance", "graffiti_arco", "cyber_angular", "cyber_baixo"),
        braco_esq=("graffiti_arco", "dance", "cyber_angular", "cyber_baixo"),
        cintura=((5.0, 5.0, 3.0), (2.5, 2.5, 1.5), (-1.5, -1.5, -1.0), (3.0, -4.0, -2.0)),
        peitoral=((-6.0, -6.0, -3.0), (-3.0, -3.0, -1.5), (2.0, 2.0, 1.0), (-3.5, 5.0, 2.0)),
    ),
)

#: Walkman Shuffle v2.0: 4 tempos. Toca no Walkman da cintura, estala os dedos e abre o passo.
WALKMAN_SHUFFLE: tuple[PassoDanca, ...] = (
    _passo(
        ((-6.0, -6.0, -4.0), (-3.0, -4.0, -2.0), (1.0, 0.0, 0.0), (3.0, 4.0, 2.0)),
        ((-4.0, 8.0, 3.0), (-2.0, 5.0, 2.0), (0.5, 1.0, 0.0), (2.0, -4.0, -2.0)),
        braco_dir=("street_solto", "cyber_baixo", "street_solto", "dance"),
        braco_esq=("idle", "street_solto", "graffiti_arco", "street_solto"),
        cintura=((3.5, -6.0, -3.0), (2.0, -4.0, -2.0), (-0.5, 0.0, 0.0), (-2.0, 4.0, 2.0)),
        peitoral=((-3.5, 7.0, 3.0), (-2.0, 4.5, 2.0), (0.5, 0.0, 0.0), (2.5, -4.5, -2.0)),
        hand=((-10.0, 14.0, -12.0), (6.0, -8.0, 8.0), (-12.0, 18.0, -14.0), (-16.0, 22.0, -18.0)),
        hand2=((4.0, 6.0, -6.0), (-6.0, -10.0, 10.0), (-12.0, -18.0, 16.0), (4.0, 6.0, -6.0)),
    ),
    _passo(
        ((-5.0, 7.0, 5.0), (-2.5, 4.0, 2.5), (1.0, 0.0, 0.0), (3.0, -4.0, -2.0)),
        ((-3.5, -8.0, -4.0), (-1.5, -5.0, -2.0), (0.5, -1.0, 0.0), (2.5, 4.0, 2.0)),
        braco_dir=("dance", "street_solto", "cyber_angular", "street_solto"),
        braco_esq=("street_solto", "cyber_baixo", "street_solto", "dance"),
        cintura=((3.0, 7.0, 3.5), (1.5, 4.0, 2.0), (-0.5, 0.0, 0.0), (-2.0, -4.0, -2.0)),
        peitoral=((-3.0, -8.0, -3.5), (-1.5, -4.5, -2.0), (0.5, 0.0, 0.0), (2.5, 4.5, 2.0)),
        hand=((-14.0, 18.0, -16.0), (-6.0, 10.0, -8.0), (-14.0, 20.0, -16.0), (4.0, -6.0, 6.0)),
        hand2=((6.0, 8.0, -8.0), (8.0, 10.0, -10.0), (-10.0, -14.0, 12.0), (-16.0, -22.0, 18.0)),
    ),
    _passo(
        ((-7.0, -5.0, -3.0), (-3.5, -2.5, -1.5), (1.0, 1.0, 1.0), (4.0, 5.0, 3.0)),
        ((-5.0, 6.0, 3.0), (-2.5, 3.0, 1.5), (1.0, -1.0, -1.0), (3.0, -5.0, -3.0)),
        braco_dir=("graffiti_arco", "cyber_angular", "street_solto", "cyber_baixo"),
        braco_esq=("cyber_angular", "graffiti_arco", "street_solto", "cyber_baixo"),
        cintura=((4.0, -5.0, -3.0), (2.0, -2.5, -1.5), (-1.0, 1.0, 1.0), (-2.5, 4.0, 2.0)),
        peitoral=((-4.5, 6.0, 3.0), (-2.0, 3.0, 1.5), (1.0, -1.0, -1.0), (3.0, -5.0, -2.0)),
    ),
    _passo(
        ((-6.0, 5.0, 3.0), (-3.0, 2.5, 1.5), (0.5, 0.0, 0.0), (-3.0, -3.0, -2.0)),
        ((-4.0, -5.0, -3.0), (-2.0, -2.5, -1.5), (0.5, 0.0, 0.0), (-2.0, 3.0, 2.0)),
        braco_dir=("street_solto", "dance", "street_solto", "idle"),
        braco_esq=("street_solto", "dance", "street_solto", "idle"),
        cintura=((3.5, 5.0, 2.5), (1.5, 2.5, 1.0), (-0.5, 0.0, 0.0), (2.0, -3.0, -1.5)),
        peitoral=((-3.5, -5.5, -2.5), (-1.5, -2.5, -1.0), (0.5, 0.0, 0.0), (-2.0, 3.5, 1.5)),
    ),
)

#: Frase de cada estilo procedural padrão.
FRASES: dict[str, tuple[PassoDanca, ...]] = {
    "head_bob": HEAD_BOB,
    "rock": ROCK,
    "hip_hop": HIP_HOP,
    "breakdance": BREAKDANCE,
    "street_groove": STREET_GROOVE,
    "graffiti_dance": GRAFFITI_DANCE,
    "cyber_bounce": CYBER_BOUNCE,
    "funk_glide": FUNK_GLIDE,
    "cyber_skank": CYBER_SKANK,
    "walkman_shuffle": WALKMAN_SHUFFLE,
}


def _passo_de_dict(bruto: dict[str, object]) -> PassoDanca:
    poses_brutas = bruto.get("poses", ())
    poses: list[PoseDanca] = []
    for item in poses_brutas:  # type: ignore[attr-defined]
        corpo = {
            str(g): (float(v[0]), float(v[1]), float(v[2]))
            for g, v in item.get("corpo", {}).items()
        }
        poses.append(
            PoseDanca(
                corpo=corpo,
                braco_dir=str(item.get("braco_dir", "idle")),
                braco_esq=str(item.get("braco_esq", "idle")),
            )
        )
    return PassoDanca(poses=tuple(poses))  # type: ignore[arg-type]


def frase_do_estilo(estilo: str) -> tuple[PassoDanca, ...]:
    """Frase (passos de uma batida) do ``estilo`` de dança."""
    danca = danca_ativa()
    if danca is _anim_padrao.DANCA and estilo in FRASES:
        return FRASES[estilo]
    frase_dict = danca.get("frases", {}).get(estilo)
    if not isinstance(frase_dict, dict):
        return FRASES.get(estilo, FRASES["street_groove"])
    return tuple(_passo_de_dict(p) for p in frase_dict.get("passos", ()))
