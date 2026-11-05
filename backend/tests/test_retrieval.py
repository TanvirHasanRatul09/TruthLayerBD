from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

import pytest
import httpx
import json
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.main import app
from app.models.evidence import ComparisonRecord, Evidence, RetrievalRun, VerificationRecord
from app.models.analysis import ProviderEvent
from app.schemas.providers import ClaimExtraction, ExtractionOutcome, ProviderAttempt
from app.services import gemini_service, ocr_service, tavily_service


def extraction() -> ClaimExtraction:
    return ClaimExtraction(
        claim="সব বিশ্ববিদ্যালয় বন্ধ",
        claimed_source="Jamuna TV",
        search_queries_bn=["বাংলাদেশ সব বিশ্ববিদ্যালয় বন্ধ সরকারি ঘোষণা"],
        search_queries_en=["Bangladesh university closure"],
    )


def result(url: str, title: str, content: str, published_date=None) -> dict:
    return {"url": url, "title": title, "content": content + " সব বিশ্ববিদ্যালয় বন্ধ", "published_date": published_date}


def test_unrelated_country_and_sports_pages_are_excluded():
    claim = ClaimExtraction(claim="ভিসা জটিলতা কাটিয়ে উজবেকিস্তানের পথে টিটি তারকা হৃদয়")
    assert not tavily_service.is_relevant_result("Uzbekistan | Al Jazeera", "Ronaldo scores against Uzbekistan in the World Cup", claim)
    assert not tavily_service.is_relevant_result("উজবেকিস্তানের ভূগোল", "উজবেকিস্তান মধ্য এশিয়ার একটি দেশ", claim)
    assert tavily_service.is_relevant_result("ভিসা জটিলতা কাটিয়ে উজবেকিস্তানের পথে", "টিটি তারকা হৃদয় রওনা হয়েছেন", claim)
    assert not any("site:gov.bd" in query for query in tavily_service.generate_queries(claim, Settings()))


def test_sundarbans_other_country_result_is_not_relevant():
    claim = ClaimExtraction(claim="UNESCO listed the Sundarbans in Bangladesh as a World Heritage Site in 1987.")
    assert not tavily_service.is_relevant_result("Sundarbans National Park India UNESCO", "India's Sundarbans World Heritage Site was listed in 1987 by UNESCO.", claim)
    assert tavily_service.is_relevant_result("Sundarbans Bangladesh UNESCO", "UNESCO listed the Sundarbans in Bangladesh as a World Heritage Site in 1997, not 1987.", claim)


def test_similarly_named_structures_and_wrong_country_site_are_excluded():
    tower = ClaimExtraction(claim="The Eiffel Tower is in Berlin, Germany.")
    assert not tavily_service.is_relevant_result("Berlin TV Tower | Fun Facts", "The Berlin TV Tower was planned to surpass the Eiffel Tower in Paris.", tower)
    assert not tavily_service.is_relevant_result("Copies and replicas of the Eiffel Tower in Germany", "A small Eiffel Tower replica stands in Berlin.", tower)
    assert tavily_service.is_relevant_result("Access to the Eiffel Tower", "The Eiffel Tower is located in Paris, France, with an address at 5 avenue Anatole France.", tower, "https://toureiffel.paris/en/access-map")
    sundarbans = ClaimExtraction(claim="UNESCO listed the Sundarbans in Bangladesh in 1987.")
    assert not tavily_service.is_relevant_result("The Sundarbans", "India's 1987 Sundarbans site borders Bangladesh.", sundarbans, "https://whc.unesco.org/en/list/452/")
    assert tavily_service.is_relevant_result("The Sundarbans", "The Sundarbans in Bangladesh was listed by UNESCO in 1997.", sundarbans, "https://whc.unesco.org/en/list/798/")
    apollo = ClaimExtraction(claim="Apollo 11 first landed humans on the Moon in 1972.")
    assert not tavily_service.is_relevant_result("Apollo 17 in 1972", "The final Apollo Moon landing followed Apollo 11.", apollo)


def test_location_search_checks_subject_without_repeating_disputed_city():
    claim = ClaimExtraction(claim="The National Museum is in Berlin, Germany.")
    queries = tavily_service.generate_queries(claim, Settings(max_search_queries=5))
    assert any('National Museum' in query and 'Berlin' not in query for query in queries)


