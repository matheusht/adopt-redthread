# Live Safe Replay Demo

This is the first real live execution lane.

It is intentionally small.
It only runs:
- policy-allowed cases
- GET only
- safe-read only
- no auth guessing
- no writes

---

## Flow

```text
capture -> normalize -> live_attack_plan.json -> execute allowed GET reads -> save live_safe_replay.json
```

---

## Command from one artifact

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/safe_read_capture.har \
  runs/live_safe_read_pipeline \
  --ingestion zapi \
  --run-live-safe-replay
```

---

## What it writes

- `live_attack_plan.json`
- `live_safe_replay.json`
- `workflow_summary.json`
- normal replay/gate/runtime artifacts too

---

## What this proves

It proves the bridge can now do more than planning.

It can:
- inspect policy
- select allowed live cases
- send real read-only requests
- save execution evidence

Still honest:
- this is not authenticated live replay yet
- this is not live write execution
- this is not full workflow/session replay
