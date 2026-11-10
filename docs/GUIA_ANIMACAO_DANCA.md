# Guia de animação de dança — SeJogaDesktopCompanion

**Versão 2.0 — 05/11/2026.** Direção artística confirmada pelo autor. Este guia especifica o resultado desejado; a seção 9 distingue a especificação do que o código implementa. Uma funcionalidade descrita aqui não deve ser considerada pronta automaticamente.

## 1. Conceito aprovado pelo autor

Ao identificar música, o mascote prepara um **espirro lateral** e cospe uma caixa de som cartoon **maior que ele tanto em altura quanto em largura**. A caixa pousa ao lado/atrás dele e vira parte da encenação.

O head nod musical tem uma pose própria: personagem **de lado ou em três quartos**, **inclinado para trás**, com **as costas apoiadas na caixa**, **os dois braços cruzados na frente do corpo** e **as pernas apoiadas no chão**. A cabeça marca o ritmo com atitude relaxada. Apoiar uma mão numa caixa pequena não representa essa pose.

Para rock, executar **headbanging para baixo**, com um braço estendido para cima e **🤘 voltado à câmera**. Para hip hop e eletrônica, usar passos e frases reconhecíveis, transferência de peso e breakdance conforme andamento/energia. Não representar todas as danças pelo mesmo balanço do quadril.

Fones, porta, tentáculos e gosma são camadas secundárias. O corpo continua dançando enquanto elas atuam. Idle, aceno e troca de personalidade não substituem a dança em andamento; arraste e queda mantêm prioridade.

## 2. Música escolhe o estilo; BPM não comprova gênero

O sinal atual combina RMS, energia de graves, onsets e BPM estimado. Sons, timbres e padrões também importam. Usar os ranges como **heurísticas artísticas**, sempre com escolha manual disponível.

| Perfil observado | Seleção sugerida | Movimento |
|---|---|---|
| Energia baixa ou BPM incerto | Head nod | Postura apoiada, cabeça sutil, pernas estáveis |
| Cerca de 60–115 BPM e graves presentes | Hip hop | Bounce de joelhos, transferência de peso e braços em contrapeso |
| Cerca de 110–170 BPM e energia sustentada | Rock, quando coerente com o padrão | Base firme, headbang e mão 🤘 |
| Cerca de 118–145 BPM, pulso regular, energia alta | Groove eletrônico / breakdance | Passos marcados; chão apenas com energia sustentada |
| Energia muito alta e graves fortes | Breakdance | Toprock → descida → apoio → footwork/freeze → retorno |

