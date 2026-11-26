# SPEC E ROTEIROS DE IDLES & AÇÕES VIVAS — MARIO 2.0

**Versão:** 1.0 Canônica  
**Status:** Contrato Oficial de Animação de Idles Base e Cenas Narrativas  
**Relação com o Projeto:** Operacionaliza o *Manifesto da Criatura Viva* ([`docs/MANUAL_UNIFICADO_MARIO.md`](MANUAL_UNIFICADO_MARIO.md), Seções 1 e 2) e integra-se diretamente aos 5 estilos de [`docs/SPEC_PRODUCAO_VFX_E_MODELOS_3D.md`](SPEC_PRODUCAO_VFX_E_MODELOS_3D.md).

---

## 1. Regras de Ouro de Roteiro (Anti-Idle Robótico)

Todo idle base ou cena narrativa precisa cumprir 6 regras invioláveis:
1. **Silhueta Inconfundível:** Cada idle base deve ser reconhecível em 0,2 s até como sombra preta — proibido "ficar em pé mudando 5 graus de rotação".
2. **Causa Interna (Sem Timer Cego):** Toda cena declara o contexto/humor que a dispara (`tédio`, `curiosidade`, `música`, `pós-carinho`, `pós-queda`, `cursor parado perto`, `silêncio longo`).
3. **Estrutura em 3 Atos (Cenas):** Antecipação → Ação/Piada/Atitude (com pausa de leitura) → Consequência/Recuperação C1/C2 suave.
4. **Visor Livre & Anatomia Real:** Membros sempre por fora do gabinete (zero penetração mão-armário), pés firmes sem *foot-sliding*, dedos bilaterais articulados (`DedosCena`), porta mecânica (`0°–38°` idle; até `48°` bote/cuspe), antenas e fones com atraso inercial.
5. **Ressonância com os 5 Estilos de VFX:** Cada cena declara o substantivo de VFX que dispara, traduzido conforme o estilo ativo (`blockbench`, `street`, `anime`, `spiderverse`, `holograma`).
6. **Segurança Win32 nas Cenas de Cursor:** Nas ações com cursor (`cacar_cursor` e `roubo_cursor_tentaculo`), duração máxima curta (≤ 2,5 s) e **liberação imediata** se o usuário puxar rápido, clicar ou pressionar `ESC`.

---

## 2. Os 6 Idles Base Canônicos (Loops Contínuos com Personalidade Marcante)

Substituem/enxugam as 11 personalidades antigas redundantes (com migração automática em `configuracao.py` para perfis legados). No modo `auto`, a `Agencia` alterna entre eles conforme o humor/contexto real do Mário.

| ID Canônico | Nome / Arquétipo | Silhueta & Postura Inconfundível | Canais-Chave (Braços, Pernas, Porta, Antenas) | Entrada no `auto` |
| :--- | :--- | :--- | :--- | :--- |
| **`brc_malandro`** | Malandro de Rua (*Lethal League* × *BRC*) | *Lean back* (tronco inclinado pra trás), mão esquerda no quadril/Walkman, braço direito solto no swing, pé avançado no calcanhar balançando a ponta do tênis | Quadril lidera o gingado lateral; cabeça balança no contra-tempo; antenas tirando onda | Neutro confiante / padrão de rua |
| **`frenetico_groove`** | Groove Vivo (*FNF* × *Hi-Fi Rush*) | Base larga com **bounce elástico bem marcado nos joelhos** (squash/stretch a cada batida), mão direita perto da concha do fone, mão esquerda marcando o beat no ar | Fones e fio do fone chacoalham no tempo; dedos acompanham o ritmo mesmo sem música no PC | Feliz / música ambiente baixa |
| **`espreita_armario`** | Segredo Vivo ("Não Olha Aqui Dentro") | Corpo levemente curvado e virado de lado, uma mão próxima à **porta** tentando mantê-la quieta enquanto a portinha entreabre sozinha (`6°–14°`) com micro-batidinhas | Olhar de rabo de olho disfarçando; antenas alertas; comédia + mistério cósmico exclusivo do Mário | Curiosidade / janela nova / silêncio |
| **`jojo_exibido`** | Teatral / Ego Gigante (*JoJo* × *Persona*) | Contraposto extremo (quadril jogado pra um lado, tronco torcido pro outro), mão direita em pose angular perto do queixo/fone, esquerda estilizada pra fora, queixo erguido | Respiração lenta e teatral com pausas de "capa de revista"; dedos estilizados abertos | Pós-vitória / estilos `anime` e `street` |
| **`boxeador_pronto`** | Marrento de Arcade (*Street Fighter*) | Pés bem afastados em diagonal, **punhos fechados em guarda** na frente do tronco (sem cobrir o visor), quicando peso de um pé pro outro | Micro-esquivas laterais de cabeça (*bob & weave*); antenas apontadas à frente como radar | Teimosia / pós-queda forte / provocação |
| **`derretido_sono`** | Bateria em 1% (Pescando em Pé) | Curvado pra frente balançando como pêndulo lento, braços compridos pendurados soltos, antenas caídas pros lados, porta entreaberta num bocejo | **Assinatura cômica:** a cada ~4,5 s a cabeça cai pescando de sono e dá um **micro-tranco** acordando de susto | Tédio prolongado (antes de sentar/dormir) |

