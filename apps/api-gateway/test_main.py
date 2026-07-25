import pytest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
from main import app
import models
from routers import training

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
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


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

    # 2. Enviar landmarks válidos (com banco de dados vazio)
    resp = client.post(
        "/v1/translation/predict",
        json={"landmarks": [{"x": 0.1, "y": 0.2, "z": 0.3}] * 21}
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "SINAL_DESCONHECIDO"



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
