"""DUMP DO RIG INSTRUMENTADO — lê uma pose conhecida e imprime o estado em PT.

Aplica uma pose de produção (idle, wave, dance, sleep, drag, thrown e algumas
interações) a um ``Rig`` em repouso e imprime, em linguagem natural, para onde
cada parte do corpo está apontando segundo ``sejoga.rig_debug.estado_rig``:
mãos, cabeça, corpo, porta, braços/antebraços/ombros, pernas, pés e orientação
GLOBAL — com as flags discretas e os valores contínuos em graus.

Serve de "visualizador em código" do rig: em vez de abrir o executável com GPU,
lê-se aqui o que o rig realmente produz para cada gesto.

Uso (CLI)::

    python tools/dump_rig_estado.py --pose wave
    python tools/dump_rig_estado.py --pose idle --t 1.0

Fronteira: este script é de FERRAMENTA (tools/), mas o núcleo que ele consome
(``rig_debug``) é Python puro, sem engine. O carregamento da pose segue o padrão
de ``tools/verificar_gesto.py:_carregar_wave_producao`` (Rig com ``ALL_GROUPS``
em repouso, chama a pose, lê ``rig.pose()`` de volta).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_SRC = RAIZ / "src"

if str(_SRC) not in sys.path:
  sys.path.insert(0, str(_SRC))

from sejoga import rig as rig_mod
from sejoga import rig_debug as rd
from sejoga import spring_tuning  # noqa: E402
from sejoga.assets import resolve_model
from sejoga.body_motion import Spring  # noqa: E402
from sejoga.model import load_model


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


def _pose_drag(rig: rig_mod.Rig, t: float) -> None:
  rig_mod.pose_drag(rig, t, direction=1.0, drag_intensity=1.0)


def _pose_thrown(rig: rig_mod.Rig, t: float) -> None:
  rig_mod.pose_thrown(rig, t)


def _pose_sneeze(rig: rig_mod.Rig, t: float) -> None:
  rig_mod.pose_sneeze(rig, t)


#: Instante padrão (s) por pose — escolhido onde o gesto está "aberto"/legível.
_INSTANTE_PADRAO: dict[str, float] = {
  "idle": 1.0,
  "wave": 1.0,
  "stretch": 1.2,
  "peek": 2.5,
  "dance": 0.6,
  "sleep": 1.0,
  "drag": 0.0,
  "thrown": 0.4,
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
  "drag": _pose_drag,
  "thrown": _pose_thrown,
  "sneeze": _pose_sneeze,
}


def _carregar_pose(nome: str, t: float) -> dict[str, rig_mod.Rotation3]:
  """Instancia o Rig em repouso, aplica a pose e devolve o dict do renderer."""
  repouso = {g: rig_mod.Rotation3() for g in rig_mod.ALL_GROUPS}
  rig = rig_mod.Rig(rest=dict(repouso), current=dict(repouso))
  _POSES[nome](rig, t)

  return rig.pose()


def _formatar_dump(nome: str, t: float, estado: rd.EstadoRig) -> str:
  """Monta o texto legível do estado instrumentado."""
  linhas: list[str] = []
  linhas.append(f"═══ ESTADO DO RIG · pose '{nome}' em t={t:.2f}s ═══")

  linhas.append("")
  linhas.append("  ── ORIENTAÇÃO GLOBAL ──")
  g = estado.orientacao_global
  linhas.append(f"    geral: {g.flag} (desvio {g.desvio_graus:.1f}°)")

  linhas.append("")
  linhas.append("  ── CABEÇA ──")
  c = estado.cabeca
  linhas.append(f"    olhar: {c.olhar_flag} ({c.olhar_graus:.1f}°)")
  linhas.append(f"    topo:  {c.topo_flag} ({c.topo_graus:.1f}°)")
  linhas.append(
    f"    inclinação: {c.inclinacao_graus:.1f}°  tilt: {c.tilt_graus:.1f}°"
  )

  linhas.append("")
  linhas.append("  ── CORPO ──")
  b = estado.corpo
  linhas.append(f"    inclinação: {b.inclinacao_flag} ({b.inclinacao_graus:.1f}°)")
  linhas.append(f"    rolagem:    {b.rolagem_flag} ({b.rolagem_graus:.1f}°)")
  linhas.append(f"    torção:     {b.torcao_graus:.1f}°")
  linhas.append(f"    orientação: {b.orientacao_flag}")

  for rotulo, mao in (("MÃO DIREITA", estado.mao_direita),
                      ("MÃO ESQUERDA", estado.mao_esquerda)):
    linhas.append("")
    linhas.append(f"  ── {rotulo} ──")
    linhas.append(f"    palma: {mao.palma_flag} ({mao.palma_graus:.1f}°)")
    linhas.append(f"    dorso: {mao.dorso_flag} ({mao.dorso_graus:.1f}°)")
    linhas.append(f"    dedos: {mao.dedos_flag} ({mao.dedos_graus:.1f}°)")
    linhas.append(f"    punho: {mao.punho_flag} ({mao.punho_graus:.1f}°)")

  linhas.append("")
  linhas.append("  ── MEMBROS ──")

  for grupo, membro in estado.membros.items():
    linhas.append(
      f"    {grupo:<11} {membro.direcao_flag} "
      f"(eixo {membro.eixo_flag}, elevação {membro.elevacao_graus:.1f}°)"
    )

  linhas.append("")
  linhas.append("  ── ARTICULAÇÕES ──")

  for nome_art, art in estado.articulacoes.items():
    linhas.append(f"    {nome_art:<17} {art.flag} ({art.graus:.1f}°)")

  linhas.append("")
  linhas.append("  ── PORTA ──")
  p = estado.porta
  linhas.append(f"    {p.flag} ({p.graus:.1f}°)")

  return "\n".join(linhas)


def _assentamento_mola(grupo: str, frames: int) -> str:
  """Aplica um degrau de 1° à mola do grupo e imprime o assentamento por frame.

  Usa a tensão da junta de ``spring_tuning`` sobre a ``Spring`` analítica (puro
  Python, sem engine). Imprime, por frame a 60 Hz, o valor em graus e a
  velocidade em graus/s até assentar (ou até ``frames`` quadros).
  """
  tensao = spring_tuning.tensao_de(grupo)
  mola = Spring(tensao.frequencia, tensao.amortecimento)
  dt = 1 / 60
  alvo = 1.0

  linhas: list[str] = []
  linhas.append(
    f"═══ ASSENTAMENTO DA MOLA · grupo '{grupo}' "
    f"(freq {tensao.frequencia:.2f} Hz, amort {tensao.amortecimento:.2f}) ═══"
  )
  linhas.append(f"  degrau de alvo: {alvo:.1f}°  ·  passo: {dt * 1000:.1f} ms (60 Hz)")
  linhas.append("")
  linhas.append("  frame      tempo(s)     valor(°)   velocidade(°/s)")

  assentou_em: int | None = None

  for frame in range(1, frames + 1):
    mola.update(dt, alvo)
    linhas.append(
      f"  {frame:>5}   {frame * dt:>9.3f}   {mola.value:>9.4f}   {mola.velocity:>12.4f}"
    )

    if assentou_em is None and abs(mola.value - alvo) < 1e-3 and abs(mola.velocity) < 1e-3:
      assentou_em = frame
      break

  linhas.append("")

  if assentou_em is not None:
    linhas.append(
      f"  assentou no frame {assentou_em} (t={assentou_em * dt:.3f}s): "
      f"valor {mola.value:.4f}°, velocidade {mola.velocity:.4f}°/s."
    )
  else:
    linhas.append(
      f"  não assentou em {frames} frames: valor {mola.value:.4f}°, "
      f"velocidade {mola.velocity:.4f}°/s."
    )

  return "\n".join(linhas)


def _montar_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    description="Imprime o estado instrumentado do rig para uma pose conhecida.",
  )
  parser.add_argument(
    "--pose", choices=tuple(_POSES), default="wave",
    help="pose a aplicar (padrão: wave)",
  )
  parser.add_argument(
    "--t", type=float, default=None,
    help="instante (s) da pose; padrão depende da pose",
  )
  parser.add_argument(
    "--impulso", metavar="GRUPO", default=None,
    help="modo numérico: aplica um degrau à mola do grupo e imprime o "
         "assentamento por frame (ex.: --impulso hand)",
  )
  parser.add_argument(
    "--frames", type=int, default=240,
    help="máximo de frames do modo --impulso (padrão: 240)",
  )

  return parser


def main(argv: list[str] | None = None) -> int:
  # O dump usa Unicode (═ °). No Windows, stdout pode vir em cp1252 e quebrar ao
  # redirecionar/pipar; forçamos UTF-8 quando possível (como verificar_gesto).
  for fluxo in (sys.stdout, sys.stderr):
    reconfig = getattr(fluxo, "reconfigure", None)

    if callable(reconfig):
      reconfig(encoding="utf-8", errors="replace")

  args = _montar_parser().parse_args(argv)

  if args.impulso is not None:
    frames = max(1, args.frames)
    print(_assentamento_mola(args.impulso, frames))

    return 0

  t = args.t if args.t is not None else _INSTANTE_PADRAO[args.pose]

  model = load_model(resolve_model())
  pose = _carregar_pose(args.pose, t)
  estado = rd.estado_rig(pose, model)

  print(_formatar_dump(args.pose, t, estado))

  return 0


if __name__ == "__main__":
  raise SystemExit(main())
