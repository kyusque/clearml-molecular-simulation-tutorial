from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

try:
    from clearml_gamess.run_gamess import REPO_ROOT, resolve_from_repo, run_gamess, write_run_manifest_json
except ModuleNotFoundError:
    from run_gamess import REPO_ROOT, resolve_from_repo, run_gamess, write_run_manifest_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GAMESS and register ClearML artifacts.")
    parser.add_argument("--project-name", default="clearml-gamess-tutorial")
    parser.add_argument("--task-name", default="cml_task_run_gamess")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--gamess-dir", type=Path)
    parser.add_argument("--version")
    parser.add_argument("--ncpus", type=int)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--run-manifest-json", type=Path)
    parser.add_argument("--gamess-temp-dir", type=Path)
    parser.add_argument("--gamess-temp-pattern", action="append", default=[])
    parser.add_argument("--gamess-temp-file", action="append", default=[], type=Path)
    return parser.parse_args()


def get_task_path_arg(args: argparse.Namespace, params: dict[str, str], name: str) -> Path | None:
    value = getattr(args, name.replace("-", "_"))
    if value is not None:
        return value
    param_value = params.get(f"Args/--{name}")
    return Path(param_value) if param_value else None


def get_task_str_arg(args: argparse.Namespace, params: dict[str, str], name: str) -> str | None:
    value = getattr(args, name.replace("-", "_"))
    if value is not None:
        return str(value)
    return params.get(f"Args/--{name}")


def get_task_int_arg(args: argparse.Namespace, params: dict[str, str], name: str) -> int:
    value = getattr(args, name.replace("-", "_"))
    if value is not None:
        return int(value)
    param_value = params.get(f"Args/--{name}")
    return int(param_value) if param_value else 1


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


def resolve_input_path(task, input_arg: Path, run_workspace: Path) -> Path:
    input_path = resolve_from_repo(input_arg).resolve()
    if input_path.exists():
        return input_path

    artifact = task.artifacts.get("gamess_input")
    if artifact is None:
        raise FileNotFoundError(
            f"GAMESS input was not found and gamess_input artifact is missing: {input_path.as_posix()}"
        )

    artifact_path = Path(artifact.get_local_copy()).resolve()
    restored_input = run_workspace / input_arg.name
    shutil.copy2(artifact_path, restored_input)
    return restored_input


def main() -> None:
    args = parse_args()
    from clearml import Task

    task = Task.init(
        project_name=args.project_name,
        task_name=args.task_name,
        task_type=Task.TaskTypes.data_processing,
    )
    params = task.get_parameters()

    input_arg = get_task_path_arg(args, params, "input")
    if input_arg is None:
        raise ValueError("--input is required, either as a CLI argument or as ClearML parameter Args/--input")

    version = get_task_str_arg(args, params, "version") or "2023.R1.intel"
    ncpus = get_task_int_arg(args, params, "ncpus")
    run_workspace = Path(tempfile.mkdtemp(prefix=f"{input_arg.stem}_", suffix="_gamess"))
    input_path = resolve_input_path(task, input_arg, run_workspace)
    gamess_dir = (get_task_path_arg(args, params, "gamess-dir") or Path("C:/Users/Public/gamess-64")).resolve()
    log_arg = get_task_path_arg(args, params, "log")
    run_manifest_json_arg = get_task_path_arg(args, params, "run-manifest-json")
    temp_dir_arg = get_task_path_arg(args, params, "gamess-temp-dir")

    log_path = resolve_from_repo(log_arg).resolve() if log_arg else run_workspace / f"{input_path.stem}.log"
    run_manifest_json = (
        resolve_from_repo(run_manifest_json_arg).resolve()
        if run_manifest_json_arg
        else run_workspace / f"{input_path.stem}_run_manifest.json"
    )
    temp_dir = resolve_from_repo(temp_dir_arg).resolve() if temp_dir_arg else run_workspace / "gamess_temp"
    temp_files = [resolve_from_repo(path).resolve() for path in args.gamess_temp_file]

    task.connect(
        {
            "input": input_path.as_posix(),
            "gamess_dir": gamess_dir.as_posix(),
            "version": version,
            "ncpus": ncpus,
            "live_log_path": log_path.as_posix(),
            "run_manifest_json": run_manifest_json.as_posix(),
            "scratch_dir": temp_dir.as_posix(),
            "scratch_pattern": args.gamess_temp_pattern,
            "scratch_file": [path.as_posix() for path in temp_files],
            "run_workspace": run_workspace.as_posix(),
            "submit_only": True,
        }
    )
    result = run_gamess(
        input_path=input_path,
        gamess_dir=gamess_dir,
        version=version,
        ncpus=ncpus,
        log_path=log_path,
        temp_dir=temp_dir,
        temp_patterns=args.gamess_temp_pattern,
        temp_files=temp_files,
        submit_only=True,
    )
    write_run_manifest_json(result, run_manifest_json)
    upload_text_configuration(task, "gamess_run_manifest_json_text", run_manifest_json)

    logger = task.get_logger()
    return_code = int(result["return_code"])
    logger.report_scalar("process", "return_code", return_code, iteration=0)

    upload_text_artifact(task, "gamess_run_manifest", run_manifest_json, ".json")

    if return_code != 0:
        raise RuntimeError(
            "cml_task_run_gamess.py failed before cml_task_track_gamess.py could track the job: "
            f"return_code={return_code}, submission_status={result.get('submission_status')}"
        )

    task.close()
    raise SystemExit(0)


if __name__ == "__main__":
    main()
