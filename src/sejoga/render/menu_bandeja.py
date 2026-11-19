"""Menu de contexto compacto do mascote (clique direito direto no Mário — v2.0).

Mantém o menu da bandeja do sistema com todas as prévias e diagnósticos,
enquanto clicar com o botão direito diretamente no Mário abre um menu rápido,
limpo e humano com as ações essenciais do dia a dia.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMenu


def criar_menu_contexto_mascote(app) -> QMenu:
    """Cria o menu rápido exibido ao clicar com o botão direito no Mário."""
    menu = QMenu()

    danca = menu.addMenu("Dançar agora")
    for estilo, rotulo in (
        ("funk_glide", "Funk glide (v2.0)"),
        ("cyber_skank", "Cyber skank (v2.0)"),
        ("walkman_shuffle", "Walkman shuffle (v2.0)"),
        ("street_groove", "Street groove"),
        ("graffiti_dance", "Graffiti dance"),
        ("cyber_bounce", "Cyber bounce"),
        ("hip_hop", "Hip hop"),
        ("rock", "Rock"),
        ("electro_swing", "Electro Swing"),
        ("passinho", "Passinho"),
    ):
        danca.addAction(rotulo).triggered.connect(
            lambda _checked=False, s=estilo: (
                app.animation_controller.preview_dance(s)
                if app.animation_controller
                else None
            )
        )

    acoes = menu.addMenu("Ações & Cenas")
    for rotulo, kind in (
        ("Comemorar", "celebrate"),
        ("Conferir o estilo (v2.0)", "conferir_estilo"),
        ("Espreguiçar pesado (v2.0)", "espreguicar_pesado"),
        ("Olhar curioso no chão (v2.0)", "olhar_curioso_chao"),
        ("Acenar", "wave"),
        ("Mostrar tentáculos", "peek"),
        ("Espirro de tentáculos", "sneeze"),
        ("Argolas da antena", "argolas_antena"),
        ("Checar Walkman", "checar_walkman"),
    ):
        acoes.addAction(rotulo).triggered.connect(
            lambda _checked=False, k=kind: (
                app.animation_controller.interact(k)
                if app.animation_controller
                else None
            )
        )

    menu.addAction("Caminhar até o mouse").triggered.connect(
        lambda _checked=False: app.caminhar_ate_mouse()
    )
    menu.addAction("Dormir / Acordar").triggered.connect(
        lambda _checked=False: _alternar_sono(app)
    )
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


def _alternar_sono(app) -> None:
    ctrl = getattr(app, "animation_controller", None)
    if ctrl is None:
        return
    if ctrl.state is not None and ctrl.state.value == "sleep":
        ctrl.acordar()
    else:
        ctrl.colocar_para_dormir("sentado")
