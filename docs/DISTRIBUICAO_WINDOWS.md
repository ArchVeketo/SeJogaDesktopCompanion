# Distribuição Windows: instalador único e atualizações dinâmicas

Implementação na branch `feature/instalador-unico`.

## Contrato de distribuição

A distribuição é **um único instalador** com o **runtime embutido** — não há mais um setup por canal nem bootstrapper online. O setup instala para todos os usuários (com elevação do Windows), grava o runtime em `runtime/current` e **não precisa de internet para a primeira execução**. O mesmo arquivo serve para reparos reinstalando por cima.

O **canal de atualização** (release, pré-release ou nightly) é uma **configuração do aplicativo**, escolhida nas Configurações, e não uma variante de instalador. O instalador grava um `channel-info.json` neutro (`{"channel":"release","scope":"machine"}`) ao lado do launcher; quando o usuário troca o canal e manda atualizar, o app reescreve esse arquivo com o canal escolhido antes de acionar o agente nativo.

Uma mudança comum no aplicativo gera apenas **ZIP do runtime + SHA256 + channel.json**. Não recompila nem redistribui o instalador. O launcher/updater nativo fica fora do runtime e substitui somente `runtime/current`. Recompilar o instalador só é necessário quando o próprio layout/protocolo mudar.

### Layout da instalação

| Caminho | Conteúdo |
|---|---|
| `Program Files/SeJogaCompanion/SeJogaLauncher.exe` | launcher nativo (ponto de entrada dos atalhos) |
| `Program Files/SeJogaCompanion/channel-info.json` | canal + escopo lido pelo launcher |
| `Program Files/SeJogaCompanion/runtime/current/` | bundle completo + `release-info.json` |

Os feeds de cada canal são assets das releases de mesmo nome no repositório `ArchVeketo/SeJogaDesktopCompanion` (`updates-release/channel.json`, `updates-prerelease/channel.json`, `updates-nightly/channel.json`). Python não é necessário no PC de destino; alvo Windows 10 1809+/11 x64 com .NET Framework do sistema.

Configurações pertencem a cada usuário no AppData, num único caminho (`%LOCALAPPDATA%/SeJogaDesktopCompanion`). Não embutir perfis do desenvolvedor. Atualizações e desinstalação não apagam configurações. `SEJOGA_CONFIG_PATH` continua disponível para testes isolados.

## Fluxo de atualização

A busca é manual e aparece em dois lugares, ambos com confirmação antes de atualizar:

- **Configurações:** um seletor de canal (release/pré-release/nightly) persistido em `update.channel` e o botão **Buscar atualizações**, com rótulo de status cobrindo *buscando*, *nenhuma atualização*, *versão X disponível* e *erro*. A busca roda em thread e usa o canal selecionado.
- **Bandeja:** o item **Buscar atualizações…** abre o mesmo diálogo, que informa se há atualização e pergunta se o usuário quer atualizar.

Ao confirmar, o app reescreve o `channel-info.json` com o canal escolhido e aciona o launcher nativo (`--update`). A aplicação não fecha ao abrir o updater. O launcher inicia o agente elevado; cancelar UAC mantém o mascote aberto.

O agente baixa o pacote em uma pasta de preparação, valida tamanho/SHA256/canal/arquitetura/versão e extrai com limites de tamanho e proteção contra caminhos escapando do ZIP. Produção aceita somente os servidores HTTPS do GitHub definidos no código. Não aceita feed arbitrário por argumento ou ambiente.

Somente após preparar tudo, usa Restart Manager para solicitar encerramento normal. Renomeia `current` para `previous`, move a versão preparada para `current` e atualiza a versão exibida no registro de desinstalação. O launcher original reabre o mascote com o token do usuário. Se a troca falhar, restaura `previous`; se a energia cair entre renomeações, a próxima tentativa restaura `previous` antes de consultar a rede. A versão anterior permanece até a próxima atualização.

Versões antigas/build IDs regressivos são rejeitados. Não há atualização diferencial: cada atualização baixa o runtime completo. A busca no menu é manual; não há atualização silenciosa em segundo plano. O protocolo v1 mantém o agente nativo estável, que não é substituído pelo ZIP do aplicativo.

## Gerar o instalador

Requer Inno Setup 6/7 e compilador .NET Framework do Windows. Exige o bundle PyInstaller pronto em `dist/SeJogaCompanion` (gere com `.\build.ps1`).

```powershell
.\build.ps1                 # gera dist/SeJogaCompanion (runtime embutido no setup)
.\tools\build-installer.ps1 # instalador único com runtime embutido
```

Saída fixa `dist/installer/SeJogaCompanion-Setup-windows-x64.exe` e `.sha256`. Não há mais o parâmetro `-Channel`: é um único instalador. `-Version` ajusta a versão (padrão: lê do `pyproject.toml`) e `-Compiler` permite apontar o `ISCC.exe`. Se o `iscc` não estiver no PATH, o script falha com mensagem clara e ecoa o comando exato a rodar.