A [Ableton descreve ranges típicos e relaciona gênero também aos sons e padrões](https://learningmusic.ableton.com/make-beats/tempo-and-genre.html). Essa fonte não valida os nossos limiares de RMS/graves como classificadores universais.

Requisitos do seletor:

- Suavizar energia e confiança do BPM; um pico isolado não dispara a frase de chão.
- Esperar uma frase adequada para trocar de estilo e permitir meia velocidade em BPM alto.
- Manter a dança escolhida enquanto a música continuar, sem sorteios que a cortem a cada oito segundos.
- Distinguir sessão de metadados, loopback e prévia silenciosa. Metadados sozinhos não medem graves.
- Tratar a grade de quatro batidas como estimada: o primeiro tempo real do compasso ainda não é reconhecido.

## 3. Caixa gigante: modelo, textura e staging

### 3.1 Proporções

Medir o mascote em pose neutra de apresentação, excluindo tentáculos, efeitos, eixos e props. Guardar essas dimensões; não redimensionar a caixa pela pose corrente ou pela pose T.

```python
# Especificação inicial, não API implementada.
speaker_width = character_rest_width * 1.20
speaker_height = character_rest_height * 1.15
speaker_depth = character_rest_width * 0.40
speaker_center_z = floor_z + speaker_height / 2
```

A largura e altura projetadas da caixa devem ser pelo menos as do personagem no enquadramento final. Ela fica no lado livre, com uma face de apoio atrás das costas. Mostrar personagem e alto-falantes em três quartos; não esconder a caixa inteira atrás dele.

A janela adaptativa acomoda o conjunto, mantendo escala de leitura do mascote. Caixa e chão ficam no espaço do cenário: a caixa não pode girar junto com o pivô de breakdance.

### 3.2 Aparência e textura

- Gabinete blocky, dois cones facetados, bordas e pequenas proteções; geometria de baixo custo.
- Base cinza/preta, detalhes rosa SeJoga, roxo e pequenos acentos ciano.
- Graffiti original com tag **SeJoga/SJ**, riscos e adesivos simples.
- Textura 128×128 ou 256×256, sem exigir PBR complexo; detalhes precisam funcionar no tamanho real de uso.
- Cones separados vibram no acento; o gabinete não salta nem perde o contato com o chão.
- Proposta original de decal: [fonte SVG](../assets/textures/speaker_graffiti.svg) e [textura PNG 256×128](../assets/textures/speaker_graffiti.png). Aplicada ao gabinete no runtime.

Friday Night Funkin' orienta cores, caixa grande e acentos rítmicos. A postura de costas apoiadas e a ejeção por espirro são próprias do SeJoga, não uma reprodução literal da Girlfriend.

## 4. Entrada: espirro lateral

Os tempos abaixo são pontos de partida para atuação, sujeitos a revisão visual.

| Fase | Tempo inicial | Atuação e restrições |
|---|---:|---|
| Perceber a música | 0–0,25 s | Olhar para o lado livre e preparar o tronco |
| Inspirações | 0,25–1,35 s | Duas/três preparações crescentes com pausas desiguais, sem parecer ataque |
| Abrir caminho | 1,15–1,45 s | Cabeça vira de lado e porta abre antes da passagem da caixa |
| Atchim lateral | 1,40–1,65 s | Contração curta para baixo/lado, braços recuam, perdigotos rosas no acento |
| Ejeção | 1,45–2,00 s | Caixa emerge comprimida, ganha tamanho cartoon e percorre um arco até o chão |
| Pouso | 1,95–2,30 s | Pequeno quique, reação do corpo e poeira rosa discreta |
| Entrar no loop | 2,20–3,00 s | Pés plantam, costas encontram apoio e braços se cruzam |

A deformação necessária para uma caixa gigante caber no armário é cartoon e pertence ao prop. Não reintroduzir escala acumulativa no corpo do mascote.

Depois do pouso, a caixa permanece no cenário durante a sessão e não nasce novamente a cada troca de dança. Ao parar a música, usar uma ação de saída/recolhimento legível. Controlar o espaço da abertura quando caixa e tentáculos compartilharem a porta.

## 5. Coreografias específicas

### 5.1 Head nod / head bopping — postura cool

- Corpo em três quartos, aproximadamente 35–60° em relação à câmera, rosto ainda reconhecível.
- Inclinação para trás inicial de 8–12°, feita pelo quadril/coluna e compensada nas pernas.
- Costas/ombro posterior em contato com a caixa, sem atravessar cabeça, fones ou tronco.
- Ambos os braços cruzados diante do peito: cotovelos dobram, um antebraço passa ligeiramente à frente do outro e mãos repousam sobre os braços.
- Peso principal em uma perna; outra relaxada, joelhos pouco flexionados e solas plantadas.
- Quadril quase estável. Não usar passos de caminhada nem giro contínuo do quadril.

Frase inicial de quatro batidas:

| Batida | Cabeça | Corpo e membros |
|---|---|---|
| 1 | Nod curto para baixo | Ombros recebem o acento; pés continuam plantados |
| 2 | Recuperação mais lenta e leve inclinação lateral | Pulsos/dedos acomodam com atraso pequeno |
| 3 | Segundo nod com amplitude um pouco diferente | Contrapeso da coluna sem perder o apoio das costas |
| 4 | Recuperação e pausa curta | Sustentar a pose de atitude sem flutuar |

Usar uma batida ou meia velocidade conforme o andamento. Uma variação pode soltar um braço para tocar a caixa, mas isso **não substitui** a pose principal de costas apoiadas e braços cruzados.

### 5.2 Rock / headbanging

- Pés em base firme um pouco mais larga; joelhos absorvem o acento.
- Cabeça prepara e contrai para baixo; recuperação mais lenta, sem girar pelo quadril como gesto principal.
- Braço estendido para cima, cotovelo quase aberto, sem atravessar cabeça/fones.
- Pulso compensa o antebraço e apresenta o gesto para a câmera.
- Indicador e mindinho estendidos; médio/anelar recolhidos; polegar acomodado junto dos dedos dobrados.
- Alternar o braço apenas em outra frase; manter a silhueta da mão estável durante o headbang.
- Em BPM alto, reduzir para meia velocidade em vez de vibrar a cabeça.

Porta/tentáculos acompanham com atraso limitado. Gosma responde a acentos esparsos; não abrir a porta nervosamente a cada amostra.

### 5.3 Hip hop / groove eletrônico

Construir frases com bounce dos joelhos, transferência de peso, plantio do pé e contrapeso dos braços. O tronco acompanha o peso; o quadril sozinho não define a dança.

Frase inicial de oito batidas: plantar e comprimir → transferir peso e estender braço oposto → fechar passo e preparar direção → pausa → repetir para o outro lado com variação → concluir em pose legível.

Eletrônica pode usar acentos regulares e poses geométricas; hip hop pode usar mais assimetria e recuperação atrasada. Isso é direção artística; a classificação do detector continua heurística.

### 5.4 Breakdance

| Batidas | Movimento | Contatos |
|---|---|---|
| 0–3 | Toprock com peso alternado e braços amplos | Pés alternam apoio |
| 4 | Agachar e preparar braço | Pés plantados; mão se aproxima do chão |
| 5–6 | Descer em arco | Mão planta antes de receber o peso |
| 7–8 | Freeze lateral legível | Mão fixa; perna livre compensa o centro de massa |
| 9–12 | Footwork circular / six-step estilizado | Mão e pé de apoio guiam os arcos |
| 13 | Freeze breve no acento | Sustentar pose sem parar o relógio musical |
| 14–15 | Replantar pés e subir | Transferir peso antes de soltar a mão |

Não tratar giro global como footwork pronto: uma mão plantada deve ficar fixa no cenário enquanto o corpo se movimenta em relação a ela. Cabeça/fones não viram apoio principal por acidente. Primeiro finalizar uma frase curta com peso; windmill completo vem depois.

O freeze pode começar com meia batida. Segurar a pose principal, sem congelar áudio, partículas, tentáculos ou o loop gráfico.

## 6. Fones, tentáculos e gosma

- Fones recebem atraso de mola pela velocidade/aceleração angular da cabeça, com amplitude limitada.
- Isolar peças/materiais dos fones para cor/textura reativa. Não deslocar UVs do atlas inteiro nem recolorir corpo, porta e rosto junto.
- Usar detalhe luminoso ou faixa de cor no acento, preservando a textura base.
- Tentáculos seguem os pivôs da cabeça e mantêm colisão com porta, corpo, caixa e entre si.
- Perdigotos/gosma respondem a picos esparsos, sem esconder mãos e cabeça.
- Partículas/trails vêm depois de postura, contatos e ritmo convincentes.

## 7. Contatos e arquitetura de referência

### 7.1 Apoio na caixa — correção da interpretação anterior

**Apoio principal: costas na caixa, não mão esquerda no tampo.** Esta seção substitui o significado do antigo título “Caixa de Som + Braço Esquerdo”, conforme a descrição completa do autor.

Definir uma superfície de apoio da caixa no cenário, dois contatos de pés e um contato de costas. Ajustar posição/coluna até as costas encontrarem a superfície, compensando pernas sem deslizar as solas. Preservar espaço para os dois braços cruzados à frente do peito.

Não resolver isso apenas com `solve_arm`: o solver atual aproxima a mão de um ponto e não resolve apoio das costas. A caixa precisa ser maior e o staging deve ser refeito antes de acertar ângulos finos.

### 7.2 Ordem das camadas

```text
Áudio → relógio musical → seletor → frase/pose-alvo
                              ↓
                 contatos de pés/costas/mãos
                              ↓
       raiz → quadril → coluna → pescoço → cabeça
                       → ombros → cotovelos → pulsos → dedos
                       → quadris → joelhos → pés
                              ↓
              molas / fones / porta / tentáculos
                              ↓
             enquadramento e composição da janela
```

Pseudocódigo de direção, **não API já implementada**:

```python
beat = beat_clock.sample(audio_features, dt)
style = selector.choose(audio_features, manual_override=settings.dance_style)
pose = choreography.sample(style, beat, session_phase)
if style == 'head_bob':
    contacts.pin_feet(stage.floor)
    contacts.support_back(stage.speaker.support_plane)
    pose.cross_both_arms()
    pose.nod_head(beat, downward_accent=True, lateral_attitude=True)
elif style == 'rock':
    contacts.pin_feet(stage.floor)
    pose.headbang(beat, allow_half_time=True)
    pose.raise_arm_and_present_horns(camera)
elif style == 'breakdance':
    contacts.apply(choreography.active_supports)
    pose.follow_authored_floor_phrase(beat)
secondary.apply_springs(pose, dt)
appendages.update_independently(dt, head_transform=pose.head)
```

Regras para implementação:

- Transformações relativas à pose base em pivôs procedurais dedicados, sem acumular escala/matriz entre frames.
- Preservar nomes/peças do GLTF; não redefinir matrizes importadas indiscriminadamente.
- Contatos em coordenadas de cena, convertidos para o pai da articulação; não misturar pixels e unidades do modelo.
- Um relógio compartilhado para corpo/pernas; pequeno atraso nas ações secundárias.
- Definir se o máximo do gesto ocorre no onset. O pulso atual atinge o máximo em `local=.21`, depois do início da batida.
- `1-exp(-dt*7)` é um filtro em segundos: constante ≈0,143 s e ≈0,329 s para 90%. Não significa sete frames.
- `u*u*(3-2*u)` é smoothstep; não chamar de ease-out nem chamar arco senoidal de parábola balística.

## 8. Referências pesquisadas: o que aproveitar

Consultadas em 05/11/2026. Os vídeos ficam como material para análise de movimento; não foram inventados timestamps nem alegada inspeção de frames que não foram visualizados.

| Referência primária | Aplicação no SeJoga | Limite |
|---|---|---|
| [FNF — documentação oficial](https://funkincrew.github.io/funkin-modding-docs/03-custom-characters/03-02-creating-a-character.html) | `danceEvery` em batidas e alternância `danceLeft`/`danceRight`; referência de código/dados | Não define nosso rig 3D nem apoio de costas |
| [FNF — dados oficiais da Girlfriend](https://github.com/FunkinCrew/funkin.assets/blob/main/preload/data/characters/gf.json) | Duas frases rítmicas distintas; consultar junto dos assets do projeto | Índices de frames não são ângulos do mascote |
| [Kotey Annan — Breakdance Animation Splinning](https://dannan.artstation.com/projects/9EVZlo) | Silhueta, leitura dos membros em movimento rápido e fones reagindo à bateria | O autor descreve uma passagem ainda em polimento |
| [Vídeo do estudo de Kotey Annan](https://www.youtube-nocookie.com/embed/LYPIXqCjHf0?feature=oembed&rel=0) | Conferir preparação, contatos, acentos e recuperação | O player não foi reproduzido nesta pesquisa; confirmar trechos antes de registrar timestamps |
| [Marta Dias/Rumpus — DOOM, entrevista na Toon Boom](https://www.toonboom.com/rumpus-animations-marta-dias-on-getting-metal-in-doom) | Atitude metal, poses-chave e exagero; estudo de shows citado pela própria animadora | Direção de atuação/estética, não ângulos prontos para nosso esqueleto |
| [Simon Tan — Hi-Fi Rush Animation Reel](https://vimeo.com/800548923) | Performances do próprio animador: preparação, pose clara e ações secundárias | Não é biblioteca automática de passos nem código de beat tracking |
| [Ableton — Tempo and genre](https://learningmusic.ableton.com/make-beats/tempo-and-genre.html) | Ranges típicos e relação entre padrões, sons e andamento | BPM sozinho não identifica gênero |

Para escolher um passo novo, selecionar um trecho curto e registrar quatro poses: preparação, contato/acento, sustentação e recuperação. Modelos de caixa, banco de imagens e sprites ajudam no design, mas não substituem referência de movimento.

## 9. Revisão do código atual: existente versus alvo

Snapshot do fonte em 05/11/2026. Consultar o relatório de build: o executável pode estar atrás do fonte.

| Área | Referência no código | Estado e diferença para o alvo |
|---|---|---|
| Análise | [`music.py`](../src/sejoga/musica/music.py), `_BeatTracker`, `_loopback_worker` | RMS/graves/onset/BPM estimado; sem reconhecimento confiável de gênero |
| Coreografia | [`dance_motion.py`](../src/sejoga/animacao/dance_motion.py), `DanceMotion`; [`dance_poses.py`](../src/sejoga/animacao/dance_poses.py); [`dance_frases_tuning.py`](../src/sejoga/animacao/dance_frases_tuning.py) | Quatro estilos em passos de quatro poses por batida (acento no onset, u = 0), braços por alvos de mão (IK) e molas por junta; ainda sem contatos de cena |
| Prioridades | [`animation.py`](../src/sejoga/animacao/animation.py), `update`, `interact` | Dança persiste e peek tem timer independente; preservar isso |
| Caixa | [`music_speaker.py`](../src/sejoga/musica/music_speaker.py), `MusicSpeaker` | Gabinete dimensionado pela pose neutra: largura ×1,20 e altura ×1,15; graffiti aplicado |
| Entrada | `MusicSpeaker.update` e [`window.py`](../src/sejoga/render/window.py), `update_appendages` | Preparação lateral, arco, pouso, três tentáculos empurrando e gosma rosa temporária; cones e ondas reagem à batida/graves |
| Head nod | `DanceMotion.apply` e `Panda3DRenderer.update_appendages` | Frase de 4 batidas (nod no 1 e no 3, inclinação lateral no 2, pausa no 4), costas inclinadas por `body.x` e apoiadas na caixa pelo renderer; braços em fallback "cruzado" (antebraços à frente do peito, sem cruzar o corpo) |
| IK | [`arm_ik.py`](../src/sejoga/animacao/arm_ik.py), `braco_para(modelo, lado, alvo, polo)` | Solver 3D de dois segmentos (alvo de mão para ombro e cotovelo); não resolve costas/pés ou apoio completo |
| Pivôs | [`rig_flexivel.py`](../src/sejoga/animacao/rig_flexivel.py), [`lower_body.py`](../src/sejoga/animacao/lower_body.py) | Coluna/pescoço/ombros e quadril/joelho no runtime; preservar junções ao resolver apoio |
| Pernas | [`leg_motion.py`](../src/sejoga/animacao/leg_motion.py) | Fase compartilhada; magnitudes `DANCA_*` por estilo (rock com base larga e joelho no acento, hip hop com quique); footwork/plantio ainda precisam de contatos de cena |
| Mãos | [`finger_gestures.py`](../src/sejoga/animacao/finger_gestures.py) | Dedos direitos e rock existem; falta polimento do braço estendido e alternância bilateral |
| Chão | `Panda3DRenderer.apply_body_motion`, `_giro_no_quadril` | Giro e roll conjugados no quadro de autoria, pivô no quadril, correção por bounds: **a mão ainda não fica fixa no cenário (atalho `shortcut:`), não é six-step completo** |
| Gosma | [`tentacle_drips.py`](../src/sejoga/tentaculos/tentacle_drips.py) | Gotas/spray existem; ligar aos acentos sem esconder a pose |
| Fones | Peças no GLTF | Material/textura reativa e atraso específico ainda pendentes |

## 10. Ordem de implementação e validação

1. Caixa maior, staging em três quartos e pose estática de costas apoiadas.
2. Entrada lateral com inspiração, porta, ejeção e pouso coordenados.
3. Head nod acabado: contatos de costas/pés, braços cruzados e frase de atitude.
4. Rock: braço alto, palma legível, dedos e headbang; depois fones/gosma.
5. Hip hop: bounce e transferência de peso com apoios.
6. Breakdance: uma frase curta com mão plantada; depois giros/variações.
7. Graffiti, reação de cones e partículas discretas.
8. Polimento de transições, desempenho, resize e executável.

Ferramentas existentes:

```powershell
python -m sejoga run
python tools/preview_body_actions.py music-soft music-hiphop music-heavy
python tools/profile_animation.py
python tools/smoke_native_body.py
python tools/smoke_bundle_dances.py
```

O menu tem **Prévia de dança (sem som)**. `tools/capture_dance_animation.py` e `--log-level DEBUG`, citados na versão 1.0, não existem no CLI atual (removidos), assim como `tools/profile_music_styles.py`.

Critérios de aprovação:

- Silhueta reconhecível no tamanho real de uso.
- Caixa maior em altura/largura; costas apoiadas no head nod e pés firmes.
- Sem deslizamento de apoio ou interpenetração relevante.
- Mão 🤘 legível para a câmera.
- Preparação, acento, sustentação e recuperação verificadas separadamente.
- Loop sem salto; entrada, saída e troca de estilos revisadas.
- Tentáculos não cortam a dança nem atravessam a caixa.
- Medir desempenho com/sem tentáculos; não inventar hardware ou porcentagem de CPU.
- Conferir executável e desktop composto, além do framebuffer do fonte.

## Histórico

- **1.0:** levantamento inicial de código e referências gerais.
- **2.0:** incorporada a descrição completa do autor: caixa gigante e costas apoiadas tornam-se requisitos explícitos. Estado do runtime separado da especificação; referências primárias e comandos existentes conferidos. A versão original foi preservada localmente em `.local/reference-inputs/GUIA_ANIMACAO_DANCA_v1.md`.
- **2.1:** as quatro danças re-autoradas em passos de quatro poses (acento, sustentação, recuperação, preparação) com acento no onset; braços por alvos de mão; breakdance com pivô conjugado no quadril; caminhos do código atualizados para o layout `src/sejoga/animacao`, `nucleo`, `musica`, `render`, `desktop` e `tentaculos`. Decisões em [DECISOES_ANIMACOES.md](DECISOES_ANIMACOES.md).

### Validação da entrada da caixa — 05/11/2026

A ferramenta `preview_music_scene.py` foi removida (limpeza ponytail); esta sequência: preparação, arremesso, pouso e pose final, vista em `tools/preview_body_actions.py`. Descrição original: preparação, arremesso, pouso e pose final em perfil isolado. Três tentáculos empurram alvos externos distintos na caixa e se recolhem; gosma rosa sólida low-poly escorre e desaparece até 6,5 s. A dança continua durante a sequência. Cones pulsam radialmente; ondas e tremor seguem energia/graves. Prévia permanece silenciosa; o pouso em música real respeita volume e áudio habilitado.
