from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class NoteCreate(BaseModel):
    patient_ref: str
    clinician_id: str
    raw_text: str


class NoteOut(BaseModel):
    id: str
    patient_ref: str
    clinician_id: str
    raw_text: str
    created_at: datetime

    class Config:
        from_attributes = True


class SuggestionOut(BaseModel):
    id: str
    note_id: str
    snomed_code: str
    term: str
    confidence: float
    source_span: Optional[str]
    status: str
    resolved_code: Optional[str]

    class Config:
        from_attributes = True


class SuggestionDecision(BaseModel):
    action: Literal["accept", "edit", "reject"]
    decided_by: str
    resolved_code: Optional[str] = None


class CodingMetrics(BaseModel):
    window_minutes: int
    total_suggestions: int
    accepted: int
    rejected: int
    rejection_rate: float
    mean_confidence: float
