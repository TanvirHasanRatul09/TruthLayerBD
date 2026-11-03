import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

from app.core.config import Settings
from app.models.evidence import Evidence
from app.schemas.providers import ComparisonOutcome, EvidenceComparison, ProviderAttempt
from app.services.gemini_service import _post

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "compare_evidence.txt").read_text(encoding="utf-8")
SCHEMA = {
    "type": "OBJECT",
    "properties": {"comparisons": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "evidence_id": {"type": "STRING"}, "stance": {"type": "STRING", "enum": ["supports", "contradicts", "mentions_but_unclear", "unrelated", "insufficient_content"]},
        "relevance": {"type": "NUMBER"}, "reason": {"type": "STRING"}, "quote": {"type": "STRING", "nullable": True},
    }, "required": ["evidence_id", "stance", "relevance", "reason", "quote"]}}},
    "required": ["comparisons"],
}


def _fallback(item: Evidence, claim: str) -> EvidenceComparison:
    text = f"{item.title} {item.snippet}".strip()
    if len(item.snippet.strip()) < 25:
        stance, relevance, reason = "insufficient_content", 0.0, "Search snippet is too short to compare with the claim."
    else:
        claim_words = {word for word in re.findall(r"\w+", claim.casefold()) if len(word) > 2}
        words = set(re.findall(r"\w+", text.casefold()))
        overlap = len(claim_words & words) / max(len(claim_words), 1)
        stance = "mentions_but_unclear" if overlap >= 0.2 else "unrelated"
        relevance = min(overlap, 0.6)
        reason = "Snippet overlaps the claim but its stance cannot be established by rule." if stance == "mentions_but_unclear" else "Snippet has little lexical overlap with the claim."
    return EvidenceComparison(evidence_id=item.id, stance=stance, relevance=relevance, reason=reason, method="rule_fallback")


_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_BD_TIME = timezone(timedelta(hours=6))
_MONTHS = ((), ("জানুয়ারি", "জানুয়ারি", "january", "jan"), ("ফেব্রুয়ারি", "ফেব্রুয়ারি", "february", "feb"), ("মার্চ", "march", "mar"), ("এপ্রিল", "april", "apr"), ("মে", "may"), ("জুন", "june"), ("জুলাই", "july"), ("আগস্ট", "august"), ("সেপ্টেম্বর", "september", "sep"), ("অক্টোবর", "october", "oct"), ("নভেম্বর", "november", "nov"), ("ডিসেম্বর", "december", "dec"))


def _current_price_claim(claim: str) -> bool:
    folded = claim.casefold()
    return any(word in folded for word in ("দাম", "মূল্য", "price")) and any(word in folded for word in ("নতুন", "বর্তমান", "এখন", "আজ", "latest", "current", "new", "today"))


def _amounts(text: str) -> set[str]:
    normalized = text.translate(_DIGITS).replace(",", "")
    amounts = {str(int(match.group(1)) * 1000 + int(match.group(2) or 0)) for match in re.finditer(r"(\d+)\s*হাজার\s*(\d+)?\s*(?:টাকা|tk\b)", normalized, re.I)}
    amounts.update(str(int(match.group(1))) for match in re.finditer(r"(\d{3,5})\s*(?:টাকা|tk\b)", normalized, re.I))
    return amounts


def _same_current_period(item: Evidence, now: datetime) -> bool:
    if item.published_at:
        date = item.published_at.astimezone(_BD_TIME) if item.published_at.tzinfo else item.published_at
        return (date.year, date.month) == (now.year, now.month)
    text = f"{item.title} {item.snippet}".casefold().translate(_DIGITS)
    years = set(re.findall(r"\b20\d{2}\b", text))
    return years == {str(now.year)} and any(month in text for month in _MONTHS[now.month])


