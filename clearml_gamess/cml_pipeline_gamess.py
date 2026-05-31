from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_PACKAGES = [
    "clearml>=2.1.7",
    'impi-devel>=2021.18.0; (platform_system == "Linux" and platform_machine == "x86_64") or (platform_system == "Windows" and platform_machine == "AMD64")',
]
TASK_DIFF_PATHS = [
    "pyproject.toml",
    "clearml_gamess/*.py",
    "clearml_gamess/examples/*.py",
    "clearml_gamess/examples/gamess_test_cases/*.py",
    "tools/*.py",
]


def path_arg(path: Path | None) -> str | None:
    return path.as_posix() if path else None


def resolve_from_repo(path: Path) -> Path:
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def git_output(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def resolve_source_repository(args: argparse.Namespace) -> str:
    source_repository = getattr(args, "source_repository", None) or os.environ.get("CLEARML_TASK_REPOSITORY")
    if source_repository == "origin":
        return git_output("config", "--get", "remote.origin.url") or REPO_ROOT.as_posix()
    return source_repository or REPO_ROOT.as_posix()


def resolve_source_branch(args: argparse.Namespace) -> str:
    return getattr(args, "source_branch", None) or os.environ.get("CLEARML_TASK_BRANCH") or git_output("branch", "--show-current") or ""


def resolve_source_commit(args: argparse.Namespace) -> str:
    return getattr(args, "source_commit", None) or os.environ.get("CLEARML_TASK_COMMIT") or git_output("rev-parse", "HEAD") or ""


def resolve_source_diff(args: argparse.Namespace) -> str | None:
    if getattr(args, "_source_diff_resolved", False):
        return getattr(args, "source_diff", None)
    source_diff = getattr(args, "source_diff", None) or os.environ.get("CLEARML_TASK_DIFF")
    if source_diff is not None:
        return None if source_diff.lower() in {"", "none", "false", "0"} else source_diff
    return git_output("diff", "--binary", "HEAD", "--", *TASK_DIFF_PATHS)


def upload_text_artifact(task, name: str, path: Path, extension_name: str) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    task.upload_artifact(
        name=name,
        artifact_object=str(path),
        preview=text,
        extension_name=extension_name,
        wait_on_upload=True,
    )


def make_run_argparse_args(args: argparse.Namespace) -> list[tuple[str, str]]:
    run_args: list[tuple[str, str]] = [
        ("--project-name", args.project_name),
        ("--task-name", args.run_task_name),
        ("--input", args.input.as_posix()),
        ("--ncpus", str(args.ncpus)),
    ]
    if args.version:
        run_args.append(("--version", args.version))
    if args.gamess_dir:
        run_args.append(("--gamess-dir", args.gamess_dir.as_posix()))
    if getattr(args, "input_patch", None):
        run_args.append(("--input-patch", args.input_patch.as_posix()))
    if args.log:
        run_args.append(("--log", args.log.as_posix()))
    if args.run_manifest_json:
        run_args.append(("--run-manifest-json", args.run_manifest_json.as_posix()))
    if args.gamess_temp_dir:
        run_args.append(("--gamess-temp-dir", args.gamess_temp_dir.as_posix()))
    for pattern in args.gamess_temp_pattern:
        run_args.append(("--gamess-temp-pattern", pattern))
    for temp_file in args.gamess_temp_file:
        run_args.append(("--gamess-temp-file", temp_file.as_posix()))
    return run_args


def make_track_argparse_args(args: argparse.Namespace) -> list[tuple[str, str]]:
    return [
        ("--project-name", args.project_name),
        ("--task-name", args.track_task_name),
        ("--upload-scratch-artifact", "true" if getattr(args, "upload_scratch_artifact", False) else "false"),
    ]


def create_run_task(args: argparse.Namespace):
    from clearml import Task

    source_repository = resolve_source_repository(args)
    source_branch = resolve_source_branch(args)
    source_commit = resolve_source_commit(args)
    source_diff = resolve_source_diff(args)
    task = Task.create(
        project_name=args.project_name,
        task_name=args.run_task_name,
        task_type=Task.TaskTypes.data_processing,
        repo=source_repository,
        script="cml_task_run_gamess.py",
        working_directory="clearml_gamess",
        argparse_args=make_run_argparse_args(args),
        packages=TASK_PACKAGES,
        add_task_init_call=False,
    )
    task.set_script(
        repository=source_repository,
        branch=source_branch,
        commit=source_commit,
        diff=source_diff,
        working_dir="clearml_gamess",
        entry_point="cml_task_run_gamess.py",
    )
    upload_text_artifact(task, "pipeline_input", resolve_from_repo(args.input), ".txt")
    if getattr(args, "input_patch", None):
        upload_text_artifact(task, "pipeline_input_patch", resolve_from_repo(args.input_patch), ".patch")
    return task


def create_track_task(args: argparse.Namespace):
    from clearml import Task

    source_repository = resolve_source_repository(args)
    source_branch = resolve_source_branch(args)
    source_commit = resolve_source_commit(args)
    source_diff = resolve_source_diff(args)
    task = Task.create(
        project_name=args.project_name,
        task_name=args.track_task_name,
        task_type=Task.TaskTypes.data_processing,
        repo=source_repository,
        script="cml_task_track_gamess.py",
        working_directory="clearml_gamess",
        argparse_args=make_track_argparse_args(args),
        packages=TASK_PACKAGES,
        add_task_init_call=False,
    )
    task.set_script(
        repository=source_repository,
        branch=source_branch,
        commit=source_commit,
        diff=source_diff,
        working_dir="clearml_gamess",
        entry_point="cml_task_track_gamess.py",
    )
    return task


def build_pipeline(args: argparse.Namespace):
    from clearml import PipelineController

    args.source_repository = resolve_source_repository(args)
    args.source_branch = resolve_source_branch(args)
    args.source_commit = resolve_source_commit(args)
    args.source_diff = resolve_source_diff(args)
    args._source_diff_resolved = True

    clearml_config_file = os.environ.get("CLEARML_CONFIG_FILE")
    if not clearml_config_file:
        raise RuntimeError("CLEARML_CONFIG_FILE must be set before calling build_pipeline().")
    if not Path(clearml_config_file).exists():
        raise RuntimeError(f"CLEARML_CONFIG_FILE does not exist: {clearml_config_file}")

    pipe = PipelineController(
        name=args.pipeline_name,
        project=args.project_name,
        version=args.pipeline_version,
        add_pipeline_tags=True,
        abort_on_failure=True,
        packages=TASK_PACKAGES,
    )
    if getattr(args, "controller_entry_point", None):
        source_repository = resolve_source_repository(args)
        pipe.task.set_script(
            repository=source_repository,
            branch=resolve_source_branch(args),
            commit=resolve_source_commit(args),
            diff=resolve_source_diff(args),
            working_dir=args.controller_working_dir or ".",
            entry_point=args.controller_entry_point,
        )
    pipe.set_default_execution_queue(args.default_queue)

    pipe.add_step(
        name="run_gamess",
        base_task_factory=lambda _node: create_run_task(args),
        execution_queue=args.worker_queue,
        monitor_artifacts=(
            [
                ("pipeline_input", "pipeline_input"),
                ("gamess_input", "run_gamess_input"),
                ("gamess_run_manifest", "run_gamess_manifest"),
                ("gamess_rungms", "run_gamess_rungms"),
            ]
            + ([("pipeline_input_patch", "pipeline_input_patch")] if getattr(args, "input_patch", None) else [])
        ),
        clone_base_task=True,
    )
    pipe.add_step(
        name="track_gamess",
        parents=["run_gamess"],
        base_task_factory=lambda _node: create_track_task(args),
        parameter_override={"Args/--run-task-id": "${run_gamess.id}"},
        execution_queue=args.worker_queue,
        monitor_artifacts=(
            [
                ("tracking_metrics", "track_gamess_metrics"),
                ("gamess_log", "track_gamess_log"),
            ]
            + ([("gamess_temp", "track_gamess_temp")] if getattr(args, "upload_scratch_artifact", False) else [])
        ),
        clone_base_task=True,
    )
    return pipe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Define a ClearML pipeline for a GAMESS run.")
    parser.add_argument("--project-name", default="clearml-gamess-tutorial")
    parser.add_argument("--pipeline-name")
    parser.add_argument("--pipeline-version", default="0.1.0")
    parser.add_argument("--run-task-name")
    parser.add_argument("--track-task-name")
    parser.add_argument("--source-repository")
    parser.add_argument("--source-branch")
    parser.add_argument("--source-commit")
    parser.add_argument("--controller-entry-point")
    parser.add_argument("--controller-working-dir")
    parser.add_argument("--default-queue", default="services")
    parser.add_argument("--worker-queue")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--input-patch", type=Path)
    parser.add_argument("--gamess-dir", type=Path)
    parser.add_argument("--version")
    parser.add_argument("--ncpus", type=int, default=1)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--run-manifest-json", type=Path)
    parser.add_argument("--gamess-temp-dir", type=Path)
    parser.add_argument("--gamess-temp-pattern", action="append", default=[])
    parser.add_argument("--gamess-temp-file", action="append", default=[], type=Path)
    parser.add_argument("--upload-scratch-artifact", action="store_true")
    return parser.parse_args()


def normalize_args(args: argparse.Namespace) -> argparse.Namespace:
    case_name = args.input.stem
    args.pipeline_name = args.pipeline_name or f"{case_name}.cml_pipeline_gamess"
    args.run_task_name = args.run_task_name or f"{case_name}.cml_task_run_gamess"
    args.track_task_name = args.track_task_name or f"{case_name}.cml_task_track_gamess"
    return args


def main() -> None:
    args = normalize_args(parse_args())
    pipe = build_pipeline(args)
    print(f"pipeline_name={args.pipeline_name}")
    print("Pipeline definition was created locally. Use clearml_gamess/examples/water_rhf_sto3g_opt.cml.py to start an example run.")


if __name__ == "__main__":
    main()
