"""Painel direito de inspetor: árvore do rig, juntas locais e editores por família."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sejoga.editor.catalogo import AcaoCatalogo
from sejoga.editor.esquema import CURVAS_SUPORTADAS, LIMITES_DURACAO, LIMITES_JUNTA
from sejoga.editor.painel_inspetor_familias import (
    PainelEstimulosRapidos,
    PainelFormularioDict,
    PainelFraseDanca,
    PainelObstaculoTentaculos,
)
from sejoga.editor.roteiro import RoteiroEnsaio
from sejoga.editor.widgets_campos import SpinPreciso, criar_spin_de_limite
from sejoga.nucleo.esqueleto import ALL_GROUPS

ROTULOS_JUNTAS: dict[str, str] = {
    "head": "Cabeça",
    "fones": "Fones",
    "fone-direito": "Fone direito",
    "fone-esquerdo": "Fone esquerdo",
    "antena-direita": "Antena direita",
    "antena-esquerda": "Antena esquerda",
    "body": "Corpo (raiz)",
    "cintura": "Cintura",
    "abdomen": "Abdômen",
    "peitoral": "Peitoral",
    "door": "Porta",
    "shoulder": "Clavícula direita",
    "right-arm": "Ombro direito",
    "ant-arm": "Antebraço direito",
    "hand": "Mão direita",
    "fingers": "Dedos direitos",
    "shoulder2": "Clavícula esquerda",
    "left-arm": "Ombro esquerdo",
    "ant-arm2": "Antebraço esquerdo",
    "hand2": "Mão esquerda",
    "fingers2": "Dedos esquerdos",
    "legs": "Pernas",
    "coxa-direita": "Coxa direita",
    "joelho-direito": "Joelho direito",
    "canela-direita": "Canela direita",
    "right-feet": "Pé direito",
    "coxa-esquerda": "Coxa esquerda",
    "joelho-esquerdo": "Joelho esquerdo",
    "canela-esquerda": "Canela esquerda",
    "left-feet": "Pé esquerdo",
}


def nome_amigavel_junta(grupo: str) -> str:
    """Retorna rótulo legível para um grupo anatômico mantendo o ID técnico."""
    base = grupo.split(":", 1)[0]
    rotulo = ROTULOS_JUNTAS.get(base, base)
    if ":" in grupo:
        sufixo = grupo.split(":", 1)[1]
        return f"{rotulo} ({sufixo})"
    if rotulo != grupo:
        return f"{rotulo} ({grupo})"
    return grupo


class PainelInspetor(QWidget):
    """Inspetor contextual à direita para juntas, curvas, efeitos e parâmetros."""

    junta_selecionada = Signal(str)
    rotacao_junta_editada = Signal(str, tuple)
    chave_alternada = Signal(str, tuple)
    junta_redefinida = Signal(str)
    curva_alterada = Signal(str)
    duracao_solicitada = Signal(float)
    campo_editado = Signal(str, object, object)
    janela_efeito_editada = Signal(str, float, float)
    obstaculo_alterado = Signal(object)
    estimulo_disparado = Signal(object)
    estimulo_adicionado = Signal(object)
    roteiro_limpo = Signal()
    modo_sono_alterado = Signal(str)
    alvo_mover_solicitado = Signal(str)

    @property
    def efeito_selecionado(self) -> str | None:
        """Nome do efeito VFX selecionado atualmente na cena."""
        return self._efeito_selecionado

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa cabeçalho, árvore do rig e seções roláveis do inspetor."""
        super().__init__(parent)
        self.setObjectName("painelInspetor")
        self.setAccessibleName("Inspetor de propriedades")
        self.setMinimumWidth(290)

        self._acao: AcaoCatalogo | None = None
        self._variante: str | None = None
        self._rascunho: dict[str, Any] = {}
        self._grupo_atual: str = "right-arm"
        self._efeito_selecionado: str | None = None
        self._chaves_selecionadas: list[tuple[str, float]] = []
        self._bloqueando = False
        self._construir_layout()

    def _construir_layout(self) -> None:
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(8, 8, 8, 8)
        raiz.setSpacing(6)

        self._titulo = QLabel("Ombro direito", self)
        fonte = self._titulo.font()
        fonte.setBold(True)
        fonte.setPointSize(max(11, fonte.pointSize() + 1))
        self._titulo.setFont(fonte)
        self._subtitulo = QLabel("Rotação local", self)
        self._subtitulo.setObjectName("rotuloSuave")
        raiz.addWidget(self._titulo)
        raiz.addWidget(self._subtitulo)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        conteudo = QWidget(scroll)
        self._vbox = QVBoxLayout(conteudo)
        self._vbox.setContentsMargins(2, 2, 2, 2)
        self._vbox.setSpacing(8)
        self._montar_blocos(conteudo)
        self._vbox.addStretch(1)
        scroll.setWidget(conteudo)
        raiz.addWidget(scroll, 1)

    def _montar_blocos(self, pai: QWidget) -> None:
        self._grupo_arvore = self._criar_grupo_arvore(pai)
        self._grupo_junta = self._criar_grupo_junta(pai)
        self._grupo_cena = self._criar_grupo_cena(pai)
        self._grupo_efeito_cena = self._criar_grupo_efeito_cena(pai)
        self._painel_dict = PainelFormularioDict(pai)
        self._painel_dict.campo_editado.connect(self.campo_editado.emit)
        self._painel_saida_tent = PainelFormularioDict(pai)
        self._painel_saida_tent.campo_editado.connect(self.campo_editado.emit)
        self._painel_frase = PainelFraseDanca(pai)
        self._painel_frase.campo_editado.connect(self.campo_editado.emit)
        self._painel_obstaculo = PainelObstaculoTentaculos(pai)
        self._painel_obstaculo.obstaculo_alterado.connect(self.obstaculo_alterado.emit)
        self._painel_estimulos = PainelEstimulosRapidos(pai)
        self._conectar_estimulos()
        for w in (
            self._grupo_arvore,
            self._grupo_junta,
            self._grupo_cena,
            self._grupo_efeito_cena,
            self._painel_dict,
            self._painel_saida_tent,
            self._painel_frase,
            self._painel_obstaculo,
            self._painel_estimulos,
        ):
            self._vbox.addWidget(w)

    def _conectar_estimulos(self) -> None:
        self._painel_estimulos.estimulo_disparado.connect(self.estimulo_disparado.emit)
        self._painel_estimulos.estimulo_adicionado.connect(
            self.estimulo_adicionado.emit,
        )
        self._painel_estimulos.roteiro_limpo.connect(self.roteiro_limpo.emit)
        self._painel_estimulos.modo_sono_alterado.connect(
            self.modo_sono_alterado.emit,
        )

    def _criar_grupo_arvore(self, pai: QWidget) -> QGroupBox:
        grupo = QGroupBox("Árvore do rig", pai)
        vbox = QVBoxLayout(grupo)
        self._arvore_rig = QTreeWidget(grupo)
        self._arvore_rig.setHeaderHidden(True)
        self._arvore_rig.setFixedHeight(135)
        self._arvore_rig.setAccessibleName("Árvore anatômica do rig")
        for g in ALL_GROUPS:
            item = QTreeWidgetItem([nome_amigavel_junta(g)])
            item.setData(0, Qt.ItemDataRole.UserRole, g)
            self._arvore_rig.addTopLevelItem(item)
        self._arvore_rig.currentItemChanged.connect(self._on_arvore_rig_mudou)
        vbox.addWidget(self._arvore_rig)
        return grupo

    def _criar_grupo_junta(self, pai: QWidget) -> QGroupBox:
        grupo = QGroupBox("Rotação local", pai)
        vbox = QVBoxLayout(grupo)
        self._aviso_multi = QLabel(
            "Seleção múltipla: edições alteram apenas os campos compartilhados.",
            grupo,
        )
        self._aviso_multi.setWordWrap(True)
        self._aviso_multi.setObjectName("rotuloSuave")
        self._aviso_multi.hide()
        vbox.addWidget(self._aviso_multi)
        vbox.addLayout(self._criar_grade_eixos(grupo))

        linha_curva = QHBoxLayout()
        linha_curva.addWidget(QLabel("Curva", grupo))
        self._combo_curva = QComboBox(grupo)
        self._combo_curva.addItems(list(CURVAS_SUPORTADAS))
        self._combo_curva.currentTextChanged.connect(self._on_curva_combo_mudou)
        linha_curva.addWidget(self._combo_curva, 1)
        vbox.addLayout(linha_curva)
        return grupo

    def _criar_grade_eixos(self, grupo: QWidget) -> QGridLayout:
        grade = QGridLayout()
        self._spins_eixos: list[SpinPreciso] = []
        self._btns_chave: list[QToolButton] = []
        for row, eixo in enumerate(("X", "Y", "Z")):
            sp = criar_spin_de_limite(LIMITES_JUNTA, grupo)
            sp.valor_confirmado.connect(lambda _v: self._on_rotacao_digitada())
            btn_k = self._criar_botao_chave(grupo)
            btn_r = self._criar_botao_redefinir(grupo, row)
            grade.addWidget(QLabel(eixo, grupo), row, 0)
            grade.addWidget(sp, row, 1)
            grade.addWidget(btn_k, row, 2)
            grade.addWidget(btn_r, row, 3)
            self._spins_eixos.append(sp)
            self._btns_chave.append(btn_k)
        grade.setColumnStretch(1, 1)
        return grade

    def _criar_botao_chave(self, pai: QWidget) -> QToolButton:
        btn = QToolButton(pai)
        btn.setText("◇")
        btn.setToolTip("Inserir ou remover chave no instante atual (I)")
        btn.setAccessibleName("Alternar chave da junta")
        btn.clicked.connect(self._on_alternar_chave)
        return btn

    def _criar_botao_redefinir(self, pai: QWidget, eixo_idx: int) -> QToolButton:
        btn = QToolButton(pai)
        btn.setText("↺")
        btn.setToolTip("Redefinir eixo para zero")
        btn.clicked.connect(lambda: self._on_redefinir_eixo(eixo_idx))
        return btn

    def _criar_grupo_cena(self, pai: QWidget) -> QGroupBox:
        grupo = QGroupBox("Parâmetros da tomada", pai)
        grade = QGridLayout(grupo)
        grade.setColumnStretch(1, 1)
        self._spin_duracao = criar_spin_de_limite(LIMITES_DURACAO, grupo)
        self._spin_duracao.valor_confirmado.connect(self._on_duracao_confirmada)
        self._chk_loop = QCheckBox("Loop", grupo)
        self._chk_loop.toggled.connect(self._on_loop_toggled)
        self._spin_blend_in = SpinPreciso(
            grupo,
            minimo=0.0,
            maximo=10.0,
            passo=0.02,
            casas=3,
            unidade=" s",
        )
        self._spin_blend_in.valor_confirmado.connect(
            lambda v: self._emitir_pista_campo("blend_entrada_s", v),
        )
        self._spin_blend_out = SpinPreciso(
            grupo,
            minimo=0.0,
            maximo=10.0,
            passo=0.02,
            casas=3,
            unidade=" s",
        )
        self._spin_blend_out.valor_confirmado.connect(
            lambda v: self._emitir_pista_campo("blend_saida_s", v),
        )
        self._spin_desloc_z = SpinPreciso(
            grupo,
            minimo=-5.0,
            maximo=5.0,
            passo=0.01,
            casas=3,
            unidade=" m",
        )
        self._spin_desloc_z.valor_confirmado.connect(
            lambda v: self._emitir_pista_campo("deslocamento_z", v),
        )
        grade.addWidget(QLabel("Duração", grupo), 0, 0)
        grade.addWidget(self._spin_duracao, 0, 1)
        grade.addWidget(QLabel("Repetição", grupo), 1, 0)
        grade.addWidget(self._chk_loop, 1, 1)
        grade.addWidget(QLabel("Blend entrada", grupo), 2, 0)
        grade.addWidget(self._spin_blend_in, 2, 1)
        grade.addWidget(QLabel("Blend saída", grupo), 3, 0)
        grade.addWidget(self._spin_blend_out, 3, 1)
        grade.addWidget(QLabel("Desloc. Z", grupo), 4, 0)
        grade.addWidget(self._spin_desloc_z, 4, 1)
        self._spins_desloc_corpo = self._criar_linha_desloc_corpo(grupo, grade, 5)
        return grupo

    def _criar_linha_desloc_corpo(
        self,
        grupo: QGroupBox,
        grade: QGridLayout,
        linha: int,
    ) -> list[SpinPreciso]:
        cont = QWidget(grupo)
        box = QHBoxLayout(cont)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        spins: list[SpinPreciso] = []
        for idx, eixo in enumerate(("X", "Y", "Z")):
            sp = SpinPreciso(cont, minimo=-10.0, maximo=10.0, passo=0.02, casas=3)
            sp.setButtonSymbols(SpinPreciso.ButtonSymbols.NoButtons)
            sp.setAccessibleName(f"Deslocamento do corpo eixo {eixo}")
            sp.setToolTip(f"Deslocamento do corpo {eixo} (m)")
            sp.valor_confirmado.connect(lambda _v, _i=idx: self._on_desloc_corpo_editado())
            box.addWidget(sp, 1)
            spins.append(sp)
        btn_corpo = QToolButton(cont)
        btn_corpo.setText("3D")
        btn_corpo.setToolTip("Mover o corpo inteiro no viewport 3D")
        btn_corpo.setAccessibleName("Mover corpo inteiro no 3D")
        btn_corpo.clicked.connect(lambda: self.alvo_mover_solicitado.emit("corpo"))
        box.addWidget(btn_corpo)
        self._btn_mover_corpo_linha = btn_corpo
        grade.addWidget(QLabel("Corpo XYZ", grupo), linha, 0)
        grade.addWidget(cont, linha, 1)
        return spins

    def _on_desloc_corpo_editado(self) -> None:
        if self._bloqueando:
            return
        trio = tuple(round(float(sp.value()), 4) for sp in self._spins_desloc_corpo)
        self._emitir_pista_campo("deslocamento_corpo", trio)

    def _criar_grupo_efeito_cena(self, pai: QWidget) -> QGroupBox:
        grupo = QGroupBox("Janela de efeito na cena", pai)
        grid = QGridLayout(grupo)
        grid.setColumnStretch(1, 1)
        self._combo_efeito_cena = QComboBox(grupo)
        self._combo_efeito_cena.currentTextChanged.connect(
            self._on_combo_efeito_cena_mudou,
        )
        self._spin_ef_ini = SpinPreciso(
            grupo,
            minimo=0.0,
            maximo=120.0,
            passo=0.02,
            casas=3,
            unidade=" s",
        )
        self._spin_ef_ini.valor_confirmado.connect(lambda _v: self._on_efeito_janela())
        self._spin_ef_fim = SpinPreciso(
            grupo,
            minimo=0.0,
            maximo=120.0,
            passo=0.02,
            casas=3,
            unidade=" s",
        )
        self._spin_ef_fim.valor_confirmado.connect(lambda _v: self._on_efeito_janela())
        grid.addWidget(QLabel("Efeito", grupo), 0, 0)
        grid.addWidget(self._combo_efeito_cena, 0, 1)
        grid.addWidget(QLabel("Início", grupo), 1, 0)
        grid.addWidget(self._spin_ef_ini, 1, 1)
        grid.addWidget(QLabel("Fim", grupo), 2, 0)
        grid.addWidget(self._spin_ef_fim, 2, 1)
        row_mover = QHBoxLayout()
        row_mover.setSpacing(4)
        btn_mv_ef = QPushButton("Mover efeito no 3D", grupo)
        btn_mv_ef.clicked.connect(lambda: self.alvo_mover_solicitado.emit("vfx"))
        btn_mv_corpo = QPushButton("Mover corpo", grupo)
        btn_mv_corpo.clicked.connect(lambda: self.alvo_mover_solicitado.emit("corpo"))
        row_mover.addWidget(btn_mv_ef, 1)
        row_mover.addWidget(btn_mv_corpo)
        grid.addLayout(row_mover, 3, 0, 1, 2)
        return grupo

    def carregar_contexto(
        self,
        acao: AcaoCatalogo | None,
        rascunho: dict[str, Any],
        *,
        variante: str | None = None,
        roteiro: RoteiroEnsaio | None = None,
        tempo_s: float = 0.0,
    ) -> None:
        """Atualiza os editores visíveis para a ação e os dados atuais."""
        self._acao = acao
        self._variante = variante
        self._rascunho = rascunho
        self._bloqueando = True
        try:
            self._atualizar_visibilidade_modos(acao, rascunho, roteiro, tempo_s)
        finally:
            self._bloqueando = False

    def _atualizar_visibilidade_modos(
        self,
        acao: AcaoCatalogo | None,
        rascunho: dict[str, Any],
        roteiro: RoteiroEnsaio | None,
        tempo_s: float,
    ) -> None:
        eh_pistas = acao is not None and acao.tipo_editor == "pistas_3d"
        self._grupo_arvore.setVisible(eh_pistas)
        self._grupo_junta.setVisible(eh_pistas)
        self._grupo_cena.setVisible(eh_pistas)
        self._grupo_efeito_cena.setVisible(False)
        self._painel_dict.setVisible(False)
        self._painel_saida_tent.setVisible(False)
        self._painel_frase.setVisible(False)
        self._painel_obstaculo.setVisible(False)
        self._painel_estimulos.setVisible(False)
        if acao is None:
            self._titulo.setText("Nenhuma ação")
            self._subtitulo.setText("Selecione um item no catálogo")
            return
        if eh_pistas:
            self._preencher_pistas_3d(acao, rascunho)
        else:
            self._preencher_familia_nao_3d(acao, rascunho, roteiro, tempo_s)

    def _preencher_pistas_3d(
        self,
        acao: AcaoCatalogo,
        rascunho: dict[str, Any],
    ) -> None:
        bloco = self._bloco_pistas(acao, rascunho)
        self._titulo.setText(nome_amigavel_junta(self._grupo_atual))
        self._subtitulo.setText(f"{acao.nome} • Rotação local")
        self._spin_duracao.definir_valor_silencioso(float(bloco.get("duration", 4.0)))
        self._chk_loop.setChecked(bool(bloco.get("loop", False)))
        self._spin_blend_in.definir_valor_silencioso(
            float(bloco.get("blend_entrada_s", 0.35)),
        )
        self._spin_blend_out.definir_valor_silencioso(
            float(bloco.get("blend_saida_s", 0.35)),
        )
        tem_dz = "deslocamento_z" in bloco
        self._spin_desloc_z.setEnabled(tem_dz)
        if tem_dz:
            self._spin_desloc_z.definir_valor_silencioso(
                float(bloco.get("deslocamento_z", 0.0)),
            )
        suporta_corpo = acao.secao_dados in ("IDLE_CLIPS", "CENAS_IDLE")
        bruto_corpo = bloco.get("deslocamento_corpo", (0.0, 0.0, 0.0))
        trio_corpo = (
            (float(bruto_corpo[0]), float(bruto_corpo[1]), float(bruto_corpo[2]))
            if isinstance(bruto_corpo, (tuple, list)) and len(bruto_corpo) == 3
            else (0.0, 0.0, 0.0)
        )
        for sp, val in zip(self._spins_desloc_corpo, trio_corpo, strict=True):
            sp.setEnabled(suporta_corpo)
            sp.definir_valor_silencioso(val if suporta_corpo else 0.0)
        self._btn_mover_corpo_linha.setEnabled(suporta_corpo)
        janelas = bloco.get("janelas_efeito", {})
        if isinstance(janelas, dict) and janelas:
            self._atualizar_janelas_efeito_cena(janelas, rascunho)

    def _atualizar_janelas_efeito_cena(
        self,
        janelas: dict[str, tuple[float, float]],
        rascunho: dict[str, Any],
    ) -> None:
        self._grupo_efeito_cena.setVisible(True)
        self._combo_efeito_cena.clear()
        for nome in sorted(janelas.keys()):
            self._combo_efeito_cena.addItem(nome, nome)
        escolhido = (
            self._efeito_selecionado
            if self._efeito_selecionado in janelas
            else next(iter(janelas.keys()))
        )
        self._efeito_selecionado = escolhido
        self._combo_efeito_cena.setCurrentText(escolhido)
        ini, fim = janelas[escolhido]
        self._spin_ef_ini.definir_valor_silencioso(float(ini))
        self._spin_ef_fim.definir_valor_silencioso(float(fim))
        vfx_dict = rascunho.get("VFX", {}).get(escolhido)
        if isinstance(vfx_dict, dict):
            self._painel_dict.setVisible(True)
            self._painel_dict.carregar_dicionario(
                f"Propriedades do VFX: {escolhido}",
                vfx_dict,
                ("VFX", escolhido),
            )

    def _preencher_familia_nao_3d(
        self,
        acao: AcaoCatalogo,
        rascunho: dict[str, Any],
        roteiro: RoteiroEnsaio | None,
        tempo_s: float,
    ) -> None:
        self._titulo.setText(acao.nome)
        self._subtitulo.setText(acao.familia_nome)
        caminho = self._resolver_caminho_dados(acao)
        alvo = self._resolver_subdicionario(rascunho, caminho)
        if acao.tipo_editor == "danca_frase" and isinstance(alvo, dict):
            self._painel_frase.setVisible(True)
            chave_frase = acao.chave_dados.split(":", 1)[1]
            self._painel_frase.carregar_frase(chave_frase, alvo)
        elif isinstance(alvo, dict):
            self._painel_dict.setVisible(True)
            self._painel_dict.carregar_dicionario(acao.nome, alvo, caminho)
        elif isinstance(alvo, (int, float)):
            self._painel_dict.setVisible(True)
            self._painel_dict.carregar_dicionario(
                acao.nome,
                {caminho[-1]: float(alvo)},
                caminho[:-1],
            )
        self._mostrar_auxiliares_familia(acao, rascunho, roteiro, tempo_s)

    def _mostrar_auxiliares_familia(
        self,
        acao: AcaoCatalogo,
        rascunho: dict[str, Any],
        roteiro: RoteiroEnsaio | None,
        tempo_s: float,
    ) -> None:
        if acao.tipo_editor == "tentaculos_pers":
            pers = acao.chave_dados.split(":", 1)[1]
            saida = rascunho.get("TENTACULOS", {}).get("saidas", {}).get(pers)
            if isinstance(saida, dict):
                self._painel_saida_tent.setVisible(True)
                self._painel_saida_tent.carregar_dicionario(
                    f"Saída dos tentáculos ({pers})",
                    saida,
                    ("TENTACULOS", "saidas", pers),
                )
        if acao.secao_dados == "TENTACULOS":
            self._painel_obstaculo.setVisible(True)
            if roteiro is not None:
                self._painel_obstaculo.definir_obstaculo(roteiro.obstaculo)
        if acao.secao_dados == "REACOES":
            self._painel_estimulos.setVisible(True)
            if roteiro is not None:
                self._painel_estimulos.sincronizar_roteiro(roteiro, tempo_s)

    def atualizar_junta_e_chaves(
        self,
        grupo: str,
        rotacao_graus: tuple[float, float, float],
        *,
        tem_chave_no_tempo: bool,
        curva_atual: str = "quintic",
        chaves_selecionadas: list[tuple[str, float]] | None = None,
    ) -> None:
        """Sincroniza eixos X/Y/Z, marcador de chave e árvore do rig para a junta."""
        self._grupo_atual = grupo
        self._chaves_selecionadas = list(chaves_selecionadas or [])
        multi = len(self._chaves_selecionadas) > 1
        self._bloqueando = True
        try:
            self._aviso_multi.setVisible(multi)
            self._marcar_grupo_na_arvore(grupo)
            for idx, (sp, val) in enumerate(
                zip(self._spins_eixos, rotacao_graus, strict=True),
            ):
                sp.definir_valor_silencioso(float(val), indeterminado=multi)
                self._btns_chave[idx].setText("◆" if tem_chave_no_tempo else "◇")
                self._btns_chave[idx].setChecked(tem_chave_no_tempo)
            if curva_atual in CURVAS_SUPORTADAS:
                self._combo_curva.setCurrentText(curva_atual)
            if self._acao is not None and self._acao.tipo_editor == "pistas_3d":
                self._titulo.setText(
                    f"{len(self._chaves_selecionadas)} chaves selecionadas"
                    if multi
                    else nome_amigavel_junta(grupo),
                )
        finally:
            self._bloqueando = False

    def selecionar_efeito_cena(self, nome_efeito: str) -> None:
        """Seleciona uma faixa de efeito da cena no inspetor sem perder o bloco."""
        self._efeito_selecionado = nome_efeito
        if self._acao is not None and self._acao.tipo_editor == "pistas_3d":
            self.carregar_contexto(
                self._acao,
                self._rascunho,
                variante=self._variante,
            )
            self._titulo.setText(f"Efeito: {nome_efeito}")

    def _marcar_grupo_na_arvore(self, grupo: str) -> None:
        base = grupo.split(":", 1)[0]
        for i in range(self._arvore_rig.topLevelItemCount()):
            item = self._arvore_rig.topLevelItem(i)
            if item is not None and item.data(0, Qt.ItemDataRole.UserRole) == base:
                self._arvore_rig.setCurrentItem(item)
                return

    def _bloco_pistas(
        self,
        acao: AcaoCatalogo,
        rascunho: dict[str, Any],
    ) -> dict[str, Any]:
        bloco: dict[str, Any] = rascunho.get(acao.secao_dados, {}).get(
            acao.chave_dados,
            {},
        )
        if self._variante and isinstance(bloco.get("variantes"), dict):
            sub = bloco["variantes"].get(self._variante)
            if isinstance(sub, dict):
                return sub
        return bloco

    def _resolver_caminho_dados(self, acao: AcaoCatalogo) -> tuple[str, ...]:
        if ":" in acao.chave_dados:
            raiz, resto = acao.chave_dados.split(":", 1)
            return (acao.secao_dados, raiz, resto)
        if acao.secao_dados == "RESPIRACAO" and acao.chave_dados == "ciclo":
            return ("RESPIRACAO",)
        return (acao.secao_dados, acao.chave_dados)

    def _resolver_subdicionario(
        self,
        rascunho: dict[str, Any],
        caminho: tuple[str, ...],
    ) -> Any:
        atual: Any = rascunho
        for parte in caminho:
            if isinstance(atual, dict) and parte in atual:
                atual = atual[parte]
            else:
                return {}
        return atual

    def _emitir_pista_campo(self, campo: str, valor: Any) -> None:
        if self._bloqueando or self._acao is None:
            return
        caminho: list[Any] = [self._acao.secao_dados, self._acao.chave_dados]
        if self._variante:
            bloco = self._rascunho.get(self._acao.secao_dados, {}).get(
                self._acao.chave_dados,
                {},
            )
            if (
                isinstance(bloco, dict)
                and isinstance(bloco.get("variantes"), dict)
                and self._variante in bloco["variantes"]
            ):
                caminho.extend(["variantes", self._variante])
        caminho.append(campo)
        self.campo_editado.emit(f"Alterar {campo}", tuple(caminho), valor)

    def _on_arvore_rig_mudou(
        self,
        atual: QTreeWidgetItem | None,
        _anterior: QTreeWidgetItem | None,
    ) -> None:
        if self._bloqueando or atual is None:
            return
        grupo = str(atual.data(0, Qt.ItemDataRole.UserRole))
        self.junta_selecionada.emit(grupo)

    def _on_rotacao_digitada(self) -> None:
        if self._bloqueando:
            return
        rot = (
            float(self._spins_eixos[0].value()),
            float(self._spins_eixos[1].value()),
            float(self._spins_eixos[2].value()),
        )
        self.rotacao_junta_editada.emit(self._grupo_atual, rot)

    def _on_alternar_chave(self) -> None:
        if self._bloqueando:
            return
        rot = (
            float(self._spins_eixos[0].value()),
            float(self._spins_eixos[1].value()),
            float(self._spins_eixos[2].value()),
        )
        self.chave_alternada.emit(self._grupo_atual, rot)

    def _on_redefinir_eixo(self, eixo_idx: int) -> None:
        if self._bloqueando:
            return
        vals = [float(sp.value()) for sp in self._spins_eixos]
        vals[eixo_idx] = 0.0
        self.rotacao_junta_editada.emit(
            self._grupo_atual,
            (vals[0], vals[1], vals[2]),
        )

    def _on_curva_combo_mudou(self, curva: str) -> None:
        if not self._bloqueando:
            self.curva_alterada.emit(curva)

    def _on_duracao_confirmada(self, valor: float) -> None:
        if not self._bloqueando:
            self.duracao_solicitada.emit(float(valor))

    def _on_loop_toggled(self, ativo: bool) -> None:
        self._emitir_pista_campo("loop", bool(ativo))

    def _on_combo_efeito_cena_mudou(self, nome: str) -> None:
        if not self._bloqueando and nome:
            self.selecionar_efeito_cena(nome)

    def _on_efeito_janela(self) -> None:
        if self._bloqueando or not self._efeito_selecionado:
            return
        ini = float(self._spin_ef_ini.value())
        fim = max(ini + 0.05, float(self._spin_ef_fim.value()))
        self._spin_ef_fim.definir_valor_silencioso(fim)
        self.janela_efeito_editada.emit(self._efeito_selecionado, ini, fim)
