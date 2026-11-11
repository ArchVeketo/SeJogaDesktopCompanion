#!/usr/bin/env python3
"""Ponto de entrada do executável do SeJogaDesktopCompanion.

Funciona em desenvolvimento e empacotado pelo PyInstaller.
"""

import sys
from pathlib import Path


def main():
    """Inicia o companion e devolve o código de saída."""
    # Caminhos do bundle antes dos imports do sejoga (por isso imports locais).
    if getattr(sys, "frozen", False):
        # PyInstaller bundle
        bundle_dir = Path(sys._MEIPASS)
        if str(bundle_dir) not in sys.path:
            sys.path.insert(0, str(bundle_dir))
        # Add _internal directory
        internal_dir = Path(sys.executable).parent / "_internal"
        if internal_dir.exists() and str(internal_dir) not in sys.path:
            sys.path.insert(0, str(internal_dir))

    from sejoga.__main__ import run

    return run()


if __name__ == "__main__":
    sys.exit(main())
