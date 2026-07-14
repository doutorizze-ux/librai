from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
import models
import schemas
from routers.auth import get_current_user

router = APIRouter(prefix="/v1/admin", tags=["admin"])

# Middleware auxiliar para verificar se o usuário é administrador
def verify_admin(current_user: models.User = Depends(get_current_user)):
    # Em produção, valida roles associados (RBAC)
    # Para o setup inicial executável, permitimos a passagem se ativo
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return current_user

@router.get("/models", response_model=List[schemas.ModelResponse])
def get_all_models(db: Session = Depends(get_db), admin: models.User = Depends(verify_admin)):
    return db.query(models.Model).all()

@router.post("/models", response_model=schemas.ModelResponse, status_code=status.HTTP_201_CREATED)
def register_model(model: schemas.ModelResponse, db: Session = Depends(get_db), admin: models.User = Depends(verify_admin)):
    db_model = models.Model(
        name=model.name,
        version=model.version,
        hash_sha256=model.hash_sha256,
        is_active=False
    )
    db.add(db_model)
    
    # Audit log entry
    log = models.AuditLog(user_id=admin.id, action="REGISTER_MODEL", target=model.version)
    db.add(log)
    
    db.commit()
    db.refresh(db_model)
    return db_model

@router.post("/models/{id}/deploy", response_model=schemas.ModelResponse)
def deploy_model(id: str, db: Session = Depends(get_db), admin: models.User = Depends(verify_admin)):
    # Desativa qualquer outro modelo ativo
    db.query(models.Model).update({models.Model.is_active: False})
    
    model = db.query(models.Model).filter(models.Model.id == id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")
    
    model.is_active = True
    
    # Audit log
    log = models.AuditLog(user_id=admin.id, action="DEPLOY_MODEL", target=model.version)
    db.add(log)
    
    db.commit()
    db.refresh(model)
    return model

@router.post("/models/{id}/rollback", response_model=schemas.ModelResponse)
def rollback_model(id: str, db: Session = Depends(get_db), admin: models.User = Depends(verify_admin)):
    model = db.query(models.Model).filter(models.Model.id == id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")
    
    model.is_active = False
    
    # Audit log
    log = models.AuditLog(user_id=admin.id, action="ROLLBACK_MODEL", target=model.version)
    db.add(log)
    
    db.commit()
    db.refresh(model)
    return model

@router.get("/audit-logs", response_model=List[schemas.AuditLogResponse])
def get_audit_logs(db: Session = Depends(get_db), admin: models.User = Depends(verify_admin)):
    # Retorna logs ordenados pelo mais recente
    return db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).all()
