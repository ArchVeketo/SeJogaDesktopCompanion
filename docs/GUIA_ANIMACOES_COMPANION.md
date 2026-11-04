# Guia de Animações do Companheiro Mário — SeJogaDesktopCompanion

**Data:** 2026-11-03  
**Versão:** 1.0  
**Objetivo:** Definir animações específicas do mascote Mário baseadas em referências dos jogos inspiradores (Bomb Rush Cyberfunk, Lethal League Blaze, Hi-Fi Rush, Persona 5) e padrões de desktop companions.

---

## 1. Visão Geral do Mascote

**Mário** — Personagem estilo Minecraft/Blockbench (low-poly) com **corpo completo**:
- **Cabeça:** Armário com porta funcional (`head` + `door`)
- **Corpo:** Torso + quadril (`body`)
- **Braços:** 2 braços alongados ("ant-arm") com ombro, antebraço, mão e 4 dedos cada (`right-arm`/`left-arm` → `shoulder`/`shoulder2` → `ant-arm`/`ant-arm2` → `hand`/`hand2` → `fingers`/`fingers2`)
- **Pernas:** Unidas (`legs`)
- **Pés:** Esquerdo + direito com sola (`left-feet`/`right-feet`)

**Rig:** Hierarquia de nós (61 nós, 43 meshes, **sem skin**, **sem animações baked**). Animação 100% procedural + keyframes opcionais.

### Comportamento já aplicado no runtime

- No **idle**, a porta apenas entreabre até 3°; os tentáculos são reservados à espiada; ela não gira para trás do monitor.
- O idle começa **tranquilo** e, a cada 10–16 segundos, troca suavemente e sem repetir imediatamente entre cinco personalidades: tranquilo, curioso, brincalhão, tímido e confiante. Cada uma muda o balanço do corpo e o olhar, com braços e cotovelos coordenados.
- Na **dança**, a porta pede até 48°, com movimento amortecido e sem tentáculos.
- A **espiada** dura 9 s: abertura gradual de 2,5 s, sustentação e recolhimento. Aparece após 60–100 s acumulados de idle disponível ou pela ação manual Mostrar tentáculos. Dois tentáculos grossos emergem em sequência, em alturas diferentes.
- Porta limitada a 38°/s; contatos mudam o alvo da mola sem saltar o ângulo. O recolhimento libera o fechamento.
- Na dança, os braços longos ficam recolhidos para baixo, junto às laterais do corpo. Os demais estados ainda usam suas poses próprias.
- Esses movimentos são poses procedurais em `src/sejoga/rig.py`; a tabela completa abaixo continua sendo a especificação para animações futuras.

---

## 2. State Machine de Animação

```
                              ┌──────────────┐
                              │    IDLE      │ ◄──────────────────┐
                              │  (base pose) │                    │
                              └──────┬───────┘                    │
                                     │                            │
                     ┌───────────────┼───────────────┐            │
                     ▼               ▼               ▼            │
               ┌──────────┐    ┌──────────┐    ┌──────────┐       │
               │  WALK    │    │  DRAG    │    │  MUSIC   │       │
               │ (move)   │    │ (mouse)  │    │ (beat)   │       │
               └────┬─────┘    └────┬─────┘    └────┬─────┘       │
                    │               │               │              │
                    ▼               ▼               ▼              │
               ┌──────────┐    ┌──────────┐    ┌──────────┐       │
               │  THROW   │    │  FALL    │    │  DANCE   │       │
               │(release) │    │(physics) │    │ (beat)   │       │
               └────┬─────┘    └────┬─────┘    └────┬─────┘       │
                    │               │               │              │
                    └───────────────┴───────────────┘              │
                                     │                             │
                                     ▼                             │
                              ┌──────────┐                         │
                              │   LAND   │                         │
                              │ (settle) │                         │
                              └────┬─────┘                         │
                                   │                               │
                                   └───────────────────────────────┘
```

---

## 3. Catálogo Completo de Animações

### 3.1 Idle States (Loop ∞)

