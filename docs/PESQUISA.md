# SeJogaDesktopCompanion — Pesquisa Técnica (Etapa 1)

**Data:** 2026-11-03  
**Versão:** 0.1 (rascunho)  
**Autor:** ArchVeketo

---

## Resumo Executivo

Este documento consolida a pesquisa técnica para construir o **SeJogaDesktopCompanion**: um *desktop companion* 3D interativo do mascote **Mário** em Python no Windows 11.

**Descrição do mascote Mário:** personagem estilo Minecraft/Blockbench (low-poly) com **corpo completo** — cabeça de armário (com porta funcional), corpo, dois braços alongados ("ant-arm") com mãos e dedos, pernas e pés. Os "tentáculos" referidos originalmente são os braços alongados estilo Minecraft. O modelo é exportado do Blockbench 4.12.4 em glTF 2.0, com hierarquia de nós (sem skin): `head` (com `door`), `body`, `legs`, `right-arm`/`left-arm` (com `shoulder`/`shoulder2`, `ant-arm`/`ant-arm2`, `hand`/`hand2`, `fingers`/`fingers2`), `left-feet`/`right-feet`.

**Conclusão principal:** Não existe atalho de marketplace. O caminho viável é:
1. **Modelagem/Animação** → Blockbench 5.x → exportar `.glb` (hierarquia de nós, sem skin)
2. **Engine 3D em Python** → Panda3D 1.10.x + panda3d-gltf (wheels cp314) ou raylib 6.x
3. **Janela transparente Windows** → `WS_EX_LAYERED` + `SetLayeredWindowAttributes` (color key) ou DWM blur-behind + per-pixel alpha
3. **Click-through seletivo** → `WS_EX_TRANSPARENT` + hit-test manual por alpha/bounding box
4. **Física** → pymunk 2D em pixels de tela (one-way shelves = janelas)
5. **Música** → winrt-Windows.Media.Control (metadados) + soundcard (WASAPI loopback) + numpy (onset/beat)
6. **Menus/Config** → PySide6 (QSystemTrayIcon + QDialog top-level) + pydantic-settings + TOML
7. **Empacotamento** → PyInstaller onedir + Inno Setup (user-level)

---

## 1. Marketplace DeepSeek — Veredito

> **Não existe "DeepSeek Marketplace / Store / 应用商店" de assets 3D, animações ou plugins para desktop companion.** Nenhuma fonte primária confirmou isso.

O que **existe** são três coisas distintas, nenhuma delas uma loja de assets:

| Item | O que é | Relevância para assets 3D |
|------|---------|---------------------------|
| **Plataforma de API DeepSeek** | LLM/API only | Zero |
| **Plugin Market do DSH** (dshmarket) | Marketplace de *plugins do agente* (temas, integrações, ferramentas) | Não contém modelos 3D/rigs |
| **AWS Marketplace "deepseek-marketplace"** | Licenciamento de modelos de IA na AWS | Não assets 3D |

⚠️ **Segurança:** Pacotes npm com nomes que imitam "DeepSeek marketplace" (ex.: `dshmarketplace-plugin`) já apareceram. Instalar plugin = executar código de terceiros com acesso ao perfil/credenciais do harness. **Não instalar por semelhança de nome.**

**Valor estratégico real:** existe um *canal de distribuição* (o Comi Pet tem `adapters/dsh`). Canal ≠ fonte de assets.

---

## 2. Fontes Reais de Assets 3D

