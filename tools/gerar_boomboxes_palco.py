"""Acrescenta relevo aos falantes do palco original exportado do Blockbench."""

from __future__ import annotations

import base64
import json
import math
import struct
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ORIGINAL = RAIZ / "assets/assets/boomboxgrande/Palco.original.gltf"
SAIDA_GLTF = RAIZ / "assets/model/Boomboxes.gltf"


class _Relevo:
    """Adiciona faces planas ao mesmo buffer das caixas texturizadas."""

    def __init__(self, palco: dict):
        self.palco = palco
        uri = palco["buffers"][0]["uri"]
        self.dados = bytearray(base64.b64decode(uri.split(",", 1)[1]))

    def material(self, nome, cor, tile):
        materiais = self.palco["materials"]
        materiais.append(
            {
                "name": nome,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [*cor, 1],
                    "metallicFactor": 0,
                    "roughnessFactor": 0.92,
                },
            }
        )
        nome_tex = f"pixel-{tile}"
        texturas = self.palco["textures"]
        idx = next((i for i, tex in enumerate(texturas) if tex.get("name") == nome_tex), None)
        if idx is None:
            png = (RAIZ / "assets/textures/acabamentos" / f"{tile}.png").read_bytes()
            imagens = self.palco["images"]
            imagens.append({"name": nome_tex, "mimeType": "image/png",
                            "uri": "data:image/png;base64," + base64.b64encode(png).decode("ascii")})
            idx = len(texturas)
            texturas.append({"name": nome_tex, "sampler": 0, "source": len(imagens)-1})
        materiais[-1]["pbrMetallicRoughness"]["baseColorTexture"] = {"index": idx}
        return len(materiais) - 1

    def vetores(self, valores, limites=False):
        self.dados.extend(b"\0" * (-len(self.dados) % 4))
        inicio = len(self.dados)
        dimensao = len(valores[0])
        for valor in valores:
            self.dados.extend(struct.pack(f"<{dimensao}f", *valor))
        vistas = self.palco["bufferViews"]
        vistas.append(
            {
                "buffer": 0,
                "byteOffset": inicio,
                "byteLength": len(self.dados) - inicio,
                "target": 34962,
            }
        )
        acesso = {
            "bufferView": len(vistas) - 1,
            "componentType": 5126,
            "type": f"VEC{dimensao}",
            "count": len(valores),
        }
        if limites:
            acesso.update(
                min=list(map(min, zip(*valores, strict=True))),
                max=list(map(max, zip(*valores, strict=True))),
            )
        acessos = self.palco["accessors"]
        acessos.append(acesso)
        return len(acessos) - 1

    def malha(self, nome, faces, material):
        posicoes, normais = [], []
        for face in faces:
            a, b, c = face[:3]
            u = [y - x for x, y in zip(a, b, strict=True)]
            v = [y - x for x, y in zip(a, c, strict=True)]
            cruz = [
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            ]
            norma = math.hypot(*cruz)
            normal = [n / norma for n in cruz]
            for i in range(1, len(face) - 1):
                posicoes.extend((a, face[i], face[i + 1]))
                normais.extend((normal,) * 3)
        atributos = {
            "POSITION": self.vetores(posicoes, True),
            "NORMAL": self.vetores(normais),
        }
        # Projeção frontal contínua sobre a membrana, com a luz pintada no quadrante superior.
        rx = max(abs(v[0]) for v in posicoes)
        ry = max(abs(v[1]) for v in posicoes)
        atributos["TEXCOORD_0"] = self.vetores([(.5+.48*x/rx, .5-.48*y/ry) for x,y,_ in posicoes])
        malhas = self.palco["meshes"]
        malhas.append(
            {
                "name": nome,
                "primitives": [{"attributes": atributos, "material": material}],
            }
        )
        return len(malhas) - 1

    def instalar(self, caixa, nome, malha, posicao):
        nos = self.palco["nodes"]
        caixa.setdefault("children", []).append(len(nos))
        nos.append({"name": nome, "mesh": malha, "translation": list(posicao)})

    def finalizar(self):
        self.palco["buffers"][0] = {
            "uri": "data:application/octet-stream;base64,"
            + base64.b64encode(self.dados).decode("ascii"),
            "byteLength": len(self.dados),
        }


