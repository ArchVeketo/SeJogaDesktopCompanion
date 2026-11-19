"""Indicador translúcido de carregamento exibido enquanto shaders e modelo aquecem."""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QApplication, QWidget

if TYPE_CHECKING:
    from sejoga.configuracao import Settings


class LoadingSplash(QWidget):
    """Pílula flutuante translúcida sem bloqueio de mouse durante o warmup inicial."""

    _LARGURA = 296
    _ALTURA = 96
    _MARGEM = 8

    def __init__(self, settings: Settings | None = None) -> None:
        """Prepara a janela translúcida click-through e posiciona no monitor alvo."""
        super().__init__(None)
        self._t0 = time.perf_counter()
        self._status = "Carregando modelo 3D e shaders..."
        self._closed = False
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(self._LARGURA, self._ALTURA)
        self._posicionar(settings)

    def _posicionar(self, settings: Settings | None) -> None:
        screens = QGuiApplication.screens()
        screen = QGuiApplication.primaryScreen()
        alvo_rect = screen.availableGeometry() if screen is not None else None
        sx = sy = None
        win_size = 480
        if settings is not None:
            win_size = int(settings.window.size)
            pos = settings.window.start_position
            if pos is not None:
                sx, sy = int(pos[0]), int(pos[1])
                matched = QGuiApplication.screenAt(QPoint(sx + win_size // 2, sy + win_size // 2))
                if matched is not None:
                    alvo_rect = matched.availableGeometry()
        if alvo_rect is None and screens:
            alvo_rect = screens[0].availableGeometry()
        if alvo_rect is None:
            return
        if sx is not None and sy is not None:
            px = sx + (win_size - self._LARGURA) // 2
            py = sy + win_size - self._ALTURA - 24
        else:
            px = alvo_rect.right() - self._LARGURA - 36
            py = alvo_rect.bottom() - self._ALTURA - 36
        clamped_x = max(alvo_rect.left() + 8, min(alvo_rect.right() - self._LARGURA - 8, px))
        clamped_y = max(alvo_rect.top() + 8, min(alvo_rect.bottom() - self._ALTURA - 8, py))
        self.move(clamped_x, clamped_y)

    def set_status(self, texto: str) -> None:
        """Atualiza o subtítulo visível do indicador de carregamento."""
        if not self._closed and texto and texto != self._status:
            self._status = texto
            self.update()

    def tick(self) -> None:
        """Avança o pulso visual e bombeia eventos Qt sem bloquear."""
        if self._closed:
            return
        self.update()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

    def finish(self) -> None:
        """Oculta e descarta a janela de carregamento de forma idempotente."""
        if self._closed:
            return
        self._closed = True
        self.hide()
        self.close()
        self.deleteLater()

    def _desenhar_capsula_e_orbita(
        self, painter: QPainter, box: QRectF, elapsed: float
    ) -> None:
        """Desenha fundo, borda neon e indicador orbital à esquerda."""
        path = QPainterPath()
        path.addRoundedRect(box, 18.0, 18.0)

        # Halo suave ao redor da pílula para leitura em fundos claros ou escuros.
        painter.setPen(QPen(QColor(255, 31, 143, 46), 5.0))
        painter.drawPath(path)

        bg = QLinearGradient(box.topLeft(), box.bottomRight())
        bg.setColorAt(0.0, QColor(19, 15, 34, 232))
        bg.setColorAt(1.0, QColor(12, 11, 22, 236))
        painter.fillPath(path, bg)

        border_grad = QLinearGradient(box.topLeft(), box.bottomRight())
        border_grad.setColorAt(0.0, QColor(255, 31, 143, 215))
        border_grad.setColorAt(0.5, QColor(200, 255, 46, 175))
        border_grad.setColorAt(1.0, QColor(31, 240, 255, 215))
        painter.setPen(QPen(border_grad, 1.5))
        painter.drawPath(path)

        cx = box.left() + 30.0
        cy = box.center().y() - 4.0
        painter.setPen(QPen(QColor(255, 255, 255, 28), 2.5))
        painter.drawEllipse(QPoint(int(cx), int(cy)), 12, 12)
        arc_pen = QPen(QColor(31, 240, 255, 235), 2.8)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        painter.drawArc(
            int(cx - 12),
            int(cy - 12),
            24,
            24,
            int(math.degrees(-elapsed * 4.6) * 16),
            130 * 16,
        )
        pulse = 0.5 + 0.5 * math.sin(elapsed * 6.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 31, 143, int(170 + 80 * pulse)))
        painter.drawEllipse(QPoint(int(cx), int(cy)), 5, 5)

    def _desenhar_textos(self, painter: QPainter, box: QRectF) -> None:
        """Desenha título e status atual do carregamento."""
        text_left = int(box.left() + 54.0)
        text_width = int(box.width() - 70.0)
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        painter.setPen(QColor(248, 246, 255, 248))
        painter.drawText(
            QRectF(text_left, box.top() + 12.0, text_width, 22.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Carregando Mário...",
        )
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(186, 184, 212, 220))
        painter.drawText(
            QRectF(text_left, box.top() + 33.0, text_width, 18.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._status,
        )

    def _desenhar_barra(self, painter: QPainter, box: QRectF, elapsed: float) -> None:
        """Desenha trilho e pílula deslizante da barra de progresso contínua."""
        bar_x = box.left() + 54.0
        bar_y = box.bottom() - 18.0
        bar_w = box.width() - 72.0
        bar_h = 5.0
        track = QPainterPath()
        track.addRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2.5, 2.5)
        painter.fillPath(track, QColor(255, 255, 255, 34))

        cycle = (elapsed * 0.85) % 1.0
        pill_w = bar_w * 0.42
        pill_x = bar_x - pill_w * 0.35 + cycle * (bar_w - pill_w * 0.30)
        clipped_left = max(bar_x, pill_x)
        clipped_right = min(bar_x + bar_w, pill_x + pill_w)
        if clipped_right > clipped_left:
            pill = QPainterPath()
            pill.addRoundedRect(
                QRectF(clipped_left, bar_y, clipped_right - clipped_left, bar_h),
                2.5,
                2.5,
            )
            bar_grad = QLinearGradient(clipped_left, bar_y, clipped_right, bar_y)
            bar_grad.setColorAt(0.0, QColor(255, 31, 143))
            bar_grad.setColorAt(0.55, QColor(200, 255, 46))
            bar_grad.setColorAt(1.0, QColor(31, 240, 255))
            painter.fillPath(pill, bar_grad)

    def paintEvent(self, _event) -> None:
        """Desenha a cápsula translúcida com borda neon e barra fluida."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        elapsed = max(0.0, time.perf_counter() - self._t0)
        m = float(self._MARGEM)
        box = QRectF(m, m, self.width() - 2.0 * m, self.height() - 2.0 * m)
        self._desenhar_capsula_e_orbita(painter, box, elapsed)
        self._desenhar_textos(painter, box)
        self._desenhar_barra(painter, box, elapsed)
