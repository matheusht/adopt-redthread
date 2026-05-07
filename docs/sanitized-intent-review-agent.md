# Sanitized Intent Review Agent

Schema versions: `adopt_redthread.sanitized_intent_review_context.v0`, `adopt_redthread.sanitized_intent_review.v0`, `adopt_redthread.redthread_evidence_export.v0`, `adopt_redthread.execution_handoff.v0`

Status: Phase 1-8 local implementation target.

## Executive recommendation

Add a CLI-first Sanitized Intent Review Agent as an offline, sanitized evidence interpretation layer between HAR batch artifacts and RedThread export.

The layer must not scan, replay, attack, validate, or confirm findings. It turns already-sanitized batch evidence into intent hypotheses, workflow classifications, evidence gaps, reviewer questions, RedThread-ready evidence candidates, and explicit approved-execution requirements.

The safest implementation path is deterministic scaffolding first, with optional LLM classification only after schema validation and privacy auditing are stable.

## Architecture proposal

```text
sanitized batch artifacts
  -> deterministic context builder and privacy guard
  -> sanitized intent review context
  -> deterministic Sanitized Intent Review Agent v0
  -> schema and privacy validator
  -> intent_review.json
  -> intent_review.md
  -> redthread_evidence_export.json
  -> redthread_execution_handoff.json/md
```

The agent reads only these sanitized inputs:

- `batch_manifest.json`
- `subject_index.json`
- `aggregate_blockers.json`
- `subjects/*/workflow_summary.json`
- `subjects/*/subject_summary.json`
- `subjects/*/evidence_report.md`
- `review_workflow/phase_*.json`
- `review_workflow/phase_*.md`

The implementation must not read raw HARs, raw capture files, raw replay contexts, or runtime approval files.

## Responsibility split

### adopt-redthread

Owns ingestion, sanitization, batch artifacts, sanitized context construction, deterministic intent review, local CLI workflow, marker checks, forbidden-key checks, and RedThread export file creation.

Does not own confirmed security findings, severity, exploitation claims, autonomous endpoint testing, or final RedThread gate semantics.

### Sanitized Intent Review Agent

Owns classification of sanitized evidence:

- likely user intent;
- workflow class;
- read/write/auth/boundary relevance;
- endpoint role categories without raw URLs or app values;
- test hypotheses;
- missing evidence;
- reviewer questions;
- RedThread export readiness;
- approved replay or boundary proof requirement.

### RedThread

Owns generic attack/evaluation semantics, judge/defend/validate/regress, promotion-gate recommendation semantics, confirmed findings, and severity/truth.

### Approved replay executor

Owns optional explicit non-production execution proof only. It is not invoked by the intent review layer.

## Data flow

```text
Raw HAR / capture artifacts
        |
        | local only; never sent to LLM or intent review
        v
HAR batch ingestion + sanitizer
        |
        v
Sanitized batch artifacts
        |
        v
Sanitized Intent Review Context Builder
        |
        v
Deterministic Sanitized Intent Review Agent v0
        |
        v
Schema + privacy validator
        |
        +------------------------------+
        |                              |
        v                              v
intent_review.json              intent_review.md
        |
        v
redthread_evidence_export.json
        |
        +--> redthread_execution_handoff.json/md
        |       (deterministic execution candidates; no live execution authorization)
        v
RedThread evaluation / judge / gate semantics
```

## Artifact contracts

### `intent_review_context.json`

Internal deterministic context packet. It records sanitized batch metadata, sanitized subject summaries, optional sanitized report excerpts, review workflow artifact names, and a privacy attestation. It exists to make LLM mode safe later, but Phase 2-3 use it deterministically.

### `intent_review.json`

Required top-level fields:

- `schema_version`
- `review_id`
- `source_batch`
- `privacy_attestation`
- `subjects`
- `batch_summary`

Each subject contains:

