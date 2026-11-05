"""VERIFICADOR DE SPEC DE GESTO (camada semântica, código puro).

Dada uma :class:`AmostragemClipe` (produzida pelo analisador objetivo de
``tools/analisar_anim.py``) e uma :class:`SpecGesto` (de ``tools/spec_gestos.py``),
confere cada expectativa e emite UMA :class:`Constatacao` por expectativa, com
✓/✗, o PORQUÊ e o VALOR MEDIDO. Isto responde à pergunta semântica que o
analisador objetivo não responde: "o movimento é mesmo o que esse gesto exige?"
(ex.: "a mão não pode ficar parada numa saudação; ela deve acenar no eixo X").

Reuso, não reimplementação
---------------------------
O verificador NÃO reamostra nem recalcula derivadas. Ele lê ``am.series`` /
``am.tempos`` da amostragem a 60fps do analisador, opera sobre ``SerieEixo`` e
reusa o conceito de ``Constatacao`` (com ``formatar()``) e ``nome_junta()``.

Fronteira: Python puro. Para o gesto de PRODUÇÃO ``wave`` (que é procedural,
``rig.pose_flourish(rig, "wave", t)`` e NÃO está em ``anim_clips.CLIPES``), o
carregador instancia um ``Rig`` em repouso — ``rig.py`` é dataclass pura, não
carrega GLB/engine — dirige ``pose_flourish`` e lê a pose de volta em graus.

Uso (CLI)
---------
    python tools/verificar_gesto.py --fonte producao --gesto wave

Carrega o clipe, amostra via analisador, aplica a spec, imprime o laudo
semântico e sai com código != 0 se ALGUMA expectativa falhar (gate).
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Só para o type-checker: os módulos são carregados em runtime via importlib
    # (ver abaixo), mas estática mente resolvem como estes arquivos de tools/.
    import analisar_anim as aa
    import spec_gestos as sg

RAIZ = Path(__file__).resolve().parent.parent

# Garante que 'src' esteja no path para importar o pacote sejoga (rig_debug).
_SRC = RAIZ / "src"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _carregar_modulo(nome: str, caminho: Path) -> ModuleType:
    """Importa um .py solto como módulo (mesmo padrão do analisador/testes)."""
    spec = importlib.util.spec_from_file_location(nome, caminho)

    if spec is None or spec.loader is None:
        raise ImportError(f"não foi possível carregar {caminho}")

    modulo = importlib.util.module_from_spec(spec)
    # Registra antes de executar: dataclasses com anotações adiadas precisam
    # encontrar o próprio módulo em sys.modules durante a definição.
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)

    return modulo


if not TYPE_CHECKING:
    # Em runtime, carrega os módulos soltos; para o type-checker, os nomes já
    # vêm do bloco TYPE_CHECKING acima (evita reatribuir para ModuleType).
    aa = _carregar_modulo("analisar_anim", RAIZ / "tools" / "analisar_anim.py")
    sg = _carregar_modulo("spec_gestos", RAIZ / "tools" / "spec_gestos.py")


# --------------------------------------------------------------------------- #
# Métricas por eixo — tudo lido de SerieEixo (sem reamostrar).
# --------------------------------------------------------------------------- #

#: Piso de velocidade (fração do pico) abaixo do qual o movimento é ruído e não
#: conta como inversão de direção em OSCILA. Evita contar tremores numéricos.
PISO_RUIDO_INVERSAO = 0.15


def _serie_eixo(am: aa.AmostragemClipe, grupo: str, eixo: str) -> aa.SerieEixo:
    """Devolve a SerieEixo de (grupo, eixo); levanta se o grupo não existe."""
    trio = am.series.get(grupo)

    if trio is None:
        raise KeyError(f"grupo {grupo!r} ausente na amostragem")

    idx = aa.EIXOS.index(eixo)

    return trio[idx]


def _amplitude(serie: aa.SerieEixo) -> float:
    """Amplitude pico-a-pico da série de ângulo."""
    if not serie.angulo:
        return 0.0

    return max(serie.angulo) - min(serie.angulo)


def _contar_inversoes(serie: aa.SerieEixo) -> int:
    """Conta inversões de sentido da velocidade, ignorando ruído.

    Cada troca de sinal da velocidade (acima de um piso) é um "vai-e-volta".
    Uma oscilação ida-e-volta completa tem pelo menos 2 inversões.
    """
    pico = max((abs(v) for v in serie.velocidade), default=0.0)

    if pico == 0.0:
        return 0

    piso = pico * PISO_RUIDO_INVERSAO
    inversoes = 0
    sinal_anterior = 0

    for v in serie.velocidade:
        if abs(v) < piso:
            continue

        sinal = 1 if v > 0 else -1

        if sinal_anterior != 0 and sinal != sinal_anterior:
            inversoes += 1

        sinal_anterior = sinal

    return inversoes


def _eixo_dominante(trio: tuple[aa.SerieEixo, aa.SerieEixo, aa.SerieEixo]) -> str:
    """Eixo (x|y|z) com a maior amplitude pico-a-pico da junta."""
    amplitudes = [(aa.EIXOS[i], _amplitude(trio[i])) for i in range(3)]
    amplitudes.sort(key=lambda par: par[1], reverse=True)

    return amplitudes[0][0]


def _inicio_movimento(serie: aa.SerieEixo, tempos: list[float]) -> float | None:
    """Primeiro instante em que a velocidade sobe acima do ruído.

    Usado por FASE/ORDEM. Devolve ``None`` se a junta praticamente não se move.
    """
    pico = max((abs(v) for v in serie.velocidade), default=0.0)

    if pico == 0.0:
        return None

    piso = pico * PISO_RUIDO_INVERSAO

    for i, v in enumerate(serie.velocidade):
        if abs(v) > piso:
            return tempos[i]

    return None


# --------------------------------------------------------------------------- #
# Verificação de uma expectativa → uma Constatacao (✓/✗).
# --------------------------------------------------------------------------- #

def _constatacao(exp: sg.ExpectativaGesto, passou: bool, medido: str) -> aa.Constatacao:
    """Monta a Constatacao de uma expectativa com ✓/✗, PORQUÊ e valor medido."""
    marca = "✓ OK" if passou else "✗ FALHOU"
    recomendacao = (
        f"{marca}: {exp.descricao}" if passou
        else f"{marca}: esperado {exp.descricao}; não corresponde ao gesto"
    )

    return aa.Constatacao(
        prioridade=5 if passou else 1,
        categoria=f"GESTO·{exp.tipo}",
        grupo=exp.grupo,
        eixo=exp.eixo,
        tempo=None,
        metrica=f"esperado {exp.descricao} | medido: {medido}",
        recomendacao=recomendacao,
    )


def _verificar_ergue_abaixa(
    am: aa.AmostragemClipe, exp: sg.ExpectativaGesto
) -> tuple[bool, str]:
    """ERGUE/ABAIXA: o eixo se afasta do início até um alvo, no sentido esperado.

    Mede o maior afastamento do valor inicial (o "alvo" do gesto). Num gesto que
    ergue e volta ao repouso — como o wave — o alvo é o PICO, não o valor final;
    por isso comparamos o extremo alcançado, não a variação líquida fim-início.
    """
    assert exp.eixo is not None
    serie = _serie_eixo(am, exp.grupo, exp.eixo)
    amp = _amplitude(serie)
    inicio = serie.angulo[0]

    if exp.sentido == sg.SENTIDO_NEGATIVO:
        # ERGUE no eixo Z do braço: o ângulo diminui até um mínimo (alvo).
        alvo = min(serie.angulo)
        deslocamento = inicio - alvo
        sentido_ok = alvo < inicio
        seta = "reduz"
    else:
        alvo = max(serie.angulo)
        deslocamento = alvo - inicio
        sentido_ok = alvo > inicio
        seta = "cresce"

    passou = sentido_ok and deslocamento >= exp.amplitude_min
    medido = (
        f"vai de {inicio:.1f}° até o alvo {alvo:.1f}° ({seta} {deslocamento:.1f}°), "
        f"amplitude {amp:.1f}° (mínimo {exp.amplitude_min:.0f}°)"
    )

    return passou, medido


def _verificar_oscila(
    am: aa.AmostragemClipe, exp: sg.ExpectativaGesto
) -> tuple[bool, str]:
    """OSCILA: >= inversoes_min inversões de direção e amplitude mínima."""
    assert exp.eixo is not None
    serie = _serie_eixo(am, exp.grupo, exp.eixo)
    amp = _amplitude(serie)
    inversoes = _contar_inversoes(serie)

    passou = inversoes >= exp.inversoes_min and amp >= exp.amplitude_min
    medido = (
        f"{inversoes} inversões (mínimo {exp.inversoes_min}), "
        f"amplitude {amp:.1f}° (mínimo {exp.amplitude_min:.0f}°)"
    )

    if inversoes == 0:
        medido += " — junta parada"

    return passou, medido


def _verificar_estavel(
    am: aa.AmostragemClipe, exp: sg.ExpectativaGesto
) -> tuple[bool, str]:
    """ESTAVEL: amplitude pico-a-pico <= epsilon (no eixo dado ou na junta)."""
    trio = am.series.get(exp.grupo)

    if trio is None:
        raise KeyError(f"grupo {exp.grupo!r} ausente na amostragem")

    if exp.eixo is not None:
        amp = _amplitude(_serie_eixo(am, exp.grupo, exp.eixo))
    else:
        amp = max(_amplitude(s) for s in trio)

    passou = amp <= exp.epsilon
    medido = f"amplitude {amp:.2f}° (tolerância {exp.epsilon:.2f}°)"

    return passou, medido


def _verificar_eixo_correto(
    am: aa.AmostragemClipe, exp: sg.ExpectativaGesto
) -> tuple[bool, str]:
    """EIXO_CORRETO: o eixo de maior amplitude da junta é o eixo esperado."""
    assert exp.eixo is not None
    trio = am.series.get(exp.grupo)

    if trio is None:
        raise KeyError(f"grupo {exp.grupo!r} ausente na amostragem")

    dominante = _eixo_dominante(trio)
    amp_esperado = _amplitude(_serie_eixo(am, exp.grupo, exp.eixo))
    amp_dominante = _amplitude(_serie_eixo(am, exp.grupo, dominante))

    passou = dominante == exp.eixo
    nota = "" if passou else f" — mexe no eixo {dominante}, não no {exp.eixo}"
    medido = (
        f"eixo dominante {dominante} (amp {amp_dominante:.1f}°); "
        f"eixo esperado {exp.eixo} (amp {amp_esperado:.1f}°){nota}"
    )

    return passou, medido


def _verificar_fase(
    am: aa.AmostragemClipe, exp: sg.ExpectativaGesto
) -> tuple[bool, str]:
    """FASE: o movimento deste grupo começa antes do de ``antes_de``."""
    if exp.antes_de is None or exp.eixo is None:
        return False, "expectativa FASE mal definida (falta eixo/antes_de)"

    serie_a = _serie_eixo(am, exp.grupo, exp.eixo)
    trio_b = am.series.get(exp.antes_de)

    if trio_b is None:
        raise KeyError(f"grupo {exp.antes_de!r} ausente na amostragem")

    # Compara início do movimento usando o eixo dominante de cada junta.
    inicio_a = _inicio_movimento(serie_a, am.tempos)
    eixo_b = _eixo_dominante(trio_b)
    inicio_b = _inicio_movimento(_serie_eixo(am, exp.antes_de, eixo_b), am.tempos)

    if inicio_a is None or inicio_b is None:
        return False, "uma das juntas não se move o suficiente para medir fase"

    passou = inicio_a < inicio_b
    medido = (
        f"{aa.nome_junta(exp.grupo)} começa em {inicio_a:.2f}s, "
        f"{aa.nome_junta(exp.antes_de)} em {inicio_b:.2f}s"
    )

    return passou, medido


# --------------------------------------------------------------------------- #
# Ponte com o rig instrumentado (rig_debug): verifica a FLAG de uma PARTE num
# instante do gesto. Reusa as séries já amostradas (grupo/eixo em graus) — não
# reamostra nem redirige o rig; só reconstrói a pose do instante pedido.
# --------------------------------------------------------------------------- #

#: Cache do Model (carregar o glTF uma vez por processo).
_MODELO_CACHE = None


def _modelo():
    """Carrega o Model do glTF de produção uma única vez (cacheado)."""
    global _MODELO_CACHE

    if _MODELO_CACHE is None:
        from sejoga.assets import resolve_model
        from sejoga.model import load_model

        _MODELO_CACHE = load_model(resolve_model())

    return _MODELO_CACHE


def _indice_instante(am: aa.AmostragemClipe, instante: float | None) -> int:
    """Índice do tempo amostrado mais próximo de ``instante`` (ou o último)."""
    if instante is None:
        return len(am.tempos) - 1

    melhor = 0
    melhor_dist = abs(am.tempos[0] - instante)

    for i, t in enumerate(am.tempos):
        dist = abs(t - instante)

        if dist < melhor_dist:
            melhor_dist = dist
            melhor = i

    return melhor


def _pose_no_indice(am: aa.AmostragemClipe, indice: int):
    """Reconstrói a pose (grupo -> Rotation3 em radianos) de um índice amostrado.

    Lê os ângulos (em graus) já guardados em ``am.series`` e converte para o
    ``Rotation3`` que ``rig_debug.estado_rig`` espera.
    """
    from sejoga.rig import Rotation3

    pose: dict[str, Rotation3] = {}

    for grupo, (sx, sy, sz) in am.series.items():
        pose[grupo] = Rotation3(
            math.radians(sx.angulo[indice]),
            math.radians(sy.angulo[indice]),
            math.radians(sz.angulo[indice]),
        )

    return pose


def _flag_da_parte(estado, parte: str) -> str:
    """Extrai a flag legível da ``parte`` de um ``EstadoRig``.

    Suporta: partes do núcleo (mao_direita/mao_esquerda -> palma; cabeca -> olhar;
    corpo -> inclinação; porta -> flag; orientacao_global -> flag), membros por
    nome de grupo (right-arm, ant-arm, ...) e articulações (cotovelo_direito...).
    """
    if parte in ("mao_direita", "mao_esquerda"):
        return getattr(estado, parte).palma_flag

    if parte == "cabeca":
        return estado.cabeca.olhar_flag

    if parte == "corpo":
        return estado.corpo.inclinacao_flag

    if parte == "porta":
        return estado.porta.flag

    if parte == "orientacao_global":
        return estado.orientacao_global.flag

    if parte in estado.membros:
        return estado.membros[parte].direcao_flag

    if parte in estado.articulacoes:
        return estado.articulacoes[parte].flag

    raise KeyError(f"parte de rig_debug desconhecida: {parte!r}")


def _verificar_flag(
    am: aa.AmostragemClipe, exp: sg.ExpectativaGesto
) -> tuple[bool, str]:
    """FLAG: no instante medido, a ``parte`` deve estar na ``flag_esperada``.

    Lê a pose do instante (das séries já amostradas), roda ``rig_debug.estado_rig``
    e compara a flag legível da parte com a esperada.
    """
    from sejoga import rig_debug

    if exp.parte is None or exp.flag_esperada is None:
        return False, "expectativa FLAG mal definida (falta parte/flag_esperada)"

    indice = _indice_instante(am, exp.instante)
    pose = _pose_no_indice(am, indice)
    estado = rig_debug.estado_rig(pose, _modelo())
    obtida = _flag_da_parte(estado, exp.parte)

    passou = obtida == exp.flag_esperada
    medido = (
        f"em t={am.tempos[indice]:.2f}s a parte '{exp.parte}' está "
        f"{obtida} (esperado {exp.flag_esperada})"
    )

    return passou, medido


_DISPATCH = {
    sg.TipoExpectativa.ERGUE: _verificar_ergue_abaixa,
    sg.TipoExpectativa.ABAIXA: _verificar_ergue_abaixa,
    sg.TipoExpectativa.OSCILA: _verificar_oscila,
    sg.TipoExpectativa.ESTAVEL: _verificar_estavel,
    sg.TipoExpectativa.EIXO_CORRETO: _verificar_eixo_correto,
    sg.TipoExpectativa.FASE: _verificar_fase,
    sg.TipoExpectativa.FLAG: _verificar_flag,
}


def verificar(
    am: aa.AmostragemClipe, spec: sg.SpecGesto
) -> tuple[list[aa.Constatacao], bool]:
    """Confere cada expectativa da spec; devolve (constatações, aprovado).

    Uma Constatacao por expectativa (prioridade 1 = falhou, 5 = passou). O flag
    agregado é True só se TODAS as expectativas passarem (gate semântico).
    """
    resultados: list[aa.Constatacao] = []
    aprovado = True

    for exp in spec.expectativas:
        verificador = _DISPATCH[exp.tipo]
        passou, medido = verificador(am, exp)
        resultados.append(_constatacao(exp, passou, medido))
        aprovado = aprovado and passou

    return resultados, aprovado


def montar_laudo_semantico(
    spec: sg.SpecGesto, resultados: list[aa.Constatacao], aprovado: bool
) -> str:
    """Monta o laudo semântico legível e específico (reusa Constatacao.formatar)."""
    tipo = "loop" if spec.loop else "não-loop"
    linhas = [
        f"═══ LAUDO SEMÂNTICO · gesto '{spec.nome}' ({tipo}, {spec.duracao:.2f}s, "
        f"{len(spec.expectativas)} expectativas) ═══",
    ]

    for c in resultados:
        linhas.append("  " + c.formatar().replace("\n", "\n  "))

    veredito = "APROVADO" if aprovado else "REPROVADO"
    passaram = sum(1 for c in resultados if c.prioridade >= 5)
    linhas.append(
        f"\n  ── {veredito} ── {passaram}/{len(resultados)} expectativas ✓"
    )

    return "\n".join(linhas)


# --------------------------------------------------------------------------- #
# Carregador do gesto → ClipeAnalisavel (dirige o rig, sem engine).
# --------------------------------------------------------------------------- #

def _carregar_wave_producao() -> aa.ClipeAnalisavel:
    """Monta o ClipeAnalisavel do wave de PRODUÇÃO dirigindo ``pose_flourish``.

    Instancia um ``Rig`` com todos os grupos de ``rig.ALL_GROUPS`` em repouso
    (sem GLB/engine), chama ``pose_flourish(rig, "wave", t)`` e lê a pose de
    volta convertendo cada ``Rotation3`` (radianos) para graus.
    """
    from sejoga import rig as rig_mod

    repouso = {g: rig_mod.Rotation3() for g in rig_mod.ALL_GROUPS}

    def amostrar(t: float) -> dict[str, tuple[float, float, float]]:
        rig = rig_mod.Rig(rest=dict(repouso), current=dict(repouso))
        rig_mod.pose_flourish(rig, "wave", t)
        pose: dict[str, tuple[float, float, float]] = {}

        for grupo, rot in rig.pose().items():
            pose[grupo] = (
                math.degrees(rot.x),
                math.degrees(rot.y),
                math.degrees(rot.z),
            )

        return pose

    return aa.ClipeAnalisavel(nome="wave", amostrar=amostrar, duracao=2.2, loop=False)


#: Carregadores por (fonte, gesto). Extensível para idle/rascunho e outros gestos.
_CARREGADORES = {
    ("producao", "wave"): _carregar_wave_producao,
}


def carregar_gesto(fonte: str, gesto: str) -> aa.ClipeAnalisavel:
    """Devolve o ClipeAnalisavel de (fonte, gesto) ou levanta se não existir."""
    carregador = _CARREGADORES.get((fonte, gesto))

    if carregador is None:
        disponiveis = ", ".join(f"{f}/{g}" for f, g in sorted(_CARREGADORES))
        raise KeyError(
            f"combinação fonte/gesto '{fonte}/{gesto}' não suportada. "
            f"Disponíveis: {disponiveis}"
        )

    return carregador()


# --------------------------------------------------------------------------- #
# CLI.
# --------------------------------------------------------------------------- #

def _montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verificação SEMÂNTICA de gesto contra uma spec (código puro).",
    )
    parser.add_argument(
        "--fonte", choices=("producao", "idle", "rascunho"), default="producao",
        help="origem do gesto (hoje: producao)",
    )
    parser.add_argument(
        "--gesto", default="wave",
        help="nome do gesto a verificar (hoje: wave)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    # O laudo usa Unicode (═ ✓ ✗ °). No Windows, stdout pode vir em cp1252 e
    # quebrar ao redirecionar/pipar; forçamos UTF-8 quando possível.
    for fluxo in (sys.stdout, sys.stderr):
        reconfig = getattr(fluxo, "reconfigure", None)
        if callable(reconfig):
            reconfig(encoding="utf-8", errors="replace")

    args = _montar_parser().parse_args(argv)

    spec = sg.SPECS.get(args.gesto)

    if spec is None:
        disponiveis = ", ".join(sorted(sg.SPECS))
        print(f"erro: gesto '{args.gesto}' sem spec. Disponíveis: {disponiveis}",
              file=sys.stderr)
        return 2

    try:
        clipe = carregar_gesto(args.fonte, args.gesto)
    except KeyError as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2

    am = aa.amostrar_clipe_analisavel(clipe)
    resultados, aprovado = verificar(am, spec)
    laudo = montar_laudo_semantico(spec, resultados, aprovado)
    print(laudo)

    return 0 if aprovado else 1


if __name__ == "__main__":
    raise SystemExit(main())
