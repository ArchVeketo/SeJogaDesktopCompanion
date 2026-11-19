# Referência de animação do Skowt

O Skowt organiza o material por personagem, modelo e movimento. A amostra foi Genshin Impact para os intervalos de golpes e Zenless Zone Zero para a organização do catálogo. A análise dos movimentos usou os metadados públicos do visualizador. Eles mostram as janelas de apresentação, enquanto as transições internas e as regras de interrupção do jogo permanecem fora dos dados publicados.

| Referência | O que os metadados mostram |
| --- | --- |
| [Tartaglia](https://skowt.cc/a/TrDKbH0FL) | Dois clipes de ataque adjacentes, com intervalos de 0,0492–2,25 s e 2,0967–4,30 s. As janelas se sobrepõem em cerca de 154 ms. O dado, por si só, não determina a duração de um blend no jogo. |
| [Ronova](https://skowt.cc/a/QeBnBEiBw) | A mesma ação tem entradas distintas para aviso, ataque e um efeito tardio. O aviso começa em 0,2686 s, a entrada principal em 0,3845 s e o efeito tardio em 2,7176 s. As três janelas coexistem em parte do movimento. |
| [Jane](https://skowt.cc/a/LFx5qEVOH) e [Ellen](https://skowt.cc/a/C7sbRpSCm) | Cada personagem tem sua página de modelo, com arma e referências visuais catalogadas separadamente. |

## Aplicação ao Mário

- **Fone com problema.** A pose existente antecipa o estouro. Aos 3,90 s da cena, um clarão de 130 ms marca o impacto; duas ondas saem da concha em +45 e +140 ms. O recuo do corpo continua depois do primeiro clarão.
- **Argolas da antena.** O brilho e o deslocamento das argolas preparam o encontro. Aos 1,95 s, o clarão nasce nos pivôs das antenas. Pares de faíscas saem em +55 e +150 ms e descrevem arcos enquanto as argolas reaparecem.
- Os tempos são autorais. O gatilho de cada cena vem do controlador e o renderer compõe os efeitos no frame com os sprites do projeto. A mudança segue a divisão de responsabilidades do [Manual Unificado](MANUAL_UNIFICADO_MARIO.md).
