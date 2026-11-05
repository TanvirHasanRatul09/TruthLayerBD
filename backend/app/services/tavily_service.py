import hashlib
import ipaddress
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.core.config import Settings
from app.schemas.providers import ClaimExtraction, ProviderAttempt

API_URL = "https://api.tavily.com/search"
PUBLISHER_DOMAINS = {
    "jamuna tv": "jamuna.tv",
    "যমুনা টিভি": "jamuna.tv",
    "প্রথম আলো": "prothomalo.com",
    "prothom alo": "prothomalo.com",
    "the daily star": "thedailystar.net",
    "bdnews24.com": "bdnews24.com",
    "dhaka tribune": "dhakatribune.com",
}
FACT_CHECK_DOMAINS = {"rumorscanner.com", "factcheck.org"}
NEWS_DOMAINS = {"thedailystar.net", "prothomalo.com", "bdnews24.com", "dhakatribune.com"}
TRACKING_PARAMETERS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
TOPIC_AUTHORITIES = (
    ("toureiffel.paris", ("eiffel tower", "tour eiffel", "আইফেল টাওয়ার", "আইফেল টাওয়ার")),
    ("who.int", ("who", "world health organization", "বিশ্ব স্বাস্থ্য সংস্থা", "covid-19", "কোভিড")),
    ("un.org", ("united nations", "জাতিসংঘ", "un membership")),
    ("ugc.gov.bd", ("বিশ্ববিদ্যালয়", "বিশ্ববিদ্যালয়", "university", "universities")),
    ("berc.org.bd", ("এলপিজি", "গ্যাস", "lpg", "gas", "জ্বালানি", "energy")),
    ("unesco.org", ("unesco", "world heritage", "বিশ্ব ঐতিহ্য")),
    ("nasa.gov", ("apollo 11", "moon landing", "চন্দ্রাভিযান")),
)


@dataclass
class EvidenceItem:
    evidence_id: str
    url: str
    canonical_url: str
    title: str
    domain: str
    source_type: str
    source_rank: int
    snippet: str
    published_at: datetime | None
    retrieved_at: datetime
    query: str


@dataclass
class RetrievalOutcome:
    items: list[EvidenceItem] = field(default_factory=list)
    status: str = "unavailable"
    query_count: int = 0
    successful_queries: int = 0
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    limitation: str | None = None
    attempts: list[ProviderAttempt] = field(default_factory=list)


def _clean(value: str, limit: int) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit]


def _domain_matches(domain: str, expected: str) -> bool:
    return domain == expected or domain.endswith("." + expected)


