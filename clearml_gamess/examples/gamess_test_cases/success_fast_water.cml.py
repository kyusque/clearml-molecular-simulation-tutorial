from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from clearml_gamess.cml_pipeline_gamess import build_pipeline


PROJECT_NAME = "clearml-gamess-tutorial"
PIPELINE_NAME = "success_fast_water.cml_pipeline_gamess"
PIPELINE_VERSION = "0.1.0"
RUN_TASK_NAME = "success_fast_water.cml_task_run_gamess"
TRACK_TASK_NAME = "success_fast_water.cml_task_track_gamess"
DEFAULT_QUEUE = "default"
WORKER_QUEUE = "default"
# Repository names where the agent clones code from. "origin" means git remote origin.
# The commit is resolved separately from the current HEAD by cml_pipeline_gamess.py.
SOURCE_REPOSITORY = os.environ.get("CLEARML_TASK_REPOSITORY", "origin")
SOURCE_BRANCH = os.environ.get("CLEARML_TASK_BRANCH")
SOURCE_COMMIT = os.environ.get("CLEARML_TASK_COMMIT")

INPUT = Path("clearml_gamess/examples/gamess_test_cases/success_fast_water.inp")
# None lets cml_task_run_gamess.py resolve the GAMESS directory on the agent machine.
GAMESS_DIR: Path | None = None
GAMESS_VERSION = os.environ.get("CLEARML_GAMESS_VERSION") or os.environ.get("GAMESS_VERSION")
NCPUS = 1


def configure_clearml_config_file() -> Path:
    clearml_config_file = os.environ.get("CLEARML_CONFIG_FILE")
    if clearml_config_file:
        config_path = Path(clearml_config_file)
    else:
        # For direct execution inside this repository, default to local/clearml.conf.
        # If you reuse this file outside the repository, set CLEARML_CONFIG_FILE explicitly.
        config_path = REPO_ROOT / "local" / "clearml.conf"
        os.environ["CLEARML_CONFIG_FILE"] = config_path.as_posix()

    if not config_path.exists():
        raise RuntimeError(
            "ClearML config file was not found. "
            "For in-repo runs, create local/clearml.conf from local/clearml.conf.example. "
            "For external reuse, set CLEARML_CONFIG_FILE explicitly. "
            f"Resolved path: {config_path.as_posix()}"
        )
    print(f"CLEARML_CONFIG_FILE={config_path.as_posix()}")
    return config_path


def main() -> None:
    configure_clearml_config_file()
    args = argparse.Namespace(
        project_name=PROJECT_NAME,
        pipeline_name=PIPELINE_NAME,
        pipeline_version=PIPELINE_VERSION,
        run_task_name=RUN_TASK_NAME,
        track_task_name=TRACK_TASK_NAME,
        source_repository=SOURCE_REPOSITORY,
        source_branch=SOURCE_BRANCH,
        source_commit=SOURCE_COMMIT,
        controller_entry_point="success_fast_water.cml.py",
        controller_working_dir="clearml_gamess/examples/gamess_test_cases",
        default_queue=DEFAULT_QUEUE,
        worker_queue=WORKER_QUEUE,
        input=INPUT,
        gamess_dir=GAMESS_DIR,
        version=GAMESS_VERSION,
        ncpus=NCPUS,
        log=None,
        run_manifest_json=None,
        gamess_temp_dir=None,
        gamess_temp_pattern=[],
        gamess_temp_file=[],
        upload_scratch_artifact=True,
    )
    pipe = build_pipeline(args)
    print(f"starting_pipeline={PIPELINE_NAME}")
    pipe.start_locally(run_pipeline_steps_locally=False)


if __name__ == "__main__":
    main()
