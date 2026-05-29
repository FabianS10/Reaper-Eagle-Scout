import uuid
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.job import SearchJob
from app.schemas.search_schema import SearchRequest, SearchJobOut
from app.workers.search_worker import run_search_pipeline

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchJobOut)
async def start_search(
    req: SearchRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Start a new search pipeline job.
    Returns immediately with a job_id to poll for progress.
    """
    job = SearchJob(
        id=str(uuid.uuid4()),
        query=req.query,
        country=req.country,
        sector=req.sector,
        max_results=req.max_results,
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_search_pipeline, job.id, db)

    return SearchJobOut.from_orm(job)


@router.get("/{job_id}", response_model=SearchJobOut)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Poll pipeline progress."""
    job = db.query(SearchJob).filter(SearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return SearchJobOut.from_orm(job)


@router.get("/{job_id}/results")
def get_job_results(job_id: str, db: Session = Depends(get_db)):
    """Return the opportunity IDs produced by a job."""
    job = db.query(SearchJob).filter(SearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("complete", "failed"):
        raise HTTPException(status_code=202, detail="Job still running")
    return {"job_id": job_id, "status": job.status, "result_ids": job.result_ids or []}


@router.get("")
def list_jobs(db: Session = Depends(get_db)):
    """List recent search jobs."""
    jobs = db.query(SearchJob).order_by(SearchJob.created_at.desc()).limit(20).all()
    return [SearchJobOut.from_orm(j) for j in jobs]
