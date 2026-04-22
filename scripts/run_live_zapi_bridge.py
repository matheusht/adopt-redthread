from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZAPI_REPO = Path("/tmp/pi-github-repos/adoptai/zapi")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.bridge.workflow import DEFAULT_REDTHREAD_PYTHON, DEFAULT_REDTHREAD_SRC, run_bridge_workflow
from adapters.zapi.live_capture import capture_live_session


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live ZAPI capture, then push the resulting artifact through the full RedThread bridge pipeline.")
    parser.add_argument("url", help="Target URL to open in the ZAPI browser")
    parser.add_argument("output_dir", help="Directory to write HAR files and pipeline outputs")
    parser.add_argument("--zapi-repo", default=str(DEFAULT_ZAPI_REPO), help="Path to local ZAPI clone")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument("--interactive", action="store_true", help="Keep capture human-guided and wait for ENTER before saving HAR")
    parser.add_argument("--duration-seconds", type=int, default=None, help="Auto-save after N seconds instead of waiting for ENTER")
    parser.add_argument("--operator-notes", default="", help="Short free-text note to store with capture metadata")
    parser.add_argument("--upload", action="store_true", help="Upload selected HAR to Adopt after capture")
    parser.add_argument("--use-original-har", action="store_true", help="Use original HAR instead of filtered HAR for downstream bridge work")
    parser.add_argument("--allow-sandbox-only", action="store_true")
    parser.add_argument("--skip-dryrun", action="store_true")
    parser.add_argument("--run-live-safe-replay", action="store_true", help="Execute policy-allowed safe-read live replay cases after planning")
    parser.add_argument("--auth-context", help="Path to approved auth context JSON for reviewed auth-safe-read GET cases")
    parser.add_argument("--allow-reviewed-auth", action="store_true", help="Allow reviewed auth-safe-read GET cases when approved auth context is supplied")
    parser.add_argument("--redthread-python", default=str(DEFAULT_REDTHREAD_PYTHON))
    parser.add_argument("--redthread-src", default=str(DEFAULT_REDTHREAD_SRC))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    capture_dir = output_dir / "zapi_capture"
    pipeline_dir = output_dir / "bridge_outputs"

    capture = capture_live_session(
        args.url,
        zapi_repo=args.zapi_repo,
        output_dir=capture_dir,
        headless=args.headless,
        duration_seconds=args.duration_seconds,
        upload=args.upload,
        prefer_filtered=not args.use_original_har,
        interactive=args.interactive,
        operator_notes=args.operator_notes,
    )
    summary = run_bridge_workflow(
        capture["selected_input"],
        ingestion="zapi",
        output_dir=pipeline_dir,
        allow_sandbox_only=args.allow_sandbox_only,
        run_dryrun=not args.skip_dryrun,
        run_live_safe_replay=args.run_live_safe_replay,
        auth_context=args.auth_context,
        allow_reviewed_auth=args.allow_reviewed_auth,
        redthread_python=args.redthread_python,
        redthread_src=args.redthread_src,
    )
    final = {"capture": capture, "bridge_summary": summary}
    final_path = output_dir / "live_zapi_bridge_summary.json"
    final_path.write_text(json.dumps(final, indent=2) + "\n")
    print(json.dumps(final, indent=2))
    print(f"live ZAPI bridge run complete -> {final_path}")


if __name__ == "__main__":
    main()
