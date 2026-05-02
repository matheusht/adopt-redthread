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

## 2026-05-01 — report reviewer-action guidance slice

Planned next slice: put the same ship/change/block reviewer-action guidance into the standalone evidence report, not only the matrix.

Implemented:

- Added a report-level reviewer action derived from the local gate decision, decision-reason category, coverage label, and coverage gaps.
- The action appears in both `## Reviewer quick read` and `## Decision`.
- The wording preserves conservative semantics:
  - `approve` is a ship candidate, not an unconditional production release claim.
  - `review` means change/review before ship.
  - auth/context `block` means block until approved context or replay gaps are resolved.
- Added focused report test coverage for block action wording.

Guardrails held:

- No verdict semantic changes.
- No raw artifact values are introduced; the field uses sanitized summary categories and coverage gaps.
- No new dependencies or integrations.

Verification:

```bash
python3 -m unittest tests.test_evidence_report -v
```

## 2026-05-01 — silent reviewer checklist report slice

Planned next slice: make the report answer the validation questions a reviewer is supposed to answer silently: ship/change/block, trusted evidence, weak evidence, next probe, and finding type.

Implemented:

- Added a `## Silent reviewer checklist` section to generated evidence reports.
- The checklist derives sanitized answers from existing gate, coverage, workflow, binding, RedThread, auth diagnostic, and attack brief summaries.
- Added helper wording for:
  - ship/change/block action
  - strongest trusted evidence
  - weak or unclear evidence gaps
  - next confidence-increasing probe
  - confirmed finding vs auth/replay/context failure vs insufficient evidence
  - when to rerun before release
- Added focused report test coverage for the block/auth-context checklist wording.

Guardrails held:

- No verdict semantic changes.
- No raw artifact values are introduced; checklist text uses sanitized categories/counts only.
- No new dependencies or integrations.

Verification:

```bash
python3 -m unittest tests.test_evidence_report -v
```

## 2026-05-01 — evidence matrix finding-type/trusted-evidence slice

Planned next slice: carry the silent-reviewer validation answers into the evidence matrix so the approve/review/block rows distinguish trusted proof from finding type at a glance.

Implemented:

- Added `finding_type` to each evidence matrix row.
- Added `trusted_evidence` to each evidence matrix row.
- Added `Finding type` and `Trusted evidence` columns to the markdown matrix.
- Finding type distinguishes confirmed security findings from auth/replay/context failures and insufficient/unproven evidence.
- Trusted evidence summarizes sanitized workflow, binding, RedThread replay, and dry-run evidence counts.
- Added focused matrix test coverage for reviewed and blocked finding-type wording and trusted-evidence wording.

Guardrails held:

- No verdict semantic changes.
- No raw artifact values are introduced; matrix cells use sanitized categories/counts only.
- No new dependencies or integrations.

Verification:

```bash
python3 -m unittest tests.test_evidence_matrix -v
```

## 2026-05-01 — report next-evidence guidance slice

Planned next slice: make the evidence report state exactly what additional sanitized evidence would increase confidence, instead of only saying what is not proven.

Implemented:

- Added `## Next evidence to collect` to generated evidence reports.
- Added a silent-reviewer checklist answer for what to collect next.
- Derived next evidence requests from coverage gaps, auth diagnostics, binding audit, and attack brief summaries.
- The report now calls out, when applicable:
  - approved non-production staging write context and workflow rerun
  - approved auth context refresh and replay rerun
  - workflow blocker resolution and rerun
  - binding review and continuity rerun
  - targeted ownership-boundary probe
  - bounded safe/workflow replay for fixture-only evidence
- Added focused report test coverage for write-context, workflow-blocker, and boundary-probe next-evidence wording.

Guardrails held:

- No verdict semantic changes.
- No raw artifact values are introduced; next-evidence text uses sanitized categories/counts and already-sanitized probe wording.
- No new dependencies or integrations.

Verification:

```bash
python3 -m unittest tests.test_evidence_report -v
```

## 2026-05-01 — matrix next-evidence guidance slice

Planned next slice: carry next-evidence guidance into the matrix so each approve/review/block row tells the reviewer what would improve confidence next.

Implemented:

- Added `next_evidence_needed` to each evidence matrix row.
- Added a `Next evidence needed` column to the markdown matrix.
- Matrix next-evidence guidance is derived from the same sanitized evidence classes: coverage gaps, auth diagnostics, binding audit, and attack brief.
- Added focused matrix test coverage for approved staging write context rerun and ownership-boundary probe wording.

Guardrails held:

- No verdict semantic changes.
- No raw artifact values are introduced; matrix cells use sanitized categories/counts and sanitized probe wording only.
- No new dependencies or integrations.

Verification:

```bash
python3 -m unittest tests.test_evidence_matrix -v
```


## 2026-05-01 — reviewer packet handoff slice

Planned next slice: turn the report and matrix into one boring reviewer handoff surface so a silent reviewer knows which sanitized artifacts to open and what questions to answer.

Implemented:

- Added `scripts/build_reviewer_packet.py`.
- Added `make evidence-packet`.
- The packet writes `runs/reviewer_packet/reviewer_packet.{md,json}`.
- The packet points to the sanitized evidence report and evidence matrix, restates `approve` / `review` / `block` semantics, and lists the six silent-review questions from the validation plan.
- Updated README and script docs with the new command.
- Added focused packet test coverage.