def test_person_specific_result_requires_same_named_person():
    claim = ClaimExtraction(claim="John Smith won the mayoral election in Dhaka in 2024.", people=["John Smith"])
    assert not tavily_service.is_relevant_result("John Doe wins mayoral election", "John Doe won the mayoral election in Dhaka in 2024.", claim)
    assert tavily_service.is_relevant_result("John Smith mayoral election", "John Smith won the mayoral election in Dhaka in 2023, not 2024.", claim)


def test_retrieval_discards_unrelated_country_results(monkeypatch):
    claim = ClaimExtraction(claim="ভিসা জটিলতা কাটিয়ে উজবেকিস্তানের পথে টিটি তারকা হৃদয়")
    search, _ = fake_search([([
        {"url": "https://example.org/uzbekistan", "title": "Uzbekistan news", "content": "Ronaldo scores against Uzbekistan in the World Cup"},
        {"url": "https://example.org/geography", "title": "উজবেকিস্তানের ভূগোল", "content": "উজবেকিস্তান মধ্য এশিয়ার দেশ"},
    ], None, 200)])
    monkeypatch.setattr(tavily_service, "_search", search)
    outcome = tavily_service.retrieve(claim, "an_test", Settings(tavily_api_key="test-key", max_search_queries=1))
    assert outcome.status == "no_results"
    assert outcome.items == []


def test_network_failure_is_distinct_and_stops_repeated_searches(monkeypatch):
    def disconnected(query, settings):
        return None, ProviderAttempt(provider="tavily", operation="search", success=False, error_code="NETWORK_ERROR")
    monkeypatch.setattr(tavily_service, "_search", disconnected)
    outcome = tavily_service.retrieve(extraction(), "an_test", Settings(tavily_api_key="test-key"))
    assert outcome.status == "unavailable"
    assert outcome.query_count == 1
    assert outcome.attempts[0].error_code == "NETWORK_ERROR"


def fake_search(responses):
    calls = []

    def search(query, settings):
        calls.append(query)
        items, error_code, status_code = responses.pop(0)
        return items, ProviderAttempt(provider="tavily", operation="search", success=items is not None, status_code=status_code, error_code=error_code)

    return search, calls


def test_query_generation_is_bounded_and_focused():
    settings = Settings(max_search_queries=5)
    queries = tavily_service.generate_queries(extraction(), settings)
    assert len(queries) == 5
    assert queries[0] == "সব বিশ্ববিদ্যালয় বন্ধ"
    assert any(query.startswith("site:ugc.gov.bd") for query in queries)
    assert any(query.startswith("site:jamuna.tv") for query in queries)
    assert any("Bangladesh university closure" in query for query in queries)


def test_official_authority_requires_topic_match():
    assert tavily_service._source_type("teachers.gov.bd", None, "১২ কেজি এলপিজি গ্যাসের নতুন দাম") == ("government_site", 4)
    assert tavily_service._source_type("ugc.gov.bd", None, "সব বিশ্ববিদ্যালয় বন্ধ") == ("official_authority", 0)


def test_eiffel_tower_search_includes_its_official_site():
    claim = ClaimExtraction(claim="The Eiffel Tower is in Berlin, Germany.")
    queries = tavily_service.generate_queries(claim, Settings())
    assert "site:toureiffel.paris Eiffel Tower location" in queries
    assert any(query.startswith("site:toureiffel.paris ") for query in queries)
    assert tavily_service._source_type("toureiffel.paris", None, claim.claim) == ("official_authority", 0)
    assert tavily_service._source_type("berlin-tickets.com", None, claim.claim) == ("other", 4)
    assert tavily_service._source_type("berc.org.bd", None, "এলপিজির নতুন দাম") == ("official_authority", 0)
    queries = tavily_service.generate_queries(ClaimExtraction(claim="এলপিজির নতুন দাম"), Settings())
    assert any(query.startswith("site:berc.org.bd") for query in queries)
    assert tavily_service._source_type("whc.unesco.org", None, "UNESCO listed the Sundarbans") == ("official_authority", 0)
    assert tavily_service._source_type("nasa.gov", None, "Apollo 11 landed on the Moon") == ("official_authority", 0)
    assert tavily_service._source_type("nasa.gov", None, "University closure in Bangladesh") != ("official_authority", 0)
    assert tavily_service._source_type("who.int", None, "WHO characterized COVID-19 as a pandemic") == ("official_authority", 0)
    assert tavily_service._source_type("un.org", None, "বাংলাদেশ জাতিসংঘের সদস্য হয়") == ("official_authority", 0)
    assert tavily_service._source_type("who.int", None, "UNESCO listed the Sundarbans") != ("official_authority", 0)


