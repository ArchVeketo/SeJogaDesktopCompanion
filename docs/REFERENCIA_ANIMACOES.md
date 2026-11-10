# Referência de Animações — SeJogaDesktopCompanion

**Data:** 2026-11-03  
**Versão:** 1.0  
**Objetivo:** Documentar animações de referência dos jogos inspiradores e definir animações do mascote Mário.

---

## 1. Jogos de Referência — Análise de Animação

### 1.1 Bomb Rush Cyberfunk (Team Reptile, 2023)

| Aspecto | Detalhes |
|---------|----------|
| **Engine** | Unity (cel-shaded) |
| **Estilo visual** | Cel-shaded, inspirado em Jet Set Radio |
| **Personagens** | Skaters, inline skaters, BMX — corpo completo com rig humanoide |
| **Animações-chave** | Grind, ollie, kickflip, wallride, boostpack dash, graffiti spray, dance victory |
| **Transições** | Blend suave entre locomotion e tricks; cancel animation on input |
| **Ritmo** | Movimento sincronizado com música (graffiti no beat) |

**Animações de referência para o Mário:**
- **Idle:** Balanço sutil do corpo, "respiração" do armário (porta abre/fecha sutil)
- **Walk/Run:** Balanço de braços alongados (ant-arm), cabeça balança no ritmo
- **Dash/Boost:** Posição agachada, braços para trás, cabeça para frente
- **Jump:** Antecipação (agacha), extensão completa no ar, aterrissagem com amortecimento
- **Grind/Slide:** Corpo inclinado, braços abertos para equilíbrio
- **Dance/Victory:** Breakdance estilizado, porta do armário abre/fecha no beat

**Referências visuais (buscar no YouTube/ArtStation):**
- "Bomb Rush Cyberfunk animation breakdown"
- "Bomb Rush Cyberfunk character rig"
- "Jet Set Radio animation reference"

---

### 1.2 Lethal League Blaze (Team Reptile, 2018/2019)

| Aspecto | Detalhes |
|---------|----------|
| **Engine** | Unity (2D/3D híbrido) |
| **Estilo** | Cel-shaded, fighting game 2D/3D |
| **Personagens** | 12+ lutadores com estilos únicos (baseball, tennis, skate) |
| **Animações-chave** | Swing (bat/racket), hit impact, knockback, dodge, taunt, victory pose |
| **Impact feel** | Hit pause (hitlag), screen shake, smear frames, motion blur |

**Animações de referência para o Mário:**
- **Hit Reaction:** Head snap, body recoil, arm flail (para quando clicado/arremessado)
- **Swing/Throw:** Anticipation → action → follow-through (para arremesso do Mário)
- **Impact:** Squash & stretch, smear frames (para quicar nas janelas)
- **Taunt/Idle:** Head bob, arm cross, finger point (para interação com mouse)

**Referências visuais:**
- "Lethal League Blaze animation cancel"
- "Lethal League Blaze hitlag"
- "Fighting game smear frames reference"

---

### 1.3 Hi-Fi Rush (Tango Gameworks, 2023)

| Aspecto | Detalhes |
|---------|----------|
| **Engine** | Unreal Engine 4 |
| **Gimmick central** | **Tudo sincronizado com o beat** — movimento, ambiente, UI |
| **Personagem (Chai)** | Cyberpunk, braço robótico, guitarra-armamento |
| **Animações-chave** | Beat-sync walk/run, attack on beat, parry (perfect block), dodge, rhythm minigames |
| **Sistema de ritmo** | Beat tracker → animações quantizadas no grid musical |

**Animações de referência para o Mário (reação à música):**
- **Beat-sync idle:** Head nod, shoulder bounce, arm sway no downbeat
- **Beat walk:** Foot placement quantizado no downbeat, arm swing no offbeat
- **Beat attack/interaction:** Action inicia no downbeat, follow-through no upbeat
- **Parry/Perfect block:** Flash visual, pose freeze por 1 frame, particle burst
- **Rhythm minigame:** Call-and-response (simon says) com cues visuais

