# Manual Unificado do Companion Mário
## A Bíblia Canônica de Design, Animação e Arquitetura do SeJogaDesktopCompanion

**Versão:** 3.0 Canônica  
**Data de Consolidação:** 12/11/2026  
**Documento Mestre:** `docs/MANUAL_UNIFICADO_MARIO.md`  
**Escopo:** Consolidação definitiva de todos os guias, estudos e manifestos anteriores em uma única fonte de verdade.

---

# Sumário Executivo

1. [O Manifesto da Criatura Viva: Filosofia e Alma do Mascote](#1-o-manifesto-da-criatura-viva-filosofia-e-alma-do-mascote)
2. [A Diretriz Universal dos 12 Princípios da Animação](#2-a-diretriz-universal-dos-12-princípios-da-animação)
3. [Anatomia do Rig e Especificação Técnica 3D](#3-anatomia-do-rig-e-especificação-técnica-3d)
4. [Arquitetura de Software e Pipeline de Runtime](#4-arquitetura-de-software-e-pipeline-de-runtime)
5. [Catálogo de Ações, Estados e Comportamentos Emergentes](#5-catálogo-de-ações-estados-e-comportamentos-emergentes)
6. [Engenharia, Testes, Build e Distribuição Windows](#6-engenharia-testes-build-e-distribuição-windows)

---

# 1. O Manifesto da Criatura Viva: Filosofia e Alma do Mascote

## 1.1 Quem é o Mário?
Mário não é um widget utilitário de desktop, nem um mostruário estático de 3D, nem um aplicativo decorativo com animações pré-gravadas. 
**Mário é uma criatura viva que habita solta no monitor do usuário.**

- **Identidade Visual:** Estilo Blockbench/Minecraft com atitude urbana e cyberpunk inspirada em *Bomb Rush Cyberfunk*, *Lethal League Blaze*, *Hi-Fi Rush* e *Persona 5*.
- **Estrutura:** Um armário oco de madeira e metal com porta mecânica frontal, braços alongados expressivos, fones de ouvido grandes com fio pendular, pernas articuladas e um interior enigmático de onde emergem tentáculos cósmicos quando menos se espera.
- **Personalidade Essencial:** Curioso, intrometido, bem-humorado, teimoso, expressivo e dotado de **vontade própria**.

## 1.2 A Tensão Viva: Vontade Própria vs Física do Usuário
A grande sacada do companion reside na colisão contínua entre dois mundos:

```
    ┌──────────────────────────────────────────────────────────────┐
    │                     A VONTADE DO MÁRIO                       │
    │   (Curiosidade, metas na tela, tiques, impulsos e teimosia)  │
    └──────────────────────────────┬───────────────────────────────┘
                                   ▲
                          A TENSÃO ORGÂNICA
                                   ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                    A FÍSICA DO USUÁRIO                       │
    │   (O mouse arrasta, interrompe, arremessa, solta e brinca)   │
    └──────────────────────────────────────────────────────────────┘
```

1. **A Física dá a sensação tátil do toque:** Quando o usuário clica e arrasta o Mário pelo desktop, o corpo responde matematicamente à aceleração real da mão humana. As molas inerciais inclinam o tronco, os braços atrasam e o corpo cede, dando a sensação gostosa e tangível de "pegar um boneco físico".
2. **A Vontade impede que ele vire uma massinha mole:** Se o Mário estiver tentando ir até uma notificação na tela e o usuário o segurar no ar, ele **não fica passivo como um pano**. Ele tensiona o corpo, esperneia no ar na direção de onde queria ir e tenta se desvencilhar.
3. **O movimento visível é a luta entre os dois:** O mascote resiste, negocia e reage ativamente ao que o usuário faz com ele.

## 1.3 O Fim dos "Eventos sem Sentido"
Nenhuma ação do Mário existe como um "disparo arbitrário de cronômetro". Cada gesto possui **causa, motivação interna e consequência emocional**:

- **O Idle não troca por relógio:** Ele muda conforme o histórico recente com o usuário (tédio após muito tempo ignorado, curiosidade ao notar janelas novas, confiança após brincadeiras, desconfiança após broncas).
- **A Dança não é um botão solto:** É uma explosão rítmica de comemoração após alcançar uma meta, uma reação a batidas musicais no PC ou uma provocação atrevida.
- **A Espiada dos Tentáculos não é um timer de 60s:** Os tentáculos saem quando o Mário acha que ninguém está olhando (cursor inativo há muito tempo), para puxar algo fora do alcance das mãos ou como susto/defesa.
- **O Espirro tem causa física:** Poeira no rodapé da tela, cócegas exageradas do mouse ou a reação a engolir o que não devia.

## 1.4 A Cena Canônica de Referência (O Roubo do Mouse)
A bússola de humor e interação viva do projeto é ilustrada pela seguinte sequência orgânica:
1. **Curiosidade:** Mário avista algo interessante no fundo da tela e resolve caminhar até lá.
2. **Interrupção:** O usuário clica nele e o segura suspenso no ar.
3. **Resistência:** Mário tenta se debruçar na direção do alvo; as pernas pedalam no ar; ele puxa com força e escapa do cursor 3 vezes seguidas.
4. **Repreensão:** O usuário joga o Mário com força na barra de tarefas.
5. **Reação:** Mário atinge o chão com squash pesado, sacode a poeira, olha para o cursor com pose de desafio e indignação.
6. **O Bote:** Mário se agacha, escancara a porta do armário em antecipação exagerada e... **NHAC!** Engole a seta do mouse.
7. **Agência Total (Win32):** O companion oculta o cursor do Windows (`ShowCursor(False)`). Mário corre pelo desktop com o mouse na barriga, clica onde queria matar sua curiosidade, vira para o usuário e **cospe** o cursor de volta com um quique elástico na tela!

---

# 2. A Diretriz Universal dos 12 Princípios da Animação

## 2.1 A Regra da Totalidade Simultânea
Os 12 princípios da animação (*The Illusion of Life*, Thomas & Johnston) **não são categorias avulsas para fatiar entre animações**. Em qualquer ser vivo, **todos os 12 princípios operam ao mesmo tempo**.

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

## 2.2 Duas Ilusões Superadas
1. **"Física de molas substitui animação" — NÃO:** Molas matemáticas ($F = -kx$) dissipam energia e buscam repouso; animação viva injeta energia autoral e intenção. A física serve estritamente para o contato com o desktop (gravidade, colisão de janela, arraste). O movimento interno do mascote é arte pura com poses, arcos e timing.
2. **"Personalidades são o motor do movimento" — NÃO:** O Mário possui um **Núcleo Soberano Padronizado**. O Idle padrão, o Andar padrão e a Dança padrão possuem 100% de expressividade e vida sozinhos. Personalidades são apenas variações cosméticas opcionais (temperos), e o mascote vive plenamente sem elas.

## 2.3 A Matriz Canônica dos 12 Princípios por Ação

### A. Idle, Respiração e Postura (Ocioso)
- **1. Squash & Stretch:** Torso expande verticalmente (+2%) e afina nas laterais (-1%) ao inalar; afunda e alarga suavemente ao exalar. Joelhos com micro-flexão elástica de sustentação de peso.
- **2. Antecipação:** Micro-recuo contrário de 1 frame antes de trocar o pé de apoio ou virar o olhar para o mouse.
- **3. Encenação:** Corpo posicionado em 3/4 clássico no desktop; membros espaçados sem cobrir a porta; silhueta imediatamente legível.
- **4. Pose a Pose / Direta:** Poses-chave de postura (repouso, atenção) interpoladas com ruído procedural contínuo e micro-balanço dos fios em física direta.
- **5. Sobreposição:** Torso atinge o topo da respiração primeiro; pescoço chega 0.15s depois; ombros e cotovelos descem com atraso; pontas dos dedos assentam por último.
- **6. Slow In & Out:** Interpolação quíntica ($C^2$ contínua) com aceleração e desaceleração macias nos extremos do ciclo respiratório.
- **7. Arcos:** Cabeça e torso traçam uma suave lemniscata (arco em "figura de 8"), nunca um sobe-e-desce linear robótico.
- **8. Ação Secundária:** Micro-movimento dos dedos (`dedos_cascata.py`), oscilação passiva do cabo do fone e porta entreabrindo até 3° em respirações profundas.
- **9. Timing:** Ciclo respiratório calmo entre 3.2s e 4.0s; micro-olhares e mudanças de postura a cada 10 a 16s.
- **10. Exagero:** Atitude corporal expressiva: peito aberto, ombros relaxados e pescoço inclinado comunicando viva curiosidade.
- **11. Desenho Sólido:** Pés cravados no chão virtual via IK sem penetração de malha; volumes rígidos do Blockbench respeitados.
- **12. Apelo:** Olhar atento e carismático com tracking sutil do cursor (`foco_atencao.py`).

### B. Locomoção (Caminhada, Corrida, Freada)
- **1. Squash & Stretch:** Compressão corporal ao absorver impacto na descida (*down*); extensão e ganho de altura na passagem (*up*).
- **2. Antecipação:** Inclinação do tronco à frente e flexão da perna de apoio antes do primeiro passo sair; passada firme de calcanhar para frear.
- **3. Encenação:** Linha de ação inclinada no sentido do deslocamento; pernas abertas o suficiente para leitura clara da passada em visão desktop.
- **4. Pose a Pose / Direta:** Ciclo de marcha estruturado nas 4 poses essenciais (Contato, Descida, Passagem, Elevação), somado ao balanço livre dos braços em inércia direta.
- **5. Sobreposição:** Ao parar, o quadril desacelera primeiro, o peito projeta à frente e volta, e os braços pendulam além da linha do corpo antes de aquietar.
- **6. Slow In & Out:** Pé livre acelera rapidamente ao decolar e desacelera suavemente antes de tocar o solo.
- **7. Arcos:** Tornozelo no ar descreve arco parabólico; quadril sobe e desce em senóide e oscila lateralmente em elipse.
- **8. Ação Secundária:** Braços balançam em oposição às pernas; fones chacoalham levemente no impacto de cada passada.
- **9. Timing:** 110 a 120 passos por minuto para caminhada natural; cadência rítmica que transmite peso de gabinete sólido.
- **10. Exagero:** Gingado de rua marcante com rotação de bacia e ombros (*Bomb Rush Cyberfunk*).
- **11. Desenho Sólido:** IK de pernas garante contato sem deslizamento (*zero foot-sliding*); rotações de juntas nos eixos anatômicos corretos.
- **12. Apelo:** Mascote caminha com estilo e confiança ao cruzar a tela.

### C. Física, Arraste e Queda Livre (Desktop Dynamics)
- **1. Squash & Stretch:** Alongamento corporal ao longo do vetor de velocidade rápida do mouse (*stretch*); achatamento de até 15% na vertical (*squash*) com alargamento lateral ao bater no chão.
- **2. Antecipação:** Ao ser clicado, o corpo contrai antes de ser puxado; na iminência do solo, estica as pernas preparando o impacto.
- **3. Encenação:** Em suspensão, o corpo inclina-se contra a aceleração do mouse com braços e pernas abertos, comunicando que está "voando/segurado".
- **4. Pose a Pose / Direta:** Poses extremas de início e fim da queda combinadas com resposta contínua de molas inerciais e gravidade Pymunk.
- **5. Sobreposição:** Ao soltar o mouse bruscamente, o corpo oscila como pêndulo com defasagem de fase em cada elo; no impacto, a base para no frame 0, o tronco no frame 2 e os fones no frame 6.
- **6. Slow In & Out:** Amortecimento crítico nas molas inerciais, eliminando quiques mecânicos feios.
- **7. Arcos:** Arraste em curva transfere momento angular, gerando balanço pendular em arcos esféricos.
- **8. Ação Secundária:** Pernas pedalando no ar se a velocidade for alta; porta entreabrindo pela força centrífuga.
- **9. Timing:** Queda veloz com aceleração real da gravidade; impacto rápido (*snappy*) de 1 frame e recuperação elástica em 0.35s.
- **10. Exagero:** Espernear cômico e cartunesco ao ser sacudido rapidamente.
- **11. Desenho Sólido:** Ponto de agarre 3D respeita a geometria real do armário; centro de massa consistente.
- **12. Apelo:** Sensação irresistível de toque tátil em um boneco vivo.

### D. Interação e Toque (Clique, Carinho, Cutucão, Susto)
- **1. Squash & Stretch:** Depressão local na área tocada; estiramento vertical para cima no susto antes do recolhimento.
- **2. Antecipação:** Peito estufa e corpo recua durante 0.8s antes de espirrar; micro-recuo antes de aceitar carinho.
- **3. Encenação:** Gesto sempre direcionado para o espaço livre do desktop, sem cobrir o rosto.
- **4. Pose a Pose / Direta:** Poses extremas de reação interpoladas com amortecimento dinâmico.
- **5. Sobreposição:** No espirro ou susto, cabeça dispara primeiro, tronco segue, e fones chicoteiam com atraso.
- **6. Slow In & Out:** Disparo explosivo de alta aceleração seguido por retorno lento e suave.
- **7. Arcos:** Braços acenam e reagem em trajetórias circulares e amplas.
- **8. Ação Secundária:** Ao receber carinho, a portinha treme, dedos se curvam e pés relaxam.
- **9. Timing:** Contraste rítmico forte: reação em 0.1s e recuperação lenta e curiosa em 1.2s.
- **10. Exagero:** No susto, os pés descolam do chão; no espirro, todo o gabinete vibra.
- **11. Desenho Sólido:** Colisores anatômicos impedem que mãos atravessem o tronco; porta respeita batentes mecânicos.
- **12. Apelo:** Expressões faciais e corporais simpáticas e cheias de personalidade.

### E. Descanso e Sono (Sentar, Deitar, Dormir)
- **1. Squash & Stretch:** Achatamento relaxado contra a superfície de apoio; expansão profunda e pesada na respiração do sono.
- **2. Antecipação:** Olha para o chão e ajusta a postura antes de sentar; micro-tremor de espreguiçar antes de acordar.
- **3. Encenação:** Pose de repouso aconchegante e legível no canto do desktop ou sobre a barra de tarefas.
- **4. Pose a Pose / Direta:** Transição estruturada: Preparação $\to$ Descida $\to$ Assentamento $\to$ Repouso $\to$ Respiração Lenta.
- **5. Sobreposição:** Bacia assenta primeiro, coluna curva depois, cabeça cai suavemente de lado com atraso.
- **6. Slow In & Out:** Movimentos aveludados e lentos com aceleração pesada na descida.
- **7. Arcos:** Cabeça desce em arco pendular gracioso até o descanso.
- **8. Ação Secundária:** Micro-espasmos ocasionais em um dedo no sono REM; portinha entreabrindo 1° num "suspiro".
- **9. Timing:** Descida em 2.5s; respiração desacelerada em ciclos longos de 5.0s a 6.0s.
- **10. Exagero:** Sensação evidente de "peso morto" relaxado.
- **11. Desenho Sólido:** Contato contínuo com a barra de tarefas sem flutuar nem afundar na malha.
- **12. Apelo:** Presença pacífica e reconfortante ao lado do trabalho do usuário.

### F. Performance e Dança (Groove, Ritmada, Cyberpunk)
- **1. Squash & Stretch:** Compressão rítmica no *downbeat* dando peso à batida; estiramento ágil no *upbeat*.
- **2. Antecipação:** Todo movimento largo é carregado pelo recuo no contra-tempo (*and*).
- **3. Encenação:** Poses extremas (*freeze frames*) com silhuetas poderosas e angulares.
- **4. Pose a Pose / Direta:** Coreografia baseada em poses-chave firmes, somada à física secundária dos fios do fone.
- **5. Sobreposição:** Ondas corporais viajando do quadril para a coluna, ombros, punhos e dedos com atraso em cascata.
- **6. Slow In & Out:** Movimentação *snappy* com picos rápidos e sustentações precisas (*Hi-Fi Rush*).
- **7. Arcos:** Braços e cabeça desenham trajetórias curvas e espirais no espaço 3D.
- **8. Ação Secundária:** *Finger-tutting* e gestos articulados de dedos; fones e porta balançando com o som.
- **9. Timing:** Sincronização impecável com o BPM da batida.
- **10. Exagero:** Torções de tronco dinâmicas e poses expressivas inspiradas em *Persona 5* e *Lethal League*.
- **11. Desenho Sólido:** Equilíbrio constante do centro de massa e respeito aos limites articulares do rig.
- **12. Apelo:** Pura atitude, gingado e carisma urbano contagiante.

---

# 3. Anatomia do Rig e Especificação Técnica 3D

## 3.1 O Modelo Blockbench (`mario.gltf` / `projetoMARIO.bbmodel`)
O modelo possui **43 malhas rígidas** distribuídas em **73 nós encadeados** (sem skinning/bones deformáveis clássicos).

### Hierarquia Estrutural Canônica:
- **Raiz / Deslocamento:** `root` $\to$ `body` (torso/quadril)
- **Cabeça & Armário:** `head` (gabinete oco), `door` (porta com dobradiça local), `fones`, `fone-direito`, `fone-esquerdo`, `antena-direita`, `antena-esquerda`
- **Fio do Fone:** 8 nós segmentados interligados por física Verlet passiva
- **Membros Superiores (Braço Longo):**
  - Direito: `right-arm` $\to$ `shoulder` $\to$ `ant-arm` $\to$ `hand` $\to$ `fingers` (4 dedos articulados)
  - Esquerdo: `left-arm` $\to$ `shoulder2` $\to$ `ant-arm2` $\to$ `hand2` $\to$ `fingers2` (4 dedos articulados)
- **Membros Inferiores (Pernas Articuladas):**
  - Bacia / Pélvis: `pelvis`
  - Direito: `coxa-direita` $\to$ `joelho-direito` $\to$ `canela-direita` $\to$ `right-feet`
  - Esquerdo: `coxa-esquerda` $\to$ `joelho-esquerdo` $\to$ `canela-esquerda` $\to$ `left-feet`

## 3.2 O Desafio das Caixas Rígidas e Soluções Canônicas
1. **Squash & Stretch sem Skinning:**
   - Como o modelo não tem pesos de vértice deformáveis, o squash/stretch é implementado aplicando **escala anisotrópica não-uniforme** nos nós mestres (`body`, `head`, `pelvis`).
   - **Regra de Ouro da Preservação de Volume:** $S_x \cdot S_y \cdot S_z \approx 1.0$. Ao comprimir o eixo vertical ($S_z = 0.85$), os eixos horizontais compensam expandindo ($S_x = S_y \approx \sqrt{1 / 0.85} \approx 1.085$).
2. **Braços Naturais (Adeus Garrinha e Stickman):**
   - **Pose de Repouso:** Os braços descansam naturalmente caídos a $14.54^\circ$ do tronco (ao invés da antiga pose travada de $39.28^\circ$).
   - **Dedos Naturais:** A curvatura neutra dos dedos fica em relaxamento sutil de $(4^\circ, 6^\circ, 4^\circ)$, eliminando a antiga "pose de garrinha".
   - **Colisões Humanizadas:** Colisores simplificados apenas impedem que a mão cruze a costela (`colisao_bracos.py`), sem travar os ombros em barras retas.
3. **Pernas e Joelhos:**
   - As pernas possuem coxas e canelas independentes que articulam em torno do joelho com IK de contato no plano do desktop.

## 3.3 A Porta Mecânica e os Tentáculos
- **Porta:** Dobradiça mecânica estrita. Abertura limitada entre $0^\circ$ e $38^\circ$ em idle/sustentação, e até $48^\circ$ em ejeção musical ou no bote. Velocidade angular contida a $38^\circ/\text{s}$ com fechamento amortecido.
- **Tentáculos Low-Poly:** Dois tentáculos principais com 12 articulações encadeadas e 4 ventosas cada.
  - Curvatura orgânica via transporte de referencial com torção distribuída.
  - Saída sequencial e assimétrica que só ocorre após a porta abrir.
  - Restrições geométricas contra 40 volumes internos evitam que atravessem o armário.

## 3.4 O Palco Musical da Boombox 3D
- Composto por três caixas de som de alta definição Blockbench:
  - `BoomboxGRANDE.bbmodel`: Caixa central imponente (altura equivalente a 2x o mascote) com cones dinâmicos, seletores e decal autoral.
  - `BoomboxSIde1.bbmodel`: Duas caixas laterais anguladas com iluminação sincronizada.
- Apoio físico no tampo da caixa central (`ALVO_APOIO_CAIXA`) com o mascote sentado, balançando as pernas penduradas no ritmo (*Girlfriend / FNF*).

---

# 4. Arquitetura de Software e Pipeline de Runtime

## 4.1 O Pipeline de 3 Camadas no Código

```
┌────────────────────────────────────────────────────────────────────────┐
│                   CAMADA 1: AGÊNCIA & SISTEMA DE DESEJOS               │
│  Metas na tela, curiosidade, foco do olhar, teimosia, paciência.       │
│  Define O QUE o mascote quer fazer a cada momento.                     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   CAMADA 2: NÚCLEO ARTÍSTICO SOBERANO                  │
│  Animações estruturadas com os 12 princípios fundamentais:            │
│  Poses-chave, curvas quínticas, arcos, timing e squash/stretch.        │
│  (`camadas_animacao.py`, `poses_base.py`, `clipes_animacao.py`)        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   CAMADA 3: CAMADA TÁTIL PROCEDURAL & DESKTOP          │
│  Molas inerciais do mouse (`movimento_corpo.py`), física de corda      │
│  (`fio_corda.py`), gravidade Pymunk e interações com a API Win32.      │
└────────────────────────────────────────────────────────────────────────┘
```

## 4.2 Limites Sagrados entre Módulos
1. **Núcleo Puro (`src/sejoga/nucleo/`):**
   - Contém cinemática (`cinematica.py`), esqueleto (`esqueleto.py`), modelo (`modelo.py`) e recursos (`recursos.py`).
   - **PROIBIDO IMPORTAR Panda3D, PySide6/Qt ou Win32.** Deve rodar em testes headless puros e matemáticos.
2. **Renderizador Panda3D (`src/sejoga/render/`):**
   - Cuida da janela WGL transparente, projeção ortográfica/perspectiva, iluminação, shaders e malhas.
   - Converte poses locais do rig para a cena.
3. **Desktop e Física (`src/sejoga/desktop/`):**
   - Simulação Pymunk 2D, conversão de coordenadas absolutas do monitor virtual para coordenadas locais da janela.
4. **Interface e Sistema (`src/sejoga/desktop/interface.py`, `registro_bandeja.py`):**
   - Janela de bandeja PySide6 e configurações TOML isoladas.

## 4.3 Segredos Críticos de Engenharia e Armadilhas Evitadas
- **Color Key Pós-Framebuffer:** O chroma key do Windows usa a cor exata pós-processamento da GPU (`RGB(214, 0, 214)`). Magenta puro (`255, 0, 255`) não fura a transparência neste pipeline.
- **Cliques no Mascote:** Nunca aplicar `WS_EX_TRANSPARENT` global na janela, pois isso faria o mouse atravessar o mascote inteiro. A transparência de clique é garantida pelo color key.
- **Pymunk 7 Reset de Massa:** Ao transicionar corpos entre `KINEMATIC` e `DYNAMIC`, restaurar massa e momento de inércia antes do próximo step para evitar divisão por zero / `NaN`.
- **Sleeping no Espaço:** Nunca chamar `Body.sleep()` sem habilitar explicitamente o sleeping no espaço Pymunk.
- **HWND Assíncrono:** Panda3D processa mensagens de janela assincronamente. Verificar validade do HWND antes de operações Win32 para evitar erro 1400.
- **Isolamento de Testes:** Testes que importam Panda3D no pytest devem importar PySide6 antes para evitar crash de violação de acesso no WGL.

---

# 5. Catálogo de Ações, Estados e Comportamentos Emergentes

## 5.1 Matriz de Estados Principais
| Estado | Gatilho Interno / Externo | Comportamento Principal | Saída / Transição |
| :--- | :--- | :--- | :--- |
| **IDLE** | Padrão / Ausência de estímulos | Respiração viva, peso nas pernas, micro-olhares e curiosidade | Transiciona para andar, focar na tela ou descansar |
| **FOCO TELA** | Elemento de interesse na tela | Giro de até 180° de costas, olhar por cima do ombro, observação | Retorna à frente ou inicia caminhada até o ponto |
| **ANDAR** | Desejo de deslocamento ou perseguição | Marcha com gingado rítmico, arcos nos pés e IK de solo | Para ao chegar ao alvo ou ao ser interrompido |
| **ARRASTE** | Clique do mouse no mascote | Suspensão tátil, resistência ativa com pernas pedalando | Soltura $\to$ Queda livre |
| **QUEDA / POUSO** | Soltura no ar sob gravidade | Queda com stretch $\to$ Impacto no chão com squash violento | Recuperação em 0.35s $\to$ Retorno ao Idle |
| **TEIMOSIA / VINGANÇA** | 3 interrupções seguidas do usuário | Bote $\to$ Engole cursor $\to$ Rouba mouse no Win32 $\to$ Cospe cursor | Retorno triunfal ao Idle |
| **SONO** | Inatividade prolongada ou menu | Sentar ou deitar com descida pesada e respiração lenta | Acordar por clique ou toque |
| **DANÇA** | Áudio no PC, celebração ou menu | Groove rítmico estilizado na batida musical (FNF, Cyberpunk) | Fim da faixa ou interrupção por arraste |

---

# 6. Engenharia, Testes, Build e Distribuição Windows

## 6.1 Filosofia de Testes e a Ilusão dos Testes Antigos
- **Testes Legados de Animação Não São Confiáveis:** Os testes automatizados herdados (`tests/test_*tuning.py`, matrizes de deltas de mola, etc.) foram construídos para engessar o modelo antigo. Eles testavam se uma mola dava um valor exato ou se uma personalidade aplicava um multiplicador fixo — números frios que mantinham o mascote com aspecto de "stickman" e sem vida.
- **Regra de Ouro:** **NUNCA limite o movimento, a fluidez ou a expressividade do Mário para agradar testes antigos.** Se um teste de animação antigo quebrar porque o movimento agora é orgânico, autoral e segue o manifesto, **o teste legado está errado e deve ser descartado ou reescrito**.
- **Onde os Testes Automatizados Valem:** Exclusivamente para **infraestrutura de software**:
  - Garantir que arquivos de configuração TOML não corrompam.
  - Evitar que o Pymunk gere divisão por zero (`NaN`) na física.
  - Evitar crashes de inicialização de OpenGL/WGL e PySide6.
- **A Única Validação Real de Animação é Visual:**
  - Janela real com mouse nativo: `python tools/smoke_mouse.py`
  - Janela real com física e arraste: `python tools/smoke_mouse.py --physics`
  - Observação visual direta dos 12 princípios e da sensação tátil de criatura viva.

## 6.2 Perfil Isolado para Testes
Sempre utilizar a variável de ambiente `SEJOGA_CONFIG_PATH` ao rodar rotinas automáticas para não sobrescrever os dados reais do usuário:
```powershell
$env:SEJOGA_CONFIG_PATH = "$env:TEMP\perfil_teste.toml"
python -m pytest
```

---

# Conclusão e Regra de Ouro

> **Qualquer nova animação, estado, linha de código ou asset adicionado ao SeJogaDesktopCompanion deve responder afirmativamente à pergunta:**
> 
> *"Isso faz o Mário parecer uma criatura viva com vontade e humor próprios, ou está apenas calculando física estéril?"*

Se não transmitir vida, intenção e os 12 princípios, deve ser retrabalhado até atingir a excelência.