def test_tavily_request_disables_generated_answer_and_caps_results(monkeypatch):
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"results": []})

    actual_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(tavily_service.httpx, "Client", lambda timeout: actual_client(transport=transport, timeout=timeout))
    items, attempt = tavily_service._search("বাংলাদেশ বিশ্ববিদ্যালয়", Settings(tavily_api_key="test-key", tavily_max_results=99))
    assert items == [] and attempt.success is True
    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["body"]["include_answer"] is False
    assert captured["body"]["include_raw_content"] is False
    assert captured["body"]["include_published_date"] is True
    assert captured["body"]["max_results"] == 5


def test_tavily_http_429_and_timeout_are_safe_errors(monkeypatch):
    actual_client = httpx.Client
    limited = httpx.MockTransport(lambda request: httpx.Response(429, json={"detail": {"error": "secret provider body"}}))
    monkeypatch.setattr(tavily_service.httpx, "Client", lambda timeout: actual_client(transport=limited, timeout=timeout))
    items, attempt = tavily_service._search("claim", Settings(tavily_api_key="test-key"))
    assert items is None and attempt.error_code == "RATE_LIMITED"
    assert "secret provider body" not in str(attempt.model_dump())

    def timeout_handler(request):
        raise httpx.ReadTimeout("timeout")

    timed_out = httpx.MockTransport(timeout_handler)
    monkeypatch.setattr(tavily_service.httpx, "Client", lambda timeout: actual_client(transport=timed_out, timeout=timeout))
    items, attempt = tavily_service._search("claim", Settings(tavily_api_key="test-key"))
    assert items is None and attempt.error_code == "TIMEOUT"


def test_url_canonicalization_rejects_unsafe_schemes():
    assert tavily_service.canonicalize_url("https://www.jamuna.tv/news/1/?utm_source=x#top") == ("https://jamuna.tv/news/1", "jamuna.tv")
    assert tavily_service.canonicalize_url("javascript:alert(1)") is None
    assert tavily_service.canonicalize_url("http://127.0.0.1/private") is None


def test_dedup_ranking_and_missing_dates(monkeypatch):
    copied = "The same copied report appears at several websites with identical content."
    first = [
        result("https://unknown.example/copy", "Copied report", copied),
        result("https://ugc.gov.bd/notice/42?utm_source=social", "Official notice", "Official update about one institution", "Tue, 11 Mar 2025 17:00:00 GMT"),
        result("https://jamuna.tv/news/42", "Publisher report", "Publisher report about closure"),
    ]
    second = [
        result("https://www.ugc.gov.bd/notice/42#section", "Official notice", "Longer official update about one institution", None),
        result("https://rumorscanner.com/fact-check/42", "Fact check", "An independent fact check on the circulated card"),
        result("https://thedailystar.net/news/42", "News report", "Independent newsroom report on the event"),
        result("https://thedailystar.net/copy", "Copied report", copied),
    ]
    search, calls = fake_search([(first, None, 200), (second, None, 200)])
    monkeypatch.setattr(tavily_service, "_search", search)
    settings = Settings(tavily_api_key="test-key", max_search_queries=2)
    outcome = tavily_service.retrieve(extraction(), "an_test", settings)
    assert outcome.status == "completed"
    assert outcome.query_count == outcome.successful_queries == 2
    assert len(calls) == 2
    assert len(outcome.items) == 5
    assert outcome.items[0].source_type == "official_authority"
    assert outcome.items[0].published_at is not None
    assert outcome.items[0].snippet.startswith("Longer")
    assert any(item.source_type == "claimed_publisher" for item in outcome.items)
    assert any(item.source_type == "fact_check" for item in outcome.items)
    assert any(item.source_type == "independent_news" for item in outcome.items)
    assert not any(item.domain == "unknown.example" for item in outcome.items)
    assert all(item.evidence_id.startswith("ev_") and item.url for item in outcome.items)
    assert all(item.retrieved_at == outcome.retrieved_at for item in outcome.items)
    assert any(item.published_at is None for item in outcome.items)


