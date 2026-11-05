# Mapeamento Completo do Corpo do Rig: Detecção e Nomenclatura

Nov 5, 2026 · @Veketo

## 1. Objetivo e escopo

O objetivo é que toda parte do corpo do Mário tenha direção, angulação, posição, estado de flexão e movimento medidos, nomeados e testáveis a cada frame. Hoje o `rig_debug` classifica vetores em seis direções discretas; este documento define o que medir, como nomear e como classificar para cobrir o corpo inteiro.

**O que muda em relação ao estado atual**

- De vetores soltos em `VETORES_REFERENCIA` para um registro completo por parte (`EstadoParte`).
- De flags em texto livre para enums tipados que o mypy valida.
- De ângulos implícitos para articulações explícitas (`EstadoArticulacao`) com limites, proporção e plano de flexão.
- De análise de um frame isolado para análise com memória do frame anterior (velocidade, sentido, fase).
- De medições só por parte para relações entre partes (simetria, distâncias, contato, equilíbrio).

**Princípios**

1. Medir primeiro, classificar depois, descrever por último. Números nunca são perdidos ao virar flag.
2. Toda flag deriva de um número guardado, com limiar nomeado e ajustável em um só lugar.
3. O módulo de análise não importa Panda3D, Qt ou Win32, seguindo a regra de `model.py`, `rig.py`, `assets.py` e `config.py` no `AGENTS.md`.
4. Nomes do GLTF são preservados como chave de grupo; só os nomes de código ao redor mudam.
5. Rotações procedurais continuam relativas ao rig; a análise só lê, nunca escreve na pose.
6. Tudo que for dedução matemática sem confirmação visual fica marcado `A_VALIDAR` até passar pela calibração visual.

**Fora de escopo**: física do Pymunk (corpo no desktop), render do overlay e animação do contorno. O mapeamento descreve a pose do rig, não a posição da janela.

## 2. Convenção de nomes

A regra central: o nome diz o que é, em que espaço está e em que unidade vem. Ninguém deve precisar abrir a função para saber se um ângulo está em graus ou radianos, ou se um vetor é local ou do mundo.

### 2.1 Idioma e estilo

| Elemento | Estilo | Exemplo |
| --- | --- | --- |
| Módulo, função, variável | `snake_case` em português, sem acento | `angulo_flexao_graus`, `medir_inclinacao` |
| Classe, dataclass, Enum | `PascalCase` | `EstadoParte`, `DirecaoPalma` |
| Membro de Enum | `MAIUSCULO_SNAKE` | `PALMA_PARA_CIMA` |
| Constante de módulo | `MAIUSCULO_SNAKE` | `LIMIAR_ESTICADO_GRAUS` |
| Chave de grupo do GLTF | igual ao arquivo, entre aspas | `"right-arm"`, `"ant-arm"` |

Termos técnicos já consolidados no código ficam como estão: `rig`, `pose`, `frame`, `pitch`, `roll`.

### 2.2 Prefixos de função

| Prefixo | Faz | Retorna | Exemplo |
| --- | --- | --- | --- |
| `medir_` | Calcula um número a partir da pose | `float`, `Vetor3` | `medir_angulo_entre(a, b)` |
| `classificar_` | Converte número em Enum usando limiares | `Enum` | `classificar_flexao(graus)` |
| `descrever_` | Monta frase em linguagem natural | `str` | `descrever_parte(estado)` |
| `analisar_` | Orquestra medir, classificar e descrever | dataclass | `analisar_rig(rig, t)` |
| `resolver_` | Acumula hierarquia pai para filho | matriz, vetor | `resolver_rot_mundo(parte)` |
| `comparar_` | Mede relação entre duas partes | `float`, `bool` | `comparar_simetria(a, b)` |

### 2.3 Sufixos de espaço e de unidade

| Sufixo | Significado | Exemplo |
| --- | --- | --- |
| `_repouso` | Valor na pose de repouso do GLTF | `vetor_repouso` |
| `_local` | Relativo ao nó pai | `rot_local_graus` |
| `_mundo` | Absoluto na cena | `vetor_mundo`, `posicao_mundo` |
| `_graus` | Ângulo em graus (padrão para saída e flags) | `angulo_flexao_graus` |
| `_rad` | Ângulo em radianos (só dentro de cálculo) | `giro_rad` |
| `_u` | Unidades da cena (a seta de calibração tem 3,2 u) | `comprimento_u` |
| `_s` | Segundos | `duracao_s` |
| `_graus_s` | Graus por segundo | `velocidade_angular_graus_s` |
| `_norm` | Valor normalizado de 0,0 a 1,0 | `proporcao_flexao_norm` |

Regra: ângulo guardado em dataclass é sempre em graus; conversão para radianos acontece só dentro da função que precisa.

### 2.4 Lado, eixo e sentido

- `Lado`: `DIREITA`, `ESQUERDA`, `CENTRO`. O lado é do personagem, não da tela: a mão direita do Mário é a que aparece à esquerda de quem olha de frente.
- `Eixo`: `X` (direita do personagem), `Y` (cima), `Z` (frente), conforme a convenção do GLTF no Panda3D descrita na calibração.
- `Sentido`: `POSITIVO`, `NEGATIVO`, `NENHUM`.
- Nunca usar `left` e `right` em inglês misturados com `esquerda` e `direita`. Um idioma só.

### 2.5 Identificação de partes

Hoje as partes são strings soltas (`"hand"`, `"hand2"`). Proposta: um Enum `Parte` cujo valor é o nome do grupo no GLTF, mais um nome semântico para código e relatórios.

| Problema atual | Solução |
| --- | --- |
| `hand` e `hand2` não dizem qual é qual | `Parte.MAO_DIREITA = "hand"`, `Parte.MAO_ESQUERDA = "hand2"` |
| `ant-arm` (antebraço) é críptico | `Parte.ANTEBRACO_DIREITO = "ant-arm"` |
| Strings repetidas em vários módulos | Uma única fonte: `Parte(...)` importável |
| Typo vira erro silencioso | Typo vira `AttributeError` na importação |

## 3. Inventário do corpo e hierarquia

O guia de calibração cita nove grupos do GLTF. O braço esquerdo e as pernas ainda não têm nome conhecido, e esse é o primeiro buraco a fechar antes de declarar o corpo todo mapeado.

&#91;embedded content: hierarquia do rig · 9 grupos nomeados, 3 a confirmar\]

Os nós tracejados não têm nome conhecido. O parentesco foi deduzido pelos nomes (por exemplo, `ant-arm` abaixo de `right-arm`) e vira verificação na Fase 0.

### 3.1 Tabela do inventário

| Parte | Grupo | Lado | Pai | Vetores de repouso | Articulação | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| `CORPO` | `body` | centro | raiz | `eixo_frente`, `eixo_cima`, `eixo_lateral` | nenhuma | Citado |
| `CABECA` | `head` | centro | `CORPO` | `eixo_olhar`, `eixo_topo`, `eixo_lateral` | `pescoco` | Citado |
| `PORTA` | `door` | centro | `CORPO` | `normal_porta`, `eixo_dobradica`, `eixo_borda_livre` | `dobradica_porta` | Citado |
| `BRACO_DIREITO` | `right-arm` | direita | `CORPO` | `eixo_longo` | `ombro_direito` | Citado |
| `ANTEBRACO_DIREITO` | `ant-arm` | direita | `BRACO_DIREITO` | `eixo_longo` | `cotovelo_direito` | Citado |
| `MAO_DIREITA` | `hand` | direita | `ANTEBRACO_DIREITO` | `normal_palma`, `normal_dorso`, `eixo_dedos`, `eixo_polegar`, `eixo_punho` | `punho_direito` | Citado |
| `BRACO_ESQUERDO` | a confirmar | esquerda | `CORPO` | `eixo_longo` | `ombro_esquerdo` | A confirmar |
| `ANTEBRACO_ESQUERDO` | a confirmar | esquerda | `BRACO_ESQUERDO` | `eixo_longo` | `cotovelo_esquerdo` | A confirmar |
| `MAO_ESQUERDA` | `hand2` | esquerda | `ANTEBRACO_ESQUERDO` (a confirmar) | `normal_palma`, `normal_dorso`, `eixo_dedos`, `eixo_polegar`, `eixo_punho` | `punho_esquerdo` | Citado |
| `PE_DIREITO` | `right-feet` | direita | `CORPO` ou perna (a confirmar) | `eixo_longo`, `normal_sola`, `eixo_frente_pe` | `tornozelo_direito` | Citado |
| `PE_ESQUERDO` | `left-feet` | esquerda | `CORPO` ou perna (a confirmar) | `eixo_longo`, `normal_sola`, `eixo_frente_pe` | `tornozelo_esquerdo` | Citado |
| Pernas, coxas e canelas | a confirmar | ambos | `CORPO` | `eixo_longo` | `quadril_*`, `joelho_*` | A confirmar |
| Tentáculos | `tentacle_system.py` | centro | `PORTA` | pontos dos elos | `tentaculo_N_elo_K` | Citado, fora do GLTF |

Todos os dados vêm do rig e do GLTF, exceto os tentáculos, que vêm da física procedural (seção 7.6).

## 4. Modelo de dados

Todo o resultado da análise cabe em quatro dataclasses imutáveis (`frozen=True`) e um conjunto de Enums. Imutável evita que um frame contamine o seguinte. Arquivo sugerido: `src/sejoga/rig_mapa.py`, sem imports de Panda3D, Qt ou Win32.

### 4.1 Enums base