Guardrails held:

- No verdict semantic changes.
- No new integration or execution path beyond existing report/matrix builders.
- The packet is an index over sanitized artifacts, not a raw run-artifact copier.

Verification:

```bash
python3 -m unittest tests.test_reviewer_packet -v
make evidence-packet
```

## 2026-05-01 — reviewer packet sanitized-marker audit slice

Planned next slice: make the reviewer handoff command fail closed when generated markdown contains configured sensitive marker strings.

Implemented:

- Added a bounded generated-markdown marker audit to `scripts/build_reviewer_packet.py`.
- The audit checks only the sanitized evidence report and matrix, not raw run artifacts.
- Checked marker strings are maintained in `scripts/build_reviewer_packet.py`; this log intentionally avoids copying the literal marker set into reviewer-facing docs.
- `make evidence-packet` uses `--fail-on-marker-hit` so handoff fails if configured markers are present.
- Added focused test coverage for both passing and failing marker-audit behavior.

Guardrails held:

- No broad scanner was added.
- No raw artifact values are read or emitted beyond the existing sanitized markdown surfaces.
- The audit is a privacy regression tripwire, not a claim of complete secret detection.

Verification:

```bash
python3 -m unittest tests.test_reviewer_packet -v
make evidence-packet
```

## 2026-05-01 — reviewer observation template slice

Planned next slice: make the reviewer packet produce a small capture template for the silent-review validation questions so observations can be recorded without raw artifacts.

Implemented:

- `scripts/build_reviewer_packet.py` now writes `runs/reviewer_packet/reviewer_observation_template.md`.
- The template records reviewer role, ship/change/block decision, trusted evidence, unclear evidence, next probe requested, and behavior-change signal.
- The template repeats the six silent-review questions and explicitly forbids pasting raw HAR, auth, session, request body, response body, or secret values.
- Added focused test coverage for template generation.

Guardrails held:

- No verdict semantic changes.
- No new execution path, integration, dependency, or raw-artifact collection.
- The template captures reviewer judgments only, not app/session data.

Verification:

```bash
python3 -m unittest tests.test_reviewer_packet -v
make evidence-packet
```

## 2026-05-01 — reviewer packet artifact-manifest slice

Planned next slice: make the reviewer packet identify the exact sanitized report and matrix artifacts handed to a reviewer without embedding raw contents.

Implemented:

- Added a sanitized artifact manifest to `reviewer_packet.json` and `reviewer_packet.md`.
- The manifest records path, existence, SHA-256, byte count, and line count for the evidence report and evidence matrix.
- This lets a reviewer/session note pin which sanitized artifacts were reviewed while keeping `runs/` raw artifacts ignored and local.
- Updated README and script docs to describe the richer packet output.
- Added focused test coverage for manifest hashes and line counts.

Guardrails held:

- No verdict semantic changes.
- No raw report/matrix contents are copied into the packet beyond paths and hashes.
- No new dependency; hashing uses the Python standard library.

Verification:

```bash
python3 -m unittest tests.test_reviewer_packet -v
make evidence-packet
```

## 2026-05-01 — report and matrix rerun-trigger slice

Planned next slice: make reports and matrix rows say which sanitized evidence changes require a rerun before release, instead of relying only on a generic repeat-before-release sentence.

Implemented:

- Added `build_rerun_trigger_summary(...)` in `adapters/bridge/evidence_summaries.py`.
- Evidence reports now include a `## Rerun triggers` section and a silent-review checklist answer for “What changes force a rerun?”
- Evidence matrix rows now include a `Rerun triggers` column with compact trigger codes.
- Trigger logic stays structural: tool/action scope, auth/write context, workflow policy/status, response-binding review/application, tenant/user/resource selectors, and RedThread rubric/attack-brief changes.

Guardrails held:

- No verdict semantic changes.
- No raw HAR/session/cookie/auth/header/body/request/response values emitted.
- No new dependency or live execution path.

Verification:

```bash
python3 -m unittest tests.test_evidence_summaries tests.test_evidence_report tests.test_evidence_matrix -v
```

## 2026-05-01 — reviewer packet handoff-completeness audit slice

Planned next slice: make the reviewer packet fail closed if the sanitized report or matrix is missing the sections needed for silent review.

Implemented:

- Added `audit_handoff_completeness(...)` in `scripts/build_reviewer_packet.py`.
- The packet now records a `handoff_completeness_audit` alongside the sanitized marker audit.
- `make evidence-packet` now passes `--fail-on-incomplete-handoff` as well as `--fail-on-marker-hit`.
- Required report markers cover quick read, silent checklist, next evidence, rerun triggers, and not-proven sections.
- Required matrix markers cover reviewer action, finding type, trusted evidence, next evidence, and rerun triggers.

Guardrails held:

- This is a completeness tripwire for generated sanitized markdown only, not a raw-artifact scanner.
- The packet still points to sanitized artifacts and does not copy raw run contents.
- No verdict semantic changes.

Verification:

```bash
python3 -m unittest tests.test_reviewer_packet -v
```

## 2026-05-01 — reviewer-observation summary capture slice

Planned next slice: make the silent-review observation loop produce a small sanitized summary of reviewer confusion and behavior-change signals after a reviewer fills the observation template.

Implemented:

