# VFX de grafite do Mário

Oito folhas PNG RGBA. Use os quadros na ordem superior esquerdo, superior direito, inferior esquerdo e inferior direito. A posição do recorte em pixels é medida a partir do canto superior esquerdo.

| Folha | Tamanho de cada quadro | Direção visual |
| --- | --- | --- |
| `derrapagem.png` | 768 × 512 | Pincel seco rosa e roxo. O rastro abre à direita e parte do pé de apoio. Espelhe para inverter o deslocamento. |
| `estouro_fone.png` | 768 × 512 | Estêncil amarelo com spray rosa. O clarão sai à esquerda a partir da concha. |
| `choque_argolas.png` | 768 × 512 | Riscos amarelos, clarão angular e fragmentos rosa e amarelos. O sprite cobre uma antena e sai à direita. Espelhe para a outra. |
| `pouso.png` | 630 × 623 | Tinta creme e lascas de poeira que se abrem no chão a partir do centro. |
| `batida.png` | 768 × 512 | Ondas serrilhadas e notas carimbadas em ciano e verde-lima. |
| `gosma.png` | 768 × 512 | Tinta rosa com contorno roxo escuro. O jato sai à direita e se divide em gotas. |
| `susto.png` | 768 × 512 | Coroa amarela de estêncil que se desfaz em fragmentos. |
| `comemoracao.png` | 630 × 623 | Arco ascendente de recortes de tinta em ciano, amarelo, verde e roxo. |

Nas folhas de 1261 × 1247, use os primeiros 1260 × 1246 pixels. A última coluna e a última linha ficam fora da grade.

O ImageGen gerou as folhas a partir das pranchas do Mário. O pedido de geração usou as direções visuais da tabela em uma grade 2 × 2, com quatro etapas por efeito, transparência, margem entre quadros e tinta saturada com grão nas bordas. Os arquivos contêm apenas os efeitos, sem o personagem e sem rótulos.
