"""Estado puro do modo CONFIRMAR do calibrador (sem Panda3D, Qt ou Win32).

O mapa de eixos agora sai do grafo de cena (``tools/gerar_oraculo_cena.py``); o usuário
não precisa mais marcar 96 combinações. No modo confirmar a ferramenta mostra
cada pose real do app, faz UMA pergunta curta e o usuário responde com uma
tecla: correto, errado ou pular. As respostas vão para
``confirmacao-parte3.json`` e dizem exatamente o que ainda está errado na GPU.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

VERSAO_ARQUIVO = 1


class Resposta(StrEnum):
    CORRETO = "correto"
    ERRADO = "errado"
    PULADO = "pulado"


@dataclass(frozen=True, slots=True)
class PoseDeConfirmacao:
    """Uma pose do app a confirmar: estado/gesto que a ferramenta dispara."""

    nome: str
    #: Estado/gesto aceito por ``tools/calibrar_interativo._pilotar``/``interact``.
    estado: str
    #: Item do recalibracao-gpu.md que a resposta decide (C1..C6).
    item: str
    pergunta: str


#: Ordem fixa das poses. As perguntas são curtas e respondíveis de relance.
POSES: tuple[PoseDeConfirmacao, ...] = (
    PoseDeConfirmacao("repouso", "idle", "C1/C6",
                      "Braços para fora do corpo, mãos visíveis e nada enfiado no tronco/short?"),
    PoseDeConfirmacao("repouso_lado", "idle", "C2",
                      "(tecla v: lado) O cotovelo dobra para a FRENTE, nunca para trás?"),
    PoseDeConfirmacao("aceno", "wave", "C1/C3",
                      "Só o braço direito acena, a mão sobe por fora da cabeça?"),
    PoseDeConfirmacao("alongamento", "stretch", "C1/C2",
                      "Os braços sobem em sequência sem atravessar a cabeça?"),
    PoseDeConfirmacao("cutucar", "poke", "C1",
                      "A mão direita vai para a FRENTE do corpo (em direção à câmera)?"),
    PoseDeConfirmacao("clique", "click", "C5a",
                      "Ao clicar, o tronco cede para a FRENTE?"),
    PoseDeConfirmacao("danca", "hip_hop", "C3/C4",
                      "Os braços se revezam sem atravessar o tronco nem um ao outro?"),
    PoseDeConfirmacao("danca_cruzada", "head_bob", "C4",
                      "Braços cruzados ficam À FRENTE do tronco, sem atravessá-lo?"),
    PoseDeConfirmacao("sono", "sleep", "C3",
                      "Os dois braços estão espelhados (simétricos)?"),
    PoseDeConfirmacao("arraste", "drag", "C5b",
                      "Arrastando, o corpo pende para o lado coerente com o puxão?"),
    PoseDeConfirmacao("queda", "fall", "C4",
                      "Na queda, braços abertos sem atravessar a cabeça ou o tronco?"),
)


class ConfirmacaoPoses:
    """Navegação e respostas do modo confirmar."""

    def __init__(self, poses: tuple[PoseDeConfirmacao, ...] = POSES) -> None:
        if not poses:
            raise ValueError("lista de poses vazia")

        self._poses = poses
        self._indice = 0
        self._respostas: dict[str, Resposta] = {}
        self.mensagem = ""

    @property
    def atual(self) -> PoseDeConfirmacao:
        return self._poses[self._indice]

    @property
    def indice(self) -> int:
        return self._indice

    def respostas(self) -> dict[str, Resposta]:
        return dict(self._respostas)

    def concluido(self) -> bool:
        return all(p.nome in self._respostas for p in self._poses)

    def responder(self, resposta: Resposta) -> bool:
        """Registra a resposta da pose atual e avança. ``False`` se já acabou."""
        self._respostas[self.atual.nome] = resposta

        return self.avancar()

    def avancar(self, passo: int = 1) -> bool:
        """Vai para a próxima pose sem resposta (circular). ``False`` se não há."""
        total = len(self._poses)

        for deslocamento in range(1, total + 1):
            candidato = (self._indice + passo * deslocamento) % total

            if self._poses[candidato].nome not in self._respostas:
                self._indice = candidato
                return True

        self.mensagem = "Todas respondidas. Esc salva e sai."

        return False

    def selecionar(self, nome: str) -> None:
        nomes = [p.nome for p in self._poses]

        if nome not in nomes:
            raise KeyError(f"pose desconhecida: {nome!r} (opções: {', '.join(nomes)})")

        self._indice = nomes.index(nome)

    def para_dict(self) -> dict[str, Any]:
        return {
            "versao": VERSAO_ARQUIVO,
            "respostas": {
                p.nome: {"item": p.item, "pergunta": p.pergunta, "resposta": self._respostas[p.nome].value}
                for p in self._poses
                if p.nome in self._respostas
            },
        }

    def carregar_dict(self, dados: dict[str, Any]) -> int:
        nomes = {p.nome for p in self._poses}
        carregadas = 0

        for nome, info in dados.get("respostas", {}).items():
            if nome in nomes:
                try:
                    self._respostas[nome] = Resposta(info["resposta"])
                except (KeyError, ValueError, TypeError):
                    continue

                carregadas += 1

        return carregadas

    def salvar(self, destino: Path) -> None:
        """Grava o JSON em UTF-8 sem BOM, LF."""
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(self.para_dict(), ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8", newline="\n")

    def carregar(self, origem: Path) -> int:
        return self.carregar_dict(json.loads(origem.read_text(encoding="utf-8")))

    def linhas_hud(self) -> list[str]:
        pose = self.atual
        resposta = self._respostas.get(pose.nome)
        linhas = [
            f"POSE {self._indice + 1}/{len(self._poses)}: {pose.nome}  [{pose.estado}]  ({pose.item})",
            pose.pergunta,
            "1 = correto   2 = errado   3 = pular   v = frente/lado   setas = navegar   esc = salva e sai",
            f"resposta atual: {resposta.value if resposta else '(nenhuma)'}   "
            f"respondidas: {len(self._respostas)}/{len(self._poses)}",
        ]

        if self.mensagem:
            linhas.append(self.mensagem)

        return linhas
