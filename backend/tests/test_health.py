from fastapi.testclient import TestClient

from app.main import app


def test_health_exposes_configuration_state_without_secrets() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["database"]["configured"], bool)
    assert isinstance(body["providers"]["gemini"]["configured"], bool)
    assert isinstance(body["providers"]["tavily"]["configured"], bool)
    assert "api_key" not in response.text.lower()
    assert "secret" not in response.text.lower()


def test_cors_allows_only_configured_frontend() -> None:
    client = TestClient(app)
    allowed = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    denied = client.get("/api/v1/health", headers={"Origin": "https://untrusted.example"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers
