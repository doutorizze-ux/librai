import hashlib
import os
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
import models
import schemas
import security
from routers.translation import extract_hand_angles
from sign_labels import canonical_visual_label

router = APIRouter(prefix="/v1", tags=["training"])

TRAINER_ACCESS_CODE = os.getenv("TRAINER_ACCESS_CODE", "")
TRAINER_DELETE_SECRET = os.getenv("TRAINER_DELETE_SECRET", "")
trainer_bearer = HTTPBearer(auto_error=False)


def _credential_version(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def get_current_trainer(
    credentials: HTTPAuthorizationCredentials = Depends(trainer_bearer),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão de treinamento ausente.",
        )
    payload = security.decode_token(credentials.credentials)
    if (
        not payload
        or payload.get("scope") != "training"
        or not payload.get("trainer")
        or payload.get("trainer_code_version")
        not in {
            _credential_version(TRAINER_ACCESS_CODE),
            _credential_version(TRAINER_DELETE_SECRET),
        }
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão de treinamento inválida ou expirada.",
        )
    return str(payload["trainer"])


@router.post(
    "/training/auth",
    response_model=schemas.TrainerTokenResponse,
)
def authenticate_trainer(request: schemas.TrainerLoginRequest):
    if not TRAINER_ACCESS_CODE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Acesso de professores ainda não configurado.",
        )
    is_professor_code = secrets.compare_digest(
        request.access_code,
        TRAINER_ACCESS_CODE,
    )
    is_administrator_code = bool(TRAINER_DELETE_SECRET) and secrets.compare_digest(
        request.access_code,
        TRAINER_DELETE_SECRET,
    )
    if not is_professor_code and not is_administrator_code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código de acesso incorreto.",
        )
    access_token = security.create_access_token(
        {
            "scope": "training",
            "trainer": request.trainer_name,
            "trainer_code_version": _credential_version(request.access_code),
        },
        expires_delta=timedelta(hours=8),
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in_seconds": 28800,
    }


@router.get("/training/model/current", response_model=schemas.TrainingModelResponse)
def get_current_training_model(db: Session = Depends(get_db)):
    """Entrega somente características geométricas para inferência local."""
    samples = db.query(
        models.TrainingSample.id,
        models.TrainingSample.sign_name,
        models.TrainingSample.landmarks,
        models.TrainingSample.created_at,
    ).filter(
        models.TrainingSample.deleted_at.is_(None)
    ).order_by(models.TrainingSample.created_at, models.TrainingSample.id).all()

    features = []
    version_parts = ["canonical-labels-v1"]

    for sample_id, sign_name, landmarks, created_at in samples:
        version_parts.append(f"{sample_id}:{created_at.isoformat()}")
        if not isinstance(landmarks, list) or len(landmarks) < 21:
            continue

        for offset in range(0, len(landmarks) - 20, 21):
            angles = extract_hand_angles(landmarks[offset:offset + 21])
            if angles:
                features.append({
                    "label": canonical_visual_label(sign_name),
                    "angles": angles,
                })

    version_source = "|".join(version_parts).encode("utf-8")
    version = hashlib.sha256(version_source).hexdigest()[:16]

    return {
        "version": version,
        "feature_schema": "hand_angles_v1",
        "threshold": 30.0,
        "features": features,
    }

@router.post("/training/samples", response_model=schemas.TrainingSampleResponse, status_code=status.HTTP_201_CREATED)
def create_training_sample(
    sample: schemas.TrainingSampleCreate,
    db: Session = Depends(get_db),
    trainer_name: str = Depends(get_current_trainer),
):
    db_sample = models.TrainingSample(
        sign_name=canonical_visual_label(sample.sign_name),
        landmarks=[point.model_dump() for point in sample.landmarks],
        trainer_name=trainer_name,
        frame_count=len(sample.landmarks) // 21,
    )
    db.add(db_sample)
    db.flush()
    db.add(models.AuditLog(
        user_id=trainer_name,
        action="TRAINING_SAMPLE_CREATE",
        target=f"{db_sample.id}:{db_sample.sign_name}:{len(sample.landmarks) // 21}_frames",
    ))
    db.commit()
    db.refresh(db_sample)
    return db_sample