- `input_quality`
- `intent_hypotheses`
- `workflow_classification`
- `endpoint_role_categories`
- `test_hypotheses`
- `missing_evidence`
- `reviewer_questions`
- `redthread_export_readiness`
- `approved_execution_requirements`
- `finding_semantics`

All findings/severity fields are negative assertions only.

### `intent_review.md`

Human-readable companion that summarizes subject intent hypotheses, workflow class, evidence gaps, reviewer questions, export readiness, approved-execution requirements, and safety notes.

### `redthread_evidence_export.json`

Required top-level fields:

- `schema_version`
- `export_id`
- `source`
- `evidence_envelope`
- `workflow_evidence`
- `intent_context`
- `execution_requirements`
- `promotion_semantics`
- `privacy_attestation`

The export must say RedThread evaluation is required. It must not claim a local final decision, confirmed finding, severity, or release override.

The export includes an `execution_handoff` pointer/summary with:

- `artifact_name: redthread_execution_handoff.json`
- candidate count
- `redthread_final_gate_required: true`
- `live_execution_allowed: false`
- `raw_artifacts_included: false`

This pointer is planning metadata only. It is not a live attack authorization.

### `redthread_execution_handoff.json`

Deterministic RedThread execution handoff generated after sanitized review validation.

Required top-level fields:

- `schema_version: adopt_redthread.execution_handoff.v0`
- `source`
- `summary`
- `execution_candidates`

Each candidate contains:

- `candidate_id`
- `subject_id`
- `rank`
- `candidate_workflow_intent`
- `evidence_strength`
- `execution_readiness`
- `recommended_redthread_action`
- `operator_summary`
- `supporting_sanitized_observations`
- `missing_context`
- `execution_constraints`
- `redthread_decides`
- `forbidden_interpretation`

Every candidate must cite at least one sanitized observation ID. Recommended actions are constrained to:

- `collect_boundary_context`
- `collect_reviewer_observation`
- `evaluate_sanitized_export`
- `prepare_reviewed_replay_plan`
- `redthread_triage`

The handoff is deliberately deterministic in this phase. Local LLM output may enrich only `subjects[].local_model_observations` in `intent_review.json`; it must not author `redthread_execution_handoff` or `execution_candidates` directly.

### `redthread_execution_handoff.md`

Operator-facing companion that answers:

1. what workflow RedThread should consider next;
2. why, citing sanitized observation IDs;
3. what context is missing;
4. whether the candidate is ready for RedThread review;
5. what RedThread, not adopt-redthread, must decide.

## Safety and privacy invariants

- LLM receives sanitized artifacts only.
- Raw HARs are never prompt input.
- No raw paths, URLs, headers, cookies, request bodies, response bodies, auth values, tenant IDs, resource IDs, user IDs, app field names, or secrets in prompts, outputs, docs, or tests.
- No live endpoint requests by default.
- No write/auth/boundary execution without explicit approved non-production context.
- No scanner, exploit, severity, vulnerability, or confirmed-finding language from the intent agent.
- RedThread owns final evaluation semantics.
- Agent outputs are schema-valid and marker-audited.
- Every execution handoff candidate cites sanitized observation IDs.
- The local model does not author execution handoff candidates; candidate planning remains deterministic until a stricter candidate validator exists.
- Every conclusion is labeled as hypothesis, evidence gap, reviewer question, export-ready evidence, approved-execution requirement, or RedThread execution candidate.
- Confirmed finding is always false in this layer.

## Failure modes and mitigations

| Failure mode | Mitigation |
|---|---|
| Raw artifact leakage into context | Strict input allowlist plus marker audit |
| Raw-looking values in output | Forbidden-key and marker audit before writing final artifacts |
| Finding/severity claims | Fixed negative fields and validator checks |
| Scanner-like drift | No network tools, no execution, no raw HAR access |
| Nondeterminism | Deterministic v0 classifier and fixture tests |
| Missing evidence treated as issue truth | Separate evidence gaps from hypotheses and findings |
| Approval implied by output | Output may require approved replay but never authorizes it |

