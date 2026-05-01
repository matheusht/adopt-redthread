# Impact Implementation Log

## 2026-04-25 — architecture review and first implementation slice

### Architecture review result

The execution plan is architecturally correct.

The repo boundary remains clean:

- `adopt-redthread` owns integration, capture-derived workflow planning, bounded live replay, operator review artifacts, and demo proof.
- `redthread` owns generic replay/gate models and security assurance behavior.

The important quality guardrail is that RedThread receives only a generic workflow trust context. It does not import ZAPI/HAR/NoUI/Adopt-specific bridge code.

### Implemented in `adopt-redthread`

#### Runtime-row binding truth

Executed workflow step evidence now includes row-level binding truth:

- `planned_response_bindings`
- `applied_response_bindings`
- `binding_application_summary`

This lets an operator compare:

1. the binding was declared/planned
2. the binding was approved or pending review
3. the binding was actually applied during replay
4. the binding failed before request execution, with the failed binding id preserved

Primary code touched:

- `adapters/live_replay/workflow_bindings.py`
- `adapters/live_replay/workflow_state.py`
- `adapters/live_replay/workflow_executor.py`
- `adapters/live_replay/workflow_results.py`

#### Workflow replay summary truth

`live_workflow_replay.json` now includes top-level:

- `binding_application_summary.planned_response_binding_count`
- `binding_application_summary.applied_response_binding_count`
- `binding_application_summary.unapplied_response_binding_count`
- workflow counts for planned/applied binding usage
- `binding_application_failure_counts`
- `failed_binding_ids`

This makes runtime binding behavior visible without inspecting each individual step.

#### Gate and runtime handoff truth

`redthread_runtime_inputs.json` now carries the richer `bridge_workflow_context` shape, including runtime binding application counts when live workflow replay has run.

The bridge now rebuilds runtime inputs after live workflow replay so RedThread receives current runtime evidence instead of only pre-run planning context.

Gate evidence and notes now surface binding application facts:

- `live_workflow_planned_response_binding_count=...`
- `live_workflow_applied_response_binding_count=...`
- `live_workflow_unapplied_response_binding_count=...`
- `live_workflow_binding_application_failures=...`
- workflow counts with planned/applied bindings

Primary code touched:

- `adapters/redthread_runtime/runtime_bridge_context.py`
- `adapters/redthread_runtime/runtime_adapter.py`
- `adapters/bridge/workflow.py`
- `adapters/bridge/gate_evidence.py`
- `scripts/prepublish_gate.py`

### Implemented in `redthread`

RedThread now accepts and surfaces a generic workflow trust context on replay bundles:

- `ReplayBundle.bridge_workflow_context`
- `evaluate_agentic_promotion(...)["bridge_workflow_context"]`

This is intentionally passive for now. RedThread surfaces the context but does not enforce new policy on it yet.

Primary code touched:

- `../redthread/src/redthread/evaluation/replay_corpus.py`
- `../redthread/src/redthread/evaluation/promotion_gate.py`

### Tests added/updated

Updated bridge tests verify:

- reviewed alias body binding appears in planned and applied step evidence
- workflow replay summaries include binding application counts
- RedThread runtime exports include the same workflow context both top-level and inside `redthread_replay_bundle`
- prepublish gate notes include planned/applied binding counts

Updated RedThread tests verify:

- replay bundle context validates
- promotion gate verdict surfaces workflow context
- default context remains `{}` when absent

### Verification run

Focused bridge pack:

```bash
python3 -m unittest \
  tests.test_reviewed_binding_alias_builder \
  tests.test_reviewed_binding_alias_loop \
  tests.test_live_workflow_binding_review \
  tests.test_live_workflow_bindings \
  tests.test_live_workflow_binding_body_inference \
  tests.test_workflow_review_manifest_phase_c \
  tests.test_redthread_runtime_adapter \
  tests.test_prepublish_gate \
  tests.test_bridge_workflow \
  -v
```

Result:

- `Ran 24 tests`
- `OK`

Focused RedThread pack:

```bash
../redthread/.venv/bin/python -m pytest \
  ../redthread/tests/test_agentic_replay_promotion.py \
  -q
```

Result:

- `6 passed`

### Hero proof artifact

A deterministic hero proof was generated under:

```text
runs/hero_binding_truth/
```

Documented in:

```text
docs/hero-flow-binding-truth.md
```

The key operator proof is:

- planned response bindings: `2`
- applied response bindings: `2`
- unapplied response bindings: `0`
- binding application failures: none
- gate decision: `approve`

This is intentionally deterministic and credential-free. The external ATP app run remains useful as a real-world bounded-streaming proof, but the deterministic hero artifact is the clean runtime-row binding proof.

## 2026-04-29 — proof boundary reconciliation

### Direction clarified

The repo now documents the honest decision boundary:

- live workflow execution is currently owned by `adopt-redthread`
- RedThread replay/dry-run output is evidence consumed by this repo
- this repo's local pre-publish gate currently emits the final `approve`, `review`, or `block` decision

This prevents the docs from implying that RedThread alone is making the bridge publish decision today.

### Golden demo durability

The hero binding-truth run remains generated under ignored `runs/hero_binding_truth/`, but it is now durable through code and tests:

- `scripts/generate_hero_binding_truth.py` regenerates the deterministic artifacts
- `make demo-hero-binding-truth` wraps that generator
- `tests/test_golden_demo_truth.py` verifies the generated result and the documented result stay aligned

The decision was not to track all of `runs/` because real runs can contain session-derived data. Generated local artifacts are allowed; checked-in scripts/tests are the source of truth.

### Real ZAPI reference demo

The current real ZAPI reference is:

```text
runs/atp_tennis_01_live_bound/
```

It is intentionally documented as `review`, not `approve`:

- ZAPI input: `demo_session_filtered.har`
- live workflow replay succeeded
- 3 declared response bindings were applied
- RedThread replay passed
- final local gate decision is `review`
- reason: write paths still require manual review

Durability path added:

- `fixtures/reference_demos/atp_tennis_zapi_reference_expected.json` stores the non-secret expected result
- `scripts/check_atp_zapi_reference.py` validates the local HAR plus local ignored run artifacts
- `make check-zapi-reference` writes `runs/atp_tennis_reference_check/sanitized_evidence.json`
- `docs/zapi-reference-demo.md` explains why `review` is the correct outcome

## 2026-04-30 — deterministic reviewed-write operator path

### What changed

The repo now has a deterministic ATP-like reviewed-write proof path:

```bash
make demo-reviewed-write-reference
```

That command hides the internal complexity from the operator:

- local ATP-like replay server
- generated HAR
- approved auth context
- approved staging write context
- approved response-binding overrides
- RedThread runtime input generation
- RedThread replay/dry-run
- local gate verdict
- markdown evidence report

Primary output:

```text
runs/reviewed_write_reference/evidence_report.md
```

Expected result remains `review`, not `approve`, because reviewed write paths are present.

### Still open

The implementation has completed the first architecture slice, durable hero proof, real ZAPI reference validation, and deterministic reviewed-write operator path. Remaining impact work:

1. watch a target reviewer read `runs/reviewed_write_reference/evidence_report.md` without explanation and record where it is unclear
2. update RedThread docs/wiki only after that reviewer can explain the evidence and decision back correctly

## 2026-04-30 — minimum sanitized app context

### What changed

Added a minimal `app_context.v1` contract for RedThread-facing runtime and evidence paths.

The context covers five fields only:

1. workflow order
2. tool/action schema
3. auth model
4. data sensitivity
5. tenant/user boundary

It is generated in `adapters/redthread_runtime/app_context.py` and exported by `build_redthread_runtime_inputs(...)` as both:

- top-level `app_context` / `app_context_summary`
- `redthread_replay_bundle.bridge_workflow_context.app_context` / `app_context_summary`

The bridge workflow summary also surfaces `app_context_summary`, and the evidence report now includes an `App context for RedThread` section with sanitized counts, tags, and auth summary.

### Safety boundary

The app context is intentionally structural. It can include safe metadata such as operation ids, path templates, field names, auth class, scope hints, and sensitivity tags.

It must not include raw HAR/session/cookie/header/body/request/response values. Tests now parse raw HAR request/response values and assert those values do not appear in the generated app context.

### Verification run

Targeted validation:

```bash
python3 -m unittest tests.test_redthread_runtime_adapter tests.test_bridge_workflow tests.test_prepublish_gate tests.test_evidence_report tests.test_reviewed_write_reference -v
```

Result:

- `Ran 13 tests`
- `OK`

Full validation:

```bash
make test
```

Result:

- `Ran 135 tests`
- `OK`

### Follow-up recommendation accepted

Keep this contract in `adopt-redthread` until reviewer comprehension is proven. The next step is to use the Senior AI Engineer review posture against the evidence report and matrix, record unclear points, and only then propose a tiny generic RedThread evidence/context contract upstream.

## 2026-04-30 — Venice evidence run and reviewer-facing wording pass

Ran the full available bridge pipeline on `venice.har` into local ignored artifacts under `runs/venice/`.

Sanitized result:

- fixture count: `15`
- workflow count: `2`
- workflow class: `reviewed_write_workflow:2`
- live workflow replay: `0` executed successfully, `2` blocked, `0` aborted
- blocker reasons: `missing_auth_context:1`, `missing_write_context:1`
- response bindings planned/applied/unapplied: `0/0/0`
- RedThread replay: passed
- RedThread dry-run: executed
- local bridge gate decision: `block`

This is a correct fail-closed result. The run had RedThread evidence, but the local bridge gate blocked because approved auth/write context was required and was not supplied.

Reviewer-facing changes:

- `scripts/build_evidence_report.py` now states that RedThread replay/dry-run is evidence and the final verdict is currently emitted by the local Adopt RedThread bridge gate.
- `adapters/redthread_runtime/app_context.py` now summarizes action classes and splits approved auth context from approved write context.
- `scripts/build_evidence_matrix.py` now includes app-context, auth-context, and sensitivity columns.

Validation remains incomplete until one real external AI engineer reads the matrix/report without explanation and can explain whether they trust the decision.

## 2026-05-01 — external AI engineer feedback direction

A target AI engineer reviewed three evidence runs: ATP Tennis, Gainly, and Venice.

Sanitized cross-run result:

- ATP's `review` decision was trusted because workflow replay executed end-to-end and response bindings applied, but tenant/resource boundary evidence and binding-review auditability were still missing.
- Gainly's `review` decision was technically trusted but weak because evidence was mostly fixture/dry-run level with no workflow/live replay coverage. The useful general signal was generic action-dispatch and token-like field risk.
- Venice's `block` decision was trusted with a caveat: the block reflected auth/session/replay failure, not a confirmed security finding. The useful general signal was strong app-context inference plus missing user-boundary validation.

Direction chosen:

- strengthen the engine generally instead of hand-fixing the three runs
- add clearer decision reason categories so `block` can distinguish security finding, auth/replay failure, and insufficient evidence
- add coverage confidence so weak planning-only runs do not look equivalent to end-to-end workflow evidence
- generate a sanitized attack brief from app context so users do not need to know what RedThread needs
- improve targeted rubric selection, tenant/user boundary candidate detection, auth delivery diagnostics, and binding review auditability

Durable memo:

```text
docs/next-efforts-ai-engineer-feedback.md
```

This keeps the long-term direction intact: pre-release evidence assurance for AI agent/tool workflows, not generic scanner expansion or per-app patching.

## 2026-05-01 — first feedback-driven engine/reporting slice

Implemented the first general engine slice from `docs/next-efforts-ai-engineer-feedback.md` without changing `approve` / `review` / `block` semantics.

Added sanitized summaries:

- `decision_reason_summary`: classifies decisions as approval, manual review, auth/context block, replay failure, binding/context block, or other blocked state; blocks caused by auth/session/replay gaps are not labeled as confirmed vulnerabilities.
- `coverage_summary`: distinguishes strong workflow coverage, weak fixture/dry-run-only coverage, auth/replay-blocked coverage, and explicit coverage gaps such as unproven tenant/user boundary.
- `attack_brief_summary`: derives sanitized risk themes, boundary/dispatch/secret-like field classes, top targeted probe, and dry-run rubric rationale from `app_context.v1` structural metadata.

Updated reviewer outputs:

- `scripts/build_evidence_report.py` now shows decision reason category, confirmed-finding flag, coverage confidence, top targeted probe/question, and dry-run rubric rationale.
- `scripts/build_evidence_matrix.py` now includes the same engine summary columns across approve/review/block examples.
- `adapters/bridge/workflow.py` now writes these summaries into `workflow_summary.json`.
- `adapters/redthread_runtime/runtime_adapter.py` now includes `attack_brief_summary` in runtime inputs and bridge workflow context.

Acceptance-target tests cover:

- ATP-like strong workflow coverage with tenant/user boundary still unproven.
- Gainly-like weak fixture/dry-run-only coverage with dispatch and token-like field risk.
- Venice-like auth/context blocked coverage that is not reported as a confirmed vulnerability.

Verification:

```bash
python3 -m unittest tests.test_evidence_summaries tests.test_evidence_report tests.test_evidence_matrix tests.test_bridge_workflow tests.test_redthread_runtime_adapter -v
make evidence-report
make evidence-matrix
make test
```

## 2026-05-01 — targeted rubric and missing-context question slice

Planned next slice: keep scope to deterministic rubric selection and reviewer-visible missing-context questions. This directly addresses Gainly-like generic action dispatch risk without adding a broad scanner or config wizard.

Implemented:

- `select_campaign_strategy(...)` for deterministic RedThread dry-run case selection from sanitized fixture structure.
- Dispatch/action fields now take priority over generic sensitive-info framing, so generic action endpoints route toward authorization/dispatch probing.
- Runtime campaign cases now include sanitized `risk_themes`, `top_targeted_probe`, `targeted_questions`, and `rubric_selection_rationale`.
- `scripts/run_redthread_dryrun.py` preserves those fields in dry-run summaries.
- `workflow_summary.json` now carries `dryrun_rubric_rationale` when a dry-run executes.
- Evidence reports now show targeted missing-context questions, capped at three.

Guardrails held:

- No `approve` / `review` / `block` semantic changes.
- No raw auth/header/session/body values emitted.
- Deterministic prompt-injection sample behavior remains stable.

Verification:

```bash
python3 -m unittest tests.test_evidence_summaries tests.test_redthread_runtime_adapter tests.test_bridge_workflow tests.test_evidence_report tests.test_evidence_matrix -v
make evidence-report
make evidence-matrix
make test
```

## 2026-05-01 — boundary selector detection slice

Planned next slice: improve tenant/user/resource boundary evidence without changing verdict semantics or adding a broad context wizard.

Implemented:

- `app_context.v1` now emits sanitized `candidate_boundary_selectors` with selector name, location, class, operation ID, path template, and reason category.
- Boundary detection now covers:
  - user/account/profile/member/customer/actor-like fields
  - tenant/org/workspace/company/business-like fields
  - resource/chat/conversation/document/order/report/memory-like fields
  - route parameters classified from sanitized path templates such as `workspaces.id` and `documents.id`
- `app_context_summary` now includes resource-field count, boundary-selector count, and boundary reason categories.
- `attack_brief_summary` now exposes boundary candidate classes and locations, not raw values.
- Evidence report and matrix summaries include the new boundary counts/reasons.

Guardrails held:

- No raw path IDs, auth, header, session, body, request, or response values emitted.
- No `approve` / `review` / `block` semantic changes.
- Output remains structural metadata only.

Verification:

```bash
python3 -m unittest tests.test_redthread_runtime_adapter tests.test_evidence_summaries tests.test_evidence_report tests.test_evidence_matrix -v
make evidence-report
make evidence-matrix
make test
```

## 2026-05-01 — auth delivery diagnostics slice

Planned next slice: make replay/auth failures understandable without exposing auth headers, cookies, tokens, sessions, or raw host/body values.

Implemented:

- Added `auth_header_families` to `app_context_summary` as structural metadata only.
- Added `auth_diagnostics_summary` with:
  - observed auth mode and header family classes
  - required header family counts
  - approved auth/write context required vs supplied
  - auth/write context gap booleans
  - auth-applied result counts
  - HTTP status/error class counts
  - replay/auth failure category such as `missing_auth_context`, `missing_write_context`, `auth_header_family_mismatch`, `server_rejected_auth`, or `environment_or_continuity_mismatch`
  - sanitized operator notes
- Wired auth diagnostics into `workflow_summary.json`, evidence reports, and the evidence matrix.
- Added tests for missing-context vs server-rejected-auth classification.

Guardrails held:

- No raw auth header values, cookies, tokens, sessions, request bodies, response bodies, or raw host values emitted.
- No `approve` / `review` / `block` semantic changes.
- Diagnostics explain failure class; they do not claim confirmed vulnerability.

Verification:

```bash
python3 -m unittest tests.test_evidence_summaries tests.test_evidence_report tests.test_evidence_matrix tests.test_bridge_workflow -v
make evidence-report
make evidence-matrix
make test
```

## 2026-05-01 — binding review auditability slice

Planned next slice after auth diagnostics: make response binding evidence inspectable without exposing bound values.

Implemented:

- Added sanitized `binding_audit_summary.v1` in live workflow replay summaries.
- Exposed `live_workflow_binding_audit_summary` in bridge workflow summaries.
- Reported binding audit details in evidence reports and the evidence matrix:
  - inferred vs declared origin counts
  - approved/pending/rejected/replaced status counts
  - source field and target field/path class metadata
  - runtime applied vs unapplied state
  - whether an applied binding structurally changed a later request
  - allow/hold reason such as `approved_binding_applied` or `held_for_binding_review`
- Added focused tests for approved/applied bindings and pending-review holds.

Guardrails held:

- Audit records contain no bound values or value previews.
- Reports remain structural/sanitized only.
- No verdict semantic changes.

Verification:

```bash
python3 -m unittest tests.test_live_workflow_binding_review tests.test_evidence_report tests.test_evidence_matrix tests.test_bridge_workflow -v
```

## 2026-05-01 — standalone gate rationale and binding-audit handoff slice

Planned next slice after binding auditability: make the standalone pre-publish gate artifact carry the same sanitized rationale now visible in reports, and carry binding audit evidence through the RedThread runtime context.

Implemented:

- `gate_verdict.json` now includes:
  - `decision_reason_summary`
  - `coverage_summary`
  - `auth_diagnostics_summary`
- Pre-publish gate evidence counts now preserve `binding_audit_summary` when live workflow replay produced it.
- Pre-publish gate notes now expose sanitized binding audit status/origin/change counts.
- `redthread_runtime_inputs.json` / `redthread_replay_bundle.bridge_workflow_context` now carry `binding_audit_summary` when live workflow replay has it.

Guardrails held:

- No gate verdict semantics changed.
- Binding audit handoff remains structural only; no bound values or value previews.
- Auth diagnostics still classify replay/auth failure without exposing headers, cookies, tokens, sessions, request bodies, or response bodies.

Verification:

```bash
python3 -m unittest tests.test_redthread_runtime_adapter tests.test_prepublish_gate -v
```

## 2026-05-01 — reviewer quick-read evidence report slice

Planned next slice: reduce silent-reviewer confusion before the external reviewer test by putting the five required comprehension answers at the top of each evidence report.

Implemented:

- Added a `## Reviewer quick read` section to generated evidence reports.
- The section summarizes, using sanitized fields only:
  - tested input artifact and ingestion type
  - whether live workflow replay ran, workflow result counts, workflow classes, and binding applied/planned counts
  - RedThread replay/dry-run evidence
  - local gate outcome, decision category, and confirmed-security-finding boolean
  - why the outcome is correct
  - remaining coverage gaps
  - next useful probe from the attack brief
- Added focused report test coverage for block/auth-context wording and binding quick-read counts.

Guardrails held:

- No new dependencies or integrations.
- No verdict semantic changes.
- Quick-read content is derived from already-sanitized summaries and does not expose raw HAR/session/header/body/request/response values.

Verification:

```bash
python3 -m unittest tests.test_evidence_report -v
```

## 2026-05-01 — evidence matrix reviewer-action slice

Planned next slice: make the evidence matrix answer the validation question reviewers are supposed to ask: ship, change/review, or block.

Implemented:

- Added a `reviewer_action` field to each evidence matrix row.
- Added a `Reviewer action` column to the markdown matrix.
- The action is derived from existing gate decision, decision-reason category, and coverage label:
  - `approve` becomes a ship candidate, not an unconditional production release claim.
  - `review` becomes change/review before ship.
  - auth/context `block` becomes block until the approved context/replay gap is resolved.
- Added focused matrix test coverage for approve/review/block action wording.

Guardrails held:

- No `approve` / `review` / `block` semantic changes.
- No raw artifact values are introduced; the field uses sanitized summary categories and coverage gaps.
- No new dependencies or integrations.

Verification:

```bash
python3 -m unittest tests.test_evidence_matrix -v
```

## 2026-05-01 — dynamic not-proven report wording slice

Planned next slice: make the evidence report's `Not proven by this run` section explain the actual coverage gaps instead of only listing generic caveats.

Implemented:

- Added dynamic not-proven bullets derived from existing sanitized `coverage_summary` and `auth_diagnostics_summary` fields.
- The report now calls out, when applicable:
  - fixture/replay/dry-run only evidence
  - blocked workflow execution not proven under approved context
  - incomplete binding application
  - cross-user/cross-tenant/resource boundary enforcement not proven
  - auth/session/write-context delivery gaps that are not confirmed vulnerabilities
- Kept durable product caveats about release-system wiring, external app stability, RedThread live-execution ownership, and broad authenticated/write-path coverage.
- Added focused report test coverage for blocked workflow, boundary, and auth-context not-proven wording.

Guardrails held:

- No verdict semantic changes.
- No raw artifact values are introduced; the section uses sanitized labels/categories only.
- No new dependencies or integrations.

Verification:

```bash
python3 -m unittest tests.test_evidence_report -v
```

