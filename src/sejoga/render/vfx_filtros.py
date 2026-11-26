"""Grafismos animados no plano do contato. A coordenada +X aponta para fora do emissor."""

from functools import lru_cache

from panda3d.core import Shader

_VERT = """#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec4 p3d_MultiTexCoord0;
out vec2 uv;
void main() {
    uv = p3d_MultiTexCoord0.xy;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
"""

# art() retorna a tinta que cobre o fragmento. A parte vazia permanece transparente
# no color key do Windows. Os desenhos compartilham apenas primitivas de distância.
_BASE = """#version 130
in vec2 uv;
out vec4 fragColor;
uniform float fase;
uniform int evento;
uniform vec3 chave;
const int POUSO=0, GRAVE=1, CHOQUE=2, RASTRO=3, CARINHO=4, SONO=5, CALOR=6, SUSTO=7, BATIDA=8;
const float PI=3.141593;
float segmento(vec2 p, vec2 a, vec2 b) {
    vec2 v=b-a;
    return length(p-a-v*clamp(dot(p-a,v)/max(dot(v,v),0.000001),0.,1.));
}
bool suave() {return evento==CARINHO || evento==SONO;}
"""

_PIXEL = """
vec3 art(vec2 p,float t){
    float k=floor(t*11.)/11.;
    vec2 cell=floor(p*14.);
    for(int i=0;i<6;i++){
        float n=float(i);
        vec2 c=floor(vec2(1.+k*(9.+2.3*n),sin(PI*k)*((suave()?2.:5.)+mod(n*5.,8.))-n*.65));
        vec2 d=abs(cell-c); float r=(1.-k)*(i==0?3.:1.8);
        if(d.x+d.y<=r || (i==0 && min(d.x,d.y)==0. && max(d.x,d.y)<=r+1.))
            return d.x+d.y<1.?vec3(1.,.94,.61):i%2==0?vec3(1.,.53,.10):vec3(.20,.71,.94);
    }
    discard;
}
"""

_QUADRINHO = """
vec3 art(vec2 p,float t){
    float k=floor(t*8.)/8.;
    vec2 c=vec2(.37+.46*k,.09*sin(k*9.));
    vec2 q=(p-c)/(vec2(.53,.37)*max(.06,1.-smoothstep(.73,1.,t)));
    float a=atan(q.y,q.x);
    float raio=(.70+.27*cos(a*9.+.48*sin(3.*a)))*(.72+.40*sin(PI*t));
    if(length(q+vec2(.08,.055))<raio) {
        if(length(q)>raio-.09) return vec3(.025,.032,.045);
        if(length(q-vec2(.10,.06))>raio-.15) return vec3(.96,.13,.22);
        if(q.y<-.13 && length(fract(q*6.)-.5)<.25) return vec3(.13,.10,.22);
        if(abs(q.y-.12*sin(q.x*7.))<.06 && abs(q.x)<.42) return vec3(.10,.09,.15);
        return vec3(.99,.75,.16);
    }
    if(length(q-vec2(.08,.06))<raio) return vec3(.09,.82,.87);
    discard;
}
"""

_HIFI = """
vec3 art(vec2 p,float t){
    float x=p.x*6.5;
    int banda=int(floor(x));
    if(banda<0 || banda>7 || fract(x)<.15 || fract(x)>.88) discard;
    float atraso=float(banda)*.055;
    float a=(t-atraso)/(1.-atraso);
    if(a<0.) discard;
    float pico=(.30+.24*cos(float(banda)*1.41))*(suave()?.65:1.);
    float h=pico*max(0.,min(a*10.,1.))*pow(1.-a,1.6)+.05;
    float y=p.y+.14;
    if(y>=0. && y<h && fract(y*17.)>.15) return y>.18?vec3(1.,.69,.10):vec3(.08,.83,.66);
    if(y>h+.025 && y<h+.064 && a<.82) return vec3(1.,.92,.64);
    discard;
}
"""

_CYBER = """
vec3 art(vec2 p,float t){
    for(int i=0;i<3;i++){
        float n=float(i), y=.19*(n-1.);
        float a=clamp(t*1.38-n*.10,0.,1.);
        float x=.06+1.24*a;
        float knee=.32+n*.13;
        float path=y+clamp(p.x-knee,0.,.21)*(i==1?-1.:1.);
        float d=abs(p.y-path);
        if(p.x>max(.04,x-.66*(1.-smoothstep(.65,1.,t))) && p.x<x && d<.032) return vec3(.05,.81,.74);
        if(abs(p.x-x)+d<.084*(1.-t)) return vec3(.98,.44,.14);
        if(abs(p.x-knee)<.036 && d<.047 && a>.35 && a<.76) return vec3(.97,.95,.76);
    }
    discard;
}
"""

