from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
import models
import schemas
import security

router = APIRouter(prefix="/v1", tags=["auth"])

from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/auth/login")

def get_current_user_helper(token: str, db: Session) -> models.User:
    payload = security.decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado"
        )
    user = db.query(models.User).filter(models.User.email == payload["sub"]).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado"
        )
    return user

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    return get_current_user_helper(token, db)

@router.post("/auth/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    # Criar usuário inicial para testes
    existing = db.query(models.User).filter(models.User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    
    hashed = security.get_password_hash(request.password)
    user = models.User(email=request.email, hashed_password=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/auth/login", response_model=schemas.TokenResponse)
def login(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == request.email).first()
    if not user or not security.verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais incorretas"
        )
    
    access = security.create_access_token({"sub": user.email})
    refresh = security.create_refresh_token({"sub": user.email})
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}

@router.post("/auth/refresh", response_model=schemas.TokenResponse)
def refresh(refresh_token: str, db: Session = Depends(get_db)):
    payload = security.decode_token(refresh_token)
    if not payload or "refresh" not in payload or "sub" not in payload:
        raise HTTPException(status_code=400, detail="Token de atualização inválido")
    
    user = db.query(models.User).filter(models.User.email == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    access = security.create_access_token({"sub": user.email})
    new_refresh = security.create_refresh_token({"sub": user.email})
    return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer"}

@router.post("/auth/logout")
def logout():
    return {"detail": "Sessão encerrada com sucesso"}

@router.get("/me", response_model=schemas.UserResponse)
def get_me(user: models.User = Depends(get_current_user)):
    return user

@router.patch("/me", response_model=schemas.UserResponse)
def update_me(email: Optional[str] = None, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if email:
        user.email = email
        db.commit()
        db.refresh(user)
    return user
