# Diretriz Fundamental: Os 12 Princípios da Animação em Todas as Ações do Mascote

**Documento:** `docs/DIRETRIZ_12_PRINCIPIOS_ANIMACAO.md`  
**Status:** Proposta e Especificação Canônica de Animação  
**Referência Clássica:** *The Illusion of Life: Disney Animation* (Frank Thomas & Ollie Johnston)  
**Aplicação:** SeJogaDesktopCompanion (Mário — Modelo Blockbench low-poly, Panda3D, Pymunk, Procedural + Clipes)

---

## 1. Visão Geral e Mudança de Paradigma

### 1.1 O Erro da Fragmentação Prévia
Anteriormente, o projeto tratava os 12 princípios como uma lista de "etiquetas avulsas" (por exemplo: associando *Squash & Stretch* apenas ao pouso das caixas, *Antecipação* apenas ao ato de sentar, e *Arcos* apenas à passada). 

Essa fragmentação é a causa direta dos sintomas apontados pela direção do projeto:
- **Aspecto travado e engessado:** sem sobreposição (*Overlapping*) contínua no tronco e braços, o personagem parece um robô desmontável.
- **Braços em pose de stickman:** sem arcos (*Arcs*) orgânicos e sem ação secundária (*Secondary Action*), os membros tornam-se réguas estáticas.
- **Idles sem vida:** um repouso que não possui compressão (*Squash*), antecipação de peso (*Anticipation*) e ritmo (*Timing*) transmite morte e rigidez.

### 1.2 O Princípio da Totalidade Simultânea
Na animação profissional e viva, **os 12 princípios não são categorias excludentes**. **Eles operam juntos e simultaneamente em TODAS as animações do personagem**, do menor piscar de olhos ou respiração em *idle* até a queda física mais violenta ou a dança mais estilizada.

### 1.3 As Duas Ilusões que Prejudicaram o Projeto (E como desfazê-las)

#### 1. "A física deve ditar a animação (idle, dança, etc.)" — **Falso!**
- **O erro:** No passado, tentou-se usar simulação física (molas matemáticas com amortecimento, coeficientes `zeta`, Pymunk) para resolver movimentos internos do personagem como idle e dança. Simulação de mola pura produz apenas um boneco oscilante de pano ou um pêndulo mecânico; ela não produz ritmo, não produz intenção, não produz arcos expressivos e não produz poses fortes.
- **A regra real:** A física matemática (Pymunk, inércia de mouse) serve **estritamente para estímulos externos do desktop** (o mascote caindo no chão, sendo arrastado pelo cursor, colidindo com a barra de tarefas ou reagindo ao movimento brusco da janela). O **movimento interno** do personagem (respirar, olhar, caminhar, dançar, comemorar) é **animação artística pura**, guiada por poses, curvas e timing, e NÃO por equações de molas tentando "adivinhar" como um ser vivo dança ou descansa.

#### 2. "As personalidades ditam como o personagem se move" — **Falso!**
- **O erro:** Tratava-se o personagem como uma casca oca que só ganharia vida se uma das "9 personalidades" injetasse um vetor de modificadores. Se a personalidade não estivesse afinada, o mascote ficava travado.
- **A regra real:** **O NÚCLEO É PADRONIZADO E SOBERANO.** O Mário possui uma identidade corporal única, rica, viva e expressiva por padrão. A animação base de idle, caminhada, dança e repouso existe e brilha **sem precisar de nenhuma personalidade ativa**. As personalidades (se e quando existirem) são apenas temperos ou sutis modificadores cosméticos (ex: um olhar ligeiramente mais desconfiado ou relaxado), mas **nunca a fundação do movimento**.

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                CAMADA 1: O NÚCLEO SOBERANO                      │
    │  (Animação artística padronizada com os 12 princípios completos) │
    │  • Idle vivo com respiração e peso                              │
    │  • Locomoção expressiva com arcos e timing                      │
    │  • Dança rítmica coreografada (Hi-Fi, Cyberfunk, Persona)       │
    │  • Reações e poses com intenção clara                           │
    └────────────────────────────────┬────────────────────────────────┘
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
┌─────────────────────────────────────┐     ┌─────────────────────────────────────┐
│    CAMADA 2: FÍSICA EXTERNA         │     │   CAMADA 3: TEMPEROS OPCIONAIS      │
│ (Desktop, Pymunk & Cursor)          │     │ (Variações / Personalidades)        │
│ • Gravidade e colisão de janela     │     │ • Offsets cosméticos mínimos        │
│ • Arraste de mouse e impacto no solo│     │ • NUNCA substitui o núcleo          │
│ • Pêndulo passivo do fio do fone    │     │ • O personagem vive 100% sem elas   │
└─────────────────────────────────────┘     └─────────────────────────────────────┘
```

```
       ┌─────────────────────────────────────────────────────────────┐
       │                 OS 12 PRINCÍPIOS DA ANIMAÇÃO                │
       │                                                             │
       │  1. Compressão e Extensão       7. Arcos                    │
       │  2. Antecipação                 8. Ação Secundária          │
       │  3. Encenação                   9. Timing                   │
       │  4. Pose a Pose / Direta       10. Exagero                  │
       │  5. Continuidade / Sobreposição 11. Desenho Sólido          │
       │  6. Aceleração / Desaceleração 12. Apelo                    │
       └──────────────────────────────┬──────────────────────────────┘
                                      │
     Presentes obrigatoriamente e simultaneamente em cada ação:
     ┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
     │   IDLE &     │  LOCOMOÇÃO   │  ARRASTE &   │  REAÇÕES &   │   DESCANSO   │
     │  ATENÇÃO     │  (CAMINHADA) │   FÍSICA     │  INTERAÇÃO   │    (SONO)    │
     └──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

