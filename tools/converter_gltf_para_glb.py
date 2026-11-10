#!/usr/bin/env python3
"""Converte um glTF 2.0 (com buffer/imagem embutidos em *data URI* base64)
para um `.glb` binário único.

Motivação
---------
O export do Blockbench gera um `.gltf` em que o buffer de vértices e a textura
PNG ficam embutidos como *data URI* base64 dentro do JSON. Isso funciona, mas:

* o arquivo fica ~35% maior (overhead do base64);
* alguns runtimes carregam `.glb` de forma mais direta e rápida;
* um único arquivo binário é mais fácil de empacotar/distribuir.

Uso
---
    python tools/converter_gltf_para_glb.py assets/model/mario.gltf -o assets/model/mario.glb

O script não depende de nenhuma biblioteca externa: só ``json``, ``base64``,
``struct`` e ``pathlib`` da stdlib.
"""

from __future__ import annotations

import argparse
import base64
import json
import struct
import sys
from pathlib import Path

GLB_MAGIC = 0x46546C67  # 'glTF'
GLB_VERSION = 2
CHUNK_JSON = 0x4E4F534A  # 'JSON'
CHUNK_BIN = 0x004E4942  # 'BIN\0'

# Alinhamento exigido pela spec do glTF para bufferViews.
BV_ALIGN = 4


def _decode_data_uri(uri: str) -> bytes:
    """Decodifica uma data URI ``data:<mime>;base64,<payload>``."""
    if not uri.startswith("data:"):
        raise ValueError(f"URI não é data URI: {uri[:40]!r}...")
    _, _, payload = uri.partition(",")
    if not payload:
        raise ValueError("data URI sem payload base64")
    return base64.b64decode(payload)


def _is_data_uri(uri: str | None) -> bool:
    return uri is not None and uri.startswith("data:")


def convert(gltf_path: Path, out_path: Path) -> dict:
    doc = json.loads(gltf_path.read_text(encoding="utf-8"))

    buffers = doc.get("buffers", [])
    if len(buffers) != 1:
        raise SystemExit(f"esperado exatamente 1 buffer, encontrado {len(buffers)}")

    buffer = buffers[0]
    if _is_data_uri(buffer.get("uri")):
        buf_bytes = _decode_data_uri(buffer["uri"])
    else:
        raise SystemExit("buffer externo (.bin) não suportado por este script")

    if len(buf_bytes) != buffer.get("byteLength"):
        print(
            f"aviso: byteLength declarado={buffer.get('byteLength')} "
            f"real={len(buf_bytes)}",
            file=sys.stderr,
        )
    buffer.pop("uri", None)
    buffer["byteLength"] = len(buf_bytes)

    # Move cada imagem embutida para o BIN chunk, como bufferView.
    buffer_views = doc.setdefault("bufferViews", [])
    for image in doc.get("images", []):
        uri = image.get("uri")
        if not _is_data_uri(uri):
            continue
        img_bytes = _decode_data_uri(uri)
        while len(buf_bytes) % BV_ALIGN:
            buf_bytes += b"\x00"
        offset = len(buf_bytes)
        buf_bytes += img_bytes
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": offset,
                "byteLength": len(img_bytes),
            }
        )
        image.pop("uri", None)
        image["bufferView"] = len(buffer_views) - 1
        image["mimeType"] = image.get("mimeType", "image/png")

    # BIN chunk é sempre o último e deve estar alinhado em 4 bytes.
    while len(buf_bytes) % BV_ALIGN:
        buf_bytes += b"\x00"

    json_bytes = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    while len(json_bytes) % BV_ALIGN:
        json_bytes += b" "

    total = 12 + 8 + len(json_bytes) + 8 + len(buf_bytes)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as fh:
        fh.write(struct.pack("<III", GLB_MAGIC, GLB_VERSION, total))
        fh.write(struct.pack("<II", len(json_bytes), CHUNK_JSON))
        fh.write(json_bytes)
        fh.write(struct.pack("<II", len(buf_bytes), CHUNK_BIN))
        fh.write(buf_bytes)

    return {
        "gltf_bytes": gltf_path.stat().st_size,
        "glb_bytes": total,
        "images_moved": sum(1 for i in doc.get("images", []) if "bufferView" in i),
        "nodes": len(doc.get("nodes", [])),
        "meshes": len(doc.get("meshes", [])),
        "animations": len(doc.get("animations", [])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gltf", type=Path, help="caminho do .gltf de entrada")
    parser.add_argument(
        "-o", "--output", type=Path, default=None, help="caminho do .glb de saída"
    )
    args = parser.parse_args(argv)

    out = args.output or args.gltf.with_suffix(".glb")
    stats = convert(args.gltf, out)
    print(f"ok: {out}")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
