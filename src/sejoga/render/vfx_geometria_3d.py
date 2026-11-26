"""Construtores procedurais de malhas 3D estilizadas para os VFX por estilo.

Cada estilo usa geometria 3D real com sombreamento cel em 2 bandas, contorno
opaco (sem semi-transparência para preservar o color key Win32) e guarda contra
magenta em todas as cores de vértice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    NodePath,
    TransparencyAttrib,
    Vec3,
)

from sejoga.render.chroma_tuning import CHROMA_HEX_PADRAO, seguro_contra_chroma_255

_LUZ_CEL = Vec3(0.36, -0.82, 0.44).normalized()
CorRGB = tuple[float, float, float]


def cor_vfx_3d(
    rgb: CorRGB,
    colorkey_hex: str = CHROMA_HEX_PADRAO,
) -> tuple[float, float, float, float]:
    """Converte RGB linear (0..1) em cor de vértice segura contra o chroma key."""
    rs, gs, bs = seguro_contra_chroma_255(
        round(max(0.0, min(1.0, rgb[0])) * 255.0),
        round(max(0.0, min(1.0, rgb[1])) * 255.0),
        round(max(0.0, min(1.0, rgb[2])) * 255.0),
        colorkey_hex,
    )
    return (
        (rs / 255.0) ** 1.85,
        (gs / 255.0) ** 1.85,
        (bs / 255.0) ** 1.85,
        1.0,
    )


@dataclass
class _ConstrutorMalha:
    v_wr: GeomVertexWriter
    n_wr: GeomVertexWriter
    c_wr: GeomVertexWriter
    tris: GeomTriangles
    vdata: GeomVertexData
    colorkey_hex: str
    idx: int = 0

    @classmethod
    def criar(cls, nome: str, colorkey_hex: str) -> _ConstrutorMalha:
        vdata = GeomVertexData(nome, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
        return cls(
            v_wr=GeomVertexWriter(vdata, "vertex"),
            n_wr=GeomVertexWriter(vdata, "normal"),
            c_wr=GeomVertexWriter(vdata, "color"),
            tris=GeomTriangles(Geom.UHStatic),
            vdata=vdata,
            colorkey_hex=colorkey_hex,
        )

    def _cor_cel(self, normal: Vec3, base_rgb: CorRGB, sombrear: bool) -> tuple[float, float, float, float]:
        if not sombrear:
            return cor_vfx_3d(base_rgb, self.colorkey_hex)
        dot = normal.dot(_LUZ_CEL)
        fator = 1.04 if dot >= 0.08 else (0.82 if dot >= -0.35 else 0.62)
        return cor_vfx_3d(
            (min(1.0, base_rgb[0] * fator), min(1.0, base_rgb[1] * fator), min(1.0, base_rgb[2] * fator)),
            self.colorkey_hex,
        )

    def tri(
        self,
        p0: Vec3,
        p1: Vec3,
        p2: Vec3,
        rgb: CorRGB,
        *,
        sombrear: bool = True,
        inverter: bool = False,
    ) -> None:
        a, b, c = (p0, p2, p1) if inverter else (p0, p1, p2)
        normal = (b - a).cross(c - a)
        if normal.lengthSquared() < 1e-11:
            return
        normal.normalize()
        cor = self._cor_cel(normal, rgb, sombrear)
        for pt in (a, b, c):
            self.v_wr.addData3(pt)
            self.n_wr.addData3(normal)
            self.c_wr.addData4(*cor)
        self.tris.addVertices(self.idx, self.idx + 1, self.idx + 2)
        self.idx += 3

    def quad(
        self,
        p0: Vec3,
        p1: Vec3,
        p2: Vec3,
        p3: Vec3,
        rgb: CorRGB,
        *,
        sombrear: bool = True,
        inverter: bool = False,
    ) -> None:
        self.tri(p0, p1, p2, rgb, sombrear=sombrear, inverter=inverter)
        self.tri(p0, p2, p3, rgb, sombrear=sombrear, inverter=inverter)

    def caixa(
        self,
        centro: Vec3,
        meia: Vec3,
        cor_a: CorRGB,
        cor_topo: CorRGB | None = None,
        *,
        rot_z: float = 0.0,
        inverter: bool = False,
        sombrear: bool = True,
    ) -> None:
        cz_cos, cz_sin = math.cos(rot_z), math.sin(rot_z)
        mx, my, mz = meia.x, meia.y, meia.z
        pts = []
        for sz in (-mz, mz):
            for sx, sy in ((-mx, -my), (mx, -my), (mx, my), (-mx, my)):
                rx = sx * cz_cos - sy * cz_sin
                ry = sx * cz_sin + sy * cz_cos
                pts.append(Vec3(centro.x + rx, centro.y + ry, centro.z + sz))
        top_c = cor_topo if cor_topo is not None else cor_a
        for i0, i1, i2, i3 in ((0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.quad(pts[i0], pts[i1], pts[i2], pts[i3], cor_a, sombrear=sombrear, inverter=inverter)
        self.quad(pts[4], pts[5], pts[6], pts[7], top_c, sombrear=sombrear, inverter=inverter)
        self.quad(pts[3], pts[2], pts[1], pts[0], cor_a, sombrear=sombrear, inverter=inverter)

    def finalizar(
        self,
        nome: str,
        *,
        two_sided: bool = False,
        cull_inverter: bool = False,
    ) -> NodePath:
        geom = Geom(self.vdata)
        geom.addPrimitive(self.tris)
        gnode = GeomNode(nome)
        gnode.addGeom(geom)
        np = NodePath(gnode)
        np.setTwoSided(two_sided and not cull_inverter)
        np.setLightOff(1)
        np.setShaderOff(1)
        np.setDepthTest(True)
        np.setDepthWrite(True)
        np.setTransparency(TransparencyAttrib.MNone)
        np.setCollideMask(0)
        np.setBin("fixed", 43)
        return np


def _extrudir_poligono(
    cb: _ConstrutorMalha,
    contorno: list[tuple[float, float]],
    espessura_y: float,
    rgb: CorRGB,
    *,
    centro_z: float | None = None,
    inverter: bool = False,
    sombrear: bool = True,
) -> None:
    if len(contorno) < 3:
        return
    # Garante sentido horário em (X, Z) visto de -Y para que todas as normais apontem para fora.
    n = len(contorno)
    area2 = sum(
        contorno[k][0] * contorno[(k + 1) % n][1] - contorno[(k + 1) % n][0] * contorno[k][1]
        for k in range(n)
    )
    pts = list(reversed(contorno)) if area2 > 0.0 else contorno
    cx = sum(p[0] for p in pts) / n
    cz = centro_z if centro_z is not None else sum(p[1] for p in pts) / n
    c_f = Vec3(cx, -espessura_y, cz)
    c_b = Vec3(cx, espessura_y, cz)
    for k in range(n):
        x0, z0 = pts[k]
        x1, z1 = pts[(k + 1) % n]
        f0, f1 = Vec3(x0, -espessura_y, z0), Vec3(x1, -espessura_y, z1)
        b0, b1 = Vec3(x0, espessura_y, z0), Vec3(x1, espessura_y, z1)
        cb.tri(c_f, f1, f0, rgb, sombrear=sombrear, inverter=inverter)
        cb.tri(c_b, b0, b1, rgb, sombrear=sombrear, inverter=inverter)
        cb.quad(f0, f1, b1, b0, rgb, sombrear=sombrear, inverter=inverter)


def _inflar_poligono(contorno: list[tuple[float, float]], margem: float) -> list[tuple[float, float]]:
    cx = sum(p[0] for p in contorno) / len(contorno)
    cz = sum(p[1] for p in contorno) / len(contorno)
    out: list[tuple[float, float]] = []
    for px, pz in contorno:
        dx, dz = px - cx, pz - cz
        d = max(1e-4, math.hypot(dx, dz))
        out.append((px + (dx / d) * margem, pz + (dz / d) * margem))
    return out


def _adicionar_contorno_faixa(
    cb: _ConstrutorMalha,
    p_in0: Vec3,
    p_in1: Vec3,
    p_out0: Vec3,
    p_out1: Vec3,
    cor: CorRGB,
    esp: float,
    off_y: float = 0.025,
) -> None:
    y_back = off_y
    v_i0 = Vec3(p_in0.x * (1.0 - esp), p_in0.y + y_back, p_in0.z * (1.0 - esp))
    v_i1 = Vec3(p_in1.x * (1.0 - esp), p_in1.y + y_back, p_in1.z * (1.0 - esp))
    v_o0 = Vec3(p_out0.x * (1.0 + esp), p_out0.y + y_back, p_out0.z * (1.0 + esp))
    v_o1 = Vec3(p_out1.x * (1.0 + esp), p_out1.y + y_back, p_out1.z * (1.0 + esp))
    cb.quad(v_i0, v_i1, v_o1, v_o0, cor, sombrear=False)


def construir_anel_onda_3d(
    cor_a: CorRGB,
    cor_b: CorRGB,
    *,
    lados: int = 20,
    r_int: float = 0.68,
    r_ext: float = 1.0,
    irregular: float = 0.0,
    aberto_frac: float = 1.0,
    segmentado: bool = False,
    cor_borda: CorRGB | None = None,
    colorkey_hex: str = CHROMA_HEX_PADRAO,
) -> NodePath:
    """Constrói anel 3D chanfrado de onda sonora, impacto, tinta ou pincelada Enso."""
    cb = _ConstrutorMalha.criar("vfx-3d-anel", colorkey_hex)
    passos = max(6, lados)
    ang_total = math.tau * max(0.15, min(1.0, aberto_frac))
    esp_z = 0.045
    pontos: list[tuple[Vec3, Vec3]] = []
    for k in range(passos + 1):
        u = k / passos
        ang = u * ang_total
        wob = 1.0 + irregular * (0.55 * math.sin(k * 2.7) + 0.45 * math.cos(k * 4.3))
        taper = math.sin(min(1.0, u / 0.14) * math.pi * 0.5) * math.sin(min(1.0, (1.0 - u) / 0.14) * math.pi * 0.5) if aberto_frac < 0.99 else 1.0
        meia = (r_ext - r_int) * 0.5 * wob * max(0.12, taper)
        rm = (r_ext + r_int) * 0.5 * (1.0 + irregular * 0.15 * math.cos(k * 3.1))
        ri, ro = max(0.08, rm - meia), rm + meia
        pontos.append((Vec3(math.cos(ang) * ri, 0.0, math.sin(ang) * ri), Vec3(math.cos(ang) * ro, 0.0, math.sin(ang) * ro)))

    for k in range(passos):
        if segmentado and k % 2 == 1:
            continue
        pi0, po0 = pontos[k]
        pi1, po1 = pontos[k + 1]
        faixa = k // 2 if segmentado else k
        rgb = cor_a if faixa % 2 == 0 else cor_b
        for dy in (-esp_z, esp_z):
            inv = dy > 0.0
            cb.quad(
                Vec3(pi0.x, dy, pi0.z), Vec3(pi1.x, dy, pi1.z),
                Vec3(po1.x, dy, po1.z), Vec3(po0.x, dy, po0.z),
                rgb, sombrear=True, inverter=inv,
            )
        cb.quad(Vec3(po0.x, -esp_z, po0.z), Vec3(po1.x, -esp_z, po1.z), Vec3(po1.x, esp_z, po1.z), Vec3(po0.x, esp_z, po0.z), rgb)
        cb.quad(Vec3(pi1.x, -esp_z, pi1.z), Vec3(pi0.x, -esp_z, pi0.z), Vec3(pi0.x, esp_z, pi0.z), Vec3(pi1.x, esp_z, pi1.z), rgb)
        if segmentado or (aberto_frac < 0.99 and k == 0):
            cb.quad(Vec3(pi0.x, -esp_z, pi0.z), Vec3(po0.x, -esp_z, po0.z),
                    Vec3(po0.x, esp_z, po0.z), Vec3(pi0.x, esp_z, pi0.z), rgb)
        if segmentado or (aberto_frac < 0.99 and k == passos - 1):
            cb.quad(Vec3(po1.x, -esp_z, po1.z), Vec3(pi1.x, -esp_z, pi1.z),
                    Vec3(pi1.x, esp_z, pi1.z), Vec3(po1.x, esp_z, po1.z), rgb)
        if cor_borda is not None:
            _adicionar_contorno_faixa(cb, pi0, pi1, po0, po1, cor_borda, 0.09, off_y=esp_z + 0.015)

    return cb.finalizar("vfx-3d-anel", two_sided=True)


def construir_arco_slash_3d(
    cor_a: CorRGB,
    cor_b: CorRGB,
    *,
    abertura_graus: float = 165.0,
    espessura: float = 0.22,
    ondulado: float = 0.0,
    zigue_zague: bool = False,
    cor_borda: CorRGB | None = None,
    colorkey_hex: str = CHROMA_HEX_PADRAO,
) -> NodePath:
    """Constrói arco crescente afunilado (corte anime, Spidey-Sense ou pincelada sumi-e)."""
    cb = _ConstrutorMalha.criar("vfx-3d-arco", colorkey_hex)
    passos = 16 if not zigue_zague else 18
    ang_tot = math.radians(max(45.0, min(330.0, abertura_graus)))
    ang_ini = -ang_tot * 0.5
    pts: list[tuple[Vec3, Vec3]] = []
    for k in range(passos + 1):
        u = k / passos
        ang = ang_ini + u * ang_tot
        taper = math.sin(u * math.pi) ** 0.72
        if zigue_zague:
            desvio = (0.14 if k % 2 == 0 else -0.14) * taper
            r_mid = 0.85 + desvio
        else:
            r_mid = 0.85 + ondulado * math.sin(u * math.tau * 2.0) * 0.12
        meia = max(0.015, espessura * 0.5 * taper)
        ri, ro = r_mid - meia, r_mid + meia
        pts.append((Vec3(math.cos(ang) * ri, 0.0, math.sin(ang) * ri), Vec3(math.cos(ang) * ro, 0.0, math.sin(ang) * ro)))

    for k in range(passos):
        pi0, po0 = pts[k]
        pi1, po1 = pts[k + 1]
        rgb = cor_a if k < passos // 2 else cor_b
        cb.quad(pi0, pi1, po1, po0, rgb, sombrear=False)
        if cor_borda is not None:
            _adicionar_contorno_faixa(cb, pi0, pi1, po0, po1, cor_borda, 0.075, off_y=0.022)

    return cb.finalizar("vfx-3d-arco", two_sided=True)


def construir_cubo_cel_3d(
    cor_a: CorRGB,
    cor_b: CorRGB,
    *,
    proporcao: tuple[float, float, float] = (1.0, 1.0, 1.0),
    cor_borda: CorRGB | None = (0.04, 0.04, 0.06),
    escala_borda: float = 1.16,
    colorkey_hex: str = CHROMA_HEX_PADRAO,
) -> NodePath:
    """Constrói cubo/bloco 3D cel-shaded com casca opaca de contorno invertido."""
    cb = _ConstrutorMalha.criar("vfx-3d-cubo", colorkey_hex)
    mx, my, mz = (max(0.05, float(v) * 0.5) for v in proporcao)
    cb.caixa(Vec3(0.0, 0.0, 0.0), Vec3(mx, my, mz), cor_a, cor_b, sombrear=True)
    raiz = cb.finalizar("vfx-3d-cubo", two_sided=False)
    if cor_borda is not None:
        cb_out = _ConstrutorMalha.criar("vfx-3d-cubo-borda", colorkey_hex)
        cb_out.caixa(
            Vec3(0.0, 0.0, 0.0),
            Vec3(mx * escala_borda, my * escala_borda, mz * escala_borda),
            cor_borda,
            cor_borda,
            inverter=True,
            sombrear=False,
        )
        cb_out.finalizar("vfx-3d-cubo-borda", cull_inverter=True).reparentTo(raiz)
    return raiz


def _emitir_agulha_radial(
    cb: _ConstrutorMalha,
    ang: float,
    r0: float,
    r1: float,
    larg: float,
    rgb: CorRGB,
    cor_borda: CorRGB | None,
) -> None:
    ux, uz = math.cos(ang), math.sin(ang)
    nx, nz = -uz * larg, ux * larg
    p_esq = Vec3(ux * r0 + nx, 0.0, uz * r0 + nz)
    p_dir = Vec3(ux * r0 - nx, 0.0, uz * r0 - nz)
    p_ponta = Vec3(ux * r1, 0.0, uz * r1)
    p_topo = Vec3(ux * (r0 + (r1 - r0) * 0.28), -0.05, uz * (r0 + (r1 - r0) * 0.28))
    cb.tri(p_esq, p_ponta, p_topo, rgb, sombrear=True)
    cb.tri(p_topo, p_ponta, p_dir, rgb, sombrear=True)
    cb.tri(p_dir, p_ponta, p_esq, rgb, sombrear=True)
    if cor_borda is not None:
        m = 1.24
        b_esq = Vec3(ux * (r0 * 0.90) + nx * m, 0.025, uz * (r0 * 0.90) + nz * m)
        b_dir = Vec3(ux * (r0 * 0.90) - nx * m, 0.025, uz * (r0 * 0.90) - nz * m)
        b_ponta = Vec3(ux * (r1 * 1.12), 0.025, uz * (r1 * 1.12))
        cb.tri(b_esq, b_ponta, b_dir, cor_borda, sombrear=False)


def construir_raios_radiais_3d(
    cor_a: CorRGB,
    cor_b: CorRGB,
    *,
    qtd: int = 8,
    r_ini: float = 0.16,
    r_fim: float = 1.0,
    largura: float = 0.14,
    assimetrico: bool = False,
    cruz_anime: bool = False,
    cor_borda: CorRGB | None = None,
    colorkey_hex: str = CHROMA_HEX_PADRAO,
) -> NodePath:
    """Feixe radial 3D: cruz de brilho anime, shuchusen mangá ou estrela de impacto."""
    cb = _ConstrutorMalha.criar("vfx-3d-raios", colorkey_hex)
    if cruz_anime:
        especs = [(k * math.pi * 0.5, 0.06, 1.15 if k % 2 == 0 else 0.92, largura, cor_a) for k in range(4)]
        especs += [(math.pi * 0.25 + k * math.pi * 0.5, 0.05, 0.52, largura * 0.65, cor_b) for k in range(4)]
        for ang, ri, rf, lg, rgb in especs:
            _emitir_agulha_radial(cb, ang, ri, rf, lg, rgb, cor_borda)
        return cb.finalizar("vfx-3d-raios", two_sided=True)

    total = max(4, qtd)
    for k in range(total):
        ang = k * (math.tau / total)
        if assimetrico:
            ang += 0.14 * math.sin(k * 2.9)
        fator = 0.62 + 0.45 * ((k % 3) / 2.0) if assimetrico else (1.0 if k % 2 == 0 else 0.72)
        rf = r_fim * fator
        lg = largura * (0.78 if k % 2 else 1.12)
        rgb = cor_a if k % 2 == 0 else cor_b
        _emitir_agulha_radial(cb, ang, r_ini, rf, lg, rgb, cor_borda)
    return cb.finalizar("vfx-3d-raios", two_sided=True)


def construir_pilar_energia_3d(
    cor_a: CorRGB,
    cor_b: CorRGB,
    *,
    tipo: str = "chama",
    cor_borda: CorRGB | None = None,
    colorkey_hex: str = CHROMA_HEX_PADRAO,
) -> NodePath:
    """Pilar vertical ancorado na base z=0..1 (barra de equalizador 3D ou chama Ki)."""
    cb = _ConstrutorMalha.criar(f"vfx-3d-pilar-{tipo}", colorkey_hex)
    if tipo == "barra_eq":
        cb.caixa(Vec3(0.0, 0.0, 0.48), Vec3(0.14, 0.10, 0.48), cor_a, cor_b, sombrear=True)
        raiz = cb.finalizar("vfx-3d-barra-eq", two_sided=False)
        if cor_borda is not None:
            cb_out = _ConstrutorMalha.criar("vfx-3d-barra-eq-borda", colorkey_hex)
            cb_out.caixa(
                Vec3(0.0, 0.0, 0.48), Vec3(0.175, 0.13, 0.52),
                cor_borda, cor_borda, inverter=True, sombrear=False,
            )
            cb_out.finalizar("vfx-3d-barra-eq-borda", cull_inverter=True).reparentTo(raiz)
        return raiz

    altura_segs = (0.0, 0.22, 0.50, 0.78, 1.0)
    largs = (0.14, 0.30, 0.24, 0.11, 0.01)
    desvios = (0.0, 0.06, -0.08, 0.05, 0.0)
    for cam, scale_w, dy, rgb in ((cor_b, 1.0, 0.0, cor_b), (cor_a, 0.54, -0.025, cor_a)):
        del cam
        for k in range(len(altura_segs) - 1):
            z0, z1 = altura_segs[k], altura_segs[k + 1]
            w0, w1 = largs[k] * scale_w, largs[k + 1] * scale_w
            x0, x1 = desvios[k] * scale_w, desvios[k + 1] * scale_w
            cb.quad(
                Vec3(x0 - w0, dy, z0), Vec3(x0 + w0, dy, z0),
                Vec3(x1 + w1, dy, z1), Vec3(x1 - w1, dy, z1),
                rgb, sombrear=False,
            )
    if cor_borda is not None:
        for k in range(len(altura_segs) - 1):
            z0, z1 = altura_segs[k], altura_segs[k + 1]
            w0, w1 = largs[k] * 1.18, largs[k + 1] * 1.18 + 0.025
            x0, x1 = desvios[k], desvios[k + 1]
            cb.quad(
                Vec3(x0 - w0, 0.03, z0), Vec3(x0 + w0, 0.03, z0),
                Vec3(x1 + w1, 0.03, z1), Vec3(x1 - w1, 0.03, z1),
                cor_borda, sombrear=False,
            )
    return cb.finalizar("vfx-3d-chama", two_sided=True)


def _montar_poligono_com_borda(
    nome: str,
    contorno: list[tuple[float, float]],
    esp_y: float,
    cor_a: CorRGB,
    cor_borda: CorRGB | None,
    colorkey_hex: str,
) -> NodePath:
    cb = _ConstrutorMalha.criar(nome, colorkey_hex)
    _extrudir_poligono(cb, contorno, esp_y, cor_a, sombrear=True)
    raiz = cb.finalizar(nome, two_sided=False)
    if cor_borda is not None:
        cb_b = _ConstrutorMalha.criar(f"{nome}-borda", colorkey_hex)
        _extrudir_poligono(
            cb_b, _inflar_poligono(contorno, 0.055), esp_y + 0.045, cor_borda, inverter=True, sombrear=False
        )
        cb_b.finalizar(f"{nome}-borda", cull_inverter=True).reparentTo(raiz)
    return raiz


def _construir_estrela_origami(
    cor_a: CorRGB,
    cor_b: CorRGB,
    colorkey_hex: str,
) -> NodePath:
    cb = _ConstrutorMalha.criar("vfx-3d-estrela-origami", colorkey_hex)
    topo = Vec3(0.0, -0.18, 0.0)
    verso = Vec3(0.0, 0.18, 0.0)
    anel = [
        Vec3(
            math.cos(k * (math.tau / 8.0)) * (0.56 if k % 2 == 0 else 0.25),
            0.0,
            math.sin(k * (math.tau / 8.0)) * (0.56 if k % 2 == 0 else 0.25),
        )
        for k in range(8)
    ]
    for k in range(8):
        p0, p1 = anel[k], anel[(k + 1) % 8]
        rgb = cor_a if k % 2 == 0 else cor_b
        cb.tri(p0, p1, topo, rgb, sombrear=True)
        cb.tri(p1, p0, verso, rgb, sombrear=True)
    return cb.finalizar("vfx-3d-estrela-origami", two_sided=True)


def _construir_aviao_ou_papel(
    tipo: str,
    cor_a: CorRGB,
    cor_b: CorRGB,
    cor_borda: CorRGB | None,
    colorkey_hex: str,
) -> NodePath:
    if tipo == "estrela_origami":
        return _construir_estrela_origami(cor_a, cor_b, colorkey_hex)
    cb = _ConstrutorMalha.criar(f"vfx-3d-{tipo}", colorkey_hex)
    if tipo == "aviao_papel":
        bico = Vec3(0.70, 0.0, 0.0)
        cauda_c = Vec3(-0.55, 0.0, 0.04)
        asa_e = Vec3(-0.52, -0.50, 0.22)
        asa_d = Vec3(-0.52, 0.50, 0.22)
        quilha = Vec3(-0.46, 0.0, -0.22)
        cb.tri(bico, cauda_c, asa_e, cor_a, sombrear=True)
        cb.tri(bico, asa_d, cauda_c, cor_b, sombrear=True)
        cb.tri(bico, quilha, cauda_c, cor_b, sombrear=True)
        if cor_borda is not None:
            m = 1.08
            dz = Vec3(0.0, 0.0, -0.03)
            cb.tri(bico * m + dz, cauda_c * m + dz, asa_e * m + dz, cor_borda, sombrear=False)
            cb.tri(bico * m + dz, asa_d * m + dz, cauda_c * m + dz, cor_borda, sombrear=False)
        return cb.finalizar("vfx-3d-aviao-papel", two_sided=True)

    pts = [
        (Vec3(-0.34, -0.04, -0.24), Vec3(0.0, 0.05, -0.20), Vec3(0.36, -0.03, -0.22)),
        (Vec3(-0.32, 0.02, 0.24), Vec3(0.0, 0.08, 0.22), Vec3(0.34, -0.05, 0.26)),
    ]
    cb.quad(pts[0][0], pts[0][1], pts[1][1], pts[1][0], cor_a)
    cb.quad(pts[0][1], pts[0][2], pts[1][2], pts[1][1], cor_b)
    if cor_borda is not None:
        cb.quad(
            Vec3(-0.39, 0.09, -0.29), Vec3(0.41, 0.09, -0.29),
            Vec3(0.39, 0.09, 0.30), Vec3(-0.37, 0.09, 0.30), cor_borda, sombrear=False,
        )
    return cb.finalizar("vfx-3d-folha", two_sided=True)


def _construir_nota_ou_raio(
    tipo: str,
    cor_a: CorRGB,
    cor_b: CorRGB,
    cor_borda: CorRGB | None,
    colorkey_hex: str,
) -> NodePath:
    if tipo == "raio_3d":
        contorno = [
            (-0.18, 0.62), (0.24, 0.62), (0.04, 0.12),
            (0.28, 0.12), (-0.24, -0.64), (-0.02, -0.06), (-0.28, -0.06),
        ]
        return _montar_poligono_com_borda("vfx-3d-raio", contorno, 0.08, cor_a, cor_borda, colorkey_hex)

    cb = _ConstrutorMalha.criar("vfx-3d-nota", colorkey_hex)
    cb.caixa(Vec3(-0.14, 0.0, -0.34), Vec3(0.22, 0.11, 0.15), cor_a, cor_b, rot_z=0.35)
    cb.caixa(Vec3(0.06, 0.0, 0.12), Vec3(0.075, 0.10, 0.48), cor_a, cor_b)
    cb.caixa(Vec3(0.26, 0.0, 0.44), Vec3(0.22, 0.10, 0.10), cor_b, cor_a, rot_z=-0.42)
    raiz = cb.finalizar("vfx-3d-nota", two_sided=False)
    if cor_borda is not None:
        cb_b = _ConstrutorMalha.criar("vfx-3d-nota-borda", colorkey_hex)
        cb_b.caixa(Vec3(-0.14, 0.0, -0.34), Vec3(0.26, 0.15, 0.19), cor_borda, cor_borda, rot_z=0.35, inverter=True, sombrear=False)
        cb_b.caixa(Vec3(0.06, 0.0, 0.12), Vec3(0.115, 0.14, 0.52), cor_borda, cor_borda, inverter=True, sombrear=False)
        cb_b.caixa(Vec3(0.26, 0.0, 0.44), Vec3(0.26, 0.14, 0.14), cor_borda, cor_borda, rot_z=-0.42, inverter=True, sombrear=False)
        cb_b.finalizar("vfx-3d-nota-borda", cull_inverter=True).reparentTo(raiz)
    return raiz


def _construir_emblema_simetrico(
    tipo: str,
    cor_a: CorRGB,
    cor_b: CorRGB,
    cor_borda: CorRGB | None,
    colorkey_hex: str,
) -> NodePath:
    if tipo == "coracao_3d":
        contorno = [
            (0.0, -0.52), (-0.42, -0.10), (-0.48, 0.24), (-0.24, 0.44),
            (0.0, 0.24), (0.24, 0.44), (0.48, 0.24), (0.42, -0.10),
        ]
        return _montar_poligono_com_borda("vfx-3d-coracao", contorno, 0.11, cor_a, cor_borda, colorkey_hex)
    if tipo == "chevron_3d":
        contorno = [(-0.34, 0.48), (0.04, 0.48), (0.42, 0.0), (0.04, -0.48), (-0.34, -0.48), (0.04, 0.0)]
        return _montar_poligono_com_borda("vfx-3d-chevron", contorno, 0.09, cor_a, cor_borda, colorkey_hex)
    if tipo == "seta_street_3d":
        contorno = [
            (-0.56, -0.14), (0.08, -0.14), (0.02, -0.40),
            (0.60, 0.0), (0.02, 0.40), (0.08, 0.14), (-0.56, 0.14),
        ]
        return _montar_poligono_com_borda("vfx-3d-seta-street", contorno, 0.09, cor_a, cor_borda, colorkey_hex)
    if tipo == "gota_3d":
        contorno = [(0.0, 0.58), (-0.28, -0.05), (-0.22, -0.42), (0.0, -0.54), (0.22, -0.42), (0.28, -0.05)]
        return _montar_poligono_com_borda("vfx-3d-gota", contorno, 0.10, cor_a, cor_borda, colorkey_hex)

    # faisca_losango_3d ou cristal_3d (bipirâmide)
    rz = 0.62 if tipo == "faisca_losango_3d" else 0.48
    rx = 0.16 if tipo == "faisca_losango_3d" else 0.34
    cb = _ConstrutorMalha.criar(f"vfx-3d-{tipo}", colorkey_hex)
    topo, base = Vec3(0.0, 0.0, rz), Vec3(0.0, 0.0, -rz)
    lados = 4 if tipo == "faisca_losango_3d" else 6
    anel = [Vec3(math.cos(k * (math.tau / lados)) * rx, math.sin(k * (math.tau / lados)) * rx, 0.0) for k in range(lados)]
    for k in range(lados):
        p0, p1 = anel[k], anel[(k + 1) % lados]
        rgb = cor_a if k % 2 == 0 else cor_b
        cb.tri(p0, p1, topo, rgb)
        cb.tri(p1, p0, base, rgb)
    return cb.finalizar(f"vfx-3d-{tipo}", two_sided=False)


def _caixas_simbolo_3d(tipo: str) -> tuple[tuple[Vec3, Vec3, float], ...]:
    if tipo == "pausa_3d":
        return (
            (Vec3(-0.20, 0.0, 0.0), Vec3(0.11, 0.10, 0.44), 0.0),
            (Vec3(0.20, 0.0, 0.0), Vec3(0.11, 0.10, 0.44), 0.0),
        )
    if tipo == "exclamacao_3d":
        return (
            (Vec3(0.0, 0.0, 0.18), Vec3(0.12, 0.10, 0.36), 0.0),
            (Vec3(0.0, 0.0, -0.38), Vec3(0.12, 0.10, 0.12), 0.0),
        )
    return (
        (Vec3(0.0, 0.0, 0.34), Vec3(0.32, 0.09, 0.09), 0.0),
        (Vec3(0.0, 0.0, 0.0), Vec3(0.09, 0.09, 0.40), -0.65),
        (Vec3(0.0, 0.0, -0.34), Vec3(0.32, 0.09, 0.09), 0.0),
    )


def _construir_misc_3d(
    tipo: str,
    cor_a: CorRGB,
    cor_b: CorRGB,
    cor_borda: CorRGB | None,
    colorkey_hex: str,
) -> NodePath:
    if tipo == "nuvem_spray_3d":
        cb = _ConstrutorMalha.criar("vfx-3d-spray", colorkey_hex)
        for cx, cz, raio, rgb in (
            (-0.24, -0.08, 0.22, cor_a), (0.04, 0.12, 0.26, cor_b),
            (0.28, -0.06, 0.19, cor_a), (-0.06, -0.22, 0.16, cor_b),
        ):
            cb.caixa(Vec3(cx, 0.0, cz), Vec3(raio, raio * 0.75, raio), rgb, cor_b, rot_z=cx * 2.1)
        return cb.finalizar("vfx-3d-spray", two_sided=False)

    if tipo in ("pausa_3d", "exclamacao_3d", "z_bloco_3d"):
        pecas = _caixas_simbolo_3d(tipo)
        cb = _ConstrutorMalha.criar(f"vfx-3d-{tipo}", colorkey_hex)
        for idx, (c_pos, meia, rz) in enumerate(pecas):
            c1, c2 = (cor_a, cor_b) if idx % 2 == 0 else (cor_b, cor_a)
            cb.caixa(c_pos, meia, c1, c2, rot_z=rz)
        raiz = cb.finalizar(f"vfx-3d-{tipo}", two_sided=False)
        if cor_borda is not None:
            cb_b = _ConstrutorMalha.criar(f"vfx-3d-{tipo}-b", colorkey_hex)
            for c_pos, meia, rz in pecas:
                cb_b.caixa(
                    c_pos, meia + Vec3(0.045, 0.045, 0.045),
                    cor_borda, cor_borda, rot_z=rz, inverter=True, sombrear=False,
                )
            cb_b.finalizar(f"vfx-3d-{tipo}-b", cull_inverter=True).reparentTo(raiz)
        return raiz

    # espiral_arame_3d: curva helicoidal em 3D (molas / novelo / espiral)
    cb = _ConstrutorMalha.criar("vfx-3d-espiral", colorkey_hex)
    passos = 26
    for k in range(passos):
        u0, u1 = k / passos, (k + 1) / passos
        a0, a1 = u0 * math.tau * 2.2, u1 * math.tau * 2.2
        r0, r1 = 0.08 + u0 * 0.48, 0.08 + u1 * 0.48
        p0 = Vec3(math.cos(a0) * r0, math.sin(a0 * 0.5) * 0.10, math.sin(a0) * r0)
        p1 = Vec3(math.cos(a1) * r1, math.sin(a1 * 0.5) * 0.10, math.sin(a1) * r1)
        off = Vec3(0.0, 0.055, 0.055)
        cb.quad(p0 - off, p1 - off, p1 + off, p0 + off, cor_a if k % 2 == 0 else cor_b, sombrear=False)
    return cb.finalizar("vfx-3d-espiral", two_sided=True)


_CACHE_OBJETOS_3D: dict[tuple, NodePath] = {}


def construir_objeto_tematico_3d(
    tipo: str,
    cor_a: CorRGB,
    cor_b: CorRGB,
    *,
    cor_borda: CorRGB | None = None,
    colorkey_hex: str = CHROMA_HEX_PADRAO,
) -> NodePath:
    """Constrói miniatura 3D estilizada para eventos específicos de cada tema (com cache)."""
    chave = (tipo, cor_a, cor_b, cor_borda, colorkey_hex)
    tpl = _CACHE_OBJETOS_3D.get(chave)
    if tpl is None or tpl.isEmpty():
        if tipo in ("aviao_papel", "estrela_origami", "folha_papel"):
            tpl = _construir_aviao_ou_papel(tipo, cor_a, cor_b, cor_borda, colorkey_hex)
        elif tipo in ("nota_3d", "raio_3d"):
            tpl = _construir_nota_ou_raio(tipo, cor_a, cor_b, cor_borda, colorkey_hex)
        elif tipo in ("coracao_3d", "chevron_3d", "seta_street_3d", "gota_3d", "faisca_losango_3d", "cristal_3d"):
            tpl = _construir_emblema_simetrico(tipo, cor_a, cor_b, cor_borda, colorkey_hex)
        else:
            tpl = _construir_misc_3d(tipo, cor_a, cor_b, cor_borda, colorkey_hex)
        _CACHE_OBJETOS_3D[chave] = tpl
    tmp = NodePath("__vfx_clone__")
    clone = tpl.copyTo(tmp)
    clone.detachNode()
    return clone
