# External Human Cold-Review Handoff

## Purpose

This handoff is for real external reviewers. It packages the sanitized evidence artifacts so a reviewer can decide whether they would ship, change, block, or remain unsure without seeing raw run material or getting an operator walkthrough.

This is not validation by itself. It becomes validation evidence only after filled reviewer observations are summarized and rolled up.

## Build the handoff

Regenerate the base evidence first:

```bash
make evidence-report
make evidence-matrix
make evidence-packet
```

Then build the external handoff directory:

```bash
make evidence-external-review-handoff
```

Generated local output:

```text
runs/external_review_handoff/
├── evidence_report.md
├── evidence_matrix.md
├── reviewer_packet.md
├── reviewer_observation_template.md
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

Repeat for reviewers 2 and 3 with separate output directories.

Then roll up the three sanitized summaries:

```bash
make evidence-validation-rollup \
  SUMMARIES="runs/reviewer_validation/review_1/reviewer_observation_summary.json runs/reviewer_validation/review_2/reviewer_observation_summary.json runs/reviewer_validation/review_3/reviewer_observation_summary.json"
```

## Interpretation

- `ready_for_validation_readout` means the mechanics produced enough complete sanitized summaries to discuss the result.
- It does not prove buyer demand.
- It does not prove production readiness.
- It does not mean RedThread owns the final bridge gate verdict.
- If reviewers repeatedly ask for tenant/user boundary proof, prioritize that evidence before adding integrations.
