"""Ferramenta de ANÁLISE DE CURVA DE ANIMAÇÃO (código puro, sem engine).

Transforma o julgamento visual de qualidade de movimento em MÉTRICAS objetivas
sobre os DADOS de animação. A motivação é concreta: um agente (e o reviewer
automático) não avalia bem qualidade visual olhando GIFs/frames; aqui os
problemas de movimento são detectados numericamente a partir das curvas de
ângulo por junta/eixo, para orientar ajustes ANTES da avaliação estética humana.

Fronteira: Python puro. NÃO importa Panda3D, Qt ou Win32. O único acoplamento é
ler clipes como dados (tracks de keyframes em graus) das fontes do projeto.

Interface desacoplada de fonte
------------------------------
O analisador trabalha sobre um :class:`ClipeAnalisavel`: uma função amostradora
``amostrar(t) -> {grupo: (x, y, z)}``, a ``duracao`` em segundos e uma flag
``loop``. Qualquer fonte que produza esse formato pode ser analisada, inclusive
os clipes de RASCUNHO A1-A5 de ``src/sejoga/_preview/clipes_rascunho.py`` (ver
``_carregar_rascunho`` abaixo para apontar o analisador a eles).

Uso (CLI)
---------
    python tools/analisar_anim.py --fonte producao
    python tools/analisar_anim.py --fonte idle --clipe street
    python tools/analisar_anim.py --fonte rascunho --clipe comemorar --md laudo.md
    python tools/analisar_anim.py --fonte producao --png-dir graficos/
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

# --------------------------------------------------------------------------- #
# THRESHOLDS — limiares nomeados, comentados e ajustáveis.
#
# Calibração: as curvas são em GRAUS, amostradas a 60 fps. Jerk e aceleração
# ficam em graus/s^2 e graus/s^3. Os valores abaixo são razoáveis, não perfeitos;
# o objetivo é serem TRANSPARENTES — ajuste conforme o gosto do estúdio.
# --------------------------------------------------------------------------- #

#: Taxa de amostragem da análise. 60 fps casa com o alvo de render.
FPS = 60.0

#: Pico de jerk (graus/s^3) acima do qual o frame é marcado como TRANCO.
#: Um easing quíntico bem comportado mantém o jerk baixo; estouros aqui
#: indicam degraus de aceleração ("robótico/abrupto"). Calibrado observando
#: que os clipes de produção suaves ficam na casa de centenas; trancos reais
#: passam de poucos milhares.
LIMIAR_JERK_TRANCO = 8000.0

#: Fração mínima do deslocamento principal que o contra-movimento inicial deve
#: ter para contar como ANTECIPAÇÃO legível. Abaixo disso, "sem antecipação".
FRACAO_MIN_ANTECIPACAO = 0.04

#: Janela inicial (fração da duração) onde procuramos a antecipação.
JANELA_ANTECIPACAO = 0.35

#: Descontinuidade de POSIÇÃO no fechamento do loop (graus) acima da qual há
#: "pop" de posição. Clipes bem fechados batem praticamente em zero.
LIMIAR_POP_POSICAO = 0.5

#: Descontinuidade de VELOCIDADE no fechamento do loop (graus/s) acima da qual
#: há "pop" de velocidade (a derivada salta mesmo quando a posição fecha).
LIMIAR_POP_VELOCIDADE = 30.0

#: Diferença RMS (graus) abaixo da qual duas juntas espelhadas são consideradas
#: espelho EXATO (lê como robô). Compara uma junta com o espelho da parceira.
LIMIAR_SIMETRIA_EXATA = 0.75

#: Amplitude mínima (graus) para uma junta ser considerada "ativa" — abaixo
#: disso ela é ruído/repouso e não entra em simetria/follow-through.
AMPLITUDE_MINIMA_ATIVA = 2.0

#: Diferença máxima de TEMPO DE PARADA (segundos) entre juntas de uma cadeia
#: para acusar PARADA SIMULTÂNEA (rígido, sem follow-through escalonado).
LIMIAR_PARADA_SIMULTANEA = 1.0 / FPS * 1.5

#: Overshoot: fração do alvo que a curva ultrapassa e volta. Acima disso há
#: overshoot legível (bom para snap). Serve de diagnóstico, não de erro.
FRACAO_OVERSHOOT = 0.03


# --------------------------------------------------------------------------- #
# Modelo do rig relevante para a análise de cadeia/simetria.
# --------------------------------------------------------------------------- #

#: Cadeias de braço (da raiz à ponta) para avaliar follow-through/overlap.
CADEIAS = (
    ("right-arm", "ant-arm", "hand", "fingers"),
    ("left-arm", "ant-arm2", "hand2", "fingers2"),
)

#: Pares espelhados (direita, esquerda) para avaliar simetria rígida.
PARES_ESPELHO = (
    ("right-arm", "left-arm"),
    ("ant-arm", "ant-arm2"),
    ("hand", "hand2"),
    ("fingers", "fingers2"),
    ("left-feet", "right-feet"),
)

#: Nomes amigáveis em português para o laudo.
NOMES_JUNTAS = {
    "right-arm": "braço direito",
    "left-arm": "braço esquerdo",
    "ant-arm": "antebraço direito",
    "ant-arm2": "antebraço esquerdo",
    "hand": "mão direita",
    "hand2": "mão esquerda",
    "fingers": "dedos direitos",
    "fingers2": "dedos esquerdos",
    "left-feet": "pé esquerdo",
    "right-feet": "pé direito",
    "body": "tronco",
    "head": "cabeça",
    "legs": "pernas",
    "door": "portinha",
}

EIXOS = ("x", "y", "z")


def nome_junta(grupo: str) -> str:
    """Devolve o nome amigável da junta, ou o próprio id se desconhecido."""
    return NOMES_JUNTAS.get(grupo, grupo)


# --------------------------------------------------------------------------- #
# Interface de fonte: um clipe analisável é "amostrador + duração + loop".
# --------------------------------------------------------------------------- #

Amostrador = Callable[[float], dict[str, tuple[float, float, float]]]


@dataclass(frozen=True)
class ClipeAnalisavel:
    """Clipe desacoplado de fonte: função amostradora, duração e flag loop."""

    nome: str
    amostrar: Amostrador
    duracao: float
    loop: bool


# --------------------------------------------------------------------------- #
# Amostragem e cálculo numérico de derivadas.
# --------------------------------------------------------------------------- #

@dataclass
class SerieEixo:
    """Série temporal de um eixo de uma junta e suas derivadas numéricas."""

    angulo: list[float] = field(default_factory=list)
    velocidade: list[float] = field(default_factory=list)
    aceleracao: list[float] = field(default_factory=list)
    jerk: list[float] = field(default_factory=list)


@dataclass
class AmostragemClipe:
    """Resultado da amostragem: tempos e, por junta/eixo, a série e derivadas."""

    nome: str
    duracao: float
    loop: bool
    tempos: list[float]
    # grupo -> (serie_x, serie_y, serie_z)
    series: dict[str, tuple[SerieEixo, SerieEixo, SerieEixo]]


def _derivar(valores: list[float], dt: float) -> list[float]:
    """Derivada numérica por diferenças centrais (bordas por diferença simples).

    Diferença central reduz o viés nas bordas e mantém o mesmo comprimento da
    série de entrada, o que simplifica alinhar ângulo/velocidade/aceleração.
    """
    n = len(valores)

    if n < 2:
        return [0.0] * n

    saida = [0.0] * n
    saida[0] = (valores[1] - valores[0]) / dt
    saida[-1] = (valores[-1] - valores[-2]) / dt

    for i in range(1, n - 1):
        saida[i] = (valores[i + 1] - valores[i - 1]) / (2.0 * dt)

    return saida


def amostrar_clipe_analisavel(clipe: ClipeAnalisavel) -> AmostragemClipe:
    """Amostra o clipe a ``FPS`` na duração e deriva velocidade/aceleração/jerk.

    Loop: amostra um ciclo completo e repete o primeiro frame no fim para medir
    o fechamento. Não-loop: do início ao fim (inclusive o último frame).
    """
    dt = 1.0 / FPS
    n_passos = max(2, round(clipe.duracao * FPS))
    tempos: list[float] = [i * dt for i in range(n_passos + 1)]

    # Coleta ângulos por junta/eixo.
    brutos: dict[str, tuple[list[float], list[float], list[float]]] = {}

    for t in tempos:
        pose = clipe.amostrar(t)
        for grupo, (gx, gy, gz) in pose.items():
            if grupo not in brutos:
                brutos[grupo] = ([], [], [])
            brutos[grupo][0].append(gx)
            brutos[grupo][1].append(gy)
            brutos[grupo][2].append(gz)

    series: dict[str, tuple[SerieEixo, SerieEixo, SerieEixo]] = {}

    for grupo, eixos in brutos.items():
        trio: list[SerieEixo] = []
        for ang in eixos:
            vel = _derivar(ang, dt)
            acel = _derivar(vel, dt)
            jerk = _derivar(acel, dt)
            trio.append(SerieEixo(ang, vel, acel, jerk))
        series[grupo] = (trio[0], trio[1], trio[2])

    return AmostragemClipe(
        nome=clipe.nome,
        duracao=clipe.duracao,
        loop=clipe.loop,
        tempos=tempos,
        series=series,
    )


# --------------------------------------------------------------------------- #
# Constatações do laudo.
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Constatacao:
    """Um achado priorizado do laudo."""

    prioridade: int  # 1 = mais grave
    categoria: str
    grupo: str
    eixo: str | None
    tempo: float | None
    metrica: str
    recomendacao: str

    def formatar(self) -> str:
        partes = [f"[{self.categoria}] {nome_junta(self.grupo)}"]

        if self.eixo:
            partes.append(f"eixo {self.eixo}")

        if self.tempo is not None:
            partes.append(f"t={self.tempo:.2f}s")

        cabecalho = " · ".join(partes)

        return f"{cabecalho}\n    {self.metrica}\n    → {self.recomendacao}"


# --------------------------------------------------------------------------- #
# Métricas auxiliares.
# --------------------------------------------------------------------------- #

def _amplitude(serie: SerieEixo) -> float:
    """Amplitude pico-a-pico da série de ângulo."""
    if not serie.angulo:
        return 0.0

    return max(serie.angulo) - min(serie.angulo)


def _amplitude_junta(trio: tuple[SerieEixo, SerieEixo, SerieEixo]) -> float:
    """Maior amplitude entre os três eixos da junta."""
    return max(_amplitude(s) for s in trio)


def _tempo_de_parada(serie: SerieEixo, tempos: list[float]) -> float | None:
    """Último instante em que a velocidade do eixo cai e fica abaixo do ruído.

    Usado para follow-through: juntas que "assentam" no mesmo instante são
    rígidas; o ideal é a ponta da cadeia parar depois da raiz.
    """
    if _amplitude(serie) < AMPLITUDE_MINIMA_ATIVA:
        return None

    pico_vel = max(abs(v) for v in serie.velocidade) or 1.0
    piso = pico_vel * 0.08

    for i in range(len(serie.velocidade) - 1, -1, -1):
        if abs(serie.velocidade[i]) > piso:
            return tempos[i]

    return None


# --------------------------------------------------------------------------- #
# Detectores.
# --------------------------------------------------------------------------- #

def detectar_trancos(am: AmostragemClipe) -> list[Constatacao]:
    """SUAVIDADE: picos de jerk indicam degrau de aceleração (robótico)."""
    achados: list[Constatacao] = []

    for grupo, trio in am.series.items():
        for eixo_nome, serie in zip(EIXOS, trio, strict=True):
            if _amplitude(serie) < AMPLITUDE_MINIMA_ATIVA:
                continue

            pior_jerk = 0.0
            pior_i = 0

            for i, j in enumerate(serie.jerk):
                if abs(j) > abs(pior_jerk):
                    pior_jerk = j
                    pior_i = i

            if abs(pior_jerk) >= LIMIAR_JERK_TRANCO:
                t = am.tempos[pior_i]
                achados.append(Constatacao(
                    prioridade=1,
                    categoria="SUAVIDADE",
                    grupo=grupo,
                    eixo=eixo_nome,
                    tempo=t,
                    metrica=(f"tranco: pico de jerk {pior_jerk:,.0f}°/s³ "
                             f"(limiar {LIMIAR_JERK_TRANCO:,.0f})"),
                    recomendacao=(f"suavize {nome_junta(grupo)} em t={t:.2f}s "
                                  f"com keyframe intermediário no eixo {eixo_nome} "
                                  "para quebrar o degrau de aceleração"),
                ))

    return achados


def detectar_antecipacao(am: AmostragemClipe) -> list[Constatacao]:
    """ANTECIPAÇÃO (só não-loop): contra-movimento antes do principal."""
    if am.loop:
        return []

    achados: list[Constatacao] = []

    for grupo, trio in am.series.items():
        for eixo_nome, serie in zip(EIXOS, trio, strict=True):
            amp = _amplitude(serie)

            if amp < AMPLITUDE_MINIMA_ATIVA:
                continue

            base = serie.angulo[0]

            # Deslocamento principal: maior afastamento absoluto do início.
            desloc_principal = max(serie.angulo, key=lambda a: abs(a - base))
            sentido = 1.0 if (desloc_principal - base) >= 0 else -1.0

            # Janela inicial onde a antecipação deve aparecer.
            fim_janela = max(1, int(len(serie.angulo) * JANELA_ANTECIPACAO))
            contra = 0.0

            for i in range(fim_janela):
                desvio = serie.angulo[i] - base
                # Contra-movimento = desvio no sentido OPOSTO ao principal.
                if desvio * sentido < 0:
                    contra = max(contra, abs(desvio))

            if contra < amp * FRACAO_MIN_ANTECIPACAO:
                achados.append(Constatacao(
                    prioridade=2,
                    categoria="ANTECIPAÇÃO",
                    grupo=grupo,
                    eixo=eixo_nome,
                    tempo=0.0,
                    metrica=(f"sem contra-movimento inicial (máx {contra:.2f}° "
                             f"< {amp * FRACAO_MIN_ANTECIPACAO:.2f}° exigido)"),
                    recomendacao=(f"adicione antecipação em {nome_junta(grupo)}: "
                                  f"um pequeno recuo no eixo {eixo_nome} oposto ao "
                                  "movimento antes de disparar o principal"),
                ))

    return achados


def detectar_follow_through(am: AmostragemClipe) -> list[Constatacao]:
    """FOLLOW-THROUGH/OVERLAP: juntas da cadeia que param ao MESMO tempo."""
    achados: list[Constatacao] = []

    for cadeia in CADEIAS:
        paradas: list[tuple[str, float]] = []

        for grupo in cadeia:
            trio = am.series.get(grupo)

            if trio is None:
                continue

            # Usa o eixo de maior amplitude da junta como referência.
            eixo_ref = max(trio, key=_amplitude)
            t_parada = _tempo_de_parada(eixo_ref, am.tempos)

            if t_parada is not None:
                paradas.append((grupo, t_parada))

        if len(paradas) < 2:
            continue

        tempos_parada = [t for _, t in paradas]
        espalhamento = max(tempos_parada) - min(tempos_parada)

        if espalhamento <= LIMIAR_PARADA_SIMULTANEA:
            t = tempos_parada[0]
            grupos_txt = ", ".join(nome_junta(g) for g, _ in paradas)
            ponta = nome_junta(paradas[-1][0])
            achados.append(Constatacao(
                prioridade=2,
                categoria="FOLLOW-THROUGH",
                grupo=paradas[-1][0],
                eixo=None,
                tempo=t,
                metrica=(f"cadeia para junta em t≈{t:.2f}s "
                         f"(espalhamento {espalhamento * 1000:.0f}ms): {grupos_txt}"),
                recomendacao=(f"escalone a parada: atrase {ponta} alguns frames "
                              "após a raiz da cadeia para gerar overlap/arrasto"),
            ))

    return achados


def detectar_fechamento_loop(am: AmostragemClipe) -> list[Constatacao]:
    """FECHAMENTO DE LOOP: descontinuidade de posição E velocidade (pop)."""
    if not am.loop:
        return []

    achados: list[Constatacao] = []

    for grupo, trio in am.series.items():
        for eixo_nome, serie in zip(EIXOS, trio, strict=True):
            if _amplitude(serie) < AMPLITUDE_MINIMA_ATIVA:
                continue

            salto_pos = abs(serie.angulo[-1] - serie.angulo[0])
            salto_vel = abs(serie.velocidade[-1] - serie.velocidade[0])

            if salto_pos >= LIMIAR_POP_POSICAO or salto_vel >= LIMIAR_POP_VELOCIDADE:
                detalhe_pos = f"Δposição {salto_pos:.2f}°"
                detalhe_vel = f"Δvelocidade {salto_vel:.1f}°/s"
                achados.append(Constatacao(
                    prioridade=1,
                    categoria="LOOP",
                    grupo=grupo,
                    eixo=eixo_nome,
                    tempo=am.duracao,
                    metrica=(f"pop no fechamento: {detalhe_pos}, {detalhe_vel}"),
                    recomendacao=(f"case o último e o primeiro keyframe de "
                                  f"{nome_junta(grupo)} (eixo {eixo_nome}) em "
                                  "posição e tangente para o loop não dar salto"),
                ))

    return achados


def detectar_simetria_rigida(am: AmostragemClipe) -> list[Constatacao]:
    """SIMETRIA RÍGIDA: pares espelhados com movimento espelho exato."""
    achados: list[Constatacao] = []

    for dir_g, esq_g in PARES_ESPELHO:
        trio_d = am.series.get(dir_g)
        trio_e = am.series.get(esq_g)

        if trio_d is None or trio_e is None:
            continue

        if (_amplitude_junta(trio_d) < AMPLITUDE_MINIMA_ATIVA
                or _amplitude_junta(trio_e) < AMPLITUDE_MINIMA_ATIVA):
            continue

        # Espelho esperado: X e Y iguais, Z com sinal trocado (roll espelhado).
        rms_total = 0.0
        n = 0

        for idx, (sinal) in enumerate((1.0, 1.0, -1.0)):
            ser_d = trio_d[idx]
            ser_e = trio_e[idx]
            m = min(len(ser_d.angulo), len(ser_e.angulo))

            for i in range(m):
                dif = ser_d.angulo[i] - sinal * ser_e.angulo[i]
                rms_total += dif * dif
                n += 1

        rms = (rms_total / n) ** 0.5 if n else 0.0

        if rms <= LIMIAR_SIMETRIA_EXATA:
            achados.append(Constatacao(
                prioridade=3,
                categoria="SIMETRIA",
                grupo=dir_g,
                eixo=None,
                tempo=None,
                metrica=(f"{nome_junta(dir_g)} e {nome_junta(esq_g)} em espelho "
                         f"exato (RMS {rms:.2f}° ≤ {LIMIAR_SIMETRIA_EXATA:.2f}°)"),
                recomendacao=(f"dessincronize o par: defase {nome_junta(esq_g)} "
                              "em alguns frames ou varie a amplitude para não "
                              "ler como robô"),
            ))

    return achados


def detectar_overshoot_amplitude(am: AmostragemClipe) -> list[Constatacao]:
    """OVERSHOOT/AMPLITUDE: ultrapassa o alvo e volta, ou chega 'seca'."""
    achados: list[Constatacao] = []

    # Só faz sentido falar de 'alvo' em clipes não-loop (começam/terminam parados).
    if am.loop:
        return []

    for grupo, trio in am.series.items():
        for eixo_nome, serie in zip(EIXOS, trio, strict=True):
            amp = _amplitude(serie)

            if amp < AMPLITUDE_MINIMA_ATIVA:
                continue

            base = serie.angulo[0]
            # Alvo = valor no instante de maior afastamento (pico do gesto).
            idx_pico = max(range(len(serie.angulo)),
                           key=lambda i: abs(serie.angulo[i] - base))
            alvo = serie.angulo[idx_pico]
            sentido = 1.0 if (alvo - base) >= 0 else -1.0

            # Settle: valor de regime no fim (média do último ~10%).
            cauda = serie.angulo[max(0, int(len(serie.angulo) * 0.9)):]
            settle = sum(cauda) / len(cauda)

            # Overshoot = quanto o pico passa do settle, no sentido do gesto.
            excesso = (alvo - settle) * sentido
            ref = abs(settle - base) or abs(amp)

            if ref > 0 and excesso > ref * FRACAO_OVERSHOOT and idx_pico < len(serie.angulo) - 2:
                t = am.tempos[idx_pico]
                achados.append(Constatacao(
                    prioridade=4,
                    categoria="OVERSHOOT",
                    grupo=grupo,
                    eixo=eixo_nome,
                    tempo=t,
                    metrica=(f"overshoot de {excesso:.1f}° antes de assentar em "
                             f"{settle:.1f}° (amplitude {amp:.1f}°)"),
                    recomendacao=(f"overshoot presente em {nome_junta(grupo)} "
                                  f"(eixo {eixo_nome}): bom para snap; confira se "
                                  "o settle de volta está suave"),
                ))

    return achados


def analisar(clipe: ClipeAnalisavel) -> tuple[AmostragemClipe, list[Constatacao]]:
    """Executa todos os detectores e devolve amostragem + constatações."""
    am = amostrar_clipe_analisavel(clipe)

    achados: list[Constatacao] = []
    achados += detectar_trancos(am)
    achados += detectar_fechamento_loop(am)
    achados += detectar_follow_through(am)
    achados += detectar_antecipacao(am)
    achados += detectar_simetria_rigida(am)
    achados += detectar_overshoot_amplitude(am)

    achados.sort(key=lambda c: (c.prioridade, c.grupo, c.tempo or 0.0))

    return am, achados


# --------------------------------------------------------------------------- #
# Laudo em texto.
# --------------------------------------------------------------------------- #

def montar_laudo(am: AmostragemClipe, achados: list[Constatacao]) -> str:
    """Monta o laudo em texto priorizado de um clipe."""
    tipo = "loop" if am.loop else "não-loop"
    juntas = len(am.series)
    linhas = [
        f"═══ LAUDO · clipe '{am.nome}' ({tipo}, {am.duracao:.2f}s, "
        f"{juntas} juntas, {FPS:.0f} fps) ═══",
    ]

    if not achados:
        linhas.append("  Nenhuma constatação acima dos limiares. Movimento limpo.")
        return "\n".join(linhas)

    rotulo = {1: "GRAVE", 2: "ATENÇÃO", 3: "ESTILO", 4: "INFO"}

    atual = None
    for c in achados:
        if c.prioridade != atual:
            atual = c.prioridade
            linhas.append(f"\n  ── {rotulo.get(c.prioridade, '?')} ──")
        linhas.append("  " + c.formatar().replace("\n", "\n  "))

    return "\n".join(linhas)


# --------------------------------------------------------------------------- #
# Gráfico PNG opcional (matplotlib se disponível; senão, pula sem falhar).
# --------------------------------------------------------------------------- #

def salvar_grafico(am: AmostragemClipe, destino: Path) -> bool:
    """Salva PNG das curvas de ângulo. Devolve False se matplotlib faltar."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    fig, ax = plt.subplots(figsize=(10, 5))

    for grupo, trio in am.series.items():
        if _amplitude_junta(trio) < AMPLITUDE_MINIMA_ATIVA:
            continue

        for eixo_nome, serie in zip(EIXOS, trio, strict=True):
            if _amplitude(serie) < AMPLITUDE_MINIMA_ATIVA:
                continue
            ax.plot(am.tempos, serie.angulo, label=f"{grupo}.{eixo_nome}", linewidth=1)

    ax.set_title(f"Curvas de ângulo · {am.nome}")
    ax.set_xlabel("tempo (s)")
    ax.set_ylabel("ângulo (graus)")
    ax.legend(fontsize=6, ncol=2, loc="upper right")
    ax.grid(True, alpha=0.3)

    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(destino, dpi=120)
    plt.close(fig)

    return True


