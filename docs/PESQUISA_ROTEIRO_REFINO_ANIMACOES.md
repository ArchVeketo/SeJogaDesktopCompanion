# Pesquisa Consolidada: Roteiros, Idles e Loop de Refino de Animações do Mário

**Data:** 18/11/2026  
**Alinhamento Canônico:** [MANUAL_UNIFICADO_MARIO.md](MANUAL_UNIFICADO_MARIO.md), [ROTEIRO_DE_ANIMACOES.md](ROTEIRO_DE_ANIMACOES.md), [REFERENCIAS_IDLES_CYBERFUNK.md](REFERENCIAS_IDLES_CYBERFUNK.md), [ESTUDO_LOOPS_GACHA_MIXAMO.md](ESTUDO_LOOPS_GACHA_MIXAMO.md) e [PLANO_ECOSSISTEMA_ANIMACOES_ZZZ.md](PLANO_ECOSSISTEMA_ANIMACOES_ZZZ.md).

---

## 1. Síntese das Referências Reais e Tradução para a Anatomia do Mário

O Mário combina três particularidades anatômicas no rig Blockbench (`91 nós`, `30 grupos lógicos`, `10 malhas de dedos fatiadas em cascata`):
1. **Cabeça-armário grande e rígida sem rosto pintado** (a emoção vem da inclinação de `head`, abertura de `door`, vibração de `fones` e `antena-direita`/`antena-esquerda`, e aparições de tentáculos);
2. **Proporções urbanas *chunky*** (mangas largas, luvas grandes com dedos individuais, calça autoral deformável `PernasTecido` e botas pesadas);
3. **Habitante vivo no interior** (uma criatura tímida, curiosa e cheia de atitude que divide a vontade própria do corpo com os tentáculos ocultos atrás da porta).

| Obra de Referência | Princípio Chave Extraído | Como Traduzir Diretamente para o Rig do Mário |
| :--- | :--- | :--- |
| **Bomb Rush Cyberfunk & Jet Set Radio** | **Groove como Estado de Repouso ("Idle Groove"):** O personagem nunca está "esperando parado"; seu metrônomo interno está travado na batida. Peso assimétrico num quadril, joelhos sempre destravados (*springy*) e isolamento do tronco superior (mexer no Walkman, girar o ombro, checar o pulso). | Manter os joelhos com micro-flexão elástica (`movimento_pernas.py`), bacia levemente deslocada em contrapeso com `peitoral` e `head`, e transição instantânea (*snap response*) do groove para a caminhada/dança porque a postura já está carregada de energia potencial. |
| **Hi-Fi Rush (Chai)** | **Antecipação no Contra-Tempo (*Off-Beat Wind-Up*) e Ação Secundária Elástica:** Antecipações seguram a tensão no *upbeat* ("&") e disparam no *downbeat*. Fios, casacos e acessórios chicoteiam com overshoot quando o corpo trava numa pose (*freeze frame*). | Em `escutar_fone`, `batida_guardada` e nas danças, carregar o recuo do tronco/ombro `0.18s–0.25s` antes do acento. Ao parar numa pose, deixar o `fio do fone` (Verlet), as argolas das antenas e os punhos (`hand`/`hand2`) passarem do ponto (*overshoot*) e assentarem `0.15s–0.35s` depois. |
| **Zenless Zone Zero (HoYoverse)** | **Arquitetura de Postura Hub + Cascata Hierárquica Estrita:** Todo clipe de idle ou reação parte de um Hub cíclico limpo (`4.0s` a `12.0s`) com defasagem de fase explícita: `quadril (0.0s) → cintura/peito (+0.18s) → cabeça (+0.30s) → braço/antebraço (+0.40s) → punho/dedos/tecido (+0.50s)`. | Nunca atingir o keyframe de pico no mesmo segundo em todas as juntas de `tracks` (`animation.py`). Deslocar sistematicamente os tempos dos keyframes de `cintura` → `peitoral` → `head` → `right-arm`/`left-arm` → `ant-arm` → `hand` para criar chicote orgânico e peso real. |
| **WALL·E & Astro Bot** | **Linguagem Corporal Mecânica sem Rosto (*Head Tilt & Chassis Compression*):** Sem sobrancelhas ou boca humana, o *roll* e o *pitch* da cabeça são a "pupila emocional". Inclinar a cabeça de lado (`roll ±8°..14°`) lê imediatamente como curiosidade/dúvida; encolher o pescoço/peito lê como timidez; abrir a portinha `2°..6°` funciona como um "suspiro" ou "boquiaberto". | Usar a porta (`door`) como subtexto emocional sutil em idles e reações (entreabrir `3°..8°` na surpresa, no suspiro de sono ou na curiosidade, sem precisar ejetar tentáculos toda vez) e usar as antenas (`antena-direita`/`antena-esquerda`) como "orelhas/sobrancelhas" mecânicas que divergem ou abaixam conforme o humor. |
| **Splatoon & Animal Crossing: New Horizons** | **Micro-Ações de Monólogo Interno (*Fidgets with Intent*):** Em *Animal Crossing*, toda reação tem 4 tempos claros: *Percepção → Pausa de Leitura → Gesto Curto na Silhueta Externa → Assentamento*. Em *Splatoon*, o tédio vira atitude (checar o equipamento, rolar o ombro, bater o pé). | Posicionar mãos sempre **fora da silhueta do gabinete** (evitando cobrir a frente da TV, onde a leitura se perde na câmera frontal) e incluir uma pausa de leitura (`0.25s–0.45s`) entre notar algo e agir. |

