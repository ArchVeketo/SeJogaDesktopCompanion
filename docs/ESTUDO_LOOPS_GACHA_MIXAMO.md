# Estudo de Loops Gacha (`skowt.cc`) & Clipes Mixamo para o Mário

Estudo técnico para orientar o refinamento das animações procedurais e o pipeline futuro de loops em glTF/Blockbench do Mário, baseado em:
1. Inspeção da interface e comportamento dos loops em `https://skowt.cc/` (referência Zenless Zone Zero — personagem Jane Doe).
2. Análise binária dos 17 clipes Mixamo FBX (v7.7, `30.00 FPS`, `67` ossos) presentes em `D:\Downloads\animacoes legais`.
3. Contrato atual de poses e camadas em `src/sejoga/animacao/` e `src/sejoga/animacao/clipes_gltf.py`.

---

## 1. Arquitetura de Referência (`skowt.cc` / Zenless Zone Zero)

A visualização de personagens em `https://skowt.cc/` (`Games / Zenless Zone Zero / Characters / Jane`, abas `Models`, `Art`, `Namecards`, `Icons`) expõe quatro pilares úteis para o SeJoga:

### 1.1 Controles de Inspeção Observados
- **Moves:** `Play` / `Pause`, passo quadro a quadro (`A frame back` / `on`), barra de timeline contínua, multiplicadores de velocidade (`1x`, `½×`, `¼×`) e categorias funcionais (`Idle`, `Move`, `Combat`, `Extras`).
- **Pose:** marcadores de juntas manipuláveis, `Undo` / `Redo`, `Mirror side`, `Start over from this frame`, `Reset pose`, `Hide joints` e `Copy link`.
- **Layers:** isolamento ou alternância granular por segmento (`Hair`, `Face`, `Torso`, `Arms`, `Legs`, além de `Solo`).
- **View:** alternância de `Props`, `Shadow`, `Reflection`, `Camera Follow`, sombreamento (`Toon` / `Flat shading`) e presets de iluminação (`Studio`, `Sunset`, `Night`, `Dramatic` com azimute `0–360°`).

### 1.2 Duração, Hierarquia e Overlap dos Loops Gacha
- **Durações medidas @ 30 FPS:**
  - `Idle`: `4.00 s` (`120` frames)
  - `Walk`: `1.167 s` (`35` frames)
  - `Run`: `0.667 s` (`20` frames)
  - `Combat Run`: `5.55 s`
- **Janela de `1 s` a `6 s`:** cycles curtos mantêm baixo custo de memória/CPU, leitura imediata e fechamento limpo (`frame[0] == frame[-1]`).
- **Cascata hierárquica e contra-estabilização:**
  - O quadril conduz o impulso e o tronco/peito responde com atraso aproximado de `~0.25 s`.
  - A cabeça estabiliza o olhar em fase compensatória com atraso de `~0.3 s`.
  - Apêndices secundários (cauda, cabelo, tecido/aba) propagam onda de follow-through defasada em `~0.5 s`.

---

## 2. Análise dos 17 Clipes Mixamo (`D:\Downloads\animacoes legais`)

Todos os arquivos amostrados usam FBX binário v7.7 a `30.00 FPS` com esqueleto padrão Mixamo de `67` ossos.

### 2.1 Classificação por Fechamento de Loop

| Categoria | Arquivo | Duração | Frames | Observações Técnicas |
|---|---|---:|---:|---|
| Loop exato | `Standard Walk.fbx` | `1.167 s` | `36` | `ΔZ = +182.47 cm` (`156.3 cm/s`), zero drift angular |
| Loop exato | `Boxing.fbx` | `1.800 s` | `55` | In-place, cadência `133.3 BPM` |
| Loop exato | `Dodging Right.fbx` | `1.433 s` | `44` | In-place, cadência `167.5 BPM` |
| Loop exato | `Flair.fbx` | `1.000 s` | `31` | In-place, `120 BPM`, rotação módulo `360°` |
| Quase-loop | `Arm Stretching.fbx` | `8.867 s` | — | Erro ponta-a-ponta `0.030°` |
| Quase-loop | `Left Strafe Walking.fbx` | `1.033 s` | — | Erro ponta-a-ponta `0.010°` |
| Quase-loop | `Swimming.fbx` | `4.533 s` | — | Erro ponta-a-ponta `0.011°` |
| Quase-loop | `Dancing Twerk.fbx` | `15.200 s` | — | Erro ponta-a-ponta `0.044°` |
| Quase-loop | `Walk Strafe Left.fbx` | `1.467 s` | — | Erro ponta-a-ponta `0.380°` |
| Quase-loop | `Right Strafe Walk.fbx` | `0.933 s` | — | Erro ponta-a-ponta `3.389°` |
| Quase-loop | `Breakdance Freeze Var 2.fbx` | `4.867 s` | — | Erro ponta-a-ponta `5.136°` |
| Quase-loop | `Breakdance Uprock Var 2.fbx` | `5.333 s` | — | Erro ponta-a-ponta `9.213°` |
| One-shot | `Cover To Stand.fbx` | `1.500 s` | — | Transição não cíclica |
| One-shot | `Baseball Hit.fbx` | `3.900 s` | — | Ação única |
| One-shot | `Goalkeeper Drop Kick.fbx` | `3.900 s` | — | Ação única |
| One-shot | `Running.fbx` | `1.633 s` | — | Clipe assimétrico para fechar em loop |
| One-shot | `Breakdance 1990.fbx` | `3.500 s` | — | Ação única com giro |