```python
from enum import Enum

class Lado(Enum):
    DIREITA = "direita"
    ESQUERDA = "esquerda"
    CENTRO = "centro"

class Parte(Enum):
    """Valor = nome do grupo no GLTF. Não renomear o valor."""
    CORPO = "body"
    CABECA = "head"
    PORTA = "door"
    BRACO_DIREITO = "right-arm"
    ANTEBRACO_DIREITO = "ant-arm"
    MAO_DIREITA = "hand"
    MAO_ESQUERDA = "hand2"
    PE_DIREITO = "right-feet"
    PE_ESQUERDO = "left-feet"
    # A_CONFIRMAR no GLTF: braço e antebraço esquerdos, pernas, tentáculos

class DirecaoMundo(Enum):
    CIMA = "cima"
    BAIXO = "baixo"
    FRENTE = "frente"
    TRAS = "tras"
    DIREITA = "direita"
    ESQUERDA = "esquerda"
    INDEFINIDA = "indefinida"   # vetor nulo ou ambíguo demais

class EstadoFlexao(Enum):
    ESTICADO = "esticado"
    LEVE = "leve"
    DOBRADO = "dobrado"
    MUITO_DOBRADO = "muito_dobrado"
    HIPEREXTENDIDO = "hiperextendido"

class PlanoFlexao(Enum):
    PARA_FRENTE = "para_frente"
    PARA_TRAS = "para_tras"
    PARA_DENTRO = "para_dentro"   # em direção à linha central
    PARA_FORA = "para_fora"
    SEM_FLEXAO = "sem_flexao"

class AlturaRelativa(Enum):
    ACIMA_CABECA = "acima_cabeca"
    NIVEL_CABECA = "nivel_cabeca"
    NIVEL_OMBRO = "nivel_ombro"
    NIVEL_PEITO = "nivel_peito"
    NIVEL_CINTURA = "nivel_cintura"
    ABAIXO_CINTURA = "abaixo_cintura"
    NIVEL_CHAO = "nivel_chao"

class SentidoMovimento(Enum):
    PARADO = "parado"
    SUBINDO = "subindo"
    DESCENDO = "descendo"
    ABRINDO = "abrindo"
    FECHANDO = "fechando"
    GIRANDO_HORARIO = "girando_horario"
    GIRANDO_ANTIHORARIO = "girando_antihorario"

class Validacao(Enum):
    CONFIRMADO = "confirmado"   # visto na calibração visual
    A_VALIDAR = "a_validar"     # deduzido por matemática
```

### 4.2 Direção classificada

Uma flag sozinha perde informação. `Direcao` guarda o resultado completo da classificação de um vetor.

```python
@dataclass(frozen=True)
class Direcao:
    principal: DirecaoMundo       # eixo mais alinhado
    secundaria: DirecaoMundo      # segundo mais alinhado, ou INDEFINIDA
    alinhamento_norm: float       # cos do ângulo com o eixo principal, 0,0 a 1,0
    ambigua: bool                 # True se principal e secundária quase empatam
    angulo_vertical_graus: float  # 0 = cima, 90 = horizontal, 180 = baixo
    azimute_graus: float          # giro no plano horizontal, 0 = frente, +90 = direita
```

### 4.3 Estado de uma parte

```python
Vetor3 = tuple[float, float, float]

@dataclass(frozen=True)
class EstadoParte:
    parte: Parte
    lado: Lado
    pai: Parte | None
    validacao: Validacao

    # Rotação
    rot_local_graus: Vetor3          # HPR relativo ao pai
    rot_mundo_graus: Vetor3          # HPR absoluto
    desvio_repouso_graus: float      # ângulo total entre repouso e pose atual
    torcao_graus: float              # giro em torno do eixo longo

    # Vetores (um por entrada de VETORES_REFERENCIA)
    vetores_mundo: dict[str, Vetor3]
    direcoes: dict[str, Direcao]
    flags: dict[str, Enum]           # ex.: {"normal_palma": DirecaoPalma.PARA_CIMA}

    # Posição
    origem_mundo: Vetor3
    ponta_mundo: Vetor3 | None       # extremidade do membro
    comprimento_u: float | None
    altura_relativa: AlturaRelativa
    distancia_ao_eixo_central_u: float
```

### 4.4 Estado de uma articulação

```python
@dataclass(frozen=True)
class EstadoArticulacao:
    nome: str                        # "cotovelo_direito"
    lado: Lado
    segmento_proximal: Parte
    segmento_distal: Parte
    angulo_flexao_graus: float       # 0 = esticado
    angulo_min_graus: float
    angulo_max_graus: float
    proporcao_norm: float            # posição dentro de [min, max]
    estado: EstadoFlexao
    plano: PlanoFlexao
    torcao_graus: float              # giro relativo entre os dois segmentos
    fora_do_limite: bool             # True se passou de min ou max
```

### 4.5 Dinâmica, relações e relatório

```python
@dataclass(frozen=True)
class DinamicaParte:
    parte: Parte
    velocidade_angular_graus_s: float
    velocidade_linear_u_s: float
    aceleracao_angular_graus_s2: float
    sentido_vertical: SentidoMovimento
    sentido_giro: SentidoMovimento
    parado_ha_s: float               # tempo sem mover acima do ruído
    fase_ciclo_norm: float | None    # 0,0 a 1,0 em movimentos periódicos

@dataclass(frozen=True)
class Relacao:
    nome: str                        # "distancia_mao_direita_cabeca"
    valor: float | bool
    unidade: str                     # "u", "graus", "bool"
    partes: tuple[Parte, ...]

@dataclass(frozen=True)
class RelatorioRig:
    t_s: float
    pose: str
    partes: dict[Parte, EstadoParte]
    articulacoes: dict[str, EstadoArticulacao]
    dinamica: dict[Parte, DinamicaParte]
    relacoes: dict[str, Relacao]
    postura: "Postura"               # resumo do corpo todo (seção 8)
    descricao: str                   # frase em linguagem natural
```

## 5. Medições por parte

Cada parte do corpo recebe o mesmo conjunto de medições, agrupado em seis famílias: rotação, direção, posição, extensão, visibilidade e validação. Partes sem uma família (por exemplo, a cabeça não tem comprimento de membro) deixam o campo como `None`, nunca inventam um valor.

### 5.1 Pipeline de cálculo

1. `resolver_rot_mundo`: acumula rotação de repouso e rotação animada, do nó raiz até a parte.
2. `medir_vetor_mundo`: aplica a matriz acumulada a cada vetor de `VETORES_REFERENCIA`.
3. `medir_*`: deriva ângulos, posições e distâncias.
4. `classificar_*`: converte números em Enums usando os limiares da seção 10.

```latex
R_{mundo}(p) = R_{mundo}(pai(p)) \cdot R_{repouso}(p) \cdot R_{anim}(p)
```

```latex
v_{mundo} = R_{mundo}(p) \cdot v_{repouso}
```

### 5.2 Rotação

| Grandeza | Nome no código | Como calcular | Unidade |
| --- | --- | --- | --- |
| Rotação local | `rot_local_graus` | HPR animado somado ao repouso, relativo ao pai | graus (H, P, R) |
| Rotação do mundo | `rot_mundo_graus` | HPR extraído de `R_mundo` | graus (H, P, R) |
| Desvio do repouso | `desvio_repouso_graus` | Ângulo da rotação relativa entre repouso e pose | graus, 0 a 180 |
| Torção | `torcao_graus` | Componente de giro em torno do eixo `longo` (decomposição swing-twist) | graus, -180 a 180 |
| Balanço (swing) | `balanco_graus` | Desvio do eixo `longo` em relação ao repouso, sem a torção | graus, 0 a 180 |

```latex
\theta_{desvio} = \arccos\left(\frac{\mathrm{tr}(R_{rel}) - 1}{2}\right), \quad R_{rel} = R_{repouso}^{T} \cdot R_{mundo}
```

A torção importa nas mãos e antebraços: palma para cima e palma para baixo diferem quase só por torção, sem mudar a direção do braço.

### 5.3 Direção

| Grandeza | Nome no código | Como calcular | Unidade |
| --- | --- | --- | --- |
| Vetor no mundo | `vetor_mundo` | `R_mundo @ vetor_repouso`, normalizado | adimensional |
| Direção principal | `Direcao.principal` | Eixo do mundo com maior produto escalar | Enum |
| Direção secundária | `Direcao.secundaria` | Segundo eixo com maior produto escalar | Enum |
| Alinhamento | `Direcao.alinhamento_norm` | Produto escalar com o eixo principal | 0,0 a 1,0 |
| Ambiguidade | `Direcao.ambigua` | Diferença entre os dois maiores produtos menor que `MARGEM_AMBIGUIDADE` | bool |
| Inclinação vertical | `angulo_vertical_graus` | `arccos(v.y)`: 0 = cima, 90 = horizontal, 180 = baixo | graus |
| Azimute | `azimute_graus` | `atan2(v.x, v.z)` projetado no plano XZ: 0 = frente, +90 = direita | graus |

```latex
\mathrm{inclinacao} = \arccos(v_y), \qquad \mathrm{azimute} = \mathrm{atan2}(v_x, v_z)
```

O ganho principal está em guardar o número junto da flag. Um vetor com alinhamento 0,55 em `CIMA` e secundária `FRENTE` é uma diagonal, e a descrição deve dizer isso em vez de forçar um `CIMA` seco.

### 5.4 Posição

| Grandeza | Nome no código | Como calcular | Unidade |
| --- | --- | --- | --- |
| Origem | `origem_mundo` | Translação do nó acumulada pela hierarquia | u (x, y, z) |
| Ponta | `ponta_mundo` | `origem_mundo + R_mundo @ (longo * comprimento_u)` | u (x, y, z) |
| Comprimento | `comprimento_u` | Medido uma vez no repouso | u |
| Altura relativa | `altura_relativa` | `origem_mundo.y` ou `ponta_mundo.y` comparado com as alturas de referência do corpo | Enum |
| Distância ao eixo central | `distancia_ao_eixo_central_u` | `abs(origem_mundo.x - x_central)` | u |
| Profundidade | `profundidade_u` | `origem_mundo.z` relativo ao peito (frente ou atrás do tronco) | u |

As alturas de referência (`y_chao`, `y_cintura`, `y_peito`, `y_ombro`, `y_cabeca`, `y_topo`) são medidas uma vez no repouso e guardadas em `ReferenciasCorpo`. Elas não ficam fixas no código, para sobreviverem a trocas do modelo ou de escala.

