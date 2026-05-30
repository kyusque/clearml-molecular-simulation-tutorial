from __future__ import annotations

import argparse
import json
import shutil
import time
import tempfile
from pathlib import Path

try:
    from clearml_gamess.track_gamess import FINAL_RHF_ENERGY_RE, TOTAL_WALL_CLOCK_RE, track_gamess
except ModuleNotFoundError:
    from track_gamess import FINAL_RHF_ENERGY_RE, TOTAL_WALL_CLOCK_RE, track_gamess


DISPLAY_START_MARKERS = (
    "GAMESS VERSION =",
)
GAMESS_NORMAL_TERMINATION = "EXECUTION OF GAMESS TERMINATED NORMALLY"
GAMESS_ABNORMAL_TERMINATION = "EXECUTION OF GAMESS TERMINATED -ABNORMALLY-"
POST_TERMINATION_QUIET_SECONDS = 5.0
GAMESS_STATUS_CODES = {
    "completed": 0,
    "failed": 1,
    "running": 2,
    "missing_log": 3,
    "unknown": 4,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Track a GAMESS job from a ClearML run manifest.")
    parser.add_argument("--project-name", default="clearml-gamess-tutorial")
    parser.add_argument("--task-name", default="cml_task_track_gamess")
    parser.add_argument("--run-task-id")
    parser.add_argument("--tracking-metrics-json", type=Path)
    parser.add_argument("--tail-poll-seconds", type=float)
    parser.add_argument("--tail-timeout-seconds", type=float)
    parser.add_argument("--upload-scratch-artifact")
    return parser.parse_args()


def get_task_str_arg(args: argparse.Namespace, params: dict[str, str], name: str) -> str | None:
    value = getattr(args, name.replace("-", "_"))
    if value is not None:
        return str(value)
    return params.get(f"Args/--{name}")


def get_task_path_arg(args: argparse.Namespace, params: dict[str, str], name: str) -> Path | None:
    value = getattr(args, name.replace("-", "_"))
    if value is not None:
        return value
    param_value = params.get(f"Args/--{name}")
    return Path(param_value) if param_value else None


def get_task_float_arg(args: argparse.Namespace, params: dict[str, str], name: str, default: float) -> float:
    value = getattr(args, name.replace("-", "_"))
    if value is not None:
        return float(value)
    param_value = params.get(f"Args/--{name}")
    return float(param_value) if param_value else default


def get_task_bool_arg(args: argparse.Namespace, params: dict[str, str], name: str, default: bool) -> bool:
    value = getattr(args, name.replace("-", "_"))
    if value is not None:
        return str(value).lower() in {"1", "true", "yes", "on"}
    param_value = params.get(f"Args/--{name}")
    if param_value is None:
        return default
    return str(param_value).lower() in {"1", "true", "yes", "on"}


def upload_text_configuration(task, name: str, path: Path) -> None:
    return


def upload_text_artifact(task, name: str, path: Path, extension_name: str) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    task.upload_artifact(
        name=name,
        artifact_object=str(path),
        preview=text,
        extension_name=extension_name,
        wait_on_upload=True,
    )


def upload_file_artifact(task, name: str, path: Path) -> None:
    task.upload_artifact(name=name, artifact_object=str(path), wait_on_upload=True)


def upload_directory_artifact(task, name: str, directory: Path) -> None:
    if not directory.exists() or not directory.is_dir():
        return
    archive_base = directory.parent / directory.name
    archive_path = Path(shutil.make_archive(str(archive_base), "zip", directory))
    task.upload_artifact(name=name, artifact_object=str(archive_path), wait_on_upload=True)


def collect_matching_scratch_files(source_dir: Path, pattern: str, destination_dir: Path) -> list[Path]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    copied_paths: list[Path] = []
    for source_path in source_dir.glob(pattern):
        if not source_path.is_file():
            continue
        destination_path = destination_dir / source_path.name
        shutil.copy2(source_path, destination_path)
        copied_paths.append(destination_path)
    return copied_paths


def cleanup_matching_scratch_files(source_dir: Path, pattern: str) -> None:
    for source_path in source_dir.glob(pattern):
        if source_path.is_file():
            source_path.unlink(missing_ok=True)


def get_required_artifact(task, name: str):
    artifact = task.artifacts.get(name)
    if artifact is None:
        raise RuntimeError(
            f"Task {task.id} does not have required artifact {name!r}. "
            "It may still be queued/running, or cml_task_run_gamess.py failed before producing it."
        )
    return artifact


def is_process_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        import os

        os.kill(pid, 0)
    except OSError:
        return False
    return True


def assert_live_log_path_accessible(log_path: Path) -> None:
    parent = log_path.parent
    if not parent.exists() or not parent.is_dir():
        raise RuntimeError(
            "Live log path is not accessible from track_gamess. "
            f"Expected directory does not exist: {parent.as_posix()}. "
            "In submit_only mode, run_gamess and track_gamess must share a visible filesystem path."
        )
    if log_path.exists():
        try:
            # Validate read permission early to fail fast on sandbox boundary issues.
            with log_path.open("rb") as fp:
                fp.read(1)
        except OSError as exc:
            raise RuntimeError(
                "Live log file exists but is not readable from track_gamess: "
                f"{log_path.as_posix()}"
            ) from exc


def find_display_start_offset(log_text: str) -> int | None:
    candidates = [log_text.find(marker) for marker in DISPLAY_START_MARKERS if marker in log_text]
    if not candidates:
        return None
    return min(candidates)


def emit_log_text(log_text: str) -> None:
    for line in log_text.splitlines():
        print(line, flush=True)
    if log_text and not log_text.endswith(("\n", "\r")):
        print(flush=True)


def print_log_full_then_tail(log_path: Path, pid: int | None, poll_seconds: float, timeout_seconds: float) -> str:
    start = time.time()
    offset = 0
    header_printed = False
    display_started = False
    hidden_prefix_notice_printed = False
    termination_result: str | None = None
    termination_seen_at: float | None = None
    last_growth_at = start

    while True:
        if log_path.exists():
            log_bytes = log_path.read_bytes()
            full_text = log_bytes.decode("utf-8", errors="replace")
            if len(log_bytes) > offset:
                last_growth_at = time.time()
            if not display_started:
                display_start_offset = find_display_start_offset(full_text)
                if len(log_bytes) > 0:
                    if display_start_offset is None:
                        display_start_offset = 0
                    if not header_printed:
                        print(f"Following GAMESS log: {log_path.as_posix()}")
                        print("--- GAMESS log (initial full display) ---")
                        header_printed = True
                    visible_text = full_text[display_start_offset:]
                    emit_log_text(visible_text)
                    offset = len(log_bytes)
                    display_started = True
                elif not hidden_prefix_notice_printed:
                    print(f"Following GAMESS log: {log_path.as_posix()}")
                    print("--- waiting for GAMESS log output ---")
                    hidden_prefix_notice_printed = True
            elif len(log_bytes) > offset:
                chunk = log_bytes[offset:]
                chunk_text = chunk.decode("utf-8", errors="replace")
                emit_log_text(chunk_text)
                offset = len(log_bytes)

            if termination_result is None:
                if GAMESS_NORMAL_TERMINATION in full_text:
                    termination_result = "normal_termination"
                    termination_seen_at = time.time()
                    print("\n--- GAMESS normal termination marker found; waiting for log/process to settle ---")
                elif GAMESS_ABNORMAL_TERMINATION in full_text:
                    termination_result = "abnormal_termination"
                    termination_seen_at = time.time()
                    print("\n--- GAMESS abnormal termination marker found; waiting for log/process to settle ---")

        if pid and not is_process_alive(pid):
            if not display_started:
                print("--- process exited before any GAMESS marker was found; see gamess_log artifact for full output ---")
            print("\n--- end of tail (submitted process exited) ---")
            return termination_result or "process_exited"

        if termination_result and termination_seen_at is not None:
            quiet_for = time.time() - max(termination_seen_at, last_growth_at)
            if quiet_for >= POST_TERMINATION_QUIET_SECONDS:
                print("\n--- end of tail (termination marker observed and log was quiet) ---")
                return termination_result

        if timeout_seconds > 0 and (time.time() - start) > timeout_seconds:
            if not display_started:
                print("--- timeout reached before any GAMESS marker was found; see gamess_log artifact for full output ---")
            print("\n--- end of tail (timeout reached) ---")
            return "timeout"

        time.sleep(max(0.2, poll_seconds))


def energy_callback(context: dict[str, object], output_dir: Path) -> dict[str, object]:
    log_text = str(context["log_text"])
    values: dict[str, object] = {}

    final_rhf_energies = FINAL_RHF_ENERGY_RE.findall(log_text)
    wall_clock_times = TOTAL_WALL_CLOCK_RE.findall(log_text)
    if final_rhf_energies:
        energy = float(final_rhf_energies[-1])
        energy_text = output_dir / "energy.txt"
        energy_text.write_text(f"final_rhf_energy_hartree {energy}\n", encoding="utf-8")
        values["final_rhf_energy_hartree"] = energy
    if wall_clock_times:
        values["total_wall_clock_seconds"] = float(wall_clock_times[-1])

    return values


def main() -> None:
    args = parse_args()

    from clearml import Task

    task = Task.init(
        project_name=args.project_name,
        task_name=args.task_name,
        task_type=Task.TaskTypes.data_processing,
    )
    params = task.get_parameters()

    run_task_id = get_task_str_arg(args, params, "run-task-id")
    if not run_task_id:
        raise ValueError("--run-task-id is required")

    tail_poll_seconds = get_task_float_arg(args, params, "tail-poll-seconds", 2.0)
    tail_timeout_seconds = get_task_float_arg(args, params, "tail-timeout-seconds", 21600.0)
    upload_scratch_artifact = get_task_bool_arg(args, params, "upload-scratch-artifact", False)

    track_workspace = Path(tempfile.mkdtemp(prefix=f"{run_task_id}_track_"))
    tracking_metrics_arg = get_task_path_arg(args, params, "tracking-metrics-json")
    tracking_metrics_json = tracking_metrics_arg or track_workspace / "tracking_metrics.json"

    run_task = Task.get_task(task_id=run_task_id)
    run_manifest = Path(get_required_artifact(run_task, "gamess_run_manifest").get_local_copy()).resolve()
    run_data = json.loads(run_manifest.read_text(encoding="utf-8"))
    pid = int(run_data.get("pid")) if run_data.get("pid") is not None else None

    submit_only = bool(run_data.get("submit_only"))
    log_value = run_data.get("live_log_path") if submit_only else run_data.get("log_path")
    log_path = Path(str(log_value)).resolve() if log_value else None
    if not log_path:
        required_field = "live_log_path" if submit_only else "log_path"
        raise RuntimeError(f"run manifest is missing required field {required_field!r}.")

    if submit_only:
        # In submit_only mode we must tail the live file path, not an artifact copy.
        assert_live_log_path_accessible(log_path)
    elif not log_path.exists():
        log_path = Path(get_required_artifact(run_task, "gamess_log").get_local_copy()).resolve()

    temp_dir_path = Path(str(run_data.get("scratch_dir", ""))).resolve() if run_data.get("scratch_dir") else None
    input_path = Path(str(run_data["input_path"]))
    temp_pattern = str(run_data.get("scratch_pattern") or f"{input_path.stem}.*")

    tail_result = print_log_full_then_tail(
        log_path=log_path,
        pid=pid if submit_only else None,
        poll_seconds=tail_poll_seconds,
        timeout_seconds=tail_timeout_seconds,
    )

    if submit_only:
        run_data["observed_live_log_path"] = log_path.as_posix()
    else:
        run_data["log_path"] = log_path.as_posix()
    if tail_result == "timeout":
        run_data["observed_status"] = "running"
    local_run_manifest = track_workspace / run_manifest.name
    local_run_manifest.write_text(json.dumps(run_data, indent=2, sort_keys=True), encoding="utf-8")

    task.connect(
        {
            "run_task_id": run_task_id,
            "run_manifest_json": local_run_manifest.as_posix(),
            "observed_log_path": log_path.as_posix(),
            "tracking_metrics_json": tracking_metrics_json.as_posix(),
            "track_workspace": track_workspace.as_posix(),
        }
    )

    upload_text_artifact(task, "gamess_run_manifest", local_run_manifest, ".json")
    upload_text_configuration(task, "gamess_run_manifest_json_text", local_run_manifest)
    upload_text_artifact(task, "gamess_log", log_path, ".txt")
    upload_text_configuration(task, "gamess_log_text", log_path)
    if temp_dir_path is not None and temp_dir_path.exists() and upload_scratch_artifact and tail_result in {"normal_termination", "abnormal_termination"}:
        scratch_copy_dir = track_workspace / "gamess_temp"
        copied_scratch = collect_matching_scratch_files(temp_dir_path, temp_pattern, scratch_copy_dir)
        if copied_scratch:
            upload_directory_artifact(task, "gamess_temp", scratch_copy_dir)

    values = track_gamess(
        run_manifest_json=local_run_manifest,
        tracking_metrics_json=tracking_metrics_json,
        callbacks=[energy_callback],
    )

    logger = task.get_logger()
    gamess_status = str(values["gamess_status"])
    logger.report_scalar("gamess", "status_code", GAMESS_STATUS_CODES.get(gamess_status, 99), iteration=0)
    if "final_rhf_energy_hartree" in values:
        logger.report_scalar("gamess", "final_rhf_energy_hartree", values["final_rhf_energy_hartree"], iteration=0)
    if "total_wall_clock_seconds" in values:
        logger.report_scalar("gamess", "total_wall_clock_seconds", values["total_wall_clock_seconds"], iteration=0)

    upload_text_artifact(task, "tracking_metrics", tracking_metrics_json, ".json")
    upload_text_configuration(task, "tracking_metrics_json_text", tracking_metrics_json)
    energy_text = track_workspace / "energy.txt"
    if energy_text.exists():
        upload_text_artifact(task, "gamess_energy", energy_text, ".txt")
        upload_text_configuration(task, "gamess_energy_text", energy_text)

    if values["gamess_status"] != "completed":
        if temp_dir_path is not None and temp_dir_path.exists():
            cleanup_matching_scratch_files(temp_dir_path, temp_pattern)
        raise RuntimeError(f"GAMESS status is {values['gamess_status']}")

    if temp_dir_path is not None and temp_dir_path.exists():
        cleanup_matching_scratch_files(temp_dir_path, temp_pattern)

    task.close()


if __name__ == "__main__":
    main()
