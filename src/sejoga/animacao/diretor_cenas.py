"""Diretor declarativo de cenas e atuação procedimental do Mário (Python puro).

Substitui pistas travadas por roteiros declarativos ``RoteiroCena`` com:
- Splines Catmull-Rom C1 contínuas + curvas ``snap_out``, ``anticipate`` e ``overshoot``;
- Sobreposição temporal real (cascata coluna -> cabeça -> ombros -> mãos -> antenas);
- Holds vivos com micro-movimento assimétrico para poses nunca congelarem;
- Auxiliar IK 3D (``pose_braco_ik``) sobre ``ik_bracos.braco_para``.

FRONTEIRA: módulo 100% puro, sem importações de Panda3D, Qt ou Win32.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from itertools import pairwise
from math import degrees, pi, radians, sin

from sejoga.animacao import ik_bracos
from sejoga.animacao.braco_hpr import _modelo_ik
from sejoga.animacao.braco_tuning import POLO_COTOVELO_ANATOMICO
from sejoga.animacao.cenas_idle import AmostraCenaIdle
from sejoga.animacao.estados_delta import delta_absoluto_para_repouso
from sejoga.animacao.gestos_dedos import CURL_NEUTRO
from sejoga.animacao.interpolacao import amostrar_pista_continua, suavizar_quintico
from sejoga.nucleo.esqueleto import Rotation3

Vec3 = tuple[float, float, float]
Dedos5 = tuple[float, float, float, float, float]
DedosCena = tuple[Dedos5, Dedos5]

_DEDOS_NEUTROS: Dedos5 = (CURL_NEUTRO,) * 5
_DEDOS_FECHADOS: Dedos5 = (0.76, 0.84, 0.90, 0.92, 0.94)
_DEDOS_ABERTOS: Dedos5 = (0.04, 0.04, 0.06, 0.08, 0.10)

_ATRASO_CASCATA: dict[str, float] = {
    "head": 0.055,
    "fones": 0.070,
    "shoulder": 0.040,
    "shoulder2": 0.040,
    "right-arm": 0.075,
    "left-arm": 0.075,
    "ant-arm": 0.105,
    "ant-arm2": 0.105,
    "hand": 0.130,
    "hand2": 0.130,
    "fingers": 0.145,
    "fingers2": 0.145,
    "antena-direita": 0.145,
    "antena-esquerda": 0.145,
}

_GRUPOS_ABS_PADRAO = frozenset({"right-arm", "left-arm", "ant-arm", "ant-arm2"})


@dataclass(frozen=True, slots=True)
class EventoVfxCena:
    """Marco sincronizado de VFX durante uma cena dirigida."""

    tempo: float
    evento: str
    ancora: str = "cabeca_topo"
    dir_x: float = 1.0
    forca: float = 1.0


@dataclass(frozen=True, slots=True)
class PoseChave:
    """Keyframe em graus locais por grupo com curva de entrada e extras."""

    tempo: float
    grupos: dict[str, Vec3]
    curva: str = "catmull"
    deslocamento_z: float = 0.0
    pernas: tuple[float, ...] | None = None
    dedos: DedosCena | None = None


@dataclass(frozen=True, slots=True)
class RoteiroCena:
    """Roteiro completo e autoral de uma cena procedural."""

    nome: str
    duracao: float
    chaves: tuple[PoseChave, ...]
    eventos_vfx: tuple[EventoVfxCena, ...] = ()
    permite_sentado: bool = False
    trava_maos: bool = False
    trava_pernas: bool = False
    atraso_cascata: bool = True
    grupos_absolutos: frozenset[str] = _GRUPOS_ABS_PADRAO
    blend_entrada_s: float = 0.24
    blend_saida_s: float = 0.34
    peso_vida: float = 1.0


@cache
def _ik_braco_graus(lado: str, alvo: Vec3, polo: Vec3) -> tuple[Vec3, Vec3]:
    res = ik_bracos.braco_para(_modelo_ik(), lado, alvo, polo)
    arm_key = "right-arm" if lado == "right" else "left-arm"
    ant_key = "ant-arm" if lado == "right" else "ant-arm2"
    ra, rf = res[arm_key], res[ant_key]
    return (
        (degrees(ra.x), degrees(ra.y), degrees(ra.z)),
        (degrees(rf.x), degrees(rf.y), degrees(rf.z)),
    )


def pose_braco_ik(
    lado: str,
    alvo_xyz: Vec3,
    polo_xyz: Vec3 = POLO_COTOVELO_ANATOMICO,
) -> dict[str, Vec3]:
    """Resolve ombro+cotovelo pelo IK 3D analítico já convertido em graus."""
    arm_k = "right-arm" if lado == "right" else "left-arm"
    ant_k = "ant-arm" if lado == "right" else "ant-arm2"
    arm_g, ant_g = _ik_braco_graus(lado, alvo_xyz, polo_xyz)
    return {arm_k: arm_g, ant_k: ant_g}


def _pista_de_grupo(
    chaves: tuple[PoseChave, ...], grupo: str
) -> tuple[tuple[tuple[float, Vec3], ...], tuple[str, ...]]:
    pontos: list[tuple[float, Vec3]] = []
    curvas: list[str] = []
    for idx, ch in enumerate(chaves):
        if grupo not in ch.grupos:
            continue
        pontos.append((ch.tempo, ch.grupos[grupo]))
        if idx + 1 < len(chaves):
            curvas.append(chaves[idx + 1].curva)
    return tuple(pontos), tuple(curvas)


def _compilar_pistas(roteiro: RoteiroCena) -> tuple[dict[str, tuple[tuple[float, Vec3], ...]], dict[str, tuple[str, ...]]]:
    nomes_grupos: set[str] = set()
    for chave in roteiro.chaves:
        nomes_grupos.update(chave.grupos.keys())
    pistas: dict[str, tuple[tuple[float, Vec3], ...]] = {}
    curvas_map: dict[str, tuple[str, ...]] = {}
    for grupo in nomes_grupos:
        pts, curvs = _pista_de_grupo(roteiro.chaves, grupo)
        if pts:
            pistas[grupo] = pts
            curvas_map[grupo] = curvs
    return pistas, curvas_map


@cache
def _pistas_cacheadas(roteiro_id: str) -> tuple[dict[str, tuple[tuple[float, Vec3], ...]], dict[str, tuple[str, ...]]]:
    return _compilar_pistas(ROTEIROS_CENAS[roteiro_id])


def _aplicar_micro_vida(delta: dict[str, Rotation3], t: float, peso: float) -> None:
    if peso <= 0.01:
        return
    pulso_a = sin(t * 2.17)
    pulso_b = sin(t * 3.41 + 0.9)
    for g, ax, ay in (("head", 1.3, 1.8), ("antena-direita", 3.2, -2.0), ("antena-esquerda", -3.0, 2.2)):
        if g in delta:
            cur = delta[g]
            delta[g] = Rotation3(
                cur.x + radians(ax * pulso_a * peso),
                cur.y + radians(ay * pulso_b * peso),
                cur.z,
            )


def _amostrar_pernas_chaves(chaves_p: list[tuple[float, tuple[float, ...]]], t: float) -> tuple[float, ...] | None:
    if not chaves_p:
        return None
    if t <= chaves_p[0][0]:
        return chaves_p[0][1]
    if t >= chaves_p[-1][0]:
        return chaves_p[-1][1]
    for (t0, v0), (t1, v1) in pairwise(chaves_p):
        if t <= t1:
            f = suavizar_quintico((t - t0) / max(1e-6, t1 - t0))
            return tuple(a + (b - a) * f for a, b in zip(v0, v1, strict=True))
    return chaves_p[-1][1]


def _amostrar_dedos_chaves(chaves_d: list[tuple[float, DedosCena]], t: float) -> DedosCena | None:
    if not chaves_d:
        return None
    if t <= chaves_d[0][0]:
        return chaves_d[0][1]
    if t >= chaves_d[-1][0]:
        return chaves_d[-1][1]
    for (t0, d0), (t1, d1) in pairwise(chaves_d):
        if t <= t1:
            f = suavizar_quintico((t - t0) / max(1e-6, t1 - t0))
            r = tuple(a + (b - a) * f for a, b in zip(d0[0], d1[0], strict=True))
            e = tuple(a + (b - a) * f for a, b in zip(d0[1], d1[1], strict=True))
            return (r, e)  # type: ignore[return-value]
    return chaves_d[-1][1]


def _amostrar_escalares_extras(roteiro: RoteiroCena, t: float) -> tuple[float, tuple[float, ...] | None, DedosCena | None]:
    pista_z = tuple((ch.tempo, (ch.deslocamento_z, 0.0, 0.0)) for ch in roteiro.chaves)
    dz = amostrar_pista_continua(pista_z, t, padrao="catmull")[0]
    chaves_p = [(ch.tempo, ch.pernas) for ch in roteiro.chaves if ch.pernas is not None]
    chaves_d = [(ch.tempo, ch.dedos) for ch in roteiro.chaves if ch.dedos is not None]
    return dz, _amostrar_pernas_chaves(chaves_p, t), _amostrar_dedos_chaves(chaves_d, t)


def amostrar_roteiro(roteiro: RoteiroCena, tempo: float, variante: int = 0) -> AmostraCenaIdle:
    """Amostra ``RoteiroCena`` em ``tempo`` com cascata real de sobreposição e holds vivos."""
    del variante
    if roteiro.duracao <= 0.0 or tempo < 0.0 or tempo >= roteiro.duracao:
        return AmostraCenaIdle()
    t = max(0.0, min(roteiro.duracao, tempo))
    w_in = suavizar_quintico(t / max(1e-3, roteiro.blend_entrada_s))
    w_out = suavizar_quintico((roteiro.duracao - t) / max(1e-3, roteiro.blend_saida_s))
    peso = max(0.0, min(1.0, min(w_in, w_out)))
    if roteiro.nome in ROTEIROS_CENAS:
        pistas, curvas_map = _pistas_cacheadas(roteiro.nome)
    else:
        pistas, curvas_map = _compilar_pistas(roteiro)
    delta: dict[str, Rotation3] = {}
    for grupo, pts in pistas.items():
        atraso = _ATRASO_CASCATA.get(grupo, 0.0) if roteiro.atraso_cascata else 0.0
        tg = max(0.0, min(roteiro.duracao, t - atraso))
        gx, gy, gz = amostrar_pista_continua(pts, tg, curvas=curvas_map.get(grupo), padrao="catmull")
        if grupo in roteiro.grupos_absolutos:
            delta[grupo] = delta_absoluto_para_repouso(grupo, gx, gy, gz)
        else:
            delta[grupo] = Rotation3(radians(gx), radians(gy), radians(gz))
    _aplicar_micro_vida(delta, t, roteiro.peso_vida * sin(min(1.0, t / roteiro.duracao) * pi))
    dz, pernas, dedos = _amostrar_escalares_extras(roteiro, t)
    return AmostraCenaIdle(
        ativa=True,
        nome=roteiro.nome,
        delta_rig=delta,
        peso_mistura=peso,
        pernas_graus=pernas,
        deslocamento_z=dz,
        dedos=dedos,
    )


def _construir_roteiros_autorais() -> dict[str, RoteiroCena]:
    braco_r_alto = pose_braco_ik("right", (0.19, 0.16, 0.12))
    braco_l_alto = pose_braco_ik("left", (-0.19, 0.16, 0.12))
    braco_r_peito = pose_braco_ik("right", (0.10, -0.02, 0.21))
    braco_r_polir_a = pose_braco_ik("right", (0.04, 0.06, 0.22))
    braco_r_polir_b = pose_braco_ik("right", (0.12, -0.04, 0.21))
    braco_r_fone = pose_braco_ik("right", (0.19, 0.15, 0.10))
    braco_l_fone = pose_braco_ik("left", (-0.19, 0.15, 0.10))
    braco_r_solto = pose_braco_ik("right", (0.16, -0.19, 0.07))
    braco_l_solto = pose_braco_ik("left", (-0.16, -0.19, 0.07))
    r_espirro = RoteiroCena(
        nome="espirro",
        duracao=3.20,
        trava_maos=True,
        permite_sentado=True,
        chaves=(
            PoseChave(0.0, {"body": (0, 0, 0), "head": (0, 0, 0), "door": (0, 0, 0), **braco_r_solto, **braco_l_solto}),
            PoseChave(0.55, {"body": (6, 0, -2), "head": (11, -4, -3), "door": (0, 2, 0), **braco_r_peito, **braco_l_solto}, curva="anticipate", deslocamento_z=0.02),
            PoseChave(0.95, {"body": (11, 0, 2), "head": (19, 5, 3), "door": (0, 5, 0), **braco_r_peito, **braco_l_solto}, curva="overshoot", deslocamento_z=0.04),
            PoseChave(1.18, {"body": (-14, 0, 0), "head": (-26, 0, 0), "door": (0, 42, 0), "antena-direita": (-22, 0, -10), "antena-esquerda": (-22, 0, 10), **braco_r_alto, **braco_l_alto}, curva="snap_out", deslocamento_z=-0.09, dedos=(_DEDOS_ABERTOS, _DEDOS_ABERTOS)),
            PoseChave(1.68, {"body": (-6, 4, 2), "head": (-10, 7, 3), "door": (0, 8, 0), "antena-direita": (8, 0, -4), "antena-esquerda": (8, 0, 4), **braco_r_peito, **braco_l_solto}, curva="overshoot", deslocamento_z=-0.03),
            PoseChave(3.20, {"body": (0, 0, 0), "head": (0, 0, 0), "door": (0, 0, 0), "antena-direita": (0, 0, 0), "antena-esquerda": (0, 0, 0), **braco_r_solto, **braco_l_solto}),
        ),
        eventos_vfx=(
            EventoVfxCena(1.14, "espirro", "porta", 1.0, 1.12),
            EventoVfxCena(2.05, "suspiro", "visor_lado", 1.0, 0.88),
        ),
    )
    r_suspiro = RoteiroCena(
        nome="suspiro_pesado",
        duracao=3.00,
        permite_sentado=True,
        trava_maos=True,
        chaves=(
            PoseChave(0.0, {"body": (0, 0, 0), "head": (0, 0, 0), **braco_r_solto, **braco_l_solto}),
            PoseChave(0.65, {"body": (5, 0, 0), "head": (8, 0, 0), "antena-direita": (6, 0, -4), "antena-esquerda": (6, 0, 4), **braco_r_solto, **braco_l_solto}, curva="ease_in_out", deslocamento_z=0.03),
            PoseChave(1.35, {"body": (-11, 2, -2), "head": (-18, -3, -3), "antena-direita": (-14, 0, -18), "antena-esquerda": (-14, 0, 18), "door": (0, 4, 0), **braco_r_solto, **braco_l_solto}, curva="snap_out", deslocamento_z=-0.06),
            PoseChave(2.25, {"body": (-9, 1, -2), "head": (-15, -2, -2), "antena-direita": (-12, 0, -15), "antena-esquerda": (-12, 0, 15), **braco_r_solto, **braco_l_solto}, deslocamento_z=-0.04),
            PoseChave(3.00, {"body": (0, 0, 0), "head": (0, 0, 0), "antena-direita": (0, 0, 0), "antena-esquerda": (0, 0, 0), **braco_r_solto, **braco_l_solto}),
        ),
        eventos_vfx=(
            EventoVfxCena(1.05, "suspiro", "visor_lado", 1.0, 0.96),
            EventoVfxCena(1.62, "tristeza", "cabeca_topo", 1.0, 0.90),
        ),
    )
    r_espreguicar = RoteiroCena(
        nome="espreguicar",
        duracao=3.40,
        trava_maos=True,
        chaves=(
            PoseChave(0.0, {"body": (0, 0, 0), "head": (0, 0, 0), **braco_r_solto, **braco_l_solto}),
            PoseChave(0.38, {"body": (-7, 0, 0), "head": (-8, 0, 0), **braco_r_peito, **braco_l_solto}, curva="anticipate", deslocamento_z=-0.06),
            PoseChave(1.10, {"body": (11, 0, 3), "head": (15, -6, 3), "antena-direita": (12, 0, -8), "antena-esquerda": (12, 0, 8), **braco_r_alto, **braco_l_alto}, curva="overshoot", deslocamento_z=0.06, dedos=(_DEDOS_ABERTOS, _DEDOS_ABERTOS)),
            PoseChave(2.05, {"body": (8, 0, -4), "head": (10, 8, -3), **braco_r_alto, **braco_l_alto}, deslocamento_z=0.04),
            PoseChave(3.40, {"body": (0, 0, 0), "head": (0, 0, 0), "antena-direita": (0, 0, 0), "antena-esquerda": (0, 0, 0), **braco_r_solto, **braco_l_solto}),
        ),
        eventos_vfx=(EventoVfxCena(1.85, "suspiro", "visor_lado", 1.0, 0.92),),
    )
    r_polir = RoteiroCena(
        nome="polir_gabinete",
        duracao=3.40,
        permite_sentado=True,
        trava_maos=True,
        chaves=(
            PoseChave(0.0, {"body": (0, 0, 0), "head": (0, 0, 0), **braco_r_solto, **braco_l_solto}),
            PoseChave(0.55, {"body": (-4, -6, 0), "head": (-10, 10, -4), **braco_r_polir_a, **braco_l_solto}, curva="snap_out", dedos=(_DEDOS_ABERTOS, _DEDOS_NEUTROS)),
            PoseChave(1.05, {"body": (-5, -8, 2), "head": (-12, 12, -3), **braco_r_polir_b, **braco_l_solto}),
            PoseChave(1.55, {"body": (-4, -5, -2), "head": (-10, 8, -4), **braco_r_polir_a, **braco_l_solto}),
            PoseChave(2.15, {"body": (4, 8, 2), "head": (5, -8, 5), **braco_r_solto, **braco_l_solto}, curva="overshoot"),
            PoseChave(3.40, {"body": (0, 0, 0), "head": (0, 0, 0), **braco_r_solto, **braco_l_solto}),
        ),
        eventos_vfx=(EventoVfxCena(1.65, "brilho_estilo", "cabeca_topo", 1.0, 0.95),),
    )
    r_fones = RoteiroCena(
        nome="ajustar_fones",
        duracao=2.90,
        permite_sentado=True,
        trava_maos=True,
        chaves=(
            PoseChave(0.0, {"head": (0, 0, 0), **braco_r_solto, **braco_l_solto}),
            PoseChave(0.65, {"head": (4, -14, -7), "fones": (0, 0, -6), **braco_r_fone, **braco_l_solto}, curva="snap_out", dedos=(_DEDOS_FECHADOS, _DEDOS_NEUTROS)),
            PoseChave(1.25, {"head": (3, 14, 7), "fones": (0, 0, 6), **braco_r_solto, **braco_l_fone}, curva="overshoot", dedos=(_DEDOS_NEUTROS, _DEDOS_FECHADOS)),
            PoseChave(1.90, {"head": (2, 0, 0), "fones": (0, 0, 0), **braco_r_fone, **braco_l_fone}, curva="ease_in_out"),
            PoseChave(2.90, {"head": (0, 0, 0), **braco_r_solto, **braco_l_solto}),
        ),
        eventos_vfx=(
            EventoVfxCena(0.68, "estalo_fone", "fone_dir", 1.0, 0.94),
            EventoVfxCena(1.30, "estalo_fone", "fone_esq", -1.0, 0.94),
        ),
    )
    return {r.nome: r for r in (r_espirro, r_suspiro, r_espreguicar, r_polir, r_fones)}


ROTEIROS_CENAS: dict[str, RoteiroCena] = _construir_roteiros_autorais()

_METADADOS_LEGADO: dict[str, dict[str, bool]] = {
    "espreguicar": {"permite_sentado": False, "trava_maos": True, "trava_pernas": False},
    "bater_pe_impaciente": {"permite_sentado": True, "trava_maos": True, "trava_pernas": True},
    "bater_pe_ritmo": {"permite_sentado": True, "trava_maos": True, "trava_pernas": True},
    "groove_um_pe": {"permite_sentado": False, "trava_maos": True, "trava_pernas": True},
    "solo_guitarra_ar": {"permite_sentado": False, "trava_maos": True, "trava_pernas": True},
    "finger_guns_camera": {"permite_sentado": True, "trava_maos": True, "trava_pernas": False},
    "tentaculo_fujao": {"permite_sentado": True, "trava_maos": True, "trava_pernas": False},
    "cacar_cursor_sucesso": {"permite_sentado": True, "trava_maos": True, "trava_pernas": True},
    "cacar_cursor_falha": {"permite_sentado": True, "trava_maos": True, "trava_pernas": True},
    "roubo_cursor_tentaculo": {"permite_sentado": True, "trava_maos": True, "trava_pernas": False},
    "cuspir_item": {"permite_sentado": True, "trava_maos": True, "trava_pernas": False},
    "bocejar_longo": {"permite_sentado": True, "trava_maos": True, "trava_pernas": False},
    "escutar_fone": {"permite_sentado": True, "trava_maos": True, "trava_pernas": False},
    "cochilo_em_pe": {"permite_sentado": False, "trava_maos": True, "trava_pernas": False},
    "balanco_relaxado": {"permite_sentado": True, "trava_maos": False, "trava_pernas": False},
    "arrumar_antena": {"permite_sentado": True, "trava_maos": True, "trava_pernas": False},
    "olhar_pes": {"permite_sentado": False, "trava_maos": False, "trava_pernas": False},
    "conferir_luva": {"permite_sentado": True, "trava_maos": True, "trava_pernas": False},
    "pensar_gabinete": {"permite_sentado": True, "trava_maos": True, "trava_pernas": False},
    "olhar_curioso_chao": {"permite_sentado": True, "trava_maos": False, "trava_pernas": False},
    "checar_walkman": {"permite_sentado": True, "trava_maos": True, "trava_pernas": False},
    "argolas_antena": {"permite_sentado": True, "trava_maos": False, "trava_pernas": False},
    "respiracao_profunda": {"permite_sentado": True, "trava_maos": False, "trava_pernas": False},
}


def registrar_roteiro(roteiro: RoteiroCena) -> None:
    """Registra ou substitui dinamicamente um ``RoteiroCena`` no catálogo ativo."""
    ROTEIROS_CENAS[roteiro.nome] = roteiro


def obter_roteiro(nome: str) -> RoteiroCena | None:
    """Retorna o ``RoteiroCena`` associado ao nome, caso exista."""
    return ROTEIROS_CENAS.get(nome)


def metadados_cena(nome: str) -> dict[str, bool]:
    """Devolve flags de atuação (``permite_sentado``, ``trava_maos``, ``trava_pernas``)."""
    roteiro = ROTEIROS_CENAS.get(nome)
    if roteiro is not None:
        return {
            "permite_sentado": roteiro.permite_sentado,
            "trava_maos": roteiro.trava_maos,
            "trava_pernas": roteiro.trava_pernas,
        }
    return dict(
        _METADADOS_LEGADO.get(
            nome,
            {"permite_sentado": True, "trava_maos": True, "trava_pernas": False},
        )
    )


def eventos_vfx_cena(nome: str) -> tuple[tuple[float, str, str, float, float], ...]:
    """Retorna a lista de cues VFX para ``nome`` no formato esperado por ``efeitos_street``."""
    roteiro = ROTEIROS_CENAS.get(nome)
    if roteiro is None or not roteiro.eventos_vfx:
        return ()
    return tuple(
        (ev.tempo, ev.evento, ev.ancora, ev.dir_x, ev.forca)
        for ev in roteiro.eventos_vfx
    )
