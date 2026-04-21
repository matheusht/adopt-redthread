from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from adapters.zapi.live_capture import capture_live_session


class _FakeSession:
    def __init__(self) -> None:
        self.closed = False
        self.dumped_to: str | None = None

    def dump_logs(self, path: str) -> None:
        self.dumped_to = path
        Path(path).write_text('{"log":{"entries":[]}}\n')

    def close(self) -> None:
        self.closed = True


class _FakeClient:
    def __init__(self) -> None:
        self.session = _FakeSession()
        self.uploaded: str | None = None
        self.launch_args: dict[str, object] | None = None

    def launch_browser(self, *, url: str, headless: bool) -> _FakeSession:
        self.launch_args = {"url": url, "headless": headless}
        return self.session

    def upload_har(self, path: str) -> None:
        self.uploaded = path


class LiveCaptureTests(unittest.TestCase):
    def test_interactive_capture_writes_metadata(self) -> None:
        prompts: list[str] = []
        client = _FakeClient()

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            result = capture_live_session(
                "https://example.com",
                zapi_repo=output_dir,
                output_dir=output_dir,
                headless=True,
                duration_seconds=None,
                upload=False,
                prefer_filtered=True,
                interactive=True,
                operator_notes="login + settings flow",
                wait_for_input=lambda prompt: prompts.append(prompt) or "",
                zapi_factory=lambda: client,
                har_analyzer=lambda *_args, **_kwargs: (
                    SimpleNamespace(valid_entries=3, estimated_cost_usd=0.12, estimated_time_minutes=1.5),
                    None,
                    str(output_dir / "session_filtered.har"),
                ),
            )

            metadata = json.loads((output_dir / "capture_metadata.json").read_text())
            self.assertEqual(result["capture_mode"], "interactive")
            self.assertEqual(result["completion_mode"], "human_confirmed")
            self.assertEqual(metadata["operator_notes"], "login + settings flow")
            self.assertTrue(prompts)
            self.assertTrue(client.session.closed)

    def test_timed_capture_uses_timer_path(self) -> None:
        sleeps: list[int] = []
        client = _FakeClient()

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            result = capture_live_session(
                "https://example.com",
                zapi_repo=output_dir,
                output_dir=output_dir,
                headless=False,
                duration_seconds=7,
                upload=True,
                prefer_filtered=False,
                interactive=False,
                sleep_fn=lambda seconds: sleeps.append(seconds),
                zapi_factory=lambda: client,
                har_analyzer=lambda *_args, **_kwargs: (
                    SimpleNamespace(valid_entries=1, estimated_cost_usd=0.01, estimated_time_minutes=0.2),
                    None,
                    str(output_dir / "session_filtered.har"),
                ),
            )

            self.assertEqual(result["capture_mode"], "timed")
            self.assertEqual(result["completion_mode"], "timer_elapsed")
            self.assertEqual(sleeps, [7])
            self.assertEqual(client.uploaded, str(output_dir / "session.har"))


if __name__ == "__main__":
    unittest.main()
