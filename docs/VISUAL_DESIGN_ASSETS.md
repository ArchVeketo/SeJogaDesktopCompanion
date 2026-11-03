# Visual Design & Art Direction — SeJogaDesktopCompanion

**Data:** 2026-11-03  
**Versão:** 1.0  
**Objetivo:** Definir todos os assets visuais 2D (sprites, particles, UI, fonts, paleta) para o companion Mário

---

## 1. Paleta de Cores Oficial (Mário)

### 1.1 Cores Principais (Extraídas do Modelo 3D + Brand)

| Nome | Hex | RGB | Uso | Contexto |
|------|-----|-----|-----|----------|
| **Armário Base** | `#4A3F35` | 74, 63, 53 | Corpo principal do armário | Base color |
| **Armário Claro** | `#5D4E42` | 93, 78, 66 | Highlights do armário | Highlights |
| **Armário Escuro** | `#362D26` | 54, 45, 38 | Sombras, reentrâncias | Shadows |
| **Porta** | `#5D4E42` | 93, 78, 66 | Porta do armário | Functional |
| **Porta Aberta (Interior)** | `#2D1B15` | 45, 27, 21 | Interior escuro | Depth |
| **Rosa Neon (Destaque)** | `#FF2D95` | 255, 45, 149 | **Cor signature** - olhos, accents, UI | **Signature** |
| **Rosa Neon Claro** | `#FF6EC7` | 255, 110, 199 | Highlights rosa | Highlights |
| **Rosa Neon Escuro** | `#CC0077` | 204, 0, 119 | Pressed states | Pressed |
| **Verde Neon (Música)** | `#00FF88` | 0, 255, 136 | Beat sync, música ativa | Music |
| **Azul Ciano (Tech)** | `#00D4FF` | 0, 212, 255 | Tech/UI elements, speaker | Tech |
| **Amarelo Ouro (Itens)** | `#FFD700` | 255, 215, 0 | Itens, coins, rewards | Items |
| **Laranja Fogo (Throw)** | `#FF6B35` | 255, 107, 53 | Throw, dash, impacto | Action |
| **Branco Suave** | `#F5F0EB` | 245, 240, 235 | Texto principal, UI clara | Text |
| **Preto Suave** | `#1A1612` | 26, 22, 18 | Texto escuro, outlines | Text Dark |
| **Cinza Fumaça** | `#8B7D72` | 139, 125, 114 | Partículas, disabled states | Particles |
| **Branco Partícula** | `#FFFFFF` | 255, 255, 255 | Partículas brilhantes | Particles |

### 1.2 Gradientes Oficiais

```css
/* Gradiente Signature (Rosa Neon) */
background: linear-gradient(135deg, #FF2D95 0%, #FF6EC7 50%, #FF2D95 100%);

/* Gradiente Música (Verde → Ciano) */
background: linear-gradient(90deg, #00FF88 0%, #00D4FF 100%);

/* Gradiente Fogo (Laranja → Vermelho) */
background: linear-gradient(45deg, #FF6B35 0%, #FF2D55 100%);

/* Gradiente UI Dark */
background: linear-gradient(180deg, #1A1612 0%, #2D1B15 100%);
```

### 1.3 Semântica de Cores (Design System)

| Semântica | Cor | Uso |
|-----------|-----|-----|
| **Primary** | `#FF2D95` | Botões primários, links, focus |
| **Secondary** | `#00D4FF` | Botões secundários, info |
| **Success** | `#00FF88` | Sucesso, música ativa, beat |
| **Warning** | `#FFD700` | Avisos, itens raros |
| **Danger** | `#FF2D55` | Erro, perigo, delete |
| **Background** | `#1A1612` | Fundo principal |
| **Surface** | `#2D1B15` | Cards, menus, modais |
| **Border** | `#4A3F35` | Bordas sutis |
| **Text Primary** | `#F5F0EB` | Texto principal |
| **Text Muted** | `#8B7D72` | Texto secundário |
| **Accent** | `#FF2D95` | Destaques, hover |

---

## 2. Tipografia

