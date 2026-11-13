# Idle e linguagem corporal do Mário

12 de novembro de 2026 · Base de design no [Manual Unificado](MANUAL_UNIFICADO_MARIO.md) e no [Manifesto da Criatura Viva](MANIFESTO_CRIATURA_VIVA_MARIO.md). O [estudo de fluidez e animação procedural](ESTUDO_FLUIDEZ_E_ANIMACAO_PROCEDURAL.md) descreve o pipeline compartilhado.

## Por que o Mário parece estar “na lua”

Na prévia renderizada, o Mário já movimenta cabeça, braços e pernas em repouso. Em `calm` e `curious`, a silhueta e os pequenos balanços se parecem. Dá para perceber que ele se mexe. É mais difícil ver **onde está a atenção dele, o que ele acabou de perceber e quando tomou uma decisão**. O movimento contínuo torna a diferença entre esperar e investigar pouco visível.

| Evidência no código e na execução | Efeito provável |
|---|---|
| `sample_idle` combina arcos contínuos de cabeça, tronco e braços, trilhas cíclicas e respiração. `LegMotion` calcula balanço e joelhos a partir de outras ondas, com contribuição da inclinação. | Os gestos podem se acumular mesmo sem uma mudança de intenção. A cabeça continua viajando quando deveria estar examinando um ponto. O movimento das pernas parece balanço quando a bacia e a sola não mostram qual pé recebeu o peso. [Clipes ociosos](../src/sejoga/animacao/clipes_ocioso.py) · [Pernas](../src/sejoga/animacao/movimento_pernas.py) |
| Em um ensaio de 480 frames a 60 Hz, forcei `fonte_atencao="cursor"` com direção −1 ou +1, mantendo o Mário em `idle`. Com o mesmo rig de teste, o giro local de cabeça foi idêntico frame a frame. Variou de −11,36° a +11,36° e terminou em +0,94°. O controlador suaviza a direção e a usa explicitamente em hover, reações e no pacote de olhar acionado por troca de foco. A pose comum de idle vem de `delta_idle`. | Existe um alvo calculado, mas o idle comum não transformou esse alvo em direção de cabeça no cenário ensaiado. A diferença de intenção precisa aparecer na pose final. [Controlador](../src/sejoga/animacao/controlador_animacao.py) · [Deltas de estado](../src/sejoga/animacao/estados_delta.py) |
| Com a mesma posição de cursor enviada por oito segundos, `tempo_sem_cursor_movimento` terminou praticamente em zero. O controlador registra movimento sempre que recebe uma posição. O overlay oferece o cursor global como candidato contínuo. Na ordem atual, foco tem prioridade sobre cursor, que tem prioridade sobre batida e borda. | A agência recebe um sinal enganoso de atividade e um alvo parado pode dominar a seleção. Um endereço conhecido do cursor e um evento de movimento precisam ser tratados como informações distintas. [Agência](../src/sejoga/animacao/agencia.py) · [Gate de atenção](../src/sejoga/animacao/foco_atencao.py) · [Overlay](../src/sejoga/render/janela.py) |
| `LowerBody` compensa altura pela sola. A pose de idle ainda não carrega um contrato de apoio com posição fixa em cena. | É plausível que o balanço aparente anteceda a leitura de peso. Medir a trajetória projetada da sola antes de atribuir todo o efeito ao contato. [Aplicação das pernas](../src/sejoga/render/corpo_inferior.py) |

Usei a ferramenta de prévias do projeto em janela Panda3D, com perfil temporário, cinco segundos de `calm` e `curious`, e três de `hover` com direção simulada. A revisão foi das folhas de poses renderizadas. O ensaio numérico isolou o controlador. A prévia não percorre o mesmo caminho do cursor global e da troca de foco Win32. A leitura de intenção em uso real continua por validar.

## O que observar em jogos e pesquisa

