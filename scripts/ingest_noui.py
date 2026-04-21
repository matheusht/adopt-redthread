from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.noui.loader import build_noui_fixture_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize a NoUI MCP server output into a RedThread-friendly fixture bundle.")
    parser.add_argument("input", help="Path to NoUI MCP server directory or manifest.json")
    parser.add_argument("output", help="Path to write normalized fixture bundle JSON")
    args = parser.parse_args()

    bundle = build_noui_fixture_bundle(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bundle, indent=2) + "\n")

    print(f"wrote {bundle['fixture_count']} NoUI fixtures to {output_path}")


if __name__ == "__main__":
    main()