### 2.1 Fontes Oficiais

| Uso | Fonte | Fallback | Tamanhos | Peso |
|-----|-------|----------|----------|------|
| **Display/Logo** | **"Bangers"** | "Fredoka One", cursive | 24-48px | 400 |
| **UI Principal** | **"JetBrains Mono"** | "Fira Code", "Cascadia Code", monospace | 12-16px | 400, 500, 700 |
| **UI Pequena** | **"JetBrains Mono"** | monospace | 10-11px | 400 |
| **Números/Contadores** | **"Space Mono"** | "JetBrains Mono", monospace | 14-24px | 700 |
| **Handwriting/Notas** | **"Kalam"** | "Comic Neue", cursive | 13-16px | 400, 700 |

### 2.2 Escala Tipográfica (Design Tokens)

```css
:root {
  --text-xs: 10px;      /* Labels, timestamps */
  --text-sm: 12px;      /* Body small, captions */
  --text-base: 14px;    /* Body padrão */
  --text-lg: 16px;      /* Body large, buttons */
  --text-xl: 20px;      /* Subtítulos */
  --text-2xl: 28px;     /* Títulos seção */
  --text-3xl: 40px;     /* Título principal */
  --text-4xl: 56px;     /* Hero, logo */
  
  --leading-tight: 1.2;
  --leading-normal: 1.5;
  --leading-relaxed: 1.75;
}
```

### 2.3 Google Fonts CDN (Para Web/HTML UI)

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bangers&family=JetBrains+Mono:wght@400;500;700&family=Kalam:wght@400;700&family=Space+Mono:wght@700&display=swap" rel="stylesheet">
```

---

## 3. Particle Systems / Sprites Animados

### 3.1 Sistema de Partículas (Especificação Técnica)

```python
PARTICLE_CONFIG = {
    # Configurações globais
    "max_particles": 200,
    "pool_size": 500,
    "atlas_path": "assets/sprites/particles.png",
    "atlas_grid": (8, 8),  # 64 frames
    
    # Emissores
    "emitters": {
        "dust_landing": {
            "spawn_rate": 30,      # particles/sec
            "burst_count": 8,      # on land
            "lifetime": (0.3, 0.6),
            "size": (4, 12),
            "velocity": (0, 50),   # upward then gravity
            "gravity": 200,
            "fade": "out",
            "colors": ["#8B7D72", "#A09085", "#6B5D52"],
            "scale_curve": "ease_out",
            "rotation": (-0.5, 0.5),
        },
        "dust_sliding": {
            "spawn_rate": 20,
            "lifetime": (0.2, 0.4),
            "size": (3, 8),
            "velocity": (-30, 30),
            "gravity": 100,
            "colors": ["#8B7D72", "#6B5D52"],
            "scale_curve": "linear",
        },
        "smoke_throw": {
            "spawn_rate": 0,
            "burst_count": 12,
            "lifetime": (0.4, 0.8),
            "size": (8, 24),
            "velocity": (-50, 50),
            "gravity": -20,  # rises
            "colors": ["#4A3F35", "#5D4E42", "#362D26"],
            "alpha_curve": "fade_out",
            "scale_curve": "ease_in",
            "rotation": (-1.0, 1.0),
        },
        "music_notes": {
            "spawn_rate": 0,
            "burst_on_beat": 3,
            "lifetime": (0.8, 1.5),
            "size": (16, 32),
            "velocity": (0, -80),  # upward
            "gravity": -30,
            "colors": ["#00FF88", "#00D4FF", "#FF2D95", "#FFD700"],
            "shapes": ["eighth", "quarter", "half", "whole"],
            "scale_curve": "ease_out",
            "rotation": (-0.3, 0.3),
            "fade": "out",
        },
        "spark_impact": {
            "burst_count": 8,
            "lifetime": (0.1, 0.3),
            "size": (2, 6),
            "velocity": (100, 300),
            "gravity": 300,
            "colors": ["#FF6B35", "#FFD700", "#FF2D95", "#FFFFFF"],
            "scale_curve": "ease_out",
        },
        "dust_idle": {
            "spawn_rate": 2,
            "lifetime": (2.0, 4.0),
            "size": (2, 6),
            "velocity": (-5, 5),
            "gravity": 10,
            "colors": ["#8B7D72", "#A09085"],
            "alpha": 0.3,
        },
        "sparkle_magic": {
            "spawn_rate": 5,
            "lifetime": (0.5, 1.0),
            "size": (4, 12),
            "velocity": (-20, 20),
            "gravity": -50,
            "colors": ["#FFD700", "#FFD700", "#FFF8DC", "#FF2D95"],
            "shapes": ["star", "sparkle", "diamond"],
            "twinkle": True,
        },
        "speaker_waves": {
            "spawn_on_beat": True,
            "burst_count": 2,
            "lifetime": (0.6, 1.0),
            "size": (20, 60),
            "velocity": (0, -40),
            "colors": ["#00D4FF44", "#00FF8844"],  # with alpha
            "shapes": ["wave_ring", "wave_bar"],
            "scale_curve": "ease_out",
        },
        "speaker_pulse": {
            "on_beat": True,
            "scale_pulse": (1.0, 1.15),
            "duration": 0.15,
            "color_tint": "#00D4FF",
        },
    }
}
```

### 3.2 Sprite Sheets (Atlas) — Layout Sugerido

```
particles.png (512x512) - 8x8 grid = 64 frames (64x64 each)

