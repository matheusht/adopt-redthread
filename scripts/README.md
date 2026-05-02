# Scripts

This folder will hold small MVP entrypoints.

Current scripts:
- `ingest_zapi.py` — normalize ZAPI discovery output or HAR-derived captures
- `ingest_noui.py` — normalize a NoUI MCP server output into fixtures
- `ingest_adopt_actions.py` — normalize an Adopt action catalog into fixtures
- `generate_replay_pack.py` — turn normalized fixtures into replay-pack groups
- `prepublish_gate.py` — prototype gate for approve/review/block decisions, now able to include live replay/workflow evidence and RedThread replay verdicts
- `generate_live_attack_plan.py` — create `live_attack_plan.json` with execution policy for each normalized fixture
- `generate_hero_binding_truth.py` — regenerate the deterministic golden demo artifacts under `runs/hero_binding_truth/`
- `generate_reviewed_write_reference.py` — run the deterministic ATP-like reviewed-write reference demo and hide auth/write/binding setup from the operator
- `build_evidence_report.py` — build a markdown evidence report from a bridge run directory, including plain-English block reasons and rerun triggers
- `build_evidence_matrix.py` — build a local approve/review/block evidence matrix with responsible decision agents, rerun triggers, and sanitized summaries only
- `build_reviewer_packet.py` — build a sanitized reviewer handoff packet that points to the report/matrix, includes silent-review questions and an observation template, records artifact hashes, and audits generated markdown for configured sensitive markers plus required handoff sections
- `build_external_review_handoff.py` — copy only the sanitized reviewer-facing artifacts into an external human cold-review handoff directory, with instructions, hashes, marker audit, and explicit non-validation status until filled observations are summarized
- `build_external_review_session_batch.py` — create isolated per-review session folders from the sanitized external handoff, with allowed artifacts, blank observation files, and summary commands; not validation by itself
- `build_external_validation_readout.py` — read the external session batch plus sanitized reviewer-observation summaries and report waiting/needs-more/ready/privacy-blocked validation state without raw reviewer text
- `build_evidence_freshness_manifest.py` — compare hashes for sanitized reviewer packet, external handoff, and per-review session copies so stale reviewer-facing evidence is visible before sharing
- `build_evidence_readiness.py` — build a one-page sanitized readiness ledger across matrix, packet, handoff, sessions, validation readout, boundary context, boundary result, and freshness metadata
- `build_external_review_distribution_manifest.py` — build a sanitized per-review distribution send list from external sessions plus freshness metadata; ready to distribute is not validation
- `build_evidence_remediation_queue.py` — build an ordered remediation queue from sanitized readiness/distribution blockers without raw artifacts or verdict-semantic changes
- `build_boundary_probe_plan.py` — build a sanitized tenant/user boundary probe plan from app-context and coverage evidence; plan-only, no raw values, no execution, and fails on configured sensitive marker hits
- `build_boundary_execution_design.py` — write the approved-context and sanitized-result contract for future tenant/user boundary probe execution; design-only, no executor
- `build_boundary_probe_context.py` — write a sanitized tenant/user boundary context template/intake validator for approved non-production metadata; no executor and no raw context values
- `build_boundary_probe_context_request.py` — write a sanitized request package showing which approved-context metadata is missing and how to validate a local ignored context file; no executor and no raw context values
- `build_boundary_probe_result.py` — write a sanitized tenant/user boundary result template/validator; default output is `blocked_missing_context`, no executor, no raw context values
- `summarize_reviewer_observation.py` — summarize a filled reviewer observation template into sanitized behavior-change/confusion signals without raw run artifacts; accepts both `Answer:` on its own line and `Answer: value` inline template output
- `summarize_reviewer_validation_rollup.py` — aggregate sanitized reviewer-observation summaries across cold-review sessions into validation status, theme counts, and next actions without copying free-form reviewer answers
- `build_redthread_evidence_contract_proposal.py` — write the tiny generic RedThread evidence-contract proposal to `docs/` and `runs/` without upstreaming or adding integration plumbing
- `check_atp_zapi_reference.py` — validate the local ATP Tennis ZAPI reference run and write a sanitized non-secret evidence summary
- `run_live_safe_replay.py` — execute policy-allowed safe reads, reviewed auth-safe-read GETs, and reviewed non-destructive staging writes when explicit approved context is supplied
- `run_live_workflow_replay.py` — execute grouped sequential workflow replay from workflow and attack plans using the same auth/write guardrails
  - carries bounded state/evidence forward between steps
  - emits structured workflow failure reasons and reason counts
  - emits workflow requirement summaries, failure-class summaries, binding review artifacts, and data for a unified operator review manifest