| Estado | Tipo | Duração | Descrição | Rig Groups | Prioridade |
|--------|------|---------|-----------|------------|------------|
| **IDLE** | Procedural | Loop ∞ | Balanço sutil (sway 0.5-1Hz), respiração (0.2Hz), porta abre/fecha aleatória (0.05Hz) | `head`, `door`, `body`, `shoulder*`, `ant-arm*`, `legs` | Base |
| **IDLE_BREATHE** | Keyframe | 3-5s | Respiração profunda: ombros sobem/descem (inhale 1.5s, hold 0.5s, exhale 2s) | `body`, `shoulder*`, `head` | Variação |
| **IDLE_LOOK** | Keyframe | 2-4s | Olha ao redor: head yaw ±30°, pitch ±15°, porta entreabre 15° | `head`, `door`, `ant-arm*` | Variação |
| **IDLE_SCRATCH** | Keyframe | 2s | Coça a cabeça com ant-arm direito: hand→head contact, fingers curl | `head`, `ant-arm`, `hand`, `fingers` | Variação |
| **IDLE_TAIL_SWAY** | Procedural | Loop | "Tentáculos" (ant-arms) balançam levemente no idle | `ant-arm*`, `hand*` | Ambient |

### 3.2 Locomotion (Procedural + Blend)

| Estado | Tipo | Parâmetros | Descrição | Rig Groups | Blend Params |
|--------|------|------------|-----------|------------|--------------|
| **WALK** | Procedural | `speed` 0.5-1.0 | Ciclo de passada (freq 1.5Hz), braços balançam opostos às pernas (counter-swing), cabeça bob sutil | `legs`, `ant-arm*`, `hand*`, `body`, `head` | `speed`, `direction` |
| **RUN** | Procedural | `speed` 1.0-2.5 | Passada mais longa (stride 1.5x), frequência 2.5Hz, braços bombeiam, lean forward 10° | `legs`, `ant-arm*`, `body`, `head` | `speed`, `direction` |
| **DASH** | Keyframe | 0.3s | Agacha (anticipation 0.1s) → projeta corpo → braços para trás (follow-through 0.2s) | `body`, `legs`, `ant-arm*`, `head` | `dash_phase` |
| **JUMP_START** | Keyframe | 0.15s | Agacha (anticipation), braços sobem (wind-up), squash vertical 0.8x | `legs`, `body`, `ant-arm*`, `head` | `vertical_vel` |
| **JUMP_AIR** | Procedural | Variável | Corpo esticado (stretch 1.1x), braços abertos (glide pose), pernas dobradas | `body`, `ant-arm*`, `legs` | `vertical_vel` |
| **JUMP_LAND** | Keyframe | 0.25s | Aterrissa → squash 0.7x → recoil (stretch 1.15x) → settle (damped spring) | `legs`, `body`, `head`, `door` | `vertical_vel`, `impact_intensity` |
| **DASH_LAND** | Keyframe | 0.3s | Slide no chão (friction), corpo inclina, recupera postura | `legs`, `body`, `ant-arm*` | `speed`, `friction` |

### 3.2 Drag & Throw (Mouse Interaction)

| Estado | Tipo | Duração | Descrição | Rig Groups | Triggers |
|--------|------|---------|-----------|------------|----------|
| **IDLE_DRAG** | Procedural | Contínuo | Segue mouse: corpo inclina na direção (max 20°), ant-arm esticado verso cursor | `body`, `head`, `ant-arm*`, `legs` | `drag_active=1` |
| **DRAG_POSE** | Procedural | Contínuo | Braço ativo esticado verso cursor, fingers fechados (grip), corpo rotaciona | `ant-arm` (ativo), `hand`, `fingers` (closed), `body` | `drag_active=1` |
| **THROW_WINDUP** | Keyframe | 0.15s | Puxa braço para trás (wind-up 90°), rotação corpo oposta, fingers abrem | `ant-arm`, `shoulder`, `hand`, `fingers` (open) | `throw_phase=0.5` |
| **THROW_RELEASE** | Keyframe | 0.1s | Projeta braço (extend 180°), abre dedos, corpo projeta para frente | `ant-arm`, `hand`, `fingers` (open), `body` | `throw_phase=1.0` |
| **THROW_FOLLOW** | Procedural | 0.3s | Follow-through: braço desacelera (damping), corpo recupera postura | `ant-arm`, `hand`, `body` | Auto |
| **THROW_WINDOW_BOUNCE** | Keyframe | 0.4s | Impacto na janela → squash horizontal → slide down → recover | `body`, `head`, `ant-arm*`, `legs` | `collision=window` |

### 3.3 Physics States (pymunk-driven)