Row 0: Dust (8 frames) - landing dust animation
Row 1: Dust sliding (8 frames)
Row 2: Smoke/Throw (8 frames)
Row 3: Music Notes (8 frames) - eighth, quarter, half, whole, sixteenth, dotted, rest, clef
Row 4: Sparks/Impact (8 frames)
Row 5: Music Notes Variants (8 frames) - different styles
Row 6: Sparkle/Magic (8 frames) - star, diamond, sparkle, heart, circle, square, triangle, cross
Row 7: Speaker Waves (4) + Pulse (4)

UI Elements (separate atlas: ui_atlas.png 256x256)
- Buttons (normal/hover/pressed/disabled) - 9-slice
- Sliders (track, thumb, fill)
- Checkboxes/Radio (on/off/indeterminate)
- Dropdown arrows
- Close/Minimize/Maximize
- Scrollbars
- Tooltips backgrounds
- Toasts
- Context menu
- Color picker swatches
```

### 3.3 Especificação por Tipo de Partícula

| Partícula | Atlas Frame | Size (px) | Lifetime | Cor | Comportamento |
|-----------|-------------|-----------|----------|-----|---------------|
| **Dust Landing** | 0-7 | 8-16 | 0.3-0.6s | `#8B7D72` → fade | Gravity, fade out, slight rotation |
| **Dust Slide** | 8-15 | 4-10 | 0.2-0.4s | `#6B5D52` → fade | Horizontal velocity, fade |
| **Smoke Throw** | 16-23 | 16-32 | 0.4-0.8s | `#4A3F35` → transparent | Rises, expands, fades |
| **Music Note ♪** | 24-31 | 16-32 | 0.8-1.5s | Beat color | Rises, fades, slight sway |
| **Spark Impact** | 32-39 | 4-8 | 0.1-0.3s | `#FF6B35`/`#FFD700` | Burst, gravity, fade fast |
| **Dust Idle** | 40-47 | 4-8 | 2-4s | `#8B7D72` (30% alpha) | Gentle drift |
| **Sparkle Magic** | 48-55 | 8-16 | 0.5-1.0s | Gold/Pink | Twinkle, rise, fade |
| **Speaker Wave** | 56-59 | 32-64 | 0.6-1.0s | Cyan/Green (15% alpha) | Ring expands, fades |
| **Speaker Pulse** | 60-63 | - | 0.15s | Cyan tint | Scale pulse 1.0→1.15 |

---

## 4. UI Sprites & Components

### 4.1 UI Atlas (ui_atlas.png — 512x512, 9-slice ready)

