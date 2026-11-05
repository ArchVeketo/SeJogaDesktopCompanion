from math import cos, isfinite, radians, sin
import pytest
from sejoga.limb_ik import solve_arm


@pytest.mark.parametrize('x,y',[(.16,.17),(.08,.22),(-.06,.15)])
def test_planar_solver_reaches_requested_point(x,y):
    shoulder,elbow=map(radians,solve_arm(x,y,.125,.15625))
    assert .125*cos(shoulder)+.15625*cos(shoulder+elbow)==pytest.approx(x,abs=1e-6)
    assert .125*sin(shoulder)+.15625*sin(shoulder+elbow)==pytest.approx(y,abs=1e-6)


def test_unreachable_target_is_clamped_without_invalid_angles():
    angles=solve_arm(5,5,.125,.15625)
    assert all(isfinite(angle) for angle in angles)
