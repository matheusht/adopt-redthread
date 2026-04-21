PYTHON ?= python3
REDTHREAD_PYTHON ?= ../redthread/.venv/bin/python

.PHONY: test demo-zapi demo-zapi-har demo-noui demo-noui-redthread demo-redthread-runtime demo-redthread-dryrun demo-adopt-actions demo-gate demo-all

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

demo-zapi:
	$(PYTHON) scripts/ingest_zapi.py fixtures/zapi_samples/sample_discovery.json fixtures/replay_packs/sample_fixture_bundle.json

demo-zapi-har:
	$(PYTHON) scripts/ingest_zapi.py fixtures/zapi_samples/sample_filtered_har.json fixtures/replay_packs/sample_har_fixture_bundle.json
	$(PYTHON) scripts/generate_replay_pack.py fixtures/replay_packs/sample_har_fixture_bundle.json fixtures/replay_packs/sample_har_replay_plan.json
	$(PYTHON) scripts/prepublish_gate.py fixtures/replay_packs/sample_har_replay_plan.json fixtures/replay_packs/sample_har_gate_verdict.json

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

demo-all: demo-zapi demo-zapi-har demo-redthread-runtime demo-redthread-dryrun demo-adopt-actions demo-gate demo-noui demo-noui-redthread
