"""Vocabulário de ALVOS DE MÃO por gesto/estado (dados puros, sem engine).

Cada gesto declara ONDE o punho (origem do nó ``hand``) deve ficar, relativo ao
ombro, em eixos do mascote: ``x`` = direita, ``y`` = cima, ``z`` = frente (o
rosto). O solver (``arm_ik.braco_para``) converte isso nos ``Rotation3`` do
ombro e do cotovelo. Os eixos são os da FK do grafo de cena
(``nucleo.cinematica``, igual ao Panda em posição, ``test_cinematica_oraculo``);
``z > 0`` é de fato à frente do corpo no render.

COMO OS VALORES FORAM ESCOLHIDOS (medido, não chutado): cada alvo é o ponto livre
de atravessamento (``animacao.colisao_bracos``) mais próximo do alvo autoral
anterior, numa grade de 0.02 u (``python tools/oraculo_cena.py --sugerir``). A
tabela antes/depois está em ``.agents/tasks/frente3-animacao/recalibracao-gpu.md``.

Limite medido do asset SEM folga: nenhuma pose com o punho mais de 0.08 u abaixo do ombro é
livre. O antebraço pendurado entra no short (malha ``legs``, meia-largura 0.312,
mais larga que a camiseta) e a mão (0.33 u) chega aos pés. Por isso o repouso é
com os braços abertos e levemente baixados, e não colados ao corpo. Se o usuário
preferir braços encostando no short, a alavanca é
``colisao_bracos.FRACAO_NUCLEO_BRACO`` (C4/C6 do recalibracao-gpu.md).

Alcance do braço ≈ 0.281 (upper 0.125 + forearm 0.15625). Alvos fora são
clampados pelo solver sem gerar NaN.

FRONTEIRA: Python puro. Só ``dataclass``; nenhum import de engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from sejoga.animacao.braco_tuning import POLO_COTOVELO_ANATOMICO

Vec3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class AlvoBraco:
    """Alvo do punho (relativo ao ombro) + polo (para onde o cotovelo aponta)."""

    #: Posição-alvo do punho relativa ao ombro (x direita, y cima, z frente).
    alvo: Vec3
    #: Direção para onde o COTOVELO aponta (padrão anatômico: trás, baixo, fora).
    polo: Vec3 = POLO_COTOVELO_ANATOMICO

    def alvo_espelhado(self) -> Vec3:
        """Alvo com o X invertido (pose simétrica para o braço esquerdo)."""
        return (-self.alvo[0], self.alvo[1], self.alvo[2])


#: REPOUSO/idle: braços abertos e levemente baixados, mão um pouco à frente. É o
#: ponto livre mais baixo perto do repouso autoral (0.075, -0.265, 0.02).
ALVO_IDLE = AlvoBraco(alvo=(0.24, -0.14, 0.08))

#: WAVE/aceno: punho na altura do ombro, por fora da orelha, antebraço para cima.
#: O balanço e o giro do pulso entram como termos aditivos em ``rig.pose_flourish``.
ALVO_WAVE = AlvoBraco(alvo=(0.23, 0.075, 0.03))

#: DRAG/arraste: mão à frente e para fora, como quem se equilibra ao ser puxado.
ALVO_DRAG = AlvoBraco(alvo=(0.18, -0.04, 0.15))

#: STRETCH/alongamento: mão alta e à frente (ajuste de jaqueta).
ALVO_STRETCH = AlvoBraco(alvo=(0.12, 0.08, 0.18))

#: DANCE/dança: mão à frente e um pouco acima do ombro; o ``beat`` modula por cima.
ALVO_DANCE = AlvoBraco(alvo=(0.15, 0.08, 0.17))

#: SLEEP/sono: braços relaxados, mãos recolhidas à frente.
ALVO_SLEEP = AlvoBraco(alvo=(0.22, -0.10, 0.10))

#: THROWN/arremesso: mãos à frente e para fora, silhueta aérea legível.
ALVO_THROWN = AlvoBraco(alvo=(0.16, 0.02, 0.16))

#: INTERACTION/interação (base): mãos à frente, como quem reage ao cursor.
ALVO_INTERACTION = AlvoBraco(alvo=(0.15, -0.01, 0.16))

#: DRAG_PERNA: pego pela perna, os braços pendem o máximo que o corpo permite.
ALVO_DRAG_PERNA = AlvoBraco(alvo=(0.23, -0.14, 0.06))

#: FALL/queda: mãos abertas para fora (o flailing entra aditivo).
ALVO_FALL = AlvoBraco(alvo=(0.21, -0.02, 0.08))

#: Danças. Cruzar os braços sobre o peito é inviável sem atravessar o corpo
#: (medido: nenhum alvo com o punho além do ombro em direção ao centro fica
#: livre), então "cruzado" é o fallback documentado em DECISOES_ANIMACOES.md:
#: antebraços à frente do peito, mãos próximas, um braço mais à frente que o outro.
ALVO_CRUZADO_DIR = AlvoBraco(alvo=(0.08, 0.06, 0.22))
ALVO_CRUZADO_ESQ = AlvoBraco(alvo=(0.08, 0.06, 0.16))

#: Chifre do rock: o ponto livre mais alto e para fora (acima da cabeça fica
#: fora do alcance de 0.281 u, o ombro está 0.19 u abaixo do topo da cabeça).
ALVO_CHIFRE = AlvoBraco(alvo=(0.24, 0.08, 0.04))

#: Contrapeso do hip hop: braço quase estendido (cotovelo ~17 graus) para
#: frente-fora, na altura do ombro. Mais perto (0.20) dobrava o cotovelo 42 graus.
ALVO_CONTRAPESO = AlvoBraco(alvo=(0.22, 0.0, 0.17))

#: Apoio de chão do breakdance: mão baixa à frente e para fora (o roll do corpo
#: no renderer leva a mão ao chão).
ALVO_APOIO_CHAO = AlvoBraco(alvo=(0.22, -0.12, 0.12))


#: Registro por nome (facilita consumo e documentação).
ALVOS: dict[str, AlvoBraco] = {
    "idle": ALVO_IDLE,
    "wave": ALVO_WAVE,
    "drag": ALVO_DRAG,
    "drag_perna": ALVO_DRAG_PERNA,
    "stretch": ALVO_STRETCH,
    "dance": ALVO_DANCE,
    "sleep": ALVO_SLEEP,
    "thrown": ALVO_THROWN,
    "fall": ALVO_FALL,
    "interaction": ALVO_INTERACTION,
    "cruzado_dir": ALVO_CRUZADO_DIR,
    "cruzado_esq": ALVO_CRUZADO_ESQ,
    "chifre": ALVO_CHIFRE,
    "contrapeso": ALVO_CONTRAPESO,
    "apoio_chao": ALVO_APOIO_CHAO,
}

#: Alvos autorais anteriores (antes da medição de colisão), para o relatório.
ALVOS_AUTORAIS_ANTERIORES: dict[str, Vec3] = {
    "idle": (0.075, -0.265, 0.02),
    "wave": (0.11, 0.235, 0.03),
    "drag": (0.14, -0.08, 0.17),
    "drag_perna": (0.035, -0.272, 0.0),
    "stretch": (0.12, 0.18, 0.12),
    "dance": (0.15, 0.1, 0.15),
    "sleep": (0.05, -0.25, 0.08),
    "thrown": (0.16, 0.0, 0.16),
    "fall": (0.19, 0.03, 0.05),
    "interaction": (0.13, -0.02, 0.18),
}
