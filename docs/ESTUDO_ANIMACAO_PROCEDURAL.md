# Estudo de animação procedural aplicado ao SeJogaDesktopCompanion

**Data:** 10/11/2026
**Tipo:** estudo e catálogo de técnicas. Nenhum código do projeto foi alterado.
**Público:** quem for mexer em `src/sejoga/animacao/`, `tentaculos/` ou no fio do fone.

## 0. Como ler este documento

- Seção 1: o que o projeto já tem, mapeado para o nome da técnica.
- Seção 2: fundamentos (tempo, easing, molas, integração).
- Seção 3: achados concretos no código atual (riscos e lacunas).
- Seção 4: catálogo de técnicas, cada uma com onde encaixa, esforço e risco.
- Seção 5: receitas por tema do projeto (música, mouse, física, fio, tentáculos, olhar).
- Seção 6: validação e ferramentas.
- Seção 7: roadmap priorizado.
- Seção 8: conhecimento de base das fontes (resumo escrito no próprio documento, sem links).
- Seção 9: limites do estudo (o que li e o que não li).

Este documento é autocontido: as ideias, fórmulas e algoritmos vêm explicados no
texto. Os nomes de autores e palestras aparecem só como crédito.

Convenção de esforço: **P** (horas), **M** (1 a 3 dias), **G** (semana ou mais).
Risco = chance de mexer na aparência já calibrada ou quebrar teste existente.

Os trechos de código abaixo seguem a convenção do projeto (português, type hints,
constantes em `*_tuning.py`). São ilustrações para o estudo, não código aprovado.

---

## 1. O que o projeto já tem (mapa técnica → módulo)

| Técnica (nome na literatura) | Onde está | Observação |
|---|---|---|
| Mola subamortecida com solução analítica | `body_motion.Spring` | Independe de FPS. Base de quase tudo. |
| Mola por junta (3 eixos) | `joint_springs.JointSpring`, `SpringPose` | Tabela de tensão em `spring_tuning.py`. |
| Follow-through / overlapping action | `joint_springs.LagChain` | Braço → antebraço → mão → dedos em cascata. |
| Camadas aditivas com prioridade | `anim_layers.LayerStack`, `CamadaDelta`, `Prioridade` | Estados produzem deltas sobre a base. |
| Pose base única (rest pose) | `rig_base.py` | Fonte única dos valores de repouso. |
| Resolução final (blend, colisão, clamp) | `pose_resolver.PoseResolver` | Aplicado uma vez, no fim. |
| IK analítico de 2 ossos | `limb_ik.solve_arm` | Plano 2D. |
| IK 3D por alvo de mão | `arm_ik.py`, `arm_targets.py` | Não li o conteúdo; ver seção 9. |
| IK de pernas / apoio dos pés | `lower_body.py`, `leg_motion.py` | Não li o conteúdo. |
| Giro de corpo limitado por mola | `body_motion.GiroCorpo` | Zona morta + clamp + mola. |
| Respiração (oscilador lento) | `respiracao.py` | |
| Atenção / olhar | `attention.py`, `foco_atencao.py` | |
| Dança dirigida por música | `dance_motion.py`, `dance_tuning.py`, `musica/` | RMS + onset; BPM inicial. |
| Keyframes autorados no runtime | `idle_clips.py`, `anim_clips.py` | Híbrido: autorado + procedural. |
| Cadeia articulada com torção | `tentaculos/` | 12 juntas, Catmull–Rom, cápsulas de contato. |
| Física 2D de tela | `desktop/physics.py` (Pymunk) | Alimenta o corpo procedural. |

Leitura geral: o projeto **já é uma arquitetura procedural em camadas**, com decisão
registrada de não usar ossos com skin nem Mixamo (modelo de partes rígidas, runtime reativo).
Este estudo não propõe trocar isso. Propõe refinar e preencher lacunas.

---

## 2. Fundamentos

### 2.1 Animação procedural em uma frase

A pose de cada frame é **calculada** a partir de parâmetros (tempo, velocidade, alvo,
estado, música), e não lida de uma sequência de quadros-chave. Na prática quase todo
sistema real é híbrido: poses autoradas como alvo, comportamento procedural como
filtro, reação e correção.

Três famílias de ferramentas cobrem 95% dos casos:

1. **Geradores**: funções do tempo (seno, ruído, curvas). Dão vida contínua.
2. **Filtros dinâmicos**: molas, amortecedores, Verlet. Dão peso, inércia, atraso.
3. **Solucionadores**: IK, restrições, colisão. Dão precisão geométrica.

O projeto usa bem a 2 e a 3. A família 1 aparece em respiração e dança.

### 2.2 Tempo

- **Passo variável (dt do frame)**: serve para tudo que tem solução analítica
  (as molas atuais). Resultado igual em 30, 60 e 120 Hz.
- **Passo fixo com acumulador**: obrigatório para integração numérica
  (Verlet, Euler semi-implícito, cadeias com restrições). Sem isso, o fio do fone
  vai se comportar diferente conforme o FPS.
- **Limitar dt**: quando o app trava (arraste de janela, GPU ocupada) o próximo dt
  pode ser enorme. Limitar a algo como 1/20 s evita saltos e explosão numérica.
  Molas analíticas toleram, mas o *efeito visual* de um dt de 500 ms ainda é um salto.

### 2.3 Easing e curvas

| Curva | Fórmula (u em 0..1) | Uso |
|---|---|---|
| Linear | `u` | Quase nunca. |
| Smoothstep | `u*u*(3-2u)` | Transições curtas simétricas. |
| Smootherstep (quíntica) | `u*u*u*(u*(6u-15)+10)` | Retorno suave; já usado nos idles. |
| Ease-out expo | `1-2^(-10u)` | Reação rápida que assenta. |
| Overshoot (back) | `1+c3*(u-1)^3+c1*(u-1)^2` | Antecipação/arremate de gesto. |
| Arco senoidal | `sin(pi*u)` | Sobe e desce (pulo, aceno). |

Nota já registrada em `GUIA_ANIMACAO_DANCA.md`: smoothstep não é ease-out e arco
senoidal não é parábola balística. Manter os nomes honestos.

### 2.4 A mola como primitiva universal

Um oscilador amortecido `x'' = -k(x - alvo) - c x'` parametrizado por **frequência**
`f` (Hz) e **razão de amortecimento** `zeta`:

| zeta | Comportamento | Uso típico |
|---|---|---|
| 0 | Oscila para sempre | Nunca em personagem. |
| 0.3 a 0.6 | Balança vários ciclos | Dedos, fones, gelatina, "juice". |
| 0.6 a 0.85 | 1 a 2 balanços, assenta | Braços, cabeça, corpo vivo. |
| 1.0 | **Crítico**: mais rápido sem overshoot | Câmera, olhar, UI, correções. |
| > 1 | Lento, sem overshoot | Peso morto, objetos pesados. |

Regras práticas:

- Frequência controla **velocidade**. Zeta controla **personalidade**.
- Overshoot percentual de uma mola subamortecida: `exp(-pi*zeta/sqrt(1-zeta^2))`.
  Para zeta 0.72 dá cerca de 3%; para 0.40, cerca de 25%. O `spring_tuning.py` já
  documenta overshoot-alvo por junta; essa fórmula permite derivar zeta de um
  overshoot desejado em vez de chutar.
- **Impulso**: somar à velocidade (`mola.velocity += impulso`) é a forma mais barata
  de reagir a evento (clique, batida, pouso). Sem keyframe, sem estado, e o assentamento
  é automático.
- **Alvo móvel**: a mola persegue qualquer alvo, inclusive alvo que muda a cada frame.
  É isso que faz o rastreio do cursor parecer vivo.

### 2.5 Parametrização por meia-vida (recomendada para novas molas)

Frequência e zeta são ruins para ajuste fino. Uma alternativa de Daniel Holden: a
**meia-vida** (tempo para cobrir metade da distância restante) numa mola criticamente
amortecida. Um número, intuitivo, sem caso especial de zeta = 1.

