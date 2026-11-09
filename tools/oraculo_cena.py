"""Oráculo de cena: mapa de eixos, AABBs e alvos de braço medidos no grafo do Panda.

Carrega ``assets/model/mario.gltf`` com ``gltf.load_model`` + ``NodePath`` (sem
janela/GPU). A FK pura (``nucleo.cinematica``) é conferida (posição) contra este grafo em
``tests/test_cinematica_oraculo.py``; aqui o Panda é usado para as malhas.

Saídas (Markdown no stdout ou em ``--saida``):
  --eixos     para cada junta x (±x, ±y, ±z) a direção em que a ponta vai, no
              referencial do mascote (direita/esquerda, frente/trás, cima/baixo).
  --aabbs     caixas de cada malha no referencial de autoria (fonte de
              ``animacao/colisao_bracos.CAIXAS_CORPO``).
  --alvos     tabela alvo x punho (FK) x penetração do braço para ``arm_targets``.
  --sugerir   para cada alvo em colisão, o ponto livre mais próximo (grade).
  --tronco    pitch/roll/yaw do pivô do tronco → direção do topo da cabeça.
  --dedos     cadeia de juntas dos dedos: para onde a ponta vai com flexão positiva
              (FK pura) e o erro contra os pivôs reais do Panda.
"""

from __future__ import annotations

import argparse
import itertools
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sejoga.animacao import arm_ik
from sejoga.animacao import colisao_bracos as cb
from sejoga.animacao.arm_targets import ALVOS
from sejoga.nucleo import cinematica as cin
from sejoga.nucleo.assets import resolve_model
from sejoga.nucleo.model import load_model
from sejoga.nucleo.rig import ALL_GROUPS, Rotation3

#: Ângulo de teste (graus) do mapa de eixos.
ANGULO_TESTE_GRAUS = 30.0
#: Deslocamento mínimo (u) para considerar que a ponta se moveu num eixo.
DESLOCAMENTO_MINIMO_U = 0.005
#: Grade da busca de alvos livres (u) e alcance útil (fração do braço esticado).
PASSO_GRADE_U = 0.02
FRACAO_ALCANCE = 0.99
#: Distância mínima ombro-punho testada (cotovelo no limite de flexão).
ALCANCE_MINIMO_U = 0.1

#: Ponta usada para cada junta (nó filho mais distal, ou a própria origem).
PONTA_DA_JUNTA = {
    "right-arm": "hand", "ant-arm": "hand", "hand": "fingers",
    "left-arm": "hand2", "ant-arm2": "hand2", "hand2": "fingers2",
    "head": "door", "body": None, "legs": None, "door": None,
    "left-feet": None, "right-feet": None, "shoulder": None, "shoulder2": None,
    "fingers": None, "fingers2": None,
}
_NOMES_EIXO = (("direita", "esquerda"), ("frente", "trás"), ("cima", "baixo"))


def _direcao(delta: cin.Vec3) -> str:
    partes = [
        nomes[0] if valor > 0 else nomes[1]
        for valor, nomes in zip(delta, _NOMES_EIXO, strict=True)
        if abs(valor) >= DESLOCAMENTO_MINIMO_U
    ]

    return "+".join(partes) or "nenhum (só torce)"


def _ponto_de_teste(modelo, grupo: str, pose) -> cin.Vec3:
    ponta = PONTA_DA_JUNTA.get(grupo)

    if ponta:
        return cin.posicao_no(modelo, ponta, pose)

    # Sem filho: ponto a 0.1 u no eixo +Z local da junta (mostra o giro).
    rot, origem = cin.transformacao_no(modelo, grupo, pose)

    return cin.somar(origem, cin.escalar(cin.coluna(rot, 2), 0.1))


