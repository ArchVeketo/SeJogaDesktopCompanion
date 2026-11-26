"""Menu de contexto compacto do mascote (clique direito direto no Mário — v2.0).

Mantém o menu da bandeja do sistema com ações e diagnósticos completos,
enquanto clicar com o botão direito diretamente no Mário abre um menu rápido,
limpo e humano com as 8 ações essenciais do dia a dia.
"""

from __future__ import annotations

from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QMenu

from sejoga.catalogos_ui import (
    ACOES_RAPIDAS_MASCOTE_UI,
    ESTILOS_DANCA_RAPIDOS_MASCOTE,
    FILTROS_VISUAIS_UI,
    PALETAS_VFX_UI,
)


def _adicionar_grupo_acoes(menu: QMenu, itens, selecionado_fn, ao_acionar):
    """Adiciona um grupo exclusivo de ações marcáveis ao menu e retorna (grupo, mapa)."""
    grupo = QActionGroup(menu)
    grupo.setExclusive(True)
    acoes = {}
    for key, rotulo in itens:
        act = menu.addAction(rotulo)
        act.setCheckable(True)
        act.setChecked(bool(selecionado_fn(key)))
        grupo.addAction(act)
        act.triggered.connect(lambda _checked=False, k=key: ao_acionar(k))
        acoes[key] = act
    return grupo, acoes


def popular_menu_visual(menu: QMenu, app, *, registrar_grupo: str) -> None:
    """Preenche um submenu de Visual & Efeitos com ações marcáveis sincronizadas."""
    filtro_atual = getattr(app.settings.window, "visual_filter", "padrao")
    paleta_atual = getattr(app.settings.window, "vfx_palette", "auto")
    vfx_ativo = bool(getattr(app.settings.window, "vfx_enabled", True))

    filtros_menu = [(k, f"Filtro: {rotulo}") for k, rotulo in FILTROS_VISUAIS_UI]
    paletas_menu = [(k, f"VFX: {rotulo}" if k == "auto" else f"Ilustração extra: {rotulo}") for k, rotulo in PALETAS_VFX_UI]

    _, f_actions = _adicionar_grupo_acoes(
        menu, filtros_menu, lambda k: k == filtro_atual, app._set_visual_filter
    )
    menu.addSeparator()
    p_group, p_actions = _adicionar_grupo_acoes(
        menu, paletas_menu, lambda k: vfx_ativo and k == paleta_atual, app._set_vfx_palette
    )

    off_act = menu.addAction("Desligar efeitos")
    off_act.setCheckable(True)
    off_act.setChecked(not vfx_ativo)
    p_group.addAction(off_act)
    off_act.triggered.connect(lambda _checked=False: app._set_vfx_enabled(False))

    if not hasattr(app, "_visual_menu_registries"):
        app._visual_menu_registries = {}
    app._visual_menu_registries[registrar_grupo] = (f_actions, p_actions, off_act)


def criar_menu_contexto_mascote(app) -> QMenu:
    """Cria o menu rápido (8 itens raiz) exibido ao clicar com o botão direito no Mário."""
    menu = QMenu()

    danca = menu.addMenu("Dançar agora")
    for estilo, rotulo in ESTILOS_DANCA_RAPIDOS_MASCOTE:
        danca.addAction(rotulo).triggered.connect(
            lambda _checked=False, s=estilo: (
                app.animation_controller.preview_dance(s)
                if app.animation_controller
                else None
            )
        )

    acoes = menu.addMenu("Ações & Cenas")
    for kind, rotulo in ACOES_RAPIDAS_MASCOTE_UI:
        acoes.addAction(rotulo).triggered.connect(
            lambda _checked=False, k=kind: (
                app.animation_controller.interact(k)
                if app.animation_controller
                else None
            )
        )

    movimento = menu.addMenu("Movimento")
    walk_mouse_act = movimento.addAction("Caminhar até o mouse")
    walk_mouse_act.triggered.connect(lambda _checked=False: app.caminhar_ate_mouse())
    jump_act = movimento.addAction("Pular")
    jump_act.triggered.connect(lambda _checked=False: app.pular_mascote())
    movimento.addAction("Sentar / Levantar").triggered.connect(
        lambda _checked=False: _alternar_sentado(app)
    )
    if hasattr(app, "_registrar_acoes_fisica"):
        app._registrar_acoes_fisica(walk_mouse_act, jump_act)

    menu.addAction("Dormir / Acordar").triggered.connect(
        lambda _checked=False: _alternar_sono(app)
    )

    visual = menu.addMenu("Visual & Efeitos")
    popular_menu_visual(visual, app, registrar_grupo="context")

    menu.addSeparator()
    menu.addAction("Configurações...").triggered.connect(
        lambda _checked=False: app.open_settings_dialog()
    )
    menu.addAction("Ocultar Mário").triggered.connect(
        lambda _checked=False: app.toggle_visibility()
    )
    menu.addAction("Encerrar").triggered.connect(
        lambda _checked=False: app.quit_app()
    )
    return menu


def _alternar_sentado(app) -> None:
    ctrl = getattr(app, "animation_controller", None)
    if ctrl is None:
        return
    ctrl.alternar_sentado()


def _alternar_sono(app) -> None:
    ctrl = getattr(app, "animation_controller", None)
    if ctrl is None:
        return
    if ctrl.state is not None and ctrl.state.value == "sleep":
        ctrl.acordar()
    else:
        ctrl.colocar_para_dormir("sentado")
