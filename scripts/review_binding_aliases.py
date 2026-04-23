from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.live_replay.binding_alias_reviews import build_approved_binding_aliases


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reviewed approved binding alias artifact from proposal candidates")
    parser.add_argument("binding_pattern_candidates", help="Path to binding_pattern_candidates.json")
    parser.add_argument("review_input", help="Path to operator review JSON with approved_candidates")
    parser.add_argument("output", help="Path to write approved_binding_aliases.json")
    args = parser.parse_args()

    payload = build_approved_binding_aliases(
        args.binding_pattern_candidates,
        args.review_input,
        output_path=args.output,
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
