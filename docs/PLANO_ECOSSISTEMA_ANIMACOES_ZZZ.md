# Plano do Ecossistema de Animações Inspirado em ZZZ (`SeJogaDesktopCompanion`)

> Alinhado ao [MANUAL_UNIFICADO_MARIO.md](file:///c:/GitHub/SeJogaDesktopCompanion/docs/MANUAL_UNIFICADO_MARIO.md) e ao [ESTUDO_LOOPS_GACHA_MIXAMO.md](file:///c:/GitHub/SeJogaDesktopCompanion/docs/ESTUDO_LOOPS_GACHA_MIXAMO.md).

## 1. Visão Central: O Mário como Criatura Contínua (Modelo Ecossistema ZZZ)

Em jogos como *Zenless Zone Zero*, animações não são clipes isolados disparados ao acaso: todas orbitam uma **Postura Hub (Idle Base)** coerente com a personalidade do personagem, usam loops matemáticos fechados (`1s` a `6s`), aplicam **sobreposição hierárquica em cascata** (quadril -> peito -> cabeça -> braços -> mãos/antenas/tecido/tentáculos) e sempre retornam com continuidade tangencial ao Hub.

Para o Mário (criatura curiosa com monitor CRT retrô, Walkman/MP3 na cintura, fone sobreposto e tentáculos tímidos por trás das portas):

- **Motivo condutor do Hub (`Idle Padrão`):** O Mário está em repouso ativo sobre a área de trabalho curtindo música no Walkman. Peso descansando levemente em uma perna, postura aberta/natural (pés com rotação externa leve `yaw ±5°`, joelhos macios), mão esquerda próxima ao cinto/Walkman ou apoiada no quadril, mão direita relaxada marcando micro-ritmo suave, cabeça acompanhando o balanço com atraso em cascata e olhar atento ao ambiente.
- **Duração do Ciclo Base:** Exatamente `4.00s` (harmônicos `1x`, `2x`, `4x` via senoides fechadas em `0..2π`), evitando micro-saltos na costura do loop (`seam-free`).

---

## 2. Arquitetura em Cascata e Ramificações do Ecossistema

```
                [ Cenas Autônomas / Curiosidade ]
                 (olhar tela, espiada de tentáculo, sono)
                                 ▲
                                 │ transição suave (blend + settle)
                                 ▼
[ Reações Imediatas ] ◄──► [ HUB: IDLE PADRÃO (4.00s) ] ◄──► [ Cenas de Fone & Antena ]
(drag pêndulo, fall,        (Walkman groove + respiro      (ajeitar_fone, fone_com_problema,
 heavy_land, clique)         + olhar + tecido frontal)      argolas_antena RGB)
                                 ▲
                                 │ transferência de peso contínua
                                 ▼
                   [ Locomoção & Danças ZZZ ]
             (walk 1.167s, run 0.667s, danças em compasso)
```

### Tabela de Cadência e Cascata Hierárquica

| Camada do Rig | Atraso de Fase (`phase_lag`) | Papel no Ecossistema |
| :--- | :--- | :--- |
| `hips` / `legs` / `belt` | `0.00s` (referência) | Transferência de peso, inclinação (`sway`) e base plantar firme (`turnout` externo) |
| `waist` / `chest` | `+0.18s .. +0.25s` | Respiração (`squash & stretch` sutil) e torção contrária ao quadril |
| `head` / `headphones` | `+0.30s .. +0.35s` | Antecipação do olhar, *neck lead* e folga do arco do fone |
| `left/right arm & fingers` | `+0.40s .. +0.48s` | Follow-through nos cotovelos, gestos do Walkman/fone e relaxamento dos dedos |
| `antennas`, `pants cloth`, `tentacles` | `+0.50s .. +0.60s` | Ação secundária viva (tecido na frente/atrás da calça, argolas RGB finas, tentáculos em S) |

---

## 3. Roteiro Lógico de Idle, Variantes e Autonomia

Em vez de sortear espasmos desconexos ou espamar efeitos visuais, todo disparo autônomo parte da **motivação narrativa** no estado atual:

1. **Idle Padrão (`calm` / `brc_stance`, `4.00s`)**
   - Balanço lento de peso lateral entre as duas pernas sem deslocar o pé de apoio nem girar joelhos para dentro.
   - Respiração limpa (`chest` + `waist`) mantendo a linha do ombro natural e fone alinhado às laterais do CRT.
   - Mão esquerda próxima ao aparelho de som na cintura; mão direita com gesto relaxado e esporádico micro-groove de dedos.
2. **Ramo de Manutenção do Equipamento (`cenas_idle.py`)**
   - `ajeitar_fone` (`2.6s`): desencadeado após tempo ouvindo música; um lado do fone escorrega levemente, a cabeça inclina acompanhando o ouvido, a mão sobe com antecipação, reposiciona o fone e retorna ao Hub com pequeno assentamento.
   - `fone_com_problema` (`5.2s`): o som falha/engasga -> estalo leve de surpresa (`sem card exagerado`), mão bate de leve no Walkman/fone, Mário aguarda/testa, o áudio volta firme e ele retoma o balanço do Hub.
   - `argolas_antena` (`3.8s`): pulso sci-fi sutil nas pontas das antenas com anéis orbitais RGB finos e sincronizados quando a energia/música ressoa ou em inspeção curiosa.
3. **Ramo de Curiosidade com o Usuário (`agencia.py` + `controlador_animacao.py`)**
   - `pacote_olhar_tela` / `inclinada_curiosa`: após período calmo sem mouse, Mário desvia do groove, projeta levemente tronco/cabeça em direção ao cursor/janela ativa, observa e volta suavemente ao Hub.
   - *Tentáculos reativos*: permanecem recolhidos nas portas laterais/topo durante calma normal; surgem em poses específicas (`curioso`, `sleep` relaxado, susto, celebração, arraste) preservando a geometria clássica esculpida (`8 lados`, tons carmesim profundos e ventosas hexagonais).
4. **Ramo de Repouso (`sleep`: `em_pe` -> `sentado` -> `deitado`)**
   - `em_pe` (cochilo em pé com queda lenta de cabeça e susto suave ao acordar).
   - `sentado` (pernas abertas confortavelmente para fora `yaw ±12°, roll ±7°`, sem pinçar os joelhos para dentro; mãos apoiadas próximas ao chão).
   - `deitado` (relaxamento total com respiração lenta e `Z` discreto).

---

## 4. Padrões Técnicos do Rig, Tecido e Efeitos (Sem Poluição)

1. **Eixos Corretos de Pernas e Pés (`movimento_pernas.py`)**
   - No espaço do rig (`legs` com `H = -180°` em relação a `model`), abertura externa correta exige **`left_yaw > 0, right_yaw < 0, left_roll < 0, right_roll > 0`**.
   - Nenhuma pose (especialmente `virtual_insanity`, `street_groove`, `sleep/sentado` e `idle`) pode girar coxas ou pés para dentro; joelhos devem apontar sobre a linha dos dedos dos pés.
2. **Tecido da Calça na Frente e Atrás (`pernas_tecido.py`)**
   - A calça baggy reage tanto **atrás** quanto **na frente** (`+dir_xy.y` no espaço `legs`) e nas **laterais** (`±X`) à inércia vertical/horizontal, à aceleração do passo e às dobraduras de quadril/joelho, sempre com trava anti-clipping na zona inferior da bota (`ring_idx >= 5`) e costura interna separada do eixo `X = 0`.
3. **Tentáculos Clássicos (`sistema_tentaculos.py`)**
   - Geometria fiel ao modelo antigo aprovado: tubo octogonal (`8 lados`) com perfil cônico orgânico, paleta carmesim/magenta rica e **4 ventosas hexagonais salientes** na face frontal, mantendo compatibilidade total com `TENTACLE_MORPHOLOGIES`, `outline_mesh_node`, quadro de Bishop e abertura das portas do CRT.
4. **Argolas Sci-Fi RGB e Efeitos 2D Limpos (`renderizador.py`, `efeitos_cena.py`)**
   - Argolas das antenas finas, concêntricas, com inclinação orbital sci-fi e transição RGB suave em vez de aros amarelos espessos.
   - Efeitos 2D só disparam por causa clara (nunca durante `walk` normal ou `idle`/`hover` leve), sem barras verticais sobre o tronco em `fall` e com *cooldowns* longos para leitura limpa da silhueta do personagem.
