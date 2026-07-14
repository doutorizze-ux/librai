import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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

def test_model_manifest_fields():
    # Cadastra e ativa modelo no banco
    db = TestingSessionLocal()
    model = models.Model(
        name="LSTMBaseline",
        version="1.0.0-lstm",
        hash_sha256="cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce",
        is_active=True
    )
    db.add(model)
    db.commit()
    
    response = client.get("/v1/models/manifest")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "LSTMBaseline"
    assert data["version"] == "1.0.0-lstm"
    assert data["hash_sha256"] == "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce"
