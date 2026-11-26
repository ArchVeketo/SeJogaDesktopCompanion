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
    Vec3,
)

from sejoga.animacao import fio_corda as tuning
from sejoga.animacao.colisao_bracos import COMPRIMENTO_MAO_U
from sejoga.animacao.fio_corda import (
    FioFone,
    construir_tubo,
    empurrar_ponto_de_caixa,
    indices_dos_tubos,
)
from sejoga.animacao.primitivas_colisao import CaixaOrientada, Capsula

from sejoga.render.sprites_efeitos import textura_acabamento

#: Grupo do fio desenhado no asset rigado (filho de ``head``).
NOME_GRUPO_FIO = "fio do fone"
#: Peça rígida do fio no GLTF LEGADO (plano do cabo, filho de um nó ``plane``).
NOME_PECA_RIGIDA = "mesh18"
#: Eixo para a câmera no referencial de ``model_np`` (a frente é -Y).
REFERENCIA_VISUAL = (0.0, -1.0, 0.0)
#: Caixas do corpo para o fio: (nó do rig, grupo/malha específica cujo volume vira
#: a caixa; vazio = GeomNodes diretos do nó). Usar malhas específicas evita que
#: ``peitoral.getTightBounds(body)`` englobe cabeça e braços reparentados pelo
#: ``FlexibleRig`` (o que gerava uma caixa gigante e ejetava o fio para as costas).
CAIXAS_DO_CORPO = (
    ("peitoral", ("mesh28", "mesh20")),
    ("abdomen", ("mesh27",)),
    ("pelvis", ("mesh45",)),
    ("shoulder", ("mesh29",)),
    ("shoulder2", ("mesh37",)),
    ("coxa-direita", ("mesh46",)),
    ("coxa-esquerda", ("mesh49",)),
    ("head", ("Armario", "mesh0")),
    ("fone-direito", ()),
    ("fone-esquerdo", ()),
    ("canela-direita", ()),
    ("canela-esquerda", ()),
    ("left-feet", ()),
    ("right-feet", ()),
)
#: Subconjunto de colisores do tronco/pélvis/coxas usado também para blindar a malha do asset.
_NOMES_CAIXAS_TRONCO = frozenset(
    ("peitoral", "abdomen", "pelvis", "calca-autoral", "coxa-direita", "coxa-esquerda")
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
        self._peitoral: NodePath = nos.get("peitoral", self._corpo)
        # Ancoragem v2.0: prende cada ponta diretamente ao fone real e ao abdômen/walkman
        # mantendo a posição exata de repouso, mas acompanhando o balanço dos fones e da cintura.
        self._no_fone_esq: NodePath = nos.get("fone-esquerdo", self._cabeca)
        self._no_fone_dir: NodePath = nos.get("fone-direito", self._cabeca)
        self._no_aparelho: NodePath = nos.get("abdomen", nos.get("cintura", self._corpo))
        x, y, z = tuning.ANCORA_ORELHA_U
        self._local_fone_esq = self._no_fone_esq.getRelativePoint(
            self._cabeca, _gltf_para_panda((-x, y, z))
        )
        self._local_fone_dir = self._no_fone_dir.getRelativePoint(
            self._cabeca, _gltf_para_panda((x, y, z))
        )
        self._local_aparelho = self._no_aparelho.getRelativePoint(
            self._corpo, _gltf_para_panda(tuning.ANCORA_APARELHO_U)
        )
        self._caixas_locais = self._medir_caixas(nos)
        self._caixas_tronco_atuais: list[CaixaOrientada] = []
        self._bracos = [
            (nos[ombro], nos[cotovelo], nos[punho], sentido)
            for ombro, cotovelo, punho, sentido in BRACOS
            if {ombro, cotovelo, punho} <= nos.keys()
        ]
        ancoras = self._ancoras()
        self._fio = FioFone(ancoras)
        caixas_ini, capsulas_ini = self._colisores()
        frente_ini = self._frente_modelo()
        self._fio.assentar(
            ancoras, self._gravidade(), caixas_ini, capsulas_ini, frente_modelo=frente_ini
        )
        self._malha: NodePath | None = None
        self._contorno: NodePath | None = None
        self._nos_fio: list[NodePath] = []
        self._visivel = True
        self._pecas_asset: list[tuple[GeomVertexData, list, list, GeomVertexRewriter]] = []
        self._tempo_parado: float = 0.0
        self._ultima_chave_parada: tuple | None = None
        if not self._ligar_fio_do_asset(renderer.outline_np):
            self._criar_malha(renderer.outline_np)
        self._escrever_vertices(frente=frente_ini)

    # ------------------------------------------------------------------ #
    # Fio desenhado no asset
    # ------------------------------------------------------------------ #
    def _ligar_malha_a_corda(self, malha, identidade):
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
        # Remove folga traseira (+Y em model_np) já presente no asset em repouso.
        repouso_limpo: list[Vec3] = []
        for p, (c, k, t) in zip(repouso, ligacoes, strict=True):
            a = self._corda_repouso[c][k]
            b = self._corda_repouso[c][k + 1]
            p_corda = a + (b - a) * t
            if p.y - p_corda.y > 0.008:
                repouso_limpo.append(Vec3(p.x, p_corda.y + 0.008, p.z))
            else:
                repouso_limpo.append(p)
        # Assa a pose de repouso nos vértices: a peça passa a viver direto
        # no referencial de model_np (a corda já segue cabeça e corpo).
        escritor_n = GeomVertexRewriter(dados, "normal")
        for n in normais:
            escritor_n.setData3(n)
        malha.wrtReparentTo(self._model_np)
        malha.setMat(identidade)
        malha.setCollideMask(0)
        return dados, repouso_limpo, ligacoes

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
            dados, repouso, ligacoes = self._ligar_malha_a_corda(malha, identidade)
            self._nos_fio.append(malha)
            if indice < len(malhas_contorno):
                contorno = malhas_contorno[indice]
                contorno.node().modifyGeom(0).setVertexData(dados)
                contorno.wrtReparentTo(contorno_np)
                contorno.setMat(identidade)
                self._nos_fio.append(contorno)
            self._pecas_asset.append((dados, repouso, ligacoes, GeomVertexRewriter(dados, "vertex")))
        return True

    def _escrever_fio_do_asset(self, frente: tuple[float, float, float] | None = None) -> None:
        agora = self._fio.pontos_das_cadeias()
        deltas: list[list[tuple[float, float, float, float, float, float]]] = []
        for c, pontos in enumerate(agora):
            repouso_c = self._corda_repouso[c]
            seg_deltas: list[tuple[float, float, float, float, float, float]] = []
            for k in range(len(pontos) - 1):
                a0 = repouso_c[k]
                b0 = repouso_c[k + 1]
                a1x, a1y, a1z = pontos[k]
                b1x, b1y, b1z = pontos[k + 1]
                dax = a1x - a0.x
                day = a1y - a0.y
                daz = a1z - a0.z
                ddx = (b1x - b0.x) - dax
                ddy = (b1y - b0.y) - day
                ddz = (b1z - b0.z) - daz
                seg_deltas.append((dax, day, daz, ddx, ddy, ddz))
            deltas.append(seg_deltas)
        caixas_tronco = self._caixas_tronco_atuais
        frente_atual = frente if frente is not None else self._frente_modelo()
        for _dados, repouso, ligacoes, escritor in self._pecas_asset:
            escritor.setRow(0)
            escrever = escritor.setData3
            for p, (c, k, t) in zip(repouso, ligacoes, strict=True):
                dax, day, daz, ddx, ddy, ddz = deltas[c][k]
                vx = p.x + dax + ddx * t
                vy = p.y + day + ddy * t
                vz = p.z + daz + ddz * t
                if caixas_tronco:
                    ponto_proj = (vx, vy, vz)
                    for cx in caixas_tronco:
                        ponto_proj = empurrar_ponto_de_caixa(
                            ponto_proj, cx, 0.008, preferir_frente=True, frente_modelo=frente_atual
                        )
                    vx, vy, vz = ponto_proj
                escrever(vx, vy, vz)
        for no in self._nos_fio:
            if not no.isEmpty() and no.node() is not None:
                no.node().markInternalBoundsStale()

    def _frente_modelo(self) -> tuple[float, float, float]:
        """Direção frontal atual do tórax em ``model_np`` (acompanha giros de 180°)."""
        v = self._model_np.getRelativeVector(self._peitoral, Vec3(0, 1, 0))
        if v.lengthSquared() < 1e-8:
            return REFERENCIA_VISUAL
        v.normalize()
        return (float(v.x), float(v.y), float(v.z))

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

    @staticmethod
    def _limites_sem_antena(no: NodePath) -> tuple[Vec3, Vec3] | None:
        """Limites locais ao ``no`` ignorando qualquer subárvore ``antena-*``."""
        min_x = min_y = min_z = 1e9
        max_x = max_y = max_z = -1e9
        achou = False
        for geom_np in no.findAllMatches("**/+GeomNode"):
            cur = geom_np
            tem_antena = False
            while not cur.isEmpty() and cur != no:
                if cur.getName().startswith("antena"):
                    tem_antena = True
                    break
                cur = cur.getParent()
            if tem_antena:
                continue
            limites = geom_np.getTightBounds(no)
            if not limites:
                continue
            achou = True
            lo, hi = limites
            min_x, min_y, min_z = min(min_x, float(lo.x)), min(min_y, float(lo.y)), min(min_z, float(lo.z))
            max_x, max_y, max_z = max(max_x, float(hi.x)), max(max_y, float(hi.y)), max(max_z, float(hi.z))
        return (Vec3(min_x, min_y, min_z), Vec3(max_x, max_y, max_z)) if achou else None

    def _medir_caixas(self, nos) -> list[tuple[str, NodePath, Vec3, Vec3]]:
        caixas: list[tuple[str, NodePath, Vec3, Vec3]] = []

        for nome_no, nomes_malha in CAIXAS_DO_CORPO:
            no = nos.get(nome_no)
            if no is not None and not no.isEmpty() and not nomes_malha and nome_no.startswith("fone-"):
                limites = self._limites_sem_antena(no)
            else:
                malha = self._malha_da_caixa(no, nomes_malha)
                limites = (
                    malha.getTightBounds(no)
                    if malha is not None and not malha.isEmpty()
                    else None
                )

            if limites:
                caixas.append((nome_no, no, Vec3(limites[0]), Vec3(limites[1])))

        pelvis = nos.get("pelvis")
        if pelvis is not None and not pelvis.isEmpty():
            # Volume explícito do cós/baixo-ventre de calca-autoral no referencial local da pelvis.
            caixas.append(
                (
                    "calca-autoral",
                    pelvis,
                    Vec3(-0.228, -0.162, -0.045),
                    Vec3(0.228, 0.148, 0.095),
                )
            )

        return caixas

    def _ancoras(self) -> tuple[tuple[float, float, float], ...]:
        esquerda = self._model_np.getRelativePoint(
            self._no_fone_esq, self._local_fone_esq
        )
        direita = self._model_np.getRelativePoint(
            self._no_fone_dir, self._local_fone_dir
        )
        aparelho = self._model_np.getRelativePoint(
            self._no_aparelho, self._local_aparelho
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
        tronco = []

        for nome_caixa, no, minimo, maximo in self._caixas_locais:
            mat = no.getMat(self._model_np)
            centro = mat.xformPoint((minimo + maximo) * 0.5)
            meias = (maximo - minimo) * 0.5
            eixos = []
            meias_reais = []

            for indice in range(3):
                vetor = mat.getRow3(indice)
                escala = vetor.length()
                if escala > 1e-8:
                    inv = 1.0 / escala
                    eixos.append((vetor.x * inv, vetor.y * inv, vetor.z * inv))
                else:
                    eixos.append((1.0 if indice == 0 else 0.0, 1.0 if indice == 1 else 0.0, 1.0 if indice == 2 else 0.0))
                meias_reais.append(meias[indice] * escala)

            caixa = CaixaOrientada(
                (centro.x, centro.y, centro.z), tuple(eixos), tuple(meias_reais)  # type: ignore[arg-type]
            )
            caixas.append(caixa)
            if nome_caixa in _NOMES_CAIXAS_TRONCO:
                tronco.append(caixa)

        self._caixas_tronco_atuais = tronco
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
        dados = GeomVertexData("fio-fone", GeomVertexFormat.getV3n3c4t2(), Geom.UHDynamic)
        dados.setNumRows(total_vertices)
        cores = GeomVertexWriter(dados, "color")

        uv = GeomVertexWriter(dados, "texcoord")
        for _ in range(total_vertices // 4):
            for u, v in ((0, 0), (1, 0), (1, 1), (0, 1)):
                cores.addData4f(*tuning.COR_FIO)
                uv.addData2f(u, v)

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
        self._malha.setTexture(textura_acabamento("borracha"), 1)
        self._contorno = self._malha.copyTo(contorno_np)
        self._contorno.setName("fio-fone-contorno")
        self._nos_fio.extend((self._malha, self._contorno))
        # As duas cascas compartilham o mesmo GeomVertexData: escrever uma vez.
        self._escritor_vertices = GeomVertexRewriter(dados, "vertex")
        self._escritor_normais = GeomVertexRewriter(dados, "normal")

    def _escrever_vertices(self, *, frente: tuple[float, float, float] | None = None) -> None:
        if self._pecas_asset:
            self._escrever_fio_do_asset(frente=frente)
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
        for no in self._nos_fio:
            if not no.isEmpty() and no.node() is not None:
                no.node().markInternalBoundsStale()

    def definir_visivel(self, visivel: bool) -> None:
        """Exibe ou oculta o fio do fone (usado durante desmontagem LEGO)."""
        self._visivel = visivel
        for no in self._nos_fio:
            if not no.isEmpty():
                (no.show if visivel else no.hide)()

    def atualizar(self, dt: float) -> None:
        """Avança a corda ``dt`` segundos e reescreve a malha."""
        if not self._visivel:
            return
        ancoras = self._ancoras()
        frente = self._frente_modelo()
        gravidade = self._gravidade()
        chave = (
            tuple(round(c, 4) for p in ancoras for c in p),
            tuple(round(c, 4) for c in frente),
            tuple(round(c, 4) for c in gravidade),
        )
        max_v2 = max(
            (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2
            for p, q in zip(self._fio.posicoes, self._fio._anteriores, strict=True)
        )
        if chave == self._ultima_chave_parada and max_v2 < 1e-10:
            self._tempo_parado += max(0.0, float(dt))
            if self._tempo_parado >= 0.35:
                return
        else:
            self._ultima_chave_parada = chave
            self._tempo_parado = 0.0
        caixas, capsulas = self._colisores()
        self._fio.atualizar(
            dt,
            ancoras,
            gravidade,
            caixas,
            capsulas,
            frente_modelo=frente,
        )  # type: ignore[arg-type]
        self._escrever_vertices(frente=frente)
