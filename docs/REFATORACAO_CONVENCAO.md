# Refatoração para a convenção Python

Registro da refatoração de `src/`, `tests/` e `tools/` para [CONVENCAO_PYTHON.md](CONVENCAO_PYTHON.md), feita na branch `frente3-animacao` sem mudança de comportamento. Docs datados (`SESSION_SUMMARY_2026-11-04`, `MELHORIAS_ANIMACAO_2026-11-04`, `REVISAO_GUIA_DANCA_2026-11-05`) mantêm os nomes da época; use o mapa abaixo para traduzir.

## Baseline (HEAD 62aa821)

- `python -m pytest`: verde.
- `ruff check` com as regras novas: 520 achados (D 330, PLR0915 55, E702 39, PLR1702 27, C901 20, N 27, E701 8, I001 8, E402 1 fora de `window.py`).
- `mypy src tools`: 14 erros em 5 arquivos, todos preexistentes (`physics`, `renderer`, `fio_corda`, `idle_clips`, `fio_fone_malha`).
- `smoke_mouse`: já falhava em `WindowFromPoint` neste ambiente.

## Resultado

- `ruff check src tests tools` e `ruff format --check src tests tools`: limpos.
- `mypy src tools`: os mesmos 14 erros do baseline, agora com os nomes novos (`fisica`, `renderizador`, `fio_corda`, `clipes_ocioso`, `fio_fone_malha`).
- `python -m pytest`: verde em todos os commits.
- Caracterização (script fora do repositório): saídas das `pose_*` (todos os `kind`, incluindo `hover`), de `braco_hpr_graus`, de 1500 quadros do `AnimationController.update` em todos os estados e de 900 quadros do `TentacleDirector.update`. Comparadas com igualdade exata de float contra o HEAD 2a63fba depois de cada lote que tocou esses módulos: idênticas.
- `smoke_mouse` e `smoke_mouse --physics`: abrem a janela real com os módulos novos e falham no mesmo `assert WindowFromPoint` do baseline.

## Decisões

1. Renomeados módulos, testes e scripts de `tools/`. Identificadores em inglês (classes, métodos, variáveis) só mudaram onde o ruff `N` exige. O restante fica para um lote próprio, para não arriscar o "sem mudar comportamento".
2. O nome de teste em três partes vale para testes novos. Os antigos mantêm o nome.
3. `tests/**` ignora `D102`, `D103` e `D107`: o nome do teste já descreve o cenário. A docstring de módulo continua obrigatória.
4. `max-nested-blocks = 3`, como diz a convenção (o padrão do ruff é 5). `PLR1702` só existe em preview, por isso `preview = true` com `explicit-preview-rules = true` (nenhuma outra regra de preview liga).
5. `ignore` global:
   - `N802` e `N816`: nomes camelCase exigidos por Panda3D, Qt e Win32 (`userExit`, métodos do Qt).
   - `D401`: a heurística de modo imperativo do ruff é do inglês e erra em português ("Converte" falha, "Devolve" passa).
6. `E402` só em `render/janela.py`. `tools/construir_atualizacao.py` e `tools/gerar_modelo_tentaculo.py` carregam o `sejoga` com `importlib.import_module` depois do `sys.path.insert`, sem precisar da exceção.
7. Encoding: UTF-8 sem BOM e LF no índice (`.editorconfig`). Os quatro arquivos do fio do fone que tinham BOM perderam o BOM.
8. Dependência invertida `nucleo → animacao` corrigida:
   - O IK do braço por alvo (`braco_hpr_graus`, `definir_modelo_ik`) saiu de `nucleo/rig.py` para `animacao/braco_hpr.py`.
   - As `pose_*` e `_idle_pulse` saíram para `animacao/poses_base.py`.
   - `flexible_rig.py` foi para `animacao/rig_flexivel.py`.
   - As constantes da FK (`TORCAO_BASE_ANTEBRACO_GRAUS`, `EPSILON_DEGENERADO`) foram para `nucleo/cinematica_const.py`. `animacao/braco_tuning.py` as reexporta.
   - `tests/test_camadas_puras.py` agora varre todos os módulos de `nucleo/`, `rig_mapa/`, `animacao/` e `configuracao.py`, e proíbe `nucleo` de importar `animacao` ou `rig_mapa`.
