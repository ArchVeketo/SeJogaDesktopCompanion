"""Frases de dança por estilo: um passo por batida, quatro poses por passo.

Dados calibráveis (graus sobre o repouso para cabeça/tronco; nomes de alvos de
mão de ``alvos_bracos`` para os braços). Cada passo declara, na ordem de
``dance_tuning.U_POSES``: acento (no onset), sustentação, recuperação e
preparação. Sinais: ``head.x`` negativo é o nod para baixo; ``body.x`` positivo
inclina para trás (A_CONFIRMAR na GPU, C48). Python puro, sem engine.
"""

from __future__ import annotations

from dataclasses import replace

from sejoga.animacao.poses_danca import PassoDanca, PoseDanca, Trio

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
        PoseDanca(
            {"head": cabeca[i], "body": tronco[i], **(extras or {})}, dirs[i], esqs[i]
        )
        for i in range(4)
    )

    return PassoDanca(poses)  # type: ignore[arg-type]  # tupla de 4 poses montada acima


def _fixo(trio: Trio) -> Quatro:
    """O mesmo trio nas quatro poses."""
    return (trio, trio, trio, trio)


#: Inclinação do tronco no head bob sentado no topo da caixa (graus).
HEADBOB_TRONCO_TRAS = 2.0
_HB_TRONCO: Trio = (HEADBOB_TRONCO_TRAS, 0.0, 0.0)

#: Head bob: 4 batidas. Mario senta no topo da jukebox com as pernas balançando
#: e bopa a cabeça de um lado para o outro em arco estilo Girlfriend de Friday Night Funkin'.
#: O braço esquerdo apoia na caixa de som, e o braço direito descansa no colo com groove contínuo.
HEAD_BOB: tuple[PassoDanca, ...] = (
    # Batida 1: Bop para a esquerda (roll positivo), nod no onset e sustentação no pico
    _passo(
        ((-12.0, 5.0, 12.0), (-5.0, 6.0, 14.0), (-2.0, 4.0, 10.0), (0.0, 2.0, 3.0)),
        ((-2.0, 0.0, 1.5), (-1.0, 0.0, 1.5), _HB_TRONCO, _HB_TRONCO),
        braco_dir="colo",
        braco_esq="apoio_caixa",
    ),
    # Batida 2: Transição suave pelo centro
    _passo(
        ((-4.0, 2.0, 4.0), (-1.0, 1.0, 1.0), (0.0, 0.0, 0.0), (1.0, -2.0, -3.0)),
        _fixo(_HB_TRONCO),
        braco_dir="colo",
        braco_esq="apoio_caixa",
    ),
    # Batida 3: Bop para a direita (roll negativo), nod no onset e sustentação no pico
    _passo(
        ((-12.0, -5.0, -12.0), (-5.0, -6.0, -14.0), (-2.0, -4.0, -10.0), (0.0, -2.0, -3.0)),
        ((-2.0, 0.0, -1.5), (-1.0, 0.0, -1.5), _HB_TRONCO, _HB_TRONCO),
        braco_dir="colo",
        braco_esq="apoio_caixa",
    ),
    # Batida 4: Transição suave pelo centro de volta ao início
    _passo(
        ((-4.0, -2.0, -4.0), (-1.0, -1.0, -1.0), (0.0, 0.0, 0.0), (1.0, 2.0, 3.0)),
        _fixo(_HB_TRONCO),
        braco_dir="colo",
        braco_esq="apoio_caixa",
    ),
)

#: Torção do punho direito no rock (graus): vira a palma do chifre para a câmera.
_ROCK_PUNHO = {"hand": (0.0, 0.0, 0.0)}

