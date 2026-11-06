"""IK 3D de braço: posição-alvo da mão → HPR dos bones do rig (Python puro).

Causa raiz (comprovada visualmente): os bones de braço do Mário têm orientação
diagonal e nenhum eixo HPR isolado ergue o braço de forma limpa. Calibrar poses
por ângulo direto é inviável. A decisão foi usar IK: um gesto declara ONDE a mão
deve ficar no espaço (alvo relativo ao ombro) e este módulo calcula os HPR de
``right-arm``/``ant-arm`` (e o espelho ``left-arm``/``ant-arm2``) que levam a
ponta da mão até lá, respeitando a geometria REAL do modelo.

Decisão de projeto (ver PLAN): a conversão "ângulo do solver → HPR do bone" NÃO
assume eixos limpos nem usa fórmula fechada. Usa a cinemática direta (FK) pura
já existente (``rig_debug.posicao_acumulada``) como função objetivo e resolve
numericamente os HPR que colocam a mão no alvo. O solver planar ``solve_arm``
(``limb_ik.py``) fornece a semente (dobra do cotovelo + elevação no plano).

Geometria medida do glTF (ver ``tools/inspect_model.py`` e as translations dos
nós): a cadeia é ``right-arm → ant-arm → hand``, com translations locais em +X
(o eixo LONGO do braço é +X, não -Y). Comprimentos: upper ≈ 0.125, forearm ≈
0.15625, alcance ≈ 0.281. O ombro direito fica em ≈ (x=0.125, y=0.6875) no
espaço do modelo.

Convenção de eixos do mundo (verificada, MODEL_FACING_HEADING=180):
    +X = direita   +Y = cima   +Z = frente

DOFs usados (verificados por FK, ver probe no PLAN):
  - ``right-arm`` Z (roll)   → eleva o braço no plano frontal XY (Z=0 → +X,
    Z=90 → +Y reto para cima, Z=180 → -X). É a ELEVAÇÃO.
  - ``right-arm`` H (heading)→ gira o braço no plano horizontal XZ (avanço/recuo
    frente↔trás). É o AZIMUTE.
  - ``ant-arm`` Z (roll)     → dobra o cotovelo no plano do braço.
  - ``right-arm`` P (pitch)  → torção em torno do eixo longo (+X): NÃO move a
    ponta da mão. Fica em 0 (o IK não o usa para posição).

FRONTEIRA (igual a model.py/rig.py/rig_debug.py): Python puro. NÃO importa
Panda3D, Qt nem Win32. Só ``math``, ``sejoga.nucleo.model``/``rig`` e a FK pura
de ``sejoga.rig_mapa.rig_debug``.
"""

from __future__ import annotations

from math import radians, sqrt

from sejoga.animacao.limb_ik import solve_arm
from sejoga.animacao.rig_base import espelhar_braco
from sejoga.nucleo.model import Model
from sejoga.nucleo.rig import ALL_GROUPS, Rotation3
from sejoga.rig_mapa.rig_debug import posicao_acumulada

Vec3 = tuple[float, float, float]

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
_MAX_ITER = 240


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


def _pose_base() -> dict[str, Rotation3]:
    """Pose neutra (todos os grupos em zero) para medir a FK de um candidato."""
    return {g: Rotation3() for g in ALL_GROUPS}


def _offset_ombro(model: Model, lado: str) -> Vec3:
    """Posição de mundo da origem do ombro (grupo do braço) em repouso."""
    braco = _GRUPOS_BRACO[lado][0]
    pos = posicao_acumulada(_pose_base(), model)

    return pos.get(braco, (0.0, 0.0, 0.0))


