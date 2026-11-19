"""Operações puras sobre chaves, curvas, janelas e caminhos no rascunho."""

from __future__ import annotations

from typing import Any

from sejoga.editor.catalogo import AcaoCatalogo


def bloco_pistas_para_acao(
    dados: dict[str, Any],
    acao: AcaoCatalogo,
    variante: str | None = None,
) -> dict[str, Any] | None:
    """Resolve o dicionário editável de pistas para ``acao`` e ``variante``."""
    secao = dados.get(acao.secao_dados)
    if not isinstance(secao, dict):
        return None
    bloco = secao.get(acao.chave_dados)
    if not isinstance(bloco, dict):
        return None
    if variante and isinstance(bloco.get("variantes"), dict):
        sub = bloco["variantes"].get(variante)
        if isinstance(sub, dict):
            return sub
    return bloco


def mutar_caminho_rascunho(
    raiz: dict[str, Any],
    caminho: tuple[Any, ...],
    valor: Any,
) -> None:
    """Escreve ``valor`` em ``caminho``, reconstruindo tuplas intermediárias."""
    if not caminho:
        return
    atual: Any = raiz
    for depth, passo in enumerate(caminho[:-1]):
        prox = atual[passo]
        if isinstance(prox, tuple):
            nova_lista = list(prox)
            _aplicar_em_sequencia(nova_lista, caminho[depth + 1 :], valor)
            if isinstance(atual, dict):
                atual[passo] = tuple(nova_lista)
            return
        atual = prox
    ultimo = caminho[-1]
    if isinstance(atual, dict):
        atual[ultimo] = valor


def _aplicar_em_sequencia(
    seq: list[Any],
    resto: tuple[Any, ...],
    valor: Any,
) -> None:
    if len(resto) == 1:
        seq[int(resto[0])] = valor
        return
    cabeca = resto[0]
    alvo = seq[int(cabeca)]
    if isinstance(alvo, tuple):
        sub = list(alvo)
        _aplicar_em_sequencia(sub, resto[1:], valor)
        seq[int(cabeca)] = tuple(sub)
        return
    if isinstance(alvo, dict):
        mutar_caminho_rascunho(alvo, resto[1:], valor)


def indice_chave_proxima(
    chaves: tuple[tuple[float, Any], ...],
    tempo_s: float,
    tolerancia: float = 0.015,
) -> int | None:
    """Retorna o índice da chave dentro de ``tolerancia`` s ou ``None``."""
    melhor_idx: int | None = None
    melhor_dist = tolerancia
    for idx, (kt, _) in enumerate(chaves):
        dist = abs(float(kt) - tempo_s)
        if dist <= melhor_dist:
            melhor_dist = dist
            melhor_idx = idx
    return melhor_idx


def inserir_ou_atualizar_chave(
    bloco: dict[str, Any],
    grupo: str,
    tempo_s: float,
    valor: tuple[float, float, float],
    *,
    curva_padrao: str = "quintic",
    tolerancia: float = 0.015,
) -> int:
    """Insere ou atualiza chave em ``bloco['tracks'][grupo]`` preservando curvas."""
    tracks = bloco.setdefault("tracks", {})
    curvas_map = bloco.setdefault("curvas", {})
    lista = list(tracks.get(grupo, ()))
    curvas = list(curvas_map.get(grupo, ()))
    arred_t = round(max(0.0, float(tempo_s)), 4)
    val_arred = (round(valor[0], 3), round(valor[1], 3), round(valor[2], 3))

    idx_ex = indice_chave_proxima(tuple(lista), arred_t, tolerancia)
    if idx_ex is not None:
        lista[idx_ex] = (float(lista[idx_ex][0]), val_arred)
        tracks[grupo] = tuple(lista)
        return idx_ex

    lista.append((arred_t, val_arred))
    lista.sort(key=lambda item: float(item[0]))
    novo_idx = next(
        i for i, item in enumerate(lista) if abs(float(item[0]) - arred_t) < 1e-5
    )
    alvo_curvas = max(0, len(lista) - 1)
    while len(curvas) < alvo_curvas:
        curvas.insert(min(novo_idx, len(curvas)), curva_padrao)
    tracks[grupo] = tuple(lista)
    curvas_map[grupo] = tuple(curvas[:alvo_curvas])
    return novo_idx


