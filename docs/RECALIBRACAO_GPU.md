# Recalibração na GPU — Frente 3, Parte 3 (movimento dos membros)

> Cópia versionada de `.agents/tasks/frente3-animacao/recalibracao-gpu.md` (fora do git),
> para validar em outro PC. Corrigidos nomes corrompidos por caracteres de controle
> (`burst`, `frequencia_hz`, `angulo_empurrao_graus`). Capturas e o JSON de respostas
> citados abaixo continuam em `.agents/tasks/frente3-animacao/` (não versionados).

O ambiente de desenvolvimento é HEADLESS. O renderer real sobe e as capturas
saem, mas só o olho do usuário numa máquina com GPU diz se a pose está certa.
Teste verde não prova correção visual. Impossibilidade de validar visualmente em
headless não é regressão: é esta lista.

## Como rodar o calibrador interativo

A partir da raiz do worktree `frente3-animacao`, numa máquina com GPU e desktop.
Use um perfil isolado para não tocar nas configurações reais:

```
set SEJOGA_CONFIG_PATH=C:\tmp\sejoga-cal\config.toml
python tools/calibrar_interativo.py             # modo eixos (guiado)
python tools/calibrar_interativo.py --confirmar # modo confirmar (poses reais)
```

Clique na janela uma vez para dar foco ao teclado.

Modo eixos (mapa junta × eixo → direção). Escolha uma junta, gire um eixo e
aperte UMA tecla de direção para registrar o que o membro fez; o modo guiado
(`g`) pula sozinho para o próximo teste.

- Direção vista (na tela): `w` sobe, `s` desce, `a` esquerda, `d` direita,
  `f` frente, `t` trás, `i` dentro do corpo, `o` fora do corpo, `n` nenhum, `u` desfaz.
- Giro: setas cima/baixo giram o eixo; setas esq/dir ou `Tab` trocam a junta;
  `x`/`y`/`z` escolhem o eixo; `p` troca o passo; espaço alterna +45/-45/0;
  `backspace` zera o eixo, `r` a junta, `delete` tudo; `b` pula.
- `v` alterna visão frente/lado, `h` esconde a ajuda, `Enter` salva, `Esc` salva e sai.
- Saída: `mapa-eixos-CALIBRADO.json` e `.md` nesta pasta (`--saida` muda o
  destino; `--novo` ignora marcações salvas).
- Sem interação (checagem por PNG): `--capturar saida.png --teste ombro_dir:z:-45`.

Modo confirmar (recomendado, os itens C1 a C14 abaixo): ver a próxima seção.

## Como validar

Rode `python tools/calibrar_interativo.py --confirmar` (com o mesmo
`SEJOGA_CONFIG_PATH`).

Mostra cada pose REAL do app com uma pergunta. Teclas: `1` correto, `2` errado,
`3` pular, `v` troca frente/lado, setas navegam, `Esc` salva e sai. As respostas
ficam em `.agents/tasks/frente3-animacao/confirmacao-parte3.json` (`--novo`
recomeça; `--pose aceno` abre numa pose). Para cada `2`, anote uma linha do que
viu. Depois rode o app normal (`python -m sejoga`) e deixe-o em idle, arraste,
cutuque e deixe dormir.

Capturas já geradas aqui, do renderer real (câmera frontal e lateral), em
`.agents/tasks/frente3-animacao/capturas/parte3/`: `folha-antes.png` (commit
7233116), `folha-depois.png`, `antes-*.png`/`depois-*.png` por estado,
`folha-ik1.png` (só o IK novo) e `confirmar-*.png`. O `--capturar` grava após ~6
quadros: os gestos aparecem no começo do movimento. Ao vivo o gesto roda inteiro.

## Resumo do que você valida na GPU

- [ ] O1 Orientação de frente: no app normal e na vista `v` (frente/lado/costas),
  cabeça, tronco, braços, pernas e pés olham todos para o MESMO lado (para a
  câmera). Antes: pernas e pés de frente, o resto de costas. Olhe também 45° e 270°
  (`capturas/orientacao/corrigido__h045/h270.png` só foram conferidas por JSON).
