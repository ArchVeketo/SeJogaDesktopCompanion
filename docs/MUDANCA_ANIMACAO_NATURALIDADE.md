# Mudança: movimentação natural do personagem (rascunho)

**Status:** em descrição. Nenhum código será alterado antes de este documento ser aprovado.
**Origem:** relato do autor, 10/11/2026.
**Estudo técnico de apoio:** `docs/ESTUDO_ANIMACAO_PROCEDURAL.md`.

## 1. Problema, nas palavras do autor

O modelo atual passa a impressão de estar **travado**. Quatro queixas:

1. Aspecto travado.
2. Idles sem sentido.
3. Movimentação incorreta.
4. Falta de naturalidade nos movimentos.

Vale para o **corpo inteiro**, não só os braços.

## 2. Sintomas (a preencher um a um)

Para cada sintoma, descrever em linguagem livre. Se não der para descrever, anexar
captura/GIF e escrever só "olha isso".

### 2.1 Aspecto travado
- Onde aparece: **em todos os estados**: idle, andar, arrastar, dançar e troca de uma ação para outra.
- O que se vê:
- O que deveria acontecer:
- Referência (jogo, vídeo, GIF):

### 2.2 Idles sem sentido
- Quais idles: **todos**.
- O que há de errado: **falta de expressividade corporal**. Para onde a cabeça olha
  já está correto. As descrições escritas de cada idle são boas e expressivas, mas **no
  render o corpo não entrega nada do que a descrição promete**.
- O que cada idle deveria "dizer": já está escrito nas descrições dos idles (a
  intenção existe; o problema é a execução visível).

**Leitura do problema (hipótese, ainda não verificada no render):** o gap entre
descrição e render sugere que a intenção está na especificação, mas se perde no
caminho até a tela. Causas candidatas, a confirmar uma a uma:
1. O rig só articula braços, cabeça e porta; tronco e pernas são blocos rígidos, então
   uma "postura" tímida, confiante ou ritmada não tem onde aparecer (ver seção 6).
2. A amplitude dos deltas de idle pode ser pequena demais para ler a 1x de escala.
3. A mola permanente do `PoseResolver` e os clamps podem estar atenuando ou atrasando
   os gestos autorados.
4. As camadas aditivas podem estar somando e anulando umas às outras.
5. O olhar funciona porque só usa a cabeça; o que falta é o resto do corpo
   acompanhar (peso, tronco, quadril, pés).

Como verificar: para um idle, comparar três coisas lado a lado: a pose pedida na
descrição, a pose de saída do `PoseResolver` e a captura do render. Onde a diferença
aparecer, está a causa.

### 2.3 Movimentação incorreta
- Quais partes: **os braços** são o maior problema hoje.
- Em que estado: vários. No hover os braços "abrem" na direção do mouse.
- Como é o erro: os braços ficam **rígidos numa posição**. Dobram, balançam, às vezes
  descem e sobem um pouquinho, mas tudo parece **engessado**, numa **pose de stickman**.
  Não há sensação de peso, de articulação solta nem de braço ligado ao ombro e ao
  tronco.
- Observação do agente (a verificar): no render, o braço é uma barra reta e os ombros
  são blocos rosa grandes e quadrados. Isso reforça o efeito "stickman": a silhueta
  não muda de forma quando o braço dobra. A solução provavelmente combina movimento
  (ombro e tronco participando) com a hierarquia encadeada (seção 6).

### 2.4 Falta de naturalidade
- Quais movimentos parecem robóticos:
- O que falta (peso, atraso, sobra de movimento, respiração, variação):
- Um movimento que já parece bom, para servir de régua: **nenhum no projeto**.
- Referência externa do autor: **Rain World**, mas com ressalva: o nível de camadas é
  diferente (corpo mole feito de pontos ligados por distância; o Mário tem partes
  rígidas). O autor também cita repositórios e demonstrações em Unity de animação
  procedural, ainda sem links.
- Como usar a referência: do Rain World aproveitar o **princípio** (esqueleto de
  pontos/ângulos com comportamento por código e resposta ao ambiente), não o visual
  mole. Para o Mário, o equivalente é: tronco encadeado, ombro que acompanha, mola
  por junta e IK para mãos e pés.
- **A definir:** juntar 2 ou 3 demos (repositório, vídeo, cena Unity) para servirem
  de régua visual. Sem isso, o critério "ficou natural" fica subjetivo.

## 3. Restrições já decididas (não reabrir sem motivo)

- Sem ossos com skin e sem Mixamo; animação continua procedural em nós rígidos.
- Constantes de ajuste ficam em `*_tuning.py`, com o porquê.
- Código novo em português, conforme `docs/CONVENCAO_PYTHON.md`.
- Validação visual por captura multi-ângulo; teste verde não prova aparência.
- Enxugar código só depois de a animação estabilizar.

## 4. Escopo desejado

- Dentro do escopo (a definir):
- Fora do escopo (a definir):
- Ordem de prioridade (a definir):

## 5. Critérios de aceite

Como o autor vai saber que melhorou. Preferir critérios que dá para ver ou medir.

- (a definir; ex.: "idle de 10 s sem pose repetida", "troca de estado sem tranco")

## 6. Passo 1 proposto: completar o rig do modelo

Proposta do autor: antes de melhorar os movimentos, **rigar o que está pendente**:
joelho, cintura, pernas, abdômen, peitoral, ombros e fones de ouvido.