```python
from math import exp, log

EPSILON_MEIA_VIDA = 1e-5


def meia_vida_para_amortecimento(meia_vida: float) -> float:
    """Converte meia-vida (s) no coeficiente de amortecimento da mola crítica."""
    return (4.0 * log(2.0)) / (meia_vida + EPSILON_MEIA_VIDA)


def avancar_mola_critica(
    valor: float,
    velocidade: float,
    alvo: float,
    meia_vida: float,
    dt: float,
) -> tuple[float, float]:
    """Avança uma mola criticamente amortecida pela solução exata (sem overshoot)."""
    y = meia_vida_para_amortecimento(meia_vida) / 2.0
    j0 = valor - alvo
    j1 = velocidade + j0 * y
    decaimento = exp(-y * dt)
    novo_valor = decaimento * (j0 + j1 * dt) + alvo
    nova_velocidade = decaimento * (velocidade - j1 * y * dt)
    return novo_valor, nova_velocidade
```

Derivação conferida à mão: `x(t) = (j0 + j1 t) e^(-y t) + alvo` com `j1 = v0 + y j0`,
logo `v(t) = e^(-y t) (v0 - y j1 t)`. Bate com o trecho acima. Não rodei o código.

**Correspondência com a `Spring` do projeto.** A mola do projeto usa frequência `f`
(Hz) e razão de amortecimento `zeta`. Na forma física (rigidez `s`, amortecimento `d`):

| Grandeza | Fórmula |
|---|---|
| `omega` | `2 * pi * f` |
| Rigidez `s` | `omega²` |
| Amortecimento `d` | `2 * zeta * omega` |
| Razão de amortecimento | `zeta = d / (2 * sqrt(s))` |
| Decaimento `y` | `d / 2` (= `zeta * omega`, que no código é `decay`) |
| Frequência da oscilação `w` | `sqrt(s - d²/4)` (= `omega * sqrt(1 - zeta²)`, que no código é `oscillation`) |
| Meia-vida da mola crítica | `d = 4 * ln(2) / meia_vida`, ou seja `y = 2 * ln(2) / meia_vida` |

O sinal de `s - d²/4` define o regime:

- `> 0`: **subamortecida** (oscila). É o único regime que `Spring.update` trata.
- `= 0`: **crítica** (volta o mais rápido possível, sem oscilar).
- `< 0`: **superamortecida** (volta devagar, sem oscilar).

As soluções analíticas de cada regime têm formas diferentes:

| Regime | Posição ao longo do tempo |
|---|---|
| Subamortecido | `j * e^(-y t) * cos(w t + p) + c` |
| Crítico | `(j0 + j1 t) * e^(-y t) + c`, com `j0 = x0 - c` e `j1 = v0 + j0 * y` |
| Superamortecido | `j0 * e^(-y0 t) + j1 * e^(-y1 t) + c` (duas taxas de decaimento) |

Aqui `c = alvo + (d * v_alvo) / s` é o ponto de equilíbrio (igual ao alvo quando a
velocidade-alvo é zero). Isso explica o achado 3.1: o código do projeto divide por
`w`, que é zero no regime crítico e imaginário no superamortecido.

**Variantes mais baratas da mesma mola crítica** (todas com `eydt = exp(-y * dt)`):

- *Com velocidade-alvo zero:* a função `avancar_mola_critica` acima.
- *Com alvo zero (mola de decaimento):* `j1 = v + x * y`; `x = eydt * (x + j1 * dt)`;
  `v = eydt * (v - j1 * y * dt)`. É a mola certa para fazer um desvio sumir
  (inertialização, seção 4.3).
- *Pré-cálculo:* quando várias molas compartilham a mesma meia-vida e o mesmo `dt`
  (por exemplo, todas as juntas da mesma região), `y` e `eydt` podem ser calculados
  uma vez por frame.
- *Aproximação de `exp(-x)`:* `1 / (1 + x + 0.48x² + 0.235x³)`. Útil em C++; em
  Python o `math.exp` já é rápido o bastante para ~20 juntas a 60 Hz.

**Mola de amortecedor simples ("lerp exato").** Para suavizar um valor sem
velocidade própria (não oscila, mas muda de direção de forma brusca quando o alvo
inverte), a forma independente de FPS é:

```python
from math import exp, log

def suavizar_exato(valor: float, alvo: float, meia_vida: float, dt: float) -> float:
    """Aproxima o valor do alvo por decaimento exponencial, igual em qualquer FPS."""
    fator = 1.0 - exp(-(log(2.0) * dt) / (meia_vida + EPSILON_MEIA_VIDA))
    return valor + (alvo - valor) * fator
```

Por que não usar `lerp(valor, alvo, 0.1)` por frame: o resultado muda com o FPS (a
30 Hz chega na metade do ritmo de 60 Hz). Corrigir com `fator = taxa * dt` parece
resolver, mas explode quando `taxa * dt > 1`, e duas aplicações de `dt/2` não valem
uma de `dt`. O decaimento exponencial acima não tem nenhum dos dois defeitos.
Desvantagem: sem velocidade própria, então o movimento muda de sentido de uma vez
quando o alvo inverte. Para olhar e cursor, prefira a mola com velocidade.

### 2.6 Integração numérica (quando não há solução analítica)

| Método | Estabilidade | Quando usar |
|---|---|---|
| Euler explícito | Ruim, ganha energia | Evitar. |
| Euler semi-implícito (velocidade primeiro) | Boa | Partículas, gotas de gosma. |
| Verlet posicional | Muito boa, restrições fáceis | Fio do fone, cordas, tecido. |
| Solução analítica (mola) | Exata | Qualquer mola linear. |

**Por que a mola por Euler ingênuo falha.** A forma
`v += dt * (rigidez * (alvo - x) + amortecimento * (v_alvo - v)); x += dt * v`
(Euler semi-implícito) funciona com `dt` pequeno, mas fica instável quando
`dt * rigidez` ou `dt * amortecimento` crescem, e os parâmetros brutos não dão
intuição. A solução analítica elimina as duas coisas, e é por isso que o projeto
acertou ao usá-la.

### 2.7 Variantes de mola úteis ao projeto

Todas derivam da mola crítica (`avancar_mola_critica`) ou de composições dela.

| Variante | Ideia | Uso no projeto |
|---|---|---|
| **Dupla** | Uma mola persegue o alvo e uma segunda persegue a primeira (cada uma com metade da meia-vida). O arranque deixa de ser íngreme e a curva ganha formato de "S". | Início suave de gestos (aceno, virada de cabeça) sem keyframe de ease-in. |
| **Temporizada** | Para chegar ao alvo em um tempo `T`, a mola persegue um ponto que anda em linha reta até o alvo, adiantado pelo atraso da mola. O atraso de uma mola crítica seguindo um alvo em velocidade constante é `meia_vida / ln(2)`. | Fazer uma mão chegar ao alvo do IK numa batida exata da música. |
| **De velocidade** | Mesmo truque, mas o ponto intermediário anda a velocidade constante em vez de a tempo constante. | Limitar a velocidade máxima de um membro (evita braço "teleportando" em alvo distante). |
| **Quaternion** | Converte a diferença entre rotações em vetor de eixo-ângulo escalado, aplica a mola crítica nele e converte de volta. A diferença é calculada como `atual * inverso(alvo)`. | Ombros e cabeça, se houver migração para quaternions (4.9). |
| **De escala** | Mesma ideia aplicada à escala, em escala logarítmica para não inverter. | Squash e stretch (4.4). |
| **Extrapolação** | Estima a posição futura de algo que perde velocidade por decaimento exponencial: `x_futuro = x + (v / y) * (1 - exp(-y * t))`, com `v_futuro = v * exp(-y * t)`. | Prever onde o mascote vai parar após o arremesso, para preparar a pose de pouso antes do impacto. |
| **Controlador** | Usar a mola na *velocidade* (a posição da mola vira a velocidade do personagem, a velocidade da mola vira a aceleração). Como a solução é exata, dá para avaliá-la com um `dt` grande e prever o futuro sem simular os passos intermediários. | Suavizar a velocidade de caminhada e prever a trajetória nos próximos 0,5 s para antecipar o pouso. |
| **Ressonância** | Uma mola alimentada por um sinal na sua frequência própria acumula energia; fora dela, perde. Energia = `(v² + s * (x - repouso)²) / 2`. Com várias molas em frequências diferentes dá para saber qual frequência domina um sinal, sem FFT. | Estimar o andamento da música com um banco de molas, alternativa leve ao detector de onset. Meia-vida longa = seletivo, curta = tolerante. |
| **Filtro / suavização** | Uma mola de meia-vida pequena remove ruído e saltos de qualquer sinal. | Suavizar a velocidade do HWND no arraste, o cursor, e o nível de RMS da música. |

