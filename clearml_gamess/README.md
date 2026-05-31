# clearml_gamess

[日本語版](README-ja.md)

`clearml_gamess/` contains reusable code for running and tracking GAMESS calculations with ClearML Tasks and Pipelines.

| File | Role |
| --- | --- |
| `run_gamess.py` | Submits a GAMESS job and writes a run manifest JSON |
| `track_gamess.py` | Follows and classifies the GAMESS log; writes extracted values to `tracking_metrics` |
| `cml_task_run_gamess.py` | Task definition for the pipeline `run_gamess` step (runs on Agent) |
| `cml_task_track_gamess.py` | Task definition for the pipeline `track_gamess` step (runs on Agent) |
| `cml_pipeline_gamess.py` | Pipeline definition with `run_gamess` and `track_gamess` steps |
| `examples/` | `.inp` files and matching `.cml.py` submission examples |

## GAMESS Installation

GAMESS is not included in this repository. Install it on the machine where the ClearML Agent runs.

**Windows (recommended layout)**

Extract GAMESS to `C:/Users/Public/gamess-64` so that `rungms.bat` and `gamess.<version>.exe` are inside. `cml_task_run_gamess.py` uses this path by default.

If you install elsewhere, set `CLEARML_GAMESS_DIR` in the Agent environment. When starting the Agent with `tools/start_clearml_agent.py`, the helper searches for `rungms.bat` automatically.

**macOS/Linux**

Build GAMESS from source and make `rungms` available. When starting the Agent with `tools/start_clearml_agent.py`, if `rungms` is on `PATH` it is detected at startup and passed to the Agent as `CLEARML_GAMESS_DIR`. If it is not on `PATH`, set `CLEARML_GAMESS_DIR` manually.

## What .cml.py Does

A `.cml.py` file is the user-edited submission script. It contains only execution conditions: project name, queue, GAMESS input file, and CPU count.

Generated output paths — logs, run manifest, metrics — are not written by users. The Agent-side Tasks (`cml_task_run_gamess.py` and `cml_task_track_gamess.py`) create a per-run temporary workspace and manage those paths themselves.

## Generated Artifacts

| Artifact | What it is |
| --- | --- |
| `gamess_input` | The exact input file passed to GAMESS on the Agent |
| `gamess_run_manifest` | Handoff JSON for the track task (log path, execution environment) |
| `gamess_rungms` | The exact `rungms` or `rungms.bat` that was launched |
| `gamess_log` | GAMESS output log with text preview |
| `tracking_metrics` | Classification result (`gamess_status`, `return_code`, etc.) |
| `gamess_temp` | Scratch/restart files (when enabled) |

These are also aggregated on the Pipeline Task with `run_gamess_` and `track_gamess_` prefixes.

## Completion Detection

The log is scanned for these markers:

- `EXECUTION OF GAMESS TERMINATED NORMALLY` → `gamess_status: completed`
- `EXECUTION OF GAMESS TERMINATED -ABNORMALLY-` → `gamess_status: failed`

If neither appears, the status is `running` or `unknown`. When GAMESS fails, artifacts are saved before the tracking Task is marked failed.

## Task Naming

ClearML UI truncates long names, so the input file stem comes first:

```
water_rhf_sto3g_opt.cml_pipeline_gamess
water_rhf_sto3g_opt.cml_task_run_gamess
water_rhf_sto3g_opt.cml_task_track_gamess
```

Task type is set to `data_processing`, not `training`. GAMESS execution is external-program data processing, not ML training.

## Updating Agent Code

When changing Python code that runs on the Agent (such as `cml_task_run_gamess.py` or `cml_task_track_gamess.py`), the diff must reach the Agent.

`cml_pipeline_gamess.py` resolves `repository`, `branch`, `commit`, and the uncommitted diff (`git diff --binary HEAD`) before creating Tasks. The Agent clones that commit and applies the Task diff on top. Commits are not required on every iteration, but new files must be staged with `git add` before submitting or they may not appear in the diff.

