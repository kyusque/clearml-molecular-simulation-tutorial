# ClearML Molecular Simulation Tutorial

[日本語版](README-ja.md)

Running GAMESS calculations tends to create these familiar problems:

- You cannot tell at a glance when a running job will finish
- Log files and input files from past calculations are scattered and hard to find later
- Comparing results across multiple runs requires manual bookkeeping
- You want an LLM agent to handle the full calculation cycle — job submission, I/O management, and dataset management — but no existing tool has all of those APIs in one place

This tutorial shows how to use **ClearML** to solve these problems. ClearML brings job submission, input/output management, and dataset management APIs together in one platform, so the same interface works whether a human is running calculations manually or an LLM agent is automating the workflow. When you submit a calculation, the input file, log, and extracted values such as energy are recorded automatically and accessible from a web browser or API at any time.

## Quick Start

### What you need

- **A ClearML account** — free at [app.clear.ml](https://app.clear.ml/) ([self-hosting](https://github.com/clearml/clearml-server) is also supported)
- **A Windows PC with GAMESS installed** — see [clearml_gamess/README.md](clearml_gamess/README.md) for GAMESS setup
- **uv** — a Python package manager (installed in step 4)

### Steps

#### 1. Get ClearML API credentials

Sign up at [app.clear.ml](https://app.clear.ml/) and generate credentials from **Settings → Workspace → Create new credentials**.

#### 2. Clone this repository

```bash
git clone https://github.com/kyusque/clearml-molecular-simulation-tutorial.git
cd clearml-molecular-simulation-tutorial
```

#### 3. Configure credentials

Copy `local/clearml.conf.example` to `local/clearml.conf` and fill in the API credentials from step 1.

#### 4. Install uv

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

On macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 5. Start a ClearML Agent

ClearML Agent is the process that receives calculation jobs from ClearML and runs GAMESS.

```powershell
uv run tools/start_clearml_agent.py --queue default --create-queue --cpu-only
```

#### 6. Submit the sample calculation

In another terminal:

```powershell
uv run clearml_gamess/examples/water_rhf_sto3g_opt.cml.py
```

Open [app.clear.ml](https://app.clear.ml/) — the calculation appears as a Task and the Agent starts running it. After completion, the log and energy metrics are visible from the web UI.

## How it works

Three components work together:

| Component | Role |
| --- | --- |
| **This PC (submission side)** | Runs `.cml.py` scripts that register a GAMESS calculation in ClearML and push it to a queue |
| **ClearML Agent** | Watches the queue, pulls calculation Tasks, and runs GAMESS |
| **ClearML Server (app.clear.ml)** | Manages Tasks, logs, and artifacts; provides the web UI |

The flow from submission to completion:

1. Run `.cml.py` → the input file is stored as an artifact and the Task is queued
2. Agent picks up the Task → runs GAMESS and streams the log in real time
3. Calculation finishes → log, extracted values such as energy, and optionally scratch/temp files are stored as artifacts
4. If GAMESS terminates abnormally → the Task is marked failed and visible in the web UI

For a small setup, all three roles can run on the same machine. To offload computation to a dedicated machine, start the Agent there instead. ClearML Server can also be self-hosted instead of using the app.clear.ml SaaS.

## Running your own calculation

The convention in this repository is to place a `.cml.py` submission script beside each input file:

```
clearml_gamess/examples/
  water_rhf_sto3g_opt.inp        ← GAMESS input file
  water_rhf_sto3g_opt.cml.py     ← ClearML submission script
```

To submit your own calculation:

1. Prepare a GAMESS input file (`.inp`).
2. Copy an existing `.cml.py` and edit the project name and input file path.
3. Run `uv run your_calculation.cml.py`.

Changing input files and resubmitting does not require Git. If you want to change log analysis or metrics extraction code, the diff must reach the Agent — stage new files with `git add` before submitting.

## Test cases

`clearml_gamess/examples/gamess_test_cases/` contains inputs for testing different outcomes:

| File | Description |
| --- | --- |
| `success_fast_water` | Small water molecule (completes quickly) |
| `success_long_c4h6_uhf_hessian` | C4H6 UHF Hessian (takes longer) |
| `error_fast_bad_scf` | SCF convergence failure (for testing failed Tasks) |
| `error_delayed_timlim_c28` | Time-limit termination (for testing TIMLIM errors) |

## Details

- GAMESS-specific setup (install location, `rungms` configuration): [clearml_gamess/README.md](clearml_gamess/README.md)
- Agent, Pipeline, and artifact design notes: [skills/clearml/](skills/clearml/)
