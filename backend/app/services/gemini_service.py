import json
import re
import time
from pathlib import Path

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.providers import ClaimExtraction, ExtractionOutcome, ProviderAttempt
from app.services.tavily_service import PUBLISHER_DOMAINS

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "extract_claim.txt").read_text(encoding="utf-8")
API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"

_STRING = {"type": "STRING", "nullable": True}
_ARRAY = {"type": "ARRAY", "items": {"type": "STRING"}}
EXTRACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "claim": _STRING,
        "claimed_source": _STRING,
        "people": _ARRAY,
        "organizations": _ARRAY,
        "places": _ARRAY,
        "event_date_text": _STRING,
        "event_date": _STRING,
        "keywords": _ARRAY,
        "search_queries_bn": _ARRAY,
        "search_queries_en": _ARRAY,
        "needs_user_confirmation": {"type": "BOOLEAN"},
        "ambiguities": _ARRAY,
    },
    "required": ["claim", "claimed_source", "people", "organizations", "places", "event_date_text", "event_date", "keywords", "search_queries_bn", "search_queries_en", "needs_user_confirmation", "ambiguities"],
}
ACCESS_SCHEMA = {"type": "OBJECT", "properties": {"ok": {"type": "BOOLEAN"}}, "required": ["ok"]}


def _payload(prompt: str, schema: dict) -> dict:
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "temperature": 0,
        },
    }


def _post(model: str, api_key: str, prompt: str, schema: dict, timeout: int, operation: str) -> tuple[str | None, ProviderAttempt]:
    started = time.monotonic()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{API_ROOT}/{model}:generateContent",
                headers={"x-goog-api-key": api_key},
                json=_payload(prompt, schema),
            )
        duration = round((time.monotonic() - started) * 1000)
        if response.status_code != 200:
            code = "RATE_LIMITED" if response.status_code == 429 else "ACCESS_DENIED" if response.status_code in (401, 403, 404) else "SERVER_ERROR" if response.status_code >= 500 else "BAD_REQUEST"
            return None, ProviderAttempt(operation=operation, success=False, status_code=response.status_code, latency_ms=duration, error_code=code)
        body = response.json()
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        if not isinstance(text, str):
            raise ValueError("Missing text")
        return text, ProviderAttempt(operation=operation, success=True, status_code=200, latency_ms=duration)
    except httpx.TimeoutException:
        return None, ProviderAttempt(operation=operation, success=False, latency_ms=round((time.monotonic() - started) * 1000), error_code="TIMEOUT")
    except httpx.ConnectError:
        return None, ProviderAttempt(operation=operation, success=False, latency_ms=round((time.monotonic() - started) * 1000), error_code="NETWORK_ERROR")
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return None, ProviderAttempt(operation=operation, success=False, latency_ms=round((time.monotonic() - started) * 1000), error_code="BAD_RESPONSE")


def _post_with_retry(model: str, settings: Settings, prompt: str, schema: dict, operation: str) -> tuple[str | None, list[ProviderAttempt]]:
    """Retry transient provider failures; never retry malformed source evidence."""
    attempts = []
    for attempt_number in range(max(0, settings.gemini_max_retries) + 1):
        output, event = _post(model, settings.gemini_api_key, prompt, schema, settings.gemini_timeout_seconds, operation)
        attempts.append(event)
        if output is not None or event.error_code != "SERVER_ERROR" or attempt_number >= settings.gemini_max_retries:
            break
        time.sleep(min(0.5 * (attempt_number + 1), 2.0))
    return output, attempts


def _clean_list(values: list[str], limit: int = 8) -> list[str]:
    return [value.strip()[:160] for value in values if isinstance(value, str) and value.strip()][:limit]


def _overlaps(candidate: str, source: str) -> bool:
    tokens = [token for token in re.findall(r"\w+", candidate.casefold()) if len(token) > 1]
    source_tokens = set(re.findall(r"\w+", source.casefold()))
    return any(token in source_tokens for token in tokens)


def _visible_publisher(text: str) -> str | None:
    folded = text.casefold()
    for name in sorted(PUBLISHER_DOMAINS, key=len, reverse=True):
        if name in folded:
            return name
    return None


