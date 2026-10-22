from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.metrics import check_and_fire_alert

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


@router.patch("/{suggestion_id}", response_model=schemas.SuggestionOut)
def decide_suggestion(suggestion_id: str, decision: schemas.SuggestionDecision, db: Session = Depends(get_db)):
    suggestion = db.query(models.SuggestedCode).filter(models.SuggestedCode.id == suggestion_id).first()
    if suggestion is None:
        raise HTTPException(status_code=404, detail="suggestion not found")

    if decision.action == "accept":
        suggestion.status = "accepted"
        suggestion.resolved_code = suggestion.snomed_code
    elif decision.action == "edit":
        if not decision.resolved_code:
            raise HTTPException(status_code=400, detail="resolved_code required for edit")
        suggestion.status = "edited"
        suggestion.resolved_code = decision.resolved_code
    else:
        suggestion.status = "rejected"
        suggestion.resolved_code = None

    suggestion.decided_by = decision.decided_by
    suggestion.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(suggestion)

    check_and_fire_alert(db)
    return suggestion
