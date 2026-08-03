from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db


router = APIRouter(prefix="/v1", tags=["developer-api"])

INFERENCE_SERVICE_URL = os.getenv(
    "INFERENCE_SERVICE_URL",
    "http://inference-service:8001",
).rstrip("/")
API_KEY_PEPPER = os.getenv("API_KEY_PEPPER", "")
ADMIN_API_SECRET = os.getenv("ADMIN_API_SECRET", "")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_key(raw_key: str) -> str:
    if not API_KEY_PEPPER:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credenciais de desenvolvedor ainda não foram configuradas.",
        )
    return hashlib.sha256(
        f"{API_KEY_PEPPER}:{raw_key}".encode("utf-8")
    ).hexdigest()


def _require_admin_secret(value: str) -> None:
    if not ADMIN_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administração de credenciais ainda não foi configurada.",
        )
    if not secrets.compare_digest(value, ADMIN_API_SECRET):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Credencial administrativa inválida.",
        )


def _parse_prefix(raw_key: str) -> str | None:
    parts = raw_key.split("_", 2)
    if len(parts) != 3 or parts[0] != "librai" or len(parts[1]) != 10:
        return None
    return parts[1]


def require_developer_scope(required_scope: str):
    def dependency(
        x_librai_key: str = Header(..., alias="X-Librai-Key"),
        db: Session = Depends(get_db),
    ) -> models.DeveloperCredential:
        prefix = _parse_prefix(x_librai_key)
        if prefix is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credencial de API inválida.",
            )
        credential = db.query(models.DeveloperCredential).filter(
            models.DeveloperCredential.key_prefix == prefix,
            models.DeveloperCredential.is_active.is_(True),
        ).first()
        if credential is None or not secrets.compare_digest(
            credential.key_hash,
            _hash_key(x_librai_key),
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credencial de API inválida.",
            )
        now = _utcnow()
        if credential.expires_at and credential.expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credencial de API expirada.",
            )
        if required_scope not in set(credential.scopes or []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Credencial sem permissão para este recurso.",
            )
        credential.last_used_at = now
        credential.request_count = int(credential.request_count or 0) + 1
        db.commit()
        return credential

    return dependency


@router.post(
    "/admin/developer-credentials",
    response_model=schemas.DeveloperCredentialCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_developer_credential(
    request: schemas.DeveloperCredentialCreate,
    x_librai_admin_secret: str = Header(..., alias="X-Librai-Admin-Secret"),
    db: Session = Depends(get_db),
):
    _require_admin_secret(x_librai_admin_secret)
    prefix = secrets.token_hex(5)
    raw_key = f"librai_{prefix}_{secrets.token_urlsafe(32)}"
    credential = models.DeveloperCredential(
        name=request.name.strip(),
        key_prefix=prefix,
        key_hash=_hash_key(raw_key),
        scopes=list(request.scopes),
        expires_at=(
            request.expires_at.astimezone(timezone.utc).replace(tzinfo=None)
            if request.expires_at and request.expires_at.tzinfo
            else request.expires_at
        ),
    )
    db.add(credential)
    db.add(models.AuditLog(
        action="DEVELOPER_CREDENTIAL_CREATE",
        target=f"{prefix}:{','.join(request.scopes)}",
    ))
    db.commit()
    db.refresh(credential)
    return {
        "id": credential.id,
        "name": credential.name,
        "key_prefix": credential.key_prefix,
        "api_key": raw_key,
        "scopes": credential.scopes,
        "expires_at": credential.expires_at,
        "created_at": credential.created_at,
    }


@router.get(
    "/admin/developer-credentials",
    response_model=list[schemas.DeveloperCredentialMetadata],
)
def list_developer_credentials(
    x_librai_admin_secret: str = Header(..., alias="X-Librai-Admin-Secret"),
    db: Session = Depends(get_db),
):
    _require_admin_secret(x_librai_admin_secret)
    return db.query(models.DeveloperCredential).order_by(
        models.DeveloperCredential.created_at.desc()
    ).all()


@router.delete("/admin/developer-credentials/{credential_id}")
def revoke_developer_credential(
    credential_id: str,
    x_librai_admin_secret: str = Header(..., alias="X-Librai-Admin-Secret"),
    db: Session = Depends(get_db),
):
    _require_admin_secret(x_librai_admin_secret)
    credential = db.query(models.DeveloperCredential).filter(
        models.DeveloperCredential.id == credential_id,
    ).first()
    if credential is None:
        raise HTTPException(status_code=404, detail="Credencial não encontrada.")
    credential.is_active = False
    db.add(models.AuditLog(
        action="DEVELOPER_CREDENTIAL_REVOKE",
        target=credential.key_prefix,
    ))
    db.commit()
    return {"id": credential.id, "revoked": True}


def _forward_recognition(payload: dict) -> tuple[int, dict]:
    try:
        response = httpx.post(
            f"{INFERENCE_SERVICE_URL}/internal/v1/recognition/chunks",
            json=payload,
            timeout=httpx.Timeout(3.0, connect=1.0),
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Motor de reconhecimento temporariamente indisponível.",
        ) from exc
    try:
        body = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Resposta inválida do motor de reconhecimento.",
        ) from exc
    return response.status_code, body


@router.post("/developer/recognition/chunks")
def recognize_continuous_chunk(
    chunk: schemas.ContinuousRecognitionChunk,
    credential: models.DeveloperCredential = Depends(
        require_developer_scope("translation:recognize")
    ),
):
    response_status, body = _forward_recognition(chunk.model_dump())
    if response_status >= 400:
        raise HTTPException(
            status_code=response_status,
            detail=body.get("detail", "Falha no motor de reconhecimento."),
        )
    return body