def remover_chave_no_tempo(
    bloco: dict[str, Any],
    grupo: str,
    tempo_s: float,
    *,
    tolerancia: float = 0.015,
) -> bool:
    """Remove a chave próxima a ``tempo_s`` mantendo ao menos 1 chave na pista."""
    tracks = bloco.get("tracks", {})
    lista = list(tracks.get(grupo, ()))
    if len(lista) <= 1:
        return False
    idx = indice_chave_proxima(tuple(lista), tempo_s, tolerancia)
    if idx is None:
        return False
    lista.pop(idx)
    tracks[grupo] = tuple(lista)
    curvas_map = bloco.get("curvas", {})
    if isinstance(curvas_map, dict) and grupo in curvas_map:
        curvas = list(curvas_map[grupo])
        if idx < len(curvas):
            curvas.pop(idx)
        curvas_map[grupo] = tuple(curvas[: max(0, len(lista) - 1)])
    return True


def mover_chave_indice(
    bloco: dict[str, Any],
    grupo: str,
    indice: int,
    novo_tempo_s: float,
    nova_rot: tuple[float, float, float] | None = None,
) -> int:
    """Move a chave ``indice`` para ``novo_tempo_s`` e atualiza rotação opcional."""
    tracks = bloco.get("tracks", {})
    lista = list(tracks.get(grupo, ()))
    if not (0 <= indice < len(lista)):
        return indice
    rot_atual = lista[indice][1]
    rot = (
        (round(nova_rot[0], 3), round(nova_rot[1], 3), round(nova_rot[2], 3))
        if nova_rot is not None
        else rot_atual
    )
    dur = float(bloco.get("duration", 120.0))
    t_clamped = round(max(0.0, min(dur, float(novo_tempo_s))), 4)
    marca = object()
    marcada: list[tuple[float, Any, object]] = [
        (t_clamped if i == indice else float(item[0]), rot if i == indice else item[1], marca if i == indice else None)
        for i, item in enumerate(lista)
    ]
    marcada.sort(key=lambda item: item[0])
    tracks[grupo] = tuple((t, r) for t, r, _ in marcada)
    for idx_out, (_, _, m) in enumerate(marcada):
        if m is marca:
            return idx_out
    return indice


def aplicar_curva_selecao(
    bloco: dict[str, Any],
    curva: str,
    chaves_sel: list[tuple[str, int]],
    *,
    grupo_padrao: str,
    tempo_s: float,
) -> None:
    """Aplica o tipo de curva às chaves selecionadas ou ao segmento atual."""
    tracks = bloco.get("tracks", {})
    curvas_map = bloco.setdefault("curvas", {})
    alvos = list(chaves_sel)
    if not alvos and grupo_padrao in tracks:
        chaves = tracks[grupo_padrao]
        seg = max(
            0,
            min(
                max(0, len(chaves) - 2),
                next(
                    (i for i, (kt, _) in enumerate(chaves) if float(kt) >= tempo_s - 1e-4),
                    0,
                )
                - 1,
            ),
        )
        alvos = [(grupo_padrao, seg)]

    for grupo, idx in alvos:
        if grupo not in tracks:
            continue
        qtd_segs = max(0, len(tracks[grupo]) - 1)
        if qtd_segs == 0:
            continue
        curvas = list(curvas_map.get(grupo, ("quintic",) * qtd_segs))
        while len(curvas) < qtd_segs:
            curvas.append("quintic")
        seg_idx = max(0, min(qtd_segs - 1, idx))
        curvas[seg_idx] = curva
        curvas_map[grupo] = tuple(curvas[:qtd_segs])


def calcular_ids_sujos(
    salvo: dict[str, Any],
    rascunho: dict[str, Any],
    acoes: list[AcaoCatalogo],
) -> set[str]:
    """Identifica todas as ações do catálogo com diferenças entre salvo e rascunho."""
    sujos: set[str] = set()
    for acao in acoes:
        a = _valor_para_acao(salvo, acao)
        b = _valor_para_acao(rascunho, acao)
        if a != b:
            sujos.add(acao.id)
    return sujos


def _valor_para_acao(dados: dict[str, Any], acao: AcaoCatalogo) -> Any:
    sec = dados.get(acao.secao_dados, {})
    if not isinstance(sec, dict):
        return None
    if ":" in acao.chave_dados:
        raiz, resto = acao.chave_dados.split(":", 1)
        sub = sec.get(raiz)
        return sub.get(resto) if isinstance(sub, dict) else None
    return sec.get(acao.chave_dados)
