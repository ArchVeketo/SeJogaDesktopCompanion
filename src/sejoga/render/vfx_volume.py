"""Encenação volumétrica dos filtros Street e Blockbench no espaço do rig."""

from functools import lru_cache
from math import cos, pi, sin

from panda3d.core import NodePath, Shader, Vec3

from sejoga.render import vfx_geometria_3d as geo
from sejoga.render.sprites_efeitos import textura_acabamento

_TINTA = (0.085, 0.055, 0.16)
_LIMA = (0.83, 0.98, 0.12)
_CEREJA = (0.99, 0.16, 0.39)
_TURQUESA = (0.12, 0.89, 0.83)
_CREME = (1.0, 0.88, 0.66)

_VERT = """#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex, p3d_Color;
in vec3 p3d_Normal;
out vec3 local, normal;
out vec4 tinta;
void main() {
    local = p3d_Vertex.xyz;
    normal = p3d_Normal;
    tinta = p3d_Color;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
"""
_FRAGMENTO = """#version 130
in vec3 local, normal;
in vec4 tinta;
out vec4 cor;
vec2 plano(){
    vec3 a=abs(normal);
    if(a.y>=a.x && a.y>=a.z) return local.xz;
    return a.x>a.z ? local.yz : local.xy;
}
"""
_RETICULA = """
void main(){
    vec2 p=plano();
    vec2 grade=mat2(.89,.45,-.45,.89)*p*13.;
    float r=clamp(.24-.18*p.y+.06*normal.y,.10,.34);
    float d=length(fract(grade)-.5);
    float aa=clamp(fwidth(d),.015,.12);
    float pontos=(1.-smoothstep(r-aa,r+aa,d))*(1.-smoothstep(.36,.9,fwidth(grade.x)));
    cor=vec4(tinta.rgb*mix(1.,.20,pontos),1.);
}
"""
_TEXEL = """
uniform sampler2D acabamento;
void main(){
    vec2 uv=fract(plano()+.5);
    vec3 texel=texture(acabamento,uv).rgb;
    cor=vec4(tinta.rgb*texel,1.);
}
"""


@lru_cache(maxsize=2)
def _shader(blocos):
    return Shader.make(
        Shader.SL_GLSL, _VERT, _FRAGMENTO + (_TEXEL if blocos else _RETICULA)
    )


def _pincel(chave):
    # Pincel chato com dorso de tinta escura. O centro da pincelada torce em Y.
    cb = geo._ConstrutorMalha.criar("pincel", chave)
    anterior = None
    for i in range(10):
        u = i / 9
        x = u - 0.45
        y = 0.20 * sin(pi * 1.65 * u)
        z = 0.32 * sin(pi * u) + 0.19 * u
        largura = 0.015 + 0.18 * sin(pi * u) ** 0.67 * (1.25 - 0.65 * u)
        borda = Vec3(x, y, z - largura)
        nervura = Vec3(x, y - 0.12 * sin(pi * u), z - 0.43 * largura)
        topo = Vec3(x, y, z + largura)
        verso = Vec3(x, y + 0.10 * sin(pi * u), z)
        secao = (borda, nervura, topo, verso)
        if anterior:
            for j, cor in enumerate((_TINTA, _LIMA, _CREME, _CEREJA)):
                k = (j + 1) % 4
                cb.quad(anterior[j], secao[j], secao[k], anterior[k], cor)
        anterior = secao
    return cb.finalizar("pincel-impresso", two_sided=True)


@lru_cache(maxsize=64)
def _molde(tipo, chave):
    if tipo == "pincel":
        return _pincel(chave)
    if tipo == "onda":
        return geo.construir_anel_onda_3d(
            _TURQUESA,
            _LIMA,
            aberto_frac=0.84,
            lados=18,
            r_int=0.77,
            irregular=0.19,
            cor_borda=_TINTA,
            colorkey_hex=chave,
        )
    if tipo in ("caco", "fumaca", "escada", "brasa"):
        cb = geo._ConstrutorMalha.criar(tipo, chave)
        if tipo == "fumaca":
            partes = [
                ((-0.23, 0.04, -0.08), 0.26),
                ((0.04, 0.13, 0.08), 0.32),
                ((0.28, -0.08, -0.07), 0.21),
            ]
            base, topo = (0.53, 0.55, 0.66), (0.95, 0.89, 0.78)
        elif tipo == "escada":
            partes = [
                ((i * 0.19, 0, (0.18 if i == 1 else 0)), 0.105) for i in range(-1, 3)
            ]
            base, topo = (0.24, 0.72, 0.85), (0.72, 0.99, 0.93)
        else:
            partes = [((0, 0, 0), 0.43)]
            base, topo = (
                ((0.81, 0.36, 0.14), (0.99, 0.79, 0.30))
                if tipo == "brasa"
                else ((0.34, 0.46, 0.61), (0.74, 0.86, 0.94))
            )
        for centro, raio in partes:
            cb.caixa(Vec3(*centro), Vec3(raio), base, topo)
        return cb.finalizar(tipo, two_sided=False)
    cor = _CEREJA if tipo in ("gota_3d", "coracao_3d") else _TURQUESA
    return geo.construir_objeto_tematico_3d(
        tipo, cor, _CREME, cor_borda=_TINTA, colorkey_hex=chave
    )


