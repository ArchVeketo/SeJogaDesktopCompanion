"""Leitura, inspeção e *bounds* do modelo glTF/GLB — sem depender de engine.

Este módulo existe para que a lógica de configuração (escala da janela, ponto
de apoio no chão, alvo de clique) seja calculada a partir do arquivo e não de
números mágicos espalhados pelo código.

Conceitos:

* O export do Blockbench **não usa skin**: o "rig" é uma hierarquia de nós
  (``head``, ``door``, ``shoulder``...). Animação é transformação de nó.
* ``bounds`` são calculados em espaço de mundo aplicando as TRS de cada nó.
* ``ground_offset`` diz quantos pixels/ unidades o modelo precisa subir para
  apoiar os pés na borda inferior.
"""

from __future__ import annotations

import json
import math
import struct
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GLB_MAGIC = 0x46546C67
_GLB_JSON = 0x4E4F534A

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]
Mat4 = tuple[float, ...]  # 16 floats, coluna-maior


# --------------------------------------------------------------------------- #
# Álgebra mínima (coluna-maior, compatível com glTF/OpenGL)
# --------------------------------------------------------------------------- #
def _identity() -> Mat4:
    return (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)


def _mul(a: Mat4, b: Mat4) -> Mat4:
    out = [0.0] * 16
    for col in range(4):
        for row in range(4):
            out[col * 4 + row] = sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
    return tuple(out)


def _trs(t: Vec3, r: Quat, s: Vec3) -> Mat4:
    x, y, z, w = r
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    m = [
        1 - 2 * (yy + zz),
        2 * (xy + wz),
        2 * (xz - wy),
        0.0,
        2 * (xy - wz),
        1 - 2 * (xx + zz),
        2 * (yz + wx),
        0.0,
        2 * (xz + wy),
        2 * (yz - wx),
        1 - 2 * (xx + yy),
        0.0,
        t[0],
        t[1],
        t[2],
        1.0,
    ]
    for i in range(3):
        m[i] *= s[0]
        m[4 + i] *= s[1]
        m[8 + i] *= s[2]
    return tuple(m)


def _apply(m: Mat4, p: Vec3) -> Vec3:
    x, y, z = p
    return (
        m[0] * x + m[4] * y + m[8] * z + m[12],
        m[1] * x + m[5] * y + m[9] * z + m[13],
        m[2] * x + m[6] * y + m[10] * z + m[14],
    )


# --------------------------------------------------------------------------- #
# Carregamento do arquivo
# --------------------------------------------------------------------------- #
def load_gltf_document(path: Path) -> dict[str, Any]:
    """Lê um ``.gltf`` (JSON) ou ``.glb`` (contêiner binário) para um dict."""
    raw = path.read_bytes()
    if raw[:4] == b"glTF":
        if len(raw) < 12:
            raise ValueError("GLB truncado")
        _, version, total = struct.unpack("<III", raw[:12])
        if version != 2:
            raise ValueError(f"GLB versão {version} não suportada")
        offset = 12
        while offset + 8 <= min(total, len(raw)):
            chunk_len, chunk_type = struct.unpack("<II", raw[offset : offset + 8])
            offset += 8
            chunk = raw[offset : offset + chunk_len]
            offset += chunk_len
            if chunk_type == _GLB_JSON:
                return json.loads(chunk.decode("utf-8"))
        raise ValueError("GLB sem chunk JSON")
    return json.loads(raw.decode("utf-8"))


# --------------------------------------------------------------------------- #
# Estruturas públicas
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Node:
    """Nó do glTF com nome, transformação local e filhos."""

    index: int
    name: str
    parent: int | None
    depth: int
    translation: Vec3
    rotation: Quat
    scale: Vec3
    mesh: int | None
    children: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ModelBounds:
    """Caixa delimitadora do modelo em coordenadas de mundo."""

    minimum: Vec3
    maximum: Vec3

    @property
    def size(self) -> Vec3:
        """Devolve as dimensões da caixa."""
        return tuple(self.maximum[i] - self.minimum[i] for i in range(3))  # type: ignore[return-value]

    @property
    def center(self) -> Vec3:
        """Devolve o centro da caixa."""
        return tuple((self.maximum[i] + self.minimum[i]) / 2 for i in range(3))  # type: ignore[return-value]

    @property
    def height(self) -> float:
        """Devolve a altura da caixa."""
        return self.maximum[1] - self.minimum[1]


@dataclass(frozen=True, slots=True)
class Model:
    """Resumo imutável de um modelo carregado."""

    path: Path
    nodes: tuple[Node, ...]
    mesh_count: int
    primitive_count: int
    vertex_count: int
    material_count: int
    texture_count: int
    animation_names: tuple[str, ...]
    bounds: ModelBounds
    is_skinned: bool

    def node(self, index: int) -> Node:
        """Devolve o nó pelo índice do glTF."""
        return self.nodes[index]

    def find(self, name: str) -> Node | None:
        """Primeiro nó com ``name`` exato (``None`` se ausente)."""
        for node in self.nodes:
            if node.name == name:
                return node
        return None

    def all_named(self, name: str) -> list[Node]:
        """Devolve todos os nós com o nome dado."""
        return [n for n in self.nodes if n.name == name]

    def named_set(self) -> set[str]:
        """Devolve o conjunto de nomes de nós do modelo."""
        return {n.name for n in self.nodes if n.name}

    def ground_offset(self) -> float:
        """Distância da origem até o ponto mais baixo do modelo."""
        return -self.bounds.minimum[1]


