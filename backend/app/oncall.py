"""On-call agent: reacts to `coding-quality-degraded`, diagnoses, acts.

Per docs/TEAM.md: pulls recent rejections, diagnoses a likely cause, and
either rolls back the extraction model to the last known-good version, or
raises a flagged incident for a human to review — never both, and never
touching a clinician's pending `suggested_code.status` directly. Always
writes one `audit_event` describing what it found and did.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import models
from app.extraction_config import get_or_create_extraction_config

WINDOW_MINUTES = 60
CATEGORY_SKEW_THRESHOLD = 0.5  # one SNOMED code causing >=50% of rejections


def diagnose_and_act(db: Session, window_minutes: int = WINDOW_MINUTES) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    rejected = (
        db.query(models.SuggestedCode)
        .filter(models.SuggestedCode.status == "rejected", models.SuggestedCode.decided_at >= cutoff)
        .all()
    )

    if not rejected:
        return {"cause": "insufficient_data", "action": "none"}

    code_counts = Counter(s.snomed_code for s in rejected)
    top_code, top_count = code_counts.most_common(1)[0]
    max_share = top_count / len(rejected)

    if max_share >= CATEGORY_SKEW_THRESHOLD:
        return _raise_incident(db, "category_skew", {"dominant_code": top_code, "share": max_share})

    config = get_or_create_extraction_config(db)
    if config.active_model != config.known_good_model:
        return _rollback(db, config)

    return _raise_incident(db, "model_regression_on_known_good", {"rejected_count": len(rejected)})


def _rollback(db: Session, config: models.ExtractionConfig) -> dict:
    previous = config.active_model
    config.active_model = config.known_good_model
    db.commit()
    db.add(
        models.AuditEvent(
            event_type="on_call_action",
            payload={
                "action": "rollback",
                "cause": "model_regression",
                "from_model": previous,
                "to_model": config.active_model,
            },
        )
    )
    db.commit()
    return {"cause": "model_regression", "action": "rollback", "from_model": previous, "to_model": config.active_model}


def _raise_incident(db: Session, cause: str, details: dict) -> dict:
    db.add(
        models.AuditEvent(
            event_type="on_call_action",
            payload={"action": "raise_incident", "cause": cause, **details},
        )
    )
    db.commit()
    return {"cause": cause, "action": "raise_incident", **details}