- `export_redthread_runtime_inputs.py` — convert normalized fixture bundles into real RedThread replay and dry-run campaign input shapes
- `evaluate_redthread_replay.py` — evaluate exported replay traces with RedThread's actual promotion-gate code
- `run_redthread_dryrun.py` — run one exported case through a real RedThread dry-run campaign path
- `run_bridge_pipeline.py` — run the full bridge flow from one artifact input
  - writes a unified `workflow_review_manifest.json` when workflow planning is present
  - writes that manifest before live workflow replay, then refreshes it after replay with enriched candidate detection and failure narratives when live results exist
- `run_live_zapi_bridge.py` — run live ZAPI capture, then feed the selected HAR into the full bridge flow
  - supports `--interactive` for human-guided capture
  - writes `zapi_capture/capture_metadata.json`

Handy commands:
- `make test` — run the local test suite
- `make demo-zapi` — regenerate the sample catalog-style ZAPI fixture bundle
- `make demo-zapi-har` — regenerate the sample HAR-derived fixture bundle, replay plan, and gate verdict
- `make demo-noui` — regenerate the sample NoUI MCP-derived fixture bundle
- `make demo-noui-redthread` — push the NoUI sample through RedThread runtime export, replay evaluation, and dry-run execution
- `make demo-redthread-runtime` — export HAR-derived fixtures into real RedThread replay inputs and evaluate them with the promotion gate
- `make demo-redthread-dryrun` — run one generated bridge case through a real RedThread dry-run campaign
- `make demo-adopt-actions` — regenerate the sample action fixture bundle
- `make demo-gate` — regenerate the replay plan and gate verdict for the catalog-style sample
- `make demo-live-plan` — generate the sample machine-readable live attack plan
- `make demo-hero-binding-truth` — regenerate the deterministic golden demo artifacts under ignored `runs/hero_binding_truth/`
- `make demo-reviewed-write-reference` — run the deterministic reviewed-write reference and write `runs/reviewed_write_reference/evidence_report.md`
- `make evidence-report` — rebuild the markdown evidence report for `runs/reviewed_write_reference/`
- `make evidence-matrix` — build `runs/evidence_matrix/evidence_matrix.{md,json}` with approve, review, and block rows
- `make evidence-packet` — build `runs/reviewer_packet/reviewer_packet.{md,json}` plus `reviewer_observation_template.md` from the sanitized report/matrix and fail if configured sensitive markers or required handoff sections are missing
- `make evidence-external-review-handoff` — build `runs/external_review_handoff/` with only sanitized review artifacts, external reviewer instructions, hashes, marker audit, and a clear not-validation-until-summarized status
- `make evidence-external-review-sessions` — build `runs/external_review_sessions/` with isolated per-review folders and expected summary commands for external cold reviews
- `make evidence-external-validation-readout` — build `runs/external_validation_readout/` from the external session batch and sanitized reviewer-observation summaries; missing summaries remain waiting state, not validation
- `make evidence-freshness` — build `runs/evidence_freshness/evidence_freshness_manifest.{md,json}` reporting stale/missing sanitized copies and failing on configured marker hits
- `make evidence-readiness` — build `runs/evidence_readiness/evidence_readiness.{md,json}` from sanitized evidence metadata, including boundary context intake state; current no-reviewer state remains waiting, not validation
- `make evidence-external-review-distribution` — build `runs/external_review_distribution/external_review_distribution_manifest.{md,json}` with exact reviewer-session delivery records and expected summary paths
- `make evidence-external-review-returns` — build `runs/external_review_returns/external_review_return_ledger.{md,json}` with per-review missing/incomplete/privacy/follow-up/complete status from sanitized summaries
- `make evidence-remediation-queue` — build `runs/evidence_remediation/evidence_remediation_queue.{md,json}` from sanitized readiness/distribution blockers; current open items remain external reviews, boundary context intake, and approved boundary execution context
- `make evidence-boundary-probe-plan` — build `runs/boundary_probe_plan/tenant_user_boundary_probe_plan.{md,json}` from existing reviewed-write evidence; this is a sanitized next-probe plan, not execution evidence
- `make evidence-boundary-execution-design` — write `docs/tenant-user-boundary-execution-design.md` plus generated `runs/boundary_execution_design/` copies of the approved-context and boundary-result contract; this is design-only, not execution
- `make evidence-boundary-probe-context` — write `runs/boundary_probe_context/tenant_user_boundary_probe_context.template.{md,json}` from the plan/design, or validate an explicit sanitized context file via `BOUNDARY_CONTEXT=...`; this is context intake only, not execution proof
- `make evidence-boundary-context-request` — write `runs/boundary_probe_context_request/tenant_user_boundary_probe_context_request.{md,json}` with the sanitized missing-context checklist and validation commands; this is a request package, not execution proof
- `make evidence-boundary-probe-result` — write `runs/boundary_probe_result/tenant_user_boundary_probe_result.{md,json}` from the plan/design; this is a sanitized result template/validator, not execution proof
- `make evidence-observation-summary OBSERVATION=/path/to/filled_reviewer_observation_template.md OBSERVATION_OUTPUT=/path/to/review_output_dir` — summarize filled silent-review answers into `reviewer_observation_summary.{md,json}` under the output directory and fail on configured sensitive markers; default output is `runs/reviewer_packet/`
- `make evidence-validation-rollup SUMMARIES="/path/to/summary1.json /path/to/summary2.json /path/to/summary3.json"` — aggregate sanitized observation summaries into `runs/reviewer_validation/reviewer_validation_rollup.{md,json}`; default uses the current local packet summary
- `make redthread-contract-proposal` — regenerate `docs/redthread-evidence-contract-proposal.md` and `runs/redthread_evidence_contract_proposal/redthread_evidence_contract_proposal.{md,json}`
- `make check-zapi-reference` — validate `demo_session_filtered.har` plus `runs/atp_tennis_01_live_bound/` against checked-in non-secret expectations
- `make demo-bridge-pipeline` — run the full one-command pipeline from the sanitized HAR sample
- `make live-zapi-bridge URL=https://example.com` — run a real ZAPI capture, then execute the full bridge flow
- `make demo-all` — run the full local demo flow across ZAPI, NoUI, replay, dry-run, and the one-command pipeline