- Added `scripts/summarize_reviewer_observation.py`.
- Added `make evidence-observation-summary OBSERVATION=/path/to/filled_reviewer_observation_template.md`.
- The summary writes `runs/reviewer_packet/reviewer_observation_summary.{md,json}`.
- Captured signals include release decision, behavior-change recorded, next probe requested, trusted evidence recorded, weak/unclear evidence recorded, repeat-review request, and missing observation fields.
- Added a bounded configured-marker audit for the filled observation text; markdown/JSON output records marker hit counts without listing marker strings.

Guardrails held:

- No verdict semantic changes.
- No raw run artifacts are read or copied.
- The summary is for reviewer judgments only; it forbids raw HAR/session/cookie/auth/header/body/request/response values.
- No new dependencies or live execution paths.

Verification:

```bash
python3 -m unittest tests.test_reviewer_observation_summary tests.test_reviewer_packet -v
```

Senior AI engineer review was run against the slice. Follow-up fixes applied:

- Observation summarization now fails closed on configured marker hits by default.
- Packet handoff now includes the exact post-review summary command.
- Decision vocabulary normalizes reviewer `ship/change/block` answers into project `approve/review/block/unsure` signals.
- Metadata release decision is reconciled with silent-review Question 1 and inconsistency is flagged.
- Incomplete summaries now show `none_captured_do_not_use_as_validation` and `incomplete_not_reviewer_evidence`.
- Silent-review Question 1-6 completion is counted; a reviewer signal is complete only when metadata fields and silent questions are answered.
- Negated decision phrases such as “do not ship” and “cannot approve” are not classified as `approve`.

## 2026-05-01 — next two slices: wording hardening and RedThread contract proposal

Planned two bounded slices after reviewer-observation summary capture:

1. **Post-review wording hardening.** Patch generated reviewer surfaces where the senior AI engineer review still saw confusion risk: evidence-envelope scope, local bridge vs RedThread ownership, `approve` / `review` / `block` vocabulary, and the difference between confirmed findings vs auth/replay/context or insufficient-evidence outcomes.
2. **Tiny RedThread evidence-contract proposal.** Draft a generic, proposal-only contract for fields RedThread should eventually own, without upstreaming, adding an integration, or leaking source-specific ingestion names into the generic schema.

Implemented wording hardening:

- Evidence reports now include `## How to read this evidence` before the decision section.
- Evidence matrices now include `## How to read this matrix` before the row table.
- Reviewer packets now state how reviewer words map to project verdict terms: `ship` -> `approve`, `change` -> `review`, `block` -> `block`, and warn not to infer approval from negated phrases.
- Wording explicitly says each artifact is a tested evidence envelope, not a whole-app safety proof.
- Wording explicitly says RedThread replay/dry-run is evidence while the local bridge still emits the final gate verdict.
- Wording explicitly says auth/replay/context failures and insufficient evidence are not confirmed vulnerabilities unless `confirmed_security_finding` is true.

Implemented RedThread contract proposal:

- Added `scripts/build_redthread_evidence_contract_proposal.py`.
- Added `make redthread-contract-proposal`.
- Added checked-in proposal doc: `docs/redthread-evidence-contract-proposal.md`.
- Generated local copies under `runs/redthread_evidence_contract_proposal/`.
- Proposal schema: `redthread.evidence_contract_proposal.v0`.
- Required generic sections:
  - `evidence_envelope`
  - `workflow_evidence`
  - `attack_context_summary`
  - `replay_and_auth_diagnostics`
  - `promotion_recommendation`
  - `next_evidence_guidance`
- Proposal preserves ownership split: RedThread should own generic evidence/recommendation vocabulary; adapters should own source ingestion and source-to-contract mapping.
- Proposal non-goals explicitly exclude new integrations, live-write expansion, scanner-wrapper behavior, full secret scanning, and upstream migration before reviewer comprehension is proven.

Guardrails held:

- No verdict semantic changes.
- No raw run artifacts are read or copied.
- No new dependencies.
- No live execution path changes.
- No RedThread upstream changes.
- Contract field names avoid source-specific ingestion names.

Verification added:

- Evidence report tests assert the new reading guide and confirmed-finding caveat.
- Evidence matrix tests assert the new reading guide and finding-type explanation.
- Reviewer packet tests assert the reviewer vocabulary mapping.
- RedThread contract proposal tests assert generic sections, proposal-only status, configured-marker pass, and no source-specific field names in required contract fields.

Senior AI engineer review was run against these two slices. Follow-up fixes applied:

- Fixed auth/replay diagnostics so successful HTTP 2xx/3xx replay results are not classified as `runtime_replay_failure`.
- Added a regression test proving a 200 replay with auth applied produces `replay_failure_category=none`.
- Expanded the RedThread contract proposal from a boolean workflow-order hint to `ordered_operations` carrying sanitized operation sequence/classes/templates/role labels.
- Expanded the contract proposal's attack context from counts alone to `tool_action_schemas` plus field-role summaries, required/optional parameter names, binding targets, and boundary-relevant field classes.

Additional follow-up after final packet inspection:

- The deterministic approve demo now marks its bounded tenant/boundary replay expectation as exercised, so the generated evidence matrix no longer shows `tenant_user_boundary_unproven` on the real approve row. Reviewed-write and blocked rows still retain boundary gaps when ownership probing remains unproven.

## 2026-05-01 — next two slices: cold-review protocol and validation rollup

Planned two bounded slices after packet/contract packaging:

1. **Cold-review protocol hardening.** Make the reviewer packet itself state exactly which artifacts a cold reviewer may see, which inputs are forbidden, what steps to follow, and what counts as a successful silent review. This keeps the next validation from depending on operator memory or an informal walkthrough.
2. **Reviewer-validation rollup.** Add a tiny aggregation step for multiple sanitized observation summaries so three real pre-release reviews can be compared without copying raw reviewer free-form answers, raw run artifacts, HAR/session/cookie/header/body values, or app-specific context.

Implemented cold-review protocol hardening:

- `scripts/build_reviewer_packet.py` now embeds `cold_review_protocol` in `reviewer_packet.json`.
- `runs/reviewer_packet/reviewer_packet.md` now includes a `## Cold review protocol` section.
- The protocol records:
  - allowed artifacts: evidence report, evidence matrix, reviewer packet
  - forbidden inputs: raw HAR files, session cookies/auth headers, request/response bodies, operator walkthroughs before silent answers, and production/staging write context values
  - review steps: give sanitized artifacts first, collect silent answers, fill the observation template, summarize the observation
  - success criteria: decision recorded, trusted/weak evidence recorded, next probe captured or explicitly unnecessary, marker audit passed

Implemented reviewer-validation rollup:

- Added `scripts/summarize_reviewer_validation_rollup.py`.
- Added `make evidence-validation-rollup SUMMARIES="/path/to/summary1.json /path/to/summary2.json /path/to/summary3.json"`.
- Default local rollup reads `runs/reviewer_packet/reviewer_observation_summary.json` and writes:
  - `runs/reviewer_validation/reviewer_validation_rollup.md`
  - `runs/reviewer_validation/reviewer_validation_rollup.json`
- Rollup schema: `adopt_redthread.reviewer_validation_rollup.v1`.
- The rollup reads only `reviewer_observation_summary.json` files, never raw observation markdown or raw run artifacts.
- Free-form reviewer text is not copied into rollup outputs; it is reduced to bounded theme counts.
- Theme buckets:
  - `tenant_user_boundary`
  - `coverage_strength`
  - `confirmed_vs_replay_language`
  - `write_context`
  - `redthread_vs_bridge_ownership`
  - `artifact_navigation`
- Rollup status values:
  - `privacy_blocked`
  - `needs_valid_observation_summaries`
  - `needs_more_complete_reviews`
  - `needs_decision_language_followup`
  - `ready_for_validation_readout`

Documented:

- Added `docs/reviewer-validation-loop.md` with the cold-review protocol, observation summary flow, rollup command, status meanings, theme policy, and decision rule.
- Updated `README.md`, `scripts/README.md`, `docs/project-direction.md`, and `docs/next-efforts-ai-engineer-feedback.md`.

Guardrails held:

- No verdict semantic changes.
- No new live execution path.
- No new integration.
- No new dependency.
- No raw run artifact copying.
- Rollup marker audit uses the existing configured sensitive-marker set and fails closed by default.
- The three-review threshold is documented as a minimum readout threshold, not a statistical claim.

Verification added:

- Reviewer packet tests assert the cold-review protocol appears in markdown and JSON.
- Reviewer validation rollup tests assert:
  - complete/incomplete review counts
  - decision counts
  - behavior-change and next-probe counts
  - bounded theme buckets
  - free-form reviewer text is not copied into rollup markdown or JSON
  - configured marker hits fail closed by default
  - three complete consistent reviews produce `ready_for_validation_readout`

## 2026-05-01 — real no-tools AI cold-review validation and capture fixes

Planned the next two validation-focused slices:

1. **Make real cold-review capture robust to actual reviewer output.** Run no-tools cold reviewers against only sanitized artifacts and fix any capture failures before drawing product conclusions.
2. **Make multi-review validation reproducible.** Allow per-review observation-summary output directories and document the exact AI cold-review readout, including limits.

Real validation run:

- Rebuilt the sanitized artifacts:
  - `make evidence-report`
  - `make evidence-matrix`
  - `make evidence-packet`
- Ran three separate Pi no-tools cold-review sessions.
- Disabled repo context files, skills, prompt templates, themes, sessions, and tools for the reviewer runs.
- Supplied only:
  - `runs/reviewed_write_reference/evidence_report.md`
  - `runs/evidence_matrix/evidence_matrix.md`
  - `runs/reviewer_packet/reviewer_packet.md`
  - `runs/reviewer_packet/reviewer_observation_template.md`
- Stored local ignored outputs under `runs/reviewer_validation/cold_review_ai_{1,2,3}/`.

Validation found a real capture bug before any product conclusion:

- All three reviewers filled the template with inline `Answer: value` text.
- The parser only recognized `Answer:` followed by later lines.
- Result before the fix: all three summaries were incorrectly marked incomplete.

Implemented fix:

- `scripts/summarize_reviewer_observation.py` now accepts both:
  - `Answer:` followed by answer lines
  - `Answer: value` inline
- Added `test_inline_answer_template_style_is_captured`.

Validation found a second signal bug:

- Reviewers answered Question 6 with `Yes, ... before release` wording.
- The repeat-review detector only recognized narrower `before every release` wording.
- Result before the fix: rollup undercounted repeat-review requests.

Implemented fix:

- `scripts/summarize_reviewer_observation.py` now treats silent Question 6 beginning with `Yes`, `Yep`, or `Yeah` as a repeat-review request, unless it begins with `No`.
- Added `test_question_six_yes_counts_as_repeat_review_request`.

