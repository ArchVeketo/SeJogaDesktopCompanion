# Manual técnico e teórico do editor do Mário

Este manual descreve a proposta para a primeira versão do editor. A referência para movimento, agência e anatomia continua sendo o [Manual Unificado do Mário](MANUAL_UNIFICADO_MARIO.md). O editor serve para ensaiar uma ação no próprio personagem, corrigir o que se vê e gravar a alteração no código-fonte do companion.

## 1. O que a primeira versão cobre

A cobertura inicial inclui todas as famílias abaixo. Cada ação existente entra no catálogo com os controles que fazem sentido para ela e um cenário reproduzível. Por exemplo, uma pose de aceno pede chaves de juntas, enquanto uma ondulação de tentáculo pede trajetória, amplitude e atraso entre segmentos. O inventário dessas ações e dos respectivos controles é parte da entrega da primeira versão.

| Família | O que editar | Como ensaiar | Integração existente |
| --- | --- | --- | --- |
| Poses, idles e cenas | Poses locais, curvas, duração, loops, variantes, deslocamento do corpo e pesos de entrada e saída | Repetir a cena e vê-la começar e terminar no repouso | `clipes_ocioso.py`, `cenas_idle.py`, `clipes_animacao.py` |
| Respiração | Ritmo, amplitude, assimetria entre inspiração e expiração e contribuição por parte do corpo | Comparar alguns ciclos em repouso, em movimento e na transição para outra ação | `respiracao.py`, `respiracao_tuning.py`, `clipes_ocioso.py` |
| Dança | Frases, poses, acentos, fase, intensidade e mistura com a pose base | Tocar com metrônomo em BPM escolhido, com sequência gravada de batidas ou com música ao vivo | `movimento_danca.py`, `danca_clipes.py`, `musica/` |
| Tentáculos | Abertura da porta, revelação e retração, trajetória da ponta, ondulação, atraso por segmento e gotas | Repetir saída, contato com um obstáculo e retorno, com câmera frontal e lateral | `coreografia_porta.py`, `ondulacao.py`, `sistema_tentaculos.py` |
| Reações e transições | Antecipação, pose de resposta, recuperação, envelope e parâmetros autorais expostos pelo comportamento | Disparar clique, hover, susto, arraste, soltura ou impacto em instantes definidos. Ensaiar também sono, caminhada, entrada e saída | `gestos_reacao.py`, `controlador_animacao.py`, `movimento_pernas.py`, `animacao_entrada.py`, `animacao_saida.py` |
| VFX | Disparo, duração, ancoragem, deslocamento, cor, escala, emissão e desaparecimento, conforme o efeito | Tocar junto com a ação, pausar e voltar ao quadro que causou a emissão | `efeitos_cena.py`, `vfx_grafite.py`, `choque_antenas_3d.py`, `gotas_tentaculos.py` |

Clipes importados em glTF podem ter referência, recorte, velocidade e mistura editáveis. A animação já contida no asset permanece representada pelo clipe original. A edição de chaves autorais do Mário acontece nas pistas Python ligadas ao seu rig.

## 2. Como se edita

**Catálogo à esquerda.** Buscar uma ação pelo nome, escolher uma variante e abrir seu cenário. Ao trocar de ação, o editor deve avisar se a tomada tem alterações pendentes.

**Prévia 3D no centro.** Selecionar uma junta no modelo ou na árvore do rig. Arrastar o manipulador no eixo local, digitar o valor em graus e inserir uma chave no instante atual. Permitir orbitar, aproximar e voltar às vistas frontal e lateral. Sobreposições opcionais mostram a trajetória de uma mão, a raiz do corpo e as âncoras dos efeitos. Uma comparação entre a versão salva e o rascunho facilita julgar diferenças pequenas.

**Timeline embaixo.** Pausar, avançar quadro a quadro, fazer loop de uma seleção e editar chaves, valores e curvas. Eventos pontuais aparecem como marcadores. Janelas de efeito, como o intervalo de faíscas do fone, aparecem como trechos com início e fim. A timeline mostra segundos e quadros na taxa escolhida. Na dança, pode alinhar à grade de batidas. A taxa da prévia e a grade visual são independentes do tempo em que os dados foram gravados.

