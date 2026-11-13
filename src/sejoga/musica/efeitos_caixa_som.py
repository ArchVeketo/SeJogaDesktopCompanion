"""Respingo pixelado nas quinas da caixa ao tocar o chão."""

from sejoga.render.sprites_efeitos import atlas_gosma, cartao_pixel, quadro_gosma


class SpeakerEffects:
    """Espalha a gosma pelas duas quinas inferiores e seca no chão."""

    def __init__(self, geometry):
        """Cria um respingo para cada quina voltada à câmera."""
        self.slime = []
        for _ in range(2):
            node = cartao_pixel(geometry, "speaker-splash", atlas_gosma())
            node.setColorScale(1.22, 0.64, 0.91, 1)
            node.hide()
            self.slime.append(node)

    def update(self, age):
        """Expande os respingos no impacto e troca pelos quadros de secagem."""
        for lado, node in zip((-1, 1), self.slime, strict=True):
            if not 0 <= age < 1.4:
                node.hide()
                continue
            node.show()
            espalha = min(1.0, age / 0.28)
            node.setPos(lado * (0.72 + 0.13 * espalha), 0.015, 0.12 - 0.05 * espalha)
            node.setScale(0.26 + 0.25 * espalha, 1, 0.28 - 0.10 * espalha)
            if age < 0.28:
                quadro_gosma(node, 0, min(3, int(age / 0.07)))
            else:
                quadro_gosma(node, 3, min(3, int((age - 0.28) / 0.28)))
