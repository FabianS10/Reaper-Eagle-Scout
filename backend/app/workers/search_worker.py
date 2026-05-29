"""
Search worker.
Orchestrates the full pipeline for a single search job:
Discovery → Fetch → Parse → Extract → Score → Persist.

Runs as a FastAPI BackgroundTask.
Upgrade path: replace with Celery task for true async queue.
"""
import logging
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.job import SearchJob
from app.models.opportunity import Opportunity
from app.services.discovery_service import discover_candidates
from app.services.brightdata_unlocker import smart_fetch
from app.services.parser_service import parse_document
from app.services.extractor_service import (
    extract_opportunity,
    build_fallback_extract,
    enrich_extract_with_candidate,
)
from app.services.scoring_service import compute_scores
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _update_job(db: Session, job: SearchJob, **kwargs):
    """Flush job state changes to the database."""
    for key, val in kwargs.items():
        setattr(job, key, val)
    db.commit()


async def run_search_pipeline(job_id: str, db: Session):
    """
    Full pipeline for a search job.
    Tolerates partial failures — one bad URL should not abort the entire job.
    """
    job: SearchJob = db.query(SearchJob).filter(SearchJob.id == job_id).first()
    if not job:
        logger.error(f"Job {job_id} not found")
        return

    _update_job(db, job, status="running", started_at=datetime.utcnow())

    try:
        # ── 1. Discovery ────────────────────────────────────────────────────
        _update_job(db, job, status="discovery")
        candidates = await discover_candidates(
            user_query=job.query,
            country=job.country,
            sector=job.sector,
            max_results=job.max_results,
        )
        _update_job(db, job, urls_discovered=len(candidates))
        logger.info(f"[{job_id}] Discovered {len(candidates)} candidates")

        if not candidates:
            _update_job(db, job, status="complete", completed_at=datetime.utcnow(),
                        result_ids=[])
            return

        # ── 2. Fetch ────────────────────────────────────────────────────────
        _update_job(db, job, status="fetching")
        fetch_results = []
        for i, candidate in enumerate(candidates):
            # Skip if we already have this URL
            existing = db.query(Opportunity).filter(
                Opportunity.source_url == candidate.url
            ).first()
            if existing:
                logger.debug(f"[{job_id}] URL already in DB, skipping: {candidate.url}")
                continue

            try:
                result = await smart_fetch(candidate.url)
                fetch_results.append((candidate, result))
                _update_job(db, job, urls_fetched=i + 1)
            except Exception as e:
                logger.warning(f"[{job_id}] Fetch error for {candidate.url}: {e}")

            # Small delay to be polite
            await asyncio.sleep(0.3)

        # ── 3. Parse ────────────────────────────────────────────────────────
        _update_job(db, job, status="parsing")
        parsed_docs = []
        for candidate, fetch_result in fetch_results:
            doc = parse_document(fetch_result)
            parsed_docs.append((candidate, fetch_result, doc))
        _update_job(db, job, urls_parsed=len(parsed_docs))
        logger.info(f"[{job_id}] Parsed {len(parsed_docs)} documents")

        # ── 4. Extract ──────────────────────────────────────────────────────
        _update_job(db, job, status="extracting")
        extracts = []
        for candidate, fetch_result, doc in parsed_docs:
            try:
                extract = await extract_opportunity(doc, user_query=job.query)
                if extract is None:
                    extract = build_fallback_extract(doc)

                # Hackathon hardening layer:
                # merge LLM/parser output with SERP metadata, URL/domain rules,
                # date/budget regexes, and official-source heuristics.
                extract = enrich_extract_with_candidate(
                    extract=extract,
                    doc=doc,
                    candidate=candidate,
                    user_query=job.query,
                )

                extracts.append((candidate, doc, extract))
                _update_job(db, job, opportunities_extracted=len(extracts))
            except Exception as e:
                logger.warning(f"[{job_id}] Extract error: {e}")

        # ── 5. Score & Persist ──────────────────────────────────────────────
        _update_job(db, job, status="scoring")
        result_ids = []

        for candidate, doc, extract in extracts:
            try:
                scores = compute_scores(
                    extract=extract,
                    user_query=job.query,
                    domain_trust=candidate.domain_trust_score,
                    parse_confidence=doc.parse_confidence,
                )

                # Skip very-low-score non-opportunities
                if scores.final < 20 and extract.opportunity_type == "unknown":
                    continue

                opp = Opportunity(
                    job_id=job_id,
                    title=extract.title,
                    source_url=candidate.url,
                    organization=extract.organization,
                    country=extract.country,
                    city=extract.city,
                    sector=extract.sector,
                    opportunity_type=extract.opportunity_type,
                    budget_amount=extract.budget_amount,
                    budget_currency=extract.budget_currency,
                    deadline=extract.deadline,
                    publication_date=extract.publication_date,
                    summary=extract.summary,
                    requirements=extract.requirements,
                    eligibility=extract.eligibility,
                    documents=extract.documents,
                    contact_email=extract.contact_email,
                    evidence_snippets=extract.evidence_snippets,
                    relevance_score=scores.relevance,
                    urgency_score=scores.urgency,
                    strategic_fit_score=scores.strategic_fit,
                    evidence_confidence_score=scores.evidence_confidence,
                    value_score=scores.value,
                    final_score=scores.final,
                    source_reliability=round(candidate.domain_trust_score * 100, 1),
                    extraction_confidence=extract.extraction_confidence,
                    raw_text_length=doc.word_count,
                    content_type=doc.content_type,
                )
                db.add(opp)
                db.commit()
                db.refresh(opp)
                result_ids.append(opp.id)
                _update_job(db, job, opportunities_scored=len(result_ids))

            except Exception as e:
                logger.error(f"[{job_id}] Persist error: {e}")
                db.rollback()

        _update_job(
            db, job,
            status="complete",
            completed_at=datetime.utcnow(),
            result_ids=result_ids,
        )
        logger.info(f"[{job_id}] Complete — {len(result_ids)} opportunities stored")

    except Exception as e:
        logger.exception(f"[{job_id}] Pipeline failed: {e}")
        _update_job(db, job, status="failed", error_message=str(e),
                    completed_at=datetime.utcnow())