# --------------------------------------------------------------------------- #
# Fontes de clipe.
# --------------------------------------------------------------------------- #

def _carregar_producao() -> dict[str, ClipeAnalisavel]:
    """Clipes de produção (walk, run) de ``sejoga.animacao.anim_clips``."""
    from sejoga.animacao import anim_clips

    clipes: dict[str, ClipeAnalisavel] = {}

    for nome, clipe in anim_clips.CLIPES.items():
        def amostrar(t: float, n: str = nome) -> dict[str, tuple[float, float, float]]:
            return anim_clips.amostrar_clipe(n, t)

        clipes[nome] = ClipeAnalisavel(
            nome=nome,
            amostrar=amostrar,
            duracao=clipe.duracao,
            loop=True,  # locomoção é cíclica
        )

    return clipes


#: Janela (s) de amostragem do idle procedural. NÃO é um "ciclo fechado": a base
#: procedural do idle é INTENCIONALMENTE APERIÓDICA (frequências incomensuráveis
#: + frases de 4.8-14 s) para parecer viva e não repetir mecanicamente. Em
#: produção o clock só cresce e o idle roda aberto para sempre; por isso o idle
#: é analisado como ``loop=False`` (sem teste de fechamento de loop). A janela
#: cobre as frases mais longas (~14 s) para medir energia e suavidade.
IDLE_JANELA_ANALISE = 30.0