## HAR notes

The HAR lane is meant for local bridge work against real captures.

Recommended flow:

```bash
python3 scripts/ingest_zapi.py /path/to/demo_session_filtered.har /path/to/output_fixture_bundle.json
python3 scripts/generate_replay_pack.py /path/to/output_fixture_bundle.json /path/to/output_replay_plan.json
python3 scripts/prepublish_gate.py /path/to/output_replay_plan.json /path/to/output_gate_verdict.json
```

Safety rule:
- keep raw `.har` files out of git
- commit normalized fixture bundles only after checking that sensitive values are gone

## NoUI flow

Canonical local sequence:

```bash
python3 scripts/ingest_noui.py \
  fixtures/noui_samples/expedia_stay_search \
  fixtures/replay_packs/sample_noui_fixture_bundle.json

python3 scripts/export_redthread_runtime_inputs.py \
  fixtures/replay_packs/sample_noui_fixture_bundle.json \
  fixtures/replay_packs/sample_noui_redthread_runtime_inputs.json

../redthread/.venv/bin/python scripts/evaluate_redthread_replay.py \
  fixtures/replay_packs/sample_noui_redthread_runtime_inputs.json \
  fixtures/replay_packs/sample_noui_redthread_replay_verdict.json
```

What this proves:
- NoUI MCP output can be normalized into the same bridge fixture model
- the NoUI lane can reuse the same RedThread runtime export seam
- one NoUI-derived case can be evaluated by RedThread without changing RedThread core

