import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import EXTRACTION_PROVIDER
from app.db import get_db
from app.extraction import AnthropicExtractionClient, ExtractionClient, GroqExtractionClient, extract_candidates
from app.extraction_config import get_or_create_extraction_config
from app.telemetry import extraction_latency_seconds, get_tracer, suggestion_confidence, suggestions_created_total

router = APIRouter(prefix="/notes", tags=["notes"])
tracer = get_tracer()


def get_extraction_client(db: Session = Depends(get_db)) -> ExtractionClient:
    if EXTRACTION_PROVIDER == "groq":
        return GroqExtractionClient()  # local-only workaround, see app/config.py
    config = get_or_create_extraction_config(db)
    return AnthropicExtractionClient(model=config.active_model)


@router.post("", response_model=schemas.NoteOut)
def create_note(
    note_in: schemas.NoteCreate,
    db: Session = Depends(get_db),
    extraction_client: ExtractionClient = Depends(get_extraction_client),
):
    with tracer.start_as_current_span("note.submitted"):
        note = models.ConsultationNote(
            patient_ref=note_in.patient_ref,
            clinician_id=note_in.clinician_id,
            raw_text=note_in.raw_text,
        )
        db.add(note)
        db.commit()
        db.refresh(note)

    with tracer.start_as_current_span("extraction.call") as span:
        start = time.perf_counter()
        candidates = extract_candidates(note.raw_text, extraction_client)
        extraction_latency_seconds.observe(time.perf_counter() - start)
        span.set_attribute("candidate_count", len(candidates))

    with tracer.start_as_current_span("suggestions.returned") as span:
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
            suggestions_created_total.inc()
            suggestion_confidence.observe(candidate.confidence)
        db.commit()
        span.set_attribute("suggestion_count", len(candidates))

    return note


@router.get("/{note_id}/suggestions", response_model=list[schemas.SuggestionOut])
def list_suggestions(note_id: str, db: Session = Depends(get_db)):
    return db.query(models.SuggestedCode).filter(models.SuggestedCode.note_id == note_id).all()


@router.post("/preview", response_model=list[schemas.NotePreviewSuggestion])
def preview_note(
    preview_in: schemas.NotePreviewRequest,
    extraction_client: ExtractionClient = Depends(get_extraction_client),
):
    """Live-scan while a clinician types. Writes nothing — no note, no
    suggested_code row — so the hard invariant (no code reaches the record
    without an explicit accept) holds trivially: nothing here can become an
    accepted code directly.
    """
    with tracer.start_as_current_span("note.preview") as span:
        candidates = extract_candidates(preview_in.raw_text, extraction_client)
        span.set_attribute("candidate_count", len(candidates))
    return candidates
