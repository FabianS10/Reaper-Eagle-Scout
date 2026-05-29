import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, JSON, Float
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class SearchJob(Base):
    __tablename__ = "search_jobs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    query = Column(Text, nullable=False)
    country = Column(String(100), nullable=True)
    sector = Column(String(100), nullable=True)
    max_results = Column(Integer, default=20)

    # Pipeline state
    status = Column(String(30), default="pending")
    # pending | running | discovery | fetching | parsing | extracting | scoring | complete | failed

    # Progress counters
    urls_discovered = Column(Integer, default=0)
    urls_fetched = Column(Integer, default=0)
    urls_parsed = Column(Integer, default=0)
    opportunities_extracted = Column(Integer, default=0)
    opportunities_scored = Column(Integer, default=0)

    # Results
    result_ids = Column(JSON, nullable=True)   # list of opportunity IDs
    error_message = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def progress_pct(self) -> int:
        stages = {
            "pending": 0,
            "running": 5,
            "discovery": 15,
            "fetching": 35,
            "parsing": 55,
            "extracting": 75,
            "scoring": 90,
            "complete": 100,
            "failed": 0,
        }
        return stages.get(self.status, 0)
