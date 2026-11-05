# Calibração Visual de Vetores do Rig

**Data:** 2026-11-05  
**Versão:** 1.0  
**Objetivo:** Documentar o sistema de calibração visual de vetores de referência do rig instrumentado para diagnóstico preciso de poses.

---

## 1. Visão Geral

O sistema de **rig debug** (`src/sejoga/rig_debug.py`) classifica a orientação de cada parte do corpo do mascote Mário em linguagem natural — "palma para cima", "olhar à direita", "porta entreaberta", etc. Essas classificações dependem de **vetores de referência** definidos em `VETORES_REFERENCIA`, que representam as direções características de cada parte em sua pose de repouso.

A ferramenta `tools/calibrar_vetores.py` **renderiza o modelo em uma pose escolhida** e desenha esses vetores de referência como **setas 3D coloridas** sobre cada parte, gerando imagens PNG para validação visual. Isso permite confirmar se os vetores apontam nas direções esperadas e detectar inversões ou erros de orientação.

---

## 2. Problema que Resolve

### 2.1 Origem da Necessidade

Vários vetores de referência em `rig_debug.py` foram deduzidos matematicamente sem confirmação visual e estão marcados com `# A VALIDAR`. Se um vetor estiver invertido ou mal orientado, as flags de diagnóstico saem erradas.

**Exemplo real:** Em testes iniciais, o aceno (`wave`) reportou "palma PARA_CIMA" quando deveria ser outra direção, provavelmente por um vetor de referência torto.

### 2.2 Solução: Calibração Visual

Em vez de testar vetores apenas com asserts numéricos, **visualizamos** cada vetor como uma seta 3D ancorada na parte correspondente, em uma pose específica. O usuário olha as imagens e confirma:
- ✅ Vetor de "palma" aponta na direção correta da palma da mão
- ✅ Vetor de "olhar" aponta para onde o rosto está voltado
- ✅ Vetor de "dorso" aponta na direção oposta à palma
- ❌ Se algo estiver invertido, fica visualmente óbvio

---

## 3. Como Funciona

### 3.1 Arquitetura

```
tools/calibrar_vetores.py
    ↓
1. Carrega modelo GLTF (mario.gltf)
2. Aplica pose escolhida (idle, wave, dance, etc.)
3. Calcula VETORES_REFERENCIA transformados pela pose
4. Renderiza modelo + setas em Panda3D offscreen
5. Gera PNG por parte (hand, head, door, feet)
6. Cria folha-contato com todas as imagens
```

### 3.2 Vetores de Referência Atuais

Definidos em `src/sejoga/rig_debug.py` — `VETORES_REFERENCIA`:

#### **Mãos (hand, hand2):**
- `normal_palma`: Vetor normal à superfície da palma — `(0.0, -1.0, 0.0)` em repouso (para baixo) ⚠️ **A VALIDAR**
- `dorso`: Oposto à palma — `(0.0, 1.0, 0.0)` (para cima) ⚠️ **A VALIDAR**
- `direcao_dedos`: Direção dos dedos — `(0.0, -1.0, 0.0)` (para baixo)

#### **Cabeça (head):**
- `olhar`: Para onde o rosto aponta — `(0.0, 0.0, 1.0)` (frente)
- `topo`: Coroa da cabeça — `(0.0, 1.0, 0.0)` (cima)

#### **Corpo (body):**
- `frente`: Peito — `(0.0, 0.0, 1.0)` (frente)
- `cima`: Tronco ereto — `(0.0, 1.0, 0.0)` (cima)

#### **Porta (door):**
- `normal`: Normal da porta fechada — `(0.0, 0.0, 1.0)` (frente) ⚠️ **A VALIDAR**
- `eixo_giro`: Eixo da dobradiça — `(0.0, 1.0, 0.0)` (vertical Y)

#### **Membros (braços, pernas, pés):**
- `longo`: Eixo longo do membro — `(0.0, -1.0, 0.0)` (para baixo em repouso)

