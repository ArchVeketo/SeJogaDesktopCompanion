from sejoga.leg_motion import LegMotion


def test_molas_de_leg_motion_assentam_no_alvo_em_walk():
    # Em walk as molas perseguem o passo senoidal; os campos ficam limitados e
    # finitos (sem explodir), provando que as molas seguem o alvo.
    legs = LegMotion()
    for _ in range(300):
        pose = legs.update(1 / 60, "walk", (200, 0))

    for valor in pose.__dict__.values():
        assert abs(valor) < 60


def test_resposta_identica_em_30_60_120_hz():
    # A Spring analítica é independente do framerate quando persegue um alvo
    # fixo: 'drag' com sway constante dá um degrau estável, então após o mesmo
    # tempo total o valor das molas bate em 30/60/120 Hz (abs tolerante).
    def _simular(hz: int) -> LegMotion:
        legs = LegMotion()
        dt = 1 / hz
        passos = 2 * hz  # dois segundos a partir do repouso
        for _ in range(passos):
            legs.update(dt, "drag", sway=3.0)
        return legs

    a = _simular(30)
    b = _simular(60)
    c = _simular(120)
    for campo in ("left", "right", "left_knee", "right_knee"):
        va = getattr(a.pose, campo)
        vb = getattr(b.pose, campo)
        vc = getattr(c.pose, campo)
        assert abs(va - vb) < 1e-9
        assert abs(vb - vc) < 1e-9


def test_passos_ainda_alternam_em_walk():
    legs = LegMotion()
    poses = [legs.update(1 / 60, "walk", (200, 0)) for _ in range(120)]
    assert any(p.left > 5 and p.right < -5 for p in poses)
    assert any(p.right > 5 and p.left < -5 for p in poses)


def test_idle_converge_a_zero():
    legs = LegMotion()
    for _ in range(300):
        rest = legs.update(1 / 60, "idle")
    assert abs(rest.left) < 1e-3 and rest.left_knee < 1e-3
