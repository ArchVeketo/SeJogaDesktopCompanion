"""Casos sintéticos que PROVAM cada detector do analisador de animação.

Cada teste constrói um amostrador mínimo com um problema conhecido (ou a sua
ausência) e verifica que o detector correspondente acusa (ou não) o achado.
Os clipes reais de produção/idle também passam pelo pipeline como fumaça.
"""

from __future__ import annotations

import importlib.util
import itertools
import math
import sys
from collections.abc import Callable
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "analisar_anim", RAIZ / "tools" / "analisar_anim.py"
)
assert _spec is not None and _spec.loader is not None
aa = importlib.util.module_from_spec(_spec)
# Registra antes de executar: dataclasses com anotações adiadas precisam
# encontrar o próprio módulo em sys.modules durante a definição.
sys.modules["analisar_anim"] = aa
_spec.loader.exec_module(aa)


Pose = dict[str, tuple[float, float, float]]


def _clipe(nome: str, amostrar: Callable[[float], Pose], duracao: float,
           loop: bool) -> aa.ClipeAnalisavel:
    return aa.ClipeAnalisavel(nome=nome, amostrar=amostrar, duracao=duracao, loop=loop)


def _categorias(achados: list[aa.Constatacao]) -> set[str]:
    return {c.categoria for c in achados}


# --------------------------------------------------------------------------- #
# SUAVIDADE — clipe abrupto acusa tranco; clipe suave não.
# --------------------------------------------------------------------------- #

def test_clipe_abrupto_acusa_tranco() -> None:
    # Degrau brusco: fica em 0 e salta para 40° na metade (aceleração em degrau).
    def amostrar(t: float) -> Pose:
        ang = 0.0 if t < 0.5 else 40.0
        return {"head": (ang, 0.0, 0.0)}

    _, achados = aa.analisar(_clipe("abrupto", amostrar, 1.0, loop=False))

    assert "SUAVIDADE" in _categorias(achados)


def test_clipe_suave_nao_acusa_tranco() -> None:
    # Seno suave: jerk limitado, bem abaixo do limiar.
    def amostrar(t: float) -> Pose:
        return {"head": (10.0 * math.sin(math.tau * t), 0.0, 0.0)}

    _, achados = aa.analisar(_clipe("suave", amostrar, 1.0, loop=True))

    assert "SUAVIDADE" not in _categorias(achados)


# --------------------------------------------------------------------------- #
# LOOP — loop com pop é detectado; loop que fecha não é.
# --------------------------------------------------------------------------- #

def test_loop_com_pop_e_detectado() -> None:
    # Rampa linear 0->30° que NÃO volta: último frame longe do primeiro.
    def amostrar(t: float) -> Pose:
        return {"body": (30.0 * t, 0.0, 0.0)}

    _, achados = aa.analisar(_clipe("pop", amostrar, 1.0, loop=True))

    assert "LOOP" in _categorias(achados)


def test_loop_fechado_nao_acusa_pop() -> None:
    # Seno de período inteiro: posição e velocidade batem no fechamento.
    def amostrar(t: float) -> Pose:
        return {"body": (15.0 * math.sin(math.tau * t), 0.0, 0.0)}

    _, achados = aa.analisar(_clipe("fechado", amostrar, 1.0, loop=True))

    assert "LOOP" not in _categorias(achados)


# --------------------------------------------------------------------------- #
# SIMETRIA — par perfeitamente espelhado acusa; par defasado não.
# --------------------------------------------------------------------------- #

def test_par_espelhado_exato_acusa_simetria() -> None:
    # right-arm e left-arm em espelho exato (Z com sinal trocado).
    def amostrar(t: float) -> Pose:
        v = 20.0 * math.sin(math.tau * t)
        return {
            "right-arm": (0.0, 0.0, v),
            "left-arm": (0.0, 0.0, -v),
        }

    _, achados = aa.analisar(_clipe("espelho", amostrar, 1.0, loop=True))

    assert "SIMETRIA" in _categorias(achados)


def test_par_defasado_nao_acusa_simetria() -> None:
    # Mesma amplitude, mas defasado 1/4 de ciclo: não é espelho exato.
    def amostrar(t: float) -> Pose:
        d = 20.0 * math.sin(math.tau * t)
        e = 20.0 * math.sin(math.tau * t + math.pi / 2)
        return {
            "right-arm": (0.0, 0.0, d),
            "left-arm": (0.0, 0.0, -e),
        }

    _, achados = aa.analisar(_clipe("defasado", amostrar, 1.0, loop=True))

    assert "SIMETRIA" not in _categorias(achados)