9. `animacao/lower_body.py` importava `panda3d.core`, então foi para `render/corpo_inferior.py`.
10. Constantes locais em maiúsculo viraram constantes de módulo com o mesmo valor:
    - `SURPRESA_*` em `gestos_tuning`.
    - `ARRASTE_PENDENTE_*` em `movimento_corpo_tuning`.
    - `_ARRASTE_BRACO_Z` e `_PEGA_CORPO_BRACO_Z` em `controlador_animacao`.
    - `ATENCAO_BORDA_MARGEM_PX` em `janela_const`.
11. Aliases de módulo em maiúsculo (`T`, `C`) viraram `tuning_dedos`, `tuning_gestos` e `const_desktop` (N812). `RenderIndisponivel` virou `RenderIndisponivelError` (N818).
12. Funções fatiadas de verdade (sem mudar a ordem das operações):
    - `pose_interaction`: despacho por `kind`, e `kind` desconhecido continua aplicando só a base.
    - `pose_sneeze` e `pose_secondary`.
    - `modelo._compute_bounds`, `rig_flexivel.__init__`, `gestos_dedos.update`, `dedos_malha._ler_triangulos`.
    - `atualizador.download_update`, que mantém os mesmos limites de tamanho e SHA256.

## Exceções que ficaram (TODO convenção)

Funções grandes ou muito aninhadas, cujo fatiamento exige prova visual na GPU ou no desktop real, ficaram com `# noqa: <regra>  # TODO convenção: <motivo>` na linha da `def`. São 69 marcações. Liste-as com `git grep -n "TODO convenção" -- src tests tools`. As principais:

- `animacao/controlador_animacao.py`: `update` (183 comandos, complexidade 50) e `__init__`.
- `animacao/interacao_mouse.py` `update`, `movimento_pernas.update`, `movimento_corpo.update`, `colisao_bracos._resolver_lado`, `primitivas_colisao`.
- `render/janela.py` (`_mouse_poll`, `__init__`, `_fit_pose_window`, `_apply_settings`, menus) e `render/renderizador.py` (`update_appendages`, `__init__`, `_setup_*`).
- `tentaculos/sistema_tentaculos.py` (geometria, segmentos, separação, transições), `renderizador_tentaculos`, `gotas_tentaculos`, `modelo_tentaculo`, `coreografia_porta.avancar`.
- `desktop/interface.py` (montagem do diálogo Qt), `desktop/fisica.py`, `musica/caixa_som.py`, `musica/escuta_musica.py`.
- Ferramentas de captura e calibração em `tools/` e testes de cenário longo.

Também ficam para lotes próprios:

- Imports dentro de função em módulos com engine (`render/`, `desktop/`, `musica/`, `distribuicao/`, `tentaculos/`, `configuracao.py`, `__main__.py`). Eles existem por dependência opcional (`winrt`, `soundcard`, `numpy`, `pygame`, `simplepbr`, `PIL`), pela ordem Qt antes do Panda3D ou por custo de startup. No pacote puro `animacao/` todos foram para o topo, sem ciclo.
- Literais numéricos de domínio ainda soltos dentro das poses e dos gestos.
- Identificadores em inglês (por exemplo `AnimationController`, `BodyMotion`, `pose_idle`).

## Mapa de renomeações (antigo → novo)

Prefixo `src/sejoga/`.

