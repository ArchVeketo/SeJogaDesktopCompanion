"""IK 3D de braço: posição-alvo da mão → HPR dos bones do rig (Python puro).

Um gesto declara ONDE a mão deve ficar (alvo relativo ao ombro, em
``alvos_bracos``: ``x`` direita, ``y`` cima, ``z`` frente) e este módulo calcula
os ``Rotation3`` de ``right-arm``/``ant-arm`` (e o espelho ``left-arm``/
``ant-arm2``) que levam o punho (origem do nó ``hand``) até lá.

CADEIA COM OSSO BASE (ombro como raiz):

  ``right-arm`` (OMBRO, 3 DOF: P, H, R)  →  ``ant-arm`` (COTOVELO, dobradiça R,
  com torção-base fixa ``TORCAO_BASE_ANTEBRACO_GRAUS`` em P)  →  ``hand``
  (punho)  →  ``fingers``.

O braço tem o eixo longo em ±X. A dobradiça do cotovelo é o R do antebraço; com a
torção-base de 90° em P ela fica lateral e o antebraço dobra para a FRENTE. A
torção-base é somada pelo renderer e por ``cinematica`` (não está nos
``Rotation3`` do IK): os gestos escrevem DELTAS em ``ant-arm`` em torno dela.

FK ÚNICA: a verdade é ``nucleo.cinematica`` (igual ao grafo de cena do Panda3D,
conferida em posição por ``tests/test_cinematica_oraculo.py``). Este IK é analítico e usa essa
mesma convenção ``Rz(h)·Rx(p)·Ry(r)``:

  1. cotovelo: lei dos cossenos fixa a flexão ``c`` (0 = reto) a partir da
     distância ombro-alvo, limitada a ``[COTOVELO_MIN, COTOVELO_MAX]``;
  2. posição do cotovelo: no círculo de posições possíveis, a mais próxima do
     ``polo`` (para onde o cotovelo aponta);
  3. com braço ``u`` e antebraço ``f`` conhecidos, a base do ombro é
     ``[u, (f - cos c·u)/sen c, u x …]`` e vira H/P/R por ``hpr_de_matriz``.

O lado esquerdo é a imagem no plano sagital (lei única ``espelhar_rotacao``):
resolve-se o direito para o alvo espelhado e espelham-se as rotações.

O QUE NÃO ESTÁ PROVADO AQUI: que a pose "pareça" anatômica na GPU (palma da mão,
conforto do cotovelo, simetria na tela, polo ``POLO_COTOVELO_ANATOMICO``). Isso depende do usuário (ver ``recalibracao-gpu.md``).

FRONTEIRA: Python puro. NÃO importa Panda3D, Qt nem Win32.
"""

from __future__ import annotations

from math import acos, cos, pi, sin, sqrt

from sejoga.animacao import braco_tuning as tun
from sejoga.nucleo import cinematica as cin
from sejoga.nucleo.esqueleto import Rotation3
from sejoga.nucleo.modelo import Model

Vec3 = cin.Vec3
Mat3 = cin.Mat3

#: Comprimentos de fallback (translations do glTF) caso o modelo não exponha a
#: cadeia ``right-arm → ant-arm → hand`` (ver ``tools/inspecionar_modelo.py``).
_UPPER_FALLBACK = 0.125
_FOREARM_FALLBACK = 0.15625

#: Nomes dos grupos por lado: (braço, antebraço, mão).
_GRUPOS_BRACO = {
    "right": ("right-arm", "ant-arm", "hand"),
    "left": ("left-arm", "ant-arm2", "hand2"),
}

#: Tolerância padrão (unidades do modelo) para o alvo ser considerado atingido.
TOLERANCIA_PADRAO = tun.TOLERANCIA_PADRAO

#: Troca de eixos ``alvos_bracos`` ↔ autoria é a própria ``cinematica``; a matriz
#: abaixo faz o mesmo para rotações (permuta y↔z), usada só por ``medir_braco_render``.
_PERMUTA_YZ: Mat3 = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0)


def comprimentos_braco(model: Model, lado: str = "right") -> tuple[float, float]:
    """Lê (upper, forearm) da cadeia real do rig; cai para o fallback do glTF.

    ``upper`` é a translação de ``ant-arm`` (cotovelo) em relação ao ombro;
    ``forearm`` é a translação de ``hand`` em relação a ``ant-arm``.
    """
    _braco, antebraco, mao = _GRUPOS_BRACO[lado]

    upper = _norma_translacao(model, antebraco) or _UPPER_FALLBACK
    forearm = _norma_translacao(model, mao) or _FOREARM_FALLBACK

    return upper, forearm