---

## 2. A Matriz Completa: 12 Princípios Aplicados a Cada Ação

Abaixo está o detalhamento de como cada um dos 12 princípios é incorporado em cada grande categoria de comportamento do mascote Mário.

---

### A. Idle, Respiração e Postura de Repouso (Ocioso)

Mesmo quando o mascote "não está fazendo nada", ele está vivo. O *idle* precisa respirar, ponderar e habitar o desktop.

1. **Compressão e Extensão (Squash & Stretch):**
   - Na inalação, o torso expande verticalmente (+2%) e afunila levemente nas laterais (-1%); na exalação, o torso assenta, comprimindo suavemente e alargando.
   - Os joelhos têm micro-flexão elástica acompanhando o ciclo respiratório, sustentando o peso corporal.
2. **Antecipação (Anticipation):**
   - Antes de alternar a perna de apoio (shift de peso), há uma sutil transferência contrária de massa e um pequeno rebaixamento de 0.5° no quadril.
   - Antes de virar a cabeça para seguir o mouse, o tronco faz um micro-recuo oposto de 1 frame.
3. **Encenação (Staging):**
   - O corpo fica naturalmente orientado em três quartos (3/4) em relação à câmera, nunca de frente chapada nem de perfil plano.
   - Braços descansam com silhueta clara e espaçada do tronco; os fones e a porta do armário permanecem visíveis contra o desktop.
4. **Ação Direta e Pose a Pose (Straight Ahead & Pose to Pose):**
   - Poses-chave rítmicas de postura (repouso alto, repouso baixo, postura curiosa/tímida) autoradas via *Pose to Pose*.
   - Ruído procedural contínuo (`ruido_procedural.py`) e micro-oscilações dos fios (`fio_corda.py`) calculados em *Straight Ahead* a cada quadro.
5. **Continuidade e Sobreposição (Follow Through & Overlapping Action):**
   - O tronco atinge o topo da respiração primeiro; a cabeça atinge 0.15s depois; os ombros descem, os cotovelos seguem em atraso, e os dedos das mãos assentam por último.
   - O cabo do fone de ouvido oscila em atraso de fase contínuo em relação ao movimento da cabeça.
6. **Aceleração e Desaceleração (Slow In & Slow Out):**
   - As transições de respiração e trocas de peso utilizam interpolação quíntica ($C^2$ suave), com velocidade e aceleração nulas nos extremos do ciclo.
7. **Arcos (Arcs):**
   - O movimento sutil de flutuação da cabeça e o balanço do tronco traçam um arco em formato de lemniscata ("figura em oito" horizontal e suave), nunca subindo e descendo em linha reta.
8. **Ação Secundária (Secondary Action):**
   - Micro-movimentos orgânicos dos 4 dedos de cada mão (`dedos_cascata.py`), pequenos ajustes na inclinação dos fones, e a porta do armário entreabrindo até 3° em respirações profundas.