## Evaluation strategy

Phase 1-3 tests must verify:

- context packet contains only sanitized fields;
- marker audit passes;
- `intent_review.json` schema shape is stable;
- `redthread_evidence_export.json` does not claim findings, severity, final approval, or release override;
- write/auth/boundary gaps become approved-execution requirements or missing evidence, not findings;
- existing tests continue to pass.

## Implementation phases

### Phase 1 — Contract and design doc

Objective: document the layer, responsibilities, artifact contracts, invariants, and implementation sequence.

Files likely changed:

- `docs/sanitized-intent-review-agent.md`
- `README.md` or `docs/offline-har-evidence-batch.md` only for short cross-links if needed.

Acceptance criteria:

- Contract is explicit and bounded.
- Examples contain no raw values.
- RedThread ownership remains clear.

Verification:

```bash
make test
```

### Phase 2 — Deterministic context packet builder

Objective: build a sanitized context packet from existing batch artifacts.

Files likely changed:

- `scripts/build_sanitized_intent_review.py`
- `tests/test_sanitized_intent_review.py`
- `Makefile`

Acceptance criteria:

- Reads only sanitized batch artifacts.
- Writes `intent_review_context.json`.
- Fails on marker or forbidden-key hits when requested.
- Does not read raw HARs.

Verification:

```bash
python3 -m pytest tests/test_sanitized_intent_review.py
make test
```

### Phase 3 — Deterministic review generator v0

Objective: generate `intent_review.json` and `intent_review.md` without LLM dependency.

Files likely changed:

- `scripts/build_sanitized_intent_review.py`
- `tests/test_sanitized_intent_review.py`
- `Makefile`

Acceptance criteria:

- Produces expected review artifacts from a sanitized batch fixture.
- Uses conservative enum classifications.
- Marks uncertain cases as `unknown` or low confidence.
- Never emits findings, severity, scanner language, or execution claims.

Verification:

```bash
make evidence-intent-review HAR_BATCH_OUTPUT=runs/har_batches/latest
python3 -m unittest tests.test_sanitized_intent_review
make test
```

Manual testing guide: `docs/sanitized-intent-review-manual-test.md`.

Next outcome-first plan: `docs/structured-reviewer-observation-and-boundary-context-plan.md`.

### Phase 4 — RedThread export v0

Objective: produce `redthread_evidence_export.json` from the sanitized intent review.

Files likely changed:

- `scripts/build_sanitized_intent_review.py`
- `tests/test_sanitized_intent_review.py`

Acceptance criteria:

- Export contains workflow evidence, intent context, missing evidence, reviewer questions, and execution requirements.
- Export says RedThread evaluation is required.
- Export does not claim final local decision, confirmed finding, severity, or release override.

Verification:

```bash
make evidence-intent-review HAR_BATCH_OUTPUT=runs/har_batches/latest
python3 -m unittest tests.test_sanitized_intent_review
```

### Phase 5 — Optional LLM mode behind guardrails

Objective: support local advisory reasoning and optional offline LLM-output validation without exposing raw artifacts or changing RedThread authority.

Files likely changed:

- `scripts/build_sanitized_intent_review.py`
- `tests/test_sanitized_intent_review.py`
- `Makefile`

Acceptance criteria:

- Default mode is `auto`: use `INTENT_REVIEW_LOCAL_LLM_CMD` when configured, otherwise fall back to deterministic review.
- The local LLM command receives `llm_intent_review_prompt.json` on stdin only; no raw HAR, URL, header, cookie, body, auth value, ID, secret, app field name, or live endpoint is provided.
- `local_llm_status.json` records whether local advisory reasoning was accepted or deterministic fallback was used.
- `--agent-mode llm` still supports the explicit offline validation path with `--llm-review-output`.
- LLM output is rejected if subject IDs do not match, if default live execution is allowed, or if finding/severity/scanner semantics are claimed.

Verification:

```bash
python3 -m unittest tests.test_sanitized_intent_review
```