Implemented reproducibility fix:

- `Makefile` now supports `OBSERVATION_OUTPUT` for `make evidence-observation-summary`, so each reviewer summary can be written to a separate directory before rollup.

Regenerated validation result after fixes:

- summary count: `3`
- complete summaries: `3/3`
- validation status: `ready_for_validation_readout`
- decisions: `review:3`
- decision consistency: `3/3 consistent`
- marker hits: `0`
- behavior-change recorded: `3`
- next-probe requested: `3`
- repeat-review requested: `3`

Repeated reviewer signal:

- All three AI cold reviewers selected `change`, normalized to project `review`.
- All three requested tenant/user boundary evidence: verify that the actor cannot access another actor's resource identifier class.
- This supports keeping reviewed-write as `review`, not `approve`, and prioritizing tenant/user boundary evidence before any new integration.

Documented:

- Added `docs/ai-cold-review-validation-readout.md`.
- Updated `docs/reviewer-validation-loop.md` with inline-answer support, per-review output directories, repeat-review wording, and the AI validation note.
- Updated `README.md`, `scripts/README.md`, `docs/project-direction.md`, and `docs/next-efforts-ai-engineer-feedback.md`.

Boundaries:

- This is real AI cold-review validation of the packet mechanics, not external human buyer validation.
- Do not claim production readiness, demand validation, or full sanitization proof.
- Do not treat the repeated tenant/user boundary ask as a confirmed vulnerability.

## 2026-05-01 — tenant/user boundary next-probe plan

Followed up on the repeated cold-review signal with a small planning artifact, not a new integration or executor.

Implemented:

- `scripts/build_boundary_probe_plan.py`
- `make evidence-boundary-probe-plan`
- `tests/test_boundary_probe_plan.py`

The generated artifact is:

```text
runs/boundary_probe_plan/tenant_user_boundary_probe_plan.{md,json}
```

What it does:

- reads existing reviewed-write `workflow_summary.json` and `redthread_runtime_inputs.json`
- extracts only structural boundary selector evidence: selector names/classes/locations, operation IDs, path templates, and reason categories
- turns that into a reviewer-readable next-probe plan for own-scope vs cross-actor/cross-tenant checks
- records pass/review/block interpretation rules without changing the current gate verdict
- fails closed on the configured sensitive-marker audit

What it does **not** do:

- does not execute against production or staging
- does not add a new integration
- does not copy raw HAR/session/cookie/header/body/request/response values
- does not convert reviewed-write evidence into `approve`

Validation:

- unit tests cover sanitized artifact generation and marker-hit fail-closed behavior
- real generated-artifact validation ran `make evidence-boundary-probe-plan` against `runs/reviewed_write_reference/`
- generated-artifact result: `boundary_probe_status=needs_boundary_probe`, `selector_count=3`, `marker_hits=0`, `marker_audit_passed=true`

## 2026-05-01 — next three implementation slices

Planned and implemented the next three local slices without adding integrations or changing verdict semantics.

### Slice 1 — package sanitized external-review handoff

Implemented:

- `scripts/build_external_review_handoff.py`
- `make evidence-external-review-handoff`
- `tests/test_external_review_handoff.py`
- `docs/external-human-cold-review-handoff.md`

What it does:

- copies only the sanitized reviewer-facing markdown artifacts into `runs/external_review_handoff/`
- writes `external_reviewer_instructions.md`
- writes `external_review_handoff_manifest.json` with artifact hashes, marker-audit status, and handoff-completeness status
- explicitly marks the package as `not_validation_until_filled_observations_are_summarized`

What it does not do:

- does not claim an external review has happened
- does not copy raw captures, repo context, source files, session material, request/response bodies, or write-context values
- does not bypass the observation-summary and validation-rollup flow

### Slice 2 — external human validation protocol made executable

The handoff directory now contains a reviewer protocol that can be given to a human reviewer with no walkthrough.

Count rule:

- observation summary must be complete
- configured sensitive-marker audit must pass
- release decision must be recorded
- trusted and weak/unclear evidence must be recorded
- all six silent-review answers must be present

Blocked status remains:

- actual external human validation is still pending until reviewers fill observations
- incomplete, walked-through, or marker-hit observations are not validation evidence

### Slice 3 — tenant/user boundary execution design

Implemented:

- `scripts/build_boundary_execution_design.py`
- `make evidence-boundary-execution-design`
- `tests/test_boundary_execution_design.py`
- `docs/tenant-user-boundary-execution-design.md`

What it defines:

- approved local context contract: `adopt_redthread.boundary_probe_context.v1`
- sanitized boundary result contract: `adopt_redthread.boundary_probe_result.v1`
- allowed result statuses: `not_run`, `passed_boundary_probe`, `failed_boundary_probe`, `blocked_missing_context`, `auth_or_replay_failed`
- execution flow to implement later: load approved context, select selector, run own-scope control, run cross-scope probe, write sanitized result
- decision mapping that keeps auth/replay/context failures separate from confirmed findings

What it does not do:

- does not implement an executor
- does not execute against production or staging
- does not change `approve` / `review` / `block` semantics
- does not remove `tenant_user_boundary_unproven` until actual boundary result evidence exists

## 2026-05-01 — boundary result artifact and reviewer-surface integration

### Slice 1 — tenant/user boundary result template/validator

Implemented:

