"""IK 3D de braço: posição-alvo da mão → HPR dos bones do rig (Python puro).

Causa raiz (comprovada visualmente): os bones de braço do Mário têm orientação
diagonal e nenhum eixo HPR isolado ergue o braço de forma limpa quando se olha
pela convenção errada. Calibrar poses por ângulo direto é inviável. A decisão
foi usar IK: um gesto declara ONDE a mão deve ficar no espaço (alvo relativo ao
ombro) e este módulo calcula os HPR de ``right-arm``/``ant-arm`` (e o espelho
``left-arm``/``ant-arm2``) que levam a ponta da mão até lá.

IMPORTANTE — a FK é calibrada contra o RENDERER REAL, não contra ``rig_debug``.
Medindo frames reais (ver a investigação na task), a geometria do braço NO
RENDERER é:

  - Eixo longo do braço em repouso = +X (right-arm → ant-arm → hand, todas as
    translations locais em +X). Upper ≈ 0.125, forearm ≈ 0.15625.
  - ``Rotation3.y`` (HEADING/H do renderer) ELEVA o braço no plano frontal XY:
    y=0 → braço lateral (+X), y=+90 → reto p/ CIMA (+Y), y=-90 → reto p/ BAIXO.
  - ``Rotation3.z`` (ROLL/R do renderer) gira o braço no plano horizontal XZ
    (AZIMUTE: avanço/recuo): z=0 → +X, z=+90 → -Z (trás), z=-90 → +Z (frente).
  - ``Rotation3.x`` (PITCH/P) é torção em torno do eixo longo: NÃO move a mão.
  - O cotovelo é ``ant-arm.Rotation3.z`` (roll), que dobra no plano local do
    braço, composto DEPOIS da rotação do ombro (``R_arm · R_elbow``).

Esta é a convenção que o renderer de fato aplica (``renderer.apply_rig_pose``:
``setHpr(base_h+deg(y), base_p+deg(x), base_r+deg(z))`` sobre os nós do Panda).
``rig_debug`` reimplementa uma composição que NÃO bate com o renderer para os
braços (eixo longo assumido -Y); por isso aqui usamos o modelo de FK medido do
renderer, em matrizes 3x3 puras — e os previews reais confirmam a pose.

Eixos do mundo no espaço do corpo (medidos): +X=direita, +Y=cima, +Z=frente.

FRONTEIRA (igual a model.py/rig.py): Python puro. NÃO importa Panda3D, Qt nem
Win32. Só ``math`` e ``sejoga.nucleo``.
"""

from __future__ import annotations

from math import atan2, cos, degrees, radians, sin, sqrt

from sejoga.animacao.limb_ik import solve_arm
from sejoga.animacao.rig_base import espelhar_braco
from sejoga.nucleo.model import Model
from sejoga.nucleo.rig import Rotation3

Vec3 = tuple[float, float, float]
Mat3 = tuple[float, float, float, float, float, float, float, float, float]

#: Comprimentos de fallback (translations do glTF) caso o modelo não exponha a
#: cadeia ``right-arm → ant-arm → hand`` (ver ``tools/inspect_model.py``).
_UPPER_FALLBACK = 0.125
_FOREARM_FALLBACK = 0.15625

#: Nomes dos grupos por lado: (braço, antebraço).
_GRUPOS_BRACO = {
    "right": ("right-arm", "ant-arm"),
    "left": ("left-arm", "ant-arm2"),
}

#: Tolerância padrão (unidades do modelo) para o alvo ser considerado atingido.
TOLERANCIA_PADRAO = 0.01

#: Máximo de iterações do solver numérico (converge em poucas).
_MAX_ITER = 300


# --------------------------------------------------------------------------- #
# Álgebra 3x3 e FK do RENDERER (validada medindo frames reais)
# --------------------------------------------------------------------------- #
def _mul(a: Mat3, b: Mat3) -> Mat3:
    return tuple(
        sum(a[i * 3 + k] * b[k * 3 + j] for k in range(3))
        for i in range(3)
        for j in range(3)
    )  # type: ignore[return-value]


def _apply(m: Mat3, v: Vec3) -> Vec3:
    return (
        m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
        m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
        m[6] * v[0] + m[7] * v[1] + m[8] * v[2],
    )


def _rh(h: float) -> Mat3:
    """Heading (H do renderer), radianos: +X → +Y (plano frontal XY, elevação)."""
    c, s = cos(h), sin(h)
    return (c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0)


def _rr(r: float) -> Mat3:
    """Roll (R do renderer), radianos: +X → -Z (plano horizontal XZ, azimute)."""
    c, s = cos(r), sin(r)
    return (c, 0.0, s, 0.0, 1.0, 0.0, -s, 0.0, c)


