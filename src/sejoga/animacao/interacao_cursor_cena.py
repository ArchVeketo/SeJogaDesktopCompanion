"""Máquina pura de interação segura com o cursor para cenas narrativas.

Cumpre estritamente a Regra #6 de ``SPEC_ROTEIROS_IDLES_E_ACOES.md``:
- Só atua se o cursor começar próximo do Mário e o usuário não estiver ocupado
  (digitando, clicando ou em janela busy).
- Retenção/ocultação máxima <= 2.45 s.
- Liberação IMEDIATA (< 1 quadro) ao menor puxão rápido do mouse, clique ou ESC.
- Se o usuário puxar o mouse para fugir durante o bote de ``cacar_cursor_sucesso``,
  converte em tempo real a cena para ``cacar_cursor_falha`` no mesmo instante ``t``.

Módulo puro: sem dependências de Panda3D, Qt ou Win32.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, hypot, pi, sin

Ponto2D = tuple[float, float]

CENAS_CURSOR = frozenset({"cacar_cursor_sucesso", "roubo_cursor_tentaculo"})
LIMIAR_PUXAO_ESCAPE_PX: float = 26.0
MAX_DURACAO_RETENCAO_S: float = 2.45


@dataclass(frozen=True, slots=True)
class ComandoCursorCena:
    """Instrução por quadro para a ponte Win32 em ``janela.py``."""

    mover_para: Ponto2D | None = None
    ocultar_cursor: bool = False
    converter_para_falha: bool = False
    encerrado_por_escape: bool = False


class ControladorCursorCena:
    """Orquestra captura suave, pulinhos e escape imediato do cursor em cenas."""

    def __init__(self) -> None:
        """Inicializa o estado desarmado."""
        self.cena_ativa: str = ""
        self.engajado: bool = False
        self.cancelado: bool = False
        self.tempo_retido_s: float = 0.0
        self.origem_captura: Ponto2D | None = None
        self.ultimo_imposto: Ponto2D | None = None

    def resetar(self) -> None:
        """Limpa todo o estado ao encerrar ou cancelar uma cena."""
        self.cena_ativa = ""
        self.engajado = False
        self.cancelado = False
        self.tempo_retido_s = 0.0
        self.origem_captura = None
        self.ultimo_imposto = None

    def _checar_escape(
        self,
        cursor_atual: Ponto2D,
        *,
        clicou: bool,
        tecla_escape: bool,
        digitando: bool,
    ) -> bool:
        if clicou or tecla_escape or digitando or self.tempo_retido_s > MAX_DURACAO_RETENCAO_S:
            return True
        if self.ultimo_imposto is not None:
            dist = hypot(
                cursor_atual[0] - self.ultimo_imposto[0],
                cursor_atual[1] - self.ultimo_imposto[1],
            )
            if dist >= LIMIAR_PUXAO_ESCAPE_PX:
                return True
        return False

    def atualizar(
        self,
        dt: float,
        *,
        cena_nome: str,
        cena_tempo: float,
        cursor_atual: Ponto2D,
        mascote_centro: Ponto2D,
        raio_proximidade_px: float,
        ponto_chao: Ponto2D,
        ponto_palma: Ponto2D,
        ponto_boca: Ponto2D,
        permitido: bool = True,
        clicou: bool = False,
        tecla_escape: bool = False,
        digitando: bool = False,
    ) -> ComandoCursorCena:
        """Calcula o comando de cursor para o quadro atual."""
        if cena_nome not in CENAS_CURSOR or not permitido:
            self.resetar()
            return ComandoCursorCena()

        if cena_nome != self.cena_ativa:
            self.resetar()
            self.cena_ativa = cena_nome
            dist_ini = hypot(
                cursor_atual[0] - mascote_centro[0],
                cursor_atual[1] - mascote_centro[1],
            )
            if dist_ini > max(80.0, raio_proximidade_px) or clicou or tecla_escape or digitando:
                self.cancelado = True

        if self.cancelado:
            return ComandoCursorCena()

        # Antes do bote: monitora se o usuário puxou o mouse pra longe na hora H!
        t_inicio_acao = 1.68 if cena_nome == "cacar_cursor_sucesso" else 0.70
        if cena_tempo < t_inicio_acao:
            dist_agora = hypot(
                cursor_atual[0] - mascote_centro[0],
                cursor_atual[1] - mascote_centro[1],
            )
            if clicou or tecla_escape or digitando or dist_agora > max(95.0, raio_proximidade_px * 1.15):
                self.cancelado = True
                conv = cena_nome == "cacar_cursor_sucesso" and 1.10 <= cena_tempo < 1.88
                return ComandoCursorCena(converter_para_falha=conv, encerrado_por_escape=True)
            return ComandoCursorCena()

        if not self.engajado:
            self.engajado = True
            self.origem_captura = cursor_atual
            self.ultimo_imposto = cursor_atual

        if self._checar_escape(
            cursor_atual, clicou=clicou, tecla_escape=tecla_escape, digitando=digitando
        ):
            self.cancelado = True
            self.ultimo_imposto = None
            conv = cena_nome == "cacar_cursor_sucesso" and cena_tempo < 1.90
            return ComandoCursorCena(
                ocultar_cursor=False,
                converter_para_falha=conv,
                encerrado_por_escape=True,
            )

        if cena_nome == "cacar_cursor_sucesso":
            return self._passo_cacar_sucesso(dt, cena_tempo, ponto_chao, ponto_palma)
        return self._passo_roubo_tentaculo(dt, cena_tempo, ponto_boca, ponto_chao)

    def _passo_cacar_sucesso(
        self, dt: float, t: float, chao: Ponto2D, palma: Ponto2D
    ) -> ComandoCursorCena:
        orig = self.origem_captura or chao
        if t < 2.28:
            self.tempo_retido_s += max(0.0, dt)
            u = max(0.0, min(1.0, (t - 1.68) / 0.60))
            s = u * u * (3.0 - 2.0 * u)
            meio = (orig[0] + (chao[0] - orig[0]) * min(1.0, u * 2.5), orig[1] + (chao[1] - orig[1]) * min(1.0, u * 2.5))
            alvo = (meio[0] + (palma[0] - meio[0]) * s, meio[1] + (palma[1] - meio[1]) * s)
            self.ultimo_imposto = alvo
            return ComandoCursorCena(mover_para=alvo)
        if t < 4.10:
            self.tempo_retido_s += max(0.0, dt)
            pulo = sum(exp(-(((t - c) / 0.09) ** 2)) for c in (2.68, 3.06, 3.68))
            alvo = (palma[0] + pulo * 5.0, palma[1] - pulo * 11.0)
            self.ultimo_imposto = alvo
            return ComandoCursorCena(mover_para=alvo)
        if t < 4.38:
            u = (t - 4.10) / 0.28
            alvo = (palma[0] + u * 28.0, palma[1] - sin(u * pi * 0.5) * 34.0)
            self.ultimo_imposto = alvo
            return ComandoCursorCena(mover_para=alvo)
        self.ultimo_imposto = None
        return ComandoCursorCena()

    def _passo_roubo_tentaculo(
        self, dt: float, t: float, boca: Ponto2D, chao: Ponto2D
    ) -> ComandoCursorCena:
        orig = self.origem_captura or boca
        if t < 1.22:
            self.tempo_retido_s += max(0.0, dt)
            u = max(0.0, min(1.0, (t - 0.70) / 0.52))
            s = u * u * (3.0 - 2.0 * u)
            alvo = (orig[0] + (boca[0] - orig[0]) * s, orig[1] + (boca[1] - orig[1]) * s)
            self.ultimo_imposto = alvo
            return ComandoCursorCena(mover_para=alvo, ocultar_cursor=False)
        if t < 3.30:
            self.tempo_retido_s += max(0.0, dt)
            self.ultimo_imposto = boca
            return ComandoCursorCena(mover_para=boca, ocultar_cursor=True)
        if t < 3.86:
            u = (t - 3.30) / 0.56
            destino_x = boca[0] + 64.0
            destino_y = chao[1] - 6.0
            arco_y = -sin(u * pi) * 26.0
            alvo = (
                boca[0] + (destino_x - boca[0]) * u,
                boca[1] + (destino_y - boca[1]) * (u * u) + arco_y,
            )
            self.ultimo_imposto = alvo
            return ComandoCursorCena(mover_para=alvo, ocultar_cursor=False)
        self.ultimo_imposto = None
        return ComandoCursorCena(ocultar_cursor=False)