**Sistema de "Beat Tracker" para o Mário:**
```
BPM detectado → phase accumulator → quantize animation triggers
Downbeat (1, 3): strong poses, heavy impacts
Upbeat (2, 4): light movements, anticipations
Offbeat (and): transitions, flourishes
```

---

### 1.4 Persona 5 / Persona 5 Royal (P-Studio/Atlus, 2016/2019)

| Aspecto | Detalhes |
|---------|----------|
| **Engine** | Própria (Atlus/P-Studio) |
| **Estilo visual** | Anime stylized, high contrast UI, "stylish" aesthetic |
| **Animações UI/Transição** | Menu transitions fluidas, persona summon (mask shatter), all-out attack |
| **Personagens** | Anime-styled, expressive faces, stylized combat poses |
| **Animações-chave** | Persona summon (mask pull), all-out attack (freeze frame → zoom → finish), baton pass, showtime |

**Animações de referência para o Mário (UI/Personality):**
- **Persona Summon → Mário "Power Up":** Máscara/porta do armário abre → glow → pose de poder
- **All-Out Attack → "Mário Ultimate":** Freeze frame → camera zoom → pose final com linhas de velocidade
- **Baton Pass → "Mário Tag":** Passe de energia entre estados (idle → dance → throw)
- **Menu Transitions:** Snap transitions, stylized wipes (para menus do companion)
- **Confidant Rank Up → "Mário Level Up":** Carta vira, glow, texto aparece letra por letra

**Estilo "Stylish" aplicável ao Mário:**
- **Pose confidence:** Mesmo parado, pose tem atitude (weight shift, head tilt)
- **Micro-expressões:** Pisca, head tilt, mouth movement no idle
- **Color palette shifts:** Mudança de paleta por estado (idle=cool, music=warm, throw=high contrast)

---

## 2. Padrões de Animação para Desktop Companion (Estado da Arte)

### 2.1 Referências de Desktop Companions Existentes

| Projeto | Engine | Animações Notáveis |
|---------|--------|-------------------|
| **Comi Pet (IvenKooLab)** | Tkinter/Python | 8-frame hop, 6-frame blink, walk cycle, throw physics, window-edge walk |
| **Shimeji (Shimeji-ee)** | Java | XML behavior FSM: fall → walk → grab → throw → idle |
| **Desktop Mate (Unity)** | Unity | VRM-based, head-pat, window-sit, drag physics, VRM blendshapes |
| **Shijima-Qt (C++/Qt6)** | Qt6 | Modern C++ rewrite, behavior-driven |

**Padrões consolidados:**
- **State Machine:** Idle → Walk → Drag → Throw → Fall → Land → Idle
- **Physics-driven:** Velocity → animation blend (speed → walk cycle speed)
- **Window awareness:** Edge detection → "cling" animation, "peek" over edge
- **Interactivity:** Click → reaction (pet, poke, throw), drag → drag pose, release → throw

---

## 3. Definição de Animações do Mário (Especificação Completa)

### 3.1 Hierarquia de Rig (do modelo Blockbench)

```
root (0)
├── 47c25daa... (root offset)
├── head (22)
│   ├── cuboid (mesh 0)      -- cabeça principal
│   ├── cylinder (1-4, 8, 17) -- detalhes/cilindros
│   ├── cuboid (5-7)         -- detalhes/cubos
│   ├── pyramid (9, 16)      -- detalhes/pontas
│   ├── sphere (10, 15)      -- olhos/bolas
│   ├── plane (11-14, 18)    -- faces/olhos
│   └── door (21)            -- PORTA DO ARMÁRIO (cuboid mesh 19)
├── body (25)
│   ├── cuboid (23)          -- torso
│   └── cylinder (24)        -- quadril
├── right-arm (38)
│   ├── shoulder (27)        -- ombro
│   │   └── cuboid (22)      -- ombro cubo
│   ├── ant-arm (37)         -- BRAÇO ALONGADO ("tentáculo")
│   │   ├── cuboid (23)      -- braço superior
│   │   └── hand (36)
│   │       ├── cuboid (24,25) -- mão
│   │       └── fingers (35) -- 4 dedos (meshes 26-29)
├── legs (40)
│   └── cuboid (30)          -- pernas unidas
├── left-feet (43)
│   ├── cuboid (31)          -- pé esquerdo
│   └── plane (32)           -- sola
├── right-feet (46)
│   ├── cuboid (33)          -- pé direito
│   └── plane (34)           -- sola
└── left-arm (59)
    ├── shoulder2 (48)       -- ombro esquerdo
    │   └── cuboid (35)
    ├── ant-arm2 (58)
    │   ├── cuboid (36)      -- braço superior
    │   └── hand2 (57)
    │       ├── cuboid (37,38) -- mão
    │       └── fingers2 (56) -- 4 dedos (meshes 39-42)
```