| Categoria | Fontes (licença) |
|-----------|------------------|
| CC0 / low-poly | [polyhaven.com/models](https://polyhaven.com/models) · [kenney.nl/assets](https://kenney.nl/assets) · [quaternius.com](https://quaternius.com) · [kaylousberg.itch.io](https://kaylousberg.itch.io) |
| Modelos gerais (licença varia) | [sketchfab.com](https://sketchfab.com) — [guia download glTF](https://help.sketchfab.com/en/articles/16152217-downloading-3d-models) |
| Animações humanoides | [mixamo.com](https://www.mixamo.com) (Adobe: permite uso no projeto, **não** redistribuir clipes crus) |
| Plugins Blockbench | [blockbench.net/plugins](https://www.blockbench.net/plugins) |
| MCP servers (ferramentas) | [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) · [smithery.ai](https://smithery.ai) · [mcp.so](https://mcp.so) |

**Mozilla Hubs:** DESCONTINUADO (fim do suporte 2024) — não usar como referência.

---

## 3. Projetos de Referência (Arquitetura)

### Desktop Mate (Unity) — [Steam 3301060](https://store.steampowered.com/app/3301060/)
- **Stack:** Unity + IL2CPP. Personagens = VRM em asset bundles (criptografados).
- **Política oficial:** **NÃO suporta VRM do usuário nem mods** (licenciamento IP + qualidade).
- **Mods da comunidade** quebram a cada update (MelonLoader + .VRM).
- **Lição:** O moat é licenciamento de IP, não tecnologia. Copiar UX: janela transparente always-on-top, "sentado" nas bordas de janelas, head-pat, pipeline de conteúdo licenciado.

### Shimeji (Java) — Melhor referência de *state machine*
- **Canônico:** [a1098832322/shimeji](https://github.com/a1098832322/shimeji) (Java, GPL-3.0, ativo) + [pixelomer/Shijima-Qt](https://github.com/pixelomer/Shijima-Qt) (C++/Qt6, arquivado — arquitetura mais limpa)
- **O que copiar:** Behaviors em XML (ações/poses/condições) + sprites PNG → FSM `falling / walk / grab / throw`. *Behavior-driven* directly portable to 3D.

### Comi Pet — Melhor blueprint Windows/Python (2D sprites)
- [IvenKooLab/desktop-pet](https://github.com/IvenKooLab/desktop-pet) (MIT, ~234★, Windows+macOS, ~60fps)
- **Atenção:** README diz "3D 绒质" mas é **arte 3D em sprites 2D** (frames: hop 8, blink 6), tkinter, **sem glTF/OpenGL**.
- **Blueprint Windows/Python:** janela transparente, drag, física arremesso com quique, **andar nas bordas superiores das janelas**, config em `~/.comi-pet/config.json`, **IPC por arquivos locais**, adapter DSH.

### Waifu / VTube Studio
- [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) (Live2D + LLM + voz, ~14.5k★)
- [VTubeStudio API](https://github.com/DenchiSoft/VTubeStudio) (WebSocket `ws://localhost:8001`, tokens, hotkeys, expressions, UDP discovery 47779)
- Libs Python: [pyvts](https://github.com/Genteki/pyvts) · [coovts](https://github.com/lgc2333/coovts)
- **Uso estratégico:** companion 3D = *cérebro* que dispara hotkeys/itens no VTS.

---

## 4. Pipeline de Animação Blockbench → glTF

**Fatos verificados:**
- Blockbench 5.x: aba **Animate** → timeline por **bone = group**. Pivot = tecla **P**. Root bone obrigatório, nomes `snake_case`.
- **Rig blocky não deforma:** cada cubo = filho rígido de bone → animação = transform de **nó (TRS)**, sem skin/blending. Exatamente o desejado.
- Export: **File > Export > glTF** → suporta animações (bedrock/generic/geckolib). Texturas embedded.
- **Não passar pelo Blender:** glTF "não otimizado para edição posterior" (quads→tris, vértices não compartilhados). Round-trip renomeia/reordena tracks e quebra lookup por nome.
- Se precisar Blender: **não** usar automatic weights. Use (a) bone parenting / parent-to-bone, ou (b) peso **1.0 rígido** por cubo (1 bone por cubo). Export com "Animation > Sampling".
- Clipes a autorar: `idle` (loop 2–4s), `walk` (loop, 1º keyframe == último), `throw`, `hit`, `dance`. Nomes exatos; loop vs one-shot por convenção.

**glTF para engine:**
- Distribuir **`.glb`** (textura embutida); `.gltf`+.bin+.png só em dev.
- Texturas pequenas POT (16/32/64px), `magFilter = NEAREST` pixel-perfect. 1 atlas + 1 material.
- Se possível **não usar skinning** (hierarquia de nós). Se usar, 1 influência por vértice.
- Interpolação **STEP** combina com blocky; LINEAR para idle suave.
- Validar: [glTF-Validator](https://github.com/KhronosGroup/glTF-Validator) · Otimizar: [glTF-Transform](https://github.com/donmccurdy/glTF-Transform) · [gltfpack](https://meshoptimizer.org/)
- Guidelines Khronos: [Asset Creation 2.0](https://www.khronos.org/blog/introducing-asset-creation-guidelines-2.0-siggraph-2025) · [3DC-Asset-Creation](https://github.com/KhronosGroup/3DC-Asset-Creation) · [spec](https://github.com/KhronosGroup/glTF)

---

## 5. Stack de Engine 3D em Python (Windows 11)

| Critério | Panda3D 1.10.x | raylib 6.x | Ursina (Panda3D wrapper) | pyglet + moderngl |
|----------|---------------|------------|--------------------------|-------------------|
| Wheels cp314 | ✅ 1.10.16 | ✅ 6.2.0 | ✅ (via Panda3D) | ✅ py3 |
| glTF + animações | ✅ panda3d-gltf 1.3 | ✅ LoadModel/LoadModelAnimations | ✅ (herda) | manual (pygltflib) |
| Sistema animação | ✅ Actor/AnimControl/blending | básico (UpdateModelAnimation) | ✅ | manual |
| Janela transparente | framebuffer-alpha + DWM blur | `FLAG_WINDOW_TRANSPARENT` | herda Panda3D | controle total (Win32) |
| Física | Bullet built-in | Raylib physics (simples) | herda Bullet | pymunk (2D) |
| Curva aprendizado | média | baixa | baixa | alta |
| **Veredito** | **Recomendado** | alternativa | não testado | máximo controle |

**Escolha recomendada: Panda3D 1.10.16 + panda3d-gltf + panda3d-simplepbr**
- Roda nativo em Python 3.14 (wheels oficiais)
- Sistema de animação maduro (Actor, blend, intervals)
- glTF com hierarquia de nós (o rig do Blockbench é node-based)
- Física Bullet built-in (embora usemos pymunk 2D para tela)
- `ConfigVariableBool('framebuffer-alpha', True)` + DWM blur-behind para per-pixel alpha

---

## 6. Janela Transparente + Click-through (Windows 11)

### Per-pixel alpha
Duas abordagens consolidadas:

| Método | Como funciona | Trade-off |
|--------|---------------|-----------|
| **Color key (LWA_COLORKEY)** | Clear para cor mágica (ex.: magenta) + `SetLayeredWindowAttributes(hwnd, RGB(255,0,255), 0, LWA_COLORKEY)` | Simples, funciona com OpenGL; cor mágica não pode aparecer no modelo |
| **Per-pixel alpha (LWA_ALPHA + DWM)** | `WS_EX_LAYERED` + framebuffer com alpha + `DwmEnableBlurBehindWindow` + `DWM_BB_ENABLE` | Alpha real; exige DWM composition ativo; mais complexo |

**Recomendação:** Color key (magenta 0xFF00FF) + clear color magenta no render. O modelo não usa magenta. Simples, robusto, testado em apps desktop companion.

### Click-through seletivo
- `WS_EX_TRANSPARENT` faz o mouse atravessar **toda** a janela.
- Para clicar *no* personagem: hit-test manual por alpha/bounding box + toggle `WS_EX_TRANSPARENT` dinâmico.
- Alternativa: `WM_NCHITTEST` → `HTTRANSPARENT` onde alpha=0, `HTCLIENT` onde personagem está. Exige WndProc customizado (pywin32/ctypes).
- **Padrão Comi Pet:** janela topmost sem click-through global; hit-test por bounding box do sprite; click-through só em áreas vazias (se necessário).

**Z-order (acima/abaixo):**
```python
user32.SetWindowPos(hwnd, HWND_TOPMOST, 0,0,0,0, SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE)
# "abaixo" = HWND_BOTTOM (perde topmost, vai para fim da ordem Z)
```
- `SWP_NOACTIVATE` **obrigatório** (não roubar foco).
- Qt: `Qt.WindowStaysOnTopHint` + `Qt.WindowDoesNotAcceptFocus` (≈ `WS_EX_NOACTIVATE`).

---

## 7. Física de Arremesso (pymunk 2D)

**Modelo:** espaço 2D em **pixels de tela** (y para baixo), passo fixo 1/120s.
- Corpo = `pymunk.Circle` (raio ≈ metade do sprite). `elasticity ≈ 0.7`, `friction ≈ 0.5`.
- Gravidade 0 no modo "flutuando"; gravidade > 0 só quando cair/quicar.
- **One-way shelves (o segredo):** só a aresta superior de cada janela é sólida, só quando descendo:
```python
h = space.add_collision_handler(CAT_MASCOT, CAT_SHELF)
h.pre_solve = lambda arb, *_: setattr(arb, 'process_collision', arb.shapes[0].body.velocity.y > 0) or True
```
- **Arremesso:** durante drag → `KINEMATIC`; no release → `DYNAMIC` + `velocity = clamp(estimate_velocity(samples), 3200)`.
- **Refresh janelas:** `EnumWindows` + `DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS=9)` (borda real, sem a borda invisível de 7–8px do `GetWindowRect`). Cache 250–400ms só enquanto mascote se move.
- DPI: `SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)` **antes** de criar janela.

---

## 8. Interação com Música

### (a) Metadados — GSMTU (Global System Media Transport Controls)
```python
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager

async def now_playing():
    mgr = await MediaManager.request_async()
    session = mgr.get_current_session()
    if not session: return None
    props = await session.try_get_media_properties_async()
    pb = session.get_playback_info()
    return {"title": props.title, "artist": props.artist, "status": pb.playback_status}
```
- Pacotes: `winrt-runtime` + `winrt-Windows.Media.Control` (pure Python `py3-none-any`, rodam em 3.14). `winsdk` é legado (parado em 2023).
- Events: `MediaPropertiesChanged`, `PlaybackInfoChanged` → atualiza título/artista/pausa em tempo real.

### (b) Áudio — WASAPI Loopback (soundcard / pyaudiowpatch)
```python
import soundcard as sc
speaker = sc.default_speaker()
mic = sc.get_microphone(str(speaker.name), include_loopback=True)
with mic.recorder(samplerate=48000, blocksize=480) as rec:
    while True:
        block = rec.record(numframes=1024)    # (1024, ch) float32
        mono = block.mean(axis=1)             # soundcard bug: 1 canal no WASAPI → mono com mean
```
- `pyaudiowpatch` duplica devices WASAPI como entrada loopback (callback PortAudio + queue).
- **Privacidade:** opt-in explícito, sem gravação em disco, indicador visual.

### Ritmo (beat/onset) em tempo real
| Abordagem | Latência | Custo/hop | Veredito |
|-----------|----------|-----------|----------|
| RMS / FFT (numpy) | 20–40ms | <0.5ms | **Sempre** (respiração, quique no grave) |
| Flux espectral + limiar adaptativo | 40–80ms | ~0.3ms | **Onset barato** |
| `librosa.beat.beat_track` (janela 4s) | 1–2s (offline) | 10–40ms/chamada | **BPM/fase a cada 2s** |
| `aubio.tempo` (C, streaming) | ~1 hop | ~0.1ms | Ideal **se wheel cp314** (sdist) |
| Essentia | não streaming | alto | Offline |

**Pipeline recomendado:** hop 1024@48kHz (21ms) → `onset_strength`/flux → limiar = mediana(últimos 43 hops)×1.5 → "beat" quando passa. A cada 2s: `beat_track(onset_envelope=env_4s, sr=48000, hop_length=1024)` → extrapole fase+período (PLL simples) → agende pulo/animação.

---

## 9. Menus / Bandeja / Configuração

| Opção | Prós | Contras |
|-------|------|---------|
| **PySide6 QSystemTrayIcon** | Mesmo toolkit do 3D; QMenu com checkable/ícones; `showMessage` | Puxa Qt inteiro (já tem se usar Panda3D? não — Panda3D não usa Qt) |
| **pystray** | Mínimo, Win32 nativo, `run_detached()` integra com loop | PopupMenu Win32 (sem estilo), sem widgets ricos |
| **Menu na janela** | Visual integrado | Hit-test difícil em janela pequena/transparente; quebra com click-through |

**Recomendação:** `QSystemTrayIcon` + `QMenu` para bandeja; config em `QDialog` **top-level separado** (`parent=None`, `Qt.Window`, `Qt.WindowStaysOnTopHint` se mascote topmost). **Nunca** filho da janela do mascote (seria recortado).

```python
tray = QSystemTrayIcon(QIcon(str(ASSETS / "tray.ico")))
menu = QMenu()
menu.addAction("Configurações…", open_settings)
menu.addAction("Sair", app.quit)
tray.setContextMenu(menu); tray.show()

def open_settings():
    dlg = SettingsDialog(None)  # parent None = HWND própria
    dlg.setWindowFlag(Qt.Window, True)
    if config.always_on_top: dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dlg.setAttribute(Qt.WA_DeleteOnClose, True)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
```

**Click-through no Qt:** `Qt.WA_TransparentForMouseEvents` é hit-test interno. Win32 real:
```python
GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT = -20, 0x80000, 0x20
def set_click_through(w, on):
    hwnd = int(w.winId())
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ex = (ex | WS_EX_LAYERED | WS_EX_TRANSPARENT) if on else (ex & ~WS_EX_TRANSPARENT)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
```

**Configuração:** `pydantic-settings` + TOML em `%LOCALAPPDATA%\SeJogaDesktopCompanion\config.toml`, escrita atômica (`tmp` → `os.replace`), `schema_version` + migrações, hot-reload com `QFileSystemWatcher` (debounce 200ms). Defaults no código → app nunca falha por config inválido.

---

## 10. Empacotamento Windows

**PyInstaller onedir** (não `--onefile` — evita descompactar a cada run):
```python
# paths.py
def asset(*p):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath("assets", *p)
```

```python
# app.spec
a = Analysis(["main.py"],
             datas=[("assets", "assets"), ("app.ico", ".")],
             hiddenimports=["pymunk"], excludes=["tkinter"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, exclude_binaries=True, name="SeJogaCompanion",
          console=False, icon="app.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="SeJogaCompanion")
```
- **`.glb` obrigatório** (um arquivo só, evita "carrega no dev, não no exe").
- Nuitka só se startup justificar (build lento, risco AV maior).
- Inno Setup (per-user, sem UAC):
```ini
[Setup] PrivilegesRequired=lowest
[Files] Source: "dist\SeJogaCompanion\*"; DestDir: "{app}"; Flags: recursesubdirs
[Registry] Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "SeJogaCompanion"; ValueData: """{app}\SeJogaCompanion.exe"""; Tasks: autostart
```
- **Falsos positivos AV:** assinatura de código (EV) é o único mitigador real.
- Ícone `.ico` multi-res (16/24/32/48) em `datas` **e** `icon=` do EXE.

---

## 11. Autostart + Z-order

**Autostart:** `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` via `winreg` (stdlib). Valor = linha comando entre aspas.
```python
def set_autostart(exe, on, name="SeJogaCompanion"):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN, 0, winreg.KEY_SET_VALUE) as k:
        if on: winreg.SetValueEx(k, name, 0, winreg.REG_SZ, f'"{exe}"')
        else:
            try: winreg.DeleteValue(k, name)
            except FileNotFoundError: pass
```

**Z-order:** não existe chave de registro. É runtime:
```python
HWND_TOPMOST, HWND_BOTTOM = -1, 1
SWP_NOSIZE|SWP_NOMOVE|SWP_NOACTIVATE = 0x1|0x2|0x10
user32.SetWindowPos(hwnd, HWND_TOPMOST, 0,0,0,0, SWP_NOSIZE|SWP_NOMOVE|SWP_NOACTIVATE)
```
- `HWND_TOPMOST` = acima de tudo; `HWND_BOTTOM` = perde topmost; `HWND_NOTOPMOST` = acima dos normais, atrás dos topmost.
- `SWP_NOACTIVATE` **obrigatório** (não roubar foco).

---

## 12. Checklist de Riscos Transversais

| Risco | Mitigação |
|-------|-----------|
| **DPI** | `SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)` **antes** da 1ª janela |
| **Foco** | Nunca `SetForegroundWindow`/`show()` sem `NOACTIVATE`/`Qt.WindowDoesNotAcceptFocus` |
| **CPU/Bateria** | 60fps + física 120Hz + enumeração periódica → `body.sleep()` + parar áudio em silêncio >2s |
| **Privacidade** | Loopback = microfone sistema → opt-in, sem disco, indicador visual |
| **Single instance** | Dois mascotes = duas físicas/autostarts → mutex nomeado / `QSharedMemory` |
| **Falsos positivos AV** | Assinatura de código (EV) é o único mitigador real |
| **Fullscreen exclusivo** | Ignora topmost (mascote "some") — detectar e pausar |

---

## URLs Citadas (Referência Rápida)

- **Pymunk:** https://www.pymunk.org/ · API: https://www.pymunk.org/en/latest/pymunk.html · tunneling: https://www.pymunk.org/en/latest/overview.html#object-tunneling
- **DWM attributes:** https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute
- **pywin32 EnumWindows:** https://timgolden.me.uk/pywin32-docs/win32gui__EnumWindows_meth.html
- **WindowFromPoint:** https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-windowfrompoint
- **SetWindowPos:** https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos
- **GSMTU SessionManager:** https://learn.microsoft.com/en-us/uwp/api/windows.media.control.globalsystemmediatransportcontrolssessionmanager
- **winrt-Windows.Media.Control:** https://pypi.org/project/winrt-Windows.Media.Control/
- **SoundCard:** https://soundcard.readthedocs.io/ · PyAudioWPatch: https://pypi.org/project/PyAudioWPatch/
- **librosa beat_track:** https://librosa.org/doc/latest/api/generated/librosa.beat.beat_track.html · aubio: https://aubio.readthedocs.io/
- **pystray:** https://pystray.readthedocs.io/ · PySide6 QSystemTrayIcon: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html
- **pydantic-settings:** https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/
- **PyInstaller spec/runtime:** https://pyinstaller.org/en/stable/spec-files.html · https://pyinstaller.org/en/stable/runtime-information.html
- **Nuitka AV:** https://nuitka.net/user-documentation/common-issue-solutions.html
- **Inno Setup:** https://jrsoftware.org/isinfo.php

---

*Fim do documento de pesquisa. Próximo passo: `docs/ARQUITETURA.md` com decisões finais e mapa de módulos.*