"""Coreografia tentáculos x porta (lógica pura, sem Panda3D, Qt ou Win32).

ABRIR: um tentáculo empurra a porta com a ponta; o ângulo da porta é função da
revelação desse tentáculo, então porta e contato andam juntos. Com a porta aberta
os outros saem de acordo com o temperamento (`SAIDA_POR_TEMPERAMENTO`).
FECHAR: todos entram esquecendo a porta aberta. Depois de um atraso, UM tentáculo
sai, puxa a porta rápido até quase fechar, solta e volta enquanto ela termina de fechar.

A máquina de fases só decide ângulos e eventos. Quem move a malha é o diretor.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sejoga.nucleo.rig import IdlePersonality

# --- Porta -------------------------------------------------------------------

#: Abaixo disso a porta conta como fechada (o idle deixa a porta entreaberta até 3°).
LIMIAR_PORTA_FECHADA_GRAUS = 5.0
#: Pedido de porta vindo do rig acima disso = outra animação é dona da porta.
LIMIAR_PEDIDO_EXTERNO_GRAUS = 5.0
#: Os tentáculos só aparecem com a porta acima deste ângulo.
LIMIAR_SAIDA_PORTA_GRAUS = 50.0

# --- Abrir: empurrão ---------------------------------------------------------

#: Revelação do empurrador em que a ponta encosta na porta e começa a abri-la.
REVELACAO_INICIO_CONTATO = 0.10
#: Revelação em que o empurrão termina; a porta chega ao ângulo do temperamento.
REVELACAO_FIM_EMPURRAO = 0.35

# --- Fechar: esquecimento e puxão -------------------------------------------

#: Tempo com a porta aberta e nenhum tentáculo fora, antes do puxador sair.
ATRASO_ESQUECIMENTO_S = 1.6
#: Tempo do puxador para alcançar a borda livre da porta.
TEMPO_ALCANCE_PUXAO_S = 0.7
#: Velocidade da porta enquanto puxada (rápida).
VELOCIDADE_PUXAO_GRAUS_S = 300.0
#: Ângulo em que o puxador solta a porta e começa a voltar.
ANGULO_SOLTAR_PUXAO_GRAUS = 18.0
#: Velocidade com que a porta termina de fechar depois de solta.
VELOCIDADE_FECHAR_FINAL_GRAUS_S = 40.0
#: Duração do puxador recolhendo (o fechamento final dura algo parecido).
VOLTA_PUXADOR_S = 0.5
#: Fração do comprimento que o puxador pode estender (como o estado curioso, porém maior).
ALCANCE_PUXADOR = 1.0
#: Mola e amortecedor do puxador: rápidos para a ponta acompanhar a porta.
MOLA_PUXADOR = 380.0
AMORTECEDOR_PUXADOR = 30.0
#: Tolerância para considerar a porta fechada ao terminar a coreografia.
TOLERANCIA_PORTA_FECHADA_GRAUS = 0.5


class FasePorta(StrEnum):
    FECHADA = "fechada"
    EMPURRANDO = "empurrando"
    ABERTA = "aberta"
    ESQUECIDA = "esquecida"
    ALCANCANDO = "alcancando"
    PUXANDO = "puxando"
    VOLTANDO = "voltando"


@dataclass(frozen=True, slots=True)
class SaidaTuning:
    """Como os tentáculos saem pela porta em um temperamento."""

    duracao_s: float            # tempo da revelação (e do empurrão: contato segue a revelação)
    escalonamento_s: float      # atraso entre um tentáculo e o próximo
    angulo_empurrao_graus: float  # porta ao fim do empurrão (maior = empurrão mais forte)


#: Calmo preserva a temporização anterior (1,8 s e 0,48 s). Ângulo > LIMIAR_SAIDA_PORTA_GRAUS.
SAIDA_CALMA = SaidaTuning(duracao_s=1.8, escalonamento_s=0.48, angulo_empurrao_graus=60.0)
SAIDA_CURIOSA = SaidaTuning(duracao_s=1.3, escalonamento_s=0.36, angulo_empurrao_graus=66.0)
SAIDA_AGITADA = SaidaTuning(duracao_s=0.55, escalonamento_s=0.12, angulo_empurrao_graus=85.0)
SAIDA_TIMIDA = SaidaTuning(duracao_s=2.6, escalonamento_s=0.70, angulo_empurrao_graus=55.0)
SAIDA_CONFIANTE = SaidaTuning(duracao_s=0.9, escalonamento_s=0.24, angulo_empurrao_graus=75.0)

#: Espirro = saída violenta levada ao extremo: revelação quase instantânea, porta já aberta pela rajada.
SAIDA_ESPIRRO = SaidaTuning(duracao_s=0.16, escalonamento_s=0.0, angulo_empurrao_graus=130.0)

SAIDA_POR_TEMPERAMENTO: dict[IdlePersonality, SaidaTuning] = {
    IdlePersonality.CALM: SAIDA_CALMA,
    IdlePersonality.CURIOUS: SAIDA_CURIOSA,
    IdlePersonality.PLAYFUL: SAIDA_AGITADA,
    IdlePersonality.SHY: SAIDA_TIMIDA,
    IdlePersonality.CONFIDENT: SAIDA_CONFIANTE,
    # Estilos herdam o temperamento mais próximo, como em SPRING_PARAMS.
    IdlePersonality.STREET: SAIDA_CALMA,
    IdlePersonality.FIGHTER: SAIDA_CONFIANTE,
    IdlePersonality.RHYTHM: SAIDA_CALMA,
    IdlePersonality.STYLISH: SAIDA_CURIOSA,
}


def angulo_empurrado(revelacao: float, angulo_final: float) -> float:
    """Ângulo da porta empurrada: 0 até o contato, `angulo_final` ao fim do empurrão."""
    x = (revelacao - REVELACAO_INICIO_CONTATO) / (REVELACAO_FIM_EMPURRAO - REVELACAO_INICIO_CONTATO)
    x = max(0.0, min(1.0, x))
    return angulo_final * x * x * (3.0 - 2.0 * x)


@dataclass(frozen=True, slots=True)
class Passo:
    """Resultado de um quadro: ângulo imposto à porta (None = porta livre) e eventos."""

    angulo_porta: float | None = None
    fim_empurrao: bool = False
    chamar_puxador: bool = False
    soltar_puxador: bool = False


@dataclass(slots=True)
class CoreografiaPorta:
    """Máquina de fases da coreografia. Estado mínimo: fase e tempo na fase."""

    fase: FasePorta = FasePorta.FECHADA
    tempo: float = 0.0

    def iniciar_empurrao(self) -> None:
        self._entrar(FasePorta.EMPURRANDO)

    def cancelar(self) -> None:
        self._entrar(FasePorta.FECHADA)

    def _entrar(self, fase: FasePorta) -> None:
        self.fase = fase
        self.tempo = 0.0

    def avancar(
        self,
        dt: float,
        *,
        revelacao_atuador: float,
        angulo_porta: float,
        ha_ativos: bool,
        angulo_empurrao: float,
    ) -> Passo:
        """Avança um quadro. `ha_ativos`: algum tentáculo fora do estado dormente."""
        self.tempo += dt
        fase = self.fase
        if fase is FasePorta.EMPURRANDO:
            if revelacao_atuador >= REVELACAO_FIM_EMPURRAO:
                self._entrar(FasePorta.ABERTA)
                return Passo(angulo_porta=angulo_empurrao, fim_empurrao=True)
            return Passo(angulo_porta=angulo_empurrado(revelacao_atuador, angulo_empurrao))
        if fase is FasePorta.ABERTA:
            if not ha_ativos:
                self._entrar(FasePorta.ESQUECIDA)
            return Passo()
        if fase is FasePorta.ESQUECIDA:
            if self.tempo >= ATRASO_ESQUECIMENTO_S:
                self._entrar(FasePorta.ALCANCANDO)
                return Passo(angulo_porta=angulo_porta, chamar_puxador=True)
            return Passo(angulo_porta=angulo_porta)
        if fase is FasePorta.ALCANCANDO:
            if self.tempo >= TEMPO_ALCANCE_PUXAO_S:
                self._entrar(FasePorta.PUXANDO)
            return Passo(angulo_porta=angulo_porta)
        if fase is FasePorta.PUXANDO:
            angulo = max(0.0, angulo_porta - VELOCIDADE_PUXAO_GRAUS_S * dt)
            if angulo <= ANGULO_SOLTAR_PUXAO_GRAUS:
                self._entrar(FasePorta.VOLTANDO)
                return Passo(angulo_porta=angulo, soltar_puxador=True)
            return Passo(angulo_porta=angulo)
        if fase is FasePorta.VOLTANDO:
            angulo = max(0.0, angulo_porta - VELOCIDADE_FECHAR_FINAL_GRAUS_S * dt)
            if not ha_ativos and angulo <= TOLERANCIA_PORTA_FECHADA_GRAUS:
                self._entrar(FasePorta.FECHADA)
                return Passo()
            return Passo(angulo_porta=angulo)
        return Passo()