def test_429_and_timeout_do_not_fabricate_evidence(monkeypatch):
    search, calls = fake_search([(None, "RATE_LIMITED", 429)])
    monkeypatch.setattr(tavily_service, "_search", search)
    outcome = tavily_service.retrieve(extraction(), "an_test", Settings(tavily_api_key="test-key"))
    assert outcome.status == "unavailable"
    assert outcome.items == []
    assert outcome.query_count == 1
    assert "failed" in outcome.limitation
    assert len(calls) == 1

    search, calls = fake_search([(None, "TIMEOUT", None)])
    monkeypatch.setattr(tavily_service, "_search", search)
    outcome = tavily_service.retrieve(extraction(), "an_test", Settings(tavily_api_key="test-key"))
    assert outcome.status == "unavailable"
    assert outcome.items == []
    assert len(calls) == 1


def test_partial_search_and_no_results(monkeypatch):
    search, _ = fake_search([([result("https://ugc.gov.bd/notice", "Notice", "Official information")], None, 200), (None, "RATE_LIMITED", 429)])
    monkeypatch.setattr(tavily_service, "_search", search)
    partial = tavily_service.retrieve(extraction(), "an_test", Settings(tavily_api_key="test-key"))
    assert partial.status == "partial"
    assert len(partial.items) == 1
    assert partial.successful_queries == 1
    search, _ = fake_search([([], None, 200)])
    monkeypatch.setattr(tavily_service, "_search", search)
    empty = tavily_service.retrieve(extraction(), "an_test", Settings(tavily_api_key="test-key", max_search_queries=1))
    assert empty.status == "no_results"
    assert "absence is not proof" in empty.limitation


def test_no_key_does_not_call_provider(monkeypatch):
    monkeypatch.setattr(tavily_service, "_search", lambda *args: pytest.fail("provider should not be called"))
    outcome = tavily_service.retrieve(extraction(), "an_test", Settings(tavily_api_key=""))
    assert outcome.status == "unavailable"
    assert outcome.query_count == 0
    assert outcome.items == []


@pytest.fixture
def client(monkeypatch):
    settings = get_settings()
    old = (settings.database_url, settings.upload_dir, settings.gemini_api_key, settings.tavily_api_key, settings.tavily_enabled, settings.max_search_queries)
    with TemporaryDirectory(dir=".") as folder:
        settings.database_url = f"sqlite:///{(Path(folder).resolve() / 'test.db').as_posix()}"
        settings.upload_dir = str(Path(folder) / "uploads")
        settings.gemini_api_key = ""
        settings.tavily_api_key = ""
        settings.tavily_enabled = True
        settings.max_search_queries = 1
        monkeypatch.setattr(ocr_service, "extract_text", lambda path, threshold: ocr_service.OcrResult("সব বিশ্ববিদ্যালয় বন্ধ", 0.9, "[]"))
        try:
            yield TestClient(app)
        finally:
            get_engine(settings.database_url).dispose()
            get_engine.cache_clear()
            settings.database_url, settings.upload_dir, settings.gemini_api_key, settings.tavily_api_key, settings.tavily_enabled, settings.max_search_queries = old


def ready_analysis(client):
    output = BytesIO()
    Image.new("RGB", (8, 8), "white").save(output, format="PNG")
    response = client.post("/api/v1/analyses", files={"file": ("post.png", output.getvalue(), "image/png")})
    analysis_id = response.json()["analysis_id"]
    client.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": "সব বিশ্ববিদ্যালয় বন্ধ"})
    client.post(f"/api/v1/analyses/{analysis_id}/run", json={"claim": "সব বিশ্ববিদ্যালয় বন্ধ"})
    return analysis_id


