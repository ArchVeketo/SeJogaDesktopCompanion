# SeJogaDesktopCompanion

Companion Windows em Python: Panda3D renderiza, PySide6 oferece bandeja/configurações e Pymunk simula o corpo no desktop.

## Referência e comandos

- Roadmap canônico: [docs/STATUS_E_PROXIMOS_PASSOS.md](docs/STATUS_E_PROXIMOS_PASSOS.md).
- Testes: `python -m pytest`.
- Janela real e perfil temporário: `python tools/smoke_mouse.py`; repetir com `--physics` ao alterar física, arraste ou coordenadas.
- Build: `.\build.ps1`; distribuir a pasta completa `dist/SeJogaCompanion`.
- Depois de alterar render/input/empacotamento, abrir o executável produzido e verificar logs e captura. Teste com entrada simulada no polling não prova que o mouse nativo funcionou.
- `SEJOGA_CONFIG_PATH` seleciona um perfil isolado para testes. Não sobrescrever configurações reais do usuário em testes automatizados.

## Limites entre módulos

- `modelo.py`, `esqueleto.py`, `recursos.py` e `configuracao.py` não importam Panda3D, Qt ou Win32.
- Renderer/overlay integram o rig e a física em `janela.py`; coordenadas físicas são absolutas no desktop, as do renderer são locais à janela.
- Preservar nomes/hierarquia dos grupos do GLTF. Animações procedurais usam rotações relativas ao rig.

## Armadilhas verificadas

- Pymunk 7 zera massa/momento ao trocar KINEMATIC por DYNAMIC: restaurá-los antes do próximo passo para evitar NaN.
- Não chamar `Body.sleep()` sem habilitar sleeping no espaço.
- O color key usa a cor depois do pós-processamento: neste ambiente `RGB(214, 0, 214)`. Recalibrar pelo framebuffer; magenta de clear color (`255, 0, 255`) não é equivalente.
- Fundo transparente no uso normal; rosa somente no diagnóstico. Color key já deixa áreas vazias atravessarem cliques. `WS_EX_TRANSPARENT` global também impede cliques no mascote.
- Contorno deve respeitar o alpha da textura, inclusive nas faces invisíveis do rosto e tentáculos, e acompanhar a pose.
- Panda aplica propriedades de janela assincronamente: validar posição e z-order após os primeiros frames. Usar as chamadas tipadas do pywin32 para HWND.
- HWND pode ser destruído antes do último passo de física: verificar validade e encerrar tarefas sem erro 1400.
- `build.ps1` filtra o PATH privado do Codex; não remover esse filtro. A ICU do Poppler é incompatível com os símbolos importados por QtCore.
- Não trocar PySide6/compilador aleatoriamente para corrigir uma DLL: identificar origem e símbolos da DLL no bundle.
- Erros de permissão do perfil não justificam pedir execução como administrador. A persistência usa temporário exclusivo e perfil alternativo persistente em caso de acesso negado.
- Eixo de membro se prova pela FK do grafo de cena (`nucleo/cinematica.py` == Panda, `tests/test_cinematica_oraculo.py`), não pela câmera frontal: ela não enxerga profundidade. `Rotation3` é LOCAL a cada nó; nunca copiar/perseguir o ângulo de uma junta em outra.
- Testes que importam Panda3D no processo do pytest precisam importar PySide6 antes, senão os testes de Qt da mesma sessão caem com access violation.

## Ferramentas do projeto

Skills em `.agents/skills`: release, animação Blockbench e diagnóstico Win32. Context7 serve para consultar APIs/documentação; verificar suporte à biblioteca e usar documentação oficial quando necessário. GitHub está disponível pelo plugin conectado. Não instalar MCPs adicionais de automação Windows sem necessidade concreta e avaliação da fonte.
