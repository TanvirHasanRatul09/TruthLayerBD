import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

from app.core.config import Settings
from app.models.evidence import Evidence
from app.schemas.providers import ComparisonOutcome, EvidenceComparison, ProviderAttempt
from app.services.gemini_service import _post_with_retry

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
    # A dated inscription can be compared without AI only when an official
    # passage explicitly ties the same named property and country to the
    # inscription year. A nomination or the adjoining country's site is not
    # enough.
    inscription = re.search(r"\blisted\s+(?:the\s+)?(.+?)\s+in\s+(Bangladesh|India)\b.*?\b(?:19|20)\d{2}\b", claim, re.I)
    claimed_years = re.findall(r"\b(?:19|20)\d{2}\b", claim)
    if inscription and len(claimed_years) == 1 and item.source_type == "official_authority" and "unesco" in claim.casefold():
        subject, country = inscription.group(1).strip(), inscription.group(2)
        for sentence in re.split(r"(?<=[.!?])\s+", item.snippet):
            if len(sentence) > 350 or "inscrib" not in sentence.casefold() or "world heritage" not in sentence.casefold():
                continue
            if not re.search(rf"\b{re.escape(subject)}\b", sentence, re.I) or not re.search(rf"\b(?:of|in|from)\s+{re.escape(country)}\b", sentence, re.I):
                continue
            years = set(re.findall(r"\b(?:19|20)\d{2}\b", sentence))
            if len(years) == 1:
                actual_year = next(iter(years))
                return EvidenceComparison(evidence_id=item.id, stance="supports" if actual_year == claimed_years[0] else "contradicts", relevance=1.0,
                    reason=f"The official inscription passage gives {actual_year} for {subject} in {country}; the claim says {claimed_years[0]}.",
                    quote=sentence.strip(), method="official_inscription_rule")
    # A narrow, auditable fallback for an unambiguous location assertion. It
    # uses the source's own words, only for a recognized official authority.
    # A different landmark, replica, or page merely mentioning two places
    # cannot establish a contradiction.
    location = re.fullmatch(r"(?:the\s+)?(.+?)\s+(?:is|stands|lies|is located)\s+(?:in|at)\s+([\w .'-]+?)(?:,\s*([\w .'-]+))?\.?", claim.strip(), re.I)
    if location and item.source_type == "official_authority":
        subject, claimed_city, claimed_country = location.group(1).strip(), location.group(2).strip(" ."), (location.group(3) or "").strip(" .")
        if len(subject.split()) >= 2 and len(claimed_city.split()) <= 3 and not re.search(r"\b(?:replica|copy|miniature|tv tower)\b", text, re.I):
            address = re.search(rf"\b{re.escape(subject)}\b.{{0,100}}\bAddress\s+(.{{0,110}}?\b\d{{4,6}}\s+([A-Z][a-z]+)(?:,\s*([A-Z][a-z]+))?)", item.snippet, re.I)
            if address:
                actual_city, actual_country = address.group(2), address.group(3)
                if actual_city.casefold() != claimed_city.casefold() or (actual_country and claimed_country and actual_country.casefold() != claimed_country.casefold()):
                    return EvidenceComparison(evidence_id=item.id, stance="contradicts", relevance=1.0,
                        reason=f"The official source gives an address in {actual_city}, not the claimed place.",
                        quote=address.group(0), method="official_location_rule")
                if actual_city.casefold() == claimed_city.casefold() and (not claimed_country or actual_country and actual_country.casefold() == claimed_country.casefold()):
                    return EvidenceComparison(evidence_id=item.id, stance="supports", relevance=1.0,
                        reason=f"The official source gives an address in {actual_city}.",
                        quote=address.group(0), method="official_location_rule")
            place_pattern = rf"\b(?:[Tt]he\s+)?{re.escape(subject)}\b\s+(?:is\s+)?(?:located|situated|found|stands|lies)?\s*(?:in|at)\s+(?:the heart of\s+)?([A-Z][a-z]+)"
            sentence = next((part.strip() for part in re.split(r"(?<=[.!?])\s+", item.snippet) if re.search(place_pattern, part)), None)
            if sentence:
                place = re.search(place_pattern, sentence)
                if place and len(sentence) <= 300:
                    actual_city = place.group(1)
                    if claimed_country and actual_city.casefold() == claimed_city.casefold():
                        country_sentence = next((part.strip() for part in re.split(r"(?<=[.!?])\s+", item.snippet)
                            if re.search(rf"\b{re.escape(actual_city)}\s*,\s*([A-Z][a-z]+)\b", part)), None)
                        if not country_sentence or len(country_sentence) > 300:
                            country_sentence = None
                        country_match = re.search(rf"\b{re.escape(actual_city)}\s*,\s*([A-Z][a-z]+)\b", country_sentence or "")
                        if not country_match:
                            return EvidenceComparison(evidence_id=item.id, stance="mentions_but_unclear", relevance=0.6,
                                reason="The official excerpt identifies the city but not the claimed country.", method="rule_fallback")
                        actual_country = country_match.group(1)
                        stance = "supports" if actual_country.casefold() == claimed_country.casefold() else "contradicts"
                        sentence = country_sentence
                    else:
                        stance = "supports" if actual_city.casefold() == claimed_city.casefold() else "contradicts"
                    return EvidenceComparison(evidence_id=item.id, stance=stance, relevance=1.0,
                        reason=f"The official source places {subject} in {actual_city}; the claim says {claimed_city}{', ' + claimed_country if claimed_country else ''}.",
                        quote=sentence, method="official_location_rule")
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
    # A mission's return to Earth is not evidence about a claimed Moon
    # landing. For movement or arrival claims, the cited passage must name
    # the destination before it can decide either side.
    destination = re.search(r"\b(?:landed|walked|arrived|stood|crashed|touched down)\s+(?:\w+\s+){0,3}?(?:on|in|at)\s+(?:the\s+)?([A-Z][A-Za-z]+)\b", claim)
    if comparison.stance in {"supports", "contradicts"} and destination and not re.search(rf"\b{re.escape(destination.group(1))}\b", comparison.quote or "", re.I):
        comparison.stance = "mentions_but_unclear"
        comparison.relevance = min(comparison.relevance, 0.6)
        comparison.reason = "The cited passage does not name the destination in the claim."
        comparison.quote = None
        comparison.method = "rule_guardrail"
        return comparison
    simple_location = re.fullmatch(r"(?:the\s+)?(.+?)\s+(?:is|stands|lies|is located)\s+(?:in|at)\s+([\w .'-]+?)(?:,\s*([\w .'-]+))?\.?", claim.strip(), re.I)
    if comparison.stance == "contradicts" and simple_location:
        subject = simple_location.group(1).strip()
        quote = comparison.quote or ""
        quote_start = item.snippet.find(quote)
        nearby = item.snippet[max(0, quote_start - 120):quote_start] if quote_start >= 0 else ""
        direct_subject = bool(re.search(rf"\b(?:the\s+)?{re.escape(subject)}\b", quote, re.I))
        explicit_denial = bool(re.search(rf"\b(?:not|never)\s+(?:located\s+)?in\s+{re.escape(simple_location.group(2).strip())}\b", quote, re.I))
        direct_place = bool(re.search(r"\b(?:in|at|located in)\s+(?:the heart of\s+)?[A-Z][a-z]+\b|\b[A-Z][a-z]+,\s*[A-Z][a-z]+\b", quote))
        official_address = item.source_type == "official_authority" and "address" in nearby.casefold() and subject.casefold() in nearby.casefold()
        if not ((direct_subject and (direct_place or explicit_denial)) or official_address):
            comparison.stance = "mentions_but_unclear"
            comparison.relevance = min(comparison.relevance, 0.6)
            comparison.reason = "The cited passage does not directly place the named subject or deny its claimed location."
            comparison.quote = None
            comparison.method = "rule_guardrail"
            return comparison
    if comparison.stance == "supports":
        claim_text = claim.casefold()
        cited_text = (comparison.quote or "").casefold()
        claimed_years = set(re.findall(r"\b(?:19|20)\d{2}\b", claim.translate(_DIGITS)))
        cited_year_text = (comparison.quote or "").translate(_DIGITS)
        cited_years = set(re.findall(r"\b(?:19|20)\d{2}\b", cited_year_text))
        negated_year = any(re.search(rf"\b(?:not|never)\s+(?:in\s+)?{year}\b", cited_year_text, re.I) for year in claimed_years)
        if claimed_years and (not claimed_years.issubset(cited_years) or negated_year):
            comparison.stance = "mentions_but_unclear"
            comparison.relevance = min(comparison.relevance, 0.6)
            comparison.reason = "The cited passage does not state the year named in the claim."
            comparison.quote = None
            comparison.method = "rule_guardrail"
            return comparison
        location = re.search(r"\b(?:in|at)\s+([A-Z][a-z]+)(?:\s*,\s*([A-Z][a-z]+))?", claim)
        negated_place = bool(location and re.search(rf"\b(?:not|never)\s+in\s+{re.escape(location.group(1))}\b", cited_text, re.I))
        if location and (location.group(1).casefold() not in cited_text or (location.group(2) and location.group(2).casefold() not in cited_text) or negated_place):
            comparison.stance = "mentions_but_unclear"
            comparison.relevance = min(comparison.relevance, 0.6)
            comparison.reason = "The cited passage does not identify the place named in the claim."
            comparison.quote = None
            comparison.method = "rule_guardrail"
            return comparison
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
            raw, events = _post_with_retry(model, settings, prompt, SCHEMA, "compare_evidence")
            attempts.extend(events)
            attempt = events[-1]
            if raw is None:
                continue
            try:
                validated = _validate(raw, items, claim)
            except (ValueError, TypeError):
                attempt.success = False
                attempt.error_code = "INVALID_OUTPUT"
            if validated:
                break
    comparisons = []
    for item in items:
        model_row = validated.get(item.id)
        rule_row = _fallback(item, claim)
        if model_row and model_row.stance in {"supports", "contradicts"}:
            comparisons.append(model_row)
        elif rule_row.method in {"official_location_rule", "official_inscription_rule"} and rule_row.stance in {"supports", "contradicts"}:
            comparisons.append(rule_row)
        else:
            comparisons.append(model_row or rule_row)
    used_fallback = any(row.method != "gemini" for row in comparisons)
    return ComparisonOutcome(
        comparisons=comparisons,
        method="gemini_with_fallback" if validated and used_fallback else "gemini" if validated else "rule_fallback",
        attempts=attempts,
        fallbacks_used=(
            (["A country-specific claim needs a cited passage naming that country."] if any(row.reason == "The cited passage does not identify the country named in the claim." for row in comparisons) else [])
            + (["Undated, outdated, proposed, or price-mismatched snippets cannot establish a current price."] if any(row.method == "rule_guardrail" and row.reason != "The cited passage does not identify the country named in the claim." for row in comparisons) else [])
            + (["Rule comparison cannot establish support or contradiction."] if any(row.method == "rule_fallback" for row in comparisons) else [])
            + (["An official location statement was compared by a narrow text rule because AI comparison was unavailable."] if any(row.method == "official_location_rule" for row in comparisons) else [])
            + (["An official inscription date was compared by a narrow text rule because AI comparison was unavailable."] if any(row.method == "official_inscription_rule" for row in comparisons) else [])
        ),
    )