def _oitavado(rx, ry, escala, z):
    # Frente do GLTF em -Z. As quinas seguem os degraus do desenho de pixels.
    return [
        (rx * x * escala, ry * y * escala, z)
        for x, y in (
            (-0.76, 1),
            (0.76, 1),
            (1, 0.56),
            (1, -0.56),
            (0.76, -1),
            (-0.76, -1),
            (-1, -0.56),
            (-1, 0.56),
        )
    ]


def _faixa(externo, interno):
    return [
        (externo[i - 1], externo[i], interno[i], interno[i - 1])
        for i in range(len(externo))
    ]


def _malhas_falante(relevo, rx, ry, expoente, grafite, cone, calota):
    # A superelipse dá cantos suaves ao falante largo. Nas laterais vira uma elipse.
    contorno = []
    for i in range(16):
        angulo = -math.tau * i / 16
        x, y = math.cos(angulo), math.sin(angulo)
        contorno.append(
            (
                rx * math.copysign(abs(x) ** expoente, x),
                ry * math.copysign(abs(y) ** expoente, y),
            )
        )

    def perfil(escala, z):
        return [(x * escala, y * escala, z) for x, y in contorno]

    borda = perfil(1, -0.006)
    crista = perfil(0.96, -0.023)
    boca = perfil(0.92, -0.017)
    centro = perfil(0.43, -0.007)
    tampa = perfil(0.35, -0.020)
    aro_id = relevo.malha(
        "Borda do falante", _faixa(borda, crista) + _faixa(crista, boca), grafite
    )
    cone_id = relevo.malha("Membrana", _faixa(boca, centro), cone)
    calota_id = relevo.malha(
        "Centro do falante", [*_faixa(centro, tampa), tampa], calota
    )
    return aro_id, cone_id, calota_id


def gerar_gltf(destino: Path = SAIDA_GLTF) -> dict:
    """Gera o palco do jogo a partir da montagem original do Blockbench."""
    palco = json.loads(ORIGINAL.read_bytes())
    for material in palco["materials"]:
        material["pbrMetallicRoughness"]["baseColorFactor"] = [0.60, 0.56, 0.65, 1]
    relevo = _Relevo(palco)
    grafite = relevo.material("Suspensão de borracha", (0.038, 0.033, 0.048), "membrana")
    cone = relevo.material("Cone de papel", (0.057, 0.043, 0.061), "membrana")
    calota = relevo.material("Calota fosca", (0.026, 0.017, 0.030), "membrana")
    ambar = relevo.material("Luz piloto âmbar", (0.45, 0.25, 0.12), "sintonia")
    principal = _malhas_falante(relevo, 0.65, 0.32, 0.6, grafite, cone, calota)
    lateral = _malhas_falante(relevo, 0.244, 0.215, 1.0, grafite, cone, calota)
    for indice in palco["scenes"][palco["scene"]]["nodes"]:
        caixa = palco["nodes"][indice]
        nome = caixa["name"].split()[-1]
        central = nome == "meio"
        frente = -0.9375 if central else -0.3125
        aro_id, cone_id, calota_id = principal if central else lateral
        alturas = (0.385, 1.255) if central else (0.235, 0.765)
        for i, altura in enumerate(alturas):
            pos = (0, altura, frente)
            relevo.instalar(caixa, f"Borda_{nome}_{i}", aro_id, pos)
            relevo.instalar(caixa, f"Cone_{nome}_{i}", cone_id, pos)
            relevo.instalar(caixa, f"Calota_{nome}_{i}", calota_id, pos)
        if central:
            indicador = relevo.malha(
                "Piloto", [_oitavado(0.029, 0.011, 1, -0.002)], ambar
            )
            relevo.instalar(caixa, "Piloto", indicador, (0.668, 0.842, frente))

    relevo.finalizar()
    palco["asset"]["generator"] = "SeJogaDesktopCompanion-fnf-stage-speakers"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(palco, indent=2), encoding="utf-8")
    return palco


if __name__ == "__main__":
    gerar_gltf()
