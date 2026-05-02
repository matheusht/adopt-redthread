# External Human Cold-Review Handoff

## Purpose

This handoff is for real external reviewers. It packages the sanitized evidence artifacts so a reviewer can decide whether they would ship, change, block, or remain unsure without seeing raw run material or getting an operator walkthrough.

This is not validation by itself. It becomes validation evidence only after filled reviewer observations are summarized and rolled up.

## Build the handoff

Regenerate the base evidence first. If the boundary result artifact should be visible in the packet, build it before rebuilding report/matrix/packet:

```bash
make evidence-boundary-probe-plan
make evidence-boundary-execution-design
make evidence-boundary-probe-result
make evidence-report
make evidence-matrix
make evidence-packet
```

If no boundary result artifact exists, the packet/handoff preserves the existing absent/`tenant_user_boundary_unproven` wording.

Then build the external handoff directory and isolated reviewer sessions:

```bash
make evidence-external-review-handoff
make evidence-external-review-sessions
make evidence-freshness
make evidence-readiness
make evidence-external-review-distribution
make evidence-remediation-queue
```

The handoff directory is the source package. The session batch copies only those sanitized files into `runs/external_review_sessions/review_*` folders with one blank observation per reviewer. The freshness/readiness commands verify copied artifact hashes and report the current non-validation/waiting state before distribution. The distribution manifest is the exact per-review send list; the remediation queue records the remaining external-review and boundary-context work.

Generated local handoff output:

```text
runs/external_review_handoff/
├── evidence_report.md
├── evidence_matrix.md
├── reviewer_packet.md
├── reviewer_observation_template.md
├── tenant_user_boundary_probe_result.md  # only when present
├── external_reviewer_instructions.md
└── external_review_handoff_manifest.json
```

`runs/` remains ignored. Do not commit filled observations or local review outputs unless they have been manually reviewed for privacy.

## Allowed reviewer inputs

Give the reviewer only these files:

- `evidence_report.md`
- `evidence_matrix.md`
- `reviewer_packet.md`
- `reviewer_observation_template.md`
- `tenant_user_boundary_probe_result.md` when present; current default is `blocked_missing_context`, not execution proof
- `external_reviewer_instructions.md`

Do not give repo access, terminal access, raw captures, source code, walkthrough explanations, or prior reviewer answers before they answer the silent-review questions.

## Forbidden inputs

Never include:

- raw HAR files
- session material or credential values
- request or response bodies
- production or staging write-context values
- source files or repo context
- operator explanation before silent answers

## Review count rule

A review counts only when all are true:

- observation summary reports `complete=true`
- configured sensitive-marker audit passed
- release decision is recorded
- trusted evidence is recorded
- unclear or weak evidence is recorded
- all six silent-review answers are present

Incomplete, walked-through, or marker-hit observations are not validation evidence.

## Per-review capture flow

For reviewer 1:

```bash
make evidence-observation-summary \
  OBSERVATION=/path/to/reviewer_1_filled_observation.md \
  OBSERVATION_OUTPUT=runs/reviewer_validation/review_1
```

Repeat for reviewers 2 and 3 with separate output directories. If using the generated session batch, the per-review output directories are already `runs/external_review_sessions/review_1`, `review_2`, and `review_3`.

Then roll up the three sanitized summaries directly:

```bash
make evidence-validation-rollup \
  SUMMARIES="runs/reviewer_validation/review_1/reviewer_observation_summary.json runs/reviewer_validation/review_2/reviewer_observation_summary.json runs/reviewer_validation/review_3/reviewer_observation_summary.json"
```

Or build the external-specific readout from the session batch's expected summary paths:

```bash
make evidence-external-validation-readout
```

## Interpretation

- `waiting_for_filled_external_observations` means no external reviewer summaries are present yet.
- `ready_for_validation_readout` in the generic rollup, or `ready_for_external_validation_readout` in the external readout, means the mechanics produced enough complete sanitized summaries to discuss the result.
- It does not prove buyer demand.
- It does not prove production readiness.
- It does not mean RedThread owns the final bridge gate verdict.
- If reviewers repeatedly ask for tenant/user boundary proof, prioritize that evidence before adding integrations.
