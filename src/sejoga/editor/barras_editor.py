"""Barras superior, de câmera do viewport e banners de feedback do editor."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from sejoga.editor.sessao_previa import ModoPrevia
from sejoga.editor.viewport_panda import EstadoOverlays, ModoCamera, ModoFerramenta


class BarraSuperiorEditor(QFrame):
    """Barra fixa no topo (~48 px): tomada, desfazer/refazer, modo e Salvar."""

    desfazer_solicitado = Signal()
    refazer_solicitado = Signal()
    modo_alterado = Signal(object)
    salvar_solicitado = Signal()
    alternar_catalogo = Signal(bool)
    alternar_inspetor = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa os botões de histórico, modo de prévia e botão Salvar."""
        super().__init__(parent)
        self.setObjectName("barraSuperior")
        self.setFixedHeight(48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)
        self._adicionar_titulo_e_paineis(layout)
        self._adicionar_historico(layout)
        layout.addStretch(1)
        self._adicionar_modo_e_salvar(layout)

    def _adicionar_titulo_e_paineis(self, layout: QHBoxLayout) -> None:
        self._btn_cat = QToolButton(self)
        self._btn_cat.setText("Catálogo")
        self._btn_cat.setCheckable(True)
        self._btn_cat.setChecked(True)
        self._btn_cat.setToolTip("Mostrar ou recolher catálogo (F2)")
        self._btn_cat.setAccessibleName("Alternar painel catálogo")
        self._btn_cat.toggled.connect(self.alternar_catalogo.emit)

        self._lbl_acao = QLabel("Editor do Mário", self)
        fonte = self._lbl_acao.font()
        fonte.setBold(True)
        fonte.setPointSize(max(11, fonte.pointSize() + 1))
        self._lbl_acao.setFont(fonte)

        self._badge_alterado = QLabel("•", self)
        self._badge_alterado.setObjectName("badgeAlterado")
        self._badge_alterado.setAccessibleName("Alterações não salvas")
        self._badge_alterado.setToolTip("Há alterações não salvas no rascunho")
        self._badge_alterado.setVisible(False)

        layout.addWidget(self._btn_cat)
        layout.addWidget(self._lbl_acao)
        layout.addWidget(self._badge_alterado)

    def _adicionar_historico(self, layout: QHBoxLayout) -> None:
        self._btn_desfazer = QPushButton("Desfazer", self)
        self._btn_desfazer.setToolTip("Desfazer última operação (Ctrl+Z)")
        self._btn_desfazer.setAccessibleName("Desfazer")
        self._btn_desfazer.setEnabled(False)
        self._btn_desfazer.clicked.connect(self.desfazer_solicitado.emit)

        self._btn_refazer = QPushButton("Refazer", self)
        self._btn_refazer.setToolTip("Refazer operação desfeita (Ctrl+Shift+Z)")
        self._btn_refazer.setAccessibleName("Refazer")
        self._btn_refazer.setEnabled(False)
        self._btn_refazer.clicked.connect(self.refazer_solicitado.emit)

        layout.addSpacing(8)
        layout.addWidget(self._btn_desfazer)
        layout.addWidget(self._btn_refazer)

    def _adicionar_modo_e_salvar(self, layout: QHBoxLayout) -> None:
        self._btn_tomada = QToolButton(self)
        self._btn_tomada.setText("Tomada")
        self._btn_tomada.setCheckable(True)
        self._btn_tomada.setChecked(True)
        self._btn_tomada.setAccessibleName("Modo tomada isolada")
        self._btn_tomada.clicked.connect(
            lambda: self._definir_modo_clique(ModoPrevia.TOMADA),
        )

        self._btn_contexto = QToolButton(self)
        self._btn_contexto.setText("Em contexto")
        self._btn_contexto.setCheckable(True)
        self._btn_contexto.setAccessibleName("Modo em contexto do companion")
        self._btn_contexto.clicked.connect(
            lambda: self._definir_modo_clique(ModoPrevia.EM_CONTEXTO),
        )

        self._lbl_prioridade = QLabel("Prioridade: isolada", self)
        self._lbl_prioridade.setObjectName("badgePrioridade")

        self._btn_insp = QToolButton(self)
        self._btn_insp.setText("Inspetor")
        self._btn_insp.setCheckable(True)
        self._btn_insp.setChecked(True)
        self._btn_insp.setToolTip("Mostrar ou recolher inspetor (F3)")
        self._btn_insp.setAccessibleName("Alternar painel inspetor")
        self._btn_insp.toggled.connect(self.alternar_inspetor.emit)

        self._btn_salvar = QPushButton("Salvar", self)
        self._btn_salvar.setObjectName("btnSalvar")
        self._btn_salvar.setToolTip("Gravar alterações validadas no projeto (Ctrl+S)")
        self._btn_salvar.setAccessibleName("Salvar alterações")
        self._btn_salvar.clicked.connect(self.salvar_solicitado.emit)

        for w in (
            self._btn_tomada,
            self._btn_contexto,
            self._lbl_prioridade,
            self._btn_insp,
            self._btn_salvar,
        ):
            layout.addWidget(w)

    def _definir_modo_clique(self, modo: ModoPrevia) -> None:
        self.atualizar_modo(modo, "isolada" if modo == ModoPrevia.TOMADA else "normal")
        self.modo_alterado.emit(modo)

    def atualizar_titulo(
        self,
        nome_acao: str,
        variante: str | None,
        *,
        sujo: bool,
    ) -> None:
        """Atualiza o título da tomada aberta e o marcador acessível de alteração."""
        texto = f"{nome_acao} ({variante})" if variante else nome_acao
        self._lbl_acao.setText(texto)
        self._badge_alterado.setVisible(sujo)

    def atualizar_historico(
        self,
        *,
        pode_desfazer: bool,
        desc_undo: str | None,
        pode_refazer: bool,
        desc_redo: str | None,
    ) -> None:
        """Atualiza habilitação e dicas dos botões Desfazer e Refazer."""
        self._btn_desfazer.setEnabled(pode_desfazer)
        self._btn_desfazer.setToolTip(
            f"Desfazer: {desc_undo} (Ctrl+Z)" if desc_undo else "Desfazer (Ctrl+Z)",
        )
        self._btn_refazer.setEnabled(pode_refazer)
        self._btn_refazer.setToolTip(
            f"Refazer: {desc_redo} (Ctrl+Shift+Z)"
            if desc_redo
            else "Refazer (Ctrl+Shift+Z)",
        )

    def atualizar_modo(self, modo: ModoPrevia, prioridade: str) -> None:
        """Sincroniza alternância Tomada/Em contexto e leitura da prioridade."""
        self._btn_tomada.blockSignals(True)
        self._btn_contexto.blockSignals(True)
        self._btn_tomada.setChecked(modo == ModoPrevia.TOMADA)
        self._btn_contexto.setChecked(modo == ModoPrevia.EM_CONTEXTO)
        self._btn_tomada.blockSignals(False)
        self._btn_contexto.blockSignals(False)
        self._lbl_prioridade.setText(f"Prioridade: {prioridade}")

    def definir_visibilidade_paineis(
        self,
        *,
        catalogo: bool,
        inspetor: bool,
    ) -> None:
        """Mantém os botões de recolhimento em sincronia com os painéis."""
        self._btn_cat.blockSignals(True)
        self._btn_insp.blockSignals(True)
        self._btn_cat.setChecked(catalogo)
        self._btn_insp.setChecked(inspetor)
        self._btn_cat.blockSignals(False)
        self._btn_insp.blockSignals(False)