def _norma_translacao(model: Model, grupo: str) -> float:
    """Norma da translação local do nó ``grupo`` (0.0 se ausente)."""
    no = model.find(grupo)

    if no is None:
        return 0.0

    return cin.norma(no.translation)


def posicao_mao_para_hpr(
    model: Model,
    lado: str,
    hpr_braco: Rotation3,
    hpr_antebraco: Rotation3,
    pose_base: dict[str, Rotation3] | None = None,
) -> Vec3:
    """FK do renderer: punho RELATIVO ao ombro, em coordenadas de ``alvos_bracos``.

    Usa ``cinematica`` (idêntica ao Panda). ``pose_base`` opcional soma outros
    grupos (ex.: tronco) à pose; braço e antebraço sobrescrevem.
    """
    braco, antebraco, mao = _GRUPOS_BRACO[lado]
    pose = dict(pose_base or {})
    pose[braco] = hpr_braco
    pose[antebraco] = hpr_antebraco

    ombro = cin.posicao_no(model, braco, pose)
    punho = cin.posicao_no(model, mao, pose)

    return cin.autoria_para_alvo(cin.subtrair(punho, ombro))


# --------------------------------------------------------------------------- #
# Solver analítico (braço DIREITO, coordenadas de autoria)
# --------------------------------------------------------------------------- #
def _perpendicular(v: Vec3, preferida: Vec3) -> Vec3:
    """Componente de ``preferida`` ⊥ ``v`` (unitária); cai em outro eixo se nula."""
    for candidato in (preferida, cin.EIXO_FRENTE, cin.EIXO_CIMA, cin.EIXO_DIREITA):
        perp = cin.subtrair(
            candidato, cin.escalar(v, cin.produto_escalar(candidato, v))
        )

        if cin.norma(perp) > tun.EPSILON_DEGENERADO:
            return cin.normalizar(perp)

    return cin.EIXO_DIREITA


def _flexao_do_cotovelo(distancia: float, upper: float, forearm: float) -> float:
    """Flexão (rad, 0 = reto) pela lei dos cossenos para a distância ombro-punho."""
    cos_interno = (upper * upper + forearm * forearm - distancia * distancia) / (
        2.0 * upper * forearm
    )

    return pi - acos(max(-1.0, min(1.0, cos_interno)))


def _distancia_limitada(distancia: float, upper: float, forearm: float) -> float:
    """Clampa a distância ao alcance real: reto no máximo, flexão máxima no mínimo."""
    maxima = (upper + forearm) * (1.0 - tun.FOLGA_ALCANCE)
    interno_min = pi - _radianos(tun.COTOVELO_MAX_GRAUS)
    minima = sqrt(
        upper * upper + forearm * forearm - 2.0 * upper * forearm * cos(interno_min)
    )

    return max(minima, min(maxima, distancia))


def _radianos(graus: float) -> float:
    return graus * pi / 180.0


def _resolver_direito(
    alvo: Vec3, polo: Vec3, upper: float, forearm: float
) -> tuple[Rotation3, float]:
    """``(rotação do ombro, flexão do cotovelo em rad)`` para o braço direito.

    ``alvo`` e ``polo`` em coordenadas de AUTORIA (x direita, y frente, z cima).
    """
    distancia_pedida = cin.norma(alvo)
    eixo = (
        cin.normalizar(alvo)
        if distancia_pedida > tun.EPSILON_DEGENERADO
        else (0.0, 0.0, -1.0)
    )
    distancia = _distancia_limitada(distancia_pedida, upper, forearm)
    punho = cin.escalar(eixo, distancia)

    flexao = _flexao_do_cotovelo(distancia, upper, forearm)
    flexao = max(
        _radianos(tun.COTOVELO_MIN_GRAUS),
        min(_radianos(tun.COTOVELO_MAX_GRAUS), flexao),
    )

    ao_longo = (upper * upper - forearm * forearm + distancia * distancia) / (
        2.0 * distancia
    )
    raio = sqrt(max(0.0, upper * upper - ao_longo * ao_longo))
    lateral = _perpendicular(eixo, polo)
    cotovelo = cin.somar(cin.escalar(eixo, ao_longo), cin.escalar(lateral, raio))

    braco_dir = cin.normalizar(cotovelo)
    antebraco_dir = cin.normalizar(cin.subtrair(punho, cotovelo))

    seno = sin(flexao)

    if seno > tun.EPSILON_DEGENERADO:
        lado_dobra = cin.normalizar(
            cin.subtrair(antebraco_dir, cin.escalar(braco_dir, cos(flexao)))
        )
    else:
        lado_dobra = cin.escalar(
            lateral, -1.0
        )  # reto: dobra do lado oposto ao cotovelo

    terceiro = cin.produto_vetorial(braco_dir, lado_dobra)
    base: Mat3 = (
        braco_dir[0], lado_dobra[0], terceiro[0],
        braco_dir[1], lado_dobra[1], terceiro[1],
        braco_dir[2], lado_dobra[2], terceiro[2],
    )  # fmt: skip
    h, p, r = cin.hpr_de_matriz(base)

    return Rotation3(p, h, r), flexao