def posicao_mao_para_hpr(
    model: Model,
    lado: str,
    hpr_braco: Rotation3,
    hpr_antebraco: Rotation3,
    pose_base: dict[str, Rotation3] | None = None,
) -> Vec3:
    """FK pura: ponta da mão RELATIVA ao ombro para um candidato de HPR.

    Monta uma pose com só o braço/antebraço do ``lado`` ajustados e mede, via
    ``rig_debug.posicao_acumulada``, a posição da origem de ``hand``/``hand2``
    (a ponta que ``flag_mao`` reporta) menos a origem do ombro. Assim o alvo é
    sempre comparado no referencial do ombro, coerente com a API pública.
    """
    braco, antebraco = _GRUPOS_BRACO[lado]
    mao = "hand" if lado == "right" else "hand2"

    pose = dict(pose_base) if pose_base is not None else _pose_base()
    pose[braco] = hpr_braco
    pose[antebraco] = hpr_antebraco

    posicoes = posicao_acumulada(pose, model)
    ombro = posicoes.get(braco, (0.0, 0.0, 0.0))
    ponta = posicoes.get(mao, ombro)

    return (ponta[0] - ombro[0], ponta[1] - ombro[1], ponta[2] - ombro[2])


def _distancia(a: Vec3, b: Vec3) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _semente(
    model: Model,
    lado: str,
    alvo: Vec3,
    polo: Vec3,
    upper: float,
    forearm: float,
) -> tuple[float, float, float]:
    """Ângulos iniciais (elevação α, azimute β, cotovelo γ) em graus.

    - A dobra do cotovelo (γ) e a elevação do braço vêm de ``solve_arm`` no
      PLANO do braço: horizontal = projeção do alvo no plano frontal (hipotenusa
      XY), downward = componente que afasta do ombro na elevação.
    - O azimute β é o ângulo do alvo no plano horizontal XZ (avanço/recuo); o
      polo só desempata o lado do cotovelo (mantido coerente com o solver 2D).
    """
    ax, ay, az = alvo

    # Elevação no plano frontal: Z=0 → +X (lateral), Z=90 → +Y (cima). O solver
    # planar resolve em torno de um eixo "horizontal/downward"; mapeamos a
    # hipotenusa frontal (sqrt(x²+z²)) como horizontal e y como "para cima".
    horizontal = sqrt(ax * ax + az * az)
    ombro_ang, cotovelo = solve_arm(horizontal, ay, upper, forearm)

    # right-arm Z mede a elevação a partir de +X (Z=0 lateral → Z=90 cima):
    # o ângulo do ombro no plano é medido de +X para +Y, exatamente o Z do bone.
    elevacao = ombro_ang

    # Azimute: Z do bone já cobriu o plano XY; H gira esse plano em torno de Y.
    # H>0 leva +X para -Z (frente, pois +Z=frente e H=90 → -Z). Para alcançar az
    # positivo (frente) precisamos de H negativo. Semeamos pelo arco-tangente.
    from math import atan2, degrees

    azimute = degrees(atan2(-az, max(1e-6, horizontal)))

    # O polo (direção do cotovelo) desempata a dobra: cotovelo positivo dobra
    # para frente, negativo para trás. Mantemos o sinal do solver e deixamos o
    # refinamento numérico ajustar; o polo fica como preferência inicial.
    px, py, pz = polo

    if pz < 0 and cotovelo > 0:
        cotovelo = -cotovelo

    return elevacao, azimute, cotovelo


def _resolver_angulos(
    model: Model,
    lado: str,
    alvo: Vec3,
    polo: Vec3,
    upper: float,
    forearm: float,
    tolerancia: float,
) -> tuple[float, float, float]:
    """Gauss-Newton amortecido por coordenada sobre (elevação, azimute, cotovelo).

    Usa a FK pura como função objetivo (distância da ponta da mão ao alvo).
    Derivadas por diferenças finitas; passo amortecido por eixo. Converge em
    poucas iterações para alvos dentro do alcance e nunca gera NaN (a semente e
    o clamp de alcance vêm de ``solve_arm``).
    """
    elev, azim, cot = _semente(model, lado, alvo, polo, upper, forearm)

    def erro(e: float, a: float, c: float) -> float:
        pos = _hpr_para_posicao(model, lado, e, a, c)
        return _distancia(pos, alvo)

    passo = 8.0  # graus por eixo no passo de coordenada
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
            # Refina o passo quando nenhuma direção melhora (vizinhança do ótimo).
            passo *= 0.5

            if passo < 0.02:
                break

    return elev, azim, cot


