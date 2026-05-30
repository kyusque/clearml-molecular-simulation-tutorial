---
name: clearml-artifacts
description: Design ClearML artifact boundaries, names, previews, manifests, metrics, and scratch/restart uploads for external simulator workflows.
---

# ClearML Artifacts

Use this skill when deciding what to upload to ClearML and how to name or structure artifacts.

## Artifact Boundaries

- Treat simulator inputs differently from generated outputs. Upload input artifacts such as `gamess_input` before enqueueing so the agent can start without relying on the submitter's local path.
- Generated artifacts such as run manifests, logs, metrics, and scratch archives can only be uploaded by the agent-side entry points after they exist.
- Use the run manifest artifact as a handoff contract between `cml_task_run_<software>.py` and `cml_task_track_<software>.py`. Do not mix ClearML bookkeeping such as artifact name maps into the manifest.
- Keep provenance and tracking results separate:
  - Run manifest: input path, simulator directory/version, CPU count, live log path or completed log path, scratch path/pattern, submission status, pid, timestamps.
  - Tracking metrics: `return_code`, enum-like simulator status such as `gamess_status`, and extracted scalar/text results.
- Prefer user-facing status values such as `completed`, `failed`, `running`, `missing_log`, and `unknown`.

## Text Preview

- Register important text files as artifacts with `preview=` and `extension_name=` so the ClearML UI can render the body:

```python
task.upload_artifact(
    name="gamess_log",
    artifact_object=str(log_path),
    preview=log_text,
    extension_name=".txt",
    wait_on_upload=True,
)
```

- Use `.json` for run manifest and metrics JSON, and `.txt` for `.inp` / `.log` if the native extension is not previewed well.
- For especially important text, also attach a configuration text entry such as `gamess_log_text` or `tracking_metrics_json_text` if the project wants quick in-UI reading outside the artifact tab.
- The full simulator log should be a durable artifact even if console tailing is also implemented.

## Pipeline Artifact Names

- When aggregating artifacts on the Pipeline task, namespace by producing step so artifacts do not collide.
- Prefer names like:
  - `pipeline_gamess_input`
  - `run_gamess_manifest`
  - `track_gamess_log`
  - `track_gamess_metrics`
  - `track_gamess_temp`
- Avoid generic names on the Pipeline task when both run and track steps may emit related files.

## Scratch And Restart Files

- Treat scratch/restart files as optional outputs. They can be large, implementation-specific, and mostly useful for restart or debugging.
- Make scratch upload explicit, for example with `--upload-scratch-artifact`. Do not upload scratch by default unless the workflow depends on restart files.
- If scratch upload is enabled, collect only files that match the current case pattern, copy them into a per-task directory, and upload that directory as a zipped artifact such as `gamess_temp`.
- Clean up scratch files after tracking has uploaded the useful subset. This avoids stale restart files being picked up by later runs.
- Do not create a separate extract task unless there is a separate user workflow. In the common case, scratch collection belongs to `cml_task_track_<software>.py`.
