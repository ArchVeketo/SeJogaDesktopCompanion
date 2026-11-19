"""Timeline completa com transporte fixo, pistas, faixas de efeito e curvas."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QScrollBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sejoga.editor.barra_transporte import BarraTransporte
from sejoga.editor.painel_curvas import PainelCurvas
from sejoga.editor.painel_inspetor import nome_amigavel_junta
from sejoga.editor.roteiro import EstimuloRoteiro
from sejoga.editor.tema import (
    COR_BORDA,
    COR_DESTAQUE,
    COR_FUNDO,
    COR_PAINEL,
    COR_PAINEL_ALT,
    COR_TEXTO,
    COR_TEXTO_SUAVE,
    fonte_tabular,
)

ALTURA_REGUA = 26
ALTURA_LINHA = 24
LARGURA_CABECALHO = 196


@dataclass(frozen=True)
class PistaVisual:
    """Representação genérica de uma pista de chaves na timeline."""

    nome: str
    rotulo: str
    chaves: tuple[tuple[float, tuple[float, float, float]], ...]
    curvas: tuple[str, ...] = ()
    tipo: str = "junta"


@dataclass(frozen=True)
class FaixaEfeitoVisual:
    """Trecho com início e fim para disparo contínuo de efeito na cena."""

    nome: str
    inicio_s: float
    fim_s: float


@dataclass
class _ArrasteItem:
    modo: str  # "cursor", "chave", "efeito_mover", "efeito_ini", "efeito_fim", "estimulo"
    alvo: str
    indice: int
    tempo_inicial: float
    ini_orig: float = 0.0
    fim_orig: float = 0.0
    x_inicial_px: float = 0.0


def _poligono_losango(cx: float, cy: float, r: float) -> QPolygonF:
    return QPolygonF(
        [
            QPointF(cx, cy - r),
            QPointF(cx + r, cy),
            QPointF(cx, cy + r),
            QPointF(cx - r, cy),
        ],
    )


class _CabecalhosPistas(QWidget):
    """Coluna esquerda fixa exibindo nomes de pistas, botões Solo/Mudo e tipos."""

    pista_clicada = Signal(str)
    solo_alternado = Signal(str)
    mudo_alternado = Signal(str)
    efeito_clicado = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(LARGURA_CABECALHO)
        self._pistas: list[PistaVisual] = []
        self._efeitos: list[FaixaEfeitoVisual] = []
        self._tem_estimulos = True
        self._scroll_y = 0
        self._selecionada = ""
        self._solo: str | None = None
        self._silenciadas: set[str] = set()

    def definir_conteudo(
        self,
        pistas: list[PistaVisual],
        efeitos: list[FaixaEfeitoVisual],
        *,
        selecionada: str,
        solo: str | None,
        silenciadas: set[str],
    ) -> None:
        """Atualiza lista de linhas visíveis à esquerda e estado Solo/Mudo."""
        self._pistas = list(pistas)
        self._efeitos = list(efeitos)
        self._selecionada = selecionada
        self._solo = solo
        self._silenciadas = set(silenciadas)
        self.update()

    def definir_scroll_y(self, scroll_y: int) -> None:
        """Sincroniza rolagem vertical com o canvas da timeline."""
        self._scroll_y = max(0, scroll_y)
        self.update()

    def total_linhas(self) -> int:
        """Retorna a quantidade total de faixas empilhadas."""
        return len(self._pistas) + len(self._efeitos) + (1 if self._tem_estimulos else 0)

    def paintEvent(self, _event: QPaintEvent) -> None:
        """Desenha cabeçalho fixo 'Pistas' e linhas com botões S/M."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(COR_PAINEL))
        painter.setFont(fonte_tabular(9))
        self._desenhar_linhas(painter)
        painter.fillRect(0, 0, self.width(), ALTURA_REGUA, QColor(COR_PAINEL_ALT))
        painter.setPen(QColor(COR_BORDA))
        painter.drawLine(0, ALTURA_REGUA, self.width(), ALTURA_REGUA)
        painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())
        painter.setPen(QColor(COR_TEXTO))
        painter.drawText(10, 17, "Pistas")

    def _desenhar_linhas(self, painter: QPainter) -> None:
        linhas = self._listar_linhas()
        for idx, (tipo, nome, rotulo) in enumerate(linhas):
            y = ALTURA_REGUA + idx * ALTURA_LINHA - self._scroll_y
            if y + ALTURA_LINHA < ALTURA_REGUA or y > self.height():
                continue
            ret = QRectF(0.0, float(y), float(self.width() - 1), float(ALTURA_LINHA))
            bg = "#26313E" if nome == self._selecionada else COR_PAINEL
            painter.fillRect(ret, QColor(bg))
            painter.setPen(QColor("#2E3238"))
            painter.drawLine(0, y + ALTURA_LINHA - 1, self.width(), y + ALTURA_LINHA - 1)
            painter.setPen(QColor(COR_TEXTO if tipo == "junta" else COR_TEXTO_SUAVE))
            larg_txt = self.width() - (56 if tipo == "junta" else 16)
            elidido = painter.fontMetrics().elidedText(
                rotulo,
                Qt.TextElideMode.ElideRight,
                larg_txt,
            )
            painter.drawText(8, y + 16, elidido)
            if tipo == "junta":
                self._desenhar_botoes_sm(painter, nome, y)

    def _desenhar_botoes_sm(self, painter: QPainter, nome: str, y: int) -> None:
        ret_s = QRectF(float(self.width() - 48), float(y + 4), 18.0, 16.0)
        ret_m = QRectF(float(self.width() - 26), float(y + 4), 18.0, 16.0)
        ativo_s = self._solo == nome
        ativo_m = nome in self._silenciadas
        for ret, letra, ativo, cor in (
            (ret_s, "S", ativo_s, "#4EA1FF"),
            (ret_m, "M", ativo_m, "#E5A93C"),
        ):
            painter.fillRect(ret, QColor(cor if ativo else "#2D3136"))
            painter.setPen(QColor("#111315" if ativo else COR_TEXTO_SUAVE))
            painter.drawText(ret, Qt.AlignmentFlag.AlignCenter, letra)

    def _listar_linhas(self) -> list[tuple[str, str, str]]:
        itens: list[tuple[str, str, str]] = [
            (p.tipo, p.nome, p.rotulo) for p in self._pistas
        ]
        for ef in self._efeitos:
            itens.append(("efeito", ef.nome, f"[FX] {ef.nome}"))
        if self._tem_estimulos:
            itens.append(("estimulos", "Estímulos", "Estímulos"))
        return itens

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Seleciona pista ou alterna botões S/M na linha clicada."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if pos.y() <= ALTURA_REGUA:
            return
        idx = int((pos.y() - ALTURA_REGUA + self._scroll_y) // ALTURA_LINHA)
        linhas = self._listar_linhas()
        if not (0 <= idx < len(linhas)):
            return
        tipo, nome, _ = linhas[idx]
        if tipo == "junta":
            if pos.x() >= self.width() - 48 and pos.x() <= self.width() - 30:
                self.solo_alternado.emit(nome)
                return
            if pos.x() >= self.width() - 26 and pos.x() <= self.width() - 8:
                self.mudo_alternado.emit(nome)
                return
            self.pista_clicada.emit(nome)
        elif tipo == "efeito":
            self.efeito_clicado.emit(nome)


class _CanvasTimeline(QWidget):
    """Área desenhada da régua temporal, chaves, janelas de efeito e estímulos."""

    cursor_movido = Signal(float)
    chave_selecionada = Signal(str, int, list)
    chave_movida_preview = Signal(str, int, float)
    chave_movida_confirmada = Signal(str, int, float)
    chave_duplo_clique = Signal(str, float)
    efeito_selecionado = Signal(str)
    efeito_janela_preview = Signal(str, float, float)
    efeito_janela_confirmada = Signal(str, float, float)
    estimulo_movido_confirmado = Signal(int, float)
    zoom_scroll_alterado = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(130)
        self.setMouseTracking(True)
        self._pistas: list[PistaVisual] = []
        self._efeitos: list[FaixaEfeitoVisual] = []
        self._estimulos: list[EstimuloRoteiro] = []
        self._tempo_s = 0.0
        self._duracao_s = 4.0
        self._fps = 60
        self._bpm = 108.0
        self._mostrar_batidas = False
        self._snap = "livre"
        self._px_por_s = 120.0
        self._offset_x = 0.0
        self._scroll_y = 0
        self._pista_sel = ""
        self._efeito_sel = ""
        self._chaves_sel: list[tuple[str, int]] = []
        self._arraste: _ArrasteItem | None = None

    def definir_conteudo(
        self,
        pistas: list[PistaVisual],
        efeitos: list[FaixaEfeitoVisual],
        estimulos: list[EstimuloRoteiro],
    ) -> None:
        """Atualiza dados das pistas, trechos de VFX e marcadores de estímulo."""
        self._pistas = list(pistas)
        self._efeitos = list(efeitos)
        self._estimulos = list(estimulos)
        self.update()

    def definir_estado_tempo(
        self,
        *,
        tempo_s: float,
        duracao_s: float,
        fps: int,
        bpm: float,
        mostrar_batidas: bool,
        snap: str,
    ) -> None:
        """Sincroniza cursor, taxa de quadros, grade de batidas e modo de snap."""
        self._tempo_s = float(tempo_s)
        self._duracao_s = max(0.05, float(duracao_s))
        self._fps = max(1, int(fps))
        self._bpm = max(30.0, float(bpm))
        self._mostrar_batidas = mostrar_batidas
        self._snap = snap
        self.update()

    def definir_selecao(
        self,
        *,
        pista: str,
        efeito: str,
        chaves_sel: list[tuple[str, int]],
    ) -> None:
        """Define os itens atualmente destacados no canvas."""
        self._pista_sel = pista
        self._efeito_sel = efeito
        self._chaves_sel = list(chaves_sel)
        self.update()

    def definir_scroll(self, offset_x: float, scroll_y: int) -> None:
        """Atualiza deslocamentos de rolagem sem emitir loop."""
        self._offset_x = max(0.0, float(offset_x))
        self._scroll_y = max(0, int(scroll_y))
        self.update()

    def aplicar_snap(self, tempo_s: float, *, ignorar_pista: str = "") -> float:
        """Alinha ``tempo_s`` segundo o modo de snap ativo (Quadro/Chave/Batida)."""
        t = max(0.0, min(self._duracao_s, tempo_s))
        if self._snap == "quadro":
            return round(round(t * self._fps) / self._fps, 4)
        if self._snap == "batida":
            pas_b = 60.0 / self._bpm
            return round(round(t / pas_b) * pas_b, 4)
        if self._snap == "chave":
            return self._snap_chave_proxima(t, ignorar_pista)
        return round(t, 4)

    def _snap_chave_proxima(self, tempo_s: float, ignorar_pista: str) -> float:
        limiar_s = 10.0 / max(1.0, self._px_por_s)
        melhor = tempo_s
        menor_dist = limiar_s
        for p in self._pistas:
            if p.nome == ignorar_pista:
                continue
            for kt, _ in p.chaves:
                dist = abs(kt - tempo_s)
                if dist <= menor_dist:
                    menor_dist = dist
                    melhor = kt
        return round(melhor, 4)

    def _tempo_para_x(self, tempo_s: float) -> float:
        return 12.0 + tempo_s * self._px_por_s - self._offset_x

    def _x_para_tempo(self, x_px: float) -> float:
        return max(0.0, min(self._duracao_s, (x_px - 12.0 + self._offset_x) / self._px_por_s))

    def paintEvent(self, _event: QPaintEvent) -> None:
        """Renderiza faixas, losangos, janelas de efeito, estímulos, régua e cursor."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setFont(fonte_tabular(9))
        painter.fillRect(self.rect(), QColor(COR_FUNDO))
        self._desenhar_grade_fundo(painter)
        self._desenhar_pistas(painter)
        self._desenhar_efeitos(painter)
        self._desenhar_estimulos(painter)
        self._desenhar_regua(painter)
        self._desenhar_playhead(painter)

    def _desenhar_grade_fundo(self, painter: QPainter) -> None:
        x_fim = self._tempo_para_x(self._duracao_s)
        if x_fim > 0.0:
            painter.fillRect(
                QRectF(self._tempo_para_x(0.0), float(ALTURA_REGUA), x_fim - self._tempo_para_x(0.0), float(self.height())),
                QColor(COR_PAINEL),
            )
        if self._mostrar_batidas or self._snap == "batida":
            pas_b = 60.0 / self._bpm
            b = 0.0
            painter.setPen(QPen(QColor("#2F3846"), 1.0, Qt.PenStyle.DotLine))
            while b <= self._duracao_s + 0.01:
                x = self._tempo_para_x(b)
                if 0.0 <= x <= self.width():
                    painter.drawLine(int(x), ALTURA_REGUA, int(x), self.height())
                b += pas_b

    def _desenhar_pistas(self, painter: QPainter) -> None:
        for idx, pista in enumerate(self._pistas):
            y = ALTURA_REGUA + idx * ALTURA_LINHA - self._scroll_y
            if y + ALTURA_LINHA < ALTURA_REGUA or y > self.height():
                continue
            self._desenhar_linha_pista(painter, pista, y, idx)

    def _desenhar_linha_pista(
        self,
        painter: QPainter,
        pista: PistaVisual,
        y: int,
        _idx: int,
    ) -> None:
        cy = y + ALTURA_LINHA * 0.5
        if pista.nome == self._pista_sel:
            painter.fillRect(
                QRectF(0.0, float(y), float(self.width()), float(ALTURA_LINHA)),
                QColor("#232B35"),
            )
        painter.setPen(QColor("#2D3137"))
        painter.drawLine(0, y + ALTURA_LINHA - 1, self.width(), y + ALTURA_LINHA - 1)
        if not pista.chaves:
            return
        x0 = self._tempo_para_x(pista.chaves[0][0])
        x1 = self._tempo_para_x(pista.chaves[-1][0])
        painter.setPen(QColor("#4F5762"))
        painter.drawLine(int(x0), int(cy), int(x1), int(cy))
        for k_idx, (t, _) in enumerate(pista.chaves):
            x = self._tempo_para_x(t)
            if x < -8 or x > self.width() + 8:
                continue
            sel = (pista.nome, k_idx) in self._chaves_sel
            painter.setBrush(QColor(COR_DESTAQUE if sel else "#C8D0DA"))
            painter.setPen(QPen(QColor("#FFFFFF" if sel else "#16181B"), 1.2))
            painter.drawPolygon(_poligono_losango(x, cy, 5.2 if sel else 4.2))

    def _desenhar_efeitos(self, painter: QPainter) -> None:
        base_idx = len(self._pistas)
        for off, ef in enumerate(self._efeitos):
            y = ALTURA_REGUA + (base_idx + off) * ALTURA_LINHA - self._scroll_y
            if y + ALTURA_LINHA < ALTURA_REGUA or y > self.height():
                continue
            x0 = self._tempo_para_x(ef.inicio_s)
            x1 = max(x0 + 8.0, self._tempo_para_x(ef.fim_s))
            ret = QRectF(x0, float(y + 4), x1 - x0, float(ALTURA_LINHA - 8))
            sel = ef.nome == self._efeito_sel
            painter.setBrush(QColor("#29537E" if sel else "#364659"))
            painter.setPen(QPen(QColor(COR_DESTAQUE if sel else "#7B93AC"), 1.4))
            painter.drawRoundedRect(ret, 4.0, 4.0)
            painter.setPen(QColor(COR_TEXTO))
            if ret.width() >= 28:
                painter.drawText(
                    ret.adjusted(4, 0, -4, 0),
                    Qt.AlignmentFlag.AlignCenter,
                    ef.nome,
                )

    def _desenhar_estimulos(self, painter: QPainter) -> None:
        idx = len(self._pistas) + len(self._efeitos)
        y = ALTURA_REGUA + idx * ALTURA_LINHA - self._scroll_y
        if y + ALTURA_LINHA < ALTURA_REGUA or y > self.height():
            return
        painter.setPen(QColor("#2D3137"))
        painter.drawLine(0, y + ALTURA_LINHA - 1, self.width(), y + ALTURA_LINHA - 1)
        cy = y + ALTURA_LINHA * 0.5
        for est in self._estimulos:
            x = self._tempo_para_x(est.tempo_s)
            painter.setBrush(QColor("#E5A93C"))
            painter.setPen(QPen(QColor("#1A1C1E"), 1.0))
            painter.drawPolygon(_poligono_losango(x, cy, 4.8))
            painter.setPen(QColor("#F0C875"))
            painter.drawText(int(x + 8), y + 16, est.tipo)

    def _desenhar_regua(self, painter: QPainter) -> None:
        painter.fillRect(0, 0, self.width(), ALTURA_REGUA, QColor(COR_PAINEL_ALT))
        painter.setPen(QColor(COR_BORDA))
        painter.drawLine(0, ALTURA_REGUA, self.width(), ALTURA_REGUA)
        passo = 0.5 if self._px_por_s >= 150.0 else 1.0
        t = 0.0
        while t <= self._duracao_s + 0.01:
            x = self._tempo_para_x(t)
            if -20.0 <= x <= self.width():
                painter.setPen(QColor("#5C646E"))
                painter.drawLine(int(x), 14, int(x), ALTURA_REGUA)
                painter.setPen(QColor(COR_TEXTO_SUAVE))
                painter.drawText(int(x + 3), 13, f"{t:g} s")
            t += passo

    def _desenhar_playhead(self, painter: QPainter) -> None:
        x = self._tempo_para_x(self._tempo_s)
        if x < 0.0 or x > self.width():
            return
        painter.setBrush(QColor(COR_DESTAQUE))
        painter.setPen(QPen(QColor(COR_DESTAQUE), 1.6))
        painter.drawLine(int(x), 0, int(x), self.height())
        cabeca = QPolygonF(
            [
                QPointF(x - 5.0, 0.0),
                QPointF(x + 5.0, 0.0),
                QPointF(x, 8.0),
            ],
        )
        painter.drawPolygon(cabeca)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Inicia arraste de régua, chave, janela de efeito ou marcador."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if pos.y() <= ALTURA_REGUA:
            self._arraste = _ArrasteItem("cursor", "", -1, self._x_para_tempo(pos.x()))
            self.cursor_movido.emit(self._x_para_tempo(pos.x()))
            return
        if self._tentar_pegar_item(pos.x(), pos.y(), event.modifiers()):
            return
        self._arraste = _ArrasteItem("cursor", "", -1, self._x_para_tempo(pos.x()))
        self.cursor_movido.emit(self._x_para_tempo(pos.x()))

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Duplo clique em uma pista de junta solicita inserção de chave no ponto."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if pos.y() <= ALTURA_REGUA:
            return
        idx = int((pos.y() - ALTURA_REGUA + self._scroll_y) // ALTURA_LINHA)
        if 0 <= idx < len(self._pistas):
            pista = self._pistas[idx]
            if pista.tipo == "junta":
                tempo = self.aplicar_snap(
                    self._x_para_tempo(pos.x()),
                    ignorar_pista=pista.nome,
                )
                self.chave_duplo_clique.emit(pista.nome, tempo)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Atualiza arraste ao vivo do elemento selecionado ou do cursor."""
        if self._arraste is None:
            return
        self._processar_arraste(event.position(), event.modifiers(), confirmar=False)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Confirma o arraste finalizado para gravar um único comando de desfazer."""
        if self._arraste is None:
            return
        self._processar_arraste(event.position(), event.modifiers(), confirmar=True)
        self._arraste = None

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom horizontal com Ctrl ou rolagem vertical/horizontal."""
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            fator = 1.15 if delta > 0 else 1 / 1.15
            self._px_por_s = max(30.0, min(600.0, self._px_por_s * fator))
            self.zoom_scroll_alterado.emit(self._px_por_s, self._offset_x)
            self.update()
            return
        self.zoom_scroll_alterado.emit(
            self._px_por_s,
            max(0.0, self._offset_x - delta * 0.25),
        )

    def _tentar_pegar_item(
        self,
        x_px: float,
        y_px: float,
        mod: Qt.KeyboardModifier,
    ) -> bool:
        linha = int((y_px - ALTURA_REGUA + self._scroll_y) // ALTURA_LINHA)
        if 0 <= linha < len(self._pistas):
            return self._pegar_chave_na_linha(self._pistas[linha], x_px, mod)
        eff_idx = linha - len(self._pistas)
        if 0 <= eff_idx < len(self._efeitos):
            return self._pegar_efeito(self._efeitos[eff_idx], x_px)
        if eff_idx == len(self._efeitos):
            return self._pegar_estimulo(x_px)
        return False

    def _pegar_chave_na_linha(
        self,
        pista: PistaVisual,
        x_px: float,
        mod: Qt.KeyboardModifier,
    ) -> bool:
        for k_idx, (kt, _) in enumerate(pista.chaves):
            if abs(self._tempo_para_x(kt) - x_px) <= 8.0:
                par = (pista.nome, k_idx)
                estender = bool(
                    mod & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier),
                )
                nova_sel = list(self._chaves_sel) if estender else []
                if par not in nova_sel:
                    nova_sel.append(par)
                self._chaves_sel = nova_sel
                self._pista_sel = pista.nome
                self._arraste = _ArrasteItem("chave", pista.nome, k_idx, kt, x_inicial_px=x_px)
                self.chave_selecionada.emit(pista.nome, k_idx, nova_sel)
                self.update()
                return True
        return False

    def _pegar_efeito(self, ef: FaixaEfeitoVisual, x_px: float) -> bool:
        x0 = self._tempo_para_x(ef.inicio_s)
        x1 = max(x0 + 8.0, self._tempo_para_x(ef.fim_s))
        if not (x0 - 5.0 <= x_px <= x1 + 5.0):
            return False
        modo = "efeito_mover"
        if abs(x_px - x0) <= 6.0:
            modo = "efeito_ini"
        elif abs(x_px - x1) <= 6.0:
            modo = "efeito_fim"
        self._efeito_sel = ef.nome
        self._arraste = _ArrasteItem(
            modo,
            ef.nome,
            -1,
            ef.inicio_s,
            ini_orig=ef.inicio_s,
            fim_orig=ef.fim_s,
            x_inicial_px=x_px,
        )
        self.efeito_selecionado.emit(ef.nome)
        self.update()
        return True

    def _pegar_estimulo(self, x_px: float) -> bool:
        for idx, est in enumerate(self._estimulos):
            if abs(self._tempo_para_x(est.tempo_s) - x_px) <= 9.0:
                self._arraste = _ArrasteItem("estimulo", est.tipo, idx, est.tempo_s)
                return True
        return False

    def _processar_arraste(
        self,
        pos: QPointF,
        mod: Qt.KeyboardModifier,
        *,
        confirmar: bool,
    ) -> None:
        arr = self._arraste
        assert arr is not None
        sem_snap = bool(mod & Qt.KeyboardModifier.AltModifier)
        t_bruto = self._x_para_tempo(pos.x())
        t_snap = round(t_bruto, 4) if sem_snap else self.aplicar_snap(t_bruto, ignorar_pista=arr.alvo)
        if arr.modo == "cursor":
            self.cursor_movido.emit(t_bruto)
            return
        if arr.modo == "chave":
            sin = self.chave_movida_confirmada if confirmar else self.chave_movida_preview
            sin.emit(arr.alvo, arr.indice, t_snap)
            return
        if arr.modo == "estimulo" and confirmar:
            self.estimulo_movido_confirmado.emit(arr.indice, t_snap)
            return
        self._processar_arraste_efeito(arr, pos.x(), t_snap, confirmar=confirmar)

    def _processar_arraste_efeito(
        self,
        arr: _ArrasteItem,
        x_px: float,
        t_snap: float,
        *,
        confirmar: bool,
    ) -> None:
        ini, fim = arr.ini_orig, arr.fim_orig
        dur = max(0.05, fim - ini)
        if arr.modo == "efeito_mover":
            dt = (x_px - arr.x_inicial_px) / max(1.0, self._px_por_s)
            novo_ini = max(0.0, min(self._duracao_s - dur, ini + dt))
            ini = round(novo_ini, 4)
            fim = round(ini + dur, 4)
        elif arr.modo == "efeito_ini":
            ini = max(0.0, min(fim - 0.05, t_snap))
        elif arr.modo == "efeito_fim":
            fim = min(self._duracao_s, max(ini + 0.05, t_snap))
        else:
            return
        sinal = self.efeito_janela_confirmada if confirmar else self.efeito_janela_preview
        sinal.emit(arr.alvo, ini, fim)


class PainelTimeline(QWidget):
    """Área inferior completa da timeline com transporte, pistas, efeitos e curvas."""

    cursor_movido = Signal(float)
    chave_selecionada = Signal(str, int, list)
    chave_movida_preview = Signal(str, int, float)
    chave_movida_confirmada = Signal(str, int, float)
    chave_curva_movida_preview = Signal(str, int, float, tuple)
    chave_curva_movida_confirmada = Signal(str, int, float, tuple)
    chave_inserir_em = Signal(str, float)
    efeito_selecionado = Signal(str)
    efeito_janela_preview = Signal(str, float, float)
    efeito_janela_confirmada = Signal(str, float, float)
    estimulo_movido = Signal(int, float)
    solo_alternado = Signal(str)
    mudo_alternado = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa barra de transporte, cabeçalhos fixos, canvas e gráfico de curvas."""
        super().__init__(parent)
        self.setObjectName("painelTimeline")
        self.setMinimumHeight(175)
        self._snap = "livre"
        self._px_por_s = 120.0
        self._duracao_s = 4.0

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self.transporte = BarraTransporte(self)
        self.transporte.snap_alterado.connect(self._on_snap_mudou)
        self.transporte.curvas_alternadas.connect(self._on_alternar_curvas)
        raiz.addWidget(self.transporte)

        self._pilha = QStackedWidget(self)
        self._pilha.addWidget(self._criar_pagina_pistas())
        self.curvas = self._criar_painel_curvas()
        self._pilha.addWidget(self.curvas)
        raiz.addWidget(self._pilha, 1)

    def _criar_pagina_pistas(self) -> QWidget:
        pagina = QWidget(self)
        vbox = QVBoxLayout(pagina)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        corpo = QHBoxLayout()
        corpo.setContentsMargins(0, 0, 0, 0)
        corpo.setSpacing(0)
        self._cabecalhos = _CabecalhosPistas(pagina)
        self._canvas = _CanvasTimeline(pagina)
        self._conectar_canvas_e_cabecalhos()

        self._scroll_v = QScrollBar(Qt.Orientation.Vertical, pagina)
        self._scroll_v.valueChanged.connect(self._on_scroll_v)
        corpo.addWidget(self._cabecalhos)
        corpo.addWidget(self._canvas, 1)
        corpo.addWidget(self._scroll_v)
        vbox.addLayout(corpo, 1)

        self._scroll_h = QScrollBar(Qt.Orientation.Horizontal, pagina)
        self._scroll_h.valueChanged.connect(self._on_scroll_h)
        vbox.addWidget(self._scroll_h)
        return pagina

    def _criar_painel_curvas(self) -> PainelCurvas:
        curvas = PainelCurvas(self)
        curvas.definir_snap(lambda t: self._canvas.aplicar_snap(t))
        curvas.cursor_movido.connect(self.cursor_movido.emit)
        curvas.chave_movida_preview.connect(self.chave_curva_movida_preview.emit)
        curvas.chave_movida_confirmada.connect(self.chave_curva_movida_confirmada.emit)
        curvas.zoom_alterado.connect(self._on_zoom_mudou)
        return curvas

    def _conectar_canvas_e_cabecalhos(self) -> None:
        self._cabecalhos.pista_clicada.connect(
            lambda g: self.chave_selecionada.emit(g, -1, []),
        )
        self._cabecalhos.solo_alternado.connect(self.solo_alternado.emit)
        self._cabecalhos.mudo_alternado.connect(self.mudo_alternado.emit)
        self._cabecalhos.efeito_clicado.connect(self.efeito_selecionado.emit)

        self._canvas.cursor_movido.connect(self.cursor_movido.emit)
        self._canvas.chave_selecionada.connect(self.chave_selecionada.emit)
        self._canvas.chave_movida_preview.connect(self.chave_movida_preview.emit)
        self._canvas.chave_movida_confirmada.connect(self.chave_movida_confirmada.emit)
        self._canvas.chave_duplo_clique.connect(self.chave_inserir_em.emit)
        self._canvas.efeito_selecionado.connect(self.efeito_selecionado.emit)
        self._canvas.efeito_janela_preview.connect(self.efeito_janela_preview.emit)
        self._canvas.efeito_janela_confirmada.connect(self.efeito_janela_confirmada.emit)
        self._canvas.estimulo_movido_confirmado.connect(self.estimulo_movido.emit)
        self._canvas.zoom_scroll_alterado.connect(self._on_zoom_scroll_canvas)

    def carregar_conteudo(
        self,
        *,
        pistas: list[PistaVisual],
        efeitos: list[FaixaEfeitoVisual],
        estimulos: list[EstimuloRoteiro],
        pista_ativa: str,
        efeito_ativo: str = "",
        chaves_selecionadas: list[tuple[str, int]] | None = None,
        solo: str | None = None,
        silenciadas: set[str] | None = None,
    ) -> None:
        """Atualiza todas as pistas visíveis na timeline e no gráfico de curvas."""
        self._cabecalhos.definir_conteudo(
            pistas,
            efeitos,
            selecionada=pista_ativa,
            solo=solo,
            silenciadas=silenciadas or set(),
        )
        self._canvas.definir_conteudo(pistas, efeitos, estimulos)
        self._canvas.definir_selecao(
            pista=pista_ativa,
            efeito=efeito_ativo,
            chaves_sel=list(chaves_selecionadas or []),
        )
        pista_curva = next((p for p in pistas if p.nome == pista_ativa), None)
        if pista_curva is not None:
            self.curvas.carregar_pista(
                pista_curva.nome,
                pista_curva.chaves,
                pista_curva.curvas,
            )
        elif pistas:
            self.curvas.carregar_pista(pistas[0].nome, pistas[0].chaves, pistas[0].curvas)
        self._atualizar_limites_scroll()

    def atualizar_tempo(
        self,
        *,
        tempo_s: float,
        duracao_s: float,
        quadro_idx: int,
        fps: int,
        bpm: float,
        batida_ativa: bool,
        mostrar_batidas: bool,
    ) -> None:
        """Sincroniza agulha temporal, leitura numérica e visualização de batidas."""
        self._duracao_s = max(0.05, float(duracao_s))
        self.transporte.atualizar_leitura(
            tempo_s,
            quadro_idx,
            batida_ativa=batida_ativa,
            mostrar_batida=mostrar_batidas or self._snap == "batida",
            bpm=bpm,
        )
        self._canvas.definir_estado_tempo(
            tempo_s=tempo_s,
            duracao_s=self._duracao_s,
            fps=fps,
            bpm=bpm,
            mostrar_batidas=mostrar_batidas,
            snap=self._snap,
        )
        self.curvas.definir_tempo(tempo_s, self._duracao_s)
        self._atualizar_limites_scroll()

    def alternar_curvas(self, ativo: bool) -> None:
        """Alterna entre as pistas horizontais e o gráfico de curvas no mesmo cursor."""
        self.transporte.definir_modo_curvas(ativo)
        self._pilha.setCurrentIndex(1 if ativo else 0)

    def _on_alternar_curvas(self, ativo: bool) -> None:
        self._pilha.setCurrentIndex(1 if ativo else 0)

    def _on_snap_mudou(self, snap: str) -> None:
        self._snap = snap
        self.curvas.definir_snap(lambda t: self._canvas.aplicar_snap(t))

    def _on_scroll_v(self, valor: int) -> None:
        self._cabecalhos.definir_scroll_y(valor)
        self._canvas.definir_scroll(float(self._scroll_h.value()), valor)

    def _on_scroll_h(self, valor: int) -> None:
        self._canvas.definir_scroll(float(valor), self._scroll_v.value())
        self.curvas.definir_zoom_e_scroll(self._px_por_s, float(valor))

    def _on_zoom_scroll_canvas(self, px_por_s: float, offset_x: float) -> None:
        self._px_por_s = px_por_s
        self._atualizar_limites_scroll()
        self._scroll_h.setValue(int(offset_x))
        self.curvas.definir_zoom_e_scroll(px_por_s, offset_x)

    def _on_zoom_mudou(self, px_por_s: float) -> None:
        self._px_por_s = px_por_s
        self._canvas._px_por_s = px_por_s
        self._canvas.update()
        self._atualizar_limites_scroll()

    def _atualizar_limites_scroll(self) -> None:
        alt_total = self._cabecalhos.total_linhas() * ALTURA_LINHA + ALTURA_REGUA
        excesso_v = max(0, alt_total - max(1, self._canvas.height()))
        self._scroll_v.setRange(0, excesso_v)
        larg_total = int(self._duracao_s * self._px_por_s) + 80
        excesso_h = max(0, larg_total - max(1, self._canvas.width()))
        self._scroll_h.setRange(0, excesso_h)


def construir_pistas_para_acao(
    acao_tipo: str,
    bloco: dict[str, object],
    *,
    acao_chave: str = "",
) -> tuple[list[PistaVisual], list[FaixaEfeitoVisual]]:
    """Converte chaves e janelas autorais da ação atual em pistas na timeline."""
    if acao_tipo == "pistas_3d":
        return _pistas_de_cena_3d(bloco)
    if acao_tipo == "respiracao":
        raw_ciclo = bloco.get("ciclo", ())
        curvas = bloco.get("ciclo_curvas", ())
        if isinstance(raw_ciclo, (tuple, list)) and raw_ciclo:
            chaves = tuple(
                (float(t), (float(v[0]), float(v[1]), float(v[2])))
                for t, v in raw_ciclo
            )
            return [
                PistaVisual(
                    nome="ciclo",
                    rotulo="Ciclo de respiração",
                    chaves=chaves,
                    curvas=tuple(curvas) if isinstance(curvas, (tuple, list)) else (),
                    tipo="curva",
                ),
            ], []
    if acao_tipo == "vfx":
        dur_raw = bloco.get("duracao_s")
        dur = float(dur_raw) if isinstance(dur_raw, (int, float)) else 0.5
        return [], [FaixaEfeitoVisual(nome=acao_chave or "efeito", inicio_s=0.0, fim_s=dur)]
    if acao_tipo in {"gltf", "danca_clipe"}:
        ini_raw = bloco.get("inicio_s")
        ini = float(ini_raw) if isinstance(ini_raw, (int, float)) else 0.0
        fim_raw = bloco.get("fim_s")
        fim = float(fim_raw) if isinstance(fim_raw, (int, float)) else max(ini + 2.0, 2.0)
        return [], [FaixaEfeitoVisual(nome=acao_chave or "clipe", inicio_s=ini, fim_s=fim)]
    return [], []


def _pistas_de_cena_3d(
    bloco: dict[str, object],
) -> tuple[list[PistaVisual], list[FaixaEfeitoVisual]]:
    pistas: list[PistaVisual] = []
    efeitos: list[FaixaEfeitoVisual] = []
    tracks = bloco.get("tracks")
    curvas = bloco.get("curvas")
    if isinstance(tracks, dict):
        for nome in sorted(tracks.keys()):
            raw_chaves = tracks[nome]
            raw_curvas = curvas.get(nome, ()) if isinstance(curvas, dict) else ()
            pistas.append(
                PistaVisual(
                    nome=nome,
                    rotulo=nome_amigavel_junta(nome),
                    chaves=tuple(raw_chaves),
                    curvas=tuple(raw_curvas),
                    tipo="junta",
                ),
            )
    janelas = bloco.get("janelas_efeito")
    if isinstance(janelas, dict):
        for nome, par in sorted(janelas.items()):
            efeitos.append(
                FaixaEfeitoVisual(nome=nome, inicio_s=float(par[0]), fim_s=float(par[1])),
            )
    return pistas, efeitos
