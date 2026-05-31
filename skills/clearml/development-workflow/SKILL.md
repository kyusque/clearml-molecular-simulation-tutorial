---
name: clearml-development-workflow
description: Develop, submit, and debug ClearML Agent simulator tasks during local iteration, especially when local code diffs, foreground PipelineController processes, submit logs, and ClearML console behavior matter.
---

# ClearML Development Workflow

Use this skill when iterating on ClearML Agent tasks from a local repository.

## Before Submitting

- Match the workflow to the user level. Normal simulator users should not need to think about Git beyond running the submit example from a known checkout; they edit the input file and submit a new Pipeline. Wrapper developers need Git awareness because their local Python changes must reach the Agent.
- Stage intended code changes with `git add` before submitting tasks that should include local edits. ClearML captures repository metadata and uncommitted diffs, and unstaged edits can be missed or hard to reason about depending on how the task was created.
- A commit is not mandatory for every wrapper iteration. If the Agent can clone the base revision and the intended change is present in `script.diff`, ClearML can apply the local change remotely. This is a strong fit for tuning artifact upload callbacks, text previews, metrics extraction, and logging behavior.
- Use the local repository path as the default ClearML Task repository for same-machine Agent debugging. This keeps local iteration simple.
- The submit side must write correct `repository`, `branch`, `commit`, and `diff` metadata before enqueueing. Do not rely on the Agent to infer or repair a repository path after it receives the Task.
- Keep the roles distinct: `repository` is the clone source, such as a local path or `git remote origin`; `commit` is the base revision, usually `git rev-parse HEAD`; `diff` is the patch applied on top of that commit.
- If an Agent runs on another OS or another machine, do not store a submitter-local path such as `C:/Users/...` unless that exact path is visible from the Agent. Use an Agent-visible local path, a shared filesystem path, or a Git repository URL that the Agent can clone.
- For cross-machine execution, prefer explicit repository settings such as `CLEARML_TASK_REPOSITORY`, `CLEARML_TASK_BRANCH`, and optionally `CLEARML_TASK_COMMIT`. If the base commit is cloneable by the Agent, include a focused `git diff --binary HEAD -- <runtime-code-paths>` in the Task script diff so uncommitted local edits can be applied remotely. Stage new files first, and do not ship large docs-only diffs to worker tasks.
- If the goal is to validate a released wrapper commit, disable local source diffs with `source_diff="none"` or `CLEARML_TASK_DIFF=false`. If the goal is to iterate on wrapper code, keep source diffs enabled and inspect the Task's Execution tab to confirm the diff is present.
- Keep ClearML Task `packages` portable across Agent operating systems. If a runtime package is platform-specific, add PEP 508 environment markers instead of forcing every Agent to install it. For example, do not install `impi-devel` on macOS arm64; restrict it to platforms where the wheel exists.
- Agent startup helpers should detect worker-local simulator locations when possible and export stable environment variables such as `CLEARML_GAMESS_DIR` for task entry points. Print the resolved value at startup so worker configuration is visible in logs.
- Do not add machine-local secrets. Keep `local/clearml.conf` ignored and track only `local/clearml.conf.example`.
- Keep `local/` for machine-specific files. Put submit logs under `local/logs/` if they are useful; do not put logs next to `local/clearml.conf`.

## Submitting Pipelines

- A submit example launched with `uv run python <case>.cml.py` may stay in the foreground while the local PipelineController watches the pipeline.
- For test batches, start each submit example independently in the background, then inspect ClearML task state by task name or task id.
- On Windows, prefer:

```powershell
$stdout = "local/logs/submit_case.out.log"
$stderr = "local/logs/submit_case.err.log"
Start-Process `
  -FilePath "uv" `
  -ArgumentList @("run", "python", "clearml_gamess/examples/case.cml.py") `
  -WorkingDirectory (Resolve-Path .).Path `
  -WindowStyle Hidden `
  -RedirectStandardOutput $stdout `
  -RedirectStandardError $stderr
```

- Avoid one long foreground command that submits several pipelines in sequence. A single stuck PipelineController can block the rest.

## Inspecting During Iteration

- Poll ClearML through the SDK rather than relying only on the UI. Check the pipeline controller, the task created from `cml_task_run_<software>.py`, and the task created from `cml_task_track_<software>.py` separately.
- When a previous task is still running and blocks the queue, stop the specific task or pipeline intentionally before resubmitting. Do not stop the ClearML Agent process unless the worker itself is broken.
- If a task appears to run old code, check whether the intended files were staged before submission, whether `source_diff` was disabled, and whether the task's script diff contains the expected callback or runner change.

## Console And Artifacts

- For artifact upload, text preview, scratch upload, and metrics boundaries, refer to `skills/clearml/artifacts/SKILL.md`.
- For console logging and live log tail behavior, refer to `skills/clearml/logging/SKILL.md`.