### Publicar a primeira release no GitHub

O instalador gerado é a **primeira release** do projeto e deve ir para a página de Releases. Com o `gh` CLI disponível:

```powershell
gh release create v0.1.0 `
  dist/installer/SeJogaCompanion-Setup-windows-x64.exe `
  dist/installer/SeJogaCompanion-Setup-windows-x64.exe.sha256 `
  --title "SeJoga Companion 0.1.0" --notes "Primeira release: instalador único."
```

A publicação em si é feita pelo orquestrador (o `gh` não está disponível na máquina de desenvolvimento desta etapa).

## Publicar uma versão do aplicativo

```powershell
python -m pytest
.\build.ps1
python tools/construir_atualizacao.py --channel release --version 0.1.0
python tools/construir_atualizacao.py --channel prerelease --version 0.2.0rc1
python tools/construir_atualizacao.py --channel nightly
```

Saídas em `dist/updates/<canal>`: ZIP com metadados, checksum e manifesto. Exclui perfis `user-data`, logs e fontes de arte. Os padrões de versão vêm de `pyproject.toml`, com `rc1` ou `.dev<UTC>` conforme o canal. Release/prerelease precisam de versão nova para cada publicação; nightly usa timestamp. `build_id` também é monotônico.

A publicação agora é feita por um **pipeline de CI/CD no GitHub Actions** (`.github/workflows/ci.yml` + o workflow reutilizável `_build-comum.yml`). Os comandos manuais acima continuam válidos como **fallback** quando se quer publicar da própria máquina. O pipeline:

- **push na `main`** → publica **nightly** automático (feed `updates-nightly`) e gera o instalador nightly;
- **tag `v*rc*`** (ex.: `v0.2.0rc1`) → publica **prerelease** (feed `updates-prerelease` + release marcada como pré-release com o instalador);
- **tag `v*` estável** (ex.: `v0.2.0`) → publica **release** (feed `updates-release` + release com o instalador);
- **execução manual** (`workflow_dispatch`) → escolhe `canal`, `gerar_instalador` e `publicar` (publicar **default FALSE**: só builda, empacota e sobe os artefatos do Actions para inspeção).

Cada job roda testes/ruff como gate (falhou, não publica), `build.ps1`, `tools/construir_atualizacao.py --channel <canal>` e, quando `gerar_instalador=true`, Inno Setup (`choco install innosetup`) + `tools/build-installer.ps1`. O instalador é sempre do canal `release` (o `release-info.json` embutido usa `channel=release` e versão estável do `pyproject`); por isso, em nightly/prerelease o instalador usa a versão do `pyproject`, não a versão rc/dev do feed. O feed verifica regressão via `construir_atualizacao`/`updater` e sobe ZIP/checksum junto com o `channel.json`. A publicação usa o `GITHUB_TOKEN` padrão do Actions (`permissions: contents: write`), sem secret extra.

> O runner do GitHub **não tem GPU**: o CI garante **build + empacote + publica**, não a **aparência** (app abre / overlay / render). A validação visual continua **manual**. Detalhes de disparo em `.github/workflows/README.md`.

Antes de disponibilizar um setup, publicar o primeiro feed compatível do canal. Sem feed, o setup aborta a preparação com mensagem; não contém um aplicativo offline de reserva. Ainda não há feed público publicado por esta implementação.

## Validação e limites

`python tools/smoke-distribution.py` (ou `tools/smoke-installer.ps1`) usa servidor loopback, AppId de teste e perfil isolado em Documents público. O modo de teste nunca pode atualizar Program Files. Instala o bundle real, troca entre duas versões de fixture com **o mesmo setup e o mesmo launcher**, verifica fechamento/reabertura, rejeição de corrupção/ZIP traversal/downgrade, recuperação offline de troca interrompida, reparo pelo mesmo setup, quatro danças/bandeja e desinstalação preservando perfil.

Evidência local de 05/11/2026: `C:/Users/Public/Documents/SeJogaDistributionSmoke/e1c72b7e1d8d4581b52a1016aaf86c62/results.json`. As versões de fixture 0.1.0/0.2.0 usam os mesmos bytes de app para testar o protocolo; não são releases publicadas. 187 testes unitários passaram, além da UI offline e dos smokes de mouse fonte/nativo. Capturas do app ficam junto ao log do smoke do bundle.

Pendências antes da distribuição pública: testar instalação **global elevada** em VM limpa com dois usuários (o smoke local usa escopo de teste sem elevação), validar atualização entre feeds realmente publicados, configurar assinatura Authenticode com certificado do editor. SHA256 verifica integridade; não equivale à assinatura de editor. Os workflows foram preparados, mas não executados/publicados nesta etapa. Sete erros preexistentes de mypy em `fisica.py` persistem com Pymunk 7.3.1; o código novo não acrescenta erros.
