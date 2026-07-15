from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

# --- AUTH SCHEMAS ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# --- PRIVACY SCHEMAS ---
class ConsentCreate(BaseModel):
    consent_type: str
    version: str
    accepted: bool

class ConsentResponse(BaseModel):
    id: str
    consent_type: str
    version: str
    accepted: bool
    signed_at: datetime

    class Config:
        from_attributes = True

class PrivacyRequestCreate(BaseModel):
    request_type: str # "EXPORT" or "DELETE"

# --- TRANSLATION SCHEMAS ---
class SessionResponse(BaseModel):
    id: str
    user_id: Optional[str]
    created_at: datetime
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True

class SegmentCreate(BaseModel):
    text_detected: str
    confidence: float
    raw_landmarks_ref: Optional[str] = None

class SegmentResponse(BaseModel):
    id: str
    session_id: str
    text_detected: str
    confidence: float
    created_at: datetime

    class Config:
        from_attributes = True

class CorrectionCreate(BaseModel):
    corrected_text: str

class CorrectionResponse(BaseModel):
    id: str
    segment_id: str
    corrected_text: str
    approved: bool
    created_at: datetime

    class Config:
        from_attributes = True

# --- DICTIONARY SCHEMAS ---
class CategoryResponse(BaseModel):
    id: str
    name: str

    class Config:
        from_attributes = True

class SignResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    category_id: Optional[str]
    regionality: Optional[str]
    usage_context: Optional[str]

    class Config:
        from_attributes = True

# --- MODEL SCHEMAS ---
class ModelResponse(BaseModel):
    id: str
    name: str
    version: str
    hash_sha256: str
    is_active: bool
    deployed_at: datetime

    class Config:
        from_attributes = True

# --- AUDIT SCHEMAS ---
class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str]
    action: str
    target: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


# --- TRAINING SCHEMAS ---
class TrainingSampleCreate(BaseModel):
    sign_name: str
    landmarks: List[dict]

class TrainingSampleResponse(BaseModel):
    id: str
    sign_name: str
    landmarks: List[dict]
    created_at: datetime

    class Config:
        from_attributes = True