@router.post("/training/samples-v2", status_code=status.HTTP_201_CREATED)
def create_training_sample_v2(
    sample: schemas.TrainingSampleCreateV2,
    db: Session = Depends(get_db),
    trainer_name: str = Depends(get_current_trainer),
):
    """Armazena quadros sem misturar lateralidade das mãos nem ordem temporal."""
    sequence = {
        "format_version": 2,
        "frames": [frame.model_dump() for frame in sample.frames],
    }
    db_sample = models.TrainingSample(
        sign_name=canonical_visual_label(sample.sign_name),
        landmarks=sequence,
        trainer_name=trainer_name,
        frame_count=len(sample.frames),
    )
    db.add(db_sample)
    db.flush()
    db.add(models.AuditLog(
        user_id=trainer_name,
        action="TRAINING_SAMPLE_CREATE_V2",
        target=f"{db_sample.id}:{db_sample.sign_name}:{len(sample.frames)}_frames",
    ))
    db.commit()
    return {
        "id": db_sample.id,
        "sign_name": db_sample.sign_name,
        "format_version": 2,
        "frame_count": db_sample.frame_count,
        "created_at": db_sample.created_at,
    }


@router.get("/training/samples/count")
def get_sample_count(
    sign_name: str,
    db: Session = Depends(get_db),
    trainer_name: str = Depends(get_current_trainer),
):
    name = canonical_visual_label(sign_name)
    aliases = ["BOM", "BOA"] if name == "BOM" else [name]
    count = db.query(models.TrainingSample).filter(
        models.TrainingSample.sign_name.in_(aliases),
        models.TrainingSample.deleted_at.is_(None),
    ).count()
    
    return {
        "sign_name": name,
        "count": count
    }


@router.get("/training/samples/summary")
def get_samples_summary(
    db: Session = Depends(get_db),
    trainer_name: str = Depends(get_current_trainer),
):
    results = db.query(
        models.TrainingSample.sign_name,
        func.count(models.TrainingSample.id).label("count")
    ).filter(
        models.TrainingSample.deleted_at.is_(None)
    ).group_by(models.TrainingSample.sign_name).all()
    
    canonical_counts = {}
    for sign_name, count in results:
        canonical_name = canonical_visual_label(sign_name)
        canonical_counts[canonical_name] = (
            canonical_counts.get(canonical_name, 0) + count
        )
    return [
        {"sign_name": name, "count": canonical_counts[name]}
        for name in sorted(canonical_counts)
    ]


@router.get(
    "/training/my-samples",
    response_model=list[schemas.TrainingSampleMetadataResponse],
)
def list_my_training_samples(
    sign_name: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    trainer_name: str = Depends(get_current_trainer),
):
    query = db.query(models.TrainingSample).filter(
        models.TrainingSample.trainer_name == trainer_name,
        models.TrainingSample.deleted_at.is_(None),
    )
    if sign_name:
        query = query.filter(
            models.TrainingSample.sign_name
            == canonical_visual_label(sign_name)
        )
    samples = query.order_by(
        models.TrainingSample.created_at.desc()
    ).limit(min(max(limit, 1), 100)).all()
    return [
        {
            "id": sample.id,
            "sign_name": sample.sign_name,
            "frame_count": sample.frame_count
            or len(sample.landmarks or []) // 21,
            "created_at": sample.created_at,
        }
        for sample in samples
    ]


