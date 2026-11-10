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
