# Referência: DSH Marketplace / Awesome DSH Plugins / MCPs

**Data:** 2026-11-03  
**Fonte:** https://awesome-dsh-plugin.com/plugins.json (8626 plugins catalogados)  
**Objetivo:** Identificar plugins/MCPs úteis para desenvolvimento do SeJogaDesktopCompanion

---

## 1. Visão Geral do Ecossistema

O **Awesome DSH Plugin** é o catálogo oficial de plugins para **DeepSeek Harness (DSH)**. Não é uma "loja de assets 3D" — é um ecossistema de plugins para o **harness de coding agent** (DSH). 

**O que NÃO é:** marketplace de modelos 3D, animações, rigs, textures.  
**O que É:** plugins que estendem o DSH (coding agent) com ferramentas, UI, AGI, memory, UI, workflow, etc.

**Como instalar plugins:**
```bash
# Via DSH CLI
dsh plugin --profile web add <plugin-name>

# Ou via GitHub
dsh plugin --profile web add github:owner/repo

# Ou via npm
dsh plugin --profile web add @owner/package
```

---

## 2. Categorias Relevantes para o Projeto

| Categoria | Descrição | Plugins de Interesse |
|-----------|-----------|---------------------|
| **ui** | UI Enhancements | `dsh-status-rotator`, `dsh-spotlight`, `dsh-composer-expand`, `dsh-workspace-menu` |
| **dev** | Development & Runtime | `dsh-spotlight`, `dsh-session-tabs`, `dsh-workspace-menu` |
| **tools** | Tools & Capabilities | `dsh-prompt-polish`, `dsh-restart-button` |
| **workflow** | Workflow & Automation | `dph-taskboard`, `dsh-session-tabs` |
| **git** | Git & Code Review | plugins de git integration |
| **skill** | Skills | `dsh-prompt-polish` |
| **fun** | Just for Fun | `dsh-status-rotator` |

---

## 3. Plugins Selecionados para o Projeto

### 3.1 UI/UX - Essenciais para Companion Desktop

| Plugin | Descrição | Instalação | Por que usar |
|--------|-----------|------------|--------------|
| **dsh-float** | Windows desktop floating assistant: always-on-top chat panel com streaming answers, model switching, region-screenshot questions | `dsh plugin --profile web add dsh-float` | **Referência direta** para companion desktop flutuante no Windows |
| **dsh-float** | Windows desktop floating assistant | `dsh plugin --profile web add dsh-float` | Exemplo funcional de overlay Windows always-on-top |
| **dsh-status-rotator** | Rotates status label com 1059 frases, typewriter, rainbow gradient, danmaku | `dsh plugin --profile web add dsh-status-rotator` | Inspiração para animações de status do companion |
| **dsh-spotlight** | Command palette (cmd+k style) | `dsh plugin --profile web add github:0xsline/dsh-spotlight` | Referência para command palette do companion |
| **dsh-composer-expand** | Expand/collapse composer input (70vh) | `dsh plugin --profile web add dsh-composer-expand` | Referência para UI expansível |
| **dsh-workspace-menu** | Context menu: pin, rename, open in explorer, archive | `dsh plugin --profile web add @0imzero/dsh-workspace-menu` | Menu contextual do companion |
| **dsh-session-tabs** | Browser-style session tabs | `dsh plugin --profile web add github:1834395550/dsh-session-tabs` | Multi-session management |
| **dsh-composer-expand** | Expand/collapse composer (70vh) | `dsh plugin --profile web add dsh-composer-expand` | Input expansion |
| **dsh-plugin-ui-zoom** | Whole-interface zoom 70-160% | `dsh plugin --profile web add dsh-plugin-ui-zoom` | Zoom UI reference |
| **dsh-session-tabs** | Browser-style session tabs | `dsh plugin --profile web add github:1834395550/dsh-session-tabs` | Session management |
| **dsh-plugin-notes** | Sticky notes board | `dsh plugin --profile web add @zzerx/dsh-plugin-notes` | Notes panel |

### 3.2 Development/Workflow - Para Desenvolvimento do Projeto

