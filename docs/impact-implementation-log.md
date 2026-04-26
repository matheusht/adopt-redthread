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

### Still open

The implementation has completed the first architecture slice and hero proof. Remaining impact work:

1. choose and run a second proof target
2. update the RedThread wiki after the second proof confirms the evidence model beyond one workflow family