- **The Last of Us Part II.** A apresentação da Naughty Dog distingue performances ociosas que expressam o personagem e o tom do momento de performances ambientais ligadas a posições específicas do mundo. Para o Mário, a transferência é criar uma espera que expresse sua postura habitual e usar um alvo concreto para uma espiada, inclinação ou passo. Um personagem pode descansar olhando para um lugar, mudar de ideia ou abandonar um gesto. [Apresentação GDC](https://gdcvault.com/play/1027207/Bringing-Allies-to-Life-in) · [Slides da Naughty Dog](https://media.gdcvault.com/GDC%2B2021/Bringing_Allies_To_Life_In_TLOU2.pdf)
- **Team Fortress 2.** A Valve destaca silhuetas distintas e oferece material de pose a pose. A aplicação aqui é testar a postura em escala de desktop e em 3/4. De longe, curiosidade pode ser um avanço da cabeça com o gabinete ainda atrás. Desconfiança pode ser cabeça voltada ao estímulo e gabinete retraído. São propostas de atuação para este personagem, com leitura dependente da cena. [Orientações e tutoriais da Valve](https://www.teamfortress.com/workshop/)
- **Olhar dirigido.** Pejsa e colaboradores representam o olhar como mudanças seguidas de fixações em alvos, coordenando olhos, cabeça e tronco com a animação de base. O Mário pode usar a frente do gabinete como linha de atenção e distribuir a virada entre cabeça e corpo. O gesto curto pode terminar só na cabeça. O corpo acompanha quando o alvo está fora da faixa confortável ou quando ele decide agir. [Authoring Directed Gaze for Full-body Motion Capture](https://graphics.cs.wisc.edu/Papers/2016/PRMG16/)
- **Pausa com vida.** Lasseter descreve princípios de timing, encenação e continuidade em animação 3D. Para o idle do Mário, a proposta é sustentar a intenção e deixar respiração, dedos ou cabo assentarem enquanto a cabeça mantém o foco. A pausa cria contraste com a próxima reação. Testar primeiro com uma única ação dominante para ver se os detalhes secundários continuam legíveis. [John Lasseter, SIGGRAPH 1987](https://www.cs.cmu.edu/afs/cs/academic/class/15462-f13/www/lec_slides/Lesseter.pdf)

## Linguagem corporal para o gabinete

O realismo procurado aqui é coerência entre atenção, esforço e apoio em um corpo estilizado. As botas e o gabinete comunicam peso. A frente da cabeça comunica foco. Os braços comunicam compromisso com a ação. Fones, cabo, antenas e porta mostram a acomodação e os detalhes do gesto. A pose principal deve ser reconhecível antes de adicionar esses detalhes.

| Situação | Pose e ação | Quando termina |
|---|---|---|
| Esperando, disponível | Uma bota recebe mais carga, a outra fica confortável, braços relaxam com assimetria. A respiração movimenta o gabinete enquanto a direção da cabeça se mantém estável. | Um estímulo ganha atenção ou o corpo decide se acomodar. A espera pode durar. |
| Percebe um movimento próximo | A cabeça encontra a direção e sustenta. A mão que estava relaxada pode se preparar sem levantar. A bacia fica no apoio. | O cursor passa, para perto ou volta. A reação seguinte depende disso. |
| Investiga com curiosidade | Projeta a cabeça em direção ao alvo, contrabalança no quadril, aproxima um ombro. Se decidir ir, descarrega a bota livre antes de levantar o pé. | Ele se aproxima, perde o interesse ou é interrompido. |
| Desconfia após um puxão | Cabeça ainda vigia, tronco recua e uma mão protege a frente do gabinete. As botas buscam apoio estável. | Um período calmo permite relaxar. Uma nova aproximação pode manter a defesa. |
| Se acomoda depois de esperar | Um único ajuste de peso. Bacia chega ao novo apoio, braço e fones terminam depois, respiração continua na nova pose. | A postura permanece. O ajuste fica disponível de novo quando houver motivo para trocar o apoio. |

Evitar vincular um gesto a um significado universal. Braços fechados podem significar defesa ou conforto. A leitura depende do estímulo anterior, da direção da cabeça, do ritmo e da ação seguinte. Para distinguir as duas, filmar o mesmo gesto com contexto diferente e revisar na escala em que o Mário aparece.

## Integração em código

### Coordenação e roteiro de movimentação

O idle precisa de uma postura que possa durar e de frases que entrem e saiam dela. Cada frase tem **uma intenção dominante**, um membro que inicia a ação e outros que acompanham ou sustentam. O controlador escolhe a frase pelo contexto. O animador decide as poses, os arcos e as relações entre as partes. O procedural adapta o alvo e conserva o apoio.

| Frase | Quem inicia | Quem acompanha | Quem sustenta |
|---|---|---|---|
| Perceber um alvo | Cabeça | Ombro e tronco apenas se decidir investigar. Fones e cabo assentam após a virada. | Bacia e botas. |
| Trocar o peso | Bacia começa a carregar a bota de destino. | Joelhos acomodam a mudança. Ombros contrabalançam e mãos assentam depois. | Cabeça pode continuar no alvo anterior. As botas mantêm os contatos declarados. |
| Preparar uma aproximação | Cabeça confirma o alvo, depois a bacia descarrega a bota livre. | Tronco e braços entram na passagem para a marcha. | Bota carregada até a decolagem da outra. |
| Desistir e voltar a esperar | Cabeça libera o alvo e inicia o retorno. | Ombro e mãos relaxam em tempos distintos. | A postura final conserva o apoio em que ele terminou. |

**Cena de referência — o Mário percebe o cursor, fica curioso e decide ficar onde está.** Os tempos abaixo são marcações de ensaio a partir do estímulo, com o cursor parando perto do Mário. Na execução, a duração da observação depende do alvo.

| Tempo de ensaio | Pose e trajetória | Condição para avançar |
|---|---|---|
| Antes do estímulo | Apoio mais carregado à esquerda, bota direita relaxada, mão direita um pouco à frente. Cabeça estável, respiração visível. | O cursor se move perto dele. |
| 0–0,3 s | Cabeça vira num arco curto e encontra o cursor. Bacia e botas permanecem onde estavam. | A direção da cabeça chega ao alvo. |
| 0,3–0,8 s | Sustenta o olhar. A virada já terminou e o cabo ainda assenta. | Se o cursor só cruzou a região, pode passar direto para a volta. |
| 0,8–1,4 s | Com o cursor ainda perto, a cabeça avança ligeiramente e um ombro acompanha. A bacia compensa o avanço sobre o mesmo apoio. A mão livre relaxa. | A pose de curiosidade chega ao ponto de observação. |
| 1,4–2,4 s | Segura a pose e mantém a direção da cabeça. A respiração continua. | Cursor se afasta, aparece outra prioridade ou a agência decide se aproximar. |
| 2,4–3,2 s | Se decidir ficar, recua a cabeça, acomoda o ombro e volta à espera a partir da postura em que terminou. | O movimento principal terminou. Respiração e postura seguem. |

Para codificar, a amostra da frase pode declarar **pose de entrada, apoio atual, alvo de atenção, fase e saídas possíveis**. No fim, ela entrega a pose e o apoio para a próxima frase. Se a próxima frase pedir o outro pé, intercalar uma transferência de peso. Se o mouse agarrar o Mário, interromper do frame exibido e liberar o apoio. Se o alvo mudou pouco durante a observação, atualizar a direção dentro da mesma frase. Assim a sequência pode variar sem reiniciar o gesto a cada evento.

Para dirigir a atuação, fazer primeiro uma passada de poses-chave com acessórios quietos. Revisar se dá para ler a diferença entre **notou**, **investigou** e **perdeu o interesse** só pela silhueta e pela direção da cabeça. Depois animar as passagens e acrescentar respiração, mãos, fones e cabo. Se o ajuste de peso e o olhar disputarem a atenção na mesma tomada, escalonar os acentos. Um apoia a leitura do outro quando têm a mesma intenção.

### Aplicação no controlador

1. **Separar posição de movimento.** A janela continua fornecendo coordenadas de cursor para interação. O controlador só registra atividade quando recebe deslocamento real acima da resolução do ruído do polling, usando coordenadas absolutas. No primeiro frame, guardar a posição como referência. Preservar a possibilidade de manter atenção em um cursor parado próximo quando ele já tiver sido adquirido. Usar o histórico recente para decidir quando a presença deixa de ser saliente.
2. **Transformar atenção num gesto que tem início, sustentação e fim.** Reusar `GateAtencao` para escolher entre eventos recentes e meta ativa. Cada alvo precisa de identidade, ponto, motivo e validade. Ao adquirir, resolver a direção no rig a partir do ponto em cena. A cabeça vira por um arco curto, sustenta o alvo enquanto ele fizer sentido e libera quando houver decisão ou evento mais importante. Histerese evita troca de lado quando dois candidatos competem. Em hover próximo, o contato continua enquanto for intencional. Um arraste cancela a fixação e recebe prioridade.
3. **Proteger a direção da cabeça no idle.** Ligar a atenção ao caminho de deltas que realmente produz `IDLE`. Durante a fixação, compor o olhar após a amostra da postura e limitar a rotação residual que o empurraria para fora do alvo. Ao sair, transicionar a partir da pose exibida. Preservar arcos autorais na aquisição, no desvio e na acomodação, incluindo as figuras em oito do manual onde a ação comportar. Usar respiração no peito e atraso nas extremidades durante a sustentação.
4. **Dar significado à transferência de peso.** Modelar o ajuste como uma passagem entre posturas com apoio declarado, por exemplo esquerda, ambos, direita. A bacia se move sobre a bota que recebe carga, o joelho acomoda, e o membro livre só troca de posição quando descarregado. Usar a mesma solução de contatos prevista para o toprock. Para experimentar o olhar primeiro, manter a postura de apoio do rig e deixar a transferência inteira para a etapa que puder medir as botas. [Estudo de footwork](ESTUDO_FOOTWORK_MARIO.md)
5. **Reusar agência, poses e clipes.** Converter espiada, acomodação e recuperação em frases curtas com motivo e saída. Pode começar com as pistas autorais existentes. Para criar repertório sem editar o controlador a cada clipe, usar Blender para marcar poses e preparar a importação descrita no estudo de fluidez. A decisão de entrar na frase pertence à agência. Pausas entre frases são parte da atuação. Intervalos e cooldowns ajudam a evitar repetição e competição entre estímulos.

Uma implementação inicial pode ser feita com o `GateAtencao`, a FK e o mixer que já existem. Blender ajuda a testar duas poses de leitura e o arco de aquisição. A contribuição de olhar precisa ser observável na pose final antes de investir em mais clipes ou em um sistema de saliência mais elaborado.

### Os 12 princípios no mesmo idle

Usar **“o Mário percebe o cursor se aproximar, examina e volta a esperar”** como exercício. A respiração e a compressão da carga dão **squash e stretch**. Um pequeno ajuste antes de se inclinar dá **antecipação**. O alvo e a silhueta em 3/4 dão **encenação**. Preparação, fixação e retorno são **poses-chave**, com cabo e fones em movimento direto. Cabeça chega primeiro, ombro e acessórios acomodam depois, dando **sobreposição e continuidade**. A virada acelera e desacelera conforme a intenção, segue **arcos**, e a mão ou o cabo acrescentam **ação secundária**. O contraste entre perceber rápido e sustentar dá **timing**. Um avanço claro da cabeça dá **exagero**. As botas e o volume articulado garantem **desenho sólido**. A escolha de voltar à atividade ou vigiar mais um instante expressa **apelo** e personalidade. Conferir o conjunto na mesma tomada.

## Primeiro ensaio e critérios

Escolhi **“em repouso → percebe → sustenta → volta”**, em uma tomada de 20–30 segundos. Gravar o idle atual e a versão que liga a atenção à cabeça usando a mesma sequência de entradas e a mesma escala. Apresentar primeiro sem texto sobreposto e pedir que a pessoa aponte onde o Mário olhou e quando mudou de interesse. Depois rever com o alvo desenhado para diagnóstico. Usar captura contínua, porque timing e pausa somem em folhas de poses.

| Entrada | Resultado a procurar |
|---|---|
| Cursor parado por vários segundos, sem mudança de foco | O tempo de inatividade cresce. A espera tem respiração e postura estável, com liberdade para uma decisão própria. |
| Cursor cruza pela esquerda e para perto | A cabeça acompanha o evento, sustenta à esquerda e deixa a postura legível. Repetir à direita e comparar a orientação final em cena. |
| Janela muda de foco enquanto o cursor está parado | O alvo escolhido aparece na pose. Um olhar curto pode bastar. A virada de corpo fica disponível quando a ação pede. |
| Cursor passa perto sem parar, depois volta | A reação curta e a sustentação têm leituras diferentes. Evitar que o hover persistente seja a única forma de perceber atividade. |
| Mouse agarra o Mário durante a fixação e solta | O olhar deixa de competir com a pegada, o corpo reage a partir da pose exibida e retoma a espera depois do pouso. |

Registrar fonte e idade do alvo, tempo desde movimento real do cursor, fase do gesto e orientação final de cabeça e tronco. Para o próximo ensaio de peso, registrar a deriva de cada bota e a troca de apoio. Rodar as mesmas entradas a 30 e 60 FPS e validar no overlay com perfil isolado. Usar `smoke_mouse.py --physics` quando a implementação alterar contato ou arraste. Usar a gravação para decidir se a atuação comunica foco, pausa e peso.

O diagnóstico foi feito com o código atual, três prévias e um ensaio isolado de atenção. As mudanças são propostas. Ainda falta comparar o idle atual com a intervenção na janela real usando cursor e foco nativos.

## Auditoria das transições entre ações

A versão atual de `PoseResolver` já usa o menor arco por componente HPR e reaproveita a velocidade estimada na troca. Isso atualiza o diagnóstico do estudo anterior, feito quando a transição guardava apenas a pose. Rodei `python -X utf8 tools/medir_salto_transicao.py`. No caso sintético, a cabeça manteve a pose no corte e a norma da velocidade dos componentes passou de 184,80 para 174,33 °/s entre as amostras adjacentes. A medida cobre a saída do resolvedor. Mãos, resposta tátil, pernas, orientação global e contato entram por outros caminhos. [Resolvedor](../src/sejoga/animacao/resolvedor_poses.py) · [Controlador](../src/sejoga/animacao/controlador_animacao.py)

Testei o controlador isolado a 60 Hz com sequências reproduzíveis. O hover alternado e a velocidade alternada são estímulos de diagnóstico. Eles mostram como o sistema reage a oscilações junto de uma fronteira.

| Troca | Resultado observado | O que o movimento precisa comunicar |
|---|---|---|
| Idle ↔ hover | Seis frames com hover alternado produziram seis trocas consecutivas. Cada troca reiniciou uma transição de 0,55 s. As pernas tratam idle e hover como o mesmo estado, enquanto a pose superior recomeça a transição. | A curiosidade entra sobre a postura atual. Um breve cruzamento da borda do hover deve permitir que o gesto em curso continue. |
| Caminhar → parar | Após marcha a 200 px/s, alternar entre 121 e 119 px/s fez o controlador alternar repetidamente entre `walk` e `idle`. Cada mudança reiniciou o blend. O seletor reage ao limiar de velocidade, sem esperar a colocação da próxima bota. | Completar a passada ou encurtá-la, carregar o pé de freada e deixar o tronco e os braços terminarem. A espera herda esse apoio. |
| Arraste → queda → pouso | `drag` e `fall` entraram com blend de 0,22 s. Após simular a chamada `interact("land")` ao aterrissar, o controlador entrou em `land` com blend de 0,55 s e saiu após 0,45 s. Pela curva atual, o peso do destino chega a aproximadamente 95% antes de a reação expirar. O squash do renderer segue o relógio do pouso desde a entrada. | A carga aparece no contato e o corpo termina de absorvê-la depois. O rosto e os braços precisam participar da recuperação. Misturar a pose inteira desde a queda pode diluir o acento enquanto a escala do gabinete já reage. |
| Pouso com dança ativa | Com uma prévia de dança ativa, forcei queda, emiti `land` e devolvi o apoio. O estado voltou direto para `dance` e `land` ficou pendente. `LAND` fica fora da lista de reações que podem interromper dança. | Primeiro recuperar o apoio. Depois retomar a dança na próxima entrada compatível com a batida e a postura. |

O overlay dispara `hit` no callback de colisão e `land` quando passa a estar apoiado. Ambos escrevem na mesma reação do controlador, sujeitos a cooldown e às prioridades. O ensaio de pouso injetou `land` diretamente. Para saber qual reação chega em um impacto real, registrar os callbacks, o frame exibido e a superfície durante a queda. [Janela e callbacks](../src/sejoga/render/janela.py)

### Como dirigir cada passagem

1. **Idle → atenção → idle.** Preservar a postura e o apoio. Virar a cabeça, sustentar a direção, envolver ombro e tronco se o alvo justificar, e voltar a partir da pose exibida. Tratar hover como contexto do gesto. Ao sair brevemente da região, manter a fixação que já foi adquirida até ela perder validade.
2. **Marcha → freada → espera.** Quando a meta for alcançada ou a marcha tiver que parar, terminar na fase de apoio possível. A física entrega a desaceleração e o código encurta a última passada para caber na distância restante. A bacia assenta, o peito ultrapassa e volta, e mãos e fones acomodam depois. Histerese de velocidade reduz alternância, e o marcador de apoio decide a hora do fim da frase.
3. **Arraste → soltura → contato → recuperação.** Ao soltar, manter o vetor da velocidade e liberar a pose de agarrado. Preparar as pernas conforme se aproxima do chão. Usar o evento de contato para coordenar compressão, botas e cabeça na mesma batida. Dar prioridade à recuperação física sobre uma retomada automática da dança. Se houver novo agarre, interromper a recuperação a partir do frame exibido.

Para implementar, fazer a troca entregar **motivo, pose exibida, fase e apoio** ao próximo gesto. A pose e a velocidade servem ao blend. O motivo e o apoio escolhem qual passagem é possível. O contato, a soltura e a necessidade de reagir ao mouse podem exigir ação imediata. A saída para repouso ou dança pode esperar uma passagem compatível. Isso cabe no controlador e no resolvedor atuais. Começar pela continuidade de idle/hover e pela precedência do pouso. A freada com pé plantado depende da solução de contatos estudada para o footwork.

Na revisão, gravar as três sequências completas e exibir depois a trilha de estado, motivo, fase e apoio. Repetir com cursor cruzando a fronteira de hover, redução gradual de velocidade e queda com música ativa. Avaliar se dá para reconhecer a causa da próxima ação antes de ler o log. A auditoria atual foi feita no controlador e no resolvedor. As sequências completas com física e entrada nativas ainda precisam ser filmadas na janela real.