class BarraCameraViewport(QFrame):
    """Faixa acima do viewport 3D: vistas, ferramentas 3D, enquadrar, overlays e estímulo."""

    camera_alterada = Signal(object)
    enquadrar_solicitado = Signal()
    overlays_alterados = Signal(object)
    estimulo_rapido_solicitado = Signal(str)
    ferramenta_alterada = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa combo de câmeras, botões Girar/Mover, overlays e badge."""
        super().__init__(parent)
        self.setObjectName("barraCamera")
        self._overlays = EstadoOverlays()
        self._acoes_overlay: dict[str, QAction] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        self._adicionar_controles_camera(layout)
        self._adicionar_menu_exibir(layout)
        self._adicionar_controles_ferramenta(layout)
        layout.addStretch(1)
        self._adicionar_teste_contexto_e_badge(layout)

    def _adicionar_controles_camera(self, layout: QHBoxLayout) -> None:
        self._combo_camera = QComboBox(self)
        self._combo_camera.setAccessibleName("Modo de câmera")
        for modo, rot in (
            (ModoCamera.PERSPECTIVA, "Perspectiva"),
            (ModoCamera.FRONTAL, "Frontal"),
            (ModoCamera.LATERAL, "Lateral"),
            (ModoCamera.COMPANION, "Câmera do companion"),
        ):
            self._combo_camera.addItem(rot, modo)
        self._combo_camera.currentIndexChanged.connect(self._on_combo_camera)

        self._btn_enquadrar = QPushButton("Enquadrar", self)
        self._btn_enquadrar.setToolTip("Centralizar câmera no Mário (F)")
        self._btn_enquadrar.clicked.connect(self.enquadrar_solicitado.emit)

        layout.addWidget(self._combo_camera)
        layout.addWidget(self._btn_enquadrar)

    def _adicionar_menu_exibir(self, layout: QHBoxLayout) -> None:
        self._btn_exibir = QToolButton(self)
        self._btn_exibir.setText("Exibir ")
        self._btn_exibir.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_exibir.setAccessibleName("Sobreposições do viewport")
        menu = QMenu(self._btn_exibir)
        opcoes = (
            ("grade", "Grade do chão", self._overlays.grade),
            ("ossos", "Ossos do rig", self._overlays.ossos),
            ("contatos", "Contatos e obstáculo", self._overlays.contatos),
            ("ancoras", "Âncoras de VFX", self._overlays.ancoras),
            ("trilhas", "Trilha de trajetória", self._overlays.trilhas),
            ("comparar_salvo", "Comparar Salvo vs Rascunho", self._overlays.comparar_salvo),
        )
        for campo, texto, inicial in opcoes:
            act = menu.addAction(texto)
            act.setCheckable(True)
            act.setChecked(inicial)
            act.toggled.connect(lambda _v: self._on_overlay_toggled())
            self._acoes_overlay[campo] = act
        self._btn_exibir.setMenu(menu)
        layout.addWidget(self._btn_exibir)

    def _adicionar_controles_ferramenta(self, layout: QHBoxLayout) -> None:
        self._grupo_ferramenta = QButtonGroup(self)
        self._grupo_ferramenta.setExclusive(True)
        self._btn_girar = QPushButton("Girar", self)
        self._btn_girar.setCheckable(True)
        self._btn_girar.setChecked(True)
        self._btn_girar.setToolTip("Ferramenta de rotação local da junta (R)")
        self._btn_mover = QPushButton("Mover", self)
        self._btn_mover.setCheckable(True)
        self._btn_mover.setToolTip("Ferramenta de movimento 3D (G)")
        self._grupo_ferramenta.addButton(self._btn_girar)
        self._grupo_ferramenta.addButton(self._btn_mover)
        self._btn_girar.toggled.connect(self._on_ferramenta_toggled)
        layout.addWidget(self._btn_girar)
        layout.addWidget(self._btn_mover)

    def definir_ferramenta(self, modo: ModoFerramenta) -> None:
        """Seleciona programaticamente ``Girar`` ou ``Mover`` sem reemitir sinal."""
        self._btn_girar.blockSignals(True)
        self._btn_mover.blockSignals(True)
        try:
            self._btn_girar.setChecked(modo == ModoFerramenta.GIRAR)
            self._btn_mover.setChecked(modo == ModoFerramenta.MOVER)
        finally:
            self._btn_girar.blockSignals(False)
            self._btn_mover.blockSignals(False)

    def definir_dica_mover(self, rotulo_alvo: str | None) -> None:
        """Atualiza dica contextual da ferramenta ``Mover`` conforme o alvo ativo."""
        if rotulo_alvo:
            self._btn_mover.setToolTip(
                f"Ferramenta de movimento 3D (G) — Alvo: {rotulo_alvo}"
            )
        else:
            self._btn_mover.setToolTip(
                "Ferramenta de movimento 3D (G) — Indisponível nesta ação"
            )

    def _on_ferramenta_toggled(self, girar_ativo: bool) -> None:
        modo = ModoFerramenta.GIRAR if girar_ativo else ModoFerramenta.MOVER
        self.ferramenta_alterada.emit(modo)

    def _adicionar_teste_contexto_e_badge(self, layout: QHBoxLayout) -> None:
        self._btn_clique = QPushButton("Testar clique", self)
        self._btn_clique.setToolTip(
            "Simula um estímulo de clique do mouse durante a ação no modo Em contexto",
        )
        self._btn_clique.clicked.connect(
            lambda: self.estimulo_rapido_solicitado.emit("click"),
        )
        self._lbl_badge_vista = QLabel("Vista: Perspectiva", self)
        self._lbl_badge_vista.setObjectName("rotuloSuave")
        layout.addWidget(self._btn_clique)
        layout.addWidget(self._lbl_badge_vista)

    def definir_modo_camera(self, modo: ModoCamera) -> None:
        """Seleciona programaticamente o modo de câmera na barra."""
        idx = self._combo_camera.findData(modo)
        if idx >= 0:
            self._combo_camera.setCurrentIndex(idx)
        self._lbl_badge_vista.setText(f"Vista: {self._combo_camera.currentText()}")

    def _on_combo_camera(self, _idx: int) -> None:
        modo = self._combo_camera.currentData()
        if isinstance(modo, ModoCamera):
            self._lbl_badge_vista.setText(f"Vista: {self._combo_camera.currentText()}")
            self.camera_alterada.emit(modo)

    def _on_overlay_toggled(self) -> None:
        self._overlays = EstadoOverlays(
            grade=self._acoes_overlay["grade"].isChecked(),
            ossos=self._acoes_overlay["ossos"].isChecked(),
            contatos=self._acoes_overlay["contatos"].isChecked(),
            ancoras=self._acoes_overlay["ancoras"].isChecked(),
            trilhas=self._acoes_overlay["trilhas"].isChecked(),
            comparar_salvo=self._acoes_overlay["comparar_salvo"].isChecked(),
        )
        self.overlays_alterados.emit(self._overlays)


class BannersEditor(QWidget):
    """Faixa opcional de avisos: confirmação de gravação, pose provisória e erro."""

    gravar_provisoria = Signal()
    descartar_provisoria = Signal()
    recarregar_externa = Signal()
    tentar_salvar_novamente = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa banners ocultos por padrão e temporizador discreto do toast."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)
        self._criar_banner_toast(layout)
        self._criar_banner_provisoria(layout)
        self._criar_banner_erro(layout)
        self._timer_toast = QTimer(self)
        self._timer_toast.setSingleShot(True)
        self._timer_toast.timeout.connect(self._frame_toast.hide)

    def _criar_banner_toast(self, layout: QVBoxLayout) -> None:
        self._frame_toast = QFrame(self)
        self._frame_toast.setObjectName("bannerToast")
        row = QHBoxLayout(self._frame_toast)
        row.setContentsMargins(8, 3, 8, 3)
        self._lbl_toast = QLabel("", self._frame_toast)
        row.addWidget(self._lbl_toast)
        self._frame_toast.hide()
        layout.addWidget(self._frame_toast)

    def _criar_banner_provisoria(self, layout: QVBoxLayout) -> None:
        self._frame_prov = QFrame(self)
        self._frame_prov.setObjectName("bannerProvisoria")
        row = QHBoxLayout(self._frame_prov)
        row.setContentsMargins(8, 3, 8, 3)
        self._lbl_prov = QLabel(
            "Pose ajustada fora de chave — grave uma chave ou descarte.",
            self._frame_prov,
        )
        btn_ok = QPushButton("Gravar chave", self._frame_prov)
        btn_ok.clicked.connect(self.gravar_provisoria.emit)
        btn_desc = QPushButton("Descartar", self._frame_prov)
        btn_desc.clicked.connect(self.descartar_provisoria.emit)
        row.addWidget(self._lbl_prov, 1)
        row.addWidget(btn_ok)
        row.addWidget(btn_desc)
        self._frame_prov.hide()
        layout.addWidget(self._frame_prov)

    def _criar_banner_erro(self, layout: QVBoxLayout) -> None:
        self._frame_erro = QFrame(self)
        self._frame_erro.setObjectName("bannerErro")
        row = QHBoxLayout(self._frame_erro)
        row.setContentsMargins(8, 4, 8, 4)
        self._lbl_erro = QLabel("", self._frame_erro)
        self._lbl_erro.setWordWrap(True)
        self._btn_rec = QPushButton("Recarregar versão externa", self._frame_erro)
        self._btn_rec.clicked.connect(self.recarregar_externa.emit)
        self._btn_retry = QPushButton("Tentar gravar novamente", self._frame_erro)
        self._btn_retry.clicked.connect(self.tentar_salvar_novamente.emit)
        btn_fechar = QToolButton(self._frame_erro)
        btn_fechar.setText("X")
        btn_fechar.setToolTip("Fechar aviso")
        btn_fechar.clicked.connect(self._frame_erro.hide)
        row.addWidget(self._lbl_erro, 1)
        row.addWidget(self._btn_rec)
        row.addWidget(self._btn_retry)
        row.addWidget(btn_fechar)
        self._frame_erro.hide()
        layout.addWidget(self._frame_erro)

    def mostrar_toast(self, mensagem: str, *, duracao_ms: int = 3200) -> None:
        """Exibe confirmação discreta por alguns segundos."""
        self._lbl_toast.setText(mensagem)
        self._frame_toast.show()
        self._timer_toast.start(duracao_ms)

    def definir_provisoria(self, ativa: bool, grupo: str = "") -> None:
        """Exibe ou oculta o lembrete da pose provisória."""
        if ativa:
            self._lbl_prov.setText(
                f"Pose provisória ativa em '{grupo}' fora de chave.",
            )
        self._frame_prov.setVisible(ativa)

    def mostrar_erro(self, mensagem: str, *, permitir_recarregar: bool) -> None:
        """Exibe erro persistente de gravação com ações de recuperação."""
        self._lbl_erro.setText(mensagem)
        self._btn_rec.setVisible(permitir_recarregar)
        self._frame_erro.show()

    def limpar_erro(self) -> None:
        """Oculta o banner de erro após resolução."""
        self._frame_erro.hide()
