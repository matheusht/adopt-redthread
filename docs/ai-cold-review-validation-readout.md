# AI Cold-Review Validation Readout

Date: 2026-05-01

## Purpose

Validate the reviewer packet mechanically before asking external humans to use it.

This is **not** buyer validation and not proof of market demand. It is a real no-tools AI cold-review run: each reviewer saw only the sanitized evidence report, evidence matrix, reviewer packet, and observation template.

## Protocol used

Artifacts supplied to each reviewer:

- `runs/reviewed_write_reference/evidence_report.md`
- `runs/evidence_matrix/evidence_matrix.md`
- `runs/reviewer_packet/reviewer_packet.md`
- `runs/reviewer_packet/reviewer_observation_template.md`

Forbidden inputs remained forbidden:

- raw HAR files
- session cookies or auth headers
- request/response bodies
- production or staging write-context values
- operator walkthrough before silent answers

Reviewer runs were executed with Pi in no-tools mode, with context files/skills/prompt templates/themes disabled, so reviewers could not inspect the repo or raw artifacts.

## Validation bug found before conclusions

The first summarization pass marked all three observations incomplete even though they were filled. Cause: reviewers wrote answers as inline `Answer: value`, while the parser only counted a bare `Answer:` line followed by a later line.

A second issue appeared in the rollup: reviewers answered Question 6 as `Yes, ... before release`, but repeat-review detection only counted narrower `before every release` language.

Fixes implemented:

- `scripts/summarize_reviewer_observation.py` now accepts both answer forms:
  - `Answer:` followed by the answer on later lines
  - `Answer: value` inline
- repeat-review detection now treats silent Question 6 beginning with `Yes`, `Yep`, or `Yeah` as a repeat-review request unless it starts with `No`.
- tests cover both fixes.

## Regenerated validation result

After fixing and regenerating summaries:

- complete summaries: `3/3`
- validation status: `ready_for_validation_readout`
- decisions: `review:3`
- decision consistency: `3/3 consistent`
- marker hits: `0`
- behavior-change recorded: `3`
- next-probe requested: `3`
- repeat-review requested: `3`

Rollup artifact:

- `runs/reviewer_validation/ai_cold_review_rollup/reviewer_validation_rollup.md`

## Main finding

All three AI cold reviewers selected `change`, which normalizes to project `review`.

The repeated requested next probe was tenant/user boundary evidence: verify that the actor cannot access another actor's resource identifier class.

This supports the current conservative semantics:

- the reviewed-write path should remain `review`, not `approve`;
- the packet is useful enough to trigger a targeted rerun/probe request;
- the next wording/evidence slice should prioritize tenant/user boundary evidence before adding integrations.

## Boundaries

Do not claim:

- external human validation;
- buyer demand;
- production readiness;
- full privacy proof from marker checks;
- that the tenant/user boundary risk is a confirmed vulnerability.

Do claim:

- the sanitized packet can be read cold by no-tools AI reviewers;
- parser and rollup capture now handle reviewer output formats seen in validation;
- three complete AI cold-review summaries produce a clean rollup;
- the repeated reviewer ask is tenant/user boundary evidence.

## Next validation step

Run the same protocol with external target AI/security engineers. Only after their confusion or rerun requests repeat should report/matrix wording or evidence generation be changed further.
