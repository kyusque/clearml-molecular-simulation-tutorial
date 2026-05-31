# clearml_gamess

[日本語版](README-ja.md)

`clearml_gamess/` contains reusable code for running and tracking GAMESS calculations with ClearML Task / Pipeline.

- `run_gamess.py`: submits a GAMESS job and writes a run manifest JSON
- `track_gamess.py`: follows and classifies the GAMESS log, and writes extracted values to `tracking_metrics`
- `cml_task_run_gamess.py`: Task definition used by the pipeline `run_gamess` step (executed on ClearML Agent)
- `cml_task_track_gamess.py`: Task definition used by the pipeline `track_gamess` step (executed on ClearML Agent)
- `cml_pipeline_gamess.py`: ClearML Pipeline definition with `run_gamess` and `track_gamess` steps
- `examples/`: `.inp` files and matching `<input-file-name-without-ext>.cml.py` submit examples

`CLEARML_CONFIG_FILE` must be set before calling `build_pipeline()`. If it is missing, pipeline construction fails immediately.

## Code Used by the Agent

By default, `cml_pipeline_gamess.py` uses this repository's local path as the ClearML Task `repository`. This is the most direct mode when the PipelineController and ClearML Agent run on the same machine during development.

The submit side resolves `repository`, `branch`, `commit`, and the uncommitted diff before creating ClearML Tasks. `repository` is the location the Agent clones from, not a commit name such as `HEAD`. The `.cml.py` files in `examples/` default to `SOURCE_REPOSITORY="origin"`, which means `git remote origin`; the commit is resolved separately with `git rev-parse HEAD`. Override the clone source with `CLEARML_TASK_REPOSITORY` when needed. The branch can be selected with `CLEARML_TASK_BRANCH`. To pin a specific commit, use `CLEARML_TASK_COMMIT`.

If a Task is created on Windows and executed by a macOS Agent, the Windows path `C:/Users/...` is not visible from macOS. In that case, explicitly pass the local repository path on the macOS machine, a shared filesystem path, or a Git remote. `cml_pipeline_gamess.py` passes `git diff --binary HEAD` for the Python code needed at runtime, so the Agent can apply uncommitted changes as long as it can clone the base commit. Stage new files with `git add` before submitting.

Git matters most for people editing Python code that runs on the Agent: artifact upload callbacks, text previews, scratch collection, metrics extraction, and the JSON handoff between run and track tasks. A commit is not required for every iteration. If the Agent can clone the base commit and the intended change is included in the ClearML Task source diff, the Agent can apply that local diff remotely. New files may need `git add` before they appear in the diff.

For users who only want to adjust a GAMESS input and submit another calculation, Git should not be the main workflow. Edit the `.inp` and `.cml.py`, create a new Pipeline, and let the submit script upload the input as the `pipeline_input` artifact. ClearML's best-practice idea of keeping uncommitted changes for later forensics is useful here mainly for wrapper and callback development, not as a requirement for ordinary input-file edits.

## GAMESS Installation

This repository does not include GAMESS itself. Install GAMESS on the machine where the ClearML Agent runs.

When `GAMESS_DIR` is not set, `cml_task_run_gamess.py` resolves the GAMESS location. On Windows, it uses `C:/Users/Public/gamess-64`. On macOS/Linux, it looks for `rungms` on `PATH` and treats its parent directory as the GAMESS directory.

If `rungms` is not on `PATH` on macOS/Linux, set `CLEARML_GAMESS_DIR` or `GAMESS_DIR` in the environment used to start the Agent. `cml_task_run_gamess.py` checks these environment variables first and verifies that `rungms` exists under the configured directory.

When the Agent is started with this repository's `tools/start_clearml_agent.py`, the helper looks for `rungms` at startup and passes the detected directory to the Agent process as `CLEARML_GAMESS_DIR`. If `CLEARML_GAMESS_VERSION` is not set, it also infers a version from `gamess.*.x` or `gamess.*.exe` in the GAMESS directory.

On macOS/Linux, `rungms` usually receives an input name without the `.inp` extension and reads that input from the current working directory. This wrapper therefore does not copy inputs into the GAMESS installation directory. It copies the input file into the agent-side per-run temporary workspace, runs `rungms <stem>` from that workspace, and passes the GAMESS installation directory through `GMSPATH` and `GAMESS_DIR` for helper-file lookup.

Some `rungms` scripts use GNU-style `readlink -f`. macOS' built-in `readlink` does not support `-f`, so this wrapper creates a small compatibility shim in the per-run workspace and prepends it to `PATH` before launching `rungms`. If the Agent environment already has `GMSPATH`, the task-side GAMESS directory resolution takes precedence.

If the `rungms` script has a hard-coded `GMSPATH`, the wrapper does not edit the GAMESS installation in place. It copies `rungms` into the per-run workspace and patches only that temporary copy to point at the task-resolved GAMESS directory.

On Windows, the wrapper expects at least these files under that directory:

- `rungms.bat`
- `gamess.<version>.exe`

The default Windows configuration uses `version="2023.R1.intel"` and looks for `C:/Users/Public/gamess-64/gamess.2023.R1.intel.exe`. On macOS/Linux, if no version is specified, the wrapper infers one from `gamess.*.x` in the GAMESS directory. To use another version, set `CLEARML_GAMESS_VERSION` or `GAMESS_VERSION` in the Agent environment.