### Mapa de Migração de Perfis Legados (`configuracao.py`)
- `calm`, `confident`, `street`, `brc_stance`, `stylish` → `brc_malandro`
- `rhythm`, `vibing`, `playful` → `frenetico_groove`
- `curious`, `shy` → `espreita_armario`
- `fighter` → `boxeador_pronto`

---

## 3. Refino dos 15 Idles Existentes (Atuação + VFX nos 5 Estilos)

| Cena Existente | Refino de Atuação / Timing | Gatilho de VFX (Substantivo) | Tradução nos 5 Estilos |
| :--- | :--- | :--- | :--- |
| **`conferir_estilo`** | Segurar 0,25 s extras na pose final + micro-balanço de fones | 2–3 brilhos `✦` no pico | `blockbench`: pixels dourados · `street`: placa `FRESH!` · `anime`: *kirakira* + cruzinhas *smug* · `spiderverse`: hold 12 FPS + rabisco · `holograma`: varredura scanline |
| **`espreguicar_pesado`** | Aumentar contraste entre tensão máxima e alívio (porta entreabre 4°) | Vapor/suspiro curto na expiração | `blockbench`: puff leve · `street`: balão `...` · `anime`: linhas de alívio · `spiderverse`: linhas de esticamento · `holograma`: micro-distorção |
| **`olhar_curioso_chao`** | Inclinação extra de cabeça (12°) + pé avançando 1 passo curto | `?` discreto em `visor_lado` | `?` traduzido na mídia de cada estilo |
| **`conferir_luva`** | Aproximar o olhar e abrir/fechar os 4 dedos (`fingers`) em leque | 1 brilho `✦` na luva | Brilho discreto na mídia de cada estilo |
| **`pensar_gabinete`** | Leve batidinha de 1 dedo no queixo/lateral do gabinete | 3 pontinhos `...` em `visor_lado` | `blockbench`: 3 cubinhos · `street`: balão `...` · `anime`: nuvem pensativa · `spiderverse`: halftone · `holograma`: `LOADING...` |
| **`segurar_porta_timido`** | Tremor mais claro da porta antes de ele segurar com as duas mãos | Micro-estalo na `porta` + gota | `anime`: gota + tremor · `street`: `!` compacto · `blockbench`: puff mínimo |
| **`checar_walkman`** | Pausa nítida ao apertar o botão no cinto + aceno de aprovação | 1–2 micro-notas no fone | Micro-notas na mídia de cada estilo |
| **`alongar_pescoco_ombros`** | Micro-estalo seco no pico da rotação do pescoço/ombro | 1 micro-estalo no ombro | `blockbench`: 2 faíscas · `street`: mini `POP!` · `anime`: 3 riscos · `spiderverse`: riscos secos · `holograma`: glitch 1 frame |
| **`groove_um_pe`** | Sincronizar toque do pé levantado com pulso nos fones | Micro-onda no piso a cada 2 batidas | Versão reduzida (35%) de `acento_danca` |
| **`escutar_fone`** | Inclinar ouvido pro fone + 2 acenos ritmados | 1–2 micro-notas no fone ativo | Igual a `checar_walkman`, mais suave |
| **`batida_guardada`** | Antecipação curta nos joelhos antes do mini-bounce | Micro-pulso nos fones | Preparação para dança |
| **`disfarcar_olhar`** | Retorno rápido (snap cômico) quando flagrado | 1 gota de suor em `templo` | Gota/símbolo na mídia de cada estilo |
| **`ajeitar_fone`** | Empurrão firme com micro-rebote de cabeça pro lado oposto | Opcional (micro-estalo limpo) | Mantém leitura natural |
| **`fone_com_problema`** | 2 tapinhas secos na concha do fone + sacudida testando | 1–2 mini-estalos elétricos no fone | `blockbench`: faíscas ciano · `street`: `ZAP!` mini · `anime`: zigue-zague · `spiderverse`: faísca rabiscada · `holograma`: *sync tear* |
| **`argolas_antena`** | Olhar pra cima acompanhando a argola girar mais rápido | Micro-brilho nas argolas | Emissivo coerente com cada estilo |