### 6.1 Estado atual do modelo (verificado)

Fontes lidas: `assets/model/mario.gltf` (61 nós) e `assets/model/projetoMARIO.bbmodel`
(outliner do Blockbench, 43 elementos). Os dois concordam. As malhas se chamam só
`cuboid`, `cylinder`, `plane`..., então **não dá para saber pelo nome qual malha é
peitoral ou abdômen**; isso só se descobre abrindo o modelo no Blockbench.

Filhos diretos da raiz: `head`, `body`, `right-arm`, `left-arm`, `legs`,
`left-feet`, `right-feet`. **A hierarquia é plana**: cabeça, tronco, braços, pernas e
pés são irmãos. Girar o `body` não carrega braços nem cabeça. Hoje isso é compensado
por código (movimento conjunto ao redor do quadril, atraso de braço etc.).

| Região | Como está hoje | Pivô no Blockbench (y) | Limitação |
|---|---|---|---|
| Tronco | `body`: 1 nó, 2 malhas (cuboid + cylinder) | 7 | Sem cintura, abdômen e peitoral separados. |
| Pernas | `legs`: 1 nó, **1 malha** | 7 | Uma peça só para as duas pernas: sem perna esquerda/direita, coxa, canela ou joelho. |
| Pés | `left-feet`, `right-feet`: 2 malhas cada (cuboid + plane) | 4 | Irmãos da raiz, não filhos da perna. |
| Ombros | `shoulder`, `shoulder2`: 1 cuboid cada | 11 | São irmãos do antebraço dentro de `right-arm`/`left-arm`; o ombro não é pai do braço. |
| Braço | `right-arm` → `ant-arm` → `hand` → `fingers` | ombro 11; cotovelo x=4; mão x=6,5 | Cotovelo já tem nó. |
| Cabeça | `head`: 19 malhas soltas + `door` | 12 | Fones sem grupo próprio: estão misturados com a casca da cabeça. |

**Medidas da malha das pernas** (lidas dos vértices; unidades do Blockbench, onde 16
unidades = 1 do GLTF): a única malha de `legs` tem 28 vértices e 26 faces, ou seja,
**não é uma caixa simples**. Mede cerca de 10 de largura, 5,5 de altura e 5,9 de
profundidade, e é **mais larga que o tronco** (cerca de 6). Pelo render, essa malha é o
**short roxo** do personagem, com os tênis cinza logo abaixo. O personagem é um chibi:
**quase não existe canela visível**.

Consequência para o joelho: o joelho "sutil" não é uma perna longa que dobra. É uma
perna curta em que o conjunto short + pé flexiona um pouco. Isso combina com a decisão
de manter a proporção original.

Outros achados no render (captura de aceno):
- **Antenas:** os pares `pyramid` + `sphere` de `head` são as duas antenas com bolinha
  no topo, não fones. Também merecem nó próprio, por serem ótimas para movimento
  secundário.
- **Fones:** os fones de verdade são as peças grandes laterais e o arco sobre a cabeça.
- **Ombros:** são blocos rosa grandes e quadrados, que escondem a junção com o braço.
- **Fio preto:** desce dos fones até um objeto no peito. Não identifiquei de qual malha
  ele vem.

### 6.2 O que "rigar" significa neste projeto

Continua valendo a decisão registrada: **sem ossos com skin e sem Mixamo**. Rigar aqui
é **criar nós novos (grupos) no Blockbench, com pivô na articulação, e reexportar o
GLTF**. A junta passa a existir como nó, e o código (molas, limites, IK) a controla.

Cada nó novo exige também mudanças em código, por exemplo:
- incluir o grupo em `ALL_GROUPS` (`nucleo/rig.py`);
- criar a entrada em `TENSAO_POR_JUNTA` (`spring_tuning.py` falha na importação se
  faltar grupo);
- entrada no mapa do rig (`rig_mapa`) e no inventário de partes;
- renderer, contorno, colisão de membros e IK das pernas (`lower_body.py`), que
  hoje assumem a estrutura atual. Não li esses arquivos.

Regra do projeto: **nomes de nós existentes nunca mudam.** Nós novos podem entrar.

### 6.3 Lista pendente e proposta de nós

Nomes são sugestões; a decisão é do autor (6.4, item 3).

| Item | Hoje | O que criar | Tipo de junta | Observação |
|---|---|---|---|---|
| Cintura / quadril | Pivô de `body` e `legs` no mesmo ponto | Nó de pelve/cintura | Esférica, limitada | Base para a inclinação do corpo todo. |
| Abdômen | Dentro de `body` | Dividir `body` | Dobradiça/torção leve | Precisa identificar a malha no Blockbench. |
| Peitoral | Dentro de `body` | Dividir `body` | Dobradiça/torção leve | Os ombros e o pescoço devem nascer dele. |
| Ombros | Grupo com 1 cuboid, irmão do antebraço | Fazer o ombro um nó real (clavícula) | Esférica | Decidir se o braço passa a ser filho do ombro. |
| Pernas | 1 malha | 2 pernas, cada uma com coxa e canela | Quadril esférico | Divisão de malha: trabalho manual de geometria. |
| Joelho | Não existe | Pivô entre coxa e canela | Dobradiça, proposta 0 a 140 (a validar) | Já listado no mapeamento do rig como `A_CONFIRMAR`. |
| Fones | Malhas soltas em `head` | Grupos por fone (+ arco, se houver) | Esférica pequena, só para atraso | Os 4 planos cruzados `mesh11–14` estão ocultos por código; melhor removê-los do asset. |

