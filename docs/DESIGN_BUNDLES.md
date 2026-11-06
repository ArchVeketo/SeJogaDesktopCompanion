# Design: Sistema de Bundles, Ciclo de Vida e Bundle Cyberfunk

**Data:** 2026-11-05
**Status:** Proposta para revisão. Nenhum código implementado. A implementação do piloto (Cyberfunk) depende da aprovação deste documento; a parte 3D depende do relatório de viabilidade (`.agents/tasks/viabilidade-mario-3d/relatorio.md`).

---

## 1. Visão geral

Um **bundle** é a personalidade completa do Mário, expressa como **dados**. Ele substitui o conceito atual das 9 personalidades de idle (que passam a ser acessíveis apenas via modo debug). Trocar de bundle troca de uma vez o jeito do Mário ficar parado, dançar, se entreter, caminhar e os objetos que o acompanham.

Princípio central: **o motor de animação não sabe o que é um bundle.** O motor (molas por junta, camadas aditivas, respiração, colisão) só recebe poses para tocar. O bundle apenas declara keyframes e parâmetros. A ponte entre os dois é um gerente fino. Assim, adicionar um bundle novo é escrever um arquivo de dados, sem tocar no motor.

Isto é a culminação da direção "animação como dados" que o projeto vem seguindo (ver `anim_clips.py`, `idle_clips.py`).

---

## 2. Conteúdo de um bundle

Cada bundle reúne:

| Categoria | Quantidade | Papel |
| --- | --- | --- |
| Idle | 1 | Como o Mário fica parado no tema (vivo via springs + respiração) |
| Danças | 4 | Grooves do tema; disparam com música; o seletor escolhe entre as 4 por energia/BPM |
| Poses aleatórias | 4 | Gestos/emotes que disparam sozinhos no idle (como os gestos ambientes atuais) |
| Caminhar | 1+ | Animação de locomoção do tema (categoria nova) |
| Eventos aleatórios | 1+ | Ações raras e espontâneas: espirro, tropeço, coçar, etc. (categoria nova) |
| Prop | 1 | Objeto do tema; pode ser **ancorado** na mão OU **asset de cenário** (o bundle decide) |
| Parâmetros | — | Ajustes opcionais de tensão de spring/respiração próprios do tema |

O prop não precisa de ancoragem perfeita: um bundle pode declarar que seu prop é segurado (ex.: lata de spray na mão) ou que aparece no ambiente (ex.: MP3 player tocando numa caixa de som ao lado).

---

## 3. Arquitetura em três camadas

### Camada 1 — Bundle como dados
Um bundle é uma estrutura declarativa (um módulo Python de dados ou um arquivo TOML/JSON carregado em runtime). Esboço conceitual:

```
Bundle "cyberfunk":
  idle:    <clipe de dados>
  dancas:  [groove, spin, headbob, break]      # 4 clipes
  poses:   [spray, dedao, cruzar, apontar]      # 4 clipes + regra de disparo
  caminhar: <clipe de locomoção>
  eventos: [espirro, ...]                       # clipes + probabilidade
  prop:    { nome: "lata_spray", modo: ancorado|cenario, junta?: "hand", pose_uso?: "spray" }
  tensao:  <overrides opcionais de spring_tuning / respiracao_tuning>
```

Cada "clipe" segue o formato já usado em `anim_clips.py` (keyframes `(tempo, (x,y,z))` por grupo do rig, com easing). Idles e loops podem ser aperiódicos de propósito (ver a decisão registrada sobre idle aberto).

### Camada 2 — Gerente de bundles (a peça nova)
Um módulo novo (sugestão: `src/sejoga/bundles.py`), engine-agnóstico, que:
- Conhece os bundles disponíveis.
- Sabe qual está **ativo** (lido da config; substitui o seletor de personalidade de hoje).
- Entrega ao `AnimationController` o conteúdo do bundle ativo (idle, listas de danças/poses/eventos, prop) sob demanda.

