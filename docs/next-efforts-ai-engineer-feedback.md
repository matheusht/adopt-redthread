# Next Efforts from AI Engineer Feedback

Date: 2026-05-01

Status: first engine/reporting slice plus targeted rubric selection, boundary selector detection, auth delivery diagnostics, binding review auditability, standalone gate rationale summaries, binding-audit runtime handoff, reviewer quick-read report summaries, evidence-matrix reviewer-action guidance, dynamic not-proven report wording, report-level reviewer-action guidance, silent-reviewer checklist wording, evidence-matrix finding-type/trusted-evidence columns, report next-evidence guidance, matrix next-evidence guidance, reviewer packet handoff, reviewer packet sanitized-marker audit, reviewer observation template, reviewer packet artifact manifest, report/matrix rerun triggers, reviewer packet handoff-completeness audit, reviewer-observation summary capture, post-review wording hardening, a tiny generic RedThread evidence-contract proposal, cold-review protocol hardening, reviewer-validation rollup, no-tools AI cold-review validation, inline observation-answer parsing, repeat-review signal hardening, a sanitized tenant/user boundary next-probe plan, external human cold-review handoff packaging, tenant/user boundary execution design, boundary probe result template/validator, and boundary result report/matrix/packet/handoff surfacing implemented in `adapters/bridge/evidence_summaries.py`, `adapters/redthread_runtime/app_context.py`, `adapters/redthread_runtime/runtime_bridge_context.py`, `adapters/live_replay/workflow_bindings.py`, `adapters/live_replay/workflow_results.py`, `adapters/bridge/workflow.py`, `scripts/prepublish_gate.py`, `scripts/build_evidence_report.py`, `scripts/build_evidence_matrix.py`, `scripts/build_reviewer_packet.py`, `scripts/summarize_reviewer_observation.py`, `scripts/summarize_reviewer_validation_rollup.py`, `scripts/build_redthread_evidence_contract_proposal.py`, `scripts/build_boundary_probe_plan.py`, `scripts/build_external_review_handoff.py`, `scripts/build_boundary_execution_design.py`, and `scripts/build_boundary_probe_result.py`.

## Executive summary

The feedback confirms the right direction: strengthen the engine, not the three individual runs.

ATP, Gainly, and Venice exposed the same product gap from different angles: the reviewer trusts conservative `review`/`block` decisions, but the evidence still needs to explain **what was proven**, **what was only inferred**, **what failed because of replay/auth/environment**, and **which next attack would increase confidence**.

The next effort should make Adopt RedThread better at producing a compact, sanitized attack brief, a confidence/coverage label, and a precise decision reason. That generalizes across apps without asking humans to know what RedThread needs.

The near-term product remains unchanged:

> Adopt RedThread is a privacy-preserving pre-release evidence bridge for AI agent/tool workflows. It turns discovery artifacts into inspectable RedThread evidence and a conservative `approve` / `review` / `block` decision.

Do not turn this into a generic scanner, a broad config wizard, or a set of one-off per-app fixes.

## What the AI engineer feedback proves

1. **The evidence path is useful.** A real AI engineer said the artifacts would help test an agent/tool before release.
2. **Trust is possible when decisions stay conservative.** The reviewer trusted ATP's `review`, Gainly's technical `review`, and Venice's `block`, with caveats.
3. **Coverage quality matters as much as verdict.** ATP was stronger because workflow replay and bindings executed. Gainly was weak because it was mostly fixture/dry-run evidence. Venice was useful because it failed closed, but the block reason needs sharper wording.
4. **Humans do not reliably know what attack context RedThread needs.** The product must infer context and ask only targeted follow-up questions when a missing fact changes the decision.
5. **Tenant/user boundary evidence is the most important missing attack dimension.** Across runs, the useful question was not broad context. It was whether resource/user identifiers are server-side enforced or client-trusted.

## What it does not prove yet

