"""Anti-atravessamento dos braços: alvos livres, correção e checagem nas malhas.

As cápsulas usam a FK do grafo de cena (``cinematica`` == Panda). A checagem
independente (``test_vertices_...``) lê os VÉRTICES reais das malhas do braço no
Panda3D e mede quanto entram nas caixas do tronco/short.
"""

from __future__ import annotations

import contextlib
from math import radians

import pytest

from sejoga.animacao import colisao_bracos as cb
from sejoga.animacao import ik_bracos
from sejoga.animacao.alvos_bracos import ALVOS
from sejoga.animacao.resolvedor_poses import PoseResolver
from sejoga.nucleo.esqueleto import Rotation3
from sejoga.nucleo.modelo import load_model
from sejoga.nucleo.recursos import resolve_model

#: Quadros dados ao resolvedor para corrigir e para relaxar.
QUADROS_CORRECAO = 60
QUADROS_RELAXAMENTO = 240
#: Pose que enfia o braço direito no tronco (cruza o peito).
POSE_INVASORA = {
    "right-arm": Rotation3(0.0, radians(80.0), radians(30.0)),
    "ant-arm": Rotation3(0.0, 0.0, radians(90.0)),
}


@pytest.fixture(scope="module")
def modelo():
    return load_model(resolve_model())


def _pose_simetrica(modelo, nome):
    alvo = ALVOS[nome]
    pose = {}
    pose.update(ik_bracos.braco_para(modelo, "right", alvo.alvo, alvo.polo))
    pose.update(ik_bracos.braco_para(modelo, "left", alvo.alvo_espelhado(), alvo.polo))

    return pose


@pytest.mark.parametrize("nome", sorted(ALVOS))
def test_alvos_nao_atravessam_o_corpo(modelo, nome):
    pose = _pose_simetrica(modelo, nome)

    for lado in ("right", "left"):
        assert cb.penetracao_do_lado(modelo, lado, pose) <= cb.FOLGA_PENETRACAO_U, lado


def test_t_pose_do_asset_nao_conta_como_colisao(modelo):
    assert cb.penetracao_do_lado(modelo, "right", {}) <= cb.FOLGA_PENETRACAO_U


def test_resolvedor_tira_o_braco_do_tronco_e_relaxa_depois(modelo):
    resolvedor = cb.ResolvedorBracos(modelo)
    invasora = dict(_pose_simetrica(modelo, "idle"), **POSE_INVASORA)

    assert cb.penetracao_do_lado(modelo, "right", invasora) > cb.FOLGA_PENETRACAO_U

    for _ in range(QUADROS_CORRECAO):
        corrigida = resolvedor.resolver(invasora)

    assert cb.penetracao_do_lado(modelo, "right", corrigida) <= cb.FOLGA_PENETRACAO_U
    # O lado esquerdo (já livre) não é tocado.
    assert corrigida["left-arm"] == invasora["left-arm"]

    livre = _pose_simetrica(modelo, "idle")
    for _ in range(QUADROS_RELAXAMENTO):
        final = resolvedor.resolver(livre)

    assert final["right-arm"] == pytest.approx(livre["right-arm"], abs=1e-3)


def test_pose_resolver_aplica_o_anti_atravessamento_com_model(modelo):
    resolver = PoseResolver()
    invasora = dict(_pose_simetrica(modelo, "idle"), **POSE_INVASORA)

    for _ in range(QUADROS_CORRECAO):
        pose = resolver.resolver(1 / 60, invasora, model=modelo)

    assert cb.penetracao_do_lado(modelo, "right", pose) <= cb.FOLGA_PENETRACAO_U


def test_vertices_das_malhas_do_braco_nao_entram_no_tronco(modelo):
    """Checagem independente das cápsulas: vértices reais (Panda) vs caixas medidas."""
    with contextlib.suppress(ImportError):
        import PySide6.QtWidgets  # noqa: F401  # Qt antes do Panda

    core = pytest.importorskip("panda3d.core")
    gltf = pytest.importorskip("gltf")
    core.loadPrcFileData("", "window-type none\naudio-library-name null")
    from sejoga.nucleo.cinematica import BASE_ADICIONAL_GRAUS, graus

    raiz = core.NodePath(gltf.load_model(str(resolve_model())))
    referencia = raiz.find("**/legs").getParent()
    caixas = tuple(cb.CAIXAS_CORPO.values())
    # Mais fundo que a meia-espessura = o NÚCLEO do braço entrou no volume.
    limite = cb.MEIA_ESPESSURA_BRACO_U + cb.FOLGA_PENETRACAO_U

    for nome in sorted(ALVOS):  # noqa: PLR1702  # TODO convenção: teste de cenário longo; dividir em lote próprio
        pose = _pose_simetrica(modelo, nome)

        for grupo, rot in pose.items():
            no = raiz.find(f"**/{grupo}")
            h0, p0, r0 = no.getHpr()
            eh, ep, er = BASE_ADICIONAL_GRAUS.get(grupo, (0.0, 0.0, 0.0))
            h, p, r = graus(rot)
            no.setHpr(h0 + eh + h, p0 + ep + p, r0 + er + r)

        for grupo in ("ant-arm", "hand", "ant-arm2", "hand2"):
            for geom_np in raiz.find(f"**/{grupo}").findAllMatches("**/+GeomNode"):
                for vertice in _vertices(core, geom_np, referencia):
                    for caixa in caixas:
                        assert _profundidade(vertice, caixa) <= limite, (nome, grupo)

        raiz = core.NodePath(gltf.load_model(str(resolve_model())))
        referencia = raiz.find("**/legs").getParent()


def _vertices(core, geom_np, referencia):
    transform = geom_np.getMat(referencia)
    geom_node = geom_np.node()

    for i in range(geom_node.getNumGeoms()):
        leitor = core.GeomVertexReader(geom_node.getGeom(i).getVertexData(), "vertex")

        while not leitor.isAtEnd():
            yield transform.xformPoint(leitor.getData3())


def _profundidade(ponto, caixa):
    """Quanto o ponto está DENTRO da caixa alinhada (0 se fora)."""
    folgas = [
        meia - abs(ponto[i] - caixa.centro[i]) for i, meia in enumerate(caixa.meias_dim)
    ]

    return max(0.0, min(folgas))
