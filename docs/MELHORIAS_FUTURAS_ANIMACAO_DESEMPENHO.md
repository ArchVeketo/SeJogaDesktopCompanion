# Melhorias futuras de animação, fluidez e desempenho

Este documento descreve experimentos para o runtime atual do SeJoga Desktop Companion. Use `GUIA_TECNICO_CORRECOES.md` para os contratos de correção e distribuição. As propostas abaixo incluem como medir o benefício e como perceber regressões visuais.

## 1. Estabilizar o canvas durante o arraste

### Hipótese da piscada

Em `janela.py`, `_fit_pose_window()` mede a pose depois de aplicar as rotações do corpo. Uma pega pelo pé vira o tronco, e uma pega pelo braço inclina o conjunto para o membro. A extensão projetada muda bastante nesses gestos. Quando cruza um degrau, o código muda imediatamente a lente, as dimensões do renderer e os offsets da física e do arraste. O novo tamanho e a origem da janela chegam por `requestProperties()`, cuja aplicação é adiada até a tarefa da janela. Durante o gesto, `_mouse_poll()` também move o HWND por `SetWindowPos(..., SWP_NOSIZE)`.

Na `main` local, o mínimo de dois degraus da pega pelo pé é aplicado à necessidade **antes** da margem de 48 px. Com base de 480 px, a conta procura espaço para 1.008 px e escolhe 1.440 px. Em uma checagem determinística da lógica, o pé foi direto para 1.440 px. O braço, com extensões de 390, 450 e 940 px, percorreu 480 → 960 → 1.440 px. Na worktree isolada, a mudança em andamento já aplica o mínimo do pé depois de escolher o tamanho. A combinação entre mudança imediata no renderer e mudança enfileirada no HWND ainda existe.

| Lado | Pixels por imagem | Área relativa a 480 px |
| --- | ---: | ---: |
| 480 px | 230.400 | 1× |
| 960 px | 921.600 | 4× |
| 1.440 px | 2.073.600 | 9× |

Essas proporções descrevem a área. O impacto no tempo de quadro depende do driver, do MSAA, do pós-processamento e da composição. Uma piscada sincronizada com o resize pode vir de um quadro apresentado com tamanho, origem ou conteúdo diferentes do esperado. Uma queda de cadência pode ocorrer mesmo com o tamanho estável, pelo custo de desenhar a área maior.

### Experimento que separa as causas

1. Rode uma instância isolada, com perfil temporário. Registre PID, caminho do executável, HWND, backend gráfico, DPI, monitor e estado da física. Capture um arraste pelo braço, um pelo pé e um pelo tronco como controle. Inclua início, inversão, mão parada e soltura.
2. Registre por quadro o identificador da pega, `dt`, extensão projetada, tamanho decidido, tamanho do renderer, tamanho efetivo do Panda, retângulo da área cliente no desktop e origem pedida. Guarde também a posição do cursor e da pega projetada em tela. Marque os quadros em que houve pedido de resize ou mudança do tamanho efetivo.
3. Compare a captura do desktop composto com o framebuffer no mesmo intervalo. Se o modelo está no framebuffer e some apenas no desktop, investigue apresentação, resize e color key. Se desaparece nos dois, investigue lente, projeção, recorte e estado do modelo. Se fica visível, mas salta, compare a projeção da pega com o cursor e a origem efetiva.
4. Repita com o canvas reservado antes da pega e fixo até a soltura. Mantenha a mesma pose e a mesma trajetória do cursor. Se a piscada some com canvas fixo e volta com resize, há evidência a favor do redimensionamento. Se continua, compare imagem e tempos para investigar color key, custo do render ou deslocamento do HWND.

Capture vídeo do desktop em uma rodada própria. A leitura do framebuffer pode sincronizar CPU e GPU e alterar os tempos medidos. Faça a coleta de desempenho em outra rodada com os mesmos movimentos e sem captura.

### Evolução da implementação

