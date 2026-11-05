from sejoga.dance_motion import DanceMotion


def test_styles_follow_sustained_energy_and_bass_not_single_peak():
    dance = DanceMotion()
    dance.update(.02, 1, 1, 120, True)
    assert dance.style == 'head_bob'
    for _ in range(300):
        dance.update(1/60, .5, .3, 95)
    assert dance.style == 'hip_hop'
    for _ in range(300):
        dance.update(1/60, .95, .7, 150)
    assert dance.style == 'breakdance'
    for _ in range(400):
        dance.update(1/60, .08, .01, 75)
    assert dance.style == 'head_bob'
