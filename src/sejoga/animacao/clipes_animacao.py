"""Clipes de locomoção autorais como DADOS, em DELTAS (graus) sobre o repouso.

Mesma filosofia de ``clipes_ocioso``: keyframes com easing quíntico (velocidade e
aceleração contínuas nos holds), nenhum clipe exportado de ferramenta externa.
O clipe é amostrado por ``delta_states.delta_walk`` com a fase de passada de
``LegMotion``; assim braços e pernas partilham um único relógio.

Convenção de eixos (a mesma de ``pose_repouso``): ``y`` = azimute (frente/trás),
``z`` = elevação (positivo BAIXA a mão), ``x`` = torção. No tempo normalizado
``t=0`` o braço direito está no ponto mais à frente e o esquerdo, no mais atrás;
em ``t=0.5`` invertem. Como o esquerdo é o espelho ``(x, -y, -z)`` do direito, os
deltas ``y`` e ``z`` dos dois braços são IGUAIS: o espelho e a contrafase se
cancelam. Só o cotovelo difere (o esquerdo flexiona com ``z`` negativo).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import tau

from sejoga.animacao import locomocao_tuning as loc
from sejoga.animacao.dados_autorais import locomocao_clips_ativos
from sejoga.animacao.interpolacao import Chaves, amostrar_pista
from sejoga.nucleo.esqueleto import Rotation3

#: Separador de rótulo numa chave de track: ``"head:quique"`` soma em ``head``.
_SEPARADOR_ROTULO = ":"
#: Meio e quarto de ciclo (tempos normalizados das keys).
_MEIO = 0.5
_QUARTO = 0.25
_TRES_QUARTOS = 0.75


@dataclass(frozen=True)
class ClipeAnim:
    """Clipe cíclico: duração e tracks grupo->keyframes (tempo, (x, y, z))."""

    duracao: float
    tracks: dict[str, Chaves]


def _ciclo(*keys: tuple[float, tuple[float, float, float]]) -> Chaves:
    """Garante que o ciclo feche no mesmo valor com que começou (sem salto)."""
    if keys[0][1] != keys[-1][1]:
        raise ValueError("clipe cíclico deve começar e terminar no mesmo valor")

    return keys


def _par(
    frente: tuple[float, float, float], tras: tuple[float, float, float]
) -> Chaves:
    """Ciclo de dois extremos: ``frente`` em t=0 e ``tras`` em t=0.5."""
    return _ciclo((0.0, frente), (_MEIO, tras), (1.0, frente))


def _clipe_passada(
    braco_y: float,
    braco_recuo: float,
    braco_z: float,
    cotovelo: float,
    giro: float,
    inclinacao: float,
    quique: float,
    contragiro: float,
    quique_quadril: float,
    roll_quadril: float,
    fones_atraso: float,
    antena_atraso: float,
) -> ClipeAnim:
    """Monta um ciclo de passada a partir das amplitudes de pico (graus)."""
    quique_chaves = _ciclo(
        (0.0, (quique, 0.0, 0.0)),
        (_QUARTO, (-quique, 0.0, 0.0)),
        (_MEIO, (quique, 0.0, 0.0)),
        (_TRES_QUARTOS, (-quique, 0.0, 0.0)),
        (1.0, (quique, 0.0, 0.0)),
    )
    quadril_chaves = _ciclo(
        (0.0, (quique_quadril, 0.0, 0.0)),
        (_QUARTO, (-quique_quadril, 0.0, roll_quadril)),
        (_MEIO, (quique_quadril, 0.0, 0.0)),
        (_TRES_QUARTOS, (-quique_quadril, 0.0, -roll_quadril)),
        (1.0, (quique_quadril, 0.0, 0.0)),
    )
    abdomen_atraso = _ciclo(
        (0.0, (0.0, 0.0, 0.0)),
        (_QUARTO, (0.0, giro * 0.10, -0.5)),
        (_MEIO, (0.0, 0.0, 0.0)),
        (_TRES_QUARTOS, (0.0, -giro * 0.10, 0.5)),
        (1.0, (0.0, 0.0, 0.0)),
    )
    peitoral_atraso = _ciclo(
        (0.0, (0.0, 0.0, 0.0)),
        (_QUARTO, (-quique_quadril * 0.45, giro * 0.18, -0.8)),
        (_MEIO, (0.0, 0.0, 0.0)),
        (_TRES_QUARTOS, (-quique_quadril * 0.45, -giro * 0.18, 0.8)),
        (1.0, (0.0, 0.0, 0.0)),
    )
    fones_chaves = _ciclo(
        (0.0, (-0.5 * fones_atraso, 0.0, 0.0)),
        (_QUARTO, (fones_atraso, 0.0, 0.35 * fones_atraso)),
        (_MEIO, (-0.5 * fones_atraso, 0.0, 0.0)),
        (_TRES_QUARTOS, (fones_atraso, 0.0, -0.35 * fones_atraso)),
        (1.0, (-0.5 * fones_atraso, 0.0, 0.0)),
    )
    antena_dir_chaves = _ciclo(
        (0.0, (-0.6 * antena_atraso, 0.0, 0.0)),
        (_QUARTO, (antena_atraso, 0.0, 0.45 * antena_atraso)),
        (_MEIO, (-0.6 * antena_atraso, 0.0, 0.0)),
        (_TRES_QUARTOS, (antena_atraso, 0.0, -0.45 * antena_atraso)),
        (1.0, (-0.6 * antena_atraso, 0.0, 0.0)),
    )
    antena_esq_chaves = _ciclo(
        (0.0, (-0.6 * antena_atraso, 0.0, 0.0)),
        (_QUARTO, (antena_atraso, 0.0, -0.45 * antena_atraso)),
        (_MEIO, (-0.6 * antena_atraso, 0.0, 0.0)),
        (_TRES_QUARTOS, (antena_atraso, 0.0, 0.45 * antena_atraso)),
        (1.0, (-0.6 * antena_atraso, 0.0, 0.0)),
    )
    ombro_x = 1.8 + 0.08 * cotovelo
    ombro_y = giro * 0.42
    ombro_z = 2.0 + braco_z * 0.25
    shoulder_dir_chaves = _ciclo(
        (0.0, (ombro_x * 0.35, ombro_y * 0.45, -ombro_z * 0.40)),
        (_QUARTO, (-ombro_x, -ombro_y, ombro_z)),
        (_MEIO, (-ombro_x * 0.35, -ombro_y * 0.45, ombro_z * 0.40)),
        (_TRES_QUARTOS, (ombro_x, ombro_y, -ombro_z)),
        (1.0, (ombro_x * 0.35, ombro_y * 0.45, -ombro_z * 0.40)),
    )
    shoulder_esq_chaves = _ciclo(
        (0.0, (-ombro_x * 0.35, ombro_y * 0.45, -ombro_z * 0.40)),
        (_QUARTO, (ombro_x, -ombro_y, ombro_z)),
        (_MEIO, (ombro_x * 0.35, -ombro_y * 0.45, ombro_z * 0.40)),
        (_TRES_QUARTOS, (-ombro_x, ombro_y, -ombro_z)),
        (1.0, (-ombro_x * 0.35, ombro_y * 0.45, -ombro_z * 0.40)),
    )
    punho_x = 4.0 + cotovelo * 0.14
    punho_y = braco_y * 0.22
    punho_z = braco_y * 0.25
    hand_dir_chaves = _ciclo(
        (0.0, (punho_x * 0.35, -punho_y * 0.35, -punho_z * 0.30)),
        (_QUARTO, (punho_x, -punho_y, punho_z)),
        (_MEIO, (-punho_x * 0.35, punho_y * 0.35, punho_z * 0.30)),
        (_TRES_QUARTOS, (-punho_x, punho_y, -punho_z)),
        (1.0, (punho_x * 0.35, -punho_y * 0.35, -punho_z * 0.30)),
    )
    hand_esq_chaves = _ciclo(
        (0.0, (-punho_x * 0.35, -punho_y * 0.35, -punho_z * 0.30)),
        (_QUARTO, (-punho_x, -punho_y, punho_z)),
        (_MEIO, (punho_x * 0.35, punho_y * 0.35, punho_z * 0.30)),
        (_TRES_QUARTOS, (punho_x, punho_y, -punho_z)),
        (1.0, (-punho_x * 0.35, -punho_y * 0.35, -punho_z * 0.30)),
    )

    return ClipeAnim(
        1.0,
        {
            # Braço à frente sobe (z negativo ergue); recuo equilibra o balanço frente/trás.
            "right-arm": _par(
                (0.0, braco_y - braco_recuo, -braco_z),
                (0.0, -braco_y - braco_recuo, braco_z),
            ),
            "left-arm": _par(
                (0.0, braco_y + braco_recuo, -braco_z),
                (0.0, -braco_y + braco_recuo, braco_z),
            ),
            "shoulder": shoulder_dir_chaves,
            "shoulder2": shoulder_esq_chaves,
            # Cotovelo flexiona mais com o braço à frente; nunca hiperestende.
            "ant-arm": _par((0.0, 0.0, cotovelo), (0.0, 0.0, 0.0)),
            "ant-arm2": _par((0.0, 0.0, 0.0), (0.0, 0.0, -cotovelo)),
            "hand": hand_dir_chaves,
            "hand2": hand_esq_chaves,
            # Quadril (Mixamo): contragiro na cintura + onda progressiva com sobreposição até o peitoral.
            "body": _par((inclinacao, giro, 0.0), (inclinacao, -giro, 0.0)),
            "body" + _SEPARADOR_ROTULO + "cadencia": quadril_chaves,
            "cintura": _par(
                (inclinacao * 0.2, -giro * 0.55, 1.8),
                (inclinacao * 0.2, giro * 0.55, -1.8),
            ),
            "abdomen": _par(
                (inclinacao * 0.3, giro * 0.35, -1.2),
                (inclinacao * 0.3, -giro * 0.35, 1.2),
            ),
            "abdomen" + _SEPARADOR_ROTULO + "atraso": abdomen_atraso,
            "peitoral": _par(
                (inclinacao * 0.5, giro * 0.55, -1.8),
                (inclinacao * 0.5, -giro * 0.55, 1.8),
            ),
            "peitoral" + _SEPARADOR_ROTULO + "atraso": peitoral_atraso,
            # Cabeça estabilizada + atraso secundário ZZZ em fones e antenas.
            "head": _par((0.0, -contragiro, 0.0), (0.0, contragiro, 0.0)),
            "head" + _SEPARADOR_ROTULO + "quique": quique_chaves,
            "fones": fones_chaves,
            "antena-direita": antena_dir_chaves,
            "antena-esquerda": antena_esq_chaves,
        },
    )


CLIPES = {
    "walk": _clipe_passada(
        loc.BRACO_AZIMUTE_CAMINHADA,
        loc.BRACO_RECUO_CAMINHADA,
        loc.BRACO_ELEVACAO_CAMINHADA,
        loc.COTOVELO_CAMINHADA,
        loc.TRONCO_GIRO_CAMINHADA,
        loc.TRONCO_INCLINACAO_CAMINHADA,
        loc.CABECA_QUIQUE_CAMINHADA,
        loc.CABECA_CONTRAGIRO_CAMINHADA,
        loc.QUADRIL_QUIQUE_CAMINHADA,
        loc.QUADRIL_ROLL_CAMINHADA,
        loc.FONES_ATRASO_CAMINHADA,
        loc.ANTENA_ATRASO_CAMINHADA,
    ),
    "run": _clipe_passada(
        loc.BRACO_AZIMUTE_CORRIDA,
        loc.BRACO_RECUO_CORRIDA,
        loc.BRACO_ELEVACAO_CORRIDA,
        loc.COTOVELO_CORRIDA,
        loc.TRONCO_GIRO_CORRIDA,
        loc.TRONCO_INCLINACAO_CORRIDA,
        loc.CABECA_QUIQUE_CORRIDA,
        loc.CABECA_CONTRAGIRO_CORRIDA,
        loc.QUADRIL_QUIQUE_CORRIDA,
        loc.QUADRIL_ROLL_CORRIDA,
        loc.FONES_ATRASO_CORRIDA,
        loc.ANTENA_ATRASO_CORRIDA,
    ),
}


def _acumular_tracks(
    pose: dict[str, tuple[float, float, float]],
    tracks: dict[str, Chaves],
    tempo: float,
    curvas_map: dict[str, object] | None = None,
    *,
    ignorar_grupos: set[str] | None = None,
) -> None:
    """Amostra e soma ``tracks`` por grupo base dentro de ``pose``."""
    curvas_dict = curvas_map or {}
    for chave, keys in tracks.items():
        grupo = chave.split(_SEPARADOR_ROTULO)[0]
        if ignorar_grupos is not None and grupo in ignorar_grupos:
            continue
        x, y, z = amostrar_pista(keys, tempo, curvas=curvas_dict.get(chave))
        ax, ay, az = pose.get(grupo, (0.0, 0.0, 0.0))
        pose[grupo] = (ax + x, ay + y, az + z)


def amostrar_clipe(nome: str, t: float) -> dict[str, tuple[float, float, float]]:
    """Amostra o delta do clipe cíclico no tempo normalizado ``t`` (ciclos)."""
    ativos = locomocao_clips_ativos()
    cfg = ativos.get(nome)
    clipe_padrao = CLIPES.get(nome)
    pose: dict[str, tuple[float, float, float]] = {}

    if cfg is None:
        clipe = CLIPES[nome]
        _acumular_tracks(pose, clipe.tracks, t % clipe.duracao)
        return pose

    dur = max(1e-6, float(cfg.get("duration", 1.0)))
    local = t % dur if cfg.get("loop", True) else max(0.0, min(dur, t))
    tracks = cfg["tracks"]
    if clipe_padrao is not None:
        grupos_cfg = {chave.split(_SEPARADOR_ROTULO)[0] for chave in tracks}
        t_norm = (local / dur) * clipe_padrao.duracao
        _acumular_tracks(pose, clipe_padrao.tracks, t_norm, ignorar_grupos=grupos_cfg)
    _acumular_tracks(pose, tracks, local, cfg.get("curvas"))
    return pose


def amostrar_clipe_rotacoes(nome: str, t: float) -> dict[str, Rotation3]:
    """Igual a :func:`amostrar_clipe`, porém devolvendo ``Rotation3`` em graus."""
    return {
        grupo: Rotation3(*valor) for grupo, valor in amostrar_clipe(nome, t).items()
    }


def ciclo_da_fase(fase: float) -> float:
    """Converte a fase de passada (rad, de ``LegMotion``) em tempo do clipe.

    O pico do clipe (t=0) coincide com ``sin(fase) = +1``, a perna esquerda à
    frente; ``SINAL_BRACO_COM_PERNA`` = -1 inverte a contrafase (meio ciclo).
    """
    inversao = loc.CICLO_MEIO * (1.0 - loc.SINAL_BRACO_COM_PERNA) / 2.0

    return fase / tau - loc.CICLO_DESLOCAMENTO_SENO + inversao
