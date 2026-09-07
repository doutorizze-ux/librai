import math

from temporal_recognition import holistic_temporal_distance


def _signature(progress):
    return [[float(value)] * 40 for value in progress]


def test_holistic_distance_aligns_the_same_motion_at_a_different_speed():
    reference = _signature(index / 15 for index in range(16))
    slower_start = _signature((index / 15) ** 2 for index in range(16))

    frame_by_frame = sum(
        math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)) / 40)
        for first, second in zip(reference, slower_start)
    ) / len(reference)
    aligned = holistic_temporal_distance(reference, slower_start)

    assert aligned < frame_by_frame
    assert holistic_temporal_distance(reference, reference) == 0.0


def test_holistic_distance_does_not_hide_a_reversed_motion():
    forward = _signature(index / 15 for index in range(16))
    slower_forward = _signature((index / 15) ** 2 for index in range(16))
    reversed_motion = _signature(1 - index / 15 for index in range(16))

    assert holistic_temporal_distance(
        forward,
        slower_forward,
    ) < holistic_temporal_distance(forward, reversed_motion)
