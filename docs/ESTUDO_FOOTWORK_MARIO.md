# Footwork e reação física para o Mário

12 de novembro de 2026 · Base de design: [Manual Unificado](MANUAL_UNIFICADO_MARIO.md) e [Manifesto da Criatura Viva](MANIFESTO_CRIATURA_VIVA_MARIO.md).

## O que Bomb Rush Cyberfunk faz

Dion Koster, diretor e praticante de breaking e locking, relata que ele e outros dançarinos participaram das sessões de captura de movimento da Team Reptile. O repertório partiu de performances de dança. [Entrevista com Dion Koster](https://toucharcade.com/2023/12/14/bomb-rush-cyberfunk-interview-game-director-dion-koster-career-soundtrack-vinyl-physical-release-switch-iam8bit-skybound/)

Na instalação Steam 20272977, li os bundles com UnityPy 1.25.4 e o IL de `Assembly-CSharp.dll` com dnfile/dncil. O REA CLI classificou a DLL como Unity Mono, IL gerenciado AnyCPU. A DLL examinada tem SHA-256 `2c3ced00efcfbb08b12947ab4f07b00cca67729f28c08c3adc97178d8bd8002c` e MVID `e7d5b3bb-0379-47ef-98da-01aaf09c9871`. O jogo ficou fechado durante a análise.

- `DanceAbility.Init` (RVA `0x6e228`) prepara seis hashes. `OnStartAbility` toca um bounce de entrada. `SetState` (`0x6e304`) usa a seleção do menu e pede o estado correspondente ao player. `InitAnimInfosTricking` (`0x7c7e0`) registra `popping`, `locking`, `breaking`, `hiphop`, `housedance` e `toprock`, com tempos de transição específicos por estado de origem.
- `Player.PlayAnim` (`0x82df0`) lê `fadeFrom` ou `fadeTo` e chama `Animator.CrossFade`. A mesma função copia o sinalizador `AnimInfo.feetIK` para o visual. `CharacterVisual.InverseKinematics` (`0x8ca0c`) usa esse sinalizador para habilitar a parte de pés, que consulta o chão por raycast e ajusta posição e rotação. O construtor de `AnimInfo` e os blocos de registro das seis danças examinados não escrevem `feetIK`. Isso indica que os apoios dessas danças dependem principalmente dos clipes no caminho estático inspecionado. Para estabelecer quais correções entram durante o jogo, seria preciso observar o Animator em execução, inclusive as configurações de cada estado.
- Há 21 clipes e 11 Avatares em `mocap_animation`, e 42 clipes e 39 Avatares em `mocap_animation_two`. No segundo bundle aparecem, entre outros, `MocapBreakingAvatar`, `MocapHousedanceAvatar` e `MocapToprockAvatar`. Há também Avatares de personagens em `characters`. Os nomes ajudam a localizar os pares de captura para testar. O vínculo entre cada estado do jogador e cada variante de clipe, a velocidade em execução e eventual sincronização musical ainda precisam ser confirmados.

| Clipe | Duração declarada | Amostras densas | Canais densos / streamed / constantes |
|---|---:|---:|---:|
| `popping` | 9,43 s | 568 a 60 Hz | 149 / 4 / 317 |
| `locking` | 9,88 s | 595 a 60 Hz | 151 / 122 / 197 |
| `toprock` | 8,90 s | 536 a 60 Hz | 151 / 2 / 317 |
| `housedance` | 13,58 s | 817 a 60 Hz | 151 / 2 / 317 |
| `housedanceLoop` | 5,00 s | 152 a 30 Hz | 81 / 0 / 49 |
| `breaking` | 11,03 s | 664 a 60 Hz | 127 / 26 / 317 |
| `BreakingLoop` | 1,93 s | 60 a 30 Hz | 81 / 0 / 49 |
| `hiphop` | 9,80 s | 590 a 60 Hz | 151 / 2 / 317 |
| `hiphopLoop` | 2,03 s | 63 a 30 Hz | 81 / 0 / 49 |

Os três clipes curtos têm 130 bindings humanoides (tipo 95, subtipo 8) e zero entradas em `m_RotationCurves`. Em `popping` e `toprock` há também bindings de Transform. A grade densa tem duração própria de amostragem. Use o intervalo declarado do clipe para avaliar o ciclo. Para observar os movimentos no esqueleto, avalie os canais no Avatar e registre transformações locais e deslocamento da raiz. Ler a grade densa confirma a estrutura e a cadência de amostragem. Ainda falta reproduzir o resultado do Animator. [Unity HumanPoseHandler](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/HumanPoseHandler.html)

Para repetir o inventário, com UnityPy 1.25.4 no ambiente de análise:

```powershell
python tools/inspecionar_dancas_brc.py 'C:/Program Files (x86)/Steam/steamapps/common/BombRushCyberfunk/Bomb Rush Cyberfunk_Data'
```

## Onde o Mário perde o passo

`DanceMotion` já mantém fase musical, escolhe frases e amostra poses autorais para tronco e braços. `LegMotion` compartilha a fase, mas monta a dança principalmente com uma senoide, flexão e lift. `LowerBody` dobra a cadeia no plano sagital e corrige a altura do conjunto pela sola. Um pé pode estar na altura certa enquanto desliza lateralmente. O breakdance atual acrescenta inclinação e giro do corpo. A posição da mão de apoio continua livre durante o giro. A entrada na jukebox ainda muda o referencial em boa parte dos estilos.

Um passo cruzado precisa informar **onde o pé livre vai, quando ele aterrissa e para onde a bacia leva o peso**. Um pivô pode prender a ponta do pé e deixar o calcanhar girar. Um slide tem trajetória intencional durante o contato. Um freeze precisa manter a palma e, conforme a figura, um pé apoiados enquanto a pose desacelera. Tratar todo contato como uma sola colada por inteiro eliminaria passos legítimos. [Fundamentos do breaking e six-step](https://www.redbull.com/us-en/your-go-to-guide-for-b-boying-basics) · [Footskate Cleanup, Kovar, Schreiner e Gleicher](https://research.cs.wisc.edu/graphics/Gallery/kovar.vol/Cleanup/)

## Como integrar animações em Python

1. **Autoria e importação fora do jogo.** Primeiro autorar ou filmar uma frase curta com um dançarino, editar no Blender ou Blockbench e exportar no rig do Mário. Com captura externa, transferir movimentos a partir da pose de repouso, em espaço local, e recalibrar alcance e polos de joelho/cotovelo pela FK do rig real. A largura e o peso visual do armário pedem trajetórias próprias. AIST++ oferece sequências multivista com rotações e trajetória de raiz para referência de house, locking e breaking. As anotações são CC BY 4.0 e o vídeo e a música têm termos próprios. [AIST++](https://google.github.io/aistplusplus_dataset/factsfigures.html)
2. **Um clipe e seus contatos.** Começar com glTF animado no rig de destino e um JSON ao lado com ID, duração musical em batidas, BPM de referência, acentos e intervalos de contato por membro. Marcar apoio fixo, pivô ou slide quando a frase usar cada tipo. Registrar raiz e rotação local dos grupos existentes. Preservar quaternions até a conversão para a convenção de pose do renderer. Usar o modo de interpolação da faixa. Para captura densa com interpolação linear, usar SLERP para rotações e interpolação linear para translação. A interpolação quíntica atual continua adequada para poses autorais com pausas. [Especificação glTF 2.0](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#animations)
3. **Amostragem e correção após o blend.** Amostrar pela fase de `DanceMotion`. Aplicar a pose autorada e as sobreposições, fazer FK e resolver IK analítica da coxa/canela no espaço de cena em 3D. No início do apoio, capturar o alvo no referencial da superfície. Durante o intervalo, mover a bacia dentro de um limite de alcance e manter o ponto de contato. Se a trajetória for inviável, encurtar a passada ou liberar o apoio. Inclinação, yaw, squash e offset da raiz precisam entrar na FK usada pelo solver. Validar o eixo pelo oráculo FK e conferir modelo e contorno na mesma pose final. Um resolvedor de tornozelo no plano sagital serve para marcha, mas um cruzamento ou pivô usa os três eixos.
4. **Agência e física.** A intenção seleciona a frase em reação à música, comemoração ou provocação. Pymunk mantém a posição física do corpo e trata queda, arraste e colisão no desktop. Para o primeiro ciclo, o deslocamento autorado da bacia fica dentro da área de dança local. Quando houver deslocamento real pelo monitor, o controlador oferece a trajetória horizontal à camada desktop. Se a borda cortar o caminho, a dança encurta o passo ou entra numa recuperação autoral. Ao arrastar, perder a superfície ou cair, liberar os contatos naquele frame. Após o impacto, escolher um gesto de recuperação antes de decidir se volta a dançar.

Essa divisão explica por que um personagem ainda dá trabalho. Em um cruzado, o pé preso, a bacia em movimento e o joelho têm de concordar no mesmo referencial. Se o mouse pega o personagem nesse instante, o pé precisa soltar enquanto o braço e o tronco comunicam a interrupção. A cinemática resolve a restrição local, Pymunk resolve a trajetória do corpo no desktop e o gesto comunica a intenção. A palestra da Naughty Dog sobre Uncharted 4 oferece um caso documentado de simulação aplicada sobre animação de gameplay. [Physics Animation in Uncharted 4](https://www.gdcvault.com/play/1024087/Physics-Animation-in-Uncharted-4)

| O que acontece | Informação que a animação recebe | Resposta visível |
|---|---|---|
| Mouse pega o armário no cruzado | Membro e ponto agarrados, direção da puxada, pose do último frame | Soltar os apoios e sair da pose do cruzado para uma resistência direcionada. |
| Mouse solta no ar | Velocidade da soltura e distância até a superfície | Preservar a velocidade do corpo e preparar as pernas para o contato conforme o chão se aproxima. |
| Armário bate numa superfície | Normal do contato e componente da velocidade de chegada nessa normal | A intensidade governa o squash e a recuperação autorada. O olhar pode procurar o cursor antes de o Mário decidir se volta à dança. |

## Primeiro ciclo que vale colocar na janela

**Toprock cruzado, oito batidas, em 3/4, no chão do desktop.** Começa carregando o peso à esquerda, cruza o pé direito na frente e transfere peso no acento. Recolhe, abre para o outro lado, espelha a frase e retorna ao apoio inicial. A entrada e a saída têm poses próprias. Começar com uma referência humana filmada de frente e de lado. Usar um metrônomo fixo no ensaio antes de conectar ao relógio musical.

Como marcação inicial para filmar, usar 1 para o cruzado direito, 2 para a volta à base, 3 para a abertura direita, 4 para recolher. Usar 5–8 para a resposta espelhada. Marcar a carga no contratempo anterior ao cruzado. Ajustar essas marcações à performance gravada e cortar o loop numa pose com o mesmo apoio e a mesma direção de movimento dos dois lados da emenda.

- A preparação comprime joelhos e torso antes do cruzado. O acento estende a perna livre num arco e desloca a bacia sobre o apoio. A silhueta de 3/4 mostra qual bota cruza e deixa a porta legível. As poses de carga, contato e passagem têm timing distinto, com aceleração no cruzado e desaceleração na chegada.
- Ombro e mão chegam depois da bacia, fones e cabo continuam o movimento, e o olhar sustenta a provocação. Exagerar o contragiro do armário e a pausa sem perder o volume, a direção dos joelhos ou a leitura dos apoios. Conferir os 12 princípios juntos no ciclo completo, na escala do companion.
- Medir a deriva dos pontos de sola em pixels de cena durante o apoio e registrar a penetração máxima. Usar como alvo inicial até 1 px de deriva na escala padrão para contatos fixos, descontando o deslocamento da superfície e da janela. Conferir também a trajetória em vista lateral e dois loops completos para flagrar saltos de emenda.
- Na janela real, interromper o cruzado com arraste e soltar o Mário. Conferir que a bota perde o apoio imediatamente, a reação segue o mouse e a aterrissagem tem recuperação legível. Rodar `tools/smoke_mouse.py --physics` para infraestrutura e revisar uma captura contínua da dança e da interrupção. Se a mudança chegar ao renderer, validar o executável conforme o Manual Unificado.

O segundo clipe deve reutilizar o mesmo caminho de importação. House running man testa passos rápidos com recuperação e slide deliberado. Depois, um six-step curto testa apoio simultâneo de mãos e pés, passagem lateral e saída para freeze. Para o Mário, vale adaptar o raio do passo e altura da bacia ao gabinete. Uma boa passagem de toprock para downrock carrega a preparação para o chão dentro da frase, com a primeira mão chegando antes de descarregar o peso. [Demonstração e descrição do six-step](https://www.redbull.com/us-en/your-go-to-guide-for-b-boying-basics)

## Limite da investigação e próximo teste de engenharia reversa

O inventário foi executado no jogo instalado e checou as dimensões das grades de nove clipes. O ramo de caminho inválido do script também foi testado. A investigação foi estática. Como a integração do REA com Codex estava ausente, a identificação do assembly foi feita pelo REA CLI e a leitura de instruções foi feita diretamente em Python. Nenhum clipe foi convertido ou tocado no Mário nesta etapa.

O próximo teste com o jogo é avaliar localmente `BreakingLoop` num humanoide compatível em Unity 2021.3, fixar a fase em incrementos de 1/30 s, registrar bacia, tornozelos e pulsos no espaço da cena, e visualizar dois ciclos incluindo a emenda. Comparar com a execução do Animator do jogo antes de atribuir um comportamento observado a um clipe específico. Esse ensaio responde às dúvidas sobre Avatar, raiz e contatos. Para o primeiro toprock distribuível, usar uma performance própria ou uma fonte com licença de distribuição confirmada.
