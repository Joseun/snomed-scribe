# Specification

## Scope

One GP practice, one clinician-facing workflow: free-text consultation note
in, validated SNOMED CT codes out. No multi-practice tenancy, no EHR
integration, no full SNOMED CT terminology — a curated subset of ~100-200
common UK primary-care concepts (`data/snomed_subset.csv`), covering things
like respiratory symptoms, common chronic conditions, and routine findings.
Real NHS BSA / SNOMED International sample releases are the source for this
subset where licensing allows; otherwise a hand-curated list with real codes.

## Stack

- **Backend:** Python, FastAPI. Rationale: async-friendly, strong test
  tooling (pytest), easy to wire an LLM client into a request handler.
- **Frontend:** React + Vite, minimal — a note input box and a suggestion
  review list with accept/edit/reject controls per suggestion.
- **Database:** PostgreSQL. Stores notes, suggestions, and their validation
  state — this is the system of record for what was accepted.
- **Extraction agent:** Claude (Anthropic API), prompted to return structured
  JSON (candidate concept, SNOMED code, confidence, span of text it came
  from). Constrained to the curated subset via the prompt and a
  post-response validation step (reject any code not in
  `data/snomed_subset.csv`).
- **Containerization:** Docker Compose — `frontend`, `backend`, `db`,
  and an `otel-collector` + `grafana` pair for local observability.
- **CI/CD:** GitHub Actions. Tests run on every PR; merge to `main` deploys
  to a dev environment automatically; production deploy is a manual
  approval step in the same pipeline.
- **Deploy target:** Fly.io or Render (free/low-cost tier, gives a public
  URL, good enough for a demo deployment).
- **Observability:** OpenTelemetry traces + structured JSON logs sharing a
  `trace_id`, Prometheus metrics, visualized in Grafana. No patient note
  text or clinician identity is ever sent to telemetry — only concept
  counts, confidence scores, and latencies.

## Data model

- `consultation_note`
  - `id`, `patient_ref` (opaque identifier, not a real NHS number),
    `raw_text`, `created_at`, `clinician_id`
- `suggested_code`
  - `id`, `note_id` (FK), `snomed_code`, `term`, `confidence` (0-1),
    `source_span` (text offset the suggestion came from),
    `status` (`pending` / `accepted` / `edited` / `rejected`),
    `resolved_code` (nullable — set if clinician edits to a different code),
    `decided_at`, `decided_by`
- `snomed_reference`
  - `code`, `term`, `synonyms` (array) — the curated subset, loaded from
    `data/snomed_subset.csv` at startup
- `audit_event`
  - `id`, `note_id`, `event_type` (`alert_fired`, `on_call_action`, …),
    `payload`, `created_at` — append-only, used by the on-call agent and for
    review

## API (sketch)

- `POST /notes` — create a note, trigger extraction, return the note id.
- `GET /notes/{id}/suggestions` — list suggestions for a note with status.
- `PATCH /suggestions/{id}` — clinician action: `accept`, `edit` (with
  `resolved_code`), or `reject`. Writes `decided_by` + `decided_at`.
- `GET /metrics/coding` — aggregate stats (acceptance rate, average
  confidence, rejection rate) — backs the dashboard and the alert rule.

## Acceptance criteria (sample tasks — full list lives in the task tracker)

- A note submitted with an unambiguous respiratory symptom returns at least
  one suggestion whose `snomed_code` is in the curated subset, with
  `confidence` and `source_span` populated.
- A note containing an explicit negation ("no chest pain") does not return
  a positive suggestion for the negated concept.
- `PATCH /suggestions/{id}` with `accept` persists the code to
  `resolved_code` and sets `status=accepted`; no code reaches that state any
  other way.
- Rejection rate over a rolling 1-hour window above 40% fires the
  `coding-quality-degraded` alert (see [docs/PROCESS.md](PROCESS.md)).

## Testing

- **Unit:** extraction response parsing/validation (rejects out-of-subset
  codes), negation handling, API request/response schemas.
- **Integration:** full note → suggestion → clinician decision flow against
  a real test database (Dockerized Postgres), including the alert-trigger
  path.
- Both run with `make test`; CI runs the same target.

## Governance note

No suggestion is ever written to `resolved_code`/`accepted` without an
explicit clinician `PATCH` action. This is tested directly (see acceptance
criteria above) and should be treated as the project's one hard invariant.