---

## 2. Catálogo de Novos Idles e Micro-Ações Contextuais (Próxima Geração)

Atualmente `CENAS_IDLE` (`src/sejoga/animacao/animation.py` e `cenas_idle.py`) já implementa 6 cenas:
- **Manutenção/Equipamento:** `ajeitar_fone` (`2.6s`), `fone_com_problema` (`5.2s`), `argolas_antena` (`3.8s`);
- **Contextuais (entregues em 17/11):** `escutar_fone` (`6.4s`), `disfarcar_olhar` (`5.8s`), `batida_guardada` (`6.6s`).

Abaixo estão **6 novos roteiros de idles/micro-ações** desenhados especificamente para a identidade do Mário (cabeça-armário, Walkman, luvas grandes, antenas e criatura interna), prontos para autoria em `CENAS_IDLE` sem exigir novos assets:

### 2.1 `conferir_luva` ("Ajeitar a Luva e Estalar os Dedos" — `5.2s`)
- **Motivação / Gatilho:** Pós-interação física (após voltar de `DRAG`, `LAND`, `HIT` ou uma caminhada longa, quando o Mário "arruma o visual").
- **Roteiro dos 4 Tempos:**
  1. **Antecipação (`0.0s – 0.8s`):** Mário transfere o peso para a perna esquerda, inclina `head` para baixo e para a direita (`pitch +8°`, `yaw -14°`, `roll +5°`) olhando para a própria luva direita.
  2. **Ação Principal (`0.8s – 2.9s`):** Braço direito sobe em arco lateral (`right-arm`, `ant-arm`), gira o pulso (`hand` roll `-25° → +20°`) examinando o dorso e a palma; a mão esquerda aproxima-se rapidamente da borda do punho direito como se puxasse/ajustasse a luva; em seguida os dedos da mão direita abrem (`open_hands`) e fecham num punho firme (`close_fists`) testando a pegada.
  3. **Follow-Through & Sustentação (`2.9s – 4.0s`):** Pequeno aceno positivo de cabeça (`head` pitch `-4° → +3°`, "tudo no esquema") com ombros abrindo em postura confiante (`peitoral` pitch `-3°`).
  4. **Assentamento (`4.0s – 5.2s`):** Tronco relaxa primeiro (`4.2s`), braços descem em pêndulo suave (`4.5s`) e os dedos retomam a curvatura neutra por último (`5.0s`).

### 2.2 `contar_nos_dedos` / `pensar_gabinete` ("Pensando com o Gabinete" — `6.4s`)
- **Motivação / Gatilho:** Quando a Agência (`agencia.py`) está avaliando uma nova meta na tela ou após mudança de janela em foco.
- **Roteiro dos 4 Tempos:**
  1. **Antecipação (`0.0s – 0.9s`):** Compressão leve do torso (`cintura` pitch `+3°`), cabeça inclina num *head tilt* clássico estilo WALL·E (`head` roll `-11°`, yaw `+8°`), antenas assimétricas (uma sobe, outra desce).
  2. **Ação Principal (`0.9s – 3.8s`):** Mão direita sobe ao lado da bochecha do gabinete (fora da linha da porta para silhueta limpa) e faz dois pequenos toques pensativos no ar (`ant-arm` + `hand` + gesto `finger_gun` / indicador estendido), enquanto a mão esquerda apoia na cintura/Walkman.
  3. **Momento "Eureka!" (`3.8s – 4.8s`):** Micro-salto de extensão no peito (`peitoral` pitch `-4°`), cabeça endireita rápido (`head` roll `0°`, pitch `-5°`), portinha dá um micro-estalo de `4°` e fecha, como uma lâmpada acendendo.
  4. **Assentamento (`4.8s – 6.4s`):** Rampa suave de volta ao Hub com atraso de `0.22s` entre peito, ombro e mão.

