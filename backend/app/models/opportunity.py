import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Date, DateTime, Integer,
    Text, Boolean, JSON, Numeric
)
from sqlalchemy.dialects.sqlite import TEXT
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    job_id = Column(String(36), nullable=True, index=True)

    # Core identity
    title = Column(Text, nullable=True)
    source_url = Column(Text, unique=True, nullable=False)
    organization = Column(Text, nullable=True)
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    sector = Column(String(100), nullable=True)
    opportunity_type = Column(String(50), nullable=True)  # public_tender, private_rfp, grant, etc.

    # Financials
    budget_amount = Column(Numeric(20, 2), nullable=True)
    budget_currency = Column(String(10), nullable=True)

    # Dates
    deadline = Column(Date, nullable=True)
    publication_date = Column(Date, nullable=True)

    # Content
    summary = Column(Text, nullable=True)
    requirements = Column(JSON, nullable=True)     # list[str]
    eligibility = Column(JSON, nullable=True)      # list[str]
    documents = Column(JSON, nullable=True)        # list[str]
    contact_email = Column(String(255), nullable=True)
    evidence_snippets = Column(JSON, nullable=True)  # list[str]

    # Scores (0–100)
    relevance_score = Column(Float, nullable=True)
    urgency_score = Column(Float, nullable=True)
    strategic_fit_score = Column(Float, nullable=True)
    evidence_confidence_score = Column(Float, nullable=True)
    value_score = Column(Float, nullable=True)
    final_score = Column(Float, nullable=True)

    # Source reliability
    source_reliability = Column(Float, nullable=True)
    extraction_confidence = Column(Float, nullable=True)

    # Raw parser output
    raw_text_length = Column(Integer, nullable=True)
    content_type = Column(String(50), nullable=True)  # html, pdf, json

    # State
    is_bookmarked = Column(Boolean, default=False)
    response_initiated = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def why_score(self) -> str:
        """Generate a plain-language score explanation."""
        parts = []
        if self.final_score:
            parts.append(f"Final score {int(self.final_score)}/100.")
        if self.relevance_score and self.relevance_score >= 80:
            parts.append("Strong keyword and sector relevance.")
        if self.deadline:
            from datetime import date
            days = (self.deadline - date.today()).days
            if 0 < days <= 14:
                parts.append(f"Deadline in {days} days — high urgency.")
            elif days > 14:
                parts.append(f"Deadline in {days} days — actionable window.")
        if self.source_reliability and self.source_reliability >= 90:
            parts.append("Verified official source.")
        if self.budget_amount:
            parts.append(f"Confirmed budget {self.budget_currency} {self.budget_amount:,.0f}.")
        if self.extraction_confidence and self.extraction_confidence >= 0.85:
            parts.append("High AI extraction confidence.")
        return " ".join(parts) or "Scored based on available signals."