9. **Timing:**
   - Ciclo respiratório calmo entre 3.2s e 4.0s. Troca de atitudes e micro-olhares espaçados a cada 10 a 16s, transmitindo serenidade e contemplação.
10. **Exagero (Exaggeration):**
    - O repouso do Mário não é um manequim neutro e mecânico: ele tem atitude própria e peso aparente. As inclinações de pescoço, o afundar dos ombros ao exalar e a expansão do peito são ligeiramente estilizados para tornar a presença do mascote marcante e expressiva por si só.
11. **Desenho Sólido (Solid Drawing):**
    - Pés travados no chão virtual via IK sem penetração de malha; os volumes de caixa do Blockbench mantêm a rigidez de suas proporções sem cruzamento de geometria dos braços com as costelas.
12. **Apelo (Appeal):**
    - O olhar acompanha o cursor do usuário com curiosidade genuína; postura simpática e carismática que transmite a presença de um companheiro amigável na tela.

---

### B. Locomoção (Caminhar, Correr, Virar e Parar)

Andar não é transladar um modelo rígido pelo eixo X: é um ciclo constante de queda controlada e impulso.

1. **Compressão e Extensão (Squash & Stretch):**
   - Na pose de contato e descida (*down position*), o corpo comprime ao absorver o impacto; na pose de passagem e elevação (*up position*), o corpo estica e ganha altura.
2. **Antecipação (Anticipation):**
   - Antes de iniciar a caminhada a partir do repouso, o tronco inclina-se para a frente e o joelho de apoio flexiona, carregando energia cinética.
   - Na parada, há uma passada de frenagem com o calcanhar cravado antes do corpo estabilizar.
3. **Encenação (Staging):**
   - Linha de ação inclinada no sentido do movimento; pernas abertas o suficiente para que a passada seja legível na silhueta, mesmo em visão 3D isométrica/desktop.
4. **Ação Direta e Pose a Pose (Straight Ahead & Pose to Pose):**
   - Ciclo de marcha estruturado em 4 poses essenciais por perna: Contato, Descida (Down), Passagem (Pass), Elevação (Up).
   - O balanço livre dos braços e do fone calcula a inércia em tempo real (*Straight Ahead*).
5. **Continuidade e Sobreposição (Follow Through & Overlapping Action):**
   - Quando as pernas param, o quadril desacelera primeiro, o torso avança por inércia e volta, a cabeça inclina e recupera, e os braços pendulam para frente e para trás até o repouso final.
6. **Aceleração e Desaceleração (Slow In & Slow Out):**
   - O pé livre acelera rapidamente ao sair do chão e desacelera suavemente ao atingir a extensão máxima antes do contato; o tronco suaviza nos ápices de elevação.
7. **Arcos (Arcs):**
   - O tornozelo no ar descreve uma trajetória parabólica convexa; o quadril sobe e desce em curva senoidal e oscila lateralmente desenhando um arco elíptico.
8. **Ação Secundária (Secondary Action):**
   - Os braços balançam em oposição às pernas (braço esquerdo com perna direita); os fones chacoalham levemente no impacto de cada passada; as pontas dos dedos relaxam para trás no movimento de vaivém.
9. **Timing:**
   - 110 a 120 passos por minuto para caminhada natural; cadência rítmica e uniforme que transmite o peso adequado do armário de madeira/metal.
10. **Exagero (Exaggeration):**
    - Passadas expressivas inspiradas em *Bomb Rush Cyberfunk*, com giro de quadril e balanço de ombros que conferem atitude de rua ao mascote.
11. **Desenho Sólido (Solid Drawing):**
    - IK de pernas garante que os pés se plantem no piso sem deslizar (zero *foot-sliding*); os eixos locais dos joelhos e cotovelos dobram estritamente em seus planos anatômicos corretos.
12. **Apelo (Appeal):**
    - O mascote anda com personalidade confiante e curiosa, olhando ocasionalmente para a frente da tela ou para as janelas que cruza.

---

### C. Física, Arraste e Queda Livre (Desktop Dynamics)

Quando o usuário clica e arrasta o mascote com o cursor, ou quando ele cai sob gravidade Pymunk.

1. **Compressão e Extensão (Squash & Stretch):**
   - Durante aceleração rápida do cursor ou queda livre, o corpo alonga ao longo do vetor de velocidade (*stretch*); ao atingir a barra de tarefas, comprime bruscamente em até 15% na vertical (*squash*) e expande na horizontal antes de saltar e estabilizar.