```
UI Atlas Layout (512x512):

Buttons (96x32 each, 9-slice ready):
Row 0: Primary (normal/hover/pressed/disabled/focus) - 5 states × 96px = 480px
Row 1: Secondary (5 states)
Row 2: Danger (5 states)
Row 3: Ghost/Outline (5 states)
Row 4: Icon-only (48x48, 4 states)

Sliders (64x16 track, 24x24 thumb):
Row 5: Horizontal slider (track bg, fill, thumb states)
Row 6: Vertical slider

Checkboxes/Radio (24x24):
Row 6: Checkbox (unchecked/hover/checked/disabled/indeterminate)
Row 7: Radio (same states)

Dropdown/Select (32x32):
Row 7: Dropdown arrow (4 states), menu bg, item states

Window Controls (16x16):
Row 8: Close/Min/Max/Restore (hover/pressed)

Tooltips (9-slice):
Row 8: Tooltip bg (4 corners, 4 edges, center)

Context Menu (9-slice):
Row 9: Menu bg, separator, item states, submenu arrow

Scrollbars:
Row 10: Vertical/Horizontal track, thumb (hover/drag)

Color Picker:
Row 11: Hue slider, saturation/value square, alpha slider, swatches

Tabs:
Row 11: Tab states (normal/hover/active/disabled)
```

### 4.2 Button Specs (Design Tokens)

```css
.button {
  --btn-height: 36px;
  --btn-padding-x: 16px;
  --btn-radius: 8px;
  --btn-font: var(--text-base);
  --btn-weight: 500;
  --btn-transition: 120ms ease-out;
  
  /* Primary */
  --btn-primary-bg: #FF2D95;
  --btn-primary-hover: #FF6EC7;
  --btn-primary-pressed: #CC0077;
  --btn-primary-text: #FFFFFF;
  
  /* Secondary */
  --btn-secondary-bg: #2D1B15;
  --btn-secondary-border: #4A3F35;
  --btn-secondary-hover: #362D26;
  --btn-secondary-text: #F5F0EB;
  
  /* Danger */
  --btn-danger-bg: #FF2D55;
  --btn-danger-hover: #FF4D70;
  --btn-danger-text: #FFFFFF;
  
  /* Ghost */
  --btn-ghost-bg: transparent;
  --btn-ghost-hover: #2D1B15;
  --btn-ghost-text: #FF2D95;
}
```

### 4.3 Menu/Context Menu Sprites

```
Context Menu (min-width 200px, max 320px):
- Background: #2D1B15, border #4A3F35, shadow 0 8px 32px #00000080
- Items: 32px height, padding 8px 12px
- Icons: 16x16 left-aligned, gap 10px
- Separator: 1px #4A3F35, margin 4px 8px
- Submenu arrow: ► (8x8), right-aligned
- Hover: bg #362D26
- Disabled: opacity 0.4, text #8B7D72
```

---

## 5. Menu Sprites & Backgrounds

### 5.1 Settings Menu Background

```
Settings Panel (400x560 min):
┌─────────────────────────────────────┐
│  ╭───────────────────────────────╮  │
│  │  ⚙  Configurações        ✕  │  │  ← Header (48px)
│  ╰───────────────────────────────╯  │
│ ├──────────────────────────────────┤ │
│ │ 🎨 Aparência        ▼            │  │  ← Collapsible sections
│ │ 🎮 Controles         ▼            │  │
│ │ 🎵 Música & Audio    ▶            │  │
│ │ ⚙️ Comportamento      ▼            │  │
│ │ 🔔 Notificações       ▼            │  │
│ │ 🎨 Tema              ▼            │  │
│ ├──────────────────────────────────┤ │
│ │  [Restaurar Padrões]  [Salvar]    │  │  ← Footer actions
│ ╰──────────────────────────────────╯  │
└─────────────────────────────────────┘
```

**Background:** `#1A1612` com noise sutil (opacity 3%), border `#4A3F35` 1px, shadow `0 16px 48px #00000080`, border-radius 12px

### 5.2 Theme Selector Sprites