def mapa_eixos(modelo) -> str:
    linhas = [
        "| junta | eixo (Rotation3) | +30° move a ponta para | -30° move a ponta para |",
        "|---|---|---|---|",
    ]

    for grupo in ALL_GROUPS:
        if modelo.find(grupo) is None:
            continue

        repouso = _ponto_de_teste(modelo, grupo, {})

        for indice, eixo in enumerate(("x (P)", "y (H)", "z (R)")):
            celulas = []

            for sinal in (1.0, -1.0):
                valores = [0.0, 0.0, 0.0]
                valores[indice] = math.radians(sinal * ANGULO_TESTE_GRAUS)
                pose = {grupo: Rotation3(*valores)}
                celulas.append(_direcao(cin.subtrair(_ponto_de_teste(modelo, grupo, pose), repouso)))

            linhas.append(f"| {grupo} | {eixo} | {celulas[0]} | {celulas[1]} |")

    return "\n".join(linhas)


def aabbs() -> str:
    from panda3d.core import NodePath, loadPrcFileData

    loadPrcFileData("", "window-type none\naudio-library-name null")
    import gltf

    raiz = NodePath(gltf.load_model(str(resolve_model())))
    referencia = raiz.find("**/body").getParent()
    linhas = ["| grupo | malha | x | y (frente) | z (cima) |", "|---|---|---|---|---|"]

    for grupo in ALL_GROUPS:
        no = raiz.find(f"**/{grupo}")

        if no.isEmpty():
            continue

        for malha in no.findAllMatches("**/+GeomNode"):
            if malha.getParent() != no and malha.getParent().getParent() != no:
                continue

            limites = malha.getTightBounds(referencia)

            if limites:
                a, b = limites
                linhas.append(
                    f"| {grupo} | {malha.getName()} | {a.x:.3f}..{b.x:.3f} "
                    f"| {a.y:.3f}..{b.y:.3f} | {a.z:.3f}..{b.z:.3f} |"
                )

    return "\n".join(linhas)


def _pose_simetrica(modelo, alvo, polo) -> dict[str, Rotation3]:
    pose: dict[str, Rotation3] = {}
    pose.update(arm_ik.braco_para(modelo, "right", alvo, polo))
    pose.update(arm_ik.braco_para(modelo, "left", (-alvo[0], alvo[1], alvo[2]), polo))

    return pose


def tabela_alvos(modelo) -> str:
    linhas = [
        "| alvo | pedido (dir, cima, frente) | punho FK | cotovelo FK | penetração |",
        "|---|---|---|---|---|",
    ]

    for nome, alvo in ALVOS.items():
        pose = _pose_simetrica(modelo, alvo.alvo, alvo.polo)
        punho = arm_ik.posicao_mao_para_hpr(modelo, "right", pose["right-arm"], pose["ant-arm"])
        ombro = cin.posicao_no(modelo, "right-arm", pose)
        cotovelo = cin.autoria_para_alvo(cin.subtrair(cin.posicao_no(modelo, "ant-arm", pose), ombro))
        pen = cb.penetracao_do_lado(modelo, "right", pose)
        linhas.append(
            f"| {nome} | {_fmt(alvo.alvo)} | {_fmt(punho)} | {_fmt(cotovelo)} | {pen:.3f} |"
        )

    return "\n".join(linhas)


def sugerir(modelo) -> str:
    upper, forearm = arm_ik.comprimentos_braco(modelo)
    alcance = (upper + forearm) * FRACAO_ALCANCE
    passos = int(alcance / PASSO_GRADE_U) + 1
    eixo = range(-passos, passos + 1)
    livres = []

    for i, j, k in itertools.product(eixo, eixo, eixo):
        candidato = (i * PASSO_GRADE_U, j * PASSO_GRADE_U, k * PASSO_GRADE_U)
        distancia = math.dist(candidato, (0.0, 0.0, 0.0))

        if not ALCANCE_MINIMO_U <= distancia <= alcance:
            continue

        pose = _pose_simetrica(modelo, candidato, ALVOS["idle"].polo)

        if cb.penetracao_do_lado(modelo, "right", pose) <= cb.FOLGA_PENETRACAO_U:
            livres.append(candidato)

    linhas = [
        f"Pontos livres na grade de {PASSO_GRADE_U} u: {len(livres)}; menor 'cima': "
        f"{min(c[1] for c in livres):.2f}" if livres else "Nenhum ponto livre.",
        "",
        "| alvo | atual | livre mais próximo | distância |",
        "|---|---|---|---|",
    ]

    for nome, alvo in ALVOS.items():
        if not livres:
            break

        alvo_atual = alvo.alvo
        melhor = min(livres, key=lambda c: math.dist(c, alvo_atual))
        linhas.append(f"| {nome} | {_fmt(alvo.alvo)} | {_fmt(melhor)} | {math.dist(melhor, alvo.alvo):.3f} |")

    return "\n".join(linhas)


