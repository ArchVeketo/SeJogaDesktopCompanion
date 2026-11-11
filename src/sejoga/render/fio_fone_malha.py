"""Malha Panda3D do fio do fone (a física está em ``animacao.fio_corda``).

O asset rigado traz o fio desenhado (grupo ``fio do fone``, 8 planos). Ele
continua visível: cada vértice desses planos é preso ao ponto mais próximo da
corda simulada em repouso e, a cada quadro, recebe o deslocamento que esse
ponto da corda sofreu. Assim o fio mantém o visual do Blockbench e ganha a
física da corda (balanço, gravidade do mundo, colisão com corpo e braços).

Sem o grupo ``fio do fone`` (asset antigo) cai no tubo procedural de antes.
As âncoras (orelhas e aparelho de música) e os colisores (tronco, cabeça,
quadril, pernas/pés e braços) são lidos dos nós do rig a cada quadro.
"""

from __future__ import annotations

from itertools import pairwise

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexReader,
    GeomVertexRewriter,
    GeomVertexWriter,
    Mat4,
    NodePath,
    Point3,
    Texture,
    Vec3,
)

from sejoga.animacao import fio_tuning as tuning
from sejoga.animacao.colisao_bracos import COMPRIMENTO_MAO_U
from sejoga.animacao.fio_corda import FioFone, construir_tubo, indices_dos_tubos
from sejoga.animacao.primitivas_colisao import CaixaOrientada, Capsula

#: Grupo do fio desenhado no asset rigado (filho de ``head``).
NOME_GRUPO_FIO = "fio do fone"
#: Peça rígida do fio no GLTF LEGADO (plano do cabo, filho de um nó ``plane``).
NOME_PECA_RIGIDA = "mesh18"
#: Eixo para a câmera no referencial de ``model_np`` (a frente é -Y).
REFERENCIA_VISUAL = (0.0, -1.0, 0.0)
#: Caixas do corpo para o fio: (nó do rig, grupo/malha cujo volume vira a
#: caixa; vazio = nó inteiro, usado nos pés). O primeiro nome encontrado vale.
CAIXAS_DO_CORPO = (
    ("body", ("peitoral", "mesh20")),
    ("legs", ("pelvis", "mesh30")),
    ("head", ("Armario", "mesh0")),
    ("left-feet", ()),
    ("right-feet", ()),
)
#: Braços: (ombro, cotovelo, punho, sentido do osso da mão no eixo x).
BRACOS = (
    ("right-arm", "ant-arm", "hand", 1.0),
    ("left-arm", "ant-arm2", "hand2", -1.0),
)
ORIGEM = Point3(0, 0, 0)


def _achar_por_nome(raiz: NodePath, nome: str) -> NodePath:
    """Primeiro descendente com o nome exato (aceita espaços no nome)."""
    for no in raiz.findAllMatches("**"):
        if no.getName() == nome:
            return no
    return NodePath()


def ocultar_peca_rigida_do_fio(model_np: NodePath) -> bool:
    """Oculta o fio rígido LEGADO; o fio rigado do asset atual fica visível.

    Devolve ``True`` se encontrou e ocultou a peça legada (filha de um nó
    ``plane`` sob ``head``). No asset novo ``mesh18`` é outra peça (antena),
    então nada é ocultado quando existe o grupo ``fio do fone``.
    """
    if not _achar_por_nome(model_np, NOME_GRUPO_FIO).isEmpty():
        return False
    cabeca = model_np.find("**/head")
    peca = model_np.find(f"**/{NOME_PECA_RIGIDA}")

    if (
        cabeca.isEmpty()
        or peca.isEmpty()
        or not cabeca.isAncestorOf(peca)
        or peca.getParent().getName() != "plane"
    ):
        return False

    peca.stash()
    return True


def _gltf_para_panda(ponto: tuple[float, float, float]) -> Point3:
    """Converta ponto local do GLTF (y para cima) em local do Panda3D (z para cima)."""
    x, y, z = ponto
    return Point3(x, -z, y)


def _ponto_mais_proximo(
    ponto: Vec3, cadeias: list[list[Vec3]]
) -> tuple[int, int, float]:
    """(cadeia, segmento, t) do ponto da corda mais próximo de ``ponto``."""
    melhor = (0, 0, 0.0)
    melhor_d2 = float("inf")
    for c, pontos in enumerate(cadeias):
        for k, (a, b) in enumerate(pairwise(pontos)):
            ab = b - a
            l2 = ab.lengthSquared()
            t = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, (ponto - a).dot(ab) / l2))
            d2 = (a + ab * t - ponto).lengthSquared()
            if d2 < melhor_d2:
                melhor_d2, melhor = d2, (c, k, t)
    return melhor