```
Theme Cards (84x60 each, 3 per row):
┌─────────────────────────────────────┐
│  🌙 Escuro      ☀️ Claro      🌈 RGB │  ← Theme cards
│  ▢ Ativo       ▢            ▢       │  ← Radio style
└─────────────────────────────────────┘
```

---

## 6. Item Sprites (Inventário/Usáveis)

### 6.1 Categorias de Itens

| Categoria | Ícone Base | Cor | Exemplos |
|-----------|------------|-----|----------|
| **Consumíveis** | 🍔 🍕 🥤 🍰 | `#FF6B35` (laranja) | Food, drinks, energy |
| **Música** | 🎵 🎧 🎸 🎹 | `#00D4FF` (ciano) | Records, headphones, instruments |
| **Tech** | 💻 📱 🎮 🎧 | `#00D4FF` (ciano) | Gadgets, devices |
| **Cosméticos** | 🎩 👕 👟 🕶️ | `#FF2D95` (rosa) | Hats, clothes, glasses |
| **Ferramentas** | 🔧 🔨 🔩 📏 | `#8B7D72` (cinza) | Tools, utilities |
| **Especiais** | ✨ 💎 🌟 🎁 | `#FFD700` (ouro) | Rare, event, premium |
| **Caixa de Som** | 🔊 📢 🎤 | `#00D4FF` | Speaker, megaphone, mic |

### 6.2 Item Sprite Specs (64x64 base, 4x4 grid = 256x256)

```
items.png (256x256) - 4x4 grid = 16 items (64x64 each)

Row 0: Food/Drinks
  🍔 Burger    🍕 Pizza    🥤 Soda      🍰 Cake

Row 1: Music
  🎵 Note      🎧 Headphones  🎸 Guitar   🎹 Piano

Row 2: Tech/Gadgets
  💻 Laptop    📱 Phone      🎮 Controller 🎧 Headset

Row 3: Cosmetics/Accessories
  🎩 Hat       👕 Shirt      👟 Sneakers  🕶️ Glasses

Extended (items_extended.png 512x256):
Row 4: Tools/Utils
  🔧 Wrench    🔨 Hammer     🔩 Screw     📏 Ruler

Row 5: Speaker/Audio
  🔊 Speaker   📢 Megaphone  🎤 Mic       📻 Radio

Row 6: Special/Rare
  ✨ Sparkle   💎 Diamond    🌟 Star      🎁 Gift

Row 6: Seasonal/Event
  🎃 Pumpkin   🎄 Tree       💝 Heart     🎂 Cake
```

### 6.3 Item Data Structure (JSON)

```json
{
  "items": [
    {
      "id": "burger",
      "name": "Hambúrguer",
      "category": "food",
      "sprite": "burger",
      "rarity": "common",
      "effects": { "energy": 25, "happiness": 10 },
      "sprite_coords": { "x": 0, "y": 0, "w": 64, "h": 64 }
    },
    {
      "id": "vinyl_record",
      "name": "Vinil do Hideki Naganuma",
      "category": "music",
      "sprite": "vinyl",
      "rarity": "rare",
      "effects": { "music_boost": 2.0, "duration": 300 },
      "sprite_coords": { "x": 64, "y": 64, "w": 64, "h": 64 }
    },
    {
      "id": "bluetooth_speaker",
      "name": "JBL Boombox",
      "category": "tech",
      "sprite": "speaker",
      "rarity": "epic",
      "effects": { "music_range": 3.0, "quality": "high" },
      "sprite_coords": { "x": 192, "y": 128, "w": 64, "h": 64 }
    }
  ]
}
```

---

## 7. Speaker / Caixa de Som (Asset Especial)

### 7.1 Speaker Sprite Variants

