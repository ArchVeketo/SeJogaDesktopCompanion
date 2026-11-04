# SeJogaDesktopCompanion — Status atual e próximos passos

**Atualizado:** 2026-11-04  
**Base de trabalho:** commits `363276c` e seguintes.

Este é o roadmap canônico do projeto. As listas de próximos passos nos documentos de pesquisa e arquitetura foram escritas antes de várias etapas serem implementadas; consulte esta página para o estado atual.

## Status atual

### Implementado e verificado neste ambiente

- **Overlay e renderização:** `OverlayApp` cria a janela Panda3D, aplica estilos Win32 e carrega o modelo GLTF/GLB.
- **Resolução de assets:** `assets.py` resolve os caminhos em desenvolvimento e no bundle PyInstaller `onedir`.
- **Escala/enquadramento:** `window.scale` agora multiplica o ajuste automático do modelo ao overlay; o render usa os bounds reais do Panda3D e posiciona os pés em relação ao raio da física.
- **Física de tela:** `physics.py` integra Pymunk, arraste/arremesso e detecção de janelas/prateleiras.
- **Animação procedural:** `animation.py` escolhe idle, walk, run, drag, fall, dance ou sleep e interpola as poses do `rig.py`; idle alterna entre cinco personalidades, a porta abre para a frente e os braços da dança ficam recolhidos.
- **Música:** `music.py` consulta a sessão GSMTC e, no modo loopback, estima nível e batidas por RMS em worker de fundo.
- **Bandeja e loop:** `window.py` implementa menu da bandeja, polling de eventos Qt, timers de animação/física e entrada de mouse.
- **Configurações e atalhos:** diálogo da bandeja salva em TOML; escala, música, cliques e z-order aplicam na hora. Tamanho e física pedem reinício. Atalhos globais mostram/ocultam, abrem as configurações e chamam o mascote.
- **Build:** há configuração para o bundle PyInstaller `onedir` em `build.ps1`. O executável recém-compilado foi iniciado neste ambiente e permaneceu em execução durante a verificação.

Essa verificação confirma o funcionamento no ambiente usado para o desenvolvimento. Não substitui teste em uma máquina limpa nem valida todas as interações do overlay.

### Parcial ou ainda pendente

- **Animação:** o controlador procedural cobre os estados básicos; ainda faltam reações acionadas pela música, mais poses/eventos e clipes exportados do Blockbench.
- **Configuração visual:** o diálogo e os atalhos principais estão integrados; alterar tamanho ou física exige reiniciar o app.
- **Configuração persistente:** carregamento e gravação TOML estão em `config.py`; não há hot-reload de um arquivo TOML alterado externamente.
- **Música:** o módulo está integrado, mas ainda precisa ser validado com sessões reais e diferentes dispositivos. A arte do álbum ainda não é lida como imagem; a detecção de beat é inicial e precisa ser ajustada.
- **Distribuição:** não há instalador Inno Setup, assinatura ou teste em instalação limpa.

O modo padrão `media_session` lê metadados sem capturar áudio. Para usar loopback, configure `music.source = "loopback"` e instale o extra `music-loopback`; essa opção é separada do modo padrão.

## Próximos passos priorizados

### 1. Ferramentas de diagnóstico — criar HUD e captura

- Mostrar FPS, estado/persona, posição e velocidade da física, dimensões do modelo e parâmetros de câmera.
- Desenhar eixos locais do modelo e eixos globais da cena para facilitar o ajuste do rig.
- Capturar screenshot sob demanda e oferecer gravação opcional de frames com metadados, sem gravar continuamente por padrão.
- Registrar exceções e eventos relevantes em log com rotação ou limite de tamanho.

### 2. Música — validar e refinar `src/sejoga/music.py`

- Validar título/artista/álbum e status com sessões GSMTC reais.
- Instalar o extra `music-loopback` e validar captura WASAPI em diferentes saídas de áudio.
- Afinar o detector RMS/onset com diferentes gêneros e volumes; medir custo antes de considerar `librosa`.
- Ler e expor a arte do álbum quando houver uma interface que a apresente.
- Ajustar a intensidade de dança e os gatilhos de beat com base na captura real.

### 3. Configurações e controles — `src/sejoga/ui.py`

- Permitir edição das hotkeys pelo diálogo; hoje elas são configuráveis pelo TOML.
- Aplicar tamanho e ativação de física sem reiniciar, se a integração de janela e limites ficar estável.
- Avaliar hot-reload de TOML com `QFileSystemWatcher`.

### 4. Animações — expansão de `animation.py` e Blockbench

- Refinar o controlador e integrar eventos de clique/colisão/beat às transições já implementadas.
- Criar/exportar clipes `idle`, `walk`, `run`, `jump`, `throw`, `dance`, `hit`, `sleep`, `wake`, `cling` e `peek` no Blockbench.
- Ligar os estados a eventos de física, mouse e música.

### 5. Build portável e instalador

- Remover caminhos absolutos da instalação Python do ambiente atual em `build.ps1` e `SeJogaCompanion.spec`.
- Manter um único fluxo de build documentado e conferir que o `.spec` inclua todos os dados e plugins necessários ao bundle.
- Validar o pacote numa instalação limpa do Windows.
- Criar instalador Inno Setup com atalho, opção de inicialização automática e desinstalação limpa.
- Tratar assinatura de código como etapa futura, quando houver certificado.

## Build usado na validação atual

Execute no PowerShell:

```powershell
.\build.ps1
```

O script e o entry point `run_companion.py` foram incluídos no commit `96fea79`. A compilação verificada usou uma invocação PyInstaller equivalente à configuração do script. O executável fica dentro da pasta `dist\\SeJogaCompanion`; distribua a pasta completa do bundle `onedir`, não apenas o `.exe`.

## Notas de precisão sobre o empacotamento

- `SeJogaCompanion.spec` contém os três display drivers Panda3D e os hidden imports relevantes, mas atualmente referencia caminhos absolutos da instalação Python local.
- A configuração `datas` do `.spec` inclui `assets`; não há uma entrada explícita para `panda3d_gltf-1.3.0.dist-info` neste arquivo.
- O renderer carrega o modelo com `gltf.load_model(...)`; não há chamada `getModelPath().appendDirectory(model_dir())` no código atual.
- O fluxo confirmado para o build recente foi `build.ps1`. As afirmações acima devem ser revisitadas ao tornar o `.spec` o fluxo portátil e canônico.

## Dependências opcionais

Os extras do `pyproject.toml` incluem `panda3d`, `windows`, `tray`, `music`, `music-loopback` e `music-analysis`. O nome do extra Win32 é `windows` (não `win32`).