Observação sobre a "frequência" dessas molas: com amortecimento, a frequência de
oscilação real difere da frequência nominal (é `sqrt(s - d²/4)`, não `sqrt(s)`).
Por isso `f` na tabela de tensão é uma frequência *nominal*, e o overshoot medido é
a verificação honesta.

---

## 3. Achados no código atual

Leitura de `body_motion.py` (até a classe `BodyPose`), `joint_springs.py`,
`anim_layers.py`, `pose_resolver.py`, `spring_tuning.py` e `limb_ik.py`.
Nada abaixo foi reproduzido em execução. São conclusões de leitura.

### 3.1 `Spring.update` quebra para zeta ≥ 1 e frequência 0

`oscilacao = omega * sqrt(1 - zeta^2)` e depois divide por `oscilacao`.

- `zeta == 1.0`: divisão por zero.
- `zeta > 1.0`: `sqrt` de número negativo (erro de domínio).
- `frequency == 0`: `omega = 0`, divisão por zero.

Hoje não explode porque a maior zeta da tabela é 0.9 (`body`, `legs`, `GiroCorpo`).
É uma armadilha latente: quem calibrar um valor "mais seco" para 1.0 derruba o app.
Duas saídas possíveis:

- Validar a faixa na construção (`0 < zeta < 1`, `frequencia > 0`) e falhar cedo.
- Ou adicionar ramos críticos e super-amortecidos à solução analítica.

Também: `Spring.update` só protege `dt <= 0`; `JointSpring.atualizar` protege
`dt` não finito, mas `Spring.update` usado direto (ex.: `GiroCorpo`) não.

### 3.2 O crossfade zera a velocidade na troca de estado

`PoseResolver.iniciar_transicao` chama `self._crossfade.definir(pose_atual)`, e
`JointSpring.definir` grava `velocity = 0.0`. O docstring promete "continuidade de
velocidade", mas a velocidade é descartada. Efeito esperado: um braço que estava
em pleno balanço para quando o estado muda e depois recomeça. É o tipo de
"tranco" que o usuário descreve sem conseguir nomear.

Correção mínima: preservar a velocidade da mola em `definir` ao iniciar a
transição (opção A da seção 4.3). Correção estrutural: **inertialização** (opção B).
Ressalva: uma mola que só persegue um alvo novo já é contínua em posição e
velocidade por construção, então o tranco vem exatamente do `definir` e do frame
"segurado" em `_aplicar_crossfade`. Não confirmei o que `animation.py` passa como
`pose_atual`.

Verificação sugerida antes de mexer: gravar `|d pose / dt|` no frame anterior e no
posterior a uma troca de estado e medir o salto.

### 3.3 Limites rígidos criam parada seca

`_aplicar_clamps` usa `max/min`. Quando o alvo passa do limite, a junta bate
numa parede: velocidade vai a zero de um frame para o outro. Para membros em
movimento (dança, aceno) é visível. Alternativa: limite suave (seção 4.7).
Para clamp de segurança (evitar atravessar o corpo) o rígido continua válido
como última linha.

### 3.4 Soma de ângulos de Euler

`LayerStack.compor` e `MixerCamadas.compor` somam `x`, `y`, `z` por camada.
Funciona para deltas pequenos e é o que torna as camadas simples. Limites:

- Rotações de Euler não comutam; somar não equivale a compor rotações.
- Perto de 90° no pitch há gimbal lock.
- Os clamps de braço chegando a ±180° já são sintoma de que a faixa útil do
  braço usa ângulos grandes.

Não é urgente. Se aparecerem "braços girando para o lado errado" em combinações
de camadas, o caminho é compor por quaternion só nas juntas de ombro (seção 4.9).

### 3.5 Molas de ângulo não escolhem o caminho curto

`Spring` trata o valor como escalar. Se o alvo cruzar ±180°, a mola gira o
caminho longo. Hoje `GiroCorpo` está limitado a ±90°, então não ocorre. Vale a
função de ângulo mais curto (seção 4.8) antes de qualquer giro amplo.

### 3.6 `limb_ik.solve_arm`

Resolve só o plano e devolve sempre a mesma orientação do cotovelo. Não tem polo.
O trabalho 3D está em `arm_ik.py`, que não li. A memória do projeto registra que a
estrutura do IK foi aprovada mas o resultado visual ainda não, com hipótese de
espelhamento por `MODEL_FACING_HEADING = 180`. Isso é problema de **convenção de
eixos**, não de algoritmo; nenhuma técnica deste catálogo substitui a verificação
visual multi-ângulo já definida.

### 3.7 Pontos positivos a preservar

- Molas analíticas independentes de FPS.
- Tabela de tensão única com invariantes testados (corpo ≥ dedos).
- Falha cedo em `spring_tuning.py` se o rig ganhar grupo sem entrada.
- Clamps e colisão num único ponto (`PoseResolver`).
- Pose base única (`rig_base`).

---

## 4. Catálogo de técnicas

### 4.1 Impulso e "juice" por eventos (esforço P, risco baixo)

**O que é:** reagir a um evento somando velocidade a uma mola em vez de tocar um clipe.

**Onde encaixa:** clique, duplo clique (já usa), batida de música, pouso, colisão
com borda de janela, troca de música, notificação.

```python
def aplicar_impulso(mola: Spring, intensidade: float, limite: float) -> None:
    """Soma velocidade à mola, limitada para o impulso não estourar a pose."""
    mola.velocity = max(-limite, min(limite, mola.velocity + intensidade))
```

Dicas:
- Escalar por energia: batida forte, impulso maior.
- Alternar sinal (esquerda/direita) para evitar padrão repetido.
- Limitar com `limite` para dois eventos seguidos não somarem além do aceitável.

### 4.2 Follow-through, arrasto e sobreposição (P, baixo)

Já existe em `LagChain`. Melhorias possíveis:

- **Atraso por velocidade, não só por posição**: a ponta reage ao *movimento* do pai.
  Pegar a aceleração angular da cabeça para balançar fones e antena (a guia de
  dança já pede isso na seção 6).
- **Atenuação por junta**: `CADEIA_ATENUACAO` já reduz a frequência ao longo da cadeia.
- Parar a cadeia em cascata (série de molas) acumula atraso de fase. Se a ponta
  ficar atrasada demais, usar *todas as juntas perseguindo o mesmo alvo* com
  frequências diferentes (paralelo), em vez de cadeia em série.

### 4.3 Inertialização em vez de crossfade (M, médio)

**Problema que resolve:** o achado 3.2.

**Ideia (David Bollo, Gears of War 4, GDC 2018):** o crossfade clássico avalia as duas
animações (a que sai e a que entra) e mistura. A inertialização avalia **só a nova**.
No instante da troca registra o desvio entre o que estava sendo exibido e a nova pose
(posição e velocidade), passa a exibir `pose_nova + desvio` e faz o desvio **decair a
zero**. Como a velocidade do desvio entra na conta, o movimento não para nem arranca
de repente. Na versão original o desvio some por um polinômio com duração fixa; com
mola crítica (versão de Daniel Holden) não há duração fixa, mas o decaimento é
exponencial, suave e some rápido, e o código fica mínimo.

Para cada eixo de cada junta, com `origem` o valor do fluxo que estava tocando,
`destino` o valor do novo fluxo e `desvio` o desvio ainda ativo:

```python
def registrar_transicao(
    desvio: float,
    velocidade_desvio: float,
    origem: float,
    velocidade_origem: float,
    destino: float,
    velocidade_destino: float,
) -> tuple[float, float]:
    """Novo desvio e velocidade do desvio no instante da troca de estado."""
    # Soma o desvio que ainda estava ativo: trocas em sequência não dão salto.
    novo_desvio = (origem + desvio) - destino
    nova_velocidade = (velocidade_origem + velocidade_desvio) - velocidade_destino
    return novo_desvio, nova_velocidade


def avancar_decaimento(
    desvio: float,
    velocidade: float,
    meia_vida: float,
    dt: float,
) -> tuple[float, float]:
    """Faz o desvio decair a zero por mola crítica (alvo zero)."""
    y = meia_vida_para_amortecimento(meia_vida) / 2.0
    j1 = velocidade + desvio * y
    decaimento = exp(-y * dt)
    return decaimento * (desvio + j1 * dt), decaimento * (velocidade - j1 * y * dt)
```