**Inspetor à direita.** Exibir campos da seleção, com unidades e limites da implementação. Uma junta mostra rotação. A respiração mostra sua curva e intensidade. Um efeito mostra sua âncora e propriedades de emissão. Cada arraste completo gera uma operação de desfazer. O atalho de salvar grava o rascunho validado no projeto.

Exemplo de uso. Abrir **Fone com problema**, pausar na antecipação, ajustar o ombro visto de lado e adiantar o estouro na pista de efeitos. Repetir o trecho, conferir se a faixa de faíscas acompanha o fone e testar uma interrupção pelo mouse durante o gesto. Salvar quando a cena isolada e a transição estiverem certas.

### Composição visual da janela

A referência é uma janela de autoria desktop com o Mário ocupando a maior área contínua. Os tamanhos abaixo são pontos de partida em pixels lógicos do Qt. A divisão entre áreas é redimensionável e a janela lembra as larguras e a altura escolhidas.

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Fone com problema •   Desfazer  Refazer   Tomada | Em contexto Salvar│
├────────────────┬───────────────────────────────────┬────────────────┤
│ Buscar ação    │ Perspectiva ▾   Local ▾   Enquadrar│ Ombro direito  │
│ Idles          │                                   │ Rotação local  │
│ Respiração     │            Mário em 3D            │ X   28.0°   ◇  │
│ Dança          │         + eixo da seleção         │ Y  −56.0°   ◆  │
│ Tentáculos     │                                   │ Z   42.0°   ◇  │
│ Reações        │                                   │ Curva ▾        │
│ VFX            │                                   │                │
├────────────────┴───────────────────────────────────┴────────────────┤
│ ◀ Quadro   ▶ Reproduzir   Quadro ▶   Loop       3.95 s   Quadro 237  │
│ Pistas                  2 s         3 s         4 s         5 s      │
│ ▾ Ombro direito          ◆───────────◆─────────────◆                 │
│   Faíscas do fone                              [━━━━━━]             │
│   Estímulos                        Clique ◆                         │
└─────────────────────────────────────────────────────────────────────┘
```

- **Barra superior, cerca de 48 px.** Nome da tomada e variante à esquerda, desfazer e refazer próximos, alternância entre modos e botão **Salvar** no mesmo lugar em qualquer cena. O marcador de alteração tem rótulo acessível. Uma confirmação discreta mostra o sucesso da gravação. Erros ficam visíveis com a ação disponível, como recarregar a versão externa ou tentar gravar novamente.
- **Catálogo, cerca de 220 px.** Campo de busca no topo, famílias recolhíveis e itens com nomes de ação. Buscar por “fone” encontra tanto a cena quanto seus efeitos, com indicação da família. Abrir uma ação enquadra o personagem, revela suas pistas relevantes e posiciona o cursor no começo. A busca e o teclado chegam aos mesmos itens que o mouse.
- **Viewport, área central expansível.** Fundo cinza neutro com contraste suficiente para ver a silhueta, o contorno e as partículas. Por padrão aparecem o modelo, a câmera e os controles da seleção. Grade, ossos, contatos, âncoras, trilhas e fundo de comparação ficam no menu de exibição. Uma pequena indicação no canto mostra se o usuário está em perspectiva, frontal ou lateral. A câmera do companion pode ser restaurada em um clique para conferir o enquadramento do desktop.
- **Inspetor, cerca de 300 px.** Cabeçalho com o nome da seleção e campos em ordem de uso. Valor, unidade, estado da chave e comando de redefinir ficam na mesma linha. Selecionar um efeito mostra sua âncora, o instante do disparo e sua aparência. Selecionar uma faixa de respiração mostra ciclo, curva e contribuições por parte do corpo. Com seleções múltiplas, indicar valores diferentes e aplicar alterações apenas aos campos compartilhados.
- **Timeline, cerca de 240 px de altura inicial.** Transporte fixo no topo, nomes das pistas fixos à esquerda, régua e conteúdo roláveis. Losangos marcam chaves, faixas marcam durações, e marcadores identificam estímulos e disparos. A distinção é por forma e texto, com cor como apoio. Abrir o gráfico de curvas usa a própria área da timeline e mantém o cursor no mesmo instante.

A proposta visual usa **Inter** para a interface e algarismos tabulares para valores e tempo. O tema inicial é escuro, com painéis em grafite, texto claro e uma cor de destaque reservada para seleção e foco. Pistas secundárias mantêm contraste para leitura. Ícones de transporte têm área clicável maior que o desenho, rótulo acessível e dica com atalho. Quando a janela encolher, catálogo e inspetor podem recolher e reaparecer pelo teclado. Em escala alta do Windows, a timeline pode rolar e o viewport continua acessível.

### Gestos, precisão e retorno visual

| Intenção | Interação | O que a interface confirma |
| --- | --- | --- |
| Selecionar uma junta | Clicar na malha ou escolher na árvore do rig | Realce no modelo, pista selecionada e nome correspondente no inspetor |
| Entender uma pose | Orbitar com botão central, deslocar com modificador e aproximar com a roda | Indicador de vista e enquadramento recuperável. A câmera também tem controles clicáveis |
| Ajustar exatamente | Arrastar um eixo local ou digitar um ângulo. Confirmar com Enter ou cancelar com Esc | Pose atualizada e valor mostrado em graus. O arraste começa após selecionar explicitamente o manipulador |
| Registrar uma pose | Acionar o losango do campo ou o comando de inserir chave | Chave visível no instante atual. O estado indica quando o valor está interpolado ou tem chave naquele instante |
| Alterar timing | Mover uma chave ou borda de faixa, com encaixe opcional na régua, numa chave ou numa batida | Linha de encaixe e instante exato durante o arraste. Um campo numérico oferece o mesmo ajuste |
| Conferir uma reação | Agendar um estímulo na timeline ou acioná-lo na prévia em contexto | Marcador do estímulo e indicação do comportamento ativo, inclusive quando perdeu prioridade |
| Inspecionar VFX | Selecionar um marcador ou faixa e voltar ao instante do disparo | Âncora destacada e efeito recriado no momento correspondente |

Espaço controla reprodução quando o foco está na prévia ou na timeline. Setas avançam ou voltam um quadro na timeline. Ctrl+Z, Ctrl+Shift+Z e Ctrl+S operam sobre o documento. Campos de texto conservam a navegação e edição próprias. Tab percorre controles na ordem visual com foco visível. Qualquer ação essencial executada por arraste também tem comando ou campo pelo teclado. A autochave, se habilitada, fica visível no transporte. Com ela desligada, uma manipulação é uma alteração provisória de pose, sinalizada até ser inserida como chave ou descartada. Reproduzir, trocar de cena ou salvar com uma pose provisória exige resolver essa alteração para evitar perda silenciosa.

### Tarefas de referência para a V1

- **Respiração.** Em repouso, abrir a curva, aumentar a contribuição do peito e reduzir a dos ombros. Comparar os ciclos lado a lado no tempo e passar para uma reação para ver se a respiração ainda tem a presença desejada.
- **Dança.** Definir BPM no transporte, encaixar um acento na batida, comparar duas frases e inserir uma soltura no roteiro para ouvir e ver como o groove cede à reação.
- **Tentáculos.** Selecionar a ponta ou a âncora da porta na vista lateral, editar trajetória ou atraso, posicionar um obstáculo no cenário e voltar ao quadro de contato. A sobreposição distingue a trajetória pretendida da posição resolvida, com traços e rótulos.
- **Reações e efeitos.** Posicionar um clique no roteiro, revisar antecipação e recuperação, mover o início de um efeito e conferir o resultado em velocidade normal e quadro a quadro.

## 3. Como o editor preserva a atuação

O editor trabalha sobre as três camadas do manual canônico. A agência escolhe quando agir. O núcleo artístico dá forma à ação. A camada tátil resolve a interação real com o desktop. No ensaio, é possível escolher uma ação e fornecer estímulos conhecidos. No companion, o controlador continua escolhendo, negociando e interrompendo ações com as regras já usadas pelo Mário.

Cada cena tem dois modos de prévia. **Tomada** facilita ajustar rapidamente uma ação, inclusive com canais isolados. **Em contexto** passa pelos caminhos normais de seleção, mistura e interrupção, usando um roteiro de estímulos. Uma pose bonita sozinha pode perder força quando entra sobre caminhada, dança ou arraste. A tomada ajuda a encontrar o ajuste, e a execução em contexto verifica seu efeito no personagem.

Os 12 princípios atuam juntos em cada ação. No susto do fone, a pose preparatória, a silhueta legível e a direção do olhar ajudam a encenar o problema. O tempo entre aviso, estouro e recuo vende a reação. Os arcos do braço, a desaceleração, a compressão do corpo e o atraso do fio mantêm a atuação contínua e com volume. A troca entre bloquear poses e desenhar uma passagem diretamente ajuda a julgar o exagero, o gesto secundário e o apelo do conjunto. A avaliação é visual, com a ação inteira, suas transições e vistas que revelem a profundidade.

## 4. Arquitetura de execução e prévia

- **Interface PySide6.** A janela do editor é uma ferramenta de autoria. A interface envia comandos semânticos, como selecionar uma junta, alterar uma chave, posicionar o cursor no tempo ou disparar uma reação. Atualizações durante um arraste podem ser agrupadas por quadro.
- **Prévia Panda3D.** A proposta é uma saída de render dedicada que reutiliza rig, materiais, efeitos e aplicação de poses do companion. Começar com uma janela Panda comum, sem o estilo transparente do overlay, permite validar o reaproveitamento antes de escolher a integração definitiva do viewport com o Qt. O núcleo puro continua livre de importações de Qt, Panda3D e Win32.
- **Composição compartilhada.** O editor e o companion amostram as mesmas pistas e usam as mesmas regras de mistura e prioridade. O primeiro ponto de integração de cenas de idle é `amostrar_cena_idle`, já consumido pelo controlador. No editor, um rascunho em memória substitui os valores autorais antes da amostragem. As teclas de edição operam sobre dados autorais, e o viewport permite inspecionar a pose final composta.
- **Rig e unidades.** Preservar nomes e hierarquia do glTF. Juntas usam eixos locais, com conversão na fronteira que já alimenta o rig. Exibir graus no inspetor e manter a representação interna de cada consumidor. Ancorar VFX no nó escolhido e aplicar o deslocamento no espaço indicado. Trajetórias de mãos e pontas de tentáculo devem ser verificáveis na cena em 3D.

### Estado e fluxo de uma edição

O documento em memória contém os valores autorais carregados, o rascunho e seu histórico de edição. Seleção, câmera, zoom e posição do cursor ficam no estado da janela. Partículas, detecção de borda, contatos e estado do controlador pertencem à sessão de prévia. Assim, girar a câmera ou voltar um quadro pode redesenhar a cena sem sujar o documento nem criar uma entrada em **Desfazer**.

Cada cena liga identidades estáveis de suas pistas aos consumidores existentes. Uma pista de junta identifica o nó, o canal, o domínio de tempo e as chaves com interpolação. Uma pista de efeito identifica a âncora, o disparo ou intervalo e os parâmetros aceitos pelo emissor. Um controle procedural identifica o valor e as unidades que a rotina espera. O catálogo também associa a ação a um roteiro de ensaio e ao ponto do controlador que a executa. Isso permite que timeline e inspetor editem o mesmo valor, com validação idêntica.

Ao arrastar uma chave de ombro, o Qt manda o novo instante para a edição provisória. O editor limita o tempo ao domínio da pista e aplica o encaixe escolhido. A prévia recebe a revisão mais recente do rascunho e amostra o clipe no cursor usando a interpolação do runtime. O mixer combina a pose com os demais canais e o Panda atualiza nós, malhas e efeitos. Ao soltar, a operação registra o instante anterior e o novo como uma única ação de desfazer. Esc restaura o valor que existia no início do arraste. Alterações de duração precisam validar as chaves e eventos na borda antes de confirmar. Reduzir uma duração com eventos fora do novo limite deve mostrar quais itens precisam ser movidos ou removidos.

Uma mudança de cenário ou um pedido de reprodução carrega a revisão do documento e o instante solicitado. Se a integração escolhida usar um processo separado para o Panda3D, a mensagem carrega esses identificadores e o retorno informa qual revisão e instante foram renderizados. A interface descarta retornos de pedidos vencidos. Durante arraste rápido, posições intermediárias podem ser agrupadas, preservando sempre o último pedido e o valor confirmado. O transporte continua utilizável durante a reconstrução de uma tomada pesada, com indicação visível do instante em processamento.

### Como os canais chegam ao runtime

1. **Poses e curvas.** Os dados persistem no domínio de tempo nativo. A prévia converte a posição da régua para a fase ou os segundos esperados pelo amostrador. O resultado segue pelo mixer e pela cinemática do rig. A transformação de exibição do gizmo é calculada pela hierarquia, preservando os eixos locais do nó.
2. **Respiração e dança.** A rotina procedural avalia a curva ou os parâmetros editados. Na dança, o relógio de batidas fornece posição e intensidade. O mixer recebe a contribuição pelos canais existentes, de modo que isolar uma pista no viewport mude somente a visualização e a tomada em contexto mostre o peso real.
3. **Tentáculos e reações.** O cenário fornece estímulos no mesmo formato usado pelo limite do controlador. A coreografia e as restrições avançam com o passo da simulação. A trajetória autoral é a entrada desse cálculo. O resultado resolvido vai para o rig ou para a geometria dos tentáculos e pode divergir da trajetória desenhada quando uma porta ou um obstáculo interfere.
4. **Efeitos.** Marcadores e faixas alimentam os disparos do runtime. Para um disparo pontual, cruzar o instante uma vez cria a emissão. Uma faixa fornece seu estado ativo a cada passo e pode ter ações de entrada e saída. O emissor localiza a âncora na pose composta. Ao editar um disparo já passado, reconstruir a prévia desde um estado anterior a ele para que o efeito tenha a idade e a posição corretas.
5. **Validação em contexto.** Um roteiro pode injetar uma entrada num quadro exato para medir timing e mistura. A janela real verifica o que depende de Win32, DPI, foco e mouse nativo. As duas provas têm pontos de entrada próprios e observam a mesma lógica de animação.

### Relógio e reprodução

Curvas e poses que dependem apenas do tempo podem ser amostradas diretamente. Partículas, colisões, contatos e entradas dependem do que aconteceu antes. Ao mover o cursor para trás ou saltar adiante em uma tomada com simulação, reiniciar do estado inicial e repetir, com passo fixo, os estímulos até o instante solicitado. Usar a mesma semente quando houver sorteio. Durante o ensaio com música, a grade ou a sequência gravada de batidas fornece entradas reproduzíveis. O áudio ao vivo serve para a prova final de sincronização.

Ao abrir uma cena, o roteiro deve fixar variante, condições iniciais e entradas, como posição do cursor, batidas ou obstáculo. A passagem pelo começo do loop também precisa reinicializar emissores, contatos e detectores de disparo, evitando partículas acumuladas e reações duplicadas. Armazenar pontos intermediários da simulação pode ser avaliado se a medição mostrar atraso ao reposicionar o cursor em cenas longas.

## 5. Gravação direta em Python

A proposta é usar `src/sejoga/animacao/animation.py` como módulo novo de dados autorais gravados pelo editor. Os módulos atuais importam os dados de que precisam e continuam executando a lógica que já possuem. Os campos podem representar pistas de poses, curvas de intensidade, janelas de efeito e parâmetros de uma rotina procedural. Fórmulas de respiração, regras de prioridade e resolução de contato permanecem em seus módulos.

O arquivo gerado deve ser legível em revisão de Git. Usar nomes estáveis para cenas, pistas e nós, ordem determinística e precisão numérica suficiente para que abrir e salvar novamente preserve o resultado. Cada pista declara seu domínio de tempo, como segundos ou fase normalizada, e seus valores usam as unidades esperadas pelo consumidor. O editor abre os dados gerados como literais validados. O companion os importa diretamente como Python, sem exportação ou conversão intermediária.

Ao salvar, validar nós e âncoras existentes, tempos finitos e ordenados, durações, unidades e parâmetros aceitos pelo consumidor. Conferir se o arquivo mudou externamente desde a abertura e preservar o rascunho em caso de conflito. Gravar em temporário exclusivo no mesmo diretório e substituir o arquivo após validar a gravação. Uma falha de escrita deixa o arquivo anterior disponível. Para validar o código gravado pela entrada normal do companion, abrir ou reiniciar a execução de teste com um perfil isolado por `SEJOGA_CONFIG_PATH`.

Importar as ações atuais por família para o módulo gravável. Onde o dado já estiver isolado, mover sua definição. Onde o valor estiver embutido em uma fórmula ou num disparo, extrair o parâmetro que o editor precisa controlar e manter a mesma execução. Em ambos os casos, a original e a migrada devem produzir a mesma atuação antes da primeira edição.

## 6. Sequência de implementação e aceite

1. **Percorrer o caminho inteiro com Fone com problema.** Conectar catálogo, pose, timeline, VFX, gravação em Python e reabertura no companion. Medir a resposta do visor durante a edição e conferir a cena em profundidade.
2. **Completar o catálogo da V1.** Integrar as demais cenas, a respiração, as frases de dança, a coreografia dos tentáculos, as reações, as transições e os efeitos. Conferir cada entrada do inventário com seus campos e cenário, incluindo combinações como dança cortada por arraste e tentáculo interrompido por contato.
3. **Validar a edição e o runtime.** Testar abrir, editar, desfazer, salvar e reabrir sem alterar valores fora da seleção. Cobrir arquivo inválido, mudança externa e falha de gravação. No viewport, repetir a mesma tomada após navegar para trás e conferir sincronismo, pose, partículas e contatos.
4. **Validar em janela real.** Usar `python tools/smoke_mouse.py`, com `--physics` quando a integração alterar física, arraste ou coordenadas. Conferir entrada nativa, aparência e transições no desktop. As provas automatizadas cobrem a integridade dos dados e da infraestrutura. O julgamento da atuação é visual.

O primeiro passo valida a arquitetura. A versão 1 fica pronta quando todas as famílias da seção 1 têm edição e prévia utilizáveis, e quando uma alteração gravada em Python chega ao companion pela execução normal. Definir as metas de latência do arraste e de reposicionamento da timeline após medir o protótipo no Windows, incluindo uma tomada com tentáculos e VFX ativos.

### Aceite visual e de usabilidade

Fazer sessões em Windows com a escala de tela a 100%, 125% e 150%, incluindo janela reduzida e monitores com escalas diferentes. Conferir foco, legibilidade, recorte de textos, alvos clicáveis, seleção precisa na malha, digitação e confirmação de valores numéricos e recuperação dos painéis recolhidos. Verificar os atalhos com foco no viewport, na timeline e num campo de texto. Usar somente teclado para repetir um ajuste de pose e tempo.

Nas primeiras sessões de uso, entregar quatro tarefas sem demonstrar os botões antes. Ajustar o ombro numa pose, atrasar a faísca, sincronizar um acento e rever o contato de um tentáculo. Observar se a pessoa acha a ação, entende o que está selecionado, distingue rascunho de versão salva e recupera um ajuste com **Desfazer**. Registrar erros, hesitações e caminhos abandonados. Repetir as mesmas tarefas depois de corrigir os pontos que interromperam o fluxo.

Medir tempo entre entrada e pose exibida durante arraste, cadência do viewport em reprodução e tempo até um quadro correto após um salto para trás. Registrar a máquina de referência, a escala do Windows, a resolução do viewport e a cena usada. Repetir com pistas de pose simples e com uma tomada completa de tentáculos, contatos e efeitos. A meta de interação deve ser acordada a partir dessas medições e comprovada novamente antes do aceite.
