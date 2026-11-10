"""Calibrador INTERATIVO de eixos do rig (rodar na máquina com GPU/desktop).

Abre o mascote ao vivo no renderer REAL (o mesmo do app, já com a orientação de
frente assada no asset). Você escolhe uma junta, gira um eixo e vê o efeito
na hora; o HUD mostra junta, eixo, sinal e valor aplicado. Ao reconhecer o que
o membro fez, aperta UMA tecla de direção e a ferramenta marca
"junta + eixo + sinal => direção" e já pula para o próximo teste (modo guiado).
O resultado é salvo em JSON (consumível pelo código) e Markdown (legível).

A lógica de estado vive em ``sejoga.rig_mapa.calibrador_estado`` (pura e
testada); aqui só há janela, teclado e HUD.

Uso (a partir da raiz do worktree):
    python tools/calibrar_interativo.py
    python tools/calibrar_interativo.py --novo                # ignora o arquivo salvo
    python tools/calibrar_interativo.py --saida C:\\tmp\\mapa.json
    python tools/calibrar_interativo.py --capturar saida.png --teste ombro_dir:z:-45

``--capturar`` é o modo sem interação: aplica ``junta:eixo:graus``, renderiza e
salva um PNG (com HUD) para checagem programática; não abre loop de teclado.

MODO CONFIRMAR (Parte 3, recomendado): o mapa de eixos já sai do grafo de cena
(``tools/oraculo_cena.py``). Aqui o usuário só confirma as poses REAIS do app:
    python tools/calibrar_interativo.py --confirmar
    python tools/calibrar_interativo.py --confirmar --capturar x.png --pose aceno
Teclas: 1 correto, 2 errado, 3 pular, v frente/lado, setas navegam, esc salva e
sai. Respostas em ``confirmacao-parte3.json`` (ver recalibracao-gpu.md).
"""
# Pilota atributos Optional do OverlayApp e troca _animation_tick, igual aos
# demais tools.
# mypy: disable-error-code="union-attr, method-assign"
from __future__ import annotations

import argparse
import contextlib
import os
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sejoga import configuracao
from sejoga.nucleo.esqueleto import Rotation3
from sejoga.rig_mapa.calibrador_estado import (
    JUNTAS,
    PASSO_FINO_GRAUS,
    PASSO_GROSSO_GRAUS,
    PASSO_PADRAO_GRAUS,
    Direcao,
    Eixo,
    EstadoCalibrador,
)
from sejoga.rig_mapa.confirmacao_poses import ConfirmacaoPoses, Resposta

# ─────────────────────────────────────────────────────────────────────────────
# Constantes nomeadas
# ─────────────────────────────────────────────────────────────────────────────
PASTA_RAIZ = Path(__file__).resolve().parents[1] / ".agents" / "tasks" / "frente3-animacao"
ARQUIVO_JSON_PADRAO = PASTA_RAIZ / "mapa-eixos-CALIBRADO.json"
ARQUIVO_CONFIRMACAO_PADRAO = PASTA_RAIZ / "confirmacao-parte3.json"
#: Tecla -> resposta do modo confirmar.
TECLAS_RESPOSTA: dict[str, Resposta] = {"1": Resposta.CORRETO, "2": Resposta.ERRADO, "3": Resposta.PULADO}

#: Lado (px) da janela do calibrador: maior que o overlay para ver bem o membro.
TAMANHO_JANELA = 720
#: Posição inicial (px) do canto superior esquerdo da janela.
JANELA_X = 60
JANELA_Y = 40
#: Frames de estabilização antes de capturar/ao abrir (propriedades assíncronas).
FRAMES_ESTABILIZACAO = 6
#: Passo de tempo de animação fixo usado para os efeitos colaterais do tick.
DT_ANIMACAO = 1 / 60
#: Quantos segundos o idle espera antes de dormir (desligado na prática).
SEGUNDOS_ATE_DORMIR = 600

#: Estilos de dança e gestos disparáveis pelo modo confirmar.
ESTILOS_DANCA = ("head_bob", "hip_hop", "rock", "breakdance")
GESTOS = (
    "wave", "stretch", "peek", "sneeze", "click", "double_click",
    "pet", "poke", "hang_loose", "thumbs_up", "finger_gun", "land", "hit",
)

#: Passos de giro alternáveis pela tecla ``p``.
PASSOS_GRAUS = (PASSO_FINO_GRAUS, PASSO_PADRAO_GRAUS, PASSO_GROSSO_GRAUS)

#: Visões da câmera/modelo: (rótulo, heading do modelo em graus).
VISOES = (("frente", 0.0), ("lado", 90.0))

