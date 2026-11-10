"""Gestos devem pertencer ao mascote antes de provocar efeitos no desktop."""

from sejoga.animacao.interacao_mouse import MouseInteraction


def kinds(mouse, position=(100, 100), buttons=(), **kwargs):
    return [
        event.kind for event in mouse.update(position, frozenset(buttons), **kwargs)
    ]


def test_external_press_never_becomes_drag_or_click():
    mouse = MouseInteraction()
    kinds(mouse, buttons=("left",), hit=False)
    assert kinds(mouse, buttons=("left",), hit=True) == ["hover_enter"]
    assert kinds(mouse, (180, 100), ("left",), hit=True) == []
    assert kinds(mouse, (180, 100), hit=True) == []


def test_click_tolerates_small_hand_movement():
    mouse = MouseInteraction()
    kinds(mouse, buttons=("left",), hit=True)
    assert kinds(mouse, (102, 101), ("left",), hit=True) == []
    assert kinds(mouse, (102, 101), hit=True) == ["poke"]


def test_drag_continues_and_ends_outside_without_click():
    mouse = MouseInteraction()
    kinds(mouse, buttons=("left",), hit=True)
    assert kinds(mouse, (130, 100), ("left",), hit=False) == [
        "hover_exit",
        "drag_start",
        "drag_move",
    ]
    assert kinds(mouse, (230, 100), hit=False) == ["drag_end"]
    assert not mouse.dragging
    assert not mouse.has_press


def test_releasing_outside_does_not_click():
    mouse = MouseInteraction()
    kinds(mouse, buttons=("left",), hit=True)
    assert kinds(mouse, hit=False) == ["hover_exit"]


def test_cancel_hidden_overlay_requires_new_press():
    mouse = MouseInteraction()
    kinds(mouse, buttons=("left",), hit=True)
    kinds(mouse, (130, 100), ("left",), hit=True)
    assert kinds(mouse, (130, 100), ("left",), hit=True, enabled=False) == [
        "hover_exit",
        "drag_cancel",
    ]
    assert kinds(mouse, (130, 100), ("left",), hit=True) == ["hover_enter"]
    assert kinds(mouse, (130, 100), hit=True) == []


def test_disabled_drag_does_not_turn_long_gesture_into_click():
    mouse = MouseInteraction()
    kinds(mouse, buttons=("left",), hit=True, allow_drag=False)
    assert kinds(mouse, (150, 100), ("left",), hit=True, allow_drag=False) == []
    assert kinds(mouse, hit=True, allow_drag=False) == []


def test_reaction_buttons_and_click_setting():
    mouse = MouseInteraction()
    for button, reaction in (("right", "pet"), ("middle", "click")):
        kinds(mouse, buttons=(button,), hit=True)
        assert kinds(mouse, hit=True) == [reaction]
        kinds(mouse, buttons=(button,), hit=True)
        assert kinds(mouse, hit=True, allow_click=False) == []


def test_starting_app_with_button_held_does_not_own_it():
    mouse = MouseInteraction(buttons=frozenset({"left"}))
    assert kinds(mouse, buttons=("left",), hit=True) == ["hover_enter"]
    assert kinds(mouse, hit=True) == []


def test_secondary_button_during_drag_does_not_trigger_pet_on_release():
    mouse = MouseInteraction()
    kinds(mouse, buttons=("left",), hit=True)
    kinds(mouse, (130, 100), ("left", "right"), hit=True)
    assert kinds(mouse, (130, 100), hit=True) == ["drag_end"]


def test_owned_double_click_uses_time_and_distance_thresholds():
    mouse = MouseInteraction(double_click_seconds=0.4, double_click_distance=5)
    kinds(mouse, buttons=("left",), hit=True, now=0)
    assert kinds(mouse, hit=True, now=0.05) == ["poke"]
    kinds(mouse, (102, 100), ("left",), hit=True, now=0.15)
    assert kinds(mouse, (102, 100), hit=True, now=0.20) == ["double_click"]
    kinds(mouse, buttons=("left",), hit=True, now=0.25)
    assert kinds(mouse, hit=True, now=0.30) == ["poke"]
    kinds(mouse, buttons=("left",), hit=True, now=1)
    assert kinds(mouse, hit=True, now=1.05) == ["poke"]
    kinds(mouse, (120, 100), ("left",), hit=True, now=1.1)
    assert kinds(mouse, (120, 100), hit=True, now=1.15) == ["poke"]


def test_drag_or_external_press_cannot_complete_double_click():
    mouse = MouseInteraction()
    kinds(mouse, buttons=("left",), hit=True, now=0)
    kinds(mouse, hit=True, now=0.02)
    kinds(mouse, buttons=("left",), hit=False, now=0.04)
    kinds(mouse, hit=True, now=0.06)
    kinds(mouse, buttons=("left",), hit=True, now=0.08)
    assert kinds(mouse, hit=True, now=0.10) == ["poke"]
    kinds(mouse, buttons=("left",), hit=True, now=0.12)
    kinds(mouse, (160, 100), ("left",), hit=True, now=0.14)
    assert kinds(mouse, (160, 100), hit=True, now=0.16) == ["drag_end"]
