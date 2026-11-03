"""Repeatable synthetic fusion demo; never presented as a real fact check."""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.models.evidence import Evidence, RetrievalRun
from app.schemas.providers import ComparisonOutcome, EvidenceComparison
from app.services.evidence_fusion import fuse


cases = json.loads((Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "demo_cases.json").read_text(encoding="utf-8"))
for case in cases:
    items = []
    comparisons = []
    for index, source in enumerate(case["sources"]):
        evidence_id = f"ev_demo_{index}"
        text = ("This synthetic source discusses the demo claim and its date, location, and outcome. " * 3).strip()
        items.append(Evidence(id=evidence_id, analysis_id="an_demo", url=f"https://{source['domain']}/demo", canonical_url=f"https://{source['domain']}/demo", title="Synthetic demo", domain=source["domain"], source_type=source["type"], source_rank=index, snippet=text, published_at=datetime.now(timezone.utc), retrieved_at=datetime.now(timezone.utc), query="synthetic demo"))
        comparisons.append(EvidenceComparison(evidence_id=evidence_id, stance=source["stance"], relevance=1, reason="Synthetic demo comparison.", quote="This synthetic source"))
    retrieval = RetrievalRun(analysis_id="an_demo", status="completed" if items else "no_results", query_count=1, successful_queries=1, retrieved_at=datetime.now(timezone.utc))
    report = fuse(items, ComparisonOutcome(comparisons=comparisons, method="gemini" if items else "none"), retrieval)
    if report.label != case["expected"]:
        raise SystemExit(f"Demo {case['name']} yielded {report.label}, expected {case['expected']}")
    print(json.dumps({"case": case["name"], "label": report.label, "coverage": report.evidence_coverage, "citations": [reason.evidence_id for reason in report.reasons], "synthetic": True}))
