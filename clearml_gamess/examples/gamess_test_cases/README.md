# GAMESS ClearML task test cases

These inputs exercise ClearML task states around GAMESS execution.

| Case | File | Expected behavior | Source |
| --- | --- | --- | --- |
| fast success | `success_fast_water.inp` | Finishes quickly and terminates normally | local tutorial input |
| longer success | `success_long_c4h6_uhf_hessian.inp` | Runs longer than water but should terminate normally | `C:/Users/Public/gamess-64/tests/uhf/parallel/c4h6-uhf.inp` |
| fast error | `error_fast_bad_scf.inp` | Fails during input validation/setup | intentionally invalid `$CONTRL SCFTYP` |
| delayed error | `error_delayed_timlim_c28.inp` | Starts a real calculation, then fails by short `TIMLIM` | modified from `rhf/parallel/c28.inp` |

Each input has a matching `<input-file-name-without-ext>.cml.py` file beside it. Run that file to submit the corresponding ClearML pipeline.
The submitted task names put the input file name without extension first, for example `success_fast_water.cml_task_run_gamess`, so cases remain readable in the ClearML UI when names are truncated.
