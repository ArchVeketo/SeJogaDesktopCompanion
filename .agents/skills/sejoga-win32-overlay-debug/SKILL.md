---
name: sejoga-win32-overlay-debug
description: Diagnosticar falhas de mouse, transparência, z-order, DPI, foco e encerramento no overlay Win32 do SeJogaDesktopCompanion.
---

- Registre PID, executável e HWND da instância sob teste. Confira `IsWindow`, estilos e retângulo após os primeiros frames.
- `WS_EX_NOACTIVATE` evita roubar foco. `WS_EX_TRANSPARENT` global também atravessa o personagem; fundo e hit-test precisam ser verificados separadamente.
- Compare screenshot do framebuffer com captura do desktop composto. O color key compara a cor final após PBR, não a cor configurada antes do shader. Rosa é esperado no modo diagnóstico.
- Confira `WindowFromPoint` sobre malha e fundo antes de clicar; registre botão, posição, hit e janela atingida. Teste gesto iniciado fora e soltura fora. Não declare sucesso usando apenas mocks do polling.
- Converta explicitamente entre pixels locais da área cliente e coordenadas absolutas do desktop. Teste origem negativa e área útil; não afirme suporte a DPI misto ou travessia de monitores sem verificar.
- Valide o fechamento durante a física. HWND inválido deve encerrar tarefas, sem SetWindowPos em handle destruído.
- Prefira Win32/pywin32 e os smokes já presentes a adicionar um servidor MCP de automação. Preserve/restaure cursor e solte botões injetados em `finally`.