@router.delete("/training/my-samples/{sample_id}")
def delete_my_training_sample(
    sample_id: str,
    db: Session = Depends(get_db),
    trainer_name: str = Depends(get_current_trainer),
):
    sample = db.query(models.TrainingSample).filter(
        models.TrainingSample.id == sample_id,
        models.TrainingSample.deleted_at.is_(None),
    ).first()
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sessão de treinamento não encontrada.",
        )
    if sample.trainer_name != trainer_name:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você só pode excluir suas próprias sessões.",
        )

    sample.deleted_at = datetime.utcnow()
    sample.deleted_by = trainer_name
    db.add(models.AuditLog(
        user_id=trainer_name,
        action="TRAINING_SAMPLE_SOFT_DELETE",
        target=f"{sample.id}:{sample.sign_name}",
    ))
    db.commit()
    return {
        "id": sample.id,
        "sign_name": sample.sign_name,
        "deleted": True,
    }


def _require_trainer_delete_secret(value: str) -> None:
    if not TRAINER_DELETE_SECRET or not secrets.compare_digest(
        value,
        TRAINER_DELETE_SECRET,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chave administrativa inválida ou ausente.",
        )


@router.get(
    "/training/legacy-samples",
    response_model=list[schemas.TrainingSampleMetadataResponse],
)
def list_legacy_training_samples(
    db: Session = Depends(get_db),
    x_trainer_secret: str = Header(..., alias="X-Trainer-Delete-Secret"),
):
    """Lista capturas anteriores à identificação individual dos professores."""
    _require_trainer_delete_secret(x_trainer_secret)
    samples = db.query(models.TrainingSample).filter(
        models.TrainingSample.trainer_name.is_(None),
        models.TrainingSample.deleted_at.is_(None),
    ).order_by(models.TrainingSample.created_at.desc()).limit(200).all()
    return [
        {
            "id": sample.id,
            "sign_name": sample.sign_name,
            "frame_count": sample.frame_count
            or len(sample.landmarks or []) // 21,
            "created_at": sample.created_at,
        }
        for sample in samples
    ]


@router.delete("/training/legacy-samples/{sample_id}")
def delete_legacy_training_sample(
    sample_id: str,
    db: Session = Depends(get_db),
    x_trainer_secret: str = Header(..., alias="X-Trainer-Delete-Secret"),
):
    _require_trainer_delete_secret(x_trainer_secret)
    sample = db.query(models.TrainingSample).filter(
        models.TrainingSample.id == sample_id,
        models.TrainingSample.trainer_name.is_(None),
        models.TrainingSample.deleted_at.is_(None),
    ).first()
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Captura antiga não encontrada.",
        )
    sample.deleted_at = datetime.utcnow()
    sample.deleted_by = "administrator"
    db.add(models.AuditLog(
        action="LEGACY_TRAINING_SAMPLE_SOFT_DELETE",
        target=f"{sample.id}:{sample.sign_name}",
    ))
    db.commit()
    return {"id": sample.id, "sign_name": sample.sign_name, "deleted": True}


@router.delete("/training/samples/{sign_name}")
def delete_training_samples(
    sign_name: str,
    db: Session = Depends(get_db),
    x_trainer_secret: str = Header(..., alias="X-Trainer-Delete-Secret")
):
    if not TRAINER_DELETE_SECRET or not secrets.compare_digest(
        x_trainer_secret,
        TRAINER_DELETE_SECRET,
    ):
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


@router.delete("/training/samples")
def delete_training_samples_by_query(
    sign_name: str,
    db: Session = Depends(get_db),
    x_trainer_secret: str = Header(..., alias="X-Trainer-Delete-Secret")
):
    """Exclui amostras sem colocar o nome do sinal no caminho da URL."""
    if not TRAINER_DELETE_SECRET or not secrets.compare_digest(
        x_trainer_secret,
        TRAINER_DELETE_SECRET,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chave secreta de treinamento inválida ou ausente."
        )

    name = sign_name.upper().strip()
    deleted_count = db.query(models.TrainingSample).filter(
        models.TrainingSample.sign_name == name
    ).delete(synchronize_session=False)

    if deleted_count == 0:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhuma amostra encontrada para o sinal '{name}'."
        )

    db.commit()
    return {"sign_name": name, "deleted_count": deleted_count}
