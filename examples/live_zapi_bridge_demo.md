# Live ZAPI Bridge Demo

This is the new one-command workflow.

Goal:
1. run ZAPI against a real target URL
2. save HAR output automatically
3. feed the selected HAR into `adopt-redthread`
4. export RedThread runtime inputs
5. run replay evaluation
6. run one RedThread dry-run case
7. write one final summary file

---

## Command

Preferred near-term mode is **interactive**.
That means a human drives the browser and decides when capture is done.

```bash
python3 scripts/run_live_zapi_bridge.py \
  "https://www.talkie-ai.com/chat/grimace-122539993063541" \
  runs/talkie_live_run \
  --zapi-repo /tmp/pi-github-repos/adoptai/zapi \
  --interactive \
  --operator-notes "login, browse chat, open settings"
```

If you want the capture to auto-save after a fixed time:

```bash
python3 scripts/run_live_zapi_bridge.py \
  "https://www.talkie-ai.com/chat/grimace-122539993063541" \
  runs/talkie_live_run \
  --zapi-repo /tmp/pi-github-repos/adoptai/zapi \
  --duration-seconds 45
```

---

## What it writes

Inside the output directory:

- `zapi_capture/session.har`
- `zapi_capture/session_filtered.har`
- `zapi_capture/capture_metadata.json`
- `bridge_outputs/fixture_bundle.json`
- `bridge_outputs/replay_plan.json`
- `bridge_outputs/gate_verdict.json`
- `bridge_outputs/redthread_runtime_inputs.json`
- `bridge_outputs/redthread_replay_verdict.json`
- `bridge_outputs/redthread_dryrun_case0.json`
- `bridge_outputs/workflow_summary.json`
- `live_zapi_bridge_summary.json`

---

## Why this matters

Before this step, the workflow was split across multiple manual commands.

Now the path is much closer to the intended product story:

- ZAPI discovers
- Adopt RedThread translates
- RedThread evaluates
- one summary file tells you what happened

Still honest:
- this is not yet fully automatic live attack execution against a real production runtime
- it is a stronger live bridge runner, not the final platform state
