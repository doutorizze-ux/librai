from fastapi.testclient import TestClient

from continuous import ContinuousRecognitionEngine, motion_energy
from main import app
from schemas import HolisticFrame, RecognitionChunk


def frame(timestamp: int, hand_x: float | None = None) -> dict:
    hands = []
    if hand_x is not None:
        hands.append({
            "handedness": "Right",
            "score": 0.99,
            "landmarks": [
                {"x": hand_x + index * 0.001, "y": 0.4, "z": 0.0}
                for index in range(21)
            ],
        })
    pose = [{"x": 0.5, "y": 0.2, "z": 0.0} for _ in range(13)]
    pose[5] = {"x": 0.35, "y": 0.4, "z": 0.0}
    pose[6] = {"x": 0.65, "y": 0.4, "z": 0.0}
    return {
        "timestamp_ms": timestamp,
        "hands": hands,
        "pose": {"landmarks": pose},
        "expression": {
            "mouth_open": 0.1,
            "mouth_width": 0.3,
            "left_brow": 0.1,
            "right_brow": 0.1,
        },
    }


def test_motion_energy_uses_torso_normalization():
    first = HolisticFrame.model_validate(frame(0, 0.2))
    second = HolisticFrame.model_validate(frame(33, 0.23))
    assert 0.09 < motion_energy(first, second) < 0.11


def test_holistic_frame_accepts_mediapipe_depth_near_camera():
    payload = frame(0, 0.2)
    payload["pose"]["landmarks"][10]["z"] = -4.25

    parsed = HolisticFrame.model_validate(payload)

    assert parsed.pose.landmarks[10].z == -4.25


def test_completed_segment_is_never_guessed_without_production_model():
    engine = ContinuousRecognitionEngine(recognizer=None)
    frames = [frame(0, 0.2)]
    for index in range(1, 16):
        frames.append(frame(index * 33, 0.2 + index * 0.015))
    frames.extend(frame(index * 33, 0.425) for index in range(16, 24))
    result = engine.process(RecognitionChunk(
        protocol_version=1,
        stream_id="stream_1234567890",
        sequence_number=0,
        frames=frames,
        end_of_stream=True,
    ))
    assert result.status == "model_unavailable"
    assert result.predictions == []
    assert result.reason == "no_production_model"


def test_sequence_numbers_cannot_be_replayed():
    engine = ContinuousRecognitionEngine()
    chunk = RecognitionChunk(
        stream_id="stream_1234567890",
        sequence_number=2,
        frames=[],
        end_of_stream=False,
    )
    engine.process(chunk)
    try:
        engine.process(chunk)
    except ValueError as exc:
        assert "sequence_number" in str(exc)
    else:
        raise AssertionError("replayed chunk was accepted")


def test_http_contract_rejects_out_of_order_frame_timestamps():
    client = TestClient(app)
    response = client.post(
        "/internal/v1/recognition/chunks",
        json={
            "protocol_version": 1,
            "stream_id": "stream_1234567890",
            "sequence_number": 0,
            "frames": [frame(33, 0.2), frame(0, 0.3)],
            "end_of_stream": False,
        },
    )
    assert response.status_code == 422


def test_runtime_failure_is_reported_without_guessing_a_sign():
    class BrokenRecognizer:
        version = "broken-test-model"

        def predict(self, frames):
            raise RuntimeError("simulated runtime failure")

    engine = ContinuousRecognitionEngine(recognizer=BrokenRecognizer())
    frames = [frame(0, 0.2)]
    for index in range(1, 16):
        frames.append(frame(index * 33, 0.2 + index * 0.015))
    frames.extend(frame(index * 33, 0.425) for index in range(16, 24))
    result = engine.process(RecognitionChunk(
        protocol_version=1,
        stream_id="stream_failure_12345",
        sequence_number=0,
        frames=frames,
        end_of_stream=True,
    ))
    assert result.status == "unknown"
    assert result.predictions == []
    assert result.reason == "inference_error"