### 5.5 Visibilidade para a câmera

O overlay é visto de frente, então o que aparece importa mais que a direção absoluta.

| Grandeza | Nome no código | Como calcular |
| --- | --- | --- |
| Face voltada à câmera | `voltada_para_camera` | `dot(normal_mundo, direcao_para_camera) > 0` |
| Grau de exposição | `exposicao_norm` | `max(0, dot(normal_mundo, direcao_para_camera))` |
| Ocultada pelo corpo | `ocultada_pelo_corpo` | Ponta ou origem atrás do tronco em relação à câmera, dentro do contorno do corpo |

Isso responde perguntas como "o dorso da mão aparece para quem olha?" e "a porta está virada para o usuário?".

### 5.6 Validação

| Campo | Significado |
| --- | --- |
| `validacao` | `CONFIRMADO` (visto na calibração) ou `A_VALIDAR` (deduzido) |
| `confianca_norm` | Cai para perto de 0 quando `ambigua` é verdadeiro ou a norma do vetor é quase nula |
| `valido` | Falso se a matriz tiver NaN, escala degenerada ou HWND/modelo ausente |

## 6. Articulações

Dobrado ou esticado não aparece em um vetor só: é a relação entre dois segmentos. Por isso cada junta vira um objeto próprio (`EstadoArticulacao`), calculado a partir do par proximal e distal, com ângulo assinado, limites, plano de flexão e torção.

### 6.1 Tipos de articulação

```python
class TipoArticulacao(Enum):
    DOBRADICA = "dobradica"   # 1 grau de liberdade: cotovelo, joelho, porta
    ESFERICA = "esferica"     # 3 graus: ombro, quadril
    PIVO = "pivo"             # giro em torno do eixo longo: pescoço, antebraço
    CADEIA = "cadeia"         # sequência de elos: tentáculos
    FIXA = "fixa"             # sem movimento próprio
```

### 6.2 Medição

**Flexão assinada.** O ângulo entre os eixos `longo` dos dois segmentos, com sinal positivo na direção natural da dobra. Negativo significa hiperextensão.

```latex
\varphi = \mathrm{sinal} \cdot \arccos\left(\hat{l}_{prox} \cdot \hat{l}_{dist}\right)
```

**Plano de flexão.** O vetor de dobra é a componente do eixo distal perpendicular ao proximal. Ele é classificado contra os eixos do corpo, não do mundo, para que "para dentro" valha igual nos dois lados.

```latex
\vec{b} = \hat{l}_{dist} - (\hat{l}_{dist} \cdot \hat{l}_{prox})\,\hat{l}_{prox}
```

**Torção relativa.** Giro de um segmento em relação ao outro em torno do eixo `longo` comum, medido pela decomposição swing-twist da rotação relativa.

**Proporção.** Posição normalizada dentro do limite, útil para animações e para comparar lados.

```latex
p = \frac{\varphi - \varphi_{min}}{\varphi_{max} - \varphi_{min}}
```

### 6.3 Articulações esféricas: três ângulos

Ombro e quadril não cabem em um número só. Eles recebem três componentes nomeados.

| Componente | Nome no código | Significa |
| --- | --- | --- |
| Elevação frontal | `elevacao_frontal_graus` | Braço indo para frente (+) ou para trás (-) |
| Abdução | `abducao_graus` | Braço afastando do corpo (+) ou cruzando a linha central (-) |
| Rotação axial | `rotacao_axial_graus` | Giro em torno do próprio eixo, palma para dentro (-) ou para fora (+) |

Cada componente tem seu próprio mínimo, máximo e estado. Um braço pode estar esticado no cotovelo e ainda assim estar elevado no ombro.

### 6.4 Catálogo de articulações

Os limites abaixo são uma proposta inicial para um mascote de estilo cartoon, mais soltos que os de um corpo humano. Todos entram como `A_VALIDAR` até serem conferidos na calibração visual contra o que a animação realmente faz.

| Articulação | Tipo | Proximal | Distal | Faixa proposta (graus) | Observação |
| --- | --- | --- | --- | --- | --- |
| `ombro_direito` | ESFERICA | `CORPO` | `BRACO_DIREITO` | elevação -60 a 180, abdução -30 a 170 | Três componentes |
| `cotovelo_direito` | DOBRADICA | `BRACO_DIREITO` | `ANTEBRACO_DIREITO` | -10 a 150 | Já medido por `right-arm` e `ant-arm` |
| `punho_direito` | ESFERICA | `ANTEBRACO_DIREITO` | `MAO_DIREITA` | flexão -70 a 80, desvio -20 a 30 | Mão pode ser rígida; confirmar no GLTF |
| `ombro_esquerdo` | ESFERICA | `CORPO` | braço esquerdo | igual ao direito, espelhado | A\_CONFIRMAR: nome do grupo |
| `cotovelo_esquerdo` | DOBRADICA | braço esquerdo | antebraço esquerdo | -10 a 150 | A\_CONFIRMAR: o GLTF só expõe `hand2` com certeza |
| `punho_esquerdo` | ESFERICA | antebraço esquerdo | `MAO_ESQUERDA` | igual ao direito | A\_CONFIRMAR |
| `pescoco` | PIVO | `CORPO` | `CABECA` | giro -80 a 80, inclinação -40 a 50, lateral -30 a 30 | Três componentes, como o ombro |
| `dobradica_porta` | DOBRADICA | `CORPO` | `PORTA` | 0 a 120 | Eixo `eixo_giro` (Y), ver seção 7.3 |
| `quadril_direito`, `quadril_esquerdo` | ESFERICA | `CORPO` | perna | A\_CONFIRMAR | O README cita pernas articuladas |
| `joelho_direito`, `joelho_esquerdo` | DOBRADICA | coxa | canela | 0 a 140 | A\_CONFIRMAR |
| `tornozelo_direito` | DOBRADICA | perna | `PE_DIREITO` | -40 a 50 | Eixo `longo` do pé já existe |
| `tornozelo_esquerdo` | DOBRADICA | perna | `PE_ESQUERDO` | -40 a 50 |  |
| `tentaculo_N_elo_K` | CADEIA | elo K-1 | elo K | 0 a 60 por elo | 8 segmentos por tentáculo, ver seção 7.6 |

### 6.5 Classificação do estado

Limiares iniciais, ajustáveis na seção 10.

| Estado | Intervalo de flexão (graus) |
| --- | --- |
| `HIPEREXTENDIDO` | menor que `angulo_min` |
| `ESTICADO` | de 0 a 15 |
| `LEVE` | acima de 15 até 45 |
| `DOBRADO` | acima de 45 até 110 |
| `MUITO_DOBRADO` | acima de 110 |

Um campo `fora_do_limite` é verdadeiro quando a pose ultrapassa `angulo_min` ou `angulo_max`. Isso flagra animação procedural que quebra o corpo, o que hoje só se descobre olhando o render.

### 6.6 Assinatura da função

```python
def medir_flexao(
    longo_proximal_mundo: Vetor3,
    longo_distal_mundo: Vetor3,
    referencia_dobra_mundo: Vetor3,
) -> tuple[float, Vetor3]:
    """Retorna (angulo_flexao_graus assinado, vetor_de_dobra_mundo)."""

def analisar_articulacao(
    definicao: DefinicaoArticulacao,
    partes: dict[Parte, EstadoParte],
) -> EstadoArticulacao: ...
```

`DefinicaoArticulacao` é um registro estático (nome, tipo, par de partes, limites, sinal natural) que vive num único dicionário `ARTICULACOES`, do mesmo jeito que `VETORES_REFERENCIA` vive hoje.

## 7. Detecção por região do corpo

Cada região tem vetores de referência, medições próprias, Enums de classificação e limiares. A regra de nomes dos vetores muda de forma uniforme: eixos viram `eixo_*`, normais viram `normal_*`, e todo vetor novo nasce com `Validacao.A_VALIDAR`.

### 7.1 Mãos (`MAO_DIREITA`, `MAO_ESQUERDA`)

**Vetores de referência**

| Nome novo | Nome atual | Significa | Validação |
| --- | --- | --- | --- |
| `normal_palma` | `normal_palma` | Sai perpendicular da palma | A\_VALIDAR |
| `normal_dorso` | `dorso` | Oposto da palma | A\_VALIDAR |
| `eixo_dedos` | `direcao_dedos` | Do punho para a ponta dos dedos | CONFIRMADO no idle e no wave |
| `eixo_polegar` | novo | Do punho para a ponta do polegar | A\_CONFIRMAR se o modelo tem polegar |
| `eixo_punho` | novo | Prolonga o antebraço até a mão | A\_VALIDAR |

**Enums**

```python
class DirecaoPalma(Enum):
    PARA_CIMA = "para_cima"
    PARA_BAIXO = "para_baixo"
    PARA_FRENTE = "para_frente"
    PARA_TRAS = "para_tras"
    PARA_DENTRO = "para_dentro"   # em direção à linha central do corpo
    PARA_FORA = "para_fora"
    DIAGONAL = "diagonal"

class DirecaoDedos(Enum):
    CIMA = "cima"; BAIXO = "baixo"; FRENTE = "frente"
    TRAS = "tras"; DENTRO = "dentro"; FORA = "fora"; DIAGONAL = "diagonal"

class GestoMao(Enum):
    RELAXADA = "relaxada"
    ACENANDO = "acenando"
    APONTANDO = "apontando"
    POLEGAR_CIMA = "polegar_cima"
    POLEGAR_BAIXO = "polegar_baixo"
    PARADA_ABERTA = "parada_aberta"   # palma para frente, dedos para cima
    NO_ROSTO = "no_rosto"
    NO_PEITO = "no_peito"
    NA_CINTURA = "na_cintura"
```