### Current execution handoff implementation slice — phases 4-6

This slice extends the deterministic handoff added in phases 1-3.

#### Phase 4 — Build-output integration

Objective: make the handoff a first-class output of `build_sanitized_intent_review()`.

Implemented behavior:

- builds `redthread_execution_handoff.json` after intent review and advancement summary;
- validates the handoff before writing final artifacts;
- writes `redthread_execution_handoff.md` for operator review;
- writes `redthread_execution_handoff_validation.json`;
- includes handoff payloads in the privacy audit;
- returns `execution_handoff_path`, `execution_candidate_count`, and `ready_for_redthread_review_count` from the CLI/API result.

Acceptance criteria:

- every subject has a deterministic execution candidate;
- every candidate has sanitized observation citations;
- handoff validation passes before artifacts are written;
- live execution remains disabled and RedThread final gate remains required.

#### Phase 5 — RedThread export pointer

Objective: make `redthread_evidence_export.json` tell RedThread where to find the handoff without embedding attack execution authority.

Implemented behavior:

- adds `execution_handoff` summary metadata to the export;
- records `artifact_name: redthread_execution_handoff.json`;
- records candidate count and safety constraints;
- keeps `live_execution_allowed: false`;
- keeps `redthread_final_gate_required: true`.

This is a pointer and planning summary only. It does not authorize replay, mutation, live attack execution, release promotion, or a confirmed finding.

#### Phase 6 — Local LLM handoff contract boundary

Objective: ensure optional local LLM reasoning cannot become the handoff author.

Implemented behavior:

- `llm_intent_review_prompt.json` now states that execution handoff candidates are generated deterministically after review validation;
- the local model is told not to return `redthread_execution_handoff` or `execution_candidates`;
- allowed LLM enrichment remains restricted to `subjects[].local_model_observations`;
- handoff candidate recommendations still require deterministic sanitized observation IDs.

Future work may allow LLM-suggested candidate wording only after a stricter validator requires observation citations, rejects unsafe semantics, and compares subject IDs.

#### Phase 7 — Handoff validation rules

Objective: reject unsafe or malformed RedThread execution handoffs before export.

Implemented validation checks:

- top-level schema version is `adopt_redthread.execution_handoff.v0`;
- source declares `raw_artifacts_included: false`;
- summary declares `live_execution_allowed: false`;
- summary declares `redthread_final_gate_required: true`;
- candidate subject IDs match reviewed subjects;
- candidate IDs are unique;
- every candidate includes all required keys;
- every candidate uses an allowed `recommended_redthread_action` enum;
- every candidate has at least one `supporting_sanitized_observations[].observation_id`;
- every candidate keeps `execution_constraints.live_execution_allowed: false`;
- every candidate keeps `execution_constraints.redthread_final_gate_required: true`;
- every candidate keeps `execution_constraints.approved_context_required: true`;
- candidate planning text is scanned for forbidden overclaim language such as confirmed vulnerability, severity, scanner result, release approval, exploit confirmation, or live execution authorization;
- the handoff payload passes the same marker/raw-field audit used by sanitized review artifacts.

The validator writes `redthread_execution_handoff_validation.json` with:

- `passed`
- `error_count`
- `errors`
- `candidate_count`
- `privacy_audit_passed`
- `raw_field_hit_count`
- `marker_hit_count`
- `allowed_recommended_actions`
- `validated_rules`

#### Phase 8 — Operator Markdown UX

Objective: make `redthread_execution_handoff.md` the quickest operator-facing artifact for deciding what RedThread should do next.

The Markdown is organized as:

- summary counts;
- live execution and RedThread final-gate safety flags;
- one candidate section per subject;
- operator summary;
- recommended RedThread action;
- supporting sanitized observation citations;
- missing context;
- RedThread-owned decisions.

The Markdown intentionally uses action enums like `collect_boundary_context`, `evaluate_sanitized_export`, and `prepare_reviewed_replay_plan` so operators can map the recommendation directly to RedThread workflow preparation without reading raw HARs or treating the output as a finding.