| Antigo | Novo |
|---|---|
| `config.py` | `configuracao.py` |
| `nucleo/assets.py` | `nucleo/recursos.py` |
| `nucleo/model.py` | `nucleo/modelo.py` |
| `nucleo/rig.py` | `nucleo/esqueleto.py` + `animacao/braco_hpr.py` + `animacao/poses_base.py` |
| `nucleo/flexible_rig.py` | `animacao/rig_flexivel.py` |
| — | `nucleo/cinematica_const.py` |
| `animacao/animation.py` | `animacao/controlador_animacao.py` |
| `animacao/anim_clips.py` | `animacao/clipes_animacao.py` |
| `animacao/anim_layers.py` | `animacao/camadas_animacao.py` |
| `animacao/appendages.py` | `animacao/apendices.py` |
| `animacao/arm_ik.py` | `animacao/ik_bracos.py` |
| `animacao/arm_targets.py` | `animacao/alvos_bracos.py` |
| `animacao/attention.py` | `animacao/atencao_hover.py` |
| `animacao/body_motion.py` | `animacao/movimento_corpo.py` |
| `animacao/body_motion_tuning.py` | `animacao/movimento_corpo_tuning.py` |
| `animacao/dance_frases_tuning.py` | `animacao/danca_frases_tuning.py` |
| `animacao/dance_motion.py` | `animacao/movimento_danca.py` |
| `animacao/dance_poses.py` | `animacao/poses_danca.py` |
| `animacao/dance_tuning.py` | `animacao/danca_tuning.py` |
| `animacao/delta_states.py` | `animacao/estados_delta.py` |
| `animacao/exit_animation.py` | `animacao/animacao_saida.py` |
| `animacao/finger_gestures.py` | `animacao/gestos_dedos.py` |
| `animacao/hand_motion.py` | `animacao/movimento_maos.py` |
| `animacao/idle_clips.py` | `animacao/clipes_ocioso.py` |
| `animacao/interaction.py` | `animacao/interacao_mouse.py` |
| `animacao/joint_springs.py` | `animacao/molas_juntas.py` |
| `animacao/leg_motion.py` | `animacao/movimento_pernas.py` |
| `animacao/lower_body.py` | `render/corpo_inferior.py` |
| `animacao/pose_resolver.py` | `animacao/resolvedor_poses.py` |
| `animacao/rig_base.py` | `animacao/pose_repouso.py` |
| `animacao/spring_tuning.py` | `animacao/mola_tuning.py` |
| `desktop/autostart.py` | `desktop/inicializacao_automatica.py` |
| `desktop/desktop_shell.py` | `desktop/integracao_desktop.py` |
| `desktop/physics.py` | `desktop/fisica.py` |
| `desktop/tray_registration.py` | `desktop/registro_bandeja.py` |
| `desktop/ui.py` | `desktop/interface.py` |
| `distribuicao/updater.py` | `distribuicao/atualizador.py` |
| `distribuicao/update_ui.py` | `distribuicao/dialogo_atualizacao.py` |
| `musica/music.py` | `musica/escuta_musica.py` |
| `musica/music_speaker.py` | `musica/caixa_som.py` |
| `musica/sound_effects.py` | `musica/efeitos_sonoros.py` |
| `musica/speaker_effects.py` | `musica/efeitos_caixa_som.py` |
| `render/canvas_envelope.py` | `render/envelope_janela.py` |
| `render/chroma_resolve.py` | `render/resolucao_croma.py` |
| `render/debug.py` | `render/depuracao.py` |
| `render/outline_dynamics.py` | `render/dinamica_contorno.py` |
| `render/renderer.py` | `render/renderizador.py` |
| `render/win32_overlay.py` | `render/sobreposicao_win32.py` |
| `render/window.py` | `render/janela.py` |
| `render/window_const.py` | `render/janela_const.py` |
| `tentaculos/tentacles.py` | `tentaculos/renderizador_tentaculos.py` |
| `tentaculos/tentacle_constraints.py` | `tentaculos/restricoes_tentaculos.py` |
| `tentaculos/tentacle_drips.py` | `tentaculos/gotas_tentaculos.py` |
| `tentaculos/tentacle_model.py` | `tentaculos/modelo_tentaculo.py` |
| `tentaculos/tentacle_system.py` | `tentaculos/sistema_tentaculos.py` |

`tools/`:

| Antigo | Novo |
|---|---|
| `build-update.py` | `construir_atualizacao.py` |
| `build_icon.py` | `gerar_icone.py` |
| `build_tentacle_model.py` | `gerar_modelo_tentaculo.py` |
| `gltf_to_glb.py` | `converter_gltf_para_glb.py` |
| `inspect_model.py` | `inspecionar_modelo.py` |
| `oraculo_cena.py` | `gerar_oraculo_cena.py` |
| `preview_body_actions.py` | `visualizar_acoes_corpo.py` |
| `profile_animation.py` | `perfilar_animacao.py` |
| `smoke-updater.py` | `smoke_atualizador.py` |
| `smoke_bundle_dances.py` | `smoke_pacote_dancas.py` |
| `smoke_native_body.py` | `smoke_corpo_nativo.py` |

Os testes seguem o módulo testado. Por exemplo, `test_animation` virou `test_controlador_animacao`, `test_physics` virou `test_fisica` e `test_settings_dialog` virou `test_interface`. Três testes foram renomeados pelo que testam: `test_grab_parts` virou `test_movimento_corpo_pegas`, `test_installer_shutdown` virou `test_integracao_desktop` e `test_update_package` virou `test_construir_atualizacao`.

## Fechamento

- pytest verde; ruff limpo; mypy com os mesmos 14 erros do baseline.
- Pendente: `.\build.ps1` nao rodou neste ambiente (modulo PyInstaller ausente no Python 3.12 do usuario). Rodar o build na maquina com PyInstaller e abrir `dist/SeJogaCompanion` para validar na GPU.
