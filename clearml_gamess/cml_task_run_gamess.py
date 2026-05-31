from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path, PureWindowsPath

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
    parser.add_argument("--input-patch", type=Path)
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


def get_optional_artifact_path(task, name: str) -> Path | None:
    artifact = task.artifacts.get(name)
    if artifact is None:
        return None
    return Path(artifact.get_local_copy()).resolve()


def workspace_relative_path(path_arg: Path) -> Path:
    if path_arg.is_absolute() or looks_like_windows_drive_path(path_arg):
        return Path(PureWindowsPath(str(path_arg)).name)
    return path_arg


def workspace_materialized_path(path_arg: Path, run_workspace: Path) -> Path:
    return run_workspace / workspace_relative_path(path_arg)


def restore_artifact_or_local_path(task, path_arg: Path, artifact_name: str, run_workspace: Path) -> Path:
    local_path = resolve_from_repo(path_arg).resolve()
    if local_path.exists():
        return local_path

    artifact_path = get_optional_artifact_path(task, artifact_name)
    if artifact_path is None:
        raise FileNotFoundError(
            f"Required input was not found and {artifact_name} artifact is missing: {local_path.as_posix()}"
        )

    restored_path = workspace_materialized_path(path_arg, run_workspace)
    restored_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact_path, restored_path)
    return restored_path


def resolve_patch_path(task, patch_arg: Path | None, params: dict[str, str], run_workspace: Path) -> Path | None:
    if patch_arg is not None:
        return restore_artifact_or_local_path(task, patch_arg, "pipeline_input_patch", run_workspace)

    param_value = params.get("Args/--input-patch")
    if param_value:
        return restore_artifact_or_local_path(task, Path(param_value), "pipeline_input_patch", run_workspace)

    artifact_path = get_optional_artifact_path(task, "pipeline_input_patch")
    if artifact_path is not None:
        restored_path = run_workspace / artifact_path.name
        shutil.copy2(artifact_path, restored_path)
        return restored_path
    return None


def apply_input_patch(base_input: Path, input_arg: Path, patch_path: Path, run_workspace: Path) -> Path:
    patched_root = run_workspace / "patched_input"
    relative_input = workspace_relative_path(input_arg)
    staged_input = patched_root / relative_input
    staged_input.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(base_input, staged_input)

    basename_input = patched_root / input_arg.name
    if basename_input != staged_input:
        basename_input.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base_input, basename_input)

    completed = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "--recount", str(patch_path)],
        cwd=patched_root,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Failed to apply pipeline_input_patch to pipeline_input.\n"
            f"patch={patch_path.as_posix()}\n"
            f"stdout={completed.stdout}\n"
            f"stderr={completed.stderr}"
        )

    base_bytes = base_input.read_bytes()
    if staged_input.exists() and staged_input.read_bytes() != base_bytes:
        return staged_input.resolve()
    if basename_input.exists():
        return basename_input.resolve()
    if staged_input.exists():
        return staged_input.resolve()
    raise FileNotFoundError(
        "pipeline_input_patch applied, but the patched input file could not be found. "
        f"Expected {staged_input.as_posix()} or {basename_input.as_posix()}."
    )


def resolve_input_path(task, input_arg: Path, input_patch_arg: Path | None, params: dict[str, str], run_workspace: Path) -> Path:
    pipeline_input_artifact = get_optional_artifact_path(task, "pipeline_input")
    if pipeline_input_artifact is not None:
        input_path = workspace_materialized_path(input_arg, run_workspace)
        input_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pipeline_input_artifact, input_path)
        input_path = input_path.resolve()
    else:
        input_path = restore_artifact_or_local_path(task, input_arg, "pipeline_input", run_workspace)

    patch_path = resolve_patch_path(task, input_patch_arg, params, run_workspace)
    if patch_path is None:
        return input_path
    return apply_input_patch(input_path, input_arg, patch_path, run_workspace)


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
    input_patch_arg = get_task_path_arg(args, params, "input-patch")
    input_path = resolve_input_path(task, input_arg, input_patch_arg, params, run_workspace)
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
            "input_patch": input_patch_arg.as_posix() if input_patch_arg else None,
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

    upload_text_artifact(task, "gamess_input", input_path, ".txt")
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
