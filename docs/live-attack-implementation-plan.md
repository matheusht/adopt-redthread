# Live Attack Implementation Plan

## Blunt answer

We should build live attack mode in **controlled steps**.

Not like this:
- auto-discover everything
- auto-send risky requests
- hope it works

Like this:
- human captures reality first
- bridge normalizes it
- policy classifies it
- only low-risk read cases can run automatically
- everything riskier stays review-gated

That is now the implemented shape.

---

## What is implemented now

## Phase status

| Phase | Status | What it does |
|---|---|---|
| Phase 1 — Interactive capture | done | human-guided ZAPI capture is now an explicit first-class mode |
| Phase 2 — Machine-readable live plan | done | bridge emits `live_attack_plan.json` with execution policy per case |
| Phase 3 — Safe-read live lane | done | policy-allowed GET read cases can be executed live |
| Phase 4 — Auth-aware safe reads | done | reviewed auth-bound GET read cases can run only with explicit approved auth context |
| Phase 5 — Reviewed writes in staging | done | reviewed non-destructive write cases can run only in staging with explicit per-case approved write context |

So the current system now has a real ladder:

```text
interactive capture -> normalized fixtures -> live attack plan -> safe-read live replay -> auth-aware safe-read replay -> reviewed staging writes -> replay gate -> dry-run
```

Still honest:
- writes are not auto-executed
- only the first non-destructive staging write lane exists
- full session/workflow replay is not finished

---

## Main rule

The system must treat **human-guided capture as the official near-term path**.

Reason:
- real apps are messy
- login flows are messy
- MFA is messy
- app navigation is messy
- a human reaches the meaningful flows faster than brittle auto-browse logic

So the correct foundation is:

```text
human-guided discovery first
automation second
riskier live execution last
```

---

## Final architecture shape

```mermaid
flowchart TD
    A[Human starts live ZAPI capture] --> B[Human explores app manually]
    B --> C[HAR capture + capture metadata]
    C --> D[adopt-redthread normalization]
    D --> E[live_attack_plan.json]
    E --> F{execution policy}
    F -->|live_safe_read| G[execute GET replay now]
    F -->|live_safe_read_with_review| H[hold for human review]
    F -->|manual_review| H
    F -->|sandbox_only| I[block from live]
    G --> J[save live_safe_replay.json]
    D --> K[RedThread runtime export]
    K --> L[replay evaluation]
    K --> M[dry-run campaign]
    J --> N[final workflow summary]
    L --> N
    M --> N
```

---

## Phase 1 — Interactive capture

## Goal

Make human-guided capture explicit, normal, and documented.

## Delivered

### CLI support

`run_live_zapi_bridge.py` now supports:
- `--interactive`
- `--operator-notes`

### Capture metadata

Live capture now writes:
- `zapi_capture/capture_metadata.json`

That metadata records:
- URL
- capture mode
- completion mode
- selected HAR
- operator notes
- estimated HAR analysis stats

### Why it matters

This turns manual browsing into a **real supported workflow**, not a hack.

### Current operator command

```bash
python3 scripts/run_live_zapi_bridge.py \
  "https://example.com" \
  runs/live_zapi_run \
  --zapi-repo /tmp/pi-github-repos/adoptai/zapi \
  --interactive \
  --operator-notes "login, browse billing, open profile"
```

---

## Phase 2 — Machine-readable live plan

## Goal

Stop relying on prose-only future plans.
Generate a real plan artifact from normalized fixtures.

## Delivered

### New artifact

The bridge now emits:
- `live_attack_plan.json`

### Each case now includes

- `execution_mode`
- `approval_mode`
- `target_env`
- `auth_context_required`
- `max_replay_attempts`
- `side_effect_risk`
- `request_blueprint`
- `allowed`

### Current execution modes

- `live_safe_read`
- `live_safe_read_with_review`
- `manual_review`
- `sandbox_only`

### Current policy logic

Auto-allowed only when all of this is true:
- normalized case is `safe_read`
- method is `GET`
- no auth context is required

Everything else is review-gated or blocked.

### Why it matters

This gives us a machine-readable boundary between:
- what can run now
- what needs review
- what must stay out of live execution

---

## Phase 3 — Safe-read live lane

## Goal

Execute the first real live requests, but only in the safest policy lane.

## Delivered

### New execution lane

The bridge now supports:
- live execution of policy-allowed GET cases only

### New script

- `scripts/run_live_safe_replay.py`

### New workflow flag

- `scripts/run_bridge_pipeline.py --run-live-safe-replay`
- `scripts/run_live_zapi_bridge.py --run-live-safe-replay`

### New artifact

When enabled, the workflow writes:
- `live_safe_replay.json`

### What the executor does