```
speaker.png (256x256) - 4 variants (128x128 each)

Variant 0: Idle/Closed
┌──────────────────┐
│  ┌────────────┐  │
│  │ ██████████ │  │  ← Speaker grille
│  │ ██████████ │  │
│  │ ██████████ │  │
│  │ ─────────  │  │  ← Base
│  └────────────┘  │
└──────────────────┘
Colors: #2D1B15 (body), #4A3F35 (grille), #FF2D95 (accent LED)

Variant 1: Playing (Music)
┌──────────────────┐
│  ┌────────────┐  │
│  │ ██████████ │  │  ← Grille pulsing
│  │ ██████████ │  │     with music
│  │ ██████████ │  │
│  │ ─────────  │  │
│  └────────────┘  │
└──────────────────┘
Colors: + #00D4FF pulse glow, #00FF88 beat accents

Variant 2: Beat Pulse (on beat)
Scale: 1.0 → 1.15 → 1.0 (0.15s)
Glow: #00D4FF → #00FF88 → fade

Variant 3: Party Mode (High Energy)
Rotation: ±2° wiggle
Colors: Rainbow cycle
Particles: Music notes + sparkles
```

### 7.2 Speaker Data Structure

```json
{
  "speaker": {
    "id": "bluetooth_speaker",
    "name": "JBL Boombox 3",
    "sprites": {
      "idle": "speaker_idle",
      "playing": "speaker_playing",
      "beat_pulse": "speaker_pulse",
      "party": "speaker_party"
    },
    "animations": {
      "beat_pulse": { "scale": [1.0, 1.15, 1.0], "duration": 0.15 },
      "party_wiggle": { "rotation": [-2, 2], "duration": 0.1, "repeat": true },
      "idle_bob": { "y_offset": [-2, 2], "duration": 3.0, "ease": "sine" }
    },
    "colors": {
      "body": "#2D1B15",
      "grille": "#4A3F35",
      "accent_idle": "#FF2D95",
      "accent_playing": "#00D4FF",
      "accent_beat": "#00FF88",
      "accent_party": "rainbow"
    },
    "particles": {
      "on_beat": ["music_note", "sparkle"],
      "party_mode": ["music_note", "sparkle", "confetti"]
    }
  }
}
```

---

## 8. Backgrounds & Environments

### 8.1 Desktop Background Integration

O companion vive **sobre** o desktop do usuário. Não há "background" próprio, mas:

```css
/* Overlay do companion (sempre por cima) */
.companion-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  pointer-events: none;  /* Click-through por padrão */
  z-index: 2147483647;   /* Acima de tudo */
}

/* Quando interagindo: pointer-events: auto no bounding box do modelo */
.companion-interactive {
  pointer-events: auto;
}
```

### 8.2 Menu/Modal Backgrounds

```css
.modal-backdrop {
  background: rgba(26, 22, 18, 0.85);  /* #1A1612DD */
  backdrop-filter: blur(8px);
  backdrop-filter: saturate(120%);
}

.menu-panel {
  background: linear-gradient(145deg, #1A1612 0%, #2D1B15 100%);
  border: 1px solid #4A3F35;
  box-shadow: 
    0 4px 12px rgba(0,0,0,0.3),
    0 0 0 1px rgba(74,63,53,0.5) inset,
    0 16px 48px rgba(0,0,0,0.4);
  border-radius: 12px;
}
```

---

## 9. Asset Pipeline & Export Checklist

### 9.1 Export Checklist (Para Artistas)

| Asset | Formato | Resolução | Naming | Checklist |
|-------|---------|-----------|--------|-----------|
| **Particle Atlas** | PNG | 512x512 | `particles.png` | ☐ Grid 8x8 ☐ Premultiplied alpha ☐ No bleed |
| **UI Atlas** | PNG | 512x512 | `ui_atlas.png` | ☐ 9-slice ready ☐ All states ☐ No bleed |
| **Items Atlas** | PNG | 256x256 | `items.png` | ☐ 4x4 grid ☐ Transparent bg ☐ Centered |
| **Items Extended** | PNG | 512x256 | `items_extended.png` | ☐ 4x8 grid |
| **Speaker Sprites** | PNG | 256x256 | `speaker.png` | ☐ 2x2 variants |
| **UI Atlas @2x** | PNG | 1024x1024 | `ui_atlas@2x.png` | ☐ Retina ready |
| **Particle Atlas @2x** | PNG | 1024x1024 | `particles@2x.png` | ☐ Retina ready |

