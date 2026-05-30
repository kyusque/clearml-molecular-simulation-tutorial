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

## Design

`cml_task_run_gamess.py`:

- receives `gamess_input`; if the local path is unavailable, it downloads the artifact
- creates a temporary directory dedicated to that execution
- submits GAMESS and checks only immediate startup failures
- registers `gamess_run_manifest` as the handoff artifact for `cml_task_track_gamess.py`

In submit-only mode, `gamess_run_manifest` is not the final result of GAMESS. It is the handoff contract that lets `cml_task_track_gamess.py` start tracking. It contains values such as:

- `schema`: manifest format
- `mode`: `submit_only`
- `input_path`: input file actually used on the Agent
- `gamess_dir`, `version`, `ncpus`: execution environment
- `live_log_path`: log file followed by `cml_task_track_gamess.py`
- `scratch_dir`, `scratch_pattern`: information for collecting scratch/restart files
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
- optionally registers scratch/restart files as `gamess_temp`
- runs optional postprocessing callbacks such as energy extraction
- fails its ClearML Task after saving artifacts when GAMESS failed

Monitored artifacts aggregated on the Pipeline Task are namespaced per task (for example `pipeline_gamess_input`, `run_gamess_manifest`, `track_gamess_metrics`, `track_gamess_log`, `track_gamess_temp`).

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

The `.cml.py` file is the user-edited submit script. It should contain only execution conditions such as project name, queue, GAMESS input, GAMESS install directory, version, and CPU count.

Generated paths such as logs, run manifest JSON, metrics JSON, and scratch/temp directories should not be hard-coded by users. `cml_task_run_gamess.py` and `cml_task_track_gamess.py` create per-execution temporary directories after the queued Tasks are executed by the Agent.
