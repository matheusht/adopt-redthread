from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any


def capture_live_session(
    url: str,
    *,
    zapi_repo: str | Path,
    output_dir: str | Path,
    headless: bool,
    duration_seconds: int | None,
    upload: bool,
    prefer_filtered: bool,
) -> dict[str, Any]:
    repo_root = Path(zapi_repo).resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from zapi import ZAPI, analyze_har_file

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    original_har = out_dir / "session.har"
    filtered_har = out_dir / "session_filtered.har"

    client = ZAPI()
    session = client.launch_browser(url=url, headless=headless)
    try:
        if duration_seconds and duration_seconds > 0:
            print(f"live capture running for {duration_seconds} seconds... drive the browser now")
            time.sleep(duration_seconds)
        else:
            input("Use the browser freely, then press ENTER to save the HAR... ")
        session.dump_logs(str(original_har))
    finally:
        session.close()

    stats, _report, filtered_path = analyze_har_file(
        str(original_har),
        save_filtered=True,
        filtered_output_path=str(filtered_har),
    )
    chosen = original_har
    if prefer_filtered and filtered_path:
        chosen = Path(filtered_path)
    if upload:
        client.upload_har(str(chosen))

    return {
        "source": "zapi_live_capture",
        "url": url,
        "zapi_repo": str(repo_root),
        "original_har": str(original_har),
        "filtered_har": str(filtered_har) if filtered_har.exists() else None,
        "selected_input": str(chosen),
        "api_relevant_entries": getattr(stats, "valid_entries", None),
        "estimated_cost_usd": getattr(stats, "estimated_cost_usd", None),
        "estimated_time_minutes": getattr(stats, "estimated_time_minutes", None),
        "uploaded": upload,
    }