| Estado | Tipo | Descrição | Rig Groups | Physics Params |
|--------|------|-----------|------------|----------------|
| **FALL** | Procedural | Gravidade ativa (980 px/s²), corpo relaxado (ragdoll leve), braços/pernas soltos, rotação livre | `body`, `ant-arm*`, `legs`, `head` | `gravity=980`, `damping=0.995` |
| **LAND** | Keyframe + Physics | Impacto → squash 0.6x (0.05s) → recoil stretch 1.2x (0.1s) → damped settle (3 bounces) | `legs`, `body`, `head`, `door`, `legs` | `elasticity=0.55`, `bounce_vel_threshold=50` |
| **THROW_WINDOW_BOUNCE** | Keyframe + Physics | Quica na janela → slide vertical (friction 0.3) → recover pose | `body`, `legs`, `head`, `ant-arm*` | `wall_friction=0.3`, `elasticity=0.4` |
| **WINDOW_CLING** | Procedural | "Gruda" na borda: pernas dobradas (knees 90°), braços na borda (grip), corpo pressionado | `legs`, `ant-arm*`, `hands`, `body` | `cling_force=500` |
| **WINDOW_SIT** | Procedural | Sentado no topo: pernas balançam (pendulum 1Hz), corpo ereto, head bob | `legs`, `body`, `head`, `ant-arm*` | `swing_freq=1.0` |

### 3.4 Music-Reactive (Hi-Fi Rush Style Beat Sync)

| Estado | Trigger | Beat Sync | Descrição | Rig Groups | Intensity |
|--------|---------|-----------|-----------|------------|-----------|
| **MUSIC_IDLE** | Loop/Beat | Downbeat: head nod ↓, shoulder bounce ↑, door pulse; Upbeat: shoulder relax, arm sway | `head`, `body`, `shoulder*`, `ant-arm*`, `door` | `music_intensity` |
| **MUSIC_WALK** | Loop/Beat | Passos quantizados no downbeat (foot plant), arm swing no upbeat | `legs`, `ant-arm*`, `body` | `music_intensity`, `beat_phase` |
| **MUSIC_DANCE** | Loop/Beat | Breakdance stylizado: downbeat=strong pose + door bang + limb extension; offbeat=flourish | `ALL_GROUPS` | `music_intensity` × `dance_probability` |
| **MUSIC_PARRY** | Onset detect | **On beat:** freeze 1 frame + white flash + particle burst + door slam; **Off-beat:** reduced | `head`, `body`, `ant-arm*`, `door` | `beat_accuracy` |
| **MUSIC_HEADBANG** | High energy (BPM>140) | Head bang vigoroso (pitch ±45°), ant-arms windmill, door bang | `head`, `ant-arm*`, `door`, `body` | `high_energy` |

### 3.5 Interaction Reactions (Click/Hover)

| Trigger | Estado | Duração | Descrição | Rig Groups | Cooldown |
|---------|--------|---------|-----------|------------|----------|
| **Left Click** | `CLICK_REACTION` | 0.4s | Head turn toward cursor (yaw ±40°), pisca (blink 0.1s), porta abre/fecha rápido (2x) | `head`, `door` | 0.5s |
| **Right Click** | `PET_REACTION` | 1.5s | Head lean into cursor (pitch -20°, yaw toward), porta vibra (shutter 10Hz), corpo lean | `head`, `door`, `body` | 2s |
| **Middle Click** | `POKE_REACTION` | 0.3s | Squash local no ponto (scale 0.7x), recoil elastico, "oi!" pose (head tilt + arm raise) | `head` (local), `body`, `ant-arm` | 1s |
| **Double Click** | `THROW_REACTION` | 0.5s | Wind-up rápido + throw verso cursor | `ant-arm`, `shoulder`, `hand` | 1s |
| **Hover Enter** | `HOVER_REACTION` | 0.2s | Head turn toward cursor (smooth 0.15s), porta entreabre 30° | `head`, `door` | - |
| **Hover Exit** | `HOVER_EXIT` | 0.3s | Head return to center, porta fecha suave | `head`, `door` | - |
| **Scroll Wheel** | `ZOOM_REACTION` | 0.2s | Head tilt (roll ±15°), escala visual ±10% | `head`, `body` (scale) | - |

### 3.6 Window States (Desktop Integration)