| Plugin | Descrição | Instalação | Uso no Projeto |
|--------|-----------|------------|----------------|
| **dsh-spotlight** | Command palette (cmd+k) | `github:0xsline/dsh-spotlight` | Command palette do companion |
| **dsh-session-tabs** | Browser-style session tabs | `github:1834395550/dsh-session-tabs` | Multi-session |
| **dph-taskboard** | Kanban board na sidebar | `github:1070296335-create/dph-taskboard` | Task management do projeto |
| **dsh-workspace-menu** | Workspace context menu | `@0imzero/dsh-workspace-menu` | Workspace management |
| **dsh-prompt-polish** | Prompt optimizer | `github:1321928757/dsh-prompt-polish` | Prompt engineering |
| **dsh-restart-button** | Restart button no UI | `github:13520rygvv/dsh-restart-button` | Restart UI |
| **dsh-composer-expand** | Expand composer input | `dsh-composer-expand` | Input expansion |

### 3.3 AGI/Agent - Para Comportamento Inteligente do Companion

| Plugin | Descrição | Instalação | Uso no Companion |
|--------|-----------|------------|------------------|
| **clearai-dsh** | Evidence-checked research agent | `clearai-dsh` | Research agent para companion |
| **dsh-memory** | White-box AGI: metacognition, continual learning, world model | `@furongjun1999/dsh-memory` | **Memory system do companion** |
| **dsh-moa-native** | Mixture-of-Agents nativo | `dsh-moa-native` | Multi-agent reasoning |
| **dsh-advisor-flow** | Executor/advisor workflow | `github:ccll/dsh-advisor-flow` | Advisor pattern |
| **dsh-force-collab** | Forced collaboration entre sub-agents | `dsh-force-collab` | Multi-agent collaboration |
| **dsh-moa-native** | Native MoA generation | `dsh-moa-native` | MoA pattern |
| **dsh-ATN** | Adaptive topology multi-agent | `dsh-atn` | Multi-agent topology |

### 3.4 Memory/Persistence - Para Persistência do Companion

| Plugin | Descrição | Instalação | Uso |
|--------|-----------|------------|-----|
| **dsh-memory** | White-box AGI: metacognition, continual learning, world model, self-improvement | `@furongjun1999/dsh-memory` | **Memory system principal** |
| **dsh-memory-brain-plugin** | 3D neural memory map panel | `github:1DAdidi/dsh-memory-brain-plugin` | **Visual memory map** |

### 3.5 UI/Theme - Para Visual do Companion

| Plugin | Descrição | Instalação | Uso |
|--------|-----------|------------|-----|
| **dsh-status-rotator** | Status rotator com 1059 frases, typewriter, rainbow gradient | `dsh-status-rotator` | Status animations |
| **dsh-plugin-ui-zoom** | Whole-interface zoom 70-160% | `dsh-plugin-ui-zoom` | Zoom UI |
| **dsh-plugin-ui-zoom** | Zoom 70-160% | `dsh-plugin-ui-zoom` | Zoom |
| **dsh-plugin-rightbar-divider** | Fix sidebar divider drag | `dsh-plugin-rightbar-divider` | Sidebar divider |
| **dsh-plugin-ui-zoom** | Zoom 70-160% | `dsh-plugin-ui-zoom` | Zoom |
| **dsh-zh-ui** | Chinese UI design spec | `github:1186258278/dsh-zh-ui` | UI design spec |
| **dsh-restart-foot** | Restart button at sidebar foot | `github:1207291706/dsh-restart-foot` | Restart button |
| **dsh-restart-button** | Restart from 3 places | `github:13520rygvv/dsh-restart-button` | Restart |

---

## 4. Plugins Recomendados para Instalação Imediata

