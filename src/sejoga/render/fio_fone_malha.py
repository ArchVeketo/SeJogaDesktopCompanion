"""Malha Panda3D da corda do fio do fone (a física está em ``animacao.fio_corda``).

O fio rígido do GLTF (``mesh18``) é ocultado em tempo de execução, sem editar o
asset, e no lugar entra um tubo de seção quadrada que segue a corda simulada.
As âncoras (orelhas e aparelho de música) e os colisores (tronco, cabeça,
quadril e braços) são lidos dos nós do rig a cada quadro, então o fio acompanha
qualquer pose, incluindo o arraste pendurado (a gravidade vem do mundo).
"""

from __future__ import annotations

from itertools import pairwise

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexRewriter,
    GeomVertexWriter,
    NodePath,
    Point3,
    Texture,
    Vec3,
)

from sejoga.animacao import fio_tuning as tuning
from sejoga.animacao.colisao_bracos import COMPRIMENTO_MAO_U
from sejoga.animacao.fio_corda import FioFone, construir_tubo, indices_dos_tubos
from sejoga.animacao.primitivas_colisao import CaixaOrientada, Capsula

#: Peça rígida do fio no GLTF (plano do cabo do fone), filha de ``head``.
NOME_PECA_RIGIDA = "mesh18"
#: Eixo para a câmera no referencial de ``model_np`` (a frente é -Y).
REFERENCIA_VISUAL = (0.0, -1.0, 0.0)
#: Caixas do corpo para o fio: (nó do rig, malha cujo volume vira a caixa).
CAIXAS_DO_CORPO = (("body", "mesh20"), ("legs", "mesh30"), ("head", "mesh0"))
#: Braços: (ombro, cotovelo, punho, sentido do osso da mão no eixo x).
BRACOS = (
    ("right-arm", "ant-arm", "hand", 1.0),
    ("left-arm", "ant-arm2", "hand2", -1.0),
)
ORIGEM = Point3(0, 0, 0)


def ocultar_peca_rigida_do_fio(model_np: NodePath) -> bool:
    """Oculta a peça rígida do fio; devolve ``True`` se a encontrou sob ``head``."""
    cabeca = model_np.find("**/head")
    peca = model_np.find(f"**/{NOME_PECA_RIGIDA}")

    if cabeca.isEmpty() or peca.isEmpty() or not cabeca.isAncestorOf(peca):
        return False

    peca.stash()
    return True


def _gltf_para_panda(ponto: tuple[float, float, float]) -> Point3:
    """Converta ponto local do GLTF (y para cima) em local do Panda3D (z para cima)."""
    x, y, z = ponto
    return Point3(x, -z, y)


