# Backlog de Conteúdo — SeJogaDesktopCompanion

**Data:** 2026-11-05
**Objetivo:** Fonte de verdade para animações, props, efeitos e sistemas futuros do mascote Mário. Cada item é descrito no formato que o motor novo consome (animação como dados + camadas aditivas), e separa o que é **código procedural** do que é **pipeline de arte** (modelos low poly novos).

**Estilo visual transversal:** low poly + street, alternando com pixelado em efeitos/UI. Os três estilos se intercalam conforme o contexto.

> Convenção de prioridade: P0 = próximo, P1 = curto prazo, P2 = médio, P3 = visão futura.
> Convenção de esforço: código (procedural, cabe no motor atual) / arte (precisa de geometria ou sprite novo) / misto.

---

## 1. Animações (procedurais, como dados)

Entram como clipes/estados no motor novo (`clipes_animacao.py` para clipes cíclicos como dados; `esqueleto.py`/camadas para gestos). Gatilho = o que dispara. Juntas = grupos do rig que a animação controla.

| # | Animação | Gatilho | Loop? | Juntas principais | Intenção / notas | Prioridade | Tipo |
|---|----------|---------|-------|-------------------|------------------|------------|------|
| A1 | **Comemorar** | evento (inscrição, conquista, manual) | não (~2s) | braços, cabeça, corpo, porta | Explosão de energia: antecipação curta, braços pra cima, porta abre, assenta. Combina com efeito de notas/partículas. | P1 | código |
| A2 | **Dormir sentado** | idle longo (variação de SLEEP) | sim | corpo, pernas, cabeça, porta | Sentado, cabeça pende, respiração lenta. Variante da pose SLEEP atual. | P2 | código |
| A3 | **Dormir em pé** | idle longo (variação) | sim | corpo, cabeça, braços | Cochilo em pé, balanço mínimo, porta fecha. Já perto do SLEEP atual. | P2 | código |
| A4 | **Dormir deitado no chão** | idle muito longo / manual | sim | corpo inteiro, pernas, braços | Deita no desktop, respiração ampla. Precisa interagir com a física de "chão" (physics.py). | P2 | misto |
| A5 | **Reação a cutucada por parte do corpo** | duplo clique em parte específica (head/arm/body/legs/feet) | não (~0.4–1s) | localizada na parte cutucada | Já existe `double_click` genérico + picking de parte (grab_part). Expandir para reação DIFERENTE por parte (cabeça = treme porta; braço = recolhe; pernas = pula). | P1 | código |
| A6 | **Cuspir/espirrar objeto do armário** | evento / manual | não (~1.5s) | porta, cabeça, corpo | Evolui o `pose_sneeze` + `animacao_saida.py`. Porta abre forte e um PROP sai cuspido (ver A-prop). Depende de prop spawnável. | P2 | misto |
| A7 | **Loading com a logo** | app iniciando / operação longa | sim | — (tela/overlay, não o rig) | Animação de carregamento usando a logo (assets/brand). Pode ser overlay 2D pixelado, não o mascote. | P1 | arte+código |
| A8 | **Puxar objeto para dentro do armário** | evento / manual | não (~1.5s) | porta, cabeça, tentáculos | Inverso do A6: tentáculo sai, agarra prop, puxa pra dentro, porta fecha. Reusa `tentacle_system.py`. | P2 | misto |

**Observações de implementação:**
- A1, A2, A3, A5 são puramente procedurais — cabem no motor atual como clipes de dados + camadas. São os melhores candidatos para os primeiros workflows de conteúdo.
- A6, A8 dependem de props spawnáveis e de coreografar porta + tentáculo + prop. Fazer depois que o sistema de props existir.
- A7 é overlay, não rig — pipeline separado (render 2D sobre a janela).

---

## 2. Props (arte low poly/street + lógica de "segurar/spawnar")

Cada prop = **geometria nova** (pipeline de arte: Blockbench, que casa com o `.bbmodel`, ou Blender para modelagem) + **lógica de anexação** ao rig (segurado por uma junta) + opcionalmente física.

