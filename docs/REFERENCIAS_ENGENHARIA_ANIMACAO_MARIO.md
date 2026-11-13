# Referências de engenharia e animação para o Mário

**13/11/2026 · pesquisa técnica · complemento ao [manual de engenharia](MANUAL_ENGENHARIA_ANIMACAO_MARIO.md)**

As escolhas abaixo são inferências para este projeto, a partir dos trabalhos originais, documentações e repositórios ligados em cada item. O critério é o problema resolvido no Mário, a aderência ao rig rígido e o custo de operar em um executável Windows. A pesquisa é documental. Cada integração citada exige uma prova local. A capacidade descrita por um fornecedor se refere à biblioteca ou engine daquele fornecedor.

## 1. Técnica de animação e jogos de referência

| Fonte primária | O que estudar | Aplicação no Mário e prova |
| --- | --- | --- |
| [John Lasseter, princípios tradicionais em 3D](https://www.cs.cmu.edu/afs/cs/academic/class/15462-f13/www/lec_slides/Lesseter.pdf) | Tradução de timing, espaçamento, trajetória e pose em animação computadorizada. | Fazer uma folha de contato e um take da mesma ação. Comparar a leitura em miniatura com o gesto temporizado em execução. |
| [Rain World, Jakobsson e Therrien, GDC](https://www.gdcvault.com/play/1023475/Animation-Bootcamp-Rainworld-Animation) e [entrevista técnica com Jakobsson](https://unity.com/blog/exploring-procedural-design-rain-world) | Resposta à situação e integração entre corpo, apresentação e apêndices. | Dar identidade ao alvo, variar atenção por contexto e tornar tentáculos capazes de buscar e recuar. Provar com obstáculo e interrupção. A atuação do gabinete vem das poses autorais. |
| [SlugcatPet v1.3.3](https://github.com/lingxiaojun/slugcatpet/tree/v1.3.3) | FSM, retenção do alvo, mudança de estado condicionada a apoio e fase baseada em deslocamento. | Estudar uma chegada com estabilidade antes de iniciar nova ação. O [estudo histórico local](ESTUDO_PROCEDURAL_RAIN_WORLD.md) aponta as classes de referência. |
| [Shijima-Qt](https://github.com/pixelomer/Shijima-Qt) | Mascote de desktop com Qt e comportamentos. | Estudar ciclo de vida e entrada. Comparar arquitetura de desktop, respeitando as diferenças de plataforma, sprites e picking 3D. |
| [hatpet](https://github.com/amareshhebbar/hatpet) | Mascote Godot com janela transparente e arraste em Linux. | Referência de interação para uma prova visual. WGL, color key, HWND e DPI misto do Windows exigem evidência própria. |
| [Witkin e Popović, Motion Warping](https://publications.ri.cmu.edu/motion-warping) | Adaptar movimento a restrições e preservar características do original. | Alinhar um contato da mão ao tampo e preservar a pose-chave de maior apelo. Medir penetração, alcance e direção da palma. |
| [Bollo, Inertialization, GDC](https://www.gdcvault.com/play/1025165/Inertialization-High-Performance-Animation-Transitions) | Offset de transição e preservação de continuidade com custo previsível. | Interromper aceno com arraste e comparar o primeiro frame. Adaptar a ideia com curva finita e contatos explícitos. |
| [Aristidou e Lasenby, FABRIK](https://www.andreasaristidou.com/publications/papers/FABRIK.pdf) | Cadeias iterativas com ajuste de posições ao longo de segmentos. | Prototipar alcance da ponta de um tentáculo. Comparar com a restrição atual para alvos próximos, inalcançáveis e degenerações. O solver analítico local é o ponto de partida para cotovelo e joelho. |
| [Holden, Motion Matching, código de referência](https://github.com/orangeduck/Motion-Matching) e [artigo Learned Motion Matching](https://staticctf.ubisoft.com/J3yLr34U2pZ2Ieem48Dwy9uqj5PNUQTn/2EVXGPN6ynTrrJaaAUHmZS/060e223cce6a84e47e925105cac5e17f/Learned_Motion_Matching.pdf) | Comparar trajetória futura e características da pose para selecionar amostras. | Usar a noção de proximidade de fase para escolher uma transição entre poucas frases. Banco de mocap, busca e aprendizado ganham valor se houver volume suficiente de clipes compatíveis. |
| [Godot AnimationTree](https://docs.godotengine.org/en/stable/tutorials/animation/animation_tree.html) | Máscaras, mistura, máquinas de estados e root motion. | Comparar semântica de mistura com `LayerStack`. Uma cena Godot pode servir para visualizar glTF e contatos de autoria. |
| [Unity Animation Rigging, Two Bone IK](https://docs.unity3d.com/Packages/com.unity.animation.rigging@1.2/manual/constraints/TwoBoneIKConstraint.html) | Separar alvo de extremidade, polo e peso. | Usar como referência conceitual para joelho e cotovelo. Demonstrar a inversão em posição impossível e como o polo estabiliza a dobra. |
| [Unreal Motion Warping](https://dev.epicgames.com/documentation/unreal-engine/motion-warping-in-unreal-engine) e [Motion Matching](https://dev.epicgames.com/documentation/unreal-engine/motion-matching-in-unreal-engine) | Janelas de adaptação e depuração da seleção de pose. | Marcar trechos em que a pose pode se ajustar ao palco e onde deve proteger a leitura. Custo de engine, empacotamento e integração com overlay torna uma migração um projeto próprio. |

**Estudo visual de dança.** A [investigação histórica de Bomb Rush Cyberfunk](GUIA_ANIMACAO_DANCA.md) serve para localizar frases e entender a observação anterior sobre seleção de clipes. Para cada referência visual de BRC, Hi-Fi Rush, Lethal League e Persona, coletar clipe de referência em material autorizado e anotar contato, acento, silhueta, duração de hold, contrapeso e final. Recriar com o volume e os apoios do Mário. Arquivos extraídos de jogos ou datasets entram em um protótipo distribuível só com proveniência e termos de uso examinados.

## 2. Ferramentas de autoria e dados

| Candidato | Papel | Primeiro experimento e critério |
| --- | --- | --- |
| [Blockbench](https://github.com/JannisX11/blockbench) | Fonte atual do rig, edição de pivôs e poses em nós rígidos. | Exportar um aceno de uma cadeia e comparar nomes, hierarquia, repouso e eixos com a fonte. |
| [Blender glTF](https://docs.blender.org/manual/en/latest/addons/import_export/scene_gltf2.html) | Autoria auxiliar, edição de curvas, limpeza de referência, retarget e exportação. | Usar uma cópia do rig, testar ações e baking e comparar a pose exportada. Preservar texturas e pivôs da fonte. |
| [Khronos glTF](https://registry.khronos.org/glTF/) e [glTF Validator](https://github.com/KhronosGroup/glTF-Validator) | Contrato de formato e verificação estrutural. | Validar um GLTF e um GLB e guardar o relatório. Acrescentar verificação do significado dos nomes e do repouso. |
| [glTF Transform](https://github.com/donmccurdy/glTF-Transform) | Ferramentas JavaScript/TypeScript e Node para inspeção e conversão de assets. | Rodar offline em cópia. Comparar hierarquia, pivôs, canais, alpha e UV. Transforms que simplificam ou deduplicam nós precisam respeitar as identidades do rig. |
| [panda3d-gltf](https://github.com/Moguri/panda3d-gltf) | Loader atual do grafo. | Verificar carregamento de uma trilha de nó rígido com a versão instalada, uma tradução e uma rotação conhecidas. Testar no caminho do renderer. |
| [panda3d-simplepbr](https://github.com/Moguri/panda3d-simplepbr) | Materiais e pós-processamento no caminho atual. | Comparar cor de fundo pós-tonemap, alpha e legibilidade da textura antes e depois de alterar material. |
| [Ozz Animation](https://github.com/guillaumeblanc/ozz-animation) | Runtime e ferramentas C++ para animação esquelética. | Ler amostragem, blending e conversão local→modelo. Uma prova de biblioteca requer mapear nós rígidos a juntas lógicas. O custo só se justifica com um banco maior ou tempo de avaliação medido. |
| [Animation Compression Library](https://github.com/nfrechette/acl) | Compressão e avaliação de trilhas. | Comparar tamanho de um pacote representativo e erro no pé/mão depois de descomprimir. Adiar até o projeto ter volume de clipes que afete o bundle ou a memória. |

**Retarget de referência.** Identificar membros pela função e não por índice. Colocar referência e rig em uma pose comum, comparar comprimento e direções locais, normalizar a trajetória e reescrever contatos para o gabinete. Fazer o bake nas juntas do Mário. Para um take com volta completa, preservar direção do giro e chaves intermediárias. A validação de retarget é destino anatômico, contato e leitura do gesto.

**Proveniência.** Para cada entrada, guardar fonte, commit/tag, arquivo de licença, autor, modificações e termos de redistribuição do asset. Código, vídeo, áudio e modelo podem ter permissões distintas. Para benchmark de áudio, um click track sintético com anotações oferece um padrão controlado.

## 3. Linguagens e integração com a base atual

| Linguagem ou técnica | Onde cabe | Custo e critério de adoção |
| --- | --- | --- |
| Python puro | Agência, tempos autorais, presets, arbitragem, contratos, diagnósticos e primeira versão de IK. | Caminho de menor atrito. Medir antes de substituir. Reusar as rotinas existentes para o oráculo. |
| Python + NumPy | Operações em lote e análise de áudio já prevista no projeto. | Vetorizar matrizes/segmentos quando os dados já estiverem agrupados. Medir criação de arrays, alocações e cópias além do kernel. |
| [Cython](https://github.com/cython/cython) | Portar um loop numérico com tipos explícitos e baixo volume de alterações conceituais. | Requer extensão e wheels no Windows. Comparar com Python/NumPy em fluxo completo. |
| [Numba](https://github.com/numba/numba) | Experimentos de JIT para kernel denso em dados NumPy. | Avaliar suporte ao Python do projeto, tempo de aquecimento, cache, dependências e PyInstaller. Útil como benchmark antes de considerar runtime. |
| C++ com [pybind11](https://github.com/pybind/pybind11) | FK/colisão em lote, matemática existente ou integração com biblioteca C++. | Manter entrada e saída em buffers de tipos simples, uma chamada por lote. Medir custo de cópia, vida útil da memória e ABI Windows. [DirectXMath](https://github.com/Microsoft/DirectXMath) é referência de matemática SIMD se o trecho justificar. |
| Rust com [PyO3](https://pyo3.rs/) e [maturin](https://github.com/PyO3/maturin) | Extensão de matemática, análise de áudio ou interface de plataforma isolada. | Manter o mesmo contrato do oráculo. [windows-rs](https://github.com/Microsoft/windows-rs) pode servir num caso de integração Win32 delimitado. Um novo módulo deve provar build, desempenho e manutenção. |
| C com ABI explícita | Kernel pequeno e independente, acessível por CFFI ou ctypes. | Checar tamanho e alinhamento dos tipos, propriedade e erros. Para muitas chamadas por quadro, agregar lotes antes de atravessar a fronteira. |
| C# | Launcher e tooling de distribuição. O projeto já usa [SeJogaLauncher.cs](../installer/SeJogaLauncher.cs). | Aproveitar onde o fluxo de instalação já pertence ao launcher. Um sidecar tem latência, troca de mensagens e ciclo de vida próprios. |
| JavaScript/TypeScript | Inspeção de glTF, plugins Blockbench e ferramentas offline de autoria. | Exportar dados versionados para Python. Validação no bundle continua com o loader de produção. |
| GLSL | Contorno, material e efeitos que dependem de pixels. | Medir GPU, alpha e render pós-processado. Picking e contato ainda precisam da mesma geometria efetiva. |

### Como provar uma extensão nativa

1. Escolher a etapa que domina o frame. Por exemplo, busca de colisão de braços durante dança com caixa. Guardar entrada representativa e saída de referência.
2. Comparar Python atual, tentativa simples de reduzir trabalho e um único candidato nativo. Medir tempo da chamada completa, warm-up, frame p95/p99 e precisão no contato.
3. Usar testes para valores finitos, transformação local e continuidade do contrato. Reproduzir a ação na mesma cena, monitor e perfil. Checar wheel, DLLs e PyInstaller na versão de Python usada no build.
4. Adotar quando o ganho aparece no frame e a rotina pode ser mantida com dependências e ABI claras. Se o custo está na apresentação WGL ou em redimensionamento, a investigação segue pelo overlay.

## 4. Áudio, agência e desktop

| Fonte | Uso no estudo | Decisão proposta |
| --- | --- | --- |
| [WASAPI loopback](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording) e [SoundCard](https://github.com/bastibe/SoundCard) | Captura do sinal reproduzido. | Instrumentar o pipeline atual e medir atraso. Testar troca de dispositivo e falta de sinal. |
| [librosa](https://github.com/librosa/librosa) | Análise de áudio para referência offline. | Usar em ferramenta de calibração para comparar BPM/onsets com anotações e o tracker atual. |
| [aubio](https://github.com/aubio/aubio) | Alternativa de detector de onset e batida. | Comparar atraso e estabilidade em janelas curtas. Conferir licença e distribuição antes de considerar dependência. |
| [BehaviorTree.CPP](https://github.com/BehaviorTree/BehaviorTree.CPP) | Referência para cancelamento e composição de comportamento. | Começar com prioridades e estado existentes. Revisitar árvores se houver ações compostas com interrupções e donos difíceis de rastrear. |
| [Recast/Detour](https://github.com/recastnavigation/recastnavigation) | Referência de navegação em espaços complexos. | Para percorrer o desktop, começar com intervalos de apoio e destinos sobre superfícies conhecidas. Considerar grafo se houver navegação entre alturas, prateleiras e monitores. |
| [DPI por monitor, Microsoft](https://learn.microsoft.com/en-us/windows/win32/hidpi/setting-the-default-dpi-awareness-for-a-process) | Contexto de DPI e coordenadas da janela. | Registrar origem virtual, DPI do HWND e projeção. Repetir captura em monitores com densidade diferente. |
| [SetWindowPos](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos) e [ShowCursor](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-showcursor) | Z-order, posição e contador de visibilidade. | Testar movimentação sem foco roubado e restauração em cada saída. Clicar em uma janela de teste própria na eventual prova de interação nativa. |
| [Pymunk](https://pymunk.readthedocs.io/en/latest/overview.html) e [PStats](https://docs.panda3d.org/1.10/python/optimization/using-pstats) | Passo de física e medição de frame. | Manter a física já integrada. Identificar se o custo está no passo, na pose, em alocação ou no framebuffer antes de trocar biblioteca. |

## 5. Experimentos que respondem às decisões principais

| Pergunta | Comparação | Evidência |
| --- | --- | --- |
| Uma ação pode ser editada fora do Python? | Aceno no amostrador atual e a mesma intenção autorada no Blockbench. | Hierarquia igual, eventos e pose em runtime, captura e bundle. |
| O pé precisa de uma âncora explícita? | Marcha atual e marcador de apoio em desktop absoluto. | Deslocamento do pé plantado em início, reversão, freada e mudança de HWND. |
| O Mário reage com vontade própria? | Mesmo arraste com meta à esquerda, direita e meta cancelada. | Direção da tensão, reação, recuperação e escolha posterior. |
| A dança está no tempo? | Relógio livre, correção por onset e relógio com fase timestampada. | Erro do acento em click track, troca de BPM e perda de áudio. |
| Trocar o solver melhora a pose? | Resolvedor atual e um único candidato no mesmo alcance. | Penetração, estabilidade de polo, contato e custo p95. |
| Compilar resolve o gargalo? | Python, operação em lote e extensão apenas no trecho medido. | Tempo total, precisão, tamanho do bundle e compatibilidade de execução. |

**Escolha de base.** Panda3D, Python, PySide6 e Pymunk já dão os pontos de integração para a primeira cena. Blockbench e Khronos são a primeira prova de autoria externa. C++, Rust, C#, JavaScript e outros motores entram por um problema delimitado, com a cena equivalente funcionando antes e depois.