def comprimentos_braco(model: Model, lado: str = "right") -> tuple[float, float]:
    """Lê (upper, forearm) da cadeia real do rig; cai para o fallback do glTF.

    ``upper`` é a translação de ``ant-arm`` (cotovelo) em relação a ``right-arm``
    (ombro); ``forearm`` é a translação de ``hand`` em relação a ``ant-arm``. As
    translations locais do modelo são ao longo de +X, então usamos a norma.
    """
    braco, antebraco = _GRUPOS_BRACO[lado]
    mao = "hand" if lado == "right" else "hand2"

    upper = _norma_translacao(model, antebraco) or _UPPER_FALLBACK
    forearm = _norma_translacao(model, mao) or _FOREARM_FALLBACK

    return upper, forearm


def _norma_translacao(model: Model, grupo: str) -> float:
    """Norma da translação local do nó ``grupo`` (0.0 se ausente)."""
    no = model.find(grupo)

    if no is None:
        return 0.0

    tx, ty, tz = no.translation

    return sqrt(tx * tx + ty * ty + tz * tz)


def _ponta_mao_render(
    elevacao: float, azimute: float, cotovelo: float, upper: float, forearm: float
) -> Vec3:
    """FK do renderer (puro): ponta da mão relativa ao ombro, no espaço do corpo.

    ``R_arm = H(elevacao) · R(azimute)`` e o antebraço é ``R_arm · R(cotovelo)``
    (o cotovelo dobra no plano local, composto DEPOIS do ombro). Ângulos em graus.
    Este modelo bate com a FK medida do renderer dentro de ~0.002 unidades.
    """
    r_arm = _mul(_rh(radians(elevacao)), _rr(radians(azimute)))
    r_elbow = _rr(radians(cotovelo))

    upper_dir = _apply(r_arm, (1.0, 0.0, 0.0))
    fore_dir = _apply(r_arm, _apply(r_elbow, (1.0, 0.0, 0.0)))

    return (
        upper * upper_dir[0] + forearm * fore_dir[0],
        upper * upper_dir[1] + forearm * fore_dir[1],
        upper * upper_dir[2] + forearm * fore_dir[2],
    )


def posicao_mao_para_hpr(
    model: Model,
    lado: str,
    hpr_braco: Rotation3,
    hpr_antebraco: Rotation3,
    pose_base: dict[str, Rotation3] | None = None,  # noqa: ARG001  # compat de assinatura
) -> Vec3:
    """FK do renderer: ponta da mão RELATIVA ao ombro para um candidato de HPR.

    Recebe os ``Rotation3`` do braço/antebraço (como o renderer consome) e
    devolve a ponta da mão no espaço do corpo (+X dir, +Y cima, +Z frente). Para
    o lado esquerdo, desfaz o espelho (``espelhar_braco`` inverte Y e Z) antes
    de medir no referencial do braço direito, e espelha o X do resultado.
    """
    upper, forearm = comprimentos_braco(model, lado)

    if lado == "left":
        hpr_braco = espelhar_braco(hpr_braco)
        hpr_antebraco = espelhar_braco(hpr_antebraco)

    elevacao = degrees(hpr_braco.y)
    azimute = degrees(hpr_braco.z)
    cotovelo = degrees(hpr_antebraco.z)

    pos = _ponta_mao_render(elevacao, azimute, cotovelo, upper, forearm)

    if lado == "left":
        return (-pos[0], pos[1], pos[2])

    return pos


def _distancia(a: Vec3, b: Vec3) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _semente(
    alvo: Vec3, polo: Vec3, upper: float, forearm: float
) -> tuple[float, float, float]:
    """Ângulos iniciais (elevação, azimute, cotovelo) em graus.

    A dobra do cotovelo e a elevação vêm do solver planar (``solve_arm``) no
    plano frontal (horizontal = hipotenusa XY, downward = componente Y). O
    azimute inicial vem do arco-tangente do alvo no plano horizontal XZ.
    """
    ax, ay, az = alvo

    horizontal = sqrt(ax * ax + az * az)
    ombro_ang, cotovelo = solve_arm(horizontal, ay, upper, forearm)

    # Elevação inicial = ângulo do ombro no plano frontal (de +X para +Y).
    elevacao = ombro_ang

    # Azimute: z=+90 leva +X para -Z; para alcançar +Z (frente, az>0) precisa de
    # azimute negativo. Semeamos pelo arco-tangente do alvo no plano XZ.
    azimute = degrees(atan2(-az, max(1e-6, horizontal)))

    px, py, pz = polo  # noqa: F841  # polo fica como preferência; refino ajusta

    if pz < 0 and cotovelo > 0:
        cotovelo = -cotovelo

    return elevacao, azimute, cotovelo


