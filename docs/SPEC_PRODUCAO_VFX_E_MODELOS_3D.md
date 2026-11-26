# SPEC DE PRODUÇÃO DE VFX E MODELOS 3D — MARIO 2.0 (SEJOGA DESKTOP COMPANION)

**Versão:** 3.0 Canônica (5 Estilos Fechados + Quadro de Referências Visuais)  
**Status:** Contrato Oficial de Produção (Anti-Genérico / Anti-Desvio / Anti-Desperdício de Tokens)  
**Público-alvo:** Agentes de geração 3D, shaders, flipbooks e VFX (GPT 6.2 e similares)  
**Relação com o Manual:** Estende e operacionaliza a Seção 3.5 (*Direção de arte de modelos, props e VFX*) de [`docs/MANUAL_UNIFICADO_MARIO.md`](MANUAL_UNIFICADO_MARIO.md).

---

## 0. Manifesto Anti-Genérico (Leia Antes de Gerar Qualquer Pixel ou Vértice)

Modelos de IA acertam objetos concretos (rádio, caixa de som) porque eles têm **peças nomeadas e função física óbvia**, mas erram em VFX quando tratam efeito como "forma geométrica aleatória colorida voando no ar".

**Este contrato proíbe categoricamente:**
1. **Substituir o fenômeno pelo estilo:** O filtro visual **NUNCA** muda o que aconteceu na cena. Sono não pode virar espada/circuito; carinho não pode virar cubo rodando; impacto no chão não pode virar forma solta flutuando.
2. **A fórmula preguiçosa "nasce na cabeça → voa girando → some":** Cada fenômeno tem sua própria lei física (poeira corre rente ao chão e freia; choque conecta duas antenas; susto trava no lugar; sono sobe lento).
3. **Desenhar arte narrativa com matemática SDF cega:** Equações trigonométricas genéricas (`cos(a*9)`, losangos girando, riscos parabólicos soltos) não são VFX.
4. **Compensar silhueta fraca com brilho, neon ou cor saturada:** Se o efeito não é reconhecível em **escala de cinza** em cima do Mário em 0,2 segundos, ele está **REPROVADO**.
5. **Fade-out translúcido contra o fundo:** O overlay Win32 usa chroma key pós-tonemap **`RGB(214, 0, 214)` (`#D600D6`)**. Semi-transparência alfa contra o desktop gera halo rosa. A dissipação deve ocorrer por **quebra da massa (espaço negativo / fragmentos), redução de escala ou dither Bayer 4×4** — nunca alpha fade suave.
6. **Pixelação destrutiva:** Nenhum estilo pode degradar a visibilidade do rosto, das mãos ou dos detalhes do Mário (estilos como `gameboy`, `pixel` e `lowpoly_block`/PS1 foram aposentados por redundância e perda de legibilidade).

---

## 1. Regra Suprema da Arquitetura Visual

```text
EVENTO  = SUBSTANTIVO  (O QUE aconteceu, ONDE ancora, COMO se move no espaço)
ESTILO  = ADJETIVO     (EM QUE MÍDIA aquele mesmo substantivo é desenhado)
```

- **Nunca inverta essa relação.**
- Se o evento é `impacto_chao`, a silhueta em **todos os 5 estilos** continua comunicando **impacto no chão sob os pés** (anel rasante + poeira baixa abrindo para os lados).
- O que muda entre `blockbench`, `street`, `anime`, `spiderverse` e `holograma` é **a linguagem gráfica/material, o enquadramento/atuação e a cadência de FPS** daquele mesmo fenômeno — nunca o significado nem a âncora base.

---

## 2. Quadro de Referências Visuais (Âncora Obrigatória)

Antes de gerar qualquer asset ou shader para um estilo, o agente **DEVE** inspecionar a prancha de referência correspondente em [`docs/referencias_vfx/`](referencias_vfx/README.md):