**Total:** 61 nós, 43 meshes, 1 material, 1 textura (1024x1024), **0 animações baked**

---

### 3.2 Estados de Animação (State Machine)

```
┌─────────────────────────────────────────────────────────────┐
                    ANIMATION STATE MACHINE
└─────────────────────────────────────────────────────────────┘

                          ┌──────────────┐
                          │    IDLE      │ ◄──────────────────┐
                          │  (base pose) │                    │
                          └──────┬───────┘                    │
                                 │                            │
                    ┌────────────┼────────────┐              │
                    ▼            ▼            ▼              │
              ┌──────────┐ ┌──────────┐ ┌──────────┐         │
              │  WALK    │ │  DRAG    │ │  MUSIC   │         │
              │  (move)  │ │ (mouse)  │ │  (beat)  │         │
              └────┬─────┘ └────┬─────┘ └────┬─────┘         │
                   │            │            │                │
                   ▼            ▼            ▼                │
              ┌──────────┐ ┌──────────┐ ┌──────────┐         │
              │  THROW   │ │  FALL    │ │  DANCE   │         │
              │ (release)│ │ (physics)│ │ (beat)   │         │
              └────┬─────┘ └────┬─────┘ └────┬─────┘         │
                   │            │            │                │
                   └────────────┴────────────┘                │
                            │                                │
                            ▼                                │
                       ┌──────────┐                           │
                       │   LAND   │                           │
                       │ (settle) │                           │
                       └────┬─────┘                           │
                            │                                 │
                            └────────────────────────────────┘
```

---

### 3.3 Catálogo de Animações (Procedural + Keyframes)

