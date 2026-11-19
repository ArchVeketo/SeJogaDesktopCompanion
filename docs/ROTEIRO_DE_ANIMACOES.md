# Roteiro de Animações do Mário

> Proposta de direção de comportamento. Complementa o [Manual Unificado](MANUAL_UNIFICADO_MARIO.md), que continua sendo a fonte de verdade para a criatura viva e os 12 princípios.

## Intenção

Mário não deve sortear animações. Ele percebe uma situação, toma uma decisão legível, executa uma pequena cena e guarda o resultado no humor recente. O objetivo é **autoria controlada com variação de detalhe**, não um simulador caótico.

Cada cena segue quatro batidas: **leitura** (ele percebe), **antecipação** (prepara o corpo), **ação** (a pose ou deslocamento principal) e **assentamento** (consequência e retorno). O procedural só entra em respiração, olhar, sobreposição de membros, fios, antenas e tentáculos; nunca decide a intenção da cena.

## Camadas e prioridade

Há somente uma cena corporal dominante por vez. Dança, porta/tentáculos e FX podem coexistir apenas quando esta tabela permitir.

| Prioridade | Camada dominante | Interrompe | Regra de retorno |
| --- | --- | --- | --- |
| 1 | Fechamento/saída | tudo | encerra o app |
| 2 | Arraste, queda e pouso | tudo exceto saída | conclui pouso antes de retomar intenção adiada |
| 3 | Toque, cutucão e teimosia | agência, sono e dança | volta a idle de recuperação |
| 4 | Dança/música | agência e idles ativos | termina no próximo bloco de 4 batidas ou ao cessar música |
| 5 | Agência: foco e caminhada | idle | chega ao alvo e observa antes de escolher outra meta |
| 6 | Sono | idle | acorda por interação ou estímulo relevante |
| 7 | Idle/atenção | nada | é a base contínua |

Porta, tentáculos, caixa de som e efeitos são camadas de apoio, não novos estados dominantes. Eles precisam de uma causa da cena atual e fecham antes de uma saída ou de uma troca brusca de pose.

## Memória curta que guia as escolhas

| Memória | Alimentada por | Efeito narrativo |
| --- | --- | --- |
| Última interação | carinho, cutucão, arraste e queda | define a próxima reação como receptiva, surpresa ou contrariada |
| Interrupções seguidas | metas frustradas/arrastes | libera teimosia na terceira interrupção |
| Interesse atual | janela/foco/ponto de interesse | dá um alvo à caminhada e evita passeios sem motivo |
| Silêncio/inatividade | cursor e áudio sem atividade | permite sono ou espiada, nunca os obriga |
| Última grande cena | dança, espirro, tentáculos, teimosia | cria respiro antes de repetir um espetáculo |

Uma cena só começa quando há causa, espaço seguro e respiro narrativo. Se duas causas forem válidas, vence a prioridade; a outra fica adiada apenas se ainda fizer sentido ao voltar ao idle.

## Roteiro base de uma sessão

### Chegada — “estou aqui”

**Gatilho:** inicialização. Usar a entrada configurada (`fade_in`, `virtual_insanity_in`, `run_from_depth`, `kagebunshin_in` ou `sandevistan_in`), assentar os pés, olhar o desktop e entrar em `brc_stance` ou `calm`. Usar apenas o FX da própria entrada; não somar poeira, tentáculo e notas por padrão.

### Presença — “estou vivendo aqui”

**Gatilho:** ausência de estímulo dominante. Alternar entre `calm`, `brc_stance`, `vibing`, `street`, `fighter` e `playful` somente depois de a postura atual assentar e por uma razão sutil: cursor próximo, atenção à janela, energia depois da música ou recuperação de interação. A respiração é contínua; o idle não troca por cronômetro seco.

### Curiosidade — “o que é aquilo?”