- It does not prove broad production readiness.
- It does not prove RedThread can independently drive live workflow execution.
- It does not prove Gainly-style single-endpoint captures are enough for a meaningful release decision.
- It does not prove Venice has a confirmed vulnerability; the observed block was a replay/auth/session failure class, not a proven security finding.
- It does not prove buyer demand. It is positive product signal, but the next validation must measure behavior change: ship, change, or block.

## CEO / CTO / Office Hours / Senior AI Engineer synthesis

### CEO direction

Proceed, but stay narrow. The wedge is not "run more scans." The wedge is a trusted pre-release decision for AI agent/tool workflows.

The next product bet is:

> Can the engine produce a privacy-safe release review that tells an AI engineer what is proven, what is not proven, and which exact next probe would increase confidence?

Do not expand into generic scanning, compliance, production release enforcement, or broad live attack automation before this evidence loop changes a real release decision.

### CTO direction

Approve with changes. Build engine improvements that reduce operator burden:

- infer more from app context and replay state
- add fewer flags and fewer manual files
- avoid broad schemas/config wizards
- distinguish confirmed findings from auth/replay/coverage failures
- only add complexity when it improves coverage, reproducibility, trust, or false-positive control

### Office Hours direction

This is positive but still weak demand evidence. The next validation is not another demo; it is three real pre-release reviews.

For each review, ask:

> Based on this evidence, would you ship, change, or block the release?

Record what changed the engineer's mind and whether they want this before every release.

### Senior AI Engineer direction

The engine needs stronger automated context and clearer evidence language:

1. tenant/user boundary candidates
2. auth delivery diagnostics
3. workflow order and coverage
4. tool/action schema and dispatch semantics
5. data sensitivity categories and reason codes
6. binding review auditability
7. dry-run rubric rationale

## Generalizable engine improvements

### P0 — Decision reason taxonomy

Problem: `block` and `review` currently compress different realities into the same surface verdict.

Required distinction:

- `confirmed_security_finding`
- `auth_replay_failed`
- `session_or_environment_blocked`
- `insufficient_coverage`
- `tenant_boundary_unproven`
- `sensitive_write_detected`
- `binding_review_needed`
- `redthread_replay_failed`
- `manual_review_required_for_write_paths`

Why this matters:

- Venice-style `block` should not read like a confirmed vulnerability when the actual reason is replay/auth/session failure.
- Gainly-style `review` should clearly say evidence is thin and mostly fixture/dry-run based.
- ATP-style `review` should say workflow proof is strong but tenant boundary and write review remain unproven.

Suggested file anchors:

- `adapters/bridge/gate_evidence.py`
- `scripts/prepublish_gate.py`
- `scripts/build_evidence_report.py`
- `scripts/build_evidence_matrix.py`
- focused tests in `tests/test_prepublish_gate.py`, `tests/test_evidence_report.py`, and `tests/test_evidence_matrix.py`

Acceptance criteria:

- A report distinguishes security finding vs auth/replay failure vs insufficient evidence.
- Existing `approve` / `review` / `block` semantics do not change.
- No raw captured values are emitted.

### P0 — Coverage confidence model

Problem: A verdict without coverage quality can be misleading.

Add a small coverage summary:

- fixture-only
- RedThread replay only
- RedThread dry-run executed
- live safe replay executed
- live workflow replay executed
- end-to-end workflow succeeded
- response bindings applied
- auth context valid or blocked
- tenant/user boundary probed or unproven

This should be a label and reason list, not a numeric score at first.

Suggested file anchors:

- `scripts/run_bridge_pipeline.py` for summary propagation if needed
- `scripts/build_evidence_report.py`
- `scripts/build_evidence_matrix.py`
- `adapters/bridge/gate_evidence.py`

Acceptance criteria:

- Gainly-like runs are visibly labeled weak/planning-only when no workflow/live replay exists.
- ATP-like runs show stronger coverage because workflow and bindings executed.
- Venice-like runs show replay/auth blocked coverage without implying security impact.

### P0 — Automatic attack brief synthesis

