# Live Workflow Replay Demo

This is the first bounded workflow lane.

It is not full browser automation.
It is not autonomous session attack planning.

It does one simple thing:
- take grouped multi-step cases from `live_workflow_plan.json`
- run them in order
- stop on first failure
- reuse the same per-step auth and write guardrails from the single-request lane

---

## Command

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/workflow_capture.har \
  runs/live_workflow_pipeline \
  --ingestion zapi \
  --run-live-workflow-replay
```

If some workflow steps need reviewed auth context:

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/workflow_capture.har \
  runs/live_workflow_pipeline \
  --ingestion zapi \
  --run-live-workflow-replay \
  --allow-reviewed-auth \
  --auth-context /path/to/approved_auth_context.json
```

---

## What gets written

The workflow lane writes:
- `live_workflow_plan.json`
- `live_workflow_replay.json`

`live_workflow_plan.json` says:
- which cases belong to one workflow
- what order they run in
- whether review is needed

`live_workflow_replay.json` says:
- which workflows ran
- which step failed or blocked
- how many steps completed

---

## Safety truth

This lane still does **not**:
- invent new session state
- do browser-side workflow automation
- bypass auth/write review rules
- continue after a failed step

So this is a real Phase 6 step.
But it is still bounded and honest.
