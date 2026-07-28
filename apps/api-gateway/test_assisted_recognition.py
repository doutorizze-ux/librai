import numpy as np
import pytest

from assisted_recognition import (
    build_motion_features,
    frames_to_coordinates,
    rank_candidates,
    resample_sequence,
)


def _hand(handedness: str, wrist_x: float) -> dict:
    return {
        "handedness": handedness,
        "score": 0.99,
        "landmarks": [
            {
                "x": wrist_x + index / 1000,
                "y": index / 100,
                "z": -index / 1000,
            }
            for index in range(21)
        ],
    }


def test_frames_to_coordinates_preserves_left_right_slots():
    result = frames_to_coordinates(
        [
            {
                "timestamp_ms": 1,
                "hands": [_hand("Right", 0.8), _hand("Left", 0.2)],
            }
        ]
    ).reshape(1, 2, 21, 3)

    assert result.shape == (1, 2, 21, 3)
    assert result[0, 0, 0, 0] == pytest.approx(0.2)
    assert result[0, 1, 0, 0] == pytest.approx(0.8)


def test_unknown_handedness_uses_screen_position_without_losing_a_hand():
    result = frames_to_coordinates(
        [
            {
                "timestamp_ms": 1,
                "hands": [_hand("Unknown", 0.75), _hand("Unknown", 0.25)],
            }
        ]
    ).reshape(1, 2, 21, 3)

    assert result[0, 0, 0, 0] == pytest.approx(0.25)
    assert result[0, 1, 0, 0] == pytest.approx(0.75)


def test_resampling_and_motion_features_have_model_shape():
    sequence = np.arange(12 * 126, dtype=np.float32).reshape(12, 126)
    sampled = resample_sequence(sequence, 64)
    features = build_motion_features(
        sampled,
        np.zeros(126, dtype=np.float32),
        np.ones(126, dtype=np.float32),
    )

    assert sampled.shape == (64, 126)
    assert features.shape == (64, 378)
    assert np.allclose(features[0, 126:], 0)


def test_rank_candidates_groups_duplicate_display_labels():
    candidates = rank_candidates(
        np.asarray([2.0, 1.5, 1.0, 0.0], dtype=np.float32),
        ["BOM", "BOM", "TARDE", "NOITE"],
    )

    assert len(candidates) == 3
    assert candidates[0]["label"] == "BOM"
    assert 0 <= candidates[0]["confidence"] <= 1
    assert sum(item["confidence"] for item in candidates) <= 1.000001


def test_empty_sequence_is_rejected():
    with pytest.raises(ValueError):
        resample_sequence(np.empty((0, 126), dtype=np.float32))
