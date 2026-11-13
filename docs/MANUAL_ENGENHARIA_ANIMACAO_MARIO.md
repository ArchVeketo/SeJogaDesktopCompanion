# Manual de engenharia e animação do Mário

**13/11/2026 · proposta técnica complementar · base 000823e com alterações locais**

O [Manual Unificado](MANUAL_UNIFICADO_MARIO.md) define o personagem e os 12 princípios que regem toda ação. O [Manifesto](MANIFESTO_CRIATURA_VIVA_MARIO.md) define a vontade própria do Mário e o conflito com o usuário. Este manual traduz essa direção em contratos de código, métodos de animação, pipeline de assets e critérios de entrega. O [roadmap vigente](STATUS_E_PROXIMOS_PASSOS.md) continua sendo o registro do projeto. A [auditoria da árvore local](AUDITORIA_TECNICA_MARIO_2026-11-13.md) registra o que foi comprovado. O [caderno de referências](REFERENCIAS_ENGENHARIA_ANIMACAO_MARIO.md) explica o que estudar e quando integrar.

## 1. A unidade de trabalho é uma ação inteira

Uma ação precisa de causa observável, intenção, pose de preparação, ação principal, consequência e recuperação. Um novo braço, curva ou shader só termina quando a ação composta pode ser julgada na janela real. O Mário padrão deve se sustentar em qualquer perfil. Variações de estilo podem mudar a maneira de se expressar, mantendo a causa, a leitura do gesto e os apoios.

A primeira sequência de referência deve caber em poucos segundos. Mário percebe algo, antecipa a caminhada, começa a andar, é agarrado, continua interessado no alvo, é solto, absorve o impacto e decide se retoma a meta. Ela exercita a transição entre agência, movimento autoral e contato do desktop. Cada fase do roubo do mouse pode ser ensaiada com um cursor desenhado dentro da cena. A operação Win32 merece uma prova própria com os casos de cancelamento e restauração descritos adiante.

### Ficha para iniciar uma ação

| Campo | Exemplo para “olhar por cima do ombro” |
| --- | --- |
| Causa e intenção | Troca de janela perceptível enquanto está em repouso. Mário quer identificar de onde veio o estímulo. |
| Entrada | Pose atual e pé de apoio. O olhar precede a rotação do torso. |
| Poses de leitura | Micro-recuo, olhar lateral, torso acompanha, sustentação curiosa, recuperação. |
| Espaço e contatos | Alvo do olhar em espaço conhecido. Apoio preso ao desktop durante a primeira fase. |
| Propriedade dos canais | A ação conduz cabeça e torso. A respiração tem amplitude reduzida no acento. O resolvedor preserva contatos. |
| Interrupções | Arraste captura a pose corrente. Uma janela nova durante o gesto atualiza a intenção em um ponto de decisão. |
| Variação | Amplitude e duração dependem da distância, do histórico e da atenção. A direção vem do estímulo. |
| Evidência | Vídeo na escala de uso, perfil para medir arco e capturas antes e depois da interrupção. |

## 2. Contratos das três camadas

| Camada | Recebe | Decide ou entrega | Ponto de partida no repositório |
| --- | --- | --- | --- |
| Agência | Evento de mouse, foco, apoio, histórico breve, disponibilidade de áudio e ações possíveis | Meta, alvo, urgência, motivo da troca e regra de cancelamento | [agencia.py](../src/sejoga/animacao/agencia.py), [controlador_animacao.py](../src/sejoga/animacao/controlador_animacao.py) |
| Animação | Intenção, pose anterior, fase e contatos observados | Pose local, escala, alvos de mãos/pés, eventos da ação | [camadas_animacao.py](../src/sejoga/animacao/camadas_animacao.py), [resolvedor_poses.py](../src/sejoga/animacao/resolvedor_poses.py), [movimento_pernas.py](../src/sejoga/animacao/movimento_pernas.py) |
| Integração com o desktop | Entrada Win32, topologia, física, cena e saída da animação | Atualiza Pymunk, aplica a cena, apresenta o frame e gerencia efeitos do sistema | [janela.py](../src/sejoga/render/janela.py), [renderizador.py](../src/sejoga/render/renderizador.py), [fisica.py](../src/sejoga/desktop/fisica.py) |

