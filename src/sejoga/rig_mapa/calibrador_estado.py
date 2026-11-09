"""Estado puro do calibrador interativo de eixos (sem Panda3D, Qt ou Win32).

Guarda o que o usuário faz na ferramenta ``tools/calibrar_interativo.py``:
qual junta/eixo está ativo, quanto cada eixo foi girado, o que ele MARCOU ter
visto na tela e a serialização disso em JSON/Markdown. A janela e o teclado
vivem na ferramenta; aqui só há dados e regras, testáveis sem GPU.

Convenção: o renderer aplica ``setHpr(H=y, P=x, R=z)`` a partir de
``Rotation3(x, y, z)`` em radianos; os ângulos aqui ficam em GRAUS (o que o
usuário enxerga) e viram radianos só em :meth:`EstadoCalibrador.pose`.

Direções são sempre as vistas NA TELA, com o mascote de frente para a câmera:
``sobe``/``desce`` (vertical), ``frente`` (vem em direção à câmera),
``tras`` (afasta da câmera), ``dentro`` (aproxima do corpo/atravessa o tronco),
``fora`` (afasta lateralmente do corpo), ``direita``/``esquerda`` (lados da
tela) e ``nenhum`` (a rotação não produz movimento visível).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from math import radians
from pathlib import Path
from typing import Any

from sejoga.nucleo.rig import Rotation3

# --------------------------------------------------------------------------- #
# Constantes nomeadas
# --------------------------------------------------------------------------- #
VERSAO_ARQUIVO = 1
"""Versão do formato do arquivo salvo; muda se o esquema mudar."""

PASSO_PADRAO_GRAUS = 5.0
"""Passo de uma tecla de giro."""

PASSO_FINO_GRAUS = 1.0
"""Passo com a tecla modificadora de precisão."""

PASSO_GROSSO_GRAUS = 15.0
"""Passo com a tecla modificadora de salto grande."""

LIMITE_GRAUS = 180.0
"""Valor máximo absoluto de um eixo (antes de a rotação dar a volta)."""

ANGULO_TESTE_GRAUS = 45.0
"""Ângulo do atalho de teste rápido (alterna +ângulo, -ângulo e zero)."""

SINAL_POSITIVO = "+"
SINAL_NEGATIVO = "-"

ALCANCE_NULO = 0.0
"""Valor de eixo considerado "sem giro": não permite marcar sinal."""

PRECISAO_EXIBICAO = 1
"""Casas decimais do valor mostrado no HUD e salvo no arquivo."""


class Eixo(StrEnum):
    """Campo do ``Rotation3`` girado (renderer: x=pitch, y=heading, z=roll)."""

    X = "x"
    Y = "y"
    Z = "z"


class Direcao(StrEnum):
    """Movimento real visto na tela quando o eixo/sinal ativo é aplicado."""

    SOBE = "sobe"
    DESCE = "desce"
    FRENTE = "frente"
    TRAS = "tras"
    DENTRO = "dentro"
    FORA = "fora"
    DIREITA = "direita"
    ESQUERDA = "esquerda"
    NENHUM = "nenhum"


JUNTAS: dict[str, str] = {
    "tronco": "body",
    "cabeca": "head",
    "porta": "door",
    "pernas": "legs",
    "pe_esq": "left-feet",
    "pe_dir": "right-feet",
    "ombro_dir": "right-arm",
    "ombro_sub_dir": "shoulder",
    "cotovelo_dir": "ant-arm",
    "mao_dir": "hand",
    "dedos_dir": "fingers",
    "ombro_esq": "left-arm",
    "ombro_sub_esq": "shoulder2",
    "cotovelo_esq": "ant-arm2",
    "mao_esq": "hand2",
    "dedos_esq": "fingers2",
}
"""Juntas calibráveis: nome legível -> grupo real do rig.