| Estilo | Prancha de Referência | Referências Teóricas Complementares |
| :--- | :--- | :--- |
| **`blockbench`** *(Padrão)* | [`docs/referencias_vfx/ref_blockbench.png`](referencias_vfx/ref_blockbench.png) | [Mojang — VFX of Minecraft Dungeons (VFX Apprentice)](https://www.vfxapprentice.com/blog/mojang-vfx-of-minecraft-dungeons) |
| **`street`** | [`docs/referencias_vfx/ref_street.png`](referencias_vfx/ref_street.png) | Persona 5 UI/Action Typography, Bomb Rush Cyberfunk, Jet Set Radio |
| **`anime`** | [`docs/referencias_vfx/ref_anime.png`](referencias_vfx/ref_anime.png) | [What are Manpu? (Anime Art Magazine)](https://animeartmagazine.com/what-are-manpu-anime-and-manga-comic-symbols-and-how-to-use-them-right-part-1/) · [Anime's Visual Language (Japan Powered)](https://www.japanpowered.com/japan-culture/animes-visual-language) |
| **`spiderverse`** | [`docs/referencias_vfx/ref_spiderverse.png`](referencias_vfx/ref_spiderverse.png) | Estudo de estética Spider-Verse (Samara Bittencourt, 2023) |
| **`holograma`** | [`docs/referencias_vfx/ref_holograma.png`](referencias_vfx/ref_holograma.png) | Estética CRT analógico / projeção de dados instável |
| **Anti-exemplos** *(opcional)* | `docs/referencias_vfx/ref_anti_exemplos.png` | Exemplos explícitos do que é PROIBIDO gerar |

Todo entregável é revisado visualmente contra a prancha do estilo alvo.

---

## 3. Restrições Técnicas Invioláveis do Projeto

1. **Chroma Key Seguro (`RGB(214, 0, 214)` / `#D600D6`):**
   - Proibido emitir cores próximas ao magenta de chroma em vértices, texturas, explosões, feixes ou shaders.
   - Proibido alpha blending suave nas bordas externas contra o desktop vazio (usar recorte duro, geometria opaca ou dither Bayer 4×4 fino).
2. **Oclusão e Leitura do Rosto:**
   - `depthTest` e `depthWrite` ativos em malhas 3D.
   - **Proibido cobrir o visor/rosto do Mário** com efeitos de reação ou música. Molduras e auras ficam no plano traseiro ou ao redor da silhueta; impactos ficam no plano real do contato.
3. **Padrão de Modelos glTF / Blockbench:**
   - UVs definidas em repouso para a pintura acompanhar partes animadas.
   - Sampler glTF obrigatório: `minFilter = 9728` e `magFilter = 9728` (`NEAREST`).
   - Densidade de texels proporcional à textura de `assets/model/mario.gltf`.
   - Preservar pivôs, nomes de nós e eixos locais do rig (`ALL_GROUPS`).
4. **Escolha Correta da Mídia por Tipo de VFX:**
   - **Geometria 3D / Blockbench (`.bbmodel`/`.gltf` ou construtor modular com peças nomeadas):** para volumes espaciais reais (anéis rasantes, fitas/ribbons, nuvens volumétricas, frentes de pressão no cone do falante, arcos 3D biponto entre antenas, portais, peças de desmontagem).
   - **Flipbook / Sprite Sheet de 4 a 8 quadros desenhados quadro-a-quadro (vetorial/PIL com silhueta limpa):** para efeitos gráficos/simbólicos (*manpu* anime, puffs pixel-art chunky do Blockbench, placas/tipografias *street*, onomatopeias rabiscadas *spiderverse*, ícones CRT, `Zzz`, coração, `!`, gota de suor).
   - **Shader de Filtro:** responsável por estilização da superfície, iluminação, contorno, retícula, CRT/scanlines e reatividade ao movimento — **proibido** usar shader SDF cego para substituir a anatomia do evento.
5. **Estrutura Modular no Código (`src/sejoga/render/vfx/`):**
   - Cada estilo canônico implementa seus emissores autorais em `src/sejoga/render/vfx/<estilo>.py` (`blockbench.py`, `street.py`, `anime.py`, `spiderverse.py`, `holograma.py`) e os registra em `EMISSORES_POR_ESTILO` dentro de `src/sejoga/render/vfx/__init__.py`.
   - `src/sejoga/render/vfx_coreografias.py` atua apenas como roteador fino para os emissores registrados (com fallback legado para eventos ainda não migrados).
   - **Proibido** acumular emissores novos diretamente em `vfx_coreografias.py`.

---

## 4. Mapa Oficial de Âncoras do Rig do Mário

Nenhum VFX pode flutuar em posição arbitrária. Todo efeito declara explicitamente sua âncora:

| Âncora no Rig | Localização Real | Uso Canônico |
| :--- | :--- | :--- |
| `sola_esq` / `sola_dir` / `pes` | Plano exato do piso sob as botas (`z = piso`) | `impacto_chao`, `hero_drop_in`, poeira de corrida/derrapagem |
| `lado_esq` / `lado_dir` | Laterais externas do gabinete | `impacto_parede` (orientado pela normal da parede) |
| `tronco` | Centro de massa do corpo | `rastro` aéreo, `sandevistan`, `kagebunshin_in`, `portal_pull_out`, `thanos_snap`, `lego_disassemble`, molduras/auras traseiras |
| `cabeca_topo` | Acima do topo do armário (livre do visor) | `carinho`, `sobressalto` (coroa), `calor` (vapor), *gloom lines*, *kirakira* |
| `visor_lado` | Lateral externa do visor (nunca na frente) | `sono` (`Zzz` / bolha), micro-símbolos de idle (`?`, notas) |
| `templo` | Canto superior lateral do gabinete | `calor` (gota de suor), *ikari mark* (veia de raiva) |
| `fone_dir` / `fone_esq` | Caixas dos fones de ouvido | `sobressalto`, `acento_danca` (sem palco), idle `fone_com_problema` |
| `antena_d` ↔ `antena_e` | **Biponto** entre as pontas das duas antenas | `choque` (arco elétrico preso nas duas pontas) |
| `porta` (abertura frontal) | Boca interna do armário quando `door > 0°` | `gosma` / tentáculos, espirro |
| `cone_palco` | Boca dos falantes de `Boomboxes.gltf` / rádio | `acento_danca` (ondas de grave saindo do cone) |

---

## 5. Catálogo Fechado de Fichas de Engenharia — VFX (SUBSTANTIVOS)

Cada efeito abaixo é tratado como um **objeto de engenharia** (peças nomeadas, âncora, curva física em 3 fases e lista negra).

### 5.1 Eventos de Física, Impacto e Deslocamento

#### 1. `impacto_chao` (Pouso / Queda)
- **Leitura em 0,2s (cinza):** Choque rasante no piso sob as solas empurrando poeira para os lados.
- **Âncora e Espaço:** `sola_esq` e `sola_dir` no plano do chão (`z = piso`). Altura máxima do volume ≤ altura da canela.
- **Peças Nomeadas:**
  1. *Primária:* Anel rasante achatado no piso (`altura ~ 0.08`), aberto/assimétrico.
  2. *Secundária:* 3 a 4 nuvens baixas de poeira nascendo nas bordas externas dos pés.
  3. *Resíduo (apenas `forca >= 1.2`):* 2 a 4 lascas/pedrinhas pequenas em arco balístico curto quicando no chão.
- **Curva Temporal (0.45–0.55s):**
  - *Ignição (0–12%):* Anel nasce colado à sola comprimida; poeira nasce densa e compacta.
  - *Pico (12–45%):* Anel expande rápido em ease-out cúbico; poeira corre **horizontalmente** para fora com `drag` alto (quase sem subir).
  - *Dissipação (45–100%):* Anel afina e parte em arcos menores; poeira abre espaço negativo ou encolhe em fragmentos até 0.
- **Lista Negra (PROIBIDO):** Subir acima do joelho; girar como shuriken; soltar símbolo de música/circuito; nascer no tronco ou na cabeça.

#### 2. `impacto_parede` (Colisão Lateral / Teto)
- **Leitura em 0,2s (cinza):** Batida seca contra uma superfície vertical/superior com rebote direcional.
- **Âncora e Espaço:** Ponto exato de contato (`lado_esq`, `lado_dir` ou `cabeca_topo`), **alinhado à normal da superfície atingida**.
- **Peças Nomeadas:**
  1. *Primária:* Meia-lua / estrela de impacto achatada paralela à parede (no `spiderverse`, onomatopeia como `PONK` deitada na perspectiva da parede + 3 risquinhos secos no contato).
  2. *Secundária:* 3–5 raios/linhas curtas em leque ao longo do plano da parede.
  3. *Resíduo:* 2–3 lascas pequenas ricocheteando no sentido da normal com gravidade real.
- **Curva Temporal (0.35–0.45s):** Ignição seca (frame 0) → leque abre rente à parede → retrai das pontas e lascas caem.
- **Lista Negra (PROIBIDO):** Atravessar a parede; flutuar lento para cima; efeito simétrico sem vetor de normal.

#### 3. `acento_danca` (Grave do Palco / Batida Musical)
- **Leitura em 0,2s (cinza):** Pulso acústico de ar saindo fisicamente do alto-falante ou dos fones no *downbeat*.
- **Âncora e Espaço:** `cone_palco` (quando palco/rádio visível) ou `fone_dir`/`fone_esq` (sem palco), apontando para fora do cone.
- **Peças Nomeadas:**
  1. *Primária:* 2 arcos/anéis de pressão acústica concêntricos (2º atrasado 2 frames) orientados pelo eixo do cone.
  2. *Secundária (opcional em batida forte):* 1–2 notas musicais ou acentos gráficos do estilo saindo atrás do plano do rosto.
- **Curva Temporal (0.32–0.40s):** Nasce no diâmetro da calota do cone → expande rápido afinando → rompe antes do próximo grave.
- **Lista Negra (PROIBIDO):** Nascer no meio da barriga/rosto; poluir a tela inteira; girar em 3 eixos aleatórios.

#### 4. `rastro` (Corrida, Derrapagem e Arremesso Veloz)
- **Leitura em 0,2s (cinza):** Trajetória de velocidade deixada **para trás** no espaço.
- **Âncora e Espaço:** `sola_esq`/`sola_dir` no chão; `tronco` alinhado a `-velocidade` no ar.
- **Peças Nomeadas:**
  1. *No chão:* Puffs rasantes de poeira + 2 riscos curtos de atrito rente ao piso.
  2. *No ar:* Fita/ribbon luminoso (`blockbench`), letras esticadas em chevrons `FAST >>>` (`street`), *speedlines* finas (`anime`), laços rabiscados (`spiderverse`), ou ecos de scanlines desfiadas (`holograma`).
- **Curva Temporal (0.28–0.36s):** Nasce onde o Mário acabou de passar e **fica quase parado no mundo**, encolhendo da cauda para a ponta.
- **Lista Negra (PROIBIDO):** Voar na frente do Mário; ignorar o vetor `vel`; virar nuvem de confete.

#### 5. `choque` (Descarga Elétrica nas Antenas)
- **Leitura em 0,2s (cinza):** Eletricidade viva saltando de uma antena para a outra.
- **Âncora e Espaço:** **Biponto obrigatório** entre `antena_d` e `antena_e`.
- **Peças Nomeadas:**
  1. *Primária:* Polilinha quebrada em 4–6 segmentos ligando exatamente `antena_d` → `antena_e` (núcleo branco + borda do estilo).
  2. *Secundária:* 2 mini-coronas/estalos presos nas pontas das antenas (no `street`, pode disparar flash Raio-X de 1–3 frames).
- **Curva Temporal (0.28–0.36s):** Cadência seca (10–12 FPS stepped): pisca e redesenha a quebra 3 vezes no mesmo espaço e corta seco.
- **Lista Negra (PROIBIDO):** Objetos soltos voando para fora da cabeça; movimento lento; arco que não toca as duas antenas.

---

### 5.2 Eventos de Estado e Emoção

#### 6. `carinho` (Afeto / Pet)
- **Leitura em 0,2s (cinza):** Afeto gentil e orgânico subindo acima do Mário.
- **Âncora e Espaço:** `cabeca_topo` (fora do eixo do rosto).
- **Peças Nomeadas:** 1 coração legível (+ 1 mini atrasado opcional) + 2 mini-brilhos sutis (no `anime`, cruzinhas *smug*/satisfação; no `street`, placa/coração recortado compacto).
- **Curva Temporal (0.75–0.90s):** Pop elástico curto → sobe devagar em oscilação pendular ±8° → mini-estouro limpo.
- **Lista Negra (PROIBIDO):** Velocidade alta; cacos/raios/espadas; girar 360°; tampar o rosto.

#### 7. `sono` (Cochilo / Repouso)
- **Leitura em 0,2s (cinza):** Ritmo lento de respiração adormecida.
- **Âncora e Espaço:** `visor_lado` (subindo em diagonal suave para fora).
- **Peças Nomeadas:** Sequência escalonada `z` → `Z` com contorno legível **ou** bolha de cochilo pulsando na respiração.
- **Curva Temporal (1.00–1.20s):** Nasce pequeno → flutua muito lento em "S" calmo (±10°) → encolhe/desfaz em Bayer suave.
- **Lista Negra (PROIBIDO):** Qualquer forma pontuda, faísca, giro, velocidade alta ou explosão.

#### 8. `calor` (Superaquecimento / Raiva / Esforço)
- **Leitura em 0,2s (cinza):** Gabinete quente soltando vapor/mormaço, suor ou irritação.
- **Âncora e Espaço:** `cabeca_topo` (vapor) e `templo` (gota de suor ou veia de raiva *ikari mark* no `anime`).
- **Peças Nomeadas:** 2–3 ondas verticais de vapor + 1 gota escorrendo (ou veia de raiva + katakana `ゴゴゴ` nos picos do `anime`).
- **Curva Temporal (0.65–0.80s):** Vapor sobe serpentando na vertical; gota segura 3 frames no `templo` e escorrega para baixo.
- **Lista Negra (PROIBIDO):** Disparar para os lados como tiro; girar em 3D; parecer fumaça de explosão.

#### 9. `sobressalto` (Susto / Alerta)
- **Leitura em 0,2s (cinza):** Reação instantânea de choque/alerta ao redor da cabeça.
- **Âncora e Espaço:** Coroa curta ao redor de `cabeca_topo` e `fone_dir`/`fone_esq` (nunca na frente do visor).
- **Peças Nomeadas:** 3–5 linhas radiais curtas de susto ou `!` nítido (no `spiderverse`, ondas zigue-zague de *spidey-sense*; no `anime`, barras radiais curtas + zigue-zague de tremor; no `street`, balão/exclamação angular ou `HOLD UP!` em pico).
- **Curva Temporal (0.25–0.32s):** **Snap em 1 frame** (115% overshoot) → **segura quase imóvel** 3–4 frames para leitura → encurta da base para a ponta e some seco.
- **Lista Negra (PROIBIDO):** Viajar para longe da cabeça; cair com gravidade; movimento lento.

---

### 5.3 VFX Narrativos de Idle e Micro-Ações (Integração com Futuros Roteiros de Idle)

Todos os 5 estilos devem suportar um vocabulário enxuto e discreto de **VFX de apoio narrativo** para ressoar com os idles atuais e futuros:

| Gatilho de Idle / Micro-Ação | Substantivo Visual | Âncora | Regra de Discrição |
| :--- | :--- | :--- | :--- |
| **Curiosidade / Dúvida** (`olhar_curioso_chao`, janela nova) | `?` legível ou 2 brilhos *kirakira* | `visor_lado` / `cabeca_topo` | Pequeno, curta duração (0.5–0.7s), sem ruído |
| **Fone com problema** (`fone_com_problema`) | 1–2 estalos secos / micro-faísca curta | `fone_dir` / `fone_esq` | Nasce exatamente no fone tocado, 0.25s |
| **Conferir estilo / Orgulho** (`conferir_estilo`, `conferir_luva`) | 2–3 brilhos em cruz de 4 pontas (*sparkle*) | Contorno da luva / topo do gabinete | Pisca alternado e some limpo |
| **Ouvir música no Walkman** (`escutar_fone`, `checar_walkman`) | 1–2 micro-notas musicais leves | `fone_dir` / `fone_esq` | Sobe suave e curto (não confundir com grave do palco) |
| **Tédio / Desconfiança / Repreensão** | *Gloom lines* (`anime`), `...` em balão (`street`), puff baixo (`blockbench`) | `cabeca_topo` / `visor_lado` | Calmo, ritmo lento |
| **Espirro / Poeira** (`sneeze`) | Pequeno puff frontal + 2 gotículas/faíscas de ar | `porta` / frente do visor | Sincronizado no pico exato do espirro |

---

### 5.4 Efeitos Especiais de Cena e Transição

| Efeito Especial | Substantivo / Leitura Obrigatória | Ancoragem e Mecânica |
| :--- | :--- | :--- |
| **`goku_teleport_in/out`** | Estiramento relâmpago + linhas de distorção espacial (*Shunkan Idō*) | `tronco`; 2–3 frames de colapso/expansão + estalo fino de ar |
| **`sandevistan` / `sandevistan_in`** | Ecos congelados da **silhueta real do Mário** (*afterimages*) em rampa de cor | Pose exata do rig, **cravado no espaço** desvanecendo por dither/escala |
| **`kagebunshin_in`** | Nuvem densa de fumaça ninja (4–6 bolhas abrindo espaço negativo central) | `tronco`; expande em 3 frames, abre buraco revelando o Mário e quebra |
| **`hero_drop_in`** | Versão pesada de `impacto_chao`: anel duplo rasante + rachadura temporária no piso + poeira ampla + lascas | `pes` no chão; sincronizado no frame exato do squash |
| **`lego_disassemble`** | Peças reais discretas do armário/membros separando com física e quique | Posições reais dos grupos do rig; gravidade + quique no chão |
| **`thanos_snap`** | Erosão direcional do corpo virando partículas finas levadas por vento único | Superfície da malha; vetor de vento consistente |
| **`portal_pull_out`** | Fenda/vórtice espiral puxando linhas de sucção **para dentro** | Centro fixo do portal; tudo converge para dentro |
| **`gosma` (tentáculos)** | Fios e gotas viscosas que esticam por tensão superficial e caem pesadas | `porta` / superfície do tentáculo; gravidade real |

---

## 6. Matriz Oficial dos 5 Estilos Canônicos (ADJETIVOS)

**Lembrete obrigatório:** Todos os 5 estilos desenham os **MESMOS substantivos da Seção 5**. Abaixo está o DNA fechado e aprovado de cada estilo.

### 6.1 `blockbench` *(Padrão Oficial)*
- **Prancha:** `docs/referencias_vfx/ref_blockbench.png`
- **Visual do Mário:** **Sem contorno preto.** Render 3D limpo com **shading macio/difuso (*soft shading*)** preservando 100% os texels nítidos (`NEAREST`) — estética *Minecraft Dungeons* / *Hytale* / renders modernos de Blockbench.
- **VFX:** Simples, expansivos, escalonáveis e luminosos:
  - Mistura de **formas expansivas 3D limpas** (anéis de chão, fitas/ribbons luminosos, raios com núcleo branco emissivo) + **puffs de fumaça chunky pixel-art** e **ícones pixel-art nítidos** (`Zzz`, coração, nota, faíscas quadradas).
  - Alto contraste emissivo (núcleo branco quente → cor saturada vibrante: dourado, ciano/azul elétrico, verde-esmeralda, laranja).
  - Sensação de brilho/opacidade obtida de forma **chroma-safe** (camadas sólidas + núcleo emissivo + dither Bayer 4×4 fino na dissipação, sem halo rosa `#D600D6`).
  - Integração suave e natural com os **VFX narrativos de Idle**.
- **Proibido:** Contorno grosso de HQ; pixelação que borra o rosto; bloom alfa vazando para o fundo transparente; magenta próximo a `#D600D6`.

### 6.2 `street` *(Pôster Vivo / Persona / BRC)*
- **Prancha:** `docs/referencias_vfx/ref_street.png`
- **Visual do Mário:** Cel-shading duro + **contorno preto grosso/riscado à mão** (leitura limpa e forte).
- **VFX & Composição:**
  - **Hierarquia de tela:**
    - **Picos e ações marcantes** (arremesso veloz, queda pesada, choque, susto, grave forte): **molduras grandes e chamativas atrás e ao redor do Mário** (sem cobrir o rosto), encaixando no contorno do corpo como arte de pôster/sticker, combinadas com **poses fortes enquadradas** (*attitude pose* curta).
    - **Estados calmos** (`sono`, `carinho`, `calor`, idles): **balões e placas angulares compactas** com borda preta grossa e sombra dura deslocada (estilo ícones Persona/Hi-Fi Rush), sem poluir o desktop.
  - **Tipografia cinética (misto curto):** palavras curtas e onomatopeias (`BANG!`, `FAST >>>`, `ZAP!`, `DROP!`, `OPA!`, `HOLD UP!`, `ZZZ`, `?!`) em blocos recortados P&B/coloridos ou grafite que **indicam o movimento e a intenção** (ex.: `FAST >>>` virando o rastro).
  - **Impacto Raio-X (assinatura exclusiva):** em impactos pesados e choque, flash de **1–3 frames revelando ossos nos braços/pernas + interior do armário com os tentáculos/fiação brilhando no raio-X**, sobre explosão gráfica bicromática atrás (amarelo, azul cobalto, vermelho, verde-lima — longe de `#D600D6`).
- **Proibido:** Cobrir o rosto do Mário; frases longas ilegíveis; spam de moldura gigante em eventos calmos; fundo/explosão magenta.

### 6.3 `anime` *(Manpu Emocional, Drama & JoJo)*
- **Prancha:** `docs/referencias_vfx/ref_anime.png`
- **Visual do Mário:** **Line art fina e limpa + cel-shading em 2–3 bandas** no dia a dia, ativando **hachura e contraste dramático estilo JoJo** somente nos picos de raiva/pose dramática.
- **VFX & Expressão:**
  - **Coração do estilo — *Manpu* (sutil, limpo e imediato):**
    - Empolgação/curiosidade: brilhos amarelos de 4 pontas (*kirakira*).
    - Raiva/teimosia: veia vermelha (*ikari mark*) no `templo` + nos picos, **katakanas gigantes estilo JoJo (`ゴゴゴ` / `ドドド`)** + pose dramática congelada (*JoJo pose*).
    - Tédio/desconfiança/repreensão: **linhas verticais escuras (*gloom lines*)** caindo sobre a cabeça + sombra no topo.
    - Tremor/susto/esforço: **zigue-zagues amarelos sutis** contornando o corpo + barras radiais curtas + katakana fino vertical.
    - Carinho/orgulho (*smug*): cruzinhas/estalos amarelos nas laterais da cabeça.
  - **Realce dramático localizado (chroma-safe):** em picos emocionais, aura/sombra escura atrás da silhueta do Mário (recorte gráfico ou Bayer 4×4) para destacar a reação.
  - **Impactos físicos:** elegantes e mais contidos que o `street` — poeira recortada limpa com **espaço negativo real**, *speedlines* finas e **1 frame de *impact frame* P&B nanquim** nos golpes pesados.
- **Proibido:** Trocar emoções por lâminas/energias genéricas; glow difuso borrando a silhueta; exagero caótico que invade o espaço do `street`.

### 6.4 `spiderverse` *(12/24 FPS, HQ Rabiscada & Every Frame a Painting)*
- **Prancha:** `docs/referencias_vfx/ref_spiderverse.png`
- **Visual do Mário:** **Shading bem flat** (sem reflexos/gradientes 3D realistas), com **blocos duros de preto nanquim** nas sombras profundas, **retícula (pontos Ben-Day / hachura)** nas transições e **paleta fixa característica** no corpo do Mário.
- **Cadência 12 FPS ↔ 24 FPS:**
  - Deslocamento da janela/arraste do mouse permanece fluido (para nunca parecer lag), enquanto a **pose do rig e os VFX** trabalham em **12 FPS (*on twos*)** nas poses marcantes (deixando poses inusitadas em evidência) e **24 FPS** nas transições mais sutis *(ajustar finamente via validação visual na janela real)*.
- **VFX & Picos:**
  - **Explosões de cor ousadas** (amarelo ácido + ciano menta, roxo + verde-ácido, laranja + azul — sempre com guarda anti-`#D600D6`) concentradas nos picos e VFX.
  - **Estética rabiscada/duplicada à mão** + **aberração cromática (*misprint*)** nos impactos e velocidade.
  - **Onomatopeias encaixadas na perspectiva do espaço** (`PONK` na parede com 3 risquinhos secos no contato, `BWOOM` com halftone dentro, `KRACK` com laços de tinta e estrelinhas ao redor da cabeça) + ondas *spidey-sense* no susto.
- **Proibido:** Repetir a mesma estrela amarela genérica para todos os eventos; 60 FPS liso sem charme; poluir o rosto com halftone.

### 6.5 `holograma` *(Projeção de Dados Instável & CRT Analógico)*
- **Prancha:** `docs/referencias_vfx/ref_holograma.png`
- **Visual do Mário:** Mantém a **base ciano/azul elétrico atual** (scanlines limpas, sombras do visor preservadas e leitura clara em repouso), adicionando **comportamento físico de sinal CRT/dados instáveis**:
  - **Em repouso (Idle):** projeção estável com scanlines CRT sutis e micro-pulso de sinal.
  - **Movimentos rápidos / sair do chão / arremesso:** o sinal perde sincronia — o corpo/rastro **se desfaz parcialmente em ecos de scanlines fragmentadas** + cisalhamento horizontal CRT e flashes de **fósforo RGB (ciano + azul + laranja/vermelho)**, recompondo-se ao pousar/parar.
  - **Impactos / choque / susto:** *horizontal sync tear*, micro-lentidão de "recarregamento sci-fi" em faixas e fragmentação digital curta.
- **VFX:** Mesmos substantivos da Seção 5 traduzidos em projeção de dados/CRT (anel sonar/scanline no piso, ecos de scanline no rastro, arco de sobrecarga de dados entre antenas, ícones monoespaçados estilo `EXT3` para `sono`/`carinho`/`sobressalto`).
- **Proibido:** Trocar todos os eventos por um retângulo genérico; glitch tão forte parado que impede enxergar o Mário; cores próximas ao chroma `#D600D6`.

---

## 7. Padrão para Modelos 3D e Props (Rádios, Caixas, Acessórios, Cenário)

Todo novo modelo 3D segue este checklist antes da exportação:

1. **Briefing de Peças (Obrigatório antes de modelar):**
   - Listar cada subcomponente nomeado com função (ex.: carcaça, alça, visor, cone, calota, botões, base).
   - Definir proporção explícita em relação à altura do Mário (ex.: *"altura = 0.45× a altura do gabinete do Mário"*).
   - Definir pivôs locais para partes animáveis em runtime (cones no grave, ponteiros, tampas).
2. **Geometria & Silhueta:**
   - Leitura imediata em **tamanho real do companion no desktop** (vistas frontal e 3/4).
   - Geometria reservada para o que altera silhueta, oclusão ou articulação; microdetalhes vão na pintura UV.
   - Zero faces invertidas, zero z-fighting, zero peças desconectadas.
3. **Textura & Material:**
   - Densidade de texels compatível com `mario.gltf`; grupos contíguos de texels; rampa curta de sombra / cor local / luz por material.
   - Exportar em glTF/GLB com UVs em repouso, sampler `NEAREST (9728)` e validação limpa no validador glTF (0 erros, 0 avisos).
4. **Prova Visual do Prop:**
   - Capturar vista **frontal**, **3/4** e **ao lado do Mário na janela real** (em tamanho de uso + durante animação se houver partes móveis).

---

## 8. Protocolo de Execução (Anti-Desvio / Economia Máxima de Tokens)

**Proibido** gerar todos os 9 eventos × 5 estilos de uma vez. Siga obrigatoriamente os **4 estágios**:

### Estágio 0 — Contrato Textual Curto (custo mínimo de tokens)
- Escopo: **1 único evento (ou 1 prop) × 1 único estilo** (começar sempre por **`blockbench`**, o padrão).
- Consultar a prancha `docs/referencias_vfx/ref_<estilo>.png` (+ `ref_anti_exemplos.png` se presente).
- O modelo devolve **apenas** a Ficha de Engenharia preenchida (máx. 20 linhas) e **PARA** aguardando `APROVADO`.

### Estágio 1 — Piloto Funcional
- Gera o asset/código **somente** para o item aprovado no Estágio 0.
- Gera automaticamente uma **prancha de 5 quadros** (`0%`, `15%`, `40%`, `70%`, `95%`) renderizada **sobre o Mário real na pose correspondente**.
- Duas fileiras obrigatórias na prancha:
  - **Superior:** Escala de cinza (teste puro de silhueta e leitura).
  - **Inferior:** Colorido com chroma key real (`#D600D6` verificado limpo).

### Estágio 2 — Teste Cego + Comparação com Referência (Gate Obrigatório)
O entregável só passa se responder **SIM** às 6 perguntas:
1. **Teste Cego (em cinza):** Sem ler o nome do arquivo, qualquer pessoa identifica em 0,2s qual é o evento?
2. **Âncora Real:** Nasce e permanece coerente com o ponto exato do rig/cenário sem cobrir o rosto?
3. **Física Própria:** A trajetória faz sentido para aquele fenômeno (nada voando/girando sem causa)?
4. **Fidelidade à Prancha:** Bate com a linguagem visual de `ref_<estilo>.png`?
5. **Dissipação Chroma-Safe:** Desfaz por quebra/escala/Bayer sem halo magenta `#D600D6`?
6. **Escala de Desktop:** 100% legível no tamanho real do companion na tela?

> **Regra de Reprovação:** Se falhar em 1, 2 ou 3, é **proibido** "consertar com cor/brilho/partículas extras". Descarta a forma e volta ao Estágio 0.

### Estágio 3 — Expansão para os Outros 4 Estilos
- Somente após o evento ser aprovado em `blockbench` (padrão), traduz-se aquele mesmo evento para `street`, `anime`, `spiderverse` e `holograma`, preservando **100% do substantivo, âncora e lei de movimento** já validados.

---

## 9. Prompts-Contrato Prontos para Colar no GPT 6.2

### 9.1 Para Criar/Refazer um VFX
```text
ATUE SOB CONTRATO ESTRITO DE PRODUÇÃO DE VFX (SEJOGA MARIO 2.0 — ZERO DESVIO).
Siga integralmente docs/SPEC_PRODUCAO_VFX_E_MODELOS_3D.md e a prancha anexada
docs/referencias_vfx/ref_<estilo>.png.

ALVO DESTA RODADA (ESCOPO FECHADO):
- Evento: [ex: impacto_chao | choque | sono | ...]
- Estilo alvo: [blockbench | street | anime | spiderverse | holograma]
- Mídia exigida: [malha 3D modular | modelo Blockbench | flipbook 4-8 quadros]
- Entregável da Fase 0: APENAS a Ficha de Engenharia abaixo (máx. 20 linhas). NÃO gere código/asset ainda.

REGRAS INVIOLÁVEIS:
1. EVENTO = SUBSTANTIVO, ESTILO = ADJETIVO. Nunca troque o fenômeno por forma abstrata do filtro.
2. Proibido o padrão "nasce na cabeça -> voa girando -> some".
3. Proibido alpha fade suave contra fundo transparente (chroma key RGB(214,0,214)); usar quebra de massa, escala ou Bayer 4x4.
4. Nunca cobrir o visor/rosto do Mário.

PREENCHA E PARE PARA APROVAÇÃO:
- Leitura em 0.2s (escala de cinza):
- Âncora exata no rig e plano espacial:
- Peças nomeadas (máx. 3 camadas):
- Curva temporal (0% Ignição -> 20% Pico -> 60% Quebra -> 100% Fim):
- Como o estilo alvo traduz essas peças (alinhado à ref_<estilo>.png):
- 3 coisas da Lista Negra que serão evitadas:
- Se faltar algum dado decisivo, faça no máximo 1 pergunta objetiva.
```

### 9.2 Para Criar/Refinar um Modelo 3D / Prop
```text
ATUE SOB CONTRATO ESTRITO DE MODELAGEM 3D (SEJOGA MARIO 2.0 — ZERO DESVIO).
Siga integralmente a Seção 7 de docs/SPEC_PRODUCAO_VFX_E_MODELOS_3D.md.

ALVO DESTA RODADA (ESCOPO FECHADO):
- Objeto/Prop: [ex: boombox portátil / skate / caixa de som]
- Proporção relativa ao Mário: [ex: altura = 0.45x gabinete do Mário]
- Uso em cena / partes móveis: [ex: fica no chão; cone pulsa no grave]
- Entregável da Fase 0: APENAS o Briefing de Peças abaixo (máx. 20 linhas). NÃO gere o modelo ainda.

REGRAS INVIOLÁVEIS:
1. Silhueta reconhecível de frente e em 3/4 no tamanho do companion.
2. Peças discretas nomeadas com pivôs locais preservados para partes animáveis.
3. UVs em repouso, densidade de texels compatível com mario.gltf, sampler NEAREST (9728).
4. Zero cores próximas ao chroma RGB(214,0,214), zero z-fighting, 0 erros no validador glTF.

PREENCHA E PARE PARA APROVAÇÃO:
- Lista de peças nomeadas e volumes principais:
- Pivôs/grupos animáveis e seus eixos locais:
- Paleta/materiais distinguíveis na luz ambiente (rampa curta de texels):
- Plano de validação visual (vistas frontal, 3/4 e ao lado do Mário):
```
