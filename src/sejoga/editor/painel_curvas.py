"""Gráfico interativo de curvas por eixo (X, Y, Z) dentro da área da timeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from sejoga.animacao.clipes_animacao import amostrar_pista
from sejoga.editor.tema import COR_BORDA, COR_DESTAQUE, COR_PAINEL, COR_TEXTO_SUAVE

_CORES_EIXOS: tuple[str, str, str] = ("#E06C75", "#57C785", "#4EA1FF")
_MARGEM_ESQ = 48.0
_ALTURA_REGUA = 24.0


@dataclass
class _ArrasteCurva:
    eixo: int
    indice: int
    tempo_inicial: float
    valor_inicial: tuple[float, float, float]


class _CanvasCurvas(QWidget):
    """Área pintada com régua superior, curvas interpoladas e alças arrastáveis."""

    cursor_movido = Signal(float)
    chave_selecionada = Signal(str, int)
    chave_movida_preview = Signal(str, int, float, tuple)
    chave_movida_confirmada = Signal(str, int, float, tuple)
    zoom_alterado = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa o gráfico de curvas vazio aguardando a pista selecionada."""
        super().__init__(parent)
        self.setMinimumHeight(130)
        self.setMouseTracking(True)
        self._grupo = ""
        self._chaves: list[tuple[float, tuple[float, float, float]]] = []
        self._curvas: list[str] = []
        self._eixos_visiveis = [True, True, True]
        self._tempo_s = 0.0
        self._duracao_s = 4.0
        self._px_por_s = 120.0
        self._offset_x = 0.0
        self._y_min = -95.0
        self._y_max = 95.0
        self._indice_sel = -1
        self._eixo_sel = 0
        self._arraste: _ArrasteCurva | None = None
        self._arrastando_cursor = False
        self._func_snap: Callable[[float], float] | None = None

    def definir_snap(self, func_snap: Callable[[float], float] | None) -> None:
        """Registra função opcional de magnetismo horizontal durante arraste."""
        self._func_snap = func_snap

    def definir_dados(
        self,
        grupo: str,
        chaves: tuple[tuple[float, tuple[float, float, float]], ...],
        curvas: tuple[str, ...] | list[str],
    ) -> None:
        """Carrega chaves e tipos de curva do grupo ativo e enquadra Y."""
        self._grupo = grupo
        self._chaves = [(float(t), (float(r[0]), float(r[1]), float(r[2]))) for t, r in chaves]
        self._curvas = list(curvas)
        self._enquadrar_y()
        self.update()

    def definir_tempo(self, tempo_s: float, duracao_s: float) -> None:
        """Atualiza posição do cursor e duração visível."""
        self._tempo_s = float(tempo_s)
        self._duracao_s = max(0.1, float(duracao_s))
        self.update()

    def definir_eixos_visiveis(self, x: bool, y: bool, z: bool) -> None:
        """Alterna visibilidade das curvas X, Y e Z."""
        self._eixos_visiveis = [x, y, z]
        self.update()

    def definir_zoom_e_scroll(self, px_por_s: float, offset_x: float) -> None:
        """Sincroniza escala horizontal e rolagem com a timeline de chaves."""
        self._px_por_s = max(30.0, min(600.0, float(px_por_s)))
        self._offset_x = max(0.0, float(offset_x))
        self.update()

    def definir_chave_selecionada(self, indice: int) -> None:
        """Destaca o índice da chave selecionada."""
        self._indice_sel = indice
        self.update()

    def _enquadrar_y(self) -> None:
        if not self._chaves:
            self._y_min, self._y_max = -95.0, 95.0
            return
        vals = [v for _, rot in self._chaves for v in rot]
        vmin = min(-15.0, min(vals))
        vmax = max(15.0, max(vals))
        folga = max(10.0, 0.15 * (vmax - vmin))
        self._y_min = vmin - folga
        self._y_max = vmax + folga

    def _x_para_tempo(self, x_px: float) -> float:
        return max(0.0, (x_px - _MARGEM_ESQ + self._offset_x) / self._px_por_s)

    def _tempo_para_x(self, tempo_s: float) -> float:
        return _MARGEM_ESQ + tempo_s * self._px_por_s - self._offset_x

    def _grau_para_y(self, grau: float) -> float:
        altura = max(20.0, self.height() - _ALTURA_REGUA - 12.0)
        frac = (grau - self._y_min) / max(1e-4, self._y_max - self._y_min)
        return _ALTURA_REGUA + 6.0 + (1.0 - frac) * altura

    def _y_para_grau(self, y_px: float) -> float:
        altura = max(20.0, self.height() - _ALTURA_REGUA - 12.0)
        frac = 1.0 - (y_px - (_ALTURA_REGUA + 6.0)) / altura
        grau = self._y_min + frac * (self._y_max - self._y_min)
        return max(-360.0, min(360.0, grau))

    def paintEvent(self, _event: QPaintEvent) -> None:
        """Desenha grade, régua de segundos, curvas por eixo, nós e cursor."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(COR_PAINEL))
        self._desenhar_grade_e_regua(painter)
        self._desenhar_curvas(painter)
        self._desenhar_nos(painter)
        self._desenhar_playhead(painter)

    def _desenhar_grade_e_regua(self, painter: QPainter) -> None:
        painter.fillRect(
            QRectF(0.0, 0.0, float(self.width()), _ALTURA_REGUA),
            QColor("#1E2024"),
        )
        painter.setPen(QPen(QColor(COR_BORDA), 1.0))
        painter.drawLine(0, int(_ALTURA_REGUA), self.width(), int(_ALTURA_REGUA))
        painter.drawLine(int(_MARGEM_ESQ), 0, int(_MARGEM_ESQ), self.height())

        y_zero = self._grau_para_y(0.0)
        if _ALTURA_REGUA <= y_zero <= self.height():
            painter.setPen(QPen(QColor("#444A52"), 1.0, Qt.PenStyle.DashLine))
            painter.drawLine(int(_MARGEM_ESQ), int(y_zero), self.width(), int(y_zero))
            painter.setPen(QColor(COR_TEXTO_SUAVE))
            painter.drawText(6, int(y_zero + 4), "0°")

        passo = 0.5 if self._px_por_s >= 140.0 else 1.0
        t = 0.0
        while t <= self._duracao_s + 0.01:
            x = self._tempo_para_x(t)
            if x >= _MARGEM_ESQ:
                painter.setPen(QColor("#2E3238"))
                painter.drawLine(int(x), int(_ALTURA_REGUA), int(x), self.height())
                painter.setPen(QColor(COR_TEXTO_SUAVE))
                painter.drawText(int(x + 3), 16, f"{t:.1f}s")
            t += passo

    def _desenhar_curvas(self, painter: QPainter) -> None:
        if len(self._chaves) < 2:
            return
        chaves_tupla = tuple(self._chaves)
        t_ini = self._chaves[0][0]
        t_fim = max(t_ini + 0.05, self._chaves[-1][0])
        amostras = 96
        for eixo in range(3):
            if not self._eixos_visiveis[eixo]:
                continue
            caminho = QPainterPath()
            for i in range(amostras + 1):
                t = t_ini + (t_fim - t_ini) * (i / amostras)
                rot = amostrar_pista(chaves_tupla, t, curvas=self._curvas)
                pt = QPointF(self._tempo_para_x(t), self._grau_para_y(rot[eixo]))
                if i == 0:
                    caminho.moveTo(pt)
                else:
                    caminho.lineTo(pt)
            painter.setPen(QPen(QColor(_CORES_EIXOS[eixo]), 1.8))
            painter.drawPath(caminho)

    def _desenhar_nos(self, painter: QPainter) -> None:
        for idx, (t, rot) in enumerate(self._chaves):
            x = self._tempo_para_x(t)
            if x < _MARGEM_ESQ - 6:
                continue
            for eixo in range(3):
                if not self._eixos_visiveis[eixo]:
                    continue
                y = self._grau_para_y(rot[eixo])
                selecionado = idx == self._indice_sel and eixo == self._eixo_sel
                cor = QColor("#FFFFFF") if selecionado else QColor(_CORES_EIXOS[eixo])
                borda = QColor(COR_DESTAQUE) if selecionado else QColor("#111315")
                painter.setBrush(cor)
                painter.setPen(QPen(borda, 1.5))
                raio = 5.0 if selecionado else 4.0
                painter.drawEllipse(QPointF(x, y), raio, raio)

    def _desenhar_playhead(self, painter: QPainter) -> None:
        x = self._tempo_para_x(self._tempo_s)
        if x < _MARGEM_ESQ:
            return
        painter.setPen(QPen(QColor(COR_DESTAQUE), 1.6))
        painter.drawLine(int(x), 0, int(x), self.height())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Inicia arraste de nó de curva ou arraste do cursor na régua."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if pos.y() <= _ALTURA_REGUA:
            self._arrastando_cursor = True
            self._emitir_cursor(pos.x())
            return
        hit = self._encontrar_no(pos.x(), pos.y())
        if hit is not None:
            eixo, idx = hit
            self._eixo_sel = eixo
            self._indice_sel = idx
            t, rot = self._chaves[idx]
            self._arraste = _ArrasteCurva(eixo, idx, t, rot)
            self.chave_selecionada.emit(self._grupo, idx)
            self.update()
            return
        self._arrastando_cursor = True
        self._emitir_cursor(pos.x())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Atualiza prévia ao vivo ao arrastar ponto da curva ou cursor."""
        pos = event.position()
        if self._arrastando_cursor:
            self._emitir_cursor(pos.x())
            return
        if self._arraste is None:
            return
        novo_t, nova_rot = self._calcular_arraste(pos.x(), pos.y(), event.modifiers())
        self._chaves[self._arraste.indice] = (novo_t, nova_rot)
        self.chave_movida_preview.emit(
            self._grupo,
            self._arraste.indice,
            novo_t,
            nova_rot,
        )
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Finaliza o arraste emitindo uma única operação confirmada de desfazer."""
        if self._arrastando_cursor:
            self._arrastando_cursor = False
            return
        if self._arraste is None:
            return
        pos = event.position()
        novo_t, nova_rot = self._calcular_arraste(pos.x(), pos.y(), event.modifiers())
        idx = self._arraste.indice
        self._arraste = None
        self.chave_movida_confirmada.emit(self._grupo, idx, novo_t, nova_rot)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom horizontal pela roda do mouse."""
        delta = event.angleDelta().y()
        fator = 1.15 if delta > 0 else 1 / 1.15
        self._px_por_s = max(30.0, min(600.0, self._px_por_s * fator))
        self.zoom_alterado.emit(self._px_por_s)
        self.update()

    def _emitir_cursor(self, x_px: float) -> None:
        t = min(self._duracao_s, self._x_para_tempo(x_px))
        self.cursor_movido.emit(t)

    def _encontrar_no(self, x_px: float, y_px: float) -> tuple[int, int] | None:
        melhor: tuple[float, int, int] | None = None
        for idx, (t, rot) in enumerate(self._chaves):
            nx = self._tempo_para_x(t)
            for eixo in range(3):
                if not self._eixos_visiveis[eixo]:
                    continue
                ny = self._grau_para_y(rot[eixo])
                d2 = (nx - x_px) ** 2 + (ny - y_px) ** 2
                if d2 <= 100.0 and (melhor is None or d2 < melhor[0]):
                    melhor = (d2, eixo, idx)
        if melhor is None:
            return None
        return melhor[1], melhor[2]

    def _calcular_arraste(
        self,
        x_px: float,
        y_px: float,
        mod: Qt.KeyboardModifier,
    ) -> tuple[float, tuple[float, float, float]]:
        arr = self._arraste
        assert arr is not None
        novo_t = min(self._duracao_s, self._x_para_tempo(x_px))
        if not (mod & Qt.KeyboardModifier.AltModifier) and self._func_snap is not None:
            novo_t = self._func_snap(novo_t)
        vals = list(arr.valor_inicial)
        vals[arr.eixo] = round(self._y_para_grau(y_px), 2)
        return round(novo_t, 4), (vals[0], vals[1], vals[2])