`PARA_DENTRO` e `PARA_FORA` são relativos ao corpo, não ao mundo. Hoje, na mesma pose idle, a mão esquerda reporta `PALMA_PARA_DENTRO` (relativo ao corpo) e `DORSO_DIREITA` (eixo do mundo). Unificar em relativo ao corpo evita que o mesmo gesto espelhado gere flags diferentes.

**Medições extras**

| Nome | Descrição | Unidade |
| --- | --- | --- |
| `distancia_ao_rosto_u` | Origem da mão até o centro da cabeça | u |
| `distancia_ao_peito_u` | Origem da mão até o peito | u |
| `distancia_ao_corpo_u` | Menor distância até o tronco | u |
| `cruza_linha_central` | Mão passa para o lado oposto do corpo | bool |
| `mao_acima_do_ombro` | `origem_mundo.y` maior que `y_ombro` | bool |
| `alcance_norm` | Distância ombro até mão dividida pelo comprimento do braço, 1,0 = totalmente esticado | 0,0 a 1,0 |
| `aponta_para_cursor_graus` | Ângulo entre `eixo_dedos` e a direção do cursor | graus |
| `aponta_para_camera_graus` | Ângulo entre `eixo_dedos` e a câmera | graus |
| `oscilacao_hz` | Frequência do movimento lateral, detecta aceno | Hz |
| `amplitude_oscilacao_graus` | Amplitude pico a pico do aceno | graus |

**Regras de classificação (exemplos)**

- `ACENANDO`: mão acima do ombro, `oscilacao_hz` entre 1,0 e 4,0, amplitude acima de 20 graus.
- `PARADA_ABERTA`: `normal_palma` em `FRENTE` com alinhamento acima de 0,8 e `eixo_dedos` em `CIMA`.
- `NO_ROSTO`: `distancia_ao_rosto_u` abaixo de `LIMIAR_MAO_ROSTO_U`.

### 7.2 Cabeça (`CABECA`)

**Vetores de referência**

| Nome novo | Nome atual | Significa |
| --- | --- | --- |
| `eixo_olhar` | `olhar` | Para onde o rosto aponta |
| `eixo_topo` | `topo` | Da base da cabeça para a coroa |
| `eixo_lateral` | novo | Da orelha esquerda para a direita, mede inclinação lateral |

**Medições**

| Nome | Descrição | Unidade |
| --- | --- | --- |
| `giro_cabeca_graus` | Yaw da cabeça em relação ao tronco, + para a direita | graus |
| `inclinacao_cabeca_graus` | Pitch em relação ao tronco, + olhando para cima | graus |
| `rolagem_cabeca_graus` | Roll, + inclinada para a direita | graus |
| `olhar_para_cursor_graus` | Ângulo entre `eixo_olhar` e a direção até o cursor | graus |
| `olhar_para_camera_graus` | Ângulo entre `eixo_olhar` e a câmera | graus |
| `olhar_para_mao_graus` | Ângulo até cada mão, para detectar "olhando a própria mão" | graus |

**Enums**

```python
class OlharHorizontal(Enum):
    FRENTE = "frente"; DIREITA = "direita"; ESQUERDA = "esquerda"
    DIREITA_EXTREMA = "direita_extrema"; ESQUERDA_EXTREMA = "esquerda_extrema"

class OlharVertical(Enum):
    CIMA = "cima"; NIVEL = "nivel"; BAIXO = "baixo"

class InclinacaoCabeca(Enum):
    RETA = "reta"; DIREITA = "direita"; ESQUERDA = "esquerda"

class AlvoOlhar(Enum):
    CURSOR = "cursor"; CAMERA = "camera"; MAO_DIREITA = "mao_direita"
    MAO_ESQUERDA = "mao_esquerda"; CHAO = "chao"; NENHUM = "nenhum"
```

`AlvoOlhar` responde "para quem o Mário está olhando?", que o hover e o clique já usam sem nome. O alvo é o objeto com menor ângulo abaixo de `LIMIAR_ALVO_OLHAR_GRAUS`.

### 7.3 Porta (`PORTA`)

A porta é o elemento mais expressivo do personagem: ela tem estado, velocidade e relação com os tentáculos.

**Vetores de referência**

| Nome novo | Nome atual | Significa |
| --- | --- | --- |
| `normal_porta` | `normal` | Sai perpendicular à face externa |
| `eixo_dobradica` | `eixo_giro` | Linha da dobradiça, vertical em Y |
| `eixo_borda_livre` | novo | Da dobradiça para a borda que se abre |

**Medições**

| Nome | Descrição | Unidade |
| --- | --- | --- |
| `abertura_graus` | Ângulo entre `normal_porta` atual e a de repouso, em torno de `eixo_dobradica` | graus, 0 a 180 |
| `abertura_norm` | `abertura_graus` dividido pelo máximo | 0,0 a 1,0 |
| `sentido_abertura` | `ABRINDO`, `FECHANDO` ou `PARADO` | Enum |
| `velocidade_abertura_graus_s` | Derivada da abertura | graus/s |
| `lado_da_dobradica` | Em qual lado do corpo a dobradiça está | `Lado` |
| `interior_visivel_norm` | Quanto do interior aparece para a câmera | 0,0 a 1,0 |
| `vao_u` | Largura da fresta pela qual os tentáculos saem | u |

**Estados**

```python
class EstadoPorta(Enum):
    FECHADA = "fechada"          # abaixo de 5 graus
    FRESTA = "fresta"            # 5 a 15
    ENTREABERTA = "entreaberta"  # 15 a 45
    ABERTA = "aberta"            # 45 a 100
    ESCANCARADA = "escancarada"  # acima de 100
```

O guia de calibração já registra `FECHADA` no idle, `ENTREABERTA` na dança e "muito aberta" no espirro. As faixas acima são uma proposta e entram como `A_VALIDAR`, em especial a fronteira entre `ENTREABERTA` e `ABERTA`.

### 7.4 Tronco (`CORPO`)

**Vetores de referência**

| Nome novo | Nome atual | Significa |
| --- | --- | --- |
| `eixo_frente` | `frente` | Do centro do peito para fora |
| `eixo_cima` | `cima` | Da cintura para o topo do tronco |
| `eixo_lateral` | novo | Do lado esquerdo para o direito do tronco |

**Medições**

| Nome | Descrição | Unidade |
| --- | --- | --- |
| `inclinacao_frontal_graus` | Pitch do tronco, + inclinado para frente | graus |
| `inclinacao_lateral_graus` | Roll do tronco, + inclinado para a direita | graus |
| `giro_tronco_graus` | Yaw em relação à base, + para a direita | graus |
| `altura_centro_norm` | Altura do centro do corpo dividida pela altura em pé | 0,0 a 1,0+ |
| `agachamento_norm` | `1 - altura_centro_norm`, 0 = em pé | 0,0 a 1,0 |
| `balanco_lateral_u` | Deslocamento horizontal do centro sobre a base | u |
| `compressao_norm` | Squash e stretch do corpo, se a animação usar escala | 0,0 a 1,0 |

**Enums**

```python
class PosturaTronco(Enum):
    EM_PE = "em_pe"
    INCLINADO_FRENTE = "inclinado_frente"
    INCLINADO_TRAS = "inclinado_tras"
    INCLINADO_DIREITA = "inclinado_direita"
    INCLINADO_ESQUERDA = "inclinado_esquerda"
    AGACHADO = "agachado"
    DEITADO = "deitado"
    GIRADO = "girado"
```

Cada posição de dança, sono e espirro fica descrita pela combinação de `PosturaTronco`, `EstadoPorta` e `InclinacaoCabeca`, sem texto livre.

### 7.5 Braços, pernas e pés

**Vetores de referência**

| Nome novo | Nome atual | Partes | Significa |
| --- | --- | --- | --- |
| `eixo_longo` | `longo` | braços, antebraços, pernas, pés | Do início ao fim do segmento |
| `normal_sola` | novo | pés | Perpendicular à sola, aponta para o chão em pé |
| `eixo_frente_pe` | novo | pés | Para onde os dedos do pé apontam |

**Medições dos braços**

| Nome | Descrição |
| --- | --- |
| `elevacao_frontal_graus`, `abducao_graus`, `rotacao_axial_graus` | Os três componentes do ombro (seção 6.3) |
| `esticado_norm` | Distância ombro até punho dividida pelo comprimento total, 1,0 = reto |
| `posicao_braco` | Enum `PosicaoBraco` |

```python
class PosicaoBraco(Enum):
    CAIDO = "caido"
    LEVANTADO_FRENTE = "levantado_frente"
    LEVANTADO_LATERAL = "levantado_lateral"
    ACIMA_CABECA = "acima_cabeca"
    ATRAS = "atras"
    CRUZADO = "cruzado"
    NA_CINTURA = "na_cintura"
    DOBRADO_NO_PEITO = "dobrado_no_peito"
```

**Medições das pernas e pés**

| Nome | Descrição | Unidade |
| --- | --- | --- |
| `contato_chao` | Ponta ou sola abaixo de `y_chao + TOLERANCIA_CHAO_U` | bool |
| `altura_do_chao_u` | Distância vertical da sola até o chão | u |
| `inclinacao_pe_graus` | Ângulo entre `normal_sola` e o eixo vertical | graus |
| `apoio` | Enum `ApoioPe` | Enum |
| `passo_u` | Distância horizontal entre os dois pés | u |
| `afastamento_lateral_u` | Distância entre os pés no eixo X | u |

```python
class ApoioPe(Enum):
    APOIADO = "apoiado"
    LEVANTADO = "levantado"
    NA_PONTA = "na_ponta"
    NO_CALCANHAR = "no_calcanhar"
    SUSPENSO = "suspenso"      # nenhum pé toca o chão
```

O flag atual `BAIXADO` para o eixo longo do pé continua válido como `eixo_longo` em `BAIXO`, mas passa a ser derivado, não o resultado final.

### 7.6 Tentáculos