**Cenas implementadas em 17/11/2026:** ao voltar a mover o cursor após pelo menos 8 s, `disfarcar_olhar` pode responder com recuo, olhar lateral, gesto casual e última espiada antes do retorno. No início de música em repouso, `escutar_fone` aproxima uma mão da concha; música baixa escolhe `batida_guardada`, com dois acentos discretos. A dança espera essas cenas concluírem. Arraste/queda interrompem; cenas automáticas respeitam ações já em curso e intervalo mínimo de 60 s, sem disparo por relógio sozinho. Todas podem ser ensaiadas pela bandeja e pelo editor.

**Gatilho:** novo ponto de interesse ou troca relevante de janela em foco. Micro-recuo → olhar/torção 3/4 → `FOCO_TELA` → caminhada lenta ou normal até a meta → freada plantada → observação curta. Poeira só se a freada pedir. Depois de chegar, ele observa antes de andar de novo.

### Música — “isso pede palco”

**Gatilho:** áudio musical confiável, celebração de meta ou comando manual. Reconhecer a batida, antecipar por 1–2 tempos e escolher no limite de quatro batidas `street_groove`, `graffiti_dance` ou `cyber_bounce`. O estilo fica por ao menos um bloco musical; não muda a cada onset.

Notas e ondas de fone acompanham a música. Caixa de som/rádio entra uma vez por sessão de performance e fica no desktop. Tentáculos não são obrigatórios na dança. A saída reduz no próximo bloco de quatro batidas → pose final → dois ciclos de `vibing` → idle. Arraste interrompe com a pose de suspensão.

### Toque e brincadeira — “eu percebi você”

**Gatilho:** clique, duplo clique, cutucão ou carinho em cabeça, braço, corpo, perna ou pé. Reação específica da parte tocada → olhar ao cursor → gesto curto (aceno, `peace`, joinha, rock, hang loose ou pistolinha) quando amistoso. Cutucões repetidos aumentam a intensidade, mas não sorteiam ação desconexa. Ondas dos fones só entram como resposta energética.

### Física e limite — “não sou uma massinha”

**Gatilho:** pegar, arrastar, soltar ou lançar. Contração ao agarrar → suspensão com resistência orientada à meta → queda/stretch → pouso/squash → poeira e recomposição. A física resolve posição e contato; as poses autorais contam a reação.

Três interrupções frustrando a mesma intenção liberam a cena canônica: resistência → repreensão → bote → roubo do cursor → cospe o cursor → pose triunfal. Ela deve ser rara, anunciada e cancelada por saída do app.

### Segredo da porta — “não era para você ver”

**Gatilho:** repouso real com cursor parado fora do mascote, objeto inalcançável, cócega/poeira ou defesa. Espiada: olhar ao redor → porta abre → saída assimétrica de 1–4 tentáculos → investigação/puxada → recolhimento → porta fecha → olhar culpado.

Espirro: três inspirações → pausa → explosão frontal de tentáculos e gosma rosa → recuperação → esfregar o rosto. É especial e isolado: não começa em dança, queda, arraste ou teimosia.

### Descanso — “vou ficar por aqui”

**Gatilho:** inatividade prolongada real e ausência de interesse/música. Olhar o local → preparação → sentar/deitar/em pé sonolento → respiração lenta e `Zzz`. As variações automáticas evitam repetição; a escolha manual fica fixa. Ao acordar: espreguiçar → olhar a causa → idle atento. Nunca acordar direto em dança ou caminhada.

## Mapa de efeitos

| Efeito existente | Dono narrativo | Nunca usar em |
| --- | --- | --- |
| Notas e ondas de fone/caixa | dança e celebração | idle comum, sono |
| Poeira de pouso/decolagem | queda, pouso e partida forte | gesto de mão, atenção |
| Poeira de deslize | freada/deslize | caminhada normal |
| Rastro de queda | lançamento/queda veloz | arraste lento |
| Cascata `Zzz` | sono | reação ou dança |
| Gosma rosa e gotas | tentáculo/espirro | música e toque amistoso |
| Orbes cianos/holofote | `fnf_blue_balls` | estados cotidianos |

## Regras de direção que evitam caos

