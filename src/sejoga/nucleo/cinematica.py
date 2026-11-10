"""Cinemática direta (FK) pura do rig, idêntica ao grafo de cena do Panda3D.

Referencial de AUTORIA (local ao nó raiz do asset, que só gira o mascote de
frente): ``+X`` = direita do mascote, ``+Y`` = frente (rosto), ``+Z`` = cima.
É o referencial em que o renderer aplica ``setHpr`` em cada grupo.

Convenção de rotação de um nó (medida contra ``NodePath`` do Panda 1.10, ver
``tests/test_cinematica_oraculo.py``): matriz coluna ``Rz(h) · Rx(p) · Ry(r)``.
``Rotation3.y`` = H (giro em torno da vertical), ``Rotation3.x`` = P (em torno
de X, lateral) e ``Rotation3.z`` = R (em torno de Y, eixo frente-trás).
O renderer SOMA a pose (graus) ao HPR de repouso do nó (``base + pose``); aqui a
base é extraída da rotação de repouso do glTF e a soma é feita nos ângulos.

O glTF é Y-up; o loader do Panda converte para Z-up com ``(x, y, z) → (x, -z,
y)``. Esta função faz a mesma troca de base nas translações e rotações.

Lei de espelho ÚNICA (``espelhar_rotacao``): o lado esquerdo do rig é a imagem
no plano sagital (x → -x) do direito. Para ``Rz(h)·Rx(p)·Ry(r)`` isso dá
``(p, h, r) → (p, -h, -r)``, ou seja ``Rotation3 (x, y, z) → (x, -y, -z)``.

FRONTEIRA: Python puro (só ``math``); NÃO importa Panda3D, Qt nem Win32.
"""

from __future__ import annotations

from math import atan2, cos, degrees, radians, sin, sqrt

from sejoga.nucleo.cinematica_const import (
    EPSILON_DEGENERADO,
    TORCAO_BASE_ANTEBRACO_GRAUS,
)
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rotation3
from sejoga.nucleo.modelo import Model

Vec3 = tuple[float, float, float]
#: Matriz 3x3 linha-maior (9 floats), aplicada a vetores coluna.
Mat3 = tuple[float, float, float, float, float, float, float, float, float]

EIXO_DIREITA: Vec3 = (1.0, 0.0, 0.0)
EIXO_FRENTE: Vec3 = (0.0, 1.0, 0.0)
EIXO_CIMA: Vec3 = (0.0, 0.0, 1.0)

IDENTIDADE: Mat3 = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)

#: Troca de base glTF (Y-up) → autoria (Z-up): linhas de C em ``v' = C · v``.
_GLTF_PARA_AUTORIA: Mat3 = (1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 1.0, 0.0)

#: |cos(p)| abaixo do qual a decomposição HPR entra em gimbal.
_GIMBAL_COS_MINIMO = 1e-6

#: Norma abaixo da qual um vetor é tratado como nulo.
_COS_PITCH_MINIMO = EPSILON_DEGENERADO

#: HPR (graus) SOMADO ao repouso do glTF, igual no renderer (``apply_rig_pose``) e
#: na FK. É o osso base do cotovelo: torção fixa do antebraço (ver braco_tuning).
BASE_ADICIONAL_GRAUS: dict[str, tuple[float, float, float]] = {
    grupo: (0.0, TORCAO_BASE_ANTEBRACO_GRAUS, 0.0) for grupo in ("ant-arm", "ant-arm2")
}


# --------------------------------------------------------------------------- #
# Álgebra 3x3
# --------------------------------------------------------------------------- #
def mul(a: Mat3, b: Mat3) -> Mat3:
    """Produto ``a · b``."""
    return tuple(  # type: ignore[return-value]
        sum(a[i * 3 + k] * b[k * 3 + j] for k in range(3))
        for i in range(3)
        for j in range(3)
    )


def aplicar(m: Mat3, v: Vec3) -> Vec3:
    """``m · v`` (vetor coluna)."""
    return (
        m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
        m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
        m[6] * v[0] + m[7] * v[1] + m[8] * v[2],
    )


def transposta(m: Mat3) -> Mat3:
    """Devolve a transposta da matriz 3x3."""
    return (m[0], m[3], m[6], m[1], m[4], m[7], m[2], m[5], m[8])


def coluna(m: Mat3, indice: int) -> Vec3:
    """Coluna ``indice`` (eixo local transformado para o referencial pai)."""
    return (m[indice], m[3 + indice], m[6 + indice])


def somar(a: Vec3, b: Vec3) -> Vec3:
    """Soma dois vetores."""
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def subtrair(a: Vec3, b: Vec3) -> Vec3:
    """Subtrai ``b`` de ``a``."""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def escalar(v: Vec3, k: float) -> Vec3:
    """Multiplica o vetor pelo escalar ``k``."""
    return (v[0] * k, v[1] * k, v[2] * k)