Cada frame: `desvio, velocidade = avancar_decaimento(...)` e a saída é
`valor_do_fluxo_novo + desvio` (a velocidade de saída é `velocidade_do_fluxo + velocidade`).

**Diferença importante para o que o projeto faz hoje.** O `PoseResolver` mantém uma
mola por junta *perseguindo a pose alvo o tempo todo*, não só na troca. Isso dá a
"tensão" de cada junta (dedos soltos, corpo firme), mas também significa que o
movimento autoral inteiro passa por um filtro passa-baixa permanente: gestos rápidos
são atenuados e atrasados. Na inertialização, depois que o desvio decai, a pose
exibida é *exatamente* a pose autoral, sem atraso. Isso importa para a dança no tempo
da batida.

Duas opções, da menor para a maior:

- **Opção A (mínima, P):** manter as molas como estão e apenas **não zerar a velocidade**
  em `iniciar_transicao`/`definir` (achado 3.2). Antes de mexer, confirmar em
  `animation.py` se a `pose_atual` passada é o valor da própria mola; se for, basta
  preservar a velocidade e o resto já é contínuo.
- **Opção B (estrutural, M):** trocar o seguimento permanente por inertialização na
  troca, e manter a tensão por junta como *meia-vida do decaimento* (âncora curta,
  ponta longa). Ganho: movimento autoral sem atraso depois da transição. Custo:
  perde-se o efeito de "gelatina" permanente que a mola dá hoje, que teria que ser
  recriado com follow-through explícito (`LagChain`). Os testes de transição e de
  overshoot por junta precisam ser reescritos.

Recomendo começar pela A, medir (seção 6.2, item 3) e só ir para a B se o atraso
do filtro permanente atrapalhar a sincronia musical.

Riscos: a opção B exige a velocidade do fluxo novo (derivar por diferença finita se
as camadas não a fornecerem). Meia-vida muito longa deixa a pose antiga "grudada";
muito curta volta ao tranco.

### 4.4 Antecipação, ação e recuperação (M, baixo)

Princípios de Disney em forma de parâmetros:

| Princípio | Como virar código |
|---|---|
| Antecipação | Impulso curto no sentido oposto antes da ação (≈ 80 a 150 ms). |
| Squash & stretch | Escala em Y/X conservando volume (`sx = 1/sqrt(sy)`), amarrada à velocidade vertical. O projeto já tem `compression` e `stretch` em `BodyPose`. |
| Arcos | Trajetórias de mão em arco (IK com alvo em curva), não em linha reta. |
| Overlapping | `LagChain`. |
| Slow in / slow out | Smootherstep ou mola crítica. |
| Timing | Variar duração por personalidade. |
| Exagero | Multiplicador por personalidade aplicado em amplitude. |
| Secundária | Fones, tentáculos, gosma. |

Receita de gesto autoral: **preparação → acento → sustentação → recuperação**,
já definida em `GUIA_ANIMACAO_DANCA.md` seção 8. Cada fase é um alvo de mola
com sua própria meia-vida.

### 4.5 Ruído e osciladores para vida contínua (P, baixo)

Idle sem movimento parece estátua. Respiração e micro-movimentos resolvem.

Soma de senos com frequências incomensuráveis é um ruído barato e sem tabela:

```python
from math import sin, tau

RAZOES_RUIDO = (1.0, 2.3, 4.1)   # irracionais entre si: o padrão não repete cedo
PESOS_RUIDO = (1.0, 0.5, 0.25)


def calcular_ruido(tempo: float, semente: float) -> float:
    """Ruído suave em -1..1 por soma de senos incomensuráveis."""
    total = sum(
        peso * sin(tau * razao * tempo + semente * (indice + 1))
        for indice, (razao, peso) in enumerate(zip(RAZOES_RUIDO, PESOS_RUIDO))
    )
    return total / sum(PESOS_RUIDO)
```

Usos: balanço do olhar em fixação (saccades), tremor de cabeça, deriva do tronco,
variação de intensidade da respiração. Semente diferente por junta para não ficar sincronizado.

Quando precisar de ruído de verdade (Perlin/simplex 1D): `numpy` não traz, mas são
20 linhas. Só vale se o padrão de senos ficar perceptível.

### 4.6 Agendamento de comportamento (fidgets) (M, baixo)

Idle repetitivo mata a ilusão. Em vez de sorteio uniforme:

- **Sorteio ponderado com resfriamento**: cada variação tem peso e *cooldown* próprio.
- **Memória de repetição**: nunca repetir a mesma variação duas vezes seguidas.
- **Intervalos com variância**: `base * (0.7 + 0.6 * ruido)`.
- **Orçamento de atenção**: se o usuário está digitando ou o cursor está parado em
  campo de edição, reduzir amplitude e frequência (o projeto já pausa nesses casos).
- **Personalidade como vetor de parâmetros**: as nove personalidades viram um
  `dict` de multiplicadores (tempo, amplitude, zeta global, probabilidade de fidget),
  e não ramos de código.

### 4.7 Limites suaves (P, baixo)

```python
from math import tanh


def limitar_suave(valor: float, minimo: float, maximo: float) -> float:
    """Aproxima o valor da faixa sem parada seca (tangente hiperbólica)."""
    centro = (minimo + maximo) / 2.0
    meia_faixa = (maximo - minimo) / 2.0
    return centro + meia_faixa * tanh((valor - centro) / meia_faixa)
```

Comprime também o interior da faixa (inclinação 1 só no centro). Se isso incomodar,
aplicar apenas nos últimos ~15% da faixa. Manter o `max/min` como segurança final
logo depois.

### 4.8 Molas de ângulo (caminho curto) (P, baixo)

```python
def calcular_alvo_angular(valor: float, alvo: float) -> float:
    """Reposiciona o alvo (graus) para o caminho mais curto a partir do valor."""
    diferenca = ((alvo - valor + 180.0) % 360.0) - 180.0
    return valor + diferenca
```

Aplicar antes de `Spring.update` em juntas que podem passar de ±180°.

### 4.9 Quaternions (M, médio, só se necessário)

- `slerp` para interpolar rotações grandes sem passar por Euler.
- Composição por multiplicação para camadas em ombros e cabeça.
- Mola em quaternion: mola sobre a rotação de erro (`q_alvo * conj(q_atual)` em
  eixo-ângulo), integrando velocidade angular.

Panda3D tem `LQuaternion`, mas `animacao/` não pode importar Panda3D (regra de
camadas). Ou se escreve um quaternion mínimo em Python, ou se mantém Euler. Minha
recomendação é manter Euler até aparecer um defeito concreto.

### 4.10 IK: o que vale conhecer

| Solucionador | Ideia | Serve para |
|---|---|---|
| Analítico de 2 ossos (lei dos cossenos) | Já existe (`limb_ik`). | Braços e pernas. |
| Analítico 3D com vetor polo | Plano do membro escolhido por um ponto de referência. | Controlar para onde aponta o cotovelo. |
| CCD | Gira junta por junta do fim para o início. | Cadeias curtas, simples, pode torcer feio. |
| **FABRIK** | Move pontos, não ângulos: puxa a ponta ao alvo e volta pela base. | **Tentáculos e fio**. Converge em poucas iterações. |
| Jacobiano | Resolve por derivadas. | Pesado, desnecessário aqui. |

Para os tentáculos, que têm 12 juntas: FABRIK dá o *formato* alcançando um alvo
(empurrar a caixa de som), e o sistema atual (Catmull–Rom, torção distribuída,
cápsulas) continua cuidando da malha e dos contatos.

Comportamentos de IK que parecem vivos: ponta alcança o alvo com mola (não
instantânea), o alvo tem ruído, restrição de ângulo máximo por junta, e *peso* de
IK (0..1) animado na entrada e na saída para evitar estalo.

**FABRIK em detalhe** (Aristidou e Lasenby, 2011). Enquanto CCD e os métodos
jacobianos pensam em *ângulos*, o FABRIK pensa em *posições*: cada junta é um ponto e
cada osso é uma barra rígida de comprimento fixo `d[i]` entre dois pontos vizinhos.
Dado um alvo `t` para a ponta, repete duas fases:

1. **Fase para trás:** põe a ponta em `t`. Depois, da penúltima junta até a raiz,
   recoloca cada junta `i` sobre a reta que a liga à junta `i+1`, a distância `d[i]`
   dela. Agora a ponta está no alvo, mas a raiz saiu do lugar.
