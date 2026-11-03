import json
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import numpy as np
from fastapi.testclient import TestClient
from PIL import Image, ImageFilter
from sqlmodel import Session

from app.core.config import get_settings
from app.db.session import get_engine
from app.main import app
from app.models.analysis import Analysis, OcrRecord
from app.services import ocr_service


def box(x: int, y: int):
    return [[x, y], [x + 40, y], [x + 40, y + 12], [x, y + 12]]


def image_bytes(blurred: bool = False) -> bytes:
    image = Image.new("RGB", (120, 40), "white")
    if blurred:
        image = image.filter(ImageFilter.GaussianBlur(3))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def client(monkeypatch):
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


def test_mixed_bangla_english_reading_order_and_unicode():
    items = [
        (box(90, 30), "  Dhaka   2026  ", 0.8),
        (box(10, 10), "বাংলাদেশে", 0.9),
        (box(10, 30), "Jamuna TV", 0.7),
    ]
    result = ocr_service.parse_results(items)
    assert result.text == "বাংলাদেশে\nJamuna TV\nDhaka 2026"
    assert result.confidence == pytest.approx(0.8)
    raw = json.loads(result.raw_result_json)
    assert raw[0]["text"] == "বাংলাদেশে"
    assert raw[-1]["text"] == "  Dhaka   2026  "
    assert ocr_service.normalize_text("ড\u09bc   news") == ocr_service.normalize_text("ড় news")


def test_easyocr_numpy_values_are_json_serializable():
    result = ocr_service.parse_results([([[np.int32(1), np.int32(2)], [np.int32(3), np.int32(2)]], "ঢাকা", np.float64(0.8))])
    assert result.text == "ঢাকা"
    assert json.loads(result.raw_result_json)[0]["box"] == [[1.0, 2.0], [3.0, 2.0]]


def test_clear_image_uses_first_pass_without_retry(monkeypatch):
    class Reader:
        calls = 0
        def readtext(self, source, **kwargs):
            self.calls += 1
            return [(box(0, 0), "ঢাকা News", 0.91)]
    reader = Reader()
    monkeypatch.setattr(ocr_service, "get_reader", lambda: reader)
    with TemporaryDirectory(dir=".") as folder:
        path = Path(folder) / "clear.png"
        path.write_bytes(image_bytes())
        result = ocr_service.extract_text(path, 0.55)
    assert result.text == "ঢাকা News"
    assert reader.calls == 1


def test_blurred_image_gets_one_preprocessing_retry(monkeypatch):
    class Reader:
        calls = 0
        def readtext(self, source, **kwargs):
            self.calls += 1
            return [(box(0, 0), "ঢাকা", 0.2 if self.calls == 1 else 0.82)]
    reader = Reader()
    monkeypatch.setattr(ocr_service, "get_reader", lambda: reader)
    monkeypatch.setattr(ocr_service, "preprocess_image", lambda path: "preprocessed-image")
    with TemporaryDirectory(dir=".") as folder:
        path = Path(folder) / "blurred.png"
        path.write_bytes(image_bytes(blurred=True))
        result = ocr_service.extract_text(path, 0.55)
    assert result.text == "ঢাকা"
    assert result.confidence == pytest.approx(0.82)
    assert reader.calls == 2


def test_ocr_failure_keeps_manual_path(monkeypatch):
    def unavailable():
        raise RuntimeError("model unavailable")
    monkeypatch.setattr(ocr_service, "get_reader", unavailable)
    result = ocr_service.extract_text(Path("unused.png"), 0.55)
    assert result.text == ""
    assert result.error_code == "OCR_UNAVAILABLE"


def test_upload_ocr_and_correction_persist(client, monkeypatch):
    raw = json.dumps([{"box": box(0, 0), "text": "ভুল News", "confidence": 0.4}], ensure_ascii=False)
    monkeypatch.setattr(ocr_service, "extract_text", lambda path, threshold: ocr_service.OcrResult("ভুল News", 0.4, raw))
    created = client.post("/api/v1/analyses", files={"file": ("post.png", image_bytes(), "image/png")})
    assert created.status_code == 201
    analysis_id = created.json()["analysis_id"]
    assert created.json()["ocr"]["needs_confirmation"] is True
    assert created.json()["ocr"]["confidence"] == 0.4
    before = client.get(f"/api/v1/analyses/{analysis_id}").json()["ocr"]
    assert before["text"] == "ভুল News"
    corrected = client.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": "  সঠিক   News  "})
    assert corrected.status_code == 200
    assert corrected.json()["ocr"]["text"] == "সঠিক News"
    assert corrected.json()["ocr"]["needs_confirmation"] is False
    assert corrected.json()["status"] == "awaiting_confirmation"
    with Session(get_engine(get_settings().database_url)) as session:
        record = session.get(OcrRecord, analysis_id)
        assert record.confirmed_at is not None
        assert record.raw_result_json == raw
    get_engine(get_settings().database_url).dispose()
    get_engine.cache_clear()
    assert client.get(f"/api/v1/analyses/{analysis_id}").json()["ocr"]["text"] == "সঠিক News"


