import pytest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
from main import app
import models
from routers import developer, training, translation

# Configuração de banco de dados SQLite temporário para testes
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Sobrescrever a dependência get_db do FastAPI para usar o banco de testes
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    training.TRAINER_ACCESS_CODE = "codigo-professores-seguro"
    training.TRAINER_DELETE_SECRET = "segredo-admin-exclusao"
    developer.API_KEY_PEPPER = "pepper-de-teste-seguro"
    developer.ADMIN_API_SECRET = "segredo-admin-api-seguro"
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def create_developer_key(scopes=None):
    response = client.post(
        "/v1/admin/developer-credentials",
        headers={"X-Librai-Admin-Secret": "segredo-admin-api-seguro"},
        json={
            "name": "Integração de teste",
            "scopes": scopes or ["translation:recognize"],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_developer_key_is_returned_once_and_stored_as_hash():
    created = create_developer_key()
    assert created["api_key"].startswith(
        f"librai_{created['key_prefix']}_"
    )

    listed = client.get(
        "/v1/admin/developer-credentials",
        headers={"X-Librai-Admin-Secret": "segredo-admin-api-seguro"},
    )
    assert listed.status_code == 200
    assert listed.json()[0]["key_prefix"] == created["key_prefix"]
    assert "api_key" not in listed.json()[0]

    with TestingSessionLocal() as db:
        stored = db.query(models.DeveloperCredential).one()
        assert stored.key_hash != created["api_key"]
        assert created["api_key"] not in stored.key_hash


def test_continuous_recognition_requires_scoped_developer_key(monkeypatch):
    denied = client.post(
        "/v1/developer/recognition/chunks",
        headers={"X-Librai-Key": "librai_invalid_invalid"},
        json={
            "protocol_version": 1,
            "stream_id": "stream_1234567890",
            "sequence_number": 0,
            "frames": [],
            "end_of_stream": False,
        },
    )
    assert denied.status_code == 401

    credential = create_developer_key(scopes=["models:read"])
    forbidden = client.post(
        "/v1/developer/recognition/chunks",
        headers={"X-Librai-Key": credential["api_key"]},
        json={
            "protocol_version": 1,
            "stream_id": "stream_1234567890",
            "sequence_number": 0,
            "frames": [],
            "end_of_stream": False,
        },
    )
    assert forbidden.status_code == 403


def test_continuous_recognition_proxies_validated_payload(monkeypatch):
    credential = create_developer_key()

    def fake_forward(payload):
        return 200, {
            "stream_id": payload["stream_id"],
            "sequence_number": payload["sequence_number"],
            "status": "observing",
            "model_version": None,
            "predictions": [],
        }

    monkeypatch.setattr(developer, "_forward_recognition", fake_forward)
    response = client.post(
        "/v1/developer/recognition/chunks",
        headers={"X-Librai-Key": credential["api_key"]},
        json={
            "protocol_version": 1,
            "stream_id": "stream_1234567890",
            "sequence_number": 0,
            "frames": [],
            "end_of_stream": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "observing"


def test_revoked_developer_key_stops_working(monkeypatch):
    credential = create_developer_key()
    revoked = client.delete(
        f"/v1/admin/developer-credentials/{credential['id']}",
        headers={"X-Librai-Admin-Secret": "segredo-admin-api-seguro"},
    )
    assert revoked.status_code == 200

    response = client.post(
        "/v1/developer/recognition/chunks",
        headers={"X-Librai-Key": credential["api_key"]},
        json={
            "protocol_version": 1,
            "stream_id": "stream_1234567890",
            "sequence_number": 0,
            "frames": [],
            "end_of_stream": True,
        },
    )
    assert response.status_code == 401


def trainer_headers(name="Professora Teste"):
    response = client.post(
        "/v1/training/auth",
        json={
            "trainer_name": name,
            "access_code": "codigo-professores-seguro",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def valid_training_landmarks():
    frames = []
    for frame in range(10):
        frames.extend([
            {
                "x": index / 100 + frame / 10000,
                "y": (index % 5) / 10,
                "z": index / 1000,
            }
            for index in range(21)
        ])
    return frames


def test_changing_trainer_code_invalidates_existing_session():
    headers = trainer_headers("Professora Ana")
    training.TRAINER_ACCESS_CODE = "novo-codigo-professores"

    response = client.get("/v1/training/my-samples", headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Sessão de treinamento inválida ou expirada."
    )


def test_administrator_code_can_open_trainer_panel():
    response = client.post(
        "/v1/training/auth",
        json={
            "trainer_name": "Administrador",
            "access_code": "segredo-admin-exclusao",
        },
    )

    assert response.status_code == 200
    assert response.json()["expires_in_seconds"] == 604800
    token = response.json()["access_token"]
    listed = client.get(
        "/v1/training/my-samples",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200


def temporal_landmark_frames(movement_per_frame=0.0, frame_count=16):
    frames = []
    for frame_index in range(frame_count):
        offset = movement_per_frame * frame_index
        frames.append([
            {
                "x": index / 100 + offset,
                "y": (index % 5) / 10,
                "z": index / 1000 + (frame_index * 0.00001 if index else 0),
            }
            for index in range(21)
        ])
    return frames


def structured_hand_frames(
    left_movement=0.0,
    right_movement=0.0,
    frame_count=16,
    two_hands=True,
):
    frames = []
    for frame_index in range(frame_count):
        hands = []
        sides = (("Left", left_movement), ("Right", right_movement))
        for side, movement in sides[:2 if two_hands else 1]:
            offset = movement * frame_index
            hands.append({
                "handedness": side,
                "score": 0.99,
                "landmarks": [
                    {
                        "x": index / 100 + offset + (
                            0.35 if side == "Right" else 0.0
                        ),
                        "y": (index % 5) / 10,
                        "z": index / 1000,
                    }
                    for index in range(21)
                ],
            })
        frames.append({
            "timestamp_ms": 1_000 + frame_index * 33,
            "hands": hands,
        })
    return frames


def holistic_frames(repetition_offset=0.0, frame_count=24, hand_ratio=1.0):
    frames = []
    hand_frame_limit = round(frame_count * hand_ratio)
    for frame_index in range(frame_count):
        hands = []
        if frame_index < hand_frame_limit:
            hands.append({
                "handedness": "Right",
                "score": 0.99,
                "landmarks": [
                    {
                        "x": 0.2 + repetition_offset + frame_index * 0.004 + index * 0.001,
                        "y": 0.35 + (index % 5) * 0.002,
                        "z": index * 0.0005,
                    }
                    for index in range(21)
                ],
            })
        pose = [
            {"x": 0.3 + index * 0.02, "y": 0.2 + index * 0.01, "z": 0.0}
            for index in range(13)
        ]
        frames.append({
            "timestamp_ms": frame_index * 33,
            "hands": hands,
            "pose": {"landmarks": pose},
            "expression": {
                "mouth_open": 0.1,
                "mouth_width": 0.3,
                "left_brow": 0.1,
                "right_brow": 0.1,
            },
        })
    return frames


def holistic_batch(sign_name="OLÁ"):
    return {
        "format_version": 4,
        "sign_name": sign_name,
        "capture_context": {
            "platform": "web",
            "camera_facing": "front",
            "app_version": "test",
        },
        "linguistic_metadata": {
            "regional_variation": "Minas Gerais",
            "dominant_hand": "Right",
        },
        "repetitions": [
            {
                "capture_id": f"capture_holistic_{index:02d}",
                "frames": holistic_frames(index * 0.003),
            }
            for index in range(5)
        ],
    }


def test_holistic_training_batch_is_persisted_but_not_auto_deployed():
    response = client.post(
        "/v1/training/batches-v4",
        headers=trainer_headers("Professora Holística"),
        json=holistic_batch(),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["repetitions_created"] == 5
    assert body["dataset_state"] == "pending_validation"
    assert body["used_by_production_model"] is False

    with TestingSessionLocal() as db:
        samples = db.query(models.TrainingSample).all()
        assert len(samples) == 5
        assert all(sample.landmarks["format_version"] == 4 for sample in samples)
        assert all(
            sample.landmarks["dataset_state"] == "pending_validation"
            for sample in samples
        )


def test_holistic_training_keeps_multiword_label_as_one_libras_unit():
    response = client.post(
        "/v1/training/batches-v4",
        headers=trainer_headers("Professora Unidade Semantica"),
        json=holistic_batch("  Tudo   bem?  "),
    )
    assert response.status_code == 201, response.text
    assert response.json()["sign_name"] == "TUDO BEM?"

    with TestingSessionLocal() as db:
        samples = db.query(models.TrainingSample).all()
        assert len(samples) == 5
        assert {sample.sign_name for sample in samples} == {"TUDO BEM?"}


def test_holistic_draft_persists_each_repetition_and_completes_multiword_unit():
    trainer_name = "Professora Holistica Rascunho"
    headers = trainer_headers(trainer_name)

    for index in range(3):
        response = client.post(
            "/v1/training/drafts-v4/repetitions",
            headers=headers,
            json={
                "capture_id": f"draft_holistic_capture_{index:02d}",
                "format_version": 4,
                "sign_name": "Tudo bem?",
                "capture_context": {
                    "platform": "web",
                    "camera_facing": "front",
                    "app_version": "test",
                },
                "linguistic_metadata": {
                    "regional_variation": "Minas Gerais",
                    "dominant_hand": "Right",
                },
                "frames": holistic_frames(index * 0.003),
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["repetitions_saved"] == index + 1
        assert response.json()["completed"] is False

    restored = client.get("/v1/training/drafts/current", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["sign_name"] == "TUDO BEM?"
    assert restored.json()["repetitions_saved"] == 3

    with TestingSessionLocal() as db:
        assert db.query(models.TrainingSample).count() == 0

    for index in range(3, 5):
        response = client.post(
            "/v1/training/drafts-v4/repetitions",
            headers=headers,
            json={
                "capture_id": f"draft_holistic_capture_{index:02d}",
                "format_version": 4,
                "sign_name": "Tudo bem?",
                "capture_context": {
                    "platform": "web",
                    "camera_facing": "front",
                    "app_version": "test",
                },
                "linguistic_metadata": {
                    "regional_variation": "Minas Gerais",
                    "dominant_hand": "Right",
                },
                "frames": holistic_frames(index * 0.003),
            },
        )
        assert response.status_code == 201, response.text

    assert response.json()["completed"] is True
    assert response.json()["repetitions_saved"] == 5
    with TestingSessionLocal() as db:
        samples = db.query(models.TrainingSample).all()
        assert len(samples) == 5
        assert {sample.sign_name for sample in samples} == {"TUDO BEM?"}
        assert all(sample.landmarks["format_version"] == 4 for sample in samples)
        assert all(
            sample.landmarks["dataset_state"] == "pending_validation"
            for sample in samples
        )


def test_holistic_draft_accepts_mediapipe_depth_near_camera():
    frames = holistic_frames()
    for frame in frames:
        frame["pose"]["landmarks"][10]["z"] = -4.25

    response = client.post(
        "/v1/training/drafts-v4/repetitions",
        headers=trainer_headers("Professora Profundidade"),
        json={
            "capture_id": "depth_near_camera_01",
            "format_version": 4,
            "sign_name": "Ola",
            "capture_context": {
                "platform": "web",
                "camera_facing": "front",
                "app_version": "test",
            },
            "linguistic_metadata": {
                "regional_variation": "Minas Gerais",
                "dominant_hand": "Right",
            },
            "frames": frames,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["repetitions_saved"] == 1


def test_holistic_training_rejects_replayed_capture_ids():
    headers = trainer_headers("Professora Holística")
    first = client.post(
        "/v1/training/batches-v4",
        headers=headers,
        json=holistic_batch(),
    )
    assert first.status_code == 201
    replay = client.post(
        "/v1/training/batches-v4",
        headers=headers,
        json=holistic_batch("AJUDA"),
    )
    assert replay.status_code == 409


def test_holistic_training_rejects_capture_with_missing_hands():
    payload = holistic_batch()
    payload["repetitions"][0]["frames"] = holistic_frames(
        repetition_offset=0.0,
        hand_ratio=0.5,
    )
    response = client.post(
        "/v1/training/batches-v4",
        headers=trainer_headers("Professora Holística"),
        json=payload,
    )
    assert response.status_code == 422
    assert "mãos" in response.json()["detail"].lower()


def test_assisted_prediction_requires_a_complete_ordered_capture():
    too_short = client.post(
        "/v1/translation/predict-assisted",
        json={
            "format_version": 1,
            "frames": structured_hand_frames(frame_count=11),
        },
    )
    assert too_short.status_code == 422

    unordered = structured_hand_frames(frame_count=12)
    unordered[1]["timestamp_ms"] = unordered[0]["timestamp_ms"]
    duplicate_timestamp = client.post(
        "/v1/translation/predict-assisted",
        json={"format_version": 1, "frames": unordered},
    )
    assert duplicate_timestamp.status_code == 422


def test_assisted_prediction_returns_at_most_three_candidates(monkeypatch):
    class FakeRecognizer:
        def predict(self, frames):
            assert len(frames) == 12
            return [
                {"label": "BOM", "confidence": 0.61},
                {"label": "TARDE", "confidence": 0.25},
                {"label": "NOITE", "confidence": 0.09},
            ]

    monkeypatch.setattr(
        translation,
        "get_assisted_recognizer",
        lambda: FakeRecognizer(),
    )
    response = client.post(
        "/v1/translation/predict-assisted",
        json={
            "format_version": 1,
            "frames": structured_hand_frames(frame_count=12),
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "model": "motion_tcn_v1",
        "candidates": [
            {"label": "BOM", "confidence": 0.61},
            {"label": "TARDE", "confidence": 0.25},
            {"label": "NOITE", "confidence": 0.09},
        ],
    }


def test_assisted_prediction_loads_packaged_model():
    response = client.post(
        "/v1/translation/predict-assisted",
        json={
            "format_version": 1,
            "frames": structured_hand_frames(
                left_movement=0.001,
                right_movement=0.002,
                frame_count=64,
            ),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "motion_tcn_v1"
    assert len(data["candidates"]) == 3
    assert all(candidate["label"] for candidate in data["candidates"])


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["training_storage"] == {
        "total_samples": 0,
        "active_samples": 0,
        "archived_samples": 0,
        "integrity": "ok",
        "last_backup_at": None,
        "external_backup": False,
    }


def test_vlibras_reference_catalog_search():
    response = client.get("/v1/vlibras-reference/catalog?query=boa%20noite&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "1.0"
    assert data["source"] == "VLibras"
    assert data["total"] >= 1
    assert any(sign["label"] == "BOA_NOITE" for sign in data["signs"])
    assert len(data["signs"]) <= 10


def test_vlibras_reference_catalog_is_paginated():
    response = client.get("/v1/vlibras-reference/catalog?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 13597
    assert len(data["signs"]) == 2


def test_vlibras_reference_motion_contains_full_hands_and_body():
    response = client.get("/v1/vlibras-reference/motions/BOM")
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "BOM"
    assert data["fps"] == 15
    assert len(data["frames"]) > 20
    assert len(data["frames"][0]["left_hand"]) == 21
    assert len(data["frames"][0]["right_hand"]) == 21
    assert "BnCabeca" in data["frames"][0]["body"]


def test_vlibras_reference_motion_rejects_path_traversal():
    response = client.get("/v1/vlibras-reference/motions/..%2FLICENSE")
    assert response.status_code in (400, 404)


def test_vlibras_reference_composes_hearing_message():
    response = client.post(
        "/v1/vlibras-reference/compose",
        json={"text": "Boa tarde!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert [sign["label"] for sign in data["signs"]] == ["BOM", "TARDE"]
    assert all(sign["motion_ready"] for sign in data["signs"])
    assert data["unresolved"] == []


def test_vlibras_reference_composition_reports_unknown_words():
    response = client.post(
        "/v1/vlibras-reference/compose",
        json={"text": "palavraqueinexiste bom"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["unresolved"] == ["PALAVRAQUEINEXISTE"]
    assert [sign["label"] for sign in data["signs"]] == ["BOM"]


def test_auth_register_and_login():
    # Registrar novo usuário
    reg_response = client.post(
        "/v1/auth/register",
        json={"email": "teste@sinaliza.ai", "password": "senhasegura123"}
    )
    assert reg_response.status_code == 201
    assert reg_response.json()["email"] == "teste@sinaliza.ai"
    
    # Logar com o usuário criado
    login_response = client.post(
        "/v1/auth/login",
        json={"email": "teste@sinaliza.ai", "password": "senhasegura123"}
    )
    assert login_response.status_code == 200
    data = login_response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    
    # Testar me endpoint com token
    token = data["access_token"]
    me_response = client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "teste@sinaliza.ai"

def test_model_manifest():
    response = client.get("/v1/models/manifest")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Sinaliza AI Transformer Lite"
    assert data["is_active"] is True

def test_privacy_consents_flow():
    # Registrar & Logar
    client.post(
        "/v1/auth/register",
        json={"email": "privacy@sinaliza.ai", "password": "senhasegura123"}
    )
    login_data = client.post(
        "/v1/auth/login",
        json={"email": "privacy@sinaliza.ai", "password": "senhasegura123"}
    ).json()
    token = login_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Enviar consentimento de uso de câmera
    consent_resp = client.post(
        "/v1/privacy/consents",
        json={"consent_type": "camera_usage", "version": "1.0", "accepted": True},
        headers=headers
    )
    assert consent_resp.status_code == 200
    assert consent_resp.json()["accepted"] is True
    
    # Excluir dados via solicitação de exclusão
    del_resp = client.post("/v1/privacy/deletion-requests", headers=headers)
    assert del_resp.status_code == 200
    assert "processada" in del_resp.json()["message"]


def test_create_training_sample():
    landmarks = valid_training_landmarks()

    # 1. Recusar envio sem sessão autenticada
    response = client.post(
        "/v1/training/samples",
        json={"sign_name": "obrigado", "landmarks": landmarks},
    )
    assert response.status_code == 401
    
    # 2. Recusar código de professor incorreto
    response = client.post(
        "/v1/training/auth",
        json={"trainer_name": "Teste", "access_code": "codigo-incorreto"},
    )
    assert response.status_code == 401
    
    # 3. Enviar com sessão correta
    headers = trainer_headers()
    response = client.post(
        "/v1/training/samples",
        json={"sign_name": "obrigado", "landmarks": landmarks},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["sign_name"] == "OBRIGADO"
    assert len(data["landmarks"]) == 210
    assert "id" in data

    # 4. Consultar contagem de amostras
    count_resp = client.get(
        "/v1/training/samples/count?sign_name=obrigado",
        headers=headers,
    )
    assert count_resp.status_code == 200
    assert count_resp.json()["sign_name"] == "OBRIGADO"
    assert count_resp.json()["count"] == 1

    with TestingSessionLocal() as db:
        audit = db.query(models.AuditLog).filter(
            models.AuditLog.action == "TRAINING_SAMPLE_CREATE"
        ).one()
        assert audit.user_id == "Professora Teste"


def test_professor_lists_and_soft_deletes_only_own_session():
    professor_a = trainer_headers("Professora Ana")
    professor_b = trainer_headers("Professor Bruno")
    landmarks = valid_training_landmarks()

    created_a = client.post(
        "/v1/training/samples",
        json={"sign_name": "DIA", "landmarks": landmarks},
        headers=professor_a,
    )
    created_b = client.post(
        "/v1/training/samples",
        json={"sign_name": "DIA", "landmarks": landmarks},
        headers=professor_b,
    )
    assert created_a.status_code == 201
    assert created_b.status_code == 201
    sample_a_id = created_a.json()["id"]

    mine_a = client.get(
        "/v1/training/my-samples",
        headers=professor_a,
    )
    assert mine_a.status_code == 200
    assert [sample["id"] for sample in mine_a.json()] == [sample_a_id]
    assert mine_a.json()[0]["frame_count"] == 10
    assert "landmarks" not in mine_a.json()[0]

    forbidden = client.delete(
        f"/v1/training/my-samples/{sample_a_id}",
        headers=professor_b,
    )
    assert forbidden.status_code == 403

    deleted = client.delete(
        f"/v1/training/my-samples/{sample_a_id}",
        headers=professor_a,
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    count = client.get(
        "/v1/training/samples/count",
        params={"sign_name": "DIA"},
        headers=professor_a,
    )
    assert count.status_code == 200
    assert count.json()["count"] == 1

    mine_after_delete = client.get(
        "/v1/training/my-samples",
        headers=professor_a,
    )
    assert mine_after_delete.json() == []

    with TestingSessionLocal() as db:
        stored = db.query(models.TrainingSample).filter(
            models.TrainingSample.id == sample_a_id
        ).one()
        assert stored.deleted_at is not None
        assert stored.deleted_by == "Professora Ana"
        audit = db.query(models.AuditLog).filter(
            models.AuditLog.action == "TRAINING_SAMPLE_SOFT_DELETE"
        ).one()
        assert audit.user_id == "Professora Ana"


def test_professor_archives_all_own_sessions_for_sign_without_touching_others():
    professor_a = trainer_headers("Professora Arquivadora")
    professor_b = trainer_headers("Professor Preservado")
    landmarks = valid_training_landmarks()

    for _ in range(2):
        created = client.post(
            "/v1/training/samples",
            json={"sign_name": "OLÁ", "landmarks": landmarks},
            headers=professor_a,
        )
        assert created.status_code == 201
    preserved = client.post(
        "/v1/training/samples",
        json={"sign_name": "OLÁ", "landmarks": landmarks},
        headers=professor_b,
    )
    assert preserved.status_code == 201

    archived = client.delete(
        "/v1/training/my-signs",
        params={"sign_name": "olá"},
        headers=professor_a,
    )
    assert archived.status_code == 200
    assert archived.json() == {"sign_name": "OLÁ", "archived_count": 2}

    mine_a = client.get("/v1/training/my-samples", headers=professor_a)
    mine_b = client.get("/v1/training/my-samples", headers=professor_b)
    assert mine_a.json() == []
    assert len(mine_b.json()) == 1
    assert mine_b.json()[0]["id"] == preserved.json()["id"]

    with TestingSessionLocal() as db:
        archived_rows = db.query(models.TrainingSample).filter(
            models.TrainingSample.trainer_name == "Professora Arquivadora"
        ).all()
        assert len(archived_rows) == 2
        assert all(row.deleted_at is not None for row in archived_rows)
        assert all(
            row.deleted_by == "Professora Arquivadora"
            for row in archived_rows
        )
        preserved_row = db.query(models.TrainingSample).filter_by(
            id=preserved.json()["id"]
        ).one()
        assert preserved_row.deleted_at is None


def test_professor_cannot_archive_sign_owned_only_by_another_professor():
    owner = trainer_headers("Professora Dona")
    outsider = trainer_headers("Professor Sem Permissão")
    created = client.post(
        "/v1/training/samples",
        json={"sign_name": "AJUDA", "landmarks": valid_training_landmarks()},
        headers=owner,
    )
    assert created.status_code == 201

    response = client.delete(
        "/v1/training/my-signs",
        params={"sign_name": "AJUDA"},
        headers=outsider,
    )
    assert response.status_code == 404

    with TestingSessionLocal() as db:
        stored = db.query(models.TrainingSample).filter_by(
            id=created.json()["id"]
        ).one()
        assert stored.deleted_at is None


def test_administrator_can_list_and_soft_delete_legacy_sample():
    with TestingSessionLocal() as db:
        legacy = models.TrainingSample(
            sign_name="ANTIGO",
            landmarks=valid_training_landmarks(),
            frame_count=10,
            trainer_name=None,
        )
        db.add(legacy)
        db.commit()
        legacy_id = legacy.id

    admin_headers = {
        "X-Trainer-Delete-Secret": "segredo-admin-exclusao",
    }
    listed = client.get("/v1/training/legacy-samples", headers=admin_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [legacy_id]

    deleted = client.delete(
        f"/v1/training/legacy-samples/{legacy_id}",
        headers=admin_headers,
    )
    assert deleted.status_code == 200

    with TestingSessionLocal() as db:
        stored = db.query(models.TrainingSample).filter_by(id=legacy_id).one()
        assert stored.deleted_at is not None
        assert stored.deleted_by == "administrator"


def test_administrator_can_delete_sample_from_old_automatic_professor():
    with TestingSessionLocal() as db:
        old_sample = models.TrainingSample(
            sign_name="PRESO",
            landmarks=valid_training_landmarks(),
            frame_count=10,
            trainer_name="Prof1",
        )
        db.add(old_sample)
        db.commit()
        sample_id = old_sample.id

    admin_headers = {
        "X-Trainer-Delete-Secret": "segredo-admin-exclusao",
    }
    listed = client.get("/v1/training/legacy-samples", headers=admin_headers)
    assert listed.status_code == 200
    item = next(item for item in listed.json() if item["id"] == sample_id)
    assert item["trainer_name"] == "Prof1"

    deleted = client.delete(
        f"/v1/training/legacy-samples/{sample_id}",
        headers=admin_headers,
    )
    assert deleted.status_code == 200


def test_legacy_management_never_lists_or_deletes_current_professor_samples():
    with TestingSessionLocal() as db:
        current = models.TrainingSample(
            sign_name="OBRIGADO",
            landmarks=valid_training_landmarks(),
            frame_count=10,
            trainer_name="Rozana",
        )
        db.add(current)
        db.commit()
        current_id = current.id

    admin_headers = {
        "X-Trainer-Delete-Secret": "segredo-admin-exclusao",
    }
    listed = client.get("/v1/training/legacy-samples", headers=admin_headers)
    assert listed.status_code == 200
    assert current_id not in {item["id"] for item in listed.json()}

    deletion = client.delete(
        f"/v1/training/legacy-samples/{current_id}",
        headers=admin_headers,
    )
    assert deletion.status_code == 404

    with TestingSessionLocal() as db:
        stored = db.query(models.TrainingSample).filter_by(id=current_id).one()
        assert stored.deleted_at is None


def test_legacy_bulk_delete_soft_deletes_instead_of_erasing_samples():
    with TestingSessionLocal() as db:
        sample = models.TrainingSample(
            sign_name="ARQUIVAVEL",
            landmarks=valid_training_landmarks(),
            frame_count=10,
            trainer_name="Prof1",
        )
        db.add(sample)
        db.commit()
        sample_id = sample.id

    response = client.delete(
        "/v1/training/samples/ARQUIVAVEL",
        headers={"X-Trainer-Delete-Secret": "segredo-admin-exclusao"},
    )
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 1

    with TestingSessionLocal() as db:
        stored = db.query(models.TrainingSample).filter_by(id=sample_id).one()
        assert stored.deleted_at is not None
        assert stored.deleted_by == "administrator"


def test_training_rejects_incomplete_or_invalid_landmarks():
    headers = trainer_headers()
    incomplete = [{"x": 0.1, "y": 0.2, "z": 0.3}] * 21
    response = client.post(
        "/v1/training/samples",
        json={"sign_name": "TESTE", "landmarks": incomplete},
        headers=headers,
    )
    assert response.status_code == 422


def test_five_professors_can_submit_without_losing_samples():
    landmarks = valid_training_landmarks()

    def submit(index):
        headers = trainer_headers(f"Professor {index}")
        return client.post(
            "/v1/training/samples",
            json={"sign_name": "CONCORRENCIA", "landmarks": landmarks},
            headers=headers,
        ).status_code

    with ThreadPoolExecutor(max_workers=5) as executor:
        statuses = list(executor.map(submit, range(1, 6)))

    assert statuses == [201, 201, 201, 201, 201]
    headers = trainer_headers()
    count_resp = client.get(
        "/v1/training/samples/count?sign_name=CONCORRENCIA",
        headers=headers,
    )
    assert count_resp.status_code == 200
    assert count_resp.json()["count"] == 5

    with TestingSessionLocal() as db:
        audit_count = db.query(models.AuditLog).filter(
            models.AuditLog.action == "TRAINING_SAMPLE_CREATE",
            models.AuditLog.target.contains(":CONCORRENCIA:"),
        ).count()
        assert audit_count == 5

    invalid = valid_training_landmarks()
    invalid[0]["x"] = 99
    response = client.post(
        "/v1/training/samples",
        json={"sign_name": "TESTE", "landmarks": invalid},
        headers=headers,
    )
    assert response.status_code == 422

    repeated_hand = valid_training_landmarks()[:21] * 10
    response = client.post(
        "/v1/training/samples",
        json={"sign_name": "TESTE", "landmarks": repeated_hand},
        headers=headers,
    )
    assert response.status_code == 422


def test_delete_training_samples_with_url_punctuation():
    headers = trainer_headers()
    sign_name = "OI, TUDO BEM? BOA TARDE"

    create_resp = client.post(
        "/v1/training/samples",
        json={"sign_name": sign_name, "landmarks": valid_training_landmarks()},
        headers=headers,
    )
    assert create_resp.status_code == 201

    delete_resp = client.delete(
        "/v1/training/samples",
        params={"sign_name": sign_name},
        headers={"X-Trainer-Delete-Secret": "segredo-admin-exclusao"},
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"sign_name": sign_name, "deleted_count": 1}

    missing_resp = client.delete(
        "/v1/training/samples",
        params={"sign_name": sign_name},
        headers={"X-Trainer-Delete-Secret": "segredo-admin-exclusao"},
    )
    assert missing_resp.status_code == 404


def test_predict_sign():
    # 1. Enviar sem dados
    resp = client.post("/v1/translation/predict", json={})
    assert resp.status_code == 200
    assert resp.json()["label"] == "SINAL_DESCONHECIDO"


def test_temporal_prediction_distinguishes_static_d_from_moving_dia():
    headers = trainer_headers()
    static_frames = temporal_landmark_frames()
    moving_frames = temporal_landmark_frames(movement_per_frame=0.006)

    for label, frames in (("D", static_frames), ("DIA", moving_frames)):
        response = client.post(
            "/v1/training/samples",
            json={
                "sign_name": label,
                "landmarks": [point for frame in frames for point in frame],
            },
            headers=headers,
        )
        assert response.status_code == 201

    static_prediction = client.post(
        "/v1/translation/predict-sequence",
        json={"frames": static_frames},
    )
    moving_prediction = client.post(
        "/v1/translation/predict-sequence",
        json={"frames": moving_frames},
    )

    assert static_prediction.status_code == 200
    assert static_prediction.json()["label"] == "D"
    assert static_prediction.json()["model"] == "hand_sequence_v1"
    assert static_prediction.json()["confidence"] >= 0.70
    assert moving_prediction.status_code == 200
    assert moving_prediction.json()["label"] == "DIA"
    assert moving_prediction.json()["model"] == "hand_sequence_v1"
    assert moving_prediction.json()["confidence"] >= 0.70


def test_temporal_prediction_requires_a_real_sequence():
    response = client.post(
        "/v1/translation/predict-sequence",
        json={"frames": temporal_landmark_frames(frame_count=5)},
    )
    assert response.status_code == 200
    assert response.json()["label"] == "DADOS_INSUFICIENTES"

    # 2. Enviar landmarks válidos (com banco de dados vazio)
    resp = client.post(
        "/v1/translation/predict",
        json={"landmarks": [{"x": 0.1, "y": 0.2, "z": 0.3}] * 21}
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "SINAL_DESCONHECIDO"


def test_two_hand_v2_preserves_hands_and_distinguishes_motion():
    headers = trainer_headers()
    together = structured_hand_frames(
        left_movement=0.003,
        right_movement=0.003,
        frame_count=32,
    )
    right_only = structured_hand_frames(
        left_movement=0,
        right_movement=0.008,
        frame_count=32,
    )

    for label, frames in (("JUNTOS", together), ("DIREITA", right_only)):
        for _ in range(5):
            created = client.post(
                "/v1/training/samples-v2",
                json={
                    "sign_name": label,
                    "format_version": 2,
                    "frames": frames,
                },
                headers=headers,
            )
            assert created.status_code == 201, created.text
            assert created.json()["frame_count"] == 32

    prediction = client.post(
        "/v1/translation/predict-sequence-v2",
        json={"format_version": 2, "frames": right_only},
    )
    assert prediction.status_code == 200
    assert prediction.json()["label"] == "DIREITA"
    assert prediction.json()["model"] == "two_hand_sequence_v2"
    assert prediction.json()["confidence"] >= 0.72
    assert prediction.json()["support"] == 3


def test_two_hand_v2_rejects_short_or_unordered_sequence():
    headers = trainer_headers()
    short = structured_hand_frames(frame_count=5)
    rejected = client.post(
        "/v1/training/samples-v2",
        json={"sign_name": "CURTO", "format_version": 2, "frames": short},
        headers=headers,
    )
    assert rejected.status_code == 422


def test_two_hand_v2_abstains_when_labels_are_too_similar():
    headers = trainer_headers()
    first = structured_hand_frames(right_movement=0.006, frame_count=32)
    second = structured_hand_frames(right_movement=0.008, frame_count=32)
    halfway = structured_hand_frames(right_movement=0.007, frame_count=32)

    for label, frames in (("OLA", first), ("BEM", second)):
        for _ in range(5):
            created = client.post(
                "/v1/training/samples-v2",
                json={
                    "sign_name": label,
                    "format_version": 2,
                    "frames": frames,
                },
                headers=headers,
            )
            assert created.status_code == 201

    prediction = client.post(
        "/v1/translation/predict-sequence-v2",
        json={"format_version": 2, "frames": halfway},
    )

    assert prediction.status_code == 200
    assert prediction.json()["label"] == "SINAL_AMBIGUO"
    assert prediction.json()["confidence"] == 0


def test_two_hand_v2_ignores_an_isolated_accidental_match():
    headers = trainer_headers()
    expected = structured_hand_frames(right_movement=0.006, frame_count=32)
    accidental = structured_hand_frames(right_movement=0.0061, frame_count=32)

    for _ in range(5):
        created = client.post(
            "/v1/training/samples-v2",
            json={
                "sign_name": "OLA",
                "format_version": 2,
                "frames": expected,
            },
            headers=headers,
        )
        assert created.status_code == 201
    created = client.post(
        "/v1/training/samples-v2",
        json={
            "sign_name": "BEM",
            "format_version": 2,
            "frames": accidental,
        },
        headers=headers,
    )
    assert created.status_code == 201

    prediction = client.post(
        "/v1/translation/predict-sequence-v2",
        json={"format_version": 2, "frames": expected},
    )

    assert prediction.status_code == 200
    assert prediction.json()["label"] == "OLA"


def test_two_hand_v2_ignores_old_compound_training_labels():
    headers = trainer_headers()
    frames = structured_hand_frames(right_movement=0.006, frame_count=32)
    for _ in range(5):
        created = client.post(
            "/v1/training/samples-v2",
            json={
                "sign_name": "TUDO BEM",
                "format_version": 2,
                "frames": frames,
            },
            headers=headers,
        )
        assert created.status_code == 201

    prediction = client.post(
        "/v1/translation/predict-sequence-v2",
        json={"format_version": 2, "frames": frames},
    )

    assert prediction.status_code == 200
    assert prediction.json()["label"] == "SINAL_DESCONHECIDO"


def test_training_batch_requires_and_creates_exactly_five_repetitions():
    headers = trainer_headers("Professora Cinco")
    frames = structured_hand_frames(frame_count=16)

    incomplete = client.post(
        "/v1/training/batches-v2",
        json={
            "sign_name": "OBRIGADO",
            "format_version": 2,
            "repetitions": [{"frames": frames} for _ in range(4)],
        },
        headers=headers,
    )
    assert incomplete.status_code == 422

    complete = client.post(
        "/v1/training/batches-v2",
        json={
            "sign_name": "Obrigado",
            "format_version": 2,
            "repetitions": [{"frames": frames} for _ in range(5)],
        },
        headers=headers,
    )
    assert complete.status_code == 201, complete.text
    assert complete.json()["sign_name"] == "OBRIGADO"
    assert complete.json()["repetitions_created"] == 5

    more_training = client.post(
        "/v1/training/batches-v2",
        json={
            "sign_name": "Obrigado",
            "format_version": 2,
            "repetitions": [{"frames": frames} for _ in range(5)],
        },
        headers=headers,
    )
    assert more_training.status_code == 201, more_training.text

    with TestingSessionLocal() as db:
        stored = db.query(models.TrainingSample).filter(
            models.TrainingSample.sign_name == "OBRIGADO",
            models.TrainingSample.trainer_name == "Professora Cinco",
        ).all()
        assert len(stored) == 10


def test_quality_training_batch_accepts_only_isolated_checked_repetitions():
    headers = trainer_headers("Professora Qualidade")
    repetitions = [
        {
            "frames": structured_hand_frames(
                right_movement=0.001 + repetition * 0.0001,
                frame_count=32,
            )
        }
        for repetition in range(5)
    ]

    compound = client.post(
        "/v1/training/batches-v3",
        json={
            "sign_name": "BOM DIA",
            "format_version": 3,
            "capture_context": {
                "platform": "android",
                "camera_facing": "front",
            },
            "repetitions": repetitions,
        },
        headers=headers,
    )
    assert compound.status_code == 422

    created = client.post(
        "/v1/training/batches-v3",
        json={
            "sign_name": "Obrigado",
            "format_version": 3,
            "capture_context": {
                "platform": "android",
                "camera_facing": "front",
                "app_version": "1.0.0",
            },
            "repetitions": repetitions,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["sign_name"] == "OBRIGADO"
    assert payload["format_version"] == 3
    assert payload["repetitions_created"] == 5
    assert payload["used_by_current_translator"] is True
    assert all(
        sample["quality"]["duration_ms"] == 1023
        for sample in payload["samples"]
    )

    with TestingSessionLocal() as db:
        stored = db.query(models.TrainingSample).filter(
            models.TrainingSample.sign_name == "OBRIGADO",
            models.TrainingSample.trainer_name == "Professora Qualidade",
        ).all()
        assert len(stored) == 5
        assert all(sample.landmarks["format_version"] == 3 for sample in stored)
    assert all(
        sample.landmarks["capture_context"]["platform"] == "android"
        for sample in stored
    )

    prediction = client.post(
        "/v1/translation/predict-sequence-v2",
        json={
            "format_version": 2,
            "frames": repetitions[0]["frames"],
        },
    )
    assert prediction.status_code == 200
    assert prediction.json()["label"] == "OBRIGADO"

    more_repetitions = [
        {
            "frames": structured_hand_frames(
                right_movement=0.002 + repetition * 0.0001,
                frame_count=32,
            )
        }
        for repetition in range(5)
    ]
    more_training = client.post(
        "/v1/training/batches-v3",
        json={
            "sign_name": "Obrigado",
            "format_version": 3,
            "capture_context": {
                "platform": "android",
                "camera_facing": "front",
            },
            "repetitions": more_repetitions,
        },
        headers=headers,
    )
    assert more_training.status_code == 201, more_training.text

    with TestingSessionLocal() as db:
        assert db.query(models.TrainingSample).filter(
            models.TrainingSample.sign_name == "OBRIGADO",
            models.TrainingSample.trainer_name == "Professora Qualidade",
        ).count() == 10


def test_training_draft_survives_interruption_and_completes_on_fifth_repetition():
    trainer_name = "Professora Rascunho"
    headers = trainer_headers(trainer_name)

    for repetition in range(3):
        response = client.post(
            "/v1/training/drafts/repetitions",
            json={
                "capture_id": f"draft_capture_{repetition:02d}_unique",
                "sign_name": "OLÁ",
                "format_version": 3,
                "capture_context": {
                    "platform": "ios",
                    "camera_facing": "front",
                },
                "frames": structured_hand_frames(
                    right_movement=0.001 + repetition * 0.0001,
                    frame_count=32,
                ),
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["repetitions_saved"] == repetition + 1
        assert response.json()["completed"] is False

    restored_headers = trainer_headers(trainer_name)
    restored = client.get(
        "/v1/training/drafts/current",
        headers=restored_headers,
    )
    assert restored.status_code == 200
    assert restored.json() == {
        "active": True,
        "sign_name": "OLÁ",
        "repetitions_saved": 3,
        "required_repetitions": 5,
    }

    with TestingSessionLocal() as db:
        assert db.query(models.TrainingSample).filter(
            models.TrainingSample.trainer_name == trainer_name,
        ).count() == 0
        draft = db.query(models.TrainingDraft).filter_by(
            trainer_name=trainer_name,
        ).one()
        assert len(draft.repetitions) == 3

    for repetition in range(3, 5):
        response = client.post(
            "/v1/training/drafts/repetitions",
            json={
                "capture_id": f"draft_capture_{repetition:02d}_unique",
                "sign_name": "OLÁ",
                "format_version": 3,
                "capture_context": {
                    "platform": "ios",
                    "camera_facing": "front",
                },
                "frames": structured_hand_frames(
                    right_movement=0.001 + repetition * 0.0001,
                    frame_count=32,
                ),
            },
            headers=restored_headers,
        )
        assert response.status_code == 201, response.text

    assert response.json() == {
        "sign_name": "OLÁ",
        "repetitions_saved": 5,
        "required_repetitions": 5,
        "completed": True,
        "duplicate": False,
    }
    current = client.get(
        "/v1/training/drafts/current",
        headers=restored_headers,
    )
    assert current.json()["active"] is False

    # Se o celular perdeu a resposta da API, a reabertura reenvia o mesmo
    # capture_id. O servidor deve confirmar o lote sem criar duplicatas.
    retry_after_completion = client.post(
        "/v1/training/drafts/repetitions",
        json={
            "capture_id": "draft_capture_00_unique",
            "sign_name": "OLÁ",
            "format_version": 3,
            "capture_context": {
                "platform": "ios",
                "camera_facing": "front",
            },
            "frames": structured_hand_frames(
                right_movement=0.001,
                frame_count=32,
            ),
        },
        headers=restored_headers,
    )
    assert retry_after_completion.status_code == 201
    assert retry_after_completion.json()["completed"] is True
    assert retry_after_completion.json()["duplicate"] is True

    with TestingSessionLocal() as db:
        assert db.query(models.TrainingDraft).filter_by(
            trainer_name=trainer_name,
        ).count() == 0
        assert db.query(models.TrainingSample).filter(
            models.TrainingSample.trainer_name == trainer_name,
            models.TrainingSample.sign_name == "OLÁ",
            models.TrainingSample.deleted_at.is_(None),
        ).count() == 5


def test_training_draft_capture_is_idempotent_and_locks_sign_name():
    headers = trainer_headers("Professor Idempotente")
    payload = {
        "capture_id": "idempotent_capture_0001",
        "sign_name": "AJUDA",
        "format_version": 3,
        "capture_context": {
            "platform": "web",
            "camera_facing": "front",
        },
        "frames": structured_hand_frames(
            right_movement=0.001,
            frame_count=32,
        ),
    }
    first = client.post(
        "/v1/training/drafts/repetitions",
        json=payload,
        headers=headers,
    )
    retry = client.post(
        "/v1/training/drafts/repetitions",
        json=payload,
        headers=headers,
    )
    assert first.status_code == 201
    assert retry.status_code == 201
    assert retry.json()["duplicate"] is True
    assert retry.json()["repetitions_saved"] == 1

    other_sign = dict(payload)
    other_sign["capture_id"] = "idempotent_capture_0002"
    other_sign["sign_name"] = "PROVA"
    blocked = client.post(
        "/v1/training/drafts/repetitions",
        json=other_sign,
        headers=headers,
    )
    assert blocked.status_code == 409

    with TestingSessionLocal() as db:
        draft = db.query(models.TrainingDraft).filter_by(
            trainer_name="Professor Idempotente",
        ).one()
        assert len(draft.repetitions) == 1


def test_quality_training_batch_rejects_replayed_capture_but_keeps_short_capture():
    headers = trainer_headers("Professor Auditoria")
    repeated_frames = structured_hand_frames(
        right_movement=0.002,
        frame_count=32,
    )
    request = {
        "sign_name": "AJUDA",
        "format_version": 3,
        "capture_context": {
            "platform": "web",
            "camera_facing": "front",
        },
        "repetitions": [{"frames": repeated_frames} for _ in range(5)],
    }
    replayed = client.post(
        "/v1/training/batches-v3",
        json=request,
        headers=headers,
    )
    assert replayed.status_code == 422
    assert "idêntica" in replayed.json()["detail"]

    request["repetitions"] = [
        {
            "frames": [
                {
                    **frame,
                    "timestamp_ms": 1_000 + index * 20,
                }
                for index, frame in enumerate(structured_hand_frames(
                    right_movement=0.002 + repetition * 0.0001,
                    frame_count=24,
                ))
            ]
        }
        for repetition in range(5)
    ]
    accepted_with_quality_metadata = client.post(
        "/v1/training/batches-v3",
        json=request,
        headers=headers,
    )
    assert accepted_with_quality_metadata.status_code == 201
    assert all(
        "short_duration" in sample["quality"]["warnings"]
        for sample in accepted_with_quality_metadata.json()["samples"]
    )


def test_training_draft_accepts_mobile_timing_and_duplicate_handedness_labels():
    headers = trainer_headers("Professora Celular")
    frames = structured_hand_frames(
        right_movement=0.002,
        frame_count=24,
    )
    for frame in frames:
        frame["hands"][1]["handedness"] = "Left"

    response = client.post(
        "/v1/training/drafts/repetitions",
        json={
            "capture_id": "mobile_capture_timing_0001",
            "sign_name": "OLA",
            "format_version": 3,
            "capture_context": {
                "platform": "web",
                "camera_facing": "front",
            },
            "frames": frames,
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["repetitions_saved"] == 1
    with TestingSessionLocal() as db:
        draft = db.query(models.TrainingDraft).filter_by(
            trainer_name="Professora Celular",
        ).one()
        quality = draft.repetitions[0]["quality"]
        assert quality["duration_ms"] == 759
        assert quality["warnings"] == ["short_duration"]


def test_two_hand_v2_finds_sign_inside_continuous_camera_buffer():
    headers = trainer_headers()
    trained = structured_hand_frames(
        left_movement=0,
        right_movement=0.006,
        frame_count=28,
    )
    for _ in range(5):
        created = client.post(
            "/v1/training/samples-v2",
            json={
                "sign_name": "MOVIMENTO",
                "format_version": 2,
                "frames": trained,
            },
            headers=headers,
        )
        assert created.status_code == 201

    neutral = structured_hand_frames(frame_count=20)
    live_sign = structured_hand_frames(
        left_movement=0,
        right_movement=0.006,
        frame_count=28,
    )
    for index, frame in enumerate(live_sign):
        frame["timestamp_ms"] = neutral[-1]["timestamp_ms"] + (index + 1) * 33
    continuous_buffer = neutral + live_sign

    prediction = client.post(
        "/v1/translation/predict-sequence-v2",
        json={"format_version": 2, "frames": continuous_buffer},
    )
    assert prediction.status_code == 200
    assert prediction.json()["label"] == "MOVIMENTO"
    assert prediction.json()["confidence"] >= 0.72

    unordered = structured_hand_frames()
    unordered[5]["timestamp_ms"] = unordered[4]["timestamp_ms"]
    rejected = client.post(
        "/v1/training/samples-v2",
        json={"sign_name": "FORA DE ORDEM", "format_version": 2, "frames": unordered},
        headers=headers,
    )
    assert rejected.status_code == 422



def test_export_training_model_for_local_inference():
    headers = trainer_headers()
    landmarks = valid_training_landmarks()

    create_resp = client.post(
        "/v1/training/samples",
        json={"sign_name": "TESTE_LOCAL", "landmarks": landmarks},
        headers=headers,
    )
    assert create_resp.status_code == 201

    model_resp = client.get("/v1/training/model/current")
    assert model_resp.status_code == 200
    payload = model_resp.json()
    assert payload["feature_schema"] == "hand_angles_v1"
    assert payload["threshold"] == 30.0
    assert len(payload["version"]) == 16
    assert any(
        feature["label"] == "TESTE_LOCAL" and len(feature["angles"]) == 8
        for feature in payload["features"]
    )

    delete_resp = client.delete(
        "/v1/training/samples",
        params={"sign_name": "TESTE_LOCAL"},
        headers={"X-Trainer-Delete-Secret": "segredo-admin-exclusao"},
    )
    assert delete_resp.status_code == 200


def test_boa_is_canonicalized_as_bom_visual_class():
    headers = trainer_headers()
    landmarks = valid_training_landmarks()

    create_resp = client.post(
        "/v1/training/samples",
        json={"sign_name": "boa", "landmarks": landmarks},
        headers=headers,
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["sign_name"] == "BOM"

    model_resp = client.get("/v1/training/model/current")
    assert model_resp.status_code == 200
    labels = [feature["label"] for feature in model_resp.json()["features"]]
    assert "BOM" in labels
    assert "BOA" not in labels

    delete_resp = client.delete(
        "/v1/training/samples",
        params={"sign_name": "BOM"},
        headers={"X-Trainer-Delete-Secret": "segredo-admin-exclusao"},
    )
    assert delete_resp.status_code == 200