2. **Antecipação (Anticipation):**
   - Ao ser pego pelo clique do mouse, o mascote tensiona o corpo e encolhe levemente os membros antes de ser puxado; na iminência de tocar o chão, estica as pernas para baixo para antecipar o contato.
3. **Encenação (Staging):**
   - Em suspensão, o corpo inclina-se na direção contrária ao movimento da mão, mantendo os membros abertos para que a silhueta comunique claramente que está "no ar".
4. **Ação Direta e Pose a Pose (Straight Ahead & Pose to Pose):**
   - Poses de início e fim da queda autoradas via *Pose to Pose*.
   - A resposta à aceleração do mouse e as molas do corpo (`movimento_corpo.py`) funcionam em física puramente direta (*Straight Ahead*).
5. **Continuidade e Sobreposição (Follow Through & Overlapping Action):**
   - Quando o cursor para subitamente, o corpo do mascote oscila como um pêndulo, com a cabeça e os membros alcançando o ponto de inversão em tempos defasados.
   - No impacto com o solo, a base para no frame 0, a cintura no frame 2, o peito no frame 4, a cabeça no frame 6 e os fios no frame 9.
6. **Aceleração e Desaceleração (Slow In & Slow Out):**
   - As molas inerciais utilizam amortecimento crítico suave, evitando quiques robóticos ou paradas secas.
7. **Arcos (Arcs):**
   - Qualquer arraste curvilíneo do mouse transfere momento angular, fazendo o mascote balançar em arcos esféricos suaves ao redor do ponto de apoio/pega.
8. **Ação Secundária (Secondary Action):**
   - Braços e pernas reagem agitando-se sutilmente se a velocidade for alta; a porta do armário entreabre alguns graus devido à força centrífuga nas curvas rápidas.
9. **Timing:**
   - Queda rápida com aceleração da gravidade realista ($g$); impacto súbito e enérgico (1 frame de choque) com recuperação elástica em 3 fases (0.35s).
10. **Exagero (Exaggeration):**
    - Reações cômicas e cartunescas a arrastes velozes, com o mascote "esperneando" e os olhos/cabeça tentando acompanhar a velocidade.
11. **Desenho Sólido (Solid Drawing):**
    - O ponto de agarre (picking 3D) respeita a geometria real do armário; a massa aparente e o centro de gravidade permanecem consistentes no espaço.
12. **Apelo (Appeal):**
    - A sensação tátil de "pegar um boneco físico e vivo", com peso convincente e reações que dão vontade de brincar de arremessar ou balançar.

---

### D. Interação e Reações (Cutucar, Acariciar, Duplo Clique, Susto, Espirro)

Reações diretas ao input do usuário no mascote.

1. **Compressão e Extensão (Squash & Stretch):**
   - No cutucão, a área tocada sofre uma depressão imediata (*squash* local) e o corpo expande na direção oposta; no susto, o corpo estica para cima antes de encolher.
2. **Antecipação (Anticipation):**
   - No espirro, o peito estufa e o corpo vai todo para trás durante 0.8s acumulando pressão antes da explosão para a frente.
   - No carinho, o corpo recua uma fração de milímetro antes de ceder e se aninhar na direção do cursor.
3. **Encenação (Staging):**
   - A reação é projetada claramente para o espaço livre do desktop, sem que membros ou acessórios bloqueiem o rosto ou a leitura emocional.
4. **Ação Direta e Pose a Pose (Straight Ahead & Pose to Pose):**
   - Poses extremas de reação definidas (`gestos_reacao.py`) interpoladas com molas dinâmicas de impacto (*Straight Ahead*).
5. **Continuidade e Sobreposição (Follow Through & Overlapping Action):**
   - No espirro ou susto, a cabeça dispara para a frente, o tronco acompanha, e os fones chicoteiam além do limite antes de voltarem.
6. **Aceleração e Desaceleração (Slow In & Slow Out):**
   - Disparo explosivo rápido (saída com alta aceleração) seguido por um amortecimento longo e gracioso de volta à estabilidade.
7. **Arcos (Arcs):**
   - Gestos de braço (acenar, coçar a cabeça, empurrar o ar) percorrem trajetórias em arco amplo, com o punho liderando a curva.
8. **Ação Secundária (Secondary Action):**
   - Ao receber carinho, a porta do armário treme de contentamento, os dedos da mão se curvam suavemente e os pés relaxam.
