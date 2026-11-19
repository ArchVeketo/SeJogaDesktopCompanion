"""Choque elétrico 3D nas esferas douradas das antenas (antecipação pré-porta)."""

from __future__ import annotations

import math
import random

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    NodePath,
    Point3,
    Vec3,
)

# Centro medido das esferas douradas no espaço local de antena-direita/esquerda.
_ESFERA_LOCAL_FALLBACK = (
    Vec3(0.109925, -0.068164, 0.148931),
    Vec3(-0.109925, -0.068164, 0.148931),
)
_COR_NUCLEO_OURO = (1.0, 0.97, 0.50, 1.0)
_COR_RAIO_CIANO = (0.24, 0.92, 1.0, 1.0)
# Alpha >= 0.58 para sobreviver ao recorte de cobertura (>= 0.50) do colorkey WGL.
_COR_COROA_EXT = (0.22, 0.86, 1.0, 0.60)
_COR_COROA_INT = (1.0, 0.90, 0.28, 0.76)


def _centro_esfera_antena(ant_np: NodePath, eh_direita: bool) -> Point3:
    esfera = ant_np.find("**/sphere")
    if not esfera.isEmpty():
        limites = esfera.getTightBounds(ant_np)
        if limites:
            return Point3((limites[0] + limites[1]) * 0.5)
    fallback = _ESFERA_LOCAL_FALLBACK[0 if eh_direita else 1]
    return Point3(fallback)


def _perp_dupla(direcao: Vec3) -> tuple[Vec3, Vec3]:
    ref = Vec3(0.0, 0.0, 1.0) if abs(direcao.z) < 0.85 else Vec3(1.0, 0.0, 0.0)
    u = direcao.cross(ref)
    if u.lengthSquared() < 1e-8:
        u = Vec3(1.0, 0.0, 0.0)
    u.normalize()
    v = direcao.cross(u).normalized()
    return u, v


def _emitir_segmento_fita3d(
    v_wr: GeomVertexWriter,
    n_wr: GeomVertexWriter,
    c_wr: GeomVertexWriter,
    tris: GeomTriangles,
    idx_base: int,
    p0: Vec3,
    p1: Vec3,
    r0: float,
    r1: float,
    cor: tuple[float, float, float, float],
) -> int:
    """Emite dois planos ortogonais formando um segmento 3D visível de qualquer ângulo."""
    eixo = p1 - p0
    if eixo.lengthSquared() < 1e-10:
        return idx_base
    u, v = _perp_dupla(eixo.normalized())
    n_dummy = Vec3(0.0, -1.0, 0.0)
    for ortho in (u, v):
        o0 = ortho * r0
        o1 = ortho * r1
        for pt in (p0 - o0, p0 + o0, p1 + o1, p1 - o1):
            v_wr.addData3(pt)
            n_wr.addData3(n_dummy)
            c_wr.addData4(*cor)
        tris.addVertices(idx_base, idx_base + 1, idx_base + 2)
        tris.addVertices(idx_base, idx_base + 2, idx_base + 3)
        tris.addVertices(idx_base, idx_base + 2, idx_base + 1)
        tris.addVertices(idx_base, idx_base + 3, idx_base + 2)
        idx_base += 4
    return idx_base


