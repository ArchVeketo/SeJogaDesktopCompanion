# Convenção de código Python do SeJogaDesktopCompanion

Padrão de código e de nomes de arquivo deste projeto. É a fonte de verdade; a steering `sejoga-python-convencao.md` é só um resumo para o agente. Baseada na convenção Python do time Conversor Pack, adaptada ao que existe aqui.

Vale para todo arquivo `.py` em `src/sejoga/`, `tests/` e `tools/`. Código novo já nasce conforme. Código antigo é ajustado na refatoração; enquanto um trecho não puder ser ajustado, marcar com `# TODO convenção: <motivo>`.

## Idioma

- Identificadores, docstrings, comentários, mensagens de log e textos da interface em português.
- Inglês só para termo técnico consagrado. Lista aceita neste projeto: `buffer`, `frame`, `hook`, `log`, `offset`, `overlay`, `preview`, `schema`, `shader`, `smoke`, `timeout`, `tray`, `widget`. Outro termo em inglês precisa de motivo no code review.
- Nomes exigidos por bibliotecas ficam como a biblioteca exige: métodos sobrescritos do Qt (`paintEvent`, `closeEvent`), APIs do Panda3D (`setHpr`, `getTightBounds`), do Pymunk e do pywin32.
- Nomes de nós e grupos do GLTF (`right-arm`, `fingers`, `porta`, ...) não mudam. Eles vêm do asset e o AGENTS.md proíbe renomear.

## Nomes de arquivo e pasta

- Pastas e módulos em `snake_case`, em português, com substantivo que diz o que o módulo contém: `cinematica.py`, `colisao_bracos.py`, `coreografia_porta.py`.
- Módulo de constantes calibráveis termina em `_tuning.py` (`braco_tuning.py`, `chroma_tuning.py`). Módulo de constantes fixas, que não se calibram, termina em `_const.py` (`janela_const.py`).
- Módulos ficam com nome em português. Os antigos em inglês (`window.py`, `renderer.py`, `body_motion.py`, `tentacle_system.py` e outros) foram renomeados; o mapa antigo → novo está em [REFATORACAO_CONVENCAO.md](REFATORACAO_CONVENCAO.md). Exceções: `__init__.py`, `__main__.py`, `conftest.py`.
- Scripts em `tools/` começam com verbo e dizem a ação: `calibrar_interativo.py`, `capturar_porta_tentaculos.py`. Os de verificação podem começar com `smoke_`.
- Testes: um arquivo `tests/test_<modulo>.py` por módulo testado.

## Caixa e forma dos nomes

- Classes `PascalCase`. Funções, métodos, variáveis e parâmetros `snake_case`. Constantes `UPPER_CASE`.
- Siglas em maiúsculo dentro do nome: `calcular_IK`, `aplicar_FK`, `limite_FPS`, `cor_RGB`, `HPR_repouso`, `handle_HWND`. Siglas técnicas comuns aqui: `IK`, `FK`, `HPR`, `FPS`, `UV`, `RGB`, `GLTF`, `HWND`, `MSAA`, `BPM`.
- Sem prefixos herdados do Delphi (`F`, `L`, `p`, `T`, `I`).
- Função e método começam com verbo: `aplicar_pose`, `carregar_modelo`, `medir_penetracao`.
- Booleanos começam com pergunta: `esta_pendurado`, `tem_contorno`, `eh_agitado`, `possui_caixa_som`.
- Atributo privado com um `_` na frente.

## Tipos

- Type hints obrigatórios em todo parâmetro e retorno: `def somar(a: int, b: int) -> int`. Sem retorno, `-> None`.
- Nulo explícito com `X | None`.
- Uma atribuição por linha.
- Tipos do Panda3D (`NodePath`, `Vec3`) só aparecem nos pacotes com engine. Pacotes puros usam tipos próprios ou tuplas.

## Imports

