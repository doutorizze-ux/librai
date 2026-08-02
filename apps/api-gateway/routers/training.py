import hashlib
import logging
import math
import os
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from database import get_db
import models
import schemas
import security
from routers.translation import extract_hand_angles
from sign_labels import canonical_visual_label, is_isolated_sign_label

router = APIRouter(prefix="/v1", tags=["training"])
logger = logging.getLogger(__name__)

TRAINER_ACCESS_CODE = os.getenv("TRAINER_ACCESS_CODE", "")
TRAINER_DELETE_SECRET = os.getenv("TRAINER_DELETE_SECRET", "")
trainer_bearer = HTTPBearer(auto_error=False)

_LEGACY_TRAINER_NAMES = {"prof1"}


def _legacy_training_filter():
    """Identifica somente capturas anteriores às contas de professor atuais."""
    normalized_trainer = func.lower(
        func.trim(models.TrainingSample.trainer_name)
    )
    return or_(
        models.TrainingSample.trainer_name.is_(None),
        normalized_trainer.in_(_LEGACY_TRAINER_NAMES),
    )


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
        expires_delta=timedelta(days=7),
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in_seconds": 604800,
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


@router.post("/training/batches-v2", status_code=status.HTTP_201_CREATED)
def create_training_batch_v2(
    batch: schemas.TrainingBatchCreateV2,
    db: Session = Depends(get_db),
    trainer_name: str = Depends(get_current_trainer),
):
    """Grava exatamente cinco repetições do mesmo sinal em uma transação."""
    sign_name = canonical_visual_label(batch.sign_name)
    created = []
    for repetition_number, repetition in enumerate(batch.repetitions, start=1):
        sequence = {
            "format_version": 2,
            "frames": [frame.model_dump() for frame in repetition.frames],
        }
        db_sample = models.TrainingSample(
            sign_name=sign_name,
            landmarks=sequence,
            trainer_name=trainer_name,
            frame_count=len(repetition.frames),
        )
        db.add(db_sample)
        db.flush()
        created.append({
            "id": db_sample.id,
            "frame_count": db_sample.frame_count,
            "repetition": repetition_number,
        })

    db.add(models.AuditLog(
        user_id=trainer_name,
        action="TRAINING_BATCH_CREATE_V2",
        target=f"{sign_name}:5_repetitions",
    ))
    db.commit()
    return {
        "sign_name": sign_name,
        "repetitions_created": len(created),
        "samples": created,
    }


def _repetition_fingerprint(
    frames: list[schemas.TrainingFrame],
) -> str:
    coordinates = []
    for frame in frames:
        hands = sorted(
            frame.hands,
            key=lambda hand: hand.handedness,
        )
        coordinates.append(tuple(
            (
                hand.handedness,
                tuple(
                    (
                        round(point.x, 5),
                        round(point.y, 5),
                        round(point.z, 5),
                    )
                    for point in hand.landmarks
                ),
            )
            for hand in hands
        ))
    return hashlib.sha256(repr(coordinates).encode("utf-8")).hexdigest()


