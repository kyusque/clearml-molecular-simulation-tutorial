---
name: clearml-logging
description: Design ClearML console logging and log-tail behavior for external simulator workflows, especially when large simulator logs, live files, and termination markers are involved.
---

# ClearML Logging

Use this skill when deciding what a ClearML task should print to the console and how it should follow simulator logs.

## Console Role

- ClearML console output is useful for following progress, but it is not the durable record. Upload the full simulator log as an artifact.
- Keep console output human-followable: show enough log context to understand progress and failure, but do not rely on the console as the only copy.
- If the UI or SDK truncates console output, inspect the uploaded log artifact.

## Emitting Simulator Logs

- Avoid printing huge multi-line simulator logs in one `print()` call. Emit log text line by line with flushing so ClearML Agent records useful console output.
- If tracking starts after the simulator has already finished, the first tracking read should emit the useful log body, not only the termination marker.
- If the log has a large preamble that is not useful, choose a precise display-start marker. Avoid broad markers that can match only the termination line.
- A termination marker is not necessarily the final line of the log. After seeing one, continue until the process exits or the log has been quiet for a short period.

## Live Log Tracking

- In submit-only mode, `cml_task_track_<software>.py` should follow the live log path recorded in the run manifest.
- If the live log path is not visible from tracking, fail explicitly instead of silently using an artifact copy. That is a configuration problem.
- If timeout happens before a termination marker and the process still appears alive, report a `running` status rather than pretending the run is complete.
- If the process exits without a recognized termination marker, report `unknown` or `missing_log` depending on whether a log file exists.
