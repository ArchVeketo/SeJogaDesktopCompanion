"""Logo 3D animado com líquido realista e alternância da brand na inicialização."""

from __future__ import annotations

import math
import multiprocessing
import random
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageChops, ImageFilter
from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QApplication, QWidget

from sejoga.configuracao import default_config_path
from sejoga.nucleo.recursos import brand_dir

if TYPE_CHECKING:
    from sejoga.configuracao import Settings

_MARGEM_X = 8
_MARGEM_Y = 6
_PAD_W = 24
_PAD_H = 24


@dataclass(frozen=True, slots=True)
class PaletaLoading:
    """Paleta oficial da brand para o líquido 3D da tela de carregamento."""

    nome: str
    liquido: str
    topo: str
    fundo: str
    espuma: str
    borda_3d: str
    sombra: str


BRAND_PALETTES: tuple[PaletaLoading, ...] = (
    PaletaLoading(
        nome="lima",
        liquido="#A6EE1A",
        topo="#D8FF5E",
        fundo="#549100",
        espuma="#F4FFD1",
        borda_3d="#320A8C",
        sombra="#1A044E",
    ),
    PaletaLoading(
        nome="rosa",
        liquido="#EE1675",
        topo="#FF70AF",
        fundo="#940643",
        espuma="#FFD9EC",
        borda_3d="#2C0A82",
        sombra="#150447",
    ),
    PaletaLoading(
        nome="roxo",
        liquido="#7E2DF2",
        topo="#B984FF",
        fundo="#3E0D91",
        espuma="#EDE2FF",
        borda_3d="#B8F21D",
        sombra="#210554",
    ),
    PaletaLoading(
        nome="ciano",
        liquido="#16CEB9",
        topo="#75FFF0",
        fundo="#06756D",
        espuma="#DAFFFB",
        borda_3d="#2B146B",
        sombra="#0D2247",
    ),
    PaletaLoading(
        nome="azul",
        liquido="#3073F2",
        topo="#80B4FF",
        fundo="#123996",
        espuma="#E0EEFF",
        borda_3d="#1D0F52",
        sombra="#0B1845",
    ),
)


@dataclass(slots=True)
class _BolhaLiquido:
    """Bolha ascendente com oscilação lateral dentro das letras."""

    x: float
    y: float
    raio: float
    vel_y: float
    fase: float
    amp_x: float


def _escolher_proxima_paleta(state_dir: Path | None = None) -> PaletaLoading:
    """Alterna sequencialmente entre as cores oficiais da brand a cada abertura."""
    pasta = state_dir or default_config_path().parent
    arquivo = pasta / "loading-color.txt"
    indice = 0
    try:
        anterior = int(arquivo.read_text(encoding="utf-8").strip())
        indice = (anterior + 1) % len(BRAND_PALETTES)
    except (OSError, ValueError):
        indice = 0
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(str(indice), encoding="utf-8")
    except OSError:
        pass
    return BRAND_PALETTES[indice]


def _pil_alpha_para_qimage(alpha: Image.Image, cor: QColor, fator_alfa: float = 1.0) -> QImage:
    """Converte uma máscara em escala de cinza para ``QImage`` RGBA colorido."""
    a = alpha if fator_alfa >= 0.999 else alpha.point(lambda v: int(v * fator_alfa))
    rgba = Image.new("RGBA", a.size, (cor.red(), cor.green(), cor.blue(), 0))
    rgba.putalpha(a)
    dados = rgba.tobytes("raw", "RGBA")
    img = QImage(dados, a.width, a.height, a.width * 4, QImage.Format.Format_RGBA8888)
    return img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


def _misturar_cor(c0: QColor, c1: QColor, t: float) -> QColor:
    u = max(0.0, min(1.0, t))
    return QColor(
        round(c0.red() + (c1.red() - c0.red()) * u),
        round(c0.green() + (c1.green() - c0.green()) * u),
        round(c0.blue() + (c1.blue() - c0.blue()) * u),
    )


