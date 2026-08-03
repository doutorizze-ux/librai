from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from math import sqrt
import logging
from threading import Lock
from time import monotonic
from typing import Protocol

import numpy as np

from schemas import HolisticFrame, Prediction, RecognitionChunk, RecognitionResponse


logger = logging.getLogger(__name__)


MIN_SEGMENT_FRAMES = 12
MAX_SEGMENT_FRAMES = 240
PRE_ROLL_FRAMES = 4
START_MOTION_THRESHOLD = 0.018
STOP_MOTION_THRESHOLD = 0.008
START_CONFIRMATION_FRAMES = 2
STOP_CONFIRMATION_FRAMES = 6
STREAM_TTL_SECONDS = 120.0


class ProductionRecognizer(Protocol):
    version: str

    def predict(self, frames: list[HolisticFrame]) -> tuple[str, float, float]:
        """Return gloss, confidence and runner-up confidence."""


def _ordered_hands(frame: HolisticFrame) -> list[np.ndarray | None]:
    slots: list[np.ndarray | None] = [None, None]
    unknown: list[np.ndarray] = []
    for hand in frame.hands:
        points = np.asarray(
            [[point.x, point.y, point.z] for point in hand.landmarks],
            dtype=np.float32,
        )
        slot = 0 if hand.handedness == "Left" else 1 if hand.handedness == "Right" else None
        if slot is None or slots[slot] is not None:
            unknown.append(points)
        else:
            slots[slot] = points
    for points in unknown:
        available = [index for index, value in enumerate(slots) if value is None]
        if not available:
            break
        preferred = 0 if float(points[0, 0]) <= 0.5 else 1
        slot = preferred if preferred in available else available[0]
        slots[slot] = points
    return slots


def _torso_scale(frame: HolisticFrame) -> float:
    # POSE_INDICES order: nose, ears, mouth, shoulders, elbows, wrists, hips.
    pose = frame.pose.landmarks
    left_shoulder = pose[5]
    right_shoulder = pose[6]
    distance = sqrt(
        (left_shoulder.x - right_shoulder.x) ** 2
        + (left_shoulder.y - right_shoulder.y) ** 2
        + (left_shoulder.z - right_shoulder.z) ** 2
    )
    return max(distance, 0.12)


def motion_energy(previous: HolisticFrame | None, current: HolisticFrame) -> float:
    if previous is None:
        return 0.0
    before = _ordered_hands(previous)
    after = _ordered_hands(current)
    distances: list[float] = []
    scale = (_torso_scale(previous) + _torso_scale(current)) / 2.0
    for first, second in zip(before, after):
        if first is None or second is None:
            continue
        delta = (second - first) / scale
        distances.extend(np.linalg.norm(delta, axis=1).tolist())
    if not distances:
        return 0.0
    # Median is robust to an occasional unstable fingertip.
    return float(np.median(np.asarray(distances, dtype=np.float32)))


@dataclass
class StreamState:
    last_sequence_number: int = -1
    previous_frame: HolisticFrame | None = None
    pre_roll: deque[HolisticFrame] = field(
        default_factory=lambda: deque(maxlen=PRE_ROLL_FRAMES)
    )
    active_frames: list[HolisticFrame] = field(default_factory=list)
    high_motion_frames: int = 0
    quiet_frames: int = 0
    saw_hands: bool = False
    last_seen: float = field(default_factory=monotonic)