The Python environment includes `impi-devel` on Windows and Linux x86_64. In this wrapper, Intel MPI runtime libraries required by GAMESS are expected to come from the Python environment through `impi-devel` / `impi-rt`. `run_gamess.py` adds the virtual environment's `Library/bin` directory to `PATH` before launching GAMESS so the MPI DLLs are visible.

If you copy the GAMESS installation directory elsewhere and run from that copy, the required Intel MPI runtime still has to be visible on `PATH`. Windows/Linux x86_64 can use `impi-devel`, but macOS arm64 cannot install `impi-devel` from pip, so the ClearML Task requirements exclude it with platform markers. `impi-devel` does not replace the GAMESS installation, but in this Windows tutorial it is treated as a runtime dependency for launching GAMESS.

## Design

`cml_task_run_gamess.py`:

- receives `pipeline_input`; if the local path is unavailable, it downloads the artifact
- applies `pipeline_input_patch` on the Agent when that artifact is present
- registers the exact input passed to GAMESS as `gamess_input`
- creates a temporary directory dedicated to that execution
- submits GAMESS and checks only immediate startup failures
- registers `gamess_run_manifest` as the handoff artifact for `cml_task_track_gamess.py`
- registers the exact launched `rungms` or `rungms.bat` as `gamess_rungms`

`pipeline_input_patch` is expected to be a unified diff, for example one produced by `git diff` or `git diff --no-index`. The agent-side task materializes `pipeline_input` in a temporary directory and applies the patch with `git apply`. If the input file lives in this repository and its edits are part of the same uncommitted repository diff, ClearML's script diff mechanism can also carry those changes. For inputs from another repository or outside any repository, passing `pipeline_input` and `pipeline_input_patch` as artifacts is more explicit and portable.

Even when an external repository uses this Task wrapper, the run/track Task source code cloned by ClearML is the repository configured on those Tasks. Input files from the external repository are not cloned automatically; they are treated as `pipeline_input` artifacts.

In submit-only mode, `gamess_run_manifest` is not the final result of GAMESS. It is the handoff contract that lets `cml_task_track_gamess.py` start tracking. It contains values such as:

- `schema`: manifest format
- `mode`: `submit_only`
- `input_path`: input file actually used on the Agent
- `gamess_dir`, `version`, `ncpus`: execution environment
- `live_log_path`: log file followed by `cml_task_track_gamess.py`
- `scratch_dir`, `scratch_pattern`: information for collecting scratch/restart files
- `rungms_path`: exact launched `rungms` or `rungms.bat`
- `submission_status`: `submitted`, `submit_failed`, or `startup_failed`
- `pid`, `submitted_at`: submitted process information

At this point the GAMESS calculation is not finished, so the manifest does not contain `gamess_termination`. It also does not contain ClearML bookkeeping fields such as `artifact_names`.

`cml_task_track_gamess.py`:

- downloads `gamess_run_manifest` from the Task created from `cml_task_run_gamess.py`
- prints the full log on first read, then tails appended log content
- resolves the GAMESS log from the manifest
- in submit-only mode, fail immediately if the live log path is not visible/readable from tracking (no artifact-copy fallback)
- reads the GAMESS termination message and classifies the calculation status
- writes the result to `tracking_metrics` and registers it as an artifact
- registers `gamess_log` as a text-preview artifact
- optionally reads the GAMESS log to locate scratch/restart directories and registers matching files as `gamess_temp`
- runs optional postprocessing callbacks such as energy extraction
- fails its ClearML Task after saving artifacts when GAMESS failed

Monitored artifacts aggregated on the Pipeline Task are namespaced per task (for example `pipeline_input`, `pipeline_input_patch`, `run_gamess_input`, `run_gamess_manifest`, `run_gamess_rungms`, `track_gamess_metrics`, `track_gamess_log`, `track_gamess_temp`).

Termination markers:

- `EXECUTION OF GAMESS TERMINATED NORMALLY`: normal completion
- `EXECUTION OF GAMESS TERMINATED -ABNORMALLY-`: abnormal completion

`tracking_metrics` contains only tracking results, mainly `return_code` and `gamess_status`. `gamess_status` is one of `completed`, `failed`, `running`, `missing_log`, or `unknown`. Provenance information such as input paths, log paths, and the GAMESS version belongs in `gamess_run_manifest`.

## Naming

ClearML UI truncates long Task names, so put the input file name without extension first:

- `<input-file-name-without-ext>.cml_pipeline_gamess`
- `<input-file-name-without-ext>.cml_task_run_gamess`
- `<input-file-name-without-ext>.cml_task_track_gamess`

Example:

```text
success_fast_water.cml_task_run_gamess
success_fast_water.cml_task_track_gamess
```

Use ClearML Task type `data_processing`, not `training`. A GAMESS run is an external program execution, not ML training.

## Examples

```text
examples/
  gamess_test_cases/
    success_fast_water.inp
    success_fast_water.cml.py
```

The `.cml.py` file is the user-edited submit script. It should contain only execution conditions such as project name, queue, GAMESS input, optional GAMESS install directory, version, and CPU count.

Generated paths such as logs, run manifest JSON, metrics JSON, and scratch/temp directories should not be hard-coded by users. `cml_task_run_gamess.py` and `cml_task_track_gamess.py` create per-execution temporary directories after the queued Tasks are executed by the Agent.
