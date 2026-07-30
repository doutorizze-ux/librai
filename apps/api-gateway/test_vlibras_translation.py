import httpx
from fastapi.testclient import TestClient

from main import app
from routers import vlibras_reference


client = TestClient(app)


def test_uses_official_portuguese_translation(monkeypatch):
    monkeypatch.setattr(
        vlibras_reference,
        "_request_official_translation",
        lambda text: "OI MEU NOME M A U R I C I O",
    )

    response = client.post(
        "/v1/vlibras-reference/translate",
        json={"text": "Oi, meu nome é Mauricio."},
    )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "source": "VLibras Translator",
        "source_text": "Oi, meu nome é Mauricio.",
        "gloss": "OI MEU NOME M A U R I C I O",
    }


def test_reports_official_translation_failure(monkeypatch):
    def unavailable(_text):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(
        vlibras_reference,
        "_request_official_translation",
        unavailable,
    )

    response = client.post(
        "/v1/vlibras-reference/translate",
        json={"text": "Bom dia"},
    )

    assert response.status_code == 503
    assert "indisponível" in response.json()["detail"]