| Estado | Trigger | Tipo | Descrição | Rig Groups |
|--------|---------|------|-----------|------------|
| **WINDOW_CLING** | Drag to edge | Procedural | "Gruda" na borda: pernas dobradas (knees 90°), braços na borda (grip 90°), corpo pressionado | `legs`, `ant-arm*`, `hands`, `body` |
| **WINDOW_PEEK** | Hover edge | Keyframe 1.5s | Olha por cima: head pitch -40°, corpo estica, ant-arms na borda | `head`, `neck`, `body`, `ant-arm*` |
| **WINDOW_SIT** | Drop on top | Procedural | Sentado no topo: pernas balançam (pendulum 1Hz), corpo ereto, head bob | `legs`, `body`, `head`, `ant-arm*` |
| **WINDOW_PEEK_RETURN** | Leave edge | Keyframe 0.5s | Retorna suavemente (ease-out) | `head`, `body`, `ant-arm*` |
| **THROW_WINDOW_BOUNCE** | Throw at window | Keyframe+Physics | Quica na janela → slide vertical → recover | `body`, `legs`, `head`, `ant-arm*` |

### 3.7 Special States

| Estado | Trigger | Duração | Descrição | Rig Groups |
|--------|---------|---------|-----------|------------|
| **SLEEP** | Idle > 90s | Loop | Head drop (pitch -60°), porta fecha, Zzz particles (1.5s interval), respiração lenta (0.1Hz) | `head`, `body`, `door` (closed), `ant-arm*` (relaxed) |
| **WAKE** | User interaction | 1.2s | Stretch (stretch 1.2x), yawn (porta abre wide 90°), shake (shake 0.5s), blink 3x | `head`, `door` (wide), `body`, `ant-arm*`, `legs` |
| **THROW_WINDOW_BOUNCE** | Throw hits window | 0.5s | Quica na janela → slide vertical (friction 0.3) → recover pose | `body`, `legs`, `head`, `ant-arm*` |
| **WINDOW_SIT** | Drop on titlebar | Procedural | Sentado no topo: pernas balançam (pendulum 1Hz), corpo ereto | `legs`, `body`, `head`, `ant-arm*` |
| **IDLE_TAIL_SWAY** | Idle | Procedural | "Tentáculos" (ant-arms) balançam levemente (perlin noise 0.3Hz) | `ant-arm*`, `hand*` |

---

## 4. Beat-Sync Animation Rules (Hi-Fi Rush Style)

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
    },
    "dance": {
        "downbeat": ["strong_pose", "door_bang", "limb_extension"],
        "upbeat": ["transition", "limb_retract"],
        "offbeat": ["flourish", "finger_gun", "head_tilt"]
    }
}
```

### Beat Phase Mapping

```python
BEAT_PHASE_MAP = {
    0.0: "downbeat",      # 0.0 - 0.25
    0.25: "offbeat",      # 0.25 - 0.5
    0.5: "upbeat",        # 0.5 - 0.75
    0.75: "offbeat",      # 0.75 - 1.0
}

def get_beat_subdivision(beat_phase: float) -> str:
    """Map beat phase (0-1) to subdivision"""
    if beat_phase < 0.25: return "downbeat"
    elif beat_phase < 0.5: return "offbeat"
    elif beat_phase < 0.75: return "upbeat"
    else: return "offbeat"
