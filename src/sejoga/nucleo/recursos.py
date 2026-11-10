"""Resolução de caminhos de assets, em desenvolvimento e empacotado.

Regra de ouro: o código nunca monta caminhos relativos ao diretório de
trabalho. Sempre resolve a partir da raiz do projeto (dev) ou do diretório
temporário do PyInstaller (empacotado), porque o companion pode ser iniciado
pelo autostart do Windows com um ``cwd`` arbitrário.

Layout esperado::

    <raiz>/assets/
        model/            modelo principal (glTF/GLB) + texturas + fonte
        brand/            artes de referência e marca
        raw/              iterações antigas (V1..V3, OBJ)
"""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent

#: Nome-base do modelo principal, relativo a ``assets/model``.
DEFAULT_MODEL_STEM = "mario"

#: Extensões aceitas, em ordem de preferência (GLB é menor e autocontido).
MODEL_SUFFIXES = (".glb", ".gltf")


def _get_base_dir() -> Path:
    """Diretório base: raiz do projeto em dev, ou pasta do executável quando congelado."""
    # PyInstaller onefile: sys._MEIPASS existe
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        # PyInstaller onedir: executável em dist/SeJogaCompanion/, assets em _internal/assets
        return Path(sys.executable).parent / "_internal"
    # Desenvolvimento: src/sejoga/nucleo/recursos.py -> nucleo -> sejoga -> src -> raiz
    return _PACKAGE_DIR.parents[2]


def project_root() -> Path:
    """Raiz do projeto em dev; ``sys._MEIPASS`` quando congelado (onefile)."""
    return _get_base_dir()


def assets_dir() -> Path:
    """Diretório ``assets`` (ou o bundle embutido, quando empacotado)."""
    # Em desenvolvimento, pode haver um _bundled_assets local (em sejoga/, um
    # nivel acima deste modulo, que vive em sejoga/nucleo/).
    bundled = _PACKAGE_DIR.parent / "_bundled_assets"
    if bundled.is_dir():
        return bundled
    return _get_base_dir() / "assets"


def model_dir() -> Path:
    """Devolve a pasta dos modelos 3D."""
    return assets_dir() / "model"


def brand_dir() -> Path:
    """Devolve a pasta das imagens da marca."""
    return assets_dir() / "brand"


def resolve_model(stem: str = DEFAULT_MODEL_STEM) -> Path:
    """Retorna o primeiro arquivo de modelo existente para ``stem``.

    Prefere ``.glb`` (autocontido) e cai para ``.gltf`` se o derivado ainda não
    tiver sido gerado com ``python tools/gltf_to_glb.py``.

    Raises:
        FileNotFoundError: se nenhuma variante existir.
    """
    for suffix in MODEL_SUFFIXES:
        candidate = model_dir() / f"{stem}{suffix}"
        if candidate.is_file():
            return candidate
    tried = ", ".join(f"{stem}{s}" for s in MODEL_SUFFIXES)
    raise FileNotFoundError(
        f"modelo não encontrado em {model_dir()} (procurei por: {tried}). "
        "Rode 'python tools/gltf_to_glb.py assets/model/mario.gltf'."
    )


def texture_path(name: str = "Textura.png") -> Path:
    """Devolve o caminho da textura com o nome dado."""
    return model_dir() / name