---

## 4. Roteiros Fechados — 8 Novas Cenas e Ações Vivas

1. **`tentaculo_fujao` (`5.4 s`):** Algo mexe dentro do gabinete → porta abre `24°` → 1 tentáculo espia curioso → Mário olha pra baixo, leva mini-susto (`2.1 s`), empurra de volta, bate a porta fechada (`0°`) e disfarça olhando pra frente.
2. **`cuspir_item` (`1.85 s`):** Ejeção de rádio/caixas/futuros props: estufa abrindo a porta (`46°`) → projeta pra frente e **cospe o item em arco balístico** (com quique + `impacto_chao` aos `0.78 s`) → item **se ajeita naturalmente no lugar** enquanto Mário fecha a porta.
3. **`bater_pe_impaciente` (`5.2 s`):** Peso na perna esquerda, mãos na cintura, olhando de soslaio, pé direito batendo seco no chão 5 vezes (~`0.55 s` cada) com micro-puff sob a ponta do tênis → suspiro derrotado no final.
4. **`bater_pe_ritmo` (`5.6 s`):** Postura 3/4 relaxada, pé direito marcando o beat (~`112 BPM` ou BPM real), cabeça/fones em figura-de-8, *finger snap* no contra-tempo + micro-notas no fone.
5. **`solo_guitarra_ar` (`6.2 s`):** Base larga de rockstar, mão esquerda dedilhando rápido (`fingers2`), braço direito em 3 rajadas de palhetada larga, clímax aos `3.4 s` inclinado pra trás + cabeçada + **freeze de 0,5 s** (com moldura `ROCK!!` no `street`, *speedlines* no `anime`, hold 12 FPS + `SHRED!` no `spiderverse`).
6. **`finger_guns_camera` (`3.6 s`, ref: [`docs/referencias_idles/ref_finger_guns.jpg`](referencias_idles/ref_finger_guns.jpg)):** Vira direto pra câmera com inclinação marota de cabeça (`8°`), levanta as duas mãos espaçadas (sem cobrir o visor!) em *double finger guns* (`point` bilateral + polegares erguidos), dá **duplo clique de gatilho** aos `0.85 s` sincronizado com **brilho `✦` estalando ao lado da cabeça**, segura `0.75 s` e recolhe suave.
7. **`cacar_cursor` (`5.5 s` sucesso / `5.0 s` falha):** Espreita tipo gato → bote tentando agarrar o cursor próximo:
   - **Variante A (`cacar_cursor_sucesso`):** segura/foca o cursor (com escape imediato), **cutuca 3 vezes curioso** com o indicador direito (micro-estalos a cada cutucão) e solta satisfeito.
   - **Variante B (`cacar_cursor_falha`):** agarra o ar vazio, olha pras mãos, murcha ombros/antenas e **fica triste** (*gloom lines* no `anime`, `...`/`MISS!` no `street`, `404` no `holograma`).
8. **`roubo_cursor_tentaculo` (`4.8 s`, cooldown longo, escape imediato Win32):** Emboscada → porta escancara (`48°`) → tentáculo dispara e **puxa o cursor pra dentro** → porta bate fechada com o armário tremendo/mastigando (`1.8 s` max, cursor oculto com escape imediato por tecla/puxão) → estufa e **cospe o cursor de volta** com quique elástico + gotinhas de gosma.
