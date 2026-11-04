# SeJogaDesktopCompanion — Arquitetura (Etapa 1)

**Data:** 2026-11-03  
**Versão:** 0.1  
**Baseado em:** `docs/PESQUISA.md`

---

## 1. Visão Geral

O **SeJogaDesktopCompanion** é um *desktop companion* 3D interativo do mascote **Mário** que flutua no desktop Windows 11.

**Descrição do mascote Mário:** personagem estilo Minecraft/Blockbench (low-poly) com **corpo completo** — cabeça de armário (com porta funcional), corpo, dois braços alongados ("ant-arm") com mãos e dedos, pernas e pés. Os "tentáculos" referidos originalmente são os braços alongados estilo Minecraft. O modelo é exportado do Blockbench 4.12.4 em glTF 2.0, com hierarquia de nós (sem skin): `head` (com `door`), `body`, `legs`, `right-arm`/`left-arm` (com `shoulder`/`shoulder2`, `ant-arm`/`ant-arm2`, `hand`/`hand2`, `fingers`/`fingers2`), `left-feet`/`right-feet`.

**Requisitos funcionais:**
- Modelo 3D principal (glTF/GLB, hierarquia de nós Blockbench)
- Janela transparente, sem bordas, always-on-top/abaixo (toggle)
- Click-through seletivo (atravessa onde transparente, interage no personagem)
- Física de arremesso (pymunk 2D em pixels de tela, quique nas bordas/janelas)
- Reação a música (metadados GSMTU + loopback WASAPI → onset/beat)
- Menu de configurações (bandeja + diálogo top-level) + hotkeys globais
- Persistência TOML em `%LOCALAPPDATA%`
- Distribuível como `.exe` standalone (PyInstaller + Inno Setup)

**Não-funcionais:**
- Python 3.11+ (rodando em 3.14.8 com wheels)
- 60 FPS render + 120 Hz física
- Single instance (mutex)
- Opt-in de privacidade (loopback de áudio)
- Baixo CPU/bateria em idle

---

## 2. Decisões de Stack (Registradas)

| Camada | Escolha | Justificativa |
|--------|---------|---------------|
| **Engine 3D** | Panda3D 1.10.16 + panda3d-gltf 1.3 + simplepbr 0.12 | Wheels cp314, sistema animação maduro, glTF node-based, framebuffer-alpha |
| **Janela/Overlay** | PySide6 6.x (QWindow + `Qt.FramelessWindowHint` + `WA_TranslucentBackground`) + Win32 `WS_EX_LAYERED` | Mesmo toolkit para menus/bandeja; controle nativo Win32 para layered/click-through |
| **Física** | pymunk 7.3 (Chipmunk 2D) em px de tela, 120 Hz | 2D nativo, wheels cp314, one-way shelves trivial |
| **Música (metadados)** | winrt-runtime 4.x + winrt-Windows.Media.Control 4.x | GSMTU oficial, pure py3, cp314 |
| **Música (áudio)** | soundcard 0.4 (WASAPI loopback) | API numpy, loopback simples, cp314 |
| **Beat/onset** | numpy (flux/RMS) + librosa 1.0 (beat_track a cada 2s) | Streaming barato + BPM/fase estável |
| **Menus/Bandeja** | PySide6 (QSystemTrayIcon + QDialog top-level) | Mesmo toolkit do overlay, widgets ricos, `QFileSystemWatcher` |
| **Config** | pydantic-settings 2.16 + TOML (tomli_w) + platformdirs | Validação, defaults, migrações, hot-reload |
| **Empacotamento** | PyInstaller onedir + Inno Setup (per-user) | GLB embedded, startup rápido, instalação sem UAC |

---

## 3. Mapa de Módulos (src/sejoga/)

