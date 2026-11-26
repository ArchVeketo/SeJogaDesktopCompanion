"""Anti-atravessamento dos braços contra o corpo, com a FK real do rig.

Os braços são cápsulas (braço, antebraço, mão+dedos) medidas por
``nucleo.cinematica`` (mesma FK do Panda3D). O corpo são caixas do referencial de
AUTORIA (``+X`` direita, ``+Y`` frente, ``+Z`` cima) medidas no grafo de cena
do asset em repouso (``tools/gerar_oraculo_cena.py``). As primitivas de interseção são
as de ``primitivas_colisao`` (cápsula-caixa e cápsula-cápsula).

A correção é MÍNIMA e determinística: busca em subida de encosta, sobre os
quatro graus de liberdade do lado (P, H, R do ombro e a flexão do cotovelo), o
menor deslocamento que zera a penetração. O deslocamento é guardado por lado
(partida a quente) e relaxa de volta a zero quando deixa de ser necessário, para
a correção entrar e sair sem tranco.

shortcut: colisores seguem a pose autoral, sem os pivôs táteis e o IK de pernas
do renderer; incorporar essas transformações se houver penetração visível.

FRONTEIRA: Python puro (só ``math`` e módulos puros do projeto).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import degrees, radians

from sejoga.animacao.braco_tuning import (
    FOLGA_EXTRA_CAIXA_U,
    FRACAO_NUCLEO_BRACO,
    PASSOS_BUSCA_GRAUS,
)
from sejoga.animacao.primitivas_colisao import (
    CaixaOrientada,
    Capsula,
    penetracao_capsula_caixa,
    penetracao_capsula_capsula,
)
from sejoga.nucleo import cinematica as cin
from sejoga.nucleo.esqueleto import Rotation3
from sejoga.nucleo.modelo import Model

Vec3 = cin.Vec3

# --------------------------------------------------------------------------- #
# Geometria do braço (medida no asset; ver tools/gerar_oraculo_cena.py)
# --------------------------------------------------------------------------- #
#: Menor meia-aresta medida do cubo do braço (seção 0.273 x 0.227).
MEIA_ESPESSURA_BRACO_U = 0.1135
RAIO_BRACO_U = MEIA_ESPESSURA_BRACO_U * FRACAO_NUCLEO_BRACO
#: Luva/mão grande do Mário (~0.187 de largura na palma) precisa de raio próprio.
RAIO_MAO_U = MEIA_ESPESSURA_BRACO_U * 0.64
#: Comprimento da mão + dedos além do punho (``hand`` → ponta de ``fingers``).
COMPRIMENTO_MAO_U = 0.33
#: Meia-largura medida do tronco (malha ``mesh20``). O pivô do ombro (x=0.125)
#: nasce DENTRO dela: no próprio T-pose do asset os primeiros
#: ``MEIA_LARGURA_TRONCO_U + RAIO_BRACO_U - |x_ombro|`` (≈0.171) do eixo do braço
#: ficam dentro do tronco. Esse trecho estrutural da raiz não conta como colisão.
MEIA_LARGURA_TRONCO_U = 0.186


# --------------------------------------------------------------------------- #
# Volumes do corpo em repouso (referencial de autoria): (centro, meias-dimensões)
# --------------------------------------------------------------------------- #
def _caixa(
    x0: float, x1: float, y0: float, y1: float, z0: float, z1: float
) -> CaixaOrientada:
    """Caixa alinhada aos eixos de autoria a partir dos limites medidos."""
    return CaixaOrientada(
        centro=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
        eixos=(cin.EIXO_DIREITA, cin.EIXO_FRENTE, cin.EIXO_CIMA),
        meias_dim=((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2),
    )


def _espelhada(caixa: CaixaOrientada) -> CaixaOrientada:
    return CaixaOrientada(
        centro=cin.espelhar_ponto(caixa.centro),
        eixos=caixa.eixos,
        meias_dim=caixa.meias_dim,
    )


#: Volumes nucleares do corpo em repouso (relativos ao nó raiz do asset).
#: Para tronco e quadril (short evasê cuja barra inferior abre até ±0.312 perto
#: dos pés, mas na cintura tem meia-largura 0.186..0.215), a caixa representa o
#: volume real da cintura/quadril superior onde braço e punho transitam, evitando
#: que o flare da barra inferior empurre os braços para um A-pose artificial.
_ORELHA = _caixa(0.146, 0.303, -0.126, 0.112, 0.789, 1.027)
_CHAPEU_LATERAL = _caixa(0.240, 0.394, -0.200, -0.030, 1.018, 1.125)
_PE = _caixa(0.028, 0.230, -0.120, 0.220, 0.091, 0.350)
_COXA = _caixa(0.028, 0.195, -0.115, 0.115, 0.220, 0.445)
_PIVO_COXA_DIR = (0.110, 0.0, 0.440)
_PIVO_COXA_ESQ = (-0.110, 0.0, 0.440)

#: Volumes do corpo que BLOQUEIAM os braços: tronco, cabeça, topo da cabeça,
#: quadril, coxas e pés. Orelhas e chapéu lateral ficam no diagnóstico para não
#: travar arcos altos/laterais (comemoração, chifre, graffiti).
CAIXAS_CORPO: dict[str, CaixaOrientada] = {
    "tronco": _caixa(-0.165, 0.165, -0.130, 0.130, 0.420, 0.723),
    "cabeca": _caixa(-0.146, 0.146, -0.161, 0.151, 0.651, 1.100),
    "topo_cabeca": _caixa(-0.195, 0.195, -0.070, 0.032, 1.140, 1.234),
    "quadril": _caixa(-0.205, 0.205, -0.155, 0.155, 0.135, 0.474),
    "coxa_direita": _COXA,
    "coxa_esquerda": _espelhada(_COXA),
    "pe_direito": _PE,
    "pe_esquerdo": _espelhada(_PE),
}
CAIXAS_DIAGNOSTICO: dict[str, CaixaOrientada] = {
    **CAIXAS_CORPO,
    "orelha_direita": _ORELHA,
    "orelha_esquerda": _espelhada(_ORELHA),
    "chapeu_direito": _CHAPEU_LATERAL,
    "chapeu_esquerdo": _espelhada(_CHAPEU_LATERAL),
}
#: Anti-atravessamento entre as duas mãos/antebraços ativado (evita palmas grandes
#: passando uma dentro da outra em poses de cruzado, dança ou blue_balls).
COLISAO_ENTRE_BRACOS = True

# --------------------------------------------------------------------------- #
# Correção
# --------------------------------------------------------------------------- #
#: Penetração (unidades do modelo) tolerada: abaixo disto a pose passa intacta.
FOLGA_PENETRACAO_U = 0.01
#: Passos de melhoria por quadro. Um passo por quadro (≥3°, ~180°/s a 60 fps)
#: já corrige rápido e espalha o custo; o resto continua no quadro seguinte
#: (partida a quente). Custo medido (CPython, esta máquina): ~2 ms/quadro com os
#: braços livres; corrigindo, mediana ~12 ms e pico ~41 ms (quadro em que só o
#: passo grosso resolve).
#: shortcut: busca por coordenadas em Python puro, com picos de ~41 ms durante
#: correções; trocar por gradiente analítico ou cápsula-caixa fechada se o
#: usuário notar engasgos ao entrar/sair de gestos.
#: Passos de melhoria por quadro, combinados com limite suave de variação por eixo
#: para contornar o tronco gradualmente sem saltos nem travar em mínimos locais.
ITERACOES_POR_QUADRO = 4
#: Deslocamento máximo acumulado (graus) por grau de liberdade.
DESLOCAMENTO_MAXIMO_GRAUS = 70.0
#: Variação máxima (graus/quadro) permitida em roços leves.
MAX_VARIACAO_POR_QUADRO_GRAUS = 10.0
#: Fração do deslocamento mantida por quadro quando a pose já está livre.
RELAXAMENTO_POR_QUADRO = 0.85
#: Deslocamento (graus) abaixo do qual o relaxamento zera de vez.
DESLOCAMENTO_DESPREZIVEL_GRAUS = 0.05
#: Graus de liberdade corrigidos: P, H, R do ombro e flexão do cotovelo.
GRAUS_DE_LIBERDADE = 4

_GRUPOS = {
    "right": ("right-arm", "ant-arm", "hand"),
    "left": ("left-arm", "ant-arm2", "hand2"),
}
_OMBROS = {"right": "shoulder", "left": "shoulder2"}


_RAIZ_ISENTA_CACHE: dict[int, tuple[object, float]] = {}


def raiz_isenta(model: Model) -> float:
    """Comprimento da raiz do braço que fica no tronco por construção do asset."""
    key = id(model)
    cached = _RAIZ_ISENTA_CACHE.get(key)
    if cached is not None and cached[0] is model:
        return cached[1]
    x_ombro = abs(cin.posicao_no(model, _GRUPOS["right"][0])[0])
    valor = max(0.0, MEIA_LARGURA_TRONCO_U + RAIO_BRACO_U - x_ombro)
    _RAIZ_ISENTA_CACHE[key] = (model, valor)
    return valor


def capsulas_do_braco(
    model: Model, lado: str, pose: dict[str, Rotation3]
) -> list[Capsula]:
    """Cápsulas da cadeia ombro→cotovelo→punho→ponta dos dedos, sem a raiz isenta."""
    braco, antebraco, mao = _GRUPOS[lado]
    nos = cin.cadeia(model, mao, pose)
    rot_mao, punho = nos[mao]
    eixo_osso = (
        cin.EIXO_DIREITA if lado == "right" else cin.espelhar_ponto(cin.EIXO_DIREITA)
    )
    ponta = cin.somar(
        punho, cin.escalar(cin.aplicar(rot_mao, eixo_osso), COMPRIMENTO_MAO_U)
    )
    raiz, cotovelo = nos[braco][1], nos[antebraco][1]
    fim_ombro = cotovelo
    restante = raiz_isenta(model)
    capsulas: list[Capsula] = []

    for inicio, fim, raio in (
        (raiz, fim_ombro, RAIO_BRACO_U),
        (cotovelo, punho, RAIO_BRACO_U),
        (punho, ponta, RAIO_MAO_U),
    ):
        trecho = cin.subtrair(fim, inicio)
        comprimento = cin.norma(trecho)

        if restante >= comprimento:
            restante -= comprimento
            continue

        if restante > 0.0:
            inicio = cin.somar(inicio, cin.escalar(trecho, restante / comprimento))
            restante = 0.0

        capsulas.append(Capsula(inicio, fim, raio))

    return capsulas


def _longe(capsula: Capsula, caixa: CaixaOrientada) -> bool:
    """Descarte barato: esfera da cápsula e esfera circunscrita da caixa não se tocam."""
    meio = cin.escalar(cin.somar(capsula.a, capsula.b), 1 / 2)
    meio_comprimento = cin.norma(cin.subtrair(capsula.b, capsula.a)) / 2
    distancia = cin.norma(cin.subtrair(meio, caixa.centro))

    return distancia > meio_comprimento + cin.norma(caixa.meias_dim) + capsula.raio


def _rotacionar_caixa(
    caixa: CaixaOrientada,
    rot: cin.Mat3,
    pivo: Vec3,
    novo_pivo: Vec3 | None = None,
) -> CaixaOrientada:
    """Transforma ``caixa`` por ``rot`` em torno de ``pivo`` (opcionalmente transladando para ``novo_pivo``)."""
    destino = pivo if novo_pivo is None else novo_pivo
    centro = cin.somar(destino, cin.aplicar(rot, cin.subtrair(caixa.centro, pivo)))
    eixos = (
        cin.aplicar(rot, caixa.eixos[0]),
        cin.aplicar(rot, caixa.eixos[1]),
        cin.aplicar(rot, caixa.eixos[2]),
    )
    return CaixaOrientada(centro=centro, eixos=eixos, meias_dim=caixa.meias_dim)


def _rotacao_nula(rot: Rotation3 | None) -> bool:
    return rot is None or (
        abs(rot.x) < 1e-6 and abs(rot.y) < 1e-6 and abs(rot.z) < 1e-6
    )


def _rotacionar_caixas_inferiores(
    model: Model,
    pose: dict[str, Rotation3],
    caixas: dict[str, CaixaOrientada],
    leg_pose: object | None,
) -> bool:
    """Aplica pitch das coxas, rotação de ``legs`` e inverso de ``peitoral`` às caixas inferiores."""
    ang_dir = float(getattr(leg_pose, "right", 0.0) or 0.0) if leg_pose is not None else 0.0
    ang_esq = float(getattr(leg_pose, "left", 0.0) or 0.0) if leg_pose is not None else 0.0
    tem_coxas = abs(ang_dir) > 1.0 or abs(ang_esq) > 1.0
    tem_tronco = any(not _rotacao_nula(pose.get(g)) for g in ("body", "cintura", "abdomen", "peitoral"))
    tem_quadril = not _rotacao_nula(pose.get("legs"))
    if not (tem_coxas or tem_tronco or tem_quadril):
        return False
    if abs(ang_dir) > 1.0:
        caixas["coxa_direita"] = _rotacionar_caixa(
            caixas["coxa_direita"], cin.rot_x(-radians(ang_dir)), _PIVO_COXA_DIR
        )
    if abs(ang_esq) > 1.0:
        caixas["coxa_esquerda"] = _rotacionar_caixa(
            caixas["coxa_esquerda"], cin.rot_x(-radians(ang_esq)), _PIVO_COXA_ESQ
        )
    inferiores = ("quadril", "coxa_direita", "coxa_esquerda", "pe_direito", "pe_esquerdo")
    if tem_quadril:
        r_base, o_base = cin.transformacao_no(model, "legs")
        r_legs, o_legs = cin.transformacao_no(model, "legs", pose)
        r_quadril = cin.mul(r_legs, cin.transposta(r_base))
        for nome in inferiores:
            caixas[nome] = _rotacionar_caixa(caixas[nome], r_quadril, o_base, o_legs)
    if tem_tronco:
        r_peit, o_peit = cin.transformacao_no(model, "peitoral", pose)
        r_peit_repouso, o_peit_repouso = cin.transformacao_no(model, "peitoral")
        r_inv = cin.mul(r_peit_repouso, cin.transposta(r_peit))
        for nome in inferiores:
            caixas[nome] = _rotacionar_caixa(caixas[nome], r_inv, o_peit, o_peit_repouso)
    return True


def caixas_corpo_na_pose(
    model: Model,
    pose: dict[str, Rotation3],
    *,
    somente_cabeca: bool = False,
    leg_pose: object | None = None,
) -> dict[str, CaixaOrientada]:
    """Caixas de ``CAIXAS_CORPO`` no referencial local do peitoral para a ``pose`` atual.

    Em runtime (``FlexibleRig``), ``peitoral`` carrega ``head`` e os braços.
    Assim, ``tronco`` acompanha o peitoral, ``cabeca``/``topo_cabeca`` giram pela
    rotação local de ``head`` e ``quadril``/``coxa_*``/``pe_*`` giram pelo inverso
    de ``peitoral`` (mais o pitch real do quadril em ``leg_pose``).
    """
    tem_head = not _rotacao_nula(pose.get("head"))
    caixas = {"cabeca": CAIXAS_CORPO["cabeca"]} if somente_cabeca else dict(CAIXAS_CORPO)
    if tem_head:
        r_base, o_base = cin.transformacao_no(model, "head")
        r_head, o_head = cin.transformacao_no(model, "head", pose)
        m_head = cin.mul(r_head, cin.transposta(r_base))
        for nome in (("cabeca",) if somente_cabeca else ("cabeca", "topo_cabeca")):
            caixas[nome] = _rotacionar_caixa(caixas[nome], m_head, o_base, o_head)
    if somente_cabeca:
        return caixas
    if not _rotacionar_caixas_inferiores(model, pose, caixas, leg_pose) and not tem_head:
        return CAIXAS_CORPO
    return caixas


def penetracao_do_lado(
    model: Model,
    lado: str,
    pose: dict[str, Rotation3],
    do_outro: list[Capsula] | None = None,
    caixas: dict[str, CaixaOrientada] | None = None,
    *,
    somente_mao: bool = False,
    caixas_isentas: set[str] | frozenset[str] = frozenset(),
) -> float:
    """Maior penetração (u) das cápsulas do ``lado`` no corpo e no outro braço.

    ``do_outro`` permite reaproveitar as cápsulas do outro braço quando só este
    lado muda (busca do resolvedor).
    """
    minhas = capsulas_do_braco(model, lado, pose)
    if somente_mao:
        minhas = minhas[-1:]

    if do_outro is None and COLISAO_ENTRE_BRACOS:
        do_outro = capsulas_do_braco(
            model, "left" if lado == "right" else "right", pose
        )
    if not COLISAO_ENTRE_BRACOS:
        do_outro = []
    if caixas is None:
        caixas = caixas_corpo_na_pose(model, pose)
    maior = 0.0

    for capsula in minhas:
        for nome, caixa in caixas.items():
            if nome in caixas_isentas or _longe(capsula, caixa):
                continue

            folga_extra = 0.0 if somente_mao else FOLGA_EXTRA_CAIXA_U.get(nome, 0.0)
            maior = max(maior, penetracao_capsula_caixa(capsula, caixa) - folga_extra)

        for alheia in do_outro:
            maior = max(maior, penetracao_capsula_capsula(capsula, alheia))

    return maior


def _com_deslocamento(
    pose: dict[str, Rotation3], lado: str, deslocamento: list[float]
) -> dict[str, Rotation3]:
    """Pose com o deslocamento (graus, convenção do braço DIREITO) somado ao lado."""
    braco, antebraco, _mao = _GRUPOS[lado]
    if not any(deslocamento) and braco in pose and antebraco in pose:
        return pose
    dp, dh, dr, dflexao = (radians(v) for v in deslocamento)
    atual_braco = pose.get(braco, Rotation3())
    atual_ante = pose.get(antebraco, Rotation3())
    soma_braco = Rotation3(dp, dh, dr)
    soma_ante = Rotation3(0.0, 0.0, dflexao)

    if lado == "left":
        soma_braco, soma_ante = (
            cin.espelhar_rotacao(soma_braco),
            cin.espelhar_rotacao(soma_ante),
        )

    resultado = dict(pose)
    resultado[braco] = Rotation3(
        atual_braco.x + soma_braco.x,
        atual_braco.y + soma_braco.y,
        atual_braco.z + soma_braco.z,
    )
    resultado[antebraco] = Rotation3(
        atual_ante.x + soma_ante.x,
        atual_ante.y + soma_ante.y,
        atual_ante.z + soma_ante.z,
    )

    return resultado


@dataclass
class ResolvedorBracos:
    """Corrige a pose para os braços não atravessarem o corpo (com estado)."""

    model: Model
    somente_cabeca: bool = False

    def __post_init__(self) -> None:
        """Valida e normaliza os campos após a criação."""
        self._do_outro: list[Capsula] | None = None
        self._caixas_pose: dict[str, CaixaOrientada] | None = None
        self._isentas_lado_atual: set[str] | frozenset[str] = frozenset()
        self._ultimo_cache_chave: tuple | None = None
        self._ultima_pose_cache: dict[str, Rotation3] | None = None
        self._deslocamento: dict[str, list[float]] = {
            "right": [0.0] * GRAUS_DE_LIBERDADE,
            "left": [0.0] * GRAUS_DE_LIBERDADE,
        }

    def zerar(self) -> None:
        """Zera os deslocamentos acumulados ao iniciar uma transição explícita."""
        self._ultimo_cache_chave = None
        self._ultima_pose_cache = None
        for desloc in self._deslocamento.values():
            desloc[:] = [0.0] * GRAUS_DE_LIBERDADE

    def relaxar_suave(self, dt: float = 1.0 / 60.0) -> None:
        """Decai suavemente os deslocamentos sem estalar braços nas transições."""
        self._ultimo_cache_chave = None
        passo = max(1e-4, min(0.05, float(dt)))
        fator = RELAXAMENTO_POR_QUADRO ** (passo * 60.0)
        for desloc in self._deslocamento.values():
            for i, val in enumerate(desloc):
                novo = val * fator
                desloc[i] = 0.0 if abs(novo) < DESLOCAMENTO_DESPREZIVEL_GRAUS else novo

    def deslocamento(self, lado: str) -> tuple[float, ...]:
        """Deslocamento corrente (graus) do lado, para diagnóstico."""
        return tuple(self._deslocamento[lado])

    @staticmethod
    def _assinatura_pose(
        pose: dict[str, Rotation3],
        peso: float,
        leg_pose: object | None,
        isentas: dict[str, set[str]] | None,
    ) -> tuple:
        itens = tuple(
            (g, round(r.x, 4), round(r.y, 4), round(r.z, 4))
            for g, r in sorted(pose.items())
        )
        perna = (
            (
                round(float(getattr(leg_pose, "left", 0.0) or 0.0), 2),
                round(float(getattr(leg_pose, "right", 0.0) or 0.0), 2),
            )
            if leg_pose is not None
            else (0.0, 0.0)
        )
        is_key = (
            tuple((k, tuple(sorted(v))) for k, v in sorted(isentas.items()))
            if isentas
            else ()
        )
        return (itens, round(peso, 3), perna, is_key)

    def resolver(
        self,
        pose: dict[str, Rotation3],
        *,
        peso: float = 1.0,
        dt: float = 1.0 / 60.0,
        leg_pose: object | None = None,
        caixas_isentas_por_lado: dict[str, set[str]] | None = None,
    ) -> dict[str, Rotation3]:
        """Devolve a pose com os braços corrigidos (cópia; a original não muda)."""
        dt_s = max(1e-4, min(0.05, float(dt)))
        fator = max(0.0, min(1.0, peso))
        if fator <= 1e-4:
            self.relaxar_suave(dt_s)
            return dict(pose)
        chave = self._assinatura_pose(pose, fator, leg_pose, caixas_isentas_por_lado)
        if (
            chave == self._ultimo_cache_chave
            and self._ultima_pose_cache is not None
            and not any(self._deslocamento["right"])
            and not any(self._deslocamento["left"])
        ):
            return dict(self._ultima_pose_cache)
        self._dt_escala = dt_s * 60.0
        self._fator_relax = RELAXAMENTO_POR_QUADRO ** self._dt_escala
        resultado = dict(pose)
        self._caixas_pose = caixas_corpo_na_pose(
            self.model,
            pose,
            somente_cabeca=self.somente_cabeca,
            leg_pose=leg_pose,
        )

        for lado in ("right", "left"):
            self._isentas_lado_atual = (
                frozenset(caixas_isentas_por_lado.get(lado, ()))
                if caixas_isentas_por_lado
                else frozenset()
            )
            resultado = self._resolver_lado(resultado, lado, peso=fator)
        self._isentas_lado_atual = frozenset()
        if not any(self._deslocamento["right"]) and not any(self._deslocamento["left"]):
            self._ultimo_cache_chave = chave
            self._ultima_pose_cache = dict(resultado)
        else:
            self._ultimo_cache_chave = None
        return resultado

    def _penetracao(
        self, pose: dict[str, Rotation3], lado: str, desloc: list[float]
    ) -> float:
        return penetracao_do_lado(
            self.model,
            lado,
            _com_deslocamento(pose, lado, desloc),
            do_outro=self._do_outro,
            caixas=self._caixas_pose,
            somente_mao=self.somente_cabeca,
            caixas_isentas=self._isentas_lado_atual,
        )

    def _testar_eixos_passo(
        self,
        pose: dict[str, Rotation3],
        lado: str,
        desloc: list[float],
        desloc_inicial: list[float],
        limite_var: float,
        passo: float,
        melhor_pen: float,
    ) -> tuple[list[float] | None, float]:
        """Avalia +-passo em cada grau de liberdade respeitando o limite do quadro."""
        melhor: list[float] | None = None
        for eixo in range(GRAUS_DE_LIBERDADE):
            min_v = max(-DESLOCAMENTO_MAXIMO_GRAUS, desloc_inicial[eixo] - limite_var)
            max_v = min(DESLOCAMENTO_MAXIMO_GRAUS, desloc_inicial[eixo] + limite_var)
            for sinal in (1.0, -1.0):
                tentativa = list(desloc)
                tentativa[eixo] = max(min_v, min(max_v, tentativa[eixo] + sinal * passo))
                if tentativa[eixo] == desloc[eixo]:
                    continue
                pen = self._penetracao(pose, lado, tentativa)
                if pen < melhor_pen - 1e-6:
                    melhor, melhor_pen = tentativa, pen
        return melhor, melhor_pen

    def _buscar_correcao(
        self,
        pose: dict[str, Rotation3],
        lado: str,
        desloc: list[float],
        atual: float,
    ) -> float:
        """Executa busca em grade decrescente para afastar o braço da colisão."""
        desloc_inicial = list(desloc)
        escala_dt = getattr(self, "_dt_escala", 1.0)
        limite_var = (
            MAX_VARIACAO_POR_QUADRO_GRAUS * escala_dt
            if atual <= 0.02
            else 28.0 * min(2.0, max(0.25, escala_dt))
        )
        for _ in range(ITERACOES_POR_QUADRO):
            if atual <= FOLGA_PENETRACAO_U:
                break
            melhor: list[float] | None = None
            melhor_pen = atual
            passos = PASSOS_BUSCA_GRAUS[::-1] if atual > 0.012 else PASSOS_BUSCA_GRAUS
            for passo in passos:
                melhor, melhor_pen = self._testar_eixos_passo(
                    pose, lado, desloc, desloc_inicial, limite_var, passo, melhor_pen
                )
                if melhor is not None:
                    break
            if melhor is None:
                break  # sem progresso (mínimo local ou limite): aceita o que há
            desloc[:] = melhor
            atual = melhor_pen
        return atual

    def _relaxar_eixo(
        self, pose: dict[str, Rotation3], lado: str, desloc: list[float], eixo: int
    ) -> None:
        """Relaxa um eixo individualmente para não congelar os demais."""
        fator_rel = getattr(self, "_fator_relax", RELAXAMENTO_POR_QUADRO)
        for fator in (fator_rel, 0.5 * (1.0 + fator_rel)):
            novo = desloc[eixo] * fator
            valor = 0.0 if abs(novo) < DESLOCAMENTO_DESPREZIVEL_GRAUS else novo
            tentativa = list(desloc)
            tentativa[eixo] = valor
            if self._penetracao(pose, lado, tentativa) <= FOLGA_PENETRACAO_U:
                desloc[eixo] = valor
                return

    def _relaxar_deslocamento(
        self, pose: dict[str, Rotation3], lado: str, desloc: list[float]
    ) -> None:
        """Retorna suavemente o deslocamento ao repouso quando fora de colisão."""
        fator_rel = getattr(self, "_fator_relax", RELAXAMENTO_POR_QUADRO)
        relaxado = [
            0.0 if abs(v * fator_rel) < DESLOCAMENTO_DESPREZIVEL_GRAUS else v * fator_rel
            for v in desloc
        ]
        if self._penetracao(pose, lado, relaxado) <= FOLGA_PENETRACAO_U:
            desloc[:] = relaxado
            return
        for eixo in range(GRAUS_DE_LIBERDADE):
            if desloc[eixo] != 0.0:
                self._relaxar_eixo(pose, lado, desloc, eixo)

    def _liberar_mao_do_visor(
        self, pose: dict[str, Rotation3], lado: str, desloc: list[float], atual: float
    ) -> float:
        """Em um corte abrupto, recua só o trecho necessário em direção ao braço aberto."""
        braco, antebraco, _ = _GRUPOS[lado]
        ombro = pose.get(braco, Rotation3())
        cotovelo = pose.get(antebraco, Rotation3())
        if lado == "left":
            ombro = cin.espelhar_rotacao(ombro)
            cotovelo = cin.espelhar_rotacao(cotovelo)
        angulos = (ombro.x, ombro.y, ombro.z, cotovelo.z)
        recuos = [
            (-degrees(a) - d + 180.0) % 360.0 - 180.0
            for a, d in zip(angulos, desloc, strict=True)
        ]

        def amostrar(fracao: float) -> list[float]:
            return [d + r * fracao for d, r in zip(desloc, recuos, strict=True)]

        # O braço aberto aponta para fora do gabinete. A bisseção preserva o
        # máximo do gesto, inclusive quando a busca por eixo parou num canto.
        aberto = amostrar(1.0)
        if self._penetracao(pose, lado, aberto) > FOLGA_PENETRACAO_U:
            return atual
        dentro, fora = 0.0, 1.0
        for _ in range(7):
            meio = (dentro + fora) * 0.5
            if self._penetracao(pose, lado, amostrar(meio)) > FOLGA_PENETRACAO_U:
                dentro = meio
            else:
                fora = meio
        desloc[:] = amostrar(fora)
        return self._penetracao(pose, lado, desloc)

    def _resolver_lado(
        self, pose: dict[str, Rotation3], lado: str, *, peso: float = 1.0
    ) -> dict[str, Rotation3]:
        """Resolve a colisão do braço esquerdo ou direito mantendo o movimento mínimo."""
        desloc = self._deslocamento[lado]
        if COLISAO_ENTRE_BRACOS and not self.somente_cabeca:
            outro = "left" if lado == "right" else "right"
            self._do_outro = capsulas_do_braco(self.model, outro, pose)
        else:
            self._do_outro = []
        atual = self._penetracao(pose, lado, desloc)
        atual = self._buscar_correcao(pose, lado, desloc, atual)
        if self.somente_cabeca and atual > FOLGA_PENETRACAO_U:
            # Um corte de pose pode deixar a correção anterior do lado errado
            # do visor. Tenta a pose autoral antes de prolongar esse desvio.
            neutro = [0.0] * GRAUS_DE_LIBERDADE
            pen_neutra = self._penetracao(pose, lado, neutro)
            if pen_neutra < atual:
                desloc[:] = neutro
                atual = pen_neutra
            atual = self._buscar_correcao(pose, lado, desloc, atual)
            if atual > FOLGA_PENETRACAO_U:
                atual = self._liberar_mao_do_visor(pose, lado, desloc, atual)
        if any(desloc) and atual <= FOLGA_PENETRACAO_U:
            self._relaxar_deslocamento(pose, lado, desloc)
        if peso < 1.0 - 1e-4:
            escalado = [v * peso for v in desloc]
            return _com_deslocamento(pose, lado, escalado)
        return _com_deslocamento(pose, lado, desloc)
