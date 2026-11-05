# Revisão do guia de dança — 05/11/2026

Referência revisada: `GUIA_ANIMACAO_DANCA.md` (versão 1.0). Este parecer complementa o texto original sem substituir a direção artística do autor.

**Retificação posterior:** a descrição completa do autor substituiu a interpretação de apoio pela mão esquerda. A versão 2.0 de `GUIA_ANIMACAO_DANCA.md` é a direção atual: caixa maior que o mascote nos dois eixos, costas apoiadas, braços cruzados e staging lateral. As observações abaixo sobre a versão 1.0 são históricas.

## Direção artística

O guia já define uma base utilizável: postura relaxada com apoio, braços cruzados, headbang concentrado no pescoço e uma frase de breakdance com preparação, chão e recuperação. O próximo ganho depende de poses e apoios legíveis, não de acrescentar mais oscilação senoidal.

Para o refinamento, cada estilo deve ter uma frase com silhuetas distinguíveis:

- Head nod musical: a interpretação inicial de apoio do braço esquerdo foi corrigida pelo autor. Usar costas apoiadas na caixa gigante, ambos os braços cruzados e pernas estáveis, conforme o guia 2.0.
- Hip hop: flexão de joelhos → transferência de peso → contrapeso dos braços → pausa. Não deve parecer caminhada no lugar nem apenas giro do quadril.
- Rock: base firme, tronco acompanhando a contração para baixo, mão 🤘 legível e recuperação mais lenta do pescoço.
- Breakdance: toprock → preparação de apoio → descida → pose de chão legível → giro/footwork → freeze → subida. O contato da mão precisa ser conferido, não apenas o ângulo global do personagem.

## Divergências entre texto e código atual

| Trecho do guia | Situação nesta revisão |
|---|---|
| Dedos não articulados | Há pivôs individuais no runtime para a mão direita e gesto de rock; ainda não é um rig com falanges completas. |
| `floor_spin` apenas calculado | O renderer já aplica a rotação global da frase de chão. O apoio ainda é aproximado. |
| Pernas estáticas | `leg_motion.py` já usa fase compartilhada; pivôs explícitos de quadril/joelho estão na revisão em andamento. |
| IK como integração futura | Existe solver planar para o braço apoiado na caixa. A assinatura real é `solve_arm(horizontal, downward, upper_length, forearm_length)`. |
| Porta limitada a 48° durante dança | A ejeção da caixa e os tentáculos são camadas independentes e precisam de abertura maior. O corpo continua dançando. |
| `tools/capture_dance_animation.py` | Esse arquivo ainda não existe. Usar `tools/preview_body_actions.py music-soft music-hiphop music-heavy`, `tools/profile_music_styles.py` e `tools/smoke_bundle_dances.py`. |
| `python -m sejoga --log-level DEBUG` | Essa opção não existe no CLI atual. Não documentar como comando válido. |
| Logs de troca de estilo apresentados como exemplo real | São exemplos de formato; ainda não são mensagens emitidas pelo código atual. |

## Precisões de ritmo e interpolação

- `u*u*(3-2*u)` é smoothstep cúbico, com velocidade zero nas duas extremidades; não é ease-out cúbico. Os arcos implementados usam seno, não uma parábola balística.
- `1-exp(-dt*7)` usa uma constante de tempo de aproximadamente 0,143 s. Não significa sete frames: alcança cerca de 63% em 0,143 s, 90% em 0,329 s e 95% em 0,428 s.
- Uma correção de fase de 25% por batida deixa aproximadamente 31,6% do erro inicial após quatro batidas. Portanto, não há convergência completa em quatro batidas.
- O pulso `sin(local/.42*pi)^2` atinge o máximo em `local=.21`, depois do início da batida. Precisamos escolher se o alvo é começar o gesto no onset ou chegar ao máximo nele; são timings diferentes, ainda afetados pelo filtro de pose e pela latência da captura.
- Os limites de quatro batidas são uma grade estimada. O sistema não identifica o primeiro tempo de um compasso musical real.

## Referências

A página [Breakdance Animation Splinning, de Kotey Annan](https://dannan.artstation.com/projects/9EVZlo) é uma referência principal útil para estudo: o autor discute legibilidade dos membros em movimentos rápidos e sincronização dos fones com a bateria. O texto identifica o b-boy usado como referência de performance. Não foi feita análise frame a frame do vídeo nesta revisão.

Imagens de poses, modelos de caixa e bancos de sprites ajudam na silhueta e no design, mas não bastam para definir timing e apoio. Para movimentos ainda ambíguos, o ideal é selecionar um trecho curto de vídeo e marcar preparação, contato, acento e recuperação.

Os ranges de BPM devem permanecer como heurísticas de seleção, com escolha manual disponível. Não devem ser apresentados como identificação confiável de gênero.

A própria [Ableton, em Tempo and genre](https://learningmusic.ableton.com/make-beats/tempo-and-genre.html), relaciona gênero também aos sons e padrões, além do andamento. A página apresenta hip hop em 60–100 BPM e house em 115–130 BPM como faixas típicas; não valida por si só todos os ranges e limiares de energia da tabela do guia.

## Evidência e pendências

Os valores de hardware/CPU apresentados na seção 12.1 não têm relatório anexado que os comprove. As medições desta sessão estão em `tools/profile_music_styles.py`: medem o loop de animação/render, incluindo trechos com tentáculos, e não apenas `DanceMotion.update`.

Faltam congelamento musical explícito, alternância bilateral do gesto de rock e polimento dos apoios. Trilhas/partículas e som de pouso são secundários à coreografia. O fluxo de camadas deve ser preservado: porta e tentáculos não substituem a dança.
