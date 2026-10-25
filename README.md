# SNOMED-Scribe — Free-Text to SNOMED CT Coding Assistant

## Problem

GP practices in the UK are required to record clinical activity using SNOMED CT
codes, but clinicians write consultation notes as free text ("pt c/o worsening
SOB on exertion, likely COPD exacerbation"). Translating that narrative into
correct SNOMED CT codes is manual, slow, and error-prone — clinicians either
search a terminology browser term-by-term or under-code.

SNOMED-Scribe reads a clinician's free-text consultation note and suggests
candidate SNOMED CT codes for each clinically relevant concept it finds,
including handling negation ("no chest pain") and common abbreviations. The
clinician reviews every suggestion in a validation screen and explicitly
accepts, edits, or rejects each one — nothing is written to the patient
record without that sign-off.

**Who uses it:** GP practice clinicians, during or after a consultation.

**What it is not:** SNOMED-Scribe does not diagnose, does not recommend treatment,
and never saves a code without clinician approval. It is a coding aid, not a
clinical decision tool.

## Status

Core loop works end to end, verified live: a note goes in, candidate SNOMED
codes come back — including a live-scan preview that annotates codes inline
as the clinician types — and nothing reaches the record without an explicit
accept. Full stack (frontend, backend, Postgres, CI, local observability
with traces/metrics/dashboards, alerting, and a working on-call agent) runs
from a single `docker compose up`. See [docs/PROCESS.md](docs/PROCESS.md)
for how the pieces fit together and the GitHub Issues tracker for what's
built and tested.

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

Extraction defaults to the Anthropic API (`ANTHROPIC_API_KEY` in `.env`).
For local development without a paid key, `EXTRACTION_PROVIDER=groq` plus a
free-tier `GROQ_API_KEY` switches to Groq's OpenAI-compatible API instead —
an explicit local-only workaround, not the documented stack (see
[docs/SPEC.md](docs/SPEC.md)).

## Limitations

Known gaps, scoped deliberately for a course project — not a statement
about what this would take to run for real:

- **Curated SNOMED subset is small (15 concepts vs. the ~100-200 target)
  and verified against SNOMED CT International, not the licensed NHS TRUD
  UK release.** Verification already caught two real errors (a wrong
  concept, a retired code) in the original data — but the UK extension can
  still differ from International in places. A phrase outside the subset
  just reports "no code" rather than guessing.
- **Negation handling is a clause-boundary heuristic, not clinical NLP** —
  catches the common cases ("no chest pain") but will miss hedged or
  indirect phrasing ("can't rule out", "query asthma").
- **No auth, multi-practice tenancy, or EHR integration** — single-practice
  demo scope, `clinician_id`/`patient_ref` are client-supplied demo
  identifiers, not real login or NHS numbers.
- **Several pieces are demo-grade by design**: live-scan calls the LLM on
  every typing pause with no caching; the on-call agent's diagnosis is one
  fixed heuristic, not a statistical model; the observability stack has no
  auth or retention tuning; Postgres is single-instance with no backups.

## Ways to improve

- Verify the curated subset against NHS TRUD's licensed UK release and
  extend it toward the ~100-200 concept target in
  [docs/SPEC.md](docs/SPEC.md).
- Replace the clause-heuristic negation detector with a proper clinical NLP
  pass, or a second LLM-graded negation/certainty pass.
- Cache/rate-limit the live-scan preview endpoint instead of calling the
  model on every debounce tick.
- Give the on-call agent a statistical basis (real drift/anomaly detection
  over rejection patterns) instead of one fixed threshold, and exercise it
  against a seeded incident in a test.
- Add authentication and per-practice data isolation before any real use
  beyond a single-practice demo.
- Harden observability for a real deployment: Grafana auth, retention
  policies, alert routing beyond a single webhook.
- Add browser-driven end-to-end tests — the UI's been verified manually
  against a live backend, but there's no automated coverage of the
  rendered page itself.

## What this project reinforced

- **A hard invariant is only as strong as where it's enforced.** "No code
  reaches the record without accept" had to be checked server-side
  (reject anything outside the curated subset, regardless of what the
  model returns) — trusting the LLM's output shape would have been enough
  to violate it the first time the model didn't follow instructions.
- **Unit tests running outside Docker can hide real deployment bugs.**
  `make test` stayed green through a bug where the backend image genuinely
  couldn't find its own reference data — because the test suite never ran
  inside the container the bug lived in. Actually running the app, not
  just testing it, is what surfaced that.
- **LLM-cited reference data needs live verification, not just confident
  recall.** Codes that "look right" from general training/public examples
  turned out to include a wrong concept and a retired one — caught only by
  actually querying a live terminology server, not by re-checking memory
  harder.
- **A read-only preview is a cheap way to get a much better UX loop.**
  Splitting "scan while typing" from "submit for real" let the live-scan
  panel stay useful and non-destructive at the same time, without touching
  the hard invariant around persistence at all.
- **`depends_on` in Compose is about process start, not readiness.** A
  fresh-volume Postgres container takes real time to `initdb`; waiting on
  "container started" rather than "accepting connections" is a race, not
  an edge case — it reproduced the very first time the volume was wiped.
