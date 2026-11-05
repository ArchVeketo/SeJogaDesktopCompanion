# Calibração visual dos vetores de referência do rig

Guia versionado da ferramenta `tools/calibrar_vetores.py`. (Uma cópia de
trabalho também fica em `.agents/tasks/calibracao-vetores/COMO_LER.md`, que é
pasta ignorada pelo git — este é o documento canônico.)

## Para que serve

O módulo `src/sejoga/rig_debug.py` classifica flags em linguagem natural
("palma PARA_CIMA", "olhar FRENTE", "pé BAIXADO") girando **vetores de
referência** de repouso (dict `VETORES_REFERENCIA`). Vários desses vetores
foram deduzidos sem conferência visual e estão marcados com `# A VALIDAR`. Se um
vetor de partida estiver **invertido**, a flag sai errada — foi o que aconteceu
no aceno `wave`, que reportou `PALMA_PARA_CIMA`.

A ferramenta desenha cada vetor como uma **seta 3D** sobre o modelo, numa pose
escolhida, e salva **uma imagem por parte**. Em vez de raciocinar sobre álgebra,
você olha ~6 figuras e aponta quais setas estão erradas.

## Como gerar as imagens

Rode a partir da raiz do worktree (precisa de GPU para o render offscreen):

```powershell
# Ambiente (uma vez):
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[panda3d,windows,tray,music,music-analysis,dev]"

# Gerar todas as partes na pose de repouso:
python tools/calibrar_vetores.py

# Outras poses / partes:
python tools/calibrar_vetores.py --pose wave
python tools/calibrar_vetores.py --parte hand
python tools/calibrar_vetores.py --pose wave --parte hand
```

- `--pose`: `idle` (padrão), `wave`, `stretch`, `peek`, `dance`, `sleep`, `sneeze`.
- `--parte`: `hand`, `head`, `door`, `feet`, `all` (padrão).
- `--t`: instante em segundos (opcional; cada pose tem um padrão legível).

As imagens saem em `.agents/tasks/calibracao-vetores/imagens/`, uma por junta
(`hand.png`, `hand2.png`, `head.png`, `door.png`, `right-feet.png`,
`left-feet.png`), mais `_folha_contato.png` com todas lado a lado.

Se o Panda3D não conseguir renderizar offscreen na máquina atual (sem GPU, cai
para `p3tinydisplay`), a ferramenta reporta isso e sai sem inventar imagens —
rode o mesmo comando numa máquina com GPU.

## Como ler cada seta

Cada seta sai da junta e aponta na direção que o `rig_debug` usa para decidir a
flag. O rótulo no canto superior esquerdo diz **nome do vetor → FLAG produzida**
e a cor do texto é a cor da seta. Cores por tipo:

| Cor      | Vetor                                   |
|----------|-----------------------------------------|
| vermelho | `normal_palma` (mão), `olhar` (cabeça), `normal` (porta) |
| azul     | `dorso` (mão), `topo` (cabeça)          |
| verde    | `direcao_dedos` (mão)                   |
| amarelo  | `eixo_giro` (porta)                     |
| laranja  | `eixo_longo` (pés)                      |

Para **cada** seta, faça UMA pergunta:

> **Essa seta aponta para onde eu espero?**

Exemplos concretos:

- **`normal_palma`** (vermelha, mão): a seta deve sair da **palma** (lado de
  dentro da mão). Se ela estiver saindo das **costas** da mão, o vetor está
  invertido.
- **`dorso`** (azul, mão): deve sair das **costas** da mão — oposto à palma.
- **`direcao_dedos`** (verde, mão): deve apontar para a **ponta dos dedos**.
- **`olhar`** (vermelha, cabeça): deve sair do **rosto** para onde o Mário olha.
- **`topo`** (azul, cabeça): deve apontar para a **coroa** da cabeça.
- **`normal`** (vermelha, porta): deve apontar para **fora** da portinha, no
  sentido em que ela abre.
- **`eixo_longo`** (laranja, pé): deve correr ao longo do **comprimento** do pé
  (da perna para a ponta).

Confira também se a **FLAG** do rótulo bate com o que a seta mostra. No aceno
`wave`, por exemplo, confirme se `normal_palma_direita -> PALMA_PARA_CIMA` tem a
seta vermelha realmente saindo da palma virada para cima — ou se a palma está
virada para o rosto/para fora e a flag mentiu.

## O que fazer ao achar uma seta errada

Anote, por parte, **qual seta** está invertida/errada e **para onde ela deveria
apontar**. Numa tarefa seguinte, o agente ajusta o vetor correspondente em
`VETORES_REFERENCIA` (em `src/sejoga/rig_debug.py`) — tipicamente invertendo o
sinal (ex.: `(0, -1, 0)` → `(0, 1, 0)`) — e remove o comentário `# A VALIDAR`.
Depois roda a ferramenta de novo para confirmar que a seta passou a apontar
certo e que as flags do `rig_debug` ficaram coerentes.

> A ferramenta **não** edita `rig_debug.py`: ela só LÊ `VETORES_REFERENCIA` e
> renderiza. A correção dos vetores é um passo manual/futuro, feito com o
> diagnóstico destas figuras em mãos.
