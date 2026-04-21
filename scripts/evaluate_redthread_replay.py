from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REDTHREAD_SRC = REPO_ROOT.parent / "redthread" / "src"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate exported replay traces with real RedThread promotion-gate code.")
    parser.add_argument("input", help="Path to exported RedThread runtime input JSON")
    parser.add_argument("output", help="Path to write promotion-gate result JSON")
    parser.add_argument("--redthread-src", default=str(DEFAULT_REDTHREAD_SRC), help="Path to redthread/src for local import")
    args = parser.parse_args()

    redthread_src = Path(args.redthread_src).resolve()
    if str(redthread_src) not in sys.path:
        sys.path.insert(0, str(redthread_src))

    from redthread.evaluation.promotion_gate import evaluate_agentic_promotion
    from redthread.evaluation.replay_corpus import ReplayBundle
    from redthread.tools.authorization import AuthorizationEngine, default_least_agency_policies
    from redthread.orchestration.models import ActionEnvelope

    payload = json.loads(Path(args.input).read_text())
    traces = payload["redthread_replay_bundle"]["traces"]
    engine = AuthorizationEngine(default_least_agency_policies())

    for trace in traces:
        action = ActionEnvelope.model_validate(trace["scenario_result"]["action_envelope"])
        trace["authorization_decision"] = engine.authorize(action).model_dump(mode="json")

    bundle = ReplayBundle.model_validate(payload["redthread_replay_bundle"])
    result = dict(evaluate_agentic_promotion(bundle))
    result["bundle_id"] = bundle.bundle_id

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"redthread replay verdict: {'pass' if result['passed'] else 'fail'} -> {output_path}")


if __name__ == "__main__":
    main()
