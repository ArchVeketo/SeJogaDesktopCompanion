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


def project_root() -> Path:
    """Raiz do projeto em dev; ``sys._MEIPASS`` quando congelado."""
    if hasattr(sys, "_MEIPASS"):  # PyInstaller onefile
        return Path(sys._MEIPASS)
    # src/sejoga/assets.py -> src/sejoga -> src -> raiz
    return _PACKAGE_DIR.parents[1]


def assets_dir() -> Path:
    """Diretório ``assets`` (ou o bundle embutido, quando empacotado)."""
    bundled = _PACKAGE_DIR / "_bundled_assets"
    if bundled.is_dir():
        return bundled
    return project_root() / "assets"


def model_dir() -> Path:
    return assets_dir() / "model"


def brand_dir() -> Path:
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
    return model_dir() / name
