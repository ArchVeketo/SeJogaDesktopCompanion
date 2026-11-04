# SeJogaDesktopCompanion — Status atual e próximos passos

**Atualizado:** 2026-11-04  
**Base de trabalho:** commits `363276c`, `039d97a` e seguintes.

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
- **Interação de mouse:** seleção por raio contra a malha animada, passagem de cliques nas áreas vazias e checagem da janela sob o cursor. Gestos iniciados fora não são capturados. Clique esquerdo reage, direito faz carinho, meio dá uma cutucada; hover acompanha o cursor e interação acorda o mascote. Arraste começa após 6 px, reposiciona o overlay, salva ao soltar e funciona sem física; `Esc`, ocultar ou abrir preferências interrompe o gesto. Preferências de reação/arraste aplicam na hora. HUD e JSONL incluem hover, arraste e posição local do mouse.
- **Configurações e atalhos:** diálogo da bandeja salva em TOML; escala, música, cliques, z-order e atalhos aplicam na hora. Tamanho e física pedem reinício. Atalhos incluem visibilidade, configurações, convocação, diagnóstico e captura.
- **Build:** `build.ps1` recompila o bundle `onedir`, e o executável foi iniciado e conferido por captura de tela, com o modelo renderizado. A falha de importação de `QtCore` foi causada por `icuuc.dll` do Poppler incluída pelo PyInstaller a partir do PATH privado do Codex. Essa DLL não exporta `ucnv_open`, exigido pelo Qt; a ICU do Windows exporta. O filtro de PATH agora também exclui `OpenAI.CodexPrimaryRuntime`, além de `codex-runtimes`; o bundle reconstruído não inclui essa ICU incompatível.
- **Ferramentas de diagnóstico:** no runtime fonte, o HUD foi conferido visualmente; atalhos `Ctrl+Alt+F11`, `Ctrl+Alt+P` e `Ctrl+Alt+R`, eixos locais e globais, captura avulsa, gravação limitada a 300 frames e metadados JSONL funcionaram. Uma gravação curta salvou 102 PNGs e 102 linhas JSONL. A gravação é opt-in; imagens são gravadas em segundo plano em `%LOCALAPPDATA%/ArchVeketo/SeJogaDesktopCompanion/debug-captures/`.
- **Logs:** exceções não tratadas vão para `logs/companion.log`, com rotação e até três cópias antigas.

Essa verificação confirma o funcionamento no ambiente usado para o desenvolvimento. Não substitui teste em uma máquina limpa nem valida todas as interações do overlay.

### Parcial ou ainda pendente

- **Animação:** o controlador procedural cobre os estados básicos e reações de mouse com transições/cooldowns; ainda faltam duplo clique, reações acionadas pela música/colisões e clipes exportados do Blockbench. As reações implementadas usam rotações, sem squash/stretch ou alteração da textura dos olhos.
- **Arraste e física:** corpo e prateleiras agora usam coordenadas absolutas do desktop e o HWND acompanha o corpo. A soltura calcula velocidade recente, aplica `throw_multiplier` e limita a 3200 px/s; pausa antes de soltar elimina impulso antigo e cancelamento mantém o mascote flutuando. O voo fica na área útil do monitor de soltura, com suporte a origens negativas. Há queda, quique, repouso, pose de aterrissagem e persistência ao parar. Prateleiras movidas/fechadas são atualizadas; janelas minimizadas são excluídas. Colisão usa círculo, sem representar toda a silhueta; travessia entre monitores durante o voo, DPI misto e mudanças de resolução ainda exigem implementação/validação.
- **Configuração visual:** o diálogo e os atalhos editáveis estão integrados; atalhos são validados e reaplicados na hora. Se outro programa já usa uma combinação, o companion avisa. Alterar tamanho ou física exige reiniciar o app.
- **Configuração persistente:** carregamento e gravação TOML estão em `config.py`; não há hot-reload de um arquivo TOML alterado externamente.
- **Música:** o módulo está integrado, mas ainda precisa ser validado com sessões reais e diferentes dispositivos. A arte do álbum ainda não é lida como imagem; a detecção de beat é inicial e precisa ser ajustada. `react_to_beat` e `dance_chance` existem na configuração, mas ainda não controlam as animações; a semântica deve ser definida após observar sessões reais.
- **Distribuição:** não há instalador Inno Setup, assinatura ou teste em instalação limpa.
- **Diagnóstico:** a captura registra o fundo magenta usado pelo chroma key do overlay. O HUD foi conferido no runtime fonte. No executável corrigido, o atalho de gravação chegou ao handler, mas a criação da pasta em AppData falhou com `PermissionError` no contexto de execução do agente; o arquivo de log também não pôde ser aberto. A renderização do executável foi conferida por captura externa. Revalidar logs e gravação ao abrir pela sessão normal do usuário; o perfil existente também mantém `Ctrl+Alt+D`, indisponível nesta sessão, apesar do novo padrão `Ctrl+Alt+F11`.
- **Logs:** mecanismo de exceções não tratadas e rotação implementado; falta avaliar os logs após uma sessão prolongada.

O modo padrão `media_session` lê metadados sem capturar áudio. Para usar loopback, configure `music.source = "loopback"` e instale o extra `music-loopback`; essa opção é separada do modo padrão.

## Próximos passos priorizados

### 0. Continuação da interação — refinamento da física