Os tentáculos vêm de `tentacle_system.py` (física procedural com 8 segmentos cada, saindo da porta), não de grupos do GLTF. Por isso o mapeamento define uma interface de leitura, e o módulo de análise não depende do sistema de física.

```python
class FonteTentaculo(Protocol):
    def pontos_mundo(self) -> list[Vetor3]: ...   # base, elos, ponta
    def pingando(self) -> bool: ...
```

**Medições por tentáculo**

| Nome | Descrição | Unidade |
| --- | --- | --- |
| `comprimento_total_u` | Soma dos elos | u |
| `extensao_norm` | Distância base até ponta dividida pelo comprimento total, 1,0 = reto, 0,0 = enrolado | 0,0 a 1,0 |
| `curvatura_total_graus` | Soma das flexões de todos os elos | graus |
| `curvatura_elo_graus` | Lista com a flexão de cada elo | graus |
| `elo_mais_dobrado` | Índice do elo com maior flexão | int |
| `emergencia_u` | Quanto a base saiu da porta | u |
| `direcao_ponta` | `Direcao` do último elo | `Direcao` |
| `ponta_mundo` | Posição da ponta | u |
| `distancia_ponta_corpo_u` | Quão longe a ponta está do tronco | u |
| `fase_onda_norm` | Fase da ondulação, se periódica | 0,0 a 1,0 |
| `gosma_pingando` | Há gota se formando ou caindo | bool |

```python
class EstadoTentaculo(Enum):
    RECOLHIDO = "recolhido"
    EMERGINDO = "emergindo"
    ESTENDIDO = "estendido"
    ONDULANDO = "ondulando"
    ENROLADO = "enrolado"
    RECOLHENDO = "recolhendo"
```

`ONDULANDO` e `EMERGINDO` dependem da dinâmica (seção 9), porque são sobre movimento, não sobre pose estática.

### 7.7 Elementos ainda sem mapeamento

O README e os gestos citam elementos que não aparecem nos vetores de referência. Antes de declarar o corpo "todo mapeado", cada item abaixo precisa de uma entrada em `Parte` ou uma decisão explícita de ficar de fora.

| Elemento | Origem da menção | Proposta |
| --- | --- | --- |
| Jaqueta | Gesto "soltar os ombros" (ajustar a jaqueta) | Mapear como parte secundária que segue os ombros, com `ajuste_jaqueta_norm` |
| Polegar e dedos | Teste de gesto "thumbs up" | Confirmar no GLTF se existem nós de dedos; senão, derivar o gesto da pose do punho |
| Olhos, boca e expressão | Rosto com faces invisíveis na textura | Mapear só se houver geometria ou UV animados; caso contrário, fica fora |
| Braço e antebraço esquerdos | Existe `hand2` | Confirmar nomes dos grupos no GLTF |
| Pernas, coxas e canelas | README fala de pernas articuladas | Confirmar nomes dos grupos no GLTF |
| Gota de gosma | Tentáculos gotejam gosma rosa | Mapear posição e estado como `gosma_pingando` |
| Contorno | Acompanha a pose | Fora do mapeamento, é render |

Uma tarefa curta resolve a maior parte disso: listar todos os nós do GLTF (`model.py` já carrega o arquivo) e comparar com o enum `Parte`. Um teste pode falhar se surgir um grupo no modelo sem entrada no enum.

## 8. Relações entre partes e postura geral

Muita informação útil só aparece quando duas partes são comparadas. Mão no rosto, braços cruzados e pés afastados não pertencem a nenhuma parte sozinha. Essas medições ficam em `Relacao` (seção 4.5) e alimentam o resumo `Postura`.

### 8.1 Catálogo de relações

| Nome | Partes | Cálculo | Unidade |
| --- | --- | --- | --- |
| `distancia_mao_cabeca` (um por lado) | mão, cabeça | Distância entre origens | u |
| `distancia_mao_peito` (um por lado) | mão, corpo | Distância até o centro do peito | u |
| `distancia_entre_maos_u` | as duas mãos | Distância entre origens | u |
| `maos_unidas` | as duas mãos | `distancia_entre_maos_u` menor que `LIMIAR_MAOS_UNIDAS_U` | bool |
| `bracos_cruzados` | mãos, corpo | As duas mãos cruzam a linha central em alturas próximas | bool |
| `simetria_bracos_norm` | braços | Ver fórmula abaixo | 0,0 a 1,0 |
| `simetria_pernas_norm` | pernas | Idem, para as pernas | 0,0 a 1,0 |
| `diferenca_cabeca_tronco_graus` | cabeça, corpo | Ângulo entre `eixo_olhar` e `eixo_frente` | graus |
| `corpo_para_camera_graus` | corpo | Ângulo entre `eixo_frente` e a câmera | graus |
| `afastamento_pes_u` | os dois pés | Distância no plano horizontal | u |
| `ambos_pes_no_chao` | os dois pés | `contato_chao` nos dois | bool |
| `altura_relativa_maos_u` | as duas mãos | Diferença de altura entre elas, + se a direita está mais alta | u |
| `maior_extensao_u` | todas | Maior distância entre duas extremidades | u |
| `silhueta_largura_u`, `silhueta_altura_u` | todas | Caixa envolvente da pose no plano da tela | u |
| `porta_para_camera_graus` | porta | Ângulo entre `normal_porta` e a câmera | graus |

```latex
simetria = 1 - \frac{1}{N}\sum_{i=1}^{N} \frac{|\varphi_{dir,i} - \varphi_{esq,i}|}{\varphi_{max,i} - \varphi_{min,i}}
```

A silhueta merece atenção especial: o overlay usa color key e deixa cliques atravessarem as áreas vazias. A caixa envolvente da pose diz o quanto a janela precisa cobrir quando o corpo estica, por exemplo num aceno com o braço totalmente esticado.

### 8.2 Equilíbrio

Útil na dança e na física de queda: o centro de massa deve ficar sobre a base de apoio formada pelos pés em contato.

| Nome | Descrição |
| --- | --- |
| `centro_massa_mundo` | Média ponderada das origens das partes, com pesos propostos por parte |
| `base_apoio` | Segmento ou polígono entre os pés com `contato_chao` |
| `dentro_da_base_apoio` | Projeção horizontal do centro de massa cai dentro da base |
| `equilibrio_norm` | 1,0 no centro da base, 0,0 na borda ou fora |
| `margem_estabilidade_u` | Distância do centro de massa até a borda da base |

Os pesos são propostos e entram como `A_VALIDAR`: tronco e cabeça pesam mais que mãos e tentáculos. O objetivo é uma medida relativa, não física exata.

### 8.3 Resumo de postura

O objeto `Postura` condensa o corpo todo em campos tipados. É o que testes e a descrição em linguagem natural consomem.

```python
@dataclass(frozen=True)
class Postura:
    tronco: PosturaTronco
    estado_porta: EstadoPorta
    inclinacao_cabeca: InclinacaoCabeca
    alvo_olhar: AlvoOlhar
    posicao_braco_direito: PosicaoBraco
    posicao_braco_esquerdo: PosicaoBraco
    gesto_mao_direita: GestoMao
    gesto_mao_esquerda: GestoMao
    apoio: ApoioPe
    estados_tentaculos: tuple[EstadoTentaculo, ...]
    simetria_norm: float      # média de simetria_bracos e simetria_pernas
    expansao_norm: float      # maior_extensao_u dividido pela altura em pé
    equilibrio_norm: float
    energia_norm: float       # soma das velocidades angulares normalizadas
```

| Campo | Para que serve |
| --- | --- |
| `simetria_norm` | Separa poses de dança simétricas de poses casuais |
| `expansao_norm` | Distingue corpo encolhido (sono, timidez) de corpo aberto (alongar, comemorar) |
| `energia_norm` | Separa idle parado de dança, mesmo que a pose congelada seja parecida |

Esses três campos tornam as nove personalidades (Tranquila, Curiosa, Brincalhona, Tímida, Confiante, Street, Fighter, Rhythm, Stylish) comparáveis por números, o que abre caminho para um teste automático do tipo "a personalidade Tímida tem expansão média menor que a Confiante".

## 9. Dados dinâmicos entre frames

Uma pose congelada não distingue um aceno de uma mão parada no alto. A análise dinâmica guarda o frame anterior e calcula velocidade, sentido, fase e eventos. Ela é opcional: sem memória, os campos dinâmicos ficam `None` e o resto da análise segue funcionando.

### 9.1 Memória da análise

```python
@dataclass
class MemoriaAnalise:
    """Único objeto mutável do módulo. Guarda os últimos frames."""
    capacidade: int = 120                      # frames guardados por parte
    historico: dict[Parte, deque[EstadoParte]] = field(default_factory=dict)
    tempos_s: deque[float] = field(default_factory=deque)
    estados_anteriores: dict[str, Enum] = field(default_factory=dict)

def atualizar_memoria(memoria: MemoriaAnalise, relatorio: RelatorioRig) -> None: ...
def calcular_dinamica(memoria: MemoriaAnalise) -> dict[Parte, DinamicaParte]: ...
```

O restante do módulo permanece funcional e imutável. Só `MemoriaAnalise` muda, e ela é passada explicitamente, sem estado global.

### 9.2 Grandezas

| Nome | Cálculo | Unidade |
| --- | --- | --- |
| `velocidade_angular_graus_s` | Ângulo da rotação relativa entre dois frames dividido por `dt` | graus/s |
| `velocidade_linear_u_s` | Distância entre origens dividida por `dt` | u/s |
| `aceleracao_angular_graus_s2` | Variação da velocidade angular | graus/s² |
| `sentido_vertical` | Sinal de `d(origem.y)/dt` fora da zona morta | `SentidoMovimento` |
| `sentido_giro` | Sinal da rotação em torno de Y | `SentidoMovimento` |
| `parado_ha_s` | Tempo contínuo abaixo de `LIMIAR_PARADO_GRAUS_S` | s |
| `oscilacao_hz` | Cruzamentos por zero do deslocamento lateral, com histerese | Hz |
| `fase_ciclo_norm` | Posição dentro do período de uma animação periódica | 0,0 a 1,0 |
| `velocidade_abertura_graus_s` | Derivada de `abertura_graus` da porta | graus/s |
| `velocidade_flexao_graus_s` | Derivada do ângulo de flexão de cada articulação | graus/s |

