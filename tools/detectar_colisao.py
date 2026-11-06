"""Varredura de INTERPENETRAÇÃO entre membros nas poses reais (sem engine aqui).

Aplica TODAS as poses de produção a um ``Rig`` em repouso, mede cada parte com
``sejoga.rig_medidas`` e roda ``sejoga.colisao_membros.detectar_colisoes`` em
vários instantes de cada pose. Agrega por par/pose a profundidade máxima, média
e o instante do pico, imprime um laudo em português e, com ``--md CAMINHO``,
grava o mesmo conteúdo em markdown (a EVIDÊNCIA que guia o FEAT-002).

Fronteira: script de FERRAMENTA (tools/), mas o núcleo consumido
(``rig_medidas``/``colisao_membros``) é Python puro, sem engine. O carregamento
de pose segue o padrão de ``tools/dump_rig_estado.py`` (Rig com ``ALL_GROUPS``
em repouso, aplica a pose, lê ``rig.pose()`` de volta).

Uso (CLI)::

    python tools/detectar_colisao.py
    python tools/detectar_colisao.py --md docs/RELATORIO_COLISAO_MEMBROS.md
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_SRC = RAIZ / "src"

if str(_SRC) not in sys.path:
  sys.path.insert(0, str(_SRC))

from sejoga import colisao_membros as col  # noqa: E402
from sejoga import rig as rig_mod  # noqa: E402
from sejoga import rig_medidas as med  # noqa: E402
from sejoga.assets import resolve_model  # noqa: E402
from sejoga.dance_motion import DanceMotion  # noqa: E402
from sejoga.model import Model, load_model  # noqa: E402
from sejoga.rig_mapa import Parte  # noqa: E402

#: Instantes (s) amostrados por pose — cobrem início, meio e abertura do gesto.
INSTANTES_PADRAO: tuple[float, ...] = (0.0, 0.3, 0.6, 1.0, 1.5, 2.0, 2.6)

#: Nomes amigáveis (PT) por par de partes, para o laudo.
NOMES_PARTE: dict[Parte, str] = {
  Parte.CORPO: "tronco",
  Parte.CABECA: "cabeça",
  Parte.PORTA: "portinha",
  Parte.BRACO_DIREITO: "braço dir.",
  Parte.BRACO_ESQUERDO: "braço esq.",
  Parte.ANTEBRACO_DIREITO: "antebraço dir.",
  Parte.ANTEBRACO_ESQUERDO: "antebraço esq.",
  Parte.MAO_DIREITA: "mão dir.",
  Parte.MAO_ESQUERDA: "mão esq.",
  Parte.PERNAS: "pernas",
  Parte.PE_ESQUERDO: "pé esq.",
  Parte.PE_DIREITO: "pé dir.",
}


def _nome_par(par: tuple[Parte, Parte]) -> str:
  a, b = par
  return f"{NOMES_PARTE.get(a, a.value)} vs {NOMES_PARTE.get(b, b.value)}"


# --------------------------------------------------------------------------- #
# Carga de pose (padrão de dump_rig_estado): Rig em repouso + pose aplicada.
# --------------------------------------------------------------------------- #
Aplicador = Callable[[rig_mod.Rig, float], None]


def _rig_repouso() -> rig_mod.Rig:
  repouso = {g: rig_mod.Rotation3() for g in rig_mod.ALL_GROUPS}
  return rig_mod.Rig(rest=dict(repouso), current=dict(repouso))


def _pose_de(aplicador: Aplicador, t: float) -> dict[str, rig_mod.Rotation3]:
  rig = _rig_repouso()
  aplicador(rig, t)
  return rig.pose()


def _aplicador_dance_style(estilo: str) -> Aplicador:
  """Aplicador que fixa um estilo de dança via ``DanceMotion`` com override.

  Pré-roda a mola/fraseado com energia e grave altos para o estilo engatar e
  então grava a pose suavizada no rig no instante pedido.
  """

  def aplicar(rig: rig_mod.Rig, t: float) -> None:
    motion = DanceMotion()
    motion.override = estilo
    # Alimenta o motor por alguns passos para assentar estilo e molas.
    passos = max(1, int((t + 1.0) / (1.0 / 60.0)))
    for _ in range(passos):
      motion.update(1.0 / 60.0, level=0.9, bass=0.6, bpm=120.0, beat=False)
    motion.apply(rig)

  return aplicar


def _aplicador_idle(personalidade: rig_mod.IdlePersonality) -> Aplicador:
  def aplicar(rig: rig_mod.Rig, t: float) -> None:
    rig_mod.pose_idle(rig, t, personalidade, respiracao=0.6)

  return aplicar


def _aplicador_flourish(kind: str) -> Aplicador:
  def aplicar(rig: rig_mod.Rig, t: float) -> None:
    rig_mod.pose_flourish(rig, kind, t)

  return aplicar


def _aplicador_interaction(kind: str) -> Aplicador:
  def aplicar(rig: rig_mod.Rig, t: float) -> None:
    rig_mod.pose_interaction(rig, kind, t, direction=0.5, vertical=0.3)

  return aplicar


def _construir_poses() -> dict[str, Aplicador]:
  """Mapa pose_nome -> aplicador cobrindo TODAS as poses existentes."""
  poses: dict[str, Aplicador] = {}

  # Idle das 9 personalidades.
  for personalidade in rig_mod.IdlePersonality:
    poses[f"idle:{personalidade.value}"] = _aplicador_idle(personalidade)

  # Locomoção.
  poses["walk"] = lambda rig, t: rig_mod.pose_walk(rig, t, run=False)
  poses["run"] = lambda rig, t: rig_mod.pose_walk(rig, t, run=True)

  # Arraste e queda.
  poses["drag"] = lambda rig, t: rig_mod.pose_drag(rig, t, direction=1.0, drag_intensity=1.0)
  poses["fall"] = lambda rig, t: rig_mod.pose_thrown(rig, t)

  # Dança: pose procedural genérica + os 4 estilos do DanceMotion.
  poses["dance"] = lambda rig, t: rig_mod.pose_dance(rig, t)
  for estilo in ("head_bob", "hip_hop", "rock", "breakdance"):
    poses[f"dance:{estilo}"] = _aplicador_dance_style(estilo)

  # Sono.
  poses["sleep"] = lambda rig, t: rig_mod.pose_sleep(rig, t)

  # Gestos (flourish) e reações (interaction).
  for kind in ("wave", "stretch", "peek"):
    poses[f"flourish:{kind}"] = _aplicador_flourish(kind)

  for kind in ("hover", "click", "double_click", "pet", "poke", "land", "wake"):
    poses[f"interaction:{kind}"] = _aplicador_interaction(kind)

  return poses


# --------------------------------------------------------------------------- #
# Agregação por par/pose.
# --------------------------------------------------------------------------- #
@dataclass
class Agregado:
  """Acúmulo de profundidade de um par numa pose ao longo dos instantes."""

  par: tuple[Parte, Parte]
  pose: str
  profundidade_max: float = 0.0
  soma: float = 0.0
  amostras_com_colisao: int = 0
  t_pico: float = 0.0

  def registrar(self, profundidade: float, t_s: float) -> None:
    self.soma += profundidade
    self.amostras_com_colisao += 1

    if profundidade > self.profundidade_max:
      self.profundidade_max = profundidade
      self.t_pico = t_s

  @property
  def profundidade_media(self) -> float:
    if self.amostras_com_colisao == 0:
      return 0.0
    return self.soma / self.amostras_com_colisao


def varrer(
  model: Model,
  poses: dict[str, Aplicador],
  instantes: tuple[float, ...],
) -> list[Agregado]:
  """Roda a detecção em cada pose/instante e agrega por par/pose."""
  agregados: dict[tuple[str, tuple[Parte, Parte]], Agregado] = {}

  for nome_pose, aplicador in poses.items():
    for t in instantes:
      pose = _pose_de(aplicador, t)
      partes = med.medir_todas_as_partes(pose, model)
      colisoes = col.detectar_colisoes(partes, nome_pose, t)

      for colisao in colisoes:
        chave = (nome_pose, colisao.par)
        agregado = agregados.get(chave)

        if agregado is None:
          agregado = Agregado(par=colisao.par, pose=nome_pose)
          agregados[chave] = agregado

        agregado.registrar(colisao.profundidade_u, t)

  ordenados = sorted(
    agregados.values(),
    key=lambda a: a.profundidade_max,
    reverse=True,
  )

  return ordenados


# --------------------------------------------------------------------------- #
# Laudo em texto e markdown.
# --------------------------------------------------------------------------- #
def _linhas_tabela(agregados: list[Agregado]) -> list[tuple[str, str, str, str, str]]:
  linhas: list[tuple[str, str, str, str, str]] = []

  for a in agregados:
    linhas.append((
      a.pose,
      _nome_par(a.par),
      f"{a.profundidade_max:.3f}",
      f"{a.profundidade_media:.3f}",
      f"{a.t_pico:.2f}",
    ))

  return linhas


def montar_laudo(agregados: list[Agregado], total_poses: int) -> str:
  """Laudo em texto priorizado (pior penetração primeiro)."""
  linhas: list[str] = []
  linhas.append(
    f"═══ LAUDO DE INTERPENETRAÇÃO · {total_poses} poses, "
    f"limiar {col.LIMIAR_PENETRACAO_U:.3f} u ═══"
  )
  linhas.append("")

  if not agregados:
    linhas.append("  Nenhuma interpenetração acima do limiar nas poses varridas.")
    return "\n".join(linhas)

  cab = f"  {'pose':<20} {'par':<28} {'máx(u)':>8} {'média(u)':>9} {'t_pico':>7}"
  linhas.append(cab)
  linhas.append("  " + "-" * (len(cab) - 2))

  for pose, par, pmax, pmedia, tpico in _linhas_tabela(agregados):
    linhas.append(f"  {pose:<20} {par:<28} {pmax:>8} {pmedia:>9} {tpico:>7}")

  linhas.append("")
  pior = agregados[0]
  linhas.append(
    f"  Pior caso: {_nome_par(pior.par)} na pose '{pior.pose}' "
    f"({pior.profundidade_max:.3f} u em t={pior.t_pico:.2f}s)."
  )

  return "\n".join(linhas)


def montar_markdown(agregados: list[Agregado], total_poses: int) -> str:
  """Relatório markdown com tabela real + seções de parâmetros e decisão."""
  linhas: list[str] = []
  linhas.append("# Relatório de interpenetração de membros (FEAT-001)")
  linhas.append("")
  linhas.append(
    "Evidência numérica gerada por `tools/detectar_colisao.py` sobre as poses "
    "reais do companion. Profundidades em unidades do modelo (`u`), a mesma "
    "escala de `comprimento_u` em `rig_medidas`."
  )
  linhas.append("")
  linhas.append(
    f"- Poses varridas: **{total_poses}** "
    f"(instantes por pose: {', '.join(f'{t:.2f}s' for t in INSTANTES_PADRAO)})."
  )
  linhas.append(f"- Limiar de colisão: **{col.LIMIAR_PENETRACAO_U:.3f} u**.")
  linhas.append(f"- Pares verificados: **{len(col.PARES_A_CHECAR)}** (lista curada, não todos-contra-todos).")
  linhas.append("")

  linhas.append("## Interpenetração por par/pose")
  linhas.append("")

  if not agregados:
    linhas.append(
      "Nenhuma interpenetração acima do limiar foi encontrada nas poses "
      "varridas. Os volumes de partida (raios/meias-dimensões) não acusam "
      "atravessamento; ajustar os parâmetros abaixo para calibrar a sensibilidade."
    )
  else:
    linhas.append("| Pose | Par | Prof. máx (u) | Prof. média (u) | t do pico (s) |")
    linhas.append("| --- | --- | ---: | ---: | ---: |")

    for pose, par, pmax, pmedia, tpico in _linhas_tabela(agregados):
      linhas.append(f"| {pose} | {par} | {pmax} | {pmedia} | {tpico} |")

    linhas.append("")
    pior = agregados[0]
    linhas.append(
      f"**Pior caso:** {_nome_par(pior.par)} na pose `{pior.pose}` — "
      f"{pior.profundidade_max:.3f} u de penetração em t={pior.t_pico:.2f}s."
    )

    linhas.append("")
    linhas.append("### Como ler os números (overlap estrutural vs pose)")
    linhas.append("")
    linhas.append(
      "Dois sinais convivem na tabela e o FEAT-002 precisa separá-los:"
    )
    linhas.append("")
    linhas.append(
      "- **Overlap ESTRUTURAL (constante em todas as poses):** `braço vs tronco` "
      "fica em ~0,45 u e `pernas vs pé` em exatamente 0,195 u em TODA pose, "
      "inclusive no repouso. Isso não é a pose atravessando o corpo: é a RAIZ do "
      "membro nascendo dentro do volume-bloco (o ombro/braço começa dentro da "
      "caixa do tronco; as pernas encostam nas caixas dos pés). É contato "
      "esperado pela montagem dos volumes, não defeito de animação."
    )
    linhas.append(
      "- **Penetração dirigida pela POSE (varia com pose/instante):** os pares "
      "que mudam de profundidade conforme o gesto — `antebraço vs tronco` "
      "(até ~0,41 u no `wake`/`wave`), `antebraço vs cabeça` (até ~0,28 u), "
      "`mão vs tronco`, `braço dir. vs braço esq.` (0,07 u em repouso subindo a "
      "0,32 u no `wake`) e `antebraço/mão vs portinha` — são os que realmente "
      "revelam o braço cruzando o corpo/cabeça. São esses que a correção deve mirar."
    )
    linhas.append("")
    linhas.append(
      "Recomendação de calibração para o FEAT-002: descontar o piso estrutural "
      "por par (subtrair a profundidade medida no repouso) OU encolher a cápsula "
      "do membro perto da raiz / afundar menos a origem na caixa, de modo que só "
      "o excedente dirigido pela pose conte como colisão a corrigir."
    )

  linhas.append("")
  linhas.append("## Parâmetros calibráveis")
  linhas.append("")
  linhas.append(
    "Todos em `src/sejoga/colisao_membros.py`, no bloco `PARÂMETROS` do topo:"
  )
  linhas.append("")
  linhas.append("- `RAIOS_MEMBRO` e `RAIO_MEMBRO_PADRAO`: raio da cápsula por membro.")
  linhas.append("- `MEIA_DIM_TRONCO`, `MEIA_DIM_CABECA`, `MEIA_DIM_PORTA`: meias-dimensões das caixas orientadas.")
  linhas.append("- `AMOSTRAS_CAPSULA_CAIXA`: densidade da amostragem cápsula-vs-caixa.")
  linhas.append("- `LIMIAR_PENETRACAO_U`: profundidade mínima para contar como colisão.")
  linhas.append("- `PARES_A_CHECAR`: pares plausíveis varridos.")
  linhas.append("")
  linhas.append("Valores atuais:")
  linhas.append("")
  for parte, raio in col.RAIOS_MEMBRO.items():
    linhas.append(f"- raio `{parte.value}` = {raio:.3f} u")
  linhas.append(f"- `MEIA_DIM_TRONCO` = {col.MEIA_DIM_TRONCO}")
  linhas.append(f"- `MEIA_DIM_CABECA` = {col.MEIA_DIM_CABECA}")
  linhas.append(f"- `MEIA_DIM_PORTA` = {col.MEIA_DIM_PORTA}")
  linhas.append(f"- `LIMIAR_PENETRACAO_U` = {col.LIMIAR_PENETRACAO_U:.3f} u")
  linhas.append("")

  linhas.append("## Decisão para a correção (FEAT-002)")
  linhas.append("")
  linhas.append(
    "_Em aberto — a ser preenchido pelo FEAT-002 com a estratégia de correção "
    "(mover o alvo da pose sem saltar o ângulo, à moda de `tentacle_constraints`), "
    "escolhendo quais pares corrigir primeiro a partir dos piores casos acima e "
    "provando ausência de tranco com `tools/analisar_anim.py`._"
  )
  linhas.append("")

  return "\n".join(linhas)


# --------------------------------------------------------------------------- #
# CLI.
# --------------------------------------------------------------------------- #
def _montar_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    description="Varre as poses e relata a interpenetração entre membros.",
  )
  parser.add_argument(
    "--md", metavar="CAMINHO", default=None,
    help="grava o relatório em markdown no caminho dado",
  )

  return parser


def main(argv: list[str] | None = None) -> int:
  # O laudo usa Unicode (barras ═). No Windows stdout pode vir cp1252 e quebrar ao
  # redirecionar; força UTF-8 quando possível (como dump_rig_estado.main).
  for fluxo in (sys.stdout, sys.stderr):
    reconfig = getattr(fluxo, "reconfigure", None)

    if callable(reconfig):
      reconfig(encoding="utf-8", errors="replace")

  args = _montar_parser().parse_args(argv)

  model = load_model(resolve_model())
  poses = _construir_poses()
  agregados = varrer(model, poses, INSTANTES_PADRAO)

  print(montar_laudo(agregados, len(poses)))

  if args.md is not None:
    destino = Path(args.md)

    if not destino.is_absolute():
      destino = RAIZ / destino

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(montar_markdown(agregados, len(poses)), encoding="utf-8")
    print(f"\nRelatório markdown gravado em: {destino}")

  return 0


if __name__ == "__main__":
  raise SystemExit(main())
