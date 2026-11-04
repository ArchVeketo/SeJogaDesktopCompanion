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
- O fundo é transparente e deixa os cliques passar automaticamente. O rosa aparece quando o diagnóstico está ligado. Gestos iniciados em outro aplicativo não arrastam o mascote.
- O contorno acompanha as partes animadas do personagem. Em **Configurações**, escolha a cor, ajuste a espessura de 0,5 a 8 px ou desligue o contorno. As mudanças são aplicadas ao salvar.
- O olhar reage também numa área ao redor do personagem, acompanhando o cursor para os lados, para cima e para baixo.
- O menu da bandeja oferece **Acenar**, **Alongar** e **Mostrar tentáculos**. Os tentáculos aparecem com a abertura da porta, recolhem gradualmente antes de ela fechar e às vezes soltam uma gota de gosma rosa.
- Os tentáculos saem de dentro da abertura e flexionam em 3D. A porta tem mola e contato com o volume ocupado por eles: cede à passagem e volta a fechar quando há espaço.

## Barra de tarefas e saída

O aplicativo tem ícone próprio no executável, na janela e na bandeja, derivado da arte oficial SeJoga. A janela também aparece na barra de tarefas do Windows.

**Fechar janela** pela barra de tarefas ou **Encerrar Mário** pela bandeja inicia a saída: Mário fica branco, gira e voa para fora da tela; o processo encerra em seguida. `Shift` + clique direito no botão da barra abre o menu do sistema com **Encerrar Mário**, **Configurações** e **Mostrar tentáculos**. A posição fora da tela usada no efeito não substitui a posição salva.

Com a física ligada, soltar em movimento arremessa o mascote: ele cai, quica e repousa no chão ou no topo das janelas. Segurar parado antes de soltar elimina o impulso; `Esc` cancela o gesto e mantém o mascote flutuando. Com a física desligada, soltar apenas posiciona o overlay.

O arremesso fica na área útil do monitor onde o gesto terminou. O corpo de colisão é circular; o teste de monitores com DPI diferentes e a travessia entre monitores durante o voo ainda estão pendentes.

## Documentação

- [Status atual e próximos passos](docs/STATUS_E_PROXIMOS_PASSOS.md)
- [Arquitetura](docs/ARQUITETURA.md)
- [Guia de animações](docs/GUIA_ANIMACOES_COMPANION.md)
- [Referência de animações](docs/REFERENCIA_ANIMACOES.md)
- [Pesquisa técnica](docs/PESQUISA.md)