### 6.4 Decisões

| # | Tema | Decisão do autor (10/11/2026) |
|---|---|---|
| 1 | Hierarquia | **Encadeada.** Quadril → cintura → peitoral → cabeça e braços (detalhe da cadeia ainda a desenhar). |
| 2 | Quem edita o modelo | **O agente**, e se não conseguir, "vamos dar um jeito" (ver 6.5). |
| 3 | Nomes novos | **Português.** O padrão novo do projeto é modelar quase tudo em português; alguns termos técnicos ficam em inglês (convenção Python do projeto). Nós existentes não são renomeados. |
| 4 | Migração | **Aditiva.** `body` e `legs` ficam como contêineres e ganham filhos. |
| 5 | Pernas | **Manter a proporção original; joelho sutil.** |
| 6 | Cintura e abdômen | **Inclinam e torcem** (3 eixos), com limites pequenos de partida e movimento distribuído pela cadeia (cintura, abdômen, peitoral). Valores exatos a validar no render. |
| 7 | Giro de corpo / ficar de costas | **Reabrir agora**, usando a torção e a inclinação da cadeia (ver seção 7). |
| 8 | Locomoção | O Mário pode **mudar de lugar e continuar caminhando pela tela**, "solto" no desktop (ver 8.5). De costas, ele **caminha para dentro da tela**: profundidade só visual, 3 níveis (perto, médio, longe), simulada por escala e altura (ver 8.5.1). |
| 9 | Porta e tentáculos | **Permanecem no modelo e continuam funcionando em qualquer animação.** Dançar ou fazer outra interação não os desliga (ver 8.2). |
| 10 | Idles | **Todos** os idles mais recentes de Animal Crossing **substituem os atuais**; as personalidades antigas deixam de existir (ver 8.4). |
| 11 | Nomes e pivôs do rig | **O agente decide**, seguindo a convenção em português e registrando as escolhas no documento para revisão do autor. |
| 12 | Escopo dos pacotes | **Só o pacote principal** (Olhar a tela) nesta fase; os outros ficam para depois (ver 8.3). |
| 13 | Acionamento para teste | **O menu precisa de entradas para disparar a animação quando quiser** (ver 8.9). |

Consequência da decisão 1: encadear significa **reparentar** nós existentes
(por exemplo, `right-arm` deixa de ser filho da raiz e passa a ser filho do peitoral).
Isso muda o espaço em que cada pose é aplicada (local do pai, não da raiz). O código
que assume nós irmãos precisa ser auditado: composição de poses, IK dos braços e das
pernas, clamps, colisão de membros, medições do rig, contorno e renderer. Em geral o
GLTF aceita isso sem problema; o trabalho é no código.

Consequência da decisão 3: conflito de nomes a resolver. Os nós existentes continuam em
inglês (`head`, `body`, `legs`, `ant-arm`), e os novos entram em português. Isso cria um
modelo com dois idiomas por um tempo. Alternativa a decidir: manter um mapa
"nome do GLTF → nome em português" no código, para o resto do projeto falar só
português.

### 6.5 Como o agente pode editar o modelo (viabilidade)

O autor quer que o agente faça a edição do modelo. O que já sei:

- O `.bbmodel` é **JSON** (formato `free`, malhas com vértices e faces, hierarquia no
  `outliner`). Criar grupos, mover elementos entre grupos e ajustar origens (pivôs) é
  edição de dados. Cortar uma malha exige código de geometria.
- O GLTF atual foi gerado pelo exportador do Blockbench 4.12.4.
- O projeto já tem precedente de GLTF gerado por código: `tools/build_tentacle_model.py`
  (validado pela Khronos, zero erros).
- Os arquivos do modelo estão no git (`assets/model/`), então há backup e diff.
- Python 3.12 roda neste ambiente (testado no `.venv-build`).
- A malha das pernas é uma peça única de 28 vértices (short), então o corte em duas
  pernas exige preservar UV e vértices com cuidado.

Caminhos possíveis:

| Opção | Como | Vantagem | Risco |
|---|---|---|---|
| A | O agente edita o `.bbmodel` por script; o autor abre no Blockbench, confere os pivôs e exporta o GLTF | O Blockbench continua sendo a fonte; 1 passo manual curto | Depende do autor para exportar |
| B | O agente edita o `.bbmodel` **e** gera o GLTF por script | Totalmente automático e verificável | O GLTF gerado pode divergir do exportado (nomes, textura embutida, escala) |
| C | O agente edita só o GLTF | Mais rápido | O próximo export do Blockbench apaga o trabalho; **evitar** |

Recomendação: começar por **A** e usar **B** como verificação e plano de contingência
(o "dar um jeito" do autor): se a exportação manual virar gargalo, o GLTF passa a sair
por script.

Primeira tarefa de viabilidade, que **não altera o modelo**: um script só de leitura que
gera um render do repouso com **cada malha em cor diferente e numerada**, e uma tabela
malha → região (tronco, short, tênis, fone, antena, ombro...). Isso resolve o problema
das malhas chamadas `cuboid`/`cylinder` e diz exatamente o que precisa ser cortado.