``right-arm``/``left-arm`` são o OSSO BASE de cada braço (o nó que o IK gira);
``shoulder``/``shoulder2`` são sub-nós de compensação do ombro.
"""

#: Chave interna de uma marcação: (junta, eixo, sinal).
ChaveMarcacao = tuple[str, Eixo, str]


@dataclass(frozen=True, slots=True)
class Marcacao:
    """O que o usuário viu ao girar uma junta num eixo e sinal."""

    direcao: Direcao
    graus: float


def sinal_de(valor: float) -> str | None:
    """Sinal ``+``/``-`` de um valor, ou ``None`` se não há giro."""
    if valor > ALCANCE_NULO:
        return SINAL_POSITIVO
    if valor < ALCANCE_NULO:
        return SINAL_NEGATIVO
    return None


class EstadoCalibrador:
    """Seleção, valores aplicados e marcações do calibrador interativo."""

    def __init__(self, juntas: dict[str, str] | None = None) -> None:
        self._juntas = dict(JUNTAS if juntas is None else juntas)
        if not self._juntas:
            raise ValueError("o calibrador precisa de ao menos uma junta")
        self._nomes = tuple(self._juntas)
        self._indice = 0
        self._eixo = Eixo.X
        self._valores: dict[str, dict[Eixo, float]] = {
            nome: dict.fromkeys(Eixo, 0.0) for nome in self._nomes
        }
        self._marcacoes: dict[ChaveMarcacao, Marcacao] = {}
        self.mensagem = ""

    # ------------------------------------------------------------------ seleção
    @property
    def nomes_juntas(self) -> tuple[str, ...]:
        return self._nomes

    @property
    def junta(self) -> str:
        return self._nomes[self._indice]

    @property
    def grupo(self) -> str:
        return self._juntas[self.junta]

    @property
    def eixo(self) -> Eixo:
        return self._eixo

    @property
    def valor(self) -> float:
        """Valor (graus) do eixo ativo da junta ativa."""
        return self._valores[self.junta][self._eixo]

    def valor_de(self, junta: str, eixo: Eixo) -> float:
        return self._valores[junta][eixo]

    def proxima_junta(self, passo: int = 1) -> None:
        """Avança (ou recua, com ``passo`` negativo) circularmente."""
        self._indice = (self._indice + passo) % len(self._nomes)

    def selecionar_junta(self, nome: str) -> None:
        if nome not in self._juntas:
            raise KeyError(nome)
        self._indice = self._nomes.index(nome)

    def selecionar_eixo(self, eixo: Eixo) -> None:
        self._eixo = Eixo(eixo)

    def _combinacoes(self) -> list[ChaveMarcacao]:
        """Todas as combinações (junta, eixo, sinal) na ordem do roteiro."""
        return [
            (nome, eixo, sinal)
            for nome in self._nomes
            for eixo in Eixo
            for sinal in (SINAL_POSITIVO, SINAL_NEGATIVO)
        ]

    def ir_para_proximo_pendente(
        self, angulo: float = ANGULO_TESTE_GRAUS, incluir_atual: bool = False
    ) -> bool:
        """Modo guiado: leva a ferramenta à próxima combinação sem marcação.

        Zera todas as juntas, seleciona junta e eixo e aplica ``±angulo``, de
        modo que o usuário só precise olhar e apertar uma tecla de direção.
        A busca começa depois da combinação ativa (circular). Devolve ``False``
        quando tudo já foi marcado.
        """
        todas = self._combinacoes()
        sinal_atual = sinal_de(self.valor) or SINAL_POSITIVO
        inicio = todas.index((self.junta, self._eixo, sinal_atual))
        primeiro = 0 if incluir_atual else 1
        for deslocamento in range(primeiro, len(todas) + primeiro):
            junta, eixo, sinal = todas[(inicio + deslocamento) % len(todas)]
            if (junta, eixo, sinal) in self._marcacoes:
                continue
            self.zerar_tudo()
            self.selecionar_junta(junta)
            self.selecionar_eixo(eixo)
            self.definir_valor(angulo if sinal == SINAL_POSITIVO else -angulo)
            return True
        return False

    def pendencias(self, junta: str) -> list[tuple[Eixo, str]]:
        """Combinações (eixo, sinal) da junta ainda sem marcação."""
        return [
            (eixo, sinal)
            for eixo in Eixo
            for sinal in (SINAL_POSITIVO, SINAL_NEGATIVO)
            if (junta, eixo, sinal) not in self._marcacoes
        ]

    # ------------------------------------------------------------------- valores
    def girar(self, delta_graus: float) -> float:
        """Soma ``delta_graus`` ao eixo ativo, respeitando o limite."""
        return self.definir_valor(self.valor + delta_graus)

    def definir_valor(self, graus: float) -> float:
        limitado = max(-LIMITE_GRAUS, min(LIMITE_GRAUS, graus))
        self._valores[self.junta][self._eixo] = limitado
        return limitado

    def alternar_teste(self, angulo: float = ANGULO_TESTE_GRAUS) -> float:
        """Atalho: zero -> +ângulo -> -ângulo -> zero no eixo ativo."""
        atual = self.valor
        if atual == ALCANCE_NULO:
            return self.definir_valor(angulo)
        if atual > ALCANCE_NULO:
            return self.definir_valor(-angulo)
        return self.definir_valor(ALCANCE_NULO)

    def zerar_eixo(self) -> None:
        self.definir_valor(ALCANCE_NULO)

    def zerar_junta(self) -> None:
        self._valores[self.junta] = dict.fromkeys(Eixo, 0.0)

    def zerar_tudo(self) -> None:
        for nome in self._nomes:
            self._valores[nome] = dict.fromkeys(Eixo, 0.0)

    def pose(self) -> dict[str, Rotation3]:
        """Pose para o renderer: só as juntas com algum giro, em radianos."""
        saida: dict[str, Rotation3] = {}
        for nome in self._nomes:
            v = self._valores[nome]
            if any(v[e] != ALCANCE_NULO for e in Eixo):
                saida[self._juntas[nome]] = Rotation3(
                    radians(v[Eixo.X]), radians(v[Eixo.Y]), radians(v[Eixo.Z])
                )
        return saida

    # ---------------------------------------------------------------- marcações
    def marcar(self, direcao: Direcao) -> bool:
        """Registra o que se viu para junta/eixo/sinal ATIVOS.

        O sinal vem do valor atual do eixo; sem giro não há o que marcar e a
        mensagem explica o motivo. Marcar de novo a mesma combinação substitui.
        """
        sinal = sinal_de(self.valor)
        if sinal is None:
            self.mensagem = "Gire o eixo antes de marcar (valor está em 0)."
            return False
        chave = (self.junta, self._eixo, sinal)
        self._marcacoes[chave] = Marcacao(Direcao(direcao), round(self.valor, PRECISAO_EXIBICAO))
        self.mensagem = f"{self.junta} {sinal}{self._eixo.value} = {Direcao(direcao).value}"
        return True

    def desmarcar(self) -> bool:
        """Remove a marcação da combinação ativa (sinal do valor atual)."""
        sinal = sinal_de(self.valor)
        if sinal is None:
            self.mensagem = "Gire o eixo para escolher qual sinal desmarcar."
            return False
        removida = self._marcacoes.pop((self.junta, self._eixo, sinal), None)
        self.mensagem = "Marcação removida." if removida else "Não havia marcação."
        return removida is not None

    def marcacao_ativa(self) -> Marcacao | None:
        """Marcação já feita para a combinação ativa, se houver."""
        sinal = sinal_de(self.valor)
        if sinal is None:
            return None
        return self._marcacoes.get((self.junta, self._eixo, sinal))

    @property
    def marcacoes(self) -> dict[ChaveMarcacao, Marcacao]:
        return dict(self._marcacoes)

    def total_marcado(self) -> int:
        return len(self._marcacoes)

    def total_possivel(self) -> int:
        return len(self._nomes) * len(Eixo) * 2

    # --------------------------------------------------------------- serialização
    def para_dict(self) -> dict[str, Any]:
        """Dicionário serializável: marcações por junta e mapa inverso.

        ``marcacoes``: junta -> ``"+x"`` -> {direcao, graus}.
        ``inverso``: junta -> direção -> lista de {eixo, sinal}, ou seja,
        "para fazer o membro SUBIR, gire este eixo neste sinal" (o que o código
        consome para corrigir a convenção).
        """
        marcacoes: dict[str, dict[str, dict[str, Any]]] = {}
        inverso: dict[str, dict[str, list[dict[str, str]]]] = {}
        for (junta, eixo, sinal), m in sorted(
            self._marcacoes.items(), key=lambda kv: (self._nomes.index(kv[0][0]), kv[0][1], kv[0][2])
        ):
            marcacoes.setdefault(junta, {})[f"{sinal}{eixo.value}"] = {
                "direcao": m.direcao.value,
                "graus": m.graus,
            }
            inverso.setdefault(junta, {}).setdefault(m.direcao.value, []).append(
                {"eixo": eixo.value, "sinal": sinal}
            )
        return {
            "versao": VERSAO_ARQUIVO,
            "juntas": {nome: grupo for nome, grupo in self._juntas.items()},
            "marcacoes": marcacoes,
            "inverso": inverso,
        }

    def para_json(self) -> str:
        return json.dumps(self.para_dict(), ensure_ascii=False, indent=2) + "\n"

    def carregar_dict(self, dados: dict[str, Any]) -> int:
        """Mescla marcações de um dicionário salvo; devolve quantas aplicou.

        Ignora com segurança juntas, eixos ou direções que não existem mais.
        """
        if dados.get("versao") != VERSAO_ARQUIVO:
            raise ValueError(f"versão de arquivo não suportada: {dados.get('versao')!r}")
        aplicadas = 0
        for junta, itens in dados.get("marcacoes", {}).items():
            if junta not in self._juntas:
                continue
            for chave, info in itens.items():
                if len(chave) != 2 or chave[0] not in (SINAL_POSITIVO, SINAL_NEGATIVO):
                    continue
                try:
                    eixo = Eixo(chave[1])
                    direcao = Direcao(info["direcao"])
                    graus = float(info["graus"])
                except (ValueError, KeyError, TypeError):
                    continue
                self._marcacoes[(junta, eixo, chave[0])] = Marcacao(direcao, graus)
                aplicadas += 1
        return aplicadas

    def salvar(self, destino_json: Path, destino_md: Path | None = None) -> None:
        """Grava o JSON (e, se pedido, o Markdown) em UTF-8 sem BOM, LF."""
        destino_json.parent.mkdir(parents=True, exist_ok=True)
        destino_json.write_text(self.para_json(), encoding="utf-8", newline="\n")
        if destino_md is not None:
            destino_md.parent.mkdir(parents=True, exist_ok=True)
            destino_md.write_text(self.para_markdown(), encoding="utf-8", newline="\n")

    def carregar(self, origem_json: Path) -> int:
        return self.carregar_dict(json.loads(origem_json.read_text(encoding="utf-8")))

    def para_markdown(self) -> str:
        """Tabela legível: uma linha por junta/eixo/sinal marcado."""
        linhas = [
            "# Mapa de eixos CALIBRADO (interativo)",
            "",
            f"Marcações: {self.total_marcado()} de {self.total_possivel()}.",
            "Direções vistas na tela, mascote de frente para a câmera.",
            "",
            "| junta | grupo | eixo/sinal | direção vista | graus aplicados |",
            "|---|---|---|---|---|",
        ]
        dados = self.para_dict()["marcacoes"]
        for junta in self._nomes:
            for chave, info in dados.get(junta, {}).items():
                linhas.append(
                    f"| {junta} | `{self._juntas[junta]}` | {chave} | "
                    f"{info['direcao']} | {info['graus']:g} |"
                )
        faltando = [n for n in self._nomes if self.pendencias(n)]
        linhas += ["", "## Juntas com pendências", ""]
        linhas += [f"- {n}: {len(self.pendencias(n))} combinação(ões)" for n in faltando] or [
            "- nenhuma"
        ]
        return "\n".join(linhas) + "\n"

    # --------------------------------------------------------------------- HUD
    def linhas_hud(self) -> list[str]:
        """Texto do painel: junta, eixo, sinal, valor aplicado e marcação."""
        sinal = sinal_de(self.valor) or "0"
        marc = self.marcacao_ativa()
        marcada = marc.direcao.value if marc else "(sem marcação)"
        linhas = [
            f"JUNTA {self._indice + 1}/{len(self._nomes)}: {self.junta}  [{self.grupo}]",
            f"EIXO {self._eixo.value.upper()}  sinal {sinal}  valor {self.valor:+.{PRECISAO_EXIBICAO}f} graus",
            "valores (x y z): "
            + " ".join(f"{self.valor_de(self.junta, e):+.{PRECISAO_EXIBICAO}f}" for e in Eixo),
            f"marcado para esta combinação: {marcada}",
            f"progresso: {self.total_marcado()}/{self.total_possivel()} marcações",
        ]
        if self.mensagem:
            linhas.append(self.mensagem)
        return linhas
