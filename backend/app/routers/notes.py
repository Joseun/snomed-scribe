from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.extraction import AnthropicExtractionClient, ExtractionClient, extract_candidates

router = APIRouter(prefix="/notes", tags=["notes"])


def get_extraction_client() -> ExtractionClient:
    return AnthropicExtractionClient()


@router.post("", response_model=schemas.NoteOut)
def create_note(
    note_in: schemas.NoteCreate,
    db: Session = Depends(get_db),
    extraction_client: ExtractionClient = Depends(get_extraction_client),
):
    note = models.ConsultationNote(
        patient_ref=note_in.patient_ref,
        clinician_id=note_in.clinician_id,
        raw_text=note_in.raw_text,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    candidates = extract_candidates(note.raw_text, extraction_client)
    for candidate in candidates:
        db.add(
            models.SuggestedCode(
                note_id=note.id,
                snomed_code=candidate.snomed_code,
                term=candidate.term,
                confidence=candidate.confidence,
                source_span=candidate.source_span,
            )
        )
    db.commit()
    return note


@router.get("/{note_id}/suggestions", response_model=list[schemas.SuggestionOut])
def list_suggestions(note_id: str, db: Session = Depends(get_db)):
    return db.query(models.SuggestedCode).filter(models.SuggestedCode.note_id == note_id).all()
