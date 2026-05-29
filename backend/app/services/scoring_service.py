"""
Scoring service.
Computes five component scores and combines them into a final 0–100 score.

Final Score = 0.30 × Relevance
            + 0.25 × Urgency
            + 0.20 × Strategic Fit
            + 0.15 × Evidence Confidence
            + 0.10 × Budget/Value
"""
from __future__ import annotations
import logging
from datetime import date, datetime
from dataclasses import dataclass
from typing import Optional
from app.schemas.opportunity_schema import OpportunityExtract

logger = logging.getLogger(__name__)

# Scoring weights
W_RELEVANCE = 0.30
W_URGENCY   = 0.25
W_FIT       = 0.20
W_EVIDENCE  = 0.15
W_VALUE     = 0.10

# Target sectors for this deployment
TARGET_SECTORS = {
    "AI", "Machine Learning", "Data Analytics", "Software",
    "Healthcare", "Traffic", "Cybersecurity", "Cloud", "Automation",
}

TARGET_COUNTRIES = {"Colombia", "Mexico", "Peru", "Chile", "Brazil", "Argentina"}

# Budget value tiers (USD equivalent)
VALUE_TIERS = [
    (10_000_000, 100),
    (5_000_000,   90),
    (1_000_000,   78),
    (500_000,     65),
    (100_000,     50),
    (0,           30),
]

# Approximate exchange rates to USD
FX_TO_USD = {
    "COP": 1 / 4200,
    "MXN": 1 / 17,
    "PEN": 1 / 3.7,
    "CLP": 1 / 900,
    "ARS": 1 / 1000,
    "BRL": 1 / 5.1,
    "USD": 1.0,
    "EUR": 1.08,
}


@dataclass
class ScoreBreakdown:
    relevance: float
    urgency: float
    strategic_fit: float
    evidence_confidence: float
    value: float
    final: float


def score_relevance(
    extract: OpportunityExtract,
    user_query: str,
    domain_trust: float = 0.5,
) -> float:
    """
    Measures how well the opportunity matches what the user is looking for.
    Factors: keyword overlap, sector match, country match, opportunity type.
    """
    score = 0.0
    text = " ".join([
        extract.title or "",
        extract.summary or "",
        extract.sector or "",
        " ".join(extract.requirements),
    ]).lower()

    query_words = set(w.lower() for w in user_query.split() if len(w) > 3)
    text_words = set(text.split())
    overlap = len(query_words & text_words) / max(len(query_words), 1)
    score += overlap * 35  # up to 35 pts

    # Sector match
    sector = (extract.sector or "").strip()
    if sector in TARGET_SECTORS:
        score += 25
    elif any(s.lower() in text for s in TARGET_SECTORS):
        score += 12

    # Country match
    country = extract.country or ""
    if country in TARGET_COUNTRIES:
        score += 20
    elif any(c.lower() in text for c in TARGET_COUNTRIES):
        score += 8

    # Official source bonus
    score += domain_trust * 20  # up to 20 pts

    return min(score, 100.0)


def score_urgency(deadline: Optional[date]) -> float:
    """
    Time pressure score.
    Peak window: 4–30 days out.
    Extreme urgency (<= 3 days) is risky, not ideal.
    """
    if deadline is None:
        return 35.0  # unknown deadline — moderate uncertainty penalty

    today = date.today()
    days_remaining = (deadline - today).days

    if days_remaining < 0:
        return 0.0   # already closed
    if days_remaining == 0:
        return 5.0   # closes today — too late to act
    if days_remaining <= 3:
        return 40.0  # risky urgency
    if days_remaining <= 7:
        return 80.0  # high urgency
    if days_remaining <= 14:
        return 90.0  # ideal urgency window
    if days_remaining <= 30:
        return 75.0
    if days_remaining <= 60:
        return 55.0
    return 30.0      # far out — low time pressure


