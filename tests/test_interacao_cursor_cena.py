"""Testes da máquina pura de interação segura com o cursor nas cenas narrativas."""

from __future__ import annotations

from sejoga.animacao.interacao_cursor_cena import (
    LIMIAR_PUXAO_ESCAPE_PX,
    MAX_DURACAO_RETENCAO_S,
    ControladorCursorCena,
)


def _chamar(
    ctrl: ControladorCursorCena,
    *,
    dt: float = 1 / 60,
    cena: str = "cacar_cursor_sucesso",
    t: float = 1.75,
    cursor: tuple[float, float] = (500.0, 540.0),
    centro: tuple[float, float] = (500.0, 500.0),
    raio: float = 180.0,
    clicou: bool = False,
    esc: bool = False,
    digitando: bool = False,
):
    return ctrl.atualizar(
        dt,
        cena_nome=cena,
        cena_tempo=t,
        cursor_atual=cursor,
        mascote_centro=centro,
        raio_proximidade_px=raio,
        ponto_chao=(500.0, 560.0),
        ponto_palma=(508.0, 490.0),
        ponto_boca=(500.0, 460.0),
        clicou=clicou,
        tecla_escape=esc,
        digitando=digitando,
    )


def test_ignora_cursor_longe_sem_teletransportar() -> None:
    ctrl = ControladorCursorCena()
    cmd = _chamar(ctrl, t=0.2, cursor=(1400.0, 200.0), centro=(500.0, 500.0), raio=180.0)
    assert cmd.mover_para is None
    cmd2 = _chamar(ctrl, t=2.0, cursor=(1400.0, 200.0), centro=(500.0, 500.0), raio=180.0)
    assert cmd2.mover_para is None
    assert not cmd2.ocultar_cursor


def test_escape_imediato_ao_puxar_mouse_rapido() -> None:
    ctrl = ControladorCursorCena()
    cmd1 = _chamar(ctrl, t=1.80, cursor=(500.0, 540.0))
    assert cmd1.mover_para is not None
    # Usuário puxa o mouse além do limiar em 1 quadro
    imp_x, imp_y = cmd1.mover_para
    cmd2 = _chamar(
        ctrl,
        t=1.82,
        cursor=(imp_x + LIMIAR_PUXAO_ESCAPE_PX + 8.0, imp_y),
    )
    assert cmd2.encerrado_por_escape
    assert cmd2.converter_para_falha
    assert cmd2.mover_para is None
    assert not cmd2.ocultar_cursor


def test_roubo_oculta_na_mastigacao_e_libera_no_esc_ou_teto() -> None:
    ctrl = ControladorCursorCena()
    # Fase de puxão até a boca
    c_puxa = _chamar(ctrl, cena="roubo_cursor_tentaculo", t=0.90, cursor=(505.0, 470.0))
    assert c_puxa.mover_para is not None
    assert not c_puxa.ocultar_cursor
    # Fase de mastigação de porta fechada
    c_mast = _chamar(ctrl, cena="roubo_cursor_tentaculo", t=1.80, cursor=c_puxa.mover_para)
    assert c_mast.ocultar_cursor
    # Apertou ESC -> restaura visibilidade imediatamente!
    c_esc = _chamar(ctrl, cena="roubo_cursor_tentaculo", t=1.85, cursor=c_mast.mover_para or (500.0, 460.0), esc=True)
    assert c_esc.encerrado_por_escape
    assert not c_esc.ocultar_cursor


def test_teto_maximo_de_retencao_nunca_excede_limite() -> None:
    ctrl = ControladorCursorCena()
    pos = (500.0, 540.0)
    cmd = _chamar(ctrl, dt=0.5, t=1.75, cursor=pos)
    for step in range(10):
        pos = cmd.mover_para or pos
        cmd = _chamar(ctrl, dt=0.35, t=1.80 + step * 0.2, cursor=pos)
        if cmd.encerrado_por_escape:
            break
    assert ctrl.tempo_retido_s <= MAX_DURACAO_RETENCAO_S + 0.36
    assert cmd.encerrado_por_escape