```
sejoga/
├── __init__.py          # versão, exports públicos
├── __main__.py          # CLI: inspect, config, doctor, run
├── assets.py            # resolução de caminhos (dev vs _MEIPASS)
├── config.py            # Settings (pydantic-settings), load/save TOML
├── model.py             # Model/Node/Bounds (leitura glTF/GLB, bounds mundo)
├── rig.py               # Rig/ALL_GROUPS + presets de pose (idle/walk/dance/etc.)
├── window.py            # (etapa 2) OverlayWindow: Panda3D+PySide6 bridge, WS_EX_LAYERED
├── physics.py           # (etapa 2) ScreenSpacePhysics: pymunk + shelves EnumWindows
├── music.py             # (etapa 2) MusicListener: GSMTU + soundcard + beat tracker
├── ui.py                # (etapa 2) SettingsDialog, TrayManager, hotkeys
├── debug.py             # HUD/eixos, log rotativo e captura opcional com metadados
└── app.py               # (etapa 2) Application: loop principal 60/120 Hz
```

**Princípio:** módulos `model.py`, `rig.py`, `assets.py`, `config.py` são **engine-agnostic** (funcionam em CI sem GPU). Módulos `window.py`, `physics.py`, `music.py`, `ui.py`, `app.py` são a **etapa 2** (runtime).

---

## 4. Fluxo de Dados (Etapa 2)

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Assets     │────▶│  Model/Rig       │────▶│  OverlayWindow  │
│  (glb+png)  │     │  (bounds,rig)    │     │  (Panda3D+Qt)   │
└─────────────┘     └──────────────────┘     └────────┬────────┘
                                                     │
                    ┌────────────────────────────────┼────────────────┐
                    ▼                                ▼                ▼
            ┌───────────────┐              ┌───────────────┐  ┌──────────────┐
            │ ScreenSpace   │              │ MusicListener │  │ Settings/UI  │
            │ Physics       │              │ (GSMTU+beat)  │  │ (tray+dlg)   │
            │ (pymunk)      │              │               │  │ (PySide6)    │
            └───────┬───────┘              └───────┬───────┘  └──────┬───────┘
                    │                                │               │
                    └────────────────────────────────┼───────────────┘
                                                     ▼
                                          ┌──────────────────┐
                                          │  App Loop        │
                                          │  60 Hz render    │
                                          │  120 Hz physics  │
                                          │  async music     │
                                          └──────────────────┘
```

**Loop principal (60 Hz render / 120 Hz physics):**
```python
FIXED_DT = 1/120
acc = 0.0
while running:
    dt = clock.tick() / 1000.0
    acc += min(dt, 0.05)
    while acc >= FIXED_DT:
        physics.step(FIXED_DT)
        acc -= FIXED_DT
    music.poll()          # não-bloqueante
    window.render()       # Panda3D frame
    process_events()      # Qt events
