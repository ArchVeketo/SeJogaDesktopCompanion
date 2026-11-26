"""Articula a calça autoral sem substituir sua silhueta por tubos arredondados."""

from __future__ import annotations

import json

from panda3d.core import (
    CullFaceAttrib,
    Filename,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexWriter,
    Mat4,
    Point3,
    Quat,
    Texture,
    Vec3,
)

from sejoga.nucleo.recursos import model_dir


def _misturar_transformacoes(matrizes, pesos):
    """Dual quaternion mantém o volume da dobra, inclusive perto de 90 graus."""
    real, dual = Quat(0, 0, 0, 0), Quat(0, 0, 0, 0)
    referencia = None
    for matriz, peso in zip(matrizes, pesos, strict=True):
        if peso <= 0:
            continue
        q = Quat()
        q.setFromMatrix(matriz.getUpper3())
        q.normalize()
        if referencia is None:
            referencia = q
        elif q.dot(referencia) < 0:
            q = -q
        t = matriz.getRow3(3)
        real += q * peso
        dual += Quat(0, t.x, t.y, t.z) * q * (0.5 * peso)
    comprimento = real.length()
    if comprimento < 1e-8:
        return Mat4.identMat()
    real /= comprimento
    dual /= comprimento
    dual -= real * real.dot(dual)
    t = dual * real.conjugate() * 2
    resultado = Mat4()
    real.extractToMatrix(resultado)
    resultado.setRow(3, Vec3(t.getI(), t.getJ(), t.getK()))
    return resultado


def _pesos_vertice(ponto, quadril_z, joelho_z):
    # A costura central e o cós ficam no quadril; as pernas se separam abaixo.
    if abs(ponto.x) < 1e-6:
        return (1.0, 0.0, 0.0)
    cintura = max(0.0, min(1.0, (ponto.z - (quadril_z - 0.07)) / 0.07))
    canela = max(0.0, min(1.0, (joelho_z + 0.035 - ponto.z) / 0.07))
    return (cintura, (1 - cintura) * (1 - canela), (1 - cintura) * canela)