- [ ] O2 Braços saindo do tronco: abertos, com ombro, braço e antebraço visíveis,
  não enfiados no tronco com só as mãos aparecendo.
- [ ] O3 Calibrador: abre, recebe teclado após um clique, HUD legível (acentos
  com `segoeui.ttf`), `1/2/3`, `v`, setas e `Esc` funcionam e o JSON é salvo.
- [ ] O4 Sinais de braços (C1, C2, C3, C7, C9): mão à frente, cotovelo dobra para
  a frente, braço esquerdo espelha o direito NA TELA, palma do aceno para a frente,
  ombro sem posição impossível.
- [ ] O5 Sinais do tronco (C5): clique cede para a frente, arraste inclina para o
  lado do braço segurado, cursor contra-gira ou acompanha, amplitude boa.
- [ ] O6 Anti-atravessamento (C4): braços/mãos não entram em tronco, short, pés,
  cabeça/fone nem no outro braço, em nenhuma pose.
- [ ] O7 Aceite de produto (C6): repouso, sono, cutucar, alongar e queda são
  distinguíveis e o repouso com braços abertos é aceitável.
- [ ] O8 Pernas e pés (C8) e caixa musical (C10): direção certa, sem se atravessar.
- [ ] O9 Desempenho percebido: sem engasgo no anti-atravessamento (pico ~41 ms
  medido corrigindo, mediana ~12 ms).
- [ ] O10 Peito (C11/C12): arraste pelo corpo, pela perna e pendurado pelo torso;
  peito em fase com braços e pernas, com balanço pequeno e sem cobrir os braços. Na
  queda também (aprovado pelo usuário: `delta_fisica` passou a depender de `hanging`).
- [ ] O11 Braços naturais (C13): idle sem abraço rígido; confira o quanto afundam na
  camiseta/short (trade-off medido: núcleo até 0,023 u dentro, casca até 0,053 u).
- [ ] O12 Flicker (C14): arraste pela perna e pelos braços sem piscar a janela.

## O que o usuário deve confirmar

Cada item: o que olhar, critério de aprovado/reprovado e a constante a mexer se
reprovar. Nenhum valor abaixo foi chutado para "parecer certo".

