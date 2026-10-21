# AGENTS.md

This file orients any agent (or human) working on ClinCode. It links out to
modular docs rather than repeating their content.

## What this project is

ClinCode is a free-text-to-SNOMED-CT coding assistant for UK GP practices.
Full problem description: [README.md](README.md).
Full specification (data model, API, acceptance criteria): [docs/SPEC.md](docs/SPEC.md).

## How the project is organized

| Doc | Covers |
|---|---|
| [docs/SPEC.md](docs/SPEC.md) | Problem, scope, data model, API contract, acceptance criteria per task |
| [docs/TEAM.md](docs/TEAM.md) | Agent roles — build-time and runtime — and their responsibilities |
| [docs/PROCESS.md](docs/PROCESS.md) | How agents collaborate, task tracker, testing/CI/CD/deploy/observability/alerting/on-call workflow |

## Ground rules for any agent working here

- Never let a suggested SNOMED code reach the patient record without an
  explicit clinician "accept" action. This is the one non-negotiable rule in
  the whole system — treat any change that weakens it as a regression.
- Keep the SNOMED reference set scoped to the curated subset in
  `data/snomed_subset.csv` (see [docs/SPEC.md](docs/SPEC.md)) — do not pull in
  a full SNOMED CT release, licensing and scope make that out of bounds for
  this project.
- Work against the public task tracker (see [docs/PROCESS.md](docs/PROCESS.md))
  — every change should map to a tracked task with stated acceptance criteria.
- Run tests before opening a PR: `make test` (unit + integration, see
  [docs/PROCESS.md](docs/PROCESS.md)).
