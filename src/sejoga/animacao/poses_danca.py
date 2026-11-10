"""Passos de dança em quatro poses (acento, sustentação, recuperação, preparação).

Cada passo dura uma batida. O acento cai no onset (u = 0); a sustentação, a
recuperação e a preparação seguem até a batida seguinte, de modo que o passo
termina na pose de acento do próximo. Cabeça e tronco são deltas em graus sobre
o repouso (zero); os braços são alvos de mão de ``alvos_bracos`` resolvidos pela
IK (``animacao.braco_hpr.braco_hpr_graus``). Python puro, sem engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sejoga.animacao import danca_tuning as tune
from sejoga.animacao.braco_hpr import braco_hpr_graus
from sejoga.animacao.clipes_ocioso import sample_track

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

    #: Graus por grupo (``head``/``body`` em delta; ``hand`` etc. absolutos).
    corpo: dict[str, Trio] = field(default_factory=dict)
    #: Nome do alvo de mão (``arm_targets.ALVOS``) do braço direito.
    braco_dir: str = "idle"
    #: Nome do alvo de mão do braço esquerdo (espelhado pela IK).
    braco_esq: str = "idle"


@dataclass(frozen=True)
class PassoDanca:
    """Um passo de uma batida com as quatro poses, na ordem de ``U_POSES``."""

    poses: tuple[PoseDanca, PoseDanca, PoseDanca, PoseDanca]


def _trio_do_grupo(pose: PoseDanca, grupo: str) -> Trio:
    """Graus (x, y, z) do ``grupo`` na ``pose``."""
    for lado, par in GRUPOS_BRACO.items():
        if grupo in par:
            nome = pose.braco_dir if lado == "right" else pose.braco_esq

            return braco_hpr_graus(lado, nome)[grupo]

    return pose.corpo.get(grupo, _ZERO)


def _grupos_das_poses(poses: list[PoseDanca]) -> set[str]:
    """Grupos escritos por ao menos uma das ``poses`` (braços sempre entram)."""
    grupos = set(_TODOS_GRUPOS_BRACO)

    for pose in poses:
        grupos.update(pose.corpo)

    return grupos


def amostrar_passo(
    passo: PassoDanca,
    u: float,
    proximo: PassoDanca | None = None,
    ganho: float = 1.0,
) -> dict[str, Trio]:
    """Pose (graus) do ``passo`` na fração ``u`` (0..1) da batida.

    O último trecho vai até o acento do ``proximo`` (ou do próprio passo, que
    fecha o laço). ``ganho`` escala só cabeça/tronco; braços e mãos vão ao declarado.
    """
    destino = (proximo or passo).poses[0]
    chaves = [*zip(tune.U_POSES, passo.poses, strict=True), (1.0, destino)]
    saida: dict[str, Trio] = {}

    for grupo in _grupos_das_poses([pose for _, pose in chaves]):
        faixa = tuple((quando, _trio_do_grupo(pose, grupo)) for quando, pose in chaves)
        trio = sample_track(faixa, u)
        saida[grupo] = (
            tuple(v * ganho for v in trio) if grupo in GRUPOS_COM_GANHO else trio
        )

    return saida