def _construir_extrusao_e_cavidade(
    mask_outer: Image.Image,
    mask_liq_a: Image.Image,
    paleta: PaletaLoading,
) -> tuple[QImage, QImage]:
    """Constrói a sombra/extrusão 3D sólida e a cavidade translúcida de vidro."""
    largura, altura = mask_outer.size
    cor_borda, cor_sombra = QColor(paleta.borda_3d), QColor(paleta.sombra)

    camada_extrusao = QImage(largura, altura, QImage.Format.Format_ARGB32_Premultiplied)
    camada_extrusao.fill(Qt.GlobalColor.transparent)
    p_ext = QPainter(camada_extrusao)
    sombra_blur = ImageChops.offset(mask_outer, 10, 11).filter(ImageFilter.GaussianBlur(4.2))
    p_ext.drawImage(0, 0, _pil_alpha_para_qimage(sombra_blur, QColor(8, 6, 18), 0.50))
    for i in range(9, 0, -1):
        fatia = ImageChops.offset(mask_outer, i, round(i * 1.1))
        p_ext.drawImage(0, 0, _pil_alpha_para_qimage(fatia, _misturar_cor(cor_borda, cor_sombra, i / 9.0), 0.96))
    p_ext.end()

    camada_cavidade = QImage(largura, altura, QImage.Format.Format_ARGB32_Premultiplied)
    camada_cavidade.fill(Qt.GlobalColor.transparent)
    p_cav = QPainter(camada_cavidade)
    p_cav.drawImage(0, 0, _pil_alpha_para_qimage(mask_liq_a, QColor(12, 14, 28), 0.36))
    bisel_int = ImageChops.subtract(mask_liq_a, ImageChops.offset(mask_liq_a, 3, 3))
    p_cav.drawImage(0, 0, _pil_alpha_para_qimage(bisel_int, QColor(0, 0, 0), 0.42))
    p_cav.end()
    return camada_extrusao, camada_cavidade


def _construir_borda_e_vidro(
    mask_inner: Image.Image,
    mask_rim_a: Image.Image,
    paleta: PaletaLoading,
) -> tuple[QImage, QImage]:
    """Constrói a borda 3D chanfrada e o reflexo especular diagonal do vidro."""
    largura, altura = mask_inner.size
    cor_borda = QColor(paleta.borda_3d)

    camada_borda = QImage(largura, altura, QImage.Format.Format_ARGB32_Premultiplied)
    camada_borda.fill(Qt.GlobalColor.transparent)
    p_brd = QPainter(camada_borda)
    p_brd.drawImage(0, 0, _pil_alpha_para_qimage(mask_rim_a, cor_borda, 1.0))
    rim_luz = ImageChops.subtract(mask_rim_a, ImageChops.offset(mask_rim_a, 2, 2))
    p_brd.drawImage(0, 0, _pil_alpha_para_qimage(rim_luz, cor_borda.lighter(155), 0.65))
    p_brd.end()

    camada_vidro = QImage(largura, altura, QImage.Format.Format_ARGB32_Premultiplied)
    camada_vidro.fill(Qt.GlobalColor.transparent)
    p_vid = QPainter(camada_vidro)
    p_vid.setRenderHint(QPainter.RenderHint.Antialiasing)
    brilho_sup = ImageChops.subtract(mask_inner, ImageChops.offset(mask_inner, 0, 2))
    p_vid.drawImage(0, 0, _pil_alpha_para_qimage(brilho_sup, QColor(255, 255, 255), 0.48))
    for x0, x1 in ((0.14, 0.32), (0.56, 0.64)):
        faixa = QPainterPath()
        faixa.moveTo(largura * x0, 0.0)
        faixa.lineTo(largura * x1, 0.0)
        faixa.lineTo(largura * (x1 - 0.22), altura)
        faixa.lineTo(largura * (x0 - 0.20), altura)
        faixa.closeSubpath()
        p_vid.fillPath(faixa, QColor(255, 255, 255, 34 if x0 < 0.3 else 22))
    p_vid.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    p_vid.drawImage(0, 0, _pil_alpha_para_qimage(mask_inner, QColor(255, 255, 255), 1.0))
    p_vid.end()
    return camada_borda, camada_vidro


