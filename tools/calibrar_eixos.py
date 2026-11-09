"""Harness de CALIBRAÇÃO VISUAL de eixos do rig (rodar na GPU do usuário).

Motivo (Frente 3): o código calcula as rotações numa convenção aparentemente
correta (base x/y/z), mas ao RENDERIZAR os membros se movem em direções
opostas/erradas ao pretendido — há um descasamento entre o sistema de eixos em
que o código calcula e o que o Panda3D aplica no modelo. Nenhum teste headless
ou medição automática prova a correção: a FONTE DE VERDADE é o olho do usuário
numa máquina com GPU.

Esta ferramenta NÃO corrige a convenção. Ela DIAGNOSTICA: para CADA articulação
do rig, com o mascote em pose neutra de frente, aplica uma rotação ISOLADA de
teste em UM eixo por vez (+X, -X, +Y, -Y, +Z, -Z) e salva uma captura nomeada
de forma legível. Depois o usuário abre as capturas, anota o que viu de verdade
("ombro_dir +X => braço DESCE, deveria SUBIR") no mapa-RESPOSTA gerado, e esse
mapa preenchido vira a fonte de verdade para corrigir o mapeamento código→tela
numa rodada posterior.

Eixos do ``Rotation3`` aplicados pelo renderer (``renderer.apply_rig_pose``):
``setHpr(base_h + deg(y), base_p + deg(x), base_r + deg(z))`` — ou seja, no
dicionário de pose cada junta recebe ``Rotation3(x, y, z)`` em RADIANOS e o
renderer deriva H=y, P=x, R=z. Este harness varre os três eixos do
``Rotation3`` (x, y, z), nos dois sinais, um de cada vez.

Uso (a partir da raiz do worktree):
    python tools/calibrar_eixos.py                 # todas as juntas, ±X/±Y/±Z
    python tools/calibrar_eixos.py --angulo 50     # amplitude do teste (graus)
    python tools/calibrar_eixos.py --junta ombro_dir
    python tools/calibrar_eixos.py --sem-capturas  # só regenera índice/RESPOSTA

Sem GPU/offscreen (``RenderIndisponivel``), as capturas não saem; o harness
ainda gera o índice e o template de RESPOSTA para o usuário rodar na GPU dele.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass
from math import radians
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sejoga import config
from sejoga.nucleo.rig import Rotation3
from sejoga.rig_mapa.calibrador_estado import JUNTAS

# ─────────────────────────────────────────────────────────────────────────────
# Constantes nomeadas (sem magic numbers soltos)
# ─────────────────────────────────────────────────────────────────────────────
#: Pasta onde as capturas de calibração e os mapas ficam para o usuário.
PASTA_RAIZ = Path(__file__).resolve().parents[1] / ".agents" / "tasks" / "frente3-animacao"
PASTA_CAPTURAS = PASTA_RAIZ / "capturas" / "calibracao"

#: Amplitude default (graus) da rotação de teste por eixo. Grande o bastante
#: para a direção do movimento ser inequívoca na captura, sem estourar o clamp.
ANGULO_TESTE_PADRAO = 45.0

#: Nº de frames renderizados antes da captura (o Panda aplica propriedades de
#: janela e pose de forma assíncrona; alguns frames estabilizam a imagem).
FRAMES_ESTABILIZACAO = 4

#: Eixos do Rotation3 varridos, com rótulo legível. O sinal é aplicado à parte.
#: (nome_do_campo, rótulo). O renderer mapeia x->pitch(P), y->heading(H), z->roll(R).
EIXOS = (
    ("x", "x"),
    ("y", "y"),
    ("z", "z"),
)
#: Sinais varridos por eixo.
SINAIS = ((+1.0, "+"), (-1.0, "-"))

# Juntas calibráveis: fonte única em calibrador_estado (usada também pelo
# calibrador interativo).

#: Efeito ESPERADO (anatômico/intuitivo) por junta+eixo+sinal, em linguagem
#: natural — o que o usuário gostaria de ver quando aplica aquela rotação. É só
#: um palpite de referência para o usuário comparar com o que de fato aparece;
#: a verdade é o que ele anota no campo OBSERVADO. Vazio = sem expectativa fixa.
ESPERADO: dict[tuple[str, str, str], str] = {
    ("ombro_dir", "z", "-"): "braço direito SOBE (mão acima do ombro)",
    ("ombro_dir", "z", "+"): "braço direito DESCE (ao lado do quadril)",
    ("ombro_esq", "z", "+"): "braço esquerdo SOBE (espelho)",
    ("ombro_esq", "z", "-"): "braço esquerdo DESCE (espelho)",
    ("cabeca", "y", "+"): "cabeça olha para a DIREITA da tela",
    ("cabeca", "y", "-"): "cabeça olha para a ESQUERDA da tela",
    ("tronco", "y", "+"): "tronco gira para a DIREITA (mesmo lado da cabeça)",
    ("porta", "y", "+"): "portinha ABRE",
}


class RenderIndisponivel(RuntimeError):
    """Render offscreen não pôde iniciar (sem GPU/driver)."""


@dataclass(frozen=True, slots=True)
class CasoTeste:
    """Um caso de calibração: junta, eixo e sinal a isolar."""

    junta: str          # nome legível (chave de JUNTAS)
    grupo: str          # grupo real do rig
    eixo: str           # "x" | "y" | "z"
    sinal: float        # +1.0 | -1.0
    rotulo_sinal: str   # "+" | "-"

    @property
    def nome(self) -> str:
        """Nome de arquivo legível, ex.: ``ombro_dir__+z``."""
        return f"{self.junta}__{self.rotulo_sinal}{self.eixo}"

    def pose(self, angulo_graus: float) -> dict[str, Rotation3]:
        """Pose neutra com APENAS este eixo desta junta rotacionado."""
        valor = radians(self.sinal * angulo_graus)
        componentes = {"x": 0.0, "y": 0.0, "z": 0.0}
        componentes[self.eixo] = valor
        rot = Rotation3(componentes["x"], componentes["y"], componentes["z"])
        return {self.grupo: rot}


def casos(juntas: dict[str, str]) -> list[CasoTeste]:
    """Gera todos os casos (junta, eixo, sinal) para as juntas pedidas."""
    saida: list[CasoTeste] = []
    for junta, grupo in juntas.items():
        for eixo, _ in EIXOS:
            for sinal, rotulo in SINAIS:
                saida.append(CasoTeste(junta, grupo, eixo, sinal, rotulo))
    return saida


def _perfil() -> Path:
    env = os.environ.get("SEJOGA_CONFIG_PATH")
    if env:
        destino = Path(env)
        destino.parent.mkdir(parents=True, exist_ok=True)
        return destino.parent
    return Path(tempfile.mkdtemp(prefix="sejoga-calibrar-eixos-"))


def capturar(
    juntas: dict[str, str],
    angulo_graus: float = ANGULO_TESTE_PADRAO,
) -> list[CasoTeste]:
    """Sobe o renderer real, aplica cada caso isolado e salva um PNG por caso.

    Devolve a lista de casos efetivamente capturados. Levanta
    ``RenderIndisponivel`` se o offscreen não iniciar (sem GPU).
    """
    perfil = _perfil()
    config.default_config_path = lambda: perfil / "config.toml"

    # ORDEM DE IMPORT CRÍTICA (igual a tools/verificar_eixos.py): o OverlayApp
    # puxa Qt (PySide6); Qt precisa inicializar ANTES de panda3d.core, senão há
    # conflito de DLL e o processo quebra com access violation. Importar
    # panda3d.core primeiro é o bug clássico — manter window/OverlayApp no topo.
    # isort: off
    try:
        from sejoga.render.window import OverlayApp
        from panda3d.core import Filename
    except Exception as exc:  # pragma: no cover - ambiente sem engine
        raise RenderIndisponivel(str(exc)) from exc
    # isort: on

    settings = config.Settings()
    settings.physics.enabled = False
    settings.music.enabled = False

    try:
        app = OverlayApp(settings)
    except Exception as exc:  # pragma: no cover - sem GPU/offscreen
        raise RenderIndisponivel(str(exc)) from exc

    # Desliga hotkeys e o polling de mouse; a POSE é dirigida por dentro do
    # tick de animação (mesmo idioma de tools/verificar_eixos.py), que também
    # roda apêndices/body_motion — aplicar a pose por fora do tick e dar step()
    # deixa sistemas nativos (tentáculos) em estado inconsistente e quebra.
    # Após o boot, estes componentes do OverlayApp existem (Optional só porque
    # são criados em etapas). As asserções narram o invariante e satisfazem o
    # type checker sem silenciar erros.
    assert app.hotkey_manager is not None
    assert app.animation_controller is not None
    assert app.debug_tools is not None
    assert app.music_listener is not None
    assert app.desktop is not None
    app.hotkey_manager.close()
    app.taskMgr.remove("mouse-poll")
    renderer = app.renderer
    animation = app.animation_controller

    # A pose vem de uma atualização de animação REAL (idle) a cada frame — isso
    # mantém body_motion/apêndices/tentáculos em estado nativo válido (dirigir a
    # pose por fora de animation.update quebra o render nativo). Sobre essa pose
    # idle o tick SUBSTITUI apenas a(s) junta(s) do caso de teste (override), de
    # modo que a captura isole o eixo pedido sem desestabilizar o resto.
    override: dict[str, Rotation3] = {}

    def tick() -> None:
        # Roda a animação real só pelos EFEITOS COLATERAIS (mantém body_motion,
        # apêndices e tentáculos em estado nativo válido). A pose renderizada,
        # porém, é NEUTRA (todas as juntas em repouso) + o override do caso, para
        # a captura isolar o eixo testado sem o ruído do idle.
        animation.update(
            1 / 60, grounded=True, idle_enabled=True,
            sleep_after_idle_seconds=600,
        )
        pose = {grupo: Rotation3() for grupo in JUNTAS.values()}
        pose.update(override)
        renderer.apply_rig_pose(pose)
        renderer.apply_body_motion(
            animation.body_motion.snapshot, None, grounded=True, dragging=False
        )
        renderer.update_appendages(1 / 60, animation.appendage_remaining > 0)

    # Troca o tick de animação (mesmo padrão de verificar_eixos.py). O
    # ignore cobre o method-assign do mypy sem recorrer a setattr (ruff B010).
    app._animation_tick = tick  # type: ignore[method-assign]

    PASTA_CAPTURAS.mkdir(parents=True, exist_ok=True)
    lista = casos(juntas)

    def render_e_salvar(pose_override: dict[str, Rotation3], nome: str) -> None:
        override.clear()
        override.update(pose_override)
        for _ in range(FRAMES_ESTABILIZACAO):
            app.taskMgr.step()
        _salvar(app, Filename, nome)

    try:
        # Baseline: idle puro, sem override — referência "de frente, neutro".
        render_e_salvar({}, "_neutro__base")
        for caso in lista:
            render_e_salvar(caso.pose(angulo_graus), caso.nome)
    finally:
        app.debug_tools.close()
        app.music_listener.stop()
        app.tray_icon.hide()
        app.desktop.close()
        app.desktop = None
        app.destroy()

    return lista


def _salvar(app, Filename, nome: str) -> None:
    """Salva o framebuffer atual como ``<nome>.png`` na pasta de capturas."""
    caminho = PASTA_CAPTURAS / f"{nome}.png"
    app.win.getScreenshot().write(Filename.fromOsSpecific(str(caminho)))


#: Margem (px) entre os quadros do contact sheet por junta.
CONTACT_MARGEM = 6
#: Altura (px) da faixa de rótulo sob cada quadro no contact sheet.
CONTACT_ROTULO_ALT = 18


def gerar_contact_sheets(juntas: dict[str, str]) -> list[Path]:
    """Monta, por junta, um PNG único com os 6 eixos lado a lado (±X/±Y/±Z).

    Facilita a revisão humana: numa imagem só, o usuário vê o neutro e as seis
    rotações isoladas da junta. Requer PIL (já usado pelos tools de preview).
    Retorna os contact sheets efetivamente gerados (pula os sem capturas).
    """
    try:
        from PIL import Image, ImageDraw
    except Exception:  # pragma: no cover - sem PIL
        return []

    gerados: list[Path] = []
    #: Ordem dos quadros: +x,-x,+y,-y,+z,-z (segue EIXOS e SINAIS).
    ordem = [f"{rotulo}{eixo}" for eixo, _ in EIXOS for _sinal, rotulo in SINAIS]

    neutro_path = PASTA_CAPTURAS / "_neutro__base.png"

    for junta in juntas:
        quadros: list[tuple[str, Path]] = []
        if neutro_path.is_file():
            quadros.append(("neutro", neutro_path))
        for tag in ordem:
            caminho = PASTA_CAPTURAS / f"{junta}__{tag}.png"
            if caminho.is_file():
                quadros.append((tag, caminho))

        if len(quadros) <= 1:
            continue

        imagens = [(rot, Image.open(p).convert("RGB")) for rot, p in quadros]
        larg = max(img.width for _, img in imagens)
        alt = max(img.height for _, img in imagens)
        n = len(imagens)
        total_l = n * larg + (n + 1) * CONTACT_MARGEM
        total_a = alt + CONTACT_ROTULO_ALT + 2 * CONTACT_MARGEM
        folha = Image.new("RGB", (total_l, total_a), (255, 255, 255))
        desenho = ImageDraw.Draw(folha)

        for i, (rot, img) in enumerate(imagens):
            x = CONTACT_MARGEM + i * (larg + CONTACT_MARGEM)
            folha.paste(img, (x, CONTACT_MARGEM))
            desenho.text((x + 2, CONTACT_MARGEM + alt + 2), rot, fill=(0, 0, 0))

        destino = PASTA_CAPTURAS / f"_contact__{junta}.png"
        folha.save(destino)
        gerados.append(destino)

    return gerados


def _linha_indice(caso: CasoTeste) -> str:
    esperado = ESPERADO.get((caso.junta, caso.eixo, caso.rotulo_sinal), "—")
    return f"| {caso.junta} | {caso.rotulo_sinal}{caso.eixo} | `{caso.nome}.png` | {esperado} |"


def escrever_indice(juntas: dict[str, str], angulo_graus: float) -> Path:
    """Escreve o índice das capturas (tabela por junta/eixo/sinal)."""
    PASTA_CAPTURAS.mkdir(parents=True, exist_ok=True)
    destino = PASTA_CAPTURAS / "INDICE.md"
    linhas = [
        "# Índice de capturas — calibração de eixos",
        "",
        f"Amplitude de teste: **{angulo_graus:g}°** por eixo. Modelo em pose neutra de frente.",
        "",
        "Cada captura isola UMA junta e UM eixo (±). Abra o PNG e compare o",
        "movimento real com a coluna 'efeito esperado'. Anote o que viu em",
        "`mapa-eixos-RESPOSTA.md`.",
        "",
        "| articulação | eixo | arquivo | efeito esperado (referência) |",
        "|---|---|---|---|",
    ]
    linhas += [_linha_indice(c) for c in casos(juntas)]
    linhas.append("")
    destino.write_text("\n".join(linhas), encoding="utf-8", newline="\n")
    return destino


def escrever_template_resposta(juntas: dict[str, str], angulo_graus: float) -> Path:
    """Gera o template que o usuário preenche com o efeito OBSERVADO na tela."""
    destino = PASTA_RAIZ / "mapa-eixos-RESPOSTA.md"
    linhas = [
        "# Mapa de eixos — RESPOSTA do usuário (fonte de verdade visual)",
        "",
        "Preencha a coluna **OBSERVADO** com o que a captura mostrou de verdade,",
        "em linguagem natural (ex.: 'braço DESCE', 'gira para a ESQUERDA',",
        "'entra no corpo'). A coluna **esperado** é só referência. Depois de",
        "preenchido, este arquivo guia a correção do mapeamento código→tela.",
        "",
        f"Amplitude de teste usada: {angulo_graus:g}° por eixo. Capturas em",
        "`capturas/calibracao/` (um PNG por linha).",
        "",
        "Legenda dos eixos do Rotation3 (o que o código escreve): o renderer faz",
        "`setHpr(H=y, P=x, R=z)`. Então no dicionário de pose: x = pitch (P),",
        "y = heading (H), z = roll (R).",
        "",
        "| articulação | grupo do rig | eixo | arquivo | esperado (ref.) | OBSERVADO (preencher) |",
        "|---|---|---|---|---|---|",
    ]
    for c in casos(juntas):
        esperado = ESPERADO.get((c.junta, c.eixo, c.rotulo_sinal), "")
        linhas.append(
            f"| {c.junta} | `{c.grupo}` | {c.rotulo_sinal}{c.eixo} | "
            f"`{c.nome}.png` | {esperado} |  |"
        )
    linhas += [
        "",
        "## Resumo por junta (preencher após olhar as 6 capturas de cada)",
        "",
        "Para cada junta, diga qual eixo+sinal do código produz CADA efeito real:",
        "",
    ]
    for junta, grupo in juntas.items():
        linhas += [
            f"### {junta} (`{grupo}`)",
            "- sobe/ergue:  ",
            "- desce/baixa:  ",
            "- gira/olha p/ direita:  ",
            "- gira/olha p/ esquerda:  ",
            "- inclina p/ frente:  ",
            "- inclina p/ trás:  ",
            "- movimento ERRADO/não-anatômico observado:  ",
            "",
        ]
    destino.write_text("\n".join(linhas), encoding="utf-8", newline="\n")
    return destino


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Harness de calibração visual de eixos do rig (uma rotação isolada por captura)."
    )
    parser.add_argument("--angulo", type=float, default=ANGULO_TESTE_PADRAO,
                        help="amplitude da rotação de teste por eixo (graus)")
    parser.add_argument("--junta", default=None,
                        help="calibra só esta junta (nome legível); default: todas")
    parser.add_argument("--sem-capturas", action="store_true",
                        help="não sobe o render; só (re)gera índice e template de resposta")
    args = parser.parse_args()

    if args.junta:
        if args.junta not in JUNTAS:
            print(f"junta desconhecida: {args.junta!r}. Opções: {', '.join(JUNTAS)}",
                  file=sys.stderr)
            return 2
        juntas = {args.junta: JUNTAS[args.junta]}
    else:
        juntas = dict(JUNTAS)

    capturadas = 0
    if not args.sem_capturas:
        try:
            capturadas = len(capturar(juntas, args.angulo))
            print(f"capturas salvas em {PASTA_CAPTURAS} ({capturadas} casos + neutro)", flush=True)
        except RenderIndisponivel as exc:
            print(f"RENDER INDISPONÍVEL (sem GPU/offscreen): {exc}", file=sys.stderr, flush=True)
            print("Gerando índice e template mesmo assim para rodar na GPU.", file=sys.stderr, flush=True)

    indice = escrever_indice(juntas, args.angulo)
    resposta = escrever_template_resposta(juntas, args.angulo)
    folhas = gerar_contact_sheets(juntas)
    print(f"índice:   {indice}", flush=True)
    print(f"resposta: {resposta}", flush=True)
    print(f"contact sheets: {len(folhas)} em {PASTA_CAPTURAS}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
