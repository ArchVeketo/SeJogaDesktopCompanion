"""Mapeia todas as 43 malhas de ``mario.gltf`` e ``projetoMARIO.bbmodel``.

Tarefa de viabilidade do Passo 1 (``docs/MUDANCA_ANIMACAO_NATURALIDADE.md`` §6.5):
não altera o modelo; lê o ``.gltf`` e o ``.bbmodel``, cruza cada ``meshN`` com
seu grupo pai, tipo primitivo (``cuboid``, ``cylinder``, ``plane``, ``sphere``,
``pyramid``), caixa envolvente em unidades do Blockbench (16 u_bb = 1 u_gltf)
e classifica a sub-região anatômica, gerando:

1. Tabela Markdown detalhada no terminal.
2. Render de diagnóstico com cada malha em cor distinta e numerada (frente e 3/4)
   quando chamado com ``--render <pasta>``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sejoga.nucleo.modelo import (
    Mat4,
    Node,
    _apply,
    _iter_tree,
    _mul,
    _node_local_matrix,
    load_gltf_document,
    load_model,
)
from sejoga.nucleo.recursos import resolve_model

ESCALA_BB = 16.0  # 1 unidade glTF = 16 unidades Blockbench


@dataclass(frozen=True, slots=True)
class InfoMalha:
    """Metadados geométricos e semânticos de uma malha do modelo."""

    mesh_idx: int
    mesh_name: str
    node_name: str
    grupo_ancestral: str
    vertices: int
    bb_min: tuple[float, float, float]
    bb_max: tuple[float, float, float]
    bb_centro: tuple[float, float, float]
    bb_dim: tuple[float, float, float]
    regiao_sugerida: str
    no_novo_sugerido: str


def _ancestral_grupo(node_idx: int, parent_of: dict[int, int | None], nodes_by_idx: dict[int, Node]) -> str:
    """Sobe na árvore até achar o grupo de rig imediato acima do nó da malha."""
    atual = parent_of.get(node_idx)
    while atual is not None:
        nome = nodes_by_idx[atual].name
        if nome and nome not in {"cuboid", "cylinder", "plane", "sphere", "pyramid"}:
            return nome
        atual = parent_of.get(atual)
    return "root"


def _classificar_regiao(
    mesh_name: str,
    node_name: str,
    grupo: str,
    bmin: tuple[float, float, float],
    bmax: tuple[float, float, float],
    centro: tuple[float, float, float],
    dim: tuple[float, float, float],
) -> tuple[str, str]:
    """Infere ``(regiao_anatomica, no_novo_em_portugues)`` pelas medidas e grupo."""
    cx, cy, cz = centro
    dx, dy, dz = dim

    if grupo == "door":
        return ("porta_cabeca", "door")

    if grupo == "head":
        if mesh_name in {"mesh11", "mesh12", "mesh13", "mesh14"}:
            return ("planos_cruzados_ocultos", "(oculto/remover)")
        if mesh_name == "mesh18":
            return ("fio_rigido_fone", "(oculto por MalhaFioFone)")
        if node_name in {"pyramid", "sphere"}:
            lado = "direita" if cx > 0 else "esquerda"
            return (f"antena_{lado} ({node_name})", f"antena-{lado}")
        if mesh_name == "mesh5":
            return ("arco_topo_fone (cuboid)", "fones")
        if mesh_name in {"mesh6", "mesh7"}:
            lado = "direito" if cx > 0 else "esquerdo"
            return (f"haste_arco_fone_{lado} (cuboid)", f"fone-{lado}")
        if mesh_name in {"mesh3", "mesh4", "mesh17"}:
            return (f"concha_fone_direito ({node_name})", "fone-direito")
        if mesh_name in {"mesh1", "mesh2", "mesh8"}:
            return (f"concha_fone_esquerdo ({node_name})", "fone-esquerdo")
        if mesh_name == "mesh0":
            return ("cranio_principal", "head")
        return (f"detalhe_cabeca ({node_name})", "head")

    if grupo == "body":
        if node_name == "cylinder":
            return ("aparelho_musica_cinto (cylinder)", "cintura / abdomen")
        return ("tronco_bloco (dividir peitoral/abdomen)", "peitoral + abdomen")

    if grupo == "legs":
        return ("short_unico (dividir 2 pernas + joelho)", "coxa-direita/esquerda + canela-direita/esquerda")

    if grupo in {"left-feet", "right-feet"}:
        lado = "esquerdo" if "left" in grupo else "direito"
        return (f"tenis_{lado} ({node_name})", grupo)

    if grupo in {"shoulder", "shoulder2"}:
        lado = "direito" if grupo == "shoulder" else "esquerdo"
        return (f"bloco_ombro_{lado}", grupo)

    if grupo in {"right-arm", "left-arm"}:
        lado = "direito" if "right" in grupo else "esquerdo"
        return (f"braco_superior_{lado}", grupo)

    if grupo in {"ant-arm", "ant-arm2"}:
        lado = "direito" if grupo == "ant-arm" else "esquerdo"
        return (f"antebraco_{lado}", grupo)

    if grupo in {"hand", "hand2"}:
        lado = "direita" if grupo == "hand" else "esquerda"
        return (f"palma_mao_{lado}", grupo)

    if grupo in {"fingers", "fingers2"}:
        lado = "direita" if grupo == "fingers" else "esquerda"
        return (f"dedo_mao_{lado}", grupo)

    return (grupo, grupo)


def inspecionar_malhas() -> list[InfoMalha]:
    """Lê o modelo padrão e devolve a lista ordenada de ``InfoMalha``."""
    caminho = resolve_model()
    doc = load_gltf_document(caminho)
    model = load_model(caminho)
    nodes_data = doc["nodes"]
    scenes = doc.get("scenes", [])
    scene = scenes[doc.get("scene", 0)] if scenes else {}
    roots = scene.get("nodes", []) or list(range(len(nodes_data)))

    world: dict[int, Mat4] = {}
    parent_of: dict[int, int | None] = {}
    for index, _depth, parent in _iter_tree(nodes_data, roots):
        local = _node_local_matrix(nodes_data[index])
        world[index] = _mul(world[parent], local) if parent is not None else local
        parent_of[index] = parent

    nodes_by_idx = {n.index: n for n in model.nodes}
    accessors = doc.get("accessors", [])
    meshes = doc.get("meshes", [])

    infos: list[InfoMalha] = []
    for node in model.nodes:
        if node.mesh is None:
            continue
        mesh_idx = node.mesh
        mesh_dict = meshes[mesh_idx]
        mesh_name = mesh_dict.get("name", f"mesh{mesh_idx}")
        mat = world[node.index]

        lo = [math.inf] * 3
        hi = [-math.inf] * 3
        vcount = 0
        for prim in mesh_dict.get("primitives", []):
            pos_idx = prim.get("attributes", {}).get("POSITION")
            if pos_idx is None:
                continue
            acc = accessors[pos_idx]
            vcount += int(acc.get("count", 0))
            amin, amax = acc["min"], acc["max"]
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
                p = _apply(mat, corner)
                # Desfaz o giro de 180° em Y do nó raiz para voltar ao espaço Blockbench:
                p_bb = (-p[0] * ESCALA_BB, p[1] * ESCALA_BB, -p[2] * ESCALA_BB)
                for k in range(3):
                    lo[k] = min(lo[k], p_bb[k])
                    hi[k] = max(hi[k], p_bb[k])

        bmin = (lo[0], lo[1], lo[2])
        bmax = (hi[0], hi[1], hi[2])
        centro = ((bmin[0] + bmax[0]) / 2, (bmin[1] + bmax[1]) / 2, (bmin[2] + bmax[2]) / 2)
        dim = (bmax[0] - bmin[0], bmax[1] - bmin[1], bmax[2] - bmin[2])
        grupo = _ancestral_grupo(node.index, parent_of, nodes_by_idx)
        regiao, no_novo = _classificar_regiao(
            mesh_name, node.name, grupo, bmin, bmax, centro, dim
        )
        infos.append(
            InfoMalha(
                mesh_idx=mesh_idx,
                mesh_name=mesh_name,
                node_name=node.name,
                grupo_ancestral=grupo,
                vertices=vcount,
                bb_min=bmin,
                bb_max=bmax,
                bb_centro=centro,
                bb_dim=dim,
                regiao_sugerida=regiao,
                no_novo_sugerido=no_novo,
            )
        )

    infos.sort(key=lambda i: i.mesh_idx)
    return infos


def formatar_markdown(infos: list[InfoMalha]) -> str:
    """Formata a tabela de malhas em Markdown."""
    linhas = [
        "| Mesh | Primitiva | Grupo atual | Vértices | Centro BB (x, y, z) | Dimensão BB (dx, dy, dz) | Y [min..max] | Região identificada | Nó alvo no rig novo |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i in infos:
        cx, cy, cz = i.bb_centro
        dx, dy, dz = i.bb_dim
        ymin, ymax = i.bb_min[1], i.bb_max[1]
        linhas.append(
            f"| `{i.mesh_name}` | `{i.node_name}` | `{i.grupo_ancestral}` | {i.vertices} | "
            f"({cx:+.2f}, {cy:+.2f}, {cz:+.2f}) | ({dx:.2f}, {dy:.2f}, {dz:.2f}) | "
            f"[{ymin:.2f}..{ymax:.2f}] | {i.regiao_sugerida} | `{i.no_novo_sugerido}` |"
        )
    return "\n".join(linhas)


def renderizar_mapa_cores(infos: list[InfoMalha], destino: Path) -> list[Path]:
    """Renderiza o modelo em repouso com cada malha em cor distinta e numerada."""
    import colorsys

    import gltf
    from direct.showbase.ShowBase import ShowBase
    from panda3d.core import (
        AmbientLight,
        DirectionalLight,
        Filename,
        NodePath,
        OrthographicLens,
        PNMImage,
        Point2,
        Point3,
        loadPrcFileData,
    )
    from PIL import Image, ImageDraw

    loadPrcFileData(
        "",
        "window-type offscreen\n"
        "audio-library-name null\n"
        "win-size 900 900\n",
    )
    base = ShowBase(windowType="offscreen")
    base.setBackgroundColor(0.12, 0.12, 0.15, 1.0)

    amb = AmbientLight("amb")
    amb.setColor((0.65, 0.65, 0.65, 1.0))
    base.render.setLight(base.render.attachNewNode(amb))
    dlight = DirectionalLight("dir")
    dlight.setColor((0.55, 0.55, 0.55, 1.0))
    dnp = base.render.attachNewNode(dlight)
    dnp.setHpr(-35, -35, 0)
    base.render.setLight(dnp)

    lens = OrthographicLens()
    lens.setFilmSize(1.85, 1.85)
    lens.setNear(0.1)
    lens.setFar(100.0)
    base.cam.node().setLens(lens)

    pivot = base.render.attachNewNode("cam-pivot")
    pivot.setPos(0, 0, 0.68)
    base.cam.reparentTo(pivot)
    base.cam.setPos(0, -10, 0)
    base.cam.lookAt(pivot)

    model_np = NodePath(gltf.load_model(str(resolve_model())))
    model_np.reparentTo(base.render)
    model_np.setTextureOff(1000)
    model_np.setMaterialOff(1000)

    # Paleta bem separada para as 43 malhas
    cores_rgb: dict[str, tuple[int, int, int]] = {}
    for idx, info in enumerate(infos):
        hue = (idx * 0.618033988749895) % 1.0
        sat = 0.75 if idx % 2 == 0 else 0.90
        val = 0.95 if idx % 3 != 0 else 0.78
        r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
        cores_rgb[info.mesh_name] = (int(r * 255), int(g * 255), int(b * 255))
        np_mesh = model_np.find(f"**/{info.mesh_name}")
        if not np_mesh.isEmpty():
            if info.mesh_name in {"mesh11", "mesh12", "mesh13", "mesh14"}:
                np_mesh.stash()
            else:
                np_mesh.setColor(r, g, b, 1.0, 1000)

    destino.mkdir(parents=True, exist_ok=True)
    gerados: list[Path] = []
    vistas = (("frente", 0.0, 0.0), ("tres_quartos", 35.0, -10.0), ("costas", 180.0, 0.0))

    for nome_vista, yaw, pitch in vistas:
        pivot.setHpr(yaw, pitch, 0.0)
        base.graphicsEngine.renderFrame()
        base.graphicsEngine.renderFrame()
        pnm = PNMImage()
        base.win.getScreenshot(pnm)
        arq = destino / f"mapa_malhas_{nome_vista}.png"
        pnm.write(Filename.fromOsSpecific(str(arq)))

        # Sobrepõe o número de cada malha projetado na tela
        img = Image.open(arq).convert("RGBA")
        draw = ImageDraw.Draw(img)
        w, h = img.size
        lens_node = base.cam.node().getLens()
        for info in infos:
            if info.mesh_name in {"mesh11", "mesh12", "mesh13", "mesh14"}:
                continue
            np_mesh = model_np.find(f"**/{info.mesh_name}")
            if np_mesh.isEmpty():
                continue
            bounds = np_mesh.getTightBounds(base.cam)
            if not bounds:
                continue
            centro_cam = (bounds[0] + bounds[1]) * 0.5
            p2 = Point2()
            if lens_node.project(Point3(centro_cam), p2):
                px = int((p2.x * 0.5 + 0.5) * w)
                py = int((0.5 - p2.y * 0.5) * h)
                cor = cores_rgb[info.mesh_name]
                rotulo = str(info.mesh_idx)
                draw.rectangle((px - 10, py - 7, px + 10, py + 7), fill=(0, 0, 0, 190), outline=cor)
                draw.text((px - 6, py - 6), rotulo, fill=cor)
        img.save(arq)
        gerados.append(arq)

    base.destroy()
    return gerados


def main() -> None:
    """Executa o mapeamento e imprime a tabela."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    parser.add_argument("--render", type=Path, default=None, help="Pasta onde salvar PNGs coloridos")
    args = parser.parse_args()

    infos = inspecionar_malhas()
    if args.render is not None:
        gerados = renderizar_mapa_cores(infos, args.render)
        for arq in gerados:
            print(f"Render salvo: {arq}")
    if args.json:
        print(json.dumps([i.__dict__ for i in infos], indent=2, ensure_ascii=False))
    else:
        print(formatar_markdown(infos))


if __name__ == "__main__":
    main()
