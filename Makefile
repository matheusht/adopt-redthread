PYTHON ?= python3

.PHONY: test demo-zapi demo-adopt-actions demo-gate demo-all

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

demo-zapi:
	$(PYTHON) scripts/ingest_zapi.py fixtures/zapi_samples/sample_discovery.json fixtures/replay_packs/sample_fixture_bundle.json

demo-adopt-actions:
	$(PYTHON) scripts/ingest_adopt_actions.py fixtures/adopt_action_samples/sample_actions.json fixtures/replay_packs/sample_action_fixture_bundle.json

demo-gate:
	$(PYTHON) scripts/generate_replay_pack.py fixtures/replay_packs/sample_fixture_bundle.json fixtures/replay_packs/sample_replay_plan.json
	$(PYTHON) scripts/prepublish_gate.py fixtures/replay_packs/sample_replay_plan.json fixtures/replay_packs/sample_gate_verdict.json

demo-all: demo-zapi demo-adopt-actions demo-gate