def braco_para(
    model: Model,
    lado: str,
    alvo_mao: Vec3,
    polo: Vec3 = tun.POLO_COTOVELO_ANATOMICO,
    tolerancia: float = TOLERANCIA_PADRAO,  # solver é analítico; mantido por compat
) -> dict[str, Rotation3]:
    """Resolve os ``Rotation3`` do braço para colocar o punho em ``alvo_mao``.

    ``alvo_mao`` é a posição do punho relativa ao ombro em ``alvos_bracos``
    (x direita, y cima, z frente), no referencial do observador: o lado esquerdo
    recebe o ``x`` no mesmo referencial (x < 0 = à esquerda). ``polo`` é a
    direção para onde o COTOVELO aponta, SEMPRE na convenção do braço direito
    (``x > 0`` = para fora do corpo; é espelhada para o esquerdo). Alvo fora de alcance é
    clampado ao alcance real (nunca NaN).

    Devolve ``{grupo: Rotation3}`` (radianos) para braço e antebraço do ``lado``.
    O antebraço NÃO inclui a torção-base (somada pelo renderer/``cinematica``).
    """
    if lado not in _GRUPOS_BRACO:
        raise ValueError(f"lado desconhecido: {lado!r} (use 'right' ou 'left')")

    upper, forearm = comprimentos_braco(model, lado)
    braco, antebraco, _mao = _GRUPOS_BRACO[lado]

    alvo = cin.alvo_para_autoria(alvo_mao)
    polo_aut = cin.alvo_para_autoria(polo)

    if lado == "left":
        alvo = cin.espelhar_ponto(alvo)  # o polo já vem na convenção do braço direito

    rot_braco, flexao = _resolver_direito(alvo, polo_aut, upper, forearm)
    rot_antebraco = Rotation3(0.0, 0.0, flexao)

    if lado == "left":
        rot_braco = cin.espelhar_rotacao(rot_braco)
        rot_antebraco = cin.espelhar_rotacao(rot_antebraco)

    return {braco: rot_braco, antebraco: rot_antebraco}


def medir_braco_render(
    model: Model, lado: str, pose: dict[str, Rotation3]
) -> dict[str, object]:
    """Geometria REAL (FK do Panda) do braço do ``lado`` para uma pose.

    Devolve rotações de mundo 3x3 de braço/antebraço/mão e a ponta da mão
    relativa ao ombro, no referencial do corpo de ``rig_debug``
    (+X direita, +Y cima, +Z frente), tudo a partir de ``cinematica``.
    """
    braco, antebraco, mao = _GRUPOS_BRACO[lado]

    def _para_corpo(m: Mat3) -> Mat3:
        return cin.mul(_PERMUTA_YZ, cin.mul(m, _PERMUTA_YZ))

    return {
        braco: _para_corpo(cin.matriz_no(model, braco, pose)),
        antebraco: _para_corpo(cin.matriz_no(model, antebraco, pose)),
        mao: _para_corpo(cin.matriz_no(model, mao, pose)),
        "ponta_mao_rel_ombro": posicao_mao_para_hpr(
            model,
            lado,
            pose.get(braco, Rotation3()),
            pose.get(antebraco, Rotation3()),
            pose,
        ),
    }


def pose_repouso_bracos(model: Model) -> dict[str, Rotation3]:
    """``Rotation3`` de repouso dos quatro grupos de braço (alvo de idle).

    Os alvos vêm de ``alvos_bracos`` (fonte única). Devolve ``right-arm``/
    ``ant-arm``/``left-arm``/``ant-arm2``.
    """
    from sejoga.animacao.alvos_bracos import ALVO_IDLE

    pose: dict[str, Rotation3] = {}
    pose.update(braco_para(model, "right", ALVO_IDLE.alvo, ALVO_IDLE.polo))
    pose.update(braco_para(model, "left", ALVO_IDLE.alvo_espelhado(), ALVO_IDLE.polo))

    return pose
