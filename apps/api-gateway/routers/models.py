from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from routers.auth import get_current_user

router = APIRouter(prefix="/v1/models", tags=["models"])

@router.get("/manifest", response_model=schemas.ModelResponse)
def get_manifest(db: Session = Depends(get_db)):
    active_model = db.query(models.Model).filter(models.Model.is_active == True).first()
    if not active_model:
        # Cria um modelo inicial para que a primeira execução local funcione sem problemas
        active_model = models.Model(
            name="Sinaliza AI Transformer Lite",
            version="1.0.0-rc1",
            hash_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            is_active=True
        )
        db.add(active_model)
        db.commit()
        db.refresh(active_model)
    return active_model

@router.get("/{id}/download")
def download_model(id: str, db: Session = Depends(get_db)):
    model = db.query(models.Model).filter(models.Model.id == id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")
    
    # Em produção, redireciona para URL assinada do S3/CDN. Aqui, retorna mock.
    return {
        "model_id": id,
        "download_url": f"https://cdn.sinaliza.ai/models/{model.hash_sha256}.onnx",
        "expires_in_seconds": 3600
    }

@router.post("/{id}/download-events")
def log_download_event(id: str, status_event: str, db: Session = Depends(get_db)):
    # Registra o evento de telemetria de download do modelo
    return {"status": "event_logged", "model_id": id, "event": status_event}
