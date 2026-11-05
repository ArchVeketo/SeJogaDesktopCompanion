"""Authored idle phrases sampled in degrees; independent of the renderer.

These are runtime keyframes, not clips exported from Blockbench. Each track
starts and ends at zero; the relaxed base pose remains underneath the phrase.
"""

from dataclasses import dataclass
from math import cos, sin, tau


@dataclass(frozen=True)
class IdleClip:
    duration: float
    tracks: dict[str, tuple[tuple[float, tuple[float, float, float]], ...]]


def sample_track(keys, time):
    """Quintic easing keeps velocity and acceleration continuous at holds."""
    if time <= keys[0][0]:
        return keys[0][1]
    for (start, a), (end, b) in zip(keys, keys[1:]):
        if time <= end:
            u = (time - start) / (end - start)
            blend = u * u * u * (u * (u * 6 - 15) + 10)
            return tuple(x + (y - x) * blend for x, y in zip(a, b))
    return keys[-1][1]


def phrase(*keys):
    return ((0.0, (0, 0, 0)), *keys, (10.0, (0, 0, 0)))


# Local axes: X pitches forward, Y turns, Z rolls. Mirrored arms need
# opposite roll signs. The hands remain children of the original forearms.
CLIPS = {
    "street": IdleClip(10.0, {
        "body": phrase((1.0, (0, 0, 0)), (1.8, (3, -7, -3)), (2.6, (1, 7, 3)),
                       (3.4, (2, -5, -2)), (4.5, (0, 0, 0))),
        "head": phrase((1.2, (0, 0, 0)), (2.0, (-3, 9, 3)), (2.8, (1, -7, -2)),
                       (3.6, (-2, 5, 2)), (4.8, (0, 0, 0))),
        "right-arm": phrase((1.2, (0, 0, 0)), (2.0, (-24, 0, -34)),
                            (2.8, (8, 0, 13)), (3.6, (-10, 0, -22)), (4.8, (0, 0, 0))),
        "left-arm": phrase((1.2, (0, 0, 0)), (2.0, (6, 0, 8)),
                           (2.8, (-16, 0, 24)), (3.6, (8, 0, -6)), (4.8, (0, 0, 0))),
        "ant-arm": phrase((1.4, (0, 0, 0)), (2.2, (-14, 0, -18)),
                          (3.0, (8, 0, 8)), (3.8, (-8, 0, -12)), (5.0, (0, 0, 0))),
        "ant-arm2": phrase((1.4, (0, 0, 0)), (2.2, (7, 0, -5)),
                           (3.0, (-12, 0, 16)), (3.8, (7, 0, 2)), (5.0, (0, 0, 0))),
        "hand": phrase((1.6, (0, 0, 0)), (2.4, (-4, 0, 8)),
                       (3.2, (3, 0, -4)), (4.0, (-2, 0, 4)), (5.2, (0, 0, 0))),
    }),
    "fighter": IdleClip(10.0, {
        "body": phrase((1.0, (0, 0, 0)), (1.6, (3, 8, -2)),
                       (2.0, (2, 8, -2)), (2.7, (-2, -8, 2)), (3.5, (-2, -8, 2)),
                       (4.8, (0, 0, 0))),
        "head": phrase((1.1, (0, 0, 0)), (1.7, (2, -10, 2)),
                       (2.1, (2, -10, 2)), (2.9, (-5, 12, -3)),
                       (3.6, (-5, 12, -3)), (4.9, (0, 0, 0))),
        "right-arm": phrase((1.2, (0, 0, 0)), (1.8, (-20, 0, -28)),
                            (2.2, (-20, 0, -28)), (2.9, (-8, 0, -12)), (4.9, (0, 0, 0))),
        "left-arm": phrase((2.6, (0, 0, 0)), (3.15, (-8, 0, 18)),
                           (3.55, (-8, 0, 18)), (4.2, (0, 0, 0)), (5.0, (0, 0, 0))),
        "ant-arm": phrase((1.35, (0, 0, 0)), (1.95, (-24, 0, -22)),
                          (2.3, (-24, 0, -22)), (3.1, (-8, 0, -6)), (5.0, (0, 0, 0))),
        "fingers": phrase((1.3, (0, 0, 0)), (1.9, (0, 0, 20)),
                          (2.3, (0, 0, 20)), (3.0, (0, 0, -8)), (4.7, (0, 0, 0))),
        "hand": phrase((1.5, (0, 0, 0)), (2.1, (-8, 0, 8)),
                       (3.0, (0, 0, -10)), (4.8, (0, 0, 0))),
    }),
    "rhythm": IdleClip(10.0, {
        "right-arm": phrase((2.0, (0, 0, 0)), (2.6, (-8, 0, -15)),
                            (3.0, (-8, 0, -15)), (3.6, (0, 0, 0))),
        "ant-arm": phrase((2.1, (0, 0, 0)), (2.7, (-12, 0, -8)),
                          (3.1, (-12, 0, -8)), (3.8, (0, 0, 0))),
        "hand": phrase((2.3, (0, 0, 0)), (2.8, (0, 0, 14)),
                       (3.05, (0, 0, -4)), (3.4, (0, 0, 8)), (4.0, (0, 0, 0))),
        "fingers": phrase((2.3, (0, 0, 0)), (2.8, (0, 0, -8)),
                          (3.05, (0, 0, 12)), (3.5, (0, 0, 0))),
    }),
    "stylish": IdleClip(10.0, {
        "body": phrase((1.0, (0, 0, 0)), (1.8, (0, -10, -3)),
                       (3.2, (0, -10, -3)), (4.6, (0, 0, 0))),
        "head": phrase((1.1, (0, 0, 0)), (1.9, (-5, 16, 5)),
                       (3.3, (-5, 16, 5)), (4.9, (0, 0, 0))),
        "right-arm": phrase((1.25, (0, 0, 0)), (2.0, (-10, 0, -25)),
                            (3.4, (-10, 0, -25)), (4.9, (0, 0, 0))),
        "ant-arm": phrase((1.4, (0, 0, 0)), (2.15, (-18, 0, -12)),
                          (3.5, (-18, 0, -12)), (5.1, (0, 0, 0))),
        "hand": phrase((1.55, (0, 0, 0)), (2.3, (0, 12, -14)),
                       (3.6, (0, 12, -14)), (5.3, (0, 0, 0))),
        "fingers": phrase((1.65, (0, 0, 0)), (2.4, (0, 0, -8)),
                          (3.7, (0, 0, -8)), (5.4, (0, 0, 0))),
    }),
}