def produto_escalar(a: Vec3, b: Vec3) -> float:
    """Calcula o produto escalar."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def produto_vetorial(a: Vec3, b: Vec3) -> Vec3:
    """Calcula o produto vetorial ``a x b``."""
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norma(v: Vec3) -> float:
    """Calcula a norma euclidiana."""
    return sqrt(produto_escalar(v, v))


def normalizar(v: Vec3) -> Vec3:
    """Vetor unitário (devolve o próprio vetor se for nulo)."""
    n = norma(v)

    if n < _COS_PITCH_MINIMO:
        return v

    return escalar(v, 1.0 / n)


def rot_x(p: float) -> Mat3:
    """Monta a rotação de pitch (radianos) em torno de X."""
    c, s = cos(p), sin(p)
    return (1.0, 0.0, 0.0, 0.0, c, -s, 0.0, s, c)


def rot_y(r: float) -> Mat3:
    """Monta a rotação de roll (radianos) em torno de Y."""
    c, s = cos(r), sin(r)
    return (c, 0.0, s, 0.0, 1.0, 0.0, -s, 0.0, c)


def rot_z(h: float) -> Mat3:
    """Monta a rotação de heading (radianos) em torno de Z."""
    c, s = cos(h), sin(h)
    return (c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0)


def rot_hpr(h: float, p: float, r: float) -> Mat3:
    """Rotação de nó do Panda para ``setHpr(h, p, r)`` (radianos)."""
    return mul(rot_z(h), mul(rot_x(p), rot_y(r)))


def hpr_de_matriz(m: Mat3) -> tuple[float, float, float]:
    """Inverso de ``rot_hpr``: ``(h, p, r)`` em radianos, com ``|p| < 90°``."""
    sen_p = max(-1.0, min(1.0, m[7]))
    cos_p = sqrt(max(0.0, 1.0 - sen_p * sen_p))
    pitch = atan2(sen_p, cos_p)

    if cos_p < _GIMBAL_COS_MINIMO:
        # Gimbal: H e R giram no mesmo eixo; só a soma importa. Fixa R = 0.
        return atan2(m[3], m[0]), pitch, 0.0

    return atan2(-m[1], m[4]), pitch, atan2(-m[6], m[8])


# --------------------------------------------------------------------------- #
# Espelho (lei única)
# --------------------------------------------------------------------------- #
def espelhar_rotacao(rotacao: Rotation3) -> Rotation3:
    """Imagem no plano sagital de uma rotação de nó: ``(x, -y, -z)``."""
    return Rotation3(rotacao.x, -rotacao.y, -rotacao.z)


def espelhar_ponto(ponto: Vec3) -> Vec3:
    """Imagem no plano sagital de um ponto/vetor de autoria: ``x → -x``."""
    return (-ponto[0], ponto[1], ponto[2])


def alvo_para_autoria(alvo: Vec3) -> Vec3:
    """``(direita, cima, frente)`` de ``alvos_bracos`` → ``(x, y=frente, z=cima)``."""
    return (alvo[0], alvo[2], alvo[1])


def autoria_para_alvo(ponto: Vec3) -> Vec3:
    """Inverso de ``alvo_para_autoria``."""
    return (ponto[0], ponto[2], ponto[1])


# --------------------------------------------------------------------------- #
# Repouso do glTF no referencial de autoria
# --------------------------------------------------------------------------- #
def _quat_para_mat3(q: tuple[float, float, float, float]) -> Mat3:
    x, y, z, w = q

    return (
        1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w),
        2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w),
        2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y),
    )  # fmt: skip


#: Cache do repouso por (id do Model, grupo): o Model é imutável (frozen).
_CACHE_REPOUSO: dict[
    tuple[int, str], tuple[Model, tuple[str | None, Vec3, tuple[float, float, float]]]
] = {}


def _repouso(
    model: Model, grupo: str
) -> tuple[str | None, Vec3, tuple[float, float, float]]:
    """``(pai, translação, hpr_base)`` do grupo, em autoria (radianos)."""
    chave = (id(model), grupo)
    guardado = _CACHE_REPOUSO.get(chave)

    # Guarda o próprio Model junto: evita colisão de id() após coleta de lixo.
    if guardado is not None and guardado[0] is model:
        return guardado[1]

    valor = _repouso_sem_cache(model, grupo)
    _CACHE_REPOUSO[chave] = (model, valor)

    return valor


def _repouso_sem_cache(
    model: Model, grupo: str
) -> tuple[str | None, Vec3, tuple[float, float, float]]:
    no = model.find(grupo)

    if no is None:
        raise KeyError(f"grupo ausente no modelo: {grupo!r}")

    pai = None

    if no.parent is not None:
        # ``Node.index`` é o índice do glTF; ``model.nodes`` está em ordem de árvore.
        nome_pai = next((n.name for n in model.nodes if n.index == no.parent), None)

        if nome_pai in ALL_GROUPS:
            pai = nome_pai

    t = aplicar(_GLTF_PARA_AUTORIA, no.translation)
    c = _GLTF_PARA_AUTORIA
    rot = mul(mul(c, _quat_para_mat3(no.rotation)), transposta(c))

    h, p, r = hpr_de_matriz(rot)
    eh, ep, er = (radians(a) for a in BASE_ADICIONAL_GRAUS.get(grupo, (0.0, 0.0, 0.0)))

    return pai, t, (h + eh, p + ep, r + er)


def transformacao_no(
    model: Model, grupo: str, pose: dict[str, Rotation3] | None = None
) -> tuple[Mat3, Vec3]:
    """``(rotação, origem)`` do grupo no referencial de autoria, com a ``pose``.

    ``pose`` usa a mesma semântica do renderer: ``Rotation3`` em radianos somado
    ao HPR de repouso (``x=P``, ``y=H``, ``z=R``). Grupos ausentes = repouso.
    """
    return cadeia(model, grupo, pose or {})[grupo]


def cadeia(
    model: Model, grupo: str, pose: dict[str, Rotation3]
) -> dict[str, tuple[Mat3, Vec3]]:
    """``{grupo: (rotação, origem)}`` de ``grupo`` e de todos os seus ancestrais."""
    nomes = [grupo]

    while (pai := _repouso(model, nomes[-1])[0]) is not None:
        nomes.append(pai)

    resultado: dict[str, tuple[Mat3, Vec3]] = {}
    r_pai, o_pai = IDENTIDADE, (0.0, 0.0, 0.0)

    for nome in reversed(nomes):
        _pai, t, (h0, p0, r0) = _repouso(model, nome)
        rot_local = pose.get(nome, Rotation3())
        r_local = rot_hpr(h0 + rot_local.y, p0 + rot_local.x, r0 + rot_local.z)
        o_pai = somar(o_pai, aplicar(r_pai, t))
        r_pai = mul(r_pai, r_local)
        resultado[nome] = (r_pai, o_pai)

    return resultado


def matriz_no(
    model: Model, grupo: str, pose: dict[str, Rotation3] | None = None
) -> Mat3:
    """Calcula a matriz mundo do nó para a pose dada."""
    return transformacao_no(model, grupo, pose)[0]


def posicao_no(
    model: Model, grupo: str, pose: dict[str, Rotation3] | None = None
) -> Vec3:
    """Calcula a posição mundo do nó para a pose dada."""
    return transformacao_no(model, grupo, pose)[1]


def rot_eixo(eixo: Vec3, angulo: float) -> Mat3:
    """Rotação de ``angulo`` (rad) em torno de ``eixo`` unitário (Rodrigues)."""
    x, y, z = eixo
    c, s = cos(angulo), sin(angulo)
    k = 1.0 - c

    return (
        c + x * x * k, x * y * k - z * s, x * z * k + y * s,
        y * x * k + z * s, c + y * y * k, y * z * k - x * s,
        z * x * k - y * s, z * y * k + x * s, c + z * z * k,
    )  # fmt: skip


def pontos_cadeia_dedo(
    rot_no: Mat3,
    origem_no: Vec3,
    pivos: list[Vec3],
    eixos: list[Vec3],
    angulos_graus: tuple[float, ...],
    ponta: Vec3,
) -> list[Vec3]:
    """FK da cadeia de juntas de um dedo: posição de cada pivô e da ``ponta``.

    ``pivos``, ``eixos`` e ``ponta`` estão no referencial do grupo ``fingers``
    em repouso; ``rot_no``/``origem_no`` vêm de ``transformacao_no`` desse grupo.
    A junta k gira em torno de ``eixos[k]`` por ``pivos[k]`` e leva as seguintes.
    """
    rot = rot_no
    resultado: list[Vec3] = []
    anterior = pivos[0]
    posicao = somar(origem_no, aplicar(rot_no, pivos[0]))

    for k, pivo in enumerate(pivos):
        if k > 0:
            posicao = somar(posicao, aplicar(rot, subtrair(pivo, anterior)))

        resultado.append(posicao)
        anterior = pivo
        rot = mul(rot, rot_eixo(eixos[k], radians(angulos_graus[k])))

    resultado.append(somar(posicao, aplicar(rot, subtrair(ponta, anterior))))

    return resultado


def graus(rotacao: Rotation3) -> tuple[float, float, float]:
    """``(h, p, r)`` em graus de um ``Rotation3`` (ordem do ``setHpr``)."""
    return degrees(rotacao.y), degrees(rotacao.x), degrees(rotacao.z)
