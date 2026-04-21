from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.adopt_actions.loader import build_action_fixture_bundle
from adapters.bridge.live_attack import build_live_attack_plan
from adapters.noui.loader import build_noui_fixture_bundle
from adapters.zapi.loader import build_fixture_bundle as build_zapi_fixture_bundle


BUILDERS = {
    "zapi": build_zapi_fixture_bundle,
    "noui": build_noui_fixture_bundle,
    "adopt_actions": build_action_fixture_bundle,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a machine-readable live attack plan from one supported bridge input.")
    parser.add_argument("input", help="Path to source artifact")
    parser.add_argument("output", help="Path to write live_attack_plan.json")
    parser.add_argument("--ingestion", default="zapi", choices=sorted(BUILDERS))
    args = parser.parse_args()

    bundle = BUILDERS[args.ingestion](args.input)
    payload = build_live_attack_plan(bundle)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote live attack plan to {output_path}")


if __name__ == "__main__":
    main()
