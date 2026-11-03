from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Analysis(SQLModel, table=True):
    __tablename__ = "analyses"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    status: str = Field(default="awaiting_confirmation", index=True)
    image_path: str
    image_sha256: str
    caption: str | None = None


class ProviderEvent(SQLModel, table=True):
    __tablename__ = "provider_events"

    id: int | None = Field(default=None, primary_key=True)
    analysis_id: str = Field(foreign_key="analyses.id", index=True)
    provider: str
    operation: str
    occurred_at: datetime = Field(default_factory=utc_now)
    success: bool
    status_code: int | None = None
    latency_ms: int | None = None
    error_code: str | None = None


class OcrRecord(SQLModel, table=True):
    __tablename__ = "ocr_records"

    analysis_id: str = Field(primary_key=True, foreign_key="analyses.id")
    text: str = ""
    confidence: float | None = None
    raw_result_json: str = "[]"
    needs_confirmation: bool = True
    confirmed_at: datetime | None = None
    error_code: str | None = None


class ExtractionRecord(SQLModel, table=True):
    __tablename__ = "extraction_records"

    analysis_id: str = Field(primary_key=True, foreign_key="analyses.id")
    data_json: str
    method: str
