from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from app.db.session import get_engine
from app.main import app
from app.services import ocr_service


def image_bytes():
    output = BytesIO()
    Image.new("RGB", (16, 16), "white").save(output, format="PNG")
    return output.getvalue()


def test_visitors_cannot_read_or_change_each_others_reports(monkeypatch):
    settings = get_settings()
    original = settings.database_url, settings.upload_dir, settings.gemini_api_key, settings.tavily_api_key
    with TemporaryDirectory(dir=".") as folder:
        settings.database_url = f"sqlite:///{(Path(folder).resolve() / 'test.db').as_posix()}"
        settings.upload_dir = str(Path(folder) / "uploads")
        settings.gemini_api_key = ""
        settings.tavily_api_key = ""
        monkeypatch.setattr(ocr_service, "extract_text", lambda path, threshold: ocr_service.OcrResult("", None, "[]"))
        try:
            with TestClient(app) as alice, TestClient(app) as bob:
                response = alice.post("/api/v1/analyses", files={"file": ("card.png", image_bytes(), "image/png")})
                assert response.status_code == 201
                analysis_id = response.json()["analysis_id"]
                assert alice.cookies.get("truthlayer_visitor")
                assert response.headers["set-cookie"].lower().find("httponly") >= 0
                assert alice.get("/api/v1/analyses").json()["total"] == 1
                assert bob.get("/api/v1/analyses").json()["total"] == 0
                assert alice.get(f"/api/v1/analyses/{analysis_id}").status_code == 200
                with TestClient(app) as reopened:
                    reopened.cookies.set("truthlayer_visitor", alice.cookies.get("truthlayer_visitor"))
                    assert reopened.get("/api/v1/analyses").json()["total"] == 1
                    assert reopened.get(f"/api/v1/analyses/{analysis_id}/image").status_code == 200
                paths = [
                    ("get", ""), ("get", "/image"),
                    ("patch", "/ocr"), ("post", "/ocr/vision-retry"),
                    ("post", "/run"), ("post", "/retrieve"),
                    ("post", "/match"), ("post", "/verify"),
                    ("delete", ""),
                ]
                for method, suffix in paths:
                    kwargs = {"json": {"text": "different claim"}} if suffix == "/ocr" else ({"json": {}} if suffix == "/run" else {})
                    assert getattr(bob, method)(f"/api/v1/analyses/{analysis_id}{suffix}", **kwargs).status_code == 404
                assert alice.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": "real claim"}).status_code == 200
                assert alice.get(f"/api/v1/analyses/{analysis_id}/image").status_code == 200
                assert alice.delete(f"/api/v1/analyses/{analysis_id}").status_code == 204
                assert alice.get("/api/v1/analyses").json()["total"] == 0
        finally:
            get_engine(settings.database_url).dispose()
            get_engine.cache_clear()
            settings.database_url, settings.upload_dir, settings.gemini_api_key, settings.tavily_api_key = original


def test_production_cookie_is_secure():
    settings = get_settings()
    original_env, original_secret = settings.app_env, settings.app_secret_key
    try:
        settings.app_env = "production"
        settings.app_secret_key = "a" * 40
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
            cookie = response.headers["set-cookie"].lower()
            assert "secure" in cookie
            assert "httponly" in cookie
            assert "samesite=lax" in cookie
    finally:
        settings.app_env, settings.app_secret_key = original_env, original_secret