```latex
\omega = \frac{\arccos\left(\frac{\mathrm{tr}(R_{t-1}^{T} R_{t}) - 1}{2}\right)}{\Delta t}
```

### 9.3 Cuidados de implementação

1. **Primeiro frame.** Não há anterior, então velocidade e aceleração são `None`, nunca zero. Zero significa "parado", e isso seria falso.
2. **Ângulos com salto.** Valores em HPR saltam de 180 para -180. Calcular a velocidade pela rotação relativa (fórmula acima), nunca pela diferença de Euler.
3. **Ruído.** Aplicar média exponencial com constante `SUAVIZACAO_VELOCIDADE` (proposta 0,3) antes de comparar com limiares, para a flag não piscar entre frames.
4. **Zona morta e histerese.** Estados como `PARADO` usam dois limiares (entrar e sair) para não oscilar na fronteira.
5. **`dt` variável.** O Panda3D entrega `dt` real; nos testes use passo fixo. A API aceita os dois.
6. **Fase periódica.** As animações procedurais são funções de `t`, então a fase mais confiável vem da própria animação: cada pose declara `periodo_s`, e `fase_ciclo_norm = (t mod periodo_s) / periodo_s`. Detectar o período por autocorrelação fica como alternativa para poses sem período declarado.

### 9.4 Eventos

Transições de estado importam tanto quanto o estado. Elas viram eventos com marca de tempo.

```python
@dataclass(frozen=True)
class EventoMapa:
    t_s: float
    parte: Parte | None
    tipo: str            # "porta_abriu", "pe_tocou_chao", "mao_comecou_acenar"
    de: Enum | None
    para: Enum | None
```

| Evento | Disparo |
| --- | --- |
| `porta_abriu`, `porta_fechou` | `EstadoPorta` muda de ou para `FECHADA` |
| `pe_tocou_chao`, `pe_saiu_do_chao` | `contato_chao` muda |
| `mao_comecou_acenar`, `mao_parou_de_acenar` | `GestoMao` muda de ou para `ACENANDO` |
| `olhar_mudou_alvo` | `AlvoOlhar` muda |
| `articulacao_no_limite` | `fora_do_limite` vira verdadeiro |
| `tentaculo_emergiu`, `tentaculo_recolheu` | `EstadoTentaculo` muda |
| `corpo_perdeu_equilibrio` | `dentro_da_base_apoio` vira falso |

Os eventos tornam possível testar sequências inteiras ("no espirro a porta abre antes de a cabeça inclinar") sem comparar frame a frame.

### 9.5 Análise de uma sequência

```python
def analisar_sequencia(
    rig: Rig, pose: str, t_inicio_s: float, t_fim_s: float, passo_s: float = 1 / 30,
) -> tuple[list[RelatorioRig], list[EventoMapa]]: ...
```

A calibração visual passa a poder gerar, além de uma imagem no instante `--t`, um gráfico do ângulo ao longo do tempo e a lista de eventos da pose. Isso responde se uma animação passa por posições que quebram o corpo.

## 10. Limiares e classificadores

Toda flag nasce de um número comparado a um limiar. Os limiares moram em um único lugar (`src/sejoga/rig_limiares.py`), com nome, unidade e estado de validação. Isso corrige o problema de hoje: o motivo de uma flag aparecer ou não está espalhado em condicionais dentro das funções.

### 10.1 Regras

1. Nenhum número mágico dentro de `classificar_*`. Tudo vem de `Limiares`.
2. Distâncias são guardadas como fração da altura em pé (`_rel`), não em unidades da cena. A escala do mascote vai de 0,5x a 2,5x, e um limiar em unidades quebraria nos extremos.
3. Fronteiras sensíveis usam histerese: um limiar para entrar no estado e outro, menor, para sair.
4. Cada limiar tem um estado `CONFIRMADO` ou `A_VALIDAR`, atualizado pela calibração visual.
5. Mudar um limiar exige rodar os testes de poses de referência (seção 13).

```python
@dataclass(frozen=True)
class Limiares:
    # Direção
    alinhamento_min_norm: float = 0.80
    margem_ambiguidade: float = 0.15
    norma_min: float = 1e-6
    # Flexão (graus)
    esticado_ate_graus: float = 15.0
    leve_ate_graus: float = 45.0
    dobrado_ate_graus: float = 110.0
    tolerancia_limite_graus: float = 2.0
    # Porta (graus)
    porta_fechada_ate: float = 5.0
    porta_fresta_ate: float = 15.0
    porta_entreaberta_ate: float = 45.0
    porta_aberta_ate: float = 100.0
    # Cabeça (graus)
    olhar_frente_graus: float = 15.0
    olhar_extremo_graus: float = 60.0
    olhar_nivel_graus: float = 10.0
    cabeca_reta_graus: float = 8.0
    alvo_olhar_graus: float = 25.0
    # Distâncias relativas à altura em pé
    mao_rosto_rel: float = 0.18
    maos_unidas_rel: float = 0.08
    tolerancia_chao_rel: float = 0.02
    # Dinâmica
    parado_entrar_graus_s: float = 5.0
    parado_sair_graus_s: float = 8.0
    suavizacao_velocidade: float = 0.30
    aceno_hz_min: float = 1.0
    aceno_hz_max: float = 4.0
    aceno_amplitude_graus: float = 20.0
    # Tronco
    tronco_inclinado_graus: float = 12.0
    agachado_norm: float = 0.25
    deitado_graus: float = 60.0
```

### 10.2 Tabela de limiares

Todos os valores abaixo são propostas iniciais, salvo onde indicado. Os que já têm correspondência com o guia de calibração aparecem como tal.

| Limiar | Padrão | Unidade | Usado por | Validação |
| --- | --- | --- | --- | --- |
| `alinhamento_min_norm` | 0,80 | cos | Distinguir eixo puro de diagonal | A\_VALIDAR |
| `margem_ambiguidade` | 0,15 | cos | Marcar `Direcao.ambigua` | A\_VALIDAR |
| `esticado_ate_graus` | 15 | graus | `EstadoFlexao.ESTICADO` | A\_VALIDAR |
| `leve_ate_graus` | 45 | graus | `EstadoFlexao.LEVE` | A\_VALIDAR |
| `dobrado_ate_graus` | 110 | graus | `EstadoFlexao.DOBRADO` | A\_VALIDAR |
| `porta_fechada_ate` | 5 | graus | `EstadoPorta.FECHADA` (idle é fechada) | CONFIRMADO no idle |
| `porta_entreaberta_ate` | 45 | graus | `EstadoPorta.ENTREABERTA` (dança é entreaberta) | A\_VALIDAR |
| `olhar_frente_graus` | 15 | graus | `OlharHorizontal.FRENTE` | A\_VALIDAR |
| `mao_rosto_rel` | 0,18 | fração da altura | `GestoMao.NO_ROSTO` | A\_VALIDAR |
| `maos_unidas_rel` | 0,08 | fração da altura | `maos_unidas` | A\_VALIDAR |
| `aceno_hz_min`, `aceno_hz_max` | 1,0 a 4,0 | Hz | `GestoMao.ACENANDO` | A\_VALIDAR contra o wave |
| `parado_entrar_graus_s` | 5 | graus/s | `SentidoMovimento.PARADO` | A\_VALIDAR |

### 10.3 Classificadores genéricos

A maior parte das flags é "em qual faixa o número cai". Uma função só cobre isso, em vez de uma cadeia de `if` por parte do corpo.

```python
def classificar_por_faixas(
    valor: float,
    faixas: Sequence[tuple[float, E]],   # (limite_superior, estado), em ordem crescente
    acima: E,
) -> E:
    for limite, estado in faixas:
        if valor <= limite:
            return estado
    return acima

def classificar_direcao(vetor: Vetor3, limiares: Limiares) -> Direcao: ...

def classificar_com_histerese(
    valor: float, anterior: E | None, entrar: Mapping[E, float], sair: Mapping[E, float],
) -> E: ...
```

`classificar_direcao` calcula o produto escalar com os seis eixos, escolhe o maior como principal, o segundo como secundária, e marca `ambigua` quando a diferença é menor que `margem_ambiguidade`. Quando o alinhamento do principal fica abaixo de `alinhamento_min_norm`, a descrição em linguagem natural usa a diagonal ("para cima e para frente") em vez da flag seca.

### 10.4 Como ajustar um limiar

1. Gerar a imagem de calibração da pose onde o limiar importa (`tools/calibrar_vetores.py --pose <nome>`).
2. Conferir a medição numérica impressa junto da flag.
3. Se o olho humano discorda da flag, mover o limiar e rodar os testes de poses de referência.
4. Marcar o limiar como `CONFIRMADO` com a pose e a data usadas como evidência.

## 11. Descrição em linguagem natural e formato do relatório

O mesmo `RelatorioRig` precisa servir a três leitores: uma pessoa lendo o console, um teste comparando valores e uma ferramenta de calibração desenhando setas. Por isso o relatório tem uma forma estruturada (a verdade) e três saídas derivadas.

### 11.1 Saídas

| Saída | Função | Quem usa |
| --- | --- | --- |
| Frase | `descrever_rig(relatorio, detalhe)` | Console, logs, pedidos de ajuda sobre uma pose |
| Tabela de console | `formatar_tabela(relatorio)` | `calibrar_vetores.py`, depuração rápida |
| Dicionário JSON | `relatorio_para_dict(relatorio)` | Testes de snapshot, comparação entre versões |

```python
class Detalhe(Enum):
    RESUMO = "resumo"      # uma ou duas frases
    NORMAL = "normal"      # uma frase por região que saiu do repouso
    COMPLETO = "completo"  # todas as partes, com números
```

