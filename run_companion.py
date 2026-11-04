#!/usr/bin/env python3
"""
Entry point for SeJogaDesktopCompanion executable.
Handles both development and frozen (PyInstaller) modes.
"""

import sys
import os
from pathlib import Path

def setup_frozen_paths():
    """Configure paths for PyInstaller frozen executable."""
    if getattr(sys, 'frozen', False):
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
        os.environ['SEJOGA_ASSETS_DIR'] = str(bundle_dir / "assets")
    else:
        # Development mode
        project_root = Path(__file__).parent.parent
        os.environ['SEJOGA_ASSETS_DIR'] = str(project_root / "assets")


def main():
    """Main entry point."""
    # Setup paths for frozen/development mode
    import sys
    from pathlib import Path

    if getattr(sys, 'frozen', False):
        # PyInstaller bundle
        bundle_dir = Path(sys._MEIPASS)
        if str(bundle_dir) not in sys.path:
            sys.path.insert(0, str(bundle_dir))
        # Add _internal directory
        internal_dir = Path(sys.executable).parent / "_internal"
        if internal_dir.exists() and str(internal_dir) not in sys.path:
            sys.path.insert(0, str(internal_dir))

    # Now run the app
    from sejoga.config import load_settings
    from sejoga.window import OverlayApp

    settings = load_settings()
    app = OverlayApp(settings)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