#### Phase 9 — Evaluation harness metrics

Objective: measure whether the pipeline produces useful RedThread handoff structure, not merely schema-valid local LLM output.

`local_intent_review_eval.json` now records per-case handoff metrics:

- `execution_candidate_present`
- `next_redthread_action_clear`
- `missing_context_clear`
- `candidate_has_observation_citations`
- `handoff_validation_passed`
- `handoff_useful`

The summary records counts for those metrics. `handoff_useful` requires candidate presence, clear next action, explicit missing-context field, observation citations, passing handoff validation, RedThread final gate enabled, and live execution disabled.

This separates two questions:

1. Did the local model add a useful advisory delta?
2. Did the deterministic handoff give RedThread an actionable, safe next-step candidate?

### Phase 10 — RedThread intent evidence package

Objective: create a primary RedThread-importable artifact instead of another advisory-only review output.

Generated artifacts:

- `redthread_intent_evidence.json`
- `redthread_intent_evidence.md`
- `redthread_intent_evidence_validation.json`
- `redthread_importability_report.json`
- `redthread_importability_report.md`

`redthread_intent_evidence.json` uses schema version `redthread.intent_evidence.v1` and is built deterministically from validated sanitized intent review plus validated execution handoff. It includes:

- `source`: adopt-redthread provenance and source review/handoff references;
- `privacy`: explicit false flags for raw HARs, URLs, headers, cookies, bodies, payloads, and secrets;
- `intent`: target behavior and authority-boundary hypothesis with `not_a_finding: true`;
- `evidence`: RedThread evidence items mapped back to sanitized observation IDs;
- `attack_plan`: RedThread-owned candidate workflow steps, not payloads;
- `redthread_import`: import semantics requiring human review and JudgeAgent confirmation;
- `forbidden_interpretation`: explicit boundary statements that the package is not a finding, severity, exploit proof, release approval, or live execution authorization.

The package is intended to answer: “Can RedThread consume this as candidate evidence without trusting it as a finding?”

### Phase 11 — Evidence package validator

Objective: reject unsafe or non-importable evidence packages before RedThread import.

Validation rejects packages when:

- unsupported schema version is used;
- `source.raw_artifacts_included` is true;
- privacy does not assert `sanitized: true`;
- any raw artifact privacy flag is true;
- authority boundary is missing;
- `intent.not_a_finding` is not true;
- an evidence item lacks a source sanitized observation ID;
- an evidence item lacks limitations;
- evidence strength is outside `weak | moderate | strong`;
- JudgeAgent is not required;
- package is marked eligible for regression;
- package import mode is not `candidate_evidence_not_finding`;
- attack plan authorizes live execution;
- attack plan includes payloads;
- an attack step lacks expected signal, success condition, or supporting evidence IDs;
- an attack step references unknown evidence IDs;
- package text contains forbidden finding/severity/exploit/scanner/release/live-execution language;
- package fails marker/raw-field privacy audit.

`redthread_intent_evidence_validation.json` reports:

- `valid`
- `importable`
- `privacy_safe`
- `execution_ready`
- `finding_claim_detected`
- `regression_ready`
- `judge_agent_required`
- `candidate_workflow_created`
- `blocked_reason`
- `errors`
- `warnings`

### Phase 12 — Attack-plan candidates, not payloads

Objective: give RedThread execution intent without exporting raw payloads or authorizing replay.

Each attack-plan step includes:

- stable step ID;
- subject ID;
- action statement;
- expected signal;
- success condition;
- `requires_raw_payload: false`;
- `requires_live_execution: false`;
- supporting evidence IDs;
- RedThread-owned decisions.

The action text is intentionally high-level, for example collecting approved boundary context or preparing RedThread-owned replay planning. RedThread remains responsible for generating probes, executing approved workflows, judging results, assigning severity, confirming findings, and promoting regression tests.

