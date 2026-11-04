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
- **Correção de apoio:** grounded exige contato real com normal voltada para baixo; proximidade de uma borda não cria apoio. A enumeração recorta trechos de prateleiras ocultos por janelas à frente e ignora desktop/taskbar. Ao perder apoio, a gravidade é reativada. O monitor de soltura é escolhido pelo corpo, e a câmera ortográfica mantém a projeção dos pés consistente com pixels da física; inclinação do corpo em voo não é aplicada ao caminhar no chão.
- **Animação procedural:** `animation.py` escolhe idle, walk, run, drag, fall, dance ou sleep e interpola as poses do `rig.py`; idle alterna entre cinco personalidades, a porta abre para a frente e os braços da dança ficam recolhidos.
- **Novas animações e conceito:** aceno, alongamento e espiada entram como variações ambiente e ações da bandeja; impacto tem recuperação própria. Hover usa área elíptica maior e acompanha os dois eixos, com pitch vertical corrigido após feedback visual. Pausa durante clique/arraste externo, digitação, cursores de edição/link e menus/controles nativos; retoma após 1 s sem atividade bloqueante. A detecção usa entrada/cursor/classes de janela, sem analisar semanticamente toda interface de terceiros.
- **Tentáculos 3D:** o modelo separado `assets/model/tentacle.gltf` é curto, grosso e facetado, com quatro ventosas hexagonais em relevo e 246 triângulos. Fonte da geometria em `tentacle_model.py`; exportação reproduzível com `tools/build_tentacle_model.py`, prévia isolada com `tools/preview_tentacle.py`. Validado pela Khronos com zero erros/avisos. Quatro instâncias recebem movimentos e extensão ligados à abertura da porta, recolhimento gradual e gotas rosas ocasionais. A porta aguarda o recolhimento para fechar. O GLTF original do Mário não foi modificado.
- **Barra de tarefas/encerramento:** ícone multirresolução `.ico` gerado da arte existente por `tools/build_icon.py`; aplicado a Qt, HWND e PyInstaller. `DesktopIntegration` habilita entrada na barra de tarefas e personaliza o menu do sistema (Shift+clique direito na barra); fechar pela barra ou bandeja inicia o hit stop branco e lançamento com três giros, encerrando após 1,35 s. Movimento de saída não altera a posição salva. `tools/smoke_effects.py` confere ícone, menu, poses, tentáculos, recolhimento/gota e fechamento real por WM_CLOSE em subprocesso.
- **Música:** `music.py` consulta a sessão GSMTC e, no modo loopback, estima nível e batidas por RMS em worker de fundo.
- **Bandeja e loop:** `window.py` implementa menu da bandeja, polling de eventos Qt, timers de animação/física e entrada de mouse.
- **Interação de mouse:** seleção por raio contra a malha animada, passagem de cliques nas áreas vazias e checagem da janela sob o cursor. Gestos iniciados fora não são capturados. Clique esquerdo reage, direito faz carinho, meio dá uma cutucada; hover acompanha o cursor e interação acorda o mascote. Arraste começa após 6 px, reposiciona o overlay, salva ao soltar e funciona sem física; `Esc`, ocultar ou abrir preferências interrompe o gesto. Preferências de reação/arraste aplicam na hora. HUD e JSONL incluem hover, arraste e posição local do mouse.
- **Entrada nativa:** os eventos `mouse1/2/3` do Panda3D complementam `GetAsyncKeyState`; captura de mouse mantém o gesto até a soltura. Foi verificado arraste mesmo forçando a consulta global a retornar zero. No bundle final, logs registraram down, drag_start, up e drag_end, com deslocamento real de 80 × 24 px.
- **Transparência:** a cor rosa após o pós-processamento é `RGB(214, 0, 214)` neste ambiente, diferente do magenta de clear color (`255, 0, 255`). O color key usa a cor final e é recalibrado depois do primeiro frame. Áreas vazias deixam cliques passar pelo próprio color key; o estilo global `WS_EX_TRANSPARENT`, que atrasava o primeiro clique no mascote, foi removido. O diagnóstico mostra o fundo rosa para facilitar inspeção.
- **Contorno configurável:** uma cópia da malha usa extrusão das normais e desenha as faces de trás; os mesmos nós do rig recebem a pose em cada frame. O shader descarta pixels com alpha abaixo de 0,05, respeitando as partes invisíveis da textura GLTF. Cor hexadecimal, espessura aproximada em pixels e liga/desliga estão no TOML e no diálogo; mudanças de cor/escala aplicam sem reinício. O teste de render confirma que trocar a cor/desligar o contorno alteram o frame e que o centro do rosto mantém a textura original.
- **Configurações e atalhos:** diálogo da bandeja salva em TOML; escala, música, cliques, z-order e atalhos aplicam na hora. Tamanho e física pedem reinício. Atalhos incluem visibilidade, configurações, convocação, diagnóstico e captura.
- **Build:** `build.ps1` recompila o bundle `onedir`, e o executável foi iniciado e conferido por captura de tela, com o modelo renderizado. A falha de importação de `QtCore` foi causada por `icuuc.dll` do Poppler incluída pelo PyInstaller a partir do PATH privado do Codex. Essa DLL não exporta `ucnv_open`, exigido pelo Qt; a ICU do Windows exporta. O filtro de PATH agora também exclui `OpenAI.CodexPrimaryRuntime`, além de `codex-runtimes`; o bundle reconstruído não inclui essa ICU incompatível.
- **Ferramentas de diagnóstico:** no runtime fonte, o HUD foi conferido visualmente; atalhos `Ctrl+Alt+F11`, `Ctrl+Alt+P` e `Ctrl+Alt+R`, eixos locais e globais, captura avulsa, gravação limitada a 300 frames e metadados JSONL funcionaram. Uma gravação curta salvou 102 PNGs e 102 linhas JSONL. A gravação é opt-in; imagens são gravadas em segundo plano em `%LOCALAPPDATA%/ArchVeketo/SeJogaDesktopCompanion/debug-captures/`.
- **Logs:** exceções não tratadas vão para `logs/companion.log`, com rotação e até três cópias antigas.
- **Gravação das preferências:** temporário exclusivo evita colisões com `.tmp` antigo; acesso negado no perfil padrão tenta `%APPDATA%/SeJogaDesktopCompanion/config.toml` e, no bundle, `user-data/config.toml` ao lado do executável se ambos os caminhos AppData forem bloqueados. O perfil salvo passa a ser usado nos próximos carregamentos. Exclua `user-data` de distribuições públicas. `SEJOGA_CONFIG_PATH` permite perfil isolado explícito. O teste do diálogo valida salvar, emissão das opções e leitura após fallback.
- **Ambiente Codex:** [AGENTS.md](../AGENTS.md), três skills locais validadas e Context7 remoto configurado; GitHub conectado. Veja [AMBIENTE_CODEX.md](AMBIENTE_CODEX.md) para limites da verificação e login OAuth pendente.

