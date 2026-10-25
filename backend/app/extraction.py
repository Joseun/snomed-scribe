"""Free-text note -> candidate SNOMED CT suggestions.

The extraction client (LLM) proposes candidates; this module is the
validation boundary that enforces the two rules the rest of the system
relies on:
  1. a suggestion's code must be in the curated SNOMED subset, and
  2. a concept explicitly negated in the note ("no chest pain") is dropped.
Nothing past `extract_candidates` should need to re-check either rule.
"""
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.config import ANTHROPIC_API_KEY, KNOWN_GOOD_EXTRACTION_MODEL, SNOMED_SUBSET_PATH

NEGATION_CUES = ("no ", "not ", "denies ", "denied ", "without ", "no evidence of ")
CLAUSE_BOUNDARY = re.compile(r"[.,;]|\bbut\b|\bhowever\b|\balthough\b")


@dataclass(frozen=True)
class SnomedConcept:
    code: str
    term: str
    synonyms: tuple[str, ...]


@dataclass
class Candidate:
    snomed_code: str
    term: str
    confidence: float
    source_span: str


@dataclass
class PreviewCandidate:
    """Like Candidate, but snomed_code may be None — the live-scan panel
    shows a clinically relevant phrase even when it has no curated match,
    so the clinician isn't left wondering why something they typed never
    appeared. Never persisted; see routers/notes.py's /notes/preview.
    """

    snomed_code: str | None
    term: str
    confidence: float
    source_span: str


def load_snomed_subset(path: Path = SNOMED_SUBSET_PATH) -> list[SnomedConcept]:
    concepts = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            synonyms = tuple(s.strip() for s in (row.get("synonyms") or "").split(";") if s.strip())
            concepts.append(SnomedConcept(code=row["code"], term=row["term"], synonyms=synonyms))
    return concepts


def _is_negated(note_text: str, source_span: str) -> bool:
    """Negation only counts within the same clause as the span.

    A fixed character window bleeds across clause boundaries, e.g. "denies
    chest pain but reports SOB" would otherwise also mark SOB negated.
    """
    lower = note_text.lower()
    idx = lower.find(source_span.lower())
    if idx == -1:
        return False

    clause_start = 0
    for match in CLAUSE_BOUNDARY.finditer(lower):
        if match.start() >= idx:
            break
        clause_start = match.end()

    preceding_in_clause = lower[clause_start:idx]
    return any(cue in preceding_in_clause for cue in NEGATION_CUES)


class ExtractionClient(Protocol):
    def complete(self, note_text: str, concepts: list[SnomedConcept]) -> list[dict]:
        """Return raw candidates: [{term, snomed_code, confidence, source_span}, ...]."""

    def complete_preview(self, note_text: str, concepts: list[SnomedConcept]) -> list[dict]:
        """Like complete, but snomed_code may be null for a phrase with no curated match."""


def _concept_list(concepts: list[SnomedConcept]) -> str:
    return "\n".join(f"{c.code} | {c.term} | synonyms: {', '.join(c.synonyms)}" for c in concepts)


def _build_prompt(note_text: str, concepts: list[SnomedConcept]) -> str:
    return (
        "You are assisting a UK GP with clinical coding. Given the consultation "
        "note below and the allowed SNOMED CT concept list, return a JSON array "
        "of candidate concepts actually present in the note (not negated, not "
        "merely mentioned hypothetically). Only use codes from the allowed list.\n\n"
        f"Allowed concepts:\n{_concept_list(concepts)}\n\n"
        f"Note:\n{note_text}\n\n"
        "Respond with only a JSON array of objects, no other text: "
        '{"term": ..., "snomed_code": ..., "confidence": 0-1, "source_span": "<exact text from note>"}'
    )


def _build_preview_prompt(note_text: str, concepts: list[SnomedConcept]) -> str:
    return (
        "You are assisting a UK GP with clinical coding, scanning a consultation "
        "note live while it's still being typed. Identify every clinically "
        "relevant finding, symptom, condition, or action mentioned in the note "
        "below — not just the ones with a matching code. For each: if it "
        "matches one of the allowed SNOMED CT concepts, use that exact code; "
        "if it doesn't match any allowed concept, set snomed_code to null. "
        "Never invent a code that isn't in the allowed list. Skip anything "
        'explicitly negated (e.g. "no chest pain", "denies cough").\n\n'
        f"Allowed concepts:\n{_concept_list(concepts)}\n\n"
        f"Note:\n{note_text}\n\n"
        "Respond with only a JSON array of objects, no other text: "
        '{"term": ..., "snomed_code": "<code or null>", "confidence": 0-1, "source_span": "<exact text from note>"}'
    )


def _parse_json_array(text: str) -> list[dict]:
    """Strip markdown code fences some models wrap JSON in before parsing."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[len("json") :]
        stripped = stripped.strip()
    return json.loads(stripped)


class AnthropicExtractionClient:
    """Calls Claude, constrained to the curated SNOMED subset via the prompt."""

    def __init__(self, model: str = KNOWN_GOOD_EXTRACTION_MODEL, api_key: str | None = None):
        self.model = model
        self.api_key = api_key or ANTHROPIC_API_KEY

    def _call(self, prompt: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def complete(self, note_text: str, concepts: list[SnomedConcept]) -> list[dict]:
        return _parse_json_array(self._call(_build_prompt(note_text, concepts)))

    def complete_preview(self, note_text: str, concepts: list[SnomedConcept]) -> list[dict]:
        return _parse_json_array(self._call(_build_preview_prompt(note_text, concepts)))


def extract_candidates(
    note_text: str,
    client: ExtractionClient,
    concepts: list[SnomedConcept] | None = None,
) -> list[Candidate]:
    concepts = concepts if concepts is not None else load_snomed_subset()
    valid_codes = {c.code for c in concepts}

    raw_candidates = client.complete(note_text, concepts)

    results = []
    for raw in raw_candidates:
        code = raw.get("snomed_code")
        source_span = raw.get("source_span", "")
        if code not in valid_codes:
            continue
        if _is_negated(note_text, source_span):
            continue
        results.append(
            Candidate(
                snomed_code=code,
                term=raw.get("term", ""),
                confidence=float(raw.get("confidence", 0.0)),
                source_span=source_span,
            )
        )
    return results


def extract_preview_candidates(
    note_text: str,
    client: ExtractionClient,
    concepts: list[SnomedConcept] | None = None,
) -> list[PreviewCandidate]:
    """Live-scan version of extract_candidates: a phrase with no curated
    match is kept (snomed_code=None) instead of being dropped, so the
    clinician sees it was recognized even without a code. A code the model
    proposed but that isn't in the curated subset is treated the same way —
    never surfaced as a real code, only as "no code" here. Negation is still
    enforced; this is display-only and nothing here is ever persisted.
    """
    concepts = concepts if concepts is not None else load_snomed_subset()
    valid_codes = {c.code for c in concepts}

    raw_candidates = client.complete_preview(note_text, concepts)

    results = []
    for raw in raw_candidates:
        source_span = raw.get("source_span", "")
        if _is_negated(note_text, source_span):
            continue
        code = raw.get("snomed_code") or None
        if code is not None and code not in valid_codes:
            code = None
        results.append(
            PreviewCandidate(
                snomed_code=code,
                term=raw.get("term", ""),
                confidence=float(raw.get("confidence", 0.0)),
                source_span=source_span,
            )
        )
    return results