### 6.6 Ordem sugerida

1. Decisões 1 a 5 já tomadas (6.4). Falta só a decisão 6 (cintura e abdômen).
2. Rodar o script de leitura (6.5) e mapear qual malha é peitoral, abdômen, short,
   tênis, fone e antena. Desenhar a cadeia final de nós, em português.
3. Rig aditivo mínimo no Blockbench: pernas separadas com joelho, tronco dividido,
   fones agrupados. Pivôs conferidos com eixos visíveis.
4. Ajustar o código para reconhecer os nós novos **sem animá-los ainda**.
5. Só então animar (idles, andar, naturalidade).

Critério de aceite do Passo 1:
- Captura do repouso **idêntica** antes e depois (diff de imagem), em pelo menos
  frente e três quartos.
- Cada nó novo gira em torno do pivô certo (prévia com eixos).
- Nenhum teste existente quebra; tabelas de tensão e inventário cobrem os nós novos.

## 7. Giro de corpo: virar, olhar para trás, ficar de costas

O autor deixou travado de propósito o giro do corpo para trás, esperando o momento certo.
A proposta é que esse momento seja agora, com o sistema de torção e inclinação da cadeia.

### 7.1 Estado atual (verificado no código)

- `GiroCorpo` (`body_motion.py`) calcula um ângulo suavizado por mola, **limitado a ±90°**
  (`LIMITE_GRAUS`), com zona morta no olhar. O comentário do código diz que giro amplo
  de costas e locomoção dependem de decisão do autor, de um "Plano B de fullscreen" e de
  teste na GPU.
- O renderer aplica esse ângulo num nó acima do modelo (`body_facing`), girando o
  **modelo inteiro, rígido**, em torno de um pivô vertical. Não há articulação nesse giro.
- `foco_atencao.py` registra que virar de costas e locomoção são fases posteriores.
- O comentário de `GiroCorpo` avisa: subir o limite além de 90° "tende a reintroduzir
  franja/flicker" e pode sair do envelope da janela dinâmica.
- Existe `tools/preview_anim.py --camera tras`, que permite ver o personagem de costas.

### 7.2 Ideia: virar em camadas, não de uma vez

Com a cadeia articulada, "olhar para trás" deixa de ser um giro único do modelo e vira
uma **sequência**, como num corpo vivo: primeiro os olhos e a cabeça, depois o tronco
por torção, só no fim o corpo todo e os pés.

| Nível | O que gira | Resultado | Depende de |
|---|---|---|---|
| 1 | Só a cabeça | Olha para o lado, até cerca de 80° | Já existe |
| 2 | Cabeça + torção de peitoral, abdômen e cintura | Olha **por cima do ombro**, pés de frente | Rig encadeado (Passo 1) |
| 3 | Giro do corpo inteiro (`body_facing`) até 180° | Fica **de costas** para a câmera | Lógica de pés e verificação visual das costas |
| 4 | Transição frente ↔ costas | Vira de verdade, por um dos lados, com antecipação | Níveis 2 e 3 |

O nível 2 já responde "olhar para trás" sem ficar de costas, então pode vir antes do 3.
Uma conta de ordem de grandeza (não medida): cabeça em torno de 80° mais torção da
cadeia em torno de 100° chegam perto de olhar para trás sem girar os pés.

### 7.3 O que precisa ser verificado antes de liberar costas

1. **Como o personagem aparece de costas.** A textura e as malhas foram pensadas para a
   frente (porta, adesivos, rosto). Gerar capturas de costas e três quartos e julgar.
2. **Franja rosa do color key** nas bordas, que já é um problema pendente e piora com
   outra silhueta.
3. **Envelope da janela:** o tamanho dinâmico da janela precisa caber o corpo girado
   com os braços estendidos.
4. **Porta e tentáculos:** saem pela frente. De costas, o que acontece com a espiada,
   a dança e o espirro?
5. **Ângulo de 180°:** a mola atual trata o ângulo como número simples. Passando de 180°
   ela gira pelo caminho longo; precisa de "caminho mais curto" (seção 4.8 do estudo).
6. **Pés e apoio:** girar o modelo inteiro com os pés presos ao chão faz o pé deslizar
   se não houver passo. Decidir se o passo de giro entra já ou fica para depois.
7. **Picking e hover:** acerto do mouse e olhar com o personagem de costas.

### 7.4 Perguntas abertas

1. **O que dispara o giro?** Cursor atrás do personagem, idle de curiosidade, música,
   barulho, acordar, outro?
2. **Quais estados podem ficar de costas?** Só idle, ou também dança (por exemplo, de
   costas na caixa de som, como já descrito no guia de dança)?
3. **Quanto tempo ficar de costas** e como voltar (olha por cima do ombro e volta, vira
   completo)?
4. ~~As costas do personagem são aceitáveis como estão?~~ **Respondida pelo autor:**
   a aparência das costas é aceitável. A expectativa é que os eixos novos (torção e
   inclinação) deixem a animação das costas mais natural. Ainda vale conferir por
   captura os itens 2 a 5 de 7.3.

Respostas às perguntas 1 e 2 estão na seção 8 (gatilhos dos pacotes de animação).

## 8. Pacotes de animação e interações aleatórias