class MalhaFioFone:
    """Fio do fone: planos do asset (ou tubo legado) guiados pela corda simulada."""

    def __init__(self, renderer) -> None:
        """Monta a corda, assenta sob a gravidade e liga a malha do fio a ela."""
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
        self._pecas_asset: list[tuple[GeomVertexData, list, list]] = []
        if not self._ligar_fio_do_asset(renderer.outline_np):
            self._criar_malha(renderer.outline_np)
        self._escrever_vertices()

    # ------------------------------------------------------------------ #
    # Fio desenhado no asset
    # ------------------------------------------------------------------ #
    def _ligar_fio_do_asset(self, contorno_np: NodePath) -> bool:
        """Prende os vértices dos planos de ``fio do fone`` à corda em repouso."""
        grupo = _achar_por_nome(self._model_np, NOME_GRUPO_FIO)
        if grupo.isEmpty():
            return False
        grupo_contorno = (
            _achar_por_nome(contorno_np, NOME_GRUPO_FIO)
            if contorno_np is not None
            else NodePath()
        )
        malhas = list(grupo.findAllMatches("**/+GeomNode"))
        malhas_contorno = (
            list(grupo_contorno.findAllMatches("**/+GeomNode"))
            if not grupo_contorno.isEmpty()
            else []
        )
        if not malhas:
            return False
        self._corda_repouso = [
            [Vec3(*p) for p in pontos] for pontos in self._fio.pontos_das_cadeias()
        ]
        identidade = Mat4.identMat()
        for indice, malha in enumerate(malhas):
            para_modelo = malha.getMat(self._model_np)
            no_geom = malha.node()
            dados = no_geom.modifyGeom(0).modifyVertexData()
            leitor = GeomVertexReader(dados, "vertex")
            leitor_n = GeomVertexReader(dados, "normal")
            repouso: list[Vec3] = []
            normais: list[Vec3] = []
            while not leitor.isAtEnd():
                repouso.append(Vec3(para_modelo.xformPoint(leitor.getData3())))
                n = Vec3(para_modelo.xformVec(leitor_n.getData3()))
                n.normalize()
                normais.append(n)
            ligacoes = [_ponto_mais_proximo(p, self._corda_repouso) for p in repouso]
            # Assa a pose de repouso nos vértices: a peça passa a viver direto
            # no referencial de model_np (a corda já segue cabeça e corpo).
            escritor_n = GeomVertexRewriter(dados, "normal")
            for n in normais:
                escritor_n.setData3(n)
            malha.wrtReparentTo(self._model_np)
            malha.setMat(identidade)
            malha.setCollideMask(0)
            if indice < len(malhas_contorno):
                contorno = malhas_contorno[indice]
                contorno.node().modifyGeom(0).setVertexData(dados)
                contorno.wrtReparentTo(contorno_np)
                contorno.setMat(identidade)
            self._pecas_asset.append((dados, repouso, ligacoes))
        return True

    def _escrever_fio_do_asset(self) -> None:
        agora = [[Vec3(*p) for p in pontos] for pontos in self._fio.pontos_das_cadeias()]
        for dados, repouso, ligacoes in self._pecas_asset:
            escritor = GeomVertexRewriter(dados, "vertex")
            for p, (c, k, t) in zip(repouso, ligacoes, strict=True):
                a0, b0 = self._corda_repouso[c][k], self._corda_repouso[c][k + 1]
                a1, b1 = agora[c][k], agora[c][k + 1]
                delta = (a1 + (b1 - a1) * t) - (a0 + (b0 - a0) * t)
                escritor.setData3(p + delta)

    # ------------------------------------------------------------------ #
    # Leitura da pose
    # ------------------------------------------------------------------ #
    @staticmethod
    def _malha_da_caixa(
        no: NodePath | None, nomes_malha: tuple[str, ...]
    ) -> NodePath | None:
        """Malha que define a caixa; sem nomes usa o nó inteiro."""
        if no is None or not nomes_malha:
            return no

        for nome in nomes_malha:
            achado = no.find(f"**/{nome}")
            if not achado.isEmpty():
                return achado
        return None

    def _medir_caixas(self, nos) -> list[tuple[NodePath, Vec3, Vec3]]:
        caixas = []

        for nome_no, nomes_malha in CAIXAS_DO_CORPO:
            no = nos.get(nome_no)
            malha = self._malha_da_caixa(no, nomes_malha)
            limites = (
                malha.getTightBounds(no)
                if malha is not None and not malha.isEmpty()
                else None
            )

            if limites:
                caixas.append((no, Vec3(limites[0]), Vec3(limites[1])))

        return caixas

    def _ancoras(self) -> tuple[tuple[float, float, float], ...]:
        x, y, z = tuning.ANCORA_ORELHA_U
        esquerda = self._model_np.getRelativePoint(
            self._cabeca, _gltf_para_panda((-x, y, z))
        )
        direita = self._model_np.getRelativePoint(
            self._cabeca, _gltf_para_panda((x, y, z))
        )
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

            for indice, base in enumerate(
                (Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))
            ):
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
                tuple(self._model_np.getRelativePoint(no, ORIGEM))
                for no in (ombro, cotovelo, punho)
            ]
            ponta = self._model_np.getRelativePoint(
                punho, Point3(sentido * COMPRIMENTO_MAO_U, 0, 0)
            )
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
        if self._pecas_asset:
            self._escrever_fio_do_asset()
            return
        self._escritor_vertices.setRow(0)
        self._escritor_normais.setRow(0)

        for pontos in self._fio.pontos_das_cadeias():
            vertices, normais = construir_tubo(
                pontos, REFERENCIA_VISUAL, tuning.RAIO_VISUAL_FIO_U
            )

            for vertice, normal in zip(vertices, normais, strict=True):
                self._escritor_vertices.setData3(*vertice)
                self._escritor_normais.setData3(*normal)

    def atualizar(self, dt: float) -> None:
        """Avança a corda ``dt`` segundos e reescreve a malha."""
        caixas, capsulas = self._colisores()
        self._fio.atualizar(dt, self._ancoras(), self._gravidade(), caixas, capsulas)  # type: ignore[arg-type]
        self._escrever_vertices()