| Estado | Duração | Tipo | Descrição | Rig Groups Envolvidos |
|--------|---------|------|-----------|----------------------|
| **IDLE** | Loop ∞ | Procedural | Balanço sutil (sway), respiração, porta abre/fecha aleatória | `head`, `door`, `body`, `shoulder*`, `ant-arm*`, `legs` |
| **IDLE_BREATHE** | 3-5s | Keyframe | Respiração profunda, ombros sobem/descem | `body`, `shoulder*`, `head` |
| **IDLE_LOOK** | 2-4s | Keyframe | Olha ao redor, cabeça gira, porta entreabre | `head`, `door`, `ant-arm*` |
| **IDLE_SCRATCH** | 2s | Keyframe | Coça a cabeça com ant-arm | `head`, `ant-arm`, `hand`, `fingers` |
| **WALK** | Loop | Procedural | Ciclo de passada, braços balançam opostos às pernas | `legs`, `ant-arm*`, `hand*`, `body`, `head` |
| **RUN** | Loop | Procedural | Passada mais longa, braços bombeiam | `legs`, `ant-arm*`, `body`, `head` |
| **DASH** | 0.3s | Keyframe | Agacha → projeta corpo → braços para trás | `body`, `legs`, `ant-arm*`, `head` |
| **JUMP_START** | 0.2s | Keyframe | Agacha (anticipation), braços sobem | `legs`, `body`, `ant-arm*`, `head` |
| **JUMP_AIR** | Variável | Procedural | Corpo esticado, braços abertos | `body`, `ant-arm*`, `legs` |
| **JUMP_LAND** | 0.3s | Keyframe | Aterrissa, amortece (squash), recoil | `legs`, `body`, `head`, `door` |
| **IDLE_DRAG** | Contínuo | Procedural | Segue mouse, corpo inclina na direção | `body`, `head`, `ant-arm*`, `legs` |
| **DRAG_POSE** | Contínuo | Procedural | Braço esticado verso mouse, corpo segue | `ant-arm` (ativo), `hand`, `fingers` (fechados) |
| **THROW_START** | 0.1s | Keyframe | Puxa braço para trás (wind-up) | `ant-arm`, `shoulder`, `hand`, `fingers` (abrem) |
| **THROW_RELEASE** | 0.15s | Keyframe | Projeta braço, abre dedos, corpo projeta | `ant-arm`, `hand`, `fingers` (abrem), `body` |
| **THROW_FOLLOW** | 0.3s | Procedural | Follow-through, braço desacelera | `ant-arm`, `hand`, `body` |
| **FALL** | Contínuo | Procedural | Corpo relaxado, braços/pernas soltos | `body`, `ant-arm*`, `legs`, `head` |
| **LAND** | 0.4s | Keyframe | Impacto (squash), recoil, settle | `legs`, `body`, `head`, `door`, `legs` |
| **MUSIC_IDLE** | Loop/Beat | Procedural + Beat | Balanço no downbeat, head nod, shoulder bounce | `head`, `body`, `shoulder*`, `ant-arm*`, `door` |
| **MUSIC_WALK** | Loop/Beat | Procedural + Beat | Passos quantizados no downbeat | `legs`, `ant-arm*`, `body` |
| **MUSIC_DANCE** | Loop/Beat | Keyframe + Beat | Breakdance stylizado, porta no beat | `ALL_GROUPS` |
| **MUSIC_PARRY** | 0.1s | Keyframe | Pose freeze (1 frame), flash, partículas | `head`, `body`, `ant-arm*`, `door` |
| **THROW_HIT_WINDOW** | 0.2s | Keyframe | Impacto na janela, recoil, slide | `body`, `head`, `ant-arm*`, `legs` |
| **WINDOW_CLING** | Contínuo | Procedural | "Gruda" na borda, pernas dobradas, braços na borda | `legs`, `ant-arm*`, `hands`, `body` |
| **WINDOW_PEEK** | 1-2s | Keyframe | Olha por cima da janela, cabeça sobe | `head`, `neck`, `body` |
| **CLICK_REACTION** | 0.5s | Keyframe | Head turn toward cursor, pisca, smile | `head`, `door` (abre fecha rápido) |
| **PET_REACTION** | 1-2s | Keyframe | Head lean into cursor, purr (porta vibra) | `head`, `door`, `body` |
| **POKE_REACTION** | 0.3s | Keyframe | Squash local, recoil, "oi!" pose | `head` (local), `body` |
| **SLEEP** | Loop | Procedural | Head drop, Zzz particles, respiração lenta | `head`, `body`, `door` (fecha) |
| **WAKE** | 1s | Keyframe | Stretch, yawn (porta abre wide), shake | `head`, `door`, `body`, `ant-arm*`, `legs` |
| **THROW_WINDOW_BOUNCE** | 0.5s | Keyframe | Quica na janela, slide down, recover | `body`, `legs`, `head`, `ant-arm*` |
| **WINDOW_SIT** | Contínuo | Procedural | Sentado no topo da janela, pernas balançam | `legs`, `body`, `head`, `ant-arm*` |

---

### 3.4 Parâmetros de Blend (Animation Blending)

```python
# Animation Blend Tree Parameters
BLEND_PARAMS = {
    "speed": 0.0,           # 0.0 = idle, 1.0 = walk, 2.0 = run
    "direction": 0.0,       # -1.0 (left) to 1.0 (right)
    "vertical_vel": 0.0,    # y velocity (jump/fall)
    "drag_active": 0.0,     # 0.0 = não arrastando, 1.0 = arrastando
    "throw_phase": 0.0,     # 0.0 = idle, 0.5 = windup, 1.0 = release
    "music_intensity": 0.0, # 0.0 = sem música, 1.0 = beat forte
    "beat_phase": 0.0,      # 0.0-1.0 (phase no beat atual)
    "impact_intensity": 0.0, # hit reaction intensity
    "sleepiness": 0.0,      # 0.0 = acordado, 1.0 = dormindo
}
```

