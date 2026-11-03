from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class DatasetEntry(BaseModel):
    dataset_id: str = Field(pattern=r"^[a-z0-9_-]{1,60}$")
    record_id: str = Field(min_length=1, max_length=120)
    claim_text: str | None = Field(default=None, max_length=1000)
    original_label: str | None = Field(default=None, max_length=120)
    source_url: HttpUrl
    license: str = Field(min_length=1, max_length=120)
    attribution: str = Field(min_length=1, max_length=240)
    image_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    original_event_date: str | None = None
    original_location: str | None = None
    provenance_url: HttpUrl | None = None
    provenance_reviewed: bool = False


class DatasetMatchRead(BaseModel):
    dataset_id: str
    record_id: str
    match_type: Literal["related_claim", "exact_image"]
    similarity: float
    claim_text: str | None
    original_label: str | None
    source_url: str
    license: str
    attribution: str
    original_event_date: str | None
    original_location: str | None
    provenance_url: str | None
    matched_at: datetime