### 11.2 Regras de redação

1. **Dizer só o que mudou do repouso** nos níveis `RESUMO` e `NORMAL`. "Pé direito baixado" no idle é ruído.
2. **Agrupar lados iguais.** "As duas mãos com a palma para baixo" em vez de duas frases.
3. **Diagonal por extenso.** Alinhamento abaixo de `alinhamento_min_norm` vira "para cima e para frente", com o eixo secundário.
4. **Ordem fixa por importância expressiva:** porta, cabeça e olhar, braços e mãos, tronco, pernas e pés, tentáculos.
5. **Nunca esconder a incerteza.** Flag com `ambigua` ou `A_VALIDAR` leva um marcador discreto: "palma para cima (a validar)".
6. **Um vocabulário só**, vindo de uma tabela `ROTULOS` que mapeia cada membro de Enum para o texto. Mudar "entreaberta" para "fresta aberta" exige editar um lugar.

### 11.3 Exemplo ilustrativo

Pose `wave` em t = 1,00 s. O texto abaixo mostra o formato pretendido; os números não são medições reais.

```text
RESUMO
Aceno com a mão direita: braço direito levantado e dobrado, palma para cima.
Porta fechada, cabeça de frente.

NORMAL
Porta: fechada.
Cabeça: olhando de frente para o cursor, reta.
Braço direito: levantado para o lado, cotovelo dobrado.
Mão direita: acenando, palma para cima, dedos para cima.
Braço esquerdo: caído, esticado.
Tronco: em pé.

COMPLETO (trecho)
mao_direita   palma  PARA_CIMA   alinh 0.97  incl 12.4°  azim 85°   (a validar)
mao_direita   dedos  CIMA        alinh 0.93  incl 21.0°
cotovelo_dir  flexao 78.3° DOBRADO  prop 0.52  plano PARA_FRENTE  torcao 14°
mao_direita   osc 2.4 Hz  amplitude 31°  fase 0.37
```

### 11.4 Formato JSON

O JSON serializa cada Enum pelo valor e cada tupla como lista. Ele leva um campo de versão para que snapshots antigos não quebrem silenciosamente.

```json
{
  "versao_esquema": 1,
  "t_s": 1.0,
  "pose": "wave",
  "partes": {
    "hand": {
      "lado": "direita",
      "validacao": "a_validar",
      "rot_mundo_graus": [10.0, 85.0, 0.0],
      "desvio_repouso_graus": 154.2,
      "torcao_graus": 172.0,
      "direcoes": {
        "normal_palma": {
          "principal": "cima",
          "secundaria": "frente",
          "alinhamento_norm": 0.97,
          "ambigua": false,
          "angulo_vertical_graus": 12.4,
          "azimute_graus": 85.0
        }
      },
      "flags": { "normal_palma": "para_cima" }
    }
  },
  "articulacoes": {
    "cotovelo_direito": {
      "angulo_flexao_graus": 78.3,
      "estado": "dobrado",
      "plano": "para_frente",
      "proporcao_norm": 0.52
    }
  },
  "postura": { "tronco": "em_pe", "estado_porta": "fechada" }
}
```

### 11.5 Compatibilidade com o console atual

Hoje o console imprime `nome_vetor -> FLAG`. A nova saída mantém essa linha como prefixo e acrescenta os números à direita, então quem já lê o formato antigo continua entendendo.

```text
antes:  normal_palma_direita -> PALMA_PARA_CIMA
depois: normal_palma_direita -> PALMA_PARA_CIMA  [alinh 0.97, incl 12.4°, azim 85°, a_validar]
```

Os nomes de flags antigos (`PALMA_PARA_CIMA`, `DORSO_BAIXO`, `PORTA_ENTREABERTA`) viram aliases dos novos Enums durante a migração (seção 13), para que testes existentes não quebrem de uma vez.

## 12. Tabela de renomeações

Os nomes "antes" vêm do guia de calibração visual de 05/11/2026 e da conversa sobre o `rig_debug`. Não li o código-fonte de `rig_debug.py` nem de `calibrar_vetores.py`, então toda linha marcada com `confirmar` precisa de um `grep` antes da troca.

### 12.1 Grupos do GLTF para `Parte`

O valor do Enum continua sendo o nome do grupo no modelo. Só o nome usado no código muda.

| Grupo no GLTF | Antes (string) | Depois |
| --- | --- | --- |
| `body` | `"body"` | `Parte.CORPO` |
| `head` | `"head"` | `Parte.CABECA` |
| `door` | `"door"` | `Parte.PORTA` |
| `right-arm` | `"right-arm"` | `Parte.BRACO_DIREITO` |
| `ant-arm` | `"ant-arm"` | `Parte.ANTEBRACO_DIREITO` |
| `hand` | `"hand"` | `Parte.MAO_DIREITA` |
| `hand2` | `"hand2"` | `Parte.MAO_ESQUERDA` |
| `right-feet` | `"right-feet"` | `Parte.PE_DIREITO` |
| `left-feet` | `"left-feet"` | `Parte.PE_ESQUERDO` |

### 12.2 Vetores de referência

Padrão novo: `eixo_*` para direções ao longo de uma parte, `normal_*` para perpendiculares a uma superfície.

| Parte | Antes | Depois | Motivo |
| --- | --- | --- | --- |
| mãos | `normal_palma` | `normal_palma` | Já segue o padrão |
| mãos | `dorso` | `normal_dorso` | É uma normal; o nome solto não diz isso |
| mãos | `direcao_dedos` | `eixo_dedos` | Padrão `eixo_*`, mais curto |
| cabeça | `olhar` | `eixo_olhar` | Padrão `eixo_*` |
| cabeça | `topo` | `eixo_topo` | "topo" parece posição, não direção |
| corpo | `frente` | `eixo_frente` | Padrão `eixo_*` |
| corpo | `cima` | `eixo_cima` | Padrão `eixo_*` |
| porta | `normal` | `normal_porta` | "normal" sozinho confunde com "comum" |
| porta | `eixo_giro` | `eixo_dobradica` | Diz o objeto físico, não a ação |
| membros | `longo` | `eixo_longo` | Padrão `eixo_*` |
| estrutura | `VETORES_REFERENCIA` | `VETORES_REPOUSO` | Combina com o sufixo `_repouso`; manter o nome antigo como alias |

### 12.3 Variáveis e campos

| Antes | Depois | Observação |
| --- | --- | --- |
| `vetor_repouso` (já proposto) | `vetor_repouso` | Mantido |
| `vetor_mundo` | `vetor_mundo` | Mantido |
| `rot_local` | `rot_local_graus` | Acrescenta a unidade |
| `rot_mundo` | `rot_mundo_graus` | Acrescenta a unidade |
| `flag` | `flags` (dicionário) e `Direcao` | Uma parte tem várias flags |
| `lado` como `str` | `Lado` (Enum) | Evita `"direta"` por engano |
| `pai` como `str` | `Parte \| None` | Hierarquia tipada |
| ângulos soltos | `*_graus` | Regra da seção 2.3 |
| distâncias soltas | `*_u` ou `*_rel` | `_rel` quando depende da altura em pé |
| tempos soltos | `*_s` | Segundos |
| `t` nas assinaturas | `t_s` | Torna a unidade explícita; confirmar |

### 12.4 Flags de saída para Enums

Os textos antigos continuam existindo como aliases na migração (seção 13).

| Flag antiga | Enum novo | Observação |
| --- | --- | --- |
| `PALMA_PARA_CIMA` | `DirecaoPalma.PARA_CIMA` |  |
| `PALMA_PARA_BAIXO` | `DirecaoPalma.PARA_BAIXO` |  |
| `PALMA_PARA_DENTRO` | `DirecaoPalma.PARA_DENTRO` | Relativo ao corpo, já era |
| `DORSO_CIMA`, `DORSO_BAIXO` | `Direcao.principal` de `normal_dorso` | Deixa de ser flag própria; deriva da direção |
| `DORSO_DIREITA` | `Direcao.principal` de `normal_dorso` | Passa a relativo ao corpo (`DENTRO` ou `FORA`) |
| `DEDOS_CIMA`, `DEDOS_BAIXO`, `DEDOS_ESQUERDA` | `DirecaoDedos.CIMA`, `.BAIXO`, `.DENTRO` ou `.FORA` | `ESQUERDA` vira relativo ao corpo |
| `OLHAR_FRENTE` | `OlharHorizontal.FRENTE` | Mais `OlharVertical` |
| `TOPO_CIMA` | `InclinacaoCabeca.RETA` | Derivado da inclinação e da rolagem |
| `PORTA_FECHADA` | `EstadoPorta.FECHADA` |  |
| `PORTA_ENTREABERTA` | `EstadoPorta.ENTREABERTA` |  |
| `EIXO_DE_GIRO` | `Direcao` de `eixo_dobradica` | Hoje é só um rótulo, passa a ter direção |
| `BAIXADO` (pé) | `Direcao.principal == BAIXO` mais `ApoioPe` | Separa direção de contato |

### 12.5 Funções e módulos

| Antes | Depois | Observação |
| --- | --- | --- |
| `matriz_hpr` | `matriz_rotacao_hpr` | Confirmar assinatura |
| `_rot_x`, `_rot_y`, `_rot_z` | `_rotacao_eixo_x`, `_rotacao_eixo_y`, `_rotacao_eixo_z` | Opcional, baixa prioridade |
| funções que devolvem flag | `classificar_*` | Prefixo da seção 2.2 |
| `_flag_<parte>` (ex.: `_flag_nova_parte`) | `classificar_<parte>` | Citada no guia de calibração |
| `montar_setas` | `montar_setas` | Mantido |
| `Seta` | `SetaVetor` | Evita confusão com outros usos de "seta" |
| `_rotulo` | `formatar_rotulo_seta` | Diz o que formata |
| `_POSES` | `POSES` | Passa a ser interface pública da ferramenta |
| `_INSTANTE_PADRAO` | `INSTANTE_PADRAO_S` | Unidade no nome |
| `CORES_VETOR` | `CORES_VETOR` | Mantido; chaves seguem os nomes novos |
| `rig_debug.py` | `rig_debug.py` (fachada) e `rig_mapa.py` (modelo), `rig_limiares.py` | Ver seção 13 |