- Meça um envelope conservador por tipo de pega usando o rig, as escalas suportadas e os extremos do movimento. Reserve espaço no início do gesto. Quando precisar crescer em emergência para evitar corte, aguarde a confirmação do tamanho efetivo antes de pedir outro resize. Encolha depois da soltura e do assentamento.
- Preserve a posição absoluta da pega e a escala em pixels por unidade durante a troca. Se a origem da área cliente vai de `O` a `O'`, o ponto local correspondente passa de `P - O` a `P - O'`, com `P` fixo em coordenadas de tela. Use o mesmo referencial no picking, na lente e no cálculo da posição do HWND.
- Centralize a decisão de origem e tamanho por quadro. O mouse oferece a posição de arraste e a física oferece a posição durante queda e repouso. A aplicação de janela escolhe a fonte ativa, combina tamanho e origem e observa o que o Panda aplicou. Uma confirmação atrasada não deve restaurar uma origem antiga enquanto o mouse continua andando.
- Compare a alternativa de manter o canvas grande apenas durante gestos extensos. Ela diminui trocas de tamanho e aumenta custo de pixels enquanto a área está reservada. A medida deve orientar a escolha do menor degrau que ainda contém a pose.

Considere a mudança bem-sucedida quando a captura do desktop não apresentar sumiço, a pose e o contorno não forem cortados e o erro da pega não aumentar nos quadros de troca. Compare também o número de resizes e a cauda dos tempos de quadro.

## 2. Medir a cadência e reduzir picos

A 60 FPS, há 16,67 ms por quadro. Uma média de 60 pode esconder quadros que passam desse prazo. Registre mediana, p95 e p99 do tempo entre quadros e a contagem acima do orçamento. Meça separadamente o tempo de CPU da animação, os custos de submissão do render e o tempo de apresentação quando houver esse dado. Compare o mesmo backend, configuração, hardware, estado de captura e cenário.

`tools/perfilar_animacao.py` já mede cadência e CPU de `_animation_tick()` em repouso e espiada. Uma evolução é acrescentar segmentos repetíveis de arraste, dança com caixa visível e repouso com a física ligada. Separe os quadros com resize. As capturas que o script faz no meio da espiada podem afetar o intervalo seguinte. Separe esses quadros ou rode sem captura para obter a referência.

No Panda3D, o PStats separa o tempo em App, Cull e Draw. App inclui tarefas como controlador e atualização de malha. Cull é a preparação da cena visível. Draw mede o trabalho de desenho observado pelo motor e pode incluir esperas. Comece com a coleta leve e use o perfil detalhado de Python numa segunda rodada, porque instrumentar todas as chamadas altera o custo.

| Candidato no código | Experimento | Condição para adotar |
| --- | --- | --- |
| `_fit_pose_window()` chama `getTightBounds()` antes de consultar o cache de projeção | Meça bounds e projeção separadamente. Durante pega com canvas reservado, compare com limites conservadores do rig e medição exata apenas quando necessário | Menor p95 sem recorte ou perda de alinhamento com a caixa de som |
| Estados migrados produzem pose legada e deltas no mesmo quadro | Meça custo por etapa. Capture as juntas que só o caminho legado fornece. Retire trabalho duplicado em um estado por vez | Ganho mensurável com poses e transições equivalentes nas juntas existentes |
| `fio_fone_malha.py` e `sistema_tentaculos.py` atualizam vértices | Meça simulação e escrita de vértices separadamente. Compare reutilização de dados e atualização apenas quando os pontos realmente mudarem | Menor CPU sem degraus visuais, clipping ou contorno fora da malha |
| Render fica mais caro no maior degrau | Compare p95 e p99 por área, com o mesmo MSAA e shader. Compare framebuffer e desktop antes de alterar amostragem | Menor custo com transparência e borda preservadas |
| Pymunk e a janela operam em frequências diferentes | Conte subpassos físicos e mudanças reais de origem. Compare aplicar apenas a origem final do quadro quando a posição não mudou entre submissões | Menos trabalho Win32 com posição, contato e soltura preservados |

## 3. Suavização de movimento

### Mola para peso, filtro para ruído

Use a mola analítica já presente quando a pose precisa de posição e velocidade próprias. Ao trocar o alvo, mantenha a velocidade atual se a troca deve parecer contínua. Para retorno sem oscilação, compare amortecimento crítico. Para gesto que deve passar ligeiramente do alvo e voltar, use amortecimento abaixo do crítico com amplitude medida. Evite impor um limite de alvo ao valor atual da mola, pois isso introduz um salto mesmo quando o alvo mudou corretamente.

