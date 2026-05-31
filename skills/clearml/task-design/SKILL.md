---
name: clearml-task-design
description: Design, submit, debug, and inspect ClearML Agent tasks for external simulators such as GAMESS, especially when inputs, logs, JSON metadata, scratch files, and pipeline steps must survive remote agent execution.
---

# ClearML Agent Task Design

Use this skill when a ClearML task runs an external executable rather than pure Python training code.

## Task Design

- Treat the simulator input file as task data, not only as a local path. Before enqueueing a task, upload the input as an artifact such as `gamess_input`.
- In the agent-side task script, resolve the requested input path first. If it is missing, download `task.artifacts["gamess_input"].get_local_copy()` and run from that copy.
- Do not require users to hard-code output paths such as log, run manifest JSON, metrics JSON, or scratch/temp directories in submit examples. Let the agent-side task create a per-run workspace with `tempfile.mkdtemp()`.
- Keep user-facing submit scripts concrete only for the scientific inputs: project name, queue, input file, software directory/version, CPU count. Generated outputs belong to the simulator execution entry point such as `cml_task_run_gamess.py`.
- Resolve machine-local executables and wrapper scripts in the agent-side execution entry point, not in the submit script or pure runner helper. For example, `cml_task_run_gamess.py` may decide that Windows should use `C:/Users/Public/gamess-64` while macOS/Linux should look for `rungms` on `PATH`; `run_gamess.py` should then receive an explicit directory and only execute what it was given.
- For simulator installation paths that differ per worker, let the agent-side execution entry point read worker-local environment variables such as `CLEARML_GAMESS_DIR` or `GAMESS_DIR` before falling back to `PATH`. This keeps submit examples portable while still making the worker configuration explicit.
- Treat simulator version names as worker-local unless the submit example intentionally pins them. A Windows package version such as `2023.R1.intel` should not be blindly passed to macOS/Linux workers; let the worker environment provide `CLEARML_GAMESS_VERSION` / `GAMESS_VERSION`, or infer a version from worker-local executable names such as `gamess.*.x`.
- Respect wrapper-script working-directory assumptions. Some simulator wrappers, such as Unix `rungms`, read helper files like `gms-files.csh` relative to the current directory, so the runner may need to execute from the simulator directory. Do not copy user inputs into the simulator installation directory; stage them in a per-run workspace and pass an argument form that lets the wrapper find that staged input.
- Treat simulator wrapper portability bugs as agent-side runtime concerns. For example, some `rungms` scripts use GNU `readlink -f`, which macOS does not provide. Prefer a per-run PATH shim or equivalent local compatibility layer over editing the installed simulator directory.
- After resolving the simulator installation directory on the agent, pass that directory into the launched process environment explicitly. Do not let stale machine-level variables such as an old `GMSPATH` silently override the task-side resolution.
- If a simulator wrapper hard-codes an installation path, avoid editing the installed wrapper in place from a task. Copy the wrapper into the per-run workspace, patch the temporary copy, and record that in the run manifest/logs.
- When removing old submit-script defaults, consider stale ClearML task parameters. A previously created task may still carry values such as `Args/--gamess-dir=C:/Users/Public/gamess-64`; on macOS/Linux, treat known old Windows defaults as "not specified" or fail with a clear message instead of letting `Path("C:/...")` become a relative path under the cloned repository.
- For ClearML UI readability, put the case stem at the front of task names, such as `water_rhf_sto3g_opt.cml_task_run_gamess`, because long names are truncated from the right.
- External simulator tasks are not ML training jobs. Use a non-training task type such as `Task.TaskTypes.data_processing` for ClearML tasks created from these entry points.

## Run / Track Split

- Prefer a two-entry-point design for external simulators:
  - `cml_task_run_<software>.py`: prepares inputs, starts or runs the simulator, and writes a run manifest artifact.
  - `cml_task_track_<software>.py`: reads the manifest, follows or reads logs, decides status, uploads output artifacts, and runs callbacks.