### 2.2 Métricas de Overlap e Raiz Extraídas dos FBX
- **Follow-through ombro → antebraço:** o pico angular do ombro antecede o pico do antebraço em `+5 frames` (`0.16 s` @ `30 FPS`).
- **Contra-rotação peito ↔ cabeça:** o pitch do tórax fica defasado em `0.47 s` em relação à estabilização da cabeça.
- **Tratamento de Root Motion:** preservar o deslocamento vertical `Y` (variação até `5.33 cm`, capturando compressão de passo e squash/stretch) e remover deslocamento horizontal `(X, Z)` nos clipes locomotores para que a velocidade no desktop continue controlada pelo Pymunk e pela camada física.

---

## 3. Aplicação Prática ao Mário (`SeJogaDesktopCompanion`)

1. **Fechamento contínuo de loops curtos (`1–6 s`):**
   - Ao importar quase-loops (`Arm Stretching`, `Swimming`, `Breakdance Uprock Var 2`, etc.) para glTF, aplicar blend C2 (Hermite / Slerp nos últimos `3–4 frames`) garantindo `delta(0.0) == delta(T)` e derivada contínua na virada do ciclo.
   - Evitar loops longos (> `6 s`) quando puderem ser fatiados em variações menores combináveis com camadas (`LayerStack`), reduzindo repetitividade perceptível sem peso de asset.
2. **Defasagem hierárquica obrigatória em ações procedurais e clipes:**
   - Base/quadris (`hips` / `torso`) conduzem o ritmo principal (`fase 0`).
   - Ombros/tórax (`peitoral`) acompanham em cascata curta (`~0.16–0.25 s`), braços/antebraços atrasam `+0.16 s`, cabeça estabiliza em contra-fase (`~0.30–0.47 s`), e apêndices (antenas, argolas, tentáculos, barra da calça/fita) atrasam ~`0.5 s`.
3. **Mapeamento Mixamo (`67` ossos) → Rig do Mário (`ALL_GROUPS`, `30` grupos):**
   - Toda trilha exportada para o Mário entra em delta local (`Rotation3(x=P, y=H, z=R)`) convertida pela matriz `_GLTF_PARA_AUTORIA` em `src/sejoga/animacao/clipes_gltf.py` (`src/sejoga/nucleo/cinematica.py`).
   - Quadris e coluna mapeiam para `body` / `torso` / `peitoral`; cabeça e pescoço convergem em `head`; ombro/braço/antebraço/mão mapeiam para os respectivos grupos simétricos e `ant-arm`; pernas e pés respeitam a cinemática inferior (`lower_body` / `legs` / `left-feet` / `right-feet`).

### 3.1 Prioridade Recomendada dos Próximos 5 Clipes (Pipeline glTF)
1. `Standard Walk.fbx` (`1.167 s`, loop exato) — ciclo base de caminhada com root `Y` preservado (`5.33 cm`).
2. `Boxing.fbx` (`1.800 s`, loop exato, `133.3 BPM`) — reação ativa / humor energético e provocação.
3. `Dodging Right.fbx` (`1.433 s`, loop exato, `167.5 BPM`) — esquiva lateral para reações rápidas e interação com cursor.
4. `Arm Stretching.fbx` (`8.867 s`, quase-loop `0.030°`) — variação natural de ociosidade com fechamento Hermite/Slerp em `3–4 frames` (ou sub-loop fatiado dentro de `<= 6 s`).
5. `Flair.fbx` (`1.000 s`, loop exato, `120 BPM`) — floreio acrobático para dança/vitória com continuidade módulo `360°`.
