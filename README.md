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

## Mouse

- Passe o cursor sobre o personagem para ele olhar e entreabrir a porta.
- Clique esquerdo: reação rápida; clique direito: carinho; botão do meio: cutucada.
- Segure o esquerdo e mova pelo menos 6 pixels para arrastar. Ao soltar, a posição é salva. `Esc` interrompe o arraste na posição atual.
- Interagir acorda o personagem. As preferências permitem desligar reações e arraste separadamente, sem reiniciar.
- As áreas vazias deixam os cliques passar quando essa opção está ligada. Gestos iniciados em outro aplicativo não arrastam o mascote.

O arraste reposiciona o overlay, inclusive com a física desligada. Arremesso pelo desktop e colisões com bordas de janelas ainda precisam ser integrados ao movimento do overlay.

## Documentação

- [Status atual e próximos passos](docs/STATUS_E_PROXIMOS_PASSOS.md)
- [Arquitetura](docs/ARQUITETURA.md)
- [Guia de animações](docs/GUIA_ANIMACOES_COMPANION.md)
- [Referência de animações](docs/REFERENCIA_ANIMACOES.md)
- [Pesquisa técnica](docs/PESQUISA.md)
