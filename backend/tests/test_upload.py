from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from app.db.session import get_engine
from app.main import app
from app.services import ocr_service


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(ocr_service, "extract_text", lambda path, threshold: ocr_service.OcrResult("", None, "[]", "OCR_UNAVAILABLE"))
    settings = get_settings()
    previous_dir = settings.upload_dir
    previous_limit = settings.max_upload_mb
    previous_database = settings.database_url
    with TemporaryDirectory(dir=".") as test_dir:
        settings.upload_dir = str(Path(test_dir) / "uploads")
        settings.database_url = f"sqlite:///{(Path(test_dir).resolve() / 'test.db').as_posix()}"
        settings.max_upload_mb = 1
        try:
            yield TestClient(app)
        finally:
            get_engine(settings.database_url).dispose()
            get_engine.cache_clear()
            settings.upload_dir = previous_dir
            settings.max_upload_mb = previous_limit
            settings.database_url = previous_database


def image_bytes(format: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 12), "blue").save(output, format=format)
    return output.getvalue()


@pytest.mark.parametrize(
    ("format", "mime"),
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
def test_valid_image_upload_and_retrieval(client, format, mime):
    data = image_bytes(format)
    response = client.post(
        "/api/v1/analyses",
        files={"file": ("../unsafe-name.png", data, mime)},
        data={"caption": "Example context"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["analysis_id"].startswith("an_")
    assert body["status"] == "awaiting_confirmation"
    assert body["caption"] == "Example context"
    assert "unsafe-name" not in body["image_url"]
    stored = client.get(body["image_url"])
    assert stored.status_code == 200
    assert stored.headers["content-type"] == mime
    assert stored.content == data


@pytest.mark.parametrize(
    ("name", "data", "mime", "expected"),
    [
        ("fake.png", b"plain text", "image/png", 422),
        ("empty.png", b"", "image/png", 400),
        ("wrong.png", image_bytes("JPEG"), "image/png", 415),
        ("text.txt", b"hello", "text/plain", 415),
    ],
)
def test_rejects_invalid_uploads(client, name, data, mime, expected):
    response = client.post("/api/v1/analyses", files={"file": (name, data, mime)})
    assert response.status_code == expected


def test_rejects_oversized_upload(client):
    data = b"x" * (1024 * 1024 + 1)
    response = client.post("/api/v1/analyses", files={"file": ("large.png", data, "image/png")})
    assert response.status_code == 413


def test_rejects_corrupt_image_and_unsafe_id(client):
    corrupt = image_bytes("PNG")[:30]
    response = client.post("/api/v1/analyses", files={"file": ("broken.png", corrupt, "image/png")})
    assert response.status_code == 422
    assert client.get("/api/v1/analyses/..%2Fsecret/image").status_code == 404
