from sejoga.dance_motion import DanceMotion


def test_styles_follow_sustained_energy_and_bass_not_single_peak():
    dance = DanceMotion()
    dance.update(.02, 1, 1, 120, True)
    assert dance.style == 'head_bob'

    for _ in range(600):
        dance.update(1/60, .5, .3, 95)
    assert dance.style == 'hip_hop'
    for _ in range(600):
        dance.update(1/60, .95, .7, 150)
    assert dance.style == 'breakdance'
    for _ in range(600):
        dance.update(1/60, .08, .01, 75)
    assert dance.style == 'head_bob'


def test_shared_phase_keeps_leg_targets_independent_of_internal_clock():
    from sejoga.leg_motion import LegMotion
    first, second = LegMotion(), LegMotion()
    second.phase = 50
    for i in range(120):
        phase = i/60*6.28
        a = first.update(1/60, 'dance', dance_phase=phase, dance_strength=.2)
        b = second.update(1/60, 'dance', dance_phase=phase, dance_strength=.2)
        assert a == b
