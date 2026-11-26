# Baseline de Testes de Animação (Etapa 1 — v2.0)

> Documento gerado antes de qualquer alteração da Etapa 2, registrando a rede de segurança comportamental construída sobre a versão estável atual das animações.

## Resumo da Validação

- **Suíte nova:** `tests/test_baseline_animacoes.py` (107 casos parametrizados + invariantes comportamentais).
- **Ajuste anti-fragilidade:** `tests/test_danca_clipes.py` desacoplado de contagens fixas (`425`, `17`) para invariantes comportamentais (deduplicação real de loop e densidade mínima de ciclo).
- **Execução completa isolada (`SEJOGA_CONFIG_PATH=$env:TEMP\sejoga_etapa1.toml`):** **1.191 testes passando (0 falhas, 0 skips)**, `ruff check` limpo (`All checks passed!`).

## Matriz de Cobertura da Baseline

1. **Todos os 35 `AnimationState`s via `AnimationController`:** varredura de 12–62 quadros por estado (incluindo os 9 anteriormente sem cobertura direta: `hang_loose`, `thumbs_up`, `rock`, `finger_gun`, `open_hands`, `close_fists`, `goku_teleport`, `peek`, `click`, e todas as 5 fases de `teimosia`), validando finitude de todas as rotações do rig e limites de `LegMotion`.
2. **`estados_delta.py` completo:** `delta_hover`, `delta_secundario`, `delta_indignacao`, `delta_sit`, `delta_jump`, `delta_sleep` (3 modos: `em_pe`, `sentado`, `deitado`) e todos os **22 ramos de `delta_conexao`** (início em zero, atividade no pico e encerramento sem resíduo).
3. **Catálogo JSON completo (`29` `loops/*.json` + `12` `acoes/*.json`):** finitude nos 3 eixos, emenda de loop nos 3 eixos, norma unitária de `quat_raiz`, `amostrar_clipe_completo` e clamping de todos os clipes não-loop (`baseball_hit`, `cover_to_stand`, `dodging_right`, `drop_kick`).
4. **Todas as 15 `CENAS_IDLE` (`cenas_idle.py`):** varredura em 30 Hz por toda a duração de cada cena, alternância de `variante`, envelopes de entrada/saída (`peso_mistura` em `[0, 1]`), finitude de rig/pernas/dedos e encerramento fora da janela.
5. **Reações e Teimosia:** `gestos_reacao.aplicar_defesa` (ambos os lados, impacto vs cutucada, sem hiperextensão de cotovelos) e `teimosia_pose.aplicar_fase` nas 5 fases (`resistencia`, `repreensao`, `bote`, `roubo`, `cospe`).
6. **Todas as 7 entradas (`animacao_entrada.py`) e 10 saídas (`animacao_saida.py`) em 60 Hz:** finitude de todos os campos (`offset`, `scale`, `roll/yaw/pitch`, `dissolve`, `afterimage`, `shock`, `warp_scale`, `door_open`, `head_yaw`), clamping para `t < 0` e `t > duration`, valores válidos de `locomotion` e assinaturas (`classic`, `cyberpsicopata_out`, `sandevistan_in`).
7. **`LegMotion` (`movimento_pernas.py`):** `walk`, `run`, acionamento de freada (`em_freada`), `fall`, `sleep` (3 modos), `dance` (procedural + emote), reações e 5 fases de `teimosia`.
8. **Dedos (`animacao/gestos_dedos.py`):** todos os 7 `GESTURES`, 5 `PEGADAS`, `ATIVIDADE_POR_ESTADO`, limites anatômicos por junta, monotonicidade de `pegada_de_curl` e convergência de `suavizar`.
9. **Módulos puros sem cobertura direta:** `squash_stretch.py` (preservação de volume `0.98 <= Sx*Sy*Sz <= 1.02` em todos os estados), `antenas_expressivas.py` (todos os `Humor`es e estados), `arcos_autorais.py`, `ritmo_humano.py` e `interpolacao.py`.
10. **Interseções críticas de estado:** `idle ↔ sit → drag`, `idle → jump → fall → land → idle`, `run → idle`, `dance → drag`, `sleep (sentado|deitado) → wake → idle` e `teimosia → idle`.

## Achados de Baseline Registrados para a Etapa 2

- **Overshoot negativo de joelho na inercialização Hermite (`movimento_pernas.py`):** durante trocas rápidas (ex.: `idle → walk` e `electro_swing`), a contribuição de velocidade `h10` não é clampada em `>= 0°`, causando breve hiperextensão de joelho (até `-13.2°`). A Etapa 2 aplicará clamp anatômico `>= 0°` em `_limitar_aducao_pernas` e apertará a asserção da baseline.
- **Snaps C0/C1 catalogados:** `jump` em `t=0.11s` (tronco, pernas e squash), `blue_balls` em `t=0.28s`, `teimosia/bote` em `bt=0.36s`, `SIT` excluído de `em_repouso` (respiração decai a zero sentado), `sandevistan_in`/`kagebunshin_in`/`goku_teleport_in`/`cyberpsicopata_out`/`goku_teleport_out`/`fnf_blue_balls`, `antenas_expressivas`, `movimento_corpo`, `movimento_danca` (SLERP de `raiz_quat_emote`), `cenas_idle` (compensação de tornozelo e curvas quínticas) e `danca_clipes` (suavização de `intro`, `raiz`, `quat_raiz` e emenda `intro → loop`).
