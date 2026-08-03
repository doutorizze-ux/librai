from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import List, Literal, Optional
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
class TrainerLoginRequest(BaseModel):
    trainer_name: str = Field(min_length=2, max_length=80)
    access_code: str = Field(min_length=8, max_length=128)

    @field_validator("trainer_name")
    @classmethod
    def normalize_trainer_name(cls, value: str) -> str:
        return " ".join(value.strip().split())


class TrainerTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int = 604800


class TrainingLandmark(BaseModel):
    x: float = Field(ge=-0.5, le=1.5, allow_inf_nan=False)
    y: float = Field(ge=-0.5, le=1.5, allow_inf_nan=False)
    z: float = Field(ge=-3.0, le=3.0, allow_inf_nan=False)


class TrainingSampleCreate(BaseModel):
    sign_name: str = Field(min_length=1, max_length=64)
    landmarks: List[TrainingLandmark] = Field(min_length=210, max_length=5040)

    @field_validator("landmarks")
    @classmethod
    def validate_complete_hands(cls, value):
        if len(value) % 21 != 0:
            raise ValueError("landmarks deve conter blocos completos de 21 pontos")
        signatures = set()
        for offset in range(0, len(value), 21):
            hand = value[offset:offset + 21]
            signatures.add(tuple(
                (round(point.x, 5), round(point.y, 5), round(point.z, 5))
                for point in hand
            ))
        if len(signatures) < 3:
            raise ValueError(
                "captura sem variação suficiente; grave quadros novos da câmera"
            )
        return value


class TrainingHand(BaseModel):
    handedness: str = Field(pattern="^(Left|Right|Unknown)$")
    score: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    landmarks: List[TrainingLandmark] = Field(min_length=21, max_length=21)


class TrainingFrame(BaseModel):
    timestamp_ms: int = Field(ge=0)
    hands: List[TrainingHand] = Field(min_length=1, max_length=2)


class AssistedPredictionRequest(BaseModel):
    format_version: int = Field(default=1, ge=1, le=1)
    frames: List[TrainingFrame] = Field(min_length=12, max_length=180)

    @field_validator("frames")
    @classmethod
    def validate_timestamps(cls, value):
        timestamps = [frame.timestamp_ms for frame in value]
        if timestamps != sorted(timestamps) or len(timestamps) != len(set(timestamps)):
            raise ValueError("timestamps dos quadros devem ser únicos e crescentes")
        return value


class AssistedPredictionCandidate(BaseModel):
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)


class AssistedPredictionResponse(BaseModel):
    model: str = Field(default="motion_tcn_v1", pattern="^motion_tcn_v1$")
    candidates: List[AssistedPredictionCandidate] = Field(
        min_length=0,
        max_length=3,
    )


class TrainingSampleCreateV2(BaseModel):
    sign_name: str = Field(min_length=1, max_length=64)
    format_version: int = Field(default=2, ge=2, le=2)
    frames: List[TrainingFrame] = Field(min_length=12, max_length=180)

    @field_validator("frames")
    @classmethod
    def validate_timestamps(cls, value):
        timestamps = [frame.timestamp_ms for frame in value]
        if timestamps != sorted(timestamps) or len(timestamps) != len(set(timestamps)):
            raise ValueError("timestamps dos quadros devem ser únicos e crescentes")
        return value


class TrainingRepetitionV2(BaseModel):
    frames: List[TrainingFrame] = Field(min_length=12, max_length=180)

    @field_validator("frames")
    @classmethod
    def validate_timestamps(cls, value):
        timestamps = [frame.timestamp_ms for frame in value]
        if timestamps != sorted(timestamps) or len(timestamps) != len(set(timestamps)):
            raise ValueError("timestamps dos quadros devem ser únicos e crescentes")
        return value


class TrainingBatchCreateV2(BaseModel):
    sign_name: str = Field(min_length=1, max_length=64)
    format_version: int = Field(default=2, ge=2, le=2)
    repetitions: List[TrainingRepetitionV2] = Field(min_length=5, max_length=5)


class TrainingCaptureContextV3(BaseModel):
    platform: str = Field(
        pattern="^(android|ios|web|windows|macos|linux|other)$"
    )
    camera_facing: str = Field(
        pattern="^(front|back|external|unknown)$"
    )
    app_version: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=32,
    )


