from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REDTHREAD_SRC = REPO_ROOT.parent / "redthread" / "src"


async def _run_case(payload_path: Path, case_index: int, redthread_src: Path) -> dict[str, object]:
    if str(redthread_src) not in sys.path:
        sys.path.insert(0, str(redthread_src))

    from redthread.config.settings import AlgorithmType, RedThreadSettings
    from redthread.engine import RedThreadEngine
    from redthread.models import CampaignConfig

    payload = json.loads(payload_path.read_text())
    case = payload["campaign_cases"][case_index]

    settings = RedThreadSettings()
    settings.dry_run = True
    settings.algorithm = AlgorithmType(case.get("algorithm", "pair"))
    engine = RedThreadEngine(settings)
    config = CampaignConfig(
        objective=case["objective"],
        target_system_prompt=case["system_prompt"],
        rubric_name=case["rubric_name"],
        num_personas=int(case.get("personas", 1)),
    )
    result = await engine.run(config)
    return {
        "case_id": case["case_id"],
        "algorithm": case["algorithm"],
        "rubric_name": case["rubric_name"],
        "campaign_id": result.id,
        "result_count": len(result.results),
        "metadata_keys": sorted(result.metadata.keys()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one exported bridge case through real RedThread dry-run execution.")
    parser.add_argument("input", help="Path to exported RedThread runtime input JSON")
    parser.add_argument("output", help="Path to write dry-run summary JSON")
    parser.add_argument("--case-index", type=int, default=0, help="Campaign case index to run")
    parser.add_argument("--redthread-src", default=str(DEFAULT_REDTHREAD_SRC), help="Path to redthread/src for local import")
    args = parser.parse_args()

    summary = asyncio.run(_run_case(Path(args.input), args.case_index, Path(args.redthread_src).resolve()))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"redthread dry-run case complete -> {output_path}")


if __name__ == "__main__":
    main()
