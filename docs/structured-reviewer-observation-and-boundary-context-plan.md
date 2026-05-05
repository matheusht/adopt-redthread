# Structured Reviewer Observation + Boundary Context Plan

## North star

Turn sanitized evidence from **safe but cautious** into **decision-useful** by adding structured reviewer observations and boundary context while keeping RedThread as the final assurance gate.

The current sanitized HAR → intent review → RedThread evidence bridge is working safely: it avoids raw HAR exposure, avoids live execution by default, and does not claim findings or severity. Its current output is intentionally cautious because the subjects lack the product context needed to explain why a workflow matters and what boundary RedThread should evaluate.

This plan focuses on outcomes and impact first. CTO-level implementation details such as exact schema validation, parser behavior, enum naming, malformed input handling, and test matrix depth can follow after the product direction is locked.

## Product principles

- Adopt RedThread prepares sanitized evidence, hypotheses, gaps, questions, and export artifacts.
- RedThread owns final evaluation, confirmed findings, severity, promotion gates, and release decisions.
- Reviewer observations are human confidence signals, not final security verdicts.
- Boundary context is an evidence unlock, not proof that a boundary was crossed or protected.
- No raw HARs, raw paths, URLs, headers, cookies, request/response bodies, auth values, IDs, app field names, or secrets should be introduced into this workflow.
- No live endpoint execution should happen by default.
- The LLM should become more useful because the packet is better, not because the model is asked to be bolder.

## Phase 1 — Outcome framing: make cautious reviews actionable

### Outcome

Every review artifact should make clear whether the next product action is:

- more context needed
- reviewer confidence increased
- change required before release
- block should be considered by RedThread
- not enough evidence to advance

These are review-support outcomes, not replacements for RedThread verdicts.

### Impact

- Moves the pipeline from a generic uncertainty report to release decision support.
- Makes `review` useful instead of feeling like a conservative fallback.
- Helps operators understand why a subject cannot advance without overstating proof.

### Milestones

- Document the review-support outcome labels.
- Add outcome language to the plan/reporting docs.
- Make every subject summary answer:
  - what became clearer?
  - what remains unproven?
  - what decision-support action should happen next?

### Decision gate

Reviewers can read the sanitized packet and understand the next action without interpreting `unknown` as failure or as a final verdict.

## Phase 2 — Structured reviewer observations: turn human review into reusable signal

### Outcome

Reviewer feedback becomes structured product signal instead of free-form commentary.

### Impact

- Reduces ambiguity around why a subject matters.
- Makes review packets comparable across subjects and batches.
- Gives the intent review enough sanitized context to become less uniform.
- Creates reusable evidence for RedThread without leaking raw operational details.

### Milestones

- Define a reviewer observation intake focused on:
  - why the subject was selected
  - observed behavior summary
  - confidence level
  - evidence that changed the reviewer’s mind
  - uncertainty that remains
  - relevant boundary or policy area
  - reviewer questions or notes
- Keep the observation framed as sanitized review context only.
- Surface observation presence/absence in the subject summary and missing-context summary.

### Decision gate

Given the same sanitized packet, multiple reviewers can produce comparable observations that explain the subject’s relevance without adding raw details.

## Phase 3 — Boundary context intake: unlock the main confidence gap

### Outcome

The system can distinguish subjects that are blocked because boundary context is missing from subjects where boundary context is ready for RedThread evaluation.

### Impact

- Targets the largest current blocker in the 8-subject proof: missing boundary context.
- Helps reviewers ask for specific context instead of broad follow-up.
- Improves RedThread handoff quality while avoiding premature findings.

### Milestones

- Define boundary context as approved, sanitized setup metadata.
- Capture only the decision-useful context class, such as:
  - boundary or policy area
  - whether non-production approval exists
  - whether actor separation is available
  - whether tenant/user scope is represented as a sanitized class
  - whether safe execution constraints are known
  - whether approval has an owner and expiration concept
- Report boundary state separately from execution or proof:
  - boundary context missing
  - boundary context ready
  - boundary probe not executed
  - boundary evidence observed

### Decision gate

A subject with boundary context can advance to a more specific RedThread-ready evidence packet without implying that live execution occurred or that a finding was confirmed.

## Phase 4 — Deterministic missing-context summary: explain why each subject cannot advance

### Outcome

Each subject gets a simple advancement state that explains what is missing and what the next action is.

### Impact

- Turns cautious output into an operator checklist.
- Reduces repeated manual interpretation of `ready_with_gaps`.
- Makes the batch useful even when no subject is fully RedThread-ready.

### Milestones

- Add subject-level advancement states such as:
  - needs boundary context
  - needs reviewer observation
  - ready for RedThread evaluation
  - not a confirmed finding
- Explain blockers in outcome language rather than implementation language.
- Summarize batch-level blockers so the operator can see the dominant next action.

### Decision gate

An operator can answer “what must happen next for this subject?” from the summary alone.

## Phase 5 — Small proof: show the packet becomes more specific while staying safe

### Outcome

Run a focused proof on 1–2 subjects with sanitized reviewer observations and boundary context.

### Impact

