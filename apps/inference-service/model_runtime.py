from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from schemas import HolisticFrame


HAND_NODES = 21
POSE_NODES = 13
EXPRESSION_FEATURES = ("mouth_open", "mouth_width", "left_brow", "right_brow")
TOTAL_NODES = HAND_NODES * 2 + POSE_NODES + len(EXPRESSION_FEATURES)


class ModelManifestError(ValueError):
    pass


@dataclass(frozen=True)
class ModelLoadResult:
    recognizer: "OnnxProductionRecognizer | None"
    reason: str


class HolisticPreprocessor:
    """Exact NumPy counterpart of the v4 training preprocessor."""

    def __init__(self, sequence_length: int = 48):
        if sequence_length < 24 or sequence_length > 120:
            raise ValueError("sequence_length outside the supported range")
        self.sequence_length = sequence_length

    def __call__(self, frames: list[HolisticFrame]) -> np.ndarray:
        if len(frames) < 12:
            raise ValueError("at least 12 frames are required")
        indices = np.rint(
            np.linspace(0, len(frames) - 1, self.sequence_length)
        ).astype(np.int64)
        output = np.zeros(
            (4, self.sequence_length, TOTAL_NODES), dtype=np.float32
        )
        for target_index, source_index in enumerate(indices.tolist()):
            frame = frames[source_index]
            self._write_hands(output, target_index, frame)
            self._write_points(
                output,
                target_index,
                HAND_NODES * 2,
                frame.pose.landmarks,
            )
            expression_offset = HAND_NODES * 2 + POSE_NODES
            for index, name in enumerate(EXPRESSION_FEATURES):
                output[0, target_index, expression_offset + index] = float(
                    getattr(frame.expression, name)
                )
                output[3, target_index, expression_offset + index] = 1.0
        self._normalize(output)
        return output[np.newaxis, ...]

    @staticmethod
    def _write_points(output, time_index, offset, points) -> None:
        for point_index, point in enumerate(points):
            node = offset + point_index
            if node >= TOTAL_NODES:
                break
            output[0, time_index, node] = point.x
            output[1, time_index, node] = point.y
            output[2, time_index, node] = point.z
            output[3, time_index, node] = 1.0

    def _write_hands(self, output, time_index, frame: HolisticFrame) -> None:
        slots: list[Any | None] = [None, None]
        unknown = []
        for hand in frame.hands:
            slot = 0 if hand.handedness == "Left" else 1 if hand.handedness == "Right" else None
            if slot is None or slots[slot] is not None:
                unknown.append(hand)
            else:
                slots[slot] = hand
        for hand in unknown:
            available = [index for index, value in enumerate(slots) if value is None]
            if not available:
                break
            preferred = 0 if hand.landmarks[0].x <= 0.5 else 1
            slots[preferred if preferred in available else available[0]] = hand
        for slot, hand in enumerate(slots):
            if hand is not None:
                self._write_points(
                    output, time_index, slot * HAND_NODES, hand.landmarks
                )

    @staticmethod
    def _normalize(output: np.ndarray) -> None:
        kinematic_nodes = HAND_NODES * 2 + POSE_NODES
        for time_index in range(output.shape[1]):
            present = output[3, time_index, :kinematic_nodes] > 0
            if not np.any(present):
                continue
            coordinates = output[:3, time_index, :kinematic_nodes][:, present].copy()
            center = coordinates[:2].mean(axis=1, keepdims=True)
            coordinates[:2] -= center
            scale = max(float(np.abs(coordinates[:2]).max()), 1e-4)
            coordinates /= scale
            output[:3, time_index, :kinematic_nodes][:, present] = coordinates


