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
  autorais já não os tinham, e as pernas vivas vêm de `leg_motion`. Se a
  porta idle fizer falta na GPU, volta como track `door` em `CLIPS`.
- **Limite de jerk de um quíntico:** `60*delta/T^3`. Regra prática usada nas
  frases: rampas >= 0,5 s e delta <= ~16° nessas rampas, ou rampas maiores.
- `_idle_pulse` continua em `nucleo/rig.py` porque `pose_secondary` ainda o usa.

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
- **`anim_clips.py` está vivo:** reescrito como deltas sobre `REPOUSO`, é a
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