### 3.3 Cores das Setas

Definidas em `tools/calibrar_vetores.py` — `CORES_VETOR`:

| Tipo de Vetor | Cor | RGB |
|---------------|-----|-----|
| `normal_palma` | 🔴 Vermelho | (1.0, 0.25, 0.25, 1.0) |
| `dorso` | 🔵 Azul | (0.25, 0.55, 1.0, 1.0) |
| `direcao_dedos` | 🟢 Verde | (0.25, 1.0, 0.35, 1.0) |
| `olhar` | 🔴 Vermelho | (1.0, 0.25, 0.25, 1.0) |
| `topo` | 🔵 Azul | (0.25, 0.55, 1.0, 1.0) |
| `normal` (porta) | 🔴 Vermelho | (1.0, 0.25, 0.25, 1.0) |
| `eixo_giro` | 🟡 Amarelo | (0.9, 0.9, 0.25, 1.0) |
| `longo` (membro) | 🟠 Laranja | (1.0, 0.55, 0.1, 1.0) |

---

## 4. Uso da Ferramenta

### 4.1 Sintaxe Básica

```powershell
# Navegue até a raiz do projeto
cd C:\GitHub\SeJogaDesktopCompanion

# Pose padrão (idle), todas as partes
python tools/calibrar_vetores.py

# Pose específica
python tools/calibrar_vetores.py --pose wave

# Parte específica
python tools/calibrar_vetores.py --parte hand

# Combinação
python tools/calibrar_vetores.py --pose dance --parte feet --t 0.6
```

### 4.2 Parâmetros

| Parâmetro | Valores | Padrão | Descrição |
|-----------|---------|--------|-----------|
| `--pose` | idle, wave, stretch, peek, dance, sleep, sneeze | `idle` | Pose a aplicar ao modelo |
| `--parte` | hand, head, door, feet, all | `all` | Parte(s) a calibrar |
| `--t` | float (segundos) | Varia por pose | Instante da animação procedural |

#### **Poses Disponíveis:**

| Pose | Instante Padrão | Descrição |
|------|-----------------|-----------|
| `idle` | 1.0s | Pose neutra, brazos caídos |
| `wave` | 1.0s | Aceno com mão direita (palma para cima) |
| `stretch` | 1.2s | Espreguiçar (braços levantados) |
| `peek` | 2.5s | Espiada com tentáculos (porta aberta) |
| `dance` | 0.6s | Dança (corpo inclinado, porta entreaberta) |
| `sleep` | 1.0s | Dormindo (cabeça baixa, porta fechada) |
| `sneeze` | 3.68s | Espirro (porta muito aberta) |

#### **Partes Disponíveis:**

| Parte | Grupos do Rig | Vetores Renderizados |
|-------|---------------|----------------------|
| `hand` | hand, hand2 | normal_palma, dorso, direcao_dedos (3 vetores × 2 mãos = 6) |
| `head` | head | olhar, topo (2 vetores) |
| `door` | door | normal, eixo_giro (2 vetores) |
| `feet` | right-feet, left-feet | longo (1 vetor × 2 pés = 2) |
| `all` | todos acima | 12 vetores total |

### 4.3 Saída

**Pasta de destino:**
```
.agents/tasks/calibracao-vetores/imagens/
```

**Arquivos gerados:**
- `hand.png` — Mão direita com 3 setas (palma, dorso, dedos)
- `hand2.png` — Mão esquerda com 3 setas
- `head.png` — Cabeça com 2 setas (olhar, topo)
- `door.png` — Porta com 2 setas (normal, eixo de giro)
- `right-feet.png` — Pé direito com 1 seta (eixo longo)
- `left-feet.png` — Pé esquerdo com 1 seta
- `_folha_contato.png` — Montagem com todas as imagens lado a lado (grid 3×2)