### 2.3 `segurar_porta_timido` ("Opa, Quase Saiu!" — `4.8s`)
- **Motivação / Gatilho:** Repouso prolongado calmo ou logo após o cursor passar perto do rosto sem clicar. Explora o humor da criatura viva dentro do armário sem disparar a cena longa de tentáculos.
- **Roteiro dos 4 Tempos:**
  1. **Antecipação (`0.0s – 0.7s`):** As antenas tremem de leve; a porta (`door`) começa a entreabrir sozinha (`0° → 14°`) como se a criatura lá dentro estivesse empurrando para espiar.
  2. **Ação Principal (`0.7s – 2.4s`):** O corpo do Mário leva um micro-susto cômico (`peitoral` recua `-3.5°`, `head` pitch `-6°`); a mão direita sobe rápido num arco amplo e "empurra" a porta de volta (`door` fecha `14° → 0°` em `0.25s` no instante em que a mão chega perto).
  3. **Follow-Through & Olhar Desconfiado (`2.4s – 3.7s`):** Com a mão ainda perto do queixo do gabinete, Mário olha para os dois lados (`head` yaw `-12° → +12°`) conferindo se o usuário viu.
  4. **Assentamento (`3.7s – 4.8s`):** Suspiro de alívio (peito desce) e braço retorna devagar ao lado do corpo.

### 2.4 `checar_walkman` ("Trocando de Faixa no Cinto" — `5.6s`)
- **Motivação / Gatilho:** Transição de faixa de mídia no Windows (SMTC) ou variação autônoma quando `music_playing` está ativo em volume baixo.
- **Roteiro dos 4 Tempos:**
  1. **Antecipação (`0.0s – 0.8s`):** Quadril desloca peso para a direita, tronco gira em 3/4 (`cintura` yaw `-8°`, `peitoral` yaw `-12°`) e cabeça olha para o Walkman preso no lado esquerdo do cinto (`head` pitch `+14°`, yaw `-16°`).
  2. **Ação Principal (`0.8s – 3.2s`):** Mão esquerda vai até o cinto/Walkman e executa dois cliques curtos de pulso (`hand2` pitch); no segundo clique, a cabeça dá um aceno forte de aprovação ao encontrar a batida certa.
  3. **Follow-Through (`3.2s – 4.4s`):** Ombros entram num *shimmy* curto de 2 tempos acompanhando a nova música enquanto a mão direita faz um gesto rápido (`hang_loose` ou `peace` sutil).
  4. **Assentamento (`4.4s – 5.6s`):** Retorno fluido ao Hub musical.

### 2.5 `alongar_pescoco_ombros` ("Soltar a Carcaça Pesada" — `6.0s`)
- **Motivação / Gatilho:** Após muito tempo em `FOCO_TELA` ou após sair do estado `SLEEP`.
- **Roteiro dos 4 Tempos:**
  1. **Antecipação (`0.0s – 1.0s`):** Inspiração funda subindo os dois ombros (`shoulder`/`shoulder2` roll) e comprimindo levemente o pescoço.
  2. **Ação Principal (`1.0s – 3.8s`):** Cabeça desenha um meio-círculo lento e pesado pela frente (`head` roll `-14°` → pitch `+10°` → roll `+14°`), enquanto os braços pendem pesados como chumbo em contrapeso.
  3. **Follow-Through (`3.8s – 4.8s`):** Soltura rápida dos ombros de uma vez (*drop* com overshoot elástico na coluna e balanço do fio do fone).
  4. **Assentamento (`4.8s – 6.0s`):** Alinhamento da cabeça por último (`+0.3s` após o peito).

### 2.6 `groove_um_pe` ("Apoio de Rua no Calcanhar" — `7.2s`)
- **Motivação / Gatilho:** Repouso confiante (`street` / `brc_stance`) com música ativa ou humor alto.
- **Roteiro dos 4 Tempos:**
  1. **Antecipação (`0.0s – 0.9s`):** Transfere o centro de massa para a perna esquerda; joelho direito flexiona liberando o pé direito para apoiar no calcanhar (`right_ankle` positivo).
  2. **Ação Principal (`0.9s – 5.0s`):** Marca 4 compassos batendo levemente a ponta da bota direita no chão em oposição ao balanço do ombro esquerdo e da cabeça; braços cruzados baixos ou mão no quadril com silhueta aberta.
  3. **Follow-Through (`5.0s – 6.0s`):** Pausa estilosa no 4º tempo antes de transferir o peso de volta para os dois pés.
  4. **Assentamento (`6.0s – 7.2s`):** Sola direita planta firme e tronco recupera o eixo central.

---

## 3. Roteiros de Refino para Elevar a Fluidez das Animações Existentes

Para que tanto os 11 idles (`IDLE_CLIPS`), as 6 cenas (`CENAS_IDLE`) e as reações (`gestos_reacao.py`, `teimosia_pose.py`) atinjam fluidez de estúdio, cada take deve seguir a **Regra dos 4 Tempos + Cascata de Fase**:

### 3.1 Fórmula Matemática de Defasagem (Cascata Sem "Bloco Duro")
Um erro comum em animação procedural/keyframe é colocar todas as juntas (`cintura`, `peitoral`, `head`, `right-arm`, `ant-arm`, `hand`) mudando de direção exatamente no mesmo timestamp $t_k$. Isso faz o boneco parecer um bloco mecânico.
- **Regra Prática de Keyframing em `animation.py`:**
  Para qualquer mudança de pose no instante base $t_0$:
  - `cintura`: $t_0 + 0.00\text{s}$ (inicia o impulso a partir do quadril)
  - `peitoral`: $t_0 + 0.12\text{s} \text{ a } 0.16\text{s}$
  - `head`: $t_0 + 0.22\text{s} \text{ a } 0.28\text{s}$ (exceto quando o olhar lidera a ação; nesse caso `head` vai em $t_0 - 0.12\text{s}$ e o corpo segue!)
  - `right-arm` / `left-arm`: $t_0 + 0.18\text{s} \text{ a } 0.24\text{s}$
  - `ant-arm` / `ant-arm2`: $t_0 + 0.28\text{s} \text{ a } 0.34\text{s}$
  - `hand` / `hand2`: $t_0 + 0.36\text{s} \text{ a } 0.42\text{s}$
  - `antena-direita` / `antena-esquerda`: $t_0 + 0.40\text{s} \text{ a } 0.48\text{s}$ (com pequeno overshoot de sinal oposto na parada).

### 3.2 Micro-Antecipação e Overshoot no Assentamento
- **Antecipação Obrigatória (10% a 15% da amplitude na direção oposta):** Antes de girar a cabeça para a direita (`yaw +12°`), recuar `-1.8°` durante `0.18s`. Antes de levantar o braço (`roll -35°`), soltar `+3°` para baixo junto com uma leve compressão do peito.
- **Overshoot Suave no Retorno (Assentamento Vivo):** Ao voltar da pose principal para `(0, 0, 0)` no final da cena, passar `5% a 8%` além do neutro (ex.: `-1.2°` antes de `0.0°`) no penúltimo keyframe. Isso elimina a sensação de "interpolação linear que bate num muro invisível".

### 3.3 Integração dos Dedos nos Clipes e Cenas (`FingerGestures`)
- Conforme detectado na auditoria do rig dos dedos:
  - As 10 malhas dos dedos já são fatiadas em 3 falanges cada (`dedos_malha.py`), e os clipes de emote (`assets/animation/loops/*.json`) já possuem dados de `dedos` exportados, mas `renderizador.py` (`update_appendages`) ainda não repassava `dedos_clipe` para `self.finger_gestures.update(...)`.
  - Passar `dedos_clipe` do controlador para `FingerGestures.update` e permitir gestos de mão esquerda/direita independentes dará vida imediata às mãos durante danças, reações e cenas de fone!

---

## 4. Plano Prático de Loop de Estudo e Refino (Seguindo o Roadmap)

Para evoluir o catálogo com segurança, zero regressão e validação visual rápida:

### Passo 1 — Estabilização Visual Base (Em Execução por `@acoes`)
1. Corrigir o crash de `MusicSpeaker.seat` no modo rádio compacto.
2. Restaurar o menu de contexto completo e as 31 danças de prévia/seleção em `janela.py`.
3. Restaurar o interior escuro índigo profundo (`RGB(11, 0, 68)` unlit) da cabeça e a soldagem por vértice das ventosas nos tentáculos (`sistema_tentaculos.py`).
4. Validar com `tools/render_preview.py` em `1024x1024` (70–85% de preenchimento de quadro, frontal + 3/4).

### Passo 2 — Ciclo Curto de Refino por Lote (Workflow para `@animacao`)
Para cada lote de animações (Lote A: *Reações de Toque/Defesa e Teimosia*; Lote B: *6 Cenas de Idle atuais*; Lote C: *Novas Cenas Contextuais*):
1. **Auditoria de Curvas e Silhueta:** Verificar tempos de antecipação, extremas, defasagem em cascata (`cintura → peitoral → head → arm → ant-arm → hand`) e ausência de auto-interseção com o gabinete/fones.
2. **Inspeção Offscreen Multi-Ângulo (`tools/render_preview.py` / `tools/revisar_animacoes.py`):** Renderizar os 4 momentos críticos da cena (*Antecipação*, *Ápice da Ação*, *Follow-Through* e *Assentamento*) em vista frontal e 3/4.
3. **Teste de Interrupção (`medir_salto_transicao.py`):** Confirmar que interromper a cena no ápice (por arraste, queda, clique ou início de caminhada) mantém continuidade $C^2$ no `PoseResolver` sem estalos angulares.
4. **Validação na Janela Real (`smoke_mouse.py` e `.exe`):** Confirmar leitura em tamanho real no desktop do usuário.