#: Tecla -> direção marcada. Um toque registra o que foi visto.
TECLAS_DIRECAO: dict[str, Direcao] = {
    "w": Direcao.SOBE,
    "s": Direcao.DESCE,
    "a": Direcao.ESQUERDA,
    "d": Direcao.DIREITA,
    "f": Direcao.FRENTE,
    "t": Direcao.TRAS,
    "i": Direcao.DENTRO,
    "o": Direcao.FORA,
    "n": Direcao.NENHUM,
}
TECLAS_EIXO: dict[str, Eixo] = {"x": Eixo.X, "y": Eixo.Y, "z": Eixo.Z}

#: Layout do HUD (coordenadas aspect2d / escala de texto).
ESCALA_TEXTO = 0.042
MARGEM_X = 0.02
MARGEM_Y = -0.06
FUNDO_TEXTO = (0.0, 0.0, 0.0, 0.65)
COR_TEXTO = (1.0, 1.0, 1.0, 1.0)

AJUDA = (
    "TECLAS  (clique na janela uma vez para dar foco)",
    "w sobe  s desce  a esquerda(tela)  d direita(tela)  f frente  t tras",
    "i dentro (entra no corpo)  o fora (afasta do corpo)  n nenhum  u desfaz",
    "setas cima/baixo: gira o eixo   setas esq/dir ou Tab: troca junta",
    "x y z: eixo   p: passo   espaco: +45/-45/0   backspace: zera eixo",
    "r: zera junta   delete: zera tudo   b: pula   g: modo guiado",
    "v: visao frente/lado   enter: salva   h: esconde ajuda   esc: salva e sai",
)


def _perfil() -> Path:
    env = os.environ.get("SEJOGA_CONFIG_PATH")
    if env:
        destino = Path(env)
        destino.parent.mkdir(parents=True, exist_ok=True)
        return destino.parent
    return Path(tempfile.mkdtemp(prefix="sejoga-calibrar-interativo-"))


def _sem_acentos(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in base if not unicodedata.combining(c))


class RenderIndisponivel(RuntimeError):
    """O renderer não pôde iniciar (sem GPU/driver/desktop)."""