Para suavizar um escalar com ruído, como energia ou um sinal auxiliar de atenção, use uma aproximação exponencial que dependa do tempo: `alfa = 1 - exp(-ln(2) * dt / meia_vida)`. A cada passo, some `alfa * (alvo - valor)`. A meia-vida aqui é o tempo para eliminar metade do erro com alvo fixo. Na pega, mantenha o ponto sob o cursor e aplique a suavização à reação do tronco e dos membros. Filtrar a posição que ancora a pega introduz atraso perceptível.

Pymunk já integra em passos fixos de 1/120 s. Caso apareçam degraus no deslocamento com render acima da frequência física ou cadência irregular, experimente interpolar a apresentação entre dois estados físicos, usando a fração restante do acumulador. Interpolar estados passados pode adicionar atraso de até um passo. Exclua o arraste direto dessa experiência e trate arremesso, reposicionamento instantâneo e perda de apoio como eventos que podem invalidar o par anterior.

### Como comparar

- Compare a mesma trajetória de entrada em 30, 60 e 120 FPS. Para alvo fixo, avalie a pose nos mesmos instantes. Para alvo variável, mantenha a mesma trajetória de referência e identifique diferenças introduzidas pela amostragem.
- Registre pico de velocidade angular, mudança de velocidade na transição, tempo de assentamento e erro da pega em pixels. Use trajetórias conhecidas com arranque, inversão, parada e soltura.
- Para clipes de pose parada a pose parada, a curva quíntica compartilhada fornece velocidade e aceleração nulas nas extremidades. Em locomoção contínua, compare também as derivadas e o contato na emenda do ciclo. Zerar a velocidade em cada chave pode criar pausas nos pés onde a passada deveria fluir.

## 4. Animações com contato e intenção

1. **Locomoção.** Use a fase comum de braços e pernas. Durante o apoio, fixe o pé no referencial de cena e permita que tronco e pelve avancem sobre ele. Durante o balanço, libere o pé e controle altura, alcance e tempo de chegada. Meça deslizamento do pé apoiado e penetração no chão, incluindo troca entre caminhada, corrida e giro no lugar.
2. **Dança.** Mantenha fase musical, decisão de começar uma frase e execução da pose como estados distintos. Corrija a fase por batida de forma gradual e faça a troca de estilo em um limite de frase com apoio compatível. Meça atraso entre onset e acento da pose e observe a continuidade na troca de BPM. Para `head_bob`, confira o apoio no volume real da caixa e a posição dos pés depois de mudar a escala do palco.
3. **Arraste.** Guarde a junta e o ponto local da pega se o ponto for deformado pelo rig. Confira a transformação desse ponto no quadro já posado. Dê atraso secundário a ombros, cabeça, punhos e pés de acordo com a pega. Cada junta segue o próprio alvo local. Valide direita, esquerda, perfil e costas por FK do grafo.
4. **Tentáculos e porta.** Faça o contato iniciar a abertura, mantenha a intenção da espiada separada de um pedido externo de porta e verifique a passagem entre as fases. Compare a posição da ponta e da borda da porta no mesmo referencial. Meça penetração e descontinuidade na revelação, inclusive quando a espiada é cancelada.

## Ordem dos experimentos

1. Instrumente o resize e reproduza com canvas fixo. Use a captura do desktop para decidir se a piscada é de apresentação.
2. Meça a cadência por estado e tamanho. Reduza o custo do caminho que aparecer no perfil antes de alterar a frequência de atualização das poses.
3. Trabalhe primeiro na continuidade de pega e transição. Em seguida, avance para contatos dos pés, fases da dança e coreografia da porta.

### Base técnica consultada

Panda3D 1.10, referência de `GraphicsWindow` e medição com PStats. Microsoft Learn, semântica de `SetWindowPos`. Ryan Juckett, solução analítica de molas amortecidas. Glenn Fiedler, integração de passo fixo e interpolação de apresentação. O procedimento acima reúne os pontos aplicáveis ao companion.