| # | Pose / situação | Aprovado se | Reprovado se → constante |
|---|---|---|---|
| C1 | `cutucar`, `arraste`, `repouso` (visão lado: `v`) | a mão vai à FRENTE do corpo e fica visível diante do tronco | mão atrás ou escondida → `arm_targets.ALVO_*` (eixo `z`) e `braco_tuning.POLO_COTOVELO_ANATOMICO` |
| C2 | Cotovelo em todos os gestos, visão lado | dobra só para a frente; o antebraço não gira de forma estranha | dobra para os lados/trás → `COTOVELO_MAX_GRAUS` (145), `TORCAO_BASE_ANTEBRACO_GRAUS` (90), `POLO_COTOVELO_ANATOMICO` (0.3, -0.6, -0.75) |
| C3 | Repouso, sono, queda, dança simétrica | o braço esquerdo é espelho do direito NA TELA | assimetria visível → `cinematica.espelhar_rotacao` (lei `(x,-y,-z)`) |
| C4 | Todas as poses do `--confirmar` | braço/mão não entram no tronco, short, pés, cabeça/fone nem no outro braço | atravessa → `FRACAO_NUCLEO_BRACO` (0.5), `FOLGA_PENETRACAO_U` (0.01), `FOLGA_EXTRA_CAIXA_U`, `colisao_bracos.CAIXAS_CORPO` |
| C5 | Tronco (clique, arraste pelo braço direito, cursor) | (a) clique: cede para a frente; (b) arraste pelo braço direito: topo inclina para o lado do braço segurado; (c) cursor: tronco contra-gira (padrão) ou acompanha; (d) amplitude boa | sentido trocado → `TRONCO_{YAW,PITCH,ROLL}_SINAL`, `TRONCO_OLHAR_YAW_SINAL` (-1 contra-gira, +1 acompanha); amplitude → `TRONCO_*_GANHO`, `SNAP_*` |
| C6 | **BLOQUEIO DE ACEITE.** Repouso, sono, cutucar, alongar e queda | os estados são distinguíveis entre si e o repouso com braços ABERTOS é aceitável | estados parecidos demais → ver abaixo |
| C7 | Pico do aceno | a palma fica para a FRENTE (para quem olha) | palma para trás → pose da mão em `rig.py` (aceno) e `tools/spec_gestos.SPEC_WAVE` |
| C8 | Pernas e pés (repouso, queda, dança, acordar, arraste pela perna) | pernas e pés movem-se para o lado certo e sem se atravessar | direção errada ou atravessa → ver abaixo |
| C9 | Limites do ombro (gestos extremos: alongar, aceno alto, arraste) | o ombro não vira para uma posição impossível | → `OMBRO_ELEVACAO_*_GRAUS` (-120/110), `OMBRO_AZIMUTE_*_GRAUS` (±120) |
| C10 | Caixa musical | nasce no lado, altura e orientação de antes | → `music_speaker.FACING_MASCOTE_GRAUS`/`FACING_CAIXA_EXTRA_GRAUS` |
| C11 | **Parte 4.** Peito ao ser ARRASTADO PELO CORPO, PELA PERNA e PENDURADO PELO TORSO (`python tools/capturar_arraste.py --saida <pasta>` gera as capturas; confirme ao vivo) | o peito segue o corpo, fica em fase com braços e pernas, tem um balanço próprio pequeno (não rígido) e NUNCA passa por cima dos braços | peito duro → subir `body_motion_tuning.PEITO_FATOR_PENDURADO` (0.3; 1.0 = defeito antigo, gira em dobro). Peito vai longe, dessincroniza ou cobre os braços → descer `PEITO_FATOR_PENDURADO` e/ou `PEITO_PENDURADO_MAX_GRAUS` (8). Gira em dobro só no começo da pega → `PENDURADO_LIMIAR` (0.05; é a condição única do renderer e do `delta_fisica`) |
| C12 | **Parte 4.** Queda (efeito colateral aprovado do `delta_fisica`: `hanging` também é alto na queda) | o peito cai junto com o corpo, sem girar em dobro | mesmas constantes de C11 |
| C13 | **Parte 4.** Braços em idle, sono, arraste, cutucar e queda | braços naturais, caídos e afastados do tronco (não em abraço rígido), sem atravessar cabeça, fone, pés nem o outro braço; tocar levemente camiseta/short é o trade-off aceito | braço ainda duro/abraçado → subir `braco_tuning.FOLGA_EXTRA_CAIXA_U` (tronco 0.03, quadril 0.03) e/ou baixar o `y` dos alvos em `arm_targets` (idle/sleep/drag/interaction/fall/drag_perna; lembrar de atualizar `rig_base.REPOUSO` = IK do idle). Braço afunda demais no tecido → descer `FOLGA_EXTRA_CAIXA_U`. `FRACAO_NUCLEO_BRACO` (0.5) quase não muda nada: medido |
| C14 | **Parte 4.** Flicker/piscar da janela ao arrastar PELA PERNA e PELOS BRAÇOS | a janela não redimensiona nem pisca durante o arraste | piscou pelo braço → incluir `'right-arm'`/`'left-arm'` na tupla de `arraste_por_pe` em `render/window.py::_fit_pose_window` (hipótese NÃO medida, por isso não está aplicada). Piscou pela perna → degrau mínimo `base * 2` na mesma função |
| C15 | **Parte A.** Frações e sobreposição dos segmentos do dedo (dedos fechados, vista frontal e lateral, com e sem contorno) | cada dedo dobra em 3 juntas (polegar 2) sem buraco nem costura visível na junta, textura contínua e pixelada | costura/buraco no lado externo → subir `dedos_tuning.ANGULO_PROJETO_SOBREPOSICAO_GRAUS` (55). Aba grande no lado interno → descer o mesmo. Junta no lugar errado → `FRACOES_SEGMENTOS_DEDO` (0.40/0.33/0.27) / `FRACOES_SEGMENTOS_POLEGAR` (0.55/0.45). Captura headless de dedos fechados NÃO mostra as juntas: validar ao vivo |
| C16 | **Parte A.** Flexão do bloco somada duas vezes (nó `fingers` gira E `GANHO_CASCATA_DO_BLOCO` soma a cascata); idle e gestos | a mão em idle e nos gestos confirmados não curva mais do que antes | dedo curva demais → descer `dedos_tuning.GANHO_CASCATA_DO_BLOCO` (1.0; 0 = só o giro duro do bloco) |
| C17 | **Parte A.** Gesto fecha a mão com `FATOR_FLEXAO_GESTO` | mão fechada de gesto parecida com o gesto aprovado (antes 80° em um único `setR`; agora 2.0× repartido = 160° somados) | fecha demais → descer `dedos_tuning.FATOR_FLEXAO_GESTO` (2.0; 1.0 = soma igual à antiga) ou os limites `LIMITES_JUNTA_DEDO_GRAUS`. Fecha de menos → subir |
| C18 | **Parte A.** Movimento secundário dos dedos no idle, andar, dança e gestos | dedos levemente vivos, onda base→ponta, nunca duros nem trêmulos | duro → subir `AMPLITUDE_SECUNDARIA_DEDO_GRAUS` (2.5/3.5/3.0) / `AMPLITUDE_SECUNDARIA_POLEGAR_GRAUS`. Trêmulo → descer `FREQUENCIA_SECUNDARIA_HZ` (0.35) e `FREQUENCIA_POR_ESTADO`. Onda não legível → `ATRASO_FASE_JUNTA_RAD` (0.75) / `ATRASO_FASE_DEDO_RAD` (0.55). Mãos em uníssono → `DESLOCAMENTO_FASE_LADO_RAD` (0.9) |
| C19 | **Parte A.** Repouso e distribuição da flexão entre juntas | mão relaxada levemente curva (mais no mindinho), meio dobrando mais; sem pose de régua nem de garra | reto demais/garra → `CURL_REPOUSO_DEDO_GRAUS` (7/11/7), `CURL_REPOUSO_POLEGAR_GRAUS`, `VARIACAO_REPOUSO_POR_DEDO`. Cascata pouco natural → `PESOS_FLEXAO_DEDO` (0.34/0.40/0.26), `PESOS_FLEXAO_POLEGAR` |
| C20 | **Parte B.** Tuning da onda por temperamento (`tentaculos/ondulacao.py`), idle e saída | calmo: ondas lentas e suaves; agitado: rápidas e amplas; ambos sinuosos, nunca tremidos | pouco sinuoso → subir `amplitude_lateral_px`/`amplitude_cima_px` do temperamento (calmo 7/4, agitado 16/10). Frenético/trêmulo → descer `frequencia_hz` (calmo 0.45, agitado 1.5). Onda não legível → `comprimento_onda` (calmo 1.1, agitado 0.65; menor = mais curvas). Silhueta estoura → descer as amplitudes |
| C21 | **Parte B.** Envelope `posição^expoente` (base parada, ponta solta) | base presa à cabeça sem arrastar a malha da cabeça; ponta solta | base se mexe demais → subir `expoente_envelope` (calmo 1.3, agitado 1.0). Ponta rígida e meio mole → descer o expoente |
| C22 | **Parte B.** Defasagem de π/2 entre plano lateral e vertical (`DEFASAGEM_PLANOS_RAD`) | ponta serpenteia em elipse, não vai e volta numa reta | movimento em reta/chicote → manter π/2 e subir `amplitude_cima_px`. Elipse larga demais → descer `amplitude_cima_px` ou `DEFASAGEM_PLANOS_RAD` |
| C23 | **Parte B.** Onda continua ao recolher (entrada pela porta), sem jitter | tentáculos ondulam enquanto entram e somem pela porta, sem congelar nem saltar no fim | congela/pula ao entrar → conferir `tempo_onda` e o ramo RETRACTING de `_atualizar_segmentos` em `tentacle_system.py`. Ondula demais ao entrar → descer as amplitudes do temperamento |
| C24 | **Parte B/C.** Espirro (`burst`) agora usa a MESMA onda (`ONDULACAO_ESPIRRO`); ramo antigo apagado | espirro com onda base→ponta, violento mas legível, parecido com o anterior confirmado | exagerado/fraco → `ondulacao.ONDULACAO_ESPIRRO` (amplitudes 22/14, `frequencia_hz` 0.8, `comprimento_onda` 0.85) e `coreografia_porta.SAIDA_ESPIRRO.duracao_s` (0.16). Pode ter mudado o formato do espirro (confirmado antes): se reprovar, avisar. Captura headless NÃO prova |
| C25 | **Parte C.** Empurrão: a ponta do empurrador encosta na porta e a abre em sincronia | ponta toca a porta fechada e ela abre junto; sem a porta abrir sozinha antes nem atravessar | porta abre antes/depois da ponta → `coreografia_porta.REVELACAO_INICIO_CONTATO` (0.10) e `REVELACAO_FIM_EMPURRAO` (0.35). Ponta não alcança a borda → fator 1 / `REVELACAO_FIM_EMPURRAO` do alvo em `_apontar_atuador` (aproximação linear) |
| C26 | **Parte C.** Qual tentáculo empurra/puxa (escolha minha: o primeiro sorteado / índice 0) | origem do empurrão/puxão legível | prefere outro → `_iniciar_empurrao(active[0])` e `_chamar_puxador` (`get_available(1)`) |
| C27 | **Parte C.** Saída por temperamento (`SAIDA_POR_TEMPERAMENTO`) | agitado sai violento, calmo lento (calmo igual ao de antes), tímido mais lento | pouco diferente → `duracao_s`, `escalonamento_s` por temperamento. Empurrão fraco/forte → `angulo_empurrao_graus` (calmo 60, agitado 85; precisa passar de `LIMIAR_SAIDA_PORTA_GRAUS` 50) |
| C28 | **Parte C.** Esquecimento: todos entram e a porta fica aberta | porta aberta parada, depois o puxador sai | pausa longa/curta → `ATRASO_ESQUECIMENTO_S` (1.6) |
| C29 | **Parte C.** Puxão rápido e solta | tentáculo agarra a borda e fecha rápido, solta e volta; porta termina de fechar sem prender nele | lento/rápido → `VELOCIDADE_PUXAO_GRAUS_S` (300), `MOLA_PUXADOR`/`AMORTECEDOR_PUXADOR` (ponta acompanha a porta). Solta cedo/tarde → `ANGULO_SOLTAR_PUXAO_GRAUS` (18). Porta fecha com o tentáculo ainda fora → `VOLTA_PUXADOR_S` (0.5) e `VELOCIDADE_FECHAR_FINAL_GRAUS_S` (40). Não alcança a borda → `ALCANCE_PUXADOR`, `TEMPO_ALCANCE_PUXAO_S` (0.7) |
| C30 | **Parte C.** O temperamento NÃO afeta o fechamento (escolha minha) | fechar sempre igual | quer variar → usar `SaidaTuning` no puxão |
| C31 | **Parte C.** Cancelamentos: espirro, caixa de som, fúria, engolir, esconder, pedido do rig > 5 graus | reações de antes iguais; porta não fica presa | porta presa/atrasada → `LIMIAR_PEDIDO_EXTERNO_GRAUS` (5), `LIMIAR_PORTA_FECHADA_GRAUS` (5), `TentacleDirector._outro_dono_da_porta` |
| C32 | **Parte C.** Borda livre da porta calculada do bounding box (dobradiça na origem do nó) | ponta do puxador na borda certa em todas as vistas | ponta fora da borda → `_ponto_borda_porta` (eixo e extremo) |