class Calibrador:
    """Janela interativa: liga teclado, HUD e pose ao ``EstadoCalibrador``."""

    def __init__(self, estado: EstadoCalibrador, saida_json: Path) -> None:
        self.estado = estado
        self.saida_json = saida_json
        self.saida_md = saida_json.with_suffix(".md")
        self.guiado = True
        self.passo_indice = 1
        self.visao_indice = 0
        self.mostrar_ajuda = True
        self.sair = False
        self._subir()

    # ------------------------------------------------------------------ boot
    def _subir(self) -> None:
        perfil = _perfil()
        configuracao.default_config_path = lambda: perfil / "config.toml"

        # ORDEM DE IMPORT CRÍTICA: Qt (via OverlayApp) antes de panda3d.core.
        # isort: off
        try:
            from sejoga.render.window import OverlayApp
            from panda3d.core import Filename, TextNode
            from direct.gui.OnscreenText import OnscreenText
        except Exception as exc:  # pragma: no cover - ambiente sem engine
            raise RenderIndisponivel(str(exc)) from exc
        # isort: on
        self._Filename = Filename

        settings = configuracao.Settings()
        settings.physics.enabled = False
        settings.music.enabled = False
        settings.window.size = TAMANHO_JANELA
        settings.window.mode = "overlay"
        settings.window.always_on_top = False
        settings.window.start_position = (JANELA_X, JANELA_Y)
        settings.behavior.sleep_after_idle_seconds = SEGUNDOS_ATE_DORMIR

        try:
            self.app = OverlayApp(settings)
        except Exception as exc:  # pragma: no cover - sem GPU
            raise RenderIndisponivel(str(exc)) from exc

        app = self.app
        app.hotkey_manager.close()
        # Tarefas do app que reaplicariam estilo overlay/topmost/color key.
        for tarefa in ("mouse-poll", "restore-z-order", "background-key"):
            app.taskMgr.remove(tarefa)
        self.renderer = app.renderer
        self.animation = app.animation_controller
        app._animation_tick = self._tick

        self._tornar_janela_comum()
        self._criar_hud(OnscreenText, TextNode)
        self._ligar_teclas()
        app.taskMgr.add(self._tarefa_hud, "calibrador-hud")
        app.taskMgr.add(self._tarefa_encerramento, "calibrador-encerramento")
        for _ in range(FRAMES_ESTABILIZACAO):
            app.taskMgr.step()

    def _tornar_janela_comum(self) -> None:
        """Remove o estilo overlay (sem foco/transparente) para receber teclado."""
        import win32con
        import win32gui

        hwnd = self.app.hwnd
        estilo = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        retirar = (
            win32con.WS_EX_LAYERED
            | win32con.WS_EX_NOACTIVATE
            | win32con.WS_EX_TOPMOST
            | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_TOOLWINDOW
        )
        estilo = (estilo & ~retirar) | win32con.WS_EX_APPWINDOW
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, estilo)
        win32gui.SetWindowPos(
            hwnd, win32con.HWND_NOTOPMOST, JANELA_X, JANELA_Y, 0, 0,
            win32con.SWP_FRAMECHANGED | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
        )
        # O Windows pode negar o foco; nesse caso o usuário clica na janela.
        with contextlib.suppress(Exception):
            win32gui.SetForegroundWindow(hwnd)

    # ------------------------------------------------------------------- HUD
    def _criar_hud(self, OnscreenText, TextNode) -> None:
        fonte = self._carregar_fonte()
        self._fonte_ok = fonte is not None
        comum = dict(
            scale=ESCALA_TEXTO, fg=COR_TEXTO, bg=FUNDO_TEXTO,
            align=TextNode.ALeft, mayChange=True, font=fonte,
        )
        self._hud = OnscreenText(
            text="", parent=self.app.a2dTopLeft, pos=(MARGEM_X, MARGEM_Y), **comum
        )
        self._ajuda = OnscreenText(
            text="", parent=self.app.a2dBottomLeft, pos=(MARGEM_X, 0.35), **comum
        )

    def _carregar_fonte(self):
        """Fonte do Windows com acentos; ``None`` cai na fonte padrão do Panda."""
        pasta = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf"
        if not pasta.is_file():
            return None
        try:
            return self.app.loader.loadFont(self._Filename.fromOsSpecific(str(pasta)))
        except Exception:
            return None

    def _texto(self, linhas: list[str]) -> str:
        texto = "\n".join(linhas)
        return texto if self._fonte_ok else _sem_acentos(texto)

    def _linhas_status(self) -> list[str]:
        visao = VISOES[self.visao_indice][0]
        extra = (
            f"modo {'GUIADO' if self.guiado else 'LIVRE'} | passo "
            f"{PASSOS_GRAUS[self.passo_indice]:g} | visao {visao}"
        )
        return [*self.estado.linhas_hud(), extra]

    def _tarefa_hud(self, task):
        self._hud.setText(self._texto(self._linhas_status()))
        self._ajuda.setText(self._texto(list(AJUDA) if self.mostrar_ajuda else []))
        return task.cont

    # ------------------------------------------------------------------ pose
    def _tick(self) -> None:
        # Animação real só pelos efeitos colaterais (body_motion, apêndices,
        # tentáculos em estado nativo válido); a pose desenhada é NEUTRA + o
        # que o calibrador mandou, para isolar o eixo em teste.
        self.animation.update(
            DT_ANIMACAO, grounded=True, idle_enabled=True,
            sleep_after_idle_seconds=SEGUNDOS_ATE_DORMIR,
        )
        pose = {grupo: Rotation3() for grupo in JUNTAS.values()}
        pose.update(self.estado.pose())
        self.renderer.apply_rig_pose(pose)
        self.renderer.apply_body_motion(
            self.animation.body_motion.snapshot, None, grounded=True, dragging=False
        )
        self.renderer.update_appendages(DT_ANIMACAO, self.animation.appendage_remaining > 0)

    # ---------------------------------------------------------------- teclado
    def _ligar_teclas(self) -> None:
        a = self.app.accept
        for tecla, direcao in TECLAS_DIRECAO.items():
            a(tecla, self.marcar, [direcao])
        for tecla, eixo in TECLAS_EIXO.items():
            a(tecla, self.estado.selecionar_eixo, [eixo])
        for tecla, sentido in (("arrow_up", 1), ("arrow_down", -1)):
            a(tecla, self.girar, [sentido])
            a(f"{tecla}-repeat", self.girar, [sentido])
        for tecla, passo in (("arrow_right", 1), ("tab", 1), ("arrow_left", -1)):
            a(tecla, self.estado.proxima_junta, [passo])
        a("p", self.alternar_passo)
        a("space", self.estado.alternar_teste)
        a("backspace", self.estado.zerar_eixo)
        a("r", self.estado.zerar_junta)
        a("delete", self.estado.zerar_tudo)
        a("u", self.estado.desmarcar)
        a("b", self.pular)
        a("g", self.alternar_guiado)
        a("v", self.alternar_visao)
        a("h", self.alternar_ajuda)
        a("enter", self.salvar)
        a("escape", self.encerrar)

    def girar(self, sentido: int) -> None:
        self.estado.girar(sentido * PASSOS_GRAUS[self.passo_indice])

    def marcar(self, direcao: Direcao) -> None:
        if not self.estado.marcar(direcao):
            return
        self.estado.salvar(self.saida_json, self.saida_md)
        if self.guiado:
            self.pular()

    def pular(self) -> None:
        if not self.estado.ir_para_proximo_pendente():
            self.estado.mensagem = "Tudo marcado. Enter salva, Esc salva e sai."

    def alternar_passo(self) -> None:
        self.passo_indice = (self.passo_indice + 1) % len(PASSOS_GRAUS)

    def alternar_guiado(self) -> None:
        self.guiado = not self.guiado
        if self.guiado:
            self.estado.ir_para_proximo_pendente(incluir_atual=True)

    def alternar_ajuda(self) -> None:
        self.mostrar_ajuda = not self.mostrar_ajuda

    def alternar_visao(self) -> None:
        self.visao_indice = (self.visao_indice + 1) % len(VISOES)
        self.renderer.set_model_rotation(y=VISOES[self.visao_indice][1])

    def salvar(self) -> None:
        self.estado.salvar(self.saida_json, self.saida_md)
        self.estado.mensagem = f"Salvo em {self.saida_json.name} e {self.saida_md.name}"

    def encerrar(self) -> None:
        self.salvar()
        self.sair = True

    def _tarefa_encerramento(self, task):
        """Fechar pelo X da janela também salva e sai."""
        if "quit" in self.app.desktop.requests:
            self.encerrar()
        return task.cont

    # ------------------------------------------------------------------ laço
    def executar(self) -> None:
        if self.guiado:
            self.estado.ir_para_proximo_pendente(incluir_atual=True)
        try:
            while not self.sair:
                self.app.taskMgr.step()
        finally:
            self.fechar()

    def capturar(self, destino: Path) -> None:
        """Renderiza alguns frames no estado atual e salva um PNG (com HUD)."""
        try:
            for _ in range(FRAMES_ESTABILIZACAO):
                self.app.taskMgr.step()
            destino.parent.mkdir(parents=True, exist_ok=True)
            self.app.win.getScreenshot().write(self._Filename.fromOsSpecific(str(destino)))
        finally:
            self.fechar()

    def fechar(self) -> None:
        app = self.app
        app.debug_tools.close()
        app.music_listener.stop()
        app.tray_icon.hide()
        app.desktop.close()
        app.desktop = None
        app.destroy()


