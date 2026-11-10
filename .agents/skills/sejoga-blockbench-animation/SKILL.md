---
name: sejoga-blockbench-animation
description: Alterar animações e assets Blockbench do SeJogaDesktopCompanion preservando o rig GLTF, a orientação e as convenções do modelo.
---

Leia `docs/GUIA_ANIMACOES_COMPANION.md`, `docs/REFERENCIA_ANIMACOES.md` e **`docs/GUIA_ANIMACAO_DANCA.md`** nas partes relevantes ao estado solicitado.

- O modelo usa nós de transformação, sem skin. Preserve os nomes em `rig.ALL_GROUPS` e a hierarquia; confira com `tools/inspecionar_modelo.py` e `tests/test_modelo.py`.
- Presets em `esqueleto.py` não dependem do engine. O renderer aplica rotações relativas à pose base. A frente exportada aponta +Y e recebe heading 180 no renderer.
- A porta abre na dobradiça; preserve pivô e partes transparentes. O contorno deve receber os mesmos movimentos e respeitar alpha.
- Para clipes exportados, mantenha nomes como `idle`, `walk`, `run`, `throw`, `dance`, `hit`, `sleep`, `wake` conforme o guia; loops precisam de continuidade entre primeiro e último frame. O loader atual não implica suporte automático a novos clipes.
- Prefira exportação direta do Blockbench. Não introduza conversão pelo Blender sem necessidade do pedido. Valide o GLTF/GLB exportado com glTF Validator quando disponível, registrando se não foi possível executar.
- Inspecione capturas de início, pico e fim da pose e das transições afetadas. O roadmap deve distinguir preset procedural implementado de clipe ainda não integrado.

## Animações de dança

O guia completo de dança está em `docs/GUIA_ANIMACAO_DANCA.md` com referências detalhadas de:
- Caixa de som low-poly estilo Friday Night Funkin
- Ranges de BPM por gênero musical (rock 110-170, hip-hop 85-115, eletrônica 120-145, breakdance 135-150)
- Referências de animação para cada estilo (headbanging, breakdance, head bob, rock and roll gesture)
- Sistema de "espirro lateral" para ejetar a caixa de som
- Poses e ciclos específicos por gênero musical

Priorize a direção artística confirmada na versão 2.0: caixa maior que o mascote em altura e largura; head nod lateral com costas apoiadas, braços cruzados e pés firmes. O apoio atual de uma mão em caixa pequena é um protótipo que não atende a essa pose. Separe explicitamente especificação, implementação e validação. BPM é heurística de seleção de estilo, não identificação confiável de gênero.
