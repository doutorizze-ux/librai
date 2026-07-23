import os
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import func
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


@router.get("/training/samples/count")
def get_sample_count(
    sign_name: str,
    db: Session = Depends(get_db),
    x_trainer_secret: str = Header(..., alias="X-Trainer-Secret")
):
    if x_trainer_secret != TRAINER_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chave secreta de treinamento inválida ou ausente."
        )
    
    count = db.query(models.TrainingSample).filter(
        models.TrainingSample.sign_name == sign_name.upper().strip()
    ).count()
    
    return {
        "sign_name": sign_name.upper().strip(),
        "count": count
    }


@router.get("/training/samples/summary")
def get_samples_summary(
    db: Session = Depends(get_db),
    x_trainer_secret: str = Header(..., alias="X-Trainer-Secret")
):
    if x_trainer_secret != TRAINER_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chave secreta de treinamento inválida ou ausente."
        )
    
    results = db.query(
        models.TrainingSample.sign_name,
        func.count(models.TrainingSample.id).label("count")
    ).group_by(models.TrainingSample.sign_name).all()
    
    return [
        {"sign_name": row[0], "count": row[1]}
        for row in results
    ]


@router.delete("/training/samples/{sign_name}")
def delete_training_samples(
    sign_name: str,
    db: Session = Depends(get_db),
    x_trainer_secret: str = Header(..., alias="X-Trainer-Secret")
):
    if x_trainer_secret != TRAINER_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chave secreta de treinamento inválida ou ausente."
        )
    
    name = sign_name.upper().strip()
    deleted_count = db.query(models.TrainingSample).filter(
        models.TrainingSample.sign_name == name
    ).delete(synchronize_session=False)
    
    db.commit()
    return {"sign_name": name, "deleted_count": deleted_count}
