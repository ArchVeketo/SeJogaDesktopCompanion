# Decisões das animações

Registro das escolhas feitas na revisão das animações (Frente 3). Cada seção
diz o que foi decidido, a referência usada e o que **não** foi verificado.
Quem acrescentar uma animação nova deve incluir uma seção aqui.

## Idles

### Referência por personalidade

| Personalidade | Referência | Princípio aproveitado |
|---|---|---|
| `rhythm`, `playful` | Hi-Fi Rush ([GameAnim](https://www.gameanim.com/2023/09/08/hi-fi-rush-music-synced-animation/), [Digital Foundry](https://www.digitalfoundry.net/articles/digitalfoundry-2023-hi-fi-rush-tech-review-xbox-series-x-s-pc-a-bold-visual-treat)) | Poses-chave na batida; idle que transmite o ritmo |
| `playful`, `street` | FNF Girlfriend ([docs de modding](https://funkincrew.github.io/funkin-modding-docs/03-custom-characters/03-02-creating-a-character.html)) | Alternar esquerda/direita a cada N batidas |
| `curious` | Animal Crossing ([Nookipedia](https://nookipedia.com/wiki/Villager)) | Olhar ao redor com pausas entre os gestos |
| `calm` | Hollow Knight ([Team Cherry](https://www.teamcherry.com.au/blog/introducing-hollow-knight)) | Postura contida, respiração e balanço mínimos |
| `shy`, `calm` | Celeste ([sprites](https://www.spriters-resource.com/pc_computer/celeste/)) | Idle econômico, micro-movimento, silhueta legível |
| todas | Guias de idle ([MoCap Online](https://mocaponline.com/blogs/mocap-news/idle-animation-game-dev-guide), [AnimSchool](https://blog.animschool.edu/2024/06/14/breathing-life-into-idle-animations/)) | Respiração, troca de peso e ajustes de cabeça quase invisíveis |

### O que não foi verificado

- Nenhum vídeo nem frame dos jogos foi inspecionado: só princípios descritos
  nas páginas acima. Não há cópia de assets nem de curvas.
- Nada foi visto na GPU. Teste verde prova continuidade numérica (jerk), não
  que a pose fica boa. Os itens visuais estão em `docs/RECALIBRACAO_GPU.md`.

### Decisões

- **Fonte única em `idle_clips.CLIPS`.** Os nove idles são dados; `delta_idle`
  (caminho vivo) e `rig.pose_idle` (caminho legado) leem a mesma `sample_idle`.
  O ramo "fallback" de `delta_idle` e o ramo por personalidade de `pose_idle`
  foram apagados: eles davam só sway e divergiam um do outro.
- **Respiração somada uma vez.** `delta_idle` chama `sample_idle` com
  `respiracao=0` e soma `camada_respiracao` por cima. Antes a respiração entrava
  duas vezes quando `respiracao != 0` (empurrada pelo espirro).
- **Base por personalidade em `AJUSTE_BASE`.** As personalidades novas usam um
  pequeno ajuste de base (cabeça/corpo) em vez de novos `if/elif`. Os braços
  sempre saem de `REPOUSO`: y é o azimute, z a elevação, x só micro.
- **`rhythm` sem alegar sincronia com áudio.** É uma cadência interna de
  100 BPM. O balanço de braço por batida caiu de ~23° para 10° pico a pico
  (`RHYTHM_BRACO_DIR`/`ESQ`): jerk senoidal `A*(2*pi*f)^3` ficou abaixo de
  8.000 graus/s³. As keys de `hand`/`fingers` passaram a ter rampas >= 0,7 s.
- **`playful` alterna o lado a cada 2 batidas** (batida de 1 s, keys a cada
  0,5 s), como o `danceLeft/danceRight` do FNF, mas sem relação com música.
- **Porta e pés do idle legado foram descartados.** O `door` (até 3°) que as
  personalidades antigas moviam no idle e o deslocamento de peso dos pés
  (`left-feet`/`right-feet`) não existem mais em `pose_idle`: os quatro idles
  autorais já não os tinham, e as pernas vivas vêm de `movimento_pernas`. Se a
  porta idle fizer falta na GPU, volta como track `door` em `CLIPS`.
- **Limite de jerk de um quíntico:** `60*delta/T^3`. Regra prática usada nas
  frases: rampas >= 0,5 s e delta <= ~16° nessas rampas, ou rampas maiores.
- `_idle_pulse` continua em `animacao/poses_base.py` (antes `nucleo/rig.py`) porque `pose_secondary` ainda o usa.

## Sono

- Constantes em `animacao/sono_tuning.py` (`SONO_*`).
- Respiração de 0,2 Hz, corpo que afunda num vai-e-vem de 40 s, cabeça caída
  (-15°) com um "cochilo" raro (-6° a cada 23 s) e ombros um pouco caídos
  (`right-arm.z` +3°, esquerdo espelhado). Dedos relaxados: `fingers.z` +6° e
  `fingers2.z` -6° (espelho).
- Entrada no sono com crossfade de pelo menos 1,2 s (`SONO_TRANSICAO_S`),
  aplicada só ao estado SLEEP; DRAG/FALL/HIT continuam em 0,22 s.
- Não verificado: o sinal visual de "ombro caído" via `right-arm.z` e a leitura
  dos dedos relaxados. O alvo é o de `ALVO_SLEEP` somado a 3°; se a mão atravessar
  o corpo na GPU, reduzir `SONO_OMBRO_CAIDO`.

## Locomoção, arraste e queda
- Constantes em `animacao/locomocao_tuning.py`. A fase da passada é única:
  `AnimationController` passa `leg_motion.phase` a `delta_walk(fase, run)`, então
  braços e pernas partilham o mesmo relógio (antes o braço usava 3 rad/s
  próprios).
- **Por que `y` e não `x`:** `x` é a torção do braço no próprio eixo e não
  balança o braço; frente/trás é o azimute `y`. O balanço antigo em `x` saiu.
- **Contrafase (sinal provado no grafo de cena):** `setP(+a)` no nó
  `left-hip-pivot` leva o pé para +Y (frente de autoria; verificado no Panda: pé
  em (0, 0.5, -0.87) para a=30) e `LegPose.left = +sin(fase)`. Perna esquerda à
  frente implica braço direito à frente (`y` positivo).
  `SINAL_BRACO_COM_PERNA = +1`. Não provado: que o `model_np` do renderer
  coincide com o referencial de autoria de `cinematica`. Se na GPU o braço vier
  junto da perna, trocar o sinal (C42).
- **`clipes_animacao.py` está vivo:** reescrito como deltas sobre `REPOUSO`, é a
  única definição do balanço, amostrada por `delta_walk` via `ciclo_da_fase`.
  `rig.pose_walk` (caminho legado, descartado nos estados migrados) soma o mesmo
  clipe ao repouso. Sem ângulos absolutos da convenção antiga.
- **Elevação `z` em fase com `y`** (o braço sobe ao ir à frente e desce ao
  voltar), não em quadratura: o easing quíntico para em cada key e a quadratura
  obrigaria o `y` a parar no cruzamento do zero. Espelho e contrafase se
  cancelam, então os dois braços têm o mesmo delta `y`/`z`.
- Cotovelo (`ant-arm.z`) flexiona mais com o braço à frente, sempre >= 0
  (`ant-arm2.z` <= 0). O tronco contra-gira (`body.y`, sinal A_CONFIRMAR) e
  inclina na corrida; a cabeça faz contra-giro suave e quique a 2x a frequência
  (track `head:quique`; o rótulo é somado em `head`).
- **Jerk de ciclos rápidos:** a passada (1,35 Hz caminhada, 2,2 Hz corrida)
  passa de `LIMIAR_JERK_TRANCO` (8.000) por natureza: uma senóide de 14 graus já
  dá ~8.500. O teste de locomoção compara com o jerk do próprio easing
  (60*delta/T^3 por trecho, margem 1,5) e exige zero `LOOP`.
- **Arraste:** termos `z` (roll/limb_swing) e ramos por `grab_part` intactos.
  Somam-se dedos em garra (`fingers.z` = 8 + 24*intensidade, `fingers2`
  espelhado) e a soltura (`delta_soltura`: abre até -22 graus em 0,22 s, assenta
  em 4 e fecha em 0 aos 0,9 s), somada pelo controlador fora do estado DRAG.
- **Queda:** flail de `x` (torção) para `z`/`y` com espelho (`z` e `y` invertem
  à esquerda); cotovelo só flexiona (`flail^2`, sem a quina de `abs`); dedos
  abertos (-10 graus, espelhado); leve tumble de `body.z` por velocidade
  horizontal. Pernas e `delta_fisica` intactos.
- Não verificado (só GPU): sentido da contrafase, giro do tronco, leitura dos
  dedos de arraste/soltura/queda, transição fall -> land -> idle.

## Gestos de reação

Aceno, cutucar e alongar vivem em `animacao/gestos_reacao.py` (constantes em
`animacao/gestos_tuning.py`); `rig.pose_flourish` e `rig.pose_interaction`
só delegam. Continuam no caminho legado (alvo bruto, sem LayerStack).

- **Alvos de mão:** `ALVO_WAVE` e `ALVO_STRETCH` ficaram como estavam. O
  `oraculo_cena --sugerir` só achou o ponto livre mais próximo (wave a 0,015 u;
  stretch já livre). Uma varredura em grade mostrou que subir o alongamento
  (y 0,12 ou 0,16) atravessa a cabeça (0,03 a 0,06 u); o alvo atual dá ~49 graus
  de elevação sobre o repouso, medido pela FK da mão.
- **Aceno (2,6 s):** antecipação, subida de 0,6 s, três balanços de 1,8 Hz
  amortecidos (pico de 22 graus no antebraço, pulso de 15, cabeça com 0,12 s
  de atraso) e descida. O centro do balanço fica 18 graus mais estendido que o
  alvo: sem isso o punho entrava na cabeça (0,043 u) no pico de flexão.
  O cotovelo tem faixa própria, sem o recuo de antecipação, porque o recuo
  cruzaria zero (sem hiperextensão) e criaria uma quina.
- **Cutucar (0,4 -> 0,9 s):** recuo (0,15 s), estocada (0,12 s), sustentação
  (0,25 s) e recuperação (0,38 s) numa faixa única `golpe` (-1 recuo, +1
  estocada), então não há quina na passagem pelo zero. A estocada é de 30
  graus no ombro: com 45 o braço invadia o outro braço (0,02 u). O dedo
  indicador estendido não foi feito (os gestos de dedo `GESTURES` não têm
  esse caso); só o punho fecha de leve.
- **Alongar (3,2 s):** os dois braços sobem juntos, coluna em arco (10 graus),
  cabeça para trás, bocejo de 20 graus (limite 25), sustentação de ~0,8 s e
  queda dos ombros ao soltar.
- **Tranco nos gestos:** o limite de jerk 8000 não vale para gestos rápidos
  (45 graus em 0,12 s já passa de 1 milhão; o `PoseResolver` suaviza). Os testes
  usam um teto por gesto: aceno 6e4, cutucar 2,5e6, alongar 8000, wake 1,2e4.
  Nas auditorias, a flapada da porta no clique e o tremor do hit passam
  desse limite por projeto; não foram mexidos.
- **Auditoria:** click, double_click, pet, hit, land, surprise e peek não
  atravessam, terminam no repouso e não hiperestendem. Só o `wake` atravessava
  (0,09 u): a elevação dos braços foi de 70 para 30 graus (`WAKE_BRACO_ELEVACAO`).
- **Limitado pelo fone (C6):** o aceno não vai além do ponto livre atual; mais
  alto o punho encosta no fone/cabeça.
- Não verificado (só GPU): leitura visual dos três gestos, palma para a frente
  no aceno (C7), sinal da queda de ombros do alongar (`shoulder`/`shoulder2`),
  o fechamento do punho no cutucar.

## Danças

Decisões da FEAT-004, tomadas sem consulta (fila noturna), pela opção mais simples
que não toca no que já foi confirmado. Nada abaixo foi visto na GPU.

- **Acento no onset.** O acento de cada passo cai em u = 0, a batida detectada.
  O u vem da fase de `DanceMotion` (corrigida pelos onsets); o índice do passo vem de
  `style_beats` (`round(style_beats - u)`), então a emenda entre batidas não depende
  de qual das duas corre à frente. As molas (4,5 Hz) atrasam o acento visível em
  alguns quadros.
- **Quatro poses por passo.** `dance_poses.PassoDanca`: acento (u 0), sustentação
  (0,35), recuperação (0,70) e preparação (0,82), depois o acento do passo seguinte.
  A preparação ficou em 0,82 e não em 0,88 do plano: o salto de preparação para
  acento em 0,12 de batida dava jerk de 330 mil no headbang do rock; em 0,18 caiu
  para 206 mil (o código antigo tinha 227 mil). Cabeça e tronco são deltas sobre o
  repouso (zero), escalados por energia (`GANHO_PASSO_*`); os braços vão a alvos de
  mão resolvidos pela IK, sem torção-base manual (o hack `tx = REPOUSO.BRACO_X` saiu).
- **Dados em `danca_frases_tuning.py`, não em `danca_tuning.py`.** Os passos são
  `PassoDanca`, definidos em `poses_danca`; pôr os dados em `danca_tuning` criaria
  import circular. `danca_tuning` ficou com limiares, tempos, lean/floor/spin e as
  constantes novas (`U_POSES`, `GANHO_PASSO_*`, `ROCK_MEIO_TEMPO_BPM`,
  `FLOOR_ROLL_GRAUS`, `PIVO_QUADRIL_Z`). Os ângulos absolutos antigos (`HEADBOB_*`,
  `ROCK_*`, `GROOVE_*`, `BREAK_*`) foram removidos.
- **Seleção, dwell, molas e fase compartilhada com as pernas** ficaram como estavam.
- **Alvos novos de braço.** Medidos com a colisão do modelo real (grade de busca):
  `cruzado_dir` (0,08; 0,06; 0,22), `cruzado_esq` (0,08; 0,06; 0,16), `chifre`
  (0,24; 0,08; 0,04), `contrapeso` (0,22; 0; 0,17) e `apoio_chao` (0,22; -0,12; 0,12).
  Coordenadas relativas ao ombro (x para fora, y cima, z frente).
- **Braços cruzados: fallback.** Nenhum alvo com o punho passando do ombro em direção
  ao centro fica livre (o tronco e o outro braço bloqueiam), e `FRACAO_NUCLEO_BRACO`
  não foi mexida. O head bob usa antebraços à frente do peito, mãos próximas, o
  direito um pouco mais à frente que o esquerdo. Se você quiser cruzar de verdade, a
  alavanca é a folga do tronco em `braco_tuning.FOLGA_EXTRA_CAIXA_U`.
- **Chifre não passa da cabeça.** O ombro fica 0,19 u abaixo do topo da cabeça e o
  braço alcança 0,281 u; o ponto livre mais alto é (0,24; 0,08; 0,04), braço erguido
  ao lado. A torção do punho de 180 graus do rock antigo foi mantida
  (`ROCK_PUNHO_TORCAO`); os dedos continuam por `gestos_dedos` (o renderer passa
  `gesture='rock'` à mão direita).
- **Head bob.** 4 batidas: nod curto no 1, inclinação lateral lenta no 2, segundo nod
  no 3, pausa no 4. A inclinação para trás é `body.x` +8 graus (`HEADBOB_TRONCO_TRAS`);
  o renderer já soma +10 de inclinação ao encostar na caixa, então o total pode ser
  maior que o desejado. Sinal de `body.x` (positivo = para trás) A_CONFIRMAR.
- **Rock.** 2 batidas, headbang com `head.x` -26 e `body.x` -7 no acento. Acima de
  `ROCK_MEIO_TEMPO_BPM` (150) o passo dura duas batidas. A troca de regime em 150 BPM
  muda o índice de uma vez (as molas suavizam).
- **Hip hop.** 8 batidas: comprimir/transferir peso, estender o braço oposto, fechar,
  pausa, depois o lado oposto com giro de cabeça e uma pose legível com os dois braços
  fora. O lado do peso é o roll do tronco; a perna carregada vem de `movimento_pernas` pela
  fase global, que não é a posição da frase de 8 batidas, então os dois lados podem
  não coincidir (A_CONFIRMAR C50). Tentei usar `interaction` como pose intermediária
  do braço e piorou: o cotovelo dobra 78 graus ali.
- **Breakdance.** 16 batidas: toprock 0-3 (cabeça e tronco do hip hop com os braços no
  repouso), descida 4-5, footwork 6-12 e freeze 13 com as mãos plantadas em
  `apoio_chao`, subida 14-15. Trocar o alvo do braço a cada batida a 145 BPM passava
  de 250 mil de jerk no ombro, então o footwork varia só cabeça e roll do tronco. O
  roll e o giro do corpo seguem `floor_amount`/`floor_spin` (janelas inalteradas).
- **Pernas.** Só magnitudes e um ramo por estilo, sem trocar sinais: rock com
  `DANCA_ROCK_QUADRIL` (4) e joelhos flexionando no onset (`DANCA_ROCK_JOELHO`),
  hip hop com `DANCA_HIPHOP_JOELHO` (6) somado à transferência de peso. Head bob e
  breakdance ficaram como estavam. As molas das pernas absorvem os alvos (cosseno
  contínuo, sem salto).
- **Pivô do breakdance.** `apply_body_motion` usa `_giro_no_quadril`: a rotação de
  autoria (`_rotacao_no_quadro_de_autoria`) em torno do quadril (0, 0, 0,44), mais o
  ajuste de chão por `getTightBounds`. O roll é +65 graus (`FLOOR_ROLL_GRAUS`): o
  antigo `setHpr(.., -65)` valia no quadro do mundo, girado 180 graus em relação ao
  mascote, e a lei de autoria diz que roll positivo tomba o topo para a direita do
  mascote (`tests/test_tronco_quadro.py` prova o sinal e o quadril fixo no Panda
  sem janela). Ou seja, mesmo lado de antes; não foi visto na GPU.
- **Atalho: mão não fica fixa no cenário durante o giro.** Marcado como `shortcut:`
  no renderer; sobe de nível quando houver contatos de cena (guia 7.1).
- **Jerk.** O limiar global de 8000 não vale para o acento no onset (golpe por
  projeto; as molas só amortecem). `tests/test_movimento_danca.py` usa um teto por estilo
  abaixo do pior caso do código antigo e exige zero salto entre quadros. Medido a
  60 fps com BPM fixo: head bob 77 mil -> 53 mil depois de mover a preparação, rock
  206 mil, hip hop 170 mil, breakdance 94 mil.
- **Caminhos antigos nos docs.** Os 6 docs do plano passaram ao layout
  `src/sejoga/animacao`, `nucleo`, `musica`, `render`, `desktop` e `tentaculos`
  (`limb_ik` virou `animacao/ik_bracos.py`). `tools/profile_music_styles.py` e
  `tools/capture_dance_animation.py` não existem mais e foram marcados como
  removidos. Nenhum doc foi apagado.
- **Não verificado:** tudo o que é visual (leitura dos passos, braços "cruzados", mão em
  chifre, sinal do roll no chão, mão perto do chão), sinal de `body.x`, correlação
  entre a perna carregada e o braço do hip hop, e a taxa real de quadros.

## Pendências da revisão final (não bloqueantes)

Revisão aprovada. Nada abaixo foi refeito; fica para a validação na GPU ou para trabalho futuro.

- Nenhuma mudança foi vista na GPU. Conferir C39..C52 e O13..O17 em `docs/RECALIBRACAO_GPU.md`. Mais arriscados: sinal da contrafase de braço/perna (C42), roll do breakdance, sinal do `body.x` do head bob (+8 soma com +10 do renderer) e ombros caídos do sono/alongar.
- Tetos de jerk por estilo/gesto (danças até 2,3e5, cutucar 2,5e6) são altos e podem esconder trancos. Conferir visualmente.
- Head bob: braços cruzados de verdade não foram feitos (fallback de antebraços à frente do peito). Cutucar: indicador estendido não foi feito.
- Breakdance: mão plantada não fica fixa no cenário durante o giro (`shortcut:` no renderer). Resolver quando houver contatos de cena.
- Ambiente (preexistente): `test_colisao_bracos.py` e `test_efeitos_caixa_som.py` na mesma sessão fecham com 0xC0000005 (Panda + Qt). A suíte completa em ordem alfabética passa.
- Corrida pode ficar rápida demais para os amortecimentos do PoseResolver (não medido).
- Hover e gestos de mão não foram auditados por amostragem.