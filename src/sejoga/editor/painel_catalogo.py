"""Painel esquerdo de catálogo: busca, famílias recolhíveis e seleção de variantes."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sejoga.editor.catalogo import (
    FAMILIAS_ORDEM,
    AcaoCatalogo,
    buscar_catalogo,
)

_ROLE_ACAO_ID = Qt.ItemDataRole.UserRole


class PainelCatalogo(QWidget):
    """Catálogo pesquisável de ações agrupadas por família e variante."""

    acao_solicitada = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa o catálogo com busca, seletor de variante e árvore."""
        super().__init__(parent)
        self.setObjectName("painelCatalogo")
        self.setAccessibleName("Catálogo de ações")
        self.setMinimumWidth(190)

        self._acoes: list[AcaoCatalogo] = []
        self._por_id: dict[str, AcaoCatalogo] = {}
        self._ids_sujos: set[str] = set()
        self._acao_atual_id: str | None = None
        self._variante_atual: str | None = None
        self._bloqueando_sinais = False
        self._construir_ui()

    def _construir_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._campo_busca = QLineEdit(self)
        self._campo_busca.setPlaceholderText("Buscar ação…")
        self._campo_busca.setClearButtonEnabled(True)
        self._campo_busca.setAccessibleName("Buscar ação no catálogo")
        self._campo_busca.textChanged.connect(self._repopular_arvore)
        layout.addWidget(self._campo_busca)
        layout.addLayout(self._criar_linha_variante())

        self._arvore = self._criar_arvore()
        layout.addWidget(self._arvore, 1)

        self._rotulo_contagem = QLabel("0 ações", self)
        self._rotulo_contagem.setObjectName("rotuloSuave")
        layout.addWidget(self._rotulo_contagem)

    def _criar_linha_variante(self) -> QHBoxLayout:
        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        lbl_var = QLabel("Variante", self)
        lbl_var.setObjectName("rotuloSuave")
        self._combo_variante = QComboBox(self)
        self._combo_variante.setAccessibleName("Selecionar variante da ação")
        self._combo_variante.currentIndexChanged.connect(self._on_variante_mudou)
        linha.addWidget(lbl_var)
        linha.addWidget(self._combo_variante, 1)
        return linha

    def _criar_arvore(self) -> QTreeWidget:
        arvore = QTreeWidget(self)
        arvore.setHeaderHidden(True)
        arvore.setIndentation(14)
        arvore.setAnimated(False)
        arvore.setUniformRowHeights(True)
        arvore.setAccessibleName("Lista de famílias e ações")
        arvore.currentItemChanged.connect(self._on_item_atual_mudou)
        arvore.itemActivated.connect(self._on_item_ativado)
        return arvore

    def definir_acoes(self, acoes: list[AcaoCatalogo]) -> None:
        """Atualiza a lista completa de ações exibidas no catálogo."""
        self._acoes = list(acoes)
        self._por_id = {acao.id: acao for acao in self._acoes}
        self._repopular_arvore()

    def definir_sujos(self, ids_sujos: set[str]) -> None:
        """Marca visualmente ações com alterações ainda não salvas."""
        self._ids_sujos = set(ids_sujos)
        self._atualizar_rotulos_sujos()

    def buscar(self, texto: str) -> None:
        """Define o termo de busca e atualiza a filtragem imediatamente."""
        self._campo_busca.setText(texto)

    def texto_busca(self) -> str:
        """Retorna o texto atual do campo de busca."""
        return self._campo_busca.text()

    def focar_busca(self) -> None:
        """Leva foco ao campo de busca do catálogo."""
        self._campo_busca.setFocus()
        self._campo_busca.selectAll()

    def acoes_visiveis_ids(self) -> list[str]:
        """Retorna os IDs das ações visíveis atualmente após o filtro."""
        termo = self._campo_busca.text()
        filtradas = buscar_catalogo(self._acoes, termo)
        return [acao.id for acao in filtradas]

    def selecionar_acao(
        self,
        acao_id: str,
        variante: str | None = None,
        *,
        emitir: bool = False,
    ) -> None:
        """Seleciona programaticamente ação e variante no catálogo."""
        self._acao_atual_id = acao_id
        self._variante_atual = variante
        self._bloqueando_sinais = True
        try:
            self._sincronizar_combo_variante(self._por_id.get(acao_id), variante)
            item = self._encontrar_item(acao_id)
            if item is not None:
                pai = item.parent()
                if pai is not None:
                    pai.setExpanded(True)
                self._arvore.setCurrentItem(item)
        finally:
            self._bloqueando_sinais = False
        if emitir:
            self.acao_solicitada.emit(acao_id, self._variante_atual)

    def _repopular_arvore(self) -> None:
        self._bloqueando_sinais = True
        try:
            self._arvore.clear()
            termo = self._campo_busca.text().strip()
            filtradas = buscar_catalogo(self._acoes, termo)
            por_familia: dict[str, list[AcaoCatalogo]] = {}
            for acao in filtradas:
                por_familia.setdefault(acao.familia_id, []).append(acao)

            for fam_id, fam_nome in FAMILIAS_ORDEM:
                itens_fam = por_familia.get(fam_id, [])
                if not itens_fam:
                    continue
                ramo = QTreeWidgetItem([f"{fam_nome} ({len(itens_fam)})"])
                ramo.setFlags(ramo.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self._arvore.addTopLevelItem(ramo)
                for acao in itens_fam:
                    texto_item = self._formatar_texto_item(acao, mostrar_fam=bool(termo))
                    filho = QTreeWidgetItem([texto_item])
                    filho.setData(0, _ROLE_ACAO_ID, acao.id)
                    filho.setToolTip(0, f"{acao.familia_nome} — {acao.descricao}")
                    ramo.addChild(filho)
                ramo.setExpanded(bool(termo) or fam_id == "idles_cenas")

            self._rotulo_contagem.setText(f"{len(filtradas)} ações")
            if self._acao_atual_id is not None:
                item_sel = self._encontrar_item(self._acao_atual_id)
                if item_sel is not None:
                    self._arvore.setCurrentItem(item_sel)
        finally:
            self._bloqueando_sinais = False

    def _formatar_texto_item(self, acao: AcaoCatalogo, *, mostrar_fam: bool) -> str:
        prefixo = "• " if acao.id in self._ids_sujos else ""
        if mostrar_fam:
            return f"{prefixo}{acao.nome}  [{acao.familia_nome}]"
        return f"{prefixo}{acao.nome}"

    def _atualizar_rotulos_sujos(self) -> None:
        mostrar_fam = bool(self._campo_busca.text().strip())
        for i in range(self._arvore.topLevelItemCount()):
            ramo = self._arvore.topLevelItem(i)
            if ramo is None:
                continue
            for j in range(ramo.childCount()):
                filho = ramo.child(j)
                if filho is None:
                    continue
                acao_id = filho.data(0, _ROLE_ACAO_ID)
                acao = self._por_id.get(str(acao_id))
                if acao is not None:
                    filho.setText(
                        0,
                        self._formatar_texto_item(acao, mostrar_fam=mostrar_fam),
                    )

    def _encontrar_item(self, acao_id: str) -> QTreeWidgetItem | None:
        for i in range(self._arvore.topLevelItemCount()):
            ramo = self._arvore.topLevelItem(i)
            if ramo is None:
                continue
            for j in range(ramo.childCount()):
                filho = ramo.child(j)
                if filho is not None and filho.data(0, _ROLE_ACAO_ID) == acao_id:
                    return filho
        return None

    def _sincronizar_combo_variante(
        self,
        acao: AcaoCatalogo | None,
        variante: str | None,
    ) -> None:
        self._combo_variante.clear()
        self._combo_variante.addItem("Padrão", None)
        if acao is not None:
            for var in acao.variantes:
                self._combo_variante.addItem(var, var)
        indice = 0
        if variante is not None:
            pos = self._combo_variante.findData(variante)
            if pos >= 0:
                indice = pos
        self._combo_variante.setCurrentIndex(indice)
        self._combo_variante.setEnabled(
            acao is not None and len(acao.variantes) > 0,
        )

    def _on_item_atual_mudou(
        self,
        atual: QTreeWidgetItem | None,
        _anterior: QTreeWidgetItem | None,
    ) -> None:
        if self._bloqueando_sinais or atual is None:
            return
        acao_id = atual.data(0, _ROLE_ACAO_ID)
        if not acao_id:
            return
        self._emitir_escolha(str(acao_id), None)

    def _on_item_ativado(self, item: QTreeWidgetItem | None, _col: int) -> None:
        if self._bloqueando_sinais or item is None:
            return
        acao_id = item.data(0, _ROLE_ACAO_ID)
        if not acao_id:
            return
        self._emitir_escolha(str(acao_id), None)

    def _on_variante_mudou(self, indice: int) -> None:
        if self._bloqueando_sinais or self._acao_atual_id is None:
            return
        variante = self._combo_variante.itemData(indice)
        self._emitir_escolha(self._acao_atual_id, variante)

    def _emitir_escolha(self, acao_id: str, variante: str | None) -> None:
        acao = self._por_id.get(acao_id)
        self._sincronizar_combo_variante(acao, variante)
        self.acao_solicitada.emit(acao_id, variante)
