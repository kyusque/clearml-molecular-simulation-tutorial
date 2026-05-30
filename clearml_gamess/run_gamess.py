from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GAMESS_NORMAL_TERMINATION = "EXECUTION OF GAMESS TERMINATED NORMALLY"
GAMESS_ABNORMAL_TERMINATION = "EXECUTION OF GAMESS TERMINATED -ABNORMALLY-"
SUBMIT_STARTUP_GRACE_SECONDS = 5.0
TASK_MANAGES_SCRATCH_ENV = "GAMESS_TASK_MANAGES_SCRATCH"
SUPPRESS_DISK_USAGE_ENV = "GAMESS_SUPPRESS_DISK_USAGE"
STARTUP_FAILURE_PATTERNS = (
    "permission denied",
    "no such file or directory",
    "failed to read file names",
    "could not find",
    "not found",
    "指定されたパス",
    "パスが見つかりません",
)


def resolve_from_repo(path: Path) -> Path:
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def env_with_venv_library_bin() -> dict[str, str]:
    env = os.environ.copy()
    library_bin = Path(sys.prefix) / "Library" / "bin"
    if library_bin.exists():
        env["PATH"] = f"{library_bin}{os.pathsep}{env.get('PATH', '')}"
    env[TASK_MANAGES_SCRATCH_ENV] = "TRUE"
    env[SUPPRESS_DISK_USAGE_ENV] = "TRUE"
    return env