def _pilotar(animation, estado: str):
    """Entrada de animation.update apropriada ao estado."""
    velocidade = (0.0, 0.0)
    arrastando = gravidade = musica = False
    aterrado = True
    if estado == "walk":
        velocidade = (120.0, 0.0)
    elif estado == "run":
        velocidade = (520.0, 0.0)
    elif estado == "drag":
        arrastando = True
    elif estado == "fall":
        aterrado = False
        gravidade = True
        velocidade = (0.0, 600.0)
    elif estado == "dance" or estado in ESTILOS_DANCA:
        musica = True
    return animation.update(
        DT_ANIMACAO,
        velocity=velocidade,
        grounded=aterrado,
        gravity_active=gravidade,
        dragging=arrastando,
        music_playing=musica,
        music_intensity=1.0 if musica else 0.0,
        music_bass=0.8 if musica else 0.0,
        music_bpm=120 if musica else None,
        dance_chance=1.0 if musica else 0.0,
        react_to_beat=musica,
        beat_detected=musica,
        idle_enabled=True,
        sleep_after_idle_seconds=0 if estado == "sleep" else SEGUNDOS_ATE_DORMIR,
    )


class Confirmador(Calibrador):
    """Modo confirmar: mostra as poses reais do app e registra 1/2/3."""

    def __init__(self, confirmacao: ConfirmacaoPoses, saida_json: Path) -> None:
        self.confirmacao = confirmacao
        self._estado_disparado: str | None = None
        super().__init__(EstadoCalibrador(), saida_json)
        self.guiado = False

    def _linhas_status(self) -> list[str]:
        return [*self.confirmacao.linhas_hud(), f"visao {VISOES[self.visao_indice][0]}"]

    def _tarefa_hud(self, task):
        self._hud.setText(self._texto(self._linhas_status()))
        self._ajuda.setText("")
        return task.cont

    def _disparar(self, estado: str) -> None:
        if estado in ESTILOS_DANCA:
            self.animation.preview_dance(estado)
        elif estado in GESTOS:
            self.animation.interact(estado)
        self._estado_disparado = estado

    def _tick(self) -> None:
        estado = self.confirmacao.atual.estado
        # O estado pode ser None antes do primeiro update do controller.
        atual = getattr(self.animation.state, "value", None)
        gesto_acabou = estado in GESTOS and atual is not None and atual != estado
        if estado != self._estado_disparado or gesto_acabou:
            self._disparar(estado)
        pose = _pilotar(self.animation, estado)
        self.renderer.apply_rig_pose(pose)
        self.renderer.apply_body_motion(
            self.animation.body_motion.snapshot, None, grounded=True, dragging=estado == "drag"
        )
        self.renderer.update_appendages(DT_ANIMACAO, self.animation.appendage_remaining > 0)

    def _ligar_teclas(self) -> None:
        a = self.app.accept
        for tecla, resposta in TECLAS_RESPOSTA.items():
            a(tecla, self.responder, [resposta])
        a("arrow_right", self.confirmacao.avancar, [1])
        a("arrow_left", self.confirmacao.avancar, [-1])
        a("v", self.alternar_visao)
        a("enter", self.salvar)
        a("escape", self.encerrar)

    def responder(self, resposta: Resposta) -> None:
        self.confirmacao.responder(resposta)
        self.salvar()

    def salvar(self) -> None:
        self.confirmacao.salvar(self.saida_json)
        self.confirmacao.mensagem = f"Salvo em {self.saida_json.name}"

    def executar(self) -> None:
        try:
            while not self.sair:
                self.app.taskMgr.step()
        finally:
            self.fechar()