class TrainingRepetitionV3(BaseModel):
    frames: List[TrainingFrame] = Field(min_length=24, max_length=180)

    @field_validator("frames")
    @classmethod
    def validate_timestamps(cls, value):
        timestamps = [frame.timestamp_ms for frame in value]
        if (
            timestamps != sorted(timestamps)
            or len(timestamps) != len(set(timestamps))
        ):
            raise ValueError(
                "timestamps dos quadros devem ser únicos e crescentes"
            )
        return value


class TrainingBatchCreateV3(BaseModel):
    sign_name: str = Field(
        min_length=1,
        max_length=40,
        pattern=(
            r"^[A-Za-zÀ-ÖØ-öø-ÿ0-9]+"
            r"(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ0-9]+)*$"
        ),
    )
    format_version: int = Field(default=3, ge=3, le=3)
    capture_context: TrainingCaptureContextV3
    repetitions: List[TrainingRepetitionV3] = Field(
        min_length=5,
        max_length=5,
    )

    @field_validator("sign_name")
    @classmethod
    def normalize_isolated_sign_name(cls, value: str) -> str:
        return value.strip().upper()


class TrainingDraftRepetitionCreate(BaseModel):
    capture_id: str = Field(
        min_length=16,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    sign_name: str = Field(
        min_length=1,
        max_length=40,
        pattern=(
            r"^[A-Za-zÀ-ÖØ-öø-ÿ0-9]+"
            r"(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ0-9]+)*$"
        ),
    )
    format_version: int = Field(default=3, ge=3, le=3)
    capture_context: TrainingCaptureContextV3
    frames: List[TrainingFrame] = Field(min_length=24, max_length=180)

    @field_validator("sign_name")
    @classmethod
    def normalize_draft_sign_name(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("frames")
    @classmethod
    def validate_draft_timestamps(cls, value):
        timestamps = [frame.timestamp_ms for frame in value]
        if (
            timestamps != sorted(timestamps)
            or len(timestamps) != len(set(timestamps))
        ):
            raise ValueError(
                "timestamps dos quadros devem ser únicos e crescentes"
            )
        return value


class TrainingDraftRepetitionResponse(BaseModel):
    sign_name: str
    repetitions_saved: int = Field(ge=1, le=5)
    required_repetitions: int = Field(default=5, ge=5, le=5)
    completed: bool
    duplicate: bool = False


class TrainingDraftStatusResponse(BaseModel):
    active: bool
    sign_name: Optional[str] = None
    repetitions_saved: int = Field(ge=0, le=4)
    required_repetitions: int = Field(default=5, ge=5, le=5)


class TrainingSampleResponse(BaseModel):
    id: str
    sign_name: str
    landmarks: List[dict]
    created_at: datetime

    class Config:
        from_attributes = True


class TrainingSampleMetadataResponse(BaseModel):
    id: str
    sign_name: str
    frame_count: int
    trainer_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TrainingSignArchiveResponse(BaseModel):
    sign_name: str
    archived_count: int = Field(ge=1)


class TrainingFeature(BaseModel):
    label: str
    angles: List[float]


class TrainingModelResponse(BaseModel):
    version: str
    feature_schema: str = "hand_angles_v1"
    threshold: float
    features: List[TrainingFeature]


# --- DEVELOPER API AND HOLISTIC CONTINUOUS RECOGNITION ---
class HolisticLandmarkV4(BaseModel):
    """Landmark range used by MediaPipe holistic capture.

    Depth is relative to the body/camera scale and can legitimately exceed the
    narrower range used by the legacy hand-only collector.
    """

    x: float = Field(ge=-0.5, le=1.5, allow_inf_nan=False)
    y: float = Field(ge=-0.5, le=1.5, allow_inf_nan=False)
    z: float = Field(ge=-10.0, le=10.0, allow_inf_nan=False)


class HolisticHandV4(BaseModel):
    handedness: Literal["Left", "Right", "Unknown"]
    score: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    landmarks: List[HolisticLandmarkV4] = Field(min_length=21, max_length=21)


class HolisticPose(BaseModel):
    landmarks: List[HolisticLandmarkV4] = Field(min_length=13, max_length=13)


class DynamicExpression(BaseModel):
    mouth_open: float = Field(ge=0.0, le=2.0, allow_inf_nan=False)
    mouth_width: float = Field(ge=0.0, le=2.0, allow_inf_nan=False)
    left_brow: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    right_brow: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)


class HolisticFrameV4(BaseModel):
    timestamp_ms: int = Field(ge=0)
    hands: List[HolisticHandV4] = Field(min_length=0, max_length=2)
    pose: HolisticPose
    expression: DynamicExpression


class HolisticPredictionRequestV4(BaseModel):
    format_version: Literal[4] = 4
    frames: List[HolisticFrameV4] = Field(min_length=24, max_length=120)

    @field_validator("frames")
    @classmethod
    def validate_prediction_timestamps(cls, value):
        timestamps = [frame.timestamp_ms for frame in value]
        if (
            timestamps != sorted(timestamps)
            or len(timestamps) != len(set(timestamps))
        ):
            raise ValueError(
                "timestamps dos quadros devem ser únicos e crescentes"
            )
        return value


class HolisticPredictionResponseV4(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    model: Literal["holistic_sequence_v4"] = "holistic_sequence_v4"
    support: int = Field(ge=0)


class HolisticLinguisticMetadataV4(BaseModel):
    regional_variation: str = Field(min_length=2, max_length=80)
    dominant_hand: Literal["Left", "Right", "Ambidextrous", "Unknown"]


class HolisticTrainingRepetitionV4(BaseModel):
    capture_id: str = Field(
        min_length=16,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    frames: List[HolisticFrameV4] = Field(min_length=24, max_length=240)

    @field_validator("frames")
    @classmethod
    def validate_holistic_timestamps(cls, value):
        timestamps = [frame.timestamp_ms for frame in value]
        if (
            timestamps != sorted(timestamps)
            or len(timestamps) != len(set(timestamps))
        ):
            raise ValueError(
                "timestamps dos quadros devem ser únicos e crescentes"
            )
        return value


class HolisticTrainingBatchCreateV4(BaseModel):
    format_version: Literal[4] = 4
    sign_name: str = Field(min_length=1, max_length=64)
    capture_context: TrainingCaptureContextV3
    linguistic_metadata: HolisticLinguisticMetadataV4
    repetitions: List[HolisticTrainingRepetitionV4] = Field(
        min_length=5,
        max_length=5,
    )

    @field_validator("sign_name")
    @classmethod
    def normalize_holistic_sign_name(cls, value: str) -> str:
        return " ".join(value.strip().upper().split())


class HolisticTrainingDraftRepetitionCreateV4(BaseModel):
    capture_id: str = Field(
        min_length=16,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    format_version: Literal[4] = 4
    sign_name: str = Field(min_length=1, max_length=64)
    capture_context: TrainingCaptureContextV3
    linguistic_metadata: HolisticLinguisticMetadataV4
    frames: List[HolisticFrameV4] = Field(min_length=24, max_length=240)

    @field_validator("sign_name")
    @classmethod
    def normalize_holistic_draft_sign_name(cls, value: str) -> str:
        return " ".join(value.strip().upper().split())

    @field_validator("frames")
    @classmethod
    def validate_holistic_draft_timestamps(cls, value):
        timestamps = [frame.timestamp_ms for frame in value]
        if (
            timestamps != sorted(timestamps)
            or len(timestamps) != len(set(timestamps))
        ):
            raise ValueError(
                "timestamps dos quadros devem ser únicos e crescentes"
            )
        return value


class ContinuousRecognitionChunk(BaseModel):
    protocol_version: Literal[1] = 1
    stream_id: str = Field(
        min_length=16,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    sequence_number: int = Field(ge=0)
    frames: List[HolisticFrameV4] = Field(min_length=0, max_length=120)
    end_of_stream: bool = False

    @field_validator("frames")
    @classmethod
    def validate_continuous_timestamps(cls, value):
        timestamps = [frame.timestamp_ms for frame in value]
        if (
            timestamps != sorted(timestamps)
            or len(timestamps) != len(set(timestamps))
        ):
            raise ValueError(
                "timestamps dos quadros devem ser únicos e crescentes"
            )
        return value


class DeveloperCredentialCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    scopes: List[Literal[
        "translation:recognize",
        "models:read",
        "usage:read",
    ]] = Field(min_length=1)
    expires_at: Optional[datetime] = None

    @field_validator("scopes")
    @classmethod
    def validate_unique_scopes(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("escopos não podem ser repetidos")
        return value


class DeveloperCredentialCreated(BaseModel):
    id: str
    name: str
    key_prefix: str
    api_key: str
    scopes: List[str]
    expires_at: Optional[datetime]
    created_at: datetime


class DeveloperCredentialMetadata(BaseModel):
    id: str
    name: str
    key_prefix: str
    scopes: List[str]
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    last_used_at: Optional[datetime]
    request_count: int

    class Config:
        from_attributes = True