class MalhaFioFone:
    """Corda simulada do fio do fone, com malha e contorno no Panda3D."""

    def __init__(self, renderer) -> None:
        """Monta a corda, assenta sob a gravidade e cria a malha e o contorno."""
        self._model_np: NodePath = renderer.model_np
        self._render: NodePath = renderer.showbase.render
        nos = renderer._rig_nodes
        self._cabeca: NodePath = nos["head"]
        self._corpo: NodePath = nos["body"]
        self._caixas_locais = self._medir_caixas(nos)
        self._bracos = [
            (nos[ombro], nos[cotovelo], nos[punho], sentido)
            for ombro, cotovelo, punho, sentido in BRACOS
            if {ombro, cotovelo, punho} <= nos.keys()
        ]
        ancoras = self._ancoras()
        self._fio = FioFone(ancoras)
        self._fio.assentar(ancoras, self._gravidade(), *self._colisores())
        self._criar_malha(renderer.outline_np)
        self._escrever_vertices()

    # ------------------------------------------------------------------ #
    # Leitura da pose
    # ------------------------------------------------------------------ #
    def _medir_caixas(self, nos) -> list[tuple[NodePath, Vec3, Vec3]]:
        caixas = []

        for nome_no, nome_malha in CAIXAS_DO_CORPO:
            no = nos.get(nome_no)
            malha = no.find(f"**/{nome_malha}") if no is not None else None
            limites = malha.getTightBounds(no) if malha is not None and not malha.isEmpty() else None

            if limites:
                caixas.append((no, Vec3(limites[0]), Vec3(limites[1])))

        return caixas

    def _ancoras(self) -> tuple[tuple[float, float, float], ...]:
        x, y, z = tuning.ANCORA_ORELHA_U
        esquerda = self._model_np.getRelativePoint(self._cabeca, _gltf_para_panda((-x, y, z)))
        direita = self._model_np.getRelativePoint(self._cabeca, _gltf_para_panda((x, y, z)))
        aparelho = self._model_np.getRelativePoint(
            self._corpo, _gltf_para_panda(tuning.ANCORA_APARELHO_U)
        )
        return (tuple(esquerda), tuple(direita), tuple(aparelho))

    def _gravidade(self) -> tuple[float, float, float]:
        """Vetor unitário "para baixo do mundo" no referencial de ``model_np``."""
        baixo = self._model_np.getRelativeVector(self._render, Vec3(0, 0, -1))
        baixo.normalize()
        return tuple(baixo)

    def _colisores(self) -> tuple[list[CaixaOrientada], list[Capsula]]:
        return self._caixas_atuais(), self._capsulas_atuais()

    def _caixas_atuais(self) -> list[CaixaOrientada]:
        caixas = []

        for no, minimo, maximo in self._caixas_locais:
            centro = self._model_np.getRelativePoint(no, (minimo + maximo) * 0.5)
            meias = (maximo - minimo) * 0.5
            eixos = []
            meias_reais = []

            for indice, base in enumerate((Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))):
                vetor = self._model_np.getRelativeVector(no, base)
                escala = vetor.length()
                vetor.normalize()
                eixos.append(tuple(vetor))
                meias_reais.append(meias[indice] * escala)

            caixas.append(
                CaixaOrientada(tuple(centro), tuple(eixos), tuple(meias_reais))  # type: ignore[arg-type]
            )

        return caixas

    def _capsulas_atuais(self) -> list[Capsula]:
        capsulas = []

        for ombro, cotovelo, punho, sentido in self._bracos:
            pontos = [
                tuple(self._model_np.getRelativePoint(no, ORIGEM)) for no in (ombro, cotovelo, punho)
            ]
            ponta = self._model_np.getRelativePoint(punho, Point3(sentido * COMPRIMENTO_MAO_U, 0, 0))
            pontos.append(tuple(ponta))

            for a, b in pairwise(pontos):
                capsulas.append(Capsula(a, b, tuning.RAIO_BRACO_PARA_FIO_U))  # type: ignore[arg-type]

        return capsulas

    # ------------------------------------------------------------------ #
    # Malha
    # ------------------------------------------------------------------ #
    def _criar_malha(self, contorno_np: NodePath) -> None:
        quantidades = [len(cadeia) for cadeia in self._fio.cadeias]
        total_vertices = sum((q - 1) * 16 for q in quantidades)
        dados = GeomVertexData("fio-fone", GeomVertexFormat.getV3n3c4(), Geom.UHDynamic)
        dados.setNumRows(total_vertices)
        cores = GeomVertexWriter(dados, "color")

        for _ in range(total_vertices):
            cores.addData4f(*tuning.COR_FIO)

        triangulos = GeomTriangles(Geom.UHStatic)

        for a, b, c in indices_dos_tubos(quantidades):
            triangulos.addVertices(a, b, c)

        triangulos.closePrimitive()
        geom = Geom(dados)
        geom.addPrimitive(triangulos)
        no_geom = GeomNode("fio-fone")
        no_geom.addGeom(geom)
        self._malha = self._model_np.attachNewNode(no_geom)
        self._malha.setTwoSided(True)
        self._malha.setCollideMask(0)
        # Textura opaca real: o shader do contorno descarta pelo alpha dela.
        branca = Texture("fio-fone-opaca")
        branca.setup2dTexture(1, 1, Texture.TUnsignedByte, Texture.FRgba)
        branca.setRamImage(bytes((255, 255, 255, 255)))
        self._malha.setTexture(branca, 1)
        self._contorno = self._malha.copyTo(contorno_np)
        self._contorno.setName("fio-fone-contorno")
        # As duas cascas compartilham o mesmo GeomVertexData: escrever uma vez.
        self._escritor_vertices = GeomVertexRewriter(dados, "vertex")
        self._escritor_normais = GeomVertexRewriter(dados, "normal")

    def _escrever_vertices(self) -> None:
        self._escritor_vertices.setRow(0)
        self._escritor_normais.setRow(0)

        for pontos in self._fio.pontos_das_cadeias():
            vertices, normais = construir_tubo(pontos, REFERENCIA_VISUAL, tuning.RAIO_VISUAL_FIO_U)

            for vertice, normal in zip(vertices, normais, strict=True):
                self._escritor_vertices.setData3(*vertice)
                self._escritor_normais.setData3(*normal)

    def atualizar(self, dt: float) -> None:
        """Avança a corda ``dt`` segundos e reescreve a malha."""
        caixas, capsulas = self._colisores()
        self._fio.atualizar(dt, self._ancoras(), self._gravidade(), caixas, capsulas)  # type: ignore[arg-type]
        self._escrever_vertices()