def _hpr_para_posicao(
    model: Model, lado: str, elevacao: float, azimute: float, cotovelo: float
) -> Vec3:
    """FK de um candidato (graus) → ponta da mão relativa ao ombro."""
    hpr_braco, hpr_antebraco = _hpr_dos_angulos(lado, elevacao, azimute, cotovelo)

    return posicao_mao_para_hpr(model, lado, hpr_braco, hpr_antebraco)


def _hpr_dos_angulos(
    lado: str, elevacao: float, azimute: float, cotovelo: float
) -> tuple[Rotation3, Rotation3]:
    """Monta os ``Rotation3`` (radianos) do braço/antebraço a partir dos ângulos.

    O braço direito usa elevação em Z (roll), azimute em H (heading = y) e o
    cotovelo em Z (roll) do antebraço. O lado esquerdo é o espelho
    (``espelhar_braco`` inverte Y e Z), coerente com o rig de repouso.
    """
    braco_dir = Rotation3(0.0, radians(azimute), radians(elevacao))
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
        ``Model`` lido do glTF (fonte da geometria real; ``load_model``).
    lado:
        ``"right"`` ou ``"left"``.
    alvo_mao:
        Posição-alvo da ponta da mão RELATIVA ao ombro, no espaço do modelo
        (+X=direita, +Y=cima, +Z=frente). Para o lado esquerdo, o X do alvo é
        interpretado no mesmo referencial do mundo (x>0 = direita do observador);
        passe o X espelhado se quiser a pose simétrica do direito.
    polo:
        Direção preferida do cotovelo (desempata a dobra). Default aponta para a
        frente (+Z).
    tolerancia:
        Distância aceitável (unidades do modelo) entre a mão resultante e o alvo.

    Returns
    -------
    ``dict`` ``grupo -> Rotation3`` (radianos) apenas para os grupos do braço do
    ``lado`` (``right-arm``/``ant-arm`` ou ``left-arm``/``ant-arm2``). Alvo fora
    de alcance é clampado pelo próprio ``solve_arm`` (nunca NaN).
    """
    if lado not in _GRUPOS_BRACO:
        raise ValueError(f"lado desconhecido: {lado!r} (use 'right' ou 'left')")

    upper, forearm = comprimentos_braco(model, lado)

    # Para o lado esquerdo, resolvemos no referencial do braço DIREITO (espelho
    # em X) e deixamos _hpr_dos_angulos aplicar o espelho dos HPR. Assim um alvo
    # à esquerda (x<0) vira um alvo à direita equivalente para o solver.
    alvo_solver = alvo_mao
    polo_solver = polo

    if lado == "left":
        alvo_solver = (-alvo_mao[0], alvo_mao[1], alvo_mao[2])
        polo_solver = (-polo[0], polo[1], polo[2])

    elev, azim, cot = _resolver_angulos(
        model, "right", alvo_solver, polo_solver, upper, forearm, tolerancia
    )

    braco, antebraco = _GRUPOS_BRACO[lado]
    hpr_braco, hpr_antebraco = _hpr_dos_angulos(lado, elev, azim, cot)

    return {braco: hpr_braco, antebraco: hpr_antebraco}


def pose_repouso_bracos(model: Model) -> dict[str, Rotation3]:
    """HPR de repouso dos quatro grupos de braço, derivados dos alvos de idle.

    Calculado uma vez a partir do ``Model``; os alvos vêm de ``arm_targets`` para
    manter uma única fonte de verdade das poses por alvo. Devolve
    ``right-arm``/``ant-arm``/``left-arm``/``ant-arm2``.
    """
    from sejoga.animacao.arm_targets import ALVO_IDLE

    pose: dict[str, Rotation3] = {}
    pose.update(braco_para(model, "right", ALVO_IDLE.alvo, ALVO_IDLE.polo))
    pose.update(braco_para(model, "left", ALVO_IDLE.alvo_espelhado(), ALVO_IDLE.polo))

    return pose
