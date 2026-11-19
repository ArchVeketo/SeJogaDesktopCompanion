"""Tema escuro, tipografia tabular e preferências persistentes da UI do editor."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from sejoga.configuracao import default_config_path

COR_FUNDO = "#1A1C1E"
COR_PAINEL = "#222528"
COR_PAINEL_ALT = "#2A2D32"
COR_BORDA = "#363A40"
COR_TEXTO = "#E8EAED"
COR_TEXTO_SUAVE = "#9AA0A6"
COR_DESTAQUE = "#4EA1FF"
COR_DESTAQUE_FUNDO = "#20344A"
COR_SUCESSO = "#57C785"
COR_AVISO = "#E5A93C"
COR_ERRO = "#E06C75"

_QSS_TEMPLATE = """
QMainWindow, QDialog {
    background-color: %(fundo)s;
    color: %(texto)s;
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: 12px;
}
QWidget {
    color: %(texto)s;
    font-family: "Inter", "Segoe UI", sans-serif;
}
QFrame#barraSuperior, QFrame#barraCamera {
    background-color: %(painel)s;
    border-bottom: 1px solid %(borda)s;
}
QFrame#bannerErro {
    background-color: #3A2226;
    border: 1px solid %(erro)s;
    border-radius: 4px;
    padding: 4px 8px;
}
QFrame#bannerToast {
    background-color: #1F352A;
    border: 1px solid %(sucesso)s;
    border-radius: 4px;
    padding: 3px 10px;
}
QFrame#bannerProvisoria {
    background-color: #382E1D;
    border: 1px solid %(aviso)s;
    border-radius: 4px;
    padding: 3px 8px;
}
QSplitter::handle {
    background-color: %(borda)s;
}
QSplitter::handle:hover, QSplitter::handle:pressed {
    background-color: %(destaque)s;
}
QTreeWidget, QListWidget, QScrollArea {
    background-color: %(painel)s;
    border: 1px solid %(borda)s;
    border-radius: 4px;
}
QTreeWidget::item, QListWidget::item {
    padding: 4px 6px;
    border-radius: 3px;
}
QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: %(destaque_fundo)s;
    border: 1px solid %(destaque)s;
    color: %(texto)s;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: %(painel_alt)s;
    border: 1px solid %(borda)s;
    border-radius: 4px;
    padding: 3px 6px;
    min-height: 22px;
    selection-background-color: %(destaque)s;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPushButton:focus, QToolButton:focus, QTreeWidget:focus {
    border: 1px solid %(destaque)s;
    outline: none;
}
QPushButton, QToolButton {
    background-color: %(painel_alt)s;
    border: 1px solid %(borda)s;
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 24px;
}
QPushButton:hover, QToolButton:hover {
    background-color: #32363C;
    border-color: #4A5058;
}
QPushButton:checked, QToolButton:checked {
    background-color: %(destaque_fundo)s;
    border: 1px solid %(destaque)s;
    color: %(texto)s;
}
QPushButton:disabled, QToolButton:disabled {
    color: %(suave)s;
    background-color: %(painel)s;
}
QPushButton#btnSalvar {
    background-color: %(destaque_fundo)s;
    border: 1px solid %(destaque)s;
    font-weight: 600;
}
QPushButton#btnSalvar:hover {
    background-color: #2A496A;
}
QLabel#rotuloSuave, QLabel#badgePrioridade {
    color: %(suave)s;
}
QLabel#badgeAlterado {
    color: %(destaque)s;
    font-weight: 600;
}
QGroupBox {
    border: 1px solid %(borda)s;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: %(suave)s;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background: %(painel)s;
    border: none;
    width: 10px;
    height: 10px;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #42474F;
    border-radius: 4px;
    min-height: 24px;
    min-width: 24px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0px;
    height: 0px;
}
"""


def qss_tema_escuro() -> str:
    """Retorna a folha de estilos QSS completa no tema grafite escuro."""
    return _QSS_TEMPLATE % {
        "fundo": COR_FUNDO,
        "painel": COR_PAINEL,
        "painel_alt": COR_PAINEL_ALT,
        "borda": COR_BORDA,
        "texto": COR_TEXTO,
        "suave": COR_TEXTO_SUAVE,
        "destaque": COR_DESTAQUE,
        "destaque_fundo": COR_DESTAQUE_FUNDO,
        "sucesso": COR_SUCESSO,
        "aviso": COR_AVISO,
        "erro": COR_ERRO,
    }


def fonte_tabular(tamanho: int = 12, *, negrito: bool = False) -> QFont:
    """Cria fonte Inter (com fallback) usando algarismos tabulares."""
    fonte = QFont("Inter", tamanho)
    fonte.setStyleHint(QFont.StyleHint.SansSerif)
    fonte.setBold(negrito)
    return fonte


def configurar_aplicacao_qt(app: QApplication) -> None:
    """Aplica paleta grafite, fonte padrão e tema QSS na aplicação Qt."""
    app.setStyle("Fusion")
    app.setFont(fonte_tabular(10))
    paleta = QPalette()
    paleta.setColor(QPalette.ColorRole.Window, QColor(COR_FUNDO))
    paleta.setColor(QPalette.ColorRole.WindowText, QColor(COR_TEXTO))
    paleta.setColor(QPalette.ColorRole.Base, QColor(COR_PAINEL))
    paleta.setColor(QPalette.ColorRole.AlternateBase, QColor(COR_PAINEL_ALT))
    paleta.setColor(QPalette.ColorRole.Text, QColor(COR_TEXTO))
    paleta.setColor(QPalette.ColorRole.Button, QColor(COR_PAINEL_ALT))
    paleta.setColor(QPalette.ColorRole.ButtonText, QColor(COR_TEXTO))
    paleta.setColor(QPalette.ColorRole.Highlight, QColor(COR_DESTAQUE))
    paleta.setColor(QPalette.ColorRole.HighlightedText, QColor("#0E1318"))
    app.setPalette(paleta)
    app.setStyleSheet(qss_tema_escuro())


def aplicar_tema_widget(widget: QWidget) -> None:
    """Aplica a folha de estilos do editor localmente em ``widget``."""
    widget.setStyleSheet(qss_tema_escuro())
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


def caminho_preferencias_ui() -> Path:
    """Retorna o caminho do arquivo separado de layout e preferências do editor."""
    base_override = os.environ.get("SEJOGA_EDITOR_UI_PATH")
    if base_override:
        return Path(base_override)
    return default_config_path().parent / "editor_ui.json"


def carregar_preferencias_ui(caminho: Path | None = None) -> dict[str, Any]:
    """Carrega preferências visuais persistidas da janela sem falhar em arquivo ausente."""
    alvo = caminho or caminho_preferencias_ui()
    if not alvo.is_file():
        return {}
    try:
        dados = json.loads(alvo.read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def salvar_preferencias_ui(dados: dict[str, Any], caminho: Path | None = None) -> None:
    """Grava preferências de divisores e geometria do editor de forma segura."""
    alvo = caminho or caminho_preferencias_ui()
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(
            json.dumps(dados, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        return
