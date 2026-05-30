from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GAMESS_NORMAL_TERMINATION = "EXECUTION OF GAMESS TERMINATED NORMALLY"
GAMESS_ABNORMAL_TERMINATION = "EXECUTION OF GAMESS TERMINATED -ABNORMALLY-"
FINAL_RHF_ENERGY_RE = re.compile(r"FINAL\s+RHF\s+ENERGY\s+IS\s+([-+]?\d+\.\d+)", re.IGNORECASE)
TOTAL_WALL_CLOCK_RE = re.compile(r"TOTAL\s+WALL\s+CLOCK\s+TIME=\s+([-+]?\d+(?:\.\d+)?)\s+SECONDS", re.IGNORECASE)


def resolve_from_repo(path: Path) -> Path:
    if path.is_absolute():
        return path
    return REPO_ROOT / path


TrackCallback = Callable[[dict[str, object], Path], dict[str, object]]


def classify_gamess_status(log_path: Path) -> tuple[str, str]:
    if not log_path.exists():
        return "missing_log", ""

    log_text = log_path.read_text(errors="replace")
    if GAMESS_NORMAL_TERMINATION in log_text:
        return "completed", log_text
    if GAMESS_ABNORMAL_TERMINATION in log_text:
        return "failed", log_text
    return "unknown", log_text


def track_gamess(
    run_manifest_json: Path,
    tracking_metrics_json: Path,
    callbacks: list[TrackCallback] | None = None,
) -> dict[str, object]:
    run = json.loads(run_manifest_json.read_text(encoding="utf-8"))
    log_value = run.get("log_path") or run.get("live_log_path")
    if not log_value:
        raise ValueError("run manifest must contain 'log_path' or 'live_log_path'")
    log_path = Path(str(log_value))
    gamess_status, log_text = classify_gamess_status(log_path)
    if gamess_status == "unknown" and run.get("observed_status") == "running":
        gamess_status = "running"
    return_code = int(run.get("return_code", 0))
    if gamess_status not in {"completed", "running"} and return_code == 0:
        return_code = 1
    values: dict[str, object] = {
        "return_code": return_code,
        "gamess_status": gamess_status,
    }

    if callbacks and gamess_status == "completed":
        for callback in callbacks:
            values.update(callback({"log_text": log_text, **values}, tracking_metrics_json.parent))

    tracking_metrics_json.parent.mkdir(parents=True, exist_ok=True)
    tracking_metrics_json.write_text(json.dumps(values, indent=2, sort_keys=True), encoding="utf-8")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Track a GAMESS run from a run manifest JSON.")
    parser.add_argument("--run-manifest-json", required=True, type=Path)
    parser.add_argument("--tracking-metrics-json", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_manifest_json = resolve_from_repo(args.run_manifest_json).resolve()
    tracking_metrics_json = (
        resolve_from_repo(args.tracking_metrics_json).resolve()
        if args.tracking_metrics_json
        else run_manifest_json.parent / f"{run_manifest_json.stem.replace('_run_manifest', '')}_tracking_metrics.json"
    )
    values = track_gamess(run_manifest_json=run_manifest_json, tracking_metrics_json=tracking_metrics_json)
    print(f"tracking_metrics_json={tracking_metrics_json.as_posix()}")
    print(json.dumps(values, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