def _preparar_camadas_3d(
    mascara_path: Path, paleta: PaletaLoading
) -> tuple[tuple[int, int], QImage, QImage, QImage, QImage, QImage]:
    """Pré-computa extrusão 3D, cavidade de vidro, borda chanfrada e reflexo."""
    bruto = Image.open(mascara_path).convert("RGBA")
    largura, altura = bruto.width + _PAD_W, bruto.height + _PAD_H
    canvas_a = Image.new("L", (largura, altura), 0)
    canvas_a.paste(bruto.getchannel("A"), (_MARGEM_X, _MARGEM_Y))

    mask_outer = canvas_a.point(lambda v: 255 if v >= 28 else 0)
    mask_inner = canvas_a.point(lambda v: 255 if v >= 200 else 0)
    mask_liq_a = mask_inner.filter(ImageFilter.MaxFilter(3))
    mask_rim_a = ImageChops.subtract(mask_outer, mask_inner)

    camada_extrusao, camada_cavidade = _construir_extrusao_e_cavidade(mask_outer, mask_liq_a, paleta)
    camada_borda, camada_vidro = _construir_borda_e_vidro(mask_inner, mask_rim_a, paleta)
    mascara_liq_q = _pil_alpha_para_qimage(mask_liq_a, QColor(255, 255, 255), 1.0)
    return (
        (largura, altura),
        camada_extrusao,
        camada_cavidade,
        camada_borda,
        camada_vidro,
        mascara_liq_q,
    )