class PernasTecido:
    """Preserva faces, UVs e assimetrias do original, com duas cadeias de perna."""

    def __init__(self, renderer, lados):
        self._legs = renderer.model_np.find("**/legs")
        self._pelvis_node = renderer._rig_nodes.get("pelvis") or renderer.model_np.find("**/pelvis")
        if self._pelvis_node is not None and not self._pelvis_node.isEmpty():
            self._pelvis_inv = Mat4(self._pelvis_node.getMat(self._legs))
            self._pelvis_inv.invertInPlace()
        else:
            self._pelvis_node = None
            self._pelvis_inv = Mat4.identMat()
        self._nodes, self._rigidos = [], []
        self._pelvis_ocultas = []
        self._cadeias = {}
        self._ativo = True
        dados = json.loads(
            (model_dir() / "calca-autoral.json").read_text(encoding="utf-8")
        )
        self._pontos = {k: Point3(*v) for k, v in dados["vertices"].items()}
        self._faces = dados["faces"]
        for lado in lados:
            coxa, _, canela, _ = lado["nomes"]
            nos = [renderer._rig_nodes[n] for n in (coxa, canela)]
            inversas = []
            for no in nos:
                inv = Mat4(no.getMat(self._legs))
                inv.invertInPlace()
                inversas.append(inv)
            self._cadeias[lado["lado"]] = (nos, inversas)
        self._pesos = {}
        for chave, p in self._pontos.items():
            lado = "right" if p.x > 0 else "left"
            nos, _ = self._cadeias[lado]
            joelho = "joelho-direito" if lado == "right" else "joelho-esquerdo"
            self._pesos[chave] = (
                lado,
                _pesos_vertice(
                    p,
                    nos[0].getZ(self._legs),
                    renderer._rig_nodes[joelho].getZ(self._legs),
                ),
            )
        base_geom = renderer.model_np.find("**/pelvis/+GeomNode")
        estado = base_geom.node().getGeomState(0)
        formato = base_geom.node().getGeom(0).getVertexData().getFormat()
        self._vdata = GeomVertexData("calca-autoral", formato, Geom.UHDynamic)
        triangulos = GeomTriangles(Geom.UHStatic)
        uv = GeomVertexWriter(self._vdata, "texcoord.0")
        self._linhas = []
        for face in self._faces:
            inicio = len(self._linhas)
            self._linhas.extend(face["vertices"])
            for tex in face["uv"]:
                uv.addData2(*tex)
            for i in range(1, len(face["vertices"]) - 1):
                triangulos.addVertices(inicio, inicio + i, inicio + i + 1)
        geom = Geom(self._vdata)
        geom.addPrimitive(triangulos)
        no = GeomNode("calca-autoral")
        no.addGeom(geom, estado)
        vis = self._legs.attachNewNode(no)
        textura = renderer.showbase.loader.loadTexture(
            Filename.fromOsSpecific(str(model_dir() / "calca-autoral.png"))
        )
        textura.setFormat(Texture.FSrgbAlpha)
        textura.setMinfilter(Texture.FTNearest)
        textura.setMagfilter(Texture.FTNearest)
        stage = base_geom.findTextureStage("*")
        vis.setTexture(stage, textura, 10)
        self._nodes.append(vis)
        self._vdata_outline = None
        if renderer.outline_np is not None:
            outline_base = renderer.outline_np.find("**/pelvis/+GeomNode")
            estado_outline = (
                outline_base.node()
                .getGeomState(0)
                .removeAttrib(CullFaceAttrib.getClassType())
            )
            self._vdata_outline = GeomVertexData(
                "calca-autoral-outline", formato, Geom.UHDynamic
            )
            uv_out = GeomVertexWriter(self._vdata_outline, "texcoord.0")
            for face in self._faces:
                for tex in face["uv"]:
                    uv_out.addData2(*tex)
            geom_out = Geom(self._vdata_outline)
            geom_out.addPrimitive(triangulos)
            no_outline = GeomNode("calca-autoral-outline")
            no_outline.addGeom(geom_out, estado_outline)
            contorno = renderer.outline_np.find("**/legs").attachNewNode(no_outline)
            contorno.setTexture(stage, textura, 10)
            self._nodes.append(contorno)
        # Oculta só superfícies; preserva os pivôs e o picking das duas pernas.
        nomes = ["pelvis", *(n for lado in lados for n in lado["nomes"][:3])]
        for raiz in (renderer.model_np, renderer.outline_np):
            if raiz is None:
                continue
            for nome in nomes:
                grupo = raiz.find("**/" + nome)
                for child in grupo.getChildren():
                    if child.getName().startswith(("coxa-", "joelho-", "canela-")):
                        continue
                    if nome == "pelvis":
                        # O apoio sentado mede esse volume mesmo com a superfície oculta.
                        child.hide()
                        self._pelvis_ocultas.append(child)
                    else:
                        child.stash()
                        self._rigidos.append(child)
        self._escrever(self._pontos)

    def _escrever(self, pontos):
        vw = GeomVertexWriter(self._vdata, "vertex")
        nw = GeomVertexWriter(self._vdata, "normal")
        normais_suaves: dict[str, Vec3] = {}
        for face in self._faces:
            ps = [pontos[k] for k in face["vertices"]]
            normal = (ps[1] - ps[0]).cross(ps[2] - ps[0])
            normal.normalize()
            for k, p in zip(face["vertices"], ps, strict=True):
                vw.setData3(p)
                nw.setData3(normal)
                acum = normais_suaves.get(k)
                normais_suaves[k] = normal if acum is None else (acum + normal)
        if self._vdata_outline is not None:
            for k, soma in normais_suaves.items():
                if soma.lengthSquared() > 1e-10:
                    soma.normalize()
                else:
                    normais_suaves[k] = Vec3(0.0, -1.0, 0.0)
            vw_o = GeomVertexWriter(self._vdata_outline, "vertex")
            nw_o = GeomVertexWriter(self._vdata_outline, "normal")
            for face in self._faces:
                for k in face["vertices"]:
                    vw_o.setData3(pontos[k])
                    nw_o.setData3(normais_suaves[k])
        for node in self._nodes:
            node.node().markInternalBoundsStale()

    def apply(self, renderer, pose, dt):
        """Aplica skinning matricial na malha da calça autoral quando há mudança de pose."""
        if not self._ativo:
            return
        mat_pelvis = (
            self._pelvis_inv * self._pelvis_node.getMat(self._legs)
            if self._pelvis_node is not None and not self._pelvis_node.isEmpty()
            else Mat4.identMat()
        )
        matrizes = {
            lado: (
                mat_pelvis,
                *(
                    inv * no.getMat(self._legs)
                    for no, inv in zip(nos, inversas, strict=True)
                ),
            )
            for lado, (nos, inversas) in self._cadeias.items()
        }
        assinatura = tuple(
            round(m.getCell(lin, col), 5)
            for lado in sorted(matrizes)
            for m in matrizes[lado]
            for lin in range(4)
            for col in range(3)
        )
        if assinatura == getattr(self, "_ultima_assinatura_matrizes", None):
            return
        self._ultima_assinatura_matrizes = assinatura
        pontos = {}
        for chave, ponto in self._pontos.items():
            lado, pesos = self._pesos[chave]
            pontos[chave] = _misturar_transformacoes(matrizes[lado], pesos).xformPoint(
                ponto
            )
        self._escrever(pontos)

    def set_lego_mode(self, renderer, ativo):
        """Alterna visibilidade entre calça contínua e peças rígidas no modo LEGO."""
        self._ativo = not ativo
        for no in self._nodes:
            no.hide() if ativo else no.show()
        for no in self._rigidos:
            no.unstash() if ativo else no.stash()
        for no in self._pelvis_ocultas:
            no.show() if ativo else no.hide()
