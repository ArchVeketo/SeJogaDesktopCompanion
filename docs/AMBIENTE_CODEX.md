# Ambiente de desenvolvimento no Codex

Verificado em 04/11/2026. O roteiro do produto continua em [STATUS_E_PROXIMOS_PASSOS.md](STATUS_E_PROXIMOS_PASSOS.md).

## Implementado

- `AGENTS.md` na raiz reúne comandos, limites entre módulos e armadilhas verificadas neste projeto. A [documentação oficial](https://learn.chatgpt.com/docs/agent-configuration/agents-md) explica a descoberta de instruções por diretório.
- Skills locais em `.agents/skills`: `sejoga-release-build`, `sejoga-blockbench-animation` e `sejoga-win32-overlay-debug`. Foram validadas com `quick_validate.py`. A estrutura segue o [formato de skills documentado](https://learn.chatgpt.com/docs/build-skills); não é necessário criar um plugin para usar essas skills no repositório.
- O plugin GitHub já estava disponível: leitura dos metadados de `ArchVeketo/SeJogaDesktopCompanion` funcionou. Nenhuma alteração remota foi feita para configurá-lo.
- Context7 foi registrado em `~/.codex/config.toml` como MCP HTTP habilitado, apontando para `https://mcp.context7.com/mcp`. O endpoint respondeu ao handshake MCP sem credenciais (HTTP 200). Não foram enviados código nem arquivos do repositório.

## Context7: estado e uso

Foi usada a conexão remota, oferecida na [documentação do Context7 para Codex](https://context7.com/docs/clients/codex), em vez de instalar/executar um pacote Node. O Codex suporta esse transporte pela chave `url`, conforme a [referência oficial](https://learn.chatgpt.com/docs/config-file/config-reference).

A CLI detectou suporte OAuth e iniciou o fluxo de login; o login não foi concluído. O servidor permanece configurado, mas suas ferramentas não estão carregadas retroativamente nesta conversa. Abra uma nova sessão do Codex para conferir a descoberta. Se o cliente exigir autenticação, use `codex mcp login context7` e conclua o login pessoalmente. A verificação de handshake anônimo não garante acesso ilimitado às consultas nem que todas as bibliotecas desejadas estejam indexadas.

Não foram instalados MCPs de automação Windows, Blender, plugins DSH, memória ou multiagentes. Os smokes Python e Win32 existentes atendem à validação atual; integrações adicionais devem resolver uma necessidade observada.

## Perfis e permissões

O companion usa primeiro o perfil original em `%LOCALAPPDATA%/ArchVeketo/SeJogaDesktopCompanion`. A gravação usa temporário exclusivo e, se o caminho padrão recusar escrita, tenta `%APPDATA%/SeJogaDesktopCompanion/config.toml`. Se ambos forem bloqueados, o executável tenta `user-data/config.toml` ao lado do `.exe`. O perfil alternativo salvo passa a ser escolhido nos próximos carregamentos. Caminhos explicitamente fornecidos não mudam silenciosamente de destino. Não inclua `user-data` em uma distribuição pública: contém preferências/logs/capturas pessoais. Na sessão do agente, ambos os caminhos AppData foram bloqueados para o bundle, embora a gravação pelo shell de ferramentas funcionasse.

Para testes isolados, defina `SEJOGA_CONFIG_PATH` antes de iniciar o processo. Logs/capturas usam a pasta desse perfil. Não mude permissões do Windows nem execute como administrador para contornar uma falha de escrita do teste.