### C6: perda de gesto aceita sem sua confirmação

Limite MEDIDO do asset: nenhuma pose com o punho mais de 0.08 u abaixo do ombro
fica livre de atravessamento. O antebraço pendurado entra no SHORT (malha `legs`,
meia-largura 0.312, mais larga que a camiseta) e a mão (0.33 u, quase metade do
corpo) chega aos pés. O braço erguido ao lado da cabeça passa pelo fone (caixa
até x=0.394; o braço alcança x≈0.405).

Consequência na captura `folha-depois.png`: repouso, sono, cutucar, alongar e
queda ficam quase iguais, com os braços abertos em T, e o cutucar quase não se
distingue do repouso. Antes, esses estados eram distintos, mas com os braços
dentro do corpo. Trocar um pelo outro é decisão de produto, então depende de você.

Opções se reprovar C6 (escolher uma):

1. Aceitar o visual atual (braços abertos, gestos contidos).
2. Permitir mais casca no corpo: baixar `FRACAO_NUCLEO_BRACO` e regerar os alvos
   com `python tools/oraculo_cena.py --sugerir`. Braços descem e os gestos voltam
   a se diferenciar, ao custo de mais braço dentro do short/tronco.
3. Re-autorar os gestos para o espaço livre do asset (uma rodada própria).

