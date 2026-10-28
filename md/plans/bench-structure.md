# Bench structure refactor

## Objective

I want the experiment code to be easier to navigate while retaining the current commands, experiment procedure, evidence format and numerical results. I preserve existing working-tree and staged changes, including the latest fixed-three check.

## Steps

1. Save hashes of all existing result files and offline analysis outputs before editing.
2. Move tests to `tests/bench` and put shared sample/run fixtures in one helper. Update discovery and historical verification helpers that use the current tests.
3. Move shared record parsing and identity checks to `bench/records.py`. Move process, Service tunnel and host-snapshot helpers to `bench/runtime.py`. Remove imports between scenario drivers and mutual module dependencies.
4. Move phase assessment and resource calculations from `main_protocol.py` to `analyze.py`, updating callers. Keep protocol settings and preparation in `main_protocol.py`.
5. Split `run_pilot.main` into argument parsing, metadata creation, input preservation, preparation, load and finalization helpers in the same file. Include the new record dependency in future run archives.
6. Update the setup guide, architecture and current status with verified outcomes.

## Acceptance and verification

- [x] Test discovery finds all existing tests in `tests/bench`; the full local suite passes. Meaningful regression checks cover future source archives and imports from an isolated archived run.
- [x] No scenario driver imports another driver; the bench module dependency graph has no cycles, including imports inside functions.
- [x] Offline checks, metrics, phases, resource results and assessments match the pre-change baseline for every existing run that can be read. Existing partial-run errors remain the same.
- [x] Every existing result file retains its bytes. The historical integrity and negative-test verification scripts pass.
- [x] Existing CLI help works. The launcher retains cleanup/error handling and all experiment options. Future archives contain the new executable dependency.
- [x] Documentation describes the implemented layout and records verification limits. No live cluster or inference load is needed for this refactor.

## Progress

- Planning: the original local suite passed all 153 tests in this session. External Antigravity review was rejected by automatic approval review because source disclosure to that service was not authorized; review and implementation continue locally.
- Completed: ten test modules moved to `tests/bench`; shared samples and lifecycle fixtures no longer require imports between test modules. `records.py` and `runtime.py` contain the common functions. Phase assessment/resource functions moved to `analyze.py`. `run_pilot.main` is 67 lines instead of 278; its `try/finally` still owns cleanup.

## Verified results

- `.venv/Scripts/python.exe -B -m unittest discover -s tests -t .`: all 156 tests passed in 52.844 seconds, without skips. The three added tests cover imports from isolated archives, archive-version requirements and fixed-pod log capture after a prepared load fails. The existing search test also checks the archived runtime hash.
- The temporary before/after checker compared 53 supported run analyses: collection checks, metrics, replica summaries, scaling details and main assessments/resources match. Twelve legacy/partial records still report the same missing request-event files; these are unchanged read outcomes, not twelve successful analyses. The dedicated historical verifier checks the older overhead evidence separately.
- All 1,778 pre-existing files under `results` retain their hashes. Rebuilding the 18-run main comparison with `--no-plots` produces the same 13 CSV/JSON artifacts as `results/main/series-2026-10-25-v1.1/analysis-main-2026-10-26/`.
- AST inspection includes imports inside functions: all 13 Python modules form an acyclic graph, no scenario driver imports another driver, and tests do not import other test modules. Eight existing CLI `--help` commands pass.
- `md/plans/measurement-integrity/verify.py`: 120 protected files preserved, historical aggregates match and current local documentation links resolve. `md/plans/data-collection/verify-tests.py` still catches disabled unfinished-request, observation-order and observation-gap checks in temporary copies. `git diff --check` passes.
- Local baseline snapshots and QA transcripts are retained in ignored `tmp/refactor-bench/`; they are temporary verification material, not experiment evidence.

## Limits

I did not start a cluster experiment or check current runtime readiness. Local lifecycle tests use real k6 against local HTTP fixtures and simulated Kubernetes. Archived sources and measurements remain untouched. `run_series.py` still refuses current-source hash mismatches when continuing a frozen series; this refactor does not relax that rule or migrate an old series to new executable inputs. The research milestones and next load authorization are unchanged.
