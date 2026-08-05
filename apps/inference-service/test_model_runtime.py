import json

import numpy as np

from model_runtime import (
    HAND_NODES,
    HolisticPreprocessor,
    OnnxProductionRecognizer,
    TOTAL_NODES,
    load_production_recognizer,
)
from schemas import HolisticFrame


def frame(timestamp: int, offset: float = 0.0) -> HolisticFrame:
    pose = [
        {"x": 0.25 + index * 0.02, "y": 0.2 + index * 0.01, "z": 0.0}
        for index in range(13)
    ]
    return HolisticFrame.model_validate({
        "timestamp_ms": timestamp,
        "hands": [{
            "handedness": "Right",
            "score": 0.99,
            "landmarks": [
                {"x": 0.3 + offset + index * 0.002, "y": 0.4, "z": 0.0}
                for index in range(21)
            ],
        }],
        "pose": {"landmarks": pose},
        "expression": {
            "mouth_open": 0.1,
            "mouth_width": 0.3,
            "left_brow": 0.1,
            "right_brow": 0.1,
        },
    })


class FakeInput:
    name = "landmarks"


class FakeSession:
    def get_inputs(self):
        return [FakeInput()]

    def run(self, _, inputs):
        assert inputs["landmarks"].shape == (1, 4, 48, TOTAL_NODES)
        return [np.asarray([[0.0, 4.0]], dtype=np.float32)]


def test_v4_preprocessor_matches_the_training_tensor_shape():
    frames = [frame(index * 33, index * 0.002) for index in range(24)]
    output = HolisticPreprocessor(48)(frames)
    assert output.shape == (1, 4, 48, TOTAL_NODES)
    assert np.isfinite(output).all()
    assert output[:, 3].sum() > 0


def test_runtime_assigns_unknown_hands_by_screen_position():
    payload = frame(0).model_dump()

    def unknown_hand(wrist_x):
        return {
            "handedness": "Unknown",
            "score": 0.9,
            "landmarks": [
                {"x": wrist_x + index * 0.001, "y": 0.4, "z": 0.0}
                for index in range(HAND_NODES)
            ],
        }

    payload["hands"] = [unknown_hand(0.8), unknown_hand(0.2)]
    parsed = HolisticFrame.model_validate(payload)
    output = np.zeros((4, 1, TOTAL_NODES), dtype=np.float32)

    HolisticPreprocessor()._write_hands(output, 0, parsed)

    assert output[0, 0, 0] == np.float32(0.2)
    assert output[0, 0, HAND_NODES] == np.float32(0.8)


def test_runtime_keeps_multiword_semantic_unit_as_one_prediction():
    recognizer = OnnxProductionRecognizer({
        "model_id": "librai-test-model",
        "sequence_length": 48,
        "labels": {"OLA": 0, "TUDO BEM?": 1},
    }, FakeSession())
    label, confidence, runner_up = recognizer.predict(
        [frame(index * 33, index * 0.002) for index in range(24)]
    )
    assert label == "TUDO BEM?"
    assert confidence > 0.95
    assert runner_up < 0.05


def test_candidate_manifest_is_never_loaded_as_production(tmp_path):
    manifest = tmp_path / "candidate.manifest.json"
    manifest.write_text(json.dumps({
        "status": "validated_ready_for_review",
        "architecture": "ST-GCN",
        "feature_schema": "librai_holistic_v4",
        "validation_mode": "global-trainer",
        "validation_accuracy": 0.99,
        "labels": {"OLA": 0, "TUDO BEM?": 1},
    }), encoding="utf-8")
    result = load_production_recognizer(manifest)
    assert result.recognizer is None
    assert "not explicitly promoted" in result.reason


def test_production_manifest_without_ood_calibration_is_rejected(tmp_path):
    manifest = tmp_path / "production.manifest.json"
    model = tmp_path / "model.onnx"
    model.write_bytes(b"not-loaded-because-manifest-gate-fails-first")
    manifest.write_text(json.dumps({
        "status": "production",
        "architecture": "ST-GCN",
        "feature_schema": "librai_holistic_v4",
        "validation_mode": "global-trainer",
        "validation_accuracy": 0.99,
        "labels": {"OLA": 0, "TUDO BEM?": 1},
        "onnx_file": model.name,
    }), encoding="utf-8")

    result = load_production_recognizer(manifest)

    assert result.recognizer is None
    assert "rejection calibration is missing" in result.reason
