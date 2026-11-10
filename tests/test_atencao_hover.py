from sejoga.animacao.atencao_hover import HoverAttention


def test_external_interactions_suspend_hover_until_idle():
    attention = HoverAttention()
    assert attention.update(1)
    assert not attention.update(2, external_press=True)
    assert not attention.update(2.5)
    assert attention.update(3.1)
    assert not attention.update(4, typing=True)
    assert not attention.update(5, busy_cursor=True)
    assert not attention.update(6, focus_changed=True)
    assert attention.update(7.1)