O `AnimationController` muda pouco: hoje ele pergunta "qual pose de idle para a personalidade X?"; passa a perguntar "qual idle o bundle ativo define?". A máquina de estados (idle → dança → drag → fall → sleep) permanece; muda a **fonte do conteúdo**.

### Camada 3 — Seleção pelo usuário
Nas Configurações (UI PySide6 existente), o seletor de "personalidade do idle" vira **seletor de bundle**. Escolher um bundle troca tudo junto. As 9 personalidades antigas ficam atrás de uma opção de **modo debug** (lista crua, para teste).

### Por que é limpo
- O motor não conhece bundles; o bundle não conhece o motor. O gerente é a ponte fina.
- Bundle novo = arquivo de dados. Nenhuma mudança no motor.
- Testável sem engine (os dados e o gerente são Python puro).

---

## 4. Ciclo de vida do mascote

O comportamento é dirigido por **tempo sem interação** e por **eventos**. O bundle ativo só define *quais* animações tocam em cada estado; a máquina de estados é a mesma para todos os bundles. Isto evolui a máquina atual (que já tem idle, dança por música, drag/fall, e sleep por ociosidade).

### 4.1 Funil de ociosidade (tempos configuráveis)

```
                 interação / mouse perto
   ┌──────────────────────────────────────────────┐
   │                                                │
   ▼                                                │
IDLE ATIVO ──(tempo)──▶ POSES ALEATÓRIAS ──(tempo)──▶ SONOLÊNCIA
(vivo: springs    (tédio: as 4 poses do    (idle desacelera,
 + respiração)     bundle, mais frequentes  respiração lenta,
                   com o tempo)             cabeça pende)
                                                 │
                                              (tempo)
                                                 ▼
                                          DORMIR EM PÉ
                                                 │ (tempo)
                                                 ▼
                                          DORMIR SENTADO
                                                 │ (tempo)
                                                 ▼
                                   DORMIR DEITADO NO CHÃO
                                   (desce via física)
```

- Quanto mais tempo sem interação, mais fundo o sono. Cada limiar de transição é configurável.
- **Poses aleatórias** aparecem a qualquer momento no idle (o "tédio"), ficando mais frequentes conforme o tempo passa, até dar lugar à sonolência. (Confirmado com o usuário.)
- **Qualquer interação** (clique, hover, arraste, música, mouse próximo) acorda o Mário com a animação de `wake` e retorna ao idle ativo.

### 4.2 Eventos que interrompem o funil

| Evento | Comportamento |
| --- | --- |
| Música detectada | Entra em **dança**; o seletor escolhe entre as 4 do bundle por energia/BPM; pode trazer o **prop** (ex.: MP3 player tocando). Música para → volta ao idle. |
| Espirro (raro/aleatório) | Traz o prop + pose em conjunto. Usa a respiração: enche o peito a cada fungada, esvazia ao espirrar até passar o braço no nariz (gancho `empurrar()` já existe em `respiracao.py`). |
| Arraste / física | drag → fall → land. Interrompe tudo; volta ao idle ao assentar. |
| (Futuro) Atenção | Reagir a algo na tela: virar o corpo/cabeça, fingir surpresa (depende da expansão 3D). |

### 4.3 O que já existe vs. o que é novo
- **Já existe:** idle↔sleep por ociosidade, dança por música, drag/fall/land, gestos ambientes (wave/stretch) por timer.
- **Novo:** os estágios intermediários de sono (sonolência → em pé → sentado → deitado no chão), as poses de "tédio" puxando do bundle, e toda a fonte de conteúdo vindo do bundle ativo.

---

## 5. Bundle piloto: Cyberfunk

Identidade: street/skate, groove solto, atitude "na dela". É a cara-base do Mário e o menor risco (os idles atuais já têm essa raiz). Todo movimento abaixo é **original do Mário**, inspirado na vibe do gênero (Bomb Rush Cyberfunk / Jet Set Radio), não cópia de coreografia.

### 5.1 Idle
Peso alternando entre os pés, quadril solto, ombros relaxados, cabeça acompanhando um ritmo imaginário, braços longos pendendo com leve balanço. Nunca totalmente parado (respiração + springs). Aperiódico de propósito.