O autor já tinha pensado num sistema de **pacotes (bundles) de animação**, ainda
pendente. Nesta seção fica a descrição dele e o que ela exige do resto do trabalho.

### 8.1 A ideia, nas palavras do autor

- Haveria cerca de **3 ou 4 interações aleatórias** (número a definir).
- Uma delas: o Mário **olha para a tela**, ou seja, para o que o usuário está fazendo
  "atrás" do próprio mascote. Para isso ele olha, vira e fica de costas.
- Gatilhos possíveis:
  - o idle curioso (que será substituído, ver 8.3);
  - **música**: a ideia é o Mário cuspir/espirrar as caixas de som para fora da porta;
  - **dança**: breakdance e head bopping, em que ele deveria **encostar de lado** na
    caixa de som.
- As pernas e os pés têm de ser animados ativamente: para se mover para trás o Mário
  precisa **andar**, não só girar.
- Ao andar na horizontal, o corpo deve ficar **de lado (perfil)**. Andar de lado
  olhando para a frente seria estranho.

### 8.2 O que é um "pacote" (proposta de vocabulário)

Um pacote é uma unidade nomeada, escolhida e executada pelo sistema de comportamento.
Proposta do que cada pacote declara:

| Campo | Para quê |
|---|---|
| Nome | Identificar o pacote. |
| Gatilhos | O que pode iniciá-lo (aleatório, música, dança, clique, tempo parado). |
| Condições | Quando não pode rodar (arrastando, caindo, usuário digitando, outra dança ativa). |
| Fases | Preparação → ação → sustentação → recuperação (mesmo modelo dos gestos autorados). |
| Recursos que exige | Pernas e pés ativos, giro de corpo, porta, tentáculos, caixa de som. |
| Prioridade e interrupção | Quem passa na frente de quem, e como sai de forma limpa. |
| Peso e resfriamento | Chance por personalidade e tempo mínimo antes de repetir. |

O agendador que escolhe entre os pacotes é o descrito na seção 4.6 do estudo
(`docs/ESTUDO_ANIMACAO_PROCEDURAL.md`): sorteio ponderado, com resfriamento, sem repetir
duas vezes seguidas, e levando em conta a atenção do usuário.

### 8.3 Pacotes candidatos

| Pacote | Gatilhos | Exige | Esboço das fases |
|---|---|---|---|
| Olhar a tela | Aleatório, curiosidade no idle | Torção da cadeia, giro de corpo, pés ativos | Olha por cima do ombro → vira pelo lado com passos → fica de costas observando → volta |
| Entrada musical | Música detectada | Porta, espirro lateral, tentáculos (já descritos no guia de dança) | Antecipa → espirra → caixa sai e pousa → entra na dança |
| Dança: breakdance | Música + estilo | Pernas e pés, chão, tronco, giro | A definir com referências |
| Dança: head bopping encostado | Música + estilo | Giro de lado, contato com a caixa, pés firmes | Encosta de lado → balança a cabeça na batida → recupera |
| Idles de personalidade | Tempo parado | Corpo expressivo (Passo 1) | Ver abaixo |

A lista pode crescer ou encolher; o autor falou em 3 ou 4 interações.

**Escopo desta fase (decisão do autor): só o pacote principal.** Os demais pacotes só
serão pensados depois que tudo estiver resolvido. Em todo o documento, o "pacote
principal" é o **Olhar a tela** (o autor o usou como exemplo central; **confirmar**).
Isso não adia o agendador genérico da seção 4.6: basta ele existir de forma mínima para
o pacote principal.

**Regra de arquitetura (decisão do autor): porta e tentáculos não são recursos
exclusivos de um pacote.** Eles continuam existindo no modelo e funcionando durante
qualquer animação, inclusive dança e interações. Um pacote pode **pedir** algo a eles
(por exemplo, a entrada musical pede abertura da porta e saída dos tentáculos), mas
nunca os desliga nem espera por eles. O mesmo vale como proposta para fones e antenas
(movimento secundário sempre ativo).

Implicações:
- Porta, tentáculos, fones e antenas ficam numa camada própria e persistente (física e
  follow-through), independente da camada de estado/pacote.
- Com a hierarquia encadeada, eles herdam o movimento da cabeça e do tronco, o que dá
  inércia de graça. O sistema de contato dos tentáculos (cápsulas contra as caixas das
  peças sólidas) depende das peças do modelo e precisa ser reauditado quando o tronco
  for dividido.
- Com o corpo de costas, a porta e os tentáculos ficam voltados para longe da câmera.
  Eles continuam funcionando, mas ficam parcialmente ocultos pela cabeça. Isso é um
  efeito visual a conferir, não uma restrição.

### 8.4 Idles baseados em Animal Crossing

O autor pretende mudar os idles atuais e basear idles, animações e personalidades em
**Animal Crossing**, por ser um jogo muito expressivo.

O que sei do jogo (conhecimento geral e busca; **a conferir com vídeos que o autor
escolher**):
- Os moradores têm tipos de personalidade: Normal, Lazy (preguiçoso), Sisterly
  (irmã mais velha), Snooty (esnobe), Peppy (animado), Cranky (rabugento), Jock
  (esportista) e Smug (convencido).
- Cada tipo tem um conjunto próprio de **reações** (5 por tipo, segundo a wiki do
  jogo) e hobbies, o que dá identidade a cada um.