Essa verificação confirma o funcionamento no ambiente usado para o desenvolvimento. Não substitui teste em uma máquina limpa nem valida todas as interações do overlay.

### Parcial ou ainda pendente

- **Animação:** o controlador procedural cobre estados básicos, gestos, impacto e saída; ainda faltam duplo clique e clipes exportados do Blockbench. O olhar usa rotação da cabeça, sem alterar a textura dos olhos. O asset separado dos tentáculos pode ser refinado artisticamente no futuro; seus movimentos atuais são procedurais.
- **Arraste e física:** corpo e prateleiras agora usam coordenadas absolutas do desktop e o HWND acompanha o corpo. A soltura calcula velocidade recente, aplica `throw_multiplier` e limita a 3200 px/s; pausa antes de soltar elimina impulso antigo e cancelamento mantém o mascote flutuando. O voo fica na área útil do monitor de soltura, com suporte a origens negativas. Há queda, quique, repouso, pose de aterrissagem e persistência ao parar. Prateleiras movidas/fechadas são atualizadas; janelas minimizadas são excluídas. Colisão usa círculo, sem representar toda a silhueta; travessia entre monitores durante o voo, DPI misto e mudanças de resolução ainda exigem implementação/validação.
- **Configuração visual:** o diálogo e os atalhos editáveis estão integrados; atalhos são validados e reaplicados na hora. Se outro programa já usa uma combinação, o companion avisa. Alterar tamanho ou física exige reiniciar o app. O campo antigo `click_through_transparent` continua aceito no TOML por compatibilidade, mas o fundo fica transparente sempre que o diagnóstico está desligado.
- **Configuração persistente:** carregamento e gravação TOML estão em `config.py`; não há hot-reload de um arquivo TOML alterado externamente.
- **Música:** o módulo está integrado, mas ainda precisa ser validado com sessões reais e diferentes dispositivos. A arte do álbum ainda não é lida como imagem; a detecção de beat é inicial e precisa ser ajustada. `react_to_beat = false` desliga a dança musical; `dance_chance` define a probabilidade de dançar em cada intervalo de oito segundos, sem sorteio por frame. Batidas detectadas reforçam a intensidade na entrada do pulso. Parar a música interrompe a dança; arraste e queda mantêm prioridade. Testes usam snapshots simulados; falta validação auditiva/visual com música real.
- **Distribuição:** não há instalador Inno Setup, assinatura ou teste em instalação limpa.
- **Diagnóstico:** a captura registra o fundo magenta usado pelo chroma key do overlay. O HUD foi conferido no runtime fonte. No executável corrigido, o atalho de gravação chegou ao handler, mas a criação da pasta em AppData falhou com `PermissionError` no contexto de execução do agente; o arquivo de log também não pôde ser aberto. A renderização do executável foi conferida por captura externa. Revalidar logs e gravação ao abrir pela sessão normal do usuário; o perfil existente também mantém `Ctrl+Alt+D`, indisponível nesta sessão, apesar do novo padrão `Ctrl+Alt+F11`.
- **Logs:** mecanismo de exceções não tratadas e rotação implementado; falta avaliar os logs após uma sessão prolongada.