- This split is useful beyond GAMESS. It separates "how to submit the external program" from "how to interpret what happened", which makes retries, long-running jobs, failure handling, and postprocessing easier to reason about.
- Keep `cml_task_run_<software>.py` small. It should not own scientific postprocessing, metrics design, or log interpretation unless the simulator must be run synchronously and no separate tracking phase is needed.
- Keep `cml_task_track_<software>.py` stateful enough to describe the observed simulator state. It should write a single enum-like status field in metrics, such as `gamess_status`, instead of paired booleans like `terminated_normally` and `terminated_abnormally`.
- Use user-facing status values in metrics. Prefer values like `completed`, `failed`, `running`, `missing_log`, and `unknown` over simulator-internal wording such as `normal` or `abnormal`.
- Treat the tracker status as the source of truth for downstream failure. If status is not `completed`, upload text logs and metrics first, then fail the ClearML task created from `cml_task_track_<software>.py`.

## Run Manifest Contract

- The downstream contract from `cml_task_run_<software>.py` to `cml_task_track_<software>.py` is the run manifest JSON artifact, for example `gamess_run_manifest`. It does not exist while the ClearML task is merely queued; the agent-side execution entry point creates it after it starts.
- In submit-only mode, the run manifest is a tracking handoff, not the simulator result. Include fields such as `schema`, `mode`, `input_path`, `gamess_dir`, `version`, `ncpus`, `live_log_path`, `scratch_dir`, `scratch_pattern`, `rungms_path`, `submission_status`, `pid`, and `submitted_at`. Do not include `gamess_termination` before the tracker reads the log, and do not include ClearML bookkeeping such as `artifact_names`.
- If `cml_task_run_<software>.py` fails before the tracker can start, it still owns first-failure diagnostics. Upload any startup log that exists, print a bounded tail to the console, and put a short `startup_log_tail` or equivalent field in the run manifest before raising.
- If the simulator wrapper exits during the startup window without a normal completion marker, treat that as a failed submission even when the wrapper process returns zero. Wrapper scripts can print fatal messages such as incompatible executable architecture while still exiting cleanly.
- `cml_task_track_<software>.py` should start from the run manifest, then resolve the referenced live log path or completed log artifact depending on the mode. If the manifest is missing, report that `cml_task_run_<software>.py` is still queued/running or failed before producing the manifest.
- In submit-only + track-tail mode, do not silently fall back to copied log artifacts. If the manifest log path is not visible/readable from tracking, fail fast so the pipeline fails clearly.
- Treat `gamess_input` differently from generated outputs: upload input before enqueueing so the agent can start. Generated artifacts such as run manifests, logs, metrics, and scratch/temp archives can only be uploaded by the agent-side entry points after they exist.

## Artifacts And Scratch Files

- For artifact names, text previews, metrics boundaries, and scratch/restart upload policy, refer to `skills/clearml/artifacts/SKILL.md`.
- For console output and live log tail behavior, refer to `skills/clearml/logging/SKILL.md`.
- Keep the core tracker small: it should confirm the calculation status and write `tracking_metrics`. Inject software-specific postprocessing callbacks from `cml_task_track_<software>.py`.
- Start injected postprocessing with scalar/text outputs such as energy before adding geometry formats. For GAMESS RHF, a task-side callback can parse `FINAL RHF ENERGY IS ...` and write a tiny text artifact such as `gamess_energy`.

## GAMESS Test Matrix

Keep a small set of `.inp` files that exercise task state transitions:

- fast success: tiny molecule, normal termination, useful for artifact preview and callback checks.
- longer success: heavier reference input from the GAMESS `tests` tree, useful for queue/agent runtime behavior.
- fast error: intentionally invalid input keyword, useful for setup/input-validation failure handling.
- delayed error: valid larger input with short `TIMLIM`, useful for runs that start real work and fail later.

For task/pipeline validation, check both layers:

- `cml_task_run_gamess.py` input artifact: `gamess_input`, uploaded before enqueueing.
- `cml_task_run_gamess.py` generated artifact after agent execution starts: `gamess_run_manifest` as the downstream handoff JSON.
- `cml_task_run_gamess.py` generated wrapper artifact: `gamess_rungms`, the exact launched `rungms` or `rungms.bat`.
- `cml_task_track_gamess.py` artifacts: copied/observed `gamess_run_manifest`, `gamess_log`, `tracking_metrics`, optional `gamess_temp`, and callback outputs such as `gamess_energy`.
- `tracking_metrics` should describe tracking results only, mainly `return_code` and a single status field such as `gamess_status`. Prefer one enum-like status over paired booleans. For GAMESS, use values such as `completed`, `failed`, `running`, `missing_log`, and `unknown`; keep provenance paths in `gamess_run_manifest`.
- For GAMESS, distinguish completion by log markers: `EXECUTION OF GAMESS TERMINATED NORMALLY` means normal, and `EXECUTION OF GAMESS TERMINATED -ABNORMALLY-` means abnormal.
- If the tracking entry point sees a status other than `completed`, upload `tracking_metrics` first, then fail its ClearML task so the task state reflects the simulator state.

## Pipeline Pattern

- Prefer a thin submit example beside the `.inp` file for tutorials: `<input-file-name-without-ext>.inp` and `<input-file-name-without-ext>.cml.py`.
- Require `CLEARML_CONFIG_FILE` to be set before calling `build_pipeline()`. Fail immediately if it is missing.
- For local Windows experiments, run the PipelineController locally and enqueue only the worker steps:
  `pipe.start_locally(run_pipeline_steps_locally=False)`.
- If the agent cannot clone the repo, use local repository paths only for same-machine debugging. For real remote workers, commit/push the code or configure Git credentials.
- For remote workers where the base commit is cloneable, the submit side can pass a focused `git diff --binary HEAD -- <runtime-code-paths>` as the task script diff so the Agent applies local edits after cloning. Stage new files before submit, and avoid including docs-only changes in worker task diffs.
- If using `Task.create`, upload the input artifact on the base task before enqueueing/cloning.
- When using `monitor_artifacts`, map source artifact names to task-scoped target names on the pipeline task (tuple form) to keep outputs grouped by task.
- Preserve the task diff when relying on uncommitted tutorial files. Clearing `script.diff` can leave the agent with only the committed repository state.
- On Windows, avoid path separators in `entry_point`; use `working_dir="clearml_gamess"` and `entry_point="cml_task_run_gamess.py"`.

## Inspecting ClearML

For task/run inspection workflows (task state triage, console-log validation, manifest/log consistency checks, and failure expectation checks), refer to:

- `skills/clearml/inspect/SKILL.md`

## Common Failures

- Queue missing: enqueue fails with `Could not find queue named ...`; use an existing queue or start the agent with `--create-queue`.
- Agent clone failure: repository is `ssh://...` and the worker lacks credentials; use HTTPS/token/SSH setup, commit/push, or local repo path only for same-machine debugging.
- Agent cannot find input: the submit script passed a local path but no input artifact was uploaded. Upload `gamess_input` before enqueueing and implement artifact fallback.
- Live log path not visible from tracking: in submit-only + tail mode, this should be treated as configuration error and failed explicitly so parent pipeline/task states are correct.
- Run entry point fails before tracking: upload the run manifest and any startup log first, then fail the task with return code, submission status, log path, and a concise startup log tail.
- CLI args not visible in remote execution: read `task.get_parameters()` keys like `Args/--input` as a fallback.
- Windows entry point mangling: avoid path separators in `entry_point`; use `working_dir="clearml_gamess"` and `entry_point="cml_task_run_gamess.py"`.

## GAMESS Track Callback Example

Use a task-side post-run callback shape like this for energy text output:

```python
def energy_callback(context: dict[str, object], output_dir: Path) -> dict[str, object]:
    energies = FINAL_RHF_ENERGY_RE.findall(str(context["log_text"]))
    if not energies:
        return {}
    energy = float(energies[-1])
    (output_dir / "energy.txt").write_text(
        f"final_rhf_energy_hartree {energy}\n",
        encoding="utf-8",
    )
    return {"final_rhf_energy_hartree": energy}
```

Call `track_gamess(..., callbacks=[energy_callback])` from `cml_task_track_gamess.py`, then upload `gamess_energy` from that task wrapper.
