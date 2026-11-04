---
name: sejoga-release-build
description: Compilar e validar uma versão Windows do SeJogaDesktopCompanion, incluindo testes, janela real, executável PyInstaller e evidência visual.
---

Use na raiz deste repositório. Consulte `AGENTS.md` e o roadmap em `docs/STATUS_E_PROXIMOS_PASSOS.md`.

- Execute `python -m pytest` e os smokes `python tools/smoke_mouse.py` com/sem `--physics` conforme a mudança. Resolva falhas antes de distribuir.
- Feche apenas as instâncias deste companion que precisam liberar os arquivos do bundle. Verifique PID e caminho; prefira encerramento normal.
- Execute `.\build.ps1`, confira o exit code e preserve um log. Mantenha o filtro que exclui as DLLs privadas do runtime do Codex/Poppler.
- Abra o `.exe` resultante. Use `SEJOGA_CONFIG_PATH` com caminho absoluto de perfil de teste para isolar configurações, logs e capturas; não confunda sucesso em fonte com sucesso do bundle.
- Verifique fundo transparente, contorno respeitando alpha, z-order, seleção/arraste com eventos reais de mouse e saída sem erro 1400. Confira a imagem produzida, além dos logs. Ao injetar eventos, solte botões e restaure o cursor em `finally`; dê tempo ao app para observar a soltura antes de reposicionar o cursor.
- Teste salvar/reabrir preferências se a persistência mudou. Distribua toda a pasta `onedir`, nunca somente o executável. Exclua a pasta pessoal `user-data` de distribuições públicas.
- Registre versão/commit e limitações verificadas no roadmap. Faça commit quando autorizado na sessão; publicar ou enviar mensagens exige autorização específica.