```

---

## 5. Music-Reaction Configuration

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
        "update_interval": 2.0,
        "window_seconds": 4.0,
        "librosa_beat_track": True,
        "phase_lock": True
    },
    "reaction_mapping": {
        "high_energy": {   # BPM > 140, high spectral flux
            "dance_probability": 0.7,
            "intensity_multiplier": 1.5,
            "preferred_anims": ["dance", "headbang", "breakdance"]
        },
        "medium_energy": { # BPM 100-140
            "dance_probability": 0.4,
            "intensity_multiplier": 1.0,
            "preferred_anims": ["dance", "headbob", "shoulder_bounce"]
        },
        "low_energy": {    # BPM < 100, ambient
            "dance_probability": 0.1,
            "intensity_multiplier": 0.5,
            "preferred_anims": ["idle_breathe", "head_nod", "shoulder_sway"]
        },
        "silence": {       # no music > 3s
            "dance_probability": 0.0,
            "return_to_idle": True,
            "fade_time": 2.0
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

## 6. Blend Tree Parameters (Animation Controller)

```python
BLEND_PARAMS = {
    # Locomotion
    "speed": 0.0,           # 0.0=idle, 1.0=walk, 2.0=run
    "direction": 0.0,       # -1.0 (left) to 1.0 (right)
    "vertical_vel": 0.0,    # y velocity (jump/fall)
    
    # Interaction
    "drag_active": 0.0,     # 0.0=no, 1.0=dragging
    "throw_phase": 0.0,     # 0.0=idle, 0.5=windup, 1.0=release
    "drag_direction": 0.0,  # angle to cursor
    
    # Physics
    "vertical_vel": 0.0,    # y velocity
    "grounded": 1.0,        # 1.0=grounded, 0.0=airborne
    "impact_intensity": 0.0,# hit reaction intensity
    "cling_active": 0.0,    # window cling
    
    # Music
    "music_intensity": 0.0, # 0.0=none, 1.0=strong beat
    "beat_phase": 0.0,      # 0.0-1.0 (phase in current beat)
    "bpm": 120.0,           # current BPM
    "beat_confidence": 0.0, # 0.0-1.0
    "energy_level": 0.0,    # 0.0=silence, 1.0=high energy
    
    # Interaction
    "click_reaction": 0.0,  # trigger
    "pet_reaction": 0.0,    # trigger
    "throw_phase": 0.0,     # 0.0=idle, 0.5=windup, 1.0=release
    
    # State
    "sleepiness": 0.0,      # 0.0=awake, 1.0=sleeping
    "window_cling": 0.0,    # 0.0=free, 1.0=clinging
    "throw_phase": 0.0,     # throw animation phase
}
```

---

## 6. Animation Blend Tree Structure

```
                           ┌─────────────────────┐
                           │   MASTER BLEND      │
                           │   (Additive Layers) │
                           └──────────┬──────────┘
                                      │
           ┌──────────────────────────┼──────────────────────────┐
           ▼                          ▼                          ▼
    ┌─────────────┐            ┌─────────────┐            ┌─────────────┐
    │ LOCOMOTION  │            │  INTERACTION │            │   MUSIC     │
    │   LAYER     │            │   LAYER      │            │   LAYER     │
    └──────┬──────┘            └──────┬──────┘            └──────┬──────┘
           │                          │                          │
    ┌──────┴──────┐            ┌──────┴──────┐            ┌──────┴──────┐
    ▼             ▼            ▼             ▼            ▼             ▼
 IDLE◄──►WALK   JUMP/        DRAG◄──►    MUSIC_IDLE◄──►   DANCE
  ◄──►RUN      FALL/        THROW        MUSIC_WALK     MUSIC_DANCE
  ◄──►DASH     LAND         ◄──►THROW    ◄──►MUSIC_PARRY
                         FOLLOW
```

### Layer Priorities (Additive Blending)

| Layer | Priority | Weight | Masks |
|-------|----------|--------|-------|
| **Base** | 0 | 1.0 | Full body |
| **Locomotion** | 1 | `speed/2.0` | Legs, hips, spine, arms (legs=1.0, spine=0.7, arms=0.5) |
| **Interaction** | 2 | `drag_active` / `throw_phase` | Arms, hands, upper body |
| **Music** | 3 | `music_intensity` | Head, shoulders, arms, door (additive) |
| **Physics** | 4 | `(1-grounded)` / `impact_intensity` | Full body (ragdoll blend) |
| **Reaction** | 5 | `click_reaction` / `pet_reaction` | Head, door, upper body (override) |
| **Facial/Detail** | 6 | Various | Face, fingers, door (detail) |

---

## 7. Referências Visuais para Artistas/Animadores

### 7.1 URLs de Busca (YouTube/ArtStation)

| Jogo | Busca Recomendada | Links Úteis |
|------|-------------------|-------------|
| **Bomb Rush Cyberfunk** | "Bomb Rush Cyberfunk animation breakdown", "Bomb Rush Cyberfunk character rig", "Team Reptile animation" | YouTube: "Bomb Rush Cyberfunk animation", ArtStation: "Bomb Rush Cyberfunk character" |
| **Lethal League Blaze** | "Lethal League Blaze animation cancel", "Lethal League hitlag", "fighting game smear frames" | YouTube: "Lethal League Blaze animation cancel", "fighting game smear frame tutorial" |
| **Hi-Fi Rush** | "Hi-Fi Rush animation beat sync", "Hi-Fi Rush rhythm action", "Tango Gameworks animation" | YouTube: "Hi-Fi Rush animation breakdown", "Hi-Fi Rush beat sync system" |
| **Persona 5** | "Persona 5 animation style", "Persona 5 UI animation", "Persona 5 all out attack animation" | YouTube: "Persona 5 UI animation breakdown", "Persona 5 all out attack animation" |
| **Desktop Companions** | "Shimeji animation states", "Comi Pet animation", "desktop companion animation state machine" | GitHub: "IvenKooLab/desktop-pet", "Shimeji-ee", "Shijima-Qt" |

### 7.2 Assets Próprios do Projeto

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

---

## 8. Pipeline de Criação de Animações (Blockbench → Runtime)

### 8.1 Fluxo Recomendado

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
        ├── Animations procedural usam rig groups (rig.py)
        └── Animações keyframed (se houver) via Actor/AnimationController
```