def tronco() -> str:
    from panda3d.core import NodePath, loadPrcFileData

    loadPrcFileData("", "window-type none\naudio-library-name null")
    import gltf

    raiz = NodePath(gltf.load_model(str(resolve_model())))
    referencia = raiz.find("**/body").getParent()
    cabeca = raiz.find("**/head")
    pivo = raiz.attachNewNode("pivo-teste")
    pivo.setPos(referencia, 0, 0, 0.44)
    pivo.setHpr(referencia, 0, 0, 0)
    cabeca.wrtReparentTo(pivo)
    base = cabeca.getPos(referencia)
    linhas = ["| pivô (relativo ao nó raiz do asset) | cabeça vai para |", "|---|---|"]

    for nome, hpr in (("pitch +10", (0, 10, 0)), ("roll +10", (0, 0, 10)), ("yaw +10", (10, 0, 0))):
        pivo.setHpr(referencia, *hpr)
        p = cabeca.getPos(referencia)
        delta = (p.x - base.x, p.y - base.y, p.z - base.z)
        linhas.append(f"| {nome} | {_direcao(delta) if nome != 'yaw +10' else 'gira (rosto)'} |")
        pivo.setHpr(referencia, 0, 0, 0)

    return "\n".join(linhas)


#: Flexão de teste (graus) de cada junta ao provar o eixo de dobra dos dedos.
FLEXAO_TESTE_DEDO_GRAUS = 30.0
#: Rótulos das mãos e do dedo na tabela (índice 0 = polegar).
NOMES_DEDOS = ("polegar", "indicador", "médio", "anelar", "mindinho")


def medir_dedos(modelo) -> list[dict]:
    """Por dedo: eixo no referencial do mascote, deslocamento da ponta (FK) e erro contra o Panda.

    A FK usa o grupo ``fingers``/``fingers2`` (``cinematica.transformacao_no``) e a
    cadeia de pivôs fatiada pelo renderer; o Panda move os mesmos pivôs de verdade.
    """
    from panda3d.core import NodePath, loadPrcFileData

    loadPrcFileData("", "window-type none\naudio-library-name null")
    import gltf

    from sejoga.animacao import dedos_tuning as T
    from sejoga.render import dedos_malha as dm

    raiz = NodePath(gltf.load_model(str(resolve_model())))
    dm.fatiar_dedos(raiz)
    referencia = raiz.find("**/body").getParent()

    # Mesma pose-base do renderer e da FK: soma a torção base do antebraço.
    for grupo_braco, (eh, ep, er) in cin.BASE_ADICIONAL_GRAUS.items():
        braco = raiz.find(f"**/{grupo_braco}")
        h, p, r = braco.getHpr()
        braco.setHpr(h + eh, p + ep, r + er)

    linhas = []

    for grupo, meshes in (("fingers", T.MESH_DEDOS_DIREITA), ("fingers2", T.MESH_DEDOS_ESQUERDA)):
        no_grupo = raiz.find(f"**/{grupo}")
        rot, origem = cin.transformacao_no(modelo, grupo)

        for dedo, mesh in enumerate(meshes):
            cadeia = dm.pivos_da_cadeia(raiz, mesh)
            pivos = [_tupla(p.getPos(no_grupo)) for p, _ in cadeia]
            eixos = [_tupla(no_grupo.getRelativeVector(p, e)) for p, e in cadeia]
            ultimo = raiz.find(f"**/mesh{mesh}-seg{len(cadeia) - 1}")
            baixo, alto = ultimo.getTightBounds(no_grupo)
            ponta = _tupla((baixo + alto) * 0.5)
            # Ponto rígido do último segmento (a AABB muda ao girar; o ponto não).
            ponta_no_segmento = ultimo.getRelativePoint(no_grupo, (baixo + alto) * 0.5)
            angulos = (FLEXAO_TESTE_DEDO_GRAUS,) * len(cadeia)
            repouso = cin.pontos_cadeia_dedo(rot, origem, pivos, eixos, (0.0,) * len(cadeia), ponta)
            fk = cin.pontos_cadeia_dedo(rot, origem, pivos, eixos, angulos, ponta)

            for pivo, eixo in cadeia:
                dm.girar_pivo(pivo, eixo, FLEXAO_TESTE_DEDO_GRAUS)

            # Pivôs (juntas) e ponta reais do Panda contra a FK pura.
            panda = [_tupla(p.getPos(referencia)) for p, _ in cadeia]
            panda.append(_tupla(referencia.getRelativePoint(ultimo, ponta_no_segmento)))
            erro = max(math.dist(a, b) for a, b in zip(panda, fk, strict=True))
            linhas.append({
                "grupo": grupo, "dedo": dedo, "fk": fk, "repouso": repouso, "erro": erro,
                "deslocamento": cin.subtrair(fk[-1], repouso[-1]),
            })

            for pivo, eixo in cadeia:
                dm.girar_pivo(pivo, eixo, 0.0)

    return linhas