### 5.2 Danças (4)
1. **Groove base** — balanço lateral de quadril/tronco, cabeça no contratempo, braços atrasando (lag chain).
2. **Spin/flow** — giro de tronco com braços abrindo, estilo manobra de patins. (Se a expansão 3D permitir girar o corpo, esta dança ganha muito.)
3. **Headbob pesado** — foco em cabeça e ombros, quicando no beat.
4. **Breakdance leve** — agacha, apoia, uma pernada estilizada, volta (pose, sem cair de verdade).

### 5.3 Poses aleatórias (4)
1. **Spray** — grafitar o ar (usa o prop, se presente).
2. **Dedão pra cima** com atitude.
3. **Cruzar os braços** e virar a cabeça (cool).
4. **Apontar pra frente** (chamando).

### 5.4 Caminhar
Locomoção de groove solto — passada com balanço de ombros e braços longos atrasando, cabeça acompanhando. (Depende do sistema de locomoção autônoma — ver viabilidade 3D.)

### 5.5 Eventos aleatórios
Espirro (base, já descrito), e ganchos para tropeço/coçar conforme o tema evoluir.

### 5.6 Prop
**Lata de spray.** Modo: ancorado na mão durante a pose de spray. Geometria 3D vem do pipeline Blender na outra máquina (ver `BACKLOG_CONTEUDO.md` seção 6); no piloto a **animação de usar o prop** fica pronta e o modelo entra como placeholder até existir.

---

## 6. Como o conteúdo é produzido e verificado

Para cada clipe de um bundle, o fluxo é:
1. Referência de vibe do tema (descrição estruturada do movimento).
2. Keyframes no formato de dados.
3. Verificação objetiva com as ferramentas existentes:
   - `tools/analisar_anim.py` — sem trancos, energia > 0, suavidade.
   - `tools/dump_rig_estado.py` / `rig_debug` — orientação correta das partes.
   - `tools/verificar_gesto.py` — a pose bate com a spec do gesto.
4. Validação estética final do usuário na GPU.

Divisão de responsabilidade: as ferramentas garantem correção mecânica/semântica; o usuário valida charme/estilo.

---

## 7. Ordem de implementação proposta

1. **Sistema de bundles** (formato + gerente + troca via config + modo debug para as 9 antigas), com **Cyberfunk** como primeiro bundle preenchido. Prova a arquitetura inteira com um tema real.
2. Validação do usuário na GPU.
3. **Estágios de sono** do ciclo de vida (sonolência → em pé → sentado → deitado), dirigidos por tempo.
4. Cada tema seguinte (JoJo, Funk, Disco, FNF) = adicionar arquivo de dados.

Observação: as categorias "caminhar" e "virar o corpo" nas danças/poses dependem do resultado da **investigação de viabilidade 3D**. O sistema de bundles pode ser construído antes e ganhar essas categorias quando o 3D estiver decidido.

---

## 8. Visão futura (sem escopo agora)

**Conversor de animação da internet → bundle do Mário.** Pegar uma animação externa (mocap/BVH/clipe) e remapear para os grupos do rig do Mário, com âncoras/eixos selecionáveis. A base de `rig_mapa` ajuda (eixos/partes já mapeados). É um épico grande (parsing de formatos, retargeting, UI de mapeamento); fazer apenas depois que a base de bundles estiver sólida. Registrado para não se perder.

---

## 9. Decisões em aberto (para a revisão do usuário)

1. Formato concreto do bundle: módulo Python de dados (como `idle_clips.py` hoje) ou arquivo externo TOML/JSON com hot-reload. Recomendação: começar como módulo Python (zero infra nova) e migrar para externo se a autoria pedir.
2. Quantas animações de "caminhar" e "eventos" por bundle (o mínimo é 1 cada; pode crescer).
3. Se o modo debug das 9 personalidades antigas fica na UI normal (escondido) ou só via config/flag.
4. Tempos default do funil de ociosidade (quando começa o tédio, a sonolência, cada estágio de sono).
