# Guia técnico para as próximas correções

Este guia reúne as regras necessárias para implementar e verificar os pontos da revisão técnica do SeJoga Desktop Companion. Os casos originais usam a base auditada na branch `codex/refatoracao`, commit `423f0f8`. Use as condições de aceitação também para revisar correções já em andamento.

Na revisão deste documento, a worktree já continha mudanças de código em andamento. Em checagens isoladas dessa versão, o ZIP gerado incluiu os dois modelos das caixas de som e o GLB do Mário declarou 128.987 bytes, exatamente o fim da última região. O código em andamento também passou a encaminhar `--channel` ao launcher e a tratar `ValidationError` na leitura do perfil. A atualização elevada e a inicialização do executável extraído ainda precisam ser exercitadas.

## 1. Distribuição e atualização

### O ZIP precisa conter o que a inicialização abre

O PyInstaller gera o runtime completo. O instalador e o ZIP de atualização filtram esse conteúdo por caminhos diferentes. Na base auditada, o ZIP removia qualquer arquivo `.bbmodel`. `MusicSpeaker` é construído junto ao renderer e abre modelos Blockbench mesmo antes de a primeira música tocar.

O contrato mínimo da caixa de som inclui estes caminhos relativos à raiz do bundle:

| Arquivo | Uso |
| --- | --- |
| `_internal/assets/assets/boomboxgrande/BoomboxGRANDE.bbmodel` | Geometria da caixa central |
| `_internal/assets/assets/boomboxgrande/texture.png` | Textura central usada pelo código |
| `_internal/assets/assets/BoomboxSIde1.bbmodel` | Geometria das duas caixas laterais |
| `_internal/assets/assets/texture.png` | Textura lateral |

Em `tools/construir_atualizacao.py`, a correção imediata é manter a exclusão de fontes e abrir exceção pelos caminhos exatos que o runtime consome. Compare o conteúdo do ZIP final com o contrato de entrada do app. A checagem deve falhar se uma dependência estiver ausente no bundle de entrada ou for retirada pelo filtro. Inclua também o executável, o modelo principal com suas dependências e `release-info.json` no cenário de aceitação. Preserve a exclusão de `user-data` e logs.

Para simplificar a hierarquia depois, separe assets de execução e arquivos de autoria por diretório e migre carregador, instalador e empacotador juntos. O contrato deve seguir os caminhos efetivamente usados por `assets_dir()`, inclusive sob `_internal` no bundle.

### Canal por usuário e troca de runtime por máquina

O diálogo Qt roda com o token normal do usuário. A instalação padrão fica em Program Files, onde o runtime pode ler seus arquivos, mas a gravação costuma exigir elevação. O verbo `runas` inicia o agente elevado e pode resultar em recusa do usuário. O launcher original pode reabrir o runtime com seu token normal.

1. Capture o canal no início da consulta. Vincule o resultado à consulta e descarte respostas antigas quando o seletor mudar. Na confirmação, use o canal associado ao resultado.
2. Passe o canal ao launcher como um valor fechado em `release`, `prerelease` ou `nightly`. Valide-o também no C# antes de montar a URL. Uma chamada proposta é `--update --channel nightly`. O launcher repassa o valor validado ao agente elevado. A origem do feed continua sendo determinada pelo código.
3. Deixe `channel-info.json` como metadado da instalação ou como valor de compatibilidade para chamadas sem argumento. A preferência individual continua no TOML. Se houver uma gravação de metadado global, faça-a na etapa elevada e associe-a ao resultado da instalação.
4. Mantenha uma regra compartilhada para decidir se o candidato pode substituir a versão instalada. A regra pode ser implementada em Python e C# com os mesmos vetores de entrada e saída. Dentro de um canal, compare a ordem de versão e o identificador de build. Para mudança de canal, documente se um candidato com ordem inferior pode ser instalado e como o usuário confirma essa escolha. Exemplo que precisa de resultado explícito: estável `0.1.0` → nightly `0.1.0.dev20261111000000`, com ID mais novo.
5. Trate a versão confirmada e a versão baixada como parte do mesmo contrato. Se o manifesto mudar durante o handoff, informe a alteração antes de instalar outro candidato ou faça o agente recusar a tentativa e solicitar nova busca. Uma combinação de canal, versão, build ID e SHA-256 identifica o candidato. O agente consulta o feed oficial e verifica os dados por conta própria.

