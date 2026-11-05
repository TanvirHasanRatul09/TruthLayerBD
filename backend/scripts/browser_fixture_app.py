"""Local-only browser scenarios for no-result and mixed-evidence UI checks.

Run with BROWSER_FIXTURE_MODE=no_results, mixed, true, or false and an isolated database.
The synthetic .example links never represent real-world evidence.
"""
import os
from datetime import datetime, timezone

from app.main import app
from app.schemas.providers import ComparisonOutcome, EvidenceComparison
from app.services import comparison_service, tavily_service


mode = os.environ.get("BROWSER_FIXTURE_MODE", "no_results")
if mode not in {"no_results", "mixed", "true", "false"}:
    raise RuntimeError("Invalid BROWSER_FIXTURE_MODE")

original_source_type = tavily_service._source_type


def fixture_source_type(domain, claimed_source, claim=""):
    if domain == "fixture-a.example":
        return "independent_news", 3
    if domain == "fixture-b.example":
        return "fact_check", 2
    if domain == "fixture-authority.example":
        return "official_authority", 0
    return original_source_type(domain, claimed_source, claim)


def fixture_retrieve(extraction, analysis_id, settings):
    if mode == "no_results":
        return tavily_service.RetrievalOutcome(status="no_results", query_count=1, successful_queries=1)
    now = datetime.now(timezone.utc)
    passages = (
        ("ev_fixture_for", "fixture-a.example", "The Eiffel Tower is in Berlin, Germany."),
        ("ev_fixture_against", "fixture-b.example", "The Eiffel Tower is in Paris, France, not Berlin, Germany."),
    ) if mode == "mixed" else (
        ("ev_fixture_decisive", "fixture-authority.example", "The Eiffel Tower is in Paris, France, not Berlin, Germany." if mode == "false" else "UNESCO listed the Sundarbans in Bangladesh in 1997."),
    )
    return tavily_service.RetrievalOutcome(
        status="completed", query_count=1, successful_queries=1,
        items=[tavily_service.EvidenceItem(
            evidence_id=evidence_id, url=f"https://{domain}/synthetic-{analysis_id}",
            canonical_url=f"https://{domain}/synthetic-{analysis_id}",
            title=passage, snippet=passage + " Synthetic browser fixture only. " * 8,
            domain=domain, source_type=fixture_source_type(domain, None, extraction.claim or "")[0],
            source_rank=1, published_at=now, retrieved_at=now, query=extraction.claim or "",
        ) for evidence_id, domain, passage in passages],
    )


def fixture_compare(claim, items, settings):
    return ComparisonOutcome(method="gemini", comparisons=[
        EvidenceComparison(evidence_id=item.id, stance="supports" if item.id == "ev_fixture_for" or mode == "true" else "contradicts",
                           relevance=1, reason="Synthetic passage states a location.", quote=item.title, method="gemini")
        for item in items
    ])


tavily_service._source_type = fixture_source_type
tavily_service.retrieve = fixture_retrieve
comparison_service.compare = fixture_compare
