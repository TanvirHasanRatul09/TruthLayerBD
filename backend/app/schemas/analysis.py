from typing import Literal
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.providers import ClaimExtraction, EvidenceRead, RetrievalRead, Stance
from app.schemas.dataset import DatasetMatchRead


class EvidenceReason(BaseModel):
    evidence_id: str
    url: str
    stance: Stance
    summary: str


class LayerRead(BaseModel):
    status: str
    summary: str


class CitedDetail(BaseModel):
    value: str
    evidence_id: str
    url: str


class EventDetails(BaseModel):
    what: CitedDetail | None = None
    when: CitedDetail | None = None
    where: CitedDetail | None = None
    reported_by: CitedDetail | None = None


class PublisherFinding(BaseModel):
    status: Literal["confirmed_published", "confirmed_misattributed", "unverified"] = "unverified"
    claimed_name: str | None = None
    scope: Literal["claim", "image"] | None = None
    evidence: CitedDetail | None = None


class VerificationRead(BaseModel):
    label: Literal["verified", "supported", "contradicted", "conflicting", "unverified", "insufficient_evidence"]
    flags: list[str] = Field(default_factory=list)
    evidence_coverage: Literal["low", "medium", "high"]
    summary: str
    reasons: list[EvidenceReason] = Field(default_factory=list)
    decision_method: str = "python_evidence_fusion_v1"
    comparison_method: str
    fallbacks_used: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    layers: dict[str, LayerRead]
    event_details: EventDetails = Field(default_factory=EventDetails)
    related_event: CitedDetail | None = None
    publisher: PublisherFinding = Field(default_factory=PublisherFinding)


class OcrRead(BaseModel):
    text: str
    confidence: float | None = None
    needs_confirmation: bool = True
    error_code: str | None = None


class OcrCorrection(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class RunRequest(BaseModel):
    claim: str | None = Field(default=None, max_length=1000)


class UploadResponse(BaseModel):
    analysis_id: str
    status: Literal["awaiting_confirmation"]
    image_url: str
    caption: str | None = None
    ocr: OcrRead


class AnalysisRead(BaseModel):
    analysis_id: str
    created_at: datetime
    status: Literal["processing", "awaiting_confirmation", "completed", "partial", "failed"]
    image_url: str
    caption: str | None = None
    ocr: OcrRead | None = None
    extraction: ClaimExtraction | None = None
    extraction_method: str | None = None
    retrieval: RetrievalRead | None = None
    evidence: list[EvidenceRead] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    verification: VerificationRead | None = None
    dataset_matches: list[DatasetMatchRead] = Field(default_factory=list)


class AnalysisPage(BaseModel):
    items: list[AnalysisRead]
    total: int
    limit: int
    offset: int