def _repetition_quality(
    frames: list[schemas.TrainingFrame],
) -> dict[str, float | int | list[str]]:
    """Calcula qualidade sem descartar uma captura estruturalmente válida.

    A tela de treinamento já exige 24 quadros novos, mãos rastreadas e
    enquadramento bom. Duração, latência entre quadros e pequenas oscilações
    de confiança dependem do aparelho; são metadados para auditoria e para o
    modelo, não motivos para perder o trabalho do professor.
    """
    timestamps = [frame.timestamp_ms for frame in frames]
    duration_ms = timestamps[-1] - timestamps[0]
    largest_gap_ms = max(
        later - earlier
        for earlier, later in zip(timestamps, timestamps[1:])
    )

    scores = []
    hand_spans = []
    in_frame_points = 0
    point_count = 0
    frame_signatures = set()
    two_hand_frames = 0
    motion_total = 0.0
    motion_comparisons = 0
    previous_hands = {}
    tracked_indices = (0, 4, 8, 12, 16, 20)

    for frame in frames:
        two_hand_frames += int(len(frame.hands) == 2)
        signature = []
        current_hands = {}
        for hand_index, hand in enumerate(frame.hands):
            scores.append(hand.score)
            xs = [point.x for point in hand.landmarks]
            ys = [point.y for point in hand.landmarks]
            hand_spans.append(max(max(xs) - min(xs), max(ys) - min(ys)))
            for point in hand.landmarks:
                point_count += 1
                in_frame_points += int(
                    0.0 <= point.x <= 1.0 and 0.0 <= point.y <= 1.0
                )
            signature.extend(
                (
                    round(point.x, 4),
                    round(point.y, 4),
                    round(point.z, 4),
                )
                for point in hand.landmarks
            )
            slot = (
                hand.handedness
                if hand.handedness != "Unknown"
                else f"Unknown-{hand_index}"
            )
            current_hands[slot] = hand.landmarks
            if slot in previous_hands:
                previous = previous_hands[slot]
                for point_index in tracked_indices:
                    before = previous[point_index]
                    after = hand.landmarks[point_index]
                    motion_total += math.sqrt(
                        (after.x - before.x) ** 2
                        + (after.y - before.y) ** 2
                        + (after.z - before.z) ** 2
                    )
                    motion_comparisons += 1
        frame_signatures.add(tuple(signature))
        previous_hands = current_hands

    mean_score = sum(scores) / len(scores)
    in_frame_ratio = in_frame_points / point_count
    sorted_spans = sorted(hand_spans)
    median_span = sorted_spans[len(sorted_spans) // 2]
    distinct_frame_ratio = len(frame_signatures) / len(frames)

    warnings = []
    if duration_ms < 800:
        warnings.append("short_duration")
    elif duration_ms > 5000:
        warnings.append("long_duration")
    if largest_gap_ms > 250:
        warnings.append("tracking_gap")
    if mean_score < 0.55:
        warnings.append("low_tracking_confidence")
    if in_frame_ratio < 0.95:
        warnings.append("partial_out_of_frame")
    if median_span < 0.04:
        warnings.append("small_hand_span")
    elif median_span > 0.75:
        warnings.append("large_hand_span")
    if distinct_frame_ratio < 0.25:
        warnings.append("low_frame_variation")

    return {
        "frame_count": len(frames),
        "duration_ms": duration_ms,
        "largest_gap_ms": largest_gap_ms,
        "mean_hand_score": round(mean_score, 6),
        "in_frame_ratio": round(in_frame_ratio, 6),
        "median_hand_span": round(median_span, 6),
        "distinct_frame_ratio": round(distinct_frame_ratio, 6),
        "two_hand_frame_ratio": round(two_hand_frames / len(frames), 6),
        "motion_energy": round(
            motion_total / max(motion_comparisons, 1),
            6,
        ),
        "warnings": warnings,
    }


@router.get(
    "/training/drafts/current",
    response_model=schemas.TrainingDraftStatusResponse,
)
def get_current_training_draft(
    db: Session = Depends(get_db),
    trainer_name: str = Depends(get_current_trainer),
):
    draft = db.query(models.TrainingDraft).filter(
        models.TrainingDraft.trainer_name == trainer_name,
    ).first()
    if not draft:
        return {
            "active": False,
            "sign_name": None,
            "repetitions_saved": 0,
            "required_repetitions": 5,
        }
    return {
        "active": True,
        "sign_name": draft.sign_name,
        "repetitions_saved": len(draft.repetitions or []),
        "required_repetitions": 5,
    }


@router.post(
    "/training/drafts/repetitions",
    response_model=schemas.TrainingDraftRepetitionResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_training_draft_repetition(
    repetition: schemas.TrainingDraftRepetitionCreate,
    db: Session = Depends(get_db),
    trainer_name: str = Depends(get_current_trainer),
):
    """Persiste cada repetição imediatamente e conclui o lote na quinta."""
    existing_receipt = db.query(models.TrainingCaptureReceipt).filter(
        models.TrainingCaptureReceipt.capture_id == repetition.capture_id,
    ).first()
    if existing_receipt:
        if existing_receipt.trainer_name != trainer_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Identificador de captura já utilizado.",
            )
        response = dict(existing_receipt.response)
        response["duplicate"] = True
        return response

    sign_name = canonical_visual_label(repetition.sign_name)
    if not is_isolated_sign_label(sign_name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Grave somente um sinal por vez, sem espaços ou pontuação.",
        )
    quality = _repetition_quality(repetition.frames)
    if quality["warnings"]:
        logger.warning(
            "training_capture_quality_warning trainer=%s sign=%s "
            "capture_id=%s warnings=%s frame_count=%s duration_ms=%s "
            "largest_gap_ms=%s",
            trainer_name,
            sign_name,
            repetition.capture_id,
            ",".join(quality["warnings"]),
            quality["frame_count"],
            quality["duration_ms"],
            quality["largest_gap_ms"],
        )
    fingerprint = _repetition_fingerprint(repetition.frames)
    frames = [frame.model_dump() for frame in repetition.frames]
    context = repetition.capture_context.model_dump(exclude_none=True)

    draft = db.query(models.TrainingDraft).filter(
        models.TrainingDraft.trainer_name == trainer_name,
    ).with_for_update().first()
    if draft and draft.sign_name != sign_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Conclua as cinco repetições de {draft.sign_name} "
                "antes de iniciar outro sinal."
            ),
        )
    if not draft:
        draft = models.TrainingDraft(
            trainer_name=trainer_name,
            sign_name=sign_name,
            capture_context=context,
            repetitions=[],
        )
        db.add(draft)
        db.flush()

    stored_repetitions = list(draft.repetitions or [])
    if any(item.get("fingerprint") == fingerprint for item in stored_repetitions):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Esta repetição é idêntica a outra já salva. "
                "Faça o sinal novamente."
            ),
        )
    stored_repetitions.append({
        "capture_id": repetition.capture_id,
        "fingerprint": fingerprint,
        "quality": quality,
        "frames": frames,
    })
    draft.repetitions = stored_repetitions
    draft.updated_at = datetime.utcnow()
    saved_count = len(stored_repetitions)

    response = {
        "sign_name": sign_name,
        "repetitions_saved": saved_count,
        "required_repetitions": 5,
        "completed": saved_count == 5,
        "duplicate": False,
    }
    receipt = models.TrainingCaptureReceipt(
        capture_id=repetition.capture_id,
        trainer_name=trainer_name,
        sign_name=sign_name,
        response=response,
    )
    db.add(receipt)

    if saved_count < 5:
        db.add(models.AuditLog(
            user_id=trainer_name,
            action="TRAINING_DRAFT_REPETITION_SAVE",
            target=f"{draft.id}:{sign_name}:{saved_count}/5",
        ))
        db.commit()
        return response

    for entry in stored_repetitions:
        sequence = {
            "format_version": 3,
            "capture_context": draft.capture_context,
            "quality": entry["quality"],
            "frames": entry["frames"],
        }
        db.add(models.TrainingSample(
            sign_name=sign_name,
            landmarks=sequence,
            trainer_name=trainer_name,
            frame_count=len(entry["frames"]),
        ))
    db.flush()

    final_response = dict(response)
    for entry in stored_repetitions:
        saved_receipt = db.query(models.TrainingCaptureReceipt).filter(
            models.TrainingCaptureReceipt.capture_id == entry["capture_id"],
        ).first()
        if saved_receipt:
            saved_receipt.response = final_response
    db.delete(draft)
    db.add(models.AuditLog(
        user_id=trainer_name,
        action="TRAINING_DRAFT_COMPLETE_V3",
        target=f"{sign_name}:5_quality_checked_repetitions",
    ))
    db.commit()
    return final_response