- Proves the next phase improves usefulness, not just artifact count.
- Tests whether richer sanitized context changes the review from uniform caution to targeted advisory output.
- Confirms RedThread ownership and privacy constraints still hold.

### Milestones

- Select 1–2 representative subjects from the existing sanitized batch.
- Add sanitized reviewer observations and boundary context for those subjects only.
- Rerun deterministic review.
- Prepare guarded LLM prompt/output validation using offline model output only.
- Compare before/after:
  - fewer generic `unknown` explanations for proof subjects
  - more specific missing-evidence questions
  - no confirmed finding claims
  - no severity claims
  - no live execution claims
  - RedThread evaluation still required

### Decision gate

At least one proof subject becomes more decision-useful without weakening privacy, safety, or RedThread final-gate semantics.

## Phase 6 — RedThread final-gate alignment: keep ownership clean

### Outcome

Reviewer observations and boundary context improve the evidence package, but RedThread remains the only final security decision gate.

### Impact

- Prevents the bridge from becoming a parallel scanner or policy engine.
- Keeps trust boundaries clear for future integration.
- Makes the pipeline safer to scale across more subjects and teams.

### Milestones

- Document ownership boundaries:
  - reviewer observations = human confidence signal
  - boundary context = approved setup signal
  - intent review = sanitized hypotheses, gaps, and questions
  - RedThread = final evaluation and promotion gate
- Keep reports explicit that no security conclusion is final until RedThread evaluates.
- Ensure outcome labels are decision-support language, not final verdict language.

### Decision gate

The improved report is more useful but still cannot be mistaken for a confirmed finding, severity rating, scanner result, or release override.

## Phase 7 — Business validation loop: prove this changes real decisions

### Outcome

Validate that structured observations and boundary context influence real release conversations.

### Impact

- Moves the work from technical proof to product proof.
- Establishes whether teams would want this before every release.
- Creates early product metrics around decision usefulness.

### Milestones

- Run 3 sanitized pre-release reviews.
- For each review, capture:
  - did reviewer confidence increase?
  - did the packet create a change request?
  - did missing boundary context block advancement?
  - did the report reduce ambiguity?
  - would the team want this in the release workflow?
- Track simple outcome metrics:
  - percentage of subjects with clear next action
  - percentage blocked by missing boundary context
  - percentage with useful reviewer observations
  - percentage ready for RedThread evaluation
  - number of concrete product/code/security changes requested

### Decision gate

The evidence loop changes at least one real release decision, creates a concrete requested change, or materially reduces review ambiguity.

## What we defer to CTO

This plan intentionally defers implementation mechanics until the outcome direction is accepted:

- exact JSON schema shape
- enum naming
- input parser behavior
- malformed input handling
- field-level validation rules
- privacy marker implementation details
- test matrix depth
- CLI flag naming
- error class design
- artifact inventory details

The product requirements that should not be deferred are:

- no raw HAR or secret exposure
- no live execution by default
- no confirmed finding or severity claims from Adopt RedThread
- RedThread remains the final gate
- reviewer and boundary context must improve decision usefulness without overstating proof

## Phase 1–3 implementation start

The initial implementation should keep this outcome-first and small:

- expose review-support outcome labels in the sanitized context and Markdown summary;
- accept optional sanitized boundary context and reviewer observation intake files;
- enrich only the supplied proof subjects, leaving the rest of the batch cautious;
- use enriched context to make the advisory intent label, reviewer question, and next action more specific;
- continue to require RedThread for final evaluation.

Example proof run:

```bash
make evidence-intent-review \
  HAR_BATCH_OUTPUT=runs/har_batches/latest \
  INTENT_REVIEW_OUTPUT=runs/har_batches/latest/intent_review_with_context \
  INTENT_REVIEW_BOUNDARY_RUBRIC=fixtures/sanitized_intent_review/boundary_rubric.example.json \
  INTENT_REVIEW_REVIEWER_OBSERVATIONS=fixtures/sanitized_intent_review/reviewer_observations.example.json
```

## Near-term implementation sequence

1. Document outcome labels and advancement states.
2. Add structured reviewer observation intake for 1–2 proof subjects.
3. Add boundary context intake for those same proof subjects.
4. Add deterministic missing-context summary.
5. Rerun the existing 8-subject batch.
6. Compare proof subjects against the other cautious subjects.
7. Run guarded offline LLM validation.
8. Decide whether the output is now decision-useful enough to harden schemas and validation.

## Implemented phase 4–7 outputs

The phase 4–7 implementation adds these decision-support artifacts:

- `advancement_summary.json` / `advancement_summary.md`: per-subject advancement state, blockers, next action, and RedThread final-gate reminder.
- `business_validation_plan.json`: lightweight business validation loop for proving whether enriched sanitized packets affect release review usefulness.

These artifacts are intentionally advisory. They do not claim findings, severity, scanner results, live execution proof, or release overrides.

## Success criteria

This phase succeeds when:

- the 8-subject review still passes privacy and schema checks;
- 1–2 enriched subjects produce more specific advisory output;
- non-enriched subjects remain appropriately cautious;
- every subject has a clear next action;
- no output claims a confirmed finding, severity, scanner result, exploitability, live execution, or release override;
- RedThread evaluation remains required for final security conclusions.