class OnnxProductionRecognizer:
    def __init__(self, manifest: dict[str, Any], session: Any):
        self.version = str(manifest["model_id"])
        self._session = session
        self._preprocessor = HolisticPreprocessor(
            int(manifest["sequence_length"])
        )
        labels = manifest["labels"]
        self._labels = {
            int(index): str(label) for label, index in labels.items()
        }
        rejection = manifest.get("rejection") or {}
        self.minimum_confidence = float(
            rejection.get("minimum_confidence", 0.85)
        )
        self.minimum_margin = float(rejection.get("minimum_margin", 0.12))

    def predict(self, frames: list[HolisticFrame]) -> tuple[str, float, float]:
        features = self._preprocessor(frames)
        input_name = self._session.get_inputs()[0].name
        logits = np.asarray(
            self._session.run(None, {input_name: features})[0],
            dtype=np.float32,
        )[0]
        probabilities = _softmax(logits)
        order = np.argsort(probabilities)[::-1]
        best = int(order[0])
        runner_up = float(probabilities[order[1]]) if len(order) > 1 else 0.0
        if best not in self._labels:
            raise ModelManifestError("model returned an unmapped class index")
        return self._labels[best], float(probabilities[best]), runner_up


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    exponentials = np.exp(shifted)
    return exponentials / np.sum(exponentials)


def _validate_manifest(manifest: dict[str, Any], manifest_path: Path) -> Path:
    if manifest.get("status") != "production":
        raise ModelManifestError("manifest is not explicitly promoted to production")
    if manifest.get("architecture") != "ST-GCN":
        raise ModelManifestError("unsupported architecture")
    if manifest.get("feature_schema") != "librai_holistic_v4":
        raise ModelManifestError("unsupported feature schema")
    if manifest.get("validation_mode") != "global-trainer":
        raise ModelManifestError("validation must hold out complete trainers")
    if float(manifest.get("validation_accuracy", 0)) < 0.70:
        raise ModelManifestError("validation accuracy is below the production gate")
    rejection = manifest.get("rejection")
    if not isinstance(rejection, dict):
        raise ModelManifestError("unknown-sign rejection calibration is missing")
    if rejection.get("method") != "softmax_confidence_and_margin":
        raise ModelManifestError("unsupported rejection calibration")
    if float(rejection.get("known_acceptance_rate", 0)) < 0.70:
        raise ModelManifestError("known-sign acceptance is below the production gate")
    if float(rejection.get("ood_recall", 0)) < 0.90:
        raise ModelManifestError("OOD recall is below the production gate")
    if int(rejection.get("ood_validation_samples", 0)) < 30:
        raise ModelManifestError("insufficient OOD validation samples")
    minimum_confidence = float(rejection.get("minimum_confidence", 0))
    minimum_margin = float(rejection.get("minimum_margin", 0))
    if not 0.0 < minimum_confidence < 1.0 or not 0.0 < minimum_margin < 1.0:
        raise ModelManifestError("invalid rejection thresholds")
    labels = manifest.get("labels")
    if not isinstance(labels, dict) or len(labels) < 2:
        raise ModelManifestError("invalid class map")
    indices = sorted(labels.values())
    if indices != list(range(len(labels))):
        raise ModelManifestError("class indices must be contiguous")
    model_path = manifest_path.parent / str(manifest.get("onnx_file", ""))
    if not model_path.is_file():
        raise ModelManifestError("ONNX file is missing")
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if digest != manifest.get("onnx_sha256"):
        raise ModelManifestError("ONNX hash does not match the manifest")
    return model_path


def load_production_recognizer(
    manifest_path: str | Path | None = None,
) -> ModelLoadResult:
    configured = manifest_path or os.getenv("LIBRAI_MODEL_MANIFEST")
    if not configured:
        return ModelLoadResult(None, "not_configured")
    path = Path(configured)
    if not path.is_file():
        return ModelLoadResult(None, "manifest_missing")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        model_path = _validate_manifest(manifest, path)
        import onnxruntime as ort

        session = ort.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"]
        )
        return ModelLoadResult(OnnxProductionRecognizer(manifest, session), "loaded")
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        ImportError,
        json.JSONDecodeError,
    ) as exc:
        return ModelLoadResult(None, f"rejected:{exc}")
    except Exception as exc:  # ONNX Runtime uses provider-specific exceptions.
        return ModelLoadResult(None, f"rejected:{exc}")