## One-command bridge flow

For a sanitized HAR or other supported input artifact:

```bash
python3 scripts/run_bridge_pipeline.py \
  fixtures/zapi_samples/sample_filtered_har.json \
  runs/sample_har_pipeline \
  --ingestion zapi
```

If you want the first live safe-read lane too:

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/safe_read_capture.har \
  runs/live_safe_read_pipeline \
  --ingestion zapi \
  --run-live-safe-replay
```

If the safe read needs reviewed auth context too:

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/auth_safe_read_capture.har \
  runs/auth_safe_read_pipeline \
  --ingestion zapi \
  --run-live-safe-replay \
  --allow-reviewed-auth \
  --auth-context /path/to/approved_auth_context.json
```

If a reviewed non-destructive write should run in staging:

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/write_review_capture.har \
  runs/reviewed_write_pipeline \
  --ingestion zapi \
  --run-live-safe-replay \
  --allow-reviewed-writes \
  --write-context /path/to/approved_write_context.json
```

If grouped multi-step cases should replay in sequence too:

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/workflow_capture.har \
  runs/live_workflow_pipeline \
  --ingestion zapi \
  --run-live-workflow-replay
```

For a live ZAPI session:

```bash
python3 scripts/run_live_zapi_bridge.py \
  "https://example.com" \
  runs/live_zapi_run \
  --zapi-repo /tmp/pi-github-repos/adoptai/zapi \
  --interactive \
  --operator-notes "log in, click billing, open profile"
```

What this proves:
- artifact capture/export can now be chained directly into bridge normalization
- a machine-readable live attack plan now exists alongside replay and gate artifacts
- the gate can now include live replay/workflow evidence and the RedThread replay verdict
- a machine-readable live workflow plan now exists for grouped multi-step cases
- grouped workflow replay now carries bounded step-to-step evidence in output artifacts
- the first live safe-read execution lane can run against allowed GET cases
- reviewed auth-bound safe-read GETs can run only with explicit approved auth context
- reviewed non-destructive writes can run only in staging with explicit per-case approved write context
- grouped multi-step workflows can replay in sequence with stop-on-first-failure behavior
- grouped workflow output now includes `final_state`, per-step `workflow_evidence`, and summary `reason_counts`
- replay/gate/runtime export no longer need separate manual commands
- RedThread replay + dry-run checks can be triggered from one top-level runner

## RedThread runtime flow

Canonical local sequence:

```bash
python3 scripts/export_redthread_runtime_inputs.py \
  fixtures/replay_packs/sample_har_fixture_bundle.json \
  fixtures/replay_packs/sample_har_redthread_runtime_inputs.json

../redthread/.venv/bin/python scripts/evaluate_redthread_replay.py \
  fixtures/replay_packs/sample_har_redthread_runtime_inputs.json \
  fixtures/replay_packs/sample_har_redthread_replay_verdict.json

../redthread/.venv/bin/python scripts/run_redthread_dryrun.py \
  fixtures/replay_packs/sample_har_redthread_runtime_inputs.json \
  fixtures/replay_packs/sample_har_redthread_dryrun_case0.json
```

What this proves:
- bridge fixtures can become a real `ReplayBundle` payload
- RedThread's real promotion gate can score that bundle
- one generated case can run through the real RedThread dry-run engine path

Later scripts:
- `classify_risk.py` — split-out classifier if the heuristics outgrow the loader
