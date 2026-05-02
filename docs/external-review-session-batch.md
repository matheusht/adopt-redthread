# External Review Session Batch

## Purpose

The external review session batch turns the sanitized handoff directory into isolated reviewer folders for three silent external reviews.

This is scheduling/intake plumbing only. It is not validation evidence until reviewers fill observations, the observations are summarized, and the summaries are rolled up.

## Build sequence

Regenerate the sanitized handoff first:

```bash
make evidence-boundary-probe-plan
make evidence-boundary-execution-design
make evidence-boundary-probe-result
make evidence-report
make evidence-matrix
make evidence-packet
make evidence-external-review-handoff
```

Then create the reviewer sessions and distribution manifest:

```bash
make evidence-external-review-sessions
make evidence-freshness
make evidence-external-review-distribution
```

Generated local output:

```text
runs/external_review_sessions/
├── external_review_session_batch.md
├── external_review_session_batch.json
├── review_1/
│   ├── artifacts/
│   │   ├── evidence_report.md
│   │   ├── evidence_matrix.md
│   │   ├── reviewer_packet.md
│   │   ├── reviewer_observation_template.md
│   │   ├── tenant_user_boundary_probe_result.md  # only when present in handoff
│   │   └── external_reviewer_instructions.md
│   ├── filled_reviewer_observation.md
│   └── reviewer_session_instructions.md
├── review_2/
└── review_3/
```

`runs/` remains ignored. Do not commit filled observations unless they have been manually reviewed for privacy.

## What each session contains

Each session folder contains only:

- sanitized markdown copied from `runs/external_review_handoff/`
- a blank observation file for that reviewer
- session-specific instructions
- command paths for summarization

Each session intentionally excludes:

- raw HAR files
- session material or credential values
- request bodies or response bodies
- production or staging write-context values
- source files or repo context
- prior reviewer answers
- operator walkthrough text

## Per-review command

After reviewer 1 fills `runs/external_review_sessions/review_1/filled_reviewer_observation.md`:

```bash
make evidence-observation-summary \
  OBSERVATION=runs/external_review_sessions/review_1/filled_reviewer_observation.md \
  OBSERVATION_OUTPUT=runs/external_review_sessions/review_1
```

Repeat for `review_2` and `review_3`.

## Count rule

A session counts only when all are true:

- `reviewer_observation_summary.json` exists for that session
- summary schema is `adopt_redthread.reviewer_observation_summary.v1`
- completion summary reports `complete=true`
- configured sensitive-marker audit passed
- release decision is recorded
- trusted evidence and weak/unclear evidence are recorded
- all six silent-review answers are present

Blank templates, walked-through reviews, incomplete summaries, and marker-hit observations are not validation evidence.

## Schema

The session batch writes:

```text
adopt_redthread.external_review_session_batch.v1
```

Important fields:

- `session_status`: current batch readiness
- `validation_status`: always non-validation until filled observations are summarized
- `target_review_count`: default `3`
- `sessions`: per-review folders, allowed artifacts, expected summary paths, and summary commands
- `rollup_command`: command to aggregate the expected summaries
- `input_marker_audit` / `output_marker_audit`: configured sensitive-marker tripwires

`make evidence-external-review-distribution` reads this batch plus freshness metadata and writes the exact per-review send list under `runs/external_review_distribution/`. After summaries are generated, `make evidence-external-review-returns` reports per-review missing/incomplete/privacy/follow-up/complete status without reading filled observation markdown.

## Safety boundary

This command does not execute probes, does not run live requests, does not summarize raw reviewer text, and does not change bridge verdict semantics. It only packages sanitized review inputs into isolated session folders.
