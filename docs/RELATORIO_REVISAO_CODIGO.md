# Revisão técnica do SeJoga Desktop Companion

Base revisada `423f0f8`, branch `codex/refatoracao`. O cenário considerado é um companion por sessão Windows com atualização do runtime no escopo da máquina.

## Corrigir primeiro

1. **O ZIP de atualização omite modelos necessários para iniciar o app.** O renderer abre as duas caixas de som na inicialização e o empacotador exclui todos os arquivos .bbmodel. Gerei um ZIP com os dois arquivos de entrada e confirmei que ambos ficaram de fora. Inclua os dois modelos de runtime no pacote ou converta-os para um formato de distribuição e ajuste o carregador. [Empacotador](../tools/construir_atualizacao.py#L58) · [Inicialização](../src/sejoga/render/renderizador.py#L327) · [Carregador](../src/sejoga/musica/caixa_som.py#L143).
2. **A atualização pode parar antes do UAC.** Bandeja e configurações tentam gravar `channel-info.json` em Program Files antes de iniciar o launcher. Simulei acesso negado e confirmei que a exceção escapa do tratamento. Passe o canal como argumento validado ao launcher e faça a gravação necessária no processo elevado. [Diálogo](../src/sejoga/distribuicao/dialogo_atualizacao.py#L122) · [UAC](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/).
3. **A interface oferece versões que o launcher recusa.** Reproduzi a comparação de `0.1.0` estável com `0.1.0.dev20261111000000`. A interface compara com o piso do nightly e o launcher compara com o estável instalado. Ambos precisam aplicar a mesma política de troca de canal e informar recusas. [Checagem](../src/sejoga/distribuicao/atualizador.py#L225) · [Launcher](../installer/SeJogaLauncher.cs#L381).
4. **O conversor gera um GLB inconsistente com o asset atual.** O buffer do Mário declara 73.244 bytes, mas a região da imagem termina no byte 128.987. O comprimento é registrado antes da imagem. Em uma entrada sintética, o conversor também rotulou uma URI JPEG como PNG. Calcule o comprimento após anexar as imagens e antes do padding final. Leia o MIME da URI. [Conversor](../tools/converter_gltf_para_glb.py#L76) · [Especificação Khronos](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#glb-stored-buffer).
5. **Uma preferência inválida impede o app de abrir.** Com `window.scale = 0` em TOML válido, confirmei que `ValidationError` interrompe a inicialização. Trate a validação do perfil, preservando o arquivo para diagnóstico e recuperando os valores válidos ou os defaults. [Carregamento](../src/sejoga/configuracao.py#L225).
6. **O pipeline insere nomes de tags no script PowerShell.** `github.ref_name` chega a `version` e `tag_versao`. A interpolação direta permite que aspas alterem a sintaxe de um job com escrita nas Releases. A exposição depende das permissões para criar tags. Passe os valores por `env` e valide o formato. [Workflow](../.github/workflows/_build-comum.yml#L83) · [GitHub Docs](https://docs.github.com/en/actions/concepts/security/script-injections).
7. **O lint impede a publicação no CI.** `python -m ruff check` encontrou 31 infrações neste snapshot. O workflow exige que o comando passe para empacotar e publicar. Corrija as infrações por módulo, separando funções por responsabilidade. [Gate do workflow](../.github/workflows/_build-comum.yml#L69).

## Runtime

8. **A espiada cancela a própria coreografia.** Na reprodução, o diretor passou de `empurrando` para `fechada` depois de receber o pedido de 85° gerado pela espiada. Deixe o diretor comandar a abertura nesse fluxo. [Controlador](../src/sejoga/animacao/controlador_animacao.py#L874) · [Diretor](../src/sejoga/tentaculos/sistema_tentaculos.py#L418).
9. **Voltar de costas para frente salta 90° em um quadro.** A 60 FPS, medi −180° e depois −90° na primeira atualização ao pedir frente. Limite o novo alvo e deixe a posição atingida voltar pela mola. [Giro](../src/sejoga/animacao/movimento_corpo.py#L163).
10. **A chance de dançar só influencia a entrada.** Cada quadro em dança renova pelo menos um segundo, inclusive quando o sorteio falha. Com chance de 35% e semente fixa, a dança seguia após 120 s. Deixe cada sorteio controlar a duração da frase. [Controlador](../src/sejoga/animacao/controlador_animacao.py#L482).
11. **O sono manual ignora a reação de despertar.** No modo sentado, o clique produziu `wake`, mas o bloqueio manteve `sleep`. Libere o bloqueio no evento que o app já reconhece como despertar. [Sono](../src/sejoga/animacao/controlador_animacao.py#L562).
12. **Arrastar pelo pé seleciona o maior tamanho mesmo quando dois degraus bastam.** Com base de 480 px, o mínimo de 960 px recebe margem e seleciona 1.440 px. Aplique o mínimo ao tamanho escolhido. Valide o enquadramento e a posição da pega no arraste real. [Janela](../src/sejoga/render/janela.py#L948) · [Envelope](../src/sejoga/render/envelope_janela.py#L79).
13. **O fio pode continuar dentro da cápsula de colisão.** Para a cápsula vertical entre `(0,0,0)` e `(0,0,2)`, o ponto `(0,0,1)` virou `(0,0,1.25)` e permaneceu sobre o eixo. Use uma saída perpendicular ao eixo quando a distância radial for zero. [Fio](../src/sejoga/animacao/fio_corda.py#L81).
14. **A cor de transparência é salva sem aplicação imediata ou indicação de reinício.** Clear e shader são configurados ao criar a janela. A calibração também rejeitou o pixel `(96,96,96)` para `#606060` numa checagem direta da regra de canais. Sinalize a necessidade de reinício ou reaplique clear, shader e calibração juntos. Verifique as cores intermediárias após o tonemap em GPU. [Aplicação](../src/sejoga/render/janela.py#L1556) · [Calibração](../src/sejoga/render/chroma_tuning.py#L91).
15. **Mudar o canal durante a busca pode levar ao feed errado.** As configurações capturam o canal ao iniciar a thread e leem o seletor de novo na conclusão. O resultado de um canal pode ser exibido como se pertencesse a outro. Vincule o resultado ao canal consultado e descarte-o se a seleção mudou. [Busca](../src/sejoga/desktop/interface.py#L477) · [Conclusão](../src/sejoga/desktop/interface.py#L497).
16. **O CI oferece loopback sem instalar sua dependência.** O workflow instala `music-analysis` e omite o extra `music-loopback`, que fornece `soundcard`. O coletor do PyInstaller precisa que a biblioteca esteja instalada. Inclua o extra no build ou sinalize a indisponibilidade daquela fonte. [CI](../.github/workflows/_build-comum.yml#L62) · [Worker](../src/sejoga/musica/escuta_musica.py#L222).

## Ferramentas e contratos

17. **`sejoga run` sai com código 2.** Executei o comando. Ele imprime a mensagem de que o runtime será implementado depois. Delegue ao ponto de entrada já usado pelo executável, com import tardio. [CLI](../src/sejoga/__main__.py#L105).
18. **O leitor glTF pode devolver o nó errado.** Em um glTF mínimo com raiz 1 e filho 0, `Model.node(0)` devolveu a raiz de índice 1. Consulte o campo `Node.index` ou mantenha um índice explícito. [Leitor](../src/sejoga/nucleo/modelo.py#L168).
19. **A ferramenta de atualizar o rig pode validar um modelo antigo.** Depois de gravar `mario.gltf`, o script chama um resolvedor que prefere `mario.glb`. Se houver um derivado antigo, o resumo pode descrever aquele arquivo. Valide o caminho de saída explícito e indique quando regenerar o derivado. [Normalizador](../tools/atualizar_rig_modelo.py#L304) · [Resolução](../src/sejoga/nucleo/recursos.py#L67).

## Redução de código e hierarquia

20. **Bandeja e configurações duplicam o fluxo de atualização.** As duas telas mantêm workers, confirmação, canal e handoff. Isso já duplicou a gravação sem elevação e criou comportamentos diferentes durante a busca. Compartilhe o fluxo de atualização e mantenha a apresentação em cada tela. [Bandeja](../src/sejoga/distribuicao/dialogo_atualizacao.py#L78) · [Configurações](../src/sejoga/desktop/interface.py#L461).

Há remoções locais de baixo risco em `setup_frozen_paths()`, sem chamadores, em `_transitioning`, escrito e nunca lido, e em duas variáveis sem uso e um ramo vazio. O agendamento de espiada no diretor fica inerte no runtime porque o renderer sempre passa `idle_time=0`; o controlador já agenda as espiadas. Preserve a sequência aleatória ao remover trabalho desse caminho.

`FlexibleRig` manipula o grafo Panda3D pelos objetos recebidos. Essa responsabilidade cabe junto à montagem dos nós e do contorno, na camada de render. O controlador também executa poses legadas de estados que já têm deltas. Antes de retirar esse trabalho por quadro, verifique quais juntas ainda dependem da pose legada.

## Evidência dos testes e próximos lotes

- O teste de atualização usa uma pasta temporária gravável e substitui `ShellExecute`. Cobre o handoff. A ACL de Program Files exige uma verificação própria. [Teste de atualização](../tests/test_dialogo_atualizacao.py#L29)
- O teste da porta exercita a máquina de fases diretamente. O conflito dos 85° aparece quando controlador e diretor participam do mesmo cenário. [Teste da porta](../tests/test_coreografia_porta.py#L49)
- O teste de giro recria parte do grafo. O caso de costas para frente merece uma verificação no caminho usado pelo renderer. [Teste de giro](../tests/test_giro_corpo_no.py#L46)
- O smoke de polling abre janela real com entrada simulada. O smoke nativo injeta eventos no mouse do Windows. [Polling](../tools/smoke_mouse.py#L42) · [Mouse nativo](../tools/smoke_corpo_nativo.py#L66)
- A guarda de camadas verifica imports diretos. Acoplamento via objetos de render passa por essa verificação, como no caso de `FlexibleRig`. [Guarda](../tests/test_camadas_puras.py#L34) · [Rig flexível](../src/sejoga/animacao/rig_flexivel.py#L42)

Comece pelos arquivos ausentes no ZIP e pelo handoff de atualização. Em seguida, trate publicação, GLB e recuperação de perfil, continuidade de movimento e conflitos de pose. Reduza a duplicação depois de caracterizar as diferenças entre os caminhos.

## Cobertura e limites

A varredura estática cobriu 179 arquivos de código e configuração, com 170 arquivos Python analisados por AST. A leitura manual rastreou os fluxos citados acima, incluindo entrada, física, animação, render, áudio, glTF, distribuição e ferramentas. A leitura manual de cada uma das 35.520 linhas do inventário permanece incompleta. Assets binários e tabelas autorais de pose ficaram fora da inspeção integral. Os testes ficaram intactos e as conclusões usam checagens independentes ou inspeção do código, conforme indicado em cada item. GPU, DPI misto e atualização elevada numa instalação real seguem sem validação nesta revisão.
