from datetime import datetime, timezone

from app.models.evidence import Evidence, RetrievalRun
from app.schemas.analysis import CitedDetail, EventDetails, EvidenceReason, LayerRead, VerificationRead
from app.schemas.providers import ClaimExtraction, ComparisonOutcome

SOURCE_WEIGHTS = {"official_authority": 1.0, "claimed_publisher": 0.9, "fact_check": 0.9, "independent_news": 0.75, "government_site": 0.25, "other": 0.2}


def _weight(item: Evidence, relevance: float, now: datetime) -> float:
    age_days = max(0, (now - item.published_at.replace(tzinfo=timezone.utc)).days) if item.published_at else None
    recency = 1.0 if age_days is not None and age_days <= 90 else 0.85 if age_days is not None and age_days <= 365 else 0.7 if age_days is not None else 0.8
    content = min(1.0, max(0.35, len(item.snippet.strip()) / 160))
    return SOURCE_WEIGHTS.get(item.source_type, 0.2) * relevance * recency * content


def fuse(items: list[Evidence], comparisons: ComparisonOutcome, retrieval: RetrievalRun, extraction: ClaimExtraction | None = None) -> VerificationRead:
    now = datetime.now(timezone.utc)
    by_id = {item.id: item for item in items}
    ranked = []
    for comparison in comparisons.comparisons:
        item = by_id.get(comparison.evidence_id)
        if item is not None:
            ranked.append((item, comparison, _weight(item, comparison.relevance, now)))
    # Repeated pages from one publisher contribute at most one independent vote per stance.
    votes = {}
    for item, comparison, weight in ranked:
        if comparison.stance in {"supports", "contradicts"} and comparison.quote:
            key = (item.domain, comparison.stance)
            if key not in votes or weight > votes[key][2]:
                votes[key] = (item, comparison, weight)
    support = [vote for vote in votes.values() if vote[1].stance == "supports" and vote[2] >= 0.45]
    contradict = [vote for vote in votes.values() if vote[1].stance == "contradicts" and vote[2] >= 0.45]
    direct_support = [vote for vote in support if vote[0].source_type == "official_authority" and vote[2] >= 0.7]
    direct_contradict = [vote for vote in contradict if vote[0].source_type == "official_authority" and vote[2] >= 0.7]
    if support and contradict and any(left[0].domain != right[0].domain for left in support for right in contradict):
        label = "conflicting"
        selected = support + contradict
    elif support and contradict:
        label = "unverified"
        selected = []
    elif direct_support:
        label = "verified"
        selected = direct_support
    elif direct_contradict or len(contradict) >= 2:
        label = "contradicted"
        selected = direct_contradict or contradict
    elif len(support) >= 2:
        label = "supported"
        selected = support
    elif retrieval.status in {"unavailable", "partial", "no_results"} or not any(row[1].relevance >= 0.2 and row[1].stance != "unrelated" for row in ranked):
        label = "insufficient_evidence"
        selected = []
    else:
        label = "unverified"
        selected = []
    reasons = [EvidenceReason(evidence_id=item.id, url=item.url, stance=comparison.stance, summary=comparison.reason) for item, comparison, _ in selected]
    # Event fields come only from a relevant supporting source and remain separate
    # from the claim verdict, publication metadata, and image provenance.
    event_details = EventDetails()
    supporting = [(item, row) for item, row, _ in ranked if row.stance == "supports" and row.relevance >= 0.5 and row.quote and len(row.quote.strip()) >= 20 and row.quote.strip() in f"{item.title} {item.snippet}"]
    if supporting:
        item, row = max(supporting, key=lambda pair: _weight(pair[0], pair[1].relevance, now))
        cite = lambda value: CitedDetail(value=value, evidence_id=item.id, url=item.url)
        event_details.what = cite(row.quote.strip())
        event_details.reported_by = cite(item.domain)
        source_text = f"{item.title} {item.snippet}".casefold()
        if extraction:
            if extraction.event_date_text and extraction.event_date_text.casefold() in source_text:
                event_details.when = cite(extraction.event_date_text)
            for place in extraction.places:
                if place and place.casefold() in source_text:
                    event_details.where = cite(place)
                    break
    credible_domains = {item.domain for item, comparison, weight in ranked if comparison.relevance >= 0.5 and weight >= 0.3}
    coverage = "high" if len(credible_domains) >= 3 and retrieval.status == "completed" else "medium" if len(credible_domains) >= 2 and retrieval.status == "completed" else "low"
    summary = {
        "verified": "A direct official source supports the claim.",
        "supported": "Multiple independent credible sources support the claim.",
        "contradicted": "Direct official or multiple independent credible sources contradict the claim.",
        "conflicting": "Credible sources both support and contradict the claim.",
        "unverified": "Search results do not establish a consistent conclusion.",
        "insufficient_evidence": "Available evidence is insufficient to assess the claim.",
    }[label]
    limitations = ["Only search result titles and snippets were compared; full pages and image provenance were not checked."]
    if retrieval.limitation:
        limitations.append(retrieval.limitation)
    if comparisons.method != "gemini":
        limitations.append("Some or all evidence comparisons used conservative rule fallback.")
    if label == "unverified":
        limitations.append("Search without confirmation does not establish that the claim is false.")
    return VerificationRead(
        label=label, flags=[], evidence_coverage=coverage, summary=summary, reasons=reasons,
        decision_method="python_evidence_fusion_v3",
        comparison_method=comparisons.method, fallbacks_used=comparisons.fallbacks_used,
        limitations=limitations, event_details=event_details, layers={
            "claim": LayerRead(status=label, summary=summary),
            "source": LayerRead(status="inconclusive", summary="Source identity was not independently authenticated."),
            "context": LayerRead(status="inconclusive", summary="Image or event provenance was not independently established."),
            "media": LayerRead(status="inconclusive", summary="Media authenticity was not tested."),
        },
    )