def validate_extraction(raw: str, source_text: str, max_queries: int) -> ClaimExtraction:
    value = ClaimExtraction.model_validate(json.loads(raw))
    value.claim = value.claim.strip() if value.claim else None
    if not value.claim or not _overlaps(value.claim, source_text):
        raise ValueError("Claim is not grounded in input")
    if value.claimed_source and value.claimed_source.casefold() not in source_text.casefold():
        value.claimed_source = None
        value.ambiguities.append("Claimed source was not present in input.")
        value.needs_user_confirmation = True
    if not value.claimed_source:
        value.claimed_source = _visible_publisher(source_text)
    if value.event_date_text and value.event_date_text.casefold() not in source_text.casefold():
        value.event_date_text = None
        value.event_date = None
        value.ambiguities.append("Date was not present in input.")
        value.needs_user_confirmation = True
    if not value.event_date_text or re.search(r"আগামীকাল|গতকাল|today|tomorrow|yesterday", value.event_date_text, re.IGNORECASE):
        value.event_date = None
    elif value.event_date and value.event_date.isoformat() not in source_text:
        value.event_date = None
        value.ambiguities.append("Normalized date could not be verified from input.")
        value.needs_user_confirmation = True
    value.people = [item for item in _clean_list(value.people) if item.casefold() in source_text.casefold()]
    value.organizations = [item for item in _clean_list(value.organizations) if item.casefold() in source_text.casefold()]
    value.places = [item for item in _clean_list(value.places) if item.casefold() in source_text.casefold()]
    value.keywords = [item for item in _clean_list(value.keywords) if item.casefold() in source_text.casefold()]
    value.ambiguities = _clean_list(value.ambiguities)
    value.search_queries_bn = [query for query in _clean_list(value.search_queries_bn, max_queries) if _overlaps(query, value.claim)]
    value.search_queries_en = [query for query in _clean_list(value.search_queries_en, max_queries) if _overlaps(query, value.claim)]
    return value


def manual_extraction(ocr_text: str, claim_override: str | None = None) -> ClaimExtraction:
    claim = (claim_override or ocr_text).strip()
    return ClaimExtraction(
        claim=claim or None,
        claimed_source=_visible_publisher(ocr_text),
        search_queries_bn=[claim] if claim else [],
        needs_user_confirmation=claim_override is None,
        ambiguities=["Confirm or edit the main claim before searching."] if claim_override is None else [],
    )


def extract_claim(ocr_text: str, caption: str | None, settings: Settings, claim_override: str | None = None) -> ExtractionOutcome:
    if claim_override is not None:
        return ExtractionOutcome(extraction=manual_extraction(ocr_text, claim_override), method="manual")
    if not settings.gemini_enabled or not settings.gemini_api_key:
        return ExtractionOutcome(extraction=manual_extraction(ocr_text), method="manual_fallback")

    source_text = f"{ocr_text}\n{caption or ''}".strip()
    attempts: list[ProviderAttempt] = []
    for model in dict.fromkeys([settings.gemini_model, settings.gemini_fallback_model]):
        if not model:
            continue
        access, events = _post_with_retry(model, settings, 'Return {"ok": true}.', ACCESS_SCHEMA, "access_check")
        attempts.extend(events)
        event = events[-1]
        if access is None:
            continue
        try:
            if json.loads(access) != {"ok": True}:
                raise ValueError("Invalid access check")
        except (json.JSONDecodeError, ValueError):
            event.success = False
            event.error_code = "INVALID_OUTPUT"
            continue
        prompt = f"{PROMPT}\nOCR TEXT:\n{ocr_text}\nUSER CAPTION:\n{caption or ''}"
        for repair in (False, True):
            current_prompt = prompt if not repair else f"{prompt}\nYour previous output was invalid. Return only valid JSON matching the schema, using only the input text."
            output, events = _post_with_retry(model, settings, current_prompt, EXTRACTION_SCHEMA, "extract_claim_repair" if repair else "extract_claim")
            attempts.extend(events)
            event = events[-1]
            if output is None:
                break
            try:
                extraction = validate_extraction(output, source_text, settings.max_search_queries)
                return ExtractionOutcome(extraction=extraction, method=model, attempts=attempts)
            except (json.JSONDecodeError, ValidationError, ValueError):
                event.success = False
                event.error_code = "INVALID_OUTPUT"
    return ExtractionOutcome(extraction=manual_extraction(ocr_text), method="manual_fallback", attempts=attempts)
