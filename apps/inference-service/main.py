from fastapi import FastAPI, HTTPException

from continuous import ContinuousRecognitionEngine
from model_runtime import load_production_recognizer
from schemas import RecognitionChunk, RecognitionResponse


app = FastAPI(
    title="Librai Inference Service",
    version="0.1.0-lab",
    description="Internal signer-independent continuous recognition laboratory.",
)
model_load = load_production_recognizer()
engine = ContinuousRecognitionEngine(recognizer=model_load.recognizer)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "production_model_loaded": model_load.recognizer is not None,
        "model_version": (
            model_load.recognizer.version if model_load.recognizer else None
        ),
        "model_load_reason": model_load.reason,
        "mode": "production" if model_load.recognizer else "laboratory",
    }


@app.post("/internal/v1/recognition/chunks", response_model=RecognitionResponse)
def recognize_chunk(chunk: RecognitionChunk):
    try:
        return engine.process(chunk)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