# --------------------------------------------------------------------------- #
# ANTECIPAÇÃO — movimento com antecipação NÃO acusa falsamente ausência.
# --------------------------------------------------------------------------- #

def test_movimento_com_antecipacao_nao_acusa_ausencia() -> None:
    # Gesto para +40°, precedido de recuo claro para -12° (contra-movimento).
    chaves = [(0.0, 0.0), (0.2, -12.0), (0.6, 40.0), (1.0, 40.0)]

    def amostrar(t: float) -> Pose:
        return {"right-arm": (0.0, 0.0, _rampa(chaves, t))}

    _, achados = aa.analisar(_clipe("antecipa", amostrar, 1.0, loop=False))

    sem_antecipacao = [c for c in achados
                       if c.categoria == "ANTECIPAÇÃO" and c.grupo == "right-arm"]

    assert sem_antecipacao == []


def test_movimento_sem_antecipacao_acusa_ausencia() -> None:
    # Vai direto para +40° sem recuo: deve acusar ausência de antecipação.
    chaves = [(0.0, 0.0), (0.5, 40.0), (1.0, 40.0)]

    def amostrar(t: float) -> Pose:
        return {"right-arm": (0.0, 0.0, _rampa(chaves, t))}

    _, achados = aa.analisar(_clipe("direto", amostrar, 1.0, loop=False))

    assert "ANTECIPAÇÃO" in _categorias(achados)


# --------------------------------------------------------------------------- #
# FOLLOW-THROUGH — cadeia que para junta acusa; escalonada não.
# --------------------------------------------------------------------------- #

def test_cadeia_para_junta_acusa_follow_through() -> None:
    # Toda a cadeia do braço direito para exatamente no mesmo instante.
    chaves = [(0.0, 0.0), (0.5, 30.0), (0.7, 0.0), (1.0, 0.0)]

    def amostrar(t: float) -> Pose:
        v = _rampa(chaves, t)
        return {
            "right-arm": (0.0, 0.0, v),
            "ant-arm": (0.0, 0.0, v),
            "hand": (0.0, 0.0, v),
        }

    _, achados = aa.analisar(_clipe("rigido", amostrar, 1.0, loop=False))

    assert "FOLLOW-THROUGH" in _categorias(achados)


def test_cadeia_escalonada_nao_acusa_follow_through() -> None:
    # Cada elo para num instante diferente (overlap/arrasto): sem achado.
    def amostrar(t: float) -> Pose:
        return {
            "right-arm": (0.0, 0.0, _pulso(t, fim=0.4)),
            "ant-arm": (0.0, 0.0, _pulso(t, fim=0.6)),
            "hand": (0.0, 0.0, _pulso(t, fim=0.85)),
        }

    _, achados = aa.analisar(_clipe("escalonado", amostrar, 1.0, loop=False))

    ft = [c for c in achados
          if c.categoria == "FOLLOW-THROUGH" and c.grupo in ("right-arm", "ant-arm", "hand")]

    assert ft == []


# --------------------------------------------------------------------------- #
# Fumaça: os clipes reais passam pelo pipeline sem explodir e geram laudo.
# --------------------------------------------------------------------------- #

def test_pipeline_producao_gera_laudo() -> None:
    clipes = aa._carregar_producao()

    assert "walk" in clipes and "run" in clipes

    am, achados = aa.analisar(clipes["walk"])
    laudo = aa.montar_laudo(am, achados)

    assert "walk" in laudo
    assert isinstance(achados, list)


def test_pipeline_idle_gera_laudo() -> None:
    clipes = aa._carregar_idle()

    assert clipes  # há frases de idle

    nome = next(iter(clipes))
    am, achados = aa.analisar(clipes[nome])

    assert aa.montar_laudo(am, achados).startswith("═══ LAUDO")


# --------------------------------------------------------------------------- #
# Auxiliares de síntese.
# --------------------------------------------------------------------------- #

def _rampa(chaves: list[tuple[float, float]], t: float) -> float:
    """Interpolação linear simples entre (tempo, valor)."""
    if t <= chaves[0][0]:
        return chaves[0][1]

    for (t0, v0), (t1, v1) in itertools.pairwise(chaves):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * u

    return chaves[-1][1]


def _pulso(t: float, fim: float, pico: float = 30.0) -> float:
    """Sobe até o pico e volta a zero, terminando o movimento em ``fim``."""
    if t >= fim:
        return 0.0

    u = t / fim
    return pico * math.sin(math.pi * u)
