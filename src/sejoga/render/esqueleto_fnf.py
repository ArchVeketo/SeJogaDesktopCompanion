"""Esqueleto de raio-X sem crânio para o encerramento ``fnf_blue_balls``."""

from __future__ import annotations

from dataclasses import dataclass

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    NodePath,
    Vec3,
)

_COR_OSSO_CLARO = (1.0, 1.0, 1.0, 1.0)
_COR_OSSO_MEDIO = (0.86, 0.88, 0.91, 1.0)
_FACES_CAIXA = (
    (0, 1, 2, 3),
    (5, 4, 7, 6),
    (4, 0, 3, 7),
    (1, 5, 6, 2),
    (3, 2, 6, 7),
    (4, 5, 1, 0),
)


def _adicionar_caixa(
    gnode: GeomNode,
    centro: Vec3,
    meio: Vec3,
    cor: tuple[float, float, float, float],
) -> None:
    cx, cy, cz = centro.x, centro.y, centro.z
    hx, hy, hz = meio.x, meio.y, meio.z
    pts = (
        (cx - hx, cy - hy, cz - hz),
        (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz),
        (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz),
        (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz),
        (cx - hx, cy + hy, cz + hz),
    )
    vdata = GeomVertexData("osso", GeomVertexFormat.getV3c4(), Geom.UHStatic)
    vw = GeomVertexWriter(vdata, "vertex")
    cw = GeomVertexWriter(vdata, "color")
    for p in pts:
        vw.addData3f(*p)
        cw.addData4f(*cor)
    tris = GeomTriangles(Geom.UHStatic)
    for a, b, c, d in _FACES_CAIXA:
        tris.addVertices(a, b, c)
        tris.addVertices(a, c, d)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gnode.addGeom(geom)


def _adicionar_barra_entre(
    gnode: GeomNode,
    inicio: Vec3,
    fim: Vec3,
    espessura: float,
    cor: tuple[float, float, float, float],
) -> None:
    delta = fim - inicio
    comp = delta.length()
    if comp < 1e-4:
        return
    centro = (inicio + fim) * 0.5
    direcao = delta / comp
    hx = max(espessura, abs(direcao.x) * comp * 0.44 + espessura * 0.45)
    hy = max(espessura, abs(direcao.y) * comp * 0.44 + espessura * 0.45)
    hz = max(espessura, abs(direcao.z) * comp * 0.44 + espessura * 0.45)
    _adicionar_caixa(gnode, centro, Vec3(hx, hy, hz), cor)


@dataclass
class _PecaOsso:
    alvo_rig: NodePath
    osso_np: NodePath