2. **Fase para frente:** devolve a raiz à posição original. Da junta 1 até a ponta,
   recoloca cada junta sobre a reta que a liga à anterior, a distância `d[i-1]`.
   Agora a raiz está certa, mas a ponta pode ter se afastado um pouco do alvo.
3. Repete até `|ponta - alvo| < tolerância` ou até o limite de iterações. Em cadeias
   humanoides bastam 2 a 4 repetições.

Se o alvo está além do alcance total (soma dos `d[i]`), o resultado correto é a cadeia
esticada em linha reta na direção do alvo; vale tratar esse caso antes do laço.

```python
from math import dist

Vetor3 = tuple[float, float, float]

EPSILON_DISTANCIA = 1e-9  # abaixo disso a direção entre dois pontos é indefinida


def _mover_ate(origem: Vetor3, ponto: Vetor3, comprimento: float) -> Vetor3:
    """Põe `ponto` a `comprimento` de `origem`, mantendo a direção até ele."""
    distancia = dist(origem, ponto)
    if distancia < EPSILON_DISTANCIA:
        return ponto
    fator = comprimento / distancia
    return tuple(o + (p - o) * fator for o, p in zip(origem, ponto))  # type: ignore[return-value]


def resolver_FABRIK(
    pontos: list[Vetor3],
    comprimentos: list[float],
    alvo: Vetor3,
    iteracoes_maximas: int,
    tolerancia: float,
) -> list[Vetor3]:
    """Resolve a cadeia por FABRIK e devolve as novas posições das juntas."""
    pontos = list(pontos)
    raiz = pontos[0]
    if dist(raiz, alvo) >= sum(comprimentos):
        # Fora do alcance: estica em linha reta na direção do alvo.
        for i in range(1, len(pontos)):
            pontos[i] = _mover_ate(pontos[i - 1], alvo, comprimentos[i - 1])
        return pontos
    for _ in range(iteracoes_maximas):
        if dist(pontos[-1], alvo) < tolerancia:
            break
        pontos[-1] = alvo
        for i in range(len(pontos) - 2, -1, -1):
            pontos[i] = _mover_ate(pontos[i + 1], pontos[i], comprimentos[i])
        pontos[0] = raiz
        for i in range(1, len(pontos)):
            pontos[i] = _mover_ate(pontos[i - 1], pontos[i], comprimentos[i - 1])
    return pontos
```

Não rodei o código; é a transcrição do algoritmo acima.

**Posições → rotações.** O FABRIK devolve pontos. Para alimentar o rig (que usa
rotações por nó), cada osso precisa ser girado para apontar da junta `i` para a
junta `i+1` resolvida: rotação que leva a direção atual do osso à direção resolvida
(eixo = produto vetorial das duas, ângulo = arco-cosseno do produto escalar; se o
produto escalar for ≈ 1, nada a fazer; se o eixo for ≈ 0, direções opostas ou
iguais). Isso é o passo mais fácil de errar com as convenções de eixo do projeto
(+X como eixo longo do braço, H=y, P=x, R=z). Validar com captura multi-ângulo.

**Restrições de junta no FABRIK.** Como a junta é um ponto, a restrição entra
*dentro das fases*, limitando a direção antes de calcular a nova posição:

- *Dobradiça:* projetar a direção no plano perpendicular ao eixo da dobradiça e
  limitar o ângulo.
- *Esférica (cone):* se o ângulo entre a direção e a direção de referência passa do
  limite, girar a direção em direção à referência pelo excedente. Se as direções
  forem opostas, trocar pela referência.

Isso preserva o comprimento do osso e respeita o limite. Para os tentáculos, um cone
de ~25° a 35° por junta evita dobras de 180° nas pontas.

**CCD versus FABRIK.** CCD gira uma junta por vez, da ponta para a raiz; as juntas
perto da ponta ganham mais influência (viés da ponta) e em cadeias longas as juntas
da raiz giram demais enquanto as de cima mal se mexem, o que parece rígido.
FABRIK trata todas as juntas de forma simétrica e espalha a correção pela cadeia
inteira. Regra prática usada em produção: CCD para membros curtos (2 a 3 ossos,
correções pequenas, como ajuste de pé no terreno); FABRIK para alcance de braço
inteiro, colunas e cadeias longas. Para o projeto: o `limb_ik` analítico continua
certo para braços e pernas; FABRIK é a escolha para tentáculos e para o fio.

### 4.11 Verlet e cordas (fio do fone) (M, médio)

