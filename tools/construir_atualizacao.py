"""Empacota o aplicativo independente do instalador estável do Windows."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
import tomllib
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sejoga.distribuicao.atualizador import ReleaseInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# sejoga só importa depois do sys.path acima: import_module evita o E402.
_atualizador = importlib.import_module("sejoga.distribuicao.atualizador")


ASSETS_CAIXAS_DE_SOM = {
    "_internal/assets/assets/boomboxgrande/BoomboxGRANDE.bbmodel",
    "_internal/assets/assets/BoomboxSIde1.bbmodel",
    "_internal/assets/assets/boomboxgrande/texture.png",
    "_internal/assets/assets/texture.png",
}


def build_package(bundle: Path, output: Path, info: ReleaseInfo) -> dict:
    """Empacota o bundle em zip e devolve o manifesto do pacote."""
    if info.build_id <= 0:
        raise ValueError("Build ID deve ser positivo.")
    if (
        not (bundle / "SeJogaCompanion.exe").is_file()
        or not (bundle / "_internal").is_dir()
    ):
        raise ValueError("Bundle PyInstaller incompleto.")
    ausentes = sorted(
        caminho for caminho in ASSETS_CAIXAS_DE_SOM
        if not (bundle / caminho).is_file() or (bundle / caminho).is_symlink()
    )
    if ausentes:
        raise ValueError(f"Assets das caixas de som ausentes no bundle: {', '.join(ausentes)}")
    output.mkdir(parents=True, exist_ok=True)
    name = f"SeJogaCompanion-{info.channel}-{info.version}-windows-x64.zip"
    target = output / name
    metadata = {
        "schema_version": 1,
        "architecture": "windows-x64",
        "channel": info.channel,
        "version": info.version,
        "build_id": info.build_id,
        "version_order": _atualizador.version_order(info.version),
        "commit": subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip(),
    }
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for path in sorted(bundle.rglob("*")):
            relative = path.relative_to(bundle)
            if (
                not path.is_file()
                or path.is_symlink()
                or "user-data" in (p.lower() for p in relative.parts)
                or path.suffix.lower() in (".log", ".blend", ".psd", ".xcf")
                or (path.suffix.lower() == ".bbmodel" and relative.as_posix() not in ASSETS_CAIXAS_DE_SOM)
                or relative.as_posix().startswith("_internal/assets/raw/")
                or relative.as_posix() == "release-info.json"
            ):
                continue
            archive.write(path, relative.as_posix())
        archive.writestr("release-info.json", json.dumps(metadata, indent=2))
        for filename in ("LICENSE", "README.md"):
            if not (bundle / filename).exists():
                archive.write(ROOT / filename, filename)
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = dict(
        metadata,
        name=name,
        size=target.stat().st_size,
        sha256=digest,
        url=f"https://github.com/{_atualizador.REPOSITORY}/releases/download/updates-{info.channel}/{name}",
    )
    (output / "channel.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (output / (name + ".sha256")).write_text(f"{digest}  {name}\n", encoding="ascii")
    return manifest


def main():
    """Gera o pacote e o channel.json a partir dos argumentos."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", choices=_atualizador.CHANNELS, required=True)
    parser.add_argument("--version")
    parser.add_argument("--build-id", type=int)
    parser.add_argument("--bundle", type=Path, default=ROOT / "dist/SeJogaCompanion")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    base = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    build_id = args.build_id or int(datetime.now(UTC).strftime("%Y%m%d%H%M%S"))
    version = args.version or (
        base
        if args.channel == "release"
        else base + "rc1"
        if args.channel == "prerelease"
        else f"{base}.dev{build_id}"
    )
    info = _atualizador.ReleaseInfo(version, args.channel, build_id)
    output = args.output or ROOT / "dist/updates" / info.channel
    print(json.dumps(build_package(args.bundle, output, info), indent=2))


if __name__ == "__main__":
    main()
