# Adopt RedThread Impact Execution Checklist

## Architecture review

Status: **approved with one sequencing constraint**.

The direction is architecturally correct:

- `adopt-redthread` remains the field lab and integration bridge.
- `redthread` remains the generic security assurance engine.
- Runtime evidence must prove a pattern before generic code moves upstream.
- Integration glue stays local; only reusable workflow trust contracts move upstream.

The one sequencing constraint is important:

> Do not upstream workflow logic into `redthread` until `adopt-redthread` can show row-level runtime proof: planned binding, reviewed binding, applied binding, and failure state.

## Caveman law

- Adopt builds.
- Bridge proves on real app shapes.
- RedThread evaluates generic trust evidence.
- No silent mutation.
- No browser product in RedThread.
- No ATP-only hacks upstream.

## Week 1 — impact in `adopt-redthread`

### 1. Runtime-row binding truth

Goal: each executed workflow step should show whether response bindings were planned and actually applied.

Checklist:

- [x] Add planned binding records to step evidence.
- [x] Keep applied binding records in step evidence.
- [x] Add per-step binding application summary.
- [x] Add top-level workflow replay binding application summary.
- [x] Preserve existing extracted/applied binding behavior.
- [x] Add focused tests for reviewed alias replay evidence.

Primary files:

- `adapters/live_replay/workflow_bindings.py`
- `adapters/live_replay/workflow_state.py`
- `adapters/live_replay/workflow_executor.py`
- `adapters/live_replay/workflow_results.py`

### 2. Gate and RedThread handoff truth

Goal: `gate_verdict.json` and `redthread_runtime_inputs.json` should carry runtime binding application facts, not only planning facts.

Checklist:

- [x] Add planned/applied binding counts to bridge workflow context.
- [x] Rebuild runtime inputs after live workflow replay when runtime evidence exists.
- [x] Add binding application summary to gate evidence counts.
- [x] Add plain-text gate notes for planned/applied binding counts.
- [x] Keep zero-alias and no-replay runs stable.

Primary files:

- `adapters/redthread_runtime/runtime_bridge_context.py`
- `adapters/redthread_runtime/runtime_adapter.py`
- `adapters/bridge/workflow.py`
- `adapters/bridge/gate_evidence.py`
- `scripts/prepublish_gate.py`

### 3. Hero flow

Goal: one polished end-to-end bridge run with artifacts worth showing.

Checklist:

- [x] Pick one hero input.
- [x] Run plan -> replay -> gate/runtime handoff for deterministic binding-truth proof.
- [x] Generate artifacts under ignored `runs/hero_binding_truth`.
- [x] Add `scripts/generate_hero_binding_truth.py` so the golden demo is reproducible instead of checked in.
- [x] Add `tests/test_golden_demo_truth.py` so docs cannot claim `approve` while the generated summary says `block`.
- [x] Document what to inspect in `docs/hero-flow-binding-truth.md`.

Important artifacts:

- `live_workflow_plan.json`
- `live_workflow_replay.json`
- `redthread_runtime_inputs.json`
- `gate_verdict.json`
- `workflow_summary.json`

### 4. Deterministic reviewed-write reference target

Goal: give the operator one local command that proves the realistic reviewed-write path without external app drift or manual auth/write/binding setup.

Current reference:

- `make demo-reviewed-write-reference`
- output: `runs/reviewed_write_reference/evidence_report.md`
- synthetic ATP-like endpoints: `GET /api/chats`, `POST /api/chats`, `POST /api/chat`
- fixture count: 5
- live workflow replay: executed and successful
- response bindings: 3 declared, 3 applied
- RedThread replay verdict: passed
- final local gate decision: `review`
- reason: `manual_review_required_for_write_paths`

Checklist:

- [x] Add deterministic local ATP-like reviewed-write server.
- [x] Hide HAR/auth/write/binding setup behind `make demo-reviewed-write-reference`.
- [x] Generate `runs/reviewed_write_reference/evidence_report.md`.
- [x] Keep the final result as `review`, not `approve`.

### 5. Real ZAPI reference target

Goal: prove the evidence model on a real ZAPI-derived workflow family without pretending reviewed write paths should auto-approve.

Current reference:

- `runs/atp_tennis_01_live_bound/`
- input: `demo_session_filtered.har`
- ingestion: `zapi`
- live workflow replay: executed and successful
- response bindings: 3 declared, 3 applied
- RedThread replay verdict: passed
- final local gate decision: `review`
- reason: `manual_review_required_for_write_paths`

Checklist:

- [x] Inspect available candidate captures.
- [x] Promote `runs/atp_tennis_01_live_bound/` as the current real ZAPI reference demo.
- [x] Document it as `review`, not `approve`.
- [x] Add checked-in sanitized expectations at `fixtures/reference_demos/atp_tennis_zapi_reference_expected.json`.
- [x] Add `make check-zapi-reference` to validate local HAR + local run artifacts without checking in secrets.
- [x] Document the evidence standard in `docs/zapi-reference-demo.md`.

## Week 2 — tiny generic upstream into `redthread`

### 5. Replay bundle context seam

Goal: `redthread` can accept workflow trust context without depending on Adopt/ZAPI/HAR code.

Checklist:

- [x] Add optional `bridge_workflow_context` to RedThread `ReplayBundle`.
- [x] Include same context inside exported `redthread_replay_bundle` from bridge.
- [x] Keep context generic and dict-shaped.
- [x] Do not import bridge code into RedThread.

Primary files:

- `../redthread/src/redthread/evaluation/replay_corpus.py`
- `../redthread/src/redthread/evaluation/promotion_gate.py`
- `adapters/redthread_runtime/runtime_adapter.py`

### 6. RedThread verdict surfacing

Goal: RedThread gate verdict surfaces workflow context for operators.

Checklist:

- [x] Include workflow context summary in promotion gate result.
- [x] Add tests proving context survives validation.
- [x] Do not enforce policy on this field yet.

Primary tests:

- `../redthread/tests/test_agentic_replay_promotion.py`
- `tests/test_redthread_runtime_adapter.py`

## Verification commands

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

Focused RedThread pack:

```bash
../redthread/.venv/bin/python -m pytest \
  ../redthread/tests/test_agentic_replay_promotion.py \
  -q
```

## Done means

- Runtime replay rows show planned/reviewed/applied binding facts.
- Runtime replay blocks preserve binding failure ids and failure counts.
- Gate notes show binding application counts.
- RedThread runtime inputs carry workflow context after live replay.
- RedThread replay bundle accepts and surfaces generic workflow context.
- Docs explain what moved upstream and what stayed bridge-local.