### 12.6 Argumentos da linha de comando

| Antes | Depois | Observação |
| --- | --- | --- |
| `--parte hand` | `--parte mao` e alias `hand` | Aceita os dois idiomas durante a migração |
| `--parte head` | `--parte cabeca` e alias `head` |  |
| `--parte door` | `--parte porta` e alias `door` |  |
| `--parte feet` | `--parte pes` e alias `feet` |  |
| (novo) | `--parte braco`, `--parte tronco`, `--parte tentaculo`, `--parte junta` | Cobre o resto do corpo |
| (novo) | `--sequencia T0 T1 PASSO` | Gera relatório e eventos de um intervalo |
| (novo) | `--formato texto\|json` | Escolhe a saída do relatório |

## 13. Integração, testes e plano de migração

### 13.1 Módulos

O `AGENTS.md` exige que `model.py`, `rig.py`, `assets.py` e `config.py` não importem Panda3D, Qt ou Win32. Os módulos novos seguem a mesma regra, o que permite rodá-los em qualquer máquina, inclusive sem GPU.

| Módulo | Conteúdo | Importa Panda3D |
| --- | --- | --- |
| `rig_mapa.py` | Enums e dataclasses (seção 4) | Não |
| `rig_limiares.py` | `Limiares` e estado de validação (seção 10) | Não |
| `rig_medidas.py` | Funções `medir_*` e `resolver_*` (seções 5 a 9) | Não |
| `rig_classificadores.py` | Funções `classificar_*` | Não |
| `rig_descricao.py` | `descrever_*`, `ROTULOS`, JSON (seção 11) | Não |
| `rig_debug.py` | Fachada que mantém a API atual e delega aos módulos acima | Não |
| `tools/calibrar_vetores.py` | Render offscreen, setas e folha de contato | Sim |

A ferramenta de calibração é o único consumidor que desenha. Ela passa a chamar `analisar_rig` e desenhar o que o relatório descreve, em vez de recalcular as direções por conta própria.

### 13.2 Mudanças na calibração visual

**Novas setas e cores.** Os vetores novos entram em `CORES_VETOR`.

| Vetor | Cor | RGBA |
| --- | --- | --- |
| `eixo_polegar` | Magenta | (0,95; 0,30; 0,95; 1,0) |
| `eixo_punho` | Cinza claro | (0,75; 0,75; 0,75; 1,0) |
| `eixo_lateral` | Ciano | (0,25; 0,90; 0,95; 1,0) |
| `eixo_borda_livre` | Amarelo claro | (1,0; 0,95; 0,55; 1,0) |
| `normal_sola` | Verde escuro | (0,15; 0,65; 0,30; 1,0) |
| `eixo_frente_pe` | Laranja claro | (1,0; 0,75; 0,40; 1,0) |

**Novos elementos desenhados.**

- Arco de flexão em cada articulação, com o ângulo escrito ("cotovelo\_dir 78°").
- Faixa de cor no arco: verde dentro do limite, vermelha fora (`fora_do_limite`).
- Linha do centro de massa até a base de apoio, para as poses de dança.
- Rótulo com os números (alinhamento, inclinação, azimute) abaixo de cada seta.
- Gráfico de ângulo por tempo para `--sequencia`, usando só Pillow ou um desenho simples, sem depender de novas bibliotecas.

O modo atual (uma imagem por parte) continua o padrão. As novidades entram por argumento, para não mudar a saída de quem já usa.

### 13.3 Testes

O guia de calibração já lista testes em `tests/test_calibrar_vetores.py`. A nova camada precisa de uma suíte própria, que roda sem GPU.

| Grupo | O que valida | Exemplo |
| --- | --- | --- |
| Cobertura do modelo | Todo grupo do GLTF tem uma `Parte` | Falha se surgir `"left-arm"` sem entrada no enum |
| Medições analíticas | Funções contra casos de resposta conhecida | Dois vetores a 90 graus devolvem 90, a 180 devolvem 180 |
| Fronteiras | Valores exatamente no limiar | `15,0` graus cai em `ESTICADO`, `15,01` em `LEVE` |
| Invariantes de corpo rígido | Rotação preserva produtos escalares | `normal_palma` e `eixo_dedos` ficam perpendiculares em qualquer pose |
| Simetria no repouso | Pose neutra é espelhada | `simetria_bracos_norm` próxima de 1,0 no idle |
| Poses de referência | Flags esperadas por pose | `wave`: palma `PARA_CIMA`; `dance`: porta `ENTREABERTA` |
| Snapshot JSON | Relatório completo por pose, com tolerância | Floats com tolerância de 0,5 grau |
| Espelhamento | Poses espelhadas dão flags espelhadas | Aceno com a mão esquerda equivale ao da direita, com `PARA_DENTRO` e `PARA_FORA` trocados |
| Dinâmica | Sequência sintética com velocidade conhecida | Rotação de 90 graus/s devolve 90 graus/s |
| Primeiro frame | Sem memória, dinâmica é `None` | Nunca zero |
| Aliases | Flags antigas ainda resolvem | `"PALMA_PARA_CIMA"` vira `DirecaoPalma.PARA_CIMA` |

Os testes das poses de referência usam os resultados já registrados no guia de calibração (idle, dance e wave) como valores esperados iniciais. As demais poses (`stretch`, `peek`, `sleep`, `sneeze`) entram como snapshots depois de conferidas visualmente, e não antes.

### 13.4 Plano de migração

Cada fase deixa o projeto funcionando. Nenhuma exige trocar tudo de uma vez.

- [ ] **Fase 0, inventário.** Listar todos os nós do GLTF e completar o enum `Parte`, incluindo braço e antebraço esquerdos, pernas e dedos, se existirem.
- [ ] **Fase 1, fundação.** Criar `rig_mapa.py` e `rig_limiares.py`. Adicionar aliases das flags antigas. Nenhum comportamento muda.
- [ ] **Fase 2, partes.** Medir rotação, direção e posição de todas as partes. `EstadoParte` completo para cada `Parte`.
- [ ] **Fase 3, articulações.** Catálogo `ARTICULACOES`, medição de flexão, plano, torção e limites.
- [ ] **Fase 4, regiões.** Mãos, cabeça, porta, tronco, braços, pernas e pés, tentáculos, na ordem da seção 7.
- [ ] **Fase 5, relações.** Catálogo de relações, equilíbrio, silhueta e `Postura`.
- [ ] **Fase 6, dinâmica.** `MemoriaAnalise`, velocidades, fase, eventos e `analisar_sequencia`.
- [ ] **Fase 7, saídas.** Descrição em linguagem natural, JSON, formato de console e novos argumentos da CLI.
- [ ] **Fase 8, calibração visual.** Rodar as poses, mover cada `A_VALIDAR` para `CONFIRMADO` ou corrigir, congelar os snapshots.
- [ ] **Fase 9, limpeza.** Remover os aliases antigos depois de um ciclo sem uso, atualizar o `docs/` e o `AGENTS.md`.

### 13.5 Definição de pronto

O corpo conta como "todo mapeado" quando todos os itens abaixo são verdadeiros.

1. Todo grupo do GLTF tem uma `Parte` e um `EstadoParte` em todo frame.
2. Toda articulação do catálogo tem ângulo assinado, limites e estado.
3. Todo vetor de referência está `CONFIRMADO`, ou tem uma justificativa escrita para continuar `A_VALIDAR`.
4. Todo limiar tem nome, unidade, valor e estado de validação.
5. Toda flag de saída é um Enum, sem string solta.
6. As sete poses (idle, wave, stretch, peek, dance, sleep, sneeze) têm snapshot JSON versionado.
7. A suíte nova roda em máquina sem GPU, e a calibração visual roda em máquina com GPU.
8. O item 7.7 (elementos sem mapeamento) está vazio ou cada linha tem decisão escrita.

### 13.6 Riscos

| Risco | Efeito | Mitigação |
| --- | --- | --- |
| Esquerda e direita trocadas | Flags erradas em um lado só | Teste de espelhamento; definir lado como o do personagem (seção 2.4) |
| Ângulos em HPR com salto de 180 para -180 | Velocidade absurda por um frame | Calcular por rotação relativa (seção 9.3) |
| Escala do mascote de 0,5x a 2,5x | Limiares em unidades quebram | Distâncias em fração da altura (seção 10.1) |
| Análise rodando a 60 Hz no overlay | Custo no loop de render | Análise só em ferramentas e sob demanda; nunca no frame do overlay sem pedido explícito |
| Aliases esquecidos | Dois vocabulários convivendo | Fase 9 com data; teste que falha quando um alias é usado fora de `rig_debug.py` |
| Vetores deduzidos, não vistos | Flags erradas com aparência de certas | Estado `A_VALIDAR` aparece na saída e na descrição |

### 13.7 Perguntas em aberto

Pontos que dependem de informação que não está nos documentos que recebi.

| Pergunta | Por que importa |
| --- | --- |
| Quais são os nomes dos grupos do braço esquerdo e das pernas no GLTF? | Completa o enum `Parte` e o catálogo de articulações |
| O modelo tem dedos ou polegar como nós separados? | Define se `GestoMao.POLEGAR_CIMA` é medido ou derivado |
| Qual é o sentido natural de flexão de cada articulação? | Define o sinal de `angulo_flexao_graus` |
| Quais são os limites reais de cada articulação na animação atual? | Os limites propostos são de um mascote genérico |
| Os nomes de código devem ser todos em português? | Este documento assume que sim, seguindo `olhar`, `topo` e `dorso` |
| A jaqueta e o rosto precisam ser mapeados? | Entram ou saem do escopo (seção 7.7) |
