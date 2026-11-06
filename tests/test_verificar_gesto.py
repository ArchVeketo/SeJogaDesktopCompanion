"""Casos sintéticos que PROVAM cada tipo de expectativa do verificador de gesto.

Cada teste monta um amostrador mínimo com um comportamento conhecido, amostra
pelo analisador objetivo e confere que a expectativa correspondente passa ou
falha como deveria. O objetivo é provar que o verificador MEDE o que diz medir:
mão parada falha OSCILA; aceno no eixo errado falha EIXO_CORRETO mas detecta
movimento; braço que ergue passa; a spec-piloto inteira aprova; pé com chute
falha ESTAVEL.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from collections.abc import Callable
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _carregar(nome: str, caminho: Path):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    # Registra antes de executar: dataclasses com anotações adiadas precisam
    # encontrar o próprio módulo em sys.modules durante a definição.
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


aa = _carregar("analisar_anim", RAIZ / "tools" / "analisar_anim.py")
sg = _carregar("spec_gestos", RAIZ / "tools" / "spec_gestos.py")
vg = _carregar("verificar_gesto", RAIZ / "tools" / "verificar_gesto.py")


Pose = dict[str, tuple[float, float, float]]


def _amostrar(amostrar: Callable[[float], Pose], duracao: float, loop: bool):
    clipe = aa.ClipeAnalisavel(nome="sintetico", amostrar=amostrar,
                               duracao=duracao, loop=loop)
    return aa.amostrar_clipe_analisavel(clipe)


def _passou(resultados: list, grupo: str, tipo: str) -> bool:
    for c in resultados:
        if c.grupo == grupo and c.categoria == f"GESTO·{tipo}":
            return c.prioridade >= 5
    raise AssertionError(f"expectativa {tipo} de {grupo} não encontrada")


# --------------------------------------------------------------------------- #
# OSCILA — mão parada FALHA; mão que oscila PASSA.
# --------------------------------------------------------------------------- #

def test_mao_parada_falha_oscila() -> None:
    def amostrar(t: float) -> Pose:
        return {"hand": (0.0, 0.0, 0.0)}

    am = _amostrar(amostrar, 2.0, loop=False)
    exp = sg.ExpectativaGesto(
        grupo="hand", tipo=sg.TipoExpectativa.OSCILA, eixo="x",
        amplitude_min=8.0, inversoes_min=3, descricao="mão acena no eixo X",
    )
    resultados, aprovado = vg.verificar(am, sg.SpecGesto("t", 2.0, False, (exp,)))

    assert not aprovado
    assert not _passou(resultados, "hand", "OSCILA")


def test_mao_oscilando_passa_oscila() -> None:
    def amostrar(t: float) -> Pose:
        return {"hand": (30.0 * math.sin(math.tau * 2 * t), 0.0, 0.0)}

    am = _amostrar(amostrar, 2.0, loop=False)
    exp = sg.ExpectativaGesto(
        grupo="hand", tipo=sg.TipoExpectativa.OSCILA, eixo="x",
        amplitude_min=8.0, inversoes_min=3, descricao="mão acena no eixo X",
    )
    resultados, aprovado = vg.verificar(am, sg.SpecGesto("t", 2.0, False, (exp,)))

    assert aprovado
    assert _passou(resultados, "hand", "OSCILA")


# --------------------------------------------------------------------------- #
# EIXO_CORRETO — aceno no eixo errado FALHA, mas DETECTA movimento.
# --------------------------------------------------------------------------- #

def test_aceno_eixo_errado_falha_eixo_correto_mas_detecta_movimento() -> None:
    # Oscila forte no eixo Z (errado), nada no X (esperado).
    def amostrar(t: float) -> Pose:
        return {"hand": (0.0, 0.0, 30.0 * math.sin(math.tau * 2 * t))}

    am = _amostrar(amostrar, 2.0, loop=False)
    exp_eixo = sg.ExpectativaGesto(
        grupo="hand", tipo=sg.TipoExpectativa.EIXO_CORRETO, eixo="x",
        descricao="aceno no eixo X",
    )
    exp_oscila = sg.ExpectativaGesto(
        grupo="hand", tipo=sg.TipoExpectativa.OSCILA, eixo="z",
        amplitude_min=8.0, inversoes_min=3, descricao="oscila no eixo Z",
    )
    resultados, _ = vg.verificar(
        am, sg.SpecGesto("t", 2.0, False, (exp_eixo, exp_oscila))
    )

    # Eixo errado: EIXO_CORRETO falha...
    assert not _passou(resultados, "hand", "EIXO_CORRETO")
    # ...mas o movimento é detectado (há oscilação, só no eixo errado).
    assert _passou(resultados, "hand", "OSCILA")


# --------------------------------------------------------------------------- #
# ERGUE — braço que ergue corretamente PASSA; sentido errado FALHA.
# --------------------------------------------------------------------------- #

def test_braco_que_ergue_passa() -> None:
    # Z vai de 56 até -10 (pico) e volta: ergue no sentido negativo.
    def amostrar(t: float) -> Pose:
        z = 56.0 - 66.0 * math.sin(math.pi * (t / 2.0))
        return {"right-arm": (0.0, 0.0, z)}

    am = _amostrar(amostrar, 2.0, loop=False)
    exp = sg.ExpectativaGesto(
        grupo="right-arm", tipo=sg.TipoExpectativa.ERGUE, eixo="z",
        amplitude_min=40.0, sentido=sg.SENTIDO_NEGATIVO, descricao="braço ergue",
    )
    resultados, aprovado = vg.verificar(am, sg.SpecGesto("t", 2.0, False, (exp,)))

    assert aprovado
    assert _passou(resultados, "right-arm", "ERGUE")


def test_braco_que_abaixa_falha_ergue() -> None:
    # Z cresce em vez de reduzir: sentido oposto ao esperado em ERGUE.
    def amostrar(t: float) -> Pose:
        z = 56.0 + 66.0 * math.sin(math.pi * (t / 2.0))
        return {"right-arm": (0.0, 0.0, z)}

    am = _amostrar(amostrar, 2.0, loop=False)
    exp = sg.ExpectativaGesto(
        grupo="right-arm", tipo=sg.TipoExpectativa.ERGUE, eixo="z",
        amplitude_min=40.0, sentido=sg.SENTIDO_NEGATIVO, descricao="braço ergue",
    )
    resultados, aprovado = vg.verificar(am, sg.SpecGesto("t", 2.0, False, (exp,)))

    assert not aprovado
    assert not _passou(resultados, "right-arm", "ERGUE")


# --------------------------------------------------------------------------- #
# ESTAVEL — pé parado PASSA; pé com chute FALHA.
# --------------------------------------------------------------------------- #

def test_pe_parado_passa_estavel() -> None:
    def amostrar(t: float) -> Pose:
        return {"left-feet": (0.0, 0.0, 0.0)}

    am = _amostrar(amostrar, 2.0, loop=False)
    exp = sg.ExpectativaGesto(
        grupo="left-feet", tipo=sg.TipoExpectativa.ESTAVEL, epsilon=1.0,
        descricao="pé não se mexe",
    )
    resultados, aprovado = vg.verificar(am, sg.SpecGesto("t", 2.0, False, (exp,)))

    assert aprovado
    assert _passou(resultados, "left-feet", "ESTAVEL")


def test_pe_com_chute_falha_estavel() -> None:
    def amostrar(t: float) -> Pose:
        return {"left-feet": (40.0 * math.sin(math.tau * t), 0.0, 0.0)}

    am = _amostrar(amostrar, 2.0, loop=False)
    exp = sg.ExpectativaGesto(
        grupo="left-feet", tipo=sg.TipoExpectativa.ESTAVEL, epsilon=1.0,
        descricao="pé não se mexe",
    )
    resultados, aprovado = vg.verificar(am, sg.SpecGesto("t", 2.0, False, (exp,)))

    assert not aprovado
    assert not _passou(resultados, "left-feet", "ESTAVEL")


# --------------------------------------------------------------------------- #
# FASE — raiz que começa antes PASSA; raiz que começa depois FALHA.
# --------------------------------------------------------------------------- #

def test_fase_braco_antes_da_mao_passa() -> None:
    # right-arm move de 0s; hand só começa depois de 1s.
    def amostrar(t: float) -> Pose:
        z_braco = 40.0 * min(1.0, t / 0.5)
        x_mao = 0.0 if t < 1.0 else 30.0 * math.sin(math.tau * 2 * (t - 1.0))
        return {"right-arm": (0.0, 0.0, z_braco), "hand": (x_mao, 0.0, 0.0)}

    am = _amostrar(amostrar, 2.0, loop=False)
    exp = sg.ExpectativaGesto(
        grupo="right-arm", tipo=sg.TipoExpectativa.FASE, eixo="z",
        antes_de="hand", descricao="o braço ergue antes de a mão acenar",
    )
    resultados, aprovado = vg.verificar(am, sg.SpecGesto("t", 2.0, False, (exp,)))

    assert aprovado
    assert _passou(resultados, "right-arm", "FASE")


# --------------------------------------------------------------------------- #
# SPEC-PILOTO INTEIRA — um clipe sintético que satisfaz TODA a SPEC_WAVE passa.
# --------------------------------------------------------------------------- #

def test_spec_piloto_inteira_passa_com_clipe_valido() -> None:
    # Pós-IK: um aceno válido ERGUE o braço no eixo Z (de ~-86° baixado até
    # ~+40°, a mão sobe acima do ombro pelo cotovelo dobrado), a mão oscila no
    # eixo X em torno do neutro (palma para FORA com o pulso neutro) e os pés
    # ficam parados. Estes valores vêm da geometria real do rig (ver arm_ik):
    # arm z=40 + elbow=44 coloca a mão acima do ombro com palma para fora.
    def amostrar(t: float) -> Pose:
        # Pós-IK (convenção do renderer): a ELEVAÇÃO do braço é o heading Y. Um
        # aceno válido ergue Y de ~-74° (baixado) até ~+66° (acima do ombro),
        # dobra o cotovelo (ant-arm roll Z) e balança a mão no eixo X em torno
        # do neutro (palma para FORA com o pulso neutro). Tudo medido do rig.
        # Rotation3 = (x, y, z); aqui setamos y (elevação) e z (azimute/cotovelo).
        fase = math.pi * (t / 2.2)
        lift = math.sin(fase)
        y_braco = -74.0 + (66.0 - (-74.0)) * lift   # ELEVA no heading Y (sobe)
        z_antebraco = 0.0 + 44.0 * lift             # cotovelo dobra ao erguer
        x_mao = 25.0 * math.sin(math.tau * 3 * t)   # aceno em torno do neutro
        return {
            "right-arm": (0.0, y_braco, -14.0),
            "ant-arm": (0.0, 0.0, z_antebraco),
            "hand": (x_mao, 0.0, 0.0),
            "left-feet": (0.0, 0.0, 0.0),
            "right-feet": (0.0, 0.0, 0.0),
        }

    am = _amostrar(amostrar, 2.2, loop=False)
    resultados, aprovado = vg.verificar(am, sg.SPEC_WAVE)

    assert aprovado
    assert all(c.prioridade >= 5 for c in resultados)


def test_spec_piloto_falha_quando_mao_fica_parada() -> None:
    # Igual ao válido (braço ergue na elevação Y), mas a mão NÃO acena (fica
    # parada) → reprova a spec. Pós-IK a elevação é o heading Y.
    def amostrar(t: float) -> Pose:
        fase = math.pi * (t / 2.2)
        y_braco = -74.0 + (66.0 - (-74.0)) * math.sin(fase)
        return {
            "right-arm": (0.0, y_braco, -14.0),
            "hand": (0.0, 0.0, 0.0),
            "left-feet": (0.0, 0.0, 0.0),
            "right-feet": (0.0, 0.0, 0.0),
        }

    am = _amostrar(amostrar, 2.2, loop=False)
    resultados, aprovado = vg.verificar(am, sg.SPEC_WAVE)

    assert not aprovado
    assert not _passou(resultados, "hand", "OSCILA")