The `.cml.py` files in `examples/` default to `SOURCE_REPOSITORY="origin"` (the `git remote origin` URL). Override with `CLEARML_TASK_REPOSITORY` to use a different source. Use `CLEARML_TASK_BRANCH` for branch selection and `CLEARML_TASK_COMMIT` to pin a specific commit.

If Tasks are created on Windows and executed by a macOS Agent, the Windows local path is not visible from macOS. In that case, pass a Git remote URL, a shared filesystem path, or the macOS local path via `CLEARML_TASK_REPOSITORY`.

## GAMESS Version and Intel MPI

**Version detection**

When starting the Agent with `tools/start_clearml_agent.py`, the helper infers the GAMESS version from `gamess.*.x` or `gamess.*.exe` in the GAMESS directory and passes it to the Agent as `CLEARML_GAMESS_VERSION`. Set `CLEARML_GAMESS_VERSION` or `GAMESS_VERSION` explicitly to use a different version.

The default Windows version is `"2023.R1.intel"`, which looks for `C:/Users/Public/gamess-64/gamess.2023.R1.intel.exe`.

**Intel MPI (Windows and Linux x86_64)**

The Python environment in this repository includes `impi-devel` for Windows and Linux x86_64 to supply the Intel MPI runtime libraries required by GAMESS. `run_gamess.py` prepends the virtual environment's `Library/bin` to `PATH` before launching GAMESS so the MPI DLLs are visible.

macOS arm64 cannot install `impi-devel` from pip, so it is excluded from requirements via platform markers. On macOS, provide Intel MPI through another means.

## Implementation Notes (macOS/Linux)

**readlink -f compatibility**

Some `rungms` scripts use GNU-style `readlink -f`. macOS's built-in `readlink` does not support `-f`, so this code creates a small compatibility shim in the per-run workspace and prepends it to `PATH` before launching `rungms`.

**Hard-coded GMSPATH in rungms**

If the `rungms` script contains a hard-coded `GMSPATH`, this code does not edit the GAMESS installation in place. It copies `rungms` into the per-run workspace and patches only that temporary copy to point at the task-resolved GAMESS directory.

**Working directory**

macOS/Linux `rungms` scripts typically receive an input name without extension and read the input from the current working directory. This code copies the input file into the per-run temporary workspace, sets that workspace as the working directory, and runs `rungms <stem>` from there.

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

`gamess_run_manifest` is not the final result of GAMESS. It is the handoff contract that lets `cml_task_track_gamess.py` start tracking. Fields include:

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
- in submit-only mode, fails immediately if the live log path is not visible/readable from tracking (no artifact-copy fallback)
- reads the GAMESS termination message and classifies the calculation status
- writes the result to `tracking_metrics` and registers it as an artifact
- registers `gamess_log` as a text-preview artifact
- optionally reads the GAMESS log to locate scratch/restart directories and registers matching files as `gamess_temp`
- runs optional callbacks, such as energy extraction, inside the tracking loop
- fails its ClearML Task after saving artifacts when GAMESS failed

`tracking_metrics` contains only tracking results, mainly `return_code` and `gamess_status`. `gamess_status` is one of `completed`, `failed`, `running`, `missing_log`, or `unknown`. Provenance information such as input paths, log paths, and the GAMESS version belongs in `gamess_run_manifest`.

The submit side resolves `repository`, `branch`, `commit`, and the uncommitted diff before creating ClearML Tasks. `repository` is the location the Agent clones from, not a commit name such as `HEAD`. The `.cml.py` files in `examples/` default to `SOURCE_REPOSITORY="origin"`, which means `git remote origin`; the commit is resolved separately with `git rev-parse HEAD`. Override the clone source with `CLEARML_TASK_REPOSITORY` when needed. The branch can be selected with `CLEARML_TASK_BRANCH`. To pin a specific commit, use `CLEARML_TASK_COMMIT`.