@router.post("/training/batches-v3", status_code=status.HTTP_201_CREATED)
def create_training_batch_v3(
    batch: schemas.TrainingBatchCreateV3,
    db: Session = Depends(get_db),
    trainer_name: str = Depends(get_current_trainer),
):
    """Coleta isolada com qualidade para o reconhecedor temporal."""
    sign_name = canonical_visual_label(batch.sign_name)
    if not is_isolated_sign_label(sign_name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Grave somente um sinal por vez, sem espaços ou pontuação."
            ),
        )
    qualities = [
        _repetition_quality(repetition.frames)
        for repetition in batch.repetitions
    ]
    fingerprints = [
        _repetition_fingerprint(repetition.frames)
        for repetition in batch.repetitions
    ]
    if len(set(fingerprints)) != len(fingerprints):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "As cinco repetições precisam ser novas; uma captura "
                "idêntica foi enviada mais de uma vez."
            ),
        )

    context = batch.capture_context.model_dump(exclude_none=True)
    created = []
    for repetition_number, (repetition, quality) in enumerate(
        zip(batch.repetitions, qualities),
        start=1,
    ):
        sequence = {
            "format_version": 3,
            "capture_context": context,
            "quality": quality,
            "frames": [frame.model_dump() for frame in repetition.frames],
        }
        db_sample = models.TrainingSample(
            sign_name=sign_name,
            landmarks=sequence,
            trainer_name=trainer_name,
            frame_count=len(repetition.frames),
        )
        db.add(db_sample)
        db.flush()
        created.append({
            "id": db_sample.id,
            "frame_count": db_sample.frame_count,
            "repetition": repetition_number,
            "quality": quality,
        })

    db.add(models.AuditLog(
        user_id=trainer_name,
        action="TRAINING_BATCH_CREATE_V3",
        target=f"{sign_name}:5_quality_checked_repetitions",
    ))
    db.commit()
    return {
        "sign_name": sign_name,
        "format_version": 3,
        "repetitions_created": len(created),
        "used_by_current_translator": True,
        "samples": created,
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
            "trainer_name": sample.trainer_name,
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


@router.delete(
    "/training/my-signs",
    response_model=schemas.TrainingSignArchiveResponse,
)
def archive_my_training_sign(
    sign_name: str,
    db: Session = Depends(get_db),
    trainer_name: str = Depends(get_current_trainer),
):
    """Arquiva todas as sessões de um sinal pertencentes ao professor atual."""
    name = canonical_visual_label(sign_name)
    aliases = ["BOM", "BOA"] if name == "BOM" else [name]
    samples = db.query(models.TrainingSample).filter(
        models.TrainingSample.trainer_name == trainer_name,
        models.TrainingSample.sign_name.in_(aliases),
        models.TrainingSample.deleted_at.is_(None),
    ).all()
    if not samples:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma sessão ativa deste sinal foi encontrada na sua conta.",
        )

    archived_at = datetime.utcnow()
    for sample in samples:
        sample.deleted_at = archived_at
        sample.deleted_by = trainer_name
    db.add(models.AuditLog(
        user_id=trainer_name,
        action="TRAINING_SIGN_OWNER_SOFT_DELETE",
        target=f"{name}:{len(samples)}_samples",
    ))
    db.commit()
    return {
        "sign_name": name,
        "archived_count": len(samples),
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
        models.TrainingSample.deleted_at.is_(None),
        _legacy_training_filter(),
    ).order_by(models.TrainingSample.created_at.desc()).limit(500).all()
    return [
        {
            "id": sample.id,
            "sign_name": sample.sign_name,
            "frame_count": sample.frame_count
            or len(sample.landmarks or []) // 21,
            "trainer_name": sample.trainer_name,
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
        models.TrainingSample.deleted_at.is_(None),
        _legacy_training_filter(),
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
    samples = db.query(models.TrainingSample).filter(
        models.TrainingSample.sign_name == name,
        models.TrainingSample.deleted_at.is_(None),
    ).all()
    deleted_at = datetime.utcnow()
    for sample in samples:
        sample.deleted_at = deleted_at
        sample.deleted_by = "administrator"
    deleted_count = len(samples)
    if deleted_count:
        db.add(models.AuditLog(
            action="TRAINING_SIGN_SOFT_DELETE",
            target=f"{name}:{deleted_count}_samples",
        ))
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
    samples = db.query(models.TrainingSample).filter(
        models.TrainingSample.sign_name == name,
        models.TrainingSample.deleted_at.is_(None),
    ).all()
    deleted_at = datetime.utcnow()
    for sample in samples:
        sample.deleted_at = deleted_at
        sample.deleted_by = "administrator"
    deleted_count = len(samples)

    if deleted_count == 0:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhuma amostra encontrada para o sinal '{name}'."
        )

    db.add(models.AuditLog(
        action="TRAINING_SIGN_SOFT_DELETE",
        target=f"{name}:{deleted_count}_samples",
    ))
    db.commit()
    return {"sign_name": name, "deleted_count": deleted_count}