```bash
# Core UI/UX para companion desktop
dsh plugin --profile web add dsh-float
dsh plugin --profile web add dsh-status-rotator
dsh plugin --profile web add dsh-spotlight
dsh plugin --profile web add dsh-composer-expand
dsh plugin --profile web add dsh-workspace-menu
dsh plugin --profile web add dsh-session-tabs
dsh plugin --profile web add dsh-composer-expand
dsh plugin --profile web add dsh-plugin-ui-zoom
dsh plugin --profile web add dsh-plugin-rightbar-divider

# Development workflow
dsh plugin --profile web add dph-taskboard
dsh plugin --profile web add dsh-session-tabs
dsh plugin --profile web add dsh-workspace-menu
dsh plugin --profile web add dsh-spotlight
dsh plugin --profile web add dsh-prompt-polish
dsh plugin --profile web add dsh-restart-button

# AGI/Memory para companion inteligente
dsh plugin --profile web add clearai-dsh
dsh plugin --profile web add @furongjun1999/dsh-memory
dsh plugin --profile web add github:1DAdidi/dsh-memory-brain-plugin

# Themes & Appearance
dsh plugin --profile web add dsh-status-rotator
dsh plugin --profile web add dsh-plugin-ui-zoom
dsh plugin --profile web add dsh-plugin-rightbar-divider

# Restart management
dsh plugin --profile web add dsh-restart-foot
dsh plugin --profile web add dsh-restart-button

# Prompt engineering
dsh plugin --profile web add dsh-prompt-polish
```

---

## 5. MCPs (Model Context Protocol) Relevantes

O catálogo DSH não lista MCPs diretamente, mas estes são relevantes para o projeto:

| MCP | Descrição | Uso no Projeto |
|-----|-----------|----------------|
| **filesystem** | File system access | Asset loading, config persistence |
| **github** | GitHub integration | Version control, issues |
| **sqlite** | Local database | Companion memory/state |
| **fetch** | HTTP requests | Web APIs, music metadata |
| **puppeteer/playwright** | Browser automation | Web scraping, testing |
| **terminal** | Shell commands | Build, deploy, debug |

---

## 6. Referências de Assets 3D (Fora do DSH Marketplace)

Como o DSH Marketplace **não** tem assets 3D, use estas fontes:

| Fonte | Licença | Tipo | URL |
|-------|---------|------|-----|
| **Poly Haven** | CC0 | Models, HDRIs, Textures | https://polyhaven.com/models |
| **Kenney Assets** | CC0 | Low-poly models, UI, Audio | https://kenney.nl/assets |
| **Sketchfab** | Variada (ver por item) | Models, glTF | https://sketchfab.com |
| **Mixamo** | Adobe (uso em projeto, não redistribuição) | Animations, Rigs | https://www.mixamo.com |
| **Poly Haven** | CC0 | Models, HDRIs | https://polyhaven.com |
| **Quaternius** | CC0 | Low-poly characters | https://quaternius.com |
| **Kenney** | CC0 | Low-poly kits | https://kenney.nl/assets |
| **Poly Haven** | CC0 | Models | https://polyhaven.com/models |
| **Blockbench Plugins** | Grátis | Plugins para Blockbench | https://www.blockbench.net/plugins |

---

## 7. Referências de Animação (Jogos Inspiradores)

| Jogo | Engine | Estilo | Referência de Animação |
|------|--------|--------|------------------------|
| **Bomb Rush Cyberfunk** | Unity | Cel-shaded, Jet Set Radio style | Grind, ollie, wallride, boostpack, graffiti spray, dance |
| **Lethal League Blaze** | Unity | Cel-shaded, fighting 2D/3D | Swing, hit impact, knockback, dodge, taunt |
| **Hi-Fi Rush** | Unreal Engine 4 | Rhythm-action, beat-sync | Beat-sync walk/run, attack on beat, parry, rhythm minigames |
| **Persona 5** | Custom (Atlus) | Anime stylized, "stylish" | Persona summon, all-out attack, baton pass, UI transitions |

---

## 8. Próximos Passos

1. **Instalar plugins essenciais** (seção 4)
2. **Explorar plugins instalados** para entender padrões de UI/UX
3. **Adaptar padrões DSH** para o companion Python standalone
4. **Criar documentação de animação** baseada nos jogos de referência
5. **Definir state machine de animação** do Mário

---

*Documento gerado em 2026-11-03. Fonte: https://awesome-dsh-plugin.com/plugins.json (8626 plugins).*