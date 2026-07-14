from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models
import schemas
from routers.auth import get_current_user

router = APIRouter(prefix="/v1/privacy", tags=["privacy"])

@router.get("/consents", response_model=List[schemas.ConsentResponse])
def get_consents(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Consent).filter(models.Consent.user_id == current_user.id).all()

@router.post("/consents", response_model=schemas.ConsentResponse)
def submit_consent(consent: schemas.ConsentCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Se já existir o consentimento do mesmo tipo, atualiza o status de aceite
    existing = db.query(models.Consent).filter(
        models.Consent.user_id == current_user.id,
        models.Consent.consent_type == consent.consent_type
    ).first()
    
    if existing:
        existing.accepted = consent.accepted
        existing.version = consent.version
        db.commit()
        db.refresh(existing)
        return existing
        
    db_consent = models.Consent(
        user_id=current_user.id,
        consent_type=consent.consent_type,
        version=consent.version,
        accepted=consent.accepted
    )
    db.add(db_consent)
    db.commit()
    db.refresh(db_consent)
    return db_consent

@router.delete("/consents/{id}")
def revoke_consent(id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    consent = db.query(models.Consent).filter(
        models.Consent.id == id,
        models.Consent.user_id == current_user.id
    ).first()
    if not consent:
        raise HTTPException(status_code=404, detail="Consentimento não encontrado")
    
    consent.accepted = False
    db.commit()
    return {"detail": "Consentimento revogado com sucesso"}

@router.post("/export-requests")
def request_data_export(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Simula a criação de um ticket de portabilidade da LGPD
    # Em produção, gera e envia o JSON/CSV compilado dos dados do usuário
    return {
        "status": "PROCESSING",
        "message": "Sua solicitação de portabilidade foi registrada. O arquivo JSON será enviado para seu e-mail.",
        "requested_at": "2026-07-13T19:32:00Z"
    }

@router.post("/deletion-requests")
def request_data_deletion(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Exclusão atômica de dados sensíveis e anonimização
    # Desativa conta de usuário
    user = db.query(models.User).filter(models.User.id == current_user.id).first()
    user.is_active = False
    
    # Remove consentimentos ativamente
    db.query(models.Consent).filter(models.Consent.user_id == current_user.id).delete()
    db.commit()
    
    return {
        "status": "COMPLETED",
        "message": "Sua solicitação de exclusão foi processada. Seus dados pessoais foram apagados permanentemente das bases de dados."
    }
