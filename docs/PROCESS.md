# Process

## Task tracker

GitHub Issues on this repo, grouped under a GitHub Project board (public).
Every issue states its acceptance criteria up front, in the same form as the
samples in [SPEC.md](SPEC.md). Agents reference the issue number in commits
and PRs; a PR without a linked issue is treated as out of process.

## Development workflow

1. Pick (or write) an issue with stated acceptance criteria.
2. Spec agent confirms the criteria are concrete; flags gaps to a human.
3. Implementation agent writes the change, scoped to that issue only.
4. Test agent adds/updates unit + integration tests; `make test` must pass.
5. Review agent reviews the diff against the issue and the hard invariant
   (no SNOMED code saved without clinician accept).
6. PR opened, linked to the issue; CI re-runs tests; merge on green + review.

## Testing

- `make test` runs unit and integration suites together, locally and in CI.
- Integration tests run against a real Dockerized Postgres instance, not
  mocks — the thing worth proving is that a note really flows end to end to
  a persisted, clinician-approved code.

## Containerization

`docker compose up` brings up `frontend`, `backend`, `db`, `otel-collector`,
and `grafana` with one command. No manual setup steps beyond that.

## CI/CD

GitHub Actions pipeline:
- On every PR: run `make test`.
- On merge to `main`: build images, deploy to a `dev` environment
  automatically.
- Promotion to `production` is a manual approval step in the same workflow
  (not a separate process) — a human clicks approve after checking the dev
  deploy.

## Deployment

Deployed to Fly.io (or Render), reachable at a public URL. The deployed
instance uses synthetic/test note data only — no real patient data, given
this is a course project, not a live clinical system.

## Observability

- Every request carries a `trace_id` through backend logs, traces, and
  metrics, so one consultation-note request can be followed end to end.
- Logs are structured JSON; traces and metrics go through OpenTelemetry to
  Grafana (traces + metrics panels) locally, or a hosted free tier
  (Grafana Cloud) in the deployed environment.
- No note text, patient identifier, or clinician identity is ever sent to
  the telemetry backend — only concept counts, confidence scores, status
  transitions, and latencies.
- Key user journey instrumented: note submitted → extraction call →
  suggestions returned → clinician decision recorded. Each step emits a
  span and a metric.

## Alerting

- **`coding-quality-degraded`**: fires when the rejection rate over a
  rolling 1-hour window exceeds 40%, or when mean suggestion confidence
  drops below a set floor. Backed by `GET /metrics/coding`.
- Alert delivery: a simple webhook (e.g. to a logging/Slack-style endpoint)
  — not a goal in itself, just the trigger the on-call agent listens for.

## On-call agent runbook

See [TEAM.md](TEAM.md) for the agent's responsibilities. Every invocation
writes an `audit_event` — this is the project's record of what the agent
saw, decided, and did, and is what a human would review afterwards to judge
whether the agent acted correctly.