def test_api_requires_confirmed_claim_and_persists_evidence(client, monkeypatch):
    analysis_id = ready_analysis(client)
    settings = get_settings()
    settings.tavily_api_key = "test-secret-key"
    search, calls = fake_search([([result("https://ugc.gov.bd/notice/42", "Official notice", "The notice concerns one institution", "Tue, 11 Mar 2025 17:00:00 GMT")], None, 200)])
    monkeypatch.setattr(tavily_service, "_search", search)
    response = client.post(f"/api/v1/analyses/{analysis_id}/retrieve")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["retrieval"]["status"] == "completed"
    assert body["verification"] is None
    assert len(body["evidence"]) == 1
    assert body["evidence"][0]["source_type"] == "official_authority"
    assert body["evidence"][0]["published_at"] is not None
    assert body["evidence"][0]["retrieved_at"]
    assert len(calls) == 1
    with Session(get_engine(settings.database_url)) as session:
        assert len(session.exec(select(Evidence)).all()) == 1
        assert session.get(RetrievalRun, analysis_id).query_count == 1
        events = session.exec(select(ProviderEvent).where(ProviderEvent.analysis_id == analysis_id)).all()
        assert len(events) == 1 and events[0].provider == "tavily"
        assert "test-secret-key" not in str(events[0].model_dump())
    get_engine(settings.database_url).dispose()
    get_engine.cache_clear()
    assert client.get(f"/api/v1/analyses/{analysis_id}").json()["evidence"][0]["evidence_id"] == body["evidence"][0]["evidence_id"]
    assert client.delete(f"/api/v1/analyses/{analysis_id}").status_code == 204
    with Session(get_engine(settings.database_url)) as session:
        assert session.exec(select(Evidence)).all() == []
        assert session.get(RetrievalRun, analysis_id) is None


def test_api_rejects_unconfirmed_claim_and_invalidates_stale_evidence(client, monkeypatch):
    analysis_id = ready_analysis(client)
    settings = get_settings()
    settings.tavily_api_key = "test-key"
    search, _ = fake_search([([result("https://ugc.gov.bd/notice", "Notice", "Official notice for this claim")], None, 200)])
    monkeypatch.setattr(tavily_service, "_search", search)
    assert client.post(f"/api/v1/analyses/{analysis_id}/retrieve").status_code == 200
    assert client.get(f"/api/v1/analyses/{analysis_id}").json()["evidence"]
    assert client.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": "নতুন দাবি"}).status_code == 200
    after_ocr = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert after_ocr["evidence"] == [] and after_ocr["extraction"] is None
    assert client.post(f"/api/v1/analyses/{analysis_id}/retrieve").status_code == 409
    client.post(f"/api/v1/analyses/{analysis_id}/run", json={})
    assert client.post(f"/api/v1/analyses/{analysis_id}/retrieve").status_code == 409


def test_api_no_key_returns_partial_limitation(client):
    analysis_id = ready_analysis(client)
    response = client.post(f"/api/v1/analyses/{analysis_id}/retrieve")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["retrieval"]["status"] == "unavailable"
    assert body["evidence"] == []
    assert any("not configured" in limitation for limitation in body["limitations"])


def test_verify_persists_traceable_report_and_clears_stale_verdict(client, monkeypatch):
    analysis_id = ready_analysis(client)
    settings = get_settings()
    settings.tavily_api_key = "test-key"
    search, _ = fake_search([([result("https://ugc.gov.bd/notice/42", "Official notice", "The claim is discussed in a detailed official notice about the event, location, and date. This notice provides enough context to compare the claim against the reported facts.")], None, 200)])
    monkeypatch.setattr(tavily_service, "_search", search)
    retrieved = client.post(f"/api/v1/analyses/{analysis_id}/retrieve")
    assert retrieved.status_code == 200
    evidence_id = retrieved.json()["evidence"][0]["evidence_id"]
    verified = client.post(f"/api/v1/analyses/{analysis_id}/verify")
    assert verified.status_code == 200
    body = verified.json()
    assert body["status"] == "partial"
    assert body["verification"]["label"] in {"unverified", "insufficient_evidence"}
    assert body["verification"]["comparison_method"] == "rule_fallback"
    assert body["evidence"][0]["evidence_id"] == evidence_id
    assert body["evidence"][0]["stance"] not in {"supports", "contradicts"}
    with Session(get_engine(settings.database_url)) as session:
        assert session.get(VerificationRecord, analysis_id) is not None
        assert session.get(ComparisonRecord, evidence_id) is not None
    assert client.get(f"/api/v1/analyses/{analysis_id}").json()["verification"] == body["verification"]
    with Session(get_engine(settings.database_url)) as session:
        saved = session.get(VerificationRecord, analysis_id)
        old_report = json.loads(saved.data_json)
        old_report["decision_method"] = "python_evidence_fusion_v7"
        saved.data_json = json.dumps(old_report)
        session.add(saved)
        session.commit()
    stale = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert stale["verification"] is None
    assert stale["status"] == "partial"
    assert any("Rerun verification" in note for note in stale["limitations"])
    after_edit = client.patch(f"/api/v1/analyses/{analysis_id}/ocr", json={"text": "নতুন দাবি"})
    assert after_edit.status_code == 200
    assert after_edit.json()["verification"] is None
    with Session(get_engine(settings.database_url)) as session:
        assert session.get(VerificationRecord, analysis_id) is None
        assert session.get(ComparisonRecord, evidence_id) is None


