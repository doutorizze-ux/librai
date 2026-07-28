from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

import numpy as np


MODEL_NAME = "motion_tcn_v1"
FRAME_COUNT = 64
RAW_FEATURE_COUNT = 126
_recognizer = None
_recognizer_lock = threading.Lock()


def _model_directory() -> Path:
    configured = os.getenv("ASSISTED_MODEL_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / "model_artifacts" / MODEL_NAME


def _point_values(point: dict[str, Any]) -> tuple[float, float, float]:
    return (
        float(point.get("x", 0.0)),
        float(point.get("y", 0.0)),
        float(point.get("z", 0.0)),
    )


def frames_to_coordinates(frames: list[dict[str, Any]]) -> np.ndarray:
    """Convert structured MediaPipe frames to Left/Right 21x3 coordinates."""
    sequence = np.zeros((len(frames), 2, 21, 3), dtype=np.float32)
    for frame_index, frame in enumerate(frames):
        hands = frame.get("hands")
        if not isinstance(hands, list):
            continue
        occupied: set[int] = set()
        unknown = []
        for hand in hands[:2]:
            if not isinstance(hand, dict):
                continue
            handedness = str(hand.get("handedness", "Unknown"))
            slot = 0 if handedness == "Left" else 1 if handedness == "Right" else None
            if slot is None or slot in occupied:
                unknown.append(hand)
                continue
            points = hand.get("landmarks")
            if isinstance(points, list) and len(points) == 21:
                sequence[frame_index, slot] = np.asarray(
                    [_point_values(point) for point in points],
                    dtype=np.float32,
                )
                occupied.add(slot)

        for hand in unknown:
            available = [slot for slot in (0, 1) if slot not in occupied]
            if not available:
                break
            points = hand.get("landmarks")
            if not isinstance(points, list) or len(points) != 21:
                continue
            wrist_x = float(points[0].get("x", 0.5))
            preferred = 0 if wrist_x <= 0.5 else 1
            slot = preferred if preferred in available else available[0]
            sequence[frame_index, slot] = np.asarray(
                [_point_values(point) for point in points],
                dtype=np.float32,
            )
            occupied.add(slot)
    return sequence.reshape(len(frames), RAW_FEATURE_COUNT)


def resample_sequence(sequence: np.ndarray, frame_count: int = FRAME_COUNT) -> np.ndarray:
    if sequence.ndim != 2 or len(sequence) == 0:
        raise ValueError("A sequência precisa conter ao menos um quadro.")
    positions = np.linspace(0, len(sequence) - 1, frame_count, dtype=np.float32)
    left = np.floor(positions).astype(np.int64)
    right = np.minimum(left + 1, len(sequence) - 1)
    alpha = (positions - left)[:, None]
    return (
        sequence[left] * (1.0 - alpha) + sequence[right] * alpha
    ).astype(np.float32)


def build_motion_features(
    sequence: np.ndarray,
    mean: np.ndarray,
    std: np.ndarray,
) -> np.ndarray:
    normalized = (sequence - mean.reshape(1, RAW_FEATURE_COUNT)) / std.reshape(
        1, RAW_FEATURE_COUNT
    )
    velocity = np.diff(normalized, axis=0, prepend=normalized[:1])
    acceleration = np.diff(velocity, axis=0, prepend=velocity[:1])
    return np.concatenate(
        (normalized, velocity, acceleration),
        axis=1,
    ).astype(np.float32)


def rank_candidates(
    logits: np.ndarray,
    labels: list[str],
    limit: int = 3,
) -> list[dict[str, float | str]]:
    values = np.asarray(logits, dtype=np.float64).reshape(-1)
    if len(values) != len(labels):
        raise ValueError("A saída do modelo não corresponde aos rótulos.")
    values -= values.max()
    probabilities = np.exp(values)
    probabilities /= probabilities.sum()
    grouped: dict[str, float] = {}
    for label, probability in zip(labels, probabilities):
        grouped[label] = grouped.get(label, 0.0) + float(probability)
    ranked = sorted(grouped.items(), key=lambda item: item[1], reverse=True)
    return [
        {"label": label, "confidence": round(probability, 6)}
        for label, probability in ranked[:limit]
    ]


class AssistedRecognizer:
    def __init__(self, model_dir: Path | None = None):
        import onnxruntime as ort

        directory = model_dir or _model_directory()
        metadata = json.loads(
            (directory / "metadata.json").read_text(encoding="utf-8")
        )
        normalization = np.load(directory / "normalization.npz")
        self.mean = normalization["mean"].astype(np.float32)
        self.std = normalization["std"].astype(np.float32)
        self.labels = [str(label) for label in metadata["labels"]]
        self.frames = int(metadata["frames"])
        if self.frames != FRAME_COUNT:
            raise ValueError(f"Modelo exige {self.frames} quadros; esperado 64.")
        options = ort.SessionOptions()
        options.intra_op_num_threads = int(os.getenv("ORT_INTRA_OP_THREADS", "2"))
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(
            str(directory / "model.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )

    def predict(self, frames: list[dict[str, Any]]) -> list[dict[str, float | str]]:
        coordinates = frames_to_coordinates(frames)
        sampled = resample_sequence(coordinates, self.frames)
        features = build_motion_features(sampled, self.mean, self.std)
        logits = self.session.run(
            ["logits"],
            {"features": features[None, ...]},
        )[0]
        return rank_candidates(logits[0], self.labels)


def get_assisted_recognizer() -> AssistedRecognizer:
    global _recognizer
    if _recognizer is not None:
        return _recognizer
    with _recognizer_lock:
        if _recognizer is None:
            _recognizer = AssistedRecognizer()
    return _recognizer
