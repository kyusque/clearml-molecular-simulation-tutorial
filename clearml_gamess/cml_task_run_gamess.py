from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path

try:
    from clearml_gamess.run_gamess import (
        REPO_ROOT,
        resolve_from_repo,
        run_gamess,
        write_run_manifest_json,
    )
except ModuleNotFoundError:
    from run_gamess import REPO_ROOT, resolve_from_repo, run_gamess, write_run_manifest_json


WINDOWS_DEFAULT_GAMESS_DIR = Path("C:/Users/Public/gamess-64")
WINDOWS_DEFAULT_GAMESS_DIR_TEXT = "c:/users/public/gamess-64"
WINDOWS_DEFAULT_GAMESS_VERSION = "2023.R1.intel"
GAMESS_DIR_ENV_VARS = ("CLEARML_GAMESS_DIR", "GAMESS_DIR")
GAMESS_VERSION_ENV_VARS = ("CLEARML_GAMESS_VERSION", "GAMESS_VERSION")


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


def discover_gamess_version(gamess_dir: Path) -> str | None:
    suffix = ".exe" if os.name == "nt" else ".x"
    versions: list[str] = []
    for executable in sorted(gamess_dir.glob(f"gamess.*{suffix}")):
        name = executable.name
        version = name.removeprefix("gamess.").removesuffix(suffix)
        if version:
            versions.append(version)
    return versions[0] if versions else None


def resolve_task_gamess_version(version_arg: str | None, gamess_dir: Path) -> str | None:
    if version_arg:
        if os.name != "nt" and version_arg == WINDOWS_DEFAULT_GAMESS_VERSION:
            discovered_version = discover_gamess_version(gamess_dir)
            return discovered_version
        return version_arg
    for env_name in GAMESS_VERSION_ENV_VARS:
        env_value = os.environ.get(env_name)
        if env_value:
            return env_value
    if os.name == "nt":
        return WINDOWS_DEFAULT_GAMESS_VERSION
    return discover_gamess_version(gamess_dir)


def find_gamess_dir() -> Path:
    for env_name in GAMESS_DIR_ENV_VARS:
        env_value = os.environ.get(env_name)
        if env_value:
            gamess_dir = Path(env_value).expanduser()
            if (gamess_dir / ("rungms.bat" if os.name == "nt" else "rungms")).exists():
                return gamess_dir
            raise FileNotFoundError(
                f"{env_name} is set but rungms was not found under GAMESS directory: {gamess_dir}"
            )

    if os.name == "nt":
        if (WINDOWS_DEFAULT_GAMESS_DIR / "rungms.bat").exists():
            return WINDOWS_DEFAULT_GAMESS_DIR
        raise FileNotFoundError(
            "GAMESS directory was not specified and the default Windows installation was not found: "
            f"{WINDOWS_DEFAULT_GAMESS_DIR.as_posix()}"
        )

    rungms_path = shutil.which("rungms")
    if rungms_path:
        return Path(rungms_path).resolve().parent

    raise FileNotFoundError(
        "GAMESS directory was not specified and rungms was not found on PATH. "
        "Set CLEARML_GAMESS_DIR or GAMESS_DIR on the agent, or add rungms to PATH."
    )


def normalize_path_text(path: Path) -> str:
    return str(path).replace("\\", "/").rstrip("/").lower()


def looks_like_windows_drive_path(path: Path) -> bool:
    text = str(path)
    return len(text) >= 2 and text[1] == ":"


def resolve_task_gamess_dir(gamess_dir_arg: Path | None) -> Path:
    if gamess_dir_arg is None:
        return find_gamess_dir().resolve()
    if os.name != "nt" and normalize_path_text(gamess_dir_arg) == WINDOWS_DEFAULT_GAMESS_DIR_TEXT:
        return find_gamess_dir().resolve()
    if os.name != "nt" and looks_like_windows_drive_path(gamess_dir_arg):
        raise ValueError(
            "A Windows GAMESS path was passed to a non-Windows agent: "
            f"{gamess_dir_arg}. Set GAMESS_DIR to None to let cml_task_run_gamess.py find rungms on PATH, "
            "or pass a GAMESS directory that exists on this agent."
        )
    return resolve_from_repo(gamess_dir_arg).resolve()


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

    ncpus = get_task_int_arg(args, params, "ncpus")
    run_workspace = Path(tempfile.mkdtemp(prefix=f"{input_arg.stem}_", suffix="_gamess"))
    input_path = resolve_input_path(task, input_arg, run_workspace)
    gamess_dir = resolve_task_gamess_dir(get_task_path_arg(args, params, "gamess-dir"))
    version = resolve_task_gamess_version(get_task_str_arg(args, params, "version"), gamess_dir)
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
    rungms_path = Path(str(result.get("rungms_path", "")))
    if rungms_path.exists():
        upload_text_artifact(task, "gamess_rungms", rungms_path, ".txt")
    if log_path.exists():
        upload_text_artifact(task, "gamess_log", log_path, ".txt")

    if return_code != 0:
        startup_log_tail = result.get("startup_log_tail")
        if startup_log_tail:
            print("--- GAMESS startup log tail ---", flush=True)
            print(str(startup_log_tail), flush=True)
        raise RuntimeError(
            "cml_task_run_gamess.py failed before cml_task_track_gamess.py could track the job: "
            f"return_code={return_code}, submission_status={result.get('submission_status')}, "
            f"log_path={log_path.as_posix()}"
        )

    task.close()
    raise SystemExit(0)


if __name__ == "__main__":
    main()
