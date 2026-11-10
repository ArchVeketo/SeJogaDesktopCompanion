"""Oráculo da cinemática: o FK puro precisa igualar o grafo de cena do Panda3D.

O Panda é a verdade do que o renderer aplica (``setHpr(base + pose)``). Estes
testes carregam o glTF real SEM janela/GPU (``gltf.load_model`` + ``NodePath``) e
comparam posição e orientação de cada grupo com ``cinematica``. Se o Panda ou o
loader não existirem o módulo é pulado com motivo (nunca passa vazio).
"""

from __future__ import annotations

import contextlib
import random
from math import radians

import pytest

from sejoga.nucleo import cinematica as cin
from sejoga.nucleo.recursos import resolve_model
from sejoga.nucleo.modelo import load_model
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rotation3

# Qt ANTES do Panda3D no mesmo processo (senão o QtCore carregado depois
# quebra com access violation nos testes de UI da mesma sessão do pytest).
with contextlib.suppress(ImportError):
    import PySide6.QtWidgets  # noqa: F401

core = pytest.importorskip("panda3d.core", reason="Panda3D indisponível")
gltf = pytest.importorskip("gltf", reason="panda3d-gltf indisponível")

#: Tolerância de posição/rotação contra o Panda (unidades do modelo).
TOLERANCIA = 1e-4
#: Quantidade de poses aleatórias do teste de varredura e semente fixa.
POSES_ALEATORIAS = 25
SEMENTE = 20260709
#: Amplitude máxima (graus) dos ângulos aleatórios (evita o gimbal em p=±90°).
AMPLITUDE_GRAUS = 70.0
#: Grupo que o teste usa para "centro do corpo" e "rosto".
GRUPO_CORPO, GRUPO_PORTA = "body", "door"


@pytest.fixture(scope="module")
def cena():
    core.loadPrcFileData("", "window-type none\naudio-library-name null")
    caminho = resolve_model()
    modelo = load_model(caminho)
    raiz = core.NodePath(gltf.load_model(str(caminho)))
    nos = {g: raiz.find(f"**/{g}") for g in ALL_GROUPS if modelo.find(g)}
    base = {g: n.getHpr() for g, n in nos.items()}
    # O nó raiz do asset (60) só gira o mascote de frente: medimos relativo a ele.
    referencia = nos[GRUPO_CORPO].getParent()

    return modelo, raiz, referencia, nos, base


def _aplicar_pose_panda(nos, base, pose):
    for grupo, no in nos.items():
        rot = pose.get(grupo, Rotation3())
        h0, p0, r0 = base[grupo]
        eh, ep, er = cin.BASE_ADICIONAL_GRAUS.get(grupo, (0.0, 0.0, 0.0))
        h, p, r = cin.graus(rot)
        no.setHpr(h0 + eh + h, p0 + ep + p, r0 + er + r)


def _origem_panda(no, referencia):
    p = no.getPos(referencia)

    return (p.x, p.y, p.z)


def _matriz_panda(no, referencia):
    """Rotação (linha-maior, vetor coluna) do nó relativa à referência."""
    m = no.getMat(referencia)
    # Panda usa vetor-linha: v' = v · M, logo a matriz coluna é a transposta.
    return tuple(m.getCell(c, r) for r in range(3) for c in range(3))


def _pose_aleatoria(rng):
    return {
        g: Rotation3(*(radians(rng.uniform(-AMPLITUDE_GRAUS, AMPLITUDE_GRAUS)) for _ in range(3)))
        for g in ALL_GROUPS
    }


def _comparar(cena, pose):
    modelo, _raiz, referencia, nos, base = cena
    _aplicar_pose_panda(nos, base, pose)

    for grupo, no in nos.items():
        rot, origem = cin.transformacao_no(modelo, grupo, pose)
        esperado = _origem_panda(no, referencia)
        medida = _matriz_panda(no, referencia)

        assert origem == pytest.approx(esperado, abs=TOLERANCIA), grupo
        assert rot == pytest.approx(medida, abs=TOLERANCIA), grupo


def test_repouso_igual_ao_panda(cena):
    _comparar(cena, {})


def test_poses_aleatorias_iguais_ao_panda(cena):
    rng = random.Random(SEMENTE)

    for _ in range(POSES_ALEATORIAS):
        _comparar(cena, _pose_aleatoria(rng))


def _punho(cena, lado, h=0.0, p=0.0, r=0.0):
    modelo, _raiz, _ref, nos, base = cena
    braco = "right-arm" if lado == "right" else "left-arm"
    pose = {braco: Rotation3(radians(p), radians(h), radians(r))}
    _aplicar_pose_panda(nos, base, pose)
    mao = "hand" if lado == "right" else "hand2"

    return cin.posicao_no(modelo, mao, pose)


def test_heading_positivo_do_braco_direito_vai_para_frente(cena):
    repouso = _punho(cena, "right")
    ponta = _punho(cena, "right", h=30)

    assert (ponta[1] - repouso[1]) > 0.0


def test_roll_positivo_do_braco_direito_baixa(cena):
    repouso = _punho(cena, "right")
    ponta = _punho(cena, "right", r=30)

    assert (ponta[2] - repouso[2]) < 0.0


def test_espelho_x_menos_y_menos_z_gera_imagem_espelhada_no_plano_sagital(cena):
    modelo = cena[0]
    rng = random.Random(SEMENTE)

    for _ in range(POSES_ALEATORIAS):
        x, y, z = (radians(rng.uniform(-AMPLITUDE_GRAUS, AMPLITUDE_GRAUS)) for _ in range(3))
        direito = Rotation3(x, y, z)
        pose_dir = {"right-arm": direito, "ant-arm": Rotation3(x, 0.0, z)}
        pose_esq = {
            "left-arm": cin.espelhar_rotacao(direito),
            "ant-arm2": cin.espelhar_rotacao(Rotation3(x, 0.0, z)),
        }
        mao_dir = cin.posicao_no(modelo, "hand", pose_dir)
        mao_esq = cin.posicao_no(modelo, "hand2", pose_esq)

        assert mao_esq == pytest.approx(cin.espelhar_ponto(mao_dir), abs=TOLERANCIA)


def test_frente_do_mascote_e_a_do_rosto(cena):
    _modelo, _raiz, referencia, nos, _base = cena
    centro = _origem_panda(nos[GRUPO_CORPO], referencia)
    caixa = nos[GRUPO_PORTA].getTightBounds(referencia)
    meio_y = (caixa[0].y + caixa[1].y) * 0.5

    assert meio_y > centro[1]  # o rosto (portinha) fica na frente (+Y) do corpo