1. Uma causa, uma cena, uma consequência. Nada começa só porque passou um tempo.
2. Após dança, teimosia, espirro ou tentáculos, retornar a um idle legível antes de outro espetáculo.
3. Não cortar uma silhueta forte no meio. Física e saída do app são as únicas interrupções duras.
4. Toda cena preserva os 12 princípios simultaneamente; o roteiro seleciona intenção, não substitui poses, arcos e timing.
5. Aleatoriedade escolhe apenas detalhe justificado: lado do olhar, variante de postura e quantidade/morfologia de tentáculos.

## Ordem mínima de implementação

1. Centralizar no seletor de estado a prioridade, as causas e o respiro narrativo, usando a memória de agência existente.
2. Transformar cada ação atual em cena com entrada, corpo e saída explícitos; começar por dança, curiosidade e sono, que já têm os ativos necessários.
3. Vincular os FX ao estado dominante para eliminar combinações sem causa.
4. Validar visualmente cada cena em janela real com `smoke_mouse.py` e `smoke_mouse.py --physics`; testes automatizados ficam para crash, TOML inválido e NaN.

## Fora de escopo

Não criar novo sistema de personalidade, árvore comportamental genérica, assets ou novas opções de usuário antes desta direção ser aprovada e as transições existentes estarem legíveis.


## Revisão implementada em 16/11 — idles e conexões

As pistas ativas dos 11 idles estão em `animation.py/IDLE_CLIPS`, compartilhadas
com o editor. `clipes_ocioso.py` não mantém mais uma cópia independente delas.
O repouso recebe respiração, olhar e as pistas autorais; não acumula também a
antiga oscilação ampla da coluna e a ginga de combate.

| Idle | Intenção e leitura da pose | Ciclo |
| --- | --- | --- |
| calm | observar com cabeça leve e braços descansados | 12 s |
| curious | antecipar com recuo e aproximar cabeça/ombro do interesse | 12 s |
| playful | inclinar a cabeça e oferecer uma mão em provocação | 12 s |
| shy | recolher tronco e desviar o olhar | 12 s |
| confident | abrir peito, sustentar olhar e flexionar um braço | 12 s |
| street | apoio assimétrico e ombro relaxado | 12 s |
| fighter | preparar guarda bilateral abaixo do rosto e baixar os braços | 12 s |
| rhythm | gesto marcado acompanhado de pulso musical | 8 s |
| stylish | olhar lateral e apresentação da mão com atraso do punho | 12 s |
| brc_stance | contrapeso de tronco e braço, sustentando atitude | 12 s |
| vibing | balanço musical leve com mãos baixas | 8 s |

As pistas têm pausa, contramovimento, gesto, sustentação e retorno, com mãos
atrasadas em relação ao tronco. As variantes configuradas no editor continuam
suportadas. Os clipes existentes de caminhada e dança permanecem disponíveis.

Conexões implementadas:
- Repouso → caminhada/corrida/dança: preparação curta do peito e contrapeso da cabeça.
- Ação → repouso: assentamento e recuperação sem resíduo na pose final.
- Troca de dança: reinicia a mistura da pose mesmo permanecendo no estado `dance`.
- Troca de ação com rotação da raiz: conserva a orientação de saída e mistura até a próxima.
- Deitar: uma única rotação global entra em 2,6 s e sai em 0,65 s, sem contrarrotação do tronco.
- Acordar pelo menu: passa pela reação `wake`, como o despertar por interação.
- O relógio da mistura é independente do relógio do estado; trocar uma variação não cancela a mistura.

A porta possui um vão permanente e moldura com o UV original. A abertura não
esconde mais a frente inteira do gabinete ao cruzar um ângulo. As faces escuras
estão somente no interior e a dobradiça/nomenclatura do GLTF é preservada.

Revisão reproduzível: `python tools/revisar_animacoes.py`. Gera perfil temporário,
manifesto e pranchas sequenciais de idles, cenas, danças, reações, sono, movimento,
entradas, saídas e conexões. `--grupo extras` inclui GIF da porta e da troca de dança.
O cenário injeta estímulos para tornar o catálogo repetível; isso não substitui os
smokes de mouse nem a avaliação artística das sequências na janela.
