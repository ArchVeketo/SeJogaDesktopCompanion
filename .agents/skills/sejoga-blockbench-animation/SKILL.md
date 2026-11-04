---
name: sejoga-blockbench-animation
description: Alterar animações e assets Blockbench do SeJogaDesktopCompanion preservando o rig GLTF, a orientação e as convenções do modelo.
---

Leia `docs/GUIA_ANIMACOES_COMPANION.md` e `docs/REFERENCIA_ANIMACOES.md` nas partes relevantes ao estado solicitado.

- O modelo usa nós de transformação, sem skin. Preserve os nomes em `rig.ALL_GROUPS` e a hierarquia; confira com `tools/inspect_model.py` e `tests/test_model.py`.
- Presets em `rig.py` não dependem do engine. O renderer aplica rotações relativas à pose base. A frente exportada aponta +Y e recebe heading 180 no renderer.
- A porta abre na dobradiça; preserve pivô e partes transparentes. O contorno deve receber os mesmos movimentos e respeitar alpha.
- Para clipes exportados, mantenha nomes como `idle`, `walk`, `run`, `throw`, `dance`, `hit`, `sleep`, `wake` conforme o guia; loops precisam de continuidade entre primeiro e último frame. O loader atual não implica suporte automático a novos clipes.
- Prefira exportação direta do Blockbench. Não introduza conversão pelo Blender sem necessidade do pedido. Valide o GLTF/GLB exportado com glTF Validator quando disponível, registrando se não foi possível executar.
- Inspecione capturas de início, pico e fim da pose e das transições afetadas. O roadmap deve distinguir preset procedural implementado de clipe ainda não integrado.
