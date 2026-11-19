"""Cenas curtas e narrativas de idle amostradas dos dados autorais.

Cada cena aplica os 12 princípios da animação em 3D (antecipação, arcos amplos
por fora do gabinete da TV, atraso de punhos/fones/antenas, contra-peso e
contato direto com conchas do fone, Walkman do quadril e argola da antena).
Python puro, sem engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise
from math import radians, sin
from typing import Any

from sejoga.animacao import animation as _anim_padrao
from sejoga.animacao.dados_autorais import cenas_idle_ativas
from sejoga.animacao.estados_delta import delta_absoluto_para_repouso
from sejoga.animacao.gestos_dedos import CURL_NEUTRO
from sejoga.animacao.interpolacao import amostrar_pista
from sejoga.nucleo.esqueleto import Rotation3

Pista = tuple[tuple[float, tuple[float, float, float]], ...]
Pernas6 = tuple[float, ...]
Dedos5 = tuple[float, float, float, float, float]
DedosCena = tuple[Dedos5, Dedos5]


def duracoes_cenas_ativas() -> dict[str, float]:
    """Devolve o mapa ``{nome: duracao_s}`` das cenas ativas (salvas ou rascunho)."""
    return {
        nome: float(cfg["duration"]) for nome, cfg in cenas_idle_ativas().items()
    }


DURACOES_CENAS: dict[str, float] = {
    nome: float(cfg["duration"]) for nome, cfg in _anim_padrao.CENAS_IDLE.items()
}

_GRUPOS_BASE_ABS = frozenset({"right-arm", "left-arm", "ant-arm", "ant-arm2"})

_PERNAS_NEUTRAS: Pernas6 = (0.0, 0.0, 4.0, 4.0, 5.0, -5.0)
_PISTAS_PERNAS_CENAS: dict[str, tuple[tuple[float, Pernas6], ...]] = {
    "groove_um_pe": (
        (0.00, (0.0, 0.0, 4.0, 4.0, 5.0, -5.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
        (0.95, (-6.0, -22.0, 12.0, 32.0, 7.0, -14.0, -3.0, 7.0, 4.0, 16.0, 0.0, 0.003)),
        (1.45, (-6.0, -32.0, 12.0, 54.0, 7.0, -16.0, -3.0, 9.0, 4.0, -24.0, 0.0, 0.020)),
        (1.95, (-7.0, -16.0, 14.0, 20.0, 7.0, -12.0, -4.0, 6.0, 5.0, 18.0, 0.0, 0.002)),
        (2.40, (-6.0, -32.0, 12.0, 54.0, 7.0, -16.0, -3.0, 9.0, 4.0, -24.0, 0.0, 0.020)),
        (2.90, (-7.0, -16.0, 14.0, 20.0, 7.0, -12.0, -4.0, 6.0, 5.0, 18.0, 0.0, 0.002)),
        (3.35, (-6.0, -32.0, 12.0, 54.0, 7.0, -16.0, -3.0, 9.0, 4.0, -24.0, 0.0, 0.020)),
        (3.85, (-7.0, -16.0, 14.0, 20.0, 7.0, -12.0, -4.0, 6.0, 5.0, 18.0, 0.0, 0.002)),
        (4.30, (-6.0, -34.0, 12.0, 56.0, 7.0, -16.0, -3.0, 9.0, 4.0, -25.0, 0.0, 0.022)),
        (5.80, (-6.0, -20.0, 12.0, 28.0, 7.0, -13.0, -3.0, 6.0, 4.0, 12.0, 0.0, 0.005)),
        (7.20, (0.0, 0.0, 4.0, 4.0, 5.0, -5.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
    ),
    "conferir_luva": (
        (0.00, _PERNAS_NEUTRAS),
        (0.75, (-7.5, -3.5, 15.0, 7.0, 7.0, -5.0)),
        (2.50, (-8.5, -4.0, 17.0, 8.0, 7.0, -5.0)),
        (3.55, (-5.0, -5.0, 10.0, 10.0, 6.0, -6.0)),
        (5.20, _PERNAS_NEUTRAS),
    ),
    "pensar_gabinete": (
        (0.00, _PERNAS_NEUTRAS),
        (1.05, (-5.5, -10.5, 11.0, 19.0, 6.0, -7.0)),
        (3.55, (-6.0, -11.0, 12.0, 20.0, 6.0, -7.0)),
        (3.90, (-13.5, -13.5, 26.0, 26.0, 6.0, -6.0)),
        (4.22, (-2.0, -2.0, 4.0, 4.0, 5.0, -5.0)),
        (5.20, (-4.5, -4.5, 9.0, 9.0, 5.0, -5.0)),
        (6.40, _PERNAS_NEUTRAS),
    ),
    "segurar_porta_timido": (
        (0.00, _PERNAS_NEUTRAS),
        (0.75, (-4.0, -4.0, 8.0, 8.0, 5.0, -5.0)),
        (1.15, (-14.0, -14.0, 27.0, 27.0, 7.0, -7.0)),
        (1.80, (-8.0, -6.0, 16.0, 12.0, 6.0, -6.0)),
        (2.65, (-9.5, -5.0, 18.0, 10.0, 6.0, -5.0)),
        (3.35, (-5.0, -9.5, 10.0, 18.0, 5.0, -6.0)),
        (4.80, _PERNAS_NEUTRAS),
    ),
    "checar_walkman": (
        (0.00, _PERNAS_NEUTRAS),
        (0.95, (-4.0, -9.5, 8.0, 18.0, 8.0, -4.0)),
        (2.60, (-4.5, -10.5, 9.0, 20.0, 8.0, -4.0)),
        (3.35, (-9.0, -9.0, 18.0, 18.0, 6.0, -6.0)),
        (3.65, (-4.0, -4.0, 8.0, 8.0, 6.0, -6.0)),
        (3.95, (-9.0, -9.0, 18.0, 18.0, 6.0, -6.0)),
        (4.45, (-4.0, -4.0, 8.0, 8.0, 5.0, -5.0)),
        (5.60, _PERNAS_NEUTRAS),
    ),
    "alongar_pescoco_ombros": (
        (0.00, _PERNAS_NEUTRAS),
        (1.00, (-2.0, -2.0, 4.0, 4.0, 5.0, -5.0)),
        (2.50, (-5.5, -4.5, 11.0, 9.0, 6.0, -6.0)),
        (3.70, (-4.5, -5.5, 9.0, 11.0, 6.0, -6.0)),
        (4.22, (-11.5, -11.5, 22.0, 22.0, 6.0, -6.0)),
        (4.95, (-3.5, -3.5, 7.0, 7.0, 5.0, -5.0)),
        (6.00, _PERNAS_NEUTRAS),
    ),
    "escutar_fone": (
        (0.00, _PERNAS_NEUTRAS),
        (1.45, (-7.0, -4.5, 14.0, 9.0, 6.0, -5.0)),
        (2.60, (-4.5, -7.0, 9.0, 14.0, 6.0, -5.0)),
        (3.75, (-7.0, -4.5, 14.0, 9.0, 6.0, -5.0)),
        (5.10, (-4.0, -4.0, 8.0, 8.0, 5.0, -5.0)),
        (6.40, _PERNAS_NEUTRAS),
    ),
    "batida_guardada": (
        (0.00, _PERNAS_NEUTRAS),
        (1.30, (-5.5, -7.0, 11.0, 14.0, 6.0, -6.0)),
        (1.95, (-10.0, -10.0, 20.0, 20.0, 6.0, -6.0)),
        (2.18, (-4.0, -4.0, 8.0, 8.0, 6.0, -6.0)),
        (2.55, (-10.0, -10.0, 20.0, 20.0, 6.0, -6.0)),
        (2.78, (-4.0, -4.0, 8.0, 8.0, 6.0, -6.0)),
        (4.50, (-5.0, -6.0, 10.0, 12.0, 5.0, -5.0)),
        (6.60, _PERNAS_NEUTRAS),
    ),
    "conferir_estilo": (
        (0.00, _PERNAS_NEUTRAS),
        (1.00, (-8.0, -3.0, 16.0, 6.0, 8.0, -4.0)),
        (2.40, (-3.0, -9.0, 6.0, 18.0, 4.0, -8.0)),
        (3.55, (-7.0, -5.0, 14.0, 10.0, 6.0, -6.0)),
        (5.60, _PERNAS_NEUTRAS),
    ),
    "espreguicar_pesado": (
        (0.00, _PERNAS_NEUTRAS),
        (1.30, (-2.0, -2.0, 4.0, 4.0, 5.0, -5.0)),
        (2.55, (2.0, 2.0, 2.0, 2.0, 6.0, -6.0)),
        (3.95, (-12.0, -12.0, 24.0, 24.0, 6.0, -6.0)),
        (5.80, _PERNAS_NEUTRAS),
    ),
    "olhar_curioso_chao": (
        (0.00, _PERNAS_NEUTRAS),
        (1.10, (-10.0, -12.0, 20.0, 22.0, 6.0, -8.0)),
        (2.05, (-10.0, -22.0, 20.0, 34.0, 6.0, -12.0)),
        (2.65, (-10.0, -14.0, 20.0, 24.0, 6.0, -8.0)),
        (3.25, (-10.0, -22.0, 20.0, 34.0, 6.0, -12.0)),
        (4.20, (-6.0, -6.0, 12.0, 12.0, 5.0, -5.0)),
        (5.20, _PERNAS_NEUTRAS),
    ),
}


_DEDOS_NEUTROS: Dedos5 = (CURL_NEUTRO, CURL_NEUTRO, CURL_NEUTRO, CURL_NEUTRO, CURL_NEUTRO)
_PISTAS_DEDOS_CENAS: dict[str, tuple[tuple[float, DedosCena], ...]] = {
    "conferir_luva": (
        (0.00, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
        (0.90, ((0.04, 0.04, 0.04, 0.04, 0.04), (0.68, 0.74, 0.48, 0.40, 0.40))),
        (1.85, ((0.00, 0.00, 0.00, 0.00, 0.00), (0.55, 0.62, 0.42, 0.36, 0.36))),
        (2.60, ((0.95, 0.98, 0.98, 0.98, 0.98), _DEDOS_NEUTROS)),
        (3.35, ((0.16, 0.04, 0.38, 0.78, 0.94), _DEDOS_NEUTROS)),
        (4.15, ((0.06, 0.06, 0.12, 0.18, 0.22), _DEDOS_NEUTROS)),
        (5.20, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
    ),
    "pensar_gabinete": (
        (0.00, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
        (0.95, ((0.82, 0.02, 0.92, 0.95, 0.95), (0.44, 0.40, 0.48, 0.52, 0.54))),
        (3.45, ((0.82, 0.02, 0.92, 0.95, 0.95), (0.44, 0.40, 0.48, 0.52, 0.54))),
        (3.95, ((0.18, 0.02, 0.22, 0.28, 0.32), (0.24, 0.20, 0.26, 0.30, 0.32))),
        (5.00, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
        (6.40, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
    ),
    "segurar_porta_timido": (
        (0.00, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
        (0.95, ((0.06, 0.04, 0.04, 0.08, 0.10), (0.42, 0.42, 0.46, 0.50, 0.52))),
        (2.25, ((0.14, 0.12, 0.14, 0.18, 0.22), _DEDOS_NEUTROS)),
        (4.80, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
    ),
    "checar_walkman": (
        (0.00, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
        (1.05, (_DEDOS_NEUTROS, (0.76, 0.62, 0.44, 0.48, 0.52))),
        (2.35, (_DEDOS_NEUTROS, (0.82, 0.78, 0.48, 0.50, 0.54))),
        (3.30, ((0.04, 0.86, 0.86, 0.86, 0.04), _DEDOS_NEUTROS)),
        (4.30, ((0.08, 0.80, 0.80, 0.80, 0.08), _DEDOS_NEUTROS)),
        (5.60, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
    ),
    "conferir_estilo": (
        (0.00, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
        (0.95, ((0.08, 0.06, 0.08, 0.12, 0.14), (0.35, 0.35, 0.42, 0.46, 0.48))),
        (2.20, ((0.20, 0.04, 0.04, 0.88, 0.92), _DEDOS_NEUTROS)),
        (3.30, ((0.02, 0.88, 0.90, 0.92, 0.94), _DEDOS_NEUTROS)),
        (4.50, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
        (5.60, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
    ),
    "espreguicar_pesado": (
        (0.00, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
        (1.30, ((0.02, 0.02, 0.02, 0.02, 0.02), (0.02, 0.02, 0.02, 0.02, 0.02))),
        (2.55, ((0.00, 0.00, 0.00, 0.00, 0.00), (0.00, 0.00, 0.00, 0.00, 0.00))),
        (3.95, ((0.55, 0.52, 0.58, 0.62, 0.64), (0.55, 0.52, 0.58, 0.62, 0.64))),
        (5.80, (_DEDOS_NEUTROS, _DEDOS_NEUTROS)),
    ),
}


@dataclass(frozen=True, slots=True)
class AmostraCenaIdle:
    """Resultado amostrado de uma cena curta de idle no instante atual."""

    ativa: bool = False
    nome: str = ""
    delta_rig: dict[str, Rotation3] = field(default_factory=dict)
    peso_mistura: float = 0.0
    pernas_graus: tuple[float, ...] | None = None
    deslocamento_z: float = 0.0
    estouro_fone: bool = False
    brilho_argolas: float = 0.0
    deslocamento_argola_sup: float = 0.0
    deslocamento_argola_inf: float = 0.0
    escala_argolas: float = 1.0
    choque_argolas: bool = False
    dedos: DedosCena | None = None


def _suave_01(u: float) -> float:
    c = max(0.0, min(1.0, u))
    return c * c * (3.0 - 2.0 * c)


def _peso_cena(
    tempo: float,
    duracao: float,
    entrada: float = 0.36,
    saida: float = 0.44,
    *,
    peso_entrada: float = 1.0,
    peso_saida: float = 1.0,
) -> float:
    w_in = _suave_01(tempo / entrada) if entrada > 0.0 else 1.0
    w_out = _suave_01((duracao - tempo) / saida) if saida > 0.0 else 1.0
    w_in = 1.0 - peso_entrada * (1.0 - w_in)
    w_out = 1.0 - peso_saida * (1.0 - w_out)
    return max(0.0, min(1.0, min(w_in, w_out)))


def _amostrar_pistas(
    pistas: dict[str, Any],
    tempo: float,
    *,
    grupos_abs: frozenset[str],
    curvas: dict[str, Any] | None = None,
) -> dict[str, Rotation3]:
    delta: dict[str, Rotation3] = {}
    curvas_map = curvas or {}
    for grupo, keys in pistas.items():
        x, y, z = amostrar_pista(keys, tempo, curvas=curvas_map.get(grupo))
        if grupo in grupos_abs:
            delta[grupo] = delta_absoluto_para_repouso(grupo, x, y, z)
        else:
            delta[grupo] = Rotation3(radians(x), radians(y), radians(z))
    return delta


def _resolver_cfg_cena(nome: str, variante: int) -> dict[str, Any] | None:
    cenas = cenas_idle_ativas()
    cfg = cenas.get(nome)
    if cfg is None:
        return None
    if variante <= 0:
        return cfg
    variantes = cfg.get("variantes", {})
    chave = variante if variante in variantes else str(variante)
    sobre = variantes.get(chave)
    if not isinstance(sobre, dict):
        return cfg
    combinada = dict(cfg)
    combinada.update(sobre)
    return combinada


def _na_janela(t: float, janela: tuple[float, float] | list[float] | None) -> bool:
    if not janela or len(janela) != 2:
        return False
    return float(janela[0]) <= t <= float(janela[1])


def _amostrar_fone_problema(
    cfg: dict[str, Any],
    t: float,
    peso: float,
    delta: dict[str, Rotation3],
) -> AmostraCenaIdle:
    janelas = cfg.get("janelas_efeito", {})
    jan_estouro = janelas.get("estouro_fone")
    estouro = _na_janela(t, jan_estouro)
    t_vib = float(jan_estouro[0]) + 0.03 if jan_estouro else 3.98
    if t_vib <= t <= t_vib + 0.72:
        u_vib = (t - t_vib) / 0.72
        ataque = _suave_01((t - t_vib) / 0.11)
        cauda = 1.0 - _suave_01((u_vib - 0.35) / 0.65)
        vib = sin((t - t_vib) * 26.0) * ataque * cauda
        delta["fone-direito"] = Rotation3(
            radians(vib * 4.0),
            radians(vib * 5.5),
            delta.get("fone-direito", Rotation3()).z + radians(vib * 9.5),
        )
    pernas, desloc_z = _amostrar_agachamento_cena(cfg, t)
    return AmostraCenaIdle(
        ativa=True,
        nome="fone_com_problema",
        delta_rig=delta,
        peso_mistura=peso,
        pernas_graus=pernas,
        deslocamento_z=desloc_z,
        estouro_fone=estouro,
    )


def _amostrar_agachamento_cena(
    cfg: dict[str, Any], t: float
) -> tuple[tuple[float, float, float, float, float, float] | None, float]:
    jan = cfg.get("deslocamento_janela_s")
    desloc_alvo = float(cfg.get("deslocamento_z", 0.0))
    if not jan or len(jan) != 2 or not (float(jan[0]) <= t <= float(jan[1])):
        return None, 0.0
    t0, t1 = float(jan[0]), float(jan[1])
    f = 1.0
    if t < t0 + 0.45:
        f = _suave_01((t - t0) / 0.45)
    elif t > t1 - 0.65:
        f = _suave_01((t1 - t) / 0.65)
    base = cfg.get("pernas_sentado_graus") or (-46.0, -46.0, 86.0, 86.0, 8.0, -8.0)
    balanco = sin((t - (t0 + 0.45)) * 4.8) * 4.0 * f
    pernas = (
        float(base[0]) * f,
        float(base[1]) * f,
        float(base[2]) * f,
        float(base[3]) * f,
        float(base[4]) * f + balanco,
        float(base[5]) * f - balanco,
    )
    return pernas, desloc_alvo * f


def _amostrar_escalar_suave(chaves: tuple[tuple[float, float], ...], t: float) -> float:
    if t <= chaves[0][0]:
        return chaves[0][1]
    for (t0, v0), (t1, v1) in pairwise(chaves):
        if t <= t1:
            u = _suave_01((t - t0) / max(1e-6, t1 - t0))
            return v0 + (v1 - v0) * u
    return chaves[-1][1]


def _amostrar_argolas_antena(
    cfg: dict[str, Any],
    t: float,
    peso: float,
    delta: dict[str, Rotation3],
) -> AmostraCenaIdle:
    """Anima as duas argolas em sentidos opostos: vão às bordas, quicam, colidem no meio e retornam."""
    janelas = cfg.get("janelas_efeito", {})
    choque = _na_janela(t, janelas.get("choque_argolas", (1.68, 2.15)))
    # Fase 1 (0.35..1.15): sobem/descem em direções opostas até as bordas e quicam lá fora.
    # Fase 2 (1.15..1.74): correm de volta uma contra a outra até se chocarem no meio.
    # Fase 3 (1.74..2.25): ricochete da colisão central.
    # Fase 4 (2.25..3.65): retorno elástico à posição original de repouso.
    dz_sup = _amostrar_escalar_suave(
        (
            (0.00, 0.0),
            (0.28, -0.006),
            (0.76, 0.046),
            (0.92, 0.028),
            (1.08, 0.044),
            (1.74, -0.017),
            (1.98, 0.024),
            (2.26, -0.008),
            (2.60, 0.012),
            (3.45, 0.0),
            (4.20, 0.0),
        ),
        t,
    )
    dz_inf = _amostrar_escalar_suave(
        (
            (0.00, 0.0),
            (0.28, 0.006),
            (0.76, -0.056),
            (0.92, -0.036),
            (1.08, -0.052),
            (1.74, 0.017),
            (1.98, -0.026),
            (2.26, 0.008),
            (2.60, -0.012),
            (3.45, 0.0),
            (4.20, 0.0),
        ),
        t,
    )
    u_liga = _suave_01((t - 0.15) / 0.35)
    u_desliga = 1.0 - _suave_01((t - 2.95) / 0.85)
    pulso_colisao = 1.0 if choque else 0.0
    brilho = 1.0 if choque else max(0.0, min(1.0, u_liga * u_desliga))
    quique_borda = max(0.0, 1.0 - abs(t - 0.78) / 0.20)
    impacto_meio = max(0.0, 1.0 - abs(t - 1.76) / 0.22)
    escala = 1.0 + 0.10 * brilho + 0.14 * quique_borda + 0.26 * impacto_meio + 0.08 * pulso_colisao
    return AmostraCenaIdle(
        ativa=True,
        nome="argolas_antena",
        delta_rig=delta,
        peso_mistura=peso,
        brilho_argolas=brilho,
        deslocamento_argola_sup=dz_sup,
        deslocamento_argola_inf=dz_inf,
        escala_argolas=escala,
        choque_argolas=choque,
    )


def _amostrar_pista_pernas(
    chaves: tuple[tuple[float, Pernas6], ...],
    tempo: float,
) -> Pernas6:
    if tempo <= chaves[0][0]:
        return chaves[0][1]
    for (t0, v0), (t1, v1) in pairwise(chaves):
        if tempo <= t1:
            dur = t1 - t0
            u = (tempo - t0) / dur if dur > 1e-9 else 1.0
            f = u * u * u * (u * (u * 6.0 - 15.0) + 10.0)
            return tuple(a + (b - a) * f for a, b in zip(v0, v1, strict=True))  # type: ignore[return-value]
    return chaves[-1][1]


def _amostrar_pista_dedos(
    chaves: tuple[tuple[float, DedosCena], ...],
    tempo: float,
) -> DedosCena:
    if tempo <= chaves[0][0]:
        return chaves[0][1]
    for (t0, v0), (t1, v1) in pairwise(chaves):
        if tempo <= t1:
            dur = t1 - t0
            u = (tempo - t0) / dur if dur > 1e-9 else 1.0
            f = u * u * u * (u * (u * 6.0 - 15.0) + 10.0)
            dir_v = tuple(a + (b - a) * f for a, b in zip(v0[0], v1[0], strict=True))
            esq_v = tuple(a + (b - a) * f for a, b in zip(v0[1], v1[1], strict=True))
            return dir_v, esq_v  # type: ignore[return-value]
    return chaves[-1][1]


def amostrar_cena_idle(
    nome: str,
    tempo: float,
    variante: int = 0,
) -> AmostraCenaIdle:
    """Amostra a cena de idle ``nome`` em ``tempo`` segundos."""
    cfg = _resolver_cfg_cena(nome, variante)
    if cfg is None:
        return AmostraCenaIdle()
    duracao = float(cfg.get("duration", 0.0))
    if duracao <= 0.0 or tempo < 0.0:
        return AmostraCenaIdle()
    if cfg.get("loop"):
        t = tempo % duracao
    elif tempo >= duracao:
        return AmostraCenaIdle()
    else:
        t = max(0.0, min(duracao, tempo))

    peso = _peso_cena(
        t,
        duracao,
        float(cfg.get("blend_entrada_s", 0.36)),
        float(cfg.get("blend_saida_s", 0.44)),
        peso_entrada=float(cfg.get("peso_entrada", 1.0)),
        peso_saida=float(cfg.get("peso_saida", 1.0)),
    )
    grupos_abs = frozenset(cfg.get("grupos_absolutos", _GRUPOS_BASE_ABS))
    delta = _amostrar_pistas(
        cfg.get("tracks", {}),
        t,
        grupos_abs=grupos_abs,
        curvas=cfg.get("curvas"),
    )
    if nome == "fone_com_problema":
        return _amostrar_fone_problema(cfg, t, peso, delta)
    if nome == "argolas_antena":
        return _amostrar_argolas_antena(cfg, t, peso, delta)
    pista_pernas = _PISTAS_PERNAS_CENAS.get(nome)
    pernas = _amostrar_pista_pernas(pista_pernas, t) if pista_pernas is not None else None
    pista_dedos = _PISTAS_DEDOS_CENAS.get(nome)
    dedos = _amostrar_pista_dedos(pista_dedos, t) if pista_dedos is not None else None
    return AmostraCenaIdle(
        ativa=True,
        nome=nome,
        delta_rig=delta,
        peso_mistura=peso,
        pernas_graus=pernas,
        dedos=dedos,
    )
