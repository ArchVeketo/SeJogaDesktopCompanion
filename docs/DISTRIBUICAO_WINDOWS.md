# Distribuição Windows: instalador fixo e atualizações dinâmicas

Implementação isolada na branch `codex/installer-updater`. Não depende dos assets experimentais da outra branch.

## Contrato de distribuição

O instalador é um **bootstrapper online pequeno e estável**, separado das versões do aplicativo. Ao instalar, consulta o feed do canal e baixa o runtime atual. O mesmo arquivo de setup serve para instalações futuras e reparos com a versão mais recente. Exige internet na instalação inicial.

Uma mudança comum no aplicativo gera apenas **ZIP do runtime + SHA256 + channel.json**. Não recompila nem redistribui o instalador. O launcher/updater nativo fica fora do runtime e substitui somente `runtime/current`. Recompilar o bootstrapper só é necessário quando sua própria infraestrutura/protocolo mudar.

| Canal | Pasta global padrão | Feed estável no GitHub |
|---|---|---|
| release | `Program Files/SeJogaCompanion` | `updates-release/channel.json` |
| prerelease | `Program Files/SeJogaCompanion-prerelease` | `updates-prerelease/channel.json` |
| nightly | `Program Files/SeJogaCompanion-nightly` | `updates-nightly/channel.json` |

Os feeds são assets das releases de mesmo nome no repositório `ArchVeketo/SeJogaDesktopCompanion`. AppIds, atalhos, desinstaladores e namespaces de perfil são separados por canal. Instalação para todos os usuários, com elevação do Windows e atalhos globais. Python não é necessário no PC de destino; alvo Windows 10 1809+/11 x64 com .NET Framework do sistema.

Configurações pertencem a cada usuário no AppData. O canal estável preserva o caminho existente; os outros usam sufixo. Não embutir perfis do desenvolvedor. Atualizações e desinstalação não apagam configurações. `SEJOGA_CONFIG_PATH` continua disponível para testes isolados.

## Fluxo de atualização

Na bandeja, **Verificar atualizações…** consulta o feed do canal em uma thread e oferece a atualização. A aplicação não fecha ao abrir o updater. O launcher original inicia o agente elevado; cancelar UAC mantém o mascote aberto.

O agente baixa o pacote em uma pasta de preparação, valida tamanho/SHA256/canal/arquitetura/versão e extrai com limites de tamanho e proteção contra caminhos escapando do ZIP. Produção aceita somente os servidores HTTPS do GitHub definidos no código. Não aceita feed arbitrário por argumento ou ambiente.

Somente após preparar tudo, usa Restart Manager para solicitar encerramento normal. Renomeia `current` para `previous`, move a versão preparada para `current` e atualiza a versão exibida no registro de desinstalação. O launcher original reabre o mascote com o token do usuário. Se a troca falhar, restaura `previous`; se a energia cair entre renomeações, a próxima tentativa restaura `previous` antes de consultar a rede. A versão anterior permanece até a próxima atualização.

Versões antigas/build IDs regressivos são rejeitados. Não há atualização diferencial: cada atualização baixa o runtime completo. A busca no menu é manual; não há atualização silenciosa em segundo plano. O protocolo v1 mantém o agente nativo estável, que não é substituído pelo ZIP do aplicativo.

## Gerar os instaladores (somente infraestrutura)

Requer Inno Setup 6/7 e compilador .NET Framework do Windows. Não exige bundle PyInstaller.

```powershell
.\tools\build-installer.ps1 -Channel release
.\tools\build-installer.ps1 -Channel prerelease
.\tools\build-installer.ps1 -Channel nightly
```

Saídas fixas `dist/installer/SeJogaCompanion-Setup-<canal>-windows-x64.exe` e `.sha256`. A versão do bootstrapper é independente: `-BootstrapperVersion 1.0.0`. `-Compiler` permite selecionar ISCC.

## Publicar uma versão do aplicativo

```powershell
python -m pytest
.\build.ps1
python tools/build-update.py --channel release --version 0.1.0
python tools/build-update.py --channel prerelease --version 0.2.0rc1
python tools/build-update.py --channel nightly
```

Saídas em `dist/updates/<canal>`: ZIP com metadados, checksum e manifesto. Exclui perfis `user-data`, logs e fontes de arte. Os padrões de versão vêm de `pyproject.toml`, com `rc1` ou `.dev<UTC>` conforme o canal. Release/prerelease precisam de versão nova para cada publicação; nightly usa timestamp. `build_id` também é monotônico.

O workflow **Windows runtime updates** roda testes/build/empacotamento. Push na main publica nightly; tags `v*` publicam release/prerelease conforme a versão; execução manual permite selecionar canal/versão, com publicação desmarcada por padrão. A publicação verifica regressão, envia ZIP/checksum primeiro e só então avança `channel.json`. Falha antes disso mantém o feed antigo. Não chama Inno Setup.

O workflow separado **Windows stable bootstrapper** é manual e constrói os três instaladores. Publicação exige opt-in e cria `installer-v<versão>`, independente dos feeds de runtime. Não executar esses workflows de publicação para testar esta branch.

Antes de disponibilizar um setup, publicar o primeiro feed compatível do canal. Sem feed, o setup aborta a preparação com mensagem; não contém um aplicativo offline de reserva. Ainda não há feed público publicado por esta implementação.

## Validação e limites

`python tools/smoke-distribution.py` (ou `tools/smoke-installer.ps1`) usa servidor loopback, AppId de teste e perfil isolado em Documents público. O modo de teste nunca pode atualizar Program Files. Instala o bundle real, troca entre duas versões de fixture com **o mesmo setup e o mesmo launcher**, verifica fechamento/reabertura, rejeição de corrupção/ZIP traversal/downgrade, recuperação offline de troca interrompida, reparo pelo mesmo setup, quatro danças/bandeja e desinstalação preservando perfil.

Evidência local de 05/11/2026: `C:/Users/Public/Documents/SeJogaDistributionSmoke/e1c72b7e1d8d4581b52a1016aaf86c62/results.json`. As versões de fixture 0.1.0/0.2.0 usam os mesmos bytes de app para testar o protocolo; não são releases publicadas. 187 testes unitários passaram, além da UI offline e dos smokes de mouse fonte/nativo. Capturas do app ficam junto ao log do smoke do bundle.

Pendências antes da distribuição pública: testar instalação **global elevada** em VM limpa com dois usuários (o smoke local usa escopo de teste sem elevação), validar atualização entre feeds realmente publicados, configurar assinatura Authenticode com certificado do editor. SHA256 verifica integridade; não equivale à assinatura de editor. Os workflows foram preparados, mas não executados/publicados nesta etapa. Sete erros preexistentes de mypy em `physics.py` persistem com Pymunk 7.3.1; o código novo não acrescenta erros.