| # | Prop | Como aparece | Anexado a | Interação | Prioridade | Tipo |
|---|------|--------------|-----------|-----------|------------|------|
| P1a | **Lata de spray** | pego/cuspido | mão (`hand`/`hand2`) | Grafitar (combina com `speaker_graffiti` já em assets/textures) | P2 | arte+código |
| P1b | **Placa** | puxada do armário | mão | Mostrar texto configurável (like, inscrever, sininho — ver sistema REC) | P1 | arte+código |
| P1c | **Guitarra** | pega | duas mãos + corpo | Tocar junto com dança/música | P2 | arte+código |
| P1d | **Microfone** | pego | mão | Cantar/apresentar (modo REC) | P2 | arte+código |
| P1e | **MP3 player na cintura** | **já faz parte do mascote** (na cintura); pode ser destacado e segurado | cintura → mão | **Interface de player pixelada**: ao pegar, abre UI de player (play/pause/faixa) estilo pixel art. Conecta com `music.py`/`music_speaker.py`. | P1 | arte+código+UI |

**Observações:**
- Todos no estilo low poly + street. O MP3 player (P1e) é o mais rico: é prop + UI pixelada + integração com o sistema de música que já existe.
- A **lógica de segurar prop** (anexar geometria a uma junta e acompanhar a pose) é um sistema reutilizável a construir uma vez; depois cada prop novo é só geometria + config.
- A geometria nova é o ponto onde Blockbench/Blender (e, se quisermos, um MCP de arte) entram — como pipeline de ASSET, separado do motor de animação.

---

## 3. Efeitos (partículas/overlay, muitos com base existente)

Já existem `speaker_effects.py`, `sound_effects.py`, `tentacle_drips.py` (gosma) para reaproveitar.

| # | Efeito | Gatilho | Base existente | Estilo | Prioridade | Tipo |
|---|--------|---------|----------------|--------|------------|------|
| E1 | **Notas musicais pixeladas** | dança / música tocando | — (novo, overlay 2D) | pixelado | P1 | código+arte |
| E2 | **Ondas sonoras** (caixa de som / devices de música) | música / speaker ativo | `speaker_effects.py` | pixelado/low poly | P1 | código |
| E3 | **Poeira de aterrissagem** | land (queda → chão) | `sound_effects.py`? / novo | low poly/pixel | P1 | código |
| E4 | **Poeira de deslize** | arraste rápido no chão | novo | pixel | P2 | código |
| E5 | **Poeira de queda** | durante FALL | novo | pixel | P2 | código |
| E6 | **Zzz no sono** | SLEEP / dormir | novo (overlay) | pixelado | P1 | código+arte |
| E7 | **Gosma rosa pixelada** | tentáculo / cuspir / transições | `tentacle_drips.py` (gosma já existe) | pixelado | P1 | código |

**Observações:**
- E2 e E7 têm base de código existente — menor esforço.
- E1, E3, E6 são overlays de partícula relativamente simples e de alto impacto visual. Bons candidatos iniciais.
- Vale construir **um sistema de partículas/overlay reutilizável** uma vez (spawn, vida, sprite pixelado, física leve) e cada efeito vira uma config.

---

## 4. Sistema de menu "dentro do armário" (visão futura — P3)

**Conceito:** clicar algumas vezes na cabeça do Mário puxa a câmera "para dentro" do armário da cabeça. Lá dentro há mini-ambientes temáticos, cada um mapeando uma área de configuração, com o próprio Mário encenando o tema.

### Ambientes (cada um = cena 3D low poly + o Mário encenando)
| Ambiente | Configuração que representa | Encenação |
|----------|------------------------------|-----------|
| **Oficina** | Configurações gerais | Mário sentado numa oficina/bancada |
| **Discoteca / sala de música** | Música | Mário numa sala com toca-discos, estilo discoteca |
| **Laboratório** | Animações | Vários Marios em cápsulas num laboratório |
| **Estúdio de gravação** | REC (modo gravação) | Mário no estúdio |
| **Sala de pintura** | Skins | Mário pintando / trocando de visual |

