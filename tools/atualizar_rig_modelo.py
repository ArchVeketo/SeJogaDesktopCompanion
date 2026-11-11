"""Normaliza ``assets/model/projetoMARIO.gltf`` (exportado do Blockbench) para ``assets/model/mario.gltf``.

Operações determinísticas:
1. Remove animações de rascunho do Blockbench (ex.: ``teste``) e zera rotação de teste em ``right-arm``.
2. Envolve o nó ``Porta`` (malha da tampa da TV) em um grupo ``door`` sob ``head`` no pivô da dobradiça
   ``[-0.125, 0.1875, -0.15625]``, compensando a translação local de ``Porta`` para preservar a posição de repouso.
3. Renomeia o nó folha duplicado ``canela-direita`` (``mesh=47``) para ``cuboid_canela_direita`` para que apenas
   o grupo articulável se chame ``canela-direita``.
4. Simetriza os pivôs de grupo do braço esquerdo (``left-arm``, ``ant-arm2``, ``hand2``, ``fingers2``) e da perna
   esquerda (``coxa-esquerda``, ``canela-esquerda``, ``joelho-esquerdo``) em relação ao lado direito, movendo o
   polegar esquerdo para ``hand2`` e empurrando a rotação de repouso de ``coxa-esquerda`` para suas malhas filhas,
   preservando 100% da posição/orientação de mundo de todas as malhas em repouso.
5. Envolve os nós-raiz da cena no nó-raiz de orientação frontal Rota B (``rotation: [0, 1, 0, 0]``) com o marcador
   de escala Blockbench ``47c25daa-cbe1-2755-01f8-e61f9cfef872``.

Uso:
    python tools/atualizar_rig_modelo.py
    python tools/atualizar_rig_modelo.py --verificar
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
SRC_DIR = RAIZ_PROJETO / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sejoga.nucleo.esqueleto import ALL_GROUPS  # noqa: E402
from sejoga.nucleo.modelo import (  # noqa: E402
    _iter_tree,
    _mul,
    _node_local_matrix,
    load_model,
)
from sejoga.nucleo.recursos import resolve_model  # noqa: E402

CAMINHO_FONTE_GLTF = RAIZ_PROJETO / "assets" / "model" / "projetoMARIO.gltf"
CAMINHO_SAIDA_GLTF = RAIZ_PROJETO / "assets" / "model" / "mario.gltf"

PIVO_DOOR_SOB_HEAD = [-0.125, 0.1875, -0.15625]
COMPENSACAO_PORTA_SOB_DOOR = [0.125, -0.1875, 0.15625]
UUID_MARCADOR_BB = "47c25daa-cbe1-2755-01f8-e61f9cfef872"


def _matrizes_mundo_por_no(gltf_data: dict[str, Any]) -> dict[int, tuple[float, ...]]:
    """Calcula a matriz 4x4 de mundo (coluna-maior) de cada nó alcançável pela cena."""
    nodes = gltf_data["nodes"]
    scenes = gltf_data.get("scenes", [])
    scene_idx = gltf_data.get("scene", 0)
    roots = scenes[scene_idx]["nodes"] if scenes else [len(nodes) - 1]
    world: dict[int, tuple[float, ...]] = {}
    for idx, _depth, parent in _iter_tree(nodes, roots):
        local = _node_local_matrix(nodes[idx])
        world[idx] = local if parent is None else _mul(world[parent], local)
    return world


def _matrizes_mundo_malhas(gltf_data: dict[str, Any]) -> dict[int, tuple[float, ...]]:
    """Calcula a matriz 4x4 de mundo de cada nó de malha (por índice de mesh)."""
    nodes = gltf_data["nodes"]
    world = _matrizes_mundo_por_no(gltf_data)
    return {
        n["mesh"]: world[i]
        for i, n in enumerate(nodes)
        if n.get("mesh") is not None and i in world
    }


def _achar_grupo(nodes: list[dict[str, Any]], nome: str) -> int:
    for i, n in enumerate(nodes):
        if n.get("name") == nome and n.get("mesh") is None:
            return i
    raise KeyError(f"Grupo {nome!r} não encontrado no glTF")


def _achar_no_malha_por_nome(nodes: list[dict[str, Any]], nome: str) -> int:
    for i, n in enumerate(nodes):
        if n.get("name") == nome and n.get("mesh") is not None:
            return i
    raise KeyError(f"Nó de malha {nome!r} não encontrado no glTF")


def _limpar_nos_vazios_fio(nodes: list[dict[str, Any]]) -> None:
    """Remove nós plane vazios (sem mesh e sem filhos) dentro de ``fio do fone``."""
    for n in nodes:
        if n.get("name") == "fio do fone" and "children" in n:
            n["children"] = [
                c
                for c in n["children"]
                if nodes[c].get("mesh") is not None or nodes[c].get("children")
            ]


def normalizar_gltf(fonte_raw: dict[str, Any]) -> tuple[dict[str, Any], dict[int, tuple[float, ...]]]:
    """Transforma ``projetoMARIO.gltf`` em ``mario.gltf`` preservando as matrizes de repouso."""
    doc = copy.deepcopy(fonte_raw)
    nodes: list[dict[str, Any]] = doc["nodes"]

    # 1. Remove animações de teste e rotação residual no right-arm ANTES de tirar o snapshot de mundo
    doc["animations"] = []
    idx_right_arm = _achar_grupo(nodes, "right-arm")
    nodes[idx_right_arm].pop("rotation", None)

    # Remove planos vazios (mesh=None, children=None) de 'fio do fone'
    _limpar_nos_vazios_fio(nodes)

    # Snapshot das matrizes de mundo de todas as 56 malhas antes da normalização de grupos
    mundo_antes_sem_flip = _matrizes_mundo_malhas(doc)
    mundo_nos_antes = _matrizes_mundo_por_no(doc)

    # 2. Renomeia nó folha duplicado 'canela-direita' (mesh != None)
    for n in nodes:
        if n.get("name") == "canela-direita" and n.get("mesh") is not None:
            n["name"] = "cuboid_canela_direita"

    # 3. Envolve 'Porta' em um grupo 'door' sob 'head' se 'door' ainda não existir
    nomes_grupos = {n.get("name") for n in nodes if n.get("mesh") is None}
    if "door" not in nomes_grupos:
        idx_head = _achar_grupo(nodes, "head")
        idx_porta = _achar_no_malha_por_nome(nodes, "Porta")
        nodes[idx_porta]["translation"] = list(COMPENSACAO_PORTA_SOB_DOOR)
        idx_door = len(nodes)
        nodes.append(
            {
                "name": "door",
                "translation": list(PIVO_DOOR_SOB_HEAD),
                "children": [idx_porta],
            }
        )
        filhos_head = list(nodes[idx_head].get("children", []))
        if idx_porta in filhos_head:
            filhos_head[filhos_head.index(idx_porta)] = idx_door
        else:
            filhos_head.append(idx_door)
        nodes[idx_head]["children"] = filhos_head

    # 4. Simetriza pivôs do braço esquerdo (left-arm, ant-arm2, hand2, fingers2) e move polegar para hand2
    idx_left_arm = _achar_grupo(nodes, "left-arm")
    idx_shoulder2 = _achar_grupo(nodes, "shoulder2")
    idx_ant_arm2 = _achar_grupo(nodes, "ant-arm2")
    idx_hand2 = _achar_grupo(nodes, "hand2")
    idx_fingers2 = _achar_grupo(nodes, "fingers2")

    # Identifica o polegar esquerdo dentro de fingers2 (maior deslocamento X positivo local, ~0.115625)
    filhos_fingers2 = list(nodes[idx_fingers2].get("children", []))
    filhos_hand2 = list(nodes[idx_hand2].get("children", []))
    if len(filhos_fingers2) == 5:
        idx_polegar_esq = max(
            filhos_fingers2,
            key=lambda idx: (nodes[idx].get("translation") or [0.0, 0.0, 0.0])[0],
        )
        filhos_fingers2.remove(idx_polegar_esq)
        # Insere antes de idx_fingers2 em hand2 (igual a hand: [palma, polegar, fingers])
        if idx_fingers2 in filhos_hand2:
            pos_f2 = filhos_hand2.index(idx_fingers2)
            filhos_hand2.insert(pos_f2, idx_polegar_esq)
        else:
            filhos_hand2.append(idx_polegar_esq)
        nodes[idx_fingers2]["children"] = filhos_fingers2
        nodes[idx_hand2]["children"] = filhos_hand2

    # Ajusta translações dos grupos do braço esquerdo para espelhar exatamente o braço direito
    nodes[idx_left_arm]["translation"] = [-0.125, 0.6875, 0.0]
    nodes[idx_ant_arm2]["translation"] = [-0.125, 0.0, 0.0]
    nodes[idx_hand2]["translation"] = [-0.15625, 0.0, 0.0]
    nodes[idx_fingers2]["translation"] = [-0.109375, 0.03125, 0.0]

    # Recalcula matrizes de mundo dos grupos pais após a simetrização
    mundo_nos_meio = _matrizes_mundo_por_no(doc)

    # Ajusta a malha filha de shoulder2 para compensar a mudança de X em left-arm
    for idx_filho in nodes[idx_shoulder2].get("children", []):
        if nodes[idx_filho].get("mesh") is not None:
            # Em shoulder2 há uma rotação Z; usamos inversa da matriz 3x3 de shoulder2
            m_pai = mundo_nos_meio[idx_shoulder2]
            m_alvo = mundo_nos_antes[idx_filho]
            dx = m_alvo[12] - m_pai[12]
            dy = m_alvo[13] - m_pai[13]
            dz = m_alvo[14] - m_pai[14]
            # Transposta da parte rotacional ortonormal 3x3 (coluna-maior)
            tx = m_pai[0] * dx + m_pai[1] * dy + m_pai[2] * dz
            ty = m_pai[4] * dx + m_pai[5] * dy + m_pai[6] * dz
            tz = m_pai[8] * dx + m_pai[9] * dy + m_pai[10] * dz
            nodes[idx_filho]["translation"] = [round(tx, 8), round(ty, 8), round(tz, 8)]

    # Para ant-arm2, hand2 e fingers2 (grupos com rotação identidade), t_local = T_mundo_antigo - T_mundo_pai_novo
    for idx_pai in (idx_ant_arm2, idx_hand2, idx_fingers2):
        m_pai = mundo_nos_meio[idx_pai]
        for idx_filho in nodes[idx_pai].get("children", []):
            if nodes[idx_filho].get("mesh") is not None:
                m_alvo = mundo_nos_antes[idx_filho]
                nodes[idx_filho]["translation"] = [
                    round(m_alvo[12] - m_pai[12], 8),
                    round(m_alvo[13] - m_pai[13], 8),
                    round(m_alvo[14] - m_pai[14], 8),
                ]

    # 5. Simetriza pivôs da perna esquerda (coxa-esquerda, canela-esquerda, joelho-esquerdo)
    #    e empurra a rotação de repouso de coxa-esquerda (5 graus em Z) para as malhas filhas
    idx_coxa_dir = _achar_grupo(nodes, "coxa-direita")
    idx_canela_dir = _achar_grupo(nodes, "canela-direita")
    idx_joelho_dir = _achar_grupo(nodes, "joelho-direito")
    idx_coxa_esq = _achar_grupo(nodes, "coxa-esquerda")
    idx_canela_esq = _achar_grupo(nodes, "canela-esquerda")
    idx_joelho_esq = _achar_grupo(nodes, "joelho-esquerdo")

    rot_coxa_esq = nodes[idx_coxa_esq].pop("rotation", None)
    t_coxa_dir = nodes[idx_coxa_dir].get("translation", [0.0, 0.0, 0.0])
    t_canela_dir = nodes[idx_canela_dir].get("translation", [0.0, 0.0, 0.0])
    t_joelho_dir = nodes[idx_joelho_dir].get("translation", [0.0, 0.0, 0.0])

    nodes[idx_coxa_esq]["translation"] = [-t_coxa_dir[0], t_coxa_dir[1], t_coxa_dir[2]]
    nodes[idx_canela_esq]["translation"] = [-t_canela_dir[0], t_canela_dir[1], t_canela_dir[2]]
    nodes[idx_joelho_esq]["translation"] = [-t_joelho_dir[0], t_joelho_dir[1], t_joelho_dir[2]]

    mundo_nos_perna = _matrizes_mundo_por_no(doc)
    for idx_pai in (idx_coxa_esq, idx_canela_esq, idx_joelho_esq):
        m_pai = mundo_nos_perna[idx_pai]
        for idx_filho in nodes[idx_pai].get("children", []):
            if nodes[idx_filho].get("mesh") is not None:
                m_alvo = mundo_nos_antes[idx_filho]
                nodes[idx_filho]["translation"] = [
                    round(m_alvo[12] - m_pai[12], 8),
                    round(m_alvo[13] - m_pai[13], 8),
                    round(m_alvo[14] - m_pai[14], 8),
                ]
                if rot_coxa_esq is not None and "rotation" not in nodes[idx_filho]:
                    nodes[idx_filho]["rotation"] = list(rot_coxa_esq)

    # Verifica invariantes antes de aplicar o wrapper raiz Rota B
    mundo_depois_sem_flip = _matrizes_mundo_malhas(doc)
    assert set(mundo_antes_sem_flip.keys()) == set(mundo_depois_sem_flip.keys())
    max_erro = 0.0
    for mesh_id, m_a in mundo_antes_sem_flip.items():
        m_d = mundo_depois_sem_flip[mesh_id]
        erro = max(abs(a - b) for a, b in zip(m_a, m_d, strict=True))
        max_erro = max(max_erro, erro)
        if erro > 1e-6:
            raise AssertionError(f"Matriz de mundo da mesh {mesh_id} divergiu: erro={erro:.2e}")

    # 6. Envolve os nós de cena no nó-raiz de orientação frontal Rota B (rotation=[0, 1, 0, 0])
    scene_idx = doc.get("scene", 0)
    raizes_cena = list(doc["scenes"][scene_idx]["nodes"])
    if len(raizes_cena) > 1 or nodes[raizes_cena[0]].get("rotation") != [0, 1, 0, 0]:
        idx_marcador = len(nodes)
        nodes.append({"name": UUID_MARCADOR_BB, "translation": [0.0, 0.625, 0.0]})
        idx_raiz = len(nodes)
        nodes.append(
            {
                "rotation": [0, 1, 0, 0],
                "children": [idx_marcador, *raizes_cena],
            }
        )
        doc["scenes"][scene_idx]["nodes"] = [idx_raiz]

    return doc, mundo_antes_sem_flip


def verificar_grupos_esqueleto(gltf_data: dict[str, Any]) -> list[str]:
    """Retorna lista de grupos de ``ALL_GROUPS`` ausentes em ``gltf_data``."""
    nomes_grupos = {
        n.get("name")
        for n in gltf_data["nodes"]
        if n.get("name") and n.get("mesh") is None
    }
    return [g for g in ALL_GROUPS if g not in nomes_grupos]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verificar",
        action="store_true",
        help="Apenas verifica se mario.gltf contém todos os grupos de ALL_GROUPS.",
    )
    args = parser.parse_args()

    if args.verificar:
        gltf_atual = json.loads(CAMINHO_SAIDA_GLTF.read_text(encoding="utf-8"))
        faltando = verificar_grupos_esqueleto(gltf_atual)
        if faltando:
            print(f"[FALHA] Grupos de ALL_GROUPS ausentes em mario.gltf: {faltando}")
            return 1
        print(
            f"[OK] Todos os {len(ALL_GROUPS)} grupos de ALL_GROUPS estão presentes em mario.gltf "
            f"({len(gltf_atual['nodes'])} nós, {len(gltf_atual['meshes'])} malhas)."
        )
        return 0

    fonte_raw = json.loads(CAMINHO_FONTE_GLTF.read_text(encoding="utf-8"))
    doc_normalizado, _ = normalizar_gltf(fonte_raw)

    faltando = verificar_grupos_esqueleto(doc_normalizado)
    if faltando:
        raise RuntimeError(f"Grupos de ALL_GROUPS ausentes após normalização: {faltando}")

    CAMINHO_SAIDA_GLTF.write_text(
        json.dumps(doc_normalizado, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"[OK] Normalizado {CAMINHO_FONTE_GLTF.name} -> {CAMINHO_SAIDA_GLTF.name} "
        f"({len(doc_normalizado['nodes'])} nós, {len(doc_normalizado['meshes'])} malhas)."
    )

    modelo = load_model(resolve_model())
    print(
        f"[OK] Modelo recarregado via load_model: {len(modelo.nodes)} nós, "
        f"{modelo.mesh_count} malhas, {modelo.vertex_count} vértices."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
