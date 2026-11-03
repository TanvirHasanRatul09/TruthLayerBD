from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClaimExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str | None = None
    claimed_source: str | None = None
    people: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    event_date_text: str | None = None
    event_date: date | None = None
    keywords: list[str] = Field(default_factory=list)
    search_queries_bn: list[str] = Field(default_factory=list)
    search_queries_en: list[str] = Field(default_factory=list)
    needs_user_confirmation: bool = False
    ambiguities: list[str] = Field(default_factory=list)


class ProviderAttempt(BaseModel):
    provider: str = "gemini"
    operation: str
    success: bool
    status_code: int | None = None
    latency_ms: int | None = None
    error_code: str | None = None


class ExtractionOutcome(BaseModel):
    extraction: ClaimExtraction
    method: str
    attempts: list[ProviderAttempt] = Field(default_factory=list)


class EvidenceRead(BaseModel):
    evidence_id: str
    url: str
    canonical_url: str
    title: str
    domain: str
    source_type: str
    snippet: str
    published_at: datetime | None
    retrieved_at: datetime
    query: str
    stance: str | None = None
    relevance: float | None = None
    reason: str | None = None
    quote: str | None = None


Stance = Literal["supports", "contradicts", "mentions_but_unclear", "unrelated", "insufficient_content"]


class EvidenceComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    stance: Stance
    relevance: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=400)
    quote: str | None = Field(default=None, max_length=300)
    method: str = "gemini"


class ComparisonOutcome(BaseModel):
    comparisons: list[EvidenceComparison] = Field(default_factory=list)
    method: str
    attempts: list[ProviderAttempt] = Field(default_factory=list)
    fallbacks_used: list[str] = Field(default_factory=list)


class RetrievalRead(BaseModel):
    status: str
    query_count: int
    successful_queries: int
    retrieved_at: datetime
    limitation: str | None = None