def _carregar_idle() -> dict[str, ClipeAnalisavel]:
    """Idle procedural COMPLETO das 9 personalidades (Rig em repouso + pose_idle).

    Amostra o idle inteiro (base senoidal + frases autorais + camada de
    respiração viva), não apenas os deltas autorais de ``idle_clips.CLIPS``.
    A respiração é dirigida por uma ``Respiracao`` por personalidade (calibrada
    em ``respiracao_tuning``), igual ao que o ``AnimationController`` faz em
    tempo real.

    Marcado como ``loop=False``: a base procedural é aperiódica de propósito
    (roda aberta em produção), então NÃO se aplica teste de fechamento de loop a
    ela. O fechamento cíclico é verificado à parte, só sobre a camada de
    respiração (ver ``tests/test_idle_vivo.py``). Aqui medimos VIDA (energia > 0)
    e SUAVIDADE (ausência de trancos).
    """
    from sejoga.animacao.respiracao import Respiracao
    from sejoga.animacao.respiracao_tuning import parametros_de
    from sejoga.nucleo import rig as rig_mod

    fps = FPS
    dt = 1.0 / fps
    n_passos = max(2, round(IDLE_JANELA_ANALISE * fps))

    clipes: dict[str, ClipeAnalisavel] = {}

    for personalidade in rig_mod.IdlePersonality:
        # Pré-simula a respiração da personalidade frame a frame (como o
        # controller), guardando o valor centrado por índice de amostra.
        parametros = parametros_de(personalidade)
        respira = Respiracao(frequencia=parametros.frequencia,
                             amplitude=parametros.amplitude,
                             amortecimento=1.0 - parametros.bounce)
        trilha_respiracao: list[float] = [0.0]
        for _ in range(n_passos):
            trilha_respiracao.append(respira.atualizar(dt))

        def amostrar(t: float, p: rig_mod.IdlePersonality = personalidade,
                     trilha: list[float] = trilha_respiracao
                     ) -> dict[str, tuple[float, float, float]]:
            indice = min(len(trilha) - 1, round(t * fps))
            repouso = {g: rig_mod.Rotation3() for g in rig_mod.ALL_GROUPS}
            rig = rig_mod.Rig(rest=dict(repouso), current=dict(repouso))
            rig_mod.pose_idle(rig, t, p, trilha[indice])
            from math import degrees
            return {
                g: (degrees(r.x), degrees(r.y), degrees(r.z))
                for g, r in rig.pose().items()
            }

        clipes[personalidade.value] = ClipeAnalisavel(
            nome=personalidade.value,
            amostrar=amostrar,
            duracao=IDLE_JANELA_ANALISE,
            loop=False,
        )

    return clipes


