import json
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.main import app
from app.models.analysis import ExtractionRecord, ProviderEvent
from app.schemas.providers import ProviderAttempt
from app.services import gemini_service, ocr_service


def valid_extraction(**changes) -> str:
    data = {
        "claim": "সব বিশ্ববিদ্যালয় বন্ধ",
        "claimed_source": "Jamuna TV",
        "people": [],
        "organizations": ["Jamuna TV"],
        "places": [],
        "event_date_text": "আগামীকাল",
        "event_date": None,
        "keywords": ["বিশ্ববিদ্যালয়"],
        "search_queries_bn": ["সব বিশ্ববিদ্যালয় বন্ধ বাংলাদেশ"],
        "search_queries_en": [],
        "needs_user_confirmation": False,
        "ambiguities": [],
    }
    data.update(changes)
    return json.dumps(data, ensure_ascii=False)


def fake_post(sequence):
    calls = []

    def post(model, api_key, prompt, schema, timeout, operation):
        calls.append((model, operation))
        output, code = sequence.pop(0)
        return output, ProviderAttempt(operation=operation, success=output is not None, status_code=code, error_code=None if output is not None else "RATE_LIMITED" if code == 429 else "TIMEOUT")

    return post, calls


def settings_with_key() -> Settings:
    return Settings(gemini_api_key="test-secret-key", gemini_model="primary", gemini_fallback_model="fallback")


def test_valid_output_and_missing_fields_are_bounded():
    source = "Jamuna TV আগামীকাল সব বিশ্ববিদ্যালয় বন্ধ"
    result = gemini_service.validate_extraction(valid_extraction(), source, 5)
    assert result.claim == "সব বিশ্ববিদ্যালয় বন্ধ"
    assert result.claimed_source == "Jamuna TV"
    assert result.event_date is None
    missing = gemini_service.validate_extraction('{"claim":"সব বিশ্ববিদ্যালয় বন্ধ"}', source, 5)
    assert missing.claimed_source == "jamuna tv"
    assert missing.people == []
    assert missing.search_queries_bn == []


def test_invented_source_and_date_are_removed():
    source = "সব বিশ্ববিদ্যালয় বন্ধ"
    output = valid_extraction(claimed_source="Unknown TV", event_date_text="12 December 2030", event_date="2030-12-12")
    result = gemini_service.validate_extraction(output, source, 5)
    assert result.claimed_source is None
    assert result.event_date_text is None
    assert result.event_date is None
    assert result.needs_user_confirmation is True
    with pytest.raises(ValueError):
        gemini_service.validate_extraction(valid_extraction(claim="অন্য একটি অপ্রাসঙ্গিক খবর"), source, 5)


def test_manual_rerun_retains_visible_publisher_without_authenticating_it():
    result = gemini_service.manual_extraction("Jamuna TV: A bridge opened in Dhaka today", "A bridge opened in Dhaka today")
    assert result.claimed_source == "jamuna tv"
    assert gemini_service.manual_extraction("A bridge opened in Dhaka today", "A bridge opened in Dhaka today").claimed_source is None


def test_normalized_date_must_be_visible_in_input():
    source = "2026-11-02 সব বিশ্ববিদ্যালয় বন্ধ"
    output = valid_extraction(claimed_source=None, event_date_text="2026-11-02", event_date="2025-11-02")
    result = gemini_service.validate_extraction(output, source, 5)
    assert result.event_date is None
    assert result.needs_user_confirmation is True


def test_invalid_json_gets_one_repair_attempt(monkeypatch):
    post, calls = fake_post([('{"ok": true}', 200), ("{bad", 200), (valid_extraction(), 200)])
    monkeypatch.setattr(gemini_service, "_post", post)
    outcome = gemini_service.extract_claim("Jamuna TV আগামীকাল সব বিশ্ববিদ্যালয় বন্ধ", None, settings_with_key())
    assert outcome.method == "primary"
    assert outcome.extraction.claim == "সব বিশ্ববিদ্যালয় বন্ধ"
    assert calls == [("primary", "access_check"), ("primary", "extract_claim"), ("primary", "extract_claim_repair")]
    assert outcome.attempts[1].error_code == "INVALID_OUTPUT"


def test_primary_429_uses_fallback_model(monkeypatch):
    post, calls = fake_post([(None, 429), ('{"ok": true}', 200), (valid_extraction(), 200)])
    monkeypatch.setattr(gemini_service, "_post", post)
    outcome = gemini_service.extract_claim("Jamuna TV আগামীকাল সব বিশ্ববিদ্যালয় বন্ধ", None, settings_with_key())
    assert outcome.method == "fallback"
    assert calls[0] == ("primary", "access_check")
    assert calls[-1] == ("fallback", "extract_claim")


def test_transient_server_error_retries_once(monkeypatch):
    post, calls = fake_post([(None, 500), ('{"ok": true}', 200), (valid_extraction(), 200)])
    def with_server_code(*args):
        output, event = post(*args)
        if event.status_code == 500:
            event.error_code = "SERVER_ERROR"
        return output, event
    monkeypatch.setattr(gemini_service, "_post", with_server_code)
    monkeypatch.setattr(gemini_service.time, "sleep", lambda seconds: None)
    outcome = gemini_service.extract_claim("Jamuna TV আগামীকাল সব বিশ্ববিদ্যালয় বন্ধ", None, settings_with_key())
    assert outcome.method == "primary"
    assert calls[:2] == [("primary", "access_check"), ("primary", "access_check")]


