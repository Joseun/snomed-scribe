from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import models
from app.config import REJECTION_RATE_ALERT_THRESHOLD

DEFAULT_WINDOW_MINUTES = 60


def compute_coding_metrics(db: Session, window_minutes: int = DEFAULT_WINDOW_MINUTES) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    decided = (
        db.query(models.SuggestedCode)
        .filter(models.SuggestedCode.decided_at.isnot(None), models.SuggestedCode.decided_at >= cutoff)
        .all()
    )
    total = len(decided)
    accepted = sum(1 for s in decided if s.status in ("accepted", "edited"))
    rejected = sum(1 for s in decided if s.status == "rejected")
    rejection_rate = (rejected / total) if total else 0.0
    mean_confidence = (sum(s.confidence for s in decided) / total) if total else 0.0

    return {
        "window_minutes": window_minutes,
        "total_suggestions": total,
        "accepted": accepted,
        "rejected": rejected,
        "rejection_rate": rejection_rate,
        "mean_confidence": mean_confidence,
    }


def check_and_fire_alert(db: Session) -> bool:
    """Fire `coding-quality-degraded` if rejection rate breaches threshold.

    Writes one audit_event per breach; the on-call agent listens for it.
    """
    metrics = compute_coding_metrics(db)
    if metrics["total_suggestions"] < 5:
        return False  # not enough signal yet to judge quality
    if metrics["rejection_rate"] <= REJECTION_RATE_ALERT_THRESHOLD:
        return False

    db.add(
        models.AuditEvent(
            event_type="alert_fired",
            payload={"alert": "coding-quality-degraded", **metrics},
        )
    )
    db.commit()
    return True
