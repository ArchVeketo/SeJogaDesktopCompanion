"""Janela principal de autoria do Editor do Mário unindo catálogo, 3D, inspetor e timeline."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from sejoga.editor.barras_editor import (
    BannersEditor,
    BarraCameraViewport,
    BarraSuperiorEditor,
)
from sejoga.editor.catalogo import AcaoCatalogo, construir_catalogo
from sejoga.editor.documento import DocumentoEditor, PoseProvisoria
from sejoga.editor.ik_membros import (
    GRUPOS_CORPO_INTEIRO,
    amostrar_pista_bloco_no_tempo,
    resolver_espec_mover_membro,
    valor_chave_membro,
)
from sejoga.editor.mutacoes_pistas import (
    aplicar_curva_selecao,
    bloco_pistas_para_acao,
    calcular_ids_sujos,
    indice_chave_proxima,
    inserir_ou_atualizar_chave,
    mover_chave_indice,
    mutar_caminho_rascunho,
    remover_chave_no_tempo,
)
from sejoga.editor.painel_catalogo import PainelCatalogo
from sejoga.editor.painel_inspetor import PainelInspetor
from sejoga.editor.painel_timeline import PainelTimeline, construir_pistas_para_acao
from sejoga.editor.persistencia import ConflitoArquivoExternoError
from sejoga.editor.roteiro import EstimuloRoteiro, ObstaculoPrevia
from sejoga.editor.sessao_previa import STEP_SIM_S, ModoPrevia, SessaoPrevia
from sejoga.editor.tema import (
    aplicar_tema_widget,
    carregar_preferencias_ui,
    salvar_preferencias_ui,
)
from sejoga.editor.viewport_panda import (
    EstadoAlvoMover,
    EstadoOverlays,
    ModoCamera,
    ModoFerramenta,
    ViewportPandaWidget,
)


@dataclass(slots=True)
class _ContextoDragMembro:
    tempo_s: float
    pose0_deg: dict[str, tuple[float, float, float]]
    track0_deg: dict[str, tuple[float, float, float]]
    chavear_grupos: frozenset[str]
    provisoria_antes: PoseProvisoria


def _normalizar_trio(valor: Any) -> tuple[float, float, float]:
    if isinstance(valor, (tuple, list)) and len(valor) >= 3:
        return (float(valor[0]), float(valor[1]), float(valor[2]))
    return (0.0, 0.0, 0.0)


def _alvo_vfx_de(rascunho: dict[str, Any], nome_ef: str) -> EstadoAlvoMover:
    spec = rascunho.get("VFX", {}).get(nome_ef, {})
    if not isinstance(spec, dict):
        return EstadoAlvoMover()
    return EstadoAlvoMover(
        tipo="vfx",
        rotulo=f"VFX: {nome_ef}",
        valor_atual=_normalizar_trio(spec.get("deslocamento", (0.0, 0.0, 0.0))),
        ancora_vfx=str(spec.get("ancora", "cabeca")),
    )


class _FiltroTextoAtalhos(QObject):
    """Impede atalhos de tecla única quando um campo de texto tem foco."""

    _TECLAS_LIVRES = frozenset(
        {
            Qt.Key.Key_Escape,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
        }
    )

    def __init__(self, janela: QWidget) -> None:
        super().__init__(janela)
        self._janela = janela

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.ShortcutOverride:
            return False
        fw = QApplication.focusWidget()
        if (
            fw is not None
            and isinstance(fw, (QLineEdit, QAbstractSpinBox))
            and self._janela.isAncestorOf(fw)
        ):
            mods = event.modifiers()  # type: ignore[attr-defined]
            key = event.key()  # type: ignore[attr-defined]
            if (
                key not in self._TECLAS_LIVRES
                and mods in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ShiftModifier)
            ):
                event.accept()
                return True
        return False


def _rotacao_local_graus(quadro_pose: dict[str, Any], grupo: str) -> tuple[float, float, float]:
    base = grupo.split(":", 1)[0]
    rot = quadro_pose.get(grupo) or quadro_pose.get(base)
    if rot is None:
        return (0.0, 0.0, 0.0)
    return (
        round(math.degrees(rot.x), 2),
        round(math.degrees(rot.y), 2),
        round(math.degrees(rot.z), 2),
    )


class JanelaEditor(QMainWindow):
    """Janela desktop completa para ensaiar, editar e gravar ações do Mário."""

    def __init__(
        self,
        documento: DocumentoEditor | None = None,
        parent: QWidget | None = None,
        *,
        habilitar_gpu: bool = True,
        caminho_ui: Path | None = None,
        confirmar_pendencias: bool = True,
    ) -> None:
        """Inicializa documento, sessão de prévia, painéis, viewport e atalhos."""
        super().__init__(parent)
        self.setWindowTitle("Editor do Mário — SeJoga Desktop Companion")
        aplicar_tema_widget(self)

        self.documento = documento or DocumentoEditor()
        self.sessao = SessaoPrevia(self.documento)
        self._inicializar_estado(caminho_ui=caminho_ui, confirmar_pendencias=confirmar_pendencias)
        self._construir_interface(habilitar_gpu=habilitar_gpu)
        self._conectar_sinais()
        self._instalar_atalhos()
        self._restaurar_layout()
        self._configurar_timer_previa()
        self._carregar_catalogo_inicial()

    def _inicializar_estado(
        self, *, caminho_ui: Path | None, confirmar_pendencias: bool
    ) -> None:
        self._caminho_ui = caminho_ui
        self._confirmar_pendencias = confirmar_pendencias
        self._acoes: list[AcaoCatalogo] = []
        self._por_id: dict[str, AcaoCatalogo] = {}
        self._acao_atual: AcaoCatalogo | None = None
        self._variante_atual: str | None = None
        self._grupo_atual = "right-arm"
        self._auto_chave = False
        self._chaves_sel: list[tuple[str, int]] = []
        self._overlays = EstadoOverlays()
        self._ferramenta = ModoFerramenta.GIRAR
        self._alvo_mover_preferido = "auto"
        self._transacao_arraste: str | None = None
        self._em_transacao_gizmo = False
        self._em_transacao_mover = False
        self._membro_drag_ctx: _ContextoDragMembro | None = None
        self._obstaculo_antes_drag: ObstaculoPrevia | None = None
        self._musica_listener: Any = None
        self._modelo_trilha: Any = None
        self._filtro_texto = _FiltroTextoAtalhos(self)

    def _construir_interface(self, *, habilitar_gpu: bool) -> None:
        raiz_w = QWidget(self)
        self.setCentralWidget(raiz_w)
        raiz = QVBoxLayout(raiz_w)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self.barra_superior = BarraSuperiorEditor(raiz_w)
        self.banners = BannersEditor(raiz_w)
        raiz.addWidget(self.barra_superior)
        raiz.addWidget(self.banners)

        self.splitter_vertical = QSplitter(Qt.Orientation.Vertical, raiz_w)
        self.splitter_horizontal = QSplitter(Qt.Orientation.Horizontal, self.splitter_vertical)

        self.catalogo = PainelCatalogo(self.splitter_horizontal)
        self._miolo_viewport = self._criar_miolo_viewport(habilitar_gpu=habilitar_gpu)
        self.inspetor = PainelInspetor(self.splitter_horizontal)
        self.timeline = PainelTimeline(self.splitter_vertical)

        self.splitter_horizontal.addWidget(self.catalogo)
        self.splitter_horizontal.addWidget(self._miolo_viewport)
        self.splitter_horizontal.addWidget(self.inspetor)
        self.splitter_horizontal.setSizes([220, 680, 300])

        self.splitter_vertical.addWidget(self.splitter_horizontal)
        self.splitter_vertical.addWidget(self.timeline)
        self.splitter_vertical.setSizes([470, 240])
        raiz.addWidget(self.splitter_vertical, 1)

    def _criar_miolo_viewport(self, *, habilitar_gpu: bool) -> QWidget:
        cont = QWidget(self.splitter_horizontal)
        vbox = QVBoxLayout(cont)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        self.barra_camera = BarraCameraViewport(cont)
        self.viewport = ViewportPandaWidget(cont, habilitar_gpu=habilitar_gpu)
        vbox.addWidget(self.barra_camera)
        vbox.addWidget(self.viewport, 1)
        return cont

    def _conectar_sinais(self) -> None:
        self._conectar_barras()
        self._conectar_viewport_e_inspetor()
        self._conectar_timeline()
        self.sessao.registrar_callback_reset(self.viewport.reiniciar_efeitos)

    def _conectar_barras(self) -> None:
        self.catalogo.acao_solicitada.connect(self._on_acao_solicitada)
        self.barra_superior.desfazer_solicitado.connect(self.desfazer)
        self.barra_superior.refazer_solicitado.connect(self.refazer)
        self.barra_superior.modo_alterado.connect(self._on_modo_alterado)
        self.barra_superior.salvar_solicitado.connect(self.salvar_projeto)
        self.barra_superior.alternar_catalogo.connect(self._alternar_catalogo)
        self.barra_superior.alternar_inspetor.connect(self._alternar_inspetor)

        self.barra_camera.camera_alterada.connect(self.definir_modo_camera)
        self.barra_camera.enquadrar_solicitado.connect(self.viewport.enquadrar)
        self.barra_camera.overlays_alterados.connect(self._on_overlays_alterados)
        self.barra_camera.ferramenta_alterada.connect(self.definir_ferramenta)
        self.barra_camera.estimulo_rapido_solicitado.connect(
            lambda tipo: self.disparar_estimulo_contexto(tipo),
        )

        self.banners.gravar_provisoria.connect(self.gravar_pose_provisoria)
        self.banners.descartar_provisoria.connect(self.descartar_pose_provisoria)
        self.banners.recarregar_externa.connect(self.recarregar_externa)
        self.banners.tentar_salvar_novamente.connect(self.salvar_projeto)

    def _conectar_viewport_e_inspetor(self) -> None:
        self.viewport.junta_selecionada.connect(self.selecionar_junta)
        self.viewport.gizmo_iniciado.connect(self._on_gizmo_iniciado)
        self.viewport.gizmo_atualizado.connect(self._on_gizmo_atualizado)
        self.viewport.gizmo_confirmado.connect(self._on_gizmo_confirmado)
        self.viewport.gizmo_cancelado.connect(self._on_gizmo_cancelado)
        self.viewport.mover_iniciado.connect(self._on_mover_iniciado)
        self.viewport.mover_atualizado.connect(self._on_mover_atualizado)
        self.viewport.mover_confirmado.connect(self._on_mover_confirmado)
        self.viewport.mover_cancelado.connect(self._on_mover_cancelado)

        self.inspetor.junta_selecionada.connect(self.selecionar_junta)
        self.inspetor.alvo_mover_solicitado.connect(self._on_alvo_mover_solicitado)
        self.inspetor.rotacao_junta_editada.connect(self._on_rotacao_inspetor)
        self.inspetor.chave_alternada.connect(self._on_chave_alternada)
        self.inspetor.curva_alterada.connect(self._on_curva_alterada)
        self.inspetor.duracao_solicitada.connect(self._on_duracao_solicitada)
        self.inspetor.campo_editado.connect(self._on_campo_editado)
        self.inspetor.janela_efeito_editada.connect(self._on_efeito_janela_confirmada)
        self.inspetor.obstaculo_alterado.connect(self._on_obstaculo_alterado)
        self.inspetor.estimulo_disparado.connect(self._on_estimulo_disparado)
        self.inspetor.estimulo_adicionado.connect(self._on_estimulo_adicionado)
        self.inspetor.roteiro_limpo.connect(self._on_roteiro_limpo)
        self.inspetor.modo_sono_alterado.connect(self._on_modo_sono_alterado)

    def _conectar_timeline(self) -> None:
        tr = self.timeline.transporte
        tr.passo_quadro.connect(self._passo_quadro)
        tr.alternar_reproducao.connect(self.alternar_reproducao)
        tr.loop_alterado.connect(self.sessao.definir_loop)
        tr.fps_alterado.connect(self.sessao.definir_fps)
        tr.velocidade_alterada.connect(self.sessao.definir_velocidade)
        tr.auto_chave_alterado.connect(self._on_auto_chave)
        tr.bpm_alterado.connect(self._on_bpm_alterado)
        tr.metronomo_alterado.connect(self._on_metronomo_alterado)
        tr.batida_gravada.connect(self._on_gravar_batida)
        tr.musica_ao_vivo_alterada.connect(self._on_musica_ao_vivo)

        tl = self.timeline
        tl.cursor_movido.connect(self.ir_para_tempo)
        tl.chave_selecionada.connect(self._on_chave_timeline_selecionada)
        tl.chave_movida_preview.connect(self._on_chave_movida_preview)
        tl.chave_movida_confirmada.connect(self._on_chave_movida_confirmada)
        tl.chave_curva_movida_preview.connect(self._on_curva_movida_preview)
        tl.chave_curva_movida_confirmada.connect(self._on_curva_movida_confirmada)
        tl.chave_inserir_em.connect(self._on_inserir_chave_em)
        tl.efeito_selecionado.connect(self.inspetor.selecionar_efeito_cena)
        tl.efeito_janela_preview.connect(self._on_efeito_janela_preview)
        tl.efeito_janela_confirmada.connect(self._on_efeito_janela_confirmada)
        tl.estimulo_movido.connect(self._on_estimulo_movido)
        tl.solo_alternado.connect(self._on_solo_alternado)
        tl.mudo_alternado.connect(self._on_mudo_alternado)

    def _instalar_atalhos(self) -> None:
        atalhos = (
            ("Space", self.alternar_reproducao),
            ("Left", lambda: self._passo_quadro(-1)),
            ("Right", lambda: self._passo_quadro(1)),
            ("Ctrl+Z", self.desfazer),
            ("Ctrl+Shift+Z", self.refazer),
            ("Ctrl+S", self.salvar_projeto),
            ("Ctrl+F", self.catalogo.focar_busca),
            ("I", self._inserir_chave_cursor_atual),
            ("K", self._inserir_chave_cursor_atual),
            ("R", lambda: self.definir_ferramenta(ModoFerramenta.GIRAR)),
            ("G", lambda: self.definir_ferramenta(ModoFerramenta.MOVER)),
            ("F", self.viewport.enquadrar),
            ("F2", lambda: self._alternar_catalogo(not self.catalogo.isVisible())),
            ("F3", lambda: self._alternar_inspetor(not self.inspetor.isVisible())),
            ("Escape", self._on_atalho_esc),
        )
        self._atalhos_refs: list[QShortcut] = []
        for seq, slot in atalhos:
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(slot)
            self._atalhos_refs.append(sc)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self._filtro_texto)

    def _configurar_timer_previa(self) -> None:
        self._timer_previa = QTimer(self)
        self._timer_previa.setInterval(16)
        self._timer_previa.timeout.connect(self._on_tick_previa)
        self._timer_previa.start()

    def _restaurar_layout(self) -> None:
        prefs = carregar_preferencias_ui(self._caminho_ui)
        w = int(prefs.get("largura", 1240))
        h = int(prefs.get("altura", 760))
        self.resize(max(920, w), max(620, h))
        div_h = prefs.get("div_horizontal")
        if isinstance(div_h, list) and len(div_h) == 3:
            self.splitter_horizontal.setSizes([int(x) for x in div_h])
        div_v = prefs.get("div_vertical")
        if isinstance(div_v, list) and len(div_v) == 2:
            self.splitter_vertical.setSizes([int(x) for x in div_v])
        cat_vis = bool(prefs.get("catalogo_visivel", True))
        insp_vis = bool(prefs.get("inspetor_visivel", True))
        self.catalogo.setVisible(cat_vis)
        self.inspetor.setVisible(insp_vis)
        self.barra_superior.definir_visibilidade_paineis(
            catalogo=cat_vis,
            inspetor=insp_vis,
        )

    def _salvar_layout(self) -> None:
        dados = {
            "largura": self.width(),
            "altura": self.height(),
            "div_horizontal": self.splitter_horizontal.sizes(),
            "div_vertical": self.splitter_vertical.sizes(),
            "catalogo_visivel": self.catalogo.isVisible(),
            "inspetor_visivel": self.inspetor.isVisible(),
        }
        salvar_preferencias_ui(dados, self._caminho_ui)

    def _carregar_catalogo_inicial(self) -> None:
        self._acoes = list(construir_catalogo(self.documento.rascunho))
        self._por_id = {acao.id: acao for acao in self._acoes}
        self.catalogo.definir_acoes(self._acoes)
        inicial = "cenas_idle:fone_com_problema"
        if inicial not in self._por_id and self._acoes:
            inicial = self._acoes[0].id
        if inicial in self._por_id:
            self.abrir_acao(inicial, None, confirmar=False)

    def abrir_acao(
        self,
        acao_id: str,
        variante: str | None = None,
        *,
        confirmar: bool = True,
    ) -> bool:
        """Carrega ``acao_id`` na prévia, catálogo, inspetor, viewport e timeline."""
        acao = self._por_id.get(acao_id)
        if acao is None:
            return False
        if confirmar and not self._confirmar_mudanca_se_necessario():
            if self._acao_atual is not None:
                self.catalogo.selecionar_acao(
                    self._acao_atual.id,
                    self._variante_atual,
                    emitir=False,
                )
            return False

        self._acao_atual = acao
        self._variante_atual = variante
        self._alvo_mover_preferido = "auto"
        self._chaves_sel = []
        self.sessao.definir_solo(None)
        self.sessao.selecionar_acao(acao, variante)
        self.catalogo.selecionar_acao(acao.id, variante, emitir=False)
        self.timeline.transporte.definir_loop(self.sessao.loop_ativo)
        self.timeline.transporte.definir_bpm(self.sessao.roteiro.bpm)
        self.timeline.transporte.definir_reproduzindo(False)
        self._selecionar_junta_inicial_acao(acao)
        self._recarregar_paineis_visuais()
        self.viewport.enquadrar()
        return True

    def _selecionar_junta_inicial_acao(self, acao: AcaoCatalogo) -> None:
        bloco = bloco_pistas_para_acao(
            self.documento.rascunho,
            acao,
            self._variante_atual,
        )
        if bloco and isinstance(bloco.get("tracks"), dict) and bloco["tracks"]:
            tracks = bloco["tracks"]
            if "right-arm" in tracks:
                self.selecionar_junta("right-arm")
            else:
                self.selecionar_junta(next(iter(tracks.keys())))
        else:
            self.selecionar_junta("right-arm")

    def _on_acao_solicitada(self, acao_id: str, variante: object) -> None:
        var_str = str(variante) if isinstance(variante, str) else None
        if (
            self._acao_atual is not None
            and acao_id == self._acao_atual.id
            and var_str == self._variante_atual
        ):
            return
        self.abrir_acao(acao_id, var_str, confirmar=self._confirmar_pendencias)

    def _confirmar_mudanca_se_necessario(self) -> bool:
        if not self._resolver_provisoria_para("trocar de ação"):
            return False
        if (
            self._confirmar_pendencias
            and self._acao_atual is not None
            and self._acao_atual.id in self._acoes_sujas()
        ):
            msg = QMessageBox(self)
            msg.setWindowTitle("Alterações pendentes")
            msg.setText(
                f"A ação '{self._acao_atual.nome}' tem alterações não salvas.",
            )
            btn_manter = msg.addButton(
                "Manter no rascunho",
                QMessageBox.ButtonRole.AcceptRole,
            )
            btn_salvar = msg.addButton("Salvar e trocar", QMessageBox.ButtonRole.YesRole)
            msg.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            clicado = msg.clickedButton()
            if clicado is btn_manter:
                return True
            if clicado is btn_salvar:
                return self.salvar_projeto()
            return False
        return True

    def _resolver_provisoria_para(self, motivo: str) -> bool:
        if not self.documento.provisoria.ativa:
            return True
        if not self._confirmar_pendencias:
            self.documento.descartar_provisoria()
            self.banners.definir_provisoria(False)
            return True
        resp = QMessageBox.question(
            self,
            "Pose provisória ativa",
            f"Há ajustes fora de chave antes de {motivo}. Gravar chave agora?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if resp == QMessageBox.StandardButton.Yes:
            return self.gravar_pose_provisoria()
        if resp == QMessageBox.StandardButton.Discard:
            self.descartar_pose_provisoria()
            return True
        return False

    def definir_modo_camera(self, modo: ModoCamera) -> None:
        """Atualiza o modo de câmera na barra e no viewport 3D."""
        self.barra_camera.definir_modo_camera(modo)
        self.viewport.definir_modo_camera(modo)

    def selecionar_junta(self, grupo: str) -> None:
        """Sincroniza seleção da junta entre viewport 3D, inspetor e timeline."""
        self._grupo_atual = grupo
        self._alvo_mover_preferido = "auto"
        self.viewport.definir_junta_selecionada(grupo)
        self._sincronizar_inspetor_junta()
        self._recarregar_timeline()
        self._sincronizar_alvo_mover()

    def ir_para_tempo(self, tempo_s: float) -> None:
        """Reposiciona o cursor da prévia no instante ``tempo_s``."""
        self.sessao.pausar()
        self.timeline.transporte.definir_reproduzindo(False)
        self.sessao.ir_para(tempo_s)
        self._sincronizar_quadro_ui()

    def alternar_reproducao(self) -> None:
        """Alterna entre reproduzir e pausar respeitando guardas de pose provisória."""
        if (
            not self.sessao.reproduzindo
            and not self._resolver_provisoria_para("reproduzir")
        ):
            return
        self.sessao.alternar_reproducao()
        self.timeline.transporte.definir_reproduzindo(self.sessao.reproduzindo)

    def _passo_quadro(self, delta: int) -> None:
        self.sessao.pausar()
        self.timeline.transporte.definir_reproduzindo(False)
        self.sessao.avancar_quadro(delta)
        self._sincronizar_quadro_ui()

    def _on_tick_previa(self) -> None:
        if not self.sessao.reproduzindo:
            return
        self.sessao.avancar(STEP_SIM_S)
        self._sincronizar_quadro_ui()

    def _on_modo_alterado(self, modo: ModoPrevia) -> None:
        self.sessao.definir_modo(modo)
        self.sessao.reavaliar_quadro_atual()
        self._sincronizar_quadro_ui()

    def _on_overlays_alterados(self, overlays: EstadoOverlays) -> None:
        self._overlays = overlays
        self.viewport.definir_overlays(overlays)
        self._sincronizar_quadro_ui()

    def _on_auto_chave(self, ativo: bool) -> None:
        self._auto_chave = bool(ativo)

    def _on_gizmo_iniciado(self, grupo: str, eixo: str) -> None:
        self._grupo_atual = grupo
        self._em_transacao_gizmo = True
        self.documento.iniciar_transacao(f"Girar {grupo} ({eixo.upper()})")

    def _on_gizmo_atualizado(self, grupo: str, rot: object) -> None:
        if not isinstance(rot, tuple) or len(rot) != 3:
            return
        angulos = (float(rot[0]), float(rot[1]), float(rot[2]))
        self._aplicar_pose_eixo(grupo, angulos, confirmar=False)

    def _on_gizmo_confirmado(self, grupo: str, rot: object) -> None:
        if not isinstance(rot, tuple) or len(rot) != 3:
            self._em_transacao_gizmo = False
            self.documento.cancelar_transacao()
            return
        angulos = (float(rot[0]), float(rot[1]), float(rot[2]))
        self._aplicar_pose_eixo(grupo, angulos, confirmar=True)

    def _on_gizmo_cancelado(self) -> None:
        self._em_transacao_gizmo = False
        self.documento.cancelar_transacao()
        self.documento.descartar_provisoria()
        self.banners.definir_provisoria(False)
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def definir_ferramenta(self, modo: ModoFerramenta) -> None:
        """Alterna o manipulador ativo entre ``Girar`` (R) e ``Mover`` (G)."""
        self._ferramenta = modo
        self.barra_camera.definir_ferramenta(modo)
        self.viewport.definir_ferramenta(modo)
        alvo = self._sincronizar_alvo_mover()
        if modo == ModoFerramenta.MOVER and not alvo.tipo:
            self.banners.mostrar_toast(
                "Sem alvo movível em 3D nesta ação — use Girar (R).",
                duracao_ms=2600,
            )

    def _on_alvo_mover_solicitado(self, preferencia: str) -> None:
        self._alvo_mover_preferido = preferencia
        self.definir_ferramenta(ModoFerramenta.MOVER)

    def _resolver_alvo_mover(self) -> EstadoAlvoMover:
        acao = self._acao_atual
        if acao is None:
            return EstadoAlvoMover()
        if acao.secao_dados == "VFX":
            return _alvo_vfx_de(self.documento.rascunho, acao.chave_dados)
        if acao.secao_dados == "TENTACULOS":
            return EstadoAlvoMover(
                tipo="obstaculo",
                rotulo="Obstáculo dos tentáculos",
                valor_atual=self.sessao.roteiro.obstaculo.centro,
            )
        if acao.tipo_editor == "pistas_3d":
            return self._resolver_alvo_mover_pistas(acao)
        return EstadoAlvoMover()

    def _resolver_alvo_mover_pistas(self, acao: AcaoCatalogo) -> EstadoAlvoMover:
        if acao.secao_dados in ("IDLE_CLIPS", "CENAS_IDLE"):
            ef = self.inspetor.efeito_selecionado
            if (
                self._alvo_mover_preferido == "vfx"
                and ef
                and ef in self.documento.rascunho.get("VFX", {})
            ):
                return _alvo_vfx_de(self.documento.rascunho, ef)
            if (
                self._alvo_mover_preferido == "corpo"
                or self._grupo_atual in GRUPOS_CORPO_INTEIRO
            ):
                bloco = bloco_pistas_para_acao(
                    self.documento.rascunho, acao, self._variante_atual
                )
                bruto = bloco.get("deslocamento_corpo", (0.0, 0.0, 0.0)) if bloco else ()
                return EstadoAlvoMover("corpo", f"Corpo ({acao.nome})", _normalizar_trio(bruto))
        espec = resolver_espec_mover_membro(self._grupo_atual)
        if espec is not None:
            return EstadoAlvoMover(
                tipo="membro",
                rotulo=espec.rotulo,
                grupo=self._grupo_atual,
                modo_ik=espec.modo,
                juntas_afetadas=espec.juntas,
            )
        return EstadoAlvoMover()

    def _caminho_mover_atual(self, tipo: str) -> tuple[Any, ...] | None:
        acao = self._acao_atual
        if acao is None:
            return None
        if tipo == "vfx":
            nome_ef = acao.chave_dados if acao.secao_dados == "VFX" else self.inspetor.efeito_selecionado
            return ("VFX", str(nome_ef), "deslocamento") if nome_ef else None
        if tipo != "corpo":
            return None
        caminho: list[Any] = [acao.secao_dados, acao.chave_dados]
        bloco = self.documento.rascunho.get(acao.secao_dados, {}).get(acao.chave_dados, {})
        if (
            self._variante_atual
            and isinstance(bloco, dict)
            and isinstance(bloco.get("variantes"), dict)
            and self._variante_atual in bloco["variantes"]
        ):
            caminho.extend(["variantes", self._variante_atual])
        caminho.append("deslocamento_corpo")
        return tuple(caminho)

    def _sincronizar_alvo_mover(self) -> EstadoAlvoMover:
        alvo = self._resolver_alvo_mover()
        self.barra_camera.definir_dica_mover(alvo.rotulo or None)
        self.viewport.definir_alvo_mover(alvo)
        return alvo

    def _on_mover_iniciado(self, tipo: str, eixo: str) -> None:
        self._em_transacao_mover = True
        if tipo == "obstaculo":
            self._obstaculo_antes_drag = self.sessao.roteiro.obstaculo
            return
        if tipo == "membro":
            self._membro_drag_ctx = self._criar_ctx_drag_membro()
            if self._membro_drag_ctx.chavear_grupos:
                self.documento.iniciar_transacao(
                    f"Mover membro {self._grupo_atual} ({eixo.upper()})"
                )
            return
        self._membro_drag_ctx = None
        self.documento.iniciar_transacao(f"Mover {tipo} ({eixo.upper()})")

    def _criar_ctx_drag_membro(
        self, juntas_extra: tuple[str, ...] = ()
    ) -> _ContextoDragMembro:
        acao = self._acao_atual
        alvo = self._resolver_alvo_mover()
        juntas = tuple(dict.fromkeys([*(alvo.juntas_afetadas or (self._grupo_atual,)), *juntas_extra]))
        tempo = self.sessao.tempo_s
        pose0: dict[str, tuple[float, float, float]] = {}
        track0: dict[str, tuple[float, float, float]] = {}
        chavear: set[str] = set()
        bloco = (
            bloco_pistas_para_acao(self.documento.rascunho, acao, self._variante_atual)
            if acao is not None
            else None
        )
        tracks = bloco.get("tracks", {}) if bloco else {}
        pose_atual = self.sessao.ultimo_quadro.pose
        for grp in juntas:
            rot = pose_atual.get(grp)
            pose0[grp] = (
                (math.degrees(rot.x), math.degrees(rot.y), math.degrees(rot.z))
                if rot is not None
                else (0.0, 0.0, 0.0)
            )
            track0[grp] = amostrar_pista_bloco_no_tempo(
                bloco,
                grp,
                tempo,
                secao_dados=acao.secao_dados if acao else "",
                duracao_acao_s=self.sessao.duracao_s,
            )
            chaves = tuple(tracks.get(grp, ()))
            if self._auto_chave or indice_chave_proxima(chaves, tempo) is not None:
                chavear.add(grp)
        prov = self.documento.provisoria
        prov_antes = PoseProvisoria(
            acao_id=prov.acao_id,
            variante=prov.variante,
            tempo_s=prov.tempo_s,
            grupos=dict(prov.grupos),
        )
        return _ContextoDragMembro(
            tempo_s=tempo,
            pose0_deg=pose0,
            track0_deg=track0,
            chavear_grupos=frozenset(chavear),
            provisoria_antes=prov_antes,
        )

    def _on_mover_atualizado(self, tipo: str, pos: object) -> None:
        self._aplicar_movimento_3d(tipo, pos, confirmar=False)

    def _on_mover_confirmado(self, tipo: str, pos: object) -> None:
        self._aplicar_movimento_3d(tipo, pos, confirmar=True)

    def _on_mover_cancelado(self) -> None:
        self._em_transacao_mover = False
        if self._membro_drag_ctx is not None:
            self.documento.provisoria = self._membro_drag_ctx.provisoria_antes
            self._membro_drag_ctx = None
            prov = self.documento.provisoria
            self.banners.definir_provisoria(prov.ativa, ", ".join(prov.grupos.keys()))
        if self._obstaculo_antes_drag is not None:
            obs = self._obstaculo_antes_drag
            self._obstaculo_antes_drag = None
            self.sessao.definir_roteiro(replace(self.sessao.roteiro, obstaculo=obs))
        else:
            self.documento.cancelar_transacao()
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _aplicar_movimento_3d(self, tipo: str, pos: object, *, confirmar: bool) -> None:
        if tipo == "membro":
            self._aplicar_movimento_membro(pos, confirmar=confirmar)
            return
        if not isinstance(pos, tuple) or len(pos) != 3:
            if confirmar:
                self._on_mover_cancelado()
            return
        trio = (round(float(pos[0]), 4), round(float(pos[1]), 4), round(float(pos[2]), 4))
        if tipo == "obstaculo":
            self._aplicar_movimento_obstaculo(trio, confirmar=confirmar)
            return
        caminho = self._caminho_mover_atual(tipo)
        if caminho is None:
            if confirmar:
                self._on_mover_cancelado()
            return
        self._gravar_movimento_caminho(tipo, caminho, trio, confirmar=confirmar)
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _aplicar_movimento_obstaculo(
        self, trio: tuple[float, float, float], *, confirmar: bool
    ) -> None:
        novo_obs = replace(self.sessao.roteiro.obstaculo, ativo=True, centro=trio)
        self.sessao.definir_roteiro(replace(self.sessao.roteiro, obstaculo=novo_obs))
        if confirmar:
            self._em_transacao_mover = False
            self._obstaculo_antes_drag = None
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _gravar_movimento_caminho(
        self,
        tipo: str,
        caminho: tuple[Any, ...],
        trio: tuple[float, float, float],
        *,
        confirmar: bool,
    ) -> None:
        if confirmar and self._em_transacao_mover:
            self.documento.atualizar_transacao(
                lambda d: mutar_caminho_rascunho(d, caminho, trio),
            )
            self.documento.confirmar_transacao()
            self._em_transacao_mover = False
        elif confirmar:
            self.documento.aplicar_edicao(
                f"Mover {tipo}",
                lambda d: mutar_caminho_rascunho(d, caminho, trio),
            )
        else:
            self.documento.atualizar_transacao(
                lambda d: mutar_caminho_rascunho(d, caminho, trio),
            )

    def _aplicar_movimento_membro(self, payload: object, *, confirmar: bool) -> None:
        acao = self._acao_atual
        if not isinstance(payload, dict) or acao is None or acao.tipo_editor != "pistas_3d":
            if confirmar:
                self._on_mover_cancelado()
            return
        poses_deg = {
            str(g): (float(v[0]), float(v[1]), float(v[2]))
            for g, v in payload.items()
            if isinstance(v, (tuple, list)) and len(v) == 3
        }
        if not poses_deg:
            if confirmar:
                self._on_mover_cancelado()
            return
        ctx = self._membro_drag_ctx or self._criar_ctx_drag_membro(tuple(poses_deg.keys()))
        para_chave = {
            g: valor_chave_membro(
                ctx.track0_deg.get(g, (0.0, 0.0, 0.0)),
                ctx.pose0_deg.get(g, (0.0, 0.0, 0.0)),
                v,
            )
            for g, v in poses_deg.items()
            if g in ctx.chavear_grupos
        }
        if para_chave:
            self._gravar_chaves_membro(acao, ctx.tempo_s, para_chave, confirmar=confirmar)
        for grp, val in poses_deg.items():
            if grp not in ctx.chavear_grupos:
                self.documento.definir_provisoria(
                    acao.id, self._variante_atual, ctx.tempo_s, grp, val
                )
        prov = self.documento.provisoria
        self.banners.definir_provisoria(prov.ativa, ", ".join(prov.grupos.keys()))
        if confirmar:
            self._em_transacao_mover = False
            self._membro_drag_ctx = None
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _gravar_chaves_membro(
        self,
        acao: AcaoCatalogo,
        tempo_s: float,
        para_chave: dict[str, tuple[float, float, float]],
        *,
        confirmar: bool,
    ) -> None:
        def _mut(dados: dict[str, Any]) -> None:
            alvo = bloco_pistas_para_acao(dados, acao, self._variante_atual)
            if alvo is None:
                return
            for grp, val in para_chave.items():
                inserir_ou_atualizar_chave(alvo, grp, tempo_s, val)

        if not confirmar:
            self.documento.atualizar_transacao(_mut)
        elif self._membro_drag_ctx is not None and self._em_transacao_mover:
            self.documento.atualizar_transacao(_mut)
            self.documento.confirmar_transacao()
        else:
            self.documento.aplicar_edicao(f"Mover membro {self._grupo_atual}", _mut)

    def _aplicar_pose_eixo(
        self,
        grupo: str,
        angulos: tuple[float, float, float],
        *,
        confirmar: bool,
    ) -> None:
        acao = self._acao_atual
        if acao is None or acao.tipo_editor != "pistas_3d":
            return
        bloco_atual = bloco_pistas_para_acao(
            self.documento.rascunho,
            acao,
            self._variante_atual,
        )
        tracks = bloco_atual.get("tracks", {}) if bloco_atual else {}
        chaves = tuple(tracks.get(grupo, ()))
        existe_chave = indice_chave_proxima(chaves, self.sessao.tempo_s) is not None
        if self._auto_chave or existe_chave:
            self._confirmar_chave_pose_eixo(acao, grupo, angulos, confirmar=confirmar)
            self.banners.definir_provisoria(False)
        else:
            if confirmar:
                self._em_transacao_gizmo = False
                self.documento.cancelar_transacao()
            self.documento.definir_provisoria(
                acao.id,
                self._variante_atual,
                self.sessao.tempo_s,
                grupo,
                angulos,
            )
            self.banners.definir_provisoria(True, grupo)
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _confirmar_chave_pose_eixo(
        self,
        acao: AcaoCatalogo,
        grupo: str,
        angulos: tuple[float, float, float],
        *,
        confirmar: bool,
    ) -> None:
        def _mut(dados: dict[str, Any]) -> None:
            alvo = bloco_pistas_para_acao(dados, acao, self._variante_atual)
            if alvo is not None:
                inserir_ou_atualizar_chave(alvo, grupo, self.sessao.tempo_s, angulos)

        if not confirmar:
            self.documento.atualizar_transacao(_mut)
            return
        if self._em_transacao_gizmo:
            self.documento.atualizar_transacao(_mut)
            self.documento.confirmar_transacao()
            self._em_transacao_gizmo = False
        else:
            self.documento.aplicar_edicao(f"Editar chave {grupo}", _mut)

    def _on_rotacao_inspetor(self, grupo: str, rot: tuple[float, ...]) -> None:
        if self._acao_atual is None or self._acao_atual.tipo_editor != "pistas_3d":
            return
        ang = (float(rot[0]), float(rot[1]), float(rot[2]))
        acao = self._acao_atual
        bloco_atual = bloco_pistas_para_acao(
            self.documento.rascunho,
            acao,
            self._variante_atual,
        )
        chaves = tuple(bloco_atual.get("tracks", {}).get(grupo, ())) if bloco_atual else ()
        if self._auto_chave or indice_chave_proxima(chaves, self.sessao.tempo_s) is not None:
            self.documento.aplicar_edicao(
                f"Ajustar {grupo}",
                lambda d: self._mut_chave(d, acao, grupo, self.sessao.tempo_s, ang),
            )
            self.banners.definir_provisoria(False)
        else:
            self.documento.definir_provisoria(
                acao.id,
                self._variante_atual,
                self.sessao.tempo_s,
                grupo,
                ang,
            )
            self.banners.definir_provisoria(True, grupo)
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _mut_chave(
        self,
        dados: dict[str, Any],
        acao: AcaoCatalogo,
        grupo: str,
        tempo_s: float,
        ang: tuple[float, float, float],
    ) -> None:
        alvo = bloco_pistas_para_acao(dados, acao, self._variante_atual)
        if alvo is not None:
            inserir_ou_atualizar_chave(alvo, grupo, tempo_s, ang)

    def _inserir_chave_cursor_atual(self) -> None:
        rot = _rotacao_local_graus(self.sessao.ultimo_quadro.pose, self._grupo_atual)
        self._on_chave_alternada(self._grupo_atual, rot)

    def _on_chave_alternada(self, grupo: str, rot: tuple[float, ...]) -> None:
        acao = self._acao_atual
        if acao is None or acao.tipo_editor != "pistas_3d":
            return
        ang = (float(rot[0]), float(rot[1]), float(rot[2]))
        bloco = bloco_pistas_para_acao(
            self.documento.rascunho,
            acao,
            self._variante_atual,
        )
        chaves = tuple(bloco.get("tracks", {}).get(grupo, ())) if bloco else ()
        if indice_chave_proxima(chaves, self.sessao.tempo_s) is not None:
            self.documento.aplicar_edicao(
                f"Remover chave {grupo}",
                lambda d: self._mut_remover_chave(d, acao, grupo, self.sessao.tempo_s),
            )
        else:
            self.documento.aplicar_edicao(
                f"Inserir chave {grupo}",
                lambda d: self._mut_chave(d, acao, grupo, self.sessao.tempo_s, ang),
            )
            self.documento.descartar_provisoria()
            self.banners.definir_provisoria(False)
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _mut_remover_chave(
        self,
        dados: dict[str, Any],
        acao: AcaoCatalogo,
        grupo: str,
        tempo_s: float,
    ) -> None:
        alvo = bloco_pistas_para_acao(dados, acao, self._variante_atual)
        if alvo is not None:
            remover_chave_no_tempo(alvo, grupo, tempo_s)

    def _on_inserir_chave_em(self, grupo: str, tempo_s: float) -> None:
        self.ir_para_tempo(tempo_s)
        rot = _rotacao_local_graus(self.sessao.ultimo_quadro.pose, grupo)
        acao = self._acao_atual
        if acao is None or acao.tipo_editor != "pistas_3d":
            return
        self.documento.aplicar_edicao(
            f"Inserir chave {grupo}",
            lambda d: self._mut_chave(d, acao, grupo, tempo_s, rot),
        )
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _on_chave_timeline_selecionada(
        self,
        grupo: str,
        indice: int,
        selecoes: list[tuple[str, int]],
    ) -> None:
        self._chaves_sel = list(selecoes)
        self.selecionar_junta(grupo)
        bloco = (
            bloco_pistas_para_acao(self.documento.rascunho, self._acao_atual, self._variante_atual)
            if self._acao_atual is not None
            else None
        )
        if bloco and indice >= 0:
            chaves = bloco.get("tracks", {}).get(grupo, ())
            if 0 <= indice < len(chaves):
                self.ir_para_tempo(float(chaves[indice][0]))

    def _on_chave_movida_preview(self, grupo: str, idx: int, novo_t: float) -> None:
        acao = self._acao_atual
        if acao is None or acao.tipo_editor != "pistas_3d":
            return
        if self._transacao_arraste != "chave":
            self._transacao_arraste = "chave"
            self.documento.iniciar_transacao(f"Mover chave {grupo}")
        self.documento.atualizar_transacao(
            lambda d: self._mut_mover_chave(d, acao, grupo, idx, novo_t, None),
        )
        self.sessao.ir_para(novo_t, forcar_reset=True)
        self._recarregar_paineis_visuais()

    def _on_chave_movida_confirmada(self, grupo: str, idx: int, novo_t: float) -> None:
        acao = self._acao_atual
        if acao is None or acao.tipo_editor != "pistas_3d":
            return
        if self._transacao_arraste != "chave":
            self.documento.aplicar_edicao(
                f"Mover chave {grupo}",
                lambda d: self._mut_mover_chave(d, acao, grupo, idx, novo_t, None),
            )
        else:
            self.documento.atualizar_transacao(
                lambda d: self._mut_mover_chave(d, acao, grupo, idx, novo_t, None),
            )
            self.documento.confirmar_transacao()
            self._transacao_arraste = None
        self.sessao.ir_para(novo_t, forcar_reset=True)
        self._recarregar_paineis_visuais()

    def _on_curva_movida_preview(
        self,
        grupo: str,
        idx: int,
        novo_t: float,
        nova_rot: tuple[float, ...],
    ) -> None:
        acao = self._acao_atual
        if acao is None or acao.tipo_editor != "pistas_3d":
            return
        rot = (float(nova_rot[0]), float(nova_rot[1]), float(nova_rot[2]))
        if self._transacao_arraste != "curva":
            self._transacao_arraste = "curva"
            self.documento.iniciar_transacao(f"Ajustar curva {grupo}")
        self.documento.atualizar_transacao(
            lambda d: self._mut_mover_chave(d, acao, grupo, idx, novo_t, rot),
        )
        self.sessao.ir_para(novo_t, forcar_reset=True)
        self._recarregar_paineis_visuais()

    def _on_curva_movida_confirmada(
        self,
        grupo: str,
        idx: int,
        novo_t: float,
        nova_rot: tuple[float, ...],
    ) -> None:
        acao = self._acao_atual
        if acao is None or acao.tipo_editor != "pistas_3d":
            return
        rot = (float(nova_rot[0]), float(nova_rot[1]), float(nova_rot[2]))
        if self._transacao_arraste != "curva":
            self.documento.aplicar_edicao(
                f"Ajustar curva {grupo}",
                lambda d: self._mut_mover_chave(d, acao, grupo, idx, novo_t, rot),
            )
        else:
            self.documento.atualizar_transacao(
                lambda d: self._mut_mover_chave(d, acao, grupo, idx, novo_t, rot),
            )
            self.documento.confirmar_transacao()
            self._transacao_arraste = None
        self.sessao.ir_para(novo_t, forcar_reset=True)
        self._recarregar_paineis_visuais()

    def _mut_mover_chave(
        self,
        dados: dict[str, Any],
        acao: AcaoCatalogo,
        grupo: str,
        idx: int,
        novo_t: float,
        rot: tuple[float, float, float] | None,
    ) -> None:
        alvo = bloco_pistas_para_acao(dados, acao, self._variante_atual)
        if alvo is not None:
            mover_chave_indice(alvo, grupo, idx, novo_t, rot)

    def _on_curva_alterada(self, curva: str) -> None:
        acao = self._acao_atual
        if acao is None or acao.tipo_editor != "pistas_3d":
            return
        self.documento.aplicar_edicao(
            f"Curva {curva}",
            lambda d: self._mut_curva(d, acao, curva),
        )
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _mut_curva(self, dados: dict[str, Any], acao: AcaoCatalogo, curva: str) -> None:
        alvo = bloco_pistas_para_acao(dados, acao, self._variante_atual)
        if alvo is not None:
            aplicar_curva_selecao(
                alvo,
                curva,
                self._chaves_sel,
                grupo_padrao=self._grupo_atual,
                tempo_s=self.sessao.tempo_s,
            )

    def _on_duracao_solicitada(self, nova_duracao: float) -> None:
        acao = self._acao_atual
        if acao is None or acao.tipo_editor != "pistas_3d":
            return
        conflitos = self.documento.verificar_reducao_duracao(
            acao.secao_dados,
            acao.chave_dados,
            nova_duracao,
            variante=self._variante_atual,
        )
        ajustar = False
        if conflitos:
            resumo = "\n".join(f"• {c.detalhe}" for c in conflitos[:5])
            resp = QMessageBox.question(
                self,
                "Conflito ao reduzir duração",
                f"Há itens além de {nova_duracao:.2f} s:\n{resumo}\n\nAjustar automaticamente?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if resp != QMessageBox.StandardButton.Yes:
                self._recarregar_paineis_visuais()
                return
            ajustar = True
        self.documento.aplicar_nova_duracao(
            acao.secao_dados,
            acao.chave_dados,
            nova_duracao,
            variante=self._variante_atual,
            ajustar_excedentes=ajustar,
        )
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _on_campo_editado(self, descricao: str, caminho: object, valor: object) -> None:
        if not isinstance(caminho, tuple):
            return
        self.documento.aplicar_edicao(
            descricao,
            lambda d: mutar_caminho_rascunho(d, caminho, valor),
        )
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _on_efeito_janela_preview(self, nome: str, ini: float, fim: float) -> None:
        acao = self._acao_atual
        if acao is None or acao.tipo_editor != "pistas_3d":
            return
        if self._transacao_arraste != "efeito":
            self._transacao_arraste = "efeito"
            self.documento.iniciar_transacao(f"Ajustar janela de {nome}")
        self.documento.atualizar_transacao(
            lambda d: self._mut_janela_efeito(d, acao, nome, ini, fim),
        )
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _on_efeito_janela_confirmada(self, nome: str, ini: float, fim: float) -> None:
        acao = self._acao_atual
        if acao is None or acao.tipo_editor != "pistas_3d":
            return
        if self._transacao_arraste != "efeito":
            self.documento.aplicar_edicao(
                f"Ajustar janela de {nome}",
                lambda d: self._mut_janela_efeito(d, acao, nome, ini, fim),
            )
        else:
            self.documento.atualizar_transacao(
                lambda d: self._mut_janela_efeito(d, acao, nome, ini, fim),
            )
            self.documento.confirmar_transacao()
            self._transacao_arraste = None
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _mut_janela_efeito(
        self,
        dados: dict[str, Any],
        acao: AcaoCatalogo,
        nome: str,
        ini: float,
        fim: float,
    ) -> None:
        alvo = bloco_pistas_para_acao(dados, acao, self._variante_atual)
        if alvo is not None:
            janelas = alvo.setdefault("janelas_efeito", {})
            if isinstance(janelas, dict):
                janelas[nome] = (round(ini, 4), round(fim, 4))

    def _on_obstaculo_alterado(self, obstaculo: object) -> None:
        if isinstance(obstaculo, ObstaculoPrevia):
            self.sessao.definir_roteiro(replace(self.sessao.roteiro, obstaculo=obstaculo))
            self.sessao.reavaliar_quadro_atual()
            self._sincronizar_quadro_ui()

    def _on_estimulo_disparado(self, estimulo: object) -> None:
        if isinstance(estimulo, EstimuloRoteiro):
            self.disparar_estimulo_contexto(estimulo.tipo, estimulo.alvo)

    def disparar_estimulo_contexto(self, tipo: str, alvo: str = "body") -> None:
        """Alterna para ``Em contexto`` se preciso e dispara estímulo imediato."""
        est = EstimuloRoteiro(tempo_s=self.sessao.tempo_s, tipo=tipo, alvo=alvo)
        self.sessao.disparar_estimulo_agora(est)
        self._sincronizar_quadro_ui()

    def _on_estimulo_adicionado(self, estimulo: object) -> None:
        if isinstance(estimulo, EstimuloRoteiro):
            atuais = list(self.sessao.roteiro.estimulos)
            atuais.append(estimulo)
            self.sessao.definir_roteiro(replace(self.sessao.roteiro, estimulos=tuple(atuais)))
            self._recarregar_timeline()

    def _on_estimulo_movido(self, indice: int, novo_tempo: float) -> None:
        lista = list(self.sessao.roteiro.ordenados())
        if 0 <= indice < len(lista):
            lista[indice] = replace(lista[indice], tempo_s=novo_tempo)
            self.sessao.definir_roteiro(replace(self.sessao.roteiro, estimulos=tuple(lista)))
            self.sessao.reavaliar_quadro_atual()
            self._recarregar_paineis_visuais()

    def _on_roteiro_limpo(self) -> None:
        self.sessao.definir_roteiro(replace(self.sessao.roteiro, estimulos=()))
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _on_modo_sono_alterado(self, modo: str) -> None:
        self.sessao.definir_roteiro(replace(self.sessao.roteiro, modo_sono=modo))
        self.sessao.reavaliar_quadro_atual()
        self._sincronizar_quadro_ui()

    def _on_bpm_alterado(self, bpm: float) -> None:
        self.sessao.definir_roteiro(replace(self.sessao.roteiro, bpm=bpm))
        self.sessao.reavaliar_quadro_atual()
        self._sincronizar_quadro_ui()

    def _on_metronomo_alterado(self, ativo: bool) -> None:
        self.sessao.definir_roteiro(replace(self.sessao.roteiro, metronomo_ativo=ativo))

    def _on_gravar_batida(self) -> None:
        t = round(self.sessao.tempo_s, 3)
        batidas = sorted({*self.sessao.roteiro.batidas_gravadas_s, t})
        self.sessao.definir_roteiro(
            replace(self.sessao.roteiro, batidas_gravadas_s=tuple(batidas)),
        )
        self.banners.mostrar_toast(f"Batida gravada em {t:.2f} s")

    def _on_musica_ao_vivo(self, ativo: bool) -> None:
        if ativo and self._musica_listener is None:
            from sejoga.configuracao import MusicSettings
            from sejoga.musica.escuta_musica import MusicListener

            listener = MusicListener(MusicSettings(enabled=True))
            listener.start()
            self._musica_listener = listener
            self.sessao.provedor_musica = lambda: listener.snapshot
        elif not ativo and self._musica_listener is not None:
            self._musica_listener.stop(timeout=0.5)
            self._musica_listener = None
            self.sessao.provedor_musica = None
        self.sessao.definir_roteiro(replace(self.sessao.roteiro, usar_musica_ao_vivo=ativo))

    def _on_solo_alternado(self, pista: str) -> None:
        novo = None if self.sessao.pista_solo == pista else pista
        self.sessao.definir_solo(novo)
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _on_mudo_alternado(self, pista: str) -> None:
        self.sessao.alternar_silenciada(pista)
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def _on_atalho_esc(self) -> None:
        if self.viewport.cancelar_drag_gizmo():
            return
        if self._em_transacao_gizmo:
            self._on_gizmo_cancelado()
            return
        if self._em_transacao_mover:
            self._on_mover_cancelado()
            return
        self._chaves_sel = []
        self._recarregar_timeline()

    def _alternar_catalogo(self, visivel: bool) -> None:
        self.catalogo.setVisible(visivel)
        self.barra_superior.definir_visibilidade_paineis(
            catalogo=visivel,
            inspetor=self.inspetor.isVisible(),
        )

    def _alternar_inspetor(self, visivel: bool) -> None:
        self.inspetor.setVisible(visivel)
        self.barra_superior.definir_visibilidade_paineis(
            catalogo=self.catalogo.isVisible(),
            inspetor=visivel,
        )

    def gravar_pose_provisoria(self) -> bool:
        """Grava a pose provisória atual como chave da pista correspondente."""
        if not self.documento.provisoria.ativa or self._acao_atual is None:
            return False
        gravou = self.documento.gravar_provisoria_em_pista(
            self._acao_atual.secao_dados,
            self._acao_atual.chave_dados,
            variante=self._variante_atual,
        )
        self.banners.definir_provisoria(False)
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()
        return gravou

    def descartar_pose_provisoria(self) -> None:
        """Descarta ajustes fora de chave e restaura a pose interpolada da pista."""
        self.documento.descartar_provisoria()
        self.banners.definir_provisoria(False)
        self.sessao.reavaliar_quadro_atual()
        self._recarregar_paineis_visuais()

    def desfazer(self) -> str | None:
        """Desfaz a última operação validada e atualiza prévia e inspetor."""
        desc = self.documento.desfazer()
        if desc:
            self.sessao.reavaliar_quadro_atual()
            self._recarregar_paineis_visuais()
        return desc

    def refazer(self) -> str | None:
        """Refaz a operação desfeita mais recente e atualiza prévia e inspetor."""
        desc = self.documento.refazer()
        if desc:
            self.sessao.reavaliar_quadro_atual()
            self._recarregar_paineis_visuais()
        return desc

    def salvar_projeto(self, *, forcar: bool = False) -> bool:
        """Valida e grava alterações em ``animation.py``, exibindo status claro."""
        if not self._resolver_provisoria_para("salvar"):
            return False
        try:
            self.documento.salvar(forcar=forcar)
        except ConflitoArquivoExternoError as exc:
            self.banners.mostrar_erro(str(exc), permitir_recarregar=True)
            return False
        except Exception as exc:
            self.banners.mostrar_erro(f"Erro ao gravar: {exc}", permitir_recarregar=False)
            return False
        self.banners.limpar_erro()
        self.banners.mostrar_toast(f"Salvo em {self.documento.caminho.name}")
        self._atualizar_cabecalho_e_sujos()
        return True

    def recarregar_externa(self) -> None:
        """Recarrega o arquivo externo após modificação fora do editor."""
        self.documento.recarregar_externa()
        self.banners.limpar_erro()
        self._carregar_catalogo_inicial()
        self.banners.mostrar_toast("Versão externa recarregada.")

    def _acoes_sujas(self) -> set[str]:
        return calcular_ids_sujos(
            self.documento.salvo,
            self.documento.rascunho,
            self._acoes,
        )

    def _atualizar_cabecalho_e_sujos(self) -> None:
        nome = self._acao_atual.nome if self._acao_atual else "Editor do Mário"
        self.barra_superior.atualizar_titulo(
            nome,
            self._variante_atual,
            sujo=self.documento.sujo,
        )
        self.barra_superior.atualizar_historico(
            pode_desfazer=self.documento.pode_desfazer,
            desc_undo=self.documento.proxima_descricao_undo,
            pode_refazer=self.documento.pode_refazer,
            desc_redo=self.documento.proxima_descricao_redo,
        )
        self.catalogo.definir_sujos(self._acoes_sujas())

    def _recarregar_paineis_visuais(self) -> None:
        self._atualizar_cabecalho_e_sujos()
        self.inspetor.carregar_contexto(
            self._acao_atual,
            self.documento.rascunho,
            variante=self._variante_atual,
            roteiro=self.sessao.roteiro,
            tempo_s=self.sessao.tempo_s,
        )
        self._recarregar_timeline()
        self._sincronizar_quadro_ui()

    def _recarregar_timeline(self) -> None:
        if self._acao_atual is None:
            return
        bloco = self._bloco_visual_atual(self._acao_atual)
        pistas, efeitos = construir_pistas_para_acao(
            self._acao_atual.tipo_editor,
            bloco,
            acao_chave=self._acao_atual.chave_dados,
        )
        self.timeline.carregar_conteudo(
            pistas=pistas,
            efeitos=efeitos,
            estimulos=list(self.sessao.roteiro.ordenados()),
            pista_ativa=self._grupo_atual,
            chaves_selecionadas=self._chaves_sel,
            solo=self.sessao.pista_solo,
            silenciadas=self.sessao.pistas_silenciadas,
        )

    def _bloco_visual_atual(self, acao: AcaoCatalogo) -> dict[str, Any]:
        sec = self.documento.rascunho.get(acao.secao_dados, {})
        if not isinstance(sec, dict):
            return {}
        if acao.tipo_editor == "respiracao":
            return sec
        if ":" in acao.chave_dados:
            raiz, resto = acao.chave_dados.split(":", 1)
            sub = sec.get(raiz, {})
            return sub.get(resto, {}) if isinstance(sub, dict) else {}
        bloco = bloco_pistas_para_acao(self.documento.rascunho, acao, self._variante_atual)
        return bloco if bloco is not None else {}

    def _sincronizar_quadro_ui(self) -> None:
        quadro = self.sessao.ultimo_quadro
        quadro_salvo = (
            self.sessao.avaliar_quadro_salvo() if self._overlays.comparar_salvo else None
        )
        trilhas = None
        if self._overlays.trilhas:
            if self._modelo_trilha is None:
                from sejoga.nucleo.modelo import load_model
                from sejoga.nucleo.recursos import resolve_model

                self._modelo_trilha = load_model(resolve_model())
            trilhas = self.sessao.amostrar_trilha(
                self._modelo_trilha,
                self._grupo_atual,
            )
        self.viewport.sincronizar_quadro(
            quadro,
            controller=self.sessao._controller,
            quadro_salvo=quadro_salvo,
            obstaculo=self.sessao.roteiro.obstaculo,
            trilhas_pts=trilhas,
            dados_rascunho=self.documento.rascunho,
        )
        self._sincronizar_alvo_mover()
        self.barra_superior.atualizar_modo(quadro.modo, quadro.prioridade_contexto)
        eh_danca = self._acao_atual is not None and self._acao_atual.secao_dados == "DANCA"
        self.timeline.atualizar_tempo(
            tempo_s=quadro.tempo_s,
            duracao_s=quadro.duracao_s,
            quadro_idx=quadro.quadro_indice,
            fps=quadro.fps,
            bpm=quadro.bpm_efetivo,
            batida_ativa=quadro.batida_ativa,
            mostrar_batidas=eh_danca or self.sessao.roteiro.metronomo_ativo,
        )
        self._sincronizar_inspetor_junta()

    def _sincronizar_inspetor_junta(self) -> None:
        acao = self._acao_atual
        tem_chave = False
        curva = "quintic"
        if acao is not None and acao.tipo_editor == "pistas_3d":
            bloco = bloco_pistas_para_acao(
                self.documento.rascunho,
                acao,
                self._variante_atual,
            )
            if bloco is not None:
                chaves = tuple(bloco.get("tracks", {}).get(self._grupo_atual, ()))
                idx = indice_chave_proxima(chaves, self.sessao.tempo_s)
                tem_chave = idx is not None
                curvas = bloco.get("curvas", {}).get(self._grupo_atual, ())
                if idx is not None and curvas:
                    curva = str(curvas[min(idx, len(curvas) - 1)])
        chaves_sel_t: list[tuple[str, float]] = [
            (g, float(i)) for g, i in self._chaves_sel
        ]
        rot = _rotacao_local_graus(self.sessao.ultimo_quadro.pose, self._grupo_atual)
        self.inspetor.atualizar_junta_e_chaves(
            self._grupo_atual,
            rot,
            tem_chave_no_tempo=tem_chave,
            curva_atual=curva,
            chaves_selecionadas=chaves_sel_t,
        )

    def closeEvent(self, event: Any) -> None:
        """Solicita confirmação em alterações pendentes e salva preferências da janela."""
        if self._confirmar_pendencias and self.documento.sujo:
            resp = QMessageBox.question(
                self,
                "Alterações não salvas",
                "Existem alterações não salvas em rascunho. Salvar antes de sair?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if resp == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if resp == QMessageBox.StandardButton.Yes and not self.salvar_projeto():
                event.ignore()
                return
        self._timer_previa.stop()
        if self._musica_listener is not None:
            self._musica_listener.stop(timeout=0.5)
            self._musica_listener = None
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self._filtro_texto)
        self._salvar_layout()
        self.viewport.destruir()
        super().closeEvent(event)
