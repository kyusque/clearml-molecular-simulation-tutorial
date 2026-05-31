# ClearML Molecular Simulation Tutorial

[日本語版](README-ja.md)

This repository is a tutorial for managing molecular simulation jobs with ClearML.

The current example uses GAMESS, but the pattern is intended to apply to other external simulation programs as well: pass input files as ClearML artifacts, submit the simulator on a ClearML Agent, and track the log from a separate ClearML Task.

## Scope

This is tutorial material, but the code is intended to be usable as a small starting point.

- Reusable simulator-specific code lives in directories such as `clearml_gamess/`.
- Concrete submit examples live beside their input files as `<input-file-name-without-ext>.cml.py`.
- Local operational helpers, such as ClearML Agent startup, live in `tools/`.
- Agent-facing design notes live in `skills/`.

## Layout

```text
clearml_gamess/
  README.md
  README-ja.md
  cml_pipeline_gamess.py
  cml_task_run_gamess.py
  cml_task_track_gamess.py
  run_gamess.py
  track_gamess.py
  examples/

tools/
  start_clearml_agent.py

skills/
  clearml/
    task-design/
      SKILL.md
    artifacts/
      SKILL.md
    logging/
      SKILL.md
    development-workflow/
      SKILL.md
    inspect/
      SKILL.md

local/
  clearml.conf.example

draft.md
```

## Quick Start

Prepare a ClearML server first. The easiest starting point is the hosted ClearML server: create a workspace at `app.clear.ml`, generate API credentials, and put them in `local/clearml.conf`.

Molecular simulation workflows can produce many input, log, scratch/restart, and auxiliary output files. The hosted server is convenient for a tutorial, but storage size and operations may become limiting in real use. For company-internal use with proprietary data or large calculation logs, plan on setting up a self-hosted ClearML server and/or external object storage. This repository does not yet document that setup, but a future version may add server configuration examples.

Install dependencies:

```powershell
uv sync
```

Create `local/clearml.conf` from `local/clearml.conf.example` before running ClearML commands. `local/` is for machine-specific configuration and temporary local logs. If submit logs are useful, put them under `local/logs/`, not next to `clearml.conf`.

Start a ClearML Agent:

```powershell
uv run start-clearml-agent --queue default --create-queue --cpu-only
```

Submit the GAMESS sample pipeline:

```powershell
uv run python clearml_gamess/examples/water_rhf_sto3g_opt.cml.py
```

## Users and Developers

If you only want to adjust an input file and run another calculation, Git should stay mostly in the background. Edit the `.inp` and `.cml.py`, create a new Pipeline, and the submit script will store the input as the `pipeline_input` artifact.

Git becomes important when you are changing task-wrapper code that runs on the Agent: artifact upload callbacks, log previews, scratch collection, metrics extraction, and similar behavior. For that workflow, a commit is not required for every iteration. The important part is that the intended code change appears in the Task source diff. Stage new files with `git add` before submitting.

## Details

GAMESS-specific usage and design notes are documented here:

- [clearml_gamess/README.md](clearml_gamess/README.md)
- [clearml_gamess/README-ja.md](clearml_gamess/README-ja.md)

Agent-facing design notes are here:

- [skills/clearml/task-design/SKILL.md](skills/clearml/task-design/SKILL.md)
- [skills/clearml/artifacts/SKILL.md](skills/clearml/artifacts/SKILL.md)
- [skills/clearml/logging/SKILL.md](skills/clearml/logging/SKILL.md)
- [skills/clearml/development-workflow/SKILL.md](skills/clearml/development-workflow/SKILL.md)
- [skills/clearml/inspect/SKILL.md](skills/clearml/inspect/SKILL.md)

## Basic Pattern

For each simulator, the workflow is:

1. Register the input file as a ClearML artifact.
2. Submit the simulator on a ClearML Agent.
3. Write a run manifest JSON for downstream handoff.
4. Read the run manifest JSON from a separate ClearML Task and classify completion from the log.
5. Register generated files such as logs and scratch/temp outputs as artifacts.
6. Extract useful values through callbacks and save them as `tracking_metrics`.
7. If the simulator terminated abnormally, keep the artifacts and fail the ClearML task created from the tracking entry point.

In this repository, that flow is represented as the `run_gamess` and `track_gamess` steps of a ClearML Pipeline.