- A expressividade vem de **ações com propósito** (alongar, exercitar, ler, cochilar,
  olhar em volta), postura exagerada que mostra a atitude, e um repertório pequeno
  mas bem atuado.

Hoje o projeto tem nove personalidades de idle: calma, curiosa, brincalhona, tímida,
confiante, street, fighter, rhythm e stylish. **Decisão do autor:** os idles de
Animal Crossing **substituem os atuais**. Cada personalidade nova deve virar um
conjunto de pacotes e de parâmetros (amplitude, ritmo, amortecimento, probabilidade de
cada pacote).

O que a substituição toca no código (a conferir ao implementar):
- o enum `IdlePersonality` e tudo o que é indexado por ele (a tabela de respiração
  falha na importação se faltar entrada para alguma personalidade);
- as poses autoradas de cada idle (`idle_clips.py`) e os deltas de idle;
- a escolha de personalidade em Configurações e no submenu da bandeja, e o valor salvo
  no TOML do usuário;
- testes e documentação que citam as nove personalidades.

**Decisões do autor (10/11/2026):**
- Entram **todos** os idles mais recentes de Animal Crossing (a versão mais recente da
  série, New Horizons), com todos os tipos de personalidade.
- As personalidades antigas **deixam de existir**; não há convivência.
- Referências: os vídeos ou GIFs mais recentes de animação de idle do jogo.

**Como a referência será usada.** Só consegui achar texto de wiki sobre as reações e
as personalidades, nada que descreva os idles quadro a quadro. Então a régua visual
tem de vir de **GIFs ou vídeos**. O ambiente tem Pillow e ffmpeg, então dá para
extrair os quadros de um GIF ou vídeo, montar uma folha de contato (um tipo de
personalidade por folha) e analisar poses, tempo e ritmo. Não consigo assistir a vídeo
em movimento; trabalho com quadros. Fluxo proposto: colocar os arquivos numa pasta do
projeto (por exemplo, `docs/referencias/animal-crossing/<tipo>/`), e eu extraio e
descrevo as fases de cada idle (preparação, ação, sustentação, recuperação).

**Migração do perfil salvo.** Como as personalidades antigas somem, quem tem uma delas
no TOML precisa de um fallback. Proposta de partida: valor desconhecido vira
"automática". A conferir ao implementar.

Em aberto: se a escolha "automática" continua existindo e se o autor quer fixar um tipo
na bandeja, como hoje.

### 8.5 Locomoção e orientação

Pontos que o autor levantou e o que eles implicam:

1. **Andar na horizontal = corpo de perfil.** Isso muda o papel do limite antigo de
   90° do `GiroCorpo`: o perfil passa a ser o estado normal de caminhada, não um caso
   extremo.
2. **Separar "para onde o corpo olha" de "para onde ele se move".** Hoje o
   mascote fica sempre de frente. Com perfil e costas, a direção de frente vira um
   estado próprio, com transição (virar antes de andar, virar ao parar).
3. **Virar para trás exige passos.** Girar de verdade pede pés e pernas ativos, com
   apoio, e não só rotação do modelo. É por isso que o rig de pernas, joelho e quadril
   vem antes.
4. **Pernas e pés são pré-requisito do pacote "Olhar a tela"** e das danças de chão.
   As pernas hoje são uma peça só (o short), então o Passo 1 precisa ser concluído
   antes.
5. **Solto no desktop (decisão do autor).** Ao virar de costas, o Mário pode **mudar de
   lugar e continuar caminhando pela tela**, como se estivesse realmente solto no
   desktop. Isso faz da locomoção autônoma um sistema de comportamento, não só uma
   animação:
   - ele escolhe **destinos** e anda até eles. **Decisão do autor:** os destinos são
     **aleatórios** ou **em direção ao mouse do usuário**, e a frequência é **rara**;
   - precisa respeitar a física de tela que já existe (apoio em topos de janela,
     queda, arraste), e ser interrompido por arraste e clique;
   - a velocidade da caminhada alimenta a fase do passo, a inclinação do corpo e o
     movimento secundário (fones, antenas, tentáculos).
   Não li o código atual de caminhada (`walk` e `run` existem como estados, e a
   locomoção em si está em `lower_body.py`/`leg_motion.py`); falta conferir o que já
   é autônomo e o que depende de entrada do usuário.

#### 8.5.1 Caminhar para dentro da tela (decisão do autor)

Quando o Mário está de costas para a câmera, ele **caminha para dentro da tela**, isto é,
se afasta do usuário. Isso dá três modos de locomoção:

| Modo | Corpo | Movimento na tela |
|---|---|---|
| Perfil | De lado (90°) | Esquerda/direita pelo desktop |
| De costas | Costas para a câmera | **Afasta-se para dentro da tela** |
| De frente | Frente para a câmera | Aproxima-se, volta para o plano da tela |

**Problema técnico:** a câmera é ortográfica e frontal (o projeto a usa para manter a
projeção dos pés consistente com os pixels da física). Em projeção ortográfica,
afastar-se não diminui o objeto nem o sobe na tela. A profundidade precisa ser
**simulada**.

Proposta: um parâmetro de profundidade `p` (0 = plano da tela, 1 = fundo máximo) que
aciona dois efeitos, calibráveis em `*_tuning.py`:
- **escala:** o modelo diminui conforme se afasta;
- **posição vertical:** os pés sobem na tela, como numa vista levemente de cima.