def test_timeout_or_denial_preserves_manual_path(monkeypatch):
    post, calls = fake_post([(None, None), (None, 403)])
    monkeypatch.setattr(gemini_service, "_post", post)
    outcome = gemini_service.extract_claim("সব বিশ্ববিদ্যালয় বন্ধ", None, settings_with_key())
    assert outcome.method == "manual_fallback"
    assert outcome.extraction.claim == "সব বিশ্ববিদ্যালয় বন্ধ"
    assert outcome.extraction.needs_user_confirmation is True
    assert len(calls) == 2


def test_no_key_uses_manual_fallback_without_provider_calls(monkeypatch):
    monkeypatch.setattr(gemini_service, "_post", lambda *args: pytest.fail("provider must not be called"))
    outcome = gemini_service.extract_claim("সব বিশ্ববিদ্যালয় বন্ধ", None, Settings(gemini_api_key=""))
    assert outcome.method == "manual_fallback"
    assert outcome.attempts == []


@pytest.fixture
def client(monkeypatch):
    settings = get_settings()
    old = (settings.database_url, settings.upload_dir, settings.gemini_api_key, settings.gemini_enabled)
    with TemporaryDirectory(dir=".") as folder:
        settings.database_url = f"sqlite:///{(Path(folder).resolve() / 'test.db').as_posix()}"
        settings.upload_dir = str(Path(folder) / "uploads")
        settings.gemini_api_key = ""
        settings.gemini_enabled = True
        monkeypatch.setattr(ocr_service, "extract_text", lambda path, threshold: ocr_service.OcrResult("সব বিশ্ববিদ্যালয় বন্ধ", 0.9, "[]"))
        try:
            yield TestClient(app)
        finally:
            get_engine(settings.database_url).dispose()
            get_engine.cache_clear()
            settings.database_url, settings.upload_dir, settings.gemini_api_key, settings.gemini_enabled = old


def upload(client):
    output = BytesIO()
    Image.new("RGB", (8, 8), "white").save(output, format="PNG")
    response = client.post("/api/v1/analyses", files={"file": ("post.png", output.getvalue(), "image/png")})
    assert response.status_code == 201
    return response.json()["analysis_id"]


def test_run_requires_confirmed_ocr_and_manual_override_persists(client):
    analysis_id = upload(client)
    assert client.post(f"/api/v1/analyses/{analysis_id}/run", json={}).status_code == 409
    assert client.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": "সব বিশ্ববিদ্যালয় বন্ধ"}).status_code == 200
    first = client.post(f"/api/v1/analyses/{analysis_id}/run", json={})
    assert first.status_code == 200
    assert first.json()["extraction_method"] == "manual_fallback"
    assert first.json()["extraction"]["needs_user_confirmation"] is True
    assert first.json()["verification"] is None
    assert client.post(f"/api/v1/analyses/{analysis_id}/run", json={"claim": " "}).status_code == 422
    second = client.post(f"/api/v1/analyses/{analysis_id}/run", json={"claim": "দেশের সব বিশ্ববিদ্যালয় বন্ধ"})
    assert second.status_code == 200
    assert second.json()["extraction"]["claim"] == "দেশের সব বিশ্ববিদ্যালয় বন্ধ"
    assert second.json()["extraction"]["needs_user_confirmation"] is False
    with Session(get_engine(get_settings().database_url)) as session:
        assert session.get(ExtractionRecord, analysis_id) is not None
        assert session.exec(select(ProviderEvent)).all() == []
    get_engine(get_settings().database_url).dispose()
    get_engine.cache_clear()
    assert client.get(f"/api/v1/analyses/{analysis_id}").json()["extraction"]["claim"] == "দেশের সব বিশ্ববিদ্যালয় বন্ধ"
    assert client.delete(f"/api/v1/analyses/{analysis_id}").status_code == 204
    with Session(get_engine(get_settings().database_url)) as session:
        assert session.get(ExtractionRecord, analysis_id) is None


def test_provider_event_records_are_redacted(client, monkeypatch):
    analysis_id = upload(client)
    client.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": "Jamuna TV আগামীকাল সব বিশ্ববিদ্যালয় বন্ধ"})
    settings = get_settings()
    settings.gemini_api_key = "test-secret-key"
    post, _ = fake_post([(None, 429), (None, 403)])
    monkeypatch.setattr(gemini_service, "_post", post)
    response = client.post(f"/api/v1/analyses/{analysis_id}/run", json={})
    assert response.status_code == 200
    assert response.json()["extraction_method"] == "manual_fallback"
    with Session(get_engine(settings.database_url)) as session:
        events = session.exec(select(ProviderEvent)).all()
        assert len(events) == 2
        assert events[0].error_code == "RATE_LIMITED"
        assert "test-secret-key" not in " ".join(str(event.model_dump()) for event in events)
    assert "test-secret-key" not in Path(settings.database_url.removeprefix("sqlite:///")) .read_bytes().decode("latin1")
