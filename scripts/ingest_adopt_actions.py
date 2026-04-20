from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.adopt_actions.loader import build_action_fixture_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize an Adopt action catalog into RedThread-friendly fixtures.")
    parser.add_argument("input", help="Path to Adopt action catalog JSON")
    parser.add_argument("output", help="Path to write normalized fixture bundle JSON")
    args = parser.parse_args()

    bundle = build_action_fixture_bundle(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bundle, indent=2) + "\n")

    print(f"wrote {bundle['fixture_count']} action fixtures to {output_path}")


if __name__ == "__main__":
    main()
