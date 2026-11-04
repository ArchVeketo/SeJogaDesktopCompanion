# SeJogaDesktopCompanion

Mascote 3D interativo para o desktop Windows, renderizado com Panda3D e controlado por uma janela overlay.

## Estado do projeto

O overlay, carregamento do modelo, física básica, bandeja do sistema e build PyInstaller `onedir` foram implementados. O build foi aberto e verificado neste ambiente de desenvolvimento; ainda não foi validado em uma instalação limpa do Windows.

Consulte [Status atual e próximos passos](docs/STATUS_E_PROXIMOS_PASSOS.md) para o que está implementado, pendente e priorizado.

## Build no ambiente atual

No PowerShell, com as dependências Python e PyInstaller disponíveis nos caminhos esperados pelo script:

```powershell
.\build.ps1
```

O executável gerado fica em `dist\SeJogaCompanion\SeJogaCompanion.exe`.

> O script de build atual usa os caminhos de Python 3.14 deste ambiente de desenvolvimento. A portabilidade desse processo e a validação em uma máquina limpa ainda estão pendentes.

## Documentação

- [Status atual e próximos passos](docs/STATUS_E_PROXIMOS_PASSOS.md)
- [Arquitetura](docs/ARQUITETURA.md)
- [Guia de animações](docs/GUIA_ANIMACOES_COMPANION.md)
- [Referência de animações](docs/REFERENCIA_ANIMACOES.md)
- [Pesquisa técnica](docs/PESQUISA.md)
