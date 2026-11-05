"""Exporta o tentáculo low poly editável como glTF autocontido."""
import base64
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sejoga.tentacle_model import build_tentacle

vertices, normals, colors, indices = build_tentacle()
def linear(value):
    return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
colors = [(*tuple(linear(v) for v in color[:3]), color[3]) for color in colors]
def convert(p):
    return (p[0], p[2], -p[1])
vertices, normals = [convert(p) for p in vertices], [convert(p) for p in normals]
data = bytearray()
views: list = []
accessors: list = []
def add(items, width, fmt, component, kind):
    while len(data)%4:
        data.append(0)
    start = len(data)
    for item in items:
        data.extend(struct.pack('<'+fmt*width, *item))
    views.append({'buffer': 0, 'byteOffset': start, 'byteLength': len(data)-start})
    accessor = {'bufferView': len(views)-1, 'componentType': component, 'count': len(items), 'type': kind}
    if kind == 'VEC3':
        accessor['min'] = [min(p[k] for p in items) for k in range(3)]
        accessor['max'] = [max(p[k] for p in items) for k in range(3)]
    accessors.append(accessor)
    return len(accessors)-1
position = add(vertices, 3, 'f', 5126, 'VEC3')
normal = add(normals, 3, 'f', 5126, 'VEC3')
color = add(colors, 4, 'f', 5126, 'VEC4')
index = add([(i,) for i in indices], 1, 'H', 5123, 'SCALAR')
document = {
    'asset': {'version': '2.0', 'generator': 'SeJoga low-poly tentacle model'},
    'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'name': 'thick-tentacle', 'mesh': 0}],
    'meshes': [{'primitives': [{'attributes': {'POSITION': position, 'NORMAL': normal, 'COLOR_0': color},
                              'indices': index, 'material': 0}]}],
    'materials': [{'name': 'purple-pink-tentacle', 'doubleSided': True,
                   'pbrMetallicRoughness': {'metallicFactor': 0, 'roughnessFactor': .85}}],
    'buffers': [{'byteLength': len(data), 'uri': 'data:application/octet-stream;base64,'+base64.b64encode(data).decode()}],
    'bufferViews': views, 'accessors': accessors,
}
path = ROOT / 'assets/model/tentacle.gltf'
path.write_text(json.dumps(document, separators=(',', ':')), encoding='utf-8')
print(path, len(indices)//3, 'triangles')
