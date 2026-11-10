#!/usr/bin/env python3
"""Ponto de entrada do executável do SeJogaDesktopCompanion.

Funciona em desenvolvimento e empacotado pelo PyInstaller.
"""

import os
import sys
from pathlib import Path


def setup_frozen_paths():
    """Configura os caminhos do executável empacotado pelo PyInstaller."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle
        bundle_dir = Path(sys._MEIPASS)
        # Add bundle directory to sys.path for imports
        if str(bundle_dir) not in sys.path:
            sys.path.insert(0, str(bundle_dir))
        # Also add _internal directory if it exists
        internal_dir = Path(sys.executable).parent / "_internal"
        if internal_dir.exists() and str(internal_dir) not in sys.path:
            sys.path.insert(0, str(internal_dir))
        # Set assets directory for frozen mode
        os.environ["SEJOGA_ASSETS_DIR"] = str(bundle_dir / "assets")
    else:
        # Development mode
        project_root = Path(__file__).parent.parent
        os.environ["SEJOGA_ASSETS_DIR"] = str(project_root / "assets")


def main():
    """Inicia o companion e devolve o código de saída."""
    # Caminhos do bundle antes dos imports do sejoga (por isso imports locais).
    import sys
    from pathlib import Path

    if getattr(sys, "frozen", False):
        # PyInstaller bundle
        bundle_dir = Path(sys._MEIPASS)
        if str(bundle_dir) not in sys.path:
            sys.path.insert(0, str(bundle_dir))
        # Add _internal directory
        internal_dir = Path(sys.executable).parent / "_internal"
        if internal_dir.exists() and str(internal_dir) not in sys.path:
            sys.path.insert(0, str(internal_dir))

    # Now run the app
    from sejoga.configuracao import load_settings
    from sejoga.render.window import OverlayApp

    settings = load_settings()
    app = OverlayApp(settings)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