Pontos de atenção (não verifiquei como o renderer e a janela reagem a isso hoje):
1. **Física de tela.** O corpo físico usa pixels e apoia em topos de janela. A
   profundidade não existe nesse mundo. É preciso decidir se `p` é só visual (o corpo
   físico não muda) ou se mexe na posição da janela.
2. **Escala em tempo real.** A documentação do projeto diz que tamanho pede reinício.
   Escalar um nó do modelo dentro da janela existente evita redimensionar a janela, mas
   exige espaço livre acima do personagem para a subida. Alternativa: mover a própria
   janela.
3. **Raio de colisão, contorno e hit-test** dependem do tamanho do modelo; precisam
   acompanhar a escala.
4. **Contorno e franja do color key** mudam com a escala; conferir de costas e pequeno.
5. **Leitura do passo de costas.** Em vista traseira ou frontal, o balanço das pernas
   acontece na direção da câmera e quase não aparece. O que *aparece* é o **balanço
   lateral do peso**, a torção quadril/ombros em sentidos opostos, a subida e descida do
   corpo e o pé que levanta. Ou seja, caminhar de costas só fica convincente com a
   cintura, o abdômen e o peitoral articulados (decisão 6) e pernas separadas com joelho
   (decisão 5). Isso reforça a ordem do Passo 1.
6. **Fim da caminhada.** Ele fica pequeno e "longe" até sair do plano, ou volta andando
   de frente? Em aberto (ver 8.7).
7. **Oclusão.** O overlay fica sempre acima das janelas, então "dentro da tela" é só
   ilusão de escala e altura; ele não passa por trás de janelas. Se o autor quiser que
   ele passe por trás de janelas, é outra feature (z-order), fora deste escopo por ora.

**O que significa "mover a janela e o corpo físico".** O mascote tem três camadas que
hoje andam juntas:

1. **Corpo físico:** um círculo do Pymunk, em pixels absolutos do desktop. É ele que
   cai, quica e apoia nos topos das janelas do Windows.
2. **Janela do overlay:** a janela transparente do sistema (HWND) que mostra o
   mascote. Ela acompanha o corpo físico.
3. **Modelo desenhado:** o Mário 3D dentro dessa janela, com os pés posicionados em
   relação ao raio do corpo físico.

Duas formas de aplicar a profundidade:

| Opção | O que muda | Efeito |
|---|---|---|
| **A. Só visual** | Apenas o modelo desenhado: ele diminui e sobe **dentro** da janela. O corpo físico e a janela não saem do lugar. | A física continua igual (apoio, queda, clique, arraste funcionam como hoje). O Mário parece estar mais ao fundo do topo da janela. |
| **B. Física e janela** | O corpo físico sobe de verdade e seu raio encolhe; a janela do overlay sobe junto. | A janela não precisa de espaço extra acima. Mas o apoio em janelas precisa mudar: se o corpo sobe, a gravidade o puxa de volta para o topo da janela, então o "chão" de cada profundidade teria de subir junto. Mais pontos de código para mexer. |

**Recomendação: opção A.** Ela casa com o que o autor quer: no fundo, ele continua
apoiando em janelas e respondendo a clique e arraste sem regras novas de física, porque
o corpo físico nunca saiu do plano da tela. O custo é garantir espaço livre acima do
personagem dentro da janela para a subida (a janela dinâmica já tem um envelope próprio;
a conferir).

**Decisões do autor sobre a profundidade (10/11/2026):**
- **Opção A aprovada:** a profundidade é só visual (modelo dentro da janela); corpo
  físico e janela ficam no plano da tela.
- Afasta-se **pouco**, em **3 níveis de distância**: **perto, médio e longe**.
  Entre os níveis a mudança é animada (ele anda de um para o outro), não instantânea.
  Valores de partida sugeridos, a ajustar no render (não medidos):

  | Nível | Escala | Subida na tela |
  |---|---|---|
  | Perto | 100% (plano da tela, como hoje) | 0 |
  | Médio | cerca de 90% | pequena |
  | Longe | cerca de 80% | um pouco maior |

  A subida é uma fração da altura do personagem; o valor sai da calibração no render.
  "Perto" ser exatamente o plano atual é uma suposição; confirmar.
- Ao terminar, ele **volta andando de frente**.
- No fundo, ele **ainda apoia em janelas** e **responde a clique e arraste**.
- Se for arrastado enquanto está no fundo, ele é **puxado para a frente** (a profundidade
  volta a zero) com uma **animação de ser puxado**. Com a opção A isso é simples: o corpo
  físico já acompanha o cursor no arraste, então só a profundidade visual precisa
  animar de volta ao plano, com a reação do corpo (esticar, pernas penduradas, atraso de
  braços) já existente no arraste.

### 8.5.2 Acionamento manual para teste (menu)

Como os gatilhos reais serão raros e aleatórios, o autor pediu entradas no menu para
**disparar a animação quando quiser** e poder testar.

O menu existente é o **menu da bandeja**, montado em `render/window.py` (por volta das
linhas 879 a 960). Ele já tem o padrão de que precisamos: o submenu "Prévia de dança
(sem som)" (Head bob, Hip hop, Rock, Breakdance), o submenu "Personalidade do idle" e
as ações "Acenar", "Soltar os ombros", "Mostrar tentáculos" e "Espirro de tentáculos".
O clique direito no mascote hoje faz carinho, então não é um menu; por isso o "menu de
contexto" do autor é, pelo que vi, o da bandeja (**confirmar**).