### 8.2 Convenção de Nomes (Blockbench → Código)

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

## 9. Pipeline de Assets 3D (Fora do DSH)

| Fonte | Licença | Tipo | URL |
|-------|---------|------|-----|
| **Poly Haven** | CC0 | Models, HDRIs, Textures | https://polyhaven.com/models |
| **Kenney Assets** | CC0 | Low-poly models, UI, Audio | https://kenney.nl/assets |
| **Sketchfab** | Variada (ver por item) | Models, glTF | https://sketchfab.com |
| **Mixamo** | Adobe (uso em projeto, não redistribuição) | Animations, Rigs | https://www.mixamo.com |
| **Poly Haven** | CC0 | Models, HDRIs | https://polyhaven.com |
| **Quaternius** | CC0 | Low-poly characters | https://quaternius.com |
| **Kenney** | CC0 | Low-poly kits | https://kenney.nl/assets |
| **Blockbench Plugins** | Grátis | Plugins para Blockbench | https://www.blockbench.net/plugins |

---

## 10. Próximos Passos (Implementation Checklist)

> **Nota:** checklist histórico; várias etapas abaixo já foram implementadas. Use [STATUS_E_PROXIMOS_PASSOS.md](STATUS_E_PROXIMOS_PASSOS.md) como roadmap atual.

| Fase | Tarefa | Status |
|------|--------|--------|
| **2.1** | `animation.py` — AnimationController (state machine, blend tree, beat sync) | ⏳ |
| **2.2** | `window.py` — OverlayWindow (Panda3D+Qt bridge, color key, click-through) | ⏳ |
| **2.3** | `physics.py` — ScreenSpacePhysics (pymunk + shelves EnumWindows) | ⏳ |
| **2.4** | `music.py` — MusicListener (GSMTU + soundcard + beat tracker) | ⏳ |
| **2.5** | `rig_animation.py` — Integração `rig.py` + `animation.py` | ⏳ |
| **2.6** | `ui.py` — SettingsDialog + TrayManager + hotkeys | ⏳ |
| **2.7** | `app.py` — Loop principal 60Hz render / 120Hz physics | ⏳ |
| **2.8** | Animações no Blockbench (idle, walk, jump, throw, dance, hit, sleep) | ⏳ |
| **2.9** | Export `.glb` + validação (glTF Validator) | ⏳ |
| **2.9** | Build PyInstaller + Inno Setup + teste em máquina limpa | ⏳ |

---

## 11. Próximos Passos Imediatos

> **Nota:** instruções originais mantidas como referência. O estado atual e as prioridades foram atualizados em [STATUS_E_PROXIMOS_PASSOS.md](STATUS_E_PROXIMOS_PASSOS.md).

1. **Instalar dependências da Etapa 2:**
   ```bash
   pip install -e ".[panda3d,windows,tray,music-analysis]"
   ```

2. **Criar `src/sejoga/animation.py`** com:
   - `AnimationState` enum
   - `AnimationController` class (state machine + blend tree)
   - `BeatSyncMixin` para sincronização musical

3. **Criar `src/sejoga/window.py`** com:
   - `OverlayWindow` (PySide6 QWidget + Panda3D GraphicsWindow embedding)
   - Win32 layered window setup (color key magenta)
   - Click-through toggle + hit-test

4. **Testar integração Panda3D + PySide6** (exemplo mínimo: carrega `.glb`, renderiza em janela transparente)

---

*Fim do guia de animações. Para o roadmap vigente, consulte [STATUS_E_PROXIMOS_PASSOS.md](STATUS_E_PROXIMOS_PASSOS.md).*