Alvos antes × depois (punho relativo ao ombro: direita, cima, frente):

| alvo | antes (autoral) | depois (livre medido) |
|---|---|---|
| idle | (0.075, -0.265, 0.020) | (0.26, -0.08, 0.06) |
| wave | (0.110, 0.235, 0.030) | (0.23, 0.075, 0.03) |
| drag | (0.140, -0.080, 0.170) | (0.18, 0.00, 0.15) |
| drag_perna | (0.035, -0.272, 0.000) | (0.26, -0.08, 0.06) |
| stretch | (0.120, 0.180, 0.120) | (0.12, 0.08, 0.18) |
| dance | (0.150, 0.100, 0.150) | (0.15, 0.08, 0.17) |
| sleep | (0.050, -0.250, 0.080) | (0.24, -0.04, 0.10) |
| thrown | (0.160, 0.000, 0.160) | (0.16, 0.02, 0.16) |
| fall | (0.190, 0.030, 0.050) | (0.21, 0.03, 0.07) |
| interaction | (0.130, -0.020, 0.180) | (0.15, 0.02, 0.16) |

### C8: pernas e pés não foram migrados para a FK real (pendência)

`rig_mapa/rig_medidas.py` (modelo Y-up antigo, eixo longo -Y) continua medindo
pernas, pés e porta. Não foi migrado para `nucleo.cinematica`: o módulo é base de
`rig_debug`, `rig_articulacoes` e do console de diagnóstico, e a mudança de
quadro (Y-up → Z-up) alteraria a classificação de direções deles.

