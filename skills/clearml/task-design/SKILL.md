---
name: clearml-task-design
description: Design, submit, debug, and inspect ClearML Agent tasks for external simulators such as GAMESS, especially when inputs, logs, JSON metadata, scratch files, and pipeline steps must survive remote agent execution.
---

# ClearML Agent Task Design

Use this skill when a ClearML task runs an external executable rather than pure Python training code.

## Task Design

- Separate the documentation and defaults by user level:
  - normal simulator users should edit the scientific input file and a small `*.cml.py` submit file, then create a new Pipeline;
  - task-wrapper developers may rely on ClearML source diffs for changes to callbacks, artifact uploads, logging, and runner logic;
  - release/reproducibility workflows should use a pushed commit or an Agent-visible repository plus a narrow, inspectable diff.
- Do not explain Git as a requirement for ordinary input-file edits. For normal users, the important contract is that `pipeline_input` is uploaded before enqueueing and generated files are uploaded by the agent-side tasks after they exist.
- Git becomes important when changing code that runs on the Agent, such as artifact-upload callbacks, text previews, scratch collection, task naming, or run/track handoff logic. In that case, committing is not always required: a cloneable base commit plus a captured `script.diff` is enough for ClearML Agent to apply the change. Stage new files or otherwise ensure the intended diff is included before submitting.
- Keep the task diff focused on runtime code. Do not include large docs-only or skill-only diffs in worker tasks unless they are intentionally part of what the Agent must execute. This follows ClearML's "track everything for forensics" idea without making simulator wrapper execution depend on unrelated documentation edits.
- ClearML version-controls the code attached to each ClearML Task, not every file involved in the user workflow. The Task source repository/commit/diff shown in the UI is the repository configured for that Task's entry point, such as this tutorial repository containing `cml_task_run_gamess.py`.
- A submit script such as `*.cml.py` is not automatically version-managed by the run/track worker Tasks when it lives outside the Task repository. It may create the Pipeline locally, but the worker Tasks still clone and run the repository recorded on those worker Tasks.
- External input repositories are not automatically cloned or versioned just because an input path points into them. Treat their files as data: upload them as `pipeline_input` and, if needed, record external provenance such as input repository URL, commit, and path in metadata or the run manifest.
- If an external repository wants to reuse task wrappers from a GitHub repository, explicitly set the worker Task repository to the wrapper repository URL/commit, and upload the external repository's input files as artifacts. Do not assume the external repository becomes the worker Task source repository.
- This external-repository pattern has been validated with an external `external_water.cml.py`: the Pipeline submit script lived in an external repository, while the run/track worker Tasks cloned the GitHub task-wrapper repository at a pinned commit. With `source_diff="none"` or `CLEARML_TASK_DIFF=false`, the worker Tasks had no local uncommitted diff and still completed from artifact-provided `pipeline_input`.
- Be careful with source diffs in this pattern. If the submit helper imports local wrapper code and source diff is enabled, local uncommitted wrapper changes can be attached to worker Tasks even though the worker repository points to GitHub. Disable source diff when validating or running a pinned released wrapper commit.
- Treat external-repository validation as an occasional integration test, not a normal smoke test. Run it when changing Task source repository resolution, `source_diff` handling, input artifact materialization, or documentation around external submit repositories. See `skills/clearml/inspect/SKILL.md` for the validation checklist.
- Treat the simulator input file as task data, not only as a local path. Before enqueueing a task, upload the base input as a pipeline-level artifact such as `pipeline_input`.
- In the agent-side task script, resolve the requested input path first. If it is missing, download `task.artifacts["pipeline_input"].get_local_copy()` and run from that copy.
- If `pipeline_input_patch` exists, apply it on the agent side before launching the simulator. Treat this as a regular unified-diff workflow (`git diff`, `git diff --no-index`, `git apply`), not as a GAMESS-specific format. Upload the materialized final input as the software-specific artifact, for example `gamess_input`.
- ClearML's built-in uncommitted source diff can carry input-file edits when the input lives in the same repository and is intentionally included in the source diff. For inputs from a different repository or outside the code repository, prefer `pipeline_input` / `pipeline_input_patch` artifacts.
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
- Treat `pipeline_input` and `pipeline_input_patch` differently from generated outputs: upload them before enqueueing so the agent can start. Generated artifacts such as final `gamess_input`, run manifests, logs, metrics, and scratch/temp archives can only be uploaded by the agent-side entry points after they exist.

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

- `cml_task_run_gamess.py` pipeline input artifacts: `pipeline_input` and optional `pipeline_input_patch`, uploaded before enqueueing.
- `cml_task_run_gamess.py` materialized simulator input artifact: `gamess_input`, uploaded after optional patch application on the agent.
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
- For remote workers where the base commit is cloneable, the submit side can pass a focused `git diff --binary HEAD -- <runtime-code-paths>` as the task script diff so the Agent applies local edits after cloning. This is especially useful while tuning artifact upload callbacks or log parsing: a full commit is not mandatory if the intended diff is captured. Stage new files before submit, and avoid including docs-only changes in worker task diffs.
- If using `Task.create`, upload the input artifact on the base task before enqueueing/cloning.
- When using `monitor_artifacts`, map source artifact names to task-scoped target names on the pipeline task (tuple form) to keep outputs grouped by task.
- Preserve the task diff when relying on uncommitted tutorial files. Clearing `script.diff` can leave the agent with only the committed repository state.
- For small input edits, prefer editing the input file and submitting a new Pipeline instead of cloning only the `cml_task_run_gamess.py` Task. A cloned run Task is detached from the original Pipeline DAG, and artifacts such as `pipeline_input` may not be present unless manually re-uploaded.
- If you must clone a run Task manually, treat it as a standalone debug run. Upload or attach the new input as `pipeline_input` first, or pass a file-server URL/path that the agent-side script explicitly knows how to download. Do not expect the original Pipeline's downstream `cml_task_track_gamess.py` step to start automatically.
- If Pipeline task caching is available in the workflow, consider it only after defining a clear cache key over all real inputs: source commit/diff, `pipeline_input`, optional `pipeline_input_patch`, simulator version, wrapper script, environment, and relevant runtime parameters. External simulators often are not referentially transparent because of scratch state, random seeds, machine-local binaries, environment variables, filesystem side effects, and wall-clock/runtime behavior, so caching can easily hide a real rerun. Prefer fresh Pipeline runs unless cache validity is explicit and inspectable.
- On Windows, avoid path separators in `entry_point`; use `working_dir="clearml_gamess"` and `entry_point="cml_task_run_gamess.py"`.

## Inspecting ClearML

For task/run inspection workflows (task state triage, console-log validation, manifest/log consistency checks, and failure expectation checks), refer to:

- `skills/clearml/inspect/SKILL.md`

## Common Failures

- Queue missing: enqueue fails with `Could not find queue named ...`; use an existing queue or start the agent with `--create-queue`.
- Agent clone failure: repository is `ssh://...` and the worker lacks credentials; use HTTPS/token/SSH setup, commit/push, or local repo path only for same-machine debugging.
- Agent cannot find input: the submit script passed a local path but no input artifact was uploaded. Upload `pipeline_input` before enqueueing and implement artifact fallback.
- Cloned run Task cannot find input: UI cloning can preserve the `Args/--input` path but omit the original `pipeline_input` artifact. This produces errors like `pipeline_input artifact is missing` and should usually be solved by submitting a new Pipeline with the edited input artifact.
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