def _tupla(v) -> cin.Vec3:
    return (float(v[0]), float(v[1]), float(v[2]))


def tabela_dedos(modelo) -> str:
    linhas = [
        f"| mão | dedo | +{FLEXAO_TESTE_DEDO_GRAUS:.0f}° por junta move a ponta para | erro FK x Panda (u) |",
        "|---|---|---|---|",
    ]

    for medida in medir_dedos(modelo):
        mao = "direita" if medida["grupo"] == "fingers" else "esquerda"
        linhas.append(
            f"| {mao} | {NOMES_DEDOS[medida['dedo']]} | {_direcao(medida['deslocamento'])} "
            f"| {medida['erro']:.5f} |"
        )

    return "\n".join(linhas)


def _fmt(v) -> str:
    return "(" + ", ".join(f"{c:+.3f}" for c in v) + ")"


def main() -> int:
    parser = argparse.ArgumentParser(description="Oráculo de cena do rig.")
    for flag in ("eixos", "aabbs", "alvos", "sugerir", "tronco", "dedos"):
        parser.add_argument(f"--{flag}", action="store_true")
    parser.add_argument("--saida", type=Path, default=None)
    args = parser.parse_args()
    todos = not any((args.eixos, args.aabbs, args.alvos, args.sugerir, args.tronco, args.dedos))
    modelo = load_model(resolve_model())
    blocos = []

    if args.eixos or todos:
        blocos.append("## Mapa de eixos (FK = grafo de cena)\n\n" + mapa_eixos(modelo))
    if args.aabbs or todos:
        blocos.append("## AABBs das malhas (autoria: +X direita, +Y frente, +Z cima)\n\n" + aabbs())
    if args.alvos or todos:
        blocos.append("## Alvos de braço x FK x penetração\n\n" + tabela_alvos(modelo))
    if args.sugerir:
        blocos.append("## Alvos livres sugeridos\n\n" + sugerir(modelo))
    if args.tronco or todos:
        blocos.append("## Tronco (pivô no referencial do asset)\n\n" + tronco())

    if args.dedos or todos:
        blocos.append("## Cadeia dos dedos (FK x pivôs do Panda)\n\n" + tabela_dedos(modelo))

    texto = "# Oráculo de cena (gerado por tools/oraculo_cena.py)\n\n" + "\n\n".join(blocos) + "\n"

    if args.saida:
        args.saida.write_text(texto, encoding="utf-8", newline="\n")
        print(f"gravado: {args.saida}")
    else:
        sys.stdout.buffer.write(texto.encode("utf-8"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
