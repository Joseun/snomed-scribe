import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app import models
from app.config import ALERT_WEBHOOK_URL, REJECTION_RATE_ALERT_THRESHOLD

DEFAULT_WINDOW_MINUTES = 60
WEBHOOK_TIMEOUT_SECONDS = 5

logger = logging.getLogger(__name__)


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
    _send_alert_webhook({"alert": "coding-quality-degraded", **metrics})
    return True


def _send_alert_webhook(payload: dict) -> None:
    """Best-effort delivery; a down webhook must never fail the request."""
    if not ALERT_WEBHOOK_URL:
        return
    try:
        httpx.post(ALERT_WEBHOOK_URL, json=payload, timeout=WEBHOOK_TIMEOUT_SECONDS)
    except httpx.HTTPError:
        logger.warning("alert webhook delivery failed", exc_info=True)