# --------------------------------------------------------------------------- #
# Conversão
# --------------------------------------------------------------------------- #
def _vec3(value: Any, default: Vec3) -> Vec3:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    return default


def _quat(value: Any) -> Quat:
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
    return (0.0, 0.0, 0.0, 1.0)


def _node_local_matrix(data: dict[str, Any]) -> Mat4:
    if "matrix" in data:
        values = [float(v) for v in data["matrix"]]
        if len(values) != 16:
            raise ValueError("matriz de nó inválida")
        return tuple(values)
    return _trs(
        _vec3(data.get("translation"), (0.0, 0.0, 0.0)),
        _quat(data.get("rotation")),
        _vec3(data.get("scale"), (1.0, 1.0, 1.0)),
    )


def _iter_tree(nodes: list[dict[str, Any]], roots: Iterable[int]):
    """``(index, depth, parent)`` em pré-ordem, tolerando ciclos."""
    seen: set[int] = set()

    def walk(index: int, depth: int, parent: int | None):
        if index in seen or not (0 <= index < len(nodes)):
            return
        seen.add(index)
        yield index, depth, parent
        for child in nodes[index].get("children", []):
            yield from walk(child, depth + 1, index)

    for root in roots:
        yield from walk(root, 0, None)


def _expandir_limites(
    matrix: Mat4, amin: list, amax: list, lo: list[float], hi: list[float]
) -> None:
    """Amplia ``lo``/``hi`` com os 8 cantos do accessor transformados."""
    for corner in (
        (amin[0], amin[1], amin[2]),
        (amax[0], amin[1], amin[2]),
        (amin[0], amax[1], amin[2]),
        (amax[0], amax[1], amin[2]),
        (amin[0], amin[1], amax[2]),
        (amax[0], amin[1], amax[2]),
        (amin[0], amax[1], amax[2]),
        (amax[0], amax[1], amax[2]),
    ):
        p = _apply(matrix, corner)
        for i in range(3):
            lo[i] = min(lo[i], p[i])
            hi[i] = max(hi[i], p[i])


def _compute_bounds(doc: dict[str, Any], world: dict[int, Mat4]) -> ModelBounds:
    accessors = doc.get("accessors", [])
    meshes = doc.get("meshes", [])
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    found = False

    for node_index, matrix in world.items():
        mesh_index = doc["nodes"][node_index].get("mesh")
        if mesh_index is None or mesh_index >= len(meshes):
            continue
        for prim in meshes[mesh_index].get("primitives", []):
            pos_index = prim.get("attributes", {}).get("POSITION")
            if pos_index is None or pos_index >= len(accessors):
                continue
            acc = accessors[pos_index]
            amin, amax = acc.get("min"), acc.get("max")
            if not (isinstance(amin, list) and isinstance(amax, list)):
                continue
            found = True
            _expandir_limites(matrix, amin, amax, lo, hi)

    if not found:
        return ModelBounds((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    return ModelBounds((lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2]))


def load_model(path: Path) -> Model:
    """Carrega o modelo e devolve um resumo validado.

    Raises:
        FileNotFoundError: caminho inexistente.
        ValueError: documento inválido ou sem cena.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    doc = load_gltf_document(path)
    nodes_data = doc.get("nodes", [])
    if not nodes_data:
        raise ValueError("glTF sem nós")
    scenes = doc.get("scenes", [])
    scene = scenes[doc.get("scene", 0)] if scenes else {}
    roots = scene.get("nodes", []) or list(range(len(nodes_data)))

    nodes: list[Node] = []
    world: dict[int, Mat4] = {}
    for index, depth, parent in _iter_tree(nodes_data, roots):
        data = nodes_data[index]
        local = _node_local_matrix(data)
        world[index] = _mul(world[parent], local) if parent is not None else local
        nodes.append(
            Node(
                index=index,
                name=str(data.get("name", "")),
                parent=parent,
                depth=depth,
                translation=_vec3(data.get("translation"), (0.0, 0.0, 0.0)),
                rotation=_quat(data.get("rotation")),
                scale=_vec3(data.get("scale"), (1.0, 1.0, 1.0)),
                mesh=data.get("mesh"),
                children=tuple(data.get("children", [])),
            )
        )

    vertex_count = 0
    primitive_count = 0
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            primitive_count += 1
            pos = prim.get("attributes", {}).get("POSITION")
            if pos is not None:
                vertex_count += int(doc["accessors"][pos].get("count", 0))

    animation_names = tuple(
        str(anim.get("name") or f"anim_{i}")
        for i, anim in enumerate(doc.get("animations", []))
    )

    return Model(
        path=path,
        nodes=tuple(nodes),
        mesh_count=len(doc.get("meshes", [])),
        primitive_count=primitive_count,
        vertex_count=vertex_count,
        material_count=len(doc.get("materials", [])),
        texture_count=len(doc.get("textures", [])),
        animation_names=animation_names,
        bounds=_compute_bounds(doc, world),
        is_skinned=bool(doc.get("skins")),
    )
