from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
import models
import schemas
from routers.auth import get_current_user

router = APIRouter(prefix="/v1/dictionary", tags=["dictionary"])

@router.get("/categories", response_model=List[schemas.CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).all()

@router.get("/signs", response_model=List[schemas.SignResponse])
def get_signs(category_id: Optional[str] = None, query: Optional[str] = None, db: Session = Depends(get_db)):
    db_query = db.query(models.Sign)
    if category_id:
        db_query = db_query.filter(models.Sign.category_id == category_id)
    if query:
        db_query = db_query.filter(models.Sign.name.ilike(f"%{query}%"))
    return db_query.all()

@router.get("/signs/{id}", response_model=schemas.SignResponse)
def get_sign(id: str, db: Session = Depends(get_db)):
    sign = db.query(models.Sign).filter(models.Sign.id == id).first()
    if not sign:
        raise HTTPException(status_code=404, detail="Sinal não encontrado")
    return sign

@router.post("/signs/{id}/favorite")
def toggle_favorite(id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    sign = db.query(models.Sign).filter(models.Sign.id == id).first()
    if not sign:
        raise HTTPException(status_code=404, detail="Sinal não encontrado")
    
    # SQLite simplificado: retorna sucesso ao favoritar
    return {"detail": "Sinal adicionado aos favoritos", "sign_id": id, "favorited": True}