class ContinuousRecognitionEngine:
    """Stateful boundary detector that refuses to invent model predictions."""

    def __init__(self, recognizer: ProductionRecognizer | None = None):
        self._recognizer = recognizer
        self._streams: dict[str, StreamState] = {}
        self._lock = Lock()

    def _state(self, stream_id: str) -> StreamState:
        state = self._streams.get(stream_id)
        if state is None:
            state = StreamState()
            self._streams[stream_id] = state
        state.last_seen = monotonic()
        return state

    def _remove_expired(self) -> None:
        cutoff = monotonic() - STREAM_TTL_SECONDS
        expired = [
            stream_id
            for stream_id, state in self._streams.items()
            if state.last_seen < cutoff
        ]
        for stream_id in expired:
            self._streams.pop(stream_id, None)

    def process(self, chunk: RecognitionChunk) -> RecognitionResponse:
        with self._lock:
            self._remove_expired()
            state = self._state(chunk.stream_id)
            if chunk.sequence_number <= state.last_sequence_number:
                raise ValueError("sequence_number must increase for each stream")
            state.last_sequence_number = chunk.sequence_number

            completed: list[list[HolisticFrame]] = []
            for frame in chunk.frames:
                state.saw_hands = state.saw_hands or bool(frame.hands)
                energy = motion_energy(state.previous_frame, frame)
                state.previous_frame = frame

                if not state.active_frames:
                    state.pre_roll.append(frame)
                    if frame.hands and energy >= START_MOTION_THRESHOLD:
                        state.high_motion_frames += 1
                    else:
                        state.high_motion_frames = 0
                    if state.high_motion_frames >= START_CONFIRMATION_FRAMES:
                        state.active_frames = list(state.pre_roll)
                        state.pre_roll.clear()
                        state.quiet_frames = 0
                    continue

                state.active_frames.append(frame)
                state.quiet_frames = (
                    state.quiet_frames + 1
                    if energy <= STOP_MOTION_THRESHOLD
                    else 0
                )
                if (
                    state.quiet_frames >= STOP_CONFIRMATION_FRAMES
                    or len(state.active_frames) >= MAX_SEGMENT_FRAMES
                ):
                    end = max(0, len(state.active_frames) - state.quiet_frames)
                    segment = state.active_frames[:end] or state.active_frames
                    if len(segment) >= MIN_SEGMENT_FRAMES:
                        completed.append(segment)
                    state.active_frames = []
                    state.high_motion_frames = 0
                    state.quiet_frames = 0
                    state.pre_roll.clear()

            if chunk.end_of_stream and state.active_frames:
                if len(state.active_frames) >= MIN_SEGMENT_FRAMES:
                    completed.append(list(state.active_frames))
                state.active_frames = []

            response = self._response(chunk, state, completed)
            if chunk.end_of_stream:
                self._streams.pop(chunk.stream_id, None)
            return response

    def _response(
        self,
        chunk: RecognitionChunk,
        state: StreamState,
        completed: list[list[HolisticFrame]],
    ) -> RecognitionResponse:
        if completed and self._recognizer is None:
            return RecognitionResponse(
                stream_id=chunk.stream_id,
                sequence_number=chunk.sequence_number,
                status="model_unavailable",
                model_version=None,
                reason="no_production_model",
            )

        predictions: list[Prediction] = []
        rejection_reason = None
        for segment in completed:
            assert self._recognizer is not None
            try:
                gloss, confidence, runner_up = self._recognizer.predict(segment)
            except Exception:
                logger.exception(
                    "production_model_inference_failed model=%s",
                    self._recognizer.version,
                )
                rejection_reason = "inference_error"
                continue
            if confidence < 0.85:
                rejection_reason = "low_confidence"
                continue
            if confidence - runner_up < 0.12:
                rejection_reason = "ambiguous"
                continue
            predictions.append(Prediction(
                gloss=gloss,
                confidence=confidence,
                start_timestamp_ms=segment[0].timestamp_ms,
                end_timestamp_ms=segment[-1].timestamp_ms,
                finalized=True,
            ))

        if predictions:
            status = "predicted"
        elif completed:
            status = "unknown"
        elif chunk.end_of_stream:
            status = "finished"
        elif state.active_frames:
            status = "segmenting"
        else:
            status = "observing"

        reason = rejection_reason
        if chunk.end_of_stream and not completed and not state.saw_hands:
            reason = "no_hands"
        elif chunk.end_of_stream and not completed and state.saw_hands:
            reason = "insufficient_motion"
        elif chunk.end_of_stream and reason is None:
            reason = "stream_finished"

        return RecognitionResponse(
            stream_id=chunk.stream_id,
            sequence_number=chunk.sequence_number,
            status=status,
            model_version=(self._recognizer.version if self._recognizer else None),
            predictions=predictions,
            reason=reason,
        )
