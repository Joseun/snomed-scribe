from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.metrics import compute_coding_metrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/coding", response_model=schemas.CodingMetrics)
def coding_metrics(window_minutes: int = 60, db: Session = Depends(get_db)):
    return compute_coding_metrics(db, window_minutes)
