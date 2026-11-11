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

    return ClipeAnim(
        1.0,
        {
            # Braço à frente sobe (z negativo ergue); ao voltar, desce.
            "right-arm": _par((0.0, braco_y, -braco_z), (0.0, -braco_y, braco_z)),
            "left-arm": _par((0.0, braco_y, -braco_z), (0.0, -braco_y, braco_z)),
            # Cotovelo flexiona mais com o braço à frente; nunca hiperestende.
            "ant-arm": _par((0.0, 0.0, cotovelo), (0.0, 0.0, 0.0)),
            "ant-arm2": _par((0.0, 0.0, 0.0), (0.0, 0.0, -cotovelo)),
            # Tronco gira com o ombro que avança e inclina (corrida), distribuído na coluna.
            "body": _par((inclinacao, giro, 0.0), (inclinacao, -giro, 0.0)),
            "cintura": _par(
                (inclinacao * 0.2, -giro * 0.35, 1.5),
                (inclinacao * 0.2, giro * 0.35, -1.5),
            ),
            "abdomen": _par(
                (inclinacao * 0.3, giro * 0.25, -1.0),
                (inclinacao * 0.3, -giro * 0.25, 1.0),
            ),
            "peitoral": _par(
                (inclinacao * 0.5, giro * 0.45, -1.5),
                (inclinacao * 0.5, -giro * 0.45, 1.5),
            ),
            # Cabeça: contra-giro suave + quique a cada apoio (duas vezes por ciclo).
            "head": _par((0.0, -contragiro, 0.0), (0.0, contragiro, 0.0)),
            "head" + _SEPARADOR_ROTULO + "quique": quique_chaves,
        },
    )


CLIPES = {
    "walk": _clipe_passada(
        loc.BRACO_AZIMUTE_CAMINHADA,
        loc.BRACO_ELEVACAO_CAMINHADA,
        loc.COTOVELO_CAMINHADA,
        loc.TRONCO_GIRO_CAMINHADA,
        loc.TRONCO_INCLINACAO_CAMINHADA,
        loc.CABECA_QUIQUE_CAMINHADA,
        loc.CABECA_CONTRAGIRO_CAMINHADA,
    ),
    "run": _clipe_passada(
        loc.BRACO_AZIMUTE_CORRIDA,
        loc.BRACO_ELEVACAO_CORRIDA,
        loc.COTOVELO_CORRIDA,
        loc.TRONCO_GIRO_CORRIDA,
        loc.TRONCO_INCLINACAO_CORRIDA,
        loc.CABECA_QUIQUE_CORRIDA,
        loc.CABECA_CONTRAGIRO_CORRIDA,
    ),
}


MODIFICADORES_PASSADA_PERSONALIDADE: dict[str, dict[str, float]] = {
    "fighter": {"braco": 0.6, "cotovelo": 2.0, "inclinacao": 3.0, "quique": 1.4},
    "street": {"braco": 1.3, "giro": 1.5, "quique": 1.3},
    "playful": {"braco": 1.2, "quique": 1.8, "contragiro": 1.6},
    "shy": {"braco": 0.6, "cotovelo": 0.5, "giro": 0.6, "quique": 0.7},
    "stylish": {"braco": 0.9, "giro": 1.4, "inclinacao": -1.0},
    "curious": {"contragiro": 1.8, "quique": 1.2},
    "confident": {"braco": 1.15, "inclinacao": -1.5, "giro": 1.2},
    "rhythm": {"quique": 1.6, "giro": 1.3},
    "calm": {},
}


def amostrar_clipe(
    nome: str, t: float, personalidade: str = "calm"
) -> dict[str, tuple[float, float, float]]:
    """Amostra o delta do clipe cíclico no tempo normalizado ``t`` (ciclos)."""
    clipe = CLIPES[nome]
    local = t % clipe.duracao
    mods = MODIFICADORES_PASSADA_PERSONALIDADE.get(personalidade, {})
    pose: dict[str, tuple[float, float, float]] = {}

    for chave, keys in clipe.tracks.items():
        grupo = chave.split(_SEPARADOR_ROTULO)[0]
        x, y, z = amostrar_pista(keys, local)
        if grupo in ("right-arm", "left-arm"):
            fator_braco = mods.get("braco", 1.0)
            y *= fator_braco
            z *= fator_braco
        elif grupo in ("ant-arm", "ant-arm2"):
            z *= mods.get("cotovelo", 1.0)
        elif grupo in ("body", "cintura", "abdomen", "peitoral"):
            y *= mods.get("giro", 1.0)
            x += mods.get("inclinacao", 0.0) * 0.3
        elif grupo == "head":
            y *= mods.get("contragiro", 1.0)
            x *= mods.get("quique", 1.0)

        ax, ay, az = pose.get(grupo, (0.0, 0.0, 0.0))
        pose[grupo] = (ax + x, ay + y, az + z)

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