Problem: Engineers should not need to know what RedThread needs. The engine should infer the first attack brief.

Generate a sanitized brief from app context and run evidence:

- observed workflow groups and operation order
- read/write/destructive action classes
- auth model and approved-context requirements
- sensitivity tags and reason categories
- candidate user/tenant/resource fields
- generic dispatch/action fields
- highest-value next probes
- targeted missing-context questions, maximum three

Example generated questions by pattern:

- chat/resource identifiers: "Can this actor access another actor's object with this identifier class?"
- generic action dispatcher: "Is the action/path dispatch allowlisted server-side for this actor?"
- user-like body field: "Is this field server-side derived/validated or trusted from the client?"

Suggested file anchors:

- `adapters/redthread_runtime/app_context.py`
- new small helper under `adapters/redthread_runtime/` or `adapters/bridge/` only if needed
- `scripts/build_evidence_report.py`
- tests near `tests/test_redthread_runtime_adapter.py` and `tests/test_evidence_report.py`

Acceptance criteria:

- Brief contains only structural metadata: field names, operation IDs, path templates, classes, tags, and questions.
- Brief does not contain raw HAR/session/header/body/request/response values.
- The report can explain why a RedThread rubric/probe was chosen.

### P1 — Targeted rubric selection

Problem: Dry-run rubric selection must match observed structure and explain itself.

General rules:

- chat/message/system prompt fields -> prompt-injection style probing
- token/secret-like body fields -> sensitive-info and session/secret-handling probing
- user/org/tenant/resource identifiers -> authorization-boundary probing
- generic action/path dispatch endpoints -> authorization/dispatch probing
- write/destructive operations -> reviewed-write and action-abuse probing

The initial goal is not a broad rubric engine. It is a small deterministic selector with report-visible rationale.

Suggested file anchors:

- RedThread dry-run case generation path in `scripts/run_redthread_dryrun.py` and runtime export paths as needed
- `scripts/build_evidence_report.py`
- tests for representative field/action patterns

Acceptance criteria:

- A Gainly-like generic action endpoint is routed toward authorization/dispatch risk, not only generic sensitive-data framing.
- Reports include one sentence explaining why the rubric was selected.
- Existing deterministic demos remain stable.

### P1 — Tenant/user boundary candidate detection

Problem: The most valuable missing attack is often cross-user or cross-tenant access, but the engine currently under-explains this.

Improve sanitized detection for:

- user/account/profile/member/customer fields
- tenant/org/workspace/company fields
- resource identifiers such as chat/conversation/project/document/order/report IDs
- route parameter slots
- body/query fields that look like actor/resource selectors

Output should be candidate classes and locations, not values.

Suggested file anchors:

- `adapters/redthread_runtime/app_context.py`
- field inventory and boundary summary tests
- evidence report/matrix summaries

Acceptance criteria:

- ATP-like chat/resource IDs create a boundary-probe recommendation.
- Venice-like user-like request fields create a server-side validation question.
- Candidate counts and reason categories appear in the report without raw values.

### P1 — Auth delivery and continuity diagnostics

Problem: A replay/auth failure should be understandable without inspecting raw headers.

Report sanitized diagnostics:

- auth mode observed structurally: cookie, bearer, api key, session, unknown
- multi-origin or multi-auth-family hints
- approved auth context required vs supplied
- approved write context required vs supplied
- auth structurally present but not applied
- replay failed due to auth/session/environment class

Suggested file anchors:

- `adapters/live_replay/request_context.py`
- live replay/workflow result summaries
- `adapters/bridge/gate_evidence.py`
- `scripts/build_evidence_report.py`

Acceptance criteria:

- Venice-like runs explain whether the block is missing context, expired/invalid session, replay mismatch, or server rejection class.
- No raw auth headers, cookies, tokens, or session values are printed.

### P2 — Binding review auditability

Problem: Applied bindings should be inspectable without requiring raw values.

For each binding summary, report:

