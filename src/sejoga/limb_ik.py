"""Two-link planar arm solver, angles in degrees, independent of rendering."""
from math import acos, atan2, cos, degrees, sin, sqrt


def solve_arm(horizontal, downward, upper_length, forearm_length):
    distance = sqrt(horizontal*horizontal+downward*downward)
    minimum = abs(upper_length-forearm_length)+1e-6
    maximum = upper_length+forearm_length-1e-6
    reach = max(minimum,min(maximum,distance))
    if distance > 1e-8:
        horizontal *= reach/distance
        downward *= reach/distance
    elbow = acos(max(-1,min(1,(reach*reach-upper_length**2-forearm_length**2)/(2*upper_length*forearm_length))))
    shoulder = atan2(downward,horizontal)-atan2(forearm_length*sin(elbow),upper_length+forearm_length*cos(elbow))
    return degrees(shoulder),degrees(elbow)