def canonicalize_url(url: str) -> tuple[str, str] | None:
    try:
        parsed = urlsplit(url.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        domain = parsed.hostname.lower().removeprefix("www.")
        if not re.fullmatch(r"[a-z0-9.-]+", domain) or ".." in domain or "." not in domain:
            return None
        try:
            ipaddress.ip_address(domain)
            return None
        except ValueError:
            pass
        path = parsed.path.rstrip("/") or "/"
        query = urlencode(sorted((key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS))
        canonical = urlunsplit(("https", domain, path, query, ""))
        return canonical, domain
    except ValueError:
        return None


def _official_domain(claim: str) -> str | None:
    folded = claim.casefold()
    return next((domain for domain, terms in TOPIC_AUTHORITIES if any(term in folded for term in terms)), None)


def _source_type(domain: str, claimed_source: str | None, claim: str = "") -> tuple[str, int]:
    authority = _official_domain(claim)
    if authority and _domain_matches(domain, authority):
        return "official_authority", 0
    claimed_domain = PUBLISHER_DOMAINS.get((claimed_source or "").casefold().strip())
    if claimed_domain and _domain_matches(domain, claimed_domain):
        return "claimed_publisher", 1
    if any(_domain_matches(domain, known) for known in FACT_CHECK_DOMAINS):
        return "fact_check", 2
    if any(_domain_matches(domain, known) for known in NEWS_DOMAINS):
        return "independent_news", 3
    if domain.endswith(".gov.bd") or domain.endswith(".gov"):
        return "government_site", 4
    return "other", 4


def _published_at(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


_STOPWORDS = {"সব", "আজ", "কাল", "নতুন", "বাংলাদেশ", "the", "and", "for", "from", "about", "news", "latest", "today"}


def _tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFC", text).casefold()
    # Python's \w splits Bengali vowel signs and virama from their letters.
    words = []
    current = []
    for char in normalized:
        if unicodedata.category(char)[0] in {"L", "M", "N"}:
            current.append(char)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    tokens = set()
    for word in words:
        if len(word) < 3 or word in _STOPWORDS:
            continue
        if re.search(r"[\u0980-\u09ff]", word):
            for suffix in ("দের", "গুলো", "ের", "য়", "য়"):
                if word.endswith(suffix) and len(word) > len(suffix) + 3:
                    word = word[:-len(suffix)]
                    break
        tokens.add(word)
    return tokens


def is_relevant_result(title: str, snippet: str, extraction: ClaimExtraction, url: str = "") -> bool:
    """Require several claim-specific terms, never a single place or topic word."""
    result = _tokens(f"{title} {snippet}")
    claim_text = (extraction.claim or "").casefold()
    result_text = f"{title} {snippet}".casefold()
    title_text = title.casefold()
    # A source about another named person is not evidence for a person-specific
    # claim merely because the surrounding event words overlap.
    if extraction.people and not any(person.casefold() in result_text for person in extraction.people):
        return False
    # A similarly named structure or a replica is a different subject, even
    # when the search snippet repeats every location word in the claim.
    if "eiffel tower" in claim_text and re.search(r"\b(?:replica|replicas|copies|reproductions|miniature|little eiffel tower|own eiffel tower|tv tower|fernsehturm|funkturm)\b", result_text):
        return False
    if "apollo 11" in claim_text and re.search(r"\bapollo\s+(?!11\b)\d+\b", title_text) and "apollo 11" not in title_text:
        return False
    if "sundarbans" in claim_text and ("bangladesh" in claim_text or "বাংলাদেশ" in claim_text):
        if re.search(r"/en/list/452(?:/|$)", urlsplit(url).path, re.I) or "sundarbans national park" in title_text:
            return False
    # The two UNESCO Sundarbans sites have different countries and listing years.
    # A result about only the other country cannot support the named site.
    countries = (("bangladesh", "বাংলাদেশ"), ("india", "ভারত"))
    named = [index for index, names in enumerate(countries) if any(name in claim_text for name in names)]
    if len(named) == 1:
        expected = named[0]
        other = 1 - expected
        if any(name in result_text for name in countries[other]) and not any(name in result_text for name in countries[expected]):
            return False
    variants = [extraction.claim or ""] + extraction.search_queries_en[:1]
    for variant in variants:
        claim = _tokens(variant)
        if len(claim) < 2:
            continue
        overlap = len(claim & result)
        required = max(2, min(4, (len(claim) + 2) // 3))
        if overlap >= required and overlap / len(claim) >= 0.35:
            return True
    return False


def generate_queries(extraction: ClaimExtraction, settings: Settings) -> list[str]:
    claim = _clean(extraction.claim or "", 180)
    if not claim:
        return []
    official_domain = _official_domain(claim)
    candidates = [claim]
    # Search the subject independently of a possibly false location. Searching
    # only the complete claim often returns pages about a similarly named
    # object in the claimed place instead of the actual subject.
    location_claim = re.fullmatch(r"(?:the\s+)?(.+?)\s+(?:is|stands|lies|is located)\s+(?:in|at)\s+[\w .'-]+(?:,\s*[\w .'-]+)?\.?", claim, re.I)
    if location_claim and len(location_claim.group(1).split()) >= 2:
        candidates.append(f'"{location_claim.group(1).strip()}" location official')
    if official_domain:
        if official_domain == "toureiffel.paris":
            candidates.append("site:toureiffel.paris Eiffel Tower location")
        candidates.append(f"site:{official_domain} {claim}")
    claimed_domain = PUBLISHER_DOMAINS.get((extraction.claimed_source or "").casefold().strip())
    if claimed_domain:
        candidates.append(f"site:{claimed_domain} {claim}")
    elif extraction.claimed_source:
        candidates.append(f'"{extraction.claimed_source}" {claim}')
    candidates.extend(extraction.search_queries_bn[:1])
    candidates.extend(extraction.search_queries_en[:1])
    candidates.append(f"{claim} fact check")
    candidates.extend(extraction.search_queries_bn[1:] + extraction.search_queries_en[1:])
    seen: set[str] = set()
    queries: list[str] = []
    for candidate in candidates:
        query = _clean(candidate, 240)
        if query and query.casefold() not in seen:
            seen.add(query.casefold())
            queries.append(query)
        if len(queries) >= min(max(settings.max_search_queries, 1), 6):
            break
    return queries


def _search(query: str, settings: Settings) -> tuple[list[dict] | None, ProviderAttempt]:
    started = time.monotonic()
    try:
        with httpx.Client(timeout=settings.tavily_timeout_seconds) as client:
            response = client.post(
                API_URL,
                headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
                json={
                    "query": query,
                    "search_depth": "basic",
                    "max_results": min(max(settings.tavily_max_results, 1), 5),
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_published_date": True,
                },
            )
        elapsed = round((time.monotonic() - started) * 1000)
        if response.status_code != 200:
            error_code = "RATE_LIMITED" if response.status_code in {429, 432, 433} else "ACCESS_DENIED" if response.status_code in {401, 403} else "SERVER_ERROR" if response.status_code >= 500 else "BAD_REQUEST"
            return None, ProviderAttempt(provider="tavily", operation="search", success=False, status_code=response.status_code, latency_ms=elapsed, error_code=error_code)
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ValueError("Invalid search response")
        return data["results"], ProviderAttempt(provider="tavily", operation="search", success=True, status_code=200, latency_ms=elapsed)
    except httpx.TimeoutException:
        return None, ProviderAttempt(provider="tavily", operation="search", success=False, latency_ms=round((time.monotonic() - started) * 1000), error_code="TIMEOUT")
    except httpx.ConnectError:
        return None, ProviderAttempt(provider="tavily", operation="search", success=False, latency_ms=round((time.monotonic() - started) * 1000), error_code="NETWORK_ERROR")
    except (httpx.HTTPError, ValueError, TypeError):
        return None, ProviderAttempt(provider="tavily", operation="search", success=False, latency_ms=round((time.monotonic() - started) * 1000), error_code="BAD_RESPONSE")


def _copy_key(item: EvidenceItem) -> str | None:
    normalized = re.sub(r"\W+", "", (item.title + item.snippet).casefold())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if len(normalized) >= 40 else None


def retrieve(extraction: ClaimExtraction, analysis_id: str, settings: Settings) -> RetrievalOutcome:
    outcome = RetrievalOutcome()
    if not settings.tavily_enabled or not settings.tavily_api_key:
        outcome.limitation = "Live web retrieval is unavailable because Tavily is not configured."
        return outcome
    queries = generate_queries(extraction, settings)
    if not queries:
        outcome.limitation = "No confirmed claim was available for search."
        return outcome
    by_url: dict[str, EvidenceItem] = {}
    by_copy: dict[str, EvidenceItem] = {}
    for query in queries:
        outcome.query_count += 1
        results, attempt = _search(query, settings)
        outcome.attempts.append(attempt)
        if results is None:
            if attempt.error_code in {"RATE_LIMITED", "ACCESS_DENIED", "TIMEOUT", "SERVER_ERROR", "NETWORK_ERROR"}:
                break
            continue
        outcome.successful_queries += 1
        for raw in results[: min(max(settings.tavily_max_results, 1), 5)]:
            if not isinstance(raw, dict):
                continue
            url = raw.get("url")
            if not isinstance(url, str):
                continue
            parsed = canonicalize_url(url)
            if parsed is None:
                continue
            canonical, domain = parsed
            title = _clean(str(raw.get("title") or ""), 300)
            snippet = _clean(str(raw.get("content") or ""), 1200)
            if not title and not snippet:
                continue
            if not is_relevant_result(title, snippet, extraction, url):
                continue
            source_type, rank = _source_type(domain, extraction.claimed_source, extraction.claim or "")
            item = EvidenceItem(
                evidence_id="ev_" + hashlib.sha256(f"{analysis_id}:{canonical}".encode()).hexdigest()[:20],
                url=url,
                canonical_url=canonical,
                title=title,
                domain=domain,
                source_type=source_type,
                source_rank=rank,
                snippet=snippet,
                published_at=_published_at(raw.get("published_date")),
                retrieved_at=outcome.retrieved_at,
                query=query,
            )
            existing = by_url.get(canonical)
            if existing:
                if len(item.snippet) > len(existing.snippet):
                    existing.snippet = item.snippet
                if existing.published_at is None:
                    existing.published_at = item.published_at
                continue
            copy_key = _copy_key(item)
            previous = by_copy.get(copy_key) if copy_key else None
            if previous:
                if item.source_rank < previous.source_rank:
                    by_url.pop(previous.canonical_url, None)
                    by_url[canonical] = item
                    by_copy[copy_key] = item
                continue
            by_url[canonical] = item
            if copy_key:
                by_copy[copy_key] = item
    outcome.items = sorted(by_url.values(), key=lambda item: (item.source_rank, item.domain, item.canonical_url))
    if outcome.successful_queries == 0:
        outcome.status = "unavailable"
        outcome.limitation = "Live web retrieval failed; no current evidence was obtained."
    elif outcome.successful_queries < outcome.query_count:
        outcome.status = "partial"
        outcome.limitation = "Some live searches failed; results may be incomplete."
    elif not outcome.items:
        outcome.status = "no_results"
        outcome.limitation = "No relevant search results were returned; absence is not proof."
    else:
        outcome.status = "completed"
    return outcome