It will:
- load `live_attack_plan.json`
- select only `allowed=true` cases
- only execute `GET`
- send the request to the captured URL
- save response status, content type, and a short body preview

### What it will not do

It will **not**:
- replay writes
- invent auth/session state
- replay risky POST/PUT/PATCH/DELETE cases
- bypass review gates

### Why it matters

This is the first real step from:
- artifact planning
- into actual controlled live execution

without jumping straight into dangerous automation.

---

## Current commands

## Build only the live attack plan

```bash
python3 scripts/generate_live_attack_plan.py \
  fixtures/zapi_samples/sample_filtered_har.json \
  fixtures/replay_packs/sample_har_live_attack_plan.json \
  --ingestion zapi
```

## Run full pipeline with live safe-read lane enabled

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/capture.har \
  runs/live_safe_read_pipeline \
  --ingestion zapi \
  --run-live-safe-replay
```

## Run live ZAPI capture + bridge + safe-read lane

```bash
python3 scripts/run_live_zapi_bridge.py \
  "https://example.com" \
  runs/live_capture_pipeline \
  --interactive \
  --run-live-safe-replay
```

---

## What is intentionally still blocked

These are still out of the live auto-execution lane:

- authenticated read replay that needs real session/header reuse
- all writes
- destructive flows
- payment/account mutation flows
- admin or cross-tenant risk
- multi-step workflow execution

That is correct.

---

## Why this phase order is correct

Because it gives us:

### first
reality capture

### then
normalized planning

### then
safe execution

### then later
reviewed writes and session-aware execution

This is safer and easier to explain.

---

## What comes next later

These are future phases, not part of the now-completed ladder.

## Phase 4 — Auth-aware safe reads

## Goal

Reuse approved captured auth context safely for low-risk authenticated GET replay.

## Delivered

### New rule

Auth-bound safe reads are no longer treated the same as anonymous safe reads.

They now become:
- `live_safe_read_with_approved_auth`

That means:
- not auto-run by default
- still human-reviewed
- only executable when explicit approved auth context is supplied

### New executor support

The safe replay executor now accepts:
- `--auth-context`
- `--allow-reviewed-auth`

### Approved auth context shape

```json
{
  "approved": true,
  "target_hosts": ["example.com"],
  "allowed_header_names": ["authorization", "cookie"],
  "headers": {
    "authorization": "Bearer demo-token"
  }
}
```

### Safety rules

Even with auth context, the executor still only allows:
- `GET`
- safe-read cases
- approved hosts only
- allowlisted auth header names only
- headers already observed in the captured request blueprint only

So it still does **not**:
- invent new auth headers
- send auth to the wrong host
- replay writes
- bypass approval

### Why it matters

This is the first real bridge from:
- captured authenticated reality
- into bounded authenticated replay

without pretending full session-aware live attack is done.

## Phase 5 — Reviewed writes in staging

## Goal

Allow only reviewed non-destructive writes in staging.

## Delivered

### New rule

A narrow slice of write cases can now become:
- `live_reviewed_write_staging`

That only happens when the case is:
- `POST`, `PUT`, or `PATCH`
- non-destructive
- not admin/payment/account family
- single-tenant
- still human-reviewed

### New write context

The executor now accepts:
- `--write-context`
- `--allow-reviewed-writes`

### Approved write context shape

```json
{
  "approved": true,
  "target_env": "staging",
  "target_base_url": "https://staging.example.com",
  "target_hosts": ["staging.example.com"],
  "case_approvals": {
    "post_api_v1_user_preferences": {
      "method": "POST",
      "path": "/api/v1/user/preferences",
      "headers": {
        "authorization": "Bearer stage-token"
      },
      "json_body": {
        "theme": "dark"
      }
    }
  }
}
```

### Safety rules

Even here, the executor still requires:
- explicit `approved: true`
- `target_env: staging`
- host allowlist match
- per-case method/path match
- explicit operator-approved body

So it still does **not**:
- replay arbitrary captured write bodies
- auto-run writes
- allow destructive writes
- allow prod-targeted reviewed writes

### Why it matters

This is the first real move from:
- read-only live execution
- into bounded reviewed write execution

without pretending full live workflow attack is finished.

## Future Phase 6 — Workflow/session live execution

Goal:
- replay multi-step workflows, not single requests only

Needs:
- step sequencing
- state tracking
- workflow abort rules
- richer judgment

---

## Final judgment

The right live-attack rollout was:
1. make interactive capture official
2. emit a real live attack plan
3. execute only policy-allowed safe reads

That is now done.

This means the current system is no longer only talking about live attack mode.
It now has:
- an official capture path
- a real policy plan artifact
- a first live execution lane

Still honest:
- full live attack mode is **not** finished
- but the foundation is now real and properly bounded