### Phase 13 — Golden fixture/importability harness

Objective: prove the generated package is consumable as RedThread candidate evidence.

`redthread_importability_report.json` is the local contract harness. It reports:

- `importable`
- `privacy_safe`
- `execution_ready`
- `judge_required`
- `candidate_workflow_created`
- `blocked_reason`
- RedThread consumption contract metadata
- evidence and attack-step counts

The golden path for `cartao_filtered.har` is:

```text
cartao_filtered.har
→ sanitized HAR batch
→ sanitized intent review
→ execution handoff
→ redthread_intent_evidence.json
→ redthread_intent_evidence_validation.json
→ redthread_importability_report.json
```

Success means the package is importable, privacy-safe, creates at least one candidate workflow, cites sanitized evidence, preserves provenance, requires JudgeAgent, and still claims no finding/severity/exploit/release decision.

### Phase 6 — Batch review workflow integration

Objective: integrate the intent review into the existing HAR batch review workflow.

Files likely changed:

- `scripts/build_har_batch_review_workflow.py`
- `tests/test_har_batch_review_workflow.py`
- `docs/offline-har-evidence-batch.md`

Acceptance criteria:

- `make evidence-har-batch-review-workflow` also produces the batch-level `intent_review/` directory.
- The review workflow includes `phase_6_sanitized_intent_review.json/md`.
- Phase 6 records that RedThread evaluation remains required and no confirmed finding is claimed.
- Existing Phase 1-5 review workflow semantics remain unchanged.

Verification:

```bash
make evidence-har-batch-review-workflow HAR_BATCH_OUTPUT=runs/har_batches/latest
python3 -m unittest tests.test_har_batch_review_workflow
make test
```

### Phase 7 — Schema and invariant validation

Objective: write `schema_validation.json` for the intent review and RedThread export artifacts.

Acceptance criteria:

- Validation passes only when required top-level fields and schema versions are present.
- Subject sets match between `intent_review.json` and `redthread_evidence_export.json`.
- Validation fails if local final-decision, confirmed finding, severity, scanner, default live execution, or release override semantics are claimed.
- The validator is deterministic and has no dependency on external schema packages.

Verification:

```bash
python3 -m unittest tests.test_sanitized_intent_review
```

### Phase 8 — RedThread evidence contract preview

Objective: produce `redthread_evidence_contract_preview.json`, a proposal-shaped adapter view aligned to `docs/redthread-evidence-contract-proposal.md` without claiming upstream adoption.

Acceptance criteria:

- Preview includes evidence envelope, workflow evidence, attack context summary, replay/auth diagnostics, promotion recommendation, and next evidence guidance.
- Preview status remains `proposal_preview_not_upstreamed`.
- Promotion recommendation remains `review`, `not_proven: true`, and `redthread_evaluation_required: true`.
- The batch review workflow includes the preview artifact in Phase 6 artifact inventory.

Verification:

```bash
make evidence-intent-review HAR_BATCH_OUTPUT=runs/har_batches/latest
make evidence-har-batch-review-workflow HAR_BATCH_OUTPUT=runs/har_batches/latest
python3 -m unittest tests.test_sanitized_intent_review tests.test_har_batch_review_workflow
make test
```

## Minimum viable proof

The first proof is:

```text
existing sanitized HAR batch
  -> intent_review_context.json
  -> intent_review.json
  -> intent_review.md
  -> redthread_evidence_export.json
  -> privacy/schema tests
```

## What not to build yet

Do not build autonomous HAR scanning, broad endpoint testing, live replay from the intent agent, production execution, automatic attack generation inside adopt-redthread, severity/finding generation, RedThread gate replacement, raw HAR LLM summarization, UI, external scanner integrations, direct Adopt service pull, or automatic replay approval.

## Final recommendation

Proceed with changes. Build the layer as a narrow offline evidence interpretation step. Keep deterministic mode as the default and add LLM mode only after the privacy and schema guardrails are proven.
