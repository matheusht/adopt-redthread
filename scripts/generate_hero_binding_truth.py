from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.bridge.live_workflow import build_live_workflow_plan
from adapters.live_replay.workflow_executor import execute_live_workflow_replay
from adapters.redthread_runtime.runtime_adapter import build_redthread_runtime_inputs
from scripts.prepublish_gate import build_gate_verdict
from tests.live_workflow_binding_support import binding_server


def build_hero_artifacts(output_dir: str | Path) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    with binding_server() as base_url:
        live_attack_plan = _hero_attack_plan(base_url)
        live_workflow_plan = build_live_workflow_plan(live_attack_plan)
        live_workflow_replay = execute_live_workflow_replay(live_workflow_plan, live_attack_plan)

    replay_pack = _hero_replay_pack()
    redthread_replay_verdict = {"passed": True, "bundle_id": "bridge-golden-demo"}
    gate_verdict = build_gate_verdict(
        replay_pack,
        allow_sandbox_only=True,
        live_workflow_replay=live_workflow_replay,
        redthread_replay_verdict=redthread_replay_verdict,
        workflow_plan=live_workflow_plan,
    )
    fixture_bundle = _hero_fixture_bundle()
    redthread_runtime_inputs = build_redthread_runtime_inputs(fixture_bundle, live_workflow_plan, live_workflow_replay)
    workflow_summary = {
        "status": "completed",
        "output_dir": str(output_root),
        "live_workflow_replay_count": live_workflow_replay.get("executed_workflow_count", 0),
        "live_workflow_binding_application_summary": live_workflow_replay["binding_application_summary"],
        "gate_decision": gate_verdict["decision"],
    }

    artifacts = {
        "live_attack_plan.json": live_attack_plan,
        "live_workflow_plan.json": live_workflow_plan,
        "live_workflow_replay.json": live_workflow_replay,
        "redthread_runtime_inputs.json": redthread_runtime_inputs,
        "gate_verdict.json": gate_verdict,
        "workflow_summary.json": workflow_summary,
    }
    for name, payload in artifacts.items():
        (output_root / name).write_text(json.dumps(payload, indent=2) + "\n")
    return workflow_summary


def _hero_attack_plan(base_url: str) -> dict[str, Any]:
    host = base_url.replace("http://", "")
    return {
        "plan_id": "golden-hero-binding-truth",
        "source": "golden_demo",
        "input_file": "tests/live_workflow_binding_support.py",
        "fixture_count": 2,
        "allowed_case_count": 2,
        "review_case_count": 0,
        "blocked_case_count": 0,
        "cases": [
            {
                "case_id": "step_a",
                "method": "GET",
                "path": "/api/v1/account/profile",
                "workflow_group": "account",
                "workflow_step_index": 0,
                "execution_mode": "live_safe_read",
                "approval_mode": "auto",
                "target_env": "captured_target",
                "auth_context_required": False,
                "reviewable_with_auth_context": False,
                "reviewable_write_in_staging": False,
                "max_replay_attempts": 1,
                "side_effect_risk": "low",
                "allowed": True,
                "reasons": [],
                "request_blueprint": {
                    "url": f"{base_url}/api/v1/account/profile",
                    "host": host,
                    "header_names": [],
                    "query_params": [],
                    "body_fields": [],
                },
            },
            {
                "case_id": "step_b",
                "method": "GET",
                "path": "/api/v1/account/preferences/{{account_id}}",
                "workflow_group": "account",
                "workflow_step_index": 1,
                "execution_mode": "live_safe_read",
                "approval_mode": "auto",
                "target_env": "captured_target",
                "auth_context_required": False,
                "reviewable_with_auth_context": False,
                "reviewable_write_in_staging": False,
                "max_replay_attempts": 1,
                "side_effect_risk": "low",
                "allowed": True,
                "reasons": [],
                "request_blueprint": {
                    "url": f"{base_url}/api/v1/account/preferences/{{{{account_id}}}}?trace={{{{trace_id}}}}",
                    "host": host,
                    "header_names": [],
                    "query_params": [],
                    "body_fields": [],
                },
                "response_bindings": [
                    {
                        "binding_id": "account_id",
                        "source_case_id": "step_a",
                        "source_type": "response_json",
                        "source_key": "account.id",
                        "target_field": "request_url",
                        "placeholder": "{{account_id}}",
                    },
                    {
                        "binding_id": "trace_id",
                        "source_case_id": "step_a",
                        "source_type": "response_header",
                        "source_key": "x-trace-id",
                        "target_field": "request_url",
                        "placeholder": "{{trace_id}}",
                    },
                ],
            },
        ],
    }


def _hero_replay_pack() -> dict[str, Any]:
    return {
        "summary": {"fixture_count": 2},
        "safe_read_probes": [{"name": "step_a"}, {"name": "step_b"}],
        "write_path_review_items": [],
        "sandbox_only_attack_set": [],
    }


def _hero_fixture_bundle() -> dict[str, Any]:
    return {
        "source": "golden_demo",
        "input_file": "tests/live_workflow_binding_support.py",
        "fixture_count": 2,
        "fixtures": [
            _hero_fixture("step_a", "GET", "/api/v1/account/profile"),
            _hero_fixture("step_b", "GET", "/api/v1/account/preferences/{{account_id}}"),
        ],
    }


def _hero_fixture(name: str, method: str, path: str) -> dict[str, Any]:
    return {
        "name": name,
        "method": method,
        "path": path,
        "replay_class": "safe_read",
        "candidate_attack_types": ["overbroad_data_access"],
        "source": "golden_demo",
        "auth_hints": [],
        "workflow_group": "account",
        "risk_level": "low",
        "reasons": [],
        "data_sensitivity": "internal",
        "tenant_scope": "single_tenant",
        "endpoint_family": "account",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic hero binding-truth artifacts under runs/.")
    parser.add_argument("--output-dir", default="runs/hero_binding_truth", help="Directory to write generated hero artifacts")
    args = parser.parse_args()

    summary = build_hero_artifacts(args.output_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