- `scripts/build_boundary_probe_result.py`
- `make evidence-boundary-probe-result`
- `tests/test_boundary_probe_result.py`
- `docs/tenant-user-boundary-probe-result.md`

What it does:

- writes `runs/boundary_probe_result/tenant_user_boundary_probe_result.{md,json}`
- defaults to the honest current status: `blocked_missing_context`
- records `boundary_probe_executed=false`, `gate_decision=review`, and `confirmed_security_finding=false`
- records only selector labels, selector class/location, operation ID, path template, result classes, status family, replay failure category, context-readiness labels, and marker-audit status
- validates future sanitized observed-result JSON without executing a probe
- fails closed on configured sensitive-marker hits and forbidden raw-field keys

What it does not do:

- does not run a tenant/user boundary probe
- does not read or copy raw actor, tenant, resource, auth, cookie, session, request-body, response-body, or write-context values
- does not convert reviewed-write evidence into `approve`
- does not label missing context as a confirmed vulnerability

### Slice 2 — boundary result evidence surfaced in report, matrix, packet, and handoff

Implemented:

- `scripts/build_evidence_report.py` now adds a `## Tenant/user boundary probe result` section and a quick-read boundary result line
- `scripts/build_evidence_matrix.py` now adds a `Boundary probe result` column
- `scripts/build_reviewer_packet.py` now includes the boundary result artifact in the manifest when present and marks it optional in the cold-review protocol
- `scripts/build_external_review_handoff.py` now copies `tenant_user_boundary_probe_result.md` when present
- `docs/next-two-slices-plan.md` documents scope and acceptance criteria

Behavior:

- when the result artifact is absent, surfaces preserve the existing absent/`tenant_user_boundary_unproven` wording
- when the result artifact is present, surfaces show result status, executed flag, selector evidence, own/cross result classes, replay failure category, gate interpretation, confirmed-finding flag, and marker audit status
- `blocked_missing_context` changes the next-evidence wording toward approved boundary context, not toward a claim that a probe ran

Still blocked:

- live boundary execution remains blocked until approved non-production context exists with safe actor scopes, selector bindings, and operator approval
- the result artifact is evidence plumbing, not external validation and not a live executor

## 2026-05-01 — external review session batch and validation readout

### Slice 1 — isolated external review session batch

Implemented:

- `scripts/build_external_review_session_batch.py`
- `make evidence-external-review-sessions`
- `tests/test_external_review_session_batch.py`
- `docs/external-review-session-batch.md`

What it does:

- reads the sanitized external handoff manifest and its allowed markdown artifacts
- writes `runs/external_review_sessions/external_review_session_batch.{md,json}`
- creates `runs/external_review_sessions/review_*/` folders with sanitized artifacts, one blank filled-observation file, and per-review instructions
- records the exact `make evidence-observation-summary` command for each reviewer
- records the expected rollup command for the generated summary paths
- fails closed on configured sensitive-marker hits

What it does not do:

- does not claim external validation
- does not summarize observations
- does not copy raw HAR/session/cookie/header/body/request/response data, source files, repo context, or write-context values
- does not execute boundary probes or live requests

### Slice 2 — external validation readout state machine

Implemented:

- `scripts/build_external_validation_readout.py`
- `make evidence-external-validation-readout`
- `tests/test_external_validation_readout.py`
- `docs/external-validation-readout.md`

What it does:

- reads `external_review_session_batch.json` and sanitized `reviewer_observation_summary.json` files only
- reuses the existing reviewer-validation rollup logic under `runs/external_validation_readout/`
- writes `runs/external_validation_readout/external_validation_readout.{md,json}`
- reports `waiting_for_filled_external_observations` when expected summaries are absent
- reports `needs_more_complete_external_reviews`, `needs_valid_external_observation_summaries`, `needs_external_decision_language_followup`, `ready_for_external_validation_readout`, or `privacy_blocked` as appropriate
- preserves the claim boundary: even a ready readout is not buyer-demand proof, production-readiness proof, or whole-app safety proof

What it does not do:

- does not read raw filled observation text directly
- does not copy free-form reviewer answers into the readout
- does not alter bridge `approve` / `review` / `block` verdict semantics
- does not remove the boundary execution blocker

## 2026-05-01 — evidence freshness and readiness ledger

### Slice 1 — sanitized evidence freshness manifest

Implemented:

- `scripts/build_evidence_freshness_manifest.py`
- `make evidence-freshness`
- `tests/test_evidence_freshness.py`
- `docs/evidence-freshness-manifest.md`

What it does:

- compares reviewer packet manifest hashes against sanitized source artifacts
- compares external handoff copies against sanitized source artifacts
- compares external review session copies against external handoff hashes
- writes `runs/evidence_freshness/evidence_freshness_manifest.{md,json}`
- reports `fresh`, `stale_or_missing`, or `privacy_blocked`
- fails closed on configured sensitive-marker hits by default

What it does not do:

- does not read raw HAR/session/cookie/auth/header/body/request/response data
- does not read source files, write-context values, or raw boundary actor/tenant/resource values
- does not claim external validation, production readiness, buyer demand, whole-app safety, or release approval
- does not alter bridge `approve` / `review` / `block` verdict semantics

### Slice 2 — sanitized evidence readiness ledger

Implemented:

- `scripts/build_evidence_readiness.py`
- `make evidence-readiness`
- `tests/test_evidence_readiness.py`
- `docs/evidence-readiness-ledger.md`