- Validar manualmente em múltiplos monitores e DPI misto; implementar travessia entre monitores durante o voo e atualização de limites após mudanças de resolução.
- Refinar corpo circular para evitar que cabeça/braços ultrapassem bordas; avaliar apoio que acompanhe uma janela sendo arrastada (atualmente o mascote perde o apoio e cai).
- Refinar poses de impacto/aterrissagem e comportamento de prateleiras sobrepostas/ocultas.
- Testar hit-test com texturas transparentes, escalas extremas, janelas sobrepostas e DPI distintos. O teste atual usa geometria, não alpha por pixel.

### 1. Música — validar e refinar `src/sejoga/music.py`

- Validar título/artista/álbum e status com sessões GSMTC reais.
- Instalar o extra `music-loopback` e validar captura WASAPI em diferentes saídas de áudio.
- Afinar o detector RMS/onset com diferentes gêneros e volumes; medir custo antes de considerar `librosa`.
- Ler e expor a arte do álbum quando houver uma interface que a apresente.
- Ajustar a intensidade de dança e os gatilhos de beat com base na captura real.
- Definir e ligar `react_to_beat` e `dance_chance` ao controlador de animação após verificar os dados reais do listener.

### 2. Configurações e controles — `src/sejoga/ui.py`

- Aplicar tamanho e ativação de física sem reiniciar, se a integração de janela e limites ficar estável.
- Avaliar hot-reload de TOML com `QFileSystemWatcher`.

### 3. Animações — expansão de `animation.py` e Blockbench

- Refinar o controlador e integrar eventos de clique/colisão/beat às transições já implementadas.
- Criar/exportar clipes `idle`, `walk`, `run`, `jump`, `throw`, `dance`, `hit`, `sleep`, `wake`, `cling` e `peek` no Blockbench.
- Ligar os estados a eventos de física, mouse e música.

### 4. Build portável e instalador

- Remover caminhos absolutos da instalação Python do ambiente atual em `build.ps1` e `SeJogaCompanion.spec`.
- Manter um único fluxo de build documentado e conferir que o `.spec` inclua todos os dados e plugins necessários ao bundle.
- Validar o pacote numa instalação limpa do Windows.
- Criar instalador Inno Setup com atalho, opção de inicialização automática e desinstalação limpa.
- Tratar assinatura de código como etapa futura, quando houver certificado.

## Build usado na validação atual

Validação da etapa de mouse: `python -m pytest` e `python tools/smoke_mouse.py` (repetir com `--physics`). O smoke usa perfil temporário, uma janela Panda3D real e entradas simuladas no polling, sem movimentar o cursor do usuário; verifica picking, estilos de click-through, reações, deslocamento real do HWND, persistência e rejeição de gestos externos. PNG e JSONL são gravados no perfil temporário indicado ao terminar. Isso não substitui validação manual de cliques rápidos e múltiplos monitores.

Resultado em 2026-11-04: 25 testes passaram; smoke passou com física ligada e desligada. O bundle foi recompilado e iniciado; um arraste com eventos nativos do Windows moveu a janela de `(0, 0)` para `(80, 40)`, com `drag_start`/`drag_end` no log e sem erro de QtCore. A restauração da posição foi corrigida sincronizando a origem solicitada ao Panda3D antes do primeiro frame.

Etapa seguinte de física: 32 testes passaram, incluindo arremesso, pausa/cancelamento, limite de velocidade, origem negativa, chão, passagem por baixo de prateleiras e atualização/remoção de apoios. O smoke foi ampliado para simular seis segundos de arremesso com Pymunk real, movimento real do HWND e posição final persistida. Foi necessário restaurar massa/momento após trocar KINEMATIC por DYNAMIC no Pymunk 7; sem isso o primeiro passo após a soltura produzia NaN. O repouso também deixou de chamar `Body.sleep()` sem habilitar sleeping no espaço.

O executável dessa etapa foi recompilado e testado com eventos nativos de mouse: houve deslocamento após a soltura, impactos registrados e repouso estável por duas leituras separadas de 700 ms, sem exceção. O ajuste inicial de propriedades também passou a preservar o z-order no Panda3D; o smoke verifica que a janela continua topmost após os primeiros frames.

Execute no PowerShell:

```powershell
.\build.ps1
```

O script e o entry point `run_companion.py` foram incluídos no commit `96fea79`. A compilação mais recente foi executada pelo próprio `build.ps1`, após corrigir o filtro do PATH, e o executável resultante abriu a janela OpenGL e renderizou o modelo. O executável fica dentro da pasta `dist\\SeJogaCompanion`; distribua a pasta completa do bundle `onedir`, não apenas o `.exe`.

## Notas de precisão sobre o empacotamento

- `SeJogaCompanion.spec` contém os três display drivers Panda3D e os hidden imports relevantes, mas atualmente referencia caminhos absolutos da instalação Python local.
- A configuração `datas` do `.spec` inclui `assets`; não há uma entrada explícita para `panda3d_gltf-1.3.0.dist-info` neste arquivo.
- O renderer carrega o modelo com `gltf.load_model(...)`; não há chamada `getModelPath().appendDirectory(model_dir())` no código atual.
- O fluxo confirmado para o build recente foi `build.ps1`. As afirmações acima devem ser revisitadas ao tornar o `.spec` o fluxo portátil e canônico.

## Dependências opcionais

Os extras do `pyproject.toml` incluem `panda3d`, `windows`, `tray`, `music`, `music-loopback` e `music-analysis`. O nome do extra Win32 é `windows` (não `win32`).