---

### 3.5 Beat-Sync Animation Rules (Hi-Fi Rush Style)

```python
BEAT_SYNC_RULES = {
    "idle": {
        "downbeat": ["head_nod_down", "shoulder_bounce", "door_pulse"],
        "upbeat": ["shoulder_relax", "door_relax"],
        "offbeat": ["ant_arm_sway", "finger_twitch"]
    },
    "walk": {
        "downbeat": ["foot_plant", "arm_swing_extreme"],
        "upbeat": ["foot_lift", "arm_swing_return"],
        "offbeat": ["body_sway", "head_bob"]
    },
    "dance": {
        "downbeat": ["strong_pose", "door_bang", "limb_extension"],
        "upbeat": ["transition", "limb_retract"],
        "offbeat": ["flourish", "finger_gun", "head_tilt"]
    },
    "parry": {
        "on_beat": ["freeze_1frame", "white_flash", "particle_burst", "door_slam_shut"],
        "off_beat": ["reduced_freeze", "dim_flash", "no_particles"]
    },
    "throw_release": {
        "on_beat": ["extra_force", "trail_particles", "sound_punch"],
        "off_beat": ["normal_force", "no_trail"]
    }
}
```

---

### 3.6 Music-Reactive Animation Parameters

```python
MUSIC_REACTION_CONFIG = {
    "beat_detection": {
        "method": "spectral_flux + adaptive_threshold",
        "hop_size": 1024,
        "sample_rate": 48000,
        "history_window": 43,  # ~2s @ 48kHz/1024 hop
        "threshold_multiplier": 1.5
    },
    "bpm_tracking": {
        "update_interval": 2.0,  # seconds
        "window_seconds": 4.0,
        "librosa_beat_track": True,
        "phase_lock": True
    },
    "reaction_mapping": {
        "high_energy": {  # BPM > 140, high spectral flux
            "dance_probability": 0.7,
            "intensity_multiplier": 1.5
        },
        "medium_energy": {  # BPM 100-140
            "dance_probability": 0.4,
            "intensity_multiplier": 1.0
        },
        "low_energy": {  # BPM < 100, ambient
            "dance_probability": 0.1,
            "intensity_multiplier": 0.5
        },
        "silence": {  # no music detected > 3s
            "dance_probability": 0.0,
            "return_to_idle": True
        }
    },
    "animation_triggers": {
        "on_downbeat": ["head_nod", "shoulder_bounce", "door_pulse"],
        "on_upbeat": ["shoulder_relax", "arm_sway"],
        "on_onset": ["micro_jolt", "eye_flash"],
        "on_beat_4": ["dance_transition", "pose_change"],
        "on_phrase_boundary": ["major_pose_shift", "camera_shake_subtle"]
    }
}
```

---

## 4. Assets de Referência (Para Artistas/Animadores)

### 4.1 URLs de Referência (YouTube/ArtStation)

| Jogo | Busca Recomendada | Links Úteis |
|------|-------------------|-------------|
| Bomb Rush Cyberfunk | "Bomb Rush Cyberfunk animation breakdown", "Bomb Rush Cyberfunk character rig", "Team Reptile animation" | YouTube: "Bomb Rush Cyberfunk animation", ArtStation: "Bomb Rush Cyberfunk character" |
| Lethal League Blaze | "Lethal League Blaze animation cancel", "Lethal League hitlag", "fighting game smear frames" | YouTube: "Lethal League Blaze animation cancel", "fighting game smear frame tutorial" |
| Hi-Fi Rush | "Hi-Fi Rush animation beat sync", "Hi-Fi Rush rhythm action", "Tango Gameworks animation" | YouTube: "Hi-Fi Rush animation breakdown", "Hi-Fi Rush beat sync system" |
| Persona 5 | "Persona 5 animation style", "Persona 5 UI animation", "Persona 5 all out attack animation" | YouTube: "Persona 5 UI animation breakdown", "Persona 5 all out attack animation" |
| Desktop Companions | "Shimeji animation states", "Comi Pet animation", "desktop companion animation state machine" | GitHub: "IvenKooLab/desktop-pet", "Shimeji-ee", "Shijima-Qt" |

