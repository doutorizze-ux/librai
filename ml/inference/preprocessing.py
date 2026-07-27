from __future__ import annotations

import numpy as np


SEQUENCE_LENGTH = 48
HAND_NODES = 21
TOTAL_NODES = 59


def preprocess_frames(frames: list[dict]) -> np.ndarray:
    indices = np.rint(
        np.linspace(0, len(frames) - 1, SEQUENCE_LENGTH)
    ).astype(np.int64)
    output = np.zeros((4, SEQUENCE_LENGTH, TOTAL_NODES), dtype=np.float32)
    for target_index, source_index in enumerate(indices):
        frame = frames[int(source_index)]
        unknown_offset = 0
        for hand in frame.get("hands", [])[:2]:
            side = hand.get("handedness")
            if side == "Left":
                offset = 0
            elif side == "Right":
                offset = HAND_NODES
            else:
                offset = unknown_offset
                unknown_offset = HAND_NODES
            for point_index, point in enumerate(hand.get("landmarks", [])[:21]):
                output[0, target_index, offset + point_index] = float(
                    point.get("x", 0)
                )
                output[1, target_index, offset + point_index] = float(
                    point.get("y", 0)
                )
                output[2, target_index, offset + point_index] = float(
                    point.get("z", 0)
                )
                output[3, target_index, offset + point_index] = 1

    presence = output[3] > 0
    for time_index in range(SEQUENCE_LENGTH):
        present = presence[time_index, :42]
        if not present.any():
            continue
        coordinates = output[:3, time_index, :42][:, present].copy()
        coordinates[:2] -= coordinates[:2].mean(axis=1, keepdims=True)
        scale = max(float(np.abs(coordinates[:2]).max()), 1e-4)
        coordinates /= scale
        output[:3, time_index, :42][:, present] = coordinates
    return output[np.newaxis, ...]
