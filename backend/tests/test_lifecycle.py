from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.session import get_engine
from app.main import app
from app.models.analysis import Analysis, OcrRecord, ProviderEvent
from app.services import ocr_service


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(ocr_service, "extract_text", lambda path, threshold: ocr_service.OcrResult("", None, "[]", "OCR_UNAVAILABLE"))
    settings = get_settings()
    old_database, old_upload = settings.database_url, settings.upload_dir
    with TemporaryDirectory(dir=".") as test_dir:
        settings.database_url = f"sqlite:///{(Path(test_dir).resolve() / 'test.db').as_posix()}"
        settings.upload_dir = str(Path(test_dir) / "uploads")
        try:
            yield TestClient(app)
        finally:
            get_engine(settings.database_url).dispose()
            get_engine.cache_clear()
            settings.database_url, settings.upload_dir = old_database, old_upload


def upload(client, caption="example"):
    output = BytesIO()
    Image.new("RGB", (8, 8), "green").save(output, format="PNG")
    response = client.post("/api/v1/analyses", files={"file": ("post.png", output.getvalue(), "image/png")}, data={"caption": caption})
    assert response.status_code == 201
    return response.json()


def test_create_read_list_and_restart(client):
    first = upload(client, "first")
    second = upload(client, "second")
    detail = client.get(f"/api/v1/analyses/{first['analysis_id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "awaiting_confirmation"
    assert detail.json()["caption"] == "first"
    page = client.get("/api/v1/analyses?limit=1&offset=0").json()
    assert page["total"] == 2
    assert len(page["items"]) == 1
    assert client.get("/api/v1/analyses?limit=1&offset=1").json()["items"][0]["analysis_id"] != page["items"][0]["analysis_id"]
    assert client.get("/api/v1/analyses?limit=0").status_code == 422

    get_engine(get_settings().database_url).dispose()
    get_engine.cache_clear()
    assert client.get(f"/api/v1/analyses/{second['analysis_id']}").status_code == 200


@pytest.mark.parametrize("status", ["processing", "completed", "partial", "failed"])
def test_persisted_pipeline_state_is_separate_from_verification(client, status):
    created = upload(client)
    analysis_id = created["analysis_id"]
    with Session(get_engine(get_settings().database_url)) as session:
        analysis = session.get(Analysis, analysis_id)
        analysis.status = status
        session.add(analysis)
        session.commit()
    body = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert body["status"] == status
    assert body["verification"] is None


def test_delete_removes_image_and_related_rows(client):
    created = upload(client)
    analysis_id = created["analysis_id"]
    with Session(get_engine(get_settings().database_url)) as session:
        session.add(ProviderEvent(analysis_id=analysis_id, provider="gemini", operation="test", success=False, error_code="UNAVAILABLE"))
        session.commit()
        image_path = Path(session.get(Analysis, analysis_id).image_path)
    assert client.get(created["image_url"]).status_code == 200
    assert client.delete(f"/api/v1/analyses/{analysis_id}").status_code == 204
    assert not image_path.exists()
    assert client.get(f"/api/v1/analyses/{analysis_id}").status_code == 404
    assert client.get(created["image_url"]).status_code == 404
    assert client.delete(f"/api/v1/analyses/{analysis_id}").status_code == 404
    with Session(get_engine(get_settings().database_url)) as session:
        assert session.exec(select(ProviderEvent).where(ProviderEvent.analysis_id == analysis_id)).all() == []
        assert session.get(OcrRecord, analysis_id) is None
        assert session.get(Analysis, analysis_id) is None


def test_database_schema_has_no_secret_fields(client):
    upload(client)
    with Session(get_engine(get_settings().database_url)) as session:
        analysis = session.exec(select(Analysis)).first()
        assert analysis is not None
        assert "api_key" not in Analysis.model_fields
        assert "prompt" not in Analysis.model_fields
        assert "api_key" not in ProviderEvent.model_fields
        assert "prompt" not in ProviderEvent.model_fields
