import math


TARGET_FRAME_COUNT = 16
MIN_SEQUENCE_FRAMES = 12


def _vector(points, start, end):
    return [
        points[end].get("x", 0.0) - points[start].get("x", 0.0),
        points[end].get("y", 0.0) - points[start].get("y", 0.0),
        points[end].get("z", 0.0) - points[start].get("z", 0.0),
    ]


def _magnitude(vector):
    return math.sqrt(sum(component * component for component in vector))


def _angle(first, second):
    first_magnitude = _magnitude(first)
    second_magnitude = _magnitude(second)
    if first_magnitude == 0 or second_magnitude == 0:
        return 0.0
    cosine = sum(a * b for a, b in zip(first, second))
    cosine /= first_magnitude * second_magnitude
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def _angles(points):
    return [
        _angle(_vector(points, 0, 2), _vector(points, 2, 4)),
        _angle(_vector(points, 0, 5), _vector(points, 5, 8)),
        _angle(_vector(points, 0, 9), _vector(points, 9, 12)),
        _angle(_vector(points, 0, 13), _vector(points, 13, 16)),
        _angle(_vector(points, 0, 17), _vector(points, 17, 20)),
        _angle(_vector(points, 5, 8), _vector(points, 9, 12)),
        _angle(_vector(points, 9, 12), _vector(points, 13, 16)),
        _angle(_vector(points, 13, 16), _vector(points, 17, 20)),
    ]


def split_flat_landmarks(flat_landmarks):
    if not flat_landmarks:
        return []
    return [
        flat_landmarks[offset:offset + 21]
        for offset in range(0, len(flat_landmarks) - 20, 21)
    ]


def _resample(frames, target_count=TARGET_FRAME_COUNT):
    if len(frames) < MIN_SEQUENCE_FRAMES:
        return []
    if len(frames) == target_count:
        return frames
    last_index = len(frames) - 1
    return [
        frames[round(index * last_index / (target_count - 1))]
        for index in range(target_count)
    ]


def extract_temporal_signature(frames):
    sampled = _resample(frames)
    if not sampled or any(len(frame) != 21 for frame in sampled):
        return None

    origin = sampled[0][0]
    palm_scale = _magnitude(_vector(sampled[0], 0, 9))
    if palm_scale < 1e-6:
        return None

    signature = []
    for frame in sampled:
        wrist = frame[0]
        trajectory = [
            (wrist.get("x", 0.0) - origin.get("x", 0.0)) / palm_scale,
            (wrist.get("y", 0.0) - origin.get("y", 0.0)) / palm_scale,
            (wrist.get("z", 0.0) - origin.get("z", 0.0)) / palm_scale,
        ]
        signature.append((_angles(frame), trajectory))
    return signature


def temporal_distance(first, second):
    if not first or not second or len(first) != len(second):
        return math.inf

    shape_total = 0.0
    trajectory_total = 0.0
    for (first_angles, first_path), (second_angles, second_path) in zip(
        first,
        second,
    ):
        shape_total += math.sqrt(
            sum((a - b) ** 2 for a, b in zip(first_angles, second_angles)) / 8
        ) / 180.0
        trajectory_total += math.sqrt(
            sum((a - b) ** 2 for a, b in zip(first_path, second_path)) / 3
        )

    frame_count = len(first)
    # Forma e trajetória têm a mesma participação. Isso impede que uma
    # configuração manual idêntica apague a informação de movimento.
    return 0.5 * (shape_total / frame_count) + 0.5 * (
        trajectory_total / frame_count
    )


def _hand_slot(hand, fallback_index):
    handedness = str(hand.get("handedness", "Unknown"))
    if handedness in {"Left", "Right"}:
        return handedness
    # Compatibilidade defensiva: se o detector não classificar, mantém uma
    # ordem estável sem fundir as duas mãos.
    return "Left" if fallback_index == 0 else "Right"


def extract_two_hand_signature(frames):
    """Vetor temporal v2: presença, forma e trajetória de cada mão separada."""
    if not isinstance(frames, list):
        return None
    source_timestamps = [
        frame.get("timestamp_ms") for frame in frames if isinstance(frame, dict)
    ]
    if (
        len(source_timestamps) != len(frames)
        or any(not isinstance(value, int) for value in source_timestamps)
        or source_timestamps != sorted(source_timestamps)
        or len(source_timestamps) != len(set(source_timestamps))
    ):
        return None
    sampled = _resample(frames)
    if not sampled:
        return None

    normalized = []
    origins = {}
    scales = {}
    for frame in sampled:
        if not isinstance(frame, dict):
            return None
        timestamp = frame.get("timestamp_ms")
        hands = frame.get("hands")
        if not isinstance(timestamp, int) or not isinstance(hands, list):
            return None
        by_side = {}
        for index, hand in enumerate(hands[:2]):
            points = hand.get("landmarks") if isinstance(hand, dict) else None
            if not isinstance(points, list) or len(points) != 21:
                return None
            by_side[_hand_slot(hand, index)] = points

        frame_features = []
        for side in ("Left", "Right"):
            points = by_side.get(side)
            if points is None:
                frame_features.extend([0.0] * 12)
                continue
            if side not in origins:
                origins[side] = points[0]
                scales[side] = max(_magnitude(_vector(points, 0, 9)), 1e-6)
            wrist = points[0]
            origin = origins[side]
            scale = scales[side]
            frame_features.extend([
                1.0,
                *[angle / 180.0 for angle in _angles(points)],
                (wrist.get("x", 0.0) - origin.get("x", 0.0)) / scale,
                (wrist.get("y", 0.0) - origin.get("y", 0.0)) / scale,
                (wrist.get("z", 0.0) - origin.get("z", 0.0)) / scale,
            ])
        normalized.append(frame_features)
    return normalized


def two_hand_temporal_distance(first, second):
    if not first or not second or len(first) != len(second):
        return math.inf
    total = 0.0
    for frame_a, frame_b in zip(first, second):
        if len(frame_a) != 24 or len(frame_b) != 24:
            return math.inf
        total += math.sqrt(
            sum((a - b) ** 2 for a, b in zip(frame_a, frame_b)) / 24
        )
    return total / len(first)