### 9.2 Export Settings (Aseprite/Photoshop/Krita)

```
Color Mode: RGBA
Color Profile: sRGB IEC61966-2.1
Background: Transparent
Dithering: None
Compression: PNG (lossless)
Metadata: Strip EXIF
```

### 9.3 Naming Convention

```
<category>_<name>_<state>_<frame>.png
Exemplos:
  particle_dust_landing_00.png
  particle_music_note_03.png
  ui_button_primary_hover.png
  ui_button_primary_pressed.png
  item_burger_idle.png
  speaker_idle_00.png
  speaker_playing_02.png
  ui_button_primary_hover@2x.png
```

---

## 10. Implementation Snippets (Para Devs)

### 10.1 Particle System Integration (Pseudo-code)

```python
class ParticleSystem:
    def __init__(self):
        self.atlas = load_texture("assets/sprites/particles.png")
        self.emitters = {}
        self.particles = []
        self.max_particles = 200
    
    def emit(self, emitter_name, position, **kwargs):
        config = PARTICLE_CONFIG["emitters"][emitter_name]
        for _ in range(config.get("burst_count", 1)):
            p = Particle(
                position=position,
                velocity=config["velocity"] + random_variance(),
                lifetime=random.uniform(*config["lifetime"]),
                size=random.uniform(*config["size"]),
                color=random.choice(config["colors"]),
                gravity=config.get("gravity", 0),
                atlas_frame=random.randint(*config["frame_range"]),
            )
            self.particles.append(p)
    
    def update(self, dt):
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.alive]
    
    def render(self, renderer):
        # Batch render by atlas frame for efficiency
        batches = defaultdict(list)
        for p in self.particles:
            batches[p.atlas_frame].append(p)
        for frame, particles in batches.items():
            renderer.draw_batch(self.atlas, frame, particles)
```

### 10.2 Beat-Sync Particle Trigger

```python
class BeatParticleSync:
    def __init__(self, particle_system, music_listener):
        self.ps = particle_system
        self.music = music_listener
        self.last_beat = 0
    
    def update(self, dt):
        if self.music.beat_detected and self.music.beat_phase < 0.1:
            # Downbeat detected
            self.ps.emit("music_notes", self.companion.position + (0, -50))
            
            if self.music.energy_level > 0.7:
                self.ps.emit("sparkle_magic", self.companion.position)
            
            # Speaker pulse
            self.companion.speaker.trigger_beat_pulse()
```

---

## 11. Asset Priority (MVP → Polish)

| Prioridade | Assets | Blocker? |
|------------|--------|----------|
| **P0 (MVP)** | Particle atlas (dust, smoke, sparks), UI atlas (buttons, menu), Speaker sprites | ✅ Sim |
| **P1 (Core)** | Music notes, Speaker playing/pulse, Items atlas (food, music, tech) | ✅ Sim |
| **P2 (Polish)** | Sparkle magic, speaker party mode, UI @2x, particle @2x | ⏳ Depois |
| **P3 (Nice)** | Seasonal items, animated UI transitions, custom cursors | ⏳ Muito depois |

---

## 12. Referências Visuais (Moodboard)

| Estilo | Referência | Link/Busca |
|--------|------------|------------|
| **Pixel Art Particles** | Celeste, Dead Cells, Katana Zero | "pixel art particle effects reference" |
| **Music Visualizer** | Hi-Fi Rush, Rhythm Doctor, Crypt of the NecroDancer | "rhythm game particle effects" |
| **Desktop Pet UI** | Comi Pet, Shimeji, Desktop Mate | "desktop pet ui design" |
| **Particle Systems** | Unity VFX Graph samples, Unity Particle Pack | "unity vfx graph particle examples" |
| **UI Design** | Material Design 3, Apple Human Interface, Discord UI | "modern desktop app ui design" |
| **Pixel Art Sprites** | Kenney Assets, Pixel Art Academy | "kenney nl assets", "pixel art ui kit" |

---

*Documento vivo — atualizar conforme assets são criados e testados no engine.*