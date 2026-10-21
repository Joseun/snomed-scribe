# ClinCode — Free-Text to SNOMED CT Coding Assistant

## Problem

GP practices in the UK are required to record clinical activity using SNOMED CT
codes, but clinicians write consultation notes as free text ("pt c/o worsening
SOB on exertion, likely COPD exacerbation"). Translating that narrative into
correct SNOMED CT codes is manual, slow, and error-prone — clinicians either
search a terminology browser term-by-term or under-code.

ClinCode reads a clinician's free-text consultation note and suggests
candidate SNOMED CT codes for each clinically relevant concept it finds,
including handling negation ("no chest pain") and common abbreviations. The
clinician reviews every suggestion in a validation screen and explicitly
accepts, edits, or rejects each one — nothing is written to the patient
record without that sign-off.

**Who uses it:** GP practice clinicians, during or after a consultation.

**What it is not:** ClinCode does not diagnose, does not recommend treatment,
and never saves a code without clinician approval. It is a coding aid, not a
clinical decision tool.

## System at a glance

1. Clinician pastes/types a consultation note into the web UI.
2. Backend sends the note to the extraction agent, which returns ranked
   candidate SNOMED CT concepts with confidence scores.
3. Clinician accepts / edits / rejects each suggestion in the UI.
4. Accepted codes are persisted against the consultation record.
5. If suggestion quality degrades (confidence drop or rejection-rate spike),
   an alert fires and an on-call agent investigates and responds.

See [AGENTS.md](AGENTS.md) for how the project is built and operated, and
[docs/SPEC.md](docs/SPEC.md) for the full specification.

## Running locally

```
docker compose up
```

Brings up the frontend, backend API, Postgres database, and observability
stack with a single command. See [docs/SPEC.md](docs/SPEC.md) for details.
