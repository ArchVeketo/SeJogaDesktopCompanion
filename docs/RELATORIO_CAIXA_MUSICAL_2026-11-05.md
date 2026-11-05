# Caixa musical — 05/11/2026

## Implementação

- Caixa maior que a pose neutra: largura ×1,20, altura ×1,15 e profundidade ×0,40 da largura do personagem.
- Graffiti original aplicado. Leitura da textura por bytes nativos e PNMImage para funcionar no PyInstaller.
- Head nod voltado ao lado oposto, braços cruzados e costas apoiadas na lateral; correção pelo plano de contato sem deslocamento vertical dos pés.
- Espirro lateral com preparação, ejeção em arco e pouso. Três tentáculos empurram pontos diferentes do exterior da caixa, respeitando colisões e recolhendo depois.
- Gosma rosa low-poly volumétrica escorre pela frente, afina e desaparece até 6,5 segundos. Sem planos transparentes.
- Cones pulsam também radialmente, para a reação ficar visível na câmera ortográfica. Ondas e tremor seguem fase, energia e graves.
- Som curto original no pouso respeita áudio/volume; prévia de dança permanece silenciosa.

## Validação

- 97 testes passaram, incluindo ciclo de gosma/ondas e devolução dos tentáculos ao pool.
- Smokes de mouse com e sem física passaram.
- Mouse nativo: erro do ponto de pega 0 px, inversão de balanço e recuperação da bandeja passaram.
- `tools/preview_music_scene.py`: capturas de preparação, ejeção, pouso e repouso; tamanho, contatos, presença conjunta de gosma/tentáculos e limpeza final verificados com perfil temporário.
- Primeira tentativa no bundle revelou falha no carregamento da textura; corrigida usando leitura direta dos bytes.

- Bundle recompilado e instalado em `%LOCALAPPDATA%/Programs/SeJogaCompanion/current`: quatro prévias de dança passaram, bandeja registrada e saída 0. Captura do desktop inspecionada; textura aparece e o fundo fica transparente. Evidências em `%TEMP%/sejoga-bundle-dances-uobf6bs_`.
- A execução direta no checkout não conseguiu registrar a bandeja neste ambiente; a cópia instalada pelo `tools/install-local.ps1` passou. Usar o atalho instalado para testar.

## Limites artísticos

A ejeção e os contatos são procedurais. Hip hop e breakdance ainda precisam de frases mais autoradas, apoio de mão no chão e polimento de footwork; os fones ainda não têm textura reativa. BPM continua sendo uma heurística, com seleção manual disponível. Esses itens não são considerados finalizados por esta etapa.
