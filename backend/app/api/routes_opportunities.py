from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc
from app.database import get_db
from app.models.opportunity import Opportunity
from app.schemas.opportunity_schema import OpportunityOut, OpportunityListOut
from app.services.scoring_service import compute_scores

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.get("", response_model=OpportunityListOut)
def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: str = Query("final_score", regex="^(final_score|deadline|budget_amount|created_at)$"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$"),
    sector: Optional[str] = None,
    country: Optional[str] = None,
    opportunity_type: Optional[str] = None,
    min_score: float = Query(0.0, ge=0, le=100),
    search: Optional[str] = None,
    job_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Opportunity)

    if sector:
        q = q.filter(Opportunity.sector == sector)
    if country:
        q = q.filter(Opportunity.country == country)
    if opportunity_type:
        q = q.filter(Opportunity.opportunity_type == opportunity_type)
    if min_score > 0:
        q = q.filter(Opportunity.final_score >= min_score)
    if job_id:
        q = q.filter(Opportunity.job_id == job_id)
    if search:
        pattern = f"%{search}%"
        q = q.filter(or_(
            Opportunity.title.ilike(pattern),
            Opportunity.organization.ilike(pattern),
            Opportunity.summary.ilike(pattern),
        ))

    total = q.count()

    sort_col = getattr(Opportunity, sort_by)
    if sort_dir == "desc":
        q = q.order_by(desc(sort_col).nulls_last())
    else:
        q = q.order_by(asc(sort_col).nulls_last())

    items = q.offset((page - 1) * page_size).limit(page_size).all()

    return OpportunityListOut(
        items=[OpportunityOut.from_orm_with_scores(o) for o in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{opp_id}", response_model=OpportunityOut)
def get_opportunity(opp_id: str, db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return OpportunityOut.from_orm_with_scores(opp)


@router.post("/{opp_id}/bookmark")
def toggle_bookmark(opp_id: str, db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    opp.is_bookmarked = not opp.is_bookmarked
    db.commit()
    return {"id": opp_id, "is_bookmarked": opp.is_bookmarked}


@router.post("/{opp_id}/initiate")
def initiate_response(opp_id: str, db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    opp.response_initiated = True
    db.commit()
    return {"id": opp_id, "response_initiated": True}


@router.delete("/{opp_id}")
def delete_opportunity(opp_id: str, db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    db.delete(opp)
    db.commit()
    return {"deleted": opp_id}