def _resolver_angulos(
    alvo: Vec3, polo: Vec3, upper: float, forearm: float, tolerancia: float
) -> tuple[float, float, float]:
    """Descida por coordenada amortecida sobre (elevação, azimute, cotovelo).

    Usa a FK do renderer (``_ponta_mao_render``) como função objetivo (distância
    da ponta da mão ao alvo). Converge em poucas iterações para alvos dentro do
    alcance; nunca gera NaN (semente/clamp de alcance vêm de ``solve_arm``).
    """
    elev, azim, cot = _semente(alvo, polo, upper, forearm)

    def erro(e: float, a: float, c: float) -> float:
        return _distancia(_ponta_mao_render(e, a, c, upper, forearm), alvo)

    passo = 8.0
    melhor = erro(elev, azim, cot)

    for _ in range(_MAX_ITER):
        if melhor <= tolerancia:
            break

        melhorou = False

        for idx in range(3):
            for sinal in (1.0, -1.0):
                e, a, c = elev, azim, cot

                if idx == 0:
                    e += sinal * passo
                elif idx == 1:
                    a += sinal * passo
                else:
                    c += sinal * passo

                candidato = erro(e, a, c)

                if candidato < melhor - 1e-9:
                    elev, azim, cot = e, a, c
                    melhor = candidato
                    melhorou = True

        if not melhorou:
            passo *= 0.5

            if passo < 0.01:
                break

    return elev, azim, cot


def _hpr_dos_angulos(
    lado: str, elevacao: float, azimute: float, cotovelo: float
) -> tuple[Rotation3, Rotation3]:
    """Monta os ``Rotation3`` (radianos) do braço/antebraço a partir dos ângulos.

    Convenção do renderer: elevação → H (``Rotation3.y``), azimute → R
    (``Rotation3.z``) do braço; cotovelo → R (``Rotation3.z``) do antebraço. O
    lado esquerdo é o espelho (``espelhar_braco`` inverte Y e Z).
    """
    braco_dir = Rotation3(0.0, radians(elevacao), radians(azimute))
    antebraco_dir = Rotation3(0.0, 0.0, radians(cotovelo))

    if lado == "left":
        return espelhar_braco(braco_dir), espelhar_braco(antebraco_dir)

    return braco_dir, antebraco_dir


def braco_para(
    model: Model,
    lado: str,
    alvo_mao: Vec3,
    polo: Vec3 = (0.0, 0.0, 1.0),
    tolerancia: float = TOLERANCIA_PADRAO,
) -> dict[str, Rotation3]:
    """Resolve os HPR do braço para colocar a ponta da mão em ``alvo_mao``.

    Parameters
    ----------
    model:
        ``Model`` lido do glTF (fonte dos comprimentos reais; ``load_model``).
    lado:
        ``"right"`` ou ``"left"``.
    alvo_mao:
        Posição-alvo da ponta da mão RELATIVA ao ombro, no espaço do corpo
        (+X=direita, +Y=cima, +Z=frente), no referencial do observador. O lado
        esquerdo recebe o X no mesmo referencial (x<0 = à esquerda).
    polo:
        Direção preferida do cotovelo (desempata a dobra). Default +Z (frente).
    tolerancia:
        Distância aceitável (unidades do modelo) entre a mão resultante e o alvo.

    Returns
    -------
    ``dict`` ``grupo -> Rotation3`` (radianos) apenas para os grupos do braço do
    ``lado``. Alvo fora de alcance é clampado por ``solve_arm`` (nunca NaN).
    """
    if lado not in _GRUPOS_BRACO:
        raise ValueError(f"lado desconhecido: {lado!r} (use 'right' ou 'left')")

    upper, forearm = comprimentos_braco(model, lado)

    # Resolve sempre no referencial do braço DIREITO (espelho em X no esquerdo);
    # _hpr_dos_angulos aplica o espelho dos HPR no fim.
    alvo_solver = alvo_mao
    polo_solver = polo

    if lado == "left":
        alvo_solver = (-alvo_mao[0], alvo_mao[1], alvo_mao[2])
        polo_solver = (-polo[0], polo[1], polo[2])

    elev, azim, cot = _resolver_angulos(
        alvo_solver, polo_solver, upper, forearm, tolerancia
    )

    braco, antebraco = _GRUPOS_BRACO[lado]
    hpr_braco, hpr_antebraco = _hpr_dos_angulos(lado, elev, azim, cot)

    return {braco: hpr_braco, antebraco: hpr_antebraco}


def pose_repouso_bracos(model: Model) -> dict[str, Rotation3]:
    """HPR de repouso dos quatro grupos de braço, derivados do alvo de idle.

    Calculado a partir do ``Model``; os alvos vêm de ``arm_targets`` para manter
    uma única fonte de verdade. Devolve ``right-arm``/``ant-arm``/``left-arm``/
    ``ant-arm2``.
    """
    from sejoga.animacao.arm_targets import ALVO_IDLE

    pose: dict[str, Rotation3] = {}
    pose.update(braco_para(model, "right", ALVO_IDLE.alvo, ALVO_IDLE.polo))
    pose.update(braco_para(model, "left", ALVO_IDLE.alvo_espelhado(), ALVO_IDLE.polo))

    return pose
