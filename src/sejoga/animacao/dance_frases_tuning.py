"""Frases de dança por estilo: um passo por batida, quatro poses por passo.

Dados calibráveis (graus sobre o repouso para cabeça/tronco; nomes de alvos de
mão de ``arm_targets`` para os braços). Cada passo declara, na ordem de
``dance_tuning.U_POSES``: acento (no onset), sustentação, recuperação e
preparação. Sinais: ``head.x`` negativo é o nod para baixo; ``body.x`` positivo
inclina para trás (A_CONFIRMAR na GPU, C48). Python puro, sem engine.
"""

from __future__ import annotations

from sejoga.animacao.dance_poses import PassoDanca, PoseDanca, Trio

Quatro = tuple[Trio, Trio, Trio, Trio]
NomesBraco = str | tuple[str, str, str, str]


def _por_pose(valor: NomesBraco) -> tuple[str, str, str, str]:
    """Repete o nome do alvo nas quatro poses quando for um só."""
    return (valor, valor, valor, valor) if isinstance(valor, str) else valor


def _passo(
    cabeca: Quatro,
    tronco: Quatro,
    braco_dir: NomesBraco = "idle",
    braco_esq: NomesBraco = "idle",
    extras: dict[str, Trio] | None = None,
) -> PassoDanca:
    """Monta um passo a partir de quatro trios de cabeça/tronco e dos braços.

    ``extras`` são grupos fixos nas quatro poses (ex.: ``hand`` do rock).
    """
    dirs = _por_pose(braco_dir)
    esqs = _por_pose(braco_esq)
    poses = tuple(
        PoseDanca({"head": cabeca[i], "body": tronco[i], **(extras or {})}, dirs[i], esqs[i])
        for i in range(4)
    )

    return PassoDanca(poses)  # type: ignore[arg-type]  # tupla de 4 poses montada acima


def _fixo(trio: Trio) -> Quatro:
    """O mesmo trio nas quatro poses."""
    return (trio, trio, trio, trio)


#: Inclinação do tronco para trás do head bob (costas na caixa), em graus.
HEADBOB_TRONCO_TRAS = 8.0
_HB_TRONCO: Trio = (HEADBOB_TRONCO_TRAS, 0.0, 0.0)

#: Head bob: 4 batidas. Nod curto no 1, recuperação lenta com inclinação lateral
#: no 2, segundo nod no 3 e pausa no 4. Braços cruzados à frente do peito.
HEAD_BOB: tuple[PassoDanca, ...] = (
    _passo(
        ((-14.0, 0.0, 2.0), (-4.0, 0.0, 1.0), (-2.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        ((HEADBOB_TRONCO_TRAS - 2.0, 0.0, 0.0), _HB_TRONCO, _HB_TRONCO, _HB_TRONCO),
        "cruzado_dir",
        "cruzado_esq",
    ),
    _passo(
        ((-4.0, 6.0, 8.0), (-2.0, 6.0, 10.0), (-2.0, 3.0, 6.0), (-3.0, 0.0, 2.0)),
        (
            (HEADBOB_TRONCO_TRAS, 0.0, 3.0),
            (HEADBOB_TRONCO_TRAS, 0.0, 4.0),
            (HEADBOB_TRONCO_TRAS, 0.0, 2.0),
            (HEADBOB_TRONCO_TRAS, 0.0, 0.0),
        ),
        "cruzado_dir",
        "cruzado_esq",
    ),
    _passo(
        ((-12.0, -4.0, -3.0), (-4.0, -3.0, -1.0), (-2.0, -1.0, 0.0), (2.0, 0.0, 0.0)),
        ((HEADBOB_TRONCO_TRAS - 2.0, 0.0, -2.0), _HB_TRONCO, _HB_TRONCO, _HB_TRONCO),
        "cruzado_dir",
        "cruzado_esq",
    ),
    _passo(
        ((-2.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),
        _fixo(_HB_TRONCO),
        "cruzado_dir",
        "cruzado_esq",
    ),
)

#: Torção do punho direito no rock (graus): vira a palma do chifre para a câmera.
ROCK_PUNHO_TORCAO = 180.0
_ROCK_PUNHO = {"hand": (ROCK_PUNHO_TORCAO, 0.0, 0.0)}

#: Rock: 2 batidas. Headbang para baixo (cabeça e tronco) no acento, braço
#: direito alto com a mão em chifre, esquerdo baixo. Meio-tempo se BPM > 150.
ROCK: tuple[PassoDanca, ...] = (
    _passo(
        ((-26.0, 0.0, 3.0), (-10.0, 0.0, 2.0), (-5.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ((-7.0, 0.0, 0.0), (-3.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        "chifre",
        extras=_ROCK_PUNHO,
    ),
    _passo(
        ((-16.0, 0.0, -3.0), (-7.0, 0.0, -2.0), (-3.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ((-4.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        "chifre",
        extras=_ROCK_PUNHO,
    ),
)

#: Frase de cada estilo (preenchida estilo a estilo).
FRASES: dict[str, tuple[PassoDanca, ...]] = {
    "head_bob": HEAD_BOB,
    "rock": ROCK,
}


def frase_do_estilo(estilo: str) -> tuple[PassoDanca, ...]:
    """Frase (passos de uma batida) do ``estilo`` de dança."""
    return FRASES[estilo]