def _soltar(
    mgr,
    tipo,
    ponto,
    *,
    velocidade,
    tamanho,
    altura,
    vida,
    giro=0.0,
    gravidade=0.0,
    rumo=0.0,
    heading=0.0,
    inclinacao=0.0,
    modo="padrao",
    quadros=0.0,
    ancora=None,
):
    bloco = mgr._filtro == "blockbench"
    node = NodePath(_molde(tipo, mgr._colorkey_hex).node().makeCopy())
    mgr.emitir_3d(
        node,
        ponto,
        tipo_mesh=tipo,
        vel=velocidade,
        ttl=vida,
        scale_x=tamanho,
        scale_z=altura,
        rot_base=rumo,
        tilt_p=inclinacao,
        heading_h=heading,
        drag=0.86 if bloco else 1.22,
        gravity=gravidade,
        modo_mov=modo,
        rot3d_vel=Vec3(giro * 0.55, giro * 0.32, giro),
        fps_step=quadros,
        anchor_key=ancora,
        exp_final=1.28,
    )
    node.setShader(_shader(bloco), 3)
    if bloco:
        node.setShaderInput("acabamento", textura_acabamento("ceramica"))


def emitir_street(mgr, evento, ponto, lado, angulo, tamanho, vida, ancora):
    """A pincelada marca o gesto e os pingos seguem uma trajetória balística própria."""
    impacto = evento in ("impacto_chao", "impacto_parede", "rastro")
    musical = evento == "acento_danca"
    suave = evento in ("sono", "carinho", "calor")
    direcao = Vec3(lado * cos(angulo * pi / 180), -0.23, sin(angulo * pi / 180))
    tipo = {
        "acento_danca": "onda",
        "carinho": "coracao_3d",
        "choque": "raio_3d",
        "sobressalto": "seta_street_3d",
    }.get(evento, "pincel")
    velocidade = direcao * (1.05 if suave else 2.45) * tamanho
    _soltar(
        mgr,
        tipo,
        ponto,
        velocidade=velocidade,
        tamanho=tamanho * (0.82 if musical else 1.02),
        altura=tamanho * (0.65 if impacto else 0.88),
        vida=vida,
        rumo=-angulo,
        heading=180 if lado < 0 else 0,
        giro=lado * (28 if suave else 56),
        inclinacao=28 if musical else -16,
        modo="onda_expansao" if musical else "pincelada",
        ancora=ancora if suave else None,
    )
    for i in range(2 if suave else 3):
        fator = 0.72 + i * 0.29
        vel = direcao * fator * (0.85 if suave else 2.2) * tamanho
        vel += Vec3(0, (-0.45 + i * 0.48) * tamanho, (0.49 + i * 0.48) * tamanho)
        _soltar(
            mgr,
            "gota_3d" if i != 1 else "faisca_losango_3d",
            ponto,
            velocidade=vel,
            tamanho=tamanho * (0.16 + i * 0.038),
            altura=tamanho * (0.34 + 0.05 * i),
            vida=vida * (0.72 + 0.12 * i),
            gravidade=-4.7 if impacto else -0.7,
            giro=lado * (47 + i * 40),
            rumo=lado * (36 - i * 12),
        )


def emitir_blocos(mgr, evento, ponto, lado, angulo, tamanho, vida, ancora):
    """Puffs de degraus volumétricos, lascas que tombam e faíscas em células."""
    if evento == "impacto_chao":
        return
    direcao = Vec3(lado * cos(angulo * pi / 180), -0.23, sin(angulo * pi / 180))
    vapor = evento in ("sono", "calor")
    if vapor:
        _soltar(
            mgr,
            "fumaca",
            ponto,
            velocidade=direcao * tamanho + Vec3(0, 0.12, 0.57),
            tamanho=tamanho * 0.78,
            altura=tamanho * 0.57,
            vida=vida * 1.18,
            giro=32,
            modo="fumaca_voxel",
            quadros=14,
        )
    for i in range(3 if evento in ("choque", "acento_danca") else 2):
        tipo = (
            "escada"
            if evento in ("choque", "acento_danca", "rastro")
            else ("brasa" if i % 2 else "caco")
        )
        v = direcao * (1.2 + 0.88 * i) * tamanho + Vec3(
            0, 0.38 * (1 - i), (0.34 + 0.61 * i) * tamanho
        )
        _soltar(
            mgr,
            tipo,
            ponto,
            velocidade=v,
            tamanho=tamanho * (0.64 if tipo == "escada" else 0.27),
            altura=tamanho * (0.68 if tipo == "escada" else 0.28),
            vida=vida * (0.80 + 0.13 * i),
            gravidade=-3.9 if evento.startswith("impacto") else 0.20,
            giro=lado * (90 + i * 54),
            rumo=-lado * angulo,
            inclinacao=16 * i,
            modo="grade_voxel",
            quadros=12,
        )
