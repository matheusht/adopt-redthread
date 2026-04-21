# RedThread Runtime Demo

This demo shows the first real bridge seam into RedThread itself.

Before this step, the repo stopped at:
- normalized fixtures
- replay-pack planning
- prototype gate decisions

Now it goes farther.
It can turn a bridge fixture bundle into:
- a real RedThread replay bundle
- real RedThread dry-run campaign inputs

Then it can run both against RedThread code.

---

## What this demo proves

This demo proves three things:

1. bridge fixtures can be converted into `ReplayBundle`-shaped data
2. that replay bundle can be evaluated by RedThread's real promotion-gate code
3. one generated case can run through RedThread's real dry-run campaign path

This is a real step forward.

But stay honest.
It does **not** prove:
- live attack execution against a real Adopt-managed runtime
- full fidelity target prompts from production systems
- final publish-gate maturity

---

## Canonical flow

Start from the HAR-derived fixture bundle:

```bash
python3 scripts/export_redthread_runtime_inputs.py \
  fixtures/replay_packs/sample_har_fixture_bundle.json \
  fixtures/replay_packs/sample_har_redthread_runtime_inputs.json
```

Evaluate the replay traces with RedThread's actual promotion gate:

```bash
../redthread/.venv/bin/python scripts/evaluate_redthread_replay.py \
  fixtures/replay_packs/sample_har_redthread_runtime_inputs.json \
  fixtures/replay_packs/sample_har_redthread_replay_verdict.json
```

Run one generated bridge case through a real RedThread dry-run campaign:

```bash
../redthread/.venv/bin/python scripts/run_redthread_dryrun.py \
  fixtures/replay_packs/sample_har_redthread_runtime_inputs.json \
  fixtures/replay_packs/sample_har_redthread_dryrun_case0.json
```

Or use the Makefile shortcuts:

```bash
make demo-redthread-runtime
make demo-redthread-dryrun
```

---

## What gets exported

The runtime export contains two big parts.

### 1. `redthread_replay_bundle`

This is the bridge copy of a RedThread replay payload.
Each trace carries:
- a threat label
- the original bridge fixture path and method
- a generated `ActionEnvelope`
- an expected authorization outcome
- optional canary containment expectations

### 2. `campaign_cases`

These are dry-run campaign seeds for RedThread.
Each case carries:
- objective
- system prompt
- rubric
- algorithm hint
- persona count

These are generated seeds.
Not ground truth production prompts.
That matters.

---

## Why this matters

This step changes the repo story.

Old story:
- bridge plans security work

New story:
- bridge can hand off into real RedThread replay logic
- bridge can hand off into real RedThread dry-run execution logic

That is much closer to a true adapter layer.

---

## Safety and scope

Use the RedThread repo virtualenv for the real integration commands:
- `../redthread/.venv/bin/python`

Reason:
- bridge repo stays light
- RedThread runtime evaluation needs RedThread dependencies

Keep the scope honest:
- generated dry-run cases are bridge seeds
- real live agent/runtime hookup is still later work
