# Adopt RedThread

Adopt RedThread is the bridge repo between **Adopt AI** and **RedThread**.

It exists to prove one clear idea:

> **Adopt builds the agent plane. RedThread attacks, validates, and hardens it.**

## Current status

This repo is already integrated at the **prototype bridge** level.

What works today:
- ingest a ZAPI-style discovery export
- ingest a real HAR-shaped ZAPI capture and extract app-relevant endpoints
- ingest a NoUI MCP server output (`manifest.json` + `tools.json`)
- normalize all three discovery lanes into RedThread-friendly fixtures
- ingest an Adopt-style action catalog
- generate replay-pack groups
- generate a prototype pre-publish gate verdict
- export normalized fixtures into real RedThread replay-bundle inputs
- evaluate those replay traces with RedThread's actual promotion-gate code
- generate a machine-readable live attack plan with execution policy fields
- execute the first policy-gated live safe-read replay lane for allowed GET cases
- run generated bridge cases through a real RedThread dry-run campaign path
- run a one-command bridge workflow from one artifact input
- run a live ZAPI capture and hand its selected HAR into that one-command workflow
- keep that live capture explicitly human-guided with saved operator metadata when needed

What is **not** live yet:
- direct pull from real Adopt services
- broad support for all real-world NoUI output families beyond the first MCP server shape
- live authenticated replay with real session/header reuse
- reviewed write execution lanes
- fully automatic live ZAPI runtime -> RedThread attack loop against a real Adopt-managed session
- production-grade publish gating

So the honest status is:

- **yes, the bridge prototype exists and runs end to end**
- **no, this is not a full live integration yet**

## Why this repo exists

`redthread/` stays standalone.

That repo is the main portfolio project and should keep its own identity:
- autonomous AI red-teaming
- replay and validation
- self-healing
- runtime-truth and agentic-security work

This repo is different.
It is the integration lab for:
- ZAPI ingestion
- Adopt action/tool mapping
- NoUI MCP/tool output mapping
- replay-pack generation
- RedThread runtime export
- pre-publish security gates
- recruiter-ready demos for practical agent hardening

## Quick architecture

```mermaid
flowchart TD
    A[Real app or website] --> B[ZAPI or NoUI discovery]
    B --> C[Adopt tools and actions]
    C --> D[Adopt RedThread adapters]
    D --> E[Normalized RedThread fixtures]
    E --> F[Replay packs]
    F --> G[Pre-publish gate verdict]
    G --> H[Approve, review, or block]
```

## Repo goals

Short term:
- ingest ZAPI-discovered API metadata
- ingest real HAR-derived discovery captures
- classify endpoint risk
- convert the catalog into RedThread-friendly fixtures
- generate first replay packs

Medium term:
- expand the new RedThread runtime export beyond dry-run seeds into stronger execution adapters
- test Adopt-generated actions with RedThread attack suites
- add multi-turn workflow replay
- add pre-publish security gate experiments

Long term:
- become a practical reference implementation for agent-builder security assurance

## How to test locally

### Run the test suite

```bash
make test
```

### Run the full local demo flow

```bash
make demo-all
```

This will:
1. ingest sample ZAPI discovery
2. ingest sample Adopt actions
3. generate a replay plan
4. generate a pre-publish gate verdict

### Run commands one by one

```bash
make demo-zapi
make demo-zapi-har
make demo-redthread-runtime
make demo-redthread-dryrun
make demo-noui
make demo-noui-redthread
make demo-adopt-actions
make demo-gate
make demo-bridge-pipeline
```

## Key demo files

Inputs:
- `fixtures/zapi_samples/sample_discovery.json`
- `fixtures/zapi_samples/sample_filtered_har.json`
- `fixtures/noui_samples/expedia_stay_search/manifest.json`
- `fixtures/noui_samples/expedia_stay_search/tools.json`
- `fixtures/adopt_action_samples/sample_actions.json`

Generated outputs:
- `fixtures/replay_packs/sample_fixture_bundle.json`
- `fixtures/replay_packs/sample_har_fixture_bundle.json`
- `fixtures/replay_packs/sample_noui_fixture_bundle.json`
- `fixtures/replay_packs/sample_action_fixture_bundle.json`
- `fixtures/replay_packs/sample_replay_plan.json`
- `fixtures/replay_packs/sample_har_replay_plan.json`
- `fixtures/replay_packs/sample_gate_verdict.json`
- `fixtures/replay_packs/sample_har_gate_verdict.json`
- `fixtures/replay_packs/sample_har_redthread_runtime_inputs.json`
- `fixtures/replay_packs/sample_har_live_attack_plan.json`
- `fixtures/replay_packs/sample_har_redthread_replay_verdict.json`
- `fixtures/replay_packs/sample_har_redthread_dryrun_case0.json`
- `fixtures/replay_packs/sample_noui_redthread_runtime_inputs.json`
- `fixtures/replay_packs/sample_noui_redthread_replay_verdict.json`
- `fixtures/replay_packs/sample_noui_redthread_dryrun_case0.json`
- `runs/sample_har_pipeline/` — one-command sample pipeline outputs

## Docs

