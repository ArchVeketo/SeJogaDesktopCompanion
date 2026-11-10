"""Constantes fixas da cinemática do braço, usadas por ``nucleo`` e ``animacao``.

Ficam em ``nucleo`` para que ``cinematica`` não importe ``animacao``;
``animacao/braco_tuning.py`` as reexporta para os consumidores de sempre.
"""

#: Torção fixa (graus, em P/``Rotation3.x``) do antebraço em relação ao braço.
#: O nó do braço tem o eixo longo em ±X; a dobradiça do cotovelo é o ROLL (R) do
#: antebraço, que, sem torção, gira em torno do eixo frente-trás e abre o
#: antebraço PARA OS LADOS (para dentro do tronco). Com 90° de torção a dobradiça
#: passa a ser lateral e o antebraço dobra para a FRENTE (flexão anatômica) para
#: qualquer elevação lateral do ombro. Os gestos continuam escrevendo deltas em
#: ``ant-arm.x`` em torno desta base (somada pelo renderer e pela FK).
TORCAO_BASE_ANTEBRACO_GRAUS = 90.0

#: Norma abaixo da qual um vetor é tratado como nulo (direção degenerada).
EPSILON_DEGENERADO = 1e-9
