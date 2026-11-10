"""Clipes de locomoção autorais como DADOS, em DELTAS (graus) sobre o repouso.

Mesma filosofia de ``idle_clips``: keyframes com easing quíntico (velocidade e
aceleração contínuas nos holds), nenhum clipe exportado de ferramenta externa.
O clipe é amostrado por ``delta_states.delta_walk`` com a fase de passada de
``LegMotion``; assim braços e pernas partilham um único relógio.

Convenção de eixos (a mesma de ``rig_base``): ``y`` = azimute (frente/trás),
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
from sejoga.animacao.idle_clips import sample_track
from sejoga.nucleo.rig import Rotation3

#: Separador de rótulo numa chave de track: ``"head:quique"`` soma em ``head``.
_SEPARADOR_ROTULO = ":"
#: Meio e quarto de ciclo (tempos normalizados das keys).
_MEIO = 0.5
_QUARTO = 0.25
_TRES_QUARTOS = 0.75

Chaves = tuple[tuple[float, tuple[float, float, float]], ...]


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


def _par(frente: tuple[float, float, float], tras: tuple[float, float, float]) -> Chaves:
    """Ciclo de dois extremos: ``frente`` em t=0 e ``tras`` em t=0.5."""
    return _ciclo((0.0, frente), (_MEIO, tras), (1.0, frente))


def _clipe_passada(
    braco_y: float,
    braco_z: float,
    cotovelo: float,
    giro: float,
    inclinacao: float,
    quique: float,
    contragiro: float,
) -> ClipeAnim:
    """Monta um ciclo de passada a partir das amplitudes de pico (graus)."""
    quique_chaves = _ciclo(
        (0.0, (quique, 0.0, 0.0)),
        (_QUARTO, (-quique, 0.0, 0.0)),
        (_MEIO, (quique, 0.0, 0.0)),
        (_TRES_QUARTOS, (-quique, 0.0, 0.0)),
        (1.0, (quique, 0.0, 0.0)),
    )

    return ClipeAnim(1.0, {
        # Braço à frente sobe (z negativo ergue); ao voltar, desce.
        "right-arm": _par((0.0, braco_y, -braco_z), (0.0, -braco_y, braco_z)),
        "left-arm": _par((0.0, braco_y, -braco_z), (0.0, -braco_y, braco_z)),
        # Cotovelo flexiona mais com o braço à frente; nunca hiperestende.
        "ant-arm": _par((0.0, 0.0, cotovelo), (0.0, 0.0, 0.0)),
        "ant-arm2": _par((0.0, 0.0, 0.0), (0.0, 0.0, -cotovelo)),
        # Tronco gira com o ombro que avança e inclina (corrida).
        "body": _par((inclinacao, giro, 0.0), (inclinacao, -giro, 0.0)),
        # Cabeça: contra-giro suave + quique a cada apoio (duas vezes por ciclo).
        "head": _par((0.0, -contragiro, 0.0), (0.0, contragiro, 0.0)),
        "head" + _SEPARADOR_ROTULO + "quique": quique_chaves,
    })


CLIPES = {
    "walk": _clipe_passada(
        loc.BRACO_AZIMUTE_CAMINHADA, loc.BRACO_ELEVACAO_CAMINHADA,
        loc.COTOVELO_CAMINHADA, loc.TRONCO_GIRO_CAMINHADA,
        loc.TRONCO_INCLINACAO_CAMINHADA, loc.CABECA_QUIQUE_CAMINHADA,
        loc.CABECA_CONTRAGIRO_CAMINHADA,
    ),
    "run": _clipe_passada(
        loc.BRACO_AZIMUTE_CORRIDA, loc.BRACO_ELEVACAO_CORRIDA,
        loc.COTOVELO_CORRIDA, loc.TRONCO_GIRO_CORRIDA,
        loc.TRONCO_INCLINACAO_CORRIDA, loc.CABECA_QUIQUE_CORRIDA,
        loc.CABECA_CONTRAGIRO_CORRIDA,
    ),
}


def amostrar_clipe(nome: str, t: float) -> dict[str, tuple[float, float, float]]:
    """Amostra o delta do clipe cíclico no tempo normalizado ``t`` (ciclos)."""
    clipe = CLIPES[nome]
    local = t % clipe.duracao
    pose: dict[str, tuple[float, float, float]] = {}

    for chave, keys in clipe.tracks.items():
        grupo = chave.split(_SEPARADOR_ROTULO)[0]
        x, y, z = sample_track(keys, local)
        ax, ay, az = pose.get(grupo, (0.0, 0.0, 0.0))
        pose[grupo] = (ax + x, ay + y, az + z)

    return pose


def amostrar_clipe_rotacoes(nome: str, t: float) -> dict[str, Rotation3]:
    """Igual a :func:`amostrar_clipe`, porém devolvendo ``Rotation3`` em graus."""
    return {grupo: Rotation3(*valor) for grupo, valor in amostrar_clipe(nome, t).items()}


def ciclo_da_fase(fase: float) -> float:
    """Converte a fase de passada (rad, de ``LegMotion``) em tempo do clipe.

    O pico do clipe (t=0) coincide com ``sin(fase) = +1``, a perna esquerda à
    frente; ``SINAL_BRACO_COM_PERNA`` = -1 inverte a contrafase (meio ciclo).
    """
    inversao = loc.CICLO_MEIO * (1.0 - loc.SINAL_BRACO_COM_PERNA) / 2.0

    return fase / tau - loc.CICLO_DESLOCAMENTO_SENO + inversao
