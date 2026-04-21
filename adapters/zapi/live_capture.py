from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable


CaptureWaiter = Callable[[str], str]


def capture_live_session(
    url: str,
    *,
    zapi_repo: str | Path,
    output_dir: str | Path,
    headless: bool,
    duration_seconds: int | None,
    upload: bool,
    prefer_filtered: bool,
    interactive: bool = False,
    operator_notes: str = "",
    wait_for_input: CaptureWaiter = input,
    sleep_fn: Callable[[int], None] = time.sleep,
    zapi_factory: Callable[[], Any] | None = None,
    har_analyzer: Callable[..., tuple[Any, Any, str | None]] | None = None,
) -> dict[str, Any]:
    repo_root = Path(zapi_repo).resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    if zapi_factory is None or har_analyzer is None:
        from zapi import ZAPI, analyze_har_file

        zapi_factory = zapi_factory or ZAPI
        har_analyzer = har_analyzer or analyze_har_file

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    original_har = out_dir / "session.har"
    filtered_har = out_dir / "session_filtered.har"
    metadata_path = out_dir / "capture_metadata.json"

    client = zapi_factory()
    session = client.launch_browser(url=url, headless=headless)
    completion_mode = "timer_elapsed"
    try:
        if interactive or not duration_seconds or duration_seconds <= 0:
            completion_mode = "human_confirmed"
            wait_for_input(
                "Interactive capture mode. Drive the browser manually, then press ENTER to save the HAR... "
            )
        else:
            print(f"timed capture running for {duration_seconds} seconds... drive the browser now")
            sleep_fn(duration_seconds)
        session.dump_logs(str(original_har))
    finally:
        session.close()

    stats, _report, filtered_path = har_analyzer(
        str(original_har),
        save_filtered=True,
        filtered_output_path=str(filtered_har),
    )
    chosen = original_har
    if prefer_filtered and filtered_path:
        chosen = Path(filtered_path)
    if upload:
        client.upload_har(str(chosen))

    result = {
        "source": "zapi_live_capture",
        "url": url,
        "zapi_repo": str(repo_root),
        "capture_mode": "interactive" if completion_mode == "human_confirmed" else "timed",
        "completion_mode": completion_mode,
        "operator_notes": operator_notes,
        "original_har": str(original_har),
        "filtered_har": str(filtered_har) if filtered_har.exists() else None,
        "selected_input": str(chosen),
        "api_relevant_entries": getattr(stats, "valid_entries", None),
        "estimated_cost_usd": getattr(stats, "estimated_cost_usd", None),
        "estimated_time_minutes": getattr(stats, "estimated_time_minutes", None),
        "uploaded": upload,
    }
    metadata_path.write_text(json.dumps(result, indent=2) + "\n")
    result["capture_metadata"] = str(metadata_path)
    return result
