PYTHON ?= python3
REDTHREAD_PYTHON ?= ../redthread/.venv/bin/python

OBSERVATION ?= runs/reviewer_packet/reviewer_observation_template.md
OBSERVATION_OUTPUT ?= runs/reviewer_packet
SUMMARIES ?= runs/reviewer_packet/reviewer_observation_summary.json

.PHONY: test demo-zapi demo-zapi-har demo-live-plan demo-hero-binding-truth check-zapi-reference demo-reviewed-write-reference evidence-report evidence-matrix evidence-packet evidence-external-review-handoff evidence-external-review-sessions evidence-external-validation-readout evidence-freshness evidence-readiness evidence-external-review-distribution evidence-remediation-queue evidence-boundary-probe-plan evidence-boundary-execution-design evidence-boundary-probe-result evidence-observation-summary evidence-validation-rollup redthread-contract-proposal demo-bridge-pipeline demo-noui demo-noui-redthread demo-redthread-runtime demo-redthread-dryrun demo-adopt-actions demo-gate live-zapi-bridge demo-all

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

demo-zapi:
	$(PYTHON) scripts/ingest_zapi.py fixtures/zapi_samples/sample_discovery.json fixtures/replay_packs/sample_fixture_bundle.json

demo-zapi-har:
	$(PYTHON) scripts/ingest_zapi.py fixtures/zapi_samples/sample_filtered_har.json fixtures/replay_packs/sample_har_fixture_bundle.json
	$(PYTHON) scripts/generate_replay_pack.py fixtures/replay_packs/sample_har_fixture_bundle.json fixtures/replay_packs/sample_har_replay_plan.json
	$(PYTHON) scripts/prepublish_gate.py fixtures/replay_packs/sample_har_replay_plan.json fixtures/replay_packs/sample_har_gate_verdict.json

demo-live-plan:
	$(PYTHON) scripts/generate_live_attack_plan.py fixtures/zapi_samples/sample_filtered_har.json fixtures/replay_packs/sample_har_live_attack_plan.json --ingestion zapi

demo-hero-binding-truth:
	$(PYTHON) scripts/generate_hero_binding_truth.py --output-dir runs/hero_binding_truth

check-zapi-reference:
	$(PYTHON) scripts/check_atp_zapi_reference.py --har demo_session_filtered.har --run-dir runs/atp_tennis_01_live_bound

demo-reviewed-write-reference:
	$(PYTHON) scripts/generate_reviewed_write_reference.py --output-dir runs/reviewed_write_reference --redthread-python $(REDTHREAD_PYTHON) --redthread-src ../redthread/src

evidence-report:
	$(PYTHON) scripts/build_evidence_report.py --run-dir runs/reviewed_write_reference

evidence-matrix:
	$(PYTHON) scripts/build_evidence_matrix.py --redthread-python $(REDTHREAD_PYTHON) --redthread-src ../redthread/src

evidence-packet:
	$(PYTHON) scripts/build_reviewer_packet.py --redthread-python $(REDTHREAD_PYTHON) --redthread-src ../redthread/src --fail-on-marker-hit --fail-on-incomplete-handoff

evidence-external-review-handoff:
	$(PYTHON) scripts/build_external_review_handoff.py --fail-on-marker-hit --fail-on-incomplete-handoff

evidence-external-review-sessions:
	$(PYTHON) scripts/build_external_review_session_batch.py --fail-on-marker-hit

evidence-external-validation-readout:
	$(PYTHON) scripts/build_external_validation_readout.py --fail-on-marker-hit

evidence-freshness:
	$(PYTHON) scripts/build_evidence_freshness_manifest.py --fail-on-marker-hit

evidence-readiness:
	$(PYTHON) scripts/build_evidence_readiness.py --fail-on-marker-hit

evidence-external-review-distribution:
	$(PYTHON) scripts/build_external_review_distribution_manifest.py --fail-on-marker-hit

evidence-remediation-queue:
	$(PYTHON) scripts/build_evidence_remediation_queue.py --fail-on-marker-hit

evidence-boundary-probe-plan:
	$(PYTHON) scripts/build_boundary_probe_plan.py --run-dir runs/reviewed_write_reference --output-dir runs/boundary_probe_plan --fail-on-marker-hit

