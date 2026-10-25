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

Extraction defaults to the Anthropic API (`ANTHROPIC_API_KEY` in `.env`).
For local development without a paid key, `EXTRACTION_PROVIDER=groq` plus a
free-tier `GROQ_API_KEY` switches to Groq's OpenAI-compatible API instead —
an explicit local-only workaround, not the documented stack (see
[docs/SPEC.md](docs/SPEC.md)).

## Status

Core loop works end to end: a note goes in, candidate codes come back
(including a live-scan preview while typing), and nothing reaches the
record without an explicit accept. Backend, frontend, CI, local
observability (traces, metrics, dashboards), alerting, and a basic on-call
agent are all in place — see [docs/PROCESS.md](docs/PROCESS.md) for how
these pieces fit together and the task tracker (GitHub Issues) for what's
tracked and done.

What's genuinely in place vs. what's scaffolding for a course project is
important to be honest about — see Limitations below before relying on any
of this beyond a demo.

## Limitations

- **Curated SNOMED subset is small and only International-Edition
  verified.** 15 concepts against the ~100-200 the spec describes. Every
  code has been checked against SNOMED CT International via a public
  terminology server, which already caught two real errors (a wrong
  concept and a retired code) — but that's not NHS TRUD UK-release
  verification, and the UK extension can differ from International in
  places. A phrase outside the subset reports "no code" rather than a
  possibly-wrong one; a phrase with a plausible-looking code in it is not
  automatically trustworthy without that fuller verification pass.
- **Negation handling is a heuristic, not real NLP.** Clause-boundary
  splitting plus a fixed cue-word list ("no", "denies", …) catches the
  common cases well but will miss indirect negation, double negatives, and
  hedged language ("can't rule out", "query asthma").
- **The extraction model can hallucinate or drift.** The backend enforces
  the one hard rule server-side (reject any code outside the curated
  subset) regardless of what the model proposes, but confidence scores and
  term matches are still the model's self-report, not independently
  verified.
- **No authentication, authorization, or multi-practice tenancy.**
  `clinician_id` is a free-text field the client supplies; there's no login,
  no per-practice data isolation, no audit of who's allowed to see what.
  Fine for a single-practice demo, not for anything real.
- **No real EHR integration.** Notes are typed into this app's own UI, not
  pulled from or pushed to a GP clinical system. `patient_ref` is an opaque
  demo identifier, not a real NHS number.
- **Live-scan has a real cost per debounce tick.** Every pause while typing
  is a real LLM call. Fine at demo scale; would need caching, rate
  limiting, or a cheaper/local model before scaling up to many concurrent
  clinicians.
- **On-call agent's diagnosis is a single, simple heuristic.** "One SNOMED
  code dominates rejections" vs. "diffuse rejections" is a reasonable first
  cut, but it's one signal, not a real anomaly-detection model, and it's
  never been exercised against a real incident.
- **Observability stack is local-only and unauthenticated.** Grafana runs
  with anonymous admin access, Prometheus and Tempo have no retention
  policy tuning or access control — correct for local dev, wrong for
  anything deployed.
- **Single-instance Postgres, no backups, no HA.** Acceptable for synthetic
  demo data; not a statement about how this would need to run for real
  clinical use.

## Ways to improve

- Verify the full curated subset against NHS TRUD's licensed UK SNOMED CT
  release and extend it toward the ~100-200 concept target in
  [docs/SPEC.md](docs/SPEC.md), covering more of the presentations a UK GP
  actually codes day to day.
- Replace the clause-heuristic negation detector with a proper clinical NLP
  pass (or a second LLM-graded negation/certainty pass) to catch hedged and
  indirect negation.
- Add caching/rate-limiting to the live-scan preview endpoint — e.g. don't
  re-call the model for a prefix of text already scanned, or debounce
  further when a note is long and mostly stable.
- Give the on-call agent a statistical basis (e.g. a real drift/anomaly
  model over rejection patterns, confidence distributions over time)
  instead of one fixed heuristic threshold, and actually exercise it
  against a seeded incident in a test.
- Add authentication and per-practice data isolation if this were ever to
  move beyond a single-practice demo.
- Harden the observability stack for a real deployment: Grafana auth,
  retention policies, alert routing beyond a single webhook.
- Add browser-driven end-to-end tests (the UI has been verified manually
  against a live backend this session, but there's no automated coverage
  of the actual rendered page).

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