class EsqueletoFnf:
    """Constrói e sincroniza ossos de raio-X estilizados (tronco/membros, zero crânio)."""

    def __init__(self, parent: NodePath, rig_nodes: dict[str, NodePath]) -> None:
        """Cria o nó raiz de raio-X e monta os ossos de tronco e membros."""
        self.root = parent.attachNewNode("fnf-skeleton-xray")
        self.root.setLightOff(1001)
        self.root.setShaderOff(1001)
        self.root.setBin("fixed", 55)
        self.root.setDepthTest(False)
        self.root.setDepthWrite(False)
        self.root.hide()
        self._pecas: list[_PecaOsso] = []
        self._montar_pecas(rig_nodes)

    def _registrar_no(self, rig_nodes: dict[str, NodePath], nome: str, gnode: GeomNode) -> None:
        alvo = rig_nodes.get(nome)
        if alvo is None or alvo.isEmpty():
            return
        np = self.root.attachNewNode(gnode)
        self._pecas.append(_PecaOsso(alvo_rig=alvo, osso_np=np))

    def _montar_pecas(self, rig_nodes: dict[str, NodePath]) -> None:
        # 1. Tronco superior (clavícula + esterno + 3 pares de costelas, SEM crânio na cabeça!)
        g_peito = GeomNode("osso-peitoral")
        _adicionar_caixa(g_peito, Vec3(0.0, 0.0, 0.06), Vec3(0.115, 0.018, 0.014), _COR_OSSO_CLARO)
        _adicionar_caixa(g_peito, Vec3(0.0, 0.0, 0.0), Vec3(0.018, 0.018, 0.095), _COR_OSSO_CLARO)
        for z_rib, w_rib in ((0.032, 0.098), (-0.010, 0.088), (-0.052, 0.072)):
            _adicionar_caixa(g_peito, Vec3(0.0, 0.0, z_rib), Vec3(w_rib, 0.015, 0.012), _COR_OSSO_MEDIO)
        self._registrar_no(rig_nodes, "peitoral", g_peito)

        # 2. Coluna lombar e pélvis (borboleta pélvica — sem osso craniano!)
        for nome_sp, alt in (("abdomen", 0.048), ("cintura", 0.044)):
            g_sp = GeomNode(f"osso-{nome_sp}")
            _adicionar_caixa(g_sp, Vec3(0.0, 0.0, 0.02), Vec3(0.020, 0.020, alt), _COR_OSSO_CLARO)
            _adicionar_caixa(g_sp, Vec3(0.0, 0.0, -0.01), Vec3(0.030, 0.016, 0.012), _COR_OSSO_MEDIO)
            self._registrar_no(rig_nodes, nome_sp, g_sp)

        g_pelv = GeomNode("osso-pelvis")
        _adicionar_caixa(g_pelv, Vec3(0.0, 0.0, -0.01), Vec3(0.115, 0.024, 0.022), _COR_OSSO_CLARO)
        _adicionar_caixa(g_pelv, Vec3(-0.075, 0.0, 0.018), Vec3(0.036, 0.020, 0.036), _COR_OSSO_MEDIO)
        _adicionar_caixa(g_pelv, Vec3(0.075, 0.0, 0.018), Vec3(0.036, 0.020, 0.036), _COR_OSSO_MEDIO)
        self._registrar_no(rig_nodes, "pelvis", g_pelv)

        # 3. Membros longos (medidos entre nó e filho no repouso local)
        ligacoes = (
            ("right-arm", "ant-arm", 0.018),
            ("ant-arm", "hand", 0.016),
            ("left-arm", "ant-arm2", 0.018),
            ("ant-arm2", "hand2", 0.016),
            ("coxa-direita", "joelho-direito", 0.022),
            ("canela-direita", "right-feet", 0.018),
            ("coxa-esquerda", "joelho-esquerdo", 0.022),
            ("canela-esquerda", "left-feet", 0.018),
        )
        for pai, filho, esp in ligacoes:
            n_pai = rig_nodes.get(pai)
            n_filho = rig_nodes.get(filho)
            if n_pai is None or n_filho is None or n_pai.isEmpty() or n_filho.isEmpty():
                continue
            g = GeomNode(f"osso-{pai}")
            alvo_local = n_filho.getPos(n_pai)
            _adicionar_barra_entre(g, Vec3(0.0, 0.0, 0.0), alvo_local, esp, _COR_OSSO_CLARO)
            _adicionar_caixa(g, Vec3(0.0, 0.0, 0.0), Vec3(esp * 1.4, esp * 1.4, esp * 1.4), _COR_OSSO_MEDIO)
            self._registrar_no(rig_nodes, pai, g)

    def atualizar(self, power: float, render_root: NodePath) -> None:
        """Sincroniza e exibe o esqueleto sem crânio conforme intensidade ``power``."""
        if power <= 0.03:
            self.root.hide()
            return
        self.root.show()
        brilho = max(0.55, min(1.0, power))
        self.root.setColorScale(brilho, brilho, brilho, 1.0)
        for peca in self._pecas:
            if not peca.alvo_rig.isEmpty():
                peca.osso_np.setMat(peca.alvo_rig.getMat(render_root))
                if not peca.osso_np.getName().startswith(("orbe", "fnf-blue-orb")):
                    peca.osso_np.setColorScale(1.0, 1.0, 1.0, 1.0)

    def limpar(self) -> None:
        """Remove os nós de esqueleto da cena."""
        self._pecas.clear()
        if not self.root.isEmpty():
            self.root.removeNode()