def _guard(comparison: EvidenceComparison, item: Evidence, claim: str, now: datetime) -> EvidenceComparison:
    if comparison.stance == "supports":
        claim_text = claim.casefold()
        cited_text = (comparison.quote or "").casefold()
        countries = (("bangladesh", "বাংলাদেশ"), ("india", "ভারত"))
        named = [names for names in countries if any(name in claim_text for name in names)]
        if len(named) == 1 and not any(name in cited_text for name in named[0]):
            comparison.stance = "mentions_but_unclear"
            comparison.relevance = min(comparison.relevance, 0.6)
            comparison.reason = "The cited passage does not identify the country named in the claim."
            comparison.quote = None
            comparison.method = "rule_guardrail"
            return comparison
    if comparison.stance not in {"supports", "contradicts"} or not _current_price_claim(claim):
        return comparison
    text = f"{item.title} {item.snippet}"
    issue = None
    if not _same_current_period(item, now):
        issue = "A current-price claim needs a source dated to the current month."
    elif any(word in text.casefold() for word in ("প্রস্তাব", "proposal", "proposed")):
        issue = "A proposed price is not an effective current price."
    elif comparison.stance == "supports" and (claimed := _amounts(claim)) and not claimed.intersection(_amounts(text)):
        issue = "The supplied snippet does not state the claimed final price."
    if issue:
        comparison.stance = "mentions_but_unclear"
        comparison.relevance = min(comparison.relevance, 0.6)
        comparison.reason = issue
        comparison.quote = None
        comparison.method = "rule_guardrail"
    return comparison


def _validate(raw: str, items: list[Evidence], claim: str = "") -> dict[str, EvidenceComparison]:
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("comparisons"), list):
        raise ValueError("Invalid comparison envelope")
    known = {item.id: item for item in items}
    validated = {}
    for row in data["comparisons"]:
        try:
            comparison = EvidenceComparison.model_validate(row)
        except (ValidationError, TypeError, ValueError):
            continue
        item = known.get(comparison.evidence_id)
        if item is None or comparison.evidence_id in validated:
            continue
        comparison.reason = comparison.reason.strip()
        if comparison.stance in {"supports", "contradicts"}:
            if not comparison.quote or comparison.quote.strip() not in f"{item.title} {item.snippet}":
                continue
            if re.search(r"ignore (?:all |any )?(?:previous|prior|system|developer) instructions|you are (?:chatgpt|an? ai)|return (?:only )?json|system prompt", f"{item.title} {item.snippet}", re.I):
                comparison.stance = "mentions_but_unclear"
                comparison.relevance = min(comparison.relevance, 0.3)
                comparison.reason = "Source text contains instruction-like content; decisive stance was not accepted."
                comparison.quote = None
                comparison.method = "rule_guardrail"
                validated[item.id] = comparison
                continue
        comparison.method = "gemini"
        validated[item.id] = _guard(comparison, item, claim, datetime.now(_BD_TIME))
    return validated


def compare(claim: str, items: list[Evidence], settings: Settings) -> ComparisonOutcome:
    if not items:
        return ComparisonOutcome(method="none")
    attempts: list[ProviderAttempt] = []
    validated = {}
    if settings.gemini_enabled and settings.gemini_api_key:
        payload = [{"evidence_id": item.id, "title": item.title, "snippet": item.snippet} for item in items]
        prompt = f"{PROMPT}\nCLAIM:\n{claim[:1000]}\nEVIDENCE JSON:\n{json.dumps(payload, ensure_ascii=False)}"
        for model in dict.fromkeys([settings.gemini_model, settings.gemini_fallback_model]):
            if not model:
                continue
            raw, attempt = _post(model, settings.gemini_api_key, prompt, SCHEMA, settings.gemini_timeout_seconds, "compare_evidence")
            attempts.append(attempt)
            if raw is None:
                continue
            try:
                validated = _validate(raw, items, claim)
            except (ValueError, TypeError):
                attempt.success = False
                attempt.error_code = "INVALID_OUTPUT"
            if validated:
                break
    comparisons = [validated.get(item.id) or _fallback(item, claim) for item in items]
    used_fallback = any(row.method != "gemini" for row in comparisons)
    return ComparisonOutcome(
        comparisons=comparisons,
        method="gemini_with_fallback" if validated and used_fallback else "gemini" if validated else "rule_fallback",
        attempts=attempts,
        fallbacks_used=(
            (["A country-specific claim needs a cited passage naming that country."] if any(row.reason == "The cited passage does not identify the country named in the claim." for row in comparisons) else [])
            + (["Undated, outdated, proposed, or price-mismatched snippets cannot establish a current price."] if any(row.method == "rule_guardrail" and row.reason != "The cited passage does not identify the country named in the claim." for row in comparisons) else [])
            + (["Rule comparison cannot establish support or contradiction."] if any(row.method == "rule_fallback" for row in comparisons) else [])
        ),
    )
