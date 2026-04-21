from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.redthread_runtime.runtime_adapter import build_redthread_runtime_inputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Export normalized bridge fixtures into real RedThread replay and dry-run input shapes.")
    parser.add_argument("input", help="Path to normalized fixture bundle JSON")
    parser.add_argument("output", help="Path to write RedThread runtime input JSON")
    args = parser.parse_args()

    bundle = json.loads(Path(args.input).read_text())
    payload = build_redthread_runtime_inputs(bundle)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n")

    print(
        "wrote RedThread runtime inputs with "
        f"{len(payload['redthread_replay_bundle']['traces'])} replay traces and "
        f"{len(payload['campaign_cases'])} dry-run campaign cases to {output_path}"
    )


if __name__ == "__main__":
    main()
