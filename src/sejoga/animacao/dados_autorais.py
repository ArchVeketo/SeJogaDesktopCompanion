"""Fonte compartilhada dos dados autorais entre companion e editor.

Por padrão lê ``sejoga.animacao.animation``. Durante a prévia no editor,
``usar_rascunho`` (ou ``definir_rascunho_ativo``) injeta o rascunho em memória
no mesmo caminho de amostragem do runtime sem alterar o arquivo salvo.
Sem dependências de Panda3D, Qt ou Win32.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from sejoga.animacao import animation as _modulo_animacao

_CHAVES_TOPO: tuple[str, ...] = (
    "VERSAO_ESQUEMA",
    "IDLE_CLIPS",
    "CENAS_IDLE",
    "LOCOMOCAO_CLIPS",
    "RESPIRACAO",
    "DANCA",
    "TENTACULOS",
    "REACOES",
    "VFX",
    "CLIPES_GLTF",
)

_rascunho_contexto: ContextVar[dict[str, Any] | None] = ContextVar(
    "sejoga_rascunho_autorais",
    default=None,
)
_rascunho_global: dict[str, Any] | None = None


def snapshot_salvo() -> dict[str, Any]:
    """Devolve o dicionário vivo das seções atualmente carregadas de ``animation.py``."""
    return {chave: getattr(_modulo_animacao, chave) for chave in _CHAVES_TOPO}


def recarregar_dados_salvos() -> dict[str, Any]:
    """Recarrega ``sejoga.animacao.animation`` após salvamento em disco."""
    importlib.invalidate_caches()
    importlib.reload(_modulo_animacao)
    return snapshot_salvo()


def definir_rascunho_ativo(dados: dict[str, Any] | None) -> None:
    """Define ou limpa um rascunho global em memória para a sessão de prévia."""
    global _rascunho_global
    _rascunho_global = dados


@contextmanager
def usar_rascunho(dados: dict[str, Any] | None) -> Iterator[None]:
    """Ativa temporariamente ``dados`` como fonte autoral neste contexto."""
    token = _rascunho_contexto.set(dados)
    try:
        yield
    finally:
        _rascunho_contexto.reset(token)


def obter_secao(nome: str) -> Any:
    """Retorna a seção autoral ``nome`` do rascunho ativo ou de ``animation.py``."""
    ctx = _rascunho_contexto.get()
    if ctx is not None and nome in ctx:
        return ctx[nome]
    if _rascunho_global is not None and nome in _rascunho_global:
        return _rascunho_global[nome]
    return getattr(_modulo_animacao, nome)


def idle_clips_ativos() -> dict[str, dict[str, Any]]:
    """Mapa ativo de ``IDLE_CLIPS``."""
    return obter_secao("IDLE_CLIPS")


def cenas_idle_ativas() -> dict[str, dict[str, Any]]:
    """Mapa ativo de ``CENAS_IDLE``."""
    return obter_secao("CENAS_IDLE")


def locomocao_clips_ativos() -> dict[str, dict[str, Any]]:
    """Mapa ativo de ``LOCOMOCAO_CLIPS``."""
    return obter_secao("LOCOMOCAO_CLIPS")


def respiracao_ativa() -> dict[str, Any]:
    """Configuração ativa de ``RESPIRACAO``."""
    return obter_secao("RESPIRACAO")


def danca_ativa() -> dict[str, Any]:
    """Configuração ativa de ``DANCA``."""
    return obter_secao("DANCA")


def tentaculos_ativos() -> dict[str, Any]:
    """Configuração ativa de ``TENTACULOS``."""
    return obter_secao("TENTACULOS")


def reacoes_ativas() -> dict[str, Any]:
    """Configuração ativa de ``REACOES``."""
    return obter_secao("REACOES")


def vfx_ativos() -> dict[str, dict[str, Any]]:
    """Configuração ativa de ``VFX``."""
    return obter_secao("VFX")


def clipes_gltf_ativos() -> dict[str, dict[str, Any]]:
    """Configuração ativa de ``CLIPES_GLTF``."""
    return obter_secao("CLIPES_GLTF")
