"""The school's four chorak date ranges: anyone on staff reads them (the exam
list's default view is "the current chorak"), only an admin changes them."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.dependencies import require_role
from app.models.user import User
from app.schemas.quarters import QuartersIn, QuartersOut, QuarterOut
from app.services import quarter_service

router = APIRouter(prefix="/api/v1/admin/quarters", tags=["admin-quarters"])


def _out(db: Session) -> QuartersOut:
    quarters, is_default = quarter_service.get_quarters(db)
    today = quarter_service.school_today()
    year = quarter_service.school_year_start_year(today)
    return QuartersOut(
        school_year_start=year,
        current_number=quarter_service.quarter_of(quarters, today),
        is_default=is_default,
        quarters=[
            QuarterOut(number=q.number, start_date=start, end_date=end)
            for q in quarters
            for start, end in [quarter_service.quarter_dates(q, year)]
        ],
    )


@router.get("", response_model=QuartersOut)
def get_quarters(db: Session = Depends(get_db), _user: User = Depends(require_role("teacher", "admin"))):
    return _out(db)


@router.put("", response_model=QuartersOut)
def put_quarters(body: QuartersIn, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))):
    parsed = {
        q.number: (q.start_date.month, q.start_date.day, q.end_date.month, q.end_date.day) for q in body.quarters
    }
    if len(parsed) != len(body.quarters):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chorak raqami takrorlangan")
    try:
        quarter_service.save_quarters(db, parsed)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _out(db)
