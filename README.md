# ClearML Molecular Simulation Tutorial

[日本語版](README-ja.md)

This repository is a tutorial for managing molecular simulation jobs with ClearML.

The current example uses GAMESS, but the pattern is intended to apply to other molecular simulation programs as well: pass input files as ClearML artifacts, run the program on a ClearML Agent, and track the log from a separate ClearML Task.

## Scope

This is tutorial material, but the code is intended to be usable as a small starting point.

- Reusable code for each molecular simulation program lives in directories such as `clearml_gamess/`.
- Concrete ClearML task submission scripts live beside their input files as `<input-file-name-without-ext>.cml.py`.
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
```

## Terms

| Term | Meaning | Use in this tutorial |
| --- | --- | --- |
| ClearML Server | Provides the Web UI and backend, and lets ClearML manage records for Tasks, workflows, and artifact metadata. Artifact files can live on the ClearML Server or on configured external object storage / shared filesystems. | Used as the place to inspect Tasks, Pipelines, logs, and artifacts later. |
| Task | A ClearML-managed execution unit. Code, parameters, logs, metrics, and artifacts are associated with Tasks. | The GAMESS launch Task and the GAMESS log tracking Task are separate Tasks. |
| Queue | A place where Tasks wait before execution. | Tasks created by a `.cml.py` Pipeline script are enqueued, then pulled by an Agent. |
| ClearML Agent | A process that monitors queues, pulls Tasks, fetches the recorded repository/code, prepares the execution environment, and runs the specified code. | Runs on the Agent PC and executes GAMESS from the Task it receives from a queue. |
| Pipeline | A workflow that connects multiple Tasks. | Connects the Task that launches GAMESS and the Task that tracks the log. |
| ClearML task / Pipeline submission PC | Not a separate ClearML server component. It means the machine where you run `.cml.py` to create a Pipeline and enqueue Tasks. | The PC where you run the `.cml.py` file placed beside an input file. It can be the same as, or separate from, the Agent PC. |
| Agent PC | The machine running ClearML Agent. | The PC where GAMESS is installed and where `tools/start_clearml_agent.py` is run with that machine's `local/clearml.conf`. |

For a small local test, the ClearML Server, submission PC, and Agent PC can all be the same machine.

## Quick Start

### Initial Setup

#### ClearML Server

Prepare a ClearML server so the ClearML SDK and Agent can register and retrieve Tasks, logs, and artifact metadata.

The easiest starting point is the official [ClearML hosted server](https://app.clear.ml/).

- Create a workspace.
- Generate API credentials.
- Put the API credentials in `local/clearml.conf` later.

The hosted server is convenient for tutorials and small validation runs. In company-internal use, molecular simulation workflows can produce many input, log, scratch/restart, and auxiliary output files, so consider a self-hosted ClearML server and/or external object storage for proprietary data or large calculation logs. This repository does not yet document that setup, but a future version may add server configuration examples.

#### Repository

`git clone` this repository on both the ClearML task submission PC and the Agent PC. If both roles run on the same machine, one clone is enough. The Agent PC needs a clone so it can run `tools/start_clearml_agent.py` with that machine's `local/clearml.conf`.

```bash
git clone https://github.com/kyusque/clearml-molecular-simulation-tutorial.git
cd clearml-molecular-simulation-tutorial
```

#### ClearML Credentials

Create `local/clearml.conf` from `local/clearml.conf.example` and put the generated API credentials there. If the submission PC and Agent PC are separate machines, place the config in `local/clearml.conf` under each clone.

`local/` is for machine-specific configuration and temporary local logs. If submit logs are useful, put them under `local/logs/`, not next to `clearml.conf`.

#### uv

Install `uv` on both the submission PC and the Agent PC.

If `uv` is not available, install it as follows. The Agent startup helper and ClearML task submission `.cml.py` files include PEP 723 inline script metadata, so `uv sync` is not required for the quick-start path.

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

On macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### GAMESS

Install GAMESS on the Agent PC. See [clearml_gamess/README.md](clearml_gamess/README.md) for GAMESS layout and `rungms` handling.

### Run

Start a ClearML Agent on the Agent PC:

```powershell
uv run tools/start_clearml_agent.py --queue default --create-queue --cpu-only
```

Create the GAMESS sample Pipeline and enqueue its Tasks from the ClearML task submission PC:

```powershell
uv run clearml_gamess/examples/water_rhf_sto3g_opt.cml.py
```

## Users and Developers

If you only want to adjust an input file and run another calculation, Git should stay mostly in the background. Edit the `.inp` and `.cml.py`, create a new Pipeline, and the ClearML task submission script will store the input as the `pipeline_input` artifact.

Git becomes important when you are changing task execution code that runs on the Agent: artifact registration, log previews, scratch collection, metrics extraction, and similar behavior. For that workflow, a commit is not required for every iteration. The important part is that the intended code change appears in the Task source diff. Stage new files with `git add` before submitting.

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

For each molecular simulation program, the workflow is:

1. Register the input file as a ClearML artifact.
2. Run the molecular simulation program on a ClearML Agent.
3. Write a run manifest JSON for downstream handoff.
4. Read the run manifest JSON from a separate ClearML Task and classify completion from the log.
5. Register generated files such as logs and scratch/temp outputs as artifacts.
6. Extract useful values, such as energy, during the tracking step and save them as `tracking_metrics`.
7. If the molecular simulation program terminated abnormally, keep the artifacts and fail the ClearML task created from the tracking entry point.

In this repository, that flow is represented as the `run_gamess` and `track_gamess` steps of a ClearML Pipeline.