### 4.2 Assets Próprios do Projeto

| Arquivo | Descrição | Uso |
|---------|-----------|-----|
| `assets/model/mario.gltf` | Modelo base (sem animações) | Rig base para animação procedural |
| `assets/model/mario.glb` | Modelo otimizado (binário) | Runtime |
| `assets/model/projetoMARIO.bbmodel` | Projeto Blockbench fonte | Edição de rig, criação de animações no Blockbench |
| `assets/model/Textura.png` | Atlas de textura 1024x1024 | Material único |
| `assets/brand/mascot-full.png` | Render full-body (3000x3000) | Referência visual, marketing |
| `assets/brand/head-render-1.png` | Close-up cabeça (porta aberta) | Referência porta/animação |
| `assets/brand/head-render-2.png` | Close-up cabeça (outro ângulo) | Referência |
| `assets/brand/turntable.gif` | Turntable 360° | Referência 3D completa |
| `assets/brand/banner.png` | Banner do canal | Marketing |
| `assets/brand/logo-sheet.png` | 9 variantes do logo | UI, branding |

---

## 5. Pipeline de Criação de Animações (Blockbench → Runtime)

### 5.1 Fluxo Recomendado

```
Blockbench 5.x
    │
    ├── Modelagem/rig já pronto (projetoMARIO.bbmodel)
    │
    ├── Aba "Animate" (canto superior direito)
    │   ├── Criar animações: idle, walk, jump, throw, dance, hit, sleep, etc.
    │   │   ├── Keyframes por bone (rotação/posição/escala)
    │   │   ├── Timeline: definir loops (primeiro == último frame)
    │   │   ├── Interpolação: STEP para blocky, LINEAR para suave
    │   │   └── Nomear EXATAMENTE: idle, walk, run, jump, throw, dance, hit, sleep, wake, cling, peek, dance_idle, dance_walk, throw_windup, throw_release, fall, land, sleep, wake
    │   │
    │   └── Export → glTF (.gltf + .bin + .png) OU .glb
    │
    ├── Validação
    │   ├── glTF Validator (https://github.khronos.org/gltf-validator/)
    │   ├── glTF Transform (otimização: https://gltf-transform.donmccurdy.com/)
    │   └── gltfpack (meshoptimizer: https://meshoptimizer.org/)
    │
    └── Runtime
        ├── Carregar via Panda3D (panda3d-gltf) ou raylib
        ├── Animations procedural usam rig groups (esqueleto.py)
        └── Animações keyframed (se houver) via Actor/AnimationController
```

### 5.2 Convenção de Nomes de Animações (Blockbench → Código)