Entradas propostas (nomes provisórios), todas ligadas a um único ponto de entrada no
controlador de animação, como as ações atuais:

| Entrada | O que faz |
|---|---|
| Olhar a tela | Dispara o pacote principal (olhar por cima do ombro, virar, ficar de costas observando, voltar). |
| Profundidade: perto / médio / longe | Leva o Mário ao nível pedido, animando a caminhada até lá. |
| Caminhar para o fundo | Vira de costas e caminha para dentro da tela, um nível de profundidade por vez (perto → médio → longe). |
| Caminhar para a frente | Volta andando de frente, um nível por vez (longe → médio → perto). |
| Caminhar para o lado (esquerda / direita) | Vira de perfil e anda na horizontal. |
| Caminhar até o mouse | Destino em direção ao cursor. |
| Caminhar para um destino aleatório | Destino aleatório. |
| Orientação: frente / perfil / costas | Vira o corpo no lugar, para testar o giro sem caminhar. |
| Voltar ao plano (frente) | Interrompe e volta para "perto", de frente. |

**Lista confirmada pelo autor (10/11/2026):** Olhar a tela; Profundidade (perto, médio,
longe); Orientação (frente, perfil, costas); Caminhar até o mouse; Caminhar para um
destino aleatório; Voltar ao plano. O autor também citou "caminhar para o fundo,
caminhar para o lado etc."; essas entradas estão na tabela como atalhos de um passo
só (equivalem a mudar de profundidade ou de orientação andando).

**Decisão do autor:** essas entradas de teste ficam **no menu da bandeja, sempre
visíveis**, junto de "Acenar", "Mostrar tentáculos" e "Espirro de tentáculos", e não
atrás do diagnóstico. A lista acima é uma proposta inicial; o autor mencionou
"caminhar para o fundo, caminhar para o lado etc.", então outras podem entrar.

**Configurações.** O autor também quer o acionamento **na janela de Configurações**. O
que exatamente vai lá fica a confirmar. Proposta de partida:
- botões de teste que espelham o menu da bandeja;
- liga/desliga da caminhada autônoma;
- frequência da caminhada autônoma (rara como padrão);
- tipo de destino: aleatório, em direção ao mouse, ou ambos;
- liga/desliga do pacote "Olhar a tela".

As opções de comportamento seguem o padrão do diálogo atual: gravadas no TOML, com
aplicação imediata quando possível.

### 8.6 Privacidade do "olhar o que o usuário faz"

A interação pode ser só **olhar na direção da tela** (decorativa), ou **reagir ao
conteúdo** (aplicativo ativo, título de janela, atividade). Reagir ao conteúdo é outra
decisão, com implicações de privacidade. Proposta de partida: **só olhar na direção do
monitor, sem ler nada da tela.** O projeto hoje já evita analisar semanticamente
interfaces de terceiros; manter isso até o autor decidir diferente.

### 8.7 Perguntas abertas

Respondidas pelo autor:
- Ao virar de costas, o mascote **muda de lugar e continua caminhando** pela tela (8.5, item 5).
- Porta e tentáculos **continuam no modelo e funcionando** em qualquer animação (8.2).
- Os idles de Animal Crossing **substituem** os atuais (8.4).

Ainda em aberto:
1. ~~Quantos pacotes na primeira versão?~~ **Respondida:** só o principal (Olhar a tela).
2. **Profundidade (8.5.1): fechada.** Opção A (só visual), 3 níveis (perto, médio,
   longe), volta andando de frente, no fundo apoia em janelas, responde a clique e
   arraste, e é puxado para a frente ao ser arrastado. Falta só confirmar que "perto" é
   o plano atual da tela.
3. ~~Destinos e frequência.~~ **Respondida:** aleatórios ou em direção ao mouse, raro.
4. ~~As danças usam a mesma caixa de som?~~ **Adiada** junto com os outros pacotes.
5. ~~Quais tipos de Animal Crossing entram?~~ **Respondida:** todos os mais recentes; as
   antigas deixam de existir. Em aberto: se "automática" continua e como fazer o
   fallback do perfil salvo.
6. **Material de referência:** o autor fornece GIFs/vídeos recentes dos idles de
   Animal Crossing (ver 8.4). Falta definir a pasta e quem junta o material.
7. ~~Menu de teste.~~ **Respondida:** menu da bandeja, entradas sempre visíveis, e também
   nas Configurações. Em aberto: o que exatamente vai nas Configurações (ver 8.5.2).
8. ~~O pacote principal é o Olhar a tela?~~ **Respondida:** o Olhar a tela faz parte do
   pacote principal. Em aberto: se o pacote principal inclui mais que isso (por
   exemplo, a caminhada autônoma completa).

### 8.8 Ordem de dependências (esboço)

1. Passo 1: rig encadeado (cintura, abdômen, peitoral, pernas, joelho, ombros, fones, antenas).
2. Pernas e pés ativos: andar de perfil e girar com passos.
3. Giro de corpo e costas (seção 7).
4. Pacotes de animação e agendador.
5. Idles de personalidade no estilo Animal Crossing.

## 9. Pedido final ao agente

Gerado no fim, a partir das seções acima. Ainda vazio.
