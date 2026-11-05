"""Run synthetic category cards through the real API in an isolated database.

No provider response or credential is embedded in the test fixtures. Output is
an observation log, not an assertion that a verdict is correct.
"""

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.db.session import get_engine
from app.main import app
from app.models.analysis import ProviderEvent


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "docs/manual-test-cases/category-evaluation.json"
CARDS = ROOT / "docs/manual-test-cases/category-cards"
MANUAL_CASES = ROOT / "docs/manual-test-cases/manual-evaluation.json"
LOG = ROOT / "docs/manual-test-cases/category-evaluation-run.json"


def request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path}: HTTP {response.status_code}: {response.text[:300]}")
    return response.json() if response.content else None


def run_case(client, case, min_confidence):
    path = ROOT / "docs/manual-test-cases" / case["file"] if case.get("file") else CARDS / f"{case['id']}.png"
    with path.open("rb") as file:
        upload = request(client, "POST", "/api/v1/analyses", files={"file": (path.name, file, "image/png")})
    analysis_id = upload["analysis_id"]
    ocr = upload["ocr"]
    observation = {
        "id": case["id"], "difficulty": case["difficulty"], "language": case["language"],
        "categories": case["categories"], "expected_claim": case["expected_claim"],
        "ocr_text": ocr["text"], "ocr_confidence": ocr["confidence"], "ocr_error": ocr["error_code"],
    }
    corrected = not ocr["text"].strip() or (ocr["confidence"] or 0) < min_confidence
    request(client, "PATCH", f"/api/v1/analyses/{analysis_id}/ocr", json={"text": case["claim"] if corrected else ocr["text"]})
    observation["ocr_corrected"] = corrected
    extracted = request(client, "POST", f"/api/v1/analyses/{analysis_id}/run", json={})
    initial = extracted.get("extraction") or {}
    observation["initial_claim"] = initial.get("claim")
    observation["initial_extraction_method"] = extracted.get("extraction_method")
    if initial.get("needs_user_confirmation") or not initial.get("claim") or case["claim"].casefold() not in initial["claim"].casefold():
        extracted = request(client, "POST", f"/api/v1/analyses/{analysis_id}/run", json={"claim": case["claim"]})
        observation["claim_corrected"] = True
    else:
        observation["claim_corrected"] = False
    observation["final_claim"] = (extracted.get("extraction") or {}).get("claim")
    found = request(client, "POST", f"/api/v1/analyses/{analysis_id}/retrieve")
    observation["retrieval"] = found.get("retrieval")
    report = request(client, "POST", f"/api/v1/analyses/{analysis_id}/verify")
    observation["sources"] = [{"url": e["url"], "title": e["title"], "domain": e["domain"], "published_at": e["published_at"], "snippet": e["snippet"], "stance": e["stance"], "quote": e["quote"], "relevance": e["relevance"]} for e in report["evidence"]]
    verification = report.get("verification") or {}
    observation["report_status"] = report["status"]
    observation["verdict"] = verification.get("label")
    observation["reasons"] = verification.get("reasons")
    observation["event_details"] = verification.get("event_details")
    observation["publisher"] = verification.get("publisher")
    observation["layers"] = verification.get("layers")
    observation["limitations"] = verification.get("limitations")
    observation["comparison_method"] = verification.get("comparison_method")
    with Session(get_engine(get_settings().database_url)) as session:
        events = session.exec(select(ProviderEvent).where(ProviderEvent.analysis_id == analysis_id)).all()
        observation["provider_events"] = [{"operation": event.operation, "success": event.success, "status_code": event.status_code, "error_code": event.error_code} for event in events]
    return observation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="*", help="Run only these case IDs")
    parser.add_argument("--set", choices=("category", "manual", "all"), default="category")
    parser.add_argument("--output", type=Path, default=LOG)
    args = parser.parse_args()
    cases = (json.loads(CASES.read_text(encoding="utf-8")) if args.set in {"category", "all"} else [])
    if args.set in {"manual", "all"}:
        cases.extend(json.loads(MANUAL_CASES.read_text(encoding="utf-8")))
    if args.ids:
        cases = [case for case in cases if case["id"] in args.ids]
    settings = get_settings()
    original = (settings.database_url, settings.upload_dir, settings.gemini_model, settings.rate_limit_enabled)
    observations = []
    with TemporaryDirectory(dir=ROOT / "backend/data") as folder:
        settings.database_url = f"sqlite:///{(Path(folder) / 'evaluation.db').as_posix()}"
        settings.upload_dir = str(Path(folder) / "uploads")
        # The configured primary model timed out in the preflight probe; the
        # configured fallback succeeded. This still uses live Gemini.
        settings.gemini_model = settings.gemini_fallback_model
        settings.rate_limit_enabled = False
        get_engine.cache_clear()
        try:
            with TestClient(app) as client:
                for case in cases:
                    print(f"Running {case['id']}...", flush=True)
                    try:
                        observations.append(run_case(client, case, settings.min_ocr_confidence))
                    except Exception as error:
                        observations.append({"id": case["id"], "difficulty": case["difficulty"], "language": case["language"], "categories": case["categories"], "expected_claim": case["expected_claim"], "error": str(error)})
                    args.output.write_text(json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8")
        finally:
            get_engine(settings.database_url).dispose()
            get_engine.cache_clear()
            settings.database_url, settings.upload_dir, settings.gemini_model, settings.rate_limit_enabled = original
    print(f"Saved {len(observations)} observations to {args.output}")


if __name__ == "__main__":
    main()