| Nome no Blockbench | Estado no Código | Loop? | Uso |
|--------------------|------------------|-------|-----|
| `idle` | `IDLE` | Sim | Base |
| `idle_breathe` | `IDLE_BREATHE` | Não | Variação idle |
| `idle_look` | `IDLE_LOOK` | Não | Variação idle |
| `idle_scratch` | `IDLE_SCRATCH` | Não | Variação idle |
| `walk` | `WALK` | Sim | Movimento lento |
| `run` | `RUN` | Sim | Movimento rápido |
| `dash` | `DASH` | Não | Dash/boost |
| `jump_start` | `JUMP_START` | Não | Anticipation |
| `jump_air` | `JUMP_AIR` | Sim (loop curto) | No ar |
| `jump_land` | `JUMP_LAND` | Não | Aterrissagem |
| `drag_idle` | `IDLE_DRAG` | Sim | Seguindo mouse |
| `drag_pose` | `DRAG_POSE` | Sim | Pose de arraste |
| `throw_windup` | `THROW_START` | Não | Wind-up |
| `throw_release` | `THROW_RELEASE` | Não | Release |
| `throw_follow` | `THROW_FOLLOW` | Não | Follow-through |
| `fall` | `FALL` | Sim | Caindo |
| `land` | `LAND` | Não | Aterrissagem |
| `music_idle` | `MUSIC_IDLE` | Sim | Idle com música |
| `music_walk` | `MUSIC_WALK` | Sim | Andar no beat |
| `dance` / `dance_idle` | `MUSIC_DANCE` | Sim | Dança no beat |
| `parry` | `MUSIC_PARRY` | Não | Perfect block |
| `throw_window_bounce` | `THROW_WINDOW_BOUNCE` | Não | Quica na janela |
| `cling` | `WINDOW_CLING` | Sim | Grudado na janela |
| `peek` | `WINDOW_PEEK` | Não | Espia janela |
| `click_reaction` | `CLICK_REACTION` | Não | Clique |
| `pet_reaction` | `PET_REACTION` | Não | Carinho |
| `poke_reaction` | `POKE_REACTION` | Não | Cutucada |
| `sleep` | `SLEEP` | Sim | Dormindo |
| `wake` | `WAKE` | Não | Acordar |
| `throw_window_bounce` | `THROW_WINDOW_BOUNCE` | Não | Quica na janela |
| `window_sit` | `WINDOW_SIT` | Sim | Sentado na janela |

---

## 6. Checklist de Implementação (Etapa 2+)

> **Nota:** checklist histórico; consulte [STATUS_E_PROXIMOS_PASSOS.md](STATUS_E_PROXIMOS_PASSOS.md) para as etapas já concluídas e o roadmap atual.

| Fase | Tarefa | Status |
|------|--------|--------|
| **2.1** | `window.py` — OverlayWindow (Panda3D+Qt bridge, color key magenta, click-through seletivo, z-order toggle) | ⏳ |
| **2.2** | `physics.py` — ScreenSpacePhysics (pymunk + shelves EnumWindows one-way) | ⏳ |
| **2.3** | `music.py` — MusicListener (GSMTU + soundcard + beat tracker numpy/librosa) | ⏳ |
| **2.4** | `animation.py` — AnimationController (state machine, blend tree, beat sync) | ⏳ |
| **2.5** | `rig_animation.py` — Integração `esqueleto.py` + `animation.py` (procedural + keyframe) | ⏳ |
| **2.6** | `ui.py` — SettingsDialog + TrayManager + hotkeys | ⏳ |
| **2.7** | `app.py` — Loop principal 60Hz render / 120Hz physics | ⏳ |
| **2.8** | Animações no Blockbench (idle, walk, jump, throw, dance, hit, sleep, etc.) | ⏳ |
| **2.9** | Export `.glb` + validação (glTF Validator) | ⏳ |
| **2.10** | Build PyInstaller + Inno Setup + teste em máquina limpa | ⏳ |

---

## 7. Próximos Passos Imediatos

> **Nota:** instruções originais mantidas como referência. O roadmap vigente está em [STATUS_E_PROXIMOS_PASSOS.md](STATUS_E_PROXIMOS_PASSOS.md).

1. **Instalar dependências da Etapa 2:**
   ```bash
   pip install -e ".[panda3d,windows,tray,music-analysis]"
   ```

2. **Criar `src/sejoga/animacao/animation.py`** com:
   - `AnimationState` enum
   - `AnimationController` class (state machine + blend tree)
   - `BeatSyncMixin` para sincronização musical

3. **Criar `src/sejoga/render/window.py`** com:
   - `OverlayWindow` (PySide6 QWidget + Panda3D GraphicsWindow embedding)
   - Win32 layered window setup (color key magenta)
   - Click-through toggle + hit-test

3. **Testar integração Panda3D + PySide6** (exemplo mínimo: carrega `.glb`, renderiza em janela transparente)

---

*Fim do documento de referência de animações. Para o roadmap vigente, consulte [STATUS_E_PROXIMOS_PASSOS.md](STATUS_E_PROXIMOS_PASSOS.md).*