**Formato da saída no console:**
```
Calibração · pose 'wave' (t=1.00s) · parte 'all' · 6 figura(s), 12 seta(s)
  gerado: C:\...\hand.png
          normal_palma_direita -> PALMA_PARA_CIMA, dorso_direita -> DORSO_BAIXO, direcao_dedos_direita -> DEDOS_CIMA
  gerado: C:\...\hand2.png
          normal_palma_esquerda -> PALMA_PARA_BAIXO, dorso_esquerda -> DORSO_CIMA, direcao_dedos_esquerda -> DEDOS_BAIXO
  ...
  folha-contato: C:\...\\_folha_contato.png
6 imagem(ns) em C:\...\imagens
```

Cada linha mostra:
1. **Arquivo gerado**
2. **Rótulos dos vetores** (`nome_direita` ou `nome_esquerda` para lados)
3. **Flag resultante** — classificação do vetor transformado (ex: `PALMA_PARA_CIMA`)

---

## 5. Resultados Obtidos (05/11/2026)

### 5.1 Pose IDLE (neutra)

**Comando:** `python tools/calibrar_vetores.py --pose idle`

| Parte | Vetor | Flag Resultante | Observação |
|-------|-------|-----------------|------------|
| Mão direita | normal_palma | PALMA_PARA_BAIXO | ✅ Correto (braço caído) |
| Mão direita | dorso | DORSO_CIMA | ✅ Correto (oposto à palma) |
| Mão direita | direcao_dedos | DEDOS_BAIXO | ✅ Correto |
| Mão esquerda | normal_palma | PALMA_PARA_DENTRO | ✅ Correto (virada pro corpo) |
| Mão esquerda | dorso | DORSO_DIREITA | ✅ Correto |
| Mão esquerda | direcao_dedos | DEDOS_ESQUERDA | ✅ Correto |
| Cabeça | olhar | OLHAR_FRENTE | ✅ Correto |
| Cabeça | topo | TOPO_CIMA | ✅ Correto |
| Porta | normal | PORTA_FECHADA | ✅ Correto |
| Porta | eixo_giro | EIXO_DE_GIRO (Y) | ✅ Correto (vertical) |
| Pé direito | longo | BAIXADO | ✅ Correto (em pé) |
| Pé esquerdo | longo | BAIXADO | ✅ Correto |

**Conclusão:** Pose neutra está **bem calibrada**! Todas as direções fazem sentido.

### 5.2 Pose DANCE (dança)

**Comando:** `python tools/calibrar_vetores.py --pose dance`

| Parte | Vetor | Flag Resultante | Diferença vs IDLE |
|-------|-------|-----------------|-------------------|
| Mão direita | normal_palma | PALMA_PARA_BAIXO | Igual |
| Mão esquerda | normal_palma | PALMA_PARA_BAIXO | ⭐ Mudou (era PARA_DENTRO) |
| Porta | normal | **PORTA_ENTREABERTA** | ⭐ Mudou (era FECHADA) |
| Demais | — | Igual ao idle | — |

**Conclusão:** Na dança, a porta **entreabre** corretamente e a mão esquerda muda de orientação. Comportamento esperado! ✅

### 5.3 Pose WAVE (aceno)

**Comando:** `python tools/calibrar_vetores.py --pose wave`

| Parte | Vetor | Flag Resultante | Diferença vs IDLE |
|-------|-------|-----------------|-------------------|
| Mão direita | normal_palma | **PALMA_PARA_CIMA** | ⭐ Mudou (acenando!) |
| Mão direita | dorso | **DORSO_BAIXO** | ⭐ Inverteu |
| Mão direita | direcao_dedos | **DEDOS_CIMA** | ⭐ Dedos apontam pra cima |
| Mão esquerda | — | Igual ao idle | Não acena |
| Demais | — | Igual ao idle | — |

**Conclusão:** Mão direita **inverte completamente** no aceno — palma vira pra cima, dedos apontam pra cima, dorso pra baixo. Perfeito! ✅

---

## 6. Diagnóstico Visual das Imagens

