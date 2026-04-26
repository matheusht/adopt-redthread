# Hero Flow: Runtime Binding Truth

This is the first demo-grade proof slice for impact work.

It proves the bridge can show the full chain:

1. workflow step declares response bindings
2. replay extracts response values from an earlier step
3. later step applies the bindings at runtime
4. replay row records planned and applied facts
5. gate/runtime handoff receives the generic binding summary

## Artifact set

Generated artifacts live under:

```text
runs/hero_binding_truth/
```

Key files:

- `live_attack_plan.json` — deterministic two-step live plan
- `live_workflow_plan.json` — workflow plan with response bindings
- `live_workflow_replay.json` — runtime row evidence
- `redthread_runtime_inputs.json` — bridge context passed toward RedThread
- `gate_verdict.json` — gate decision and notes
- `workflow_summary.json` — short operator summary

## Current proof result

From `runs/hero_binding_truth/workflow_summary.json`:

```json
{
  "live_workflow_replay_count": 1,
  "live_workflow_binding_application_summary": {
    "planned_response_binding_count": 2,
    "applied_response_binding_count": 2,
    "unapplied_response_binding_count": 0,
    "workflow_count_with_planned_bindings": 1,
    "workflow_count_with_applied_bindings": 1,
    "binding_application_failure_counts": {},
    "failed_binding_ids": []
  },
  "gate_decision": "approve"
}
```

## What to inspect

### 1. Planned binding contract

Open:

```text
runs/hero_binding_truth/live_workflow_plan.json
```

Inspect step `step_b`. It has two response bindings:

- `account_id`: source `step_a` response JSON path `account.id` -> later request URL placeholder `{{account_id}}`
- `trace_id`: source `step_a` response header `x-trace-id` -> later request URL placeholder `{{trace_id}}`

### 2. Runtime replay row evidence

Open:

```text
runs/hero_binding_truth/live_workflow_replay.json
```

Inspect:

```text
results[0].results[1].workflow_evidence
```

Expected fields:

- `planned_response_bindings`
- `applied_response_bindings`
- `binding_application_summary`

This is the important impact surface. It tells the operator that the bridge did not merely plan a binding. It applied it in the actual replay row.

### 3. RedThread handoff context

Open:

```text
runs/hero_binding_truth/redthread_runtime_inputs.json
```

Inspect:

```text
bridge_workflow_context
redthread_replay_bundle.bridge_workflow_context
```

Both should carry the same generic context:

- planned binding count
- applied binding count
- unapplied binding count
- workflow count with planned/applied bindings
- failure counts

This is the upstream-safe seam. No ZAPI/HAR/test-server specifics are required by RedThread.

### 4. Gate notes

Open:

```text
runs/hero_binding_truth/gate_verdict.json
```

Inspect `notes` for:

- `live_workflow_planned_response_binding_count=2`
- `live_workflow_applied_response_binding_count=2`
- `live_workflow_unapplied_response_binding_count=0`
- `live_workflow_binding_application_failures=none`

## Reproduce the artifact

The checked-in tests are the durable verification path:

```bash
python3 -m unittest \
  tests.test_live_workflow_bindings \
  tests.test_reviewed_binding_alias_builder \
  tests.test_reviewed_binding_alias_loop \
  tests.test_redthread_runtime_adapter \
  tests.test_prepublish_gate \
  -v
```

The artifact was generated from the same deterministic local binding server used by `tests/live_workflow_binding_support.py`. It does not require external credentials.

## Why this matters

Before this slice, the bridge could say a binding was planned or reviewed. Now it can show runtime truth:

- planned: yes
- reviewed/approved: yes
- applied: yes
- failed/unapplied: counted and exposed when it happens

That is the proof RedThread should consume: generic trust evidence, not Adopt-specific glue.