### Animações de transição (parte da identidade do produto)
| Transição | Descrição |
|-----------|-----------|
| **Entrar nas configurações** | Câmera é puxada para dentro do armário da cabeça pelos tentáculos |
| **Sair das configurações** | Câmera é cuspida com força pra fora; fica resíduo de gosma rosa borrada na tela, que some com o tempo (reusar E7 + shader/overlay) |
| **Trocar de modo** (música/geral/animações/skins/REC) | Transição temática entre os mini-ambientes |

**Observações:**
- Isto é um subsistema grande (câmera, cenas, UI, navegação) — tratar como épico próprio, depois que animações/props/efeitos básicos existirem.
- Reaproveita tentáculos (puxar câmera) e gosma (resíduo de saída) já existentes.

---

## 5. Modo gravação / REC (visão futura — P3)

Mário é mascote do canal do YouTube; o modo REC o faz aparecer em vídeos e lives.

- Movimentos padrão de "apresentador" + ações eventuais automáticas.
- **Call-to-actions configuráveis:** trazer e apertar o botão "Inscrever-se"; puxar plaquinhas de Like e do Sininho; trazer labels arbitrários configuráveis.
- Depende de: sistema de props/placas (P1b), labels configuráveis, e um estado/comportamento "modo apresentação".

---

## Ordem sugerida de ataque (proposta)

Fase 1 — conteúdo procedural puro (cabe no motor atual, sem arte nova):
1. A1 Comemorar, A5 reação por parte do corpo (expandir double_click)
2. E1 notas, E3 poeira de pouso, E6 Zzz, E2 ondas sonoras, E7 gosma — construir primeiro um **sistema de partículas/overlay reutilizável**
3. A2/A3 variações de dormir

Fase 2 — sistema de props + primeiros props:
4. Sistema reutilizável de "segurar/spawnar prop" (anexar geometria a junta)
5. P1e MP3 player (prop + UI pixelada + integração música) — maior valor
6. P1b placa (base para o modo REC)

Fase 3 — épicos:
7. Menu "dentro do armário" (ambientes + transições)
8. Modo REC (CTAs configuráveis)

> Pré-requisitos de arte (Blockbench/Blender) começam a importar na Fase 2. Decidir lá se a geometria nova é feita manualmente ou com apoio de um MCP de arte, como pipeline separado do motor de animação.

---

## 6. Pipeline de arte 3D (props e ambientes) — Blender MCP + estilização low poly

**Decisão (2026-11-05):** a geração de geometria nova (props da seção 2 e ambientes da seção 4) será feita via **Blender com MCP**, não Blockbench. Motivos:
- O usuário **não vai refinar modelos manualmente**, então a IA precisa dirigir a ferramenta de ponta a ponta. O Blender tem MCP estabelecido (`blender-mcp`, addon + servidor); o Blockbench **não tem** MCP oficial, só API de plugin/arquivo.
- Geração de `.bbmodel`/GLTF por código (sem refino humano) foi descartada: props simples até dá, mas sem ninguém para ajustar o resultado não fecha a qualidade desejada.

**Status:** adiado. O ambiente atual (esta máquina) **não tem Blender instalado**. Executar na OUTRA máquina.

### Pré-requisitos (na máquina com Blender)
- Blender 3.x/4.x instalado.
- Addon do `blender-mcp` instalado no Blender + servidor MCP rodando.
- Configurar o servidor em `mcp.json` (workspace `.kiro/settings/mcp.json` ou user `~/.kiro/settings/mcp.json`).
- Observação de fluxo: o Blender MCP controla uma instância **aberta** do Blender (não headless); as operações acontecem na tela, é interativo.

### Estratégia "low poly / street" (o modelo não nasce estilizado — é um processo)
Não contar com a IA modelando "bonito à mão". Em vez disso:
1. **Modelar a forma base** por operações (primitivas, booleanas, extrusões) — adequado a props que são formas geométricas simples.
2. **Passo de low-poly-ify reutilizável** (script Blender padronizado, aplicado a toda peça para garantir estilo consistente): decimate/remesh para baixar polígonos, flat shading (ângulos duros), paleta de poucas cores, UVs simples. É este passo que converte "malha genérica" em "low poly street".
3. **Export GLTF** na escala/orientação do Mário (casar com `assets/model/mario.gltf`), pronto para o projeto carregar.
- O estilo voxel/Blockbench radical (tudo em caixas no grid) é difícil de garantir via Blender automático; o alvo realista é "low poly duro, poucas cores, street". Calibrar a receita até bater com o Mário.