def _main_confirmar(args) -> int:
    confirmacao = ConfirmacaoPoses()
    if args.saida_confirmacao.is_file() and not args.novo:
        print(f"{confirmacao.carregar(args.saida_confirmacao)} respostas carregadas", flush=True)
    if args.pose:
        confirmacao.selecionar(args.pose)
    try:
        confirmador = Confirmador(confirmacao, args.saida_confirmacao)
    except RenderIndisponivel as exc:
        print(f"RENDER INDISPONÍVEL: {exc}", file=sys.stderr, flush=True)
        return 1
    if args.capturar:
        confirmador.capturar(args.capturar)
        print(f"captura: {args.capturar}", flush=True)
        return 0
    confirmador.executar()
    print(f"respostas salvas em {args.saida_confirmacao}", flush=True)
    return 0


def _aplicar_teste(estado: EstadoCalibrador, texto: str) -> None:
    """Interpreta ``junta:eixo:graus`` e aplica no estado."""
    try:
        junta, eixo, graus = texto.split(":")
        estado.selecionar_junta(junta)
        estado.selecionar_eixo(Eixo(eixo))
        estado.definir_valor(float(graus))
    except (ValueError, KeyError) as exc:
        raise SystemExit(f"--teste inválido ({texto!r}): use junta:eixo:graus. {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrador interativo de eixos do rig.")
    parser.add_argument("--saida", type=Path, default=ARQUIVO_JSON_PADRAO,
                        help="arquivo JSON do mapa (o .md fica ao lado)")
    parser.add_argument("--novo", action="store_true",
                        help="não carrega marcações já salvas")
    parser.add_argument("--capturar", type=Path, default=None,
                        help="modo sem interação: salva um PNG do estado e sai")
    parser.add_argument("--teste", default=None,
                        help="com --capturar: junta:eixo:graus (ex.: ombro_dir:z:-45)")
    parser.add_argument("--confirmar", action="store_true",
                        help="modo confirmar: poses reais do app, teclas 1/2/3")
    parser.add_argument("--pose", default=None, help="com --confirmar: pose inicial (ex.: aceno)")
    parser.add_argument("--saida-confirmacao", type=Path, default=ARQUIVO_CONFIRMACAO_PADRAO)
    args = parser.parse_args()

    if args.confirmar:
        return _main_confirmar(args)

    estado = EstadoCalibrador()
    if args.saida.is_file() and not args.novo:
        carregadas = estado.carregar(args.saida)
        print(f"{carregadas} marcações carregadas de {args.saida}", flush=True)
    if args.teste:
        _aplicar_teste(estado, args.teste)

    try:
        calibrador = Calibrador(estado, args.saida)
    except RenderIndisponivel as exc:
        print(f"RENDER INDISPONÍVEL: {exc}", file=sys.stderr, flush=True)
        return 1

    if args.capturar:
        calibrador.guiado = False
        calibrador.capturar(args.capturar)
        print(f"captura: {args.capturar}", flush=True)
        return 0

    calibrador.executar()
    print(f"mapa salvo em {args.saida} ({estado.total_marcado()}/{estado.total_possivel()})",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