O launcher é instalado fora de `runtime/current`. Uma nova opção de linha de comando exige distribuir o launcher compatível antes de fazer o runtime depender dela. No caminho legado, o cliente precisa informar a incompatibilidade de forma clara e manter o app disponível.

### Preparação, troca e publicação

- Prepare o ZIP em uma pasta isolada no mesmo volume da instalação. Verifique tamanho e SHA-256, rejeite nomes que escapem do destino e confirme o layout extraído. Faça a troca sob o mutex da instalação e registre a fase que falhou. O caso de interrupção entre as duas renomeações precisa conseguir recuperar `previous` com `current` ausente.
- Diferencie versão recusada, recusa de UAC, erro de download e troca concluída. O chamador que reabre o mascote deve refletir qual runtime ficou ativo. Um erro de registro depois da troca merece tratamento distinto de um erro anterior à troca.
- No GitHub Actions, faça o valor de `github.ref_name` chegar ao PowerShell por `env` e leia-o com `$env:...`. Interpolar a expressão dentro de `run` insere caracteres no script antes de o shell analisá-lo. Valide a tag de acordo com o formato de versão que `version_order()` aceita. Passe os argumentos ao comando como elementos de um array.
- Em cada canal, publique o ZIP do candidato antes de promover seu manifesto. A publicação de um job mais antigo que concluiu depois deve preservar o manifesto mais recente. Confira o build ID remoto no ponto de promoção e serialize essa etapa por canal quando houver publicações concorrentes.
- Se a distribuição oferece loopback, instale o extra `music-loopback` no mesmo ambiente do PyInstaller. A validação final é abrir o executável e confirmar que o worker consegue abrir o dispositivo de captura, com o recurso ativado em um perfil isolado.

**Aceitação do fluxo.** Gere o ZIP, inspecione seu conteúdo, extraia em um diretório limpo e inicie aquele executável com perfil temporário. Em uma instalação de teste, busque o candidato como usuário normal. Exercite aceitar e recusar o UAC, feed alterado, erro de integridade e interrupção entre `current` e `previous`. Compare o `release-info.json` ativo com o resultado exibido. A fonte e o bundle anterior podem esconder dependências ausentes no ZIP recém-gerado.

## 2. glTF e GLB

### Conversão autocontida

GLB tem cabeçalho de 12 bytes com magic, versão e tamanho total. Cada chunk tem um cabeçalho de 8 bytes. O JSON vem primeiro e o BIN vem em seguida, quando existe. O alinhamento é de quatro bytes. O JSON completa o alinhamento com espaços e o BIN com zeros.

O comprimento declarado em `buffers[0].byteLength` é o dos dados do buffer depois de anexar as imagens e antes do padding final do chunk. Cada `bufferView` precisa caber nessa faixa. O comprimento físico do BIN pode exceder o lógico em até três bytes por causa do padding. Uma imagem apontada por `bufferView` declara seu MIME, que precisa corresponder aos bytes.

Sequência para `tools/converter_gltf_para_glb.py`:

1. Decodifique a geometria e valide a entrada que o conversor se compromete a aceitar.
2. Para cada imagem embutida, alinhe seu início, registre offset e comprimento, anexe os bytes e substitua a URI por `bufferView` e MIME coerente.
3. Registre o tamanho lógico final. Complete o alinhamento físico e calcule o tamanho total do contêiner.
4. Reabra a saída explícita e confira `offset + comprimento <= byteLength` para cada região. Valide também o tipo de imagem e os tamanhos do cabeçalho e dos chunks.