def sample_idle(style: str, time: float) -> dict[str, tuple[float, float, float]]:
    clip = CLIPS[style]
    local = time % clip.duration
    # Elbows stay softly bent and the hands sit closer to the torso at rest.
    pose = {
        "body": (sin(time * .8) * .7, 0, -1.5),
        "head": (0, sin(time * .36) * 2, 1.5),
        "right-arm": (-4, 0, 62), "left-arm": (-2, 0, -64),
        "ant-arm": (-8, 0, -22), "ant-arm2": (-6, 0, 20),
    }
    if style == "fighter":
        pose.update({"body": (3, 5, -2), "head": (1, -5, 2),
        "right-arm": (-16, 0, 58), "left-arm": (-12, 0, -62),
        "ant-arm": (-23, 0, -30), "ant-arm2": (-18, 0, 25),
                     "fingers": (0, 0, 22), "fingers2": (0, 0, -20)})
    elif style == "stylish":
        pose.update({"body": (-2, 3, -2), "head": (-3, -4, 3),
                     "right-arm": (-10, 0, 46), "left-arm": (-2, 0, -64),
                     "ant-arm": (-16, 0, -28), "ant-arm2": (-8, 0, 18),
                     "hand": (0, 12, -8)})
    elif style == "rhythm":
        # Internal cadence at 100 BPM, not a claim of synchronization to audio.
        beat = tau * time / .6
        pulse = (1 - cos(beat)) * .5
        pose["body"] = (pulse * 2.0, 0, sin(beat * .25) * 2.0)
        pose["head"] = (-1 + (1 - cos(beat - .28)), 0, 0)
        pose["right-arm"] = (-8 + sin(beat - .45) * 5, 0, 60 - pulse * 23)
        pose["left-arm"] = (-6 - sin(beat - .45) * 5, 0, -64 + pulse * 20)
    for group, keys in clip.tracks.items():
        delta = sample_track(keys, local)
        base = pose.get(group, (0, 0, 0))
        pose[group] = tuple(a + b for a, b in zip(base, delta))
    return pose
