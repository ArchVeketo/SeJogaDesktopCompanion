"""Documento de edição com histórico desfazer/refazer, transações e salvamento.

Domínio puro (sem Panda3D, Qt ou Win32). Mantém ``salvo`` versus ``rascunho``,
detecta conflitos externos por SHA-256, valida reduções de duração e guarda
ajustes provisórios quando o modo auto-chave está desligado.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sejoga.animacao import dados_autorais
from sejoga.editor.persistencia import (
    CAMINHO_ANIMATION_PADRAO,
    ArquivoAnimacao,
    carregar_arquivo_animacao,
    salvar_arquivo_animacao,
    validar_dados_animacao,
)

LIMITE_PILHA_UNDO = 120


@dataclass(frozen=True, slots=True)
class ConflitoDuracao:
    """Item que ficaria além da nova duração solicitada."""

    tipo: str  # "chave" | "janela_efeito" | "deslocamento_janela" | "evento"
    pista: str
    tempo_s: float
    detalhe: str


@dataclass(frozen=True, slots=True)
class ComandoEditor:
    """Entrada atômica na pilha de desfazer/refazer."""

    descricao: str
    antes: dict[str, Any]
    depois: dict[str, Any]


@dataclass(slots=True)
class PoseProvisoria:
    """Ajustes temporários feitos na prévia com auto-chave desligado."""

    acao_id: str = ""
    variante: str | None = None
    tempo_s: float = 0.0
    grupos: dict[str, tuple[float, float, float]] = field(default_factory=dict)

    @property
    def ativa(self) -> bool:
        """Indica se há juntas alteradas ainda não gravadas em keyframes."""
        return bool(self.grupos)


class DocumentoEditor:
    """Gerencia rascunho vivo, histórico e gravação atômica de ``animation.py``."""

    def __init__(self, arquivo: ArquivoAnimacao | None = None) -> None:
        """Abre o arquivo em disco (ou usa snapshot fornecido)."""
        carregado = arquivo or carregar_arquivo_animacao()
        self.caminho: Path = carregado.caminho
        self.sha256_disco: str = carregado.sha256
        self.mtime_ns: int = carregado.mtime_ns
        self.salvo: dict[str, Any] = deepcopy(carregado.dados)
        self.rascunho: dict[str, Any] = deepcopy(carregado.dados)
        self.revisao_id: int = 1
        self._pilha_undo: list[ComandoEditor] = []
        self._pilha_redo: list[ComandoEditor] = []
        self._transacao_desc: str | None = None
        self._transacao_antes: dict[str, Any] | None = None
        self.provisoria = PoseProvisoria()

    @property
    def sujo(self) -> bool:
        """Indica se o rascunho atual difere da última versão salva."""
        return self.rascunho != self.salvo

    @property
    def pode_desfazer(self) -> bool:
        """Indica se há operação disponível para desfazer."""
        return bool(self._pilha_undo)

    @property
    def pode_refazer(self) -> bool:
        """Indica se há operação disponível para refazer."""
        return bool(self._pilha_redo)

    @property
    def proxima_descricao_undo(self) -> str:
        """Descrição da próxima ação a desfazer."""
        return self._pilha_undo[-1].descricao if self._pilha_undo else ""

    @property
    def proxima_descricao_redo(self) -> str:
        """Descrição da próxima ação a refazer."""
        return self._pilha_redo[-1].descricao if self._pilha_redo else ""

    def sincronizar_rascunho_runtime(self) -> Any:
        """Retorna um gerenciador de contexto que expõe este rascunho em ``dados_autorais``."""
        return dados_autorais.usar_rascunho(self.rascunho)

    def aplicar_edicao(
        self,
        descricao: str,
        mutador: Callable[[dict[str, Any]], None],
    ) -> bool:
        """Aplica ``mutador`` no rascunho validado e registra uma entrada de desfazer."""
        antes = deepcopy(self.rascunho)
        candidato = deepcopy(self.rascunho)
        mutador(candidato)
        if candidato == antes:
            return False
        validar_dados_animacao(candidato)
        self._registrar_comando(ComandoEditor(descricao, antes, candidato))
        self.rascunho = candidato
        self.revisao_id += 1
        return True

    def iniciar_transacao(self, descricao: str) -> None:
        """Inicia um arraste contínuo (gizmo/timeline) que gera apenas 1 desfazer."""
        if self._transacao_antes is None:
            self._transacao_desc = descricao
            self._transacao_antes = deepcopy(self.rascunho)

    def atualizar_transacao(self, mutador: Callable[[dict[str, Any]], None]) -> bool:
        """Atualiza a prévia viva durante o arraste sem empilhar desfazer ainda."""
        if self._transacao_antes is None:
            return False
        candidato = deepcopy(self._transacao_antes)
        mutador(candidato)
        validar_dados_animacao(candidato)
        self.rascunho = candidato
        self.revisao_id += 1
        return True

    def confirmar_transacao(self) -> bool:
        """Finaliza o arraste gravando uma única operação na pilha de desfazer."""
        if self._transacao_antes is None:
            return False
        antes = self._transacao_antes
        desc = self._transacao_desc or "Ajuste interativo"
        self._transacao_antes = None
        self._transacao_desc = None
        if self.rascunho == antes:
            return False
        validar_dados_animacao(self.rascunho)
        self._registrar_comando(ComandoEditor(desc, antes, deepcopy(self.rascunho)))
        return True

    def cancelar_transacao(self) -> bool:
        """Cancela o arraste em curso (Esc) restaurando a pose anterior."""
        if self._transacao_antes is None:
            return False
        self.rascunho = self._transacao_antes
        self._transacao_antes = None
        self._transacao_desc = None
        self.revisao_id += 1
        return True

    def _registrar_comando(self, cmd: ComandoEditor) -> None:
        self._pilha_undo.append(cmd)
        if len(self._pilha_undo) > LIMITE_PILHA_UNDO:
            self._pilha_undo.pop(0)
        self._pilha_redo.clear()

    def desfazer(self) -> str | None:
        """Desfaz a última operação validada; devolve sua descrição."""
        self.cancelar_transacao()
        if not self._pilha_undo:
            return None
        cmd = self._pilha_undo.pop()
        self.rascunho = deepcopy(cmd.antes)
        self._pilha_redo.append(cmd)
        self.revisao_id += 1
        return cmd.descricao

    def refazer(self) -> str | None:
        """Refaz a última operação desfeita; devolve sua descrição."""
        self.cancelar_transacao()
        if not self._pilha_redo:
            return None
        cmd = self._pilha_redo.pop()
        self.rascunho = deepcopy(cmd.depois)
        self._pilha_undo.append(cmd)
        self.revisao_id += 1
        return cmd.descricao

    def definir_provisoria(
        self,
        acao_id: str,
        variante: str | None,
        tempo_s: float,
        grupo: str,
        valor: tuple[float, float, float],
    ) -> None:
        """Registra ajuste de junta em modo leitura (auto-chave desligado)."""
        if (
            self.provisoria.acao_id != acao_id
            or self.provisoria.variante != variante
            or abs(self.provisoria.tempo_s - tempo_s) > 1e-4
        ):
            self.provisoria = PoseProvisoria(
                acao_id=acao_id, variante=variante, tempo_s=tempo_s
            )
        self.provisoria.grupos[grupo] = (
            float(valor[0]),
            float(valor[1]),
            float(valor[2]),
        )

    def descartar_provisoria(self) -> None:
        """Limpa ajustes provisórios ainda não gravados."""
        self.provisoria = PoseProvisoria()

    def gravar_provisoria_em_pista(
        self,
        secao: str,
        chave_item: str,
        *,
        variante: str | None = None,
    ) -> bool:
        """Converte todos os ajustes provisórios pendentes em chaves reais no tempo."""
        if not self.provisoria.ativa:
            return False
        tempo = self.provisoria.tempo_s
        grupos = dict(self.provisoria.grupos)

        def _mutar(dados: dict[str, Any]) -> None:
            alvo = _bloco_pistas_editavel(dados, secao, chave_item, variante)
            dur = float(alvo["duration"])
            t_clamp = round(max(0.0, min(dur, tempo)), 4)
            for grp, val in grupos.items():
                _inserir_ou_atualizar_chave_bloco(alvo, grp, t_clamp, val)

        ok = self.aplicar_edicao(f"Inserir chave em {tempo:.2f}s", _mutar)
        self.descartar_provisoria()
        return ok

    def verificar_reducao_duracao(
        self,
        secao: str,
        chave_item: str,
        nova_duracao_s: float,
        *,
        variante: str | None = None,
    ) -> list[ConflitoDuracao]:
        """Lista chaves ou janelas que extrapolam ``nova_duracao_s``."""
        alvo = _bloco_pistas_editavel(self.rascunho, secao, chave_item, variante)
        conflitos: list[ConflitoDuracao] = []
        eps = 1e-4
        for grupo, pista in alvo.get("tracks", {}).items():
            for idx, (t, _val) in enumerate(pista):
                if float(t) > nova_duracao_s + eps and idx < len(pista) - 1:
                    conflitos.append(
                        ConflitoDuracao(
                            tipo="chave",
                            pista=grupo,
                            tempo_s=float(t),
                            detalhe=f"Chave de {grupo} em {t:.2f}s",
                        )
                    )
        for nome_ef, janela in alvo.get("janelas_efeito", {}).items():
            fim = float(janela[1])
            if fim > nova_duracao_s + eps:
                conflitos.append(
                    ConflitoDuracao(
                        tipo="janela_efeito",
                        pista=nome_ef,
                        tempo_s=fim,
                        detalhe=f"Efeito {nome_ef} termina em {fim:.2f}s",
                    )
                )
        desl = alvo.get("deslocamento_janela_s")
        if isinstance(desl, (tuple, list)) and len(desl) == 2 and float(desl[1]) > nova_duracao_s + eps:
            conflitos.append(
                ConflitoDuracao(
                    tipo="deslocamento_janela",
                    pista="deslocamento_corpo",
                    tempo_s=float(desl[1]),
                    detalhe=f"Janela de deslocamento termina em {float(desl[1]):.2f}s",
                )
            )
        return conflitos

    def aplicar_nova_duracao(
        self,
        secao: str,
        chave_item: str,
        nova_duracao_s: float,
        *,
        variante: str | None = None,
        ajustar_excedentes: bool = False,
    ) -> bool:
        """Altera a duração da ação, opcionalmente recortando chaves/janelas além do fim."""
        nova = round(max(0.05, float(nova_duracao_s)), 4)

        def _mutar(dados: dict[str, Any]) -> None:
            alvo = _bloco_pistas_editavel(dados, secao, chave_item, variante)
            dur_antiga = max(1e-4, float(alvo["duration"]))
            alvo["duration"] = nova
            _ajustar_bloco_para_duracao(alvo, dur_antiga, nova, ajustar_excedentes)

        return self.aplicar_edicao(f"Alterar duração para {nova:.2f}s", _mutar)

    def salvar(self, *, forcar: bool = False) -> ArquivoAnimacao:
        """Valida e grava o rascunho atomicamente no ``animation.py``."""
        if self.provisoria.ativa:
            raise ValueError(
                "Existem ajustes provisórios pendentes sem keyframe gravado."
            )
        self.confirmar_transacao()
        gravado = salvar_arquivo_animacao(
            self.caminho,
            deepcopy(self.rascunho),
            sha256_esperado=None if forcar else self.sha256_disco,
            forcar=forcar,
        )
        self.sha256_disco = gravado.sha256
        self.mtime_ns = gravado.mtime_ns
        self.salvo = deepcopy(self.rascunho)
        self.revisao_id += 1
        if self.caminho.resolve() == CAMINHO_ANIMATION_PADRAO.resolve():
            dados_autorais.recarregar_dados_salvos()
        return gravado

    def recarregar_externa(self) -> ArquivoAnimacao:
        """Descarta rascunho local e recarrega o ``animation.py`` atual do disco."""
        self.cancelar_transacao()
        self.descartar_provisoria()
        carregado = carregar_arquivo_animacao(self.caminho)
        self.sha256_disco = carregado.sha256
        self.mtime_ns = carregado.mtime_ns
        self.salvo = deepcopy(carregado.dados)
        self.rascunho = deepcopy(carregado.dados)
        self._pilha_undo.clear()
        self._pilha_redo.clear()
        self.revisao_id += 1
        if self.caminho.resolve() == CAMINHO_ANIMATION_PADRAO.resolve():
            dados_autorais.recarregar_dados_salvos()
        return carregado


def _bloco_pistas_editavel(
    dados: dict[str, Any],
    secao: str,
    chave_item: str,
    variante: str | None,
) -> dict[str, Any]:
    raiz = dados[secao][chave_item]
    if variante:
        vars_map = raiz.setdefault("variantes", {})
        if variante in vars_map and isinstance(vars_map[variante], dict):
            return vars_map[variante]
    return raiz


def _inserir_ou_atualizar_chave_bloco(
    alvo: dict[str, Any],
    grupo: str,
    tempo_s: float,
    valor: tuple[float, float, float],
    curva: str = "quintic",
) -> None:
    tracks = alvo.setdefault("tracks", {})
    curvas = alvo.setdefault("curvas", {})
    pista_atual = list(tracks.get(grupo, ((0.0, (0.0, 0.0, 0.0)), (float(alvo["duration"]), (0.0, 0.0, 0.0)))))
    curvas_atuais = list(curvas.get(grupo, (curva,) * max(1, len(pista_atual) - 1)))
    limpo = (round(float(valor[0]), 4), round(float(valor[1]), 4), round(float(valor[2]), 4))
    for idx, (t_k, _v_k) in enumerate(pista_atual):
        if abs(float(t_k) - tempo_s) <= 1e-3:
            pista_atual[idx] = (float(t_k), limpo)
            tracks[grupo] = tuple(pista_atual)
            return
    pares = sorted(
        [(float(t_k), tuple(float(c) for c in v_k)) for t_k, v_k in pista_atual]
        + [(tempo_s, limpo)],
        key=lambda item: item[0],
    )
    ins_idx = next(i for i, (tk, _) in enumerate(pares) if abs(tk - tempo_s) <= 1e-6)
    while len(curvas_atuais) < max(1, len(pares) - 2):
        curvas_atuais.append(curva)
    curvas_atuais.insert(min(len(curvas_atuais), max(0, ins_idx - 1)), curva)
    tracks[grupo] = tuple((t_k, (v_k[0], v_k[1], v_k[2])) for t_k, v_k in pares)
    curvas[grupo] = tuple(curvas_atuais[: max(1, len(pares) - 1)])


def _ajustar_bloco_para_duracao(
    alvo: dict[str, Any],
    dur_antiga: float,
    nova: float,
    recortar: bool,
) -> None:
    tracks = alvo.get("tracks", {})
    curvas = alvo.get("curvas", {})
    for grupo, pista in list(tracks.items()):
        mantidas = [(float(t), v) for t, v in pista[:-1] if float(t) < nova - 1e-4]
        ultima_val = pista[-1][1]
        if not mantidas:
            mantidas = [(0.0, pista[0][1])]
        if abs(float(pista[-1][0]) - dur_antiga) <= 1e-3 or float(pista[-1][0]) > nova or recortar:
            mantidas.append((nova, ultima_val))
        else:
            mantidas.append((float(pista[-1][0]), ultima_val))
        tracks[grupo] = tuple(mantidas)
        if grupo in curvas:
            n_seg = max(1, len(mantidas) - 1)
            c_old = list(curvas[grupo])
            curvas[grupo] = tuple((c_old + ["quintic"] * n_seg)[:n_seg])
    if recortar:
        janelas = alvo.get("janelas_efeito", {})
        for nome_ef, jan in list(janelas.items()):
            ini = min(float(jan[0]), max(0.0, nova - 0.05))
            fim = max(ini + 0.02, min(float(jan[1]), nova))
            janelas[nome_ef] = (round(ini, 4), round(fim, 4))
        desl = alvo.get("deslocamento_janela_s")
        if isinstance(desl, (tuple, list)) and len(desl) == 2:
            ini = min(float(desl[0]), max(0.0, nova - 0.05))
            fim = max(ini + 0.02, min(float(desl[1]), nova))
            alvo["deslocamento_janela_s"] = (round(ini, 4), round(fim, 4))