O modo padrão `media_session` lê metadados sem capturar áudio. Para usar loopback, configure `music.source = "loopback"` e instale o extra `music-loopback`; essa opção é separada do modo padrão.

## Próximos passos priorizados

### 0. Continuação da interação — refinamento da física

- Validar manualmente em múltiplos monitores e DPI misto; implementar travessia entre monitores durante o voo e atualização de limites após mudanças de resolução.
- Refinar corpo circular para evitar que cabeça/braços ultrapassem bordas; avaliar apoio que acompanhe uma janela sendo arrastada (atualmente o mascote perde o apoio e cai).
- Refinar apoio que acompanhe janelas em movimento e testar mais casos de janelas parcialmente transparentes/recortadas; a oclusão atual usa retângulos DWM e ordem Z.
- Testar hit-test com texturas transparentes, escalas extremas, janelas sobrepostas e DPI distintos. O teste atual usa geometria, não alpha por pixel.

### 1. Música — validar e refinar `src/sejoga/music.py`

- Validar título/artista/álbum e status com sessões GSMTC reais.
- Instalar o extra `music-loopback` e validar captura WASAPI em diferentes saídas de áudio.
- Afinar o detector RMS/onset com diferentes gêneros e volumes; medir custo antes de considerar `librosa`.
- Ler e expor a arte do álbum quando houver uma interface que a apresente.
- Ajustar a intensidade de dança e os gatilhos de beat com base na captura real.
- Validar `react_to_beat` e `dance_chance`, já ligados ao controlador, com dados reais do listener.

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

Última etapa visual/física (04/11/2026): 47 testes passaram, além dos smokes de mouse/física e efeitos. O modelo separado do tentáculo passou no glTF Validator da Khronos com zero erros e zero avisos. No executável, ícone e estilo de barra de tarefas foram conferidos; o hover ampliado parou sobre um controle Edit de outra janela e retomou após voltar à área ociosa. Após arremesso, a captura registrou grounded=true, velocidade (0, 0) e centro em y=1398,1 na área útil de 1440 px. O comando nativo SC_CLOSE completou a saída animada e encerrou o processo. A tentativa de medir um arraste exato sofreu interferência do cursor em uso; os logs confirmaram down/drag/up e o repouso foi verificado separadamente.

Validação da etapa de mouse: `python -m pytest` e `python tools/smoke_mouse.py` (repetir com `--physics`). O smoke usa perfil temporário, uma janela Panda3D real e entradas simuladas no polling, sem movimentar o cursor do usuário; verifica picking, estilos de click-through, reações, deslocamento real do HWND, persistência e rejeição de gestos externos. PNG e JSONL são gravados no perfil temporário indicado ao terminar. Isso não substitui validação manual de cliques rápidos e múltiplos monitores.

Resultado em 2026-11-04: 25 testes passaram; smoke passou com física ligada e desligada. O bundle foi recompilado e iniciado; um arraste com eventos nativos do Windows moveu a janela de `(0, 0)` para `(80, 40)`, com `drag_start`/`drag_end` no log e sem erro de QtCore. A restauração da posição foi corrigida sincronizando a origem solicitada ao Panda3D antes do primeiro frame.

Etapa seguinte de física: 32 testes passaram, incluindo arremesso, pausa/cancelamento, limite de velocidade, origem negativa, chão, passagem por baixo de prateleiras e atualização/remoção de apoios. O smoke foi ampliado para simular seis segundos de arremesso com Pymunk real, movimento real do HWND e posição final persistida. Foi necessário restaurar massa/momento após trocar KINEMATIC por DYNAMIC no Pymunk 7; sem isso o primeiro passo após a soltura produzia NaN. O repouso também deixou de chamar `Body.sleep()` sem habilitar sleeping no espaço.

O executável dessa etapa foi recompilado e testado com eventos nativos de mouse: houve deslocamento após a soltura, impactos registrados e repouso estável por duas leituras separadas de 700 ms, sem exceção. O ajuste inicial de propriedades também passou a preservar o z-order no Panda3D; o smoke verifica que a janela continua topmost após os primeiros frames.

Correções seguintes (04/11/2026): 36 testes passaram; smokes verificaram transparência normal, rosa no diagnóstico, contorno configurável respeitando alpha e entrada nativa. O botão Salvar do bundle foi acionado, gerou perfil portátil quando ambos os diretórios AppData recusaram escrita e fechou o diálogo. Após reiniciar, perfil e log portátil foram recuperados. Fechar a janela com física ativa encerrou normalmente, sem erro de HWND 1400. O build preserva o perfil portátil em `.local/user-data` antes de substituir a pasta do bundle e o restaura depois; não distribuir essas preferências pessoais.

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
