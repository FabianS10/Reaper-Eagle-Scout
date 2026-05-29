from __future__ import annotations
from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, HttpUrl


# ── What the LLM must return ──────────────────────────────────────────────────

class OpportunityExtract(BaseModel):
    """Structured output from the LLM extraction pass."""
    title: Optional[str] = None
    organization: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    sector: Optional[str] = None
    opportunity_type: Literal[
        "public_tender",
        "private_rfp",
        "grant",
        "accelerator",
        "competitor_signal",
        "market_signal",
        "unknown",
    ] = "unknown"
    budget_amount: Optional[float] = None
    budget_currency: Optional[str] = None
    deadline: Optional[date] = None
    publication_date: Optional[date] = None
    requirements: list[str] = Field(default_factory=list)
    eligibility: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    contact_email: Optional[str] = None
    summary: str = ""
    evidence_snippets: list[str] = Field(default_factory=list)
    extraction_confidence: float = Field(0.5, ge=0.0, le=1.0)


# ── API response shapes ────────────────────────────────────────────────────────

class OpportunityScores(BaseModel):
    relevance: float
    urgency: float
    strategic_fit: float
    evidence_confidence: float
    value: float
    final: float


class OpportunityOut(BaseModel):
    id: str
    title: Optional[str]
    source_url: str
    organization: Optional[str]
    country: Optional[str]
    city: Optional[str]
    sector: Optional[str]
    opportunity_type: Optional[str]
    budget_amount: Optional[float]
    budget_currency: Optional[str]
    deadline: Optional[date]
    publication_date: Optional[date]
    summary: Optional[str]
    requirements: Optional[list[str]]
    eligibility: Optional[list[str]]
    evidence_snippets: Optional[list[str]]
    contact_email: Optional[str]
    scores: OpportunityScores
    source_reliability: Optional[float]
    extraction_confidence: Optional[float]
    why_score: str
    is_bookmarked: bool
    response_initiated: bool
    created_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_scores(cls, opp) -> "OpportunityOut":
        return cls(
            id=opp.id,
            title=opp.title,
            source_url=opp.source_url,
            organization=opp.organization,
            country=opp.country,
            city=opp.city,
            sector=opp.sector,
            opportunity_type=opp.opportunity_type,
            budget_amount=float(opp.budget_amount) if opp.budget_amount else None,
            budget_currency=opp.budget_currency,
            deadline=opp.deadline,
            publication_date=opp.publication_date,
            summary=opp.summary,
            requirements=opp.requirements or [],
            eligibility=opp.eligibility or [],
            evidence_snippets=opp.evidence_snippets or [],
            contact_email=opp.contact_email,
            scores=OpportunityScores(
                relevance=opp.relevance_score or 0,
                urgency=opp.urgency_score or 0,
                strategic_fit=opp.strategic_fit_score or 0,
                evidence_confidence=opp.evidence_confidence_score or 0,
                value=opp.value_score or 0,
                final=opp.final_score or 0,
            ),
            source_reliability=opp.source_reliability,
            extraction_confidence=opp.extraction_confidence,
            why_score=opp.why_score(),
            is_bookmarked=opp.is_bookmarked or False,
            response_initiated=opp.response_initiated or False,
            created_at=opp.created_at,
        )


class OpportunityListOut(BaseModel):
    items: list[OpportunityOut]
    total: int
    page: int
    page_size: int
