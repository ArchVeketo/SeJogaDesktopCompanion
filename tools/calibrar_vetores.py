"""CALIBRAÇÃO VISUAL dos vetores de referência do rig instrumentado.

Problema que resolve
--------------------
``sejoga.rig_debug`` classifica flags como "palma PARA_CIMA" girando VETORES DE
REFERÊNCIA (normal da palma, dorso, direção dos dedos, olhar/topo da cabeça,
normal da porta, eixo longo dos pés...). Vários desses vetores estão marcados
com ``# A VALIDAR`` em ``VETORES_REFERENCIA`` porque foram deduzidos sem
confirmação visual. Se um vetor de partida estiver invertido, a flag sai errada
(o aceno 'wave', por exemplo, reportou palma PARA_CIMA, provavelmente por um
eixo torto).

Esta ferramenta RENDERIZA o modelo numa pose escolhida e desenha, sobre cada
parte, o(s) vetor(es) de referência daquela parte como SETA(S) 3D ancorada(s) na
junta correspondente — gerando UMA imagem PNG por parte. O usuário olha as
figuras numa máquina com GPU e aponta quais setas estão invertidas; a correção
(inverter/ajustar o vetor em ``VETORES_REFERENCIA``) fica para uma tarefa futura.

Fronteira
---------
Este arquivo é FERRAMENTA (``tools/``): pode importar o engine (Panda3D) porque
é código de render offscreen. Ele NÃO altera módulos de produção — apenas LÊ
``sejoga.rig_debug.VETORES_REFERENCIA`` / ``estado_rig`` e ``sejoga.rig``.

Convenção de rotação (idêntica a ``renderer.apply_rig_pose`` e ``rig_debug``):
de ``Rotation3(x, y, z)`` em radianos derivamos ``H = y`` (heading), ``P = x``
(pitch), ``R = z`` (roll), SOMADO ao HPR de repouso do nó e acumulado pela
hierarquia pai->filho do Panda3D. Como a seta é ancorada COMO FILHA do nó do
rig e desenhada ao longo do vetor de referência em espaço LOCAL do nó, ela herda
exatamente essa mesma transformação acumulada — a direção mostrada bate com a
que ``rig_debug`` usa para classificar a flag.

Uso (rodar com cwd DENTRO do worktree)::

    python tools/calibrar_vetores.py                       # idle, todas as partes
    python tools/calibrar_vetores.py --pose wave           # pose 'wave'
    python tools/calibrar_vetores.py --parte hand          # só as mãos
    python tools/calibrar_vetores.py --pose wave --parte hand

As imagens saem em
``.agents/tasks/calibracao-vetores/imagens/`` (uma por parte/vetor), mais uma
folha-contato ``_folha_contato.png`` quando mais de uma imagem é gerada.

AMBIENTE: se o Panda3D não conseguir renderizar offscreen (máquina sem GPU que
cai para ``p3tinydisplay``), a ferramenta monta a cena e as setas até onde o
ambiente permitir e reporta honestamente que não gerou as imagens; nesse caso o
usuário roda o MESMO comando numa máquina com GPU.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from math import degrees
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_SRC = RAIZ / "src"

if str(_SRC) not in sys.path:
  sys.path.insert(0, str(_SRC))

from sejoga import rig as rig_mod  # noqa: E402
from sejoga import rig_debug as rd  # noqa: E402

#: Pasta de saída das imagens (sempre dentro do worktree atual).
DIR_SAIDA = RAIZ / ".agents" / "tasks" / "calibracao-vetores" / "imagens"

#: Tamanho (px) de cada figura quadrada.
LADO_IMAGEM = 900


# --------------------------------------------------------------------------- #
# Poses conhecidas (mesmo padrão de tools/dump_rig_estado.py)
# --------------------------------------------------------------------------- #
def _pose_idle(rig: rig_mod.Rig, t: float) -> None:
  rig_mod.pose_idle(rig, t)


def _pose_wave(rig: rig_mod.Rig, t: float) -> None:
  rig_mod.pose_flourish(rig, "wave", t)


def _pose_stretch(rig: rig_mod.Rig, t: float) -> None:
  rig_mod.pose_flourish(rig, "stretch", t)


def _pose_peek(rig: rig_mod.Rig, t: float) -> None:
  rig_mod.pose_flourish(rig, "peek", t)


def _pose_dance(rig: rig_mod.Rig, t: float) -> None:
  rig_mod.pose_dance(rig, t)


def _pose_sleep(rig: rig_mod.Rig, t: float) -> None:
  rig_mod.pose_sleep(rig, t)


def _pose_sneeze(rig: rig_mod.Rig, t: float) -> None:
  rig_mod.pose_sneeze(rig, t)


#: Instante padrão (s) por pose — onde o gesto está "aberto"/legível.
_INSTANTE_PADRAO: dict[str, float] = {
  "idle": 1.0,
  "wave": 1.0,
  "stretch": 1.2,
  "peek": 2.5,
  "dance": 0.6,
  "sleep": 1.0,
  "sneeze": 3.68,
}

#: Mapa de nome de pose -> função que a aplica ao rig.
_POSES = {
  "idle": _pose_idle,
  "wave": _pose_wave,
  "stretch": _pose_stretch,
  "peek": _pose_peek,
  "dance": _pose_dance,
  "sleep": _pose_sleep,
  "sneeze": _pose_sneeze,
}


def _carregar_pose(nome: str, t: float) -> dict[str, rig_mod.Rotation3]:
  """Instancia o Rig em repouso, aplica a pose e devolve o dict do renderer."""
  repouso = {g: rig_mod.Rotation3() for g in rig_mod.ALL_GROUPS}
  rig = rig_mod.Rig(rest=dict(repouso), current=dict(repouso))
  _POSES[nome](rig, t)

  return rig.pose()


# --------------------------------------------------------------------------- #
# Catálogo de setas por parte
# --------------------------------------------------------------------------- #
#: Cor RGBA por TIPO de vetor (distinta para leitura rápida na figura).
CORES_VETOR: dict[str, tuple[float, float, float, float]] = {
  "normal_palma": (1.0, 0.25, 0.25, 1.0),   # vermelho
  "dorso": (0.25, 0.55, 1.0, 1.0),          # azul
  "direcao_dedos": (0.25, 1.0, 0.35, 1.0),  # verde
  "olhar": (1.0, 0.25, 0.25, 1.0),          # vermelho
  "topo": (0.25, 0.55, 1.0, 1.0),           # azul
  "normal": (1.0, 0.25, 0.25, 1.0),         # vermelho (porta)
  "eixo_giro": (0.9, 0.9, 0.25, 1.0),       # amarelo
  "longo": (1.0, 0.55, 0.1, 1.0),           # laranja (eixo longo de membro)
}


@dataclass(frozen=True)
class Seta:
  """Uma seta a desenhar: âncora num nó do rig, ao longo de um vetor local."""

  grupo: str                 # nó do rig onde a seta é ancorada (ex.: 'hand')
  nome_vetor: str            # chave em VETORES_REFERENCIA[chave_ref]
  chave_ref: str             # entrada de VETORES_REFERENCIA (ex.: 'hand')
  rotulo: str                # texto desenhado (nome do vetor -> FLAG)


def _flag_mao(estado: rd.EstadoRig, grupo: str, nome_vetor: str) -> str:
  """Flag que o rig_debug produz para um vetor de mão na pose atual."""
  mao = estado.mao_direita if grupo == "hand" else estado.mao_esquerda

  if nome_vetor == "normal_palma":
    return mao.palma_flag
  if nome_vetor == "dorso":
    return mao.dorso_flag

  return mao.dedos_flag


def _flag_cabeca(estado: rd.EstadoRig, nome_vetor: str) -> str:
  """Flag que o rig_debug produz para olhar/topo da cabeça."""
  if nome_vetor == "olhar":
    return estado.cabeca.olhar_flag

  return estado.cabeca.topo_flag


def _flag_porta(estado: rd.EstadoRig, nome_vetor: str) -> str:
  """Flag/anotação para os vetores da porta."""
  if nome_vetor == "eixo_giro":
    return "EIXO_DE_GIRO (Y)"

  return estado.porta.flag


def _flag_membro(estado: rd.EstadoRig, grupo: str) -> str:
  """Flag de direção do eixo longo de um membro (ex.: pé)."""
  membro = estado.membros.get(grupo)

  if membro is None:
    return "SEM_LEITURA"

  return membro.direcao_flag


def montar_setas(parte: str, estado: rd.EstadoRig) -> list[Seta]:
  """Lista as setas a desenhar para a ``parte`` pedida, com rótulo + flag.

  ``parte`` ∈ {hand, head, door, feet, all}. Cada seta sabe em qual nó ancora,
  qual vetor de referência desenha e o texto (``nome -> FLAG``) a estampar.
  """
  setas: list[Seta] = []

  def _rotulo(nome: str, flag: str, grupo: str) -> str:
    sufixo = "_direita" if grupo in ("hand", "right-feet") else (
      "_esquerda" if grupo in ("hand2", "left-feet") else ""
    )

    return f"{nome}{sufixo} -> {flag}"

  if parte in ("hand", "all"):
    for grupo in ("hand", "hand2"):
      for nome in ("normal_palma", "dorso", "direcao_dedos"):
        flag = _flag_mao(estado, grupo, nome)
        setas.append(Seta(grupo, nome, grupo, _rotulo(nome, flag, grupo)))

  if parte in ("head", "all"):
    for nome in ("olhar", "topo"):
      flag = _flag_cabeca(estado, nome)
      setas.append(Seta("head", nome, "head", _rotulo(nome, flag, "head")))

  if parte in ("door", "all"):
    for nome in ("normal", "eixo_giro"):
      flag = _flag_porta(estado, nome)
      setas.append(Seta("door", nome, "door", _rotulo(nome, flag, "door")))

  if parte in ("feet", "all"):
    for grupo in ("right-feet", "left-feet"):
      flag = _flag_membro(estado, grupo)
      setas.append(
        Seta(grupo, "longo", "eixo_longo_membro", _rotulo("eixo_longo", flag, grupo))
      )

  return setas


# --------------------------------------------------------------------------- #
# Render offscreen (engine)
# --------------------------------------------------------------------------- #
def _nome_arquivo(seta: Seta) -> str:
  """Nome de PNG estável e único por (grupo, vetor)."""
  return f"{seta.grupo}__{seta.nome_vetor}.png"


class RenderizadorCalibracao:
  """ShowBase offscreen enxuto: modelo + rig posado + setas, screenshot por parte.

  Evita de propósito o caminho ``OverlayApp`` (Qt/Win32/chroma/tentáculos), que
  pode quebrar fora da janela real. Monta só o necessário para ver as setas.
  """

  COR_FUNDO = (0.11, 0.12, 0.15, 1.0)
  #: Comprimento da seta em unidades de MUNDO (após escala de ajuste). As setas
  #: ficam fora da hierarquia do modelo (presas a nós-espelho em ``render``),
  #: então independem da escala nativa minúscula do glTF.
  COMPRIMENTO_SETA = 3.2
  ESPESSURA_SETA = 6.0
  #: Fração da janela que o modelo deve ocupar ao ser enquadrado.
  PREENCHIMENTO = 0.6

  def __init__(self) -> None:
    from panda3d.core import loadPrcFileData

    loadPrcFileData("", "window-type offscreen")
    loadPrcFileData("", f"win-size {LADO_IMAGEM} {LADO_IMAGEM}")
    loadPrcFileData("", "audio-library-name null")
    loadPrcFileData("", "notify-level-display error")

    from direct.showbase.ShowBase import ShowBase

    self.base = ShowBase(windowType="offscreen")
    self._montar_cena()

  # -- cena ----------------------------------------------------------------- #
  def _montar_cena(self) -> None:
    import gltf
    from panda3d.core import (
      AmbientLight,
      AntialiasAttrib,
      DirectionalLight,
      NodePath,
      OrthographicLens,
    )

    from sejoga.assets import resolve_model

    render = self.base.render
    render.setShaderAuto()
    render.setAntialias(AntialiasAttrib.MMultisample)

    self.base.setBackgroundColor(*self.COR_FUNDO)

    ambient = AmbientLight("ambient")
    ambient.setColor((0.55, 0.55, 0.55, 1))
    render.setLight(render.attachNewNode(ambient))

    dirlight = DirectionalLight("dirlight")
    dirlight.setColor((0.85, 0.85, 0.85, 1))
    dir_np = render.attachNewNode(dirlight)
    dir_np.setHpr(-45, -45, 0)
    render.setLight(dir_np)

    # Modelo: mesma orientação de frente do renderer (rosto para a câmera).
    # Centramos na origem e aplicamos escala de ajuste para preencher o quadro.
    self.model_np = NodePath(gltf.load_model(str(resolve_model())))
    self.model_np.reparentTo(render)
    self.model_np.setH(180)

    limites = self.model_np.getTightBounds()

    if limites is None:
      raise ValueError("não foi possível calcular os limites do modelo")

    minimo, maximo = limites
    dimensoes = maximo - minimo
    maior = max(dimensoes.x, dimensoes.y, dimensoes.z) or 1.0
    # Alvo: altura visível de 14 unidades no lens; ocupa PREENCHIMENTO dela.
    self._escala_ajuste = (14.0 * self.PREENCHIMENTO) / maior
    self.model_np.setScale(self._escala_ajuste)
    centro = (minimo + maximo) * 0.5
    self.model_np.setPos(-centro.x * self._escala_ajuste,
                         -centro.y * self._escala_ajuste,
                         -centro.z * self._escala_ajuste + 1.0)

    # Mapa de nós do rig e HPR de repouso (base para somar o HPR animado).
    self._rig_nodes: dict[str, NodePath] = {}
    self._base_hpr: dict[str, tuple[float, float, float]] = {}

    for grupo in rig_mod.ALL_GROUPS:
      node = self.model_np.find(f"**/{grupo}")

      if node.isEmpty():
        continue

      self._rig_nodes[grupo] = node
      hpr = node.getHpr()
      self._base_hpr[grupo] = (float(hpr.x), float(hpr.y), float(hpr.z))

    # Câmera ortográfica frontal (como o renderer).
    lens = OrthographicLens()
    lens.setFilmSize(14.0, 14.0)
    lens.setNear(0.1)
    lens.setFar(100.0)
    self.base.cam.node().setLens(lens)
    self.base.cam.setPos(0, -15, 1)
    self.base.cam.lookAt(0, 0, 1)

    self._setas_np: list[NodePath] = []
    self._rotulos_np: list[NodePath] = []

  # -- pose ----------------------------------------------------------------- #
  def aplicar_pose(self, pose: dict[str, rig_mod.Rotation3]) -> None:
    """Aplica a pose aos nós com a MESMA convenção de ``apply_rig_pose``."""
    for grupo, rot in pose.items():
      node = self._rig_nodes.get(grupo)

      if node is None:
        continue

      base_h, base_p, base_r = self._base_hpr.get(grupo, (0.0, 0.0, 0.0))
      node.setHpr(
        base_h + degrees(rot.y),
        base_p + degrees(rot.x),
        base_r + degrees(rot.z),
      )

  # -- setas ---------------------------------------------------------------- #
  def _limpar_setas(self) -> None:
    for np_ in self._setas_np:
      np_.removeNode()

    for np_ in self._rotulos_np:
      np_.removeNode()

    self._setas_np = []
    self._rotulos_np = []

  def _criar_geom_seta(
    self, direcao: tuple[float, float, float], cor: tuple[float, float, float, float]
  ):
    """Cria o geom da seta (haste + duas farpas) ao longo de ``direcao`` local."""
    from panda3d.core import LineSegs, Vec3

    base = Vec3(*direcao)

    if base.length() == 0.0:
      base = Vec3(0, 0, 1)

    base.normalize()
    ponta = base * self.COMPRIMENTO_SETA

    # Dois vetores perpendiculares para as farpas da ponta.
    perp = base.cross(Vec3(0, 1, 0))

    if perp.length() < 1e-4:
      perp = base.cross(Vec3(1, 0, 0))

    perp.normalize()
    perp2 = base.cross(perp)
    perp2.normalize()

    farpa = self.COMPRIMENTO_SETA * 0.18
    recuo = ponta - base * (self.COMPRIMENTO_SETA * 0.22)

    segs = LineSegs()
    segs.setThickness(self.ESPESSURA_SETA)
    segs.setColor(*cor)
    segs.moveTo(0, 0, 0)
    segs.drawTo(ponta)

    for lado in (perp, -perp, perp2, -perp2):
      segs.moveTo(ponta)
      segs.drawTo(recuo + lado * farpa)

    return segs.create()

  def desenhar_setas(self, setas: list[Seta]) -> None:
    """Desenha cada seta em espaço de MUNDO, na junta, com tamanho fixo.

    A seta NÃO é filha do nó do rig (herdaria a escala minúscula do glTF). Em
    vez disso: pegamos a posição de mundo da junta e a DIREÇÃO DE MUNDO do vetor
    de referência (``render.getRelativeVector(node, ref)``) — que carrega a
    mesma rotação acumulada que ``rig_debug`` usa — e desenhamos a seta presa a
    ``render`` com comprimento fixo. Direção fiel à flag, tamanho legível.
    """
    from panda3d.core import TextNode, Vec3

    self._limpar_setas()
    render = self.base.render
    topo_y = 0.9

    for indice, seta in enumerate(setas):
      node = self._rig_nodes.get(seta.grupo)

      if node is None:
        continue

      ref = rd.VETORES_REFERENCIA[seta.chave_ref][seta.nome_vetor]
      cor = CORES_VETOR.get(seta.nome_vetor, (1.0, 1.0, 1.0, 1.0))

      # Âncora no CENTRO geométrico do nó (sobre a malha visível), não no pivô
      # da junta — que no rig fica junto ao tronco e confunde a leitura. A
      # DIREÇÃO continua vindo da rotação acumulada do nó (fiel à flag).
      limites = node.getTightBounds(render)

      if limites is not None:
        baixo, alto = limites
        ancora = (baixo + alto) * 0.5
      else:
        ancora = node.getPos(render)

      direcao = render.getRelativeVector(node, Vec3(*ref))

      geom = self._criar_geom_seta((direcao.x, direcao.y, direcao.z), cor)
      seta_np = render.attachNewNode(geom)
      seta_np.setPos(ancora)
      seta_np.setLightOff()
      seta_np.setDepthTest(False)
      seta_np.setDepthWrite(False)
      seta_np.setBin("fixed", 50)
      self._setas_np.append(seta_np)

      txt = TextNode(f"rotulo-{indice}")
      txt.setText(seta.rotulo)
      txt.setTextColor(*cor)
      txt.setAlign(TextNode.ALeft)
      rot_np = self.base.aspect2d.attachNewNode(txt)
      rot_np.setScale(0.045)
      rot_np.setPos(-0.95, 0, topo_y - indice * 0.075)
      self._rotulos_np.append(rot_np)

  # -- captura -------------------------------------------------------------- #
  def capturar(self, destino: Path) -> bool:
    """Renderiza alguns frames e grava o screenshot; devolve se saiu arquivo."""
    from panda3d.core import Filename

    destino.parent.mkdir(parents=True, exist_ok=True)

    for _ in range(3):
      self.base.graphicsEngine.renderFrame()

    ok = self.base.win.getScreenshot().write(
      Filename.fromOsSpecific(str(destino))
    )

    return bool(ok) and destino.exists()

  def fechar(self) -> None:
    import contextlib

    with contextlib.suppress(Exception):
      self.base.destroy()


# --------------------------------------------------------------------------- #
# Folha-contato
# --------------------------------------------------------------------------- #
def _folha_contato(imagens: list[Path], destino: Path) -> Path | None:
  """Monta uma grade com todas as imagens lado a lado (PIL)."""
  if len(imagens) < 2:
    return None

  from PIL import Image

  quadros = [Image.open(c).convert("RGB") for c in imagens]
  colunas = 3 if len(quadros) >= 3 else len(quadros)
  linhas = (len(quadros) + colunas - 1) // colunas
  larg = quadros[0].width
  alt = quadros[0].height
  folha = Image.new("RGB", (larg * colunas, alt * linhas), (20, 20, 24))

  for indice, quadro in enumerate(quadros):
    col = indice % colunas
    lin = indice // colunas
    folha.paste(quadro, (col * larg, lin * alt))

  folha.save(destino)

  return destino


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _montar_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    description=(
      "Renderiza o modelo com os vetores de referência do rig_debug como setas "
      "3D, uma imagem por parte, para calibração visual."
    ),
  )
  parser.add_argument(
    "--pose", choices=tuple(_POSES), default="idle",
    help="pose a aplicar (padrão: idle)",
  )
  parser.add_argument(
    "--parte", choices=("hand", "head", "door", "feet", "all"), default="all",
    help="parte a calibrar (padrão: all)",
  )
  parser.add_argument(
    "--t", type=float, default=None,
    help="instante (s) da pose; padrão depende da pose",
  )

  return parser


def _forcar_utf8() -> None:
  """stdout/stderr em UTF-8 (Windows pode vir em cp1252 ao redirecionar)."""
  for fluxo in (sys.stdout, sys.stderr):
    reconfig = getattr(fluxo, "reconfigure", None)

    if callable(reconfig):
      reconfig(encoding="utf-8", errors="replace")


def _agrupar_por_arquivo(setas: list[Seta]) -> dict[str, list[Seta]]:
  """Agrupa setas por imagem de saída (uma imagem por grupo do rig).

  Mãos e cabeça reúnem seus 2-3 vetores numa única figura por grupo; porta e
  pés idem. Assim o usuário vê, por figura, todos os vetores daquela junta.
  """
  por_arquivo: dict[str, list[Seta]] = {}

  for seta in setas:
    chave = f"{seta.grupo}.png"
    por_arquivo.setdefault(chave, []).append(seta)

  return por_arquivo


def main(argv: list[str] | None = None) -> int:
  _forcar_utf8()
  args = _montar_parser().parse_args(argv)
  t = args.t if args.t is not None else _INSTANTE_PADRAO[args.pose]

  from sejoga.assets import resolve_model
  from sejoga.model import load_model

  model = load_model(resolve_model())
  pose = _carregar_pose(args.pose, t)
  estado = rd.estado_rig(pose, model)
  setas = montar_setas(args.parte, estado)

  if not setas:
    print(f"nenhuma seta para a parte {args.parte!r}", flush=True)

    return 1

  por_arquivo = _agrupar_por_arquivo(setas)

  print(
    f"Calibração · pose '{args.pose}' (t={t:.2f}s) · parte '{args.parte}' · "
    f"{len(por_arquivo)} figura(s), {len(setas)} seta(s)",
    flush=True,
  )

  # Monta a cena. Se o engine não renderizar offscreen aqui, reporta e sai.
  try:
    renderizador = RenderizadorCalibracao()
  except Exception as erro:  # pragma: no cover - depende do ambiente/GPU
    print(
      "NÃO foi possível iniciar o render offscreen neste ambiente "
      f"({type(erro).__name__}: {erro}).",
      flush=True,
    )
    print(
      "Rode o MESMO comando numa máquina com GPU; as imagens sairão em "
      f"{DIR_SAIDA}",
      flush=True,
    )

    return 2

  renderizador.aplicar_pose(pose)
  gerados: list[Path] = []

  try:
    for arquivo, setas_do_arquivo in por_arquivo.items():
      renderizador.desenhar_setas(setas_do_arquivo)
      destino = DIR_SAIDA / arquivo

      if renderizador.capturar(destino):
        gerados.append(destino)
        rotulos = ", ".join(s.rotulo for s in setas_do_arquivo)
        print(f"  gerado: {destino}", flush=True)
        print(f"          {rotulos}", flush=True)
      else:
        print(f"  FALHOU ao gravar: {destino}", flush=True)
  finally:
    renderizador.fechar()

  if not gerados:
    print(
      "Cena montada, mas nenhuma imagem foi gravada (provável ausência de GPU "
      "offscreen). Rode numa máquina com GPU.",
      flush=True,
    )

    return 2

  folha = _folha_contato(gerados, DIR_SAIDA / "_folha_contato.png")

  if folha is not None:
    print(f"  folha-contato: {folha}", flush=True)

  print(f"\n{len(gerados)} imagem(ns) em {DIR_SAIDA}", flush=True)

  return 0


if __name__ == "__main__":
  raise SystemExit(main())