def test_blank_ocr_or_unknown_analysis_rejected(client, monkeypatch):
    monkeypatch.setattr(ocr_service, "extract_text", lambda path, threshold: ocr_service.OcrResult("", None, "[]", "OCR_UNAVAILABLE"))
    created = client.post("/api/v1/analyses", files={"file": ("post.png", image_bytes(), "image/png")}).json()
    analysis_id = created["analysis_id"]
    assert created["ocr"]["needs_confirmation"] is True
    assert client.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": "   "}).status_code == 422
    assert client.patch("/api/v1/analyses/missing/ocr", json={"text": "manual"}).status_code == 404
    manual = client.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": "নিজের লেখা"})
    assert manual.status_code == 200
    assert manual.json()["ocr"]["text"] == "নিজের লেখা"


def test_unowned_legacy_analysis_is_hidden_but_preserved(client):
    with Session(get_engine(get_settings().database_url)) as session:
        session.add(Analysis(id="an_" + "a" * 32, image_path="legacy.png", image_sha256="x" * 64))
        session.commit()
    response = client.patch("/api/v1/analyses/an_" + "a" * 32 + "/ocr", json={"text": "পুরোনো ছবি"})
    assert response.status_code == 404
    assert client.get("/api/v1/analyses/an_" + "a" * 32).status_code == 404
    assert client.get("/api/v1/analyses").json()["total"] == 0
    with Session(get_engine(get_settings().database_url)) as session:
        assert session.get(Analysis, "an_" + "a" * 32) is not None


def test_vision_retry_requires_confirmation_and_clears_old_claim(client, monkeypatch):
    from app.services import vision_ocr_service

    monkeypatch.setattr(ocr_service, "extract_text", lambda path, threshold: ocr_service.OcrResult("ভুল লেখা", 0.16, "[]"))
    created = client.post("/api/v1/analyses", files={"file": ("post.png", image_bytes(), "image/png")}).json()
    analysis_id = created["analysis_id"]
    client.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": "পুরোনো নিশ্চিত লেখা"})
    client.post(f"/api/v1/analyses/{analysis_id}/run", json={"claim": "পুরোনো দাবি"})
    settings = get_settings()
    old_key = settings.gemini_api_key
    settings.gemini_api_key = "test-key"
    monkeypatch.setattr(vision_ocr_service, "transcribe", lambda path, settings: ("ভিসা জটিলতা কাটিয়ে উজবেকিস্তানের পথে", []))
    try:
        retried = client.post(f"/api/v1/analyses/{analysis_id}/ocr/vision-retry")
        assert retried.status_code == 200
        body = retried.json()
        assert body["ocr"]["text"] == ocr_service.normalize_text("ভিসা জটিলতা কাটিয়ে উজবেকিস্তানের পথে")
        assert body["ocr"]["needs_confirmation"] is True
        assert body["ocr"]["confidence"] is None
        assert body["extraction"] is None
        assert client.post(f"/api/v1/analyses/{analysis_id}/run", json={}).status_code == 409
    finally:
        settings.gemini_api_key = old_key


def test_vision_request_sends_image_and_requires_structured_text(monkeypatch):
    import base64
    import httpx
    from app.core.config import Settings
    from app.services import vision_ocr_service

    captured = {}
    def handler(request):
        payload = json.loads(request.content)
        captured["mime"] = payload["contents"][0]["parts"][1]["inline_data"]["mime_type"]
        captured["data"] = payload["contents"][0]["parts"][1]["inline_data"]["data"]
        captured["key"] = request.headers.get("x-goog-api-key")
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps({"text": "দৃশ্যমান লেখা"})}]}}]})
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(vision_ocr_service.httpx, "Client", lambda **kwargs: real_client(transport=transport, **kwargs))
    with TemporaryDirectory(dir=".") as folder:
        path = Path(folder) / "image.png"
        path.write_bytes(image_bytes())
        text, attempts = vision_ocr_service.transcribe(path, Settings(gemini_api_key="test-key"))
    assert text == "দৃশ্যমান লেখা"
    assert attempts[0].success
    assert captured["mime"] == "image/png"
    assert base64.b64decode(captured["data"]) == image_bytes()
    assert captured["key"] == "test-key"
