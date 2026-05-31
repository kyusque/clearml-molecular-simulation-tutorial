---
name: clearml-inspect
description: Inspect and triage ClearML run/track/pipeline tasks, validate log tail behavior, and verify expected failed/completed task states for simulator workflows.
---

# ClearML Inspect

Use this skill when you need to verify ClearML task state transitions, inspect artifacts/logs, and confirm that failure conditions are reflected correctly in task and pipeline statuses.

## Inspect Order

Use small Python snippets with `CLEARML_CONFIG_FILE` set. Prefer the SDK over guessing from UI state.

Recommended inspect order for flaky runs:

1. Inspect the `cml_task_run_gamess.py` task status, reason, script metadata, and parameters.
2. Verify required artifacts exist in the right place: `gamess_run_manifest` on the task created from `cml_task_run_gamess.py`, and `gamess_log` / `tracking_metrics` on the task created from `cml_task_track_gamess.py`.
3. Read the run manifest and compare its `live_log_path` or `log_path` with what the tracking step actually opened.
4. Read both task console outputs to confirm whether tailing started, timed out, or failed fast on path visibility.
5. Confirm final task states for the two step tasks and the pipeline controller match expectations.
6. Verify pipeline-level monitored artifacts are task-scoped (for example `pipeline_input`, `pipeline_input_patch`, `run_gamess_input`, `run_gamess_manifest`, `track_gamess_metrics`, `track_gamess_log`, `track_gamess_temp`).

```python
from clearml import Task

task = Task.get_task(task_id="TASK_ID")
print(task.get_status(), task.data.status_reason, task.get_status_message())
print(task.data.script.repository, task.data.script.working_dir, task.data.script.entry_point)
print(task.get_parameters())
print(list(task.artifacts.keys()))
print(task.get_reported_console_output(number_of_reports=1)[0])
```

To inspect run + track together:

```python
from clearml import Task

run_task = Task.get_task(task_id="RUN_TASK_ID")
track_task = Task.get_task(task_id="TRACK_TASK_ID")

print("run:", run_task.get_status(), run_task.data.status_reason)
print("track:", track_task.get_status(), track_task.data.status_reason)
print("run artifacts:", list(run_task.artifacts.keys()))
print("track artifacts:", list(track_task.artifacts.keys()))
```

For recent tasks:

```python
from clearml.backend_api.session.client import APIClient

client = APIClient()
tasks = client.tasks.get_all(name="water_rhf_sto3g_opt.cml_task_run_gamess", order_by=["-last_update"], page_size=5)
for task in tasks:
    print(task.id, task.type, task.status, task.status_reason or "", task.status_message or "")
    print(task.script.repository, task.script.working_dir, task.script.entry_point)
```

To inspect an artifact locally:

```python
from clearml import Task

task = Task.get_task(task_id="TASK_ID")
path = task.artifacts["tracking_metrics"].get_local_copy()
print(path)
```

To validate manifest/log consistency:

```python
import json
from pathlib import Path
from clearml import Task

run_task = Task.get_task(task_id="RUN_TASK_ID")
manifest_path = Path(run_task.artifacts["gamess_run_manifest"].get_local_copy())
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
print("manifest live log path:", manifest.get("live_log_path"))
print("manifest log path:", manifest.get("log_path"))
print("submit_only:", manifest.get("submit_only"), "pid:", manifest.get("pid"))
print("submission_status:", manifest.get("submission_status"))
```

If UI logs are sparse, reproduce with the agent and a local log file:

```bash
uv run clearml-agent execute --id TASK_ID --log-file local/logs/agent_TASK_ID.log --full-monitoring --cpu-only
```

## Log Reading Quality Checks

- In submit-only + tail mode, tracking must print an initial full log dump header, then appended chunks.
- If the live log path is not visible/readable from tracking, it must fail fast instead of silently switching to artifact copy.
- Treat `timeout reached` in tracking console as incomplete observation; inspect process liveness and log growth before deciding run outcome.
- When termination markers are missing, classify as `running` on tracking timeout or `unknown` after process exit, then fail tracking explicitly after uploading `tracking_metrics`.

## Failure Expectation Checks

- If submit fails immediately (`submit_failed` / non-zero return code), `cml_task_run_gamess` must be `failed` (not `completed`).
- If submit-only tracking cannot access the live log path, `cml_task_track_gamess` must fail fast and the pipeline controller must also be `failed`.
- If `gamess_status` is `failed`, `running`, `missing_log`, or `unknown`, `cml_task_track_gamess` must be `failed` after uploading `tracking_metrics`.
- If `gamess_status` is `completed`, `cml_task_track_gamess` should be `completed` and include expected artifacts (`tracking_metrics`, optional `gamess_energy`).

Status assertion snippet:

```python
from clearml import Task

def status_of(task_id: str) -> str:
    return Task.get_task(task_id=task_id).get_status()

run_status = status_of("RUN_TASK_ID")
track_status = status_of("TRACK_TASK_ID")
pipe_status = status_of("PIPELINE_TASK_ID")

print("run:", run_status)
print("track:", track_status)
print("pipeline:", pipe_status)

# Example expectations for abnormal/failed run:
assert run_status in {"failed", "completed"}
assert track_status == "failed"
assert pipe_status == "failed"
```