def _carregar_rascunho() -> dict[str, ClipeAnalisavel]:
    """Clipes de RASCUNHO A1-A5 de ``sejoga._preview.clipes_rascunho``.

    O módulo de rascunho pode não existir na ``main`` (vive no branch
    ``feature/previews-anim-efeitos``). Para analisar os rascunhos sem acoplar
    a ferramenta a ele, procuramos o módulo em dois lugares, nesta ordem:

    1. Import normal ``sejoga._preview.clipes_rascunho`` (se estiver instalado).
    2. Arquivo solto apontado por ``SEJOGA_RASCUNHO`` ou nos caminhos conhecidos
       (worktree/branch), carregado via ``importlib`` sem precisar do pacote.

    Se nada for encontrado, levanta ``FileNotFoundError`` com instruções de como
    apontar (copiar ``src/sejoga/_preview/clipes_rascunho.py`` do branch).
    """
    modulo = _importar_rascunho()

    clipes: dict[str, ClipeAnalisavel] = {}

    for nome, clipe in modulo.CLIPES_RASCUNHO.items():
        def amostrar(t: float, n: str = nome) -> dict[str, tuple[float, float, float]]:
            resultado: dict[str, tuple[float, float, float]] = modulo.amostrar_rascunho(n, t)
            return resultado

        clipes[nome] = ClipeAnalisavel(
            nome=nome,
            amostrar=amostrar,
            duracao=clipe.duracao,
            loop=clipe.loop,
        )

    return clipes


