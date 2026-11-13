# Manifesto da Criatura Viva: Intenção, Vontade e Expressão Orgânica no Mário

**Documento:** `docs/MANIFESTO_CRIATURA_VIVA_MARIO.md`  
**Status:** Visão Criativa e Diretriz Arquitetural Fundamental  
**Autor & Direção:** Visão autoral alinhada em 12/11/2026  

---

## 1. O Conceito Central: Mário não é um App, é uma Criatura no seu Desktop

Mário é um armário vivo com corpo, peso, carisma, curiosidade e, acima de tudo, **vontade própria**.

Ele não foi projetado para ser:
- Uma massinha de modelar inerte ou um *ragdoll* puramente passivo.
- Um conjunto de equações de física desconectadas da emoção.
- Um "mostruário de animações" que dispara eventos aleatórios a cada cronômetro de 10 segundos.

Ele foi concebido para ser um **mascote de interação viva, fluidez, humor e responsividade tátil**.

---

## 2. A Tensão Viva: Intenção Ativa vs Física Reativa

A magia do Mário nasce da **luta contínua entre a vontade dele e a física do usuário**.

```
   ┌──────────────────────────────────────────────────────────────┐
   │                     A VONTADE DO MÁRIO                       │
   │  (Metas internas, curiosidade, teimosia, humor e impulsos)   │
   └──────────────────────────────┬───────────────────────────────┘
                                  ▲
                         A TENSÃO ORGÂNICA
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │                    A FÍSICA DO USUÁRIO                       │
   │  (O cursor clica, puxa, arremessa, interrompe e brinca)      │
   └──────────────────────────────────────────────────────────────┘
```

1. **A Física dá a sensação tátil do toque:**
   - O arraste com o mouse faz o corpo balançar, ceder e responder matematicamente à aceleração real da mão do usuário. É isso que dá a sensação de pegar um objeto físico e não um sticker estático.
2. **A Vontade dá a alma e a resistência:**
   - Se o Mário estiver tentando ir até um canto da tela e o usuário segurá-lo, ele **não** aceita passivamente. Ele tensiona os braços, esperneia no ar na direção de onde queria ir, faz força contra o vetor do mouse e tenta se soltar.
   - O movimento é o resultado dinâmico dessa oposição.

---

## 3. O Fim dos "Eventos sem Sentido": Tudo é Expressão de um Ser Vivo

Antes deste alinhamento, eventos como dançar, mudar de idle, espirrar ou soltar tentáculos eram tratados como timers soltos. No novo paradigma, **cada ação tem causa, motivação e consequência emocional**:

### A. Idles e Humores
- **Não é:** um cronômetro arbitrário que troca de personalidade a cada 10s.
- **É:** a reação ao ambiente e ao histórico com o usuário.
  - Se o usuário ignora o Mário por muito tempo: ele fica entediado, senta, apoia a cabeça ou começa a inspecionar ícones do desktop.
  - Se o usuário acabou de brincar com ele: ele fica curioso, hiperativo ou brincalhão.
  - Se o usuário o repreendeu ou jogou longe: ele fica desconfiado, emburrado ou desafiador.

### B. A Dança (Groove, Ritmada, Cyberpunk)
- **Não é:** uma opção estática de menu ou uma mola oscilante.
- **É:** uma explosão de energia quando ele alcança algo que queria (comemoração), quando detecta áudio/música no computador, ou quando quer chamar a atenção do usuário de forma atrevida.

### C. A Espiada dos Tentáculos
- **Não é:** um contador mecânico de 60 segundos de ociosidade.
- **É:** o segredo cósmico que vive dentro do armário. Os tentáculos saem quando o Mário acha que o usuário não está olhando (cursor parado há muito tempo e tela calma), ou para tentar alcançar um objeto fora do alcance dos braços curtos, ou como reação de susto e bravata.

### D. O Espirro e Reações Físicas
- **Não é:** um evento aleatório.
- **É:** consequência direta de interações físicas: cutucões rápidos demais, poeira acumulada no rodapé da tela ou por ter tentado "engolir" o que não devia.

---

## 4. O Exemplo Emblemático (O Roubo do Mouse)

Para ilustrar o tipo de organicidade que o sistema deve suportar naturalmente:

1. **Curiosidade:** Mário vê um elemento interessante na tela e decide caminhar até lá.
2. **Interrupção:** O usuário clica e segura o Mário no meio do caminho.
3. **Resistência:** Mário esperneia na direção do alvo, puxa na direção oposta, e na terceira tentativa se solta do drag.
4. **Repreensão:** O usuário irritado joga o Mário longe na barra de tarefas.
5. **Reação & Vingança:** Mário bate no chão com *squash*, sacode a poeira, olha desafiadoramente para o cursor, abre a portinha do armário com antecipação exagerada e... **NHAC!** Dá o bote e engole a seta do mouse.
6. **Agência Total:** O Windows oculta o cursor real por alguns segundos. Mário anda com o cursor "dentro da barriga" até o elemento que queria ver, dá um pulinho e clica nele.
7. **Resolução:** Satisfeito, Mário vira para o usuário, cospe o cursor de volta com um quique cômico na tela e volta às suas atividades normais.

---

## 5. Arquitetura em 3 Pilares

Para sustentar esse comportamento sem scripts engessados de vídeo:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   PILAR 1: SISTEMA DE DESEJOS & AGÊNCIA                │
│  Controla intenções, foco de atenção, nível de teimosia e paciência.   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   PILAR 2: NÚCLEO ARTÍSTICO COM OS 12 PRINCÍPIOS       │
│  Poses fortes, arcos, timing contrastado, antecipação e exagero.       │
│  (Resistir ao drag, dar o bote, mastigar, cuspir, celebrar, descansar)│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   PILAR 3: CAMADA TÁTIL PROCEDURAL & DESKTOP           │
│  Física Pymunk de colisão e gravidade; inércia de mouse ao toque;      │
│  manipulação de visibilidade/posição do cursor via Win32.              │
└────────────────────────────────────────────────────────────────────────┘
```

Este manifesto é a bússola para qualquer decisão de animação, código e design no SeJogaDesktopCompanion.
