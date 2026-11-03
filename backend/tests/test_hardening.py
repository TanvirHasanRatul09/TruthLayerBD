from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.core.rate_limit import reset_rate_limits
from app.db.session import get_engine
from app.main import app
from app.services import ocr_service, tavily_service


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (8, 8), "white").save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def isolated(monkeypatch):
    settings = get_settings()
    old = settings.database_url, settings.upload_dir, settings.rate_limit_upload_per_minute, settings.rate_limit_enabled, settings.tavily_api_key
    with TemporaryDirectory(dir=".") as folder:
        settings.database_url = f"sqlite:///{(Path(folder).resolve() / 'demo.db').as_posix()}"
        settings.upload_dir = str(Path(folder) / "uploads")
        settings.rate_limit_enabled = True
        settings.rate_limit_upload_per_minute = 60
        settings.tavily_api_key = ""
        reset_rate_limits()
        monkeypatch.setattr(ocr_service, "extract_text", lambda path, threshold: ocr_service.OcrResult("দাবি", 0.9, "[]"))
        try:
            yield TestClient(app, raise_server_exceptions=False)
        finally:
            get_engine(settings.database_url).dispose()
            get_engine.cache_clear()
            settings.database_url, settings.upload_dir, settings.rate_limit_upload_per_minute, settings.rate_limit_enabled, settings.tavily_api_key = old
            reset_rate_limits()


def test_structured_errors_headers_and_input_limits(isolated):
    missing = isolated.post("/api/v1/analyses")
    assert missing.status_code == 422
    assert missing.json() == {"code": "VALIDATION_ERROR", "detail": "Invalid request data."}
    assert missing.headers["cache-control"] == "no-store"
    assert missing.headers["x-content-type-options"] == "nosniff"
    assert isolated.get("/api/v1/analyses/missing").json()["code"] == "NOT_FOUND"
    long_caption = isolated.post("/api/v1/analyses", files={"file": ("post.png", image_bytes(), "image/png")}, data={"caption": "x" * 501})
    assert long_caption.status_code == 422
    created = isolated.post("/api/v1/analyses", files={"file": ("post.png", image_bytes(), "image/png")}).json()
    assert isolated.patch(f"/api/v1/analyses/{created['analysis_id']}/ocr", json={"text": "x" * 4001}).status_code == 422


def test_upload_limit_has_retry_after(isolated):
    get_settings().rate_limit_upload_per_minute = 2
    for _ in range(2):
        assert isolated.post("/api/v1/analyses", files={"file": ("post.png", image_bytes(), "image/png")}).status_code == 201
    blocked = isolated.post("/api/v1/analyses", files={"file": ("post.png", image_bytes(), "image/png")})
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMITED"
    assert int(blocked.headers["retry-after"]) > 0


def test_unexpected_provider_failure_does_not_leave_processing_or_leak_secret(isolated, monkeypatch):
    created = isolated.post("/api/v1/analyses", files={"file": ("post.png", image_bytes(), "image/png")}).json()
    analysis_id = created["analysis_id"]
    assert isolated.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": "সব বিশ্ববিদ্যালয় বন্ধ"}).status_code == 200
    assert isolated.post(f"/api/v1/analyses/{analysis_id}/run", json={"claim": "সব বিশ্ববিদ্যালয় বন্ধ"}).status_code == 200
    monkeypatch.setattr(tavily_service, "retrieve", lambda *args: (_ for _ in ()).throw(RuntimeError("secret-provider-key")))
    failed = isolated.post(f"/api/v1/analyses/{analysis_id}/retrieve")
    assert failed.status_code == 500
    assert failed.json()["code"] == "INTERNAL_ERROR"
    assert "secret-provider-key" not in failed.text
    detail = isolated.get(f"/api/v1/analyses/{analysis_id}").json()
    assert detail["status"] == "failed"
    assert detail["retrieval"] is None
    assert detail["verification"] is None


def test_schema_check_rejects_incompatible_existing_table():
    with TemporaryDirectory(dir=".") as folder:
        path = (Path(folder).resolve() / "old.db").as_posix()
        url = f"sqlite:///{path}"
        engine = create_engine(url)
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE analyses (id VARCHAR PRIMARY KEY)")
        engine.dispose()
        with pytest.raises(RuntimeError, match="missing columns"):
            get_engine(url)