- inferred vs declared vs approved vs pending/rejected/replaced
- source field name and target field/path class
- whether it was applied at runtime
- whether it changed a later request structurally
- why it was allowed or held for review

Suggested file anchors:

- `adapters/live_replay/workflow_bindings.py`
- `adapters/live_replay/workflow_results.py`
- `scripts/build_evidence_report.py`
- tests around existing binding review/support files

Acceptance criteria:

- ATP-like runs no longer show confusing states where bindings applied but review/audit evidence looks empty.
- The report remains sanitized and does not show bound values.

## Run-specific examples, not one-off roadmap

### ATP Tennis

Use ATP as the regression example for strong workflow proof plus missing boundary proof.

General lesson:

- end-to-end workflow + applied bindings increase confidence
- write paths should remain `review`
- tenant/resource boundary must still be tested or explicitly marked unproven

Do not hand-fix ATP to look better. Use it to test boundary-question generation and binding auditability.

### Gainly

Use Gainly as the regression example for weak evidence and generic action dispatch risk.

General lesson:

- one fixture plus dry-run is not enough for a strong release review
- token/secret-like body fields and generic dispatch fields should raise stronger auth/dispatch questions
- reports need to label this as thin evidence, not a meaningful pre-release test result

Do not treat the current `review` as strong evidence. Use it to test coverage confidence and rubric selection.

### Venice

Use Venice as the regression example for strong app-context inference plus auth/replay-blocked ambiguity.

General lesson:

- sensitivity and identity-like field detection are valuable
- auth/session/replay failure must be distinguished from a confirmed security finding
- user-like fields in write/inference requests should trigger server-side validation questions

Do not downgrade or upgrade the verdict for optics. Use it to test decision reason taxonomy and auth delivery diagnostics.

## Recommended next implementation slice

Build the smallest engine/reporting slice that improves all three run classes:

1. Add a sanitized `decision_reason_summary` / `coverage_summary` to workflow summaries and reports.
2. Add an `attack_brief_summary` derived from existing `app_context.v1` fields.
3. Add report/matrix sections that expose:
   - decision reason category
   - coverage confidence label
   - top targeted probe/question
   - rubric selection rationale when dry-run exists

Keep this implementation inside existing scripts/adapters. No new dependencies, no schema upstreaming, no broad live execution changes.

## Acceptance criteria for the next slice

- ATP-like evidence shows: strong workflow coverage, reviewed write, boundary unproven, binding audit visible.
- Gainly-like evidence shows: weak/fixture-only coverage, token-like/dispatch risk, recommended auth/dispatch probe.
- Venice-like evidence shows: auth/replay/session-blocked reason, not confirmed vulnerability; user-boundary validation question surfaced.
- `approve` / `review` / `block` decisions remain unchanged.
- Report output stays sanitized.
- Focused tests cover the three pattern classes.
- Existing deterministic demos and full test suite still pass.

## What not to do

- Do not hand-fix ATP, Gainly, or Venice as separate bespoke paths.
- Do not force `approve` for a cleaner demo.
- Do not treat replay/auth failure as a confirmed vulnerability.
- Do not add a broad user-facing attack-context wizard.
- Do not add dependencies or external scanners.
- Do not broaden live writes or production execution.
- Do not expose raw HAR/session/cookie/auth/header/body/request/response values.
- Do not upstream a RedThread contract until these summaries are understandable and useful in reviewer tests.

## Open validation questions for the next 3 pre-release reviews

Ask after the reviewer reads the report/matrix without explanation:

1. Based on this evidence, would you ship, change, or block the release?
2. What part of the decision did you trust most?
3. What part was still unclear or too weak?
4. Did the attack brief identify the next probe you would run?
5. Did the report distinguish confirmed issue vs auth/replay failure vs insufficient evidence?
6. Would you want this before every release of this agent/tool?

Behavior-change success signal:

- at least one reviewer changes a release decision, adds a fix, or asks to run the review again before shipping.
