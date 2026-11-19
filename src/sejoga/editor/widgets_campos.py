"""Widgets reutilizáveis de entrada numérica, vetores, cores e metadados."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from sejoga.editor.esquema import (
    LIMITES_BLENDS,
    LIMITES_BPM,
    LIMITES_COR_CANAL,
    LIMITES_DURACAO,
    LIMITES_ESCALA_VFX,
    LIMITES_FREQUENCIA,
    LIMITES_JUNTA,
    LIMITES_PESO,
    LimiteCampo,
)


@dataclass(frozen=True)
class MetaCampo:
    """Metadados de exibição e validação de um campo escalar no inspetor."""

    rotulo: str
    minimo: float = -1000.0
    maximo: float = 1000.0
    unidade: str = ""
    passo: float = 0.05
    casas: int = 3


_TABELA_LIMITES: dict[str, MetaCampo] = {
    "duracao_s": MetaCampo(
        "Duração",
        LIMITES_DURACAO.minimo,
        LIMITES_DURACAO.maximo,
        " s",
        LIMITES_DURACAO.passo,
        LIMITES_DURACAO.casas,
    ),
    "duration": MetaCampo(
        "Duração",
        LIMITES_DURACAO.minimo,
        LIMITES_DURACAO.maximo,
        " s",
        LIMITES_DURACAO.passo,
        LIMITES_DURACAO.casas,
    ),
    "inicio_s": MetaCampo("Início", 0.0, 120.0, " s", 0.02, 3),
    "fim_s": MetaCampo("Fim", 0.0, 120.0, " s", 0.02, 3),
    "blend_entrada_s": MetaCampo(
        "Blend entrada",
        LIMITES_BLENDS.minimo,
        LIMITES_BLENDS.maximo,
        " s",
        LIMITES_BLENDS.passo,
        LIMITES_BLENDS.casas,
    ),
    "blend_saida_s": MetaCampo(
        "Blend saída",
        LIMITES_BLENDS.minimo,
        LIMITES_BLENDS.maximo,
        " s",
        LIMITES_BLENDS.passo,
        LIMITES_BLENDS.casas,
    ),
    "peso_entrada": MetaCampo(
        "Peso entrada",
        LIMITES_PESO.minimo,
        LIMITES_PESO.maximo,
        "",
        LIMITES_PESO.passo,
        LIMITES_PESO.casas,
    ),
    "peso_saida": MetaCampo(
        "Peso saída",
        LIMITES_PESO.minimo,
        LIMITES_PESO.maximo,
        "",
        LIMITES_PESO.passo,
        LIMITES_PESO.casas,
    ),
    "peso_mistura": MetaCampo(
        "Peso de mistura",
        LIMITES_PESO.minimo,
        LIMITES_PESO.maximo,
        "",
        LIMITES_PESO.passo,
        LIMITES_PESO.casas,
    ),
    "mistura_base": MetaCampo(
        "Mistura base",
        LIMITES_PESO.minimo,
        LIMITES_PESO.maximo,
        "",
        LIMITES_PESO.passo,
        LIMITES_PESO.casas,
    ),
    "bpm": MetaCampo(
        "BPM",
        LIMITES_BPM.minimo,
        LIMITES_BPM.maximo,
        " BPM",
        LIMITES_BPM.passo,
        1,
    ),
    "tempo_padrao": MetaCampo("Tempo padrão", 30.0, 260.0, " BPM", 1.0, 1),
    "tempo_min": MetaCampo("Tempo mínimo", 30.0, 260.0, " BPM", 1.0, 1),
    "tempo_max": MetaCampo("Tempo máximo", 30.0, 260.0, " BPM", 1.0, 1),
    "frequencia": MetaCampo(
        "Frequência",
        LIMITES_FREQUENCIA.minimo,
        LIMITES_FREQUENCIA.maximo,
        " Hz",
        LIMITES_FREQUENCIA.passo,
        LIMITES_FREQUENCIA.casas,
    ),
    "frequencia_hz": MetaCampo(
        "Frequência",
        LIMITES_FREQUENCIA.minimo,
        LIMITES_FREQUENCIA.maximo,
        " Hz",
        LIMITES_FREQUENCIA.passo,
        LIMITES_FREQUENCIA.casas,
    ),
    "frequencia_padrao": MetaCampo(
        "Frequência padrão",
        LIMITES_FREQUENCIA.minimo,
        LIMITES_FREQUENCIA.maximo,
        " Hz",
        LIMITES_FREQUENCIA.passo,
        LIMITES_FREQUENCIA.casas,
    ),
    "respiracao_hz": MetaCampo("Frequência respiração", 0.05, 5.0, " Hz", 0.02, 2),
    "escala": MetaCampo(
        "Escala",
        LIMITES_ESCALA_VFX.minimo,
        LIMITES_ESCALA_VFX.maximo,
        " x",
        LIMITES_ESCALA_VFX.passo,
        LIMITES_ESCALA_VFX.casas,
    ),
    "escala_min": MetaCampo("Escala mínima", 0.001, 5.0, " x", 0.005, 3),
    "escala_max": MetaCampo("Escala máxima", 0.001, 5.0, " x", 0.005, 3),
    "velocidade": MetaCampo("Velocidade", 0.05, 10.0, " x", 0.05, 2),
    "cooldown_s": MetaCampo("Cooldown", 0.0, 60.0, " s", 0.02, 3),
    "fade_start": MetaCampo("Início do fade", 0.0, 1.0, "", 0.05, 2),
    "drag": MetaCampo("Arrasto", 0.0, 20.0, "", 0.05, 2),
    "gravity": MetaCampo("Gravidade", -100.0, 100.0, "", 0.1, 2),
    "gravidade": MetaCampo("Gravidade", -100.0, 100.0, "", 0.05, 2),
    "pop_amp": MetaCampo("Amplitude pop", 0.0, 5.0, "", 0.02, 2),
    "intensidade": MetaCampo("Intensidade", 0.0, 3.0, "", 0.05, 2),
    "amplitude": MetaCampo("Amplitude", 0.0, 5.0, "", 0.05, 2),
    "assimetria": MetaCampo("Assimetria", 0.05, 0.95, "", 0.025, 3),
    "assimetria_inspiracao": MetaCampo("Assimetria inspiração", 0.05, 0.95, "", 0.025, 3),
    "bounce": MetaCampo("Quique (bounce)", 0.0, 2.0, "", 0.02, 2),
    "deslocamento_z": MetaCampo("Deslocamento Z", -5.0, 5.0, " m", 0.01, 3),
    "atraso_segmento_s": MetaCampo("Atraso por segmento", 0.0, 1.0, " s", 0.005, 3),
    "elevacao_arco": MetaCampo("Elevação do arco", -2.0, 2.0, "", 0.05, 2),
    "avanco_frontal": MetaCampo("Avanço frontal", -2.0, 2.0, "", 0.05, 2),
    "escala_alcance": MetaCampo("Escala de alcance", 0.1, 3.0, " x", 0.05, 2),
    "amplitude_cima_px": MetaCampo("Amplitude vertical", 0.0, 80.0, " px", 0.5, 1),
    "amplitude_lateral_px": MetaCampo("Amplitude lateral", 0.0, 80.0, " px", 0.5, 1),
}


def metadado_campo(chave: str) -> MetaCampo:
    """Deduz rótulo legível, unidade e limites seguros a partir da chave do dado."""
    if chave in _TABELA_LIMITES:
        return _TABELA_LIMITES[chave]
    rotulo = chave.replace("_", " ").capitalize()
    if chave.endswith("_s") or chave.endswith("_duracao"):
        return MetaCampo(rotulo, 0.0, 120.0, " s", 0.02, 3)
    if (
        chave.endswith("_graus")
        or "pitch" in chave
        or "roll" in chave
        or "giro" in chave
        or "cabeca" in chave
        or "ombro" in chave
        or "braco" in chave
        or "antebraco" in chave
        or "dedos" in chave
        or "porta" in chave
        or "arco" in chave
    ):
        return MetaCampo(rotulo, -360.0, 360.0, " °", 0.5, 2)
    if chave.endswith("_px"):
        return MetaCampo(rotulo, -500.0, 500.0, " px", 0.5, 1)
    if chave.endswith("_hz"):
        return MetaCampo(rotulo, 0.01, 20.0, " Hz", 0.02, 3)
    return MetaCampo(rotulo, -1000.0, 1000.0, "", 0.05, 3)


class SpinPreciso(QDoubleSpinBox):
    """Caixa numérica que confirma com Enter, cancela com Esc e suporta multi-valor."""

    valor_confirmado = Signal(float)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        minimo: float = LIMITES_JUNTA.minimo,
        maximo: float = LIMITES_JUNTA.maximo,
        passo: float = LIMITES_JUNTA.passo,
        casas: int = LIMITES_JUNTA.casas,
        unidade: str = "",
    ) -> None:
        """Inicializa o controle numérico com faixa, passo e sufixo configurados."""
        super().__init__(parent)
        self.setRange(minimo, maximo)
        self.setSingleStep(passo)
        self.setDecimals(casas)
        if unidade:
            self.setSuffix(unidade)
        self.setMinimumWidth(52)
        self.setKeyboardTracking(False)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._valor_salvo = 0.0
        self._indeterminado = False
        self._emitindo = False
        self.editingFinished.connect(self._on_edicao_concluida)
        self.installEventFilter(self)

    def definir_valor_silencioso(
        self,
        valor: float,
        *,
        indeterminado: bool = False,
    ) -> None:
        """Atualiza o valor exibido sem disparar ``valor_confirmado``."""
        self.blockSignals(True)
        try:
            self._indeterminado = indeterminado
            if indeterminado:
                self.setSpecialValueText("—")
                self.setValue(self.minimum())
            else:
                self.setSpecialValueText("")
                self.setValue(float(valor))
                self._valor_salvo = float(valor)
        finally:
            self.blockSignals(False)

    def stepBy(self, steps: int) -> None:
        """Dispara confirmação imediata ao usar setas ou roda do mouse."""
        if self._indeterminado:
            self._indeterminado = False
            self.setSpecialValueText("")
            self.setValue(self._valor_salvo)
        super().stepBy(steps)
        novo = float(self.value())
        self._valor_salvo = novo
        if not self._emitindo:
            self._emitindo = True
            try:
                self.valor_confirmado.emit(novo)
            finally:
                self._emitindo = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Intercepta ``Esc`` para cancelar digitação e restaurar o valor anterior."""
        if (
            watched is self
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() == Qt.Key.Key_Escape
        ):
            self.definir_valor_silencioso(
                self._valor_salvo,
                indeterminado=self._indeterminado,
            )
            self.clearFocus()
            return True
        return super().eventFilter(watched, event)

    def _on_edicao_concluida(self) -> None:
        if (
            self._indeterminado
            and self.specialValueText() == "—"
            and abs(float(self.value()) - float(self.minimum())) < 1e-6
        ):
            return
        self._indeterminado = False
        self.setSpecialValueText("")
        novo = float(self.value())
        if abs(novo - self._valor_salvo) < 1e-6:
            return
        self._valor_salvo = novo
        if not self._emitindo:
            self._emitindo = True
            try:
                self.valor_confirmado.emit(novo)
            finally:
                self._emitindo = False