```

---

## 5. Modelo de Dados (Model + Rig)

**Model (engine-agnostic):**
- Carrega glTF/GLB (JSON + buffer base64 ou GLB binário)
- Calcula *world bounds* aplicando TRS de cada nó
- Expõe `nodes[]`, `bounds`, `ground_offset()`, `find(name)`
- Sem skin, sem animações baked (procedural)

**Rig:**
- `ALL_GROUPS` = 16 nomes extraídos do modelo real
- `Rig.from_model(model)` valida presença
- `set_rotation(group, x,y,z, degrees=True)` → radianos internos
- Presets: `idle(t)`, `walk(t)`, `dance(t,intensity)`, `thrown()`, `wave(t)`

---

## 6. Janela Transparente + Click-through

**Panda3D + PySide6 bridge:**
- Panda3D renderiza em `GraphicsWindow` com `framebuffer-alpha=1`, `win-size` fixo
- `ConfigVariableBool('framebuffer-alpha', True)`, `win.set_clear_color_active(True)`, `win.set_clear_color(LColor(1,0,1,0))` (magenta = color key)
- PySide6 cria `QWindow`/`QWidget` wrapper ou `QWidget.createWindowContainer()` para o `HWND` do Panda3D
- Win32: `SetWindowLongPtr(hwnd, GWL_EXSTYLE, WS_EX_LAYERED|WS_EX_NOACTIVATE)` + `SetLayeredWindowAttributes(hwnd, 0xFF00FF, 0, LWA_COLORKEY)`

**Click-through seletivo:**
- `WS_EX_TRANSPARENT` global = mouse atravessa tudo
- Hit-test: bounding box do modelo em tela (projeção world→screen) ou alpha test no pixel do cursor
- Toggle dinâmico: `SetWindowLongPtr(hwnd, GWL_EXSTYLE, ex | WS_EX_TRANSPARENT)` / `ex & ~WS_EX_TRANSPARENT`

**Z-order:**
```python
# Acima de tudo
SetWindowPos(hwnd, HWND_TOPMOST, 0,0,0,0, SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE)
# Abaixo (fundo do desktop) — perde topmost, vai para fim da Z-order
SetWindowPos(hwnd, HWND_BOTTOM, 0,0,0,0, SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE)
```

---

## 7. Física de Tela (pymunk)

**Espaço:** pixels de tela, y para baixo.
- `space.gravity = (0, 2400)` quando caindo; `(0, 0)` flutuando
- Corpo: `Circle(radius=size//2)`, `elasticity=0.7`, `friction=0.5`, `damping=0.995`
- Step fixo `1/120` com acumulador.

**One-way shelves (janelas):**
```python
h = space.add_collision_handler(CAT_MASCOT, CAT_SHELF)
h.pre_solve = lambda arb, *_: setattr(arb, 'process_collision', 
    arb.shapes[0].body.velocity.y > 0) or True
```

**Arremesso (drag → release):**
```python
# drag: body.body_type = KINEMATIC; body.position = mouse_pos
# release: body.body_type = DYNAMIC; body.velocity = clamp(estimate(samples), 3200)
```

**Shelves (janelas):**
- `EnumWindows` + `DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS=9)` → retângulos reais
- Filtro: `IsWindowVisible`, não `CLOAKED`, não `WS_EX_TOOLWINDOW`, não próprio PID
- Cache 250ms só enquanto mascote se move.

---

## 8. Música (GSMTU + Loopback + Beat)

**GSMTU (metadados):**
```python
async def poll():
    mgr = await MediaManager.request_async()
    session = mgr.get_current_session()
    if session:
        props = await session.try_get_media_properties_async()
        pb = session.get_playback_info()
        emit({"title": props.title, "artist": props.artist, "playing": pb.playback_status == 4})
```
Events `MediaPropertiesChanged`/`PlaybackInfoChanged` → atualização imediata.

**Loopback (áudio):**
```python
with mic.recorder(samplerate=48000, blocksize=480) as rec:
    while running:
        block = rec.record(1024)      # (1024, ch) float32
        mono = block.mean(axis=1)     # soundcard bug: 1ch WASAPI → mono
        env.append(rms(mono))
```

**Beat tracker (a cada 2s):**
```python
def update_beat():
    if len(env) >= 4*sr/hop:  # 4s
        tempo, beats = librosa.beat.beat_track(onset_envelope=env[-4*sr//hop:], sr=sr, hop_length=hop)
        period = 60.0 / tempo
        phase = beats[-1] * hop / sr
        schedule_next_beat(period, phase)
```

**Integração:** `on_beat(period)` → `rig.pose_dance()` / trigger jump / particle.

---

## 9. Configuração + UI

**Config (TOML em `%LOCALAPPDATA%\SeJogaDesktopCompanion\config.toml`):**
```toml
schema_version = 1
[window] mode = "overlay" ; always_on_top = true ; click_through_transparent = true ; size = 480 ; scale = 1.0 ; fps = 60
[physics] enabled = true ; gravity = 2400.0 ; bounce = 0.55 ; friction = 0.88 ; throw_multiplier = 1.0 ; collide_with_windows = true
[music] enabled = true ; source = "media_session" ; react_to_beat = true ; sensitivity = 0.6
[behavior] idle_animation = true ; wander = true ; react_to_click = true
[audio] enabled = true ; master_volume = 0.8
[hotkeys] toggle_overlay = "ctrl+alt+t" ; open_settings = "ctrl+alt+s"
```

**Persistência:**
- `load_settings()` → TOML (se existe) + env `SEJOGA_` + defaults
- `save_settings()` → atomic (`tmp` → `os.replace`), `exclude_none=True`
- Hot-reload: `QFileSystemWatcher` + debounce 200ms → reload + diff + apply

**UI:**
- `QSystemTrayIcon` + `QMenu` (Config / Sair)
- `SettingsDialog(parent=None, Qt.Window|Qt.WindowStaysOnTopHint)` — top-level separado
- Hotkeys globais: `RegisterHotKey` (Win32) ou `QShortcut` com `Qt.ApplicationShortcut`

---

## 10. Empacotamento + Distribuição

**PyInstaller (onedir):**
```python
# app.spec
a = Analysis(["main.py"], datas=[("assets", "assets"), ("app.ico", ".")],
             hiddenimports=["pymunk", "panda3d", "panda3d.core"], excludes=["tkinter"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, exclude_binaries=True, name="SeJogaCompanion",
          console=False, icon="app.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="SeJogaCompanion")
```

**Assets:** converter glTF → `.glb` (um arquivo) com `tools/gltf_to_glb.py` antes do build.

**Inno Setup (per-user, sem UAC):**
```ini
[Setup] PrivilegesRequired=lowest
[Files] Source: "dist\SeJogaCompanion\*"; DestDir: "{app}"; Flags: recursesubdirs
[Registry] Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "SeJogaCompanion"; ValueData: """{app}\SeJogaCompanion.exe"""; Tasks: autostart
```

**Riscos AV:** assinatura código (EV) é o único mitigador real. `--onefile` evite (startup 2-5s + AV).

---

## 11. Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
| DPI | `SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)` antes da 1ª janela |
| Foco | `SWP_NOACTIVATE` / `Qt.WindowDoesNotAcceptFocus` em **tudo** |
| CPU | `body.sleep()` + parar audio em silêncio >2s; física só quando movendo |
| Privacidade | Loopback = opt-in explícito, sem disco, indicador UI |
| Single instance | `QSharedMemory` / mutex nomeado |
| AV false positive | Assinatura EV (único mitigador real) |
| Fullscreen game | Detectar `GetForegroundWindow` fullscreen → pausar mascote |

---

## 12. Roadmap (Próximos Passos)

O status detalhado e a ordem de prioridade ficam em [STATUS_E_PROXIMOS_PASSOS.md](STATUS_E_PROXIMOS_PASSOS.md). Resumo desta arquitetura:

| Etapa | Entregável | Status |
|-------|------------|--------|
| **1** | Pesquisa, assets organizados, scaffolding Python, testes, CLI, docs | ✅ Concluída |
| **2** | Overlay Panda3D + Win32 + bandeja | ✅ Implementado; validado no ambiente de desenvolvimento |
| **3** | Física Pymunk + detecção de janelas/prateleiras | ✅ Implementada; integração e interações ainda podem ser refinadas |
| **4** | Música (GSMTC + captura WASAPI + beat) | 🟡 Módulo integrado; validação de áudio e refinamento pendentes |
| **5** | `SettingsDialog` + hotkeys globais | ✅ Diálogo TOML e atalhos globais; tamanho/física requerem reinício |
| **6** | Loop de render/física + mouse | 🟡 Integrado em `OverlayApp`; falta consolidar/refinar |
| **7** | PyInstaller + Inno Setup + teste em máquina limpa | 🟡 Build onedir validado localmente; instalador/teste limpo pendentes |
| **8** | Animações no Blockbench + controlador de estados | 🟡 Controlador procedural básico implementado; clipes e reação musical pendentes |

---

*Próximo marco sugerido: validar o HUD de diagnóstico e as capturas em uma sessão interativa.*
