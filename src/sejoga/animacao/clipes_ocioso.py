"""Clipes autorais de idle por personalidade: curvas ZZZ 3D em 10s sem saltos.

Cada personalidade combina base postural assimétrica (contrapposto), cascata
de coluna (`cintura -> abdomen -> peitoral -> body -> head -> fones/antenas`),
clavículas (`shoulder`/`shoulder2`), braços em arco e leitura clara das mãos e
dedos grandes (`hand`/`fingers`), com todos os 12 princípios da animação em 3D.
Python puro, sem engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin, tau

from sejoga.animacao.dados_autorais import idle_clips_ativos, respiracao_ativa
from sejoga.animacao.interpolacao import amostrar_pista
from sejoga.animacao.pose_repouso import REPOUSO

# Mantém o alias usado por ferramentas e testes existentes.
sample_track = amostrar_pista


@dataclass(frozen=True)
class IdleClip:
    """Clipe de idle autoral: pistas de keyframes por grupo do rig."""

    duration: float
    tracks: dict[str, tuple[tuple[float, tuple[float, float, float]], ...]]


# Compatibilidade das ferramentas públicas, sem uma segunda cópia das pistas.
from sejoga.animacao.animation import IDLE_CLIPS

CLIPS = {name: IdleClip(cfg["duration"], cfg["tracks"]) for name, cfg in IDLE_CLIPS.items()}
AJUSTE_BASE = {name: cfg["ajuste_base"] for name, cfg in IDLE_CLIPS.items()}
RESPIRACAO_GANHO_PEITO = 1.6
RESPIRACAO_GANHO_OMBRO = 0.5
RESPIRACAO_GANHO_CABECA = 0.4
RHYTHM_BRACO_DIR = 10
RHYTHM_BRACO_ESQ = 9
REPOUSO_BRACO_Z = REPOUSO.BRACO_Z
REPOUSO_BRACO_X = REPOUSO.BRACO_X
REPOUSO_BRACO_Y = REPOUSO.BRACO_Y
REPOUSO_ANTEBRACO_Z = REPOUSO.ANTEBRACO_Z
REPOUSO_ANTEBRACO_X = REPOUSO.ANTEBRACO_X


def camada_respiracao(
    respiracao: float,
    amplitude: float = 1.0,
    *,
    estilo: str | None = None,
) -> dict[str, tuple[float, float, float]]:
    """Camada aditiva de respiração em graus por parte do corpo."""
    resp = respiracao_ativa()
    partes = resp.get("contribuicao_partes", {})
    pesos = (
        resp.get("personalidades", {}).get(estilo, {}).get("pesos", {})
        if estilo
        else {}
    )
    escala = respiracao * amplitude
    peito = escala * float(partes.get("peito", RESPIRACAO_GANHO_PEITO)) * float(pesos.get("peito", 1.0))
    ombro = escala * float(partes.get("ombro", RESPIRACAO_GANHO_OMBRO)) * float(pesos.get("ombro", 1.0))
    cabeca = escala * float(partes.get("cabeca", RESPIRACAO_GANHO_CABECA)) * float(pesos.get("cabeca", 1.0))
    resultado: dict[str, tuple[float, float, float]] = {
        "body": (peito, 0.0, 0.0),
        "right-arm": (ombro, 0.0, 0.0),
        "left-arm": (ombro, 0.0, 0.0),
        "head": (cabeca, 0.0, 0.0),
    }
    abdomen = escala * float(partes.get("abdomen", 0.0)) * float(pesos.get("abdomen", 1.0))
    cintura = escala * float(partes.get("cintura", 0.0)) * float(pesos.get("cintura", 1.0))
    if abdomen:
        resultado["abdomen"] = (abdomen, 0.0, 0.0)
    if cintura:
        resultado["cintura"] = (cintura, 0.0, 0.0)
    return resultado


def _somar(
    pose: dict[str, tuple[float, float, float]],
    grupo: str,
    dx: float,
    dy: float,
    dz: float,
) -> None:
    bx, by, bz = pose.get(grupo, (0.0, 0.0, 0.0))
    pose[grupo] = (bx + dx, by + dy, bz + dz)


def _aplicar_camada_periodica(pose: dict[str, tuple[float, float, float]], style: str, time: float) -> None:
    """Micro-pulso contínuo 10s-periódico próprio dos perfis musicais e de combate."""
    if style == "rhythm":
        w = tau * time * 1.0  # 60 BPM / 120 BPM harmônico (fecha exato em 10.0 s)
        pulso = (1.0 - cos(w)) * 0.5
        groove = sin(w * 0.5)
        _somar(pose, "body", pulso * 2.2, groove * 2.6, sin(w * 0.25) * 2.0)
        _somar(pose, "head", -1.5 + (1.0 - cos(w - 0.35)) * 1.6, -groove * 2.2, groove * 1.6)
        _somar(pose, "right-arm", -2.5 + sin(w - 0.45) * 3.5, groove * 3.0, -pulso * (RHYTHM_BRACO_DIR * 0.6))
        _somar(pose, "left-arm", -1.5 - sin(w - 0.45) * 3.5, groove * 3.0, pulso * (RHYTHM_BRACO_ESQ * 0.6))
        _somar(pose, "ant-arm", -3.0, 0.0, pulso * 4.5)
        _somar(pose, "ant-arm2", -3.0, 0.0, -pulso * 4.5)
    elif style == "fighter":
        ginga = sin(tau * time * 0.3)  # 3 ciclos / 10 s
        guarda = sin(tau * time * 0.5) * 2.0
        _somar(pose, "body", 1.0 + ginga * 1.6, 2.0 + sin(tau * time * 0.2) * 2.4, ginga * 1.4)
        _somar(pose, "head", -ginga * 1.1, -2.5, -ginga * 0.9)
        _somar(pose, "right-arm", ginga * 2.4 + guarda, guarda * 0.4, -(ginga * ginga) * 2.2)
        _somar(pose, "left-arm", -ginga * 2.4 - guarda, -guarda * 0.4, (ginga * ginga) * 2.2)
        _somar(pose, "ant-arm", -2.0, 0.0, (0.5 + 0.5 * ginga) * 3.5)
        _somar(pose, "ant-arm2", -2.0, 0.0, -(0.5 - 0.5 * ginga) * 3.5)
        pose["legs"] = (sin(tau * time * 0.2) * 0.8, sin(tau * time * 0.2) * 1.5, 0.0)


def _resolver_cfg_idle(style: str, variante: str | None) -> dict[str, object]:
    cfg = idle_clips_ativos().get(style)
    if cfg is None:
        clip = CLIPS[style]
        return {
            "duration": clip.duration,
            "loop": True,
            "tracks": clip.tracks,
            "curvas": {},
            "ajuste_base": AJUSTE_BASE.get(style, {}),
            "deslocamento_corpo": (0.0, 0.0, 0.0),
        }
    if variante:
        var = cfg.get("variantes", {}).get(variante)
        if isinstance(var, dict):
            combinado = dict(cfg)
            combinado.update(var)
            return combinado
    return cfg


def deslocamento_idle_ativo(
    style: str,
    variante: str | None = None,
) -> tuple[float, float, float]:
    """Deslocamento autoral do corpo (px, py, pz) para o idle ativo."""
    cfg = _resolver_cfg_idle(style, variante)
    bruto = cfg.get("deslocamento_corpo", (0.0, 0.0, 0.0))
    if isinstance(bruto, (tuple, list)) and len(bruto) == 3:
        return (float(bruto[0]), float(bruto[1]), float(bruto[2]))
    return (0.0, 0.0, 0.0)


def sample_idle(
    style: str,
    time: float,
    respiracao: float = 0.0,
    amplitude_respiracao: float = 1.0,
    *,
    variante: str | None = None,
) -> dict[str, tuple[float, float, float]]:
    """Amostra o idle da personalidade no tempo ``time``, com arcos ZZZ e respiração."""
    cfg = _resolver_cfg_idle(style, variante)
    dur = max(1e-6, float(cfg.get("duration", 10.0)))  # type: ignore[arg-type]
    local = time % dur if cfg.get("loop", True) else max(0.0, min(dur, time))
    pose = {
        **{group: (0., 0., 0.) for group in camada_respiracao(1., 1.)},
        "right-arm": (REPOUSO_BRACO_X, REPOUSO_BRACO_Y, REPOUSO_BRACO_Z),
        "left-arm": (REPOUSO_BRACO_X, -REPOUSO_BRACO_Y, -REPOUSO_BRACO_Z),
        "ant-arm": (REPOUSO_ANTEBRACO_X, 0.0, REPOUSO_ANTEBRACO_Z),
        "ant-arm2": (REPOUSO_ANTEBRACO_X, 0.0, -REPOUSO_ANTEBRACO_Z),
    }
    if style in ("rhythm", "vibing"):
        _aplicar_camada_periodica(pose, "rhythm", time)

    ajuste: dict[str, tuple[float, float, float]] = cfg.get("ajuste_base", {})  # type: ignore[assignment]
    for group, extra in ajuste.items():
        _somar(pose, group, *extra)
    tracks: dict[str, tuple[tuple[float, tuple[float, float, float]], ...]] = cfg.get("tracks", {})  # type: ignore[assignment]
    curvas_map: dict[str, tuple[str, ...]] = cfg.get("curvas", {})  # type: ignore[assignment]
    for group, keys in tracks.items():
        _somar(pose, group, *amostrar_pista(keys, local, curvas=curvas_map.get(group)))
    if respiracao:
        for group, (ex, ey, ez) in camada_respiracao(
            respiracao, amplitude_respiracao, estilo=style
        ).items():
            _somar(pose, group, ex, ey, ez)
    return pose
