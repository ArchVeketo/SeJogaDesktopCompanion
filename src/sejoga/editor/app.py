"""Ponto de entrada desktop do Editor do Mário (``sejoga editor``)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sejoga-editor",
        description="Editor desktop de autoria e ensaio de animações do Mário.",
    )
    parser.add_argument(
        "--acao",
        default=None,
        help="ID da ação inicial a abrir (ex.: cenas_idle:fone_com_problema).",
    )
    parser.add_argument(
        "--sem-gpu",
        action="store_true",
        help="Abre a interface sem inicializar janela OpenGL/Panda3D embutida.",
    )
    parser.add_argument(
        "--arquivo",
        default=None,
        help="Caminho alternativo para animation.py (isolamento ou rascunho).",
    )
    return parser


def executar_editor(
    argv: list[str] | None = None,
    *,
    exibir_e_rodar: bool = True,
) -> int:
    """Inicializa Qt com política HiDPI e abre a janela principal do editor."""
    # PySide6 precisa carregar antes de qualquer import que toque Panda3D no Windows.
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough,
    )
    args = _build_parser().parse_args(argv)
    qt_app = QApplication.instance()
    if not isinstance(qt_app, QApplication):
        qt_app = QApplication([sys.argv[0]])

    from sejoga.editor.documento import DocumentoEditor
    from sejoga.editor.janela_editor import JanelaEditor
    from sejoga.editor.persistencia import carregar_arquivo_animacao
    from sejoga.editor.tema import configurar_aplicacao_qt

    configurar_aplicacao_qt(qt_app)
    arquivo = carregar_arquivo_animacao(Path(args.arquivo)) if args.arquivo else None
    doc = DocumentoEditor(arquivo)
    janela = JanelaEditor(
        doc,
        habilitar_gpu=not args.sem_gpu,
    )
    if args.acao:
        janela.abrir_acao(str(args.acao), confirmar=False)
    if not exibir_e_rodar:
        janela.close()
        return 0
    janela.show()
    return int(qt_app.exec())


def main(argv: list[str] | None = None) -> int:
    """Função CLI do ponto de entrada ``sejoga-editor``."""
    return executar_editor(argv, exibir_e_rodar=True)


if __name__ == "__main__":
    raise SystemExit(main())
