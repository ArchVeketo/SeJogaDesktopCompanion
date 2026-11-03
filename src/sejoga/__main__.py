"""CLI do companion: ``python -m sejoga <comando>`` ou ``sejoga <comando>``.

Comandos da etapa 1 (fundação, sem engine):

* ``inspect``  — valida e imprime o modelo 3D e o rig.
* ``config``   — mostra/cria o arquivo de configuração.
* ``doctor``   — diagnostica o ambiente (Python, wheels, assets, janela).
* ``run``      — inicia o companion (implementado na etapa 2).

Todos os comandos evitam importar um renderizador, então funcionam em máquina
de CI sem GPU, sem Panda3D e sem dependências do Windows.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import sys
from pathlib import Path

from . import __version__
from .assets import assets_dir, resolve_model
from .config import default_config_path, load_settings, save_settings


def _cmd_inspect(args: argparse.Namespace) -> int:
    from .rig import ALL_GROUPS, Rig
    from .model import load_model

    path = Path(args.model) if args.model else resolve_model()
    model = load_model(path)
    rig = Rig.from_model(model)

    print(f"modelo: {model.path}")
    print(f"  nós={len(model.nodes)} meshes={model.mesh_count} "
          f"primitivas={model.primitive_count} vértices={model.vertex_count}")
    print(f"  materiais={model.material_count} texturas={model.texture_count} "
          f"skinned={model.is_skinned}")
    print(f"  animações embutidas: {model.animation_names or 'nenhuma'}")
    b = model.bounds
    print(f"  bounds min={b.minimum} max={b.maximum}")
    print(f"  tamanho={b.size} altura={b.height:.3f} chão={model.ground_offset():.3f}")
    print(f"  grupos de rig: {len(rig.groups)}/{len(ALL_GROUPS)}")
    if rig.missing:
        print(f"  ATENÇÃO — grupos ausentes: {', '.join(rig.missing)}")
        return 1
    print("  rig completo: ok")
    return 0


def _cmd_config(args: argparse.Namespace) -> int:
    path = default_config_path()
    if args.show:
        settings = load_settings(path)
        print(f"arquivo: {path} ({'existe' if path.is_file() else 'não existe'})")
        print(settings.model_dump_json(indent=2))
        return 0
    path = save_settings(load_settings(path), path)
    print(f"config escrito em: {path}")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    ok = True
    print(f"python: {sys.version.split()[0]} ({platform.architecture()[0]})")
    print(f"plataforma: {platform.platform()}")
    print(f"pacote: sejoga {__version__}")

    try:
        model_path = resolve_model()
        print(f"modelo: {model_path}")
    except FileNotFoundError as exc:
        print(f"modelo: FALTA — {exc}")
        ok = False

    print(f"assets: {assets_dir()}")
    if not assets_dir().is_dir():
        ok = False

    for extra, modules in (
        ("panda3d", ("panda3d",)),
        ("win32", ("win32gui", "win32con")),
        ("tray", ("pystray", "PIL")),
        ("music", ("winrt",)),
    ):
        found = [m for m in modules if _module_available(m)]
        status = "ok" if len(found) == len(modules) else "ausente"
        print(f"extra {extra}: {status}")
        if status == "ausente":
            print(f"  instale com: pip install -e \".[{extra}]\"")
        ok = ok and status == "ok"

    print(f"config: {default_config_path()}")
    if shutil.which("git") is None:
        print("git: não encontrado no PATH")
    return 0 if ok else 1


def _cmd_run(args: argparse.Namespace) -> int:
    print(
        "O runtime do companion entra na etapa 2.\n"
        "Antes disso, valide o modelo com: python -m sejoga inspect\n"
        "Arquitetura e decisões: docs/ARQUITETURA.md"
    )
    return 2


def _module_available(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sejoga", description=__doc__)
    parser.add_argument("--version", action="version", version=f"sejoga {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="valida e imprime o modelo e o rig")
    inspect.add_argument("model", nargs="?", help="caminho de .glb/.gltf (opcional)")
    inspect.set_defaults(func=_cmd_inspect)

    config = sub.add_parser("config", help="mostra ou cria o config")
    config.add_argument("--show", action="store_true", help="mostra o config efetivo")
    config.set_defaults(func=_cmd_config)

    doctor = sub.add_parser("doctor", help="diagnostica o ambiente")
    doctor.set_defaults(func=_cmd_doctor)

    run = sub.add_parser("run", help="inicia o companion (etapa 2)")
    run.set_defaults(func=_cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
