from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI
from pydantic import BaseModel, Field
from preprocessing import preprocess_frames


UNKNOWN = "SINAL_DESCONHECIDO"


class PredictionRequest(BaseModel):
    format_version: int
    frames: list[dict] = Field(min_length=12, max_length=96)


MODEL_PATH = Path(os.getenv("MODEL_PATH", "/models/librai_stgcn.onnx"))
MANIFEST_PATH = Path(os.getenv("MODEL_MANIFEST_PATH", "/models/model_manifest.json"))
manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
labels = {index: label for label, index in manifest["labels"].items()}
session = ort.InferenceSession(
    str(MODEL_PATH), providers=["CPUExecutionProvider"]
)
app = FastAPI(title="Librai Experimental ML", version="1.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": manifest["model_id"],
        "experimental": True,
    }


@app.post("/predict")
def predict(payload: PredictionRequest) -> dict:
    if payload.format_version != 2:
        return {
            "label": UNKNOWN,
            "confidence": 0.0,
            "model": manifest["model_id"],
            "experimental": True,
        }
    features = preprocess_frames(payload.frames)
    logits = session.run(None, {"landmarks": features})[0][0]
    probabilities = np.exp(logits - logits.max())
    probabilities /= probabilities.sum()
    order = np.argsort(probabilities)[::-1]
    best, second = int(order[0]), int(order[1])
    confidence = float(probabilities[best])
    margin = confidence - float(probabilities[second])
    if confidence < 0.80 or margin < 0.35:
        return {
            "label": UNKNOWN,
            "confidence": 0.0,
            "model": manifest["model_id"],
            "experimental": True,
        }
    return {
        "label": labels[best],
        "confidence": round(confidence, 4),
        "model": manifest["model_id"],
        "experimental": True,
    }