O que foi feito: o `PoseResolver` deixou de usar esse modelo para os braços (eles
têm `colisao_bracos` com a FK real) e só avalia os pares de pernas/pés
(`colisao_membros.PARES_PERNAS_PES`). `tests/test_colisao_pernas_pes.py` varre uma
grade de poses de pernas/pés (±25°) e confirma que essa correção NÃO empurra
nada. Ou seja: o modelo antigo não deforma as pernas. O que NÃO foi verificado:
se as pernas, quando movidas pelo IK de `lower_body` (sobre a malha), se movem
para o lado certo na tela. Isso é o que C8 pede para olhar.

Se C8 reprovar, a próxima rodada migra `rig_medidas` (ou só pernas/pés) para
`cinematica`, com eixo longo `-Z` nas pernas.

## O que foi medido aqui e o que não foi

Medido no grafo de cena do Panda (sem GPU), por `tests/test_cinematica_oraculo.py`
e `python tools/oraculo_cena.py`:

- A FK pura `nucleo.cinematica` iguala a posição/orientação dos nós do Panda
  (1e-4 u, 25 poses aleatórias, todos os grupos).
- O mapa de eixos (juntas × ±x,±y,±z → direção no mascote e na tela) sai
  automático em `mapa-eixos-OFICIAL.md`. Não há mais marcação manual de 96 eixos.
