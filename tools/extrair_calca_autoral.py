"""Extrai a calça original, preservando vértices, faces e atlas do Blockbench."""

import argparse
import base64
import hashlib
import json
import math
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    args = parser.parse_args()
    raw = args.original.read_bytes()
    doc = json.loads(raw)
    group = next(g for g in doc["outliner"] if g["name"] == "legs")
    mesh = next(e for e in doc["elements"] if e["uuid"] == group["children"][0])
    assert mesh["type"] == "mesh" and group["origin"] == [0, 7, 0]
    angle = math.radians(group["rotation"][0])
    c, s = math.cos(angle), math.sin(angle)
    # Blockbench Y-up -> Panda Z-up, relativo ao legs atual (Y=6.7 no BB).
    vertices = {
        k: [
            round(x / 16, 8),
            round(-(s * y + c * z) / 16, 8),
            round((7 + c * y - s * z - 6.7) / 16, 8),
        ]
        for k, (x, y, z) in mesh["vertices"].items()
    }
    faces = [
        {
            "vertices": f["vertices"],
            "uv": [
                [round(f["uv"][v][0] / 16, 8), round(1 - f["uv"][v][1] / 16, 8)]
                for v in f["vertices"]
            ],
        }
        for f in mesh["faces"].values()
    ]
    assert len(vertices) == 28 and len(faces) == 26
    result = {
        "source": args.original.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "vertices": vertices,
        "faces": faces,
    }
    out = Path(__file__).resolve().parents[1] / "assets/model"
    (out / "calca-autoral.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    (out / "calca-autoral.png").write_bytes(
        base64.b64decode(doc["textures"][0]["source"].split(",")[1])
    )


if __name__ == "__main__":
    main()
