import os
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas

router = APIRouter(prefix="/v1", tags=["training"])

TRAINER_SECRET = os.getenv("TRAINER_SECRET", "librAI_trainer_secret_2026")

@router.post("/training/samples", response_model=schemas.TrainingSampleResponse, status_code=status.HTTP_201_CREATED)
def create_training_sample(
    sample: schemas.TrainingSampleCreate,
    db: Session = Depends(get_db),
    x_trainer_secret: str = Header(..., alias="X-Trainer-Secret")
):
    if x_trainer_secret != TRAINER_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chave secreta de treinamento inválida ou ausente."
        )
    
    db_sample = models.TrainingSample(
        sign_name=sample.sign_name.upper().strip(),
        landmarks=sample.landmarks
    )
    db.add(db_sample)
    db.commit()
    db.refresh(db_sample)
    return db_sample
