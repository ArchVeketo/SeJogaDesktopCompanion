# Auditoria técnica do Mário

**13/11/2026 · Windows · HEAD 000823e com alterações locais e arquivos ainda fora do Git**

O companion combina Panda3D, PySide6, Win32, Pymunk e áudio opcional em um processo Windows. A análise considera um mascote por sessão, executando continuamente, com mouse e janelas reais. As linhas apontam para a árvore examinada. A documentação canônica descreve o resultado pretendido e o [manual de engenharia](MANUAL_ENGENHARIA_ANIMACAO_MARIO.md) reúne o plano. Os achados abaixo descrevem a implementação observada.

## Prioridade alta

### 1. A resistência aponta pelo sinal da coordenada global da meta

`Meta.alvo_x` e `alvo_y` são posições absolutas do desktop. `direcao_meta` devolve o par direto, embora sua docstring diga “direção normalizada”. O controlador passa o par a `BodyMotion`, que divide por 240 e satura. Com Mário em X=900 e meta em X=600, a meta está à esquerda e o código produz direção X=+1. Mover a mesma cena para um monitor com origem negativa pode inverter o efeito. Calcular o vetor no mesmo referencial de alvo e corpo e só então transformar a direção para a pose. Cobrir os dois lados e o caso de distância zero. [Agência](../src/sejoga/animacao/agencia.py#L229) · [Controlador](../src/sejoga/animacao/controlador_animacao.py#L480) · [Consumo](../src/sejoga/animacao/movimento_corpo.py#L289)

### 2. O efeito de cursor perde a restauração em rotas de encerramento

O overlay tenta ocultar pela fase privada `roubo`. Na fase `cospe`, restaura e atualiza a flag. Se a fase ainda for `cospe`, a flag capturada for verdadeira e o estado já tiver mudado, as duas verificações podem chamar a restauração no mesmo tick. O ramo de saída de `_animation_tick` retorna antes da sincronização e as rotinas de encerramento examinadas não fazem a chamada correspondente. A API opera por contador. A consequência efetiva depende da thread e do estado do cursor do Windows. Provar a sequência com adaptador simulado e verificar efeito e restauração na janela real. Modelar o efeito de sistema como responsabilidade do overlay com uma única restauração por aquisição. O alcance implementado é encenação, tentativa de ocultação/restauração e deslocamento do mascote. As buscas em `src` não encontraram envio de cliques nem reposicionamento do cursor para cumprir a cena completa. [Sincronização](../src/sejoga/render/janela.py#L902) · [Saída](../src/sejoga/render/janela.py#L1780) · [ShowCursor](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-showcursor)

### 3. Idles novos quebram o contrato de perfil

`brc_stance` e `vibing` aparecem na tabela autoral. A validação de `Settings` rejeita ambos por estarem fora da lista de opções aceitas. Dois casos da suíte reproduziram o problema. Para cada estilo destinado ao usuário, comprovar ida e volta da interface ao perfil, reabertura e retorno a Padrão. Para estilo em ensaio, identificar sua disponibilidade como tal. [Clipes](../src/sejoga/animacao/clipes_ocioso.py) · [Configuração](../src/sejoga/configuracao.py) · [Reprodução](../tests/test_clipes_ocioso.py#L30)

### 4. Um módulo de animação passou a depender do renderer

`gestos_dedos.py` importa diretamente `render.dedos_malha`. A checagem de pureza reprovou na segunda execução. Separar cálculo de gesto e aplicação aos nós Panda no ponto de integração existente. Identificar quais funções dependem de pivôs reais antes de decidir onde ficam. [Import](../src/sejoga/animacao/gestos_dedos.py#L12) · [Guarda](../tests/test_camadas_puras.py)

## Integração e qualidade

### 5. A fase de áudio calculada para cada snapshot não entra na dança

O tracker publica `beat_phase`. O overlay passa energia, grave, BPM e `beat_detected`. A dança tem fase própria e correção suave pelo evento, o que já produz reação a onset. Entre o worker e o render, um booleano retido por vários frames vira uma única borda. Dois eventos sem amostra intermediária falsa podem se fundir, e um pulso inteiramente entre frames pode sumir. Medir este caso com timestamp de onset e taxa variável. Escolher um relógio de referência e passar a fase com timestamp ou eventos identificados. [Publicação](../src/sejoga/musica/escuta_musica.py#L247) · [Envio](../src/sejoga/render/janela.py#L725) · [Borda](../src/sejoga/animacao/controlador_animacao.py#L513) · [Dança](../src/sejoga/animacao/movimento_danca.py#L29)

### 6. A curiosidade por um ponto tem API sem produtor encontrado

`_tentar_gerar_meta` exige um ponto na fila para curiosidade. A busca em `src` e testes encontrou somente a declaração de `adicionar_ponto_interesse`. O overlay tem um fluxo separado de atenção por foco. O comportamento de exploração por destino aleatório está conectado. Para o cenário de interesse concreto do Manifesto, escolher um evento já disponível e passar posição relevante e identidade ao fluxo de agência. A confirmação é o mesmo ponto conduzir olhar, deslocamento e resistência. [Agência](../src/sejoga/animacao/agencia.py#L328) · [Seleção de meta](../src/sejoga/animacao/agencia.py#L381) · [Atenção do overlay](../src/sejoga/render/janela.py#L582)

### 7. A seleção de estado extraída diverge do caminho executado

A busca encontrou a declaração de `escolher_estado` e nenhum chamador. O controlador usa `_choose_state` com histerese. A 90 px/s, apoiado e sem música, o estado anterior WALK permite continuar andando no controlador. A extração devolve IDLE. O comentário sobre manter o arquivo com menos de 200 linhas descreve organização, enquanto o contrato importante é continuidade de estado. Manter uma única regra usada pelo entrypoint e provar entrada, saída e velocidades junto do limiar. [Extração](../src/sejoga/animacao/selecao_estado.py#L15) · [Runtime](../src/sejoga/animacao/controlador_animacao.py#L384)

### 8. Novas danças existem em dados, com integração incompleta

`street_groove`, `graffiti_dance` e `cyber_bounce` estão no mapa de frases. O seletor e o contrato persistido ainda oferecem os estilos anteriores. Três testes de rotações finitas nem chegam à amostragem porque a fixture de áudio lança `KeyError` para os três nomes. Registrar cada dança como autoria disponível ou como integrada ao perfil e ao seletor. Cobrir a entrada normal pelo estilo e a transição no palco antes de declarar a integração concluída. [Frases](../src/sejoga/animacao/danca_frases_tuning.py#L411) · [Perfil](../src/sejoga/configuracao.py#L159) · [Interface](../src/sejoga/desktop/interface.py#L164) · [Fixture](../tests/test_movimento_danca.py#L29)

### 9. O inventário de rig do Manual Unificado diverge dos exports

A contagem foi feita lendo os arrays do JSON, incluindo nós auxiliares, antes da montagem no Panda. O padrão resolve o stem `mario` e nesta pasta não havia `mario.glb`. O arquivo alternativo tem uma animação glTF. Isso não comprova que o runtime executa esse take. O inventário deve registrar origem, normalização, nós auxiliares e contagens antes e depois de montar o rig. Preservar a visão do canônico e conciliar o número publicado com o critério de contagem em revisão própria. [Manual Unificado](MANUAL_UNIFICADO_MARIO.md#3-anatomia-do-rig-e-especificação-técnica-3d) · [Resolvedor](../src/sejoga/nucleo/recursos.py#L67) · [Carregamento](../src/sejoga/render/renderizador.py#L268)

| Export inspecionado | Nós | Malhas | Skins | Animações |
| --- | ---: | ---: | ---: | ---: |
| `mario.gltf` | 91 | 56 | 0 | 0 |
| `projetoMARIO.gltf` | 88 | 56 | 0 | 1 |
| `Boomboxes.gltf` | 3 | 3 | 0 | 0 |
| `tentacle.gltf` | 1 | 1 | 0 | 0 |

### 10. Há dois caminhos de pose no controlador e o resolvedor tem condições para transição

O caminho chama funções que escrevem no rig e depois monta deltas para estados migrados. Camadas posteriores ainda podem consumir o resultado parcial. A docstring inicial fala em crossfade e o resolvedor usa interpolação quíntica com termo de velocidade de saída. O termo `dur * u * (1-u)^2` fornece velocidade inicial e zera na chegada. A derivada inicial pode mudar depois dos limites e colisões. Se a pose alvo se mover durante a transição, medir também a velocidade relativa dos dois lados. Antes de remover um caminho, rastrear junta e dono nos quadros críticos e comparar a saída final. [Controlador](../src/sejoga/animacao/controlador_animacao.py#L938) · [Resolvedor](../src/sejoga/animacao/resolvedor_poses.py#L84)

### 11. O roadmap descreve como futuro um caminho de squash/stretch já chamado

O renderer chama a composição e aplica uma matriz no pivô, com ramos para respiração, locomoção, queda, arraste, dança, impacto e sono. A existência desses ramos comprova ligação em código. O efeito na passada, no contato da caixa e no picking depende da ordem de aplicação e de qual nó cada consumidor observa. Registrar o estado como implementado para inspeção e pendente de aceite na janela real. Aplicar o mesmo critério aos arcos autorais, que já entram em `clipes_ocioso.py`. [Roadmap](STATUS_E_PROXIMOS_PASSOS.md) · [Escala](../src/sejoga/render/renderizador.py#L772) · [Arcos](../src/sejoga/animacao/clipes_ocioso.py#L10)

## Comentários do código que pedem rastreabilidade

| Local | O que o comentário diz | Como tratar |
| --- | --- | --- |
| [agencia.py](../src/sejoga/animacao/agencia.py#L234) e [movimento_corpo.py](../src/sejoga/animacao/movimento_corpo.py#L251) | Vetor normalizado em um lugar, alvo da janela em outro. | Corrigir o contrato com o defeito 1. Colocar unidade e origem no ponto que produz o dado. |
| [controlador_animacao.py](../src/sejoga/animacao/controlador_animacao.py#L187) | Atraso de cadeia por mola como follow-through. | Registrar os estados que realmente usam o recurso. No manual, distinguir a resposta de arraste/queda da autoria de idle e dança. |
| [colisao_bracos.py](../src/sejoga/animacao/colisao_bracos.py#L15) | Caixas de repouso aproximam o corpo. | Testar a aproximação em torção e squash. Se a cena cruza o limite, atualizar só os volumes dos contatos que falham. |
| [colisao_bracos.py](../src/sejoga/animacao/colisao_bracos.py#L126) | Picos históricos próximos de 41 ms na busca. | Medir o frame atual com cProfile/PStats e a ação correspondente. A cifra histórica indica onde olhar. |
| [renderizador.py](../src/sejoga/render/renderizador.py#L929) | Mão não fixa durante giro. | Reproduzir com apoio em cena. Definir se aquele take exige âncora e medir o deslocamento da mão. |
| [janela.py](../src/sejoga/render/janela.py#L691) e [sistema_tentaculos.py](../src/sejoga/tentaculos/sistema_tentaculos.py#L439) | Refatoração depende de evidência visual. | Ligar cada TODO a um caso observável. Extrair por responsabilidade e medir o mesmo take antes e depois. |
| [README do projeto](../README.md#L104) | Molas aparecem como descrição central do motor. | Atualizar em revisão editorial para refletir a autoria e registrar o papel residual na resposta física. |

## O que causou os problemas antigos

| Família e registros | Causa ou armadilha documentada | Aplicação agora |
| --- | --- | --- |
| [Naturalidade](MUDANCA_ANIMACAO_NATURALIDADE.md), [Estudo procedural legado](ESTUDO_ANIMACAO_PROCEDURAL.md), [melhorias de animação](MELHORIAS_ANIMACAO_2026-11-04.md) | Colisão conservadora afastou demais os braços e levou à pose de abraço. Curl alto produziu garrinha. Crossfade zerou velocidade. Limites duros criaram parada seca. | Validar peso e silhueta em movimento. Diferenciar contato real de margem conservadora. Tratar curvas e limites onde o gesto perde leitura. |
| [Recalibração GPU](RECALIBRACAO_GPU.md), [Mapeamento do rig](Mapeamento%20Completo%20do%20Corpo%20do%20Rig%20Detecção%20e%20Nomenclatura.md) | Ângulo de uma junta repetido na descendente somou giro. Profundidade de membro foi inferida de vista frontal. Cascata dos dedos podia duplicar flexão. | Provar em FK, perfil e captura de contorno. Aplicar rotação no eixo local e separar movimento de pai e filho. |
| [Guia técnico](GUIA_TECNICO_CORRECOES.md), [revisão do código](RELATORIO_REVISAO_CODIGO.md) | Porta recebeu ordens concorrentes. Volta de costas teve salto. Passo do fio sobre o eixo da cápsula não tinha direção radial válida. | Ter dono por fase, capturar continuidade e prever caso degenerado da restrição. As reproduções históricas exigem reteste antes de reabrir cada bug. |
| [Guia Companion](GUIA_ANIMACOES_COMPANION.md), [referência de animações](REFERENCIA_ANIMACOES.md), [decisões](DECISOES_ANIMACOES.md) | A descrição misturava ideias, presets, clipes exportados e caminhos do runtime. Uma cena existente no arquivo podia ser tomada como executada. | Exigir arquivo resolvido, canal aplicado, evento e captura do take. |
| [Guia de dança](GUIA_ANIMACAO_DANCA.md), [revisão de dança](REVISAO_GUIA_DANCA_2026-11-05.md), [caixa musical](RELATORIO_CAIXA_MUSICAL_2026-11-05.md) | BPM apresentado como gênero, suporte manual confundido com apoio validado, ferramentas antigas citadas como atuais e pose artística de caixa confundida com protótipo. | Registrar preset, sinal de áudio e apoio observado. Testar contato com caixa na pose final. Os comandos de produção ficam no manual novo. |
| [Arquitetura histórica](ARQUITETURA.md), [pesquisa](PESQUISA.md), [sessão de 04/11](SESSION_SUMMARY_2026-11-04.md) | Propostas de stack e sequência de implementação envelheceram com as decisões do runtime. | Ler os fluxos a partir de `__main__`, overlay, controlador e build atual. |
| [Distribuição](DISTRIBUICAO_WINDOWS.md), [validação de updater/GPU](validacao-updater-gpu.md), [release notes](RELEASE_NOTES_v0.1.0.md) | Ausência de assets no ZIP, escrita em Program Files antes de UAC, política de versão discrepante e DLL Qt incompatível por PATH. | Abrir pacote extraído, conferir assets atuais e testar atualização com ACL real. Preservar filtro de PATH e registrar DLL carregada. |
| [Refatoração](REFATORACAO_CONVENCAO.md), [convenção Python](CONVENCAO_PYTHON.md), [ambiente Codex](AMBIENTE_CODEX.md) | Nomes e paths históricos viraram referências quebradas. Fatiar hot paths sem prova dificultou comparar movimentos. | Usar símbolos atuais. Fazer lote por responsabilidade, apoiado por uma cena comparável. |
| [Desempenho](MELHORIAS_FUTURAS_ANIMACAO_DESEMPENHO.md), [design de assets](VISUAL_DESIGN_ASSETS.md), [backlog](BACKLOG_CONTEUDO.md), [DSH](REFERENCIA_DSH_PLUGINS.md) | Propostas de recursos e estimativas perderam contexto de resolução, release e estágio de implementação. | Reusar como registro de contexto. Medir com o canvas e o build atuais antes de escolher novas dependências. |
| [Rain World](ESTUDO_PROCEDURAL_RAIN_WORLD.md), [footwork](ESTUDO_FOOTWORK_MARIO.md), [idle](ESTUDO_IDLE_E_LINGUAGEM_CORPORAL.md), [fluidez](ESTUDO_FLUIDEZ_E_ANIMACAO_PROCEDURAL.md) | Procedimento, movimento físico e autoria foram discutidos sob várias revisões. Modelos e medições pertencem à cena descrita. | Levar para o Mário retenção de atenção, transferência de peso e resposta contextual. Avaliar técnica no rig rígido e sob interrupção. |
| [Diretriz de animação](DIRETRIZ_12_PRINCIPIOS_ANIMACAO.md) e [índice](README.md) | Uma lista de técnicas pode parecer comprovação de qualidade. | Usar a matriz do Manual Unificado para julgar os doze princípios juntos em cada take. |

### Rechecagem de correções históricas

- O conversor atual deriva o MIME da URI e calcula o comprimento do buffer após anexar imagens. O normalizador valida o caminho de saída explícito. Isso responde às causas históricas observadas em código. Um GLB recém-exportado ainda exige validação Khronos. [Conversor](../tools/converter_gltf_para_glb.py#L86) · [Normalizador](../tools/atualizar_rig_modelo.py#L335)
- O workflow comum já instala `music-loopback`. O loader atual de caixas aponta para `Boomboxes.gltf`. O asset aparece fora do Git na árvore examinada. A disponibilidade em um checkout limpo ou bundle precisa ser comprovada quando o asset fizer parte da entrega. [Workflow](../.github/workflows/_build-comum.yml#L66) · [Loader](../src/sejoga/musica/caixa_som.py#L33)
- O smoke de polling remove o polling real e injeta amostras. Ele pode testar picking e framebuffer de uma janela real com um perfil temporário. A entrada pelo sistema deve ser verificada com o smoke nativo. [Polling](../tools/smoke_mouse.py#L57) · [Mouse nativo](../tools/smoke_corpo_nativo.py)

## Testes executados

A suíte rodou com `PYTHONPATH=src`, sem cache do pytest e sem bytecode. A segunda execução usou `python -m pytest -o addopts='' -p no:cacheprovider --tb=no -q` e registrou **773 aprovados e 17 falhas em 27,52 s**. A primeira execução mostrou 15 falhas, sem as falhas de pureza e atraso de ombros daquela segunda execução. O diff de código da árvore local mudou durante o estudo por alterações externas a esta entrega. Os resultados correspondem aos arquivos disponíveis durante cada execução, sem atribuição causal da diferença entre rodadas.

| Grupo | Falhas na segunda rodada | Leitura |
| --- | ---: | --- |
| Configuração | 3 | Dois idles novos rejeitados. No TOML inválido, os defaults foram retornados e o aviso saiu no logger, enquanto o teste esperava stdout. |
| Fixture de dança | 3 | `KeyError` para três estilos novos antes de testar rotações finitas. |
| Pureza de camadas | 1 | Import de renderer a partir de animação de dedos. |
| Contratos antigos e diagnóstico de movimento | 10 | Limites de jerk em wake, idle playful e dois casos de queda, fechamento da corrida, flail/espelho em dois testes, ombros de BRC stance, atraso de ombros e amplitude de respiração. A câmera e a intenção da pose devem arbitrar quais limites continuam relevantes. |

**Próximo trabalho.** Corrigir os contratos de meta, efeitos de cursor, perfil e autoria antes de estabilizar a sequência completa de locomoção e arraste. A primeira captura deve mostrar o defeito atual e a cena que servirá de comparação.

**Limites.** Revisão dirigida dos fluxos críticos, comentários e documentação histórica. Cada linha de todos os módulos, os binários de terceiros, proveniência dos assets, distribuição elevada e revisão visual de GPU ficaram fora desta execução. Os testes e as contagens de glTF não avaliam a atuação do mascote. Esta entrega escreveu exclusivamente os novos documentos Markdown.