- `docs/strategy.md` — why the repo split exists and what each system owns
- `docs/architecture.md` — proposed end-to-end integration architecture
- `docs/live-workflow-explained.md` — simple explanation of what is live now, what is not, and how the workflow should act
- `docs/full-live-loop-diagram.md` — blunt diagrams for what the future full live loop actually means
- `docs/live-attack-implementation-plan.md` — step-by-step plan for getting from human-guided ZAPI capture to policy-controlled live RedThread execution
- `docs/strix-fit-assessment.md` — blunt assessment of whether Strix should influence or integrate with this project
- `docs/recruiter-demo-notes.md` — how to present this repo in outreach
- `examples/zapi_to_replay_demo.md` — clean recruiter walkthrough for catalog-style input
- `examples/har_to_replay_demo.md` — clean walkthrough for HAR-derived real-input intake
- `examples/redthread_runtime_demo.md` — walkthrough from bridge fixtures into real RedThread replay and dry-run execution inputs
- `examples/noui_to_redthread_demo.md` — walkthrough from NoUI MCP output into normalized fixtures and then into RedThread
- `examples/live_zapi_bridge_demo.md` — one-command live ZAPI capture into bridge outputs and RedThread checks

## Repo structure

- `adapters/zapi/` — ZAPI ingestion code for catalog-style exports and HAR-derived captures
- `adapters/adopt_actions/` — Adopt action/tool catalog mapping
- `adapters/noui/` — NoUI MCP manifest/tools adaptation
- `adapters/redthread_runtime/` — bridge export into real RedThread replay and dry-run campaign inputs
- `fixtures/zapi_samples/` — sample discovery artifacts
- `fixtures/adopt_action_samples/` — sample Adopt action catalogs
- `fixtures/replay_packs/` — generated replay suites and gate verdicts
- `scripts/` — helper scripts and MVP entrypoints, including one-command workflow runners
- `tests/` — zero-dependency local test suite
- `examples/` — end-to-end demos

## Working rule

If logic is generic and reusable, it should probably belong upstream in `redthread/`.

If logic is Adopt-specific, integration-specific, HAR-shape-specific, or demo-specific, it belongs here.

## NoUI support

This repo now supports one real NoUI output shape:
- MCP server directory with `manifest.json` + `tools.json`

Current NoUI bridge behavior:
- loads the server manifest and tool inventory
- maps auth/runtime/tool metadata into the same normalized fixture model used by ZAPI and Adopt actions
- preserves downstream compatibility with replay-pack generation and RedThread runtime export

This matters because NoUI gives a stronger app/runtime view than plain API discovery alone.
It tells us:
- auth strategy
- MCP/runtime execution style
- tool parameter shapes
- response field shapes

That gives RedThread more realistic surfaces to validate.

## One-command workflow support

This repo now has two higher-level runners:

- `scripts/generate_live_attack_plan.py` — build `live_attack_plan.json` from one supported bridge input
- `scripts/run_live_safe_replay.py` — execute only policy-allowed live safe-read GET cases from a plan
- `scripts/run_bridge_pipeline.py` — one input artifact in, full bridge outputs out
- `scripts/run_live_zapi_bridge.py` — live ZAPI capture in, then full bridge workflow out

That means the intended operator story is now much closer to real life:
1. capture or provide one discovery artifact
2. normalize it
3. generate replay and gate artifacts
4. export RedThread runtime inputs
5. run RedThread replay evaluation
6. run one RedThread dry-run case
7. inspect one final summary JSON

Still honest:
- this is workflow automation around the bridge we already had
- it is not yet full live RedThread attack execution against a real production runtime

## Real RedThread runtime support

This repo now has a real bridge seam into RedThread itself.

From a normalized fixture bundle, it can now generate:
- a **RedThread replay bundle** shaped for `redthread.evaluation.replay_corpus.ReplayBundle`
- a set of **dry-run campaign cases** shaped for `RedThreadEngine.run(...)`

The bridge also ships local scripts to:
- evaluate the replay bundle with RedThread's real promotion-gate code
- run one generated case through a real RedThread dry-run campaign

This is important because the bridge is no longer only doing planning.
It now reaches one real RedThread replay path and one real RedThread dry-run execution path.

Still honest:
- this is not yet live attack execution against a real Adopt-managed runtime
- generated campaign prompts are bridge seeds, not production target truth
- this is still a bridge-layer prototype, not a full platform integration

## Real HAR support

This repo now supports two ZAPI intake lanes:

1. **catalog-style** JSON with an `endpoints` list
2. **HAR-style** JSON with `log.entries`

The HAR lane is intentionally conservative.
It:
- keeps app-like API calls
- drops obvious static assets
- drops common analytics and third-party transport noise
- dedupes by method + path
- emits the same normalized fixture shape used by the replay-pack and gate scripts

That keeps the RedThread boundary clean:
- Adopt discovery gives us better app-specific surfaces
- this repo adapts those surfaces
- RedThread remains the engine that attacks, replays, validates, and hardens

## Safety rule for HAR files

Raw HAR files may contain:
- cookies
- tokens
- user ids
- device ids
- message content
- internal response payloads

So raw HAR files should stay local and out of git history.
The commit-safe artifact is the normalized fixture bundle, not the raw capture.

## RedThread interpreter note

The replay-evaluation and dry-run execution demos use the RedThread repo's local virtualenv by default:

- `../redthread/.venv/bin/python`

Why:
- the bridge repo stays zero-dependency for its own tests where possible
- real replay evaluation needs RedThread's actual dependencies and modules
