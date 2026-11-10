# Refatoração para a convenção Python

Registro da refatoração de `src/`, `tests/` e `tools/` para [CONVENCAO_PYTHON.md](CONVENCAO_PYTHON.md), feita na branch `frente3-animacao` sem mudança de comportamento.

## Baseline (HEAD 62aa821)

- `python -m pytest`: verde.
- `ruff check` com as regras novas: 520 achados (D 330, PLR0915 55, E702 39, PLR1702 27, C901 20, N 27, E701 8, I001 8, E402 1 fora de `janela.py`).
- `mypy src tools`: 14 erros em 5 arquivos (preexistentes, `physics`/`renderer`/`window`).
- `smoke_mouse`: já falhava em `WindowFromPoint` neste ambiente.

## Decisões

1. Renomeados módulos, testes e scripts de `tools/`. Identificadores em inglês só mudam onde o ruff `N` exige; o restante fica para um lote próprio, para não arriscar o "sem mudar comportamento".
2. Nome de teste em três partes vale para testes novos; os antigos mantêm o nome.
3. `tests/**` ignora `D102`, `D103` e `D107`: o nome do teste já descreve o cenário. A docstring de módulo continua obrigatória.
4. `max-nested-blocks = 3`, como diz a convenção (o padrão do ruff é 5). `PLR1702` só existe em preview, por isso `preview = true` com `explicit-preview-rules = true`.
5. `N802`/`N816` ficam no `ignore` global: nomes camelCase exigidos por Panda3D, Qt e Win32.
6. Encoding: UTF-8 sem BOM e LF no índice (`.editorconfig`). Os quatro arquivos do fio do fone que tinham BOM perderam o BOM.
7. Prova de "sem mudar comportamento": script de caracterização fora do repositório gravou em JSON as saídas das `pose_*`, do `AnimationController.update` (1500 quadros, todos os estados) e do `TentacleDirector.update` (900 quadros). O JSON foi comparado ao final de cada lote que toca esses módulos, com igualdade exata de float.
