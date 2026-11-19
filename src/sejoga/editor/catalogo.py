"""Catálogo V1 de ações, famílias, variantes e busca do editor do Mário.

Domínio puro (sem Panda3D, Qt ou Win32). Constrói a árvore navegável a partir
dos dados autorais carregados para todas as 6 famílias + clipes glTF.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any

FAMILIAS_ORDEM: tuple[tuple[str, str], ...] = (
    ("idles_cenas", "Idles e Cenas"),
    ("respiracao", "Respiração"),
    ("danca", "Dança"),
    ("tentaculos", "Tentáculos"),
    ("reacoes", "Reações e Transições"),
    ("vfx", "VFX"),
    ("clipes_gltf", "Clipes glTF"),
)

_NOMES_AMIGAVEIS: dict[str, str] = {
    "escutar_fone": "Escutar por baixo do fone",
    "disfarcar_olhar": "Disfarçar o olhar",
    "batida_guardada": "Batida guardada",
    "ajeitar_fone": "Ajeitar o fone",
    "argolas_antena": "Argolas da antena",
    "fone_com_problema": "Fone com problema",
    "estouro_fone": "Faíscas do fone",
    "choque_argolas": "Choque das argolas",
    "aceno": "Aceno",
    "alongar": "Alongar",
    "cutucar": "Cutucar",
    "surpresa": "Surpresa",
    "walk": "Caminhada (Walk)",
    "run": "Corrida (Run)",
    "ciclo": "Ciclo base de respiração",
    "porta": "Porta e revelação",
    "trajetoria_ponta": "Trajetória da ponta",
    "gotas": "Gotas dos tentáculos",
}

_TAGS_EXTRA: dict[str, tuple[str, ...]] = {
    "escutar_fone": ("fone", "escuta", "som", "idle", "cena"),
    "disfarcar_olhar": ("olhar", "cursor", "disfarce", "idle", "cena"),
    "batida_guardada": ("musica", "groove", "ritmo", "idle", "cena"),
    "ajeitar_fone": ("fone", "headset", "idle", "cena"),
    "argolas_antena": ("antena", "argolas", "choque", "idle", "cena"),
    "fone_com_problema": ("fone", "faiscas", "estouro", "gosma", "estouro_fone"),
    "estouro_fone": ("fone", "faiscas", "fone_com_problema", "estouro"),
    "gosma": ("fone", "fone_com_problema", "espirro", "slime"),
    "choque_argolas": ("antena", "argolas", "argolas_antena"),
}


@dataclass(frozen=True, slots=True)
class AcaoCatalogo:
    """Uma entrada editável no catálogo do editor."""

    id: str
    nome: str
    familia_id: str
    familia_nome: str
    subfamilia: str
    secao_dados: str
    chave_dados: str
    tipo_editor: str
    duracao_padrao_s: float
    loop_padrao: bool
    variantes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    vfx_associados: tuple[str, ...] = ()
    descricao: str = ""


def _normalizar_texto(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _titulo_amigavel(chave: str) -> str:
    if chave in _NOMES_AMIGAVEIS:
        return _NOMES_AMIGAVEIS[chave]
    return chave.replace("_", " ").replace("-", " ").title()


def _adicionar_idles_e_cenas(dados: dict[str, Any], out: list[AcaoCatalogo]) -> None:
    fam_nome = "Idles e Cenas"
    for chave, cfg in dados.get("CENAS_IDLE", {}).items():
        vars_nomes = tuple(cfg.get("variantes", {}).keys())
        vfx = tuple(cfg.get("janelas_efeito", {}).keys())
        out.append(
            AcaoCatalogo(
                id=f"cenas_idle:{chave}",
                nome=_titulo_amigavel(chave),
                familia_id="idles_cenas",
                familia_nome=fam_nome,
                subfamilia="Cenas narrativas",
                secao_dados="CENAS_IDLE",
                chave_dados=chave,
                tipo_editor="pistas_3d",
                duracao_padrao_s=float(cfg.get("duration", 4.0)),
                loop_padrao=bool(cfg.get("loop", False)),
                variantes=vars_nomes,
                tags=(chave, *vars_nomes, *_TAGS_EXTRA.get(chave, ()), *vfx),
                vfx_associados=vfx,
                descricao="Cena narrativa em keyframes locais + janela de efeitos.",
            )
        )
    for chave, cfg in dados.get("IDLE_CLIPS", {}).items():
        vars_nomes = tuple(cfg.get("variantes", {}).keys())
        out.append(
            AcaoCatalogo(
                id=f"idle_clips:{chave}",
                nome=f"Idle • {_titulo_amigavel(chave)}",
                familia_id="idles_cenas",
                familia_nome=fam_nome,
                subfamilia="Personalidades de Idle",
                secao_dados="IDLE_CLIPS",
                chave_dados=chave,
                tipo_editor="pistas_3d",
                duracao_padrao_s=float(cfg.get("duration", 10.0)),
                loop_padrao=bool(cfg.get("loop", True)),
                variantes=vars_nomes,
                tags=(chave, "idle", *vars_nomes),
                descricao="Clipe cíclico de idle em 10s + ajuste postural assimétrico.",
            )
        )
    for chave, cfg in dados.get("LOCOMOCAO_CLIPS", {}).items():
        out.append(
            AcaoCatalogo(
                id=f"locomocao:{chave}",
                nome=_titulo_amigavel(chave),
                familia_id="idles_cenas",
                familia_nome=fam_nome,
                subfamilia="Locomoção cíclica",
                secao_dados="LOCOMOCAO_CLIPS",
                chave_dados=chave,
                tipo_editor="pistas_3d",
                duracao_padrao_s=float(cfg.get("duration", 1.0)),
                loop_padrao=bool(cfg.get("loop", True)),
                tags=(chave, "locomocao", "pernas", "passada"),
                descricao="Ciclo normalizado (0..1) de braços, tronco e cabeça.",
            )
        )


def _adicionar_respiracao(dados: dict[str, Any], out: list[AcaoCatalogo]) -> None:
    resp = dados.get("RESPIRACAO", {})
    ciclo = resp.get("ciclo", ((0.0, (0.0, 0.0, 0.0)), (3.6, (0.0, 0.0, 0.0))))
    dur_ciclo = float(ciclo[-1][0]) if ciclo else 3.6
    out.append(
        AcaoCatalogo(
            id="respiracao:ciclo",
            nome=_titulo_amigavel("ciclo"),
            familia_id="respiracao",
            familia_nome="Respiração",
            subfamilia="Curva global",
            secao_dados="RESPIRACAO",
            chave_dados="ciclo",
            tipo_editor="respiracao",
            duracao_padrao_s=dur_ciclo,
            loop_padrao=True,
            tags=("respiracao", "ciclo", "assimetria", "peito", "ombro"),
            descricao="Curva assimétrica de inspiração/expiração e contribuição por parte.",
        )
    )
    for pers in resp.get("personalidades", {}):
        out.append(
            AcaoCatalogo(
                id=f"respiracao:pers:{pers}",
                nome=f"Respiração • {_titulo_amigavel(pers)}",
                familia_id="respiracao",
                familia_nome="Respiração",
                subfamilia="Por personalidade",
                secao_dados="RESPIRACAO",
                chave_dados=f"personalidades:{pers}",
                tipo_editor="respiracao_pers",
                duracao_padrao_s=dur_ciclo,
                loop_padrao=True,
                tags=("respiracao", pers),
                descricao="Frequência, amplitude, bounce e pesos anatômicos.",
            )
        )


def _adicionar_danca(dados: dict[str, Any], out: list[AcaoCatalogo]) -> None:
    danca = dados.get("DANCA", {})
    out.append(
        AcaoCatalogo(
            id="danca:tuning",
            nome="Parâmetros globais de dança",
            familia_id="danca",
            familia_nome="Dança",
            subfamilia="Acentos e mistura",
            secao_dados="DANCA",
            chave_dados="tuning",
            tipo_editor="danca_tuning",
            duracao_padrao_s=4.0,
            loop_padrao=True,
            tags=("danca", "acento", "bpm", "mistura", "poses"),
            descricao="Fase das 4 poses por batida, acento, intensidade e mistura base.",
        )
    )
    for estilo in danca.get("frases", {}):
        out.append(
            AcaoCatalogo(
                id=f"danca:frase:{estilo}",
                nome=f"Frase • {_titulo_amigavel(estilo)}",
                familia_id="danca",
                familia_nome="Dança",
                subfamilia="Frases rítmicas",
                secao_dados="DANCA",
                chave_dados=f"frases:{estilo}",
                tipo_editor="danca_frase",
                duracao_padrao_s=4.0,
                loop_padrao=True,
                tags=("danca", "frase", estilo),
                descricao="Passos por batida (acento, sustentação, recuperação, preparação).",
            )
        )
    for clip_nome, cfg in danca.get("clipes", {}).items():
        out.append(
            AcaoCatalogo(
                id=f"danca:clipe:{clip_nome}",
                nome=f"Emote • {_titulo_amigavel(clip_nome)}",
                familia_id="danca",
                familia_nome="Dança",
                subfamilia="Clipes de dança",
                secao_dados="DANCA",
                chave_dados=f"clipes:{clip_nome}",
                tipo_editor="danca_clipe",
                duracao_padrao_s=float(cfg.get("fim_s") or 6.0),
                loop_padrao=bool(cfg.get("loop", True)),
                tags=("danca", "clipe", clip_nome),
                descricao="BPM nativo, velocidade, recorte e mistura do emote retargeted.",
            )
        )


def _adicionar_tentaculos(dados: dict[str, Any], out: list[AcaoCatalogo]) -> None:
    tent = dados.get("TENTACULOS", {})
    for chave, nome in (
        ("porta", _titulo_amigavel("porta")),
        ("trajetoria_ponta", _titulo_amigavel("trajetoria_ponta")),
        ("gotas", _titulo_amigavel("gotas")),
    ):
        if chave in tent:
            out.append(
                AcaoCatalogo(
                    id=f"tentaculos:{chave}",
                    nome=nome,
                    familia_id="tentaculos",
                    familia_nome="Tentáculos",
                    subfamilia="Mecânica e gotas",
                    secao_dados="TENTACULOS",
                    chave_dados=chave,
                    tipo_editor="tentaculos_cfg",
                    duracao_padrao_s=6.0,
                    loop_padrao=False,
                    tags=("tentaculos", chave, "obstaculo"),
                    descricao="Limiares da porta, trajetória/atraso e emissão de gotas.",
                )
            )
    for pers in tent.get("ondulacoes", {}):
        out.append(
            AcaoCatalogo(
                id=f"tentaculos:ondulacao:{pers}",
                nome=f"Ondulação • {_titulo_amigavel(pers)}",
                familia_id="tentaculos",
                familia_nome="Tentáculos",
                subfamilia="Por temperamento",
                secao_dados="TENTACULOS",
                chave_dados=f"ondulacoes:{pers}",
                tipo_editor="tentaculos_pers",
                duracao_padrao_s=6.0,
                loop_padrao=True,
                tags=("tentaculos", "ondulacao", "saida", pers),
                descricao="Amplitude, frequência, atraso e ângulo de saída da porta.",
            )
        )


def _adicionar_reacoes(dados: dict[str, Any], out: list[AcaoCatalogo]) -> None:
    reac = dados.get("REACOES", {})
    durs = reac.get("duracoes", {})
    gestos = (
        ("aceno", "wave"),
        ("alongar", "stretch"),
        ("cutucar", "poke"),
        ("surpresa", "surprise"),
        ("sono", "sleep"),
        ("pernas", "walk"),
        ("impulsos_corpo", "click"),
        ("teimosia", "teimosia"),
    )
    for chave, ref_dur in gestos:
        if chave in reac:
            dur = float(reac[chave].get("duracao_s", durs.get(ref_dur, 3.0)))
            out.append(
                AcaoCatalogo(
                    id=f"reacoes:{chave}",
                    nome=_titulo_amigavel(chave),
                    familia_id="reacoes",
                    familia_nome="Reações e Transições",
                    subfamilia="Comportamentos autorais",
                    secao_dados="REACOES",
                    chave_dados=chave,
                    tipo_editor="reacoes_cfg",
                    duracao_padrao_s=max(1.5, dur),
                    loop_padrao=chave in ("sono", "pernas"),
                    tags=("reacoes", chave, ref_dur),
                    descricao="Antecipação, resposta, recuperação e envelope comportamental.",
                )
            )
    for kind, dur in durs.items():
        if kind in ("wave", "stretch", "poke", "surprise", "teimosia"):
            continue
        out.append(
            AcaoCatalogo(
                id=f"reacoes:dur:{kind}",
                nome=f"Reação • {_titulo_amigavel(kind)}",
                familia_id="reacoes",
                familia_nome="Reações e Transições",
                subfamilia="Estímulos e gestos",
                secao_dados="REACOES",
                chave_dados=f"duracoes:{kind}",
                tipo_editor="reacao_duracao",
                duracao_padrao_s=max(0.5, float(dur)),
                loop_padrao=False,
                tags=("reacoes", "estimulo", kind),
                descricao="Duração e disparo em contexto da reação/interação.",
            )
        )
    for sub, titulo in (("entradas", "Entrada"), ("saidas", "Saída")):
        for estilo, cfg in reac.get(sub, {}).items():
            out.append(
                AcaoCatalogo(
                    id=f"reacoes:{sub}:{estilo}",
                    nome=f"{titulo} • {_titulo_amigavel(estilo)}",
                    familia_id="reacoes",
                    familia_nome="Reações e Transições",
                    subfamilia=f"Transições ({titulo}s)",
                    secao_dados="REACOES",
                    chave_dados=f"{sub}:{estilo}",
                    tipo_editor="transicao_cfg",
                    duracao_padrao_s=max(0.5, float(cfg.get("duracao_s", 1.5))),
                    loop_padrao=False,
                    tags=("transicao", sub, estilo),
                    descricao="Duração e velocidade da transição de entrada ou saída.",
                )
            )


def _adicionar_vfx(dados: dict[str, Any], out: list[AcaoCatalogo]) -> None:
    for nome, cfg in dados.get("VFX", {}).items():
        out.append(
            AcaoCatalogo(
                id=f"vfx:{nome}",
                nome=_titulo_amigavel(nome),
                familia_id="vfx",
                familia_nome="VFX",
                subfamilia=str(cfg.get("ancora", "cabeca")),
                secao_dados="VFX",
                chave_dados=nome,
                tipo_editor="vfx",
                duracao_padrao_s=max(1.0, float(cfg.get("duracao_s", 0.5)) * 3.0),
                loop_padrao=False,
                tags=(
                    "vfx",
                    nome,
                    str(cfg.get("ancora", "")),
                    str(cfg.get("disparo", "")),
                    *_TAGS_EXTRA.get(nome, ()),
                ),
                vfx_associados=(nome,),
                descricao="Âncora, deslocamento, escala, cor, emissão e fade.",
            )
        )


def _adicionar_gltf(dados: dict[str, Any], out: list[AcaoCatalogo]) -> None:
    for nome, cfg in dados.get("CLIPES_GLTF", {}).items():
        dur = float(cfg.get("fim_s") or 2.0)
        out.append(
            AcaoCatalogo(
                id=f"gltf:{nome}",
                nome=f"glTF • {nome}",
                familia_id="clipes_gltf",
                familia_nome="Clipes glTF",
                subfamilia="Importados",
                secao_dados="CLIPES_GLTF",
                chave_dados=nome,
                tipo_editor="gltf",
                duracao_padrao_s=dur,
                loop_padrao=bool(cfg.get("loop", False)),
                tags=("gltf", nome, str(cfg.get("arquivo", ""))),
                descricao="Referência glTF, recorte, velocidade, mistura e eventos.",
            )
        )


def construir_catalogo(dados: dict[str, Any]) -> tuple[AcaoCatalogo, ...]:
    """Gera o catálogo V1 completo a partir do dicionário autoral."""
    itens: list[AcaoCatalogo] = []
    _adicionar_idles_e_cenas(dados, itens)
    _adicionar_respiracao(dados, itens)
    _adicionar_danca(dados, itens)
    _adicionar_tentaculos(dados, itens)
    _adicionar_reacoes(dados, itens)
    _adicionar_vfx(dados, itens)
    _adicionar_gltf(dados, itens)
    return tuple(itens)


def buscar_catalogo(
    itens: tuple[AcaoCatalogo, ...] | list[AcaoCatalogo],
    consulta: str,
) -> list[AcaoCatalogo]:
    """Filtra ``itens`` pela busca textual normalizada em nome, família e tags."""
    termo = _normalizar_texto(consulta.strip())
    if not termo:
        return list(itens)
    partes = termo.split()
    resultado: list[AcaoCatalogo] = []
    for item in itens:
        palheiro = _normalizar_texto(
            " ".join(
                [
                    item.id,
                    item.nome,
                    item.familia_nome,
                    item.subfamilia,
                    item.chave_dados,
                    *item.tags,
                    *item.vfx_associados,
                ]
            )
        )
        if all(p in palheiro for p in partes):
            resultado.append(item)
    return resultado
