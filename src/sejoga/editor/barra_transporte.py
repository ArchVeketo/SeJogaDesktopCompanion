"""Barra de transporte e ritmo fixa no topo da área da timeline."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QWidget,
)

from sejoga.editor.esquema import LIMITES_BPM
from sejoga.editor.tema import fonte_tabular
from sejoga.editor.widgets_campos import SpinPreciso


def _botao_transporte(
    pai: QWidget,
    texto: str,
    dica: str,
    nome_acessivel: str,
    *,
    checavel: bool = False,
) -> QToolButton:
    btn = QToolButton(pai)
    btn.setText(texto)
    btn.setToolTip(dica)
    btn.setAccessibleName(nome_acessivel)
    btn.setCheckable(checavel)
    btn.setMinimumSize(30, 28)
    return btn


class BarraTransporte(QWidget):
    """Barra fixa com controles de quadro, reprodução, snap, metrônomo e leitura."""

    passo_quadro = Signal(int)
    alternar_reproducao = Signal()
    loop_alterado = Signal(bool)
    fps_alterado = Signal(int)
    velocidade_alterada = Signal(float)
    snap_alterado = Signal(str)
    auto_chave_alterado = Signal(bool)
    bpm_alterado = Signal(float)
    metronomo_alterado = Signal(bool)
    batida_gravada = Signal()
    musica_ao_vivo_alterada = Signal(bool)
    curvas_alternadas = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa botões de transporte, grade de ritmo e leitura tabular."""
        super().__init__(parent)
        self.setObjectName("barraTransporte")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        self._adicionar_controles_reproducao(layout)
        self._adicionar_controles_grade(layout)
        self._adicionar_controles_ritmo(layout)
        layout.addStretch(1)
        self._adicionar_leitura_tempo(layout)

    def _adicionar_controles_reproducao(self, layout: QHBoxLayout) -> None:
        self._btn_ant = _botao_transporte(
            self,
            "◀ Quadro",
            "Voltar um quadro (Seta esquerda)",
            "Quadro anterior",
        )
        self._btn_ant.clicked.connect(lambda: self.passo_quadro.emit(-1))
        self._btn_play = _botao_transporte(
            self,
            "▶ Reproduzir",
            "Reproduzir ou pausar (Espaço)",
            "Reproduzir ou pausar",
            checavel=True,
        )
        self._btn_play.clicked.connect(self.alternar_reproducao.emit)
        self._btn_prox = _botao_transporte(
            self,
            "Quadro ▶",
            "Avançar um quadro (Seta direita)",
            "Próximo quadro",
        )
        self._btn_prox.clicked.connect(lambda: self.passo_quadro.emit(1))
        self._btn_loop = _botao_transporte(
            self,
            "Loop",
            "Repetir tomada em loop",
            "Alternar loop",
            checavel=True,
        )
        self._btn_loop.toggled.connect(self.loop_alterado.emit)
        for btn in (self._btn_ant, self._btn_play, self._btn_prox, self._btn_loop):
            layout.addWidget(btn)

    def _adicionar_controles_grade(self, layout: QHBoxLayout) -> None:
        self._combo_fps = QComboBox(self)
        self._combo_fps.setAccessibleName("Taxa de quadros da prévia")
        self._combo_fps.setToolTip("Taxa de quadros visual da prévia")
        for fps in (24, 30, 60):
            self._combo_fps.addItem(f"{fps} fps", fps)
        self._combo_fps.setCurrentIndex(2)
        self._combo_fps.currentIndexChanged.connect(
            lambda _i: self.fps_alterado.emit(int(self._combo_fps.currentData())),
        )

        self._combo_vel = QComboBox(self)
        self._combo_vel.setAccessibleName("Velocidade da prévia")
        for vel in (0.25, 0.5, 1.0, 1.5, 2.0):
            self._combo_vel.addItem(f"{vel:g}x", vel)
        self._combo_vel.setCurrentIndex(2)
        self._combo_vel.currentIndexChanged.connect(
            lambda _i: self.velocidade_alterada.emit(float(self._combo_vel.currentData())),
        )

        self._combo_snap = QComboBox(self)
        self._combo_snap.setAccessibleName("Modo de alinhamento (snap)")
        self._combo_snap.setToolTip("Alinhamento de chaves (segure Alt para ignorar)")
        for chave, rot in (
            ("livre", "Snap: Livre"),
            ("quadro", "Snap: Quadro"),
            ("chave", "Snap: Chave"),
            ("batida", "Snap: Batida"),
        ):
            self._combo_snap.addItem(rot, chave)
        self._combo_snap.currentIndexChanged.connect(
            lambda _i: self.snap_alterado.emit(str(self._combo_snap.currentData())),
        )

        self._btn_autochave = _botao_transporte(
            self,
            "Auto-chave",
            "Gravar automaticamente ao mover junta fora de uma chave existente",
            "Alternar auto-chave",
            checavel=True,
        )
        self._btn_autochave.toggled.connect(self.auto_chave_alterado.emit)
        for w in (self._combo_fps, self._combo_vel, self._combo_snap, self._btn_autochave):
            layout.addWidget(w)

    def _adicionar_controles_ritmo(self, layout: QHBoxLayout) -> None:
        self._spin_bpm = SpinPreciso(
            self,
            minimo=LIMITES_BPM.minimo,
            maximo=LIMITES_BPM.maximo,
            passo=1.0,
            casas=1,
            unidade=" BPM",
        )
        self._spin_bpm.definir_valor_silencioso(108.0)
        self._spin_bpm.setAccessibleName("BPM do metrônomo e da grade de batidas")
        self._spin_bpm.valor_confirmado.connect(self.bpm_alterado.emit)

        self._btn_metro = _botao_transporte(
            self,
            "Metrônomo",
            "Tocar pulso visual no BPM configurado",
            "Alternar metrônomo",
            checavel=True,
        )
        self._btn_metro.toggled.connect(self.metronomo_alterado.emit)

        self._btn_batida = QPushButton("Gravar batida", self)
        self._btn_batida.setToolTip("Registrar batida no instante atual do cursor")
        self._btn_batida.setAccessibleName("Gravar batida no cursor")
        self._btn_batida.clicked.connect(self.batida_gravada.emit)

        self._btn_ao_vivo = _botao_transporte(
            self,
            "Ao vivo",
            "Usar detecção de música do sistema",
            "Alternar música ao vivo",
            checavel=True,
        )
        self._btn_ao_vivo.toggled.connect(self.musica_ao_vivo_alterada.emit)

        self._btn_curvas = _botao_transporte(
            self,
            "Curvas",
            "Alternar entre pistas de chaves e gráfico de curvas",
            "Alternar gráfico de curvas",
            checavel=True,
        )
        self._btn_curvas.toggled.connect(self.curvas_alternadas.emit)

        for w in (
            self._spin_bpm,
            self._btn_metro,
            self._btn_batida,
            self._btn_ao_vivo,
            self._btn_curvas,
        ):
            layout.addWidget(w)

    def _adicionar_leitura_tempo(self, layout: QHBoxLayout) -> None:
        self._lbl_tempo = QLabel("0.00 s   Quadro 0", self)
        self._lbl_tempo.setFont(fonte_tabular(11, negrito=True))
        self._lbl_tempo.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self._lbl_tempo.setAccessibleName("Leitura de tempo e quadro atual")
        layout.addWidget(self._lbl_tempo)

    def definir_reproduzindo(self, ativo: bool) -> None:
        """Sincroniza texto e estado do botão Reproduzir/Pausar."""
        self._btn_play.blockSignals(True)
        self._btn_play.setChecked(ativo)
        self._btn_play.setText("⏸ Pausar" if ativo else "▶ Reproduzir")
        self._btn_play.blockSignals(False)

    def definir_loop(self, ativo: bool) -> None:
        """Atualiza o botão de loop sem re-emitir sinal."""
        self._btn_loop.blockSignals(True)
        self._btn_loop.setChecked(ativo)
        self._btn_loop.blockSignals(False)

    def definir_bpm(self, bpm: float) -> None:
        """Atualiza o campo de BPM sem disparar alteração."""
        self._spin_bpm.definir_valor_silencioso(bpm)

    def definir_auto_chave(self, ativo: bool) -> None:
        """Atualiza o estado visual de Auto-chave."""
        self._btn_autochave.blockSignals(True)
        self._btn_autochave.setChecked(ativo)
        self._btn_autochave.blockSignals(False)

    def definir_modo_curvas(self, ativo: bool) -> None:
        """Atualiza o estado do botão Curvas sem re-emitir sinal."""
        self._btn_curvas.blockSignals(True)
        self._btn_curvas.setChecked(ativo)
        self._btn_curvas.blockSignals(False)

    def atualizar_leitura(
        self,
        tempo_s: float,
        quadro_idx: int,
        *,
        batida_ativa: bool = False,
        mostrar_batida: bool = False,
        bpm: float = 108.0,
    ) -> None:
        """Atualiza a leitura tabular de segundos, quadro e batida musical."""
        base = f"{tempo_s:0.2f} s   Quadro {quadro_idx}"
        if mostrar_batida and bpm > 0.0:
            batida = tempo_s * (bpm / 60.0) + 1.0
            pulso = " ●" if batida_ativa else ""
            base = f"{base}   Batida {batida:0.1f}{pulso}"
        self._lbl_tempo.setText(base)
