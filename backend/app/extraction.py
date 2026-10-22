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

from app.config import ANTHROPIC_API_KEY, SNOMED_SUBSET_PATH

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


class AnthropicExtractionClient:
    """Calls Claude, constrained to the curated SNOMED subset via the prompt."""

    def __init__(self, model: str = "claude-sonnet-5-5", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or ANTHROPIC_API_KEY

    def complete(self, note_text: str, concepts: list[SnomedConcept]) -> list[dict]:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        concept_list = "\n".join(f"{c.code} | {c.term} | synonyms: {', '.join(c.synonyms)}" for c in concepts)
        prompt = (
            "You are assisting a UK GP with clinical coding. Given the consultation "
            "note below and the allowed SNOMED CT concept list, return a JSON array "
            "of candidate concepts actually present in the note (not negated, not "
            "merely mentioned hypothetically). Only use codes from the allowed list.\n\n"
            f"Allowed concepts:\n{concept_list}\n\n"
            f"Note:\n{note_text}\n\n"
            "Respond with only a JSON array of objects: "
            '{"term": ..., "snomed_code": ..., "confidence": 0-1, "source_span": "<exact text from note>"}'
        )
        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        return json.loads(text)


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
