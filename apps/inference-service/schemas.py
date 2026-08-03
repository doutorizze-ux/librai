from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Landmark(BaseModel):
    x: float = Field(ge=-0.5, le=1.5, allow_inf_nan=False)
    y: float = Field(ge=-0.5, le=1.5, allow_inf_nan=False)
    z: float = Field(ge=-3.0, le=3.0, allow_inf_nan=False)


class Hand(BaseModel):
    handedness: Literal["Left", "Right", "Unknown"]
    score: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    landmarks: list[Landmark] = Field(min_length=21, max_length=21)


class Pose(BaseModel):
    landmarks: list[Landmark] = Field(min_length=13, max_length=13)


class DynamicExpression(BaseModel):
    mouth_open: float = Field(ge=0.0, le=2.0, allow_inf_nan=False)
    mouth_width: float = Field(ge=0.0, le=2.0, allow_inf_nan=False)
    left_brow: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    right_brow: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)


class HolisticFrame(BaseModel):
    timestamp_ms: int = Field(ge=0)
    hands: list[Hand] = Field(min_length=0, max_length=2)
    pose: Pose
    expression: DynamicExpression


class RecognitionChunk(BaseModel):
    protocol_version: Literal[1] = 1
    stream_id: str = Field(
        min_length=16,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    sequence_number: int = Field(ge=0)
    frames: list[HolisticFrame] = Field(min_length=0, max_length=120)
    end_of_stream: bool = False

    @field_validator("frames")
    @classmethod
    def validate_timestamps(cls, frames: list[HolisticFrame]):
        timestamps = [frame.timestamp_ms for frame in frames]
        if timestamps != sorted(timestamps) or len(timestamps) != len(set(timestamps)):
            raise ValueError("frame timestamps must be unique and increasing")
        return frames


class Prediction(BaseModel):
    gloss: str = Field(min_length=1, max_length=80)
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    start_timestamp_ms: int = Field(ge=0)
    end_timestamp_ms: int = Field(ge=0)
    finalized: bool = True


class RecognitionResponse(BaseModel):
    stream_id: str
    sequence_number: int
    status: Literal[
        "observing",
        "segmenting",
        "predicted",
        "unknown",
        "model_unavailable",
        "finished",
    ]
    model_version: str | None = None
    predictions: list[Prediction] = Field(default_factory=list, max_length=8)
    reason: Literal[
        "low_confidence",
        "ambiguous",
        "insufficient_motion",
        "no_hands",
        "no_production_model",
        "inference_error",
        "stream_finished",
    ] | None = None
