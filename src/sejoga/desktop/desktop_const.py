"""Constantes estruturais do subpacote ``desktop`` (layout de UI e protocolo Win32).

Separa número "mágico" de código em dois grupos nomeados:

- **Layout/UX do diálogo de configurações** (``ui.py``): faixas, passos e
  larguras dos widgets Qt. São escolhas de interface, não limiares de domínio
  (estes vivem em ``fisica_tuning.py``); os extremos espelham os limites de
  validação de ``config.py``.
- **Protocolo Win32 da bandeja e da janela** (``tray_registration.py``,
  ``desktop_shell.py``): mensagens, flags e tamanhos de ícone exigidos pela
  API do Shell/USER32. Têm valor fixo ditado pelo sistema operacional.

Módulo sem engine gráfica própria: só define números; quem desenha é o Qt/Win32.
"""

from __future__ import annotations

# ============================================================
# Layout do diálogo de configurações (ui.py)
# ============================================================

#: Largura mínima (px) do diálogo de preferências.
DIALOGO_LARGURA_MINIMA = 420

#: Tamanho da janela do mascote: faixa (px) e passo do spin box.
TAMANHO_JANELA_MINIMO = 240
TAMANHO_JANELA_MAXIMO = 960
TAMANHO_JANELA_PASSO = 40

#: FPS alvo do mascote: faixa (quadros/s), passo e sufixo (espelha config.py).
FPS_MINIMO = 15
FPS_MAXIMO = 240
FPS_PASSO = 5
FPS_SUFIXO = " FPS"

#: Escala do mascote: faixa, passo e casas decimais do spin box.
ESCALA_MINIMA = 0.5
ESCALA_MAXIMA = 2.5
ESCALA_PASSO = 0.1
ESCALA_CASAS = 1

#: Espessura do contorno: faixa (px), passo e casas (espelha config.py).
CONTORNO_LARGURA_MINIMA = 0.5
CONTORNO_LARGURA_MAXIMA = 8.0
CONTORNO_LARGURA_PASSO = 0.5
CONTORNO_LARGURA_CASAS = 1

#: Respiração do contorno: faixa, passo e casas (0 = linha estática).
CONTORNO_RESPIRACAO_MINIMA = 0.0
CONTORNO_RESPIRACAO_MAXIMA = 1.0
CONTORNO_RESPIRACAO_PASSO = 0.1
CONTORNO_RESPIRACAO_CASAS = 1

#: Faixas 0..1 (sensibilidade da batida, chance de dança) e passo comum.
FRACAO_MINIMA = 0.0
FRACAO_MAXIMA = 1.0
FRACAO_PASSO = 0.05

#: Timeout (s) para a thread de atalhos sinalizar pronta / encerrar.
THREAD_TIMEOUT = 2.0


# ============================================================
# Protocolo Win32 da bandeja (tray_registration.py)
# ============================================================

#: Qt registra o ícone com uID=0 e callback WM_APP+101; reusamos o mesmo par.
TRAY_UID = 0
TRAY_CALLBACK_MESSAGE_OFFSET = 101  # somado a win32con.WM_APP

#: Flags de NOTIFYICONDATA: MESSAGE | ICON | TIP | SHOWTIP.
NIF_MESSAGE = 0x01
NIF_ICON = 0x02
NIF_TIP = 0x04
NIF_SHOWTIP = 0x80
TRAY_FLAGS = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP

#: Comandos Shell_NotifyIcon e versão do contrato de notificação.
NIM_ADD = 0
NIM_SETVERSION = 4
NOTIFYICON_VERSION_4 = 4

#: Lado (px) do ícone carregado para a bandeja (16x16 padrão do systray).
TRAY_ICONE_LADO = 16

#: Limite de caracteres do tooltip (szTip tem 128 wchars, 1 para o terminador).
TRAY_TOOLTIP_MAX = 127


# ============================================================
# Protocolo Win32 da janela nativa (desktop_shell.py)
# ============================================================

#: Tamanhos (px) dos ícones pequeno e grande da janela.
ICONE_PEQUENO_LADO = 32
ICONE_GRANDE_LADO = 64

#: WM_SYSCOMMAND entrega o id do comando com os 4 bits baixos reservados;
#: mascaramos com isto antes de comparar com os ids do menu do sistema.
SYSCOMMAND_MASCARA = 0xFFF0
