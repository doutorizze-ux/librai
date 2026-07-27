import importlib
import os
import sys
import types
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "ml" / "models" / "pilot-v1-core-hands"
os.environ["MODEL_PATH"] = str(MODEL_DIR / "librai_stgcn.onnx")
os.environ["MODEL_MANIFEST_PATH"] = str(MODEL_DIR / "model_manifest.json")


class FakeSession:
    def __init__(self, *_args, **_kwargs):
        pass

    def run(self, *_args, **_kwargs):
        return [np.asarray([[0.0, 3.0]], dtype=np.float32)]


sys.modules["onnxruntime"] = types.SimpleNamespace(InferenceSession=FakeSession)
inference_app = importlib.import_module("app")


def frames():
    points = [
        {"x": index / 100, "y": index / 100, "z": 0.0}
        for index in range(21)
    ]
    return [
        {
            "timestamp_ms": index * 33,
            "hands": [{"handedness": "Left", "landmarks": points}],
        }
        for index in range(20)
    ]


def test_health_identifies_experimental_model():
    result = inference_app.health()
    assert result["status"] == "ok"
    assert result["experimental"] is True


def test_predict_returns_only_manifest_label():
    request = inference_app.PredictionRequest(
        format_version=2,
        frames=frames(),
    )
    result = inference_app.predict(request)
    assert result["label"] == "TRABALHAR"
    assert result["experimental"] is True
    assert result["confidence"] > 0.8