class LoadingSplash(QWidget):
    """Exibe o logo 3D enchendo com líquido realista nas cores oficiais da brand."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        paleta: PaletaLoading | None = None,
        state_dir: Path | None = None,
    ) -> None:
        """Inicializa o splash transparente com a próxima paleta da brand."""
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._paleta = paleta or _escolher_proxima_paleta(state_dir)
        self._cor = QColor(self._paleta.liquido)
        mascara_path = brand_dir() / "loading" / "banner-mask.png"
        (
            (largura, altura),
            self._camada_extrusao,
            self._camada_cavidade,
            self._camada_borda,
            self._camada_vidro,
            self._mascara_liquido,
        ) = _preparar_camadas_3d(mascara_path, self._paleta)

        self._nivel_alvo = 0.0
        self._nivel = 0.0
        self._vel_nivel = 0.0
        self._slosh_fase = 0.0
        self._ultimo_t = time.monotonic()
        self._rng = random.Random()
        self._bolhas: list[_BolhaLiquido] = self._criar_bolhas(largura, altura)
        self._estouros: list[list[float]] = []

        self.setFixedSize(largura, altura)
        self._posicionar(settings)

    def _criar_bolhas(self, largura: int, altura: int) -> list[_BolhaLiquido]:
        return [
            _BolhaLiquido(
                x=self._rng.uniform(_MARGEM_X + 12, largura - _PAD_W + _MARGEM_X - 8),
                y=self._rng.uniform(altura * 0.25, altura - _MARGEM_Y),
                raio=self._rng.uniform(1.4, 4.4),
                vel_y=self._rng.uniform(26.0, 62.0),
                fase=self._rng.uniform(0.0, math.tau),
                amp_x=self._rng.uniform(1.6, 4.2),
            )
            for _ in range(38)
        ]

    def atualizar(self, progresso: float) -> None:
        """Atualiza o nível desejado do líquido (``0.0`` a ``1.0``)."""
        self._nivel_alvo = max(0.0, min(1.0, float(progresso)))
        self._avancar_simulacao()
        self.update()

    def _avancar_simulacao(self) -> None:
        agora = time.monotonic()
        dt = max(0.004, min(0.06, agora - self._ultimo_t))
        self._ultimo_t = agora

        dif = self._nivel_alvo - self._nivel
        if abs(dif) > 0.35 or (self._nivel_alvo >= 0.999 and self._nivel == 0.0):
            self._nivel = self._nivel_alvo
            self._vel_nivel = max(self._vel_nivel, abs(dif) * 3.0)
        else:
            taxa = 18.0 if self._nivel_alvo >= 0.98 else 10.5
            passo = min(1.0, dt * taxa)
            nivel_ant = self._nivel
            self._nivel += dif * passo
            if self._nivel_alvo >= 0.999 and self._nivel > 0.985:
                self._nivel = 1.0
            self._vel_nivel = max(
                self._vel_nivel * math.exp(-dt * 4.5),
                abs(self._nivel - nivel_ant) / dt,
            )
        self._slosh_fase += dt * (4.8 + min(6.0, self._vel_nivel * 5.0))
        self._atualizar_bolhas(dt)

    def _atualizar_bolhas(self, dt: float) -> None:
        largura, altura = self.width(), self.height()
        superficie = self._altura_superficie()
        for bolha in self._bolhas:
            bolha.y -= bolha.vel_y * dt
            bolha.fase += dt * 4.2
            if bolha.y <= superficie + 2.0 and self._nivel > 0.06:
                if self._nivel < 0.98 and len(self._estouros) < 12:
                    self._estouros.append([bolha.x, superficie, bolha.raio, 0.0])
                bolha.x = self._rng.uniform(_MARGEM_X + 12, largura - _PAD_W + _MARGEM_X - 8)
                bolha.y = altura - _MARGEM_Y - self._rng.uniform(2.0, 18.0)
                bolha.raio = self._rng.uniform(1.4, 4.4)
            elif bolha.y < _MARGEM_Y:
                bolha.y = altura - _MARGEM_Y - 4.0

        ativos: list[list[float]] = []
        for est in self._estouros:
            est[3] += dt * 4.2
            if est[3] < 1.0:
                ativos.append(est)
        self._estouros = ativos

    def _altura_superficie(self) -> float:
        base_y = self.height() - _MARGEM_Y + 4.0
        topo_y = _MARGEM_Y - 6.0
        return base_y - (base_y - topo_y) * self._nivel

    def _onda_y(self, x: float, superficie: float, fase: float, amp: float) -> float:
        slosh = ((x / max(1, self.width())) - 0.5) * math.sin(self._slosh_fase * 0.7) * min(9.0, self._vel_nivel * 7.0)
        return superficie + slosh + amp * (
            math.sin(x * 0.032 + fase)
            + 0.52 * math.sin(x * 0.071 - fase * 0.68)
            + 0.24 * math.cos(x * 0.120 + fase * 1.35)
        )

    def _caminho_onda(self, superficie: float, fase: float, amp: float) -> QPainterPath:
        largura, altura = self.width(), self.height()
        caminho = QPainterPath(QPointF(0.0, self._onda_y(0.0, superficie, fase, amp)))
        for x in range(4, largura + 1, 4):
            caminho.lineTo(x, self._onda_y(float(x), superficie, fase, amp))
        caminho.lineTo(float(largura), float(altura))
        caminho.lineTo(0.0, float(altura))
        caminho.closeSubpath()
        return caminho

    def _desenhar_liquido(self, p: QPainter, superficie: float, amp: float) -> None:
        largura, altura = self.width(), self.height()
        t = time.monotonic() * 4.8

        # Menisco traseiro (profundidade 3D dentro da letra).
        cam_tras = self._caminho_onda(superficie - 4.5, t + 1.45, amp * 0.85)
        cor_tras = _misturar_cor(QColor(self._paleta.liquido), QColor(self._paleta.fundo), 0.58)
        p.fillPath(cam_tras, cor_tras)

        # Corpo líquido frontal com gradiente de profundidade e cáusticas suaves.
        cam_frente = self._caminho_onda(superficie, t, amp)
        grad = QLinearGradient(0.0, max(0.0, superficie), 0.0, float(altura))
        grad.setColorAt(0.0, QColor(self._paleta.topo))
        grad.setColorAt(0.22, QColor(self._paleta.liquido))
        grad.setColorAt(1.0, QColor(self._paleta.fundo))
        p.setClipPath(cam_frente)
        p.fillRect(self.rect(), grad)

        caustica = QColor(self._paleta.topo)
        caustica.setAlpha(46)
        p.setBrush(caustica)
        p.setPen(Qt.PenStyle.NoPen)
        for idx in range(3):
            cy = superficie + 26.0 + idx * 42.0 + math.sin(t * 0.5 + idx) * 6.0
            if cy < altura:
                p.drawEllipse(QPointF(largura * (0.28 + idx * 0.24), cy), 68.0, 11.0)

        self._desenhar_bolhas_e_espuma(p, superficie, t, amp)
        p.setClipping(False)

    def _desenhar_bolhas(self, p: QPainter, superficie: float, espuma_cor: QColor) -> None:
        for bolha in self._bolhas:
            if bolha.y <= superficie + 3.0:
                continue
            bx = bolha.x + math.sin(bolha.fase) * bolha.amp_x
            fator_y = max(0.0, min(1.0, (self.height() - bolha.y) / max(1.0, self.height())))
            r = bolha.raio * (0.85 + 0.35 * fator_y)
            aro = QColor(espuma_cor)
            aro.setAlpha(185)
            p.setPen(QPen(aro, 1.15))
            interno = QColor(espuma_cor)
            interno.setAlpha(48)
            p.setBrush(interno)
            p.drawEllipse(QPointF(bx, bolha.y), r, r)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 210))
            p.drawEllipse(QPointF(bx - r * 0.30, bolha.y - r * 0.30), max(0.7, r * 0.28), max(0.7, r * 0.28))

    def _desenhar_bolhas_e_espuma(
        self, p: QPainter, superficie: float, t: float, amp: float
    ) -> None:
        espuma_cor = QColor(self._paleta.espuma)
        self._desenhar_bolhas(p, superficie, espuma_cor)
        if self._nivel <= 0.02:
            return

        p.setPen(QPen(QColor(255, 255, 255, 190), 2.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        crista = QPainterPath(QPointF(0.0, self._onda_y(0.0, superficie, t, amp)))
        for x in range(4, self.width() + 1, 4):
            crista.lineTo(float(x), self._onda_y(float(x), superficie, t, amp))
        p.drawPath(crista)

        p.setPen(Qt.PenStyle.NoPen)
        c_esp = QColor(espuma_cor)
        c_esp.setAlpha(220)
        p.setBrush(c_esp)
        for idx, x in enumerate(range(4, self.width(), 6)):
            y = self._onda_y(float(x), superficie, t, amp)
            r = 1.8 + ((idx * 17) % 5) * 0.55 + 0.4 * math.sin(x * 0.19 + t * 1.4)
            p.drawEllipse(QPointF(float(x), y + 1.2), r, r * 0.78)

        p.setBrush(Qt.BrushStyle.NoBrush)
        for ex, ey, er, age in self._estouros:
            c_pop = QColor(espuma_cor)
            c_pop.setAlpha(int(190 * (1.0 - age)))
            p.setPen(QPen(c_pop, 1.1))
            p.drawEllipse(QPointF(ex, ey), er * (1.0 + age * 1.8), er * (0.7 + age * 1.1))

    def paintEvent(self, _event) -> None:
        """Renderiza a logo 3D preenchida pelo líquido com espuma e bolhas."""
        self._avancar_simulacao()
        camada_liq = QImage(self.size(), QImage.Format.Format_ARGB32_Premultiplied)
        camada_liq.fill(Qt.GlobalColor.transparent)
        p_liq = QPainter(camada_liq)
        p_liq.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._nivel > 0.005:
            amp = 2.6 + min(4.8, self._vel_nivel * 3.8)
            if self._nivel >= 0.995:
                amp = 0.4
            self._desenhar_liquido(p_liq, self._altura_superficie(), amp)

        p_liq.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        p_liq.drawImage(0, 0, self._mascara_liquido)
        p_liq.end()

        painter = QPainter(self)
        painter.drawImage(0, 0, self._camada_extrusao)
        painter.drawImage(0, 0, self._camada_cavidade)
        painter.drawImage(0, 0, camada_liq)
        painter.drawImage(0, 0, self._camada_borda)
        painter.drawImage(0, 0, self._camada_vidro)

    def _posicionar(self, settings: Settings | None) -> None:
        screen = QGuiApplication.primaryScreen()
        if settings is not None and settings.window.start_position is not None:
            x, y = settings.window.start_position
            half = settings.window.size // 2
            screen = QGuiApplication.screenAt(QPoint(x + half, y + half)) or screen
        if screen is not None:
            rect = self.rect()
            rect.moveCenter(screen.geometry().center())
            self.move(rect.topLeft())


def _exibir(settings, progresso, encerrado):
    """O loop Qt continua animando enquanto a thread principal carrega o Panda."""
    if encerrado.is_set():
        return
    app = QApplication([])
    splash = LoadingSplash(settings)
    timer = QTimer()
    completo = None
    parent = multiprocessing.parent_process()

    def verificar_encerramento():
        nonlocal completo
        nivel = progresso.value
        splash.atualizar(nivel)
        if encerrado.is_set() or (parent is not None and not parent.is_alive()):
            app.quit()
        elif nivel >= 1:
            if completo is None:
                completo = time.monotonic()
            elif time.monotonic() - completo >= 0.20:
                app.quit()

    timer.timeout.connect(verificar_encerramento)
    timer.start(16)
    splash.show()
    app.exec()


@contextmanager
def animacao_de_abertura(settings):
    """Vincula a vida do splash à inicialização, inclusive em caso de erro."""
    ctx = multiprocessing.get_context("spawn")
    encerrado = ctx.Event()
    progresso = ctx.Value("d", 0.0)
    processo = ctx.Process(target=_exibir, args=(settings, progresso, encerrado), daemon=True)
    processo.start()
    try:
        yield progresso
    finally:
        encerrado.set()
        processo.join(timeout=1)
        if processo.is_alive():
            processo.terminate()
            processo.join()
        processo.close()