def _criar_casco_coroa(nome: str, raio: float, cor: tuple[float, float, float, float]) -> NodePath:
    """Octaedro subdividido translúcido envolvendo a bolinha dourada em 3D."""
    vdata = GeomVertexData(nome, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
    writer = GeomVertexWriter(vdata, "vertex")
    n_wr = GeomVertexWriter(vdata, "normal")
    c_wr = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)

    polos = (Vec3(0, 0, 1), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(-1, 0, 0), Vec3(0, -1, 0), Vec3(0, 0, -1))
    faces = (
        (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
        (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4),
    )
    pts: list[Vec3] = []
    idx_tri: list[tuple[int, int, int]] = []
    for a, b, c in faces:
        p0, p1, p2 = polos[a], polos[b], polos[c]
        m01 = (p0 + p1).normalized()
        m12 = (p1 + p2).normalized()
        m20 = (p2 + p0).normalized()
        base = len(pts)
        pts.extend((p0, p1, p2, m01, m12, m20))
        idx_tri.extend((
            (base, base + 3, base + 5),
            (base + 3, base + 1, base + 4),
            (base + 5, base + 4, base + 2),
            (base + 3, base + 4, base + 5),
        ))
    for pt in pts:
        writer.addData3(pt * raio)
        n_wr.addData3(pt)
        c_wr.addData4(*cor)
    for a, b, c in idx_tri:
        tris.addVertices(a, b, c)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gnode = GeomNode(nome)
    gnode.addGeom(geom)
    return NodePath(gnode)


def _emitir_segmento_duplo(
    v_wr: GeomVertexWriter,
    n_wr: GeomVertexWriter,
    c_wr: GeomVertexWriter,
    tris: GeomTriangles,
    idx: int,
    p0: Vec3,
    p1: Vec3,
    r0: float,
    r1: float,
    rn0: float,
    rn1: float,
) -> int:
    """Emite camada externa ciano e núcleo dourado sobre o mesmo segmento 3D."""
    idx = _emitir_segmento_fita3d(v_wr, n_wr, c_wr, tris, idx, p0, p1, r0, r1, _COR_RAIO_CIANO)
    return _emitir_segmento_fita3d(v_wr, n_wr, c_wr, tris, idx, p0, p1, rn0, rn1, _COR_NUCLEO_OURO)


def _emitir_raios_radiais(
    rng: random.Random,
    v_wr: GeomVertexWriter,
    n_wr: GeomVertexWriter,
    c_wr: GeomVertexWriter,
    tris: GeomTriangles,
    idx: int,
) -> int:
    for b in range(9):
        theta = (b / 9.0) * math.tau + rng.uniform(-0.20, 0.20)
        phi = rng.uniform(-0.95, 0.95)
        d = Vec3(
            math.cos(phi) * math.cos(theta),
            math.cos(phi) * math.sin(theta),
            math.sin(phi),
        ).normalized()
        u, v = _perp_dupla(d)
        cur = d * 0.024
        for passo in range(3):
            t_seg = (passo + 1) / 3.0
            dist = 0.024 + t_seg * rng.uniform(0.042, 0.068)
            jitter = (u * rng.uniform(-1.0, 1.0) + v * rng.uniform(-1.0, 1.0)) * (
                0.015 * (1.0 - 0.35 * t_seg)
            )
            nxt = d * dist + jitter
            r0 = 0.0044 * (1.0 - 0.45 * passo / 3.0)
            r1 = 0.0030 * (1.0 - 0.55 * t_seg)
            idx = _emitir_segmento_duplo(
                v_wr, n_wr, c_wr, tris, idx, cur, nxt, r0, r1, r0 * 0.52, r1 * 0.48
            )
            cur = nxt
    return idx


def _emitir_arcos_superficie(
    rng: random.Random,
    v_wr: GeomVertexWriter,
    n_wr: GeomVertexWriter,
    c_wr: GeomVertexWriter,
    tris: GeomTriangles,
    idx: int,
) -> int:
    for _ in range(4):
        normal = Vec3(
            rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0)
        )
        if normal.lengthSquared() < 1e-4:
            normal = Vec3(0.0, 1.0, 0.0)
        e1, e2 = _perp_dupla(normal.normalized())
        ang0 = rng.uniform(0.0, math.tau)
        cur = (e1 * math.cos(ang0) + e2 * math.sin(ang0)) * 0.031
        for passo in range(5):
            ang = ang0 + (passo + 1) * 0.52
            raio_orb = 0.031 + rng.uniform(-0.003, 0.007)
            nxt = (
                e1 * math.cos(ang)
                + e2 * math.sin(ang)
                + normal.normalized() * rng.uniform(-0.008, 0.008)
            ) * raio_orb
            idx = _emitir_segmento_duplo(
                v_wr, n_wr, c_wr, tris, idx, cur, nxt, 0.0034, 0.0030, 0.0017, 0.0015
            )
            cur = nxt
    return idx


def _criar_gaiola_raios(nome: str, semente: int) -> NodePath:
    """Constrói coroa radial e arcos tangenciais 3D de raios ao redor da bolinha."""
    rng = random.Random(semente)
    vdata = GeomVertexData(nome, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
    v_wr = GeomVertexWriter(vdata, "vertex")
    n_wr = GeomVertexWriter(vdata, "normal")
    c_wr = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)
    idx = _emitir_raios_radiais(rng, v_wr, n_wr, c_wr, tris, 0)
    _emitir_arcos_superficie(rng, v_wr, n_wr, c_wr, tris, idx)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gnode = GeomNode(nome)
    gnode.addGeom(geom)
    return NodePath(gnode)


