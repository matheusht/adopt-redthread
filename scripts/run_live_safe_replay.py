from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.live_replay.executor import execute_live_safe_replay


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute only policy-allowed live safe-read replay cases from a live attack plan.")
    parser.add_argument("input", help="Path to live_attack_plan.json")
    parser.add_argument("output", help="Path to write live safe replay summary")
    parser.add_argument("--timeout-seconds", type=int, default=10)
    args = parser.parse_args()

    payload = execute_live_safe_replay(args.input, output_path=args.output, timeout_seconds=args.timeout_seconds)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
