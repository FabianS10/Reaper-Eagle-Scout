from typing import Optional
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    country: Optional[str] = None
    sector: Optional[str] = None
    max_results: int = Field(20, ge=1, le=50)
    include_competitors: bool = False
    min_score: float = Field(0.0, ge=0, le=100)


class SearchJobOut(BaseModel):
    job_id: str
    status: str
    progress_pct: int
    query: str
    urls_discovered: int
    urls_fetched: int
    urls_parsed: int
    opportunities_extracted: int
    opportunities_scored: int
    error_message: Optional[str]
    duration_seconds: Optional[float]

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, job) -> "SearchJobOut":
        return cls(
            job_id=job.id,
            status=job.status,
            progress_pct=job.progress_pct,
            query=job.query,
            urls_discovered=job.urls_discovered or 0,
            urls_fetched=job.urls_fetched or 0,
            urls_parsed=job.urls_parsed or 0,
            opportunities_extracted=job.opportunities_extracted or 0,
            opportunities_scored=job.opportunities_scored or 0,
            error_message=job.error_message,
            duration_seconds=job.duration_seconds,
        )


class DashboardSummary(BaseModel):
    total_opportunities: int
    high_priority_count: int       # score >= 80
    closing_soon_count: int        # deadline <= 14 days
    avg_confidence: float
    total_pipeline_value_usd: float
    sources_scanned: int
    by_sector: dict[str, int]
    by_country: dict[str, int]
    by_type: dict[str, int]
    urgency_map: dict[str, int]    # critical / hot / open