What it does:

- regenerates the freshness manifest by default
- reads matrix, reviewer packet, external handoff, external session batch, external validation readout, boundary result, and freshness JSON metadata
- writes `runs/evidence_readiness/evidence_readiness.{md,json}`
- reports readiness states including `privacy_blocked`, `missing_required_evidence`, `stale_or_missing_evidence`, `waiting_for_external_validation`, `boundary_context_pending`, `needs_decision_example_coverage`, and `ready_for_sanitized_readout`
- derives next actions from readiness blockers

What it does not do:

- does not approve release
- does not summarize raw reviewer answers
- does not execute boundary probes
- does not treat missing boundary context as a confirmed vulnerability
- does not change local bridge `approve` / `review` / `block` verdict semantics

## 2026-05-01 — external distribution and remediation queue

### Slice 1 — external review distribution manifest

Implemented:

- `scripts/build_external_review_distribution_manifest.py`
- `make evidence-external-review-distribution`
- `tests/test_external_review_distribution.py`
- `docs/external-review-distribution-manifest.md`

What it does:

- reads the sanitized external handoff manifest, external review session batch, freshness manifest, and copied sanitized session artifacts
- writes `runs/external_review_distribution/external_review_distribution_manifest.{md,json}`
- reports `ready_to_distribute`, `privacy_blocked`, `missing_required_evidence`, `stale_or_missing_evidence`, or `not_ready_to_distribute`
- records one delivery entry per reviewer session with allowed file count, filled observation path, expected summary path, and exact summary command
- fails closed on configured sensitive-marker hits

Current generated state:

- `distribution_status: ready_to_distribute`
- `delivery_count: 3`
- `blocker_count: 0`

What it does not do:

- does not claim external validation
- does not contact reviewers or summarize reviewer answers
- does not read raw HAR/session/cookie/auth/header/body/request/response data, source files, write-context values, raw boundary values, or prior reviewer answers
- does not change local bridge `approve` / `review` / `block` verdict semantics

### Slice 2 — evidence remediation queue

Implemented:

- `scripts/build_evidence_remediation_queue.py`
- `make evidence-remediation-queue`
- `tests/test_evidence_remediation_queue.py`
- `docs/evidence-remediation-queue.md`

What it does:

- regenerates the readiness ledger by default
- reads sanitized readiness and distribution metadata
- writes `runs/evidence_remediation/evidence_remediation_queue.{md,json}`
- converts blockers into ordered work items with owner labels, priority, status, blocked-by list, action, verification commands, acceptance criteria, and non-claims
- fails closed on configured sensitive-marker hits, including embedded audit metadata

Current generated state:

- `queue_status: open_items`
- `item_count: 2`
- open items:
  - `collect_external_reviewer_observations`
  - `wait_for_approved_boundary_context`

What it does not do:

- does not approve release
- does not create external validation
- does not execute boundary probes
- does not treat missing boundary context as a confirmed vulnerability
- does not include raw reviewer free-form answers or raw app/run artifacts
- does not change local bridge `approve` / `review` / `block` verdict semantics

## 2026-05-02 — external review return ledger

### Slice — sanitized per-review return/follow-up ledger

Implemented:

- `scripts/build_external_review_return_ledger.py`
- `make evidence-external-review-returns`
- `tests/test_external_review_return_ledger.py`
- `docs/external-review-return-ledger.md`

What it does:

- reads the external review distribution manifest and expected sanitized `reviewer_observation_summary.json` files
- writes `runs/external_review_returns/external_review_return_ledger.{md,json}`
- reports `waiting_for_returns`, `needs_followup`, `ready_for_external_validation_readout`, `privacy_blocked`, or `missing_required_evidence`
- reports each reviewer slot as `missing_summary`, `invalid_summary`, `privacy_blocked`, `incomplete_summary`, `needs_decision_followup`, or `complete`
- emits exact follow-up commands from the distribution manifest
- fails closed on configured sensitive-marker hits, including embedded summary audit metadata

Current expected local state before real external reviewer returns:

- `ledger_status: waiting_for_returns`
- `complete_count: 0/3`
- missing summaries remain operational waiting state, not external validation

What it does not do:

- does not read filled observation markdown directly
- does not copy raw reviewer free-form answers
- does not contact reviewers, execute probes, or approve release
- does not read raw HAR/session/cookie/auth/header/body/request/response data, source files, write-context values, or raw boundary values
- does not change local bridge `approve` / `review` / `block` verdict semantics

Verification:

```bash
python3 -m py_compile scripts/build_external_review_return_ledger.py scripts/build_evidence_remediation_queue.py
python3 -m unittest tests.test_external_review_return_ledger tests.test_evidence_remediation_queue -v
make evidence-external-review-returns
```

## 2026-05-02 — boundary context intake validator

### Slice — sanitized approved-context template and validator

Implemented:

- `scripts/build_boundary_probe_context.py`
- `make evidence-boundary-probe-context`
- `tests/test_boundary_probe_context.py`
- `docs/tenant-user-boundary-probe-context.md`

What it does:

- writes `runs/boundary_probe_context/tenant_user_boundary_probe_context.template.{md,json}`
- validates optional sanitized `adopt_redthread.boundary_probe_context.v1` metadata
- requires non-production target classification, explicit boundary-probe approval, actor separation, tenant/user scope class, selector bindings, operator approval, expiration, and safe execution constraints
- reports `blocked_missing_context`, `blocked_invalid_context`, `privacy_blocked`, or `ready_for_boundary_probe`
- fails closed on configured sensitive-marker hits and forbidden raw-field keys
- records that no boundary probe was executed and no confirmed security finding exists