#: Rock: 2 batidas. Headbang enérgico para baixo (cabeça e tronco) no acento, braço
#: direito alto com a mão em chifre, esquerdo com atitude. Meio-tempo se BPM > 150.
ROCK: tuple[PassoDanca, ...] = (
    _passo(
        ((-25.0, 0.0, 3.0), (-12.0, 0.0, 2.0), (-4.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ((-7.0, 0.0, 0.0), (-3.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        "chifre",
        extras=_ROCK_PUNHO,
    ),
    _passo(
        ((-18.0, 0.0, -3.0), (-8.0, 0.0, -2.0), (-2.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ((-4.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        "chifre",
        extras=_ROCK_PUNHO,
    ),
)

#: Hip hop: 8 batidas. Comprimir e transferir o peso, estender o braço oposto,
#: fechar, pausa; depois o lado oposto com variação (giro de cabeça) e uma pose
#: legível com os dois braços fora. O contrapeso vai no braço oposto ao lado
#: carregado; a perna carregada vem de ``movimento_pernas`` (fase global, A_CONFIRMAR C50).
HIP_HOP: tuple[PassoDanca, ...] = (
    _passo(
        ((-10.0, 0.0, 3.0), (-4.0, 0.0, 2.0), (-2.0, 0.0, 0.0), (3.0, 0.0, 0.0)),
        ((-6.0, 0.0, 6.0), (-2.0, 0.0, 5.0), (0.0, 0.0, 3.0), (2.0, 0.0, 2.0)),
        braco_esq=("idle", "idle", "contrapeso", "contrapeso"),
    ),
    _passo(
        ((-6.0, 0.0, 2.0), (-3.0, 0.0, 1.0), (-1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        ((-3.0, 0.0, 5.0), (-1.0, 0.0, 4.0), (0.0, 0.0, 3.0), (0.0, 0.0, 2.0)),
        braco_esq="contrapeso",
    ),
    _passo(
        ((-8.0, 0.0, 0.0), (-3.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        ((-5.0, 0.0, 2.0), (-2.0, 0.0, 1.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        braco_esq=("contrapeso", "contrapeso", "idle", "idle"),
    ),
    _passo(
        ((-2.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        _fixo((0.0, 0.0, 0.0)),
    ),
    _passo(
        ((-10.0, 0.0, -3.0), (-4.0, 0.0, -2.0), (-2.0, 0.0, 0.0), (3.0, 0.0, 0.0)),
        ((-6.0, 0.0, -6.0), (-2.0, 0.0, -5.0), (0.0, 0.0, -3.0), (2.0, 0.0, -2.0)),
        braco_dir=("idle", "idle", "contrapeso", "contrapeso"),
    ),
    _passo(
        ((-9.0, 8.0, -2.0), (-4.0, 6.0, -1.0), (-1.0, 3.0, 0.0), (2.0, 0.0, 0.0)),
        ((-4.0, 0.0, -5.0), (-1.0, 0.0, -4.0), (0.0, 0.0, -3.0), (0.0, 0.0, -2.0)),
        braco_dir="contrapeso",
    ),
    _passo(
        ((-8.0, 0.0, 0.0), (-3.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        ((-5.0, 0.0, -2.0), (-2.0, 0.0, -1.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        braco_dir=("contrapeso", "contrapeso", "idle", "idle"),
    ),
    _passo(
        ((-3.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        _fixo((0.0, 0.0, 0.0)),
        "idle",
        "idle",
    ),
)

#: Tronco inclinado para a frente no chão do breakdance (graus em ``body.x``).
BREAK_TRONCO_CHAO = -10.0
_BR_TRONCO_CHAO: Trio = (BREAK_TRONCO_CHAO, 0.0, 0.0)


#: Roll do tronco (graus) que alterna o lado a cada passo de footwork.
BREAK_TRONCO_ROLL = 4.0


def _passo_de_chao(giro: float) -> PassoDanca:
    """Passo de footwork: mãos plantadas e a cabeça/tronco trocam de lado.

    ``giro`` é o roll da cabeça em graus (o do tronco segue o mesmo sinal). As
    mãos ficam no apoio: trocar de alvo a cada batida a 145 BPM passava de 250
    mil graus/s^3 de jerk no ombro.
    """
    cabeca = (
        (-14.0, 0.0, giro),
        (-10.0, 0.0, giro),
        (-10.0, 0.0, giro),
        (-12.0, 0.0, giro),
    )
    roll = BREAK_TRONCO_ROLL * (1.0 if giro > 0 else -1.0)
    tronco = (BREAK_TRONCO_CHAO, 0.0, roll)

    return _passo(cabeca, _fixo(tronco), "apoio_chao", "apoio_chao")


def _sem_bracos(passo: PassoDanca) -> PassoDanca:
    """Cópia do ``passo`` com os dois braços no repouso (``idle``)."""
    return PassoDanca(
        tuple(replace(pose, braco_dir="idle", braco_esq="idle") for pose in passo.poses)  # type: ignore[arg-type]  # 4 poses
    )


#: Breakdance: 16 batidas (guia 5.4). Toprock 0-3 (cabeça e tronco do hip hop,
#: braços no repouso), descida 4-5, footwork 6-12 de mãos plantadas, freeze 13
#: e subida 14-15. O roll do corpo e o giro vêm de ``DanceMotion.floor_amount``
#: e ``floor_spin`` (renderer).
BREAKDANCE: tuple[PassoDanca, ...] = (
    *(_sem_bracos(passo) for passo in HIP_HOP[:4]),
    _passo(
        ((-10.0, 0.0, 0.0), (-14.0, 0.0, 3.0), (-14.0, 0.0, 5.0), (-12.0, 0.0, 5.0)),
        ((-8.0, 0.0, 0.0), _BR_TRONCO_CHAO, _BR_TRONCO_CHAO, _BR_TRONCO_CHAO),
        ("idle", "idle", "apoio_chao", "apoio_chao"),
        ("idle", "idle", "apoio_chao", "apoio_chao"),
    ),
    _passo(
        _fixo((-12.0, 0.0, 5.0)),
        _fixo(_BR_TRONCO_CHAO),
        "apoio_chao",
        "apoio_chao",
    ),
    _passo_de_chao(5.0),
    _passo_de_chao(-5.0),
    _passo_de_chao(5.0),
    _passo_de_chao(-5.0),
    _passo_de_chao(5.0),
    _passo_de_chao(-5.0),
    _passo_de_chao(5.0),
    _passo(
        _fixo((-10.0, 0.0, 10.0)),
        _fixo(_BR_TRONCO_CHAO),
        "apoio_chao",
        "apoio_chao",
    ),
    _passo(
        ((-10.0, 0.0, 6.0), (-6.0, 0.0, 3.0), (-3.0, 0.0, 0.0), (-2.0, 0.0, 0.0)),
        (
            (BREAK_TRONCO_CHAO, 0.0, 0.0),
            (-6.0, 0.0, 0.0),
            (-2.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
        ),
        ("apoio_chao", "apoio_chao", "idle", "idle"),
        ("apoio_chao", "apoio_chao", "idle", "idle"),
    ),
    _passo(
        ((-3.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        _fixo((0.0, 0.0, 0.0)),
    ),
)

#: Frase de cada estilo.
FRASES: dict[str, tuple[PassoDanca, ...]] = {
    "head_bob": HEAD_BOB,
    "rock": ROCK,
    "hip_hop": HIP_HOP,
    "breakdance": BREAKDANCE,
}


def frase_do_estilo(estilo: str) -> tuple[PassoDanca, ...]:
    """Frase (passos de uma batida) do ``estilo`` de dança."""
    return FRASES[estilo]