class ChoqueAntenas3D:
    """Choque elétrico 3D ancorado diretamente nas duas esferas douradas."""

    def __init__(self, head_np: NodePath, ant_direita: NodePath, ant_esquerda: NodePath) -> None:
        """Anexa os pivôs de choque às antenas e prepara a ponte 3D entre elas."""
        self._head = head_np
        self._relogio = 0.0
        self._ganho_visivel = 0.0
        self._pivos: list[tuple[NodePath, NodePath, NodePath, list[NodePath]]] = []
        for idx, (ant_np, eh_dir) in enumerate(((ant_direita, True), (ant_esquerda, False))):
            if ant_np is not None and not ant_np.isEmpty():
                self._pivos.append(self._criar_pivo_antena(idx, ant_np, eh_dir))
        self._arco_vdata = GeomVertexData("choque-arco-ponte", GeomVertexFormat.getV3n3c4(), Geom.UHDynamic)
        self._arco_tris = GeomTriangles(Geom.UHDynamic)
        self._arco_np = self._criar_arco_ponte_np(head_np, self._arco_vdata, self._arco_tris)

    @staticmethod
    def _criar_pivo_antena(
        idx: int, ant_np: NodePath, eh_dir: bool
    ) -> tuple[NodePath, NodePath, NodePath, list[NodePath]]:
        suf = "d" if eh_dir else "e"
        pivo = ant_np.attachNewNode(f"fx-choque-esfera-{suf}")
        pivo.setPos(_centro_esfera_antena(ant_np, eh_dir))
        pivo.setLightOff(1001)
        pivo.setShaderOff(1001)
        pivo.setBin("fixed", 52)
        pivo.setCollideMask(0)

        coroa_int = _criar_casco_coroa(f"choque-coroa-int-{suf}", 0.029, _COR_COROA_INT)
        coroa_ext = _criar_casco_coroa(f"choque-coroa-ext-{suf}", 0.039, _COR_COROA_EXT)
        for cas in (coroa_int, coroa_ext):
            cas.setTransparency(1)
            cas.setDepthWrite(False)
            cas.reparentTo(pivo)

        gaiolas = []
        for frame_idx in range(3):
            g = _criar_gaiola_raios(
                f"choque-raios-{suf}-{frame_idx}", semente=410 + idx * 97 + frame_idx * 31
            )
            g.reparentTo(pivo)
            g.hide()
            gaiolas.append(g)
        pivo.hide()
        return pivo, coroa_int, coroa_ext, gaiolas

    @staticmethod
    def _criar_arco_ponte_np(
        head_np: NodePath, vdata: GeomVertexData, tris: GeomTriangles
    ) -> NodePath:
        arco_geom = Geom(vdata)
        arco_geom.addPrimitive(tris)
        gnode = GeomNode("fx-choque-ponte-antenas")
        gnode.addGeom(arco_geom)
        arco_np = head_np.attachNewNode(gnode)
        arco_np.setLightOff(1001)
        arco_np.setShaderOff(1001)
        arco_np.setBin("fixed", 53)
        arco_np.setCollideMask(0)
        arco_np.hide()
        return arco_np

    def _atualizar_ponte(self, p0: Vec3, p1: Vec3, passo_quadro: int, ganho: float) -> None:
        self._arco_vdata.uncleanSetNumRows(0)
        self._arco_tris.clearVertices()
        v_wr = GeomVertexWriter(self._arco_vdata, "vertex")
        n_wr = GeomVertexWriter(self._arco_vdata, "normal")
        c_wr = GeomVertexWriter(self._arco_vdata, "color")
        rng = random.Random(901 + passo_quadro * 37)
        idx = 0
        ramos = ((0, 0.085, 0.0046), (1, 0.145, 0.0028), (2, 0.045, 0.0022))
        for ramo, elev, raio_f in ramos:
            if ramo == 2 and ganho < 0.45:
                continue
            meio = (p0 + p1) * 0.5 + Vec3(
                rng.uniform(-0.028, 0.028),
                -0.02 - 0.015 * ramo,
                elev + rng.uniform(-0.022, 0.036),
            )
            n_passos = 7
            pontos = []
            for s in range(n_passos + 1):
                t = s / n_passos
                omt = 1.0 - t
                pt = p0 * (omt * omt) + meio * (2.0 * omt * t) + p1 * (t * t)
                if 0 < s < n_passos:
                    pt += Vec3(
                        rng.uniform(-0.018, 0.018),
                        rng.uniform(-0.020, 0.020),
                        rng.uniform(-0.022, 0.024),
                    )
                pontos.append(pt)
            r_ext = raio_f * (0.72 + 0.48 * ganho)
            for s in range(n_passos):
                idx = _emitir_segmento_duplo(
                    v_wr,
                    n_wr,
                    c_wr,
                    self._arco_tris,
                    idx,
                    pontos[s],
                    pontos[s + 1],
                    r_ext,
                    r_ext,
                    r_ext * 0.48,
                    r_ext * 0.48,
                )
            # Ramificação elétrica lateral saindo do arco principal no pico da carga.
            if ramo == 0 and ganho >= 0.42:
                tronco = pontos[3]
                ponta_fork = tronco + Vec3(
                    rng.uniform(-0.045, 0.045),
                    rng.uniform(-0.025, 0.010),
                    rng.uniform(0.035, 0.068),
                )
                meio_fork = (tronco + ponta_fork) * 0.5 + Vec3(
                    rng.uniform(-0.014, 0.014), 0.0, rng.uniform(-0.010, 0.016)
                )
                for a_f, b_f, r_f in ((tronco, meio_fork, r_ext * 0.65), (meio_fork, ponta_fork, r_ext * 0.36)):
                    idx = _emitir_segmento_duplo(
                        v_wr, n_wr, c_wr, self._arco_tris, idx, a_f, b_f, r_f, r_f * 0.72, r_f * 0.45, r_f * 0.30
                    )

    @staticmethod
    def _atualizar_pivo(
        idx: int,
        pivo: NodePath,
        coroa_int: NodePath,
        coroa_ext: NodePath,
        gaiolas: list[NodePath],
        passo: int,
        intensidade: float,
        pulso: float,
        relogio: float,
    ) -> None:
        pivo.show()
        escala_base = (0.96 + 0.44 * intensidade) * pulso
        coroa_int.setScale(0.92 + 0.44 * pulso)
        coroa_ext.setScale(escala_base * 1.06)
        # Mistura rotação contínua suave com estalo elétrico nas gaiolas individuais.
        coroa_int.setHpr(relogio * 460.0 + idx * 45.0, relogio * 260.0, relogio * 195.0)
        coroa_ext.setHpr(-relogio * 310.0, relogio * 330.0, idx * 60.0)
        shimmer = 0.88 + 0.30 * math.sin(relogio * 44.0 + idx * 1.4)
        coroa_int.setColorScale(1.0, 0.94 + 0.06 * shimmer, 0.48 + 0.44 * intensidade, 0.95 * min(1.0, intensidade * 1.40))
        coroa_ext.setColorScale(0.60 + 0.40 * shimmer, 0.96, 1.0, 0.90 * min(1.0, intensidade * 1.32))
        ativa = (passo + idx) % len(gaiolas)
        for g_i, g in enumerate(gaiolas):
            if g_i == ativa:
                g.show()
                g.setHpr(
                    (passo * 89 + idx * 67 + relogio * 110.0) % 360,
                    ((passo * 47) % 120) - 60,
                    ((passo * 73) % 160) - 80,
                )
                g.setScale(escala_base * 1.08)
                g.setColorScale(1.0, 1.0, 1.0, min(1.0, 0.45 + 0.78 * intensidade))
            else:
                g.hide()

    def atualizar(self, dt: float, aviso_antena: float, choque_argolas: bool) -> None:
        """Atualiza animação de choque elétrico individual nas duas bobinas do fone."""
        dt_c = max(0.0, dt)
        alvo_ativo = aviso_antena > 0.0 or choque_argolas
        if alvo_ativo:
            alvo_intens = min(1.0, max(0.55 if choque_argolas else 0.0, aviso_antena / 0.35))
            passo_sub = dt_c / 0.035 if dt_c > 0.0 else 1.0
            self._ganho_visivel += min(passo_sub, max(0.0, alvo_intens - self._ganho_visivel))
        else:
            passo_des = dt_c / 0.18 if dt_c > 0.0 else 1.0
            self._ganho_visivel = max(0.0, self._ganho_visivel - passo_des)
        if self._ganho_visivel <= 1e-4:
            self.ocultar()
            return
        self._relogio += dt_c
        passo = int(self._relogio * 26.0)
        # Pequeno overshoot elástico no início do disparo elétrico.
        pop_onset = 1.0 + 0.16 * math.sin(min(1.0, self._ganho_visivel / 0.55) * math.pi)
        intensidade = self._ganho_visivel
        pulso = (0.86 + 0.30 * abs(math.sin(self._relogio * 38.0))) * pop_onset
        for idx, (pivo, coroa_int, coroa_ext, gaiolas) in enumerate(self._pivos):
            self._atualizar_pivo(
                idx, pivo, coroa_int, coroa_ext, gaiolas, passo, intensidade, pulso, self._relogio
            )
        # v2.0: ativa a ponte voltaica 3D entre as duas antenas no pico de carga/choque!
        if intensidade >= 0.42 and len(self._pivos) >= 2:
            self._atualizar_ponte(passo, intensidade)
            self._arco_np.show()
        else:
            self._arco_np.hide()

    def ocultar(self) -> None:
        """Oculta as coroas, gaiolas de raios e a ponte elétrica entre antenas."""
        self._ganho_visivel = 0.0
        for pivo, *_ in self._pivos:
            pivo.hide()
        self._arco_np.hide()
