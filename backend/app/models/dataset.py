from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.analysis import utc_now


class DatasetMatch(SQLModel, table=True):
    __tablename__ = "dataset_matches"

    id: str = Field(primary_key=True)
    analysis_id: str = Field(foreign_key="analyses.id", index=True)
    dataset_id: str
    record_id: str
    match_type: str
    similarity: float
    claim_text: str | None = None
    original_label: str | None = None
    source_url: str
    license: str
    attribution: str
    original_event_date: str | None = None
    original_location: str | None = None
    provenance_url: str | None = None
    matched_at: datetime = Field(default_factory=utc_now)
