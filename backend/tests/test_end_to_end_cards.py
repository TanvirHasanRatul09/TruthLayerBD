"""Exercise each browser card through the real API with deterministic provider fixtures."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine
from app.main import app
from app.schemas.providers import ClaimExtraction, ComparisonOutcome, EvidenceComparison, ExtractionOutcome
from app.services import comparison_service, gemini_service, ocr_service, tavily_service


CARDS = Path(__file__).resolve().parents[2] / "docs" / "manual-test-cases"
CLAIMS = {
    "01-sundarbans-1997-supported.png": "UNESCO listed the Sundarbans in Bangladesh as a World Heritage Site in 1997.",
    "02-sundarbans-1987-contradicted.png": "UNESCO listed the Sundarbans in Bangladesh as a World Heritage Site in 1987.",
    "03-apollo-1972-contradicted.png": "Apollo 11 first landed humans on the Moon in 1972.",
    "04-untraceable-claim.png": "A blue whale was seen in Dhaka city lake on 12 February 2032.",
    "05-eiffel-tower-berlin-contradicted.png": "The Eiffel Tower is in Berlin, Germany.",
}


@pytest.fixture
def card_client(monkeypatch):
    settings = get_settings()
    old_db, old_upload = settings.database_url, settings.upload_dir
    hashes = {sha256((CARDS / name).read_bytes()).hexdigest(): name for name in CLAIMS}

    def ocr(path, threshold):
        name = hashes[sha256(path.read_bytes()).hexdigest()]
        confidence = 0.3 if name.startswith("03") else 0.9
        return ocr_service.OcrResult("TEST CLAIM NOT A NEWS POST\n" + CLAIMS[name], confidence, "[]")

    def extract(text, caption, _settings, override=None):
        claim = override or next((value for value in CLAIMS.values() if value in text), text)
        return ExtractionOutcome(extraction=ClaimExtraction(claim=claim, search_queries_en=[claim], needs_user_confirmation=False), method="fixture")

    original_source_type = tavily_service._source_type

    def source_type(domain, claimed_source, claim=""):
        if domain == "source-a.example":
            return "independent_news", 3
        if domain == "source-b.example":
            return "fact_check", 2
        return original_source_type(domain, claimed_source, claim)

    def retrieve(extraction, analysis_id, _settings):
        claim = extraction.claim or ""
        if "blue whale" in claim:
            return tavily_service.RetrievalOutcome(status="no_results", query_count=1, successful_queries=1)
        if "1997" in claim:
            text = "UNESCO listed the Sundarbans in Bangladesh as a World Heritage Site in 1997."
        elif "1987" in claim:
            text = "UNESCO listed the Sundarbans in Bangladesh as a World Heritage Site in 1997, not 1987."
        elif "Eiffel Tower" in claim:
            text = "The Eiffel Tower is located in Paris, France, not Berlin, Germany."
        else:
            text = "Apollo 11 first landed humans on the Moon in 1969, not 1972."
        now = datetime.now(timezone.utc)
        items = [tavily_service.EvidenceItem(
            evidence_id=f"ev_fixture_{index}", url=f"https://{domain}/synthetic-card-{analysis_id}",
            canonical_url=f"https://{domain}/synthetic-card-{analysis_id}", title=text,
            domain=domain, source_type=source_type(domain, None, claim)[0], source_rank=index,
            snippet=text + " This synthetic source is for the local verification test only.",
            published_at=now, retrieved_at=now, query=claim,
        ) for index, domain in enumerate(("source-a.example", "source-b.example"))]
        if "1987" in claim:
            items.append(tavily_service.EvidenceItem(
                evidence_id="ev_india", url="https://india.example/synthetic", canonical_url="https://india.example/synthetic",
                title="Sundarbans National Park India UNESCO 1987", domain="india.example", source_type="other", source_rank=4,
                snippet="India's Sundarbans World Heritage Site was listed in 1987 by UNESCO.",
                published_at=now, retrieved_at=now, query=claim,
            ))
        if "Eiffel Tower" in claim:
            items.append(tavily_service.EvidenceItem(
                evidence_id="ev_replica", url="https://replica.example/berlin", canonical_url="https://replica.example/berlin",
                title="Berlin TV Tower and an Eiffel Tower replica", domain="replica.example", source_type="other", source_rank=4,
                snippet="A small replica of the Eiffel Tower stands in Berlin, Germany.",
                published_at=now, retrieved_at=now, query=claim,
            ))
        return tavily_service.RetrievalOutcome(items=items, status="completed", query_count=1, successful_queries=1)

    def compare(claim, items, _settings):
        stance = "supports" if "1997" in claim else "contradicts"
        rows = [EvidenceComparison(evidence_id=item.id, stance=stance, relevance=1, reason="Synthetic source states the comparison fact.", quote=item.title, method="gemini") for item in items]
        return ComparisonOutcome(comparisons=rows, method="gemini")

    monkeypatch.setattr(ocr_service, "extract_text", ocr)
    monkeypatch.setattr(gemini_service, "extract_claim", extract)
    monkeypatch.setattr(tavily_service, "retrieve", retrieve)
    monkeypatch.setattr(tavily_service, "_source_type", source_type)
    monkeypatch.setattr(comparison_service, "compare", compare)
    with TemporaryDirectory(dir=".") as folder:
        settings.database_url = f"sqlite:///{(Path(folder).resolve() / 'cards.db').as_posix()}"
        settings.upload_dir = str(Path(folder) / "uploads")
        try:
            yield TestClient(app)
        finally:
            get_engine(settings.database_url).dispose()
            get_engine.cache_clear()
            settings.database_url, settings.upload_dir = old_db, old_upload


@pytest.mark.parametrize("name,expected", [
    ("01-sundarbans-1997-supported.png", "supported"),
    ("02-sundarbans-1987-contradicted.png", "contradicted"),
    ("03-apollo-1972-contradicted.png", "contradicted"),
    ("04-untraceable-claim.png", "insufficient_evidence"),
    ("05-eiffel-tower-berlin-contradicted.png", "contradicted"),
])
def test_card_upload_to_saved_report(card_client, name, expected):
    response = card_client.post("/api/v1/analyses", files={"file": (name, (CARDS / name).read_bytes(), "image/png")})
    assert response.status_code == 201
    analysis_id = response.json()["analysis_id"]
    assert response.json()["ocr"]["needs_confirmation"]
    if name.startswith("03"):
        assert response.json()["ocr"]["confidence"] < 0.55
    assert card_client.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": CLAIMS[name]}).status_code == 200
    extraction = card_client.post(f"/api/v1/analyses/{analysis_id}/run", json={"claim": CLAIMS[name]})
    assert extraction.status_code == 200
    assert extraction.json()["extraction"]["claim"] == CLAIMS[name]
    assert card_client.post(f"/api/v1/analyses/{analysis_id}/retrieve").status_code == 200
    report_response = card_client.post(f"/api/v1/analyses/{analysis_id}/verify")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["verification"]["label"] == expected
    assert report["verification"]["layers"]["media"]["status"] == "inconclusive"
    assert report["verification"]["layers"]["source"]["status"] == "inconclusive"
    assert all(item["url"].startswith("https://") for item in report["evidence"])
    if name.startswith("02"):
        assert not any(item["evidence_id"] == "ev_india" for item in report["evidence"])
    if name.startswith("05"):
        assert not any(item["evidence_id"] == "ev_replica" for item in report["evidence"])
    if expected == "insufficient_evidence":
        assert report["verification"]["reasons"] == []
        assert report["verification"]["event_details"]["what"] is None
    else:
        assert report["verification"]["reasons"]
    if expected == "contradicted":
        assert report["verification"]["related_event"]["url"].startswith("https://")
        assert report["verification"]["event_details"]["what"] is None
    assert card_client.get(f"/api/v1/analyses/{analysis_id}").json()["verification"]["label"] == expected
    assert any(item["analysis_id"] == analysis_id for item in card_client.get("/api/v1/analyses").json()["items"])
    assert card_client.delete(f"/api/v1/analyses/{analysis_id}").status_code == 204
    assert card_client.get(f"/api/v1/analyses/{analysis_id}").status_code == 404


def test_card_with_two_credible_sides_stays_conflicting(card_client, monkeypatch):
    name = "05-eiffel-tower-berlin-contradicted.png"
    claim = CLAIMS[name]
    created = card_client.post("/api/v1/analyses", files={"file": (name, (CARDS / name).read_bytes(), "image/png")})
    analysis_id = created.json()["analysis_id"]
    assert card_client.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": claim}).status_code == 200
    assert card_client.post(f"/api/v1/analyses/{analysis_id}/run", json={"claim": claim}).status_code == 200

    def mixed_retrieve(_extraction, _analysis_id, _settings):
        now = datetime.now(timezone.utc)
        passages = (
            ("ev_for", "source-a.example", "The Eiffel Tower is in Berlin, Germany."),
            ("ev_against", "source-b.example", "The Eiffel Tower is in Paris, France, not Berlin, Germany."),
        )
        items = [tavily_service.EvidenceItem(
            evidence_id=evidence_id, url=f"https://{domain}/location", canonical_url=f"https://{domain}/location",
            title=passage, domain=domain, source_type="independent_news" if evidence_id == "ev_for" else "fact_check", source_rank=2,
            snippet=passage + " This detailed synthetic excerpt is only for testing conflicting citations and does not describe a real publication. " * 2,
            published_at=now, retrieved_at=now, query=claim,
        ) for evidence_id, domain, passage in passages]
        return tavily_service.RetrievalOutcome(items=items, status="completed", query_count=1, successful_queries=1)

    def mixed_compare(_claim, items, _settings):
        rows = [EvidenceComparison(evidence_id=item.id, stance="supports" if item.id == "ev_for" else "contradicts", relevance=1, reason="Synthetic passage states a location.", quote=item.title, method="gemini") for item in items]
        return ComparisonOutcome(comparisons=rows, method="gemini")

    monkeypatch.setattr(tavily_service, "retrieve", mixed_retrieve)
    monkeypatch.setattr(comparison_service, "compare", mixed_compare)
    assert card_client.post(f"/api/v1/analyses/{analysis_id}/retrieve").status_code == 200
    report = card_client.post(f"/api/v1/analyses/{analysis_id}/verify").json()
    assert report["verification"]["label"] == "conflicting"
    assert {reason["evidence_id"] for reason in report["verification"]["reasons"]} == {"ev_for", "ev_against"}


def test_refresh_can_read_saved_processing_state(card_client, monkeypatch):
    name = "01-sundarbans-1997-supported.png"
    response = card_client.post("/api/v1/analyses", files={"file": (name, (CARDS / name).read_bytes(), "image/png")})
    analysis_id = response.json()["analysis_id"]
    assert card_client.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": CLAIMS[name]}).status_code == 200
    entered, release = Event(), Event()

    def slow_extract(text, caption, settings, override=None):
        entered.set()
        assert release.wait(10)
        return ExtractionOutcome(extraction=ClaimExtraction(claim=override or CLAIMS[name], needs_user_confirmation=False), method="fixture")

    monkeypatch.setattr(gemini_service, "extract_claim", slow_extract)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(card_client.post, f"/api/v1/analyses/{analysis_id}/run", json={"claim": CLAIMS[name]})
        try:
            assert entered.wait(5)
            assert card_client.get(f"/api/v1/analyses/{analysis_id}").json()["status"] == "processing"
        finally:
            release.set()
        assert future.result(timeout=10).status_code == 200
    saved = card_client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert saved["status"] == "awaiting_confirmation"
    assert saved["extraction"]["claim"] == CLAIMS[name]