O contrato deve ser observável antes de virar uma nova abstração. Começar pelos objetos e chamadas existentes. Uma reprodução precisa reconstruir o estímulo, a ordem de eventos e a pose aceita. Os módulos puros continuam importáveis sem Panda3D, Qt e Win32. A camada de desktop traduz APIs e tipos da plataforma.

### Espaços, relógios e propriedade

- **Desktop absoluto em pixels:** cursor, posição e velocidade do corpo, limites e alvos de navegação. Um monitor à esquerda pode ter X negativo. Um vetor de intenção nasce de alvo menos posição do corpo no mesmo espaço. Transformar para a orientação local do personagem quando necessário.
- **Janela em pixels:** entrada relativa ao HWND. Converter com a origem e dimensões efetivamente apresentadas. O redimensionamento assíncrono exige validar o retângulo depois de aplicado.
- **Cena e rig:** offsets em unidades do modelo, pose em rotações locais relativas ao repouso. Usar FK para transformar ponto e vetor, com tratamento distinto da translação. Registrar ordem, unidade e lado da composição. Usar o oráculo Panda para provar eixos.
- **Tempo:** passo fixo de física, relógio monotônico de animação, tempo local da ação, fase cíclica da passada e relógio do áudio. Quadro autoral é convertido para tempo. Um evento possui instante e identidade para sobreviver a amostragens diferentes. Fases e eventos devem ser testados também após atraso de quadro.
- **Propriedade:** Pymunk governa posição física. A pose governa aparência e intenção. Resolver um contato com o prop antes de aplicar correções visuais que o possam deslocar. Cada canal concorrente tem prioridade explícita ou composição com ordem conhecida. Porta, apoio, mão em alvo e efeito de cursor precisam de um dono em cada fase.
- **Contato e render:** malha, picking e contorno seguem o mesmo transform onde compartilham geometria. Registrar pivô de escala e ponto de ancoragem. Contato válido antes da escala final pode escorregar após ela.

### Ordem proposta por quadro

1. Observar entrada, apoio, foco, cursor e áudio em um snapshot coerente. Registrar a origem das coordenadas.
2. Atualizar intenção e arbitrar a ação. Arraste, queda e pouso podem interromper uma ação. O fim do estímulo decide retomar, recuperar ou abandonar. Aplicar histerese nas fronteiras de velocidade.
3. Amostrar pose autoral e eventos. Adaptar alvos ao ambiente. Compor gestos secundários por máscaras, com prioridade de leitura.
4. Resolver apoio e colisões na pose final. Contato impossível reduz alcance ou troca o apoio. Calibrar a ordem de deformação e IK no Panda.
5. Aplicar a cena e efeitos externos. Capturar o resultado efetivamente apresentado. Quando a janela se mover, registrar o deslocamento do HWND separadamente do deslocamento do corpo.

O fluxo existente distribui partes dessas responsabilidades entre overlay, controlador e renderer. A ordem acima é um alvo para comparar com traços do runtime. Mover uma responsabilidade por lote, com evidência antes e depois.

## 3. Como construir o movimento

### Pose autoral, adaptação procedural e simulação

Use poses-chave para intenção, silhueta, linha de ação e acentos. Use procedimento para adaptar a direção do olhar, amplitude, velocidade, alcance, posição do apoio e continuidade quando o usuário interrompe. A física fornece trajetória, aceleração da mão e impulso de contato. O fio e outros apêndices passivos podem reagir por restrições. A atuação central continua autoral.

Uma curva quíntica de repouso a repouso serve para começar e terminar com velocidade e aceleração nulas. Aplicá-la a toda chave intermediária introduz uma parada em cada chave. Para um arco que atravessa um ponto, preservar tangentes com Hermite, curva de Bézier ou uma trajetória de alvo contínua. Para loop, conferir posição e derivada no fechamento. Para um acento com impacto, desenhar a quebra e sua recuperação.

Para interrupção rápida, amostrar a pose que acabou de sair, estimar a velocidade em segundos e reduzir um offset inicial em uma janela curta. A derivada do offset deve considerar a velocidade do destino móvel se a continuidade for uma exigência. Resolver novamente contatos que continuam válidos. Verificar entradas e saídas com reversão e duas interrupções seguidas. A derivada é um instrumento de diagnóstico. A escolha de um impacto seco é artística.