9. **Timing:**
   - Acentuações rápidas (0.1s para o golpe da reação) e retornos lentos e curiosos (1.2s a 1.5s), criando contraste rítmico dinâmico (*snappy*).
10. **Exagero (Exaggeration):**
    - O susto faz o mascote saltar alguns pixels do chão; o espirro balança todo o gabinete do armário.
11. **Desenho Sólido (Solid Drawing):**
    - Restrições geométricas garantem que as mãos nunca atravessem o corpo (`colisao_bracos.py`) e que a porta respeite seus limites angulares mecânicos (0° a 38°/48°).
12. **Apelo (Appeal):**
    - Expressões corporais carismáticas que criam empatia e laço afetivo com o usuário.

---

### E. Descanso e Transições (Sentar, Dormir, Acordar)

Transições para estados de baixa energia na barra de tarefas ou sobre janelas.

1. **Compressão e Extensão (Squash & Stretch):**
   - Ao sentar ou deitar, o quadril e o tronco achatam sutilmente contra a superfície de apoio; durante a respiração do sono, a compressão é profunda e pesada.
2. **Antecipação (Anticipation):**
   - Antes de sentar, o mascote olha para o chão, ajusta a postura das pernas e inclina o tronco para a frente para não cair desajeitado.
   - Antes de acordar, um pequeno tremor e um estiramento corporal (*stretch* de espreguiçar) precedem a volta à pose ereta.
3. **Encenação (Staging):**
   - A pose de repouso é organizada para que a cabeça fique apoiada e visível, com a silhueta relaxada e harmônica no canto da tela.
4. **Ação Direta e Pose a Pose (Straight Ahead & Pose to Pose):**
   - Transição sequenciada em etapas fixas: Preparação $\to$ Descida $\to$ Assentamento $\to$ Repouso $\to$ Respiração lenta.
5. **Continuidade e Sobreposição (Follow Through & Overlapping Action):**
   - O quadril atinge o chão primeiro, o peito assenta em seguida, e a cabeça cai suavemente de lado com atraso, seguida pelo relaxamento final dos braços.
6. **Aceleração e Desaceleração (Slow In & Slow Out):**
   - Movimentos lentos e aveludados, com aceleração pesada na descida e desaceleração macia no repouso.
7. **Arcos (Arcs):**
   - A cabeça desce em arco pendular gracioso até encontrar a posição de descanso.
8. **Ação Secundária (Secondary Action):**
   - Micro-espasmos ocasionais em um dedo durante o sono REM; a porta do armário entreabre 1° liberando um "suspiro" periódico.
9. **Timing:**
   - Transição de descida em 2.5s; respiração adormecida em ciclos longos de 5.0s a 6.0s, comunicando peso e sono profundo.
10. **Exagero (Exaggeration):**
    - O peso morto do personagem ao adormecer é ligeiramente exagerado, fazendo-o parecer confortável e irresistivelmente sonolento.
11. **Desenho Sólido (Solid Drawing):**
    - Contato perfeito entre as superfícies de apoio (quadril/pernas) e o plano do desktop sem flutuação nem interpenetração.
12. **Apelo (Appeal):**
    - Sensação acolhedora e pacífica de ter um mascote dormindo silenciosamente ao lado do trabalho do usuário.

---

### F. Performance e Dança (Groove, Ritmada, Estilosa)

Expressão estilizada inspirada nas referências sonoras e visuais do projeto.

1. **Compressão e Extensão (Squash & Stretch):**
   - No tempo forte (*downbeat*), o corpo comprime dando peso ao groove; no contra-tempo (*upbeat*), ele estica com agilidade.
2. **Antecipação (Anticipation):**
   - Todo movimento de dança largo é precedido por um carregamento na direção oposta (ex: recuo para trás antes de um passo ousado à frente).
3. **Encenação (Staging):**
   - Poses extremas (*freeze poses*) com silhuetas poderosas e angulares, claramente legíveis mesmo em dimensões reduzidas.
4. **Ação Direta e Pose a Pose (Straight Ahead & Pose to Pose):**
   - Coreografia baseada em *keyframes* fortes e bem desenhados (*Pose to Pose*), combinada com física secundária de cabos e acessórios (*Straight Ahead*).
