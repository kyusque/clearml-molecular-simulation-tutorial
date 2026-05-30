---
name: clearml-development-workflow
description: Develop, submit, and debug ClearML Agent simulator tasks during local iteration, especially when local code diffs, foreground PipelineController processes, submit logs, and ClearML console behavior matter.
---

# ClearML Development Workflow

Use this skill when iterating on ClearML Agent tasks from a local repository.

## Before Submitting

- Stage intended code changes with `git add` before submitting tasks that should include local edits. ClearML captures repository metadata and uncommitted diffs, and unstaged edits can be missed or hard to reason about depending on how the task was created.
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
- If a task appears to run old code, check whether the intended files were staged before submission and inspect the task's script diff.

## Console And Artifacts

- For artifact upload, text preview, scratch upload, and metrics boundaries, refer to `skills/clearml/artifacts/SKILL.md`.
- For console logging and live log tail behavior, refer to `skills/clearml/logging/SKILL.md`.
