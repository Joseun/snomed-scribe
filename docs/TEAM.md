# Agent Team

ClinCode involves two distinct sets of agents: the ones used to *build* the
system, and the one agent that runs *inside* the deployed system.

## Build-time agents (how this project gets built)

Driven via Claude Code / an equivalent coding agent, working from the tasks
in the public tracker (see [PROCESS.md](PROCESS.md)):

- **Spec agent** — turns a tracked task into a concrete acceptance criterion
  and flags ambiguity back to the human before code is written.
- **Implementation agent** — writes the code for one task at a time, scoped
  to the files the task touches.
- **Test agent** — writes/updates unit and integration tests for the task,
  and must see them pass before the task is marked done.
- **Review agent** — reviews the diff for correctness, scope creep, and
  whether it preserves the one hard invariant (no code saved without
  clinician accept).

These are roles, not necessarily separate processes — one agent can hold
multiple roles sequentially, but each role's output should be visible in the
PR (what was specified, what was tested, what was reviewed).

## Runtime agent (part of the deployed system)

- **On-call agent** — the only agent that runs as part of the live
  application, not just the build process. Wakes up when the
  `coding-quality-degraded` alert fires (see [PROCESS.md](PROCESS.md)).
  - Pulls the recent rejected/low-confidence suggestions from
    `audit_event` and `suggested_code`.
  - Diagnoses a likely cause (e.g. one concept category failing
    disproportionately, a prompt/model regression, a bad deploy).
  - Takes one of: roll back the extraction prompt/model version to the last
    known-good config, or — if the cause isn't a config regression — leave
    the system running and raise a flagged incident note for a human to
    review, rather than guessing further.
  - Always writes an `audit_event` describing what it found and what it did,
    so the action is reviewable after the fact.
  - Never touches `suggested_code.status` directly — it can only act on the
    extraction pipeline, never on a clinician's pending decision.