def test_claim_rerun_clears_previous_report_before_slow_extraction_finishes(client, monkeypatch):
    analysis_id = ready_analysis(client)
    settings = get_settings()
    settings.tavily_api_key = "test-key"
    search, _ = fake_search([([result("https://ugc.gov.bd/notice/42", "Official notice", "The claim is discussed in an official notice")], None, 200)])
    monkeypatch.setattr(tavily_service, "_search", search)
    assert client.post(f"/api/v1/analyses/{analysis_id}/retrieve").status_code == 200
    assert client.post(f"/api/v1/analyses/{analysis_id}/verify").status_code == 200
    assert client.get(f"/api/v1/analyses/{analysis_id}").json()["evidence"]

    entered, release = Event(), Event()

    def slow_extract(text, caption, config, override=None):
        entered.set()
        assert release.wait(10)
        return ExtractionOutcome(extraction=ClaimExtraction(claim=override, needs_user_confirmation=False), method="fixture")

    monkeypatch.setattr(gemini_service, "extract_claim", slow_extract)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, f"/api/v1/analyses/{analysis_id}/run", json={"claim": "নতুন দাবি"})
        try:
            assert entered.wait(5)
            pending = client.get(f"/api/v1/analyses/{analysis_id}").json()
            assert pending["status"] == "processing"
            assert pending["extraction"] is None
            assert pending["retrieval"] is None
            assert pending["evidence"] == []
            assert pending["verification"] is None
        finally:
            release.set()
        assert future.result(timeout=10).status_code == 200
    fresh = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert fresh["extraction"]["claim"] == "নতুন দাবি"
    assert fresh["evidence"] == [] and fresh["verification"] is None


def test_search_retry_clears_old_report_before_slow_provider_finishes(client, monkeypatch):
    analysis_id = ready_analysis(client)
    settings = get_settings()
    settings.tavily_api_key = "test-key"
    search, _ = fake_search([([result("https://ugc.gov.bd/notice/42", "Official notice", "The claim is discussed in an official notice")], None, 200)])
    monkeypatch.setattr(tavily_service, "_search", search)
    assert client.post(f"/api/v1/analyses/{analysis_id}/retrieve").status_code == 200
    assert client.post(f"/api/v1/analyses/{analysis_id}/verify").status_code == 200
    assert client.get(f"/api/v1/analyses/{analysis_id}").json()["verification"] is not None

    entered, release = Event(), Event()

    def slow_retrieve(*_args):
        entered.set()
        assert release.wait(10)
        return tavily_service.RetrievalOutcome(status="unavailable", query_count=1, successful_queries=0, limitation="Search timed out.")

    monkeypatch.setattr(tavily_service, "retrieve", slow_retrieve)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, f"/api/v1/analyses/{analysis_id}/retrieve")
        try:
            assert entered.wait(5)
            pending = client.get(f"/api/v1/analyses/{analysis_id}").json()
            assert pending["status"] == "processing"
            assert pending["extraction"] is not None
            assert pending["retrieval"] is None
            assert pending["evidence"] == []
            assert pending["verification"] is None
        finally:
            release.set()
        assert future.result(timeout=10).status_code == 200
    after = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert after["retrieval"]["status"] == "unavailable"
    assert after["evidence"] == [] and after["verification"] is None
