from fastapi.testclient import TestClient

from app.main import app, frontend_dist


def test_api_routes_remain_available_when_frontend_is_mounted():
    client = TestClient(app)
    assert client.get("/api/v1/health").json()["status"] == "ok"
    if frontend_dist.is_dir():
        assert client.get("/").status_code == 200
        assert "TruthLayer BD" in client.get("/").text