Current expected local state before approved context exists:

- `context_status: blocked_missing_context`
- `boundary_probe_execution_authorized: false`
- `boundary_probe_executed: false`

What it does not do:

- does not execute probes or send traffic
- does not resolve actor, tenant, resource, credential, session, auth-header, request, response, or write-context values
- does not authorize production writes
- does not approve release or change bridge verdict semantics
- does not make `blocked_missing_context` a confirmed vulnerability

Verification:

```bash
python3 -m py_compile scripts/build_boundary_probe_context.py scripts/build_evidence_remediation_queue.py
python3 -m unittest tests.test_boundary_probe_context tests.test_evidence_remediation_queue -v
make evidence-boundary-probe-context
make evidence-remediation-queue
```

## 2026-05-02 — boundary context surfaced in readiness/remediation

### Slice — explicit context-intake blocker rollup

Implemented:

- `scripts/build_evidence_readiness.py` boundary context component support
- `scripts/build_evidence_remediation_queue.py` `boundary_context_not_ready` remediation support
- `tests/test_evidence_readiness.py` missing/ready boundary context coverage
- `tests/test_evidence_remediation_queue.py` explicit context-intake queue coverage
- `docs/evidence-readiness-ledger.md` update
- `docs/evidence-remediation-queue.md` update

What it does:

- reads `runs/boundary_probe_context/tenant_user_boundary_probe_context.template.json` as a first-class readiness component
- reports `boundary_context_not_ready` separately from `boundary_probe_not_executed`
- keeps `boundary_probe_not_executed` open when context is `ready_for_boundary_probe`
- adds a `validate_approved_boundary_context` remediation item before any future execution can be considered
- carries boundary context marker-audit metadata through the existing fail-closed readiness path

What it does not do:

- does not execute probes or send traffic
- does not treat ready context as execution proof
- does not copy or surface raw boundary actor, tenant, resource, credential, request, or response values
- does not approve release or change bridge verdict semantics

Verification:

```bash
python3 -m py_compile scripts/build_evidence_readiness.py scripts/build_evidence_remediation_queue.py
python3 -m unittest tests.test_evidence_readiness tests.test_evidence_remediation_queue -v
make evidence-readiness
make evidence-remediation-queue
```

## 2026-05-02 — boundary context request package

### Slice — sanitized approved-context request checklist

Implemented:

- `scripts/build_boundary_probe_context_request.py`
- `make evidence-boundary-context-request`
- `tests/test_boundary_probe_context_request.py`
- `docs/tenant-user-boundary-probe-context-request.md`
- `BOUNDARY_CONTEXT=...` support for `make evidence-boundary-probe-context`
- remediation queue command updates for the context request/validation path

What it does:

- reads the sanitized boundary context intake artifact
- writes `runs/boundary_probe_context_request/tenant_user_boundary_probe_context_request.{md,json}`
- reports `missing_required_evidence`, `ready_to_request_context`, `context_ready`, or `privacy_blocked`
- lists missing context condition labels, validation blocker labels, required sanitized context sections, forbidden inputs, and operator validation commands
- fails closed on configured sensitive-marker hits and forbidden raw-field-key hits

What it does not do:

- does not execute probes or send traffic
- does not resolve actor, tenant, resource, credential, session, auth-header, request, response, or write-context values
- does not treat `context_ready` as execution proof
- does not approve release or change bridge verdict semantics

Verification:

```bash
python3 -m py_compile scripts/build_boundary_probe_context_request.py scripts/build_boundary_probe_context.py scripts/build_evidence_remediation_queue.py
python3 -m unittest tests.test_boundary_probe_context_request tests.test_evidence_remediation_queue -v
make evidence-boundary-context-request
make evidence-remediation-queue
```

## 2026-05-02 — boundary context request readiness surfacing

### Slice — first-class context request component in readiness/remediation

Implemented:

- `scripts/build_evidence_readiness.py` now indexes `runs/boundary_probe_context_request/tenant_user_boundary_probe_context_request.json`
- `tests/test_evidence_readiness.py` coverage for request status surfacing, missing request artifacts, and failed embedded request audits
- `scripts/build_evidence_remediation_queue.py` support for `boundary_context_request_not_ready`
- `tests/test_evidence_remediation_queue.py` coverage for the request-regeneration work item
- docs updates for readiness/remediation scope

What it does:

- shows boundary context request status separately from context intake and probe result status
- regenerates the sanitized request package during readiness generation from sanitized context intake metadata
- fails closed when the request artifact or embedded request audit is invalid/privacy-blocked
- converts request-artifact problems into an explicit remediation item

What it does not do:

- does not execute probes or send traffic
- does not resolve or surface raw actor, tenant, resource, credential, session, auth-header, request, response, or write-context values
- does not treat request readiness or context readiness as execution proof
- does not approve release or change bridge verdict semantics

Verification:

```bash
python3 -m py_compile scripts/build_evidence_readiness.py scripts/build_evidence_remediation_queue.py
python3 -m unittest tests.test_evidence_readiness tests.test_evidence_remediation_queue -v
make evidence-readiness
make evidence-remediation-queue
```
