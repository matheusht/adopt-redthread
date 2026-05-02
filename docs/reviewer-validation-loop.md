# Reviewer Validation Loop

This document defines the narrow post-packet validation loop for Adopt RedThread.

The goal is not to add another scanner, integration, or live execution path. The goal is to find out whether a cold reviewer can read the sanitized evidence and make a real ship/change/block judgment without a walkthrough.

## Scope

Allowed evidence:

- `runs/reviewed_write_reference/evidence_report.md`
- `runs/evidence_matrix/evidence_matrix.md`
- `runs/reviewer_packet/reviewer_packet.md`
- `runs/reviewer_packet/reviewer_observation_template.md` after the reviewer has answered silently
- `runs/boundary_probe_result/tenant_user_boundary_probe_result.md` when present; current default is a sanitized `blocked_missing_context` result, not execution proof
- `runs/reviewer_packet/reviewer_observation_summary.{md,json}` after summarization
- `runs/reviewer_validation/reviewer_validation_rollup.{md,json}` after multiple summaries exist

Forbidden evidence:

- raw HAR files
- session cookies or auth headers
- request bodies or response bodies
- production or staging write context values
- operator explanations before silent answers
- app-specific secret/session/account values copied into observations

## Cold-review protocol

1. Build the sanitized artifacts:

   ```bash
   make evidence-report
   make evidence-matrix
   make evidence-packet
   ```

   If boundary result evidence should be included, generate it before rebuilding the packet/handoff:

   ```bash
   make evidence-boundary-probe-plan
   make evidence-boundary-execution-design
   make evidence-boundary-probe-result
   make evidence-report
   make evidence-matrix
   make evidence-packet
   ```

   The default boundary result is `blocked_missing_context`; it is not proof that a boundary probe executed.

2. For an external human review, build the sanitized handoff directory:

   ```bash
   make evidence-external-review-handoff
   make evidence-external-review-sessions
   make evidence-freshness
   make evidence-readiness
   make evidence-external-review-distribution
   make evidence-remediation-queue
   ```

   The handoff is documented in [`docs/external-human-cold-review-handoff.md`](external-human-cold-review-handoff.md). The isolated session folders are documented in [`docs/external-review-session-batch.md`](external-review-session-batch.md). Freshness/readiness are documented in [`docs/evidence-freshness-manifest.md`](evidence-freshness-manifest.md) and [`docs/evidence-readiness-ledger.md`](evidence-readiness-ledger.md). The distribution manifest is documented in [`docs/external-review-distribution-manifest.md`](external-review-distribution-manifest.md), and the remediation queue is documented in [`docs/evidence-remediation-queue.md`](evidence-remediation-queue.md). These are packaging/state checks only, not validation by themselves.

3. Give each reviewer only one generated session folder's sanitized artifacts and blank observation file.

4. Ask the reviewer to answer the six silent-review questions before any explanation:

   - Based on this evidence, would you ship, change, or block the release?
   - What part of the decision did you trust most?
   - What part was still unclear or too weak?
   - Did the attack brief identify the next probe you would run?
   - Did the evidence distinguish confirmed issue vs auth/replay failure vs insufficient evidence?
   - Would you want this before every release of this agent/tool?

5. Have the reviewer fill a copy of:

   ```text
   reviewer_observation_template.md
   ```

6. Summarize the filled template. For one-off local use, the default output is `runs/reviewer_packet/`; for multiple reviewers, write each summary to a separate output directory:

   ```bash
   make evidence-observation-summary OBSERVATION=/path/to/filled_reviewer_observation_template.md \
     OBSERVATION_OUTPUT=runs/reviewer_validation/review_1
   ```

   The parser accepts both template styles reviewers commonly produce:

   ```text
   Answer:
   change
   ```

   and:

   ```text
   Answer: change
   ```

7. Treat incomplete summaries as non-validation evidence:

   ```text
   incomplete_not_reviewer_evidence
   ```

## Single-review output

The observation summary records:

- completion status
- release decision normalized to `approve`, `review`, `block`, `unsure`, or `unrecorded`
- consistency between metadata decision and silent Question 1
- whether behavior change was recorded
- whether a next probe was requested
- whether trusted evidence and weak/unclear evidence were recorded
- whether silent Question 6 indicates repeat review before release, including `Yes, ... before release` wording
- configured sensitive-marker audit status

The summary is still only one reviewer signal. It is not proof of product demand by itself.

## Multi-review rollup

After multiple cold reviews, aggregate only the sanitized summary JSON files:

```bash
make evidence-validation-rollup SUMMARIES="/path/to/summary1.json /path/to/summary2.json /path/to/summary3.json"
```

Default local command:

```bash
make evidence-validation-rollup
```

This writes:

```text
runs/reviewer_validation/reviewer_validation_rollup.md
runs/reviewer_validation/reviewer_validation_rollup.json
```

For the generated external session batch, you can also run:

```bash
make evidence-external-validation-readout
make evidence-freshness
make evidence-readiness
make evidence-remediation-queue
```

This writes:

```text
runs/external_validation_readout/external_validation_readout.md
runs/external_validation_readout/external_validation_readout.json
```

The rollup and readout intentionally read `reviewer_observation_summary.json` files, not raw observations or raw run artifacts. The readiness ledger remains `waiting_for_external_validation` until enough complete sanitized summaries exist.

## Rollup status values

| Status | Meaning |
|---|---|
| `privacy_blocked` | At least one input summary or source summary marker audit indicates configured sensitive-marker exposure. Do not use as validation evidence until redacted/regenerated. |
| `needs_valid_observation_summaries` | One or more input files are missing, invalid JSON, or not the expected observation-summary schema. |
| `needs_more_complete_reviews` | Fewer than three complete cold-review summaries exist. Keep collecting reviewer signals. |
| `needs_decision_language_followup` | At least one review has inconsistent metadata vs silent Question 1 decision. Clarify wording before product conclusions. |
| `ready_for_validation_readout` | At least three complete, schema-valid, marker-clean, decision-consistent summaries are present. |

Three complete reviews is a minimum readout threshold, not a statistical claim.

## Theme counts

The rollup does not copy free-form reviewer answer text. It buckets reviewer confusion/next-probe text into bounded themes:

- `tenant_user_boundary`
- `coverage_strength`
- `confirmed_vs_replay_language`
- `write_context`
- `redthread_vs_bridge_ownership`
- `artifact_navigation`

Use these counts to decide the next wording or evidence slice. Do not treat them as vulnerability findings.

## AI cold-review validation note

On 2026-05-01, three separate no-tools Pi cold-review runs were given only the sanitized report, matrix, reviewer packet, and observation template. This is real AI-review validation of the packet mechanics, not external buyer or human-security-review validation.

The run found two parser issues before product conclusions were drawn:

- reviewers commonly returned `Answer: value` inline, while the first parser only counted `Answer:` followed by a later line;
- reviewers answered Question 6 as `Yes, ... before release`, while the first repeat-review detector only counted narrower `before every release` language.

Both issues are now fixed. After regeneration, all three AI cold-review summaries were complete, marker-clean, decision-consistent, and rolled up as `ready_for_validation_readout`; all three selected `change`/project `review`, requested a tenant/user boundary probe, and treated the packet as useful before release.

Do not overclaim this as demand validation. The next stronger validation is still external target reviewers using the same sanitized protocol.

## Decision rule

Only change report/matrix/packet wording after real reviewers show confusion.

Only add new probes or execution paths when reviewer-requested evidence requires it and the existing safety envelope allows it.

Do not upstream the RedThread evidence contract until target AI engineers can explain the evidence and decision back correctly.