- No topo do arquivo, em três grupos PEP 8 separados por linha em branco: biblioteca padrão, terceiros, módulos do projeto. Ordem alfabética dentro do grupo (o ruff `I` faz isso).
- Nunca import no fim do arquivo nem dentro de função.
- Única exceção permitida: `src/sejoga/render/janela.py`, porque o Qt precisa carregar antes do Panda3D (DLLs MSVC conflitantes) e os `loadPrcFileData()` precisam rodar antes de importar o Panda3D. A exceção fica registrada no `pyproject.toml` (`E402`) com o comentário do motivo. Script de `tools/` que precise ajustar o `sys.path` antes do import também pode ter a exceção, com o motivo.

## Camadas

Regra do AGENTS.md, que aqui substitui a regra de camadas dos coletores:

- Pacotes puros, sem Panda3D, Qt nem Win32: `nucleo/`, `rig_mapa/`, `animacao/`, `configuracao.py`, `modelo.py`, `esqueleto.py`, `recursos.py`.
- Pacotes com engine: `render/`, `desktop/`, `musica/`, `distribuicao/`, `tentaculos/` e `tools/`.
- A dependência vai sempre do lado com engine para o lado puro, nunca o contrário.
- Entre os puros, `nucleo/` é a base: `animacao/` e `rig_mapa/` podem importar de `nucleo/`, e `nucleo/` não importa de `animacao/` nem de `rig_mapa/`. Constantes que o `nucleo/` precisa ficam no `nucleo/`.
- Um teste AST em `tests/` garante que os pacotes puros não importam engine.

## Números

- Nenhum literal numérico de domínio solto na lógica. Ângulos, ganhos, tempos, raios e cores vão para constantes nomeadas no `_tuning.py` ou `_const.py` do pacote, com um comentário que explica o porquê do valor. Fazem exceção `0`, `1`, `-1`, `2` em aritmética óbvia e índices.
- Valor que o usuário calibra na GPU fica em `_tuning.py`. O comentário diz o efeito de subir e de descer o valor.

## Tamanho e fluxo

- Funções curtas: no máximo 27 comandos (`PLR0915`, `max-statements = 27`), complexidade até 10 (`C901`), aninhamento até 3 níveis (`PLR1702`).
- Guard clauses: retornar ou levantar exceção cedo, em vez de aninhar `if`.
- Um comando por linha. O estilo denso de vários comandos na mesma linha (`E701`/`E702`), antes liberado em `musica/` e no antigo `lower_body.py`, foi removido na refatoração.

## Docstrings e comentários

- Docstring obrigatória em módulo, classe pública e função pública, no estilo PEP 257: aspas triplas duplas, resumo no imperativo terminando em ponto.
- Seções `Args:`, `Returns:` e `Raises:` só quando acrescentam informação.
- Comentário explica o porquê, nunca o que o código já mostra.
- Atalho com limite conhecido: `# shortcut: <limite>, <quando melhorar>`.

## Formatação e ferramentas

- 4 espaços, linha de 88 caracteres, aspas duplas.
- O ruff é o único linter e formatador: `ruff format` e `ruff check src tests tools`. A configuração fica no `pyproject.toml`.
- Regras do ruff: `E`, `F`, `W`, `I`, `UP`, `B`, `SIM`, `RUF`, `N`, `D` (convention `pep257`), `C901`, `PLR0915`, `PLR1702` (esta é regra preview do ruff). `N802` e `N816` desligados por causa das siglas em maiúsculo.
- `mypy` em `src` e `tools`.

## Testes

- Arquivos `tests/test_<modulo>.py`.
- Nome da função de teste em três partes, unidade + cenário + resultado esperado: `test_colisao_bracos_braco_dentro_do_tronco_empurra_para_fora`.
- Os testes não substituem a validação visual. Teste verde mostra que a lógica não mudou, e não que o mascote aparece certo. A validação visual é feita na GPU, pelo checklist em `docs/`.

## Arquivos

- Encoding UTF-8 sem BOM, fim de linha LF.
