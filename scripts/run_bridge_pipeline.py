from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.bridge.workflow import DEFAULT_REDTHREAD_PYTHON, DEFAULT_REDTHREAD_SRC, run_bridge_workflow


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full Adopt RedThread bridge pipeline from one input artifact.")
    parser.add_argument("input", help="Path to bridge input artifact")
    parser.add_argument("output_dir", help="Directory to write all generated artifacts")
    parser.add_argument("--ingestion", choices=["zapi", "noui", "adopt_actions"], default="zapi")
    parser.add_argument("--allow-sandbox-only", action="store_true", help="Allow sandbox-only items to downgrade gate block to review")
    parser.add_argument("--skip-dryrun", action="store_true", help="Skip the RedThread dry-run step")
    parser.add_argument("--run-live-safe-replay", action="store_true", help="Execute individual policy-allowed live replay cases after planning")
    parser.add_argument("--run-live-workflow-replay", action="store_true", help="Execute sequential workflow replay for grouped multi-step cases after planning")
    parser.add_argument("--auth-context", help="Path to approved auth context JSON for reviewed auth-safe-read GET cases")
    parser.add_argument("--allow-reviewed-auth", action="store_true", help="Allow reviewed auth-safe-read GET cases when approved auth context is supplied")
    parser.add_argument("--write-context", help="Path to approved staging write context JSON for reviewed write cases")
    parser.add_argument("--allow-reviewed-writes", action="store_true", help="Allow reviewed staging write cases when approved write context is supplied")
    parser.add_argument("--redthread-python", default=str(DEFAULT_REDTHREAD_PYTHON))
    parser.add_argument("--redthread-src", default=str(DEFAULT_REDTHREAD_SRC))
    args = parser.parse_args()

    summary = run_bridge_workflow(
        args.input,
        ingestion=args.ingestion,
        output_dir=args.output_dir,
        allow_sandbox_only=args.allow_sandbox_only,
        run_dryrun=not args.skip_dryrun,
        run_live_safe_replay=args.run_live_safe_replay,
        run_live_workflow_replay=args.run_live_workflow_replay,
        auth_context=args.auth_context,
        allow_reviewed_auth=args.allow_reviewed_auth,
        write_context=args.write_context,
        allow_reviewed_writes=args.allow_reviewed_writes,
        redthread_python=args.redthread_python,
        redthread_src=args.redthread_src,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
