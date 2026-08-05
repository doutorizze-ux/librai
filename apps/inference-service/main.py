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
    ready = model_load.recognizer is not None
    return {
        "status": "ready" if ready else "degraded",
        "production_model_loaded": ready,
        "model_version": (
            model_load.recognizer.version if model_load.recognizer else None
        ),
        "model_load_reason": model_load.reason,
        "mode": "production" if model_load.recognizer else "laboratory",
    }


@app.get("/live")
def live():
    """Sinaliza apenas que o processo está vivo, sem prometer um modelo."""
    return {"status": "alive"}


@app.get("/ready")
def ready():
    """Só libera tráfego neural quando um manifesto de produção foi carregado."""
    if model_load.recognizer is None:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "reason": model_load.reason,
            },
        )
    return {
        "status": "ready",
        "model_version": model_load.recognizer.version,
    }


@app.post("/internal/v1/recognition/chunks", response_model=RecognitionResponse)
def recognize_chunk(chunk: RecognitionChunk):
    try:
        return engine.process(chunk)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