_ANIME = """
vec3 art(vec2 p,float t){
    float k=floor(t*13.)/13.;
    vec2 q=p-vec2(.15+.92*k,.08*sin(k*PI));
    float blade=abs(q.y-(q.x*q.x*.61+q.x*.26));
    float w=.16*sin(PI*clamp((q.x+.57)/.90,0.,1.))*(1.-k*.65);
    if(q.x>-.57 && q.x<.33 && blade<w) return blade<w*.42?vec3(.99,.97,.91):vec3(.42,.66,.98);
    if(t<.39){
        vec2 s=abs(p-vec2(.30,.06));
        if(min(s.x+4.*s.y,4.*s.x+s.y)<.32*(1.-t)) return vec3(1.,.80,.37);
    }
    if(q.x>-.48 && q.x<.15 && abs(q.y-(q.x*q.x*.61+q.x*.26)-.20)<.026*(1.-k)) return vec3(.67,.69,.98);
    discard;
}
"""

_PS1 = """
vec3 art(vec2 p,float t){
    float k=floor(t*16.)/16.;
    for(int i=0;i<3;i++){
        float n=float(i), a=k*(1.13+n*.16);
        vec2 c=vec2(.12+k*(.65+n*.34),.67*a-.87*a*a+n*.13);
        vec2 q=p-c; float rot=n+4.3*k;
        q=mat2(cos(rot),-sin(rot),sin(rot),cos(rot))*q;
        q/=vec2(max(.055,abs(cos(a*4.+n)))*.24,.22)*max(.04,1.-.53*k-.43*smoothstep(.72,1.,t));
        if(abs(q.x)+abs(q.y)<1.) {
            if(q.x<-.22*q.y) return vec3(.16,.35,.66);
            return q.y>.25*q.x ? vec3(.84,.80,.56):vec3(.36,.65,.83);
        }
    }
    discard;
}
"""

_HOLOGRAMA = """
vec3 art(vec2 p,float t){
    float a=1.-pow(1.-t,2.);
    vec2 c=vec2(.43+.18*t,0.);
    float faixa=floor(p.y*19.);
    float salto=mod(faixa+floor(t*18.),7.)==0.?.115:0.;
    vec2 q=abs(p-c-vec2(salto,0.));
    vec2 size=vec2(.18+.40*a,.10+.26*a);
    vec2 edge=abs(q-size);
    if((edge.x<.021 && edge.y<.11 || edge.y<.021 && edge.x<.14) && t<.88)
        return vec3(.28,.94,.97);
    if(q.x<size.x && q.y<size.y && abs(p.y-(.38-.76*fract(t*1.4)))<.035)
        return vec3(.72,.98,1.);
    if(salto>0. && q.x<size.x*.68 && q.y<size.y && fract(p.y*34.)<.36) return vec3(.10,.51,.88);
    discard;
}
"""

_GAMEBOY = """
vec3 art(vec2 p,float t){
    // O LCD retém a silhueta anterior durante uma atualização de célula.
    vec2 cell=floor(p*12.);
    float tick=floor(t*6.);
    for(int i=0;i<2;i++){
        float k=max(0.,tick-float(i));
        vec2 q=abs(cell-vec2(3.+2.*k,mod(k,3.)-1.));
        float r=2.+mod(k,3.);
        float d=q.x+q.y;
        if(d==r || (q.x==0. && q.y==0. && i==0)){
            if(i==1 && mod(cell.x+cell.y,2.)==0.) continue;
            return i==0?vec3(.08,.14,.07):vec3(.59,.71,.34);
        }
    }
    discard;
}
"""

_MANGA = """
vec3 art(vec2 p,float t){
    float corte=floor(t*5.);
    for(int i=0;i<8;i++){
        float n=float(i);
        float ang=-.79+n*.225+.023*mod(corte+n,3.);
        vec2 v=vec2(cos(ang),sin(ang));
        float recuo=.14+.32*t+.10*mod(n,3.);
        float comp=(.30+.34*mod(n*3.,5.)/4.)*(1.-.96*t);
        float s=dot(p,v)-recuo;
        float lado=abs(dot(p,vec2(-v.y,v.x)));
        float w=.039*(1.-clamp(s/comp,0.,1.));
        if(s>0. && s<comp && lado<w+.012) return lado<w?vec3(.019,.014,.027):vec3(.91,.86,.76);
    }
    discard;
}
"""

_DESENHOS = {
    "pixel": _PIXEL,
    "rascunho": _QUADRINHO,
    "spiderverse": _QUADRINHO,
    "hifi_comic": _HIFI,
    "street": _HIFI,
    "cyberfunk": _CYBER,
    "anime": _ANIME,
    "lowpoly_block": _PS1,
    "holograma": _HOLOGRAMA,
    "gameboy": _GAMEBOY,
    "manga_papel": _MANGA,
}

_FINAL = """
void main(){
    vec2 p=vec2(uv.x*2.-.28,(uv.y-.5)*2.);
    vec3 cor=art(p,fase);
    if(distance(cor,chave)<.14) cor.g=cor.g<.5?cor.g+.18:cor.g-.18;
    fragColor=vec4(cor,1.);
}
"""


@lru_cache(maxsize=10)
def shader_grafismo(filtro: str) -> Shader:
    """Compila apenas o desenho selecionado e reutiliza o programa entre eventos."""
    return Shader.make(Shader.SL_GLSL, _VERT, _BASE + _DESENHOS[filtro] + _FINAL)