def _importar_rascunho() -> ModuleType:
    """Localiza e importa o módulo de rascunho sem acoplamento rígido."""
    import os

    try:  # 1) já instalado no pacote
        from sejoga._preview import clipes_rascunho
        return clipes_rascunho
    except ImportError:
        pass

    candidatos: list[Path] = []

    env = os.environ.get("SEJOGA_RASCUNHO")
    if env:
        candidatos.append(Path(env))

    raiz = Path(__file__).resolve().parent.parent
    candidatos += [
        raiz / "src" / "sejoga" / "_preview" / "clipes_rascunho.py",
        raiz / ".worktrees" / "previews-anim-efeitos" / "src" / "sejoga"
        / "_preview" / "clipes_rascunho.py",
    ]

    for caminho in candidatos:
        if caminho.is_file():
            return _carregar_modulo_solto(caminho)

    raise FileNotFoundError(
        "clipes_rascunho não encontrado. Os rascunhos A1-A5 vivem no branch "
        "'feature/previews-anim-efeitos'. Aponte com a variável SEJOGA_RASCUNHO "
        "para o arquivo, ou copie "
        "src/sejoga/_preview/clipes_rascunho.py do branch para este ambiente."
    )


def _carregar_modulo_solto(caminho: Path) -> ModuleType:
    """Carrega um .py solto como módulo, injetando um pacote 'pai' mínimo.

    ``clipes_rascunho`` faz ``from ..idle_clips import sample_track``, então
    carregamos com um nome de pacote que resolve ``sejoga`` já instalado.
    """
    spec = importlib.util.spec_from_file_location(
        "sejoga._preview.clipes_rascunho", caminho
    )

    if spec is None or spec.loader is None:
        raise ImportError(f"não foi possível carregar {caminho}")

    modulo = importlib.util.module_from_spec(spec)

    # Garante que o pacote 'sejoga._preview' exista para o import relativo.
    if "sejoga._preview" not in sys.modules:
        pacote = ModuleType("sejoga._preview")
        pacote.__path__ = [str(caminho.parent)]  # pacote namespace mínimo
        sys.modules["sejoga._preview"] = pacote

    sys.modules["sejoga._preview.clipes_rascunho"] = modulo
    spec.loader.exec_module(modulo)

    return modulo