### Como tocar (quando houver Blender)
1. Verificar ambiente (Blender instalado + versão) e configurar o MCP.
2. **Prop piloto** (sugestão: placa P1b ou MP3 player P1e) para calibrar a receita de low-poly-ify ANTES de produzir o resto. Um piloto, não os cinco de uma vez.
3. Com a receita validada, produzir os demais props da seção 2.
4. Ambientes (seção 4) só depois — modelagem pesada; reavaliar esforço com um caso real.

### Lógica de código que independe da arte (pode adiantar nesta máquina)
- **Sistema de "segurar/spawnar prop"**: anexar uma geometria (GLTF) a uma junta do rig e acompanhar a pose. É reutilizável e pode ser construído e testado com um placeholder (ex.: um cubo) antes dos modelos reais existirem. Depois, cada prop é só geometria + config.

---

## 7. Instruções para o agente de arte/modelos (outro PC)

Esta seção é um briefing para um agente mais capacitado em pixel art e modelagem 3D, que trabalhará na máquina com Blender instalado. O ambiente atual não tem Blender; tudo aqui é especificação para execução lá.

### Contexto do asset existente
- Modelo-fonte: `assets/model/projetoMARIO.bbmodel` (Blockbench) e `assets/model/mario.gltf` (runtime). Modelo **sem skin, sem ossos** — grupos são nós de transformação rígidos, animados proceduralmente. NÃO migrar para skin/bones (o motor de animação é procedural; ver seção sobre ossos abaixo).
- Textura: `assets/model/Textura.png` (atlas). Estilo: low poly + street, alternando com pixelado em efeitos/UI.
- Paleta de marca (do banner): fundo magenta/rosa-choque, verde-limão, roxo escuro, gosma rosa-pink, preto, tênis brancos.

### Decisão sobre rig/ossos (registrada)
NÃO riggar com ossos/skin nem usar Mixamo. O modelo de blocos rígidos não precisa de deformação de pele; Mixamo é animação baked (incompatível com o procedural reativo). Tensão de dobra, limites de junta e IK são resolvidos em CÓDIGO (sistema de springs por junta). O rig de nós de transformação atual é o correto para o estilo. Blender/MCP entra só para MODELAR GEOMETRIA NOVA (props/ambientes), como pipeline de asset — não para rig de animação do Mário.

### Pipeline de geração de geometria (Blender + low-poly-ify)
1. Modelar a forma base por operações (primitivas, booleanas, extrusões).
2. Passo reutilizável de "low-poly-ify" (script Blender padronizado): decimate/remesh, flat shading (ângulos duros), paleta de poucas cores, UVs simples. É o que garante o estilo consistente.
3. Exportar GLTF na escala/orientação do Mário (casar com `assets/model/mario.gltf`).
4. Validar com glTF Validator; otimizar com gltf-transform/gltfpack se necessário.
5. Props: cada prop = geometria + lógica de anexação a uma junta do rig (slot de "segurar prop", a construir em código).

### Itens de arte a produzir (ver seções 2, 3, 4 para detalhes)
- Props low poly/street: lata de spray, placa, guitarra, microfone, MP3 player da cintura (com UI de player pixelada).
- Efeitos pixelados: notas musicais, ondas sonoras, poeiras (pouso/deslize/queda), Zzz, gosma rosa.
- Ambientes (épico): laboratório, discoteca/sala de música, oficina, estúdio de gravação, sala de pintura.
- Prop piloto recomendado para calibrar a receita de estilo antes de produzir o resto: placa ou MP3 player.

### Pré-requisitos na máquina de arte
- Blender 3.x/4.x + addon do blender-mcp + servidor MCP; configurar em `.kiro/settings/mcp.json`.
- O Blender MCP controla uma instância aberta do Blender (não headless); fluxo interativo.
