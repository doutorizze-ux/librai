import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
from main import app
import models

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
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

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