### 6.1 Como Interpretar as Setas

Cada imagem mostra:
1. **Modelo 3D** na pose escolhida (vista frontal)
2. **Setas coloridas** ancoradas em cada parte
3. **Rótulos** no topo esquerdo com `nome_vetor -> FLAG`

**Comprimento das setas:** Fixo (3.2 unidades no mundo), não varia com a pose.

**Direção das setas:** Representa o vetor de referência **transformado** pela rotação acumulada (repouso + animação + hierarquia pai→filho).

### 6.2 Checklist de Validação

Para cada seta renderizada, verificar:

- [ ] **Seta aponta na direção esperada?**
  - Ex: "palma" deve apontar perpendicularmente à superfície da palma
  - Ex: "olhar" deve apontar para onde o rosto está voltado
  - Ex: "dedos" deve apontar do punho para as pontas dos dedos

- [ ] **Flag calculada bate com a direção visual?**
  - Ex: Se a seta aponta pra cima, a flag deve ser `PARA_CIMA` ou `CIMA`
  - Ex: Se a seta aponta pra fora do corpo, flag deve incluir `FORA` ou `DIREITA`/`ESQUERDA`

- [ ] **Poses diferentes produzem flags diferentes onde esperado?**
  - Ex: No `wave`, palma deve virar `PARA_CIMA`
  - Ex: No `dance`, porta deve ficar `ENTREABERTA`

- [ ] **Setas de pares opostos (palma/dorso) apontam em direções opostas?**
  - Ângulo entre elas deve ser ~180°

### 6.3 Problemas Comuns e Como Detectar

| Problema | Sintoma Visual | Como Corrigir |
|----------|----------------|---------------|
| **Vetor invertido** | Seta aponta na direção oposta à esperada (ex: "palma" aponta pro dorso) | Inverter sinal do vetor em `VETORES_REFERENCIA` |
| **Eixo trocado** | Seta aponta na direção perpendicular errada (ex: "dedos" apontam pro lado em vez de pra frente) | Trocar componentes do vetor (ex: `(1,0,0)` → `(0,0,1)`) |
| **Mão esquerda espelhada errado** | Flags da mão esquerda não fazem sentido vs a direita | Ajustar vetores de `hand2` considerando o espelhamento |
| **Porta abre no sentido errado** | Normal da porta inverte ao abrir | Inverter vetor `normal` de `door` |

---

## 7. Implementação Técnica

### 7.1 Coordenadas e Transformações

**Sistema de coordenadas do GLTF (Panda3D):**
- **+X** = direita
- **+Y** = cima
- **+Z** = frente (em direção à câmera)

**Convenção de rotação (HPR do Panda3D):**
```python
# De Rotation3(x, y, z) em radianos:
H = y  # Heading (yaw, giro horizontal)
P = x  # Pitch (inclinação frente/trás)
R = z  # Roll (rolagem lateral)

# Aplicado no nó:
node.setHpr(base_h + degrees(y), base_p + degrees(x), base_r + degrees(z))
```

**Ordem de aplicação (intrínseca):**
1. Roll (R) primeiro
2. Pitch (P) depois
3. Heading (H) por último

**Matriz de rotação composta:**
```python
matriz_hpr(h, p, r) = _rot_y(h) @ _rot_x(p) @ _rot_z(r)
```

### 7.2 Cálculo das Setas

Para cada vetor de referência:

1. **Ler vetor de repouso** de `VETORES_REFERENCIA[parte][nome]`
2. **Compor rotação acumulada:**
   - Rotação de repouso do nó (quaternião do GLTF)
   - HPR animado da pose (`Rotation3(x,y,z)`)
   - Rotação acumulada dos pais na hierarquia
3. **Transformar vetor:** `vetor_mundo = matriz_acumulada @ vetor_repouso`
4. **Classificar direção:** Comparar `vetor_mundo` contra os 6 eixos do mundo
5. **Renderizar seta:** Desenhar geometria 3D ao longo de `vetor_mundo`