- A lei de espelho `(x, -y, -z)` funciona a nível de nó: o punho esquerdo é a
  imagem sagital do direito. Isso é só posição. NÃO está provado que o resultado
  é simétrico e anatômico NA TELA (C3), e o usuário contesta essa simetria. A
  conclusão anterior de que "elevação = roll" seria geometria real e não
  compensação do flip também não foi provada visualmente: o teste antigo
  (`test_eixos_bracos_tela.py`) só olha a câmera frontal, nunca a profundidade, e
  só prova que a pose não mudou.
- A causa que o usuário via foi medida no IK antigo: FK própria com ordem de
  rotação trocada, cotovelo no plano errado e "frente" invertida. Todos os alvos
  "mão à frente" renderizavam a mão ATRÁS do corpo (z<0). O `LagChain` do
  follow-through também fazia o antebraço receber os ângulos do ombro.

Não verificado (só na GPU): aparência final de qualquer gesto, conforto do
cotovelo, simetria percebida, atravessamento visual (as vistas laterais mostram
mãos à frente do tronco, e a captura não distingue posição correta de
atravessamento: C1/C4), sentido de produto do tronco, foco e teclado do
calibrador, fonte com acentos do HUD (`segoeui.ttf`), custo por quadro
(anti-atravessamento: ~2 ms em regime, mediana ~12 ms e pico ~41 ms corrigindo).

## O que mudou (estrutura)

- `nucleo/cinematica.py` (puro): FK idêntica ao Panda (`Rz(h)·Rx(p)·Ry(r)`,
  referencial de autoria +X direita, +Y frente, +Z cima). Lei de espelho única.
- Cadeia do braço com osso base: ombro (P, H, R) → cotovelo (dobradiça R, com
  torção-base de 90° em P, `TORCAO_BASE_ANTEBRACO_GRAUS`) → punho → dedos. Sem a
  torção, o R do antebraço abre o antebraço para os lados (para dentro do tronco).
  Efeito colateral: a textura do antebraço gira 90° no próprio eixo (C2).
- `animacao/arm_ik.py`: IK analítico sobre a FK real, com polo do cotovelo
  (`POLO_COTOVELO_ANATOMICO`). Erro 0 em todos os alvos, dos dois lados
  (`tests/test_arm_ik.py`).
- `animacao/colisao_bracos.py`: braços não atravessam o corpo (cápsulas com a FK
  real, caixas medidas nas malhas, correção mínima suave). O
  `Panda3DRenderer._resolve_arm_clearance` foi removido.
- Alvos de `arm_targets` regenerados por medição (o ponto livre mais próximo do
  autoral anterior). `REPOUSO` é a saída do IK do novo idle (teste garante).
- Tronco: os pivôs da coluna e o arraste agora usam o mesmo referencial de
  autoria (`flexible_rig.soft-spine-facing` e
  `renderer._rotacao_no_quadro_de_autoria`). Pitch/roll saíam invertidos em
  relação às juntas. Os ombros deixaram de girar em tesoura.
- Ficou de fora: dança (`dance_tuning`) e caminhada (`anim_clips`) usam ângulos
  absolutos da convenção antiga, agora com torção-base, clamp do cotovelo e
  anti-atravessamento, mas precisam de re-autoria visual. O breakdance gira o
  `_suspension_pivot` no quadro do mundo (não conjugado).

## Parte 4: aprovações e trade-offs registrados

- Aprovação do usuário: a mudança em `delta_fisica` (o peito pendurado deixa de
  girar em dobro) foi APROVADA, com `PEITO_FATOR_PENDURADO` acima de 0 (peito não
  deve ser rígido). A física do desktop não mudou; `hanging` já era entregue.
- Braços: o anti-atravessamento ganhou folga por caixa (`FOLGA_EXTRA_CAIXA_U`,
  só tronco e quadril) em vez de projeção rígida, e `arm_targets` foi ajustado
  (alvos mais baixos, idle ainda à frente). Penetração antes → depois no
  `diagnostico-parte4.md`. É o fecho da família C6: nenhum gesto foi perdido, ao
  custo de braço tocando mais a camiseta/short. Reprovou → C13.
