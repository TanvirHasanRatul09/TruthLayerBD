"""Conservative matching of locally curated claim and image records."""
import json
import re
import unicodedata
from hashlib import sha256
from pathlib import Path

from app.models.dataset import DatasetMatch
from app.schemas.dataset import DatasetEntry


def _tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return set(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE))


def similarity(left: str, right: str) -> float:
    first, second = _tokens(left), _tokens(right)
    if len(first) < 4 or len(second) < 4:
        return 0.0
    return len(first & second) / len(first | second)


def load_entries(directory: str) -> list[DatasetEntry]:
    root = Path(directory)
    if not root.is_dir():
        return []
    entries: list[DatasetEntry] = []
    for path in sorted(root.glob("*.jsonl")):
        if path.stat().st_size > 5_000_000:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = DatasetEntry.model_validate(json.loads(line))
            except (ValueError, TypeError):
                continue
            # Historical labels are display data; records without traceable sources are rejected by schema.
            entries.append(entry)
            if len(entries) >= 10_000:
                return entries
    return entries


def find_matches(analysis_id: str, claim: str | None, image_sha256: str, directory: str) -> list[DatasetMatch]:
    candidates: list[DatasetMatch] = []
    for entry in load_entries(directory):
        exact_image = entry.image_sha256 == image_sha256 and entry.image_sha256 is not None
        score = similarity(claim, entry.claim_text) if claim and entry.claim_text else 0.0
        if not exact_image and score < 0.78:
            continue
        # An exact byte match is provenance only if a human reviewed the cited record.
        vetted = exact_image and entry.provenance_reviewed and entry.provenance_url is not None
        match_type = "exact_image" if exact_image else "related_claim"
        key = f"{analysis_id}|{entry.dataset_id}|{entry.record_id}|{match_type}"
        candidates.append(DatasetMatch(
            id="dm_" + sha256(key.encode()).hexdigest()[:24], analysis_id=analysis_id,
            dataset_id=entry.dataset_id, record_id=entry.record_id, match_type=match_type,
            similarity=1.0 if exact_image else round(score, 4), claim_text=entry.claim_text,
            original_label=entry.original_label, source_url=str(entry.source_url),
            license=entry.license, attribution=entry.attribution,
            original_event_date=entry.original_event_date if vetted else None,
            original_location=entry.original_location if vetted else None,
            provenance_url=str(entry.provenance_url) if vetted else None,
        ))
    candidates.sort(key=lambda item: (item.match_type != "exact_image", -item.similarity, item.dataset_id, item.record_id))
    return candidates[:10]