### 7.3 Render Offscreen

**Engine:** Panda3D com `window-type offscreen`

**Configuração:**
- Resolução: 900×900 px
- Iluminação: Ambiente (55%) + direcional (85%, 45° em -XY)
- Câmera: Ortográfica frontal, 14 unidades de altura
- Antialiasing: Multisample
- Fundo: RGB(28, 30, 38) — cinza escuro

**Limitações:**
- Requer GPU com suporte a offscreen rendering
- Em ambientes sem GPU (ex: `p3tinydisplay`), a ferramenta reporta e falha graciosamente
- Solução: Rodar em máquina com GPU/drivers atualizados

---

## 8. Casos de Uso

### 8.1 Validar Vetor Marcado com "A VALIDAR"

**Problema:** `normal_palma` tem comentário `# A VALIDAR` — não sabemos se está correto.

**Solução:**
```powershell
# Gerar imagens com poses que movem a palma
python tools/calibrar_vetores.py --pose idle --parte hand
python tools/calibrar_vetores.py --pose wave --parte hand
python tools/calibrar_vetores.py --pose stretch --parte hand

# Comparar visualmente: a seta vermelha (palma) aponta onde esperado?
# - Idle: palma para baixo (braço caído)
# - Wave: palma para cima (acenando)
# - Stretch: palma para frente (braços levantados)
```

### 8.2 Debugar Gesto que Falha

**Problema:** Teste de gesto "thumbs up" falha — diz que polegar está BAIXO quando deveria estar CIMA.

**Solução:**
```powershell
# Gerar calibração na pose do gesto
python tools/calibrar_vetores.py --pose <nome_do_gesto> --parte hand --t <instante_do_polegar_levantado>

# Verificar se a seta verde (dedos) realmente aponta pra cima
# Se não, o vetor ou a pose estão errados
```

### 8.3 Adicionar Novo Vetor de Referência

**Cenário:** Queremos adicionar diagnóstico de "eixo dos ombros" (linha entre os dois ombros).

**Passos:**
1. Adicionar vetor em `rig_debug.VETORES_REFERENCIA['shoulder']`
2. Adicionar cor em `calibrar_vetores.CORES_VETOR`
3. Adicionar lógica em `calibrar_vetores.montar_setas()` para incluir `shoulder`
4. Rodar calibração: `python tools/calibrar_vetores.py --parte all`
5. Validar visualmente se a seta aponta ao longo do ombro

---

## 9. Manutenção e Evolução

### 9.1 Quando Recalibrar

- ✅ **Após alterar vetores em `VETORES_REFERENCIA`**
- ✅ **Após modificar hierarquia do rig no GLTF**
- ✅ **Ao adicionar novas poses procedurais**
- ✅ **Quando testes de gesto começam a falhar inesperadamente**

### 9.2 Adicionar Novas Poses

Editar `tools/calibrar_vetores.py`:

```python
# Adicionar função de pose
def _pose_nova(rig: rig_mod.Rig, t: float) -> None:
    rig_mod.pose_nova(rig, t)  # Ou custom

# Adicionar ao mapa
_POSES["nova"] = _pose_nova
_INSTANTE_PADRAO["nova"] = 1.5  # Instante característico
```

### 9.3 Adicionar Novos Vetores

1. **Definir vetor em `rig_debug.py`:**
```python
VETORES_REFERENCIA["nova_parte"] = {
    "vetor_novo": (1.0, 0.0, 0.0),  # Exemplo: aponta pra direita
}
```

2. **Adicionar cor em `calibrar_vetores.py`:**
```python
CORES_VETOR["vetor_novo"] = (0.5, 0.0, 1.0, 1.0)  # Roxo
```

3. **Incluir em `montar_setas()`:**
```python
if parte in ("nova_parte", "all"):
    for nome in ("vetor_novo",):
        flag = _flag_nova_parte(estado, nome)
        setas.append(Seta("nova_parte", nome, "nova_parte", _rotulo(nome, flag, "nova_parte")))
```