FONTES: dict[str, Callable[[], dict[str, ClipeAnalisavel]]] = {
    "producao": _carregar_producao,
    "idle": _carregar_idle,
    "rascunho": _carregar_rascunho,
}


# --------------------------------------------------------------------------- #
# CLI.
# --------------------------------------------------------------------------- #

def _montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Análise objetiva de curvas de animação (código puro).",
    )
    parser.add_argument(
        "--fonte", choices=sorted(FONTES), default="producao",
        help="origem dos clipes: producao (walk/run), idle ou rascunho (A1-A5)",
    )
    parser.add_argument(
        "--clipe", default=None,
        help="nome do clipe; se omitido, analisa todos da fonte",
    )
    parser.add_argument(
        "--md", type=Path, default=None,
        help="salva o laudo completo neste arquivo .md além da saída padrão",
    )
    parser.add_argument(
        "--png-dir", type=Path, default=None,
        help="salva um PNG das curvas por clipe nesta pasta (precisa matplotlib)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    # O laudo usa caracteres Unicode (ex.: ═ → °). No Windows, stdout pode vir
    # em cp1252 e quebrar ao redirecionar/pipar; forçamos UTF-8 quando possível.
    for fluxo in (sys.stdout, sys.stderr):
        reconfig = getattr(fluxo, "reconfigure", None)
        if callable(reconfig):
            reconfig(encoding="utf-8", errors="replace")

    args = _montar_parser().parse_args(argv)

    try:
        clipes = FONTES[args.fonte]()
    except FileNotFoundError as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2

    if args.clipe is not None:
        if args.clipe not in clipes:
            disponiveis = ", ".join(sorted(clipes))
            print(f"erro: clipe '{args.clipe}' não existe em '{args.fonte}'. "
                  f"Disponíveis: {disponiveis}", file=sys.stderr)
            return 2
        selecionados = {args.clipe: clipes[args.clipe]}
    else:
        selecionados = clipes

    laudos: list[str] = []

    for nome, clipe in selecionados.items():
        am, achados = analisar(clipe)
        laudo = montar_laudo(am, achados)
        laudos.append(laudo)
        print(laudo)
        print()

        if args.png_dir is not None:
            destino = args.png_dir / f"{args.fonte}_{nome}.png"
            if salvar_grafico(am, destino):
                print(f"  gráfico salvo em {destino}")
            else:
                print("  (matplotlib ausente: gráfico pulado)")

    if args.md is not None:
        cabecalho = f"# Laudo de análise de animação · fonte '{args.fonte}'\n"
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(
            cabecalho + "\n```\n" + "\n\n".join(laudos) + "\n```\n",
            encoding="utf-8",
        )
        print(f"laudo salvo em {args.md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
