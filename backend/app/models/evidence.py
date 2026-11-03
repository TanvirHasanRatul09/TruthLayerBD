from datetime import datetime

from sqlmodel import Field, SQLModel


class Evidence(SQLModel, table=True):
    __tablename__ = "evidence"

    id: str = Field(primary_key=True)
    analysis_id: str = Field(foreign_key="analyses.id", index=True)
    url: str
    canonical_url: str
    title: str
    domain: str
    source_type: str
    source_rank: int
    snippet: str
    published_at: datetime | None = None
    retrieved_at: datetime
    query: str


class RetrievalRun(SQLModel, table=True):
    __tablename__ = "retrieval_runs"

    analysis_id: str = Field(primary_key=True, foreign_key="analyses.id")
    status: str
    query_count: int
    successful_queries: int
    retrieved_at: datetime
    limitation: str | None = None


class ComparisonRecord(SQLModel, table=True):
    __tablename__ = "comparisons"

    evidence_id: str = Field(primary_key=True, foreign_key="evidence.id")
    analysis_id: str = Field(foreign_key="analyses.id", index=True)
    stance: str
    relevance: float
    reason: str
    quote: str | None = None
    method: str


class VerificationRecord(SQLModel, table=True):
    __tablename__ = "verifications"

    analysis_id: str = Field(primary_key=True, foreign_key="analyses.id")
    data_json: str