Euler local é suficiente para canais simples calibrados. Quando houver rotação multieixo grande, comparar com composição por quaternion e caminho curto. Manter a ordem de referência do grafo. Para um giro autoral acima de 180°, chaves intermediárias carregam a direção desejada. Converter representação na fronteira comprovada com FK. [Inertialização, GDC](https://www.gdcvault.com/play/1025165/Inertialization-High-Performance-Animation-Transitions) · [Motion Warping, Witkin e Popović](https://publications.ri.cmu.edu/motion-warping)

### Locomoção, apoio e equilíbrio

O corpo físico fornece deslocamento horizontal. O ciclo visual fornece contato, descida, passagem e elevação. Na entrada do apoio, fixe uma âncora mundial para aquele pé. Durante o apoio, leve a âncora ao referencial do quadril e resolva o comprimento com polo do joelho. Durante o voo, use arco autoral e procure o próximo contato dentro do alcance. Se o corpo ultrapassar o alcance, antecipe a transferência de peso. Para mudar de sentido, baixar velocidade, pivotar sobre um apoio e produzir uma nova passada. Medir início, cruzeiro, freada, inversão e passagem pela borda.

O alvo de raiz de uma referência de mocap pode ser útil para medir peso e distância. No overlay, a posição horizontal vem do corpo físico. Retire ou converta o deslocamento do clipe uma vez, preservando informação de contato e fase. Somar deslocamento da raiz e de Pymunk gera deslizamento e desencontro com picking. Acompanhar um marcador no pé ancorado sobre o desktop e outro no quadril. Capturar de perfil quando a frente esconder o erro de profundidade.

Para braços, use FK quando a silhueta é o objetivo e IK quando o contato é o objetivo. Fixe polo anatômico e trate extensão máxima para evitar flips. Dois elos admitem solução analítica. FABRIK é candidato para apêndices longos e alvos interativos. Limites, contatos e troca de polo continuam sendo decisões de implementação. [FABRIK, Aristidou e Lasenby](https://www.andreasaristidou.com/publications/papers/FABRIK.pdf)

### Os 12 princípios em cada take

O take só é aceito quando os doze operam juntos. A ficha abaixo dá perguntas de direção, com um único take como exemplo. Fazer o mesmo exercício em idle, locomoção, arraste, pouso, gesto, dança, sono e tentáculos.

| Princípio | Aplicação no take de pouso após arraste |
| --- | --- |
| Compressão e extensão | Alongar na queda, comprimir no contato e reexpandir com pivô no apoio. |
| Antecipação | Joelhos e braços preparam a aterrissagem quando a superfície entra no alcance. |
| Encenação | Separar braços e cabeça da silhueta do gabinete para ler esforço. |
| Pose a pose e direta | Definir queda, impacto e recuperação como chaves. Ajustar impacto à altura e velocidade observadas. |
| Continuidade e sobreposição | Pé encontra a superfície, gabinete cede, fones e fio terminam depois. |
| Aceleração e desaceleração | Velocidade cresce no ar. O retorno amortece perto da pose recuperada. |
| Arcos | Cabeça e mãos descrevem trajetória legível durante a recuperação. |
| Ação secundária | Porta ou fones reagem sem encobrir a expressão do tronco. |
| Timing | Contato breve e recuperação com tempo para ler a indignação. |
| Exagero | Comprimir e abrir a silhueta o suficiente para leitura em miniatura. |
| Desenho sólido | Preservar volume aparente, articulações e suporte do pé. |
| Apelo | O olhar de volta ao cursor dá significado ao impacto. |

### Receitas de produção

| Ação | Poses e procedimento | Prova na janela real |
| --- | --- | --- |
| Idle e atenção | Apoio assimétrico, respiração contínua, curiosidade antecipada pelo olhar e recuperação. Arco pequeno no torso, atraso breve nos fones e dedos. Contexto escolhe a variação. | Observar um minuto em tamanho de uso, provocar troca de foco e mover o cursor. A cabeça comunica atenção e o corpo continua respirando. |
| Caminhar, correr e virar | Usar pares de contato com deslocamento real e balanço contralateral. Desenhar início, transferência, velocidade constante e freada como partes distintas. | Marcar o pé apoiado e repetir nos dois sentidos com troca de origem da janela. |
| Arraste e queda | Preservar a pega, inclinar pela aceleração observada, resistir em direção à meta e antecipar o chão. Soltura recebe velocidade do desktop. | Pegar braço, pé e corpo, inverter a mão, soltar em alturas diferentes, testar meta nos dois lados e deixar cair durante reação. |
| Pouso | Pose de absorção seguida de retorno de peso. Aplique squash a partir do impulso, em torno da base. | Inspecionar o primeiro frame no solo e o retorno. A borda da janela e o contorno devem acompanhar a pose. |
| Toque, susto e aceno | Preparação, pose legível, sustentação e recuperação. Reutilizar máscara do braço, orientar pelo estímulo e validar palma por FK. | Disparar de frente e de costas, interromper no pico e em recuperação. |
| Sono e despertar | Preparar descida, procurar o assento, transferir peso, respirar lento, recuperar o apoio antes de levantar. | Validar a superfície real em pé, sentado e deitado. Acordar por interação em fases diferentes. |
| Dança e palco | Frases de 4 ou 8 tempos com acentos, holds e variação. Corrigir fase sem saltar o contato. Caixa, mão e corpo compartilham referência do prop. | Metrônomo, música com síncope, silêncio, troca de dispositivo e transição de estilo com caixa presente. |
| Porta, tentáculos e fio | Porta com antecipação e dono por fase. Base do tentáculo espera folga. A ponta alcança por arco, recua com intenção e leva o resto da cadeia. Fio reage a fones e tronco. | Abrir e interromper durante espirro, inspeção de perfil e contato em todas as fases. Conferir alpha no contorno. |
| Teimosia | Separar resistência, repreensão, bote, roubo encenado e devolução. A meta orienta resistência e o sucesso muda a ação. | Rodar com captura interrompida, app ocultado, shutdown, atualização e desconexão de monitor. |

### Música ao vivo

Tratar estado de reprodução, energia, transiente, BPM, fase e confiança como sinais distintos. A sessão de mídia informa estado. Loopback fornece áudio de saída para análise. Um relógio comum e timestamps permitem compensar atraso do buffer. A fase prevista avança entre batidas. Ao receber evento confiável, corrigir erro de fase de forma limitada, preferencialmente na fronteira da frase. Em perda de áudio, preservar a fase por tempo curto e fazer recuperação autoral. Com música irregular, marcar groove por energia ou abandonar o sincronismo de pé. BPM descreve andamento.

Gravar uma trilha de teste com click track a 90, 120 e 160 BPM, alteração de tempo, síncope e pausas. Comparar o instante de áudio de referência com contato e acento no vídeo. Primeiro testar o relógio usando eventos sintéticos. Depois comparar captura real e prévia manual. Medir perda e duplicação dos eventos para diferentes taxas de render. [WASAPI loopback](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording)

## 4. Pipeline de assets e keyframes

### Inventário e origem

O arquivo de trabalho é [projetoMARIO.bbmodel](../assets/model/projetoMARIO.bbmodel). Nesta árvore o runtime resolve o stem `mario`, preferindo GLB se presente. A auditoria registrou contagens diferentes entre o canônico histórico e os JSON atuais. Para cada export, guardar caminho, hash, versão do exportador, unidades, hierarquia, pivôs, nomes e contagem por tipo. Listar também nós gerados no runtime. A porta, os fones, os dedos e as pernas precisam ter identidade estável. [Resolvedor de assets](../src/sejoga/nucleo/recursos.py)

### Sequência de autoria

1. Duplicar a cena de trabalho para o take. Guardar referência de movimento com licença e autoria registradas. Para referências de jogos, estudar silhueta, cadência e transferência de peso em vídeo. Produzir uma interpretação do Mário.
2. Bloquear 3 a 6 poses de leitura em chaves discretas. Testar frente, 3/4, perfil, costas e tamanho real de desktop. Marcar apoios, arcos, eventos e prioridades antes de refinar.
3. Passar ao spline e editar espaçamento. Checar tensão, acento, tempo de hold, oclusão e ação secundária. A recuperação faz parte do take.
4. Exportar do Blockbench com nomes e hierarquia preservados. Blender pode servir como estação de análise, criação de referência e retarget offline. Para um round trip, comparar transforms de repouso e pivôs com o modelo original.
5. Validar GLTF/GLB com Khronos e comparar com inventário do rig. Conferir buffers, índices, texturas, canais, trilhas de tempo e escalas. Resolver recursos por caminho explícito na auditoria do export. Reabrir o artefato que será distribuído.
6. Integrar uma ação piloto. Para o formato atual, transportar chaves de rotação local e eventos para os amostradores existentes ou provar um importador para nós rígidos com uma junta e um clipe curto. Guardar escala, translação e quaternion somente quando o contrato suportar esses canais.
7. Validar no renderer, na captura de desktop e no executável recém-gerado. Picking, contorno e malha devem concordar durante a ação e na interrupção.

### Contrato proposto para dados de animação

| Propriedade | Regra |
| --- | --- |
| Identidade | ID estável, revisão do rig, origem, autoria e termos de uso. |
| Tempo | Duração e chaves em segundos. Fase normalizada só para ciclo. FPS de autoria serve à edição. |
| Canais | Nó e propriedade local. Distinguir valor absoluto da pose base e delta. Registrar unidade, eixo e ordem. |
| Interpolação | Declaração por trilha ou segmento. glTF oferece STEP, LINEAR e CUBICSPLINE. CUBICSPLINE guarda tangentes e requer tratamento correto de quaternion. |
| Loop | Garantia de fechamento e eventos de pé na fronteira. A semântica do loop pertence ao runtime. |
| Eventos | Contato, saída de apoio, acento, abertura e ejeção com instante. Eventos colaterais devem disparar uma vez por passagem ou ter regra explícita de repetição. |
| Raiz | Definir dono do deslocamento e como aproveitar a referência de deslocamento no controlador. |
| Adaptação | Quais juntas pertencem à ação, contatos corrigíveis, limites de alcance, estratégia de interrupção. |
| Evidência | Capturas de preparação, pico, recuperação e um caso de interrupção. |

Começar com os arquivos de dados e amostradores em Python do projeto. Uma versão externa só ganha valor quando um artista precisa iterar sem editar Python ou um export recorrente precisa ser automatizado. Em uma prova glTF, a presença de `animations` no JSON indica trilhas no arquivo. A prova de execução é uma trilha afetando o nó correto na janela. [Khronos, animações glTF](https://github.khronos.org/glTF-Tutorials/gltfTutorial/gltfTutorial_007_Animations.html) · [Khronos, Validator](https://github.com/KhronosGroup/glTF-Validator)

### Materiais, contorno e props

Comparar texturas com alpha em frente e verso, na porta, na oclusão da mão e nas faces invisíveis de tentáculo. Se um nó é deformado, seu contorno e sua geometria de clique precisam da mesma pose e escala. Testar fundo claro, escuro e colorido. Se acrescentar normal/metal/roughness para um prop, abrir o arquivo no Panda com a luz de produção e testar custo. Priorizar textura nítida, silhueta e junta bem resolvida no tamanho do mascote.

Apoio em caixa de som é contato com um prop que também se move. Registrar o tampo, face de encosto e chão no espaço do prop. A caixa precisa caber no envelope da janela durante entrada, pouso e dança. Para danças referenciadas em mocap, limpar trajetória e escolher poses adaptadas ao comprimento de braço, volume de gabinete, porta e pivôs do rig.

## 5. Desktop, recursos e validação

- **Física:** fixar o passo e respeitar a transição KINEMATIC → DYNAMIC com massa e momento válidos. Cobrir dt longo, mudança de tamanho e liberação da pega em janela destruída. Chamar APIs HWND apenas enquanto o handle está válido.
- **DPI e topologia:** registrar coordenadas físicas e origem virtual. Ensaiar monitor à esquerda, barra de tarefas em posição alternativa, monitores com 100/150/200%, troca de resolução e desconexão física. Comparar pixels do desktop com a projeção e a pega.
- **Transparência:** medir a cor final após o pós-processamento. O registro histórico de RGB(214, 0, 214) serve de ponto de comparação. Validar áreas transparentes clicáveis por baixo, áreas do mascote clicáveis e franja de contorno. Evitar estilo global que torne todo o mascote inacessível ao mouse.
- **Cursor e ações de sistema:** manter o estado de um eventual efeito Win32 na camada de desktop e definir restauração única para fim, cancelamento, ocultação, atualização e encerramento. Provar o efeito na janela real antes de vinculá-lo à agência. Para cliques reais, uma cena de teste com janela alvo própria permite verificar destinatário e encerramento sem afetar aplicativos alheios. O protótipo encenado pode produzir o efeito visual inteiro.
- **Dados e distribuição:** usar perfil temporário em testes. Validar TOML inválido, valores antigos, recuperação e persistência sem elevação. Verificar o ZIP extraído e os recursos acessados durante a inicialização. Preservar o filtro de PATH do build e registrar as DLLs efetivamente carregadas.
- **Desempenho:** capturar p50/p95/p99 do tempo de quadro e do custo de pose/IK/contorno/render, junto da resolução do canvas e contagem de alterações de HWND. Usar 16,7 ms como referência inicial a 60 Hz. Registrar memória e CPU em idle e durante dança, arraste, resize e tentáculos. Otimizar a etapa medida. [Panda3D PStats](https://docs.panda3d.org/1.10/python/optimization/using-pstats)

| Verificação | Evidência |
| --- | --- |
| Infraestrutura | `python -m pytest` para persistência, integridade de rig, passos de física, valores finitos e contratos. |
| Trajetória | Traço FK e overlays de pé, mão, porta, meta e pivô. Quadro lento localiza o defeito. Velocidade normal julga peso e intenção. |
| Janela real | `python tools/smoke_mouse.py` e `python tools/smoke_mouse.py --physics`. Registrar versão, perfil, resolução e cenários. |
| Entrada nativa | `python tools/smoke_corpo_nativo.py`, em sessão supervisionada. O script move o mouse. Conferir click-through, captura e soltura. |
| Build | `./build.ps1`, abrir o bundle gerado, reproduzir com perfil isolado e conferir logs, captura e código de saída. |
| Áudio | Traço de timestamp de captura, onset e pose. Usar click track, silêncio, música real e troca de dispositivo. |
| Qualidade artística | Revisão em tamanho real com ficha dos 12 princípios, frente e perfil, interrupção e retorno. |

## 6. Plano de execução

| Ordem | Lote | Saída e condição de conclusão |
| --- | --- | --- |
| 0 | Congelar evidência da árvore | Identificar revisão e assets resolvidos. Registrar falhas de configuração, fixtures e curvas. Capturar baseline de Padrão, caminhada e arraste. |
| 1 | Uma cena de agência e arraste | Consertar o contrato de posição/direção e revisar precedência de arraste. A meta deve orientar o corpo para os dois lados e em monitores de origem diferente. Ensaiar teimosia em cena e tratar ciclo de vida do cursor como requisito próprio. |
| 2 | Idle → andar → parar → cair → pousar | Um take completo com peso, apoio e transferência. Rastrear propriedade de escala e contatos. Confirmar três ângulos, reversão e janela reposicionada. |
| 3 | Uma ação autorada fora do Python | Escolher aceno ou olhar sobre o ombro. Provar BBModel → GLTF → amostrador → renderer → bundle, com comparação de pose local e eventos. Fechar o contrato antes de produzir a biblioteca de clipes. |
| 4 | Porta, tentáculos e props | Reunir dono da porta, sequência de ejeção, atraso de tentáculos e apoio na caixa. Validar concorrência com arraste e encerramento. |
| 5 | Dança musical | Ligar um relógio de fase ao controlador, fazer um groove em referência conhecida, conferir o erro temporal e depois ampliar frases e estilos. |
| 6 | Sono, variações e acabamento | Completar repouso e despertar, adicionar estilos como variações do padrão e repetir revisões visuais. Resolver evidência de DPI misto e build Windows. |
| Condicional | Otimização nativa | Um perfil identifica o trecho caro e uma prova de ganho mede o frame inteiro. Implementação Python segue como oráculo. Comparar custo de distribuição e manutenção. |

As prioridades colocam interação e apoio antes do catálogo. O primeiro resultado verificável é a sequência em que a intenção persiste quando o usuário interfere e o corpo volta ao desktop com peso. Performance, novos estilos e novos assets entram nessa mesma sequência de verificação.