class PainelCurvas(QWidget):
    """Painel completo do gráfico de curvas compartilhando cursor e seleção."""

    cursor_movido = Signal(float)
    chave_selecionada = Signal(str, int)
    chave_movida_preview = Signal(str, int, float, tuple)
    chave_movida_confirmada = Signal(str, int, float, tuple)
    zoom_alterado = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa barra de eixos/enquadramento e o canvas do gráfico."""
        super().__init__(parent)
        self.setObjectName("painelCurvas")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addLayout(self._criar_barra())

        self._canvas = _CanvasCurvas(self)
        self._canvas.cursor_movido.connect(self.cursor_movido.emit)
        self._canvas.chave_selecionada.connect(self.chave_selecionada.emit)
        self._canvas.chave_movida_preview.connect(self.chave_movida_preview.emit)
        self._canvas.chave_movida_confirmada.connect(self.chave_movida_confirmada.emit)
        self._canvas.zoom_alterado.connect(self.zoom_alterado.emit)
        layout.addWidget(self._canvas, 1)

    def _criar_barra(self) -> QHBoxLayout:
        barra = QHBoxLayout()
        barra.setContentsMargins(6, 2, 6, 2)
        self._lbl_pista = QLabel("Curva da junta", self)
        self._chk_x = QCheckBox("X", self)
        self._chk_y = QCheckBox("Y", self)
        self._chk_z = QCheckBox("Z", self)
        for chk, cor in (
            (self._chk_x, _CORES_EIXOS[0]),
            (self._chk_y, _CORES_EIXOS[1]),
            (self._chk_z, _CORES_EIXOS[2]),
        ):
            chk.setChecked(True)
            chk.setStyleSheet(f"color: {cor}; font-weight: 600;")
            chk.toggled.connect(self._atualizar_eixos)
        btn_fit = QToolButton(self)
        btn_fit.setText("Enquadrar Y")
        btn_fit.clicked.connect(self._enquadrar)

        barra.addWidget(self._lbl_pista)
        barra.addStretch(1)
        barra.addWidget(self._chk_x)
        barra.addWidget(self._chk_y)
        barra.addWidget(self._chk_z)
        barra.addWidget(btn_fit)
        return barra

    def definir_snap(self, func_snap: Callable[[float], float] | None) -> None:
        """Repassa a função de snap de tempo ao canvas de curvas."""
        self._canvas.definir_snap(func_snap)

    def carregar_pista(
        self,
        grupo: str,
        chaves: tuple[tuple[float, tuple[float, float, float]], ...],
        curvas: tuple[str, ...] | list[str],
    ) -> None:
        """Carrega os dados da junta selecionada no gráfico."""
        self._lbl_pista.setText(f"Curva: {grupo} ({len(chaves)} chaves)")
        self._canvas.definir_dados(grupo, chaves, curvas)

    def definir_tempo(self, tempo_s: float, duracao_s: float) -> None:
        """Atualiza o cursor e duração mantendo sincronia com a timeline."""
        self._canvas.definir_tempo(tempo_s, duracao_s)

    def definir_zoom_e_scroll(self, px_por_s: float, offset_x: float) -> None:
        """Sincroniza escala horizontal e deslocamento X com a timeline."""
        self._canvas.definir_zoom_e_scroll(px_por_s, offset_x)

    def _atualizar_eixos(self) -> None:
        self._canvas.definir_eixos_visiveis(
            self._chk_x.isChecked(),
            self._chk_y.isChecked(),
            self._chk_z.isChecked(),
        )

    def _enquadrar(self) -> None:
        self._canvas._enquadrar_y()
        self._canvas.update()