def score_strategic_fit(extract: OpportunityExtract) -> float:
    """
    How well this opportunity fits the deployer's capabilities.
    Checks for tech stack alignment, company size signals, requirements realism.
    """
    score = 0.0
    text = " ".join([
        extract.summary or "",
        extract.sector or "",
        " ".join(extract.requirements),
        " ".join(extract.eligibility),
    ]).lower()

    # High-fit keywords
    high_fit_terms = [
        "inteligencia artificial", "machine learning", "python", "tensorflow",
        "pytorch", "data analytics", "tableau", "powerbi", "sql",
        "react", "fastapi", "api rest", "microservicios", "cloud",
        "aws", "gcp", "azure", "visión por computador", "nlp",
        "startup", "empresa de tecnología", "pyme", "pequeña empresa",
        "ai", "software development", "data science",
    ]
    for term in high_fit_terms:
        if term in text:
            score += 5
            if score >= 60:
                break

    # Penalty for heavy-cert requirements
    heavy_requirements = ["iso 27001", "cmmi", "experiencia 10 años", "10 years experience"]
    for req in heavy_requirements:
        if req in text:
            score -= 10

    # Bonus for LATAM expansion signals
    if any(c.lower() in text for c in ["latam", "latin america", "escalabilidad"]):
        score += 15

    # Opportunity type fit
    fit_types = {"public_tender": 20, "grant": 25, "private_rfp": 15}
    score += fit_types.get(extract.opportunity_type, 5)

    return max(0.0, min(score, 100.0))


def score_evidence_confidence(
    extract: OpportunityExtract,
    parse_confidence: float = 0.5,
    domain_trust: float = 0.5,
) -> float:
    """
    How much we trust that this data is real and complete.
    Based on field completeness, source quality, parser confidence.
    """
    score = 0.0

    # Field completeness
    fields = {
        "title": extract.title,
        "organization": extract.organization,
        "deadline": extract.deadline,
        "budget_amount": extract.budget_amount,
        "requirements": extract.requirements,
        "evidence_snippets": extract.evidence_snippets,
        "contact_email": extract.contact_email,
    }
    filled = sum(1 for v in fields.values() if v)
    score += (filled / len(fields)) * 35

    # Parser quality
    score += parse_confidence * 20

    # Source trust
    score += domain_trust * 25

    # LLM extraction confidence
    score += extract.extraction_confidence * 20

    return min(score, 100.0)


def score_value(extract: OpportunityExtract) -> float:
    """
    Contract/opportunity size score.
    Converts any currency to USD equivalent for fair comparison.
    """
    if not extract.budget_amount:
        return 30.0  # no budget info — neutral-low

    fx_rate = FX_TO_USD.get(extract.budget_currency or "USD", 1.0)
    usd_value = extract.budget_amount * fx_rate

    for threshold, score in VALUE_TIERS:
        if usd_value >= threshold:
            return float(score)

    return 20.0


def compute_scores(
    extract: OpportunityExtract,
    user_query: str = "",
    domain_trust: float = 0.5,
    parse_confidence: float = 0.5,
) -> ScoreBreakdown:
    """
    Run all five scorers and compute the weighted final score.
    All component scores are 0–100. Final is 0–100.
    """
    rel = score_relevance(extract, user_query, domain_trust)
    urg = score_urgency(extract.deadline)
    fit = score_strategic_fit(extract)
    ev  = score_evidence_confidence(extract, parse_confidence, domain_trust)
    val = score_value(extract)

    final = (
        rel * W_RELEVANCE
        + urg * W_URGENCY
        + fit * W_FIT
        + ev  * W_EVIDENCE
        + val * W_VALUE
    )

    return ScoreBreakdown(
        relevance=round(rel, 1),
        urgency=round(urg, 1),
        strategic_fit=round(fit, 1),
        evidence_confidence=round(ev, 1),
        value=round(val, 1),
        final=round(final, 1),
    )