def criar_spin_de_limite(
    limite: LimiteCampo,
    parent: QWidget | None = None,
) -> SpinPreciso:
    """Constrói um ``SpinPreciso`` a partir de ``LimiteCampo`` de ``esquema.py``."""
    sufixo = f" {limite.unidade}" if limite.unidade else ""
    return SpinPreciso(
        parent,
        minimo=limite.minimo,
        maximo=limite.maximo,
        passo=limite.passo,
        casas=limite.casas,
        unidade=sufixo,
    )


class BotaoCorRGBA(QWidget):
    """Seletor de cor RGBA [0..1] com amostra clicável e canais tabulares."""

    cor_alterada = Signal(tuple)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa o seletor com botão de paleta e 4 campos RGBA."""
        super().__init__(parent)
        self._cor = (1.0, 1.0, 1.0, 1.0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        topo = QHBoxLayout()
        self._botao = QPushButton("Escolher cor…", self)
        self._botao.clicked.connect(self._abrir_dialogo)
        self._amostra = QLabel(self)
        self._amostra.setFixedSize(26, 20)
        topo.addWidget(self._botao, 1)
        topo.addWidget(self._amostra)
        layout.addLayout(topo)

        self._canais: list[SpinPreciso] = []
        layout.addLayout(self._criar_grade_canais())
        self.definir_cor(self._cor)

    def _criar_grade_canais(self) -> QGridLayout:
        grade = QGridLayout()
        grade.setHorizontalSpacing(4)
        grade.setVerticalSpacing(3)
        grade.setColumnStretch(1, 1)
        grade.setColumnStretch(3, 1)
        for idx, nome in enumerate(("R", "G", "B", "A")):
            lbl = QLabel(nome, self)
            lbl.setObjectName("rotuloSuave")
            spin = SpinPreciso(
                self,
                minimo=LIMITES_COR_CANAL.minimo,
                maximo=LIMITES_COR_CANAL.maximo,
                passo=LIMITES_COR_CANAL.passo,
                casas=LIMITES_COR_CANAL.casas,
            )
            spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            spin.valor_confirmado.connect(
                lambda _v, i=idx: self._on_canal_alterado(i),
            )
            row = idx // 2
            col = (idx % 2) * 2
            grade.addWidget(lbl, row, col)
            grade.addWidget(spin, row, col + 1)
            self._canais.append(spin)
        return grade

    def definir_cor(self, cor: tuple[float, float, float, float]) -> None:
        """Atualiza os quatro canais sem emitir sinal de alteração."""
        self._cor = (float(cor[0]), float(cor[1]), float(cor[2]), float(cor[3]))
        for spin, val in zip(self._canais, self._cor, strict=True):
            spin.definir_valor_silencioso(val)
        qcor = QColor.fromRgbF(*self._cor)
        self._amostra.setStyleSheet(
            f"background-color: {qcor.name()}; border: 1px solid #555; border-radius: 3px;",
        )

    def _on_canal_alterado(self, _idx: int) -> None:
        nova = tuple(float(spin.value()) for spin in self._canais)
        self.definir_cor((nova[0], nova[1], nova[2], nova[3]))
        self.cor_alterada.emit(self._cor)

    def _abrir_dialogo(self) -> None:
        inicial = QColor.fromRgbF(*self._cor)
        escolhida = QColorDialog.getColor(
            inicial,
            self,
            "Cor do efeito",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if not escolhida.isValid():
            return
        self.definir_cor(
            (
                escolhida.redF(),
                escolhida.greenF(),
                escolhida.blueF(),
                escolhida.alphaF(),
            ),
        )
        self.cor_alterada.emit(self._cor)


class ListaParesTempoWidget(QWidget):
    """Editor compacto de lista de chaves escalares ``(tempo_s, valor)``."""

    lista_alterada = Signal(tuple)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        rotulo_valor: str = "Valor",
        tipo_valor_str: bool = False,
    ) -> None:
        """Inicializa controles de adição, remoção e edição de pares tempo/valor."""
        super().__init__(parent)
        self._tipo_str = tipo_valor_str
        self._rotulo_valor = rotulo_valor
        self._itens: list[tuple[float, Any]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(self._criar_barra_ponto())
        layout.addLayout(self._criar_linha_edicao(rotulo_valor, tipo_valor_str))

    def _criar_barra_ponto(self) -> QHBoxLayout:
        self._combo = QComboBox(self)
        self._combo.currentIndexChanged.connect(self._sincronizar_linha_atual)
        linha_top = QHBoxLayout()
        linha_top.addWidget(self._combo, 1)
        self._btn_add = QToolButton(self)
        self._btn_add.setText("+")
        self._btn_add.setToolTip("Adicionar ponto")
        self._btn_add.clicked.connect(self._adicionar_ponto)
        self._btn_del = QToolButton(self)
        self._btn_del.setText("-")
        self._btn_del.setToolTip("Remover ponto atual")
        self._btn_del.clicked.connect(self._remover_ponto)
        linha_top.addWidget(self._btn_add)
        linha_top.addWidget(self._btn_del)
        return linha_top

    def _criar_linha_edicao(
        self,
        rotulo_valor: str,
        tipo_valor_str: bool,
    ) -> QGridLayout:
        linha_edit = QGridLayout()
        linha_edit.setHorizontalSpacing(4)
        linha_edit.setVerticalSpacing(3)
        linha_edit.setColumnStretch(1, 1)
        self._spin_t = SpinPreciso(
            self,
            minimo=0.0,
            maximo=120.0,
            passo=0.05,
            casas=3,
            unidade=" s",
        )
        self._spin_t.valor_confirmado.connect(lambda _v: self._aplicar_item_atual())
        linha_edit.addWidget(QLabel("t:", self), 0, 0)
        linha_edit.addWidget(self._spin_t, 0, 1)
        linha_edit.addWidget(QLabel(f"{rotulo_valor}:", self), 1, 0)
        self._spin_v: SpinPreciso | None = None
        self._edit_v: QLineEdit | None = None
        if tipo_valor_str:
            self._edit_v = QLineEdit(self)
            self._edit_v.editingFinished.connect(self._aplicar_item_atual)
            linha_edit.addWidget(self._edit_v, 1, 1)
        else:
            self._spin_v = SpinPreciso(
                self,
                minimo=-50.0,
                maximo=50.0,
                passo=0.05,
                casas=3,
            )
            self._spin_v.valor_confirmado.connect(
                lambda _v: self._aplicar_item_atual(),
            )
            linha_edit.addWidget(self._spin_v, 1, 1)
        return linha_edit

    def definir_itens(self, itens: tuple[tuple[float, Any], ...]) -> None:
        """Carrega os pares ``(tempo_s, valor)`` no editor sem emitir alteração."""
        self._itens = [(float(t), v) for t, v in itens]
        idx_ant = max(0, self._combo.currentIndex())
        self._repopular_combo(min(idx_ant, max(0, len(self._itens) - 1)))

    def _repopular_combo(self, idx_alvo: int) -> None:
        self._combo.blockSignals(True)
        try:
            self._combo.clear()
            for i, (t, val) in enumerate(self._itens):
                self._combo.addItem(f"#{i + 1}  {t:.2f} s → {val}")
            if self._itens:
                self._combo.setCurrentIndex(max(0, min(idx_alvo, len(self._itens) - 1)))
        finally:
            self._combo.blockSignals(False)
        self._sincronizar_linha_atual()

    def _sincronizar_linha_atual(self) -> None:
        idx = self._combo.currentIndex()
        tem = 0 <= idx < len(self._itens)
        self._spin_t.setEnabled(tem)
        self._btn_del.setEnabled(tem and len(self._itens) > 1)
        if self._spin_v is not None:
            self._spin_v.setEnabled(tem)
        if self._edit_v is not None:
            self._edit_v.setEnabled(tem)
        if not tem:
            return
        t, val = self._itens[idx]
        self._spin_t.definir_valor_silencioso(t)
        if self._spin_v is not None:
            self._spin_v.definir_valor_silencioso(float(val))
        elif self._edit_v is not None:
            self._edit_v.blockSignals(True)
            self._edit_v.setText(str(val))
            self._edit_v.blockSignals(False)

    def _aplicar_item_atual(self) -> None:
        idx = self._combo.currentIndex()
        if not (0 <= idx < len(self._itens)):
            return
        novo_t = float(self._spin_t.value())
        if self._edit_v is not None:
            novo_v: Any = self._edit_v.text().strip()
        elif self._spin_v is not None:
            novo_v = float(self._spin_v.value())
        else:
            return
        self._itens[idx] = (novo_t, novo_v)
        self._itens.sort(key=lambda item: item[0])
        self._repopular_combo(idx)
        self.lista_alterada.emit(tuple(self._itens))

    def _adicionar_ponto(self) -> None:
        ultimo_t = self._itens[-1][0] + 0.25 if self._itens else 0.0
        novo_v: Any = "evento" if self._tipo_str else 0.0
        self._itens.append((round(ultimo_t, 3), novo_v))
        self._repopular_combo(len(self._itens) - 1)
        self.lista_alterada.emit(tuple(self._itens))

    def _remover_ponto(self) -> None:
        idx = self._combo.currentIndex()
        if not (0 <= idx < len(self._itens)) or len(self._itens) <= 1:
            return
        self._itens.pop(idx)
        self._repopular_combo(max(0, idx - 1))
        self.lista_alterada.emit(tuple(self._itens))


class ConstrutorCamposMixin:
    """Helper compacto para montar formulários tipados sem duplicar widgets."""

    @staticmethod
    def adicionar_linha_escalar(
        grade: QGridLayout,
        linha: int,
        chave: str,
        valor: Any,
        ao_mudar: Any,
    ) -> QWidget:
        """Adiciona uma linha ``Rótulo | Controle`` conforme o tipo do valor."""
        meta = metadado_campo(chave)
        lbl = QLabel(meta.rotulo, grade.parentWidget())
        grade.addWidget(lbl, linha, 0)
        if isinstance(valor, bool):
            chk = QCheckBox(grade.parentWidget())
            chk.setChecked(valor)
            chk.toggled.connect(lambda estado: ao_mudar(chave, bool(estado)))
            grade.addWidget(chk, linha, 1)
            return chk
        if isinstance(valor, int):
            sp_int = QSpinBox(grade.parentWidget())
            sp_int.setRange(0, 100)
            sp_int.setValue(valor)
            sp_int.valueChanged.connect(lambda novo: ao_mudar(chave, int(novo)))
            grade.addWidget(sp_int, linha, 1)
            return sp_int
        spin = SpinPreciso(
            grade.parentWidget(),
            minimo=meta.minimo,
            maximo=meta.maximo,
            passo=meta.passo,
            casas=meta.casas,
            unidade=meta.unidade,
        )
        spin.definir_valor_silencioso(float(valor))
        spin.valor_confirmado.connect(lambda novo: ao_mudar(chave, float(novo)))
        grade.addWidget(spin, linha, 1)
        return spin