No asset auditado, o limite lógico precisa cobrir pelo menos 128.987 bytes. Os 73.244 bytes que a versão original declarava cobriam a geometria anterior à imagem. Para validar o normalizador, abra explicitamente `CAMINHO_SAIDA_GLTF`, pois `resolve_model()` dá preferência a um `.glb` existente. Quando o GLB for derivado, regenere-o a partir do novo glTF.

### Índices e transforms

O índice de um nó é sua posição no array original do glTF. A travessia da cena pode visitar a raiz de índice 1 antes do filho de índice 0. Em `Model.node(index)`, use o índice original e defina o resultado para nós que não pertencem à cena carregada. Ao alterar pivôs, compare a transformação de mundo das malhas antes e depois, identificando cada instância pelo nó. Um mesmo mesh pode aparecer em mais de um nó. Ao comparar a FK pura com o Panda, use o grafo e pontos locais conhecidos, incluindo profundidade e os dois lados do corpo.

## 3. Perfil e inicialização

No Pydantic Settings, argumentos passados ao construtor prevalecem sobre variáveis de ambiente por padrão. Por isso, `Settings(**dados_do_toml)` faz a escala 1,2 do arquivo prevalecer sobre 1,5 no ambiente. Escolha a ordem explícita antes de mexer na API. Se o contrato for ambiente acima de TOML, coloque a fonte de ambiente antes da fonte que fornece os valores do arquivo. Confira a mesclagem de campos aninhados para que trocar a escala não descarte o restante de `window`.

Separe três casos na leitura: arquivo ausente, TOML inválido e TOML válido com campos incompatíveis com o schema. Um erro como `window.scale = 0` deve produzir diagnóstico com o caminho do campo e permitir a recuperação definida pelo projeto. Preserve o conteúdo original até o usuário salvar uma configuração recuperada. Considere que a inicialização e a saída atualmente podem persistir a configuração de forma automática.

A gravação normal usa um temporário exclusivo no diretório de destino, seguido de substituição. Isso evita que um leitor veja o TOML pela metade e que dois escritores compartilhem o mesmo temporário. Dois salvamentos completos ainda podem se sobrepor; se a aplicação passar a gravar de vários processos, trate essa disputa separadamente. Para checagens de inicialização, forneça `SEJOGA_CONFIG_PATH` apontando para um arquivo exclusivo no temporário. Exercite perfil ausente, arquivo corrompido, valor fora da faixa, conflito com ambiente e falha de escrita no destino.

## 4. Animação e colisão

### Alvo, posição e continuidade

Uma mola tem posição e velocidade internas. Trocar seu alvo muda o movimento a partir dali. Reescrever a posição atual pula diretamente para o novo valor. Em `GiroCorpo`, o limite de perfil pertence à escolha do alvo. Ao sair de costas, a posição pode estar em −180° e o novo alvo em 0°. Deixe a mola percorrer a diferença. Se houver um limite físico absoluto, aplique-o separadamente do limite do comando e trate a velocidade ao bater no limite.

Use a mola analítica já existente quando o alvo é constante durante o passo. Compare amostras no mesmo instante em 30, 60 e 120 FPS com o mesmo alvo e estado inicial. Para alvo variável, alimente a mesma trajetória de referência e meça erro de amostragem. Para transições de pose, compare diferença de ângulo e de velocidade nos primeiros quadros, além da convergência final. Preserve os eixos locais e a convenção de espelhamento de cada junta.

### Dono da decisão e dono da pose

- **Porta.** O controlador anuncia a intenção de espiar. O diretor de tentáculos decide o ângulo da porta enquanto a coreografia estiver ativa. Uma animação independente, como o espirro ou a ejeção da caixa, pode tomar a porta. O próprio pedido de espiada não deve ser encaminhado como pedido externo de 85°. Exercite o ciclo completo pelo controlador e diretor, incluindo retirada antecipada.
- **Dança.** A chance pertence ao relógio de decisão por frase. Sorteio positivo abre uma janela de oito segundos. Sorteio negativo deixa a janela expirar. A prévia manual tem seu próprio relógio. Arraste, queda, fim da música e desativação da reação têm precedência conforme a regra do controlador. Use uma semente fixa e verifique que uma sequência com acertos e erros produz entrada e saída.
- **Sono.** A interação que vira `wake` precisa liberar a trava manual no mesmo fluxo. Exercite sono automático e os modos manuais, incluindo arraste, clique e o comando explícito de acordar.
- **Cápsula.** Calcule o ponto mais próximo sobre o segmento. Se o vetor radial tem comprimento positivo, use-o para projetar o ponto até o raio mais a folga. Se ele é zero e o segmento tem comprimento, escolha um eixo cartesiano pouco alinhado e normalize seu produto vetorial com o eixo da cápsula. Se o segmento degenerou em um ponto, a cápsula se comporta como esfera. Valide a distância ao segmento depois da correção.