def load_rungms_settings(gamess_dir: Path) -> dict[str, str]:
    settings_path = gamess_dir / "rungms.gms"
    if not settings_path.exists():
        return {}

    settings: dict[str, str] = {}
    for line in settings_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("::") or stripped.startswith("@REM"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        settings[key.strip().upper()] = value.strip()
    return settings


def copy_gamess_temp_files(
    gamess_dir: Path,
    job_name: str,
    temp_dir: Path,
    temp_patterns: list[str],
    temp_files: list[Path],
) -> list[Path]:
    temp_dir.mkdir(parents=True, exist_ok=True)
    copied_paths: list[Path] = []
    seen_sources: set[Path] = set()
    patterns = temp_patterns or [f"{job_name}.*"]

    candidate_dirs = [
        gamess_dir / "restart",
        gamess_dir / "scratch",
    ]
    sources: list[Path] = []
    for candidate_dir in candidate_dirs:
        if not candidate_dir.exists():
            continue
        for pattern in patterns:
            sources.extend(candidate_dir.glob(pattern))
    sources.extend(temp_files)

    for source in sources:
        source = source.resolve()
        if source in seen_sources or not source.is_file():
            continue
        seen_sources.add(source)
        destination = temp_dir / source.name
        shutil.copy2(source, destination)
        copied_paths.append(destination)

    return copied_paths


def output_has_startup_failure(output_text: str) -> bool:
    lowered = output_text.lower()
    if GAMESS_ABNORMAL_TERMINATION.lower() in lowered:
        return True
    return any(pattern in lowered for pattern in STARTUP_FAILURE_PATTERNS)


def read_log_text_if_exists(log_path: Path) -> str:
    if not log_path.exists():
        return ""
    return log_path.read_text(encoding="utf-8", errors="replace")


def run_gamess(
    input_path: Path,
    gamess_dir: Path,
    version: str,
    ncpus: int,
    log_path: Path,
    temp_dir: Path | None,
    temp_patterns: list[str],
    temp_files: list[Path],
    submit_only: bool = False,
) -> dict[str, object]:
    rungms_path = gamess_dir / "rungms.bat"
    gamess_exe_path = gamess_dir / f"gamess.{version}.exe"

    if not input_path.exists():
        raise FileNotFoundError(f"GAMESS input was not found: {input_path}")
    if not rungms_path.exists():
        raise FileNotFoundError(f"rungms.bat was not found: {rungms_path}")
    if not gamess_exe_path.exists():
        raise FileNotFoundError(f"GAMESS executable was not found: {gamess_exe_path}")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists():
        log_path.unlink()

    command = [
        str(rungms_path),
        str(input_path),
        version,
        str(ncpus),
        str(log_path),
    ]
    display_command = [
        rungms_path.as_posix(),
        input_path.as_posix(),
        version,
        str(ncpus),
        log_path.as_posix(),
    ]
    print("Running GAMESS:")
    print(" ".join(display_command), flush=True)

    copied_paths: list[Path] = []

    if submit_only:
        rungms_settings = load_rungms_settings(gamess_dir)
        scratch_dir = Path(rungms_settings["SCRATCHDIR"]).resolve() if rungms_settings.get("SCRATCHDIR") else temp_dir
        # Submit the GAMESS job and watch a short startup window for immediate failures.
        process = subprocess.Popen(
            command,
            cwd=gamess_dir,
            env=env_with_venv_library_bin(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        startup_deadline = time.time() + SUBMIT_STARTUP_GRACE_SECONDS
        startup_log_text = ""
        immediate_return_code = None
        while time.time() < startup_deadline:
            immediate_return_code = process.poll()
            startup_log_text = read_log_text_if_exists(log_path)
            if immediate_return_code is not None or output_has_startup_failure(startup_log_text):
                break
            time.sleep(0.25)

        if immediate_return_code is not None or output_has_startup_failure(startup_log_text):
            return_code = int(immediate_return_code) if immediate_return_code is not None else 1
            submission_status = "submit_failed"
            if output_has_startup_failure(startup_log_text) and immediate_return_code is None:
                submission_status = "startup_failed"
                process.terminate()
            return {
                "schema": "clearml_gamess.run_manifest.v1",
                "mode": "submit_only",
                "input_path": input_path.as_posix(),
                "gamess_dir": gamess_dir.as_posix(),
                "version": version,
                "ncpus": ncpus,
                "live_log_path": log_path.as_posix(),
                "scratch_dir": scratch_dir.as_posix() if scratch_dir else None,
                "scratch_pattern": f"{input_path.stem}.*",
                "return_code": return_code,
                "submission_status": submission_status,
                "submit_only": True,
                "pid": process.pid,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
        return {
            "schema": "clearml_gamess.run_manifest.v1",
            "mode": "submit_only",
            "input_path": input_path.as_posix(),
            "gamess_dir": gamess_dir.as_posix(),
            "version": version,
            "ncpus": ncpus,
            "live_log_path": log_path.as_posix(),
            "scratch_dir": scratch_dir.as_posix() if scratch_dir else None,
            "scratch_pattern": f"{input_path.stem}.*",
            "return_code": 0,
            "submission_status": "submitted",
            "submit_only": True,
            "pid": process.pid,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

    completed = subprocess.run(command, cwd=gamess_dir, env=env_with_venv_library_bin(), check=False)
    log_text = log_path.read_text(errors="replace") if log_path.exists() else ""
    terminated_normally = GAMESS_NORMAL_TERMINATION in log_text
    terminated_abnormally = GAMESS_ABNORMAL_TERMINATION in log_text
    if terminated_normally:
        gamess_status = "completed"
    elif terminated_abnormally:
        gamess_status = "failed"
    elif log_path.exists():
        gamess_status = "unknown"
    else:
        gamess_status = "missing_log"

    result: dict[str, object] = {
        "schema": "clearml_gamess.run_manifest.v1",
        "mode": "wait",
        "input_path": input_path.as_posix(),
        "gamess_dir": gamess_dir.as_posix(),
        "version": version,
        "ncpus": ncpus,
        "log_path": log_path.as_posix(),
        "scratch_dir": temp_dir.as_posix() if temp_dir else None,
        "scratch_files": [],
        "return_code": completed.returncode,
        "gamess_status": gamess_status,
    }
    if completed.returncode != 0:
        return result

    if not log_path.exists():
        print(f"GAMESS log was not created: {log_path.as_posix()}")
        result["return_code"] = 1
        return result

    if not terminated_normally:
        print(f"GAMESS did not terminate normally. See log: {log_path.as_posix()}")
        result["return_code"] = 1
        return result

    if temp_dir:
        copied_paths = copy_gamess_temp_files(
            gamess_dir=gamess_dir,
            job_name=input_path.stem,
            temp_dir=temp_dir,
            temp_patterns=temp_patterns,
            temp_files=temp_files,
        )
        print(f"Copied {len(copied_paths)} GAMESS temp file(s) to {temp_dir.as_posix()}")
        for copied_path in copied_paths:
            print(f"  {copied_path.as_posix()}")
        result["scratch_files"] = [path.as_posix() for path in copied_paths]

    return result


def write_run_manifest_json(result: dict[str, object], run_manifest_json: Path) -> Path:
    run_manifest_json.parent.mkdir(parents=True, exist_ok=True)
    run_manifest_json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return run_manifest_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a GAMESS input file through rungms.bat.")
    parser.add_argument("--input", required=True, type=Path, help="Path to a GAMESS input file.")
    parser.add_argument("--gamess-dir", default=Path("C:/Users/Public/gamess-64"), type=Path)
    parser.add_argument("--version", default="2023.R1.intel")
    parser.add_argument("--ncpus", type=int, default=1)
    parser.add_argument("--log", type=Path, help="Path to a log file. Defaults to a per-run temporary directory.")
    parser.add_argument(
        "--run-manifest-json",
        type=Path,
        help="Path to a run manifest JSON. Defaults to the log file directory.",
    )
    parser.add_argument("--gamess-temp-dir", type=Path, help="Directory to copy GAMESS restart/scratch files into.")
    parser.add_argument(
        "--gamess-temp-pattern",
        action="append",
        default=[],
        help="Glob pattern for GAMESS temp files under restart/ and scratch/. Defaults to <input-stem>.*.",
    )
    parser.add_argument(
        "--gamess-temp-file",
        action="append",
        default=[],
        type=Path,
        help="Additional GAMESS temp file to copy. Can be specified multiple times.",
    )
    parser.add_argument(
        "--submit-only",
        action="store_true",
        help="Submit GAMESS and return immediately without waiting for completion.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = resolve_from_repo(args.input).resolve()
    gamess_dir = args.gamess_dir.resolve()
    run_workspace = Path(tempfile.mkdtemp(prefix=f"{input_path.stem}_", suffix="_gamess"))
    log_path = resolve_from_repo(args.log).resolve() if args.log else run_workspace / f"{input_path.stem}.log"
    run_manifest_json = (
        resolve_from_repo(args.run_manifest_json).resolve()
        if args.run_manifest_json
        else log_path.parent / f"{input_path.stem}_run_manifest.json"
    )
    temp_dir = resolve_from_repo(args.gamess_temp_dir).resolve() if args.gamess_temp_dir else None
    temp_files = [resolve_from_repo(path).resolve() for path in args.gamess_temp_file]

    result = run_gamess(
        input_path=input_path,
        gamess_dir=gamess_dir,
        version=args.version,
        ncpus=args.ncpus,
        log_path=log_path,
        temp_dir=temp_dir,
        temp_patterns=args.gamess_temp_pattern,
        temp_files=temp_files,
        submit_only=args.submit_only,
    )
    write_run_manifest_json(result, run_manifest_json)
    print(f"run_manifest_json={run_manifest_json.as_posix()}")
    raise SystemExit(int(result["return_code"]))


if __name__ == "__main__":
    main()