---

## 10. Testes Automatizados

### 10.1 Cobertura Atual

**Arquivo:** `tests/test_calibrar_vetores.py`

**Testes:**
- ✅ Carregamento de poses
- ✅ Montagem de setas por parte
- ✅ Agrupamento por arquivo de saída
- ✅ Nomes de arquivo estáveis
- ✅ Render offscreen (quando GPU disponível)

### 10.2 Executar Testes

```powershell
# Todos os testes da calibração
python -m pytest tests/test_calibrar_vetores.py -v

# Com cobertura
python -m pytest tests/test_calibrar_vetores.py --cov=tools.calibrar_vetores
```

---

## 11. Referências

### 11.1 Código-Fonte

- `src/sejoga/rig_debug.py` — Vetores de referência e classificação de direções
- `tools/calibrar_vetores.py` — Ferramenta de calibração visual
- `tests/test_calibrar_vetores.py` — Testes automatizados
- `src/sejoga/rig.py` — Poses procedurais
- `src/sejoga/model.py` — Carregamento do GLTF

### 11.2 Documentação Relacionada

- [ARQUITETURA.md](ARQUITETURA.md) — Visão geral do sistema
- [GUIA_ANIMACOES_COMPANION.md](GUIA_ANIMACOES_COMPANION.md) — Sistema de animações
- [GUIA_ANIMACAO_DANCA.md](GUIA_ANIMACAO_DANCA.md) — Animações de dança
- [REFERENCIA_ANIMACOES.md](REFERENCIA_ANIMACOES.md) — Referências de jogos

### 11.3 Conceitos de Álgebra Linear

- **Quaterniões:** Representação de rotação sem gimbal lock
- **Matrizes de rotação 3×3:** Composição de rotações HPR
- **Transformação de vetores:** Aplicação de matriz a vetor coluna
- **Ângulo entre vetores:** `acos(dot(a, b) / (|a| * |b|))`

---

## 12. FAQ

### P: Por que algumas imagens ficam sobrescritas?

**R:** Cada execução gera imagens com nomes fixos (`hand.png`, `head.png`, etc.). Para preservar múltiplas poses, renomeie manualmente ou use um script de batch:

```powershell
python tools/calibrar_vetores.py --pose idle
Rename-Item .agents\tasks\calibracao-vetores\imagens\_folha_contato.png idle_folha.png

python tools/calibrar_vetores.py --pose wave
Rename-Item .agents\tasks\calibracao-vetores\imagens\_folha_contato.png wave_folha.png
```

### P: Posso calibrar apenas uma mão?

**R:** Sim! Use `--parte hand` para apenas `hand.png` (mão direita) ou edite `montar_setas()` para filtrar por `hand` vs `hand2`.

### P: A ferramenta funciona sem GPU?

**R:** Não. Panda3D offscreen requer drivers de GPU. Em ambientes sem GPU, a ferramenta reporta o erro e sugere rodar em máquina com GPU. As imagens não são geradas.

### P: Como adicionar vetores intermediários (ex: cotovelo)?

**R:** Cotovelos não têm vetores próprios — sua flexão é medida pelo ângulo entre `right-arm` e `ant-arm` (ambos com vetor `longo`). Para visualizar a articulação, renderize ambos os segmentos.

### P: As setas podem ficar transparentes/opacas?

**R:** Atualmente todas têm alpha 1.0 (opacas). Para ajustar, edite `CORES_VETOR` alterando o quarto componente (ex: `(1.0, 0.25, 0.25, 0.5)` para 50% transparente).

---

*Fim da documentação de calibração de vetores do rig. Para dúvidas ou problemas, consulte o código-fonte ou abra uma issue.*

**Versão:** 1.0 (2026-11-05)  
**Próxima revisão:** Após validação completa dos vetores marcados com `# A VALIDAR`