Requisito registrado em memória: o fio do fone como corda simulada. Verlet com
restrições de distância é o padrão da área (Thomas Jakobsen, "Advanced Character
Physics", 2001).

**Ideia.** Cada partícula guarda só a posição atual e a anterior; a velocidade é
implícita (`atual - anterior`). Não há força de mola: o comprimento dos segmentos é
mantido por *relaxamento*, projetando as partículas de volta à distância correta, e
a colisão é a mesma coisa (empurrar a partícula para fora do obstáculo). Como a
posição é corrigida diretamente, a simulação é muito estável e dispensa ajustar
rigidez de mola. A mesma ideia serve para tecido, corpos rígidos (partículas ligadas
por "varetas") e cadeias articuladas.

Algoritmo por passo fixo:

1. `nova = atual + (atual - anterior) * (1 - arrasto) + gravidade * dt²`
2. Fixar a primeira partícula na âncora (fone na cabeça, em coordenadas do rig).
3. Repetir N vezes (3 a 8): para cada par vizinho, corrigir pela metade a diferença
   entre a distância atual e o comprimento de repouso.
4. Colisão: empurrar partículas para fora de caixas/cápsulas do corpo (reaproveitar
   `rig_mapa.colisao_membros` e a ideia de cápsulas de `tentaculos/`).
5. Gerar a malha ao longo da curva (Catmull–Rom, já usado nos tentáculos).

```python
from math import sqrt

EPSILON_DISTANCIA = 1e-9  # abaixo disso a direção do segmento é indefinida


def _corrigir_segmento(
    posicoes: list[list[float]],
    indice: int,
    comprimento: float,
) -> None:
    """Aproxima ou afasta duas partículas vizinhas até o comprimento de repouso."""
    a = posicoes[indice]
    b = posicoes[indice + 1]
    delta = [pb - pa for pa, pb in zip(a, b)]
    distancia = sqrt(sum(d * d for d in delta))
    if distancia < EPSILON_DISTANCIA:
        return
    erro = (distancia - comprimento) / distancia
    # A partícula 0 é a âncora: não se move, o par inteiro da correção vai para a 1.
    parte_a = 0.0 if indice == 0 else 0.5
    parte_b = 1.0 if indice == 0 else 0.5
    for eixo in range(len(delta)):
        a[eixo] += delta[eixo] * erro * parte_a
        b[eixo] -= delta[eixo] * erro * parte_b


def avancar_corda(
    posicoes: list[list[float]],
    anteriores: list[list[float]],
    comprimento_segmento: float,
    aceleracao: tuple[float, float, float],
    arrasto: float,
    iteracoes: int,
    dt: float,
) -> None:
    """Um passo de Verlet com restrições de distância (âncora = índice 0).

    O chamador atualiza `posicoes[0]` com a posição da âncora antes de cada passo.
    """
    for i in range(1, len(posicoes)):
        atual = posicoes[i]
        posicoes[i] = [
            p + (p - a) * (1.0 - arrasto) + g * dt * dt
            for p, a, g in zip(atual, anteriores[i], aceleracao)
        ]
        anteriores[i] = atual
    for _ in range(iteracoes):
        for i in range(len(posicoes) - 1):
            _corrigir_segmento(posicoes, i, comprimento_segmento)
```

Não rodei o código. Um relaxamento sempre na mesma ordem deixa a corda levemente
assimétrica; se aparecer um viés, alternar a ordem dos segmentos a cada iteração.
A `aceleracao` inclui a gravidade *e* a pseudo-força de inércia do movimento do
mascote (menos a aceleração do corpo), que é o que faz o fio "ficar para trás".

Armadilhas:
- **Passo fixo obrigatório** (seção 2.2). Usar acumulador, 120 Hz como a física.
- **Âncora se movendo rápido** (arraste da janela) estica a corda: limitar a
  velocidade da âncora ou aumentar iterações naquele frame.
- **Espaço**: as coordenadas físicas são absolutas no desktop e as do renderer são
  locais à janela (AGENTS.md). Simular em coordenadas locais do mascote e injetar a
  aceleração do mascote como pseudo-força (inércia), evita misturar espaços.
- **Rigidez**: poucas iterações dão corda elástica; muitas dão corda dura. Ajustar
  por *iterações* e por *arrasto*, não por constantes soltas.
- Teste de comprimento: soma dos segmentos deve permanecer dentro de ±2% do repouso.

### 4.12 Cadeias secundárias: fones, antena, gosma (P a M, baixo)

- **Uma mola por partícula** com alvo no pai, em coordenadas locais: barato e
  suficiente para fones curtos.
- **Gotas de gosma**: partículas com Euler semi-implícito + arrasto, vida curta,
  sem colisão (ou colisão só com o chão da caixa).
- **Trails**: guardar as últimas N posições da ponta e desenhar fita. A guia diz
  que partículas/trails vêm *depois* de postura e contato convincentes; respeitar.

### 4.13 Olhar e atenção (P, baixo)

Um olhar convincente tem camadas, na ordem em que o corpo reage:

1. **Olhos/cabeça rápidos, corpo lento**: a cabeça segue com meia-vida curta; o
   tronco com meia-vida maior; o corpo (`GiroCorpo`) só quando o alvo está muito
   de lado (já é assim).
2. **Zona morta + histerese**: não reagir a variações pequenas e não oscilar na
   borda da zona morta (dois limiares: entrar em 0.35, sair em 0.28).
3. **Saccades**: a cada 0,5 a 3 s, um pequeno salto de olhar para perto do alvo.
4. **Antecipação**: pequena contra-rotação antes de virar muito.
5. **Contato visual**: quando o cursor para sobre o mascote, olhar para a câmera
   (usuário) por alguns segundos.
6. **Piscar** (se houver geometria dos olhos; a memória indica que a textura dos
   olhos não é alterada, então fica fora do escopo atual).

### 4.14 Locomoção procedural (M)

O mascote anda sobre prateleiras de janelas. Quando o passo for refinado:

- **Fase do ciclo**: `fase += velocidade_horizontal / comprimento_passo * dt`. Deixa a
  cadência proporcional à velocidade real, sem deslizar o pé.
- **Planta do pé**: enquanto o pé está em apoio, sua posição no mundo fica fixa; o
  IK ajusta o resto. Já existe em `lower_body.py`.
- **Balanço de quadril e ombros** opostos, proporcional à velocidade.
- **Inclinação para a aceleração**: já feita (roll/pitch). Subir para uma mola de
  *aceleração* e não de velocidade dá peso melhor nas partidas e paradas.

### 4.15 Máquinas de estado e camadas de máscara (já adotado)

O projeto está na linha moderna: estado produz **delta mascarado e ponderado**.
Pontos a observar:

- Peso por camada animado (fade in/out) em vez de ligar e desligar.
- Estados "legados" absolutos coexistem com deltas (estado híbrido registrado).
  A migração restante remove o ramo `if estado_migrado` e o código morto.
- Máscaras por grupo de juntas já existem em `anim_layers.py`. Para dança,
  preferir máscara de metade superior e deixar pernas com IK de apoio.

### 4.16 Fisicamente informado: ragdoll parcial e "dangle" (G, alto)

Quando arrastado pelo cursor, o mascote "pende" do ponto de pega. O projeto já faz
suspensão visual e atraso de cabeça e antebraços. Um passo adiante seria uma cadeia
de corpos rígidos (Pymunk) para braços pendurados. Custo alto, ganho moderado, e
disputa espaço com a decisão de não migrar para bones. **Não recomendo agora.**

### 4.17 Motion matching, aprendizado e captura

Descartados para este projeto: exigem biblioteca de clipes de captura e
conflitam com a decisão de animação reativa ao runtime. Mencionados só para
registrar o limite do que a abordagem procedural substitui.

---

## 5. Receitas por tema do projeto

### 5.1 Música

Sinais disponíveis (conforme `PESQUISA.md` e `GUIA_ANIMACAO_DANCA.md`): RMS, energia
de graves, onset por fluxo espectral, BPM estimado por janela.

- **Onset → impulso** (4.1) em tronco e cabeça. Resposta em 40 a 80 ms de latência
  de detecção.
- **Fase de dança por PLL simples**: manter uma fase `phi` avançando a
  `2*pi*bpm/60` por segundo e corrigir `phi` levemente a cada onset detectado
  (ganho pequeno, 0,05 a 0,2). A dança usa `sin(phi)`/`cos(phi)`, não o onset cru,
  e por isso continua fluida quando um onset falha.
- **Compensação de latência**: o gesto deve *chegar* no tempo, então a fase usada
  na pose adianta `latencia_total` (áudio + render). Medir e calibrar com música real.
- **Meio-tempo e dobro**: BPM costuma ser detectado em 2x ou 0,5x. Escolher o
  múltiplo dentro da faixa do estilo (guia de dança, seção 2).
- **Energia como amplitude, não como velocidade**: energia alta aumenta amplitude;
  o BPM define a cadência. Misturar os dois gera movimento nervoso.
- **Transição de estilo** pela inertialização (4.3).
- **Silêncio**: decair amplitude por mola (meia-vida ~0,4 s) em vez de cortar.

### 5.2 Mouse e cursor

- Cursor como **alvo móvel** de mola para cabeça/tronco (já feito).
- **Velocidade do cursor** como medida de interesse: cursor rápido passando longe
  não deve atrair; cursor lento e perto, sim.
- **Zona de intimidade**: cursor muito perto do rosto, recuo leve (impulso).
- **Gesto de carinho** (botão direito): sincronizar amplitude do aceno de aprovação
  com o tempo que o botão ficou pressionado.
- Duplo clique já tem reação autorada; padrão a replicar: *preparação autoral +
  impulso nas molas do corpo*.

### 5.3 Física de tela (Pymunk) → corpo

- Velocidade do corpo físico → roll/pitch (já feito).
- **Aceleração** (derivada da velocidade, filtrada) → balanço secundário de
  cabeça e braços. Aceleração brusca é o que o olho lê como "peso".
- **Pouso**: impulso vertical + compressão proporcional à velocidade de impacto,
  com limite. Pouso em prateleira de janela deve diferir de pouso no chão.
- **Vento de janela**: janela arrastada perto do mascote aplica impulso lateral
  proporcional à velocidade da janela e inversamente à distância.
- Sempre filtrar a velocidade do HWND antes de usar (jitter do arraste).

### 5.4 Tentáculos

- Raiz acompanha a cabeça (já feito); adicionar atraso por mola à raiz.
- **Onda viajante**: deslocamento lateral `A * sin(k*s - w*t)` com amplitude
  crescente da base à ponta; dá nado/respiração sem keyframe. Trocar `A` e `w`
  por estado (espreita, empurrão, recolhimento).
- **Alcance por FABRIK** (4.10) para empurrar a caixa; suavizar o alvo com mola.
- **Recolhimento**: reduzir o comprimento efetivo exponencialmente (já feito) e
  manter seção opaca.
- Torção distribuída já presente; manter volume dos referenciais (≥ 0,9999).

### 5.5 Fio do fone

Seção 4.11, mais:
- Âncoras: um ponto em cada fone, ou do fone ao colar (`mesh18`) se o fio
  atravessar o corpo.
- Raio de colisão do fio pequeno e geometria simples (cápsulas) para não custar CPU.
- Teste visual obrigatório: arrastar rápido, soltar, dançar, e parar de repente.

### 5.6 Porta da cabeça

Articulação de 1 grau de liberdade com mola, limite de 135°, bloqueio por
volumes esféricos (já feito). Possível refino: **batida da porta** (rebote) ao
fechar rápido, com `zeta` baixa só no fechamento, e **ranger** por jitter de amplitude
muito pequena em torno do limite.

---

## 6. Validação e ferramentas

Premissas do projeto (memória): teste verde não prova o visual, e a ferramenta
de calibração precisa ser **interativa**, rodando na GPU do usuário.

### 6.1 Testes que não dependem de GPU

| Propriedade | Como medir |
|---|---|
| Independência de FPS | Mesma trajetória simulada a 30, 60 e 120 Hz; diferença máxima abaixo de tolerância. |
| Overshoot e tempo de assentamento | Resposta ao degrau por junta; comparar com o alvo da tabela de tensão. |
| Continuidade | Máximo de `|pose[t+1] - pose[t]|` e de `|aceleração|` (jerk) em troca de estado. |
| Limites | Nenhuma junta fora da faixa anatômica após o resolver. |
| Energia | A mola em repouso converge e não ganha energia (nenhum NaN). |
| Corda | Comprimento total estável; nenhuma partícula dentro de caixa do corpo. |
| Determinismo | Mesma semente, mesma saída. Ruído e fidgets com semente injetável. |

### 6.2 Ferramentas sugeridas

1. **Gráfico de resposta** (`tools/`): plota `x(t)` e `v(t)` de uma junta para um
   degrau ou impulso. Útil para derivar zeta de um overshoot desejado.
2. **Painel de molas ao vivo** (Qt, na GPU do usuário): sliders de frequência e
   zeta por junta, aplicação imediata, botão "copiar para `spring_tuning.py`".
3. **Medidor de salto em transição**: registra o salto de pose e de velocidade ao
   trocar de estado e lista os piores pares de estados (achado 3.2).
4. **Gravador de curvas de música**: salva RMS/onset/BPM e a fase do PLL ao lado
   da pose, para ajustar sincronia sem ouvir de novo.
5. **Strobe de contato**: já existem eixos e JSONL; incluir o peso de cada camada
   por frame no JSONL para ver qual camada causou um defeito.

### 6.3 Disciplina de calibração

- Sempre ajustar **um parâmetro por vez** e registrar o antes e depois.
- Mudar `zeta` altera personalidade; mudar `frequencia` altera velocidade.
  Misturar os dois confunde o diagnóstico.
- Constantes novas vão para `*_tuning.py` com o porquê (convenção do projeto).
- Verificar sempre a pose **depois** do `PoseResolver`, não a pose crua.

---

## 7. Roadmap sugerido

Ordem por retorno sobre custo. Não é plano aprovado; é insumo para decisão.

| # | Item | Seção | Esforço | Risco | Por quê |
|---|---|---|---|---|---|
| 1 | Validar faixa de `Spring` (zeta, frequência, dt finito) | 3.1 | P | baixo | Elimina crash latente. |
| 2 | Medidor de salto em transição | 6.2 | P | nenhum | Prova ou refuta o achado 3.2 antes de mexer. |
| 3 | Mola crítica por meia-vida (função utilitária) | 2.5 | P | nenhum | Primitiva para os itens seguintes. |
| 4 | Preservar velocidade na transição (opção A); inertialização (opção B) só se o atraso do filtro atrapalhar | 4.3 | P / M | baixo / médio | Remove "trancos" de troca de estado. |
| 5 | Impulso por evento (batida, pouso, colisão) | 4.1 | P | baixo | Ganho visível, pouco código. |
| 6 | Ruído de senos no idle e no olhar | 4.5 | P | baixo | Tira o aspecto de estátua. |
| 7 | Fio do fone com Verlet | 4.11 | M | médio | Requisito já registrado. |
| 8 | Fase de dança por PLL + compensação de latência | 5.1 | M | médio | Dança no tempo mesmo com onset falho. |
| 9 | Limite suave nas juntas de braço | 4.7 | P | baixo | Tira parada seca. |
| 10 | Agendador de fidgets com cooldown e personalidade como vetor | 4.6 | M | baixo | Variedade de idle. |
| 11 | FABRIK nos tentáculos para alcance de alvo | 4.10 | M | médio | Empurrão na caixa mais convincente. |
| 12 | Painel de molas ao vivo | 6.2 | M | nenhum | Calibração na GPU do usuário. |
| 13 | Quaternions nos ombros | 4.9 | M | alto | Só se aparecer defeito de composição. |

Dependências: 3 → 4; 1 → 3; 2 antes de 4.

Regras de conduta já definidas pelo usuário que este roadmap respeita:
- Enxugar código só depois de a animação estabilizar.
- Nenhuma validação final por teste automatizado; capturar frames multi-ângulo.
- Valores de ajuste em constantes nomeadas nos módulos `*_tuning.py`.

---

## 8. Conhecimento de base das fontes

Esta seção resume o que cada fonte ensina, com palavras próprias, para o documento
valer sozinho. As fórmulas e os algoritmos já estão nas seções 2 e 4; aqui ficam o
raciocínio por trás deles e as lições que importam ao projeto.

### 8.1 Molas e amortecimento (Daniel Holden, "Spring-It-On", 2021)

O artigo parte de um problema comum: um objeto precisa ir para outra posição sem
"pular". Percorre uma sequência de soluções, cada uma corrigindo a anterior:

1. **`lerp` por frame** (`x = lerp(x, alvo, 0.1)`): suaviza, mas a velocidade depende
   do FPS (a 30 Hz chega na metade do ritmo de 60 Hz).
2. **`lerp` com `fator * dt`**: parece corrigir, mas fica instável quando
   `fator * dt > 1`, e aplicar `dt/2` duas vezes não equivale a aplicar `dt` uma vez.
3. **Amortecedor exato:** repetir o `lerp` é um decaimento exponencial
   (`x(n) = y^n * x0 - y^n * alvo + alvo`). Fixar a *taxa de decaimento* em 1/2 e
   deixar o tempo variar dá `lerp(x, alvo, 1 - 2^(-dt / meia_vida))`: estável para
   qualquer `dt` e com um parâmetro intuitivo (a meia-vida, o tempo para cobrir
   metade da distância).
4. **Limitação do amortecedor:** não tem velocidade própria; se o alvo inverte de
   direção, o objeto inverte de uma vez. Para continuidade de velocidade é preciso
   uma **mola amortecida**: aceleração = `rigidez * (alvo - x) + amortecimento * (v_alvo - v)`.
5. **Mola por integração numérica** (Euler semi-implícito) funciona só com `dt`
   pequeno e fica instável com valores grandes.
6. **Mola exata:** em vez de integrar, adivinha-se a forma da solução
   (`j * e^(-y t) * cos(w t + p) + c`), substitui-se na equação da mola e resolve-se
   para `c = alvo + d * v_alvo / s`, `y = d / 2` e `w = sqrt(s - d²/4)`; `j` e `p` saem das
   condições iniciais (`x0`, `v0`). O sinal de `j` precisa ser corrigido quando
   `x0 - c < 0`, porque a raiz quadrada perde o sinal.
7. **Três regimes:** o radicando `s - d²/4` pode ser positivo (subamortecido,
   oscila), zero (crítico) ou negativo (superamortecido). Cada regime tem outra
   forma de solução, e uma implementação que só trata o primeiro quebra nos outros
   (ver achado 3.1).
8. **Parâmetros melhores:** *meia-vida* no lugar de amortecimento, *frequência* no
   lugar de rigidez e *razão de amortecimento* `r = d / (2 * sqrt(s))` (1 = crítica,
   menor que 1 = balança, maior que 1 = lenta). A frequência nominal não é a
   frequência real de oscilação, e a meia-vida não é exatamente o tempo para chegar
   na metade (a velocidade inicial muda isso).
9. **A mola crítica é o caso mais útil:** mais rápida sem oscilar, sem ramos
   especiais, a mais barata, e com poucas variantes derivadas (alvo zero, velocidade-alvo
   zero, pré-cálculo de `y` e `exp(-y * dt)` para várias molas com a mesma meia-vida).

Aplicações descritas e adotadas na seção 2.7: suavização, filtragem de jitter,
controlador de personagem (a mola atua na *velocidade*, e avaliar com `dt` grande
prevê o futuro), inertialização, interpolação paramétrica, ressonância como detector
de frequência, extrapolação com decaimento, mola dupla, temporizada, de velocidade,
de quaternion e de escala.

Lições para o projeto:
- A `Spring` atual é a solução subamortecida deste artigo. Falta o caso crítico.
- Trocar zeta por meia-vida nas molas *novas* simplifica o ajuste.
- Toda mola nova deve nascer com a mola crítica como padrão e oscilar só quando a
  personalidade pedir.

### 8.2 Inertialização (David Bollo, GDC 2018, Gears of War 4)

Motivação: o crossfade avalia duas animações durante toda a transição, o que custa
caro em personagens com muitos ossos e muitas transições. A inertialização avalia só a
animação nova.

Como funciona:
1. Na troca, calcula-se por osso a diferença de posição e de velocidade entre a pose
   que estava sendo exibida e a pose nova.
2. Passa-se a reproduzir somente a pose nova, somando a ela o desvio.
3. O desvio é reduzido a zero ao longo de um tempo, de forma que posição *e*
   velocidade cheguem a zero juntas (daí o nome: o desvio se comporta com inércia).
4. Na versão original o desvio segue um polinômio de duração fixa. Se a velocidade
   inicial aponta para zero rápido demais, a curva pode passar de zero e voltar; a
   palestra trata isso limitando a duração do bloco nesse caso.

Para referência, um polinômio cúbico `d(t) = a t³ + b t² + v0 t + x0` que leva
posição e velocidade a zero em `t1` tem `a = (2 x0 + v0 t1) / t1³` e
`b = -(3 x0 + 2 v0 t1) / t1²`. Derivei esses coeficientes para este estudo (não são
os do material original) e conferi o caso `x0 = 1`, `v0 = 0`, `t1 = 1`
(`a = 2`, `b = -3`, `d(1) = 0`, `d'(1) = 0`). A mola de decaimento da seção 4.3
dispensa a duração fixa e o tratamento de overshoot, ao custo de não ter tempo exato.

Lições para o projeto:
- A inertialização é mais um **filtro de transição** do que um filtro permanente.
  O projeto hoje usa uma mola permanente (ver 4.3, opções A e B).
- Funciona para quaternions também, aplicando a diferença como rotação.
- Vale registrar o desvio *acumulado*: se a troca acontece antes do desvio anterior
  acabar, o desvio novo soma o antigo (ver `registrar_transicao`).

### 8.3 FABRIK (Aristidou e Lasenby, 2011)

O método reposiciona *pontos* em vez de calcular ângulos: duas fases (para trás e
para frente), cada uma recolocando as juntas sobre a reta até a vizinha na distância
exata do osso. Converge em poucas repetições, não precisa de matrizes nem de
derivadas e dá poses naturais porque distribui a correção pela cadeia inteira.
Restrições entram limitando a direção dentro das fases (cone para juntas esféricas,
projeção em plano para dobradiças). A conversão de posições para rotações é um passo
à parte. Comparação com CCD e algoritmo completo na seção 4.10.

### 8.4 Verlet e restrições (Thomas Jakobsen, "Advanced Character Physics", 2001)

O artigo propõe uma física de personagem interativa, simples e estável, baseada em
**integração de Verlet** (posição atual e anterior em vez de posição e velocidade) e
em **restrições resolvidas por relaxamento**: depois de mover as partículas, cada
restrição (distância fixa entre duas partículas, limite de posição, colisão) é
satisfeita projetando as partículas, repetindo algumas vezes. Com isso simulam-se
cordas, tecidos, corpos rígidos (partículas ligadas por varetas) e personagens
articulados; o mesmo mecanismo faz a colisão com obstáculos. Vantagens: estável,
simples, sem precisar ajustar rigidez de molas. Limites: o relaxamento tem erro
residual (poucas iterações = corda elástica) e exige passo fixo.

Observação: não consegui abrir a página original do artigo no ambiente (erro de
certificado); este resumo vem dos resultados de busca e do conhecimento geral da
técnica. Os algoritmos da seção 4.11 são a aplicação padrão dela.

### 8.5 Rain World (Joar Jakobsson e James Therrien, GDC 2016)

O jogo anima as criaturas com uma combinação de código e animação tradicional. A
ideia central, nas palavras do autor, em vez de desenhar cada quadro e reproduzir,
é ter **pontos no espaço ligados a certas distâncias**; a criatura é um esqueleto
desses pontos, e a aparência é desenhada em cima. O resultado é um corpo mole e
elástico que reage ao ambiente.

Lições para o projeto (que tem partes rígidas, não corpos moles):
- Separar o **esqueleto de comportamento** (pontos, ângulos, molas) da malha. O
  projeto já faz isso: o rig GLTF é só uma hierarquia de nós.
- Animação autoral entra como **alvo** do esqueleto, não como resultado final.
- Reação ao ambiente (janelas, cursor, borda da tela) deve alimentar o esqueleto,
  como já acontece com a física e o olhar.

### 8.6 Molas para "game feel"

Artigos de design de jogos apontam que molas aplicadas a escala, rotação e posição de
elementos acrescentam muito detalhe sem complicar o código, e permitem iterar rápido
(ajustar um número em vez de refazer uma animação). É o que justifica tratar
"impulso em mola" (4.1) como ferramenta padrão do projeto.

### 8.7 Glossário

| Termo | Significado |
|---|---|
| Amortecimento (zeta) | 0 oscila para sempre; 1 é crítico; maior que 1 é lento. |
| Meia-vida | Tempo para cobrir metade da distância restante até o alvo. |
| Crossfade | Mistura de duas poses por um peso que vai de 0 a 1. |
| Inertialização | Exibir só a pose nova mais um desvio que decai a zero. |
| Delta aditivo | Rotação somada à pose base, em vez de pose absoluta. |
| Máscara | Conjunto de juntas que uma camada pode afetar. |
| FK / IK | Cinemática direta (ângulos → posição) / inversa (posição → ângulos). |
| Vetor polo | Ponto que decide para que lado dobra o cotovelo ou joelho. |
| CCD | Cyclic Coordinate Descent: gira uma junta por vez, da ponta à raiz. |
| FABRIK | IK por reposicionamento de pontos, em duas fases. |
| Verlet | Integração por posição atual e anterior; velocidade implícita. |
| Follow-through | A ponta continua o movimento depois que a base parou. |
| Squash e stretch | Achatar e esticar mantendo o volume. |
| PLL | Malha de fase: oscilador que se corrige por sinais periódicos (batidas). |
| Onset | Início de um evento sonoro (batida, nota). |
| Saccade | Pequeno salto rápido do olhar. |
| Jerk | Derivada da aceleração; picos de jerk são lidos como "trancos". |
| Gimbal lock | Perda de um grau de liberdade em ângulos de Euler perto de 90° de pitch. |

### 8.8 Documentos internos relacionados

`docs/GUIA_ANIMACAO_DANCA.md`, `docs/GUIA_ANIMACOES_COMPANION.md`,
`docs/REFERENCIA_ANIMACOES.md`, `docs/PESQUISA.md`, `docs/STATUS_E_PROXIMOS_PASSOS.md`.

---

## 9. Limites do estudo

**Li** (código): `joint_springs.py`, `anim_layers.py`, `limb_ik.py`, `pose_resolver.py`,
`spring_tuning.py`, e `body_motion.py` até `BodyPose`. Também `PESQUISA.md` e boa parte
de `STATUS_E_PROXIMOS_PASSOS.md`, mais os títulos de seção dos guias de animação.

**Não li:** `animation.py`, `delta_states.py`, `dance_motion.py`, `arm_ik.py`,
`arm_targets.py`, `lower_body.py`, `leg_motion.py`, `respiracao.py`, `attention.py`,
`foco_atencao.py`, `hand_motion.py`, `tentaculos/*`, `desktop/physics.py` e o resto de
`body_motion.py`. As linhas da tabela da seção 1 que apontam para esses arquivos vêm
dos nomes, do `STATUS_E_PROXIMOS_PASSOS.md` e das memórias do projeto, não da leitura do código.

**Fontes externas:** o artigo de Holden foi lido quase inteiro (a derivação do caso
superamortecido foi só passada por cima) e o tutorial de FABRIK foi lido por completo.
Bollo (inertialização), Jakobsen (Verlet), Rain World e o texto sobre game feel
entraram por resumos de busca e conhecimento geral; não assisti à palestra de Bollo
nem li o artigo de Jakobsen. Onde há detalhe que não vem de leitura direta, o texto
avisa (ex.: coeficientes do polinômio cúbico, derivados por mim).

**Não executei:** nenhum teste, nenhum trecho de código deste documento e nenhuma
medição. Os achados 3.1 a 3.5 são derivados por leitura e merecem reprodução
antes de virar tarefa.

**Não avaliei:** qualidade visual de qualquer animação (exige GPU e olhar do autor),
custo de CPU das técnicas propostas (o perfil atual registra cerca de 0,25 ms médios
no idle e 3 ms na espiada; qualquer técnica nova deve ser medida contra isso) e
suporte das bibliotecas em Python 3.14.
