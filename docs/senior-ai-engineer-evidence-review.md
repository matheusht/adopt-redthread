# Senior AI Engineer Evidence Review

This is an internal reviewer-pass using the `.pi/agents/senior-ai-engineer.md` posture. It is not a substitute for watching an external target AI engineer read the artifacts silently.

Reviewed artifacts:

- `runs/reviewed_write_reference/evidence_report.md`
- `runs/evidence_matrix/evidence_matrix.md`
- `runs/victoria/evidence_report.md`
- `docs/project-direction.md`
- `docs/reviewed-write-reference-demo.md`

## 1. Verdict

approve with changes

The evidence path is useful and directionally trustworthy. The new sanitized app context helps RedThread-facing review because it names the auth model, sensitivity tags, and operation/schema counts without exposing run data. The main remaining issue is reviewer comprehension: the matrix does not yet show app-context fields, and a reader still needs repo knowledge to understand exactly what RedThread consumed versus what the local bridge gate decided.

## 2. Direct answer to the three reviewer questions

### Would this help you test an agent/tool before release?

Yes. The report/matrix helps answer the release question better than a raw HAR or log bundle:

- what input was tested
- whether workflow replay ran
- whether bindings were applied
- what RedThread replay/dry-run did
- why the local gate returned `approve`, `review`, or `block`

The reviewed-write result is especially useful because it refuses to convert a write-capable path into a fake `approve`.

### What context is missing for RedThread to attack better?

Minimum missing context, ranked:

1. Concrete tenant/user boundary evidence: which fields or route slots imply tenant/user separation when the summary currently reports zero candidates.
2. Per-operation read/write/destructive classification in the reviewer-facing summary, not only buried in fixtures/gate behavior.
3. Binding-critical fields: which response fields are needed by later requests, summarized without values.
4. Auth continuity requirement per workflow: whether the same auth context must persist across steps.
5. Data-sensitivity reason codes: why a tag such as `pii_like` or `support_message_like` was inferred.

### Would you trust this `approve`, `review`, or `block` decision?

Mostly yes for the demonstrated scope.

- `approve`: trustworthy only for the deterministic safe-read demo, not as a claim about the whole app.
- `review`: trustworthy for reviewed-write reference evidence because the workflow succeeded, RedThread replay passed, and write-path risk still requires a human checkpoint.
- `block`: trustworthy for Victoria because missing approved staging write context is a real blocker and the system failed closed.

## 3. Confusion log

- The evidence matrix is the clearest high-level artifact, but it does not yet show the new app-context summary.
- The reviewed-write report says `Candidate user fields: 0` and `Candidate tenant fields: 0` while auth scope hints include user/tenant scoped. That is plausible but needs explanation or better extraction.
- A reader may not know that RedThread replay/dry-run is evidence while the final `approve/review/block` still comes from this repo's local gate.
- `Dry-run case: get_api_chats` is technically useful but does not explain why that case was selected.
- Victoria's report is clear about `missing_write_context`, but it should be regenerated through the current report builder if we want it to show app context too.

## 4. Missing RedThread context, ranked

1. Tenant/user boundary fields and route slots.
2. Per-operation action class: read, write, destructive, auth-required.
3. Workflow state dependencies: response fields that feed later requests.
4. Auth continuity and approved-context requirements per step.
5. Sensitivity tag evidence reasons.

## 5. Trust assessment of approve/review/block

The decisions are credible because they preserve the safety semantics:

- safe deterministic read path can approve
- write-capable path remains review
- missing approved staging/write context blocks

Do not move these semantics upstream until one external reviewer can explain the decision back from the report without walkthrough.

## 6. Recommended next action

Run one silent reviewer test with a target AI engineer:

1. Give them `runs/evidence_matrix/evidence_matrix.md` first.
2. Then give them `runs/reviewed_write_reference/evidence_report.md`.
3. Ask only:
   - Would this help you test an agent/tool before release?
   - What context is missing for RedThread to attack better?
   - Would you trust this decision?
4. Record confusion verbatim.
5. Only after that, tighten the report/matrix wording and propose a tiny generic RedThread context/verdict contract.

## 7. What not to do

- Do not upstream a broad schema yet.
- Do not add another scanner or integration.
- Do not run Victoria writes without approved non-production staging context.
- Do not force reviewed-write evidence into `approve`.
- Do not commit raw `runs/` artifacts or HAR-derived values.

## 8. Venice internal proxy review — 2026-04-30

This was an internal proxy review using the Senior AI Engineer posture, not external validation.

Reviewed artifacts:

- `runs/evidence_matrix/evidence_matrix.md`
- `runs/reviewed_write_reference/evidence_report.md`
- `runs/venice/evidence_report.md`

Sanitized Venice result:

- fixtures: `15`
- workflows: `2`
- workflow classes: `reviewed_write_workflow:2`
- live workflow replay: executed, `0` successful, `2` blocked, `0` aborted
- blocker reasons: `missing_auth_context:1`, `missing_write_context:1`
- response bindings: `0/0/0` planned/applied/unapplied
- RedThread replay: passed
- RedThread dry-run: executed
- local bridge gate decision: `block`
- app context: `app_context.v1`, `15` operations, `15` tool/action schemas, action classes `read:8,write:7`, auth mode `bearer`, approved auth context required, approved write context required, sensitivity tags `pii_like,secret_like,support_message_like,user_data`

Direct answers:

1. Would this help test an agent/tool before release? Yes. Venice demonstrates the useful fail-closed case: RedThread evidence can pass while the local gate still blocks because the workflow needs approved auth/write context before execution.
2. What context is missing for RedThread to attack better? Still missing: stronger tenant boundary evidence, sensitivity reason codes, and clearer dry-run case-selection rationale.
3. Would you trust this decision? Yes for the demonstrated scope. The `block` decision is correct because no approved auth/write context was supplied and no write step executed.

Reporting changes made after this review:

- evidence reports now explicitly distinguish RedThread evidence from the local bridge gate decision
- app context now summarizes action classes and splits approved auth context from approved write context
- evidence matrix now includes app-context, auth-context, and sensitivity columns

Remaining validation gap: one real external AI engineer still needs to read the matrix and report without explanation and explain the decision back correctly before any generic RedThread contract is drafted or upstreamed.
