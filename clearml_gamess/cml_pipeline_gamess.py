from __future__ import annotations

import argparse
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_PACKAGES = ["clearml>=2.1.7", "impi-devel>=2021.18.0"]


def path_arg(path: Path | None) -> str | None:
    return path.as_posix() if path else None


def resolve_from_repo(path: Path) -> Path:
    if path.is_absolute():
        return path
    return REPO_ROOT / path


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
        ("--gamess-dir", args.gamess_dir.as_posix()),
        ("--version", args.version),
        ("--ncpus", str(args.ncpus)),
    ]
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

    task = Task.create(
        project_name=args.project_name,
        task_name=args.run_task_name,
        task_type=Task.TaskTypes.data_processing,
        repo=REPO_ROOT.as_posix(),
        script="cml_task_run_gamess.py",
        working_directory="clearml_gamess",
        argparse_args=make_run_argparse_args(args),
        packages=TASK_PACKAGES,
        add_task_init_call=False,
    )
    task.set_script(
        repository=REPO_ROOT.as_posix(),
        branch="",
        commit="",
        working_dir="clearml_gamess",
        entry_point="cml_task_run_gamess.py",
    )
    upload_text_artifact(task, "gamess_input", resolve_from_repo(args.input), ".txt")
    return task


def create_track_task(args: argparse.Namespace):
    from clearml import Task

    task = Task.create(
        project_name=args.project_name,
        task_name=args.track_task_name,
        task_type=Task.TaskTypes.data_processing,
        repo=REPO_ROOT.as_posix(),
        script="cml_task_track_gamess.py",
        working_directory="clearml_gamess",
        argparse_args=make_track_argparse_args(args),
        packages=TASK_PACKAGES,
        add_task_init_call=False,
    )
    task.set_script(
        repository=REPO_ROOT.as_posix(),
        branch="",
        commit="",
        working_dir="clearml_gamess",
        entry_point="cml_task_track_gamess.py",
    )
    return task


def build_pipeline(args: argparse.Namespace):
    from clearml import PipelineController

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
        pipe.task.set_script(
            repository=REPO_ROOT.as_posix(),
            branch="",
            commit="",
            working_dir=args.controller_working_dir or ".",
            entry_point=args.controller_entry_point,
        )
    pipe.set_default_execution_queue(args.default_queue)

    pipe.add_step(
        name="run_gamess",
        base_task_factory=lambda _node: create_run_task(args),
        execution_queue=args.worker_queue,
        monitor_artifacts=[
            ("gamess_input", "pipeline_gamess_input"),
            ("gamess_run_manifest", "run_gamess_manifest"),
        ],
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
    parser.add_argument("--controller-entry-point")
    parser.add_argument("--controller-working-dir")
    parser.add_argument("--default-queue", default="services")
    parser.add_argument("--worker-queue")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--gamess-dir", default=Path("C:/Users/Public/gamess-64"), type=Path)
    parser.add_argument("--version", default="2023.R1.intel")
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