5. **Continuidade e Sobreposição (Follow Through & Overlapping Action):**
   - Ondulações corporais em que o movimento viaja do quadril para a coluna, ombros, punhos e dedos com atraso em cascata.
6. **Aceleração e Desaceleração (Slow In & Slow Out):**
   - Picos de velocidade rápida no meio do movimento com sustentação estática rápida na pose final (*snappy easing* estilo *Hi-Fi Rush*).
7. **Arcos (Arcs):**
   - Braços e cabeça desenham trajetórias circulares amplas e curvas contínuas, evitando qualquer linearidade artificial.
8. **Ação Secundária (Secondary Action):**
   - *Finger-tutting* e gestos articulados de dedos acompanhando o ritmo; oscilação rítmica dos fones e da porta.
9. **Timing:**
   - Sincronização impecável com o BPM da música, intercalando batidas rápidas e paradas cheias de atitude.
10. **Exagero (Exaggeration):**
    - Posturas e torções dinâmicas estilo *Persona 5* e *Lethal League*, levando as articulações aos limites estilizados do rig.
11. **Desenho Sólido (Solid Drawing):**
    - Respeito aos pivôs mecânicos do Blockbench e equilíbrio do centro de gravidade em cada pose de apoio.
12. **Apelo (Appeal):**
    - Carisma contagiante, energia contínua e sensação de puro estilo urbano/cyberpunk.

---

## 3. Checklist de Auditoria Técnica e Artística por Animação

Toda e qualquer nova animação ou ajuste no runtime deve passar por esta checagem obrigatória:

| Princípio | Pergunta de Validação | Implementação no Código |
|---|---|---|
| **1. Squash & Stretch** | O volume se mantém constante com compressão e extensão perceptíveis? | `animacao/respiracao.py`, `movimento_pernas.py` |
| **2. Antecipação** | O corpo prepara a ação com um movimento oposto ou carga de energia? | `animacao/clipes_animacao.py`, `gestos_reacao.py` |
| **3. Encenação** | A pose é imediatamente legível em silhueta no ângulo 3/4 do desktop? | `animacao/poses_base.py`, `foco_atencao.py` |
| **4. Pose a Pose / Direta** | Há equilíbrio entre poses-chave expressivas e física procedural contínua? | `clipes_ocioso.py` + `mola_critica.py` |
| **5. Sobreposição** | As articulações chegam em momentos diferentes (ondas e atrasos)? | `dedos_cascata.py`, `movimento_corpo.py` |
| **6. Slow In & Out** | As curvas evitam interpolação linear, usando tangentes suaves? | `interpolacao.py` (interpolação quíntica) |
| **7. Arcos** | As trajetórias espaciais são curvas e elípticas, sem linhas retas? | `ik_bracos.py`, `alvos_bracos.py`, `cinematica.py` |
| **8. Ação Secundária** | Dedos, fones, cabo e porta complementam a ação principal? | `fio_corda.py`, `gestos_dedos.py`, `apendices.py` |
| **9. Timing** | O tempo decorrido comunica o peso e a emoção corretos da ação? | Tuning de timers em `controlador_animacao.py` |
| **10. Exagero** | A pose vai além da física crua para comunicar atitude e personalidade? | Amplitudes em `danca_frases_tuning.py`, `gestos_tuning.py` |
| **11. Desenho Sólido** | Os apoios estão firmes, volumes respeitados e sem colisões grotescas? | `colisao_bracos.py`, `resolvedor_poses.py` |
| **12. Apelo** | O mascote parece vivo, carismático e expressivo na tela? | Validação visual em runtime com `smoke_mouse.py` |

---

## 4. Conclusão e Diretriz para o Código

Nenhuma animação do mascote deve ser tratada como um mero conjunto de rotações em linha reta. O código deve fornecer suporte a essas camadas simultâneas através da composição em `camadas_animacao.py`:
- Camada 1: Pose base autorada com *Pose to Pose*, *Encenação*, *Timing* e *Arcos*.
- Camada 2: *Squash & Stretch* volumétrico e respiratório.
- Camada 3: *Ação Secundária* (dedos, porta, fones).
- Camada 4: *Sobreposição e Atraso* inercial via molas procedurais (*Straight Ahead*).
- Camada 5: *Desenho Sólido* com IK de contato e prevenção de colisões.

Com essa aplicação integrada, o mascote abandona definitivamente o aspecto "travado/stickman" e ganha vida autêntica e contínua no desktop.
