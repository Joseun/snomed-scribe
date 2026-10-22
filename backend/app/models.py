import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ConsultationNote(Base):
    __tablename__ = "consultation_note"

    id = Column(String, primary_key=True, default=_uuid)
    patient_ref = Column(String, nullable=False)
    raw_text = Column(String, nullable=False)
    clinician_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now)

    suggestions = relationship("SuggestedCode", back_populates="note", cascade="all, delete-orphan")


class SuggestedCode(Base):
    __tablename__ = "suggested_code"

    id = Column(String, primary_key=True, default=_uuid)
    note_id = Column(String, ForeignKey("consultation_note.id"), nullable=False)
    snomed_code = Column(String, nullable=False)
    term = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    source_span = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending / accepted / edited / rejected
    resolved_code = Column(String, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decided_by = Column(String, nullable=True)

    note = relationship("ConsultationNote", back_populates="suggestions")


class AuditEvent(Base):
    __tablename__ = "audit_event"

    id = Column(String, primary_key=True, default=_uuid)
    note_id = Column(String, ForeignKey("consultation_note.id"), nullable=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_now)


class ExtractionConfig(Base):
    """Singleton row (id='default') tracking which model version is live.

    Lets the on-call agent roll back to the last known-good model without a
    redeploy — see app/oncall.py.
    """

    __tablename__ = "extraction_config"

    id = Column(String, primary_key=True)
    active_model = Column(String, nullable=False)
    known_good_model = Column(String, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now)