## 5. Overlay, entrada e validação

O Pymunk usa pixels absolutos do desktop. O Panda usa coordenadas locais à janela e projeta o modelo pela lente. Ao aumentar a janela de 480 para 960 px, preservar a escala aparente exige aumentar o filme da lente na mesma proporção e compensar a origem e a posição local. A margem de projeção deve ser aplicada uma vez. Para o arraste pelo pé, o mínimo de dois degraus pertence ao tamanho escolhido. Aplicá-lo à extensão antes da margem transforma o mínimo de 960 px em 1.440 px.

`requestProperties()` enfileira a alteração. Confira o tamanho e a posição efetivos nos quadros seguintes antes de concluir que o HWND e a lente estão alinhados. Use a posição da pega projetada em coordenadas de tela e compare com o cursor durante ida, inversão e soltura. Em DPI misto, valide as conversões com janelas em monitores de escalas diferentes, inclusive com origem negativa. Se configurar a política de DPI por API, faça-o antes de criar o primeiro HWND.

A transparência do Windows usa uma cor exata. O shader decide o fundo pela cobertura e o framebuffer passa pelo tonemap antes de chegar ao color key. Para trocar a cor em execução, alinhe clear, shader e chave final. Meça a chave em pixels de fundo conhecidos depois de o novo quadro aparecer. A classificação atual por canais altos e baixos foi calibrada para magenta forte. Cores intermediárias precisam de uma estratégia que preserve o reconhecimento depois do tonemap. Se a aplicação ao vivo não fizer parte da correção imediata, mostre a necessidade de reinício ao salvar.

| Checagem | Evidência esperada |
| --- | --- |
| `python tools/smoke_mouse.py` | Picking, transparência e fluxo de gesto com polling controlado |
| `python tools/smoke_mouse.py --physics` | Integração de gesto, Pymunk e posição real da janela |
| `python tools/smoke_corpo_nativo.py` | Entrada nativa, deslocamento, inversão e soltura. O script movimenta o cursor |
| `./build.ps1` e execução do bundle recém-gerado | Inicialização, logs, render e saída com perfil isolado |
| Captura em GPU | Franja do contorno, cores intermediárias, perfis, costas, janela em expansão e coreografia da porta |

Mantenha o filtro de PATH do build para evitar que o PyInstaller empacote a ICU incompatível. No arraste com Pymunk 7, restaure massa e momento após voltar de cinemático para dinâmico e antes de avançar o espaço. Teste encerramento enquanto a física ou a entrada ainda têm tarefas agendadas.

## Referências consultadas

Os detalhes usados no projeto estão descritos acima. A identificação das referências permite conferir a origem sem depender de navegação para aplicar o guia.

- Microsoft Learn, documentação de `ShellExecute`, controle de conta de usuário e configuração de DPI do processo.
- Khronos Group, glTF 2.0, armazenamento binário, imagens, nós e estrutura GLB.
- GitHub Docs, uso seguro de entradas em scripts do Actions.
- Pydantic Settings, precedência e personalização das fontes de configuração.
- Panda3D 1.10, referência de `GraphicsWindow` e suporte a mouse.
- Pymunk, referência de `Body` e `Space`. A restauração de massa e momento vem da reprodução registrada no projeto.
- Ryan Juckett, *Damped Springs*, solução analítica para molas amortecidas.
