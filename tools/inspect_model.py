#!/usr/bin/env python3
"""Inspeciona e valida o modelo 3D do Mário (glTF / .glb / .bbmodel).

Serve como *fonte da verdade* sobre o rig: em vez de assumir nomes de ossos,
o script lê o arquivo e imprime a hierarquia real, contagens e possíveis
problemas de integridade.

Uso
---
    python tools/inspect_model.py assets/model/mario.gltf
    python tools/inspect_model.py assets/model/mario.glb
    python tools/inspect_model.py assets/model/projetoMARIO.bbmodel --json

Saída legível por humanos por padrão; ``--json`` emite um resumo estruturado
(útil para CI e para o runtime).
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any

GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A

# Grupos (pivôs) que interessam à camada de animação procedural.
RIG_GROUPS = (
    "head",
    "door",
    "body",
    "right-arm",
    "left-arm",
    "shoulder",
    "shoulder2",
    "ant-arm",
    "ant-arm2",
    "hand",
    "hand2",
    "fingers",
    "fingers2",
    "legs",
    "left-feet",
    "right-feet",
)


def load_gltf(path: Path) -> dict[str, Any]:
    """Carrega um glTF texto ou um GLB binário."""
    raw = path.read_bytes()
    if raw[:4] == b"glTF":
        magic, version, length = struct.unpack("<III", raw[:12])
        if magic != GLB_MAGIC or version != 2:
            raise SystemExit("GLB inválido ou versão != 2")
        offset = 12
        while offset < length:
            chunk_len, chunk_type = struct.unpack("<II", raw[offset : offset + 8])
            offset += 8
            data = raw[offset : offset + chunk_len]
            offset += chunk_len
            if chunk_type == CHUNK_JSON:
                return json.loads(data.decode("utf-8"))
        raise SystemExit("GLB sem chunk JSON")
    return json.loads(raw.decode("utf-8"))


def load_bbmodel(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def walk_nodes(nodes: list[dict], roots: list[int]) -> list[tuple[int, dict, int]]:
    """Retorna ``(índice, nó, profundidade)`` em ordem de árvore."""
    out: list[tuple[int, dict, int]] = []

    def visit(idx: int, depth: int) -> None:
        node = nodes[idx]
        out.append((idx, node, depth))
        for child in node.get("children", []):
            visit(child, depth + 1)

    for root in roots:
        visit(root, 0)
    return out


def summarize_gltf(doc: dict[str, Any]) -> dict[str, Any]:
    nodes = doc.get("nodes", [])
    scene_roots = doc.get("scenes", [{}])[doc.get("scene", 0)].get("nodes", [])

    tree = walk_nodes(nodes, scene_roots)
    names = [node.get("name", "") for _, node, _ in tree]
    group_names = [n for n in names if n in RIG_GROUPS]

    verts = 0
    prims = 0
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            prims += 1
            pos = prim.get("attributes", {}).get("POSITION")
            if pos is not None:
                verts += doc["accessors"][pos].get("count", 0)

    return {
        "asset": doc.get("asset", {}),
        "counts": {
            "nodes": len(nodes),
            "meshes": len(doc.get("meshes", [])),
            "primitives": prims,
            "vertices": verts,
            "materials": len(doc.get("materials", [])),
            "textures": len(doc.get("textures", [])),
            "images": len(doc.get("images", [])),
            "animations": len(doc.get("animations", [])),
            "skins": len(doc.get("skins", [])),
        },
        "rig_groups_found": sorted(set(group_names)),
        "rig_groups_missing": sorted(set(RIG_GROUPS) - set(group_names)),
        "node_tree": [
            {
                "index": idx,
                "name": node.get("name", ""),
                "depth": depth,
                "mesh": node.get("mesh"),
                "children": node.get("children", []),
            }
            for idx, node, depth in tree
        ],
        "has_animations": bool(doc.get("animations")),
        "is_skinned": bool(doc.get("skins")),
    }


def summarize_bbmodel(doc: dict[str, Any]) -> dict[str, Any]:
    outliner = doc.get("outliner", [])

    def flatten(nodes: list, depth: int = 0):
        rows = []
        for node in nodes:
            if isinstance(node, dict):
                if node.get("name"):
                    rows.append({"name": node["name"], "depth": depth})
                rows.extend(flatten(node.get("children", []), depth + 1))
        return rows

    rows = flatten(outliner)
    names = [row["name"] for row in rows]
    return {
        "format_version": doc.get("meta", {}).get("format_version"),
        "model_format": doc.get("meta", {}).get("model_format"),
        "counts": {
            "elements": len(doc.get("elements", [])),
            "groups": len(rows),
            "textures": len(doc.get("textures", [])),
            "animations": len(doc.get("animations", [])),
        },
        "rig_groups_found": sorted(set(names) & set(RIG_GROUPS)),
        "rig_groups_missing": sorted(set(RIG_GROUPS) - set(names)),
        "node_tree": rows,
        "has_animations": bool(doc.get("animations")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", action="store_true", help="saída JSON estruturada")
    args = parser.parse_args(argv)

    path: Path = args.path
    if not path.exists():
        raise SystemExit(f"arquivo não encontrado: {path}")

    if path.suffix.lower() in {".gltf", ".glb"}:
        doc = load_gltf(path)
        summary = summarize_gltf(doc)
        kind = "gltf"
    elif path.suffix.lower() == ".bbmodel":
        doc = load_bbmodel(path)
        summary = summarize_bbmodel(doc)
        kind = "bbmodel"
    else:
        raise SystemExit(f"formato não suportado: {path.suffix}")

    summary["kind"] = kind
    summary["path"] = str(path)

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    print(f"arquivo: {path}")
    print(f"tipo: {kind}")
    counts = summary["counts"]
    print("contagens: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"tem animações: {summary['has_animations']}")
    print("grupos de rig encontrados: " + ", ".join(summary["rig_groups_found"]))
    missing = summary["rig_groups_missing"]
    if missing:
        print("grupos ausentes: " + ", ".join(missing))
    print("\nhierarquia:")
    for row in summary["node_tree"]:
        indent = "  " * row["depth"]
        mesh = f" mesh={row['mesh']}" if row.get("mesh") is not None else ""
        print(f"{indent}- {row['name']}{mesh}")

    if not summary["has_animations"]:
        print(
            "\nnota: sem animações embutidas. A camada de animação procedural do "
            "runtime deve dirigir os grupos acima por nome."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