evidence-boundary-execution-design:
	$(PYTHON) scripts/build_boundary_execution_design.py --probe-plan runs/boundary_probe_plan/tenant_user_boundary_probe_plan.json --fail-on-marker-hit

evidence-boundary-probe-result:
	$(PYTHON) scripts/build_boundary_probe_result.py --probe-plan runs/boundary_probe_plan/tenant_user_boundary_probe_plan.json --execution-design runs/boundary_execution_design/tenant_user_boundary_execution_design.json --fail-on-marker-hit

evidence-observation-summary:
	$(PYTHON) scripts/summarize_reviewer_observation.py --observation $(OBSERVATION) --output-dir $(OBSERVATION_OUTPUT) --fail-on-marker-hit

evidence-validation-rollup:
	$(PYTHON) scripts/summarize_reviewer_validation_rollup.py $(SUMMARIES) --output-dir runs/reviewer_validation --fail-on-marker-hit

redthread-contract-proposal:
	$(PYTHON) scripts/build_redthread_evidence_contract_proposal.py --fail-on-marker-hit

demo-bridge-pipeline:
	$(PYTHON) scripts/run_bridge_pipeline.py fixtures/zapi_samples/sample_filtered_har.json runs/sample_har_pipeline --ingestion zapi --redthread-python $(REDTHREAD_PYTHON) --redthread-src ../redthread/src

demo-noui:
	$(PYTHON) scripts/ingest_noui.py fixtures/noui_samples/expedia_stay_search fixtures/replay_packs/sample_noui_fixture_bundle.json

demo-noui-redthread:
	$(PYTHON) scripts/export_redthread_runtime_inputs.py fixtures/replay_packs/sample_noui_fixture_bundle.json fixtures/replay_packs/sample_noui_redthread_runtime_inputs.json
	$(REDTHREAD_PYTHON) scripts/evaluate_redthread_replay.py fixtures/replay_packs/sample_noui_redthread_runtime_inputs.json fixtures/replay_packs/sample_noui_redthread_replay_verdict.json
	$(REDTHREAD_PYTHON) scripts/run_redthread_dryrun.py fixtures/replay_packs/sample_noui_redthread_runtime_inputs.json fixtures/replay_packs/sample_noui_redthread_dryrun_case0.json

demo-redthread-runtime:
	$(PYTHON) scripts/export_redthread_runtime_inputs.py fixtures/replay_packs/sample_har_fixture_bundle.json fixtures/replay_packs/sample_har_redthread_runtime_inputs.json
	$(REDTHREAD_PYTHON) scripts/evaluate_redthread_replay.py fixtures/replay_packs/sample_har_redthread_runtime_inputs.json fixtures/replay_packs/sample_har_redthread_replay_verdict.json

demo-redthread-dryrun:
	$(REDTHREAD_PYTHON) scripts/run_redthread_dryrun.py fixtures/replay_packs/sample_har_redthread_runtime_inputs.json fixtures/replay_packs/sample_har_redthread_dryrun_case0.json

demo-adopt-actions:
	$(PYTHON) scripts/ingest_adopt_actions.py fixtures/adopt_action_samples/sample_actions.json fixtures/replay_packs/sample_action_fixture_bundle.json

demo-gate:
	$(PYTHON) scripts/generate_replay_pack.py fixtures/replay_packs/sample_fixture_bundle.json fixtures/replay_packs/sample_replay_plan.json
	$(PYTHON) scripts/prepublish_gate.py fixtures/replay_packs/sample_replay_plan.json fixtures/replay_packs/sample_gate_verdict.json

live-zapi-bridge:
	@test -n "$(URL)" || (echo "Usage: make live-zapi-bridge URL=https://example.com [HEADLESS=1] [DURATION=45]" && exit 1)
	$(PYTHON) scripts/run_live_zapi_bridge.py "$(URL)" runs/live_zapi_run --zapi-repo /tmp/pi-github-repos/adoptai/zapi $(if $(HEADLESS),--headless,) $(if $(DURATION),--duration-seconds $(DURATION),) --redthread-python $(REDTHREAD_PYTHON) --redthread-src ../redthread/src

demo-all: demo-zapi demo-zapi-har demo-live-plan demo-redthread-runtime demo-redthread-dryrun demo-adopt-actions demo-gate demo-noui demo-noui-redthread demo-bridge-pipeline
