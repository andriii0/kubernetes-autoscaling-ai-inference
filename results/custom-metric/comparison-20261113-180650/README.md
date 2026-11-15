# CPU versus active-request HPA comparison

## Stopped attempt

I retained this comparison with 0/6 accepted runs. Attempt 01 CPU stopped after 404.491 of the planned 782 load seconds when the collector rejected a Prometheus evaluation time about 0.78 seconds ahead of Windows. The source scrapes remained fresh; the same time check later rejected the cleanup zero. HPA removal and backend CPU quiet passed, but full cleanup validation did not.

There were 364 client starts, 335 completions (236 successful, 99 failed), and 29 unfinished requests. The remaining five cells did not start. I do not reassess this partial run as complete or recover its missing load. Original metadata, source archive, manifest and raw records remain unchanged. My notes are in the separate `notes.md` files. The corrected collector and new comparison will have a separate version boundary and output directory.

## Original launch record

I launched this separate six-run comparison at 18:06:51 UTC (19:06 Berlin) on 13 November 2026. At the startup check, driver PID 48160 and its child launcher matched this exact output directory. Attempt 01 (CPU) had entered recovery quiet; no run had completed yet. This is a launch record, not a final result.

The fixed order is CPU / active-1, active-1 / CPU, CPU / active-1. Both arms use the same Envoy, Prometheus and Adapter stack, the 782-second 2 -> 12 -> 2 burst, 300 seconds post-load, and min 1/max 3 replicas. CPU targets 60%; request HPA targets one active client request per replica. That request threshold follows the recorded preparation selection rule, despite target 2 having better latency in its single preparation.

Each run resets and warms one copy, checks backend CPU quiet and fresh gateway zeros, collects native/gateway logs and source metric timestamps, and restores one Ready copy. The driver stops on invalid collection, input/configuration changes or failed cleanup. Service target misses are retained and do not trigger replacement runs. There are no automatic reruns or continuation after a failure.

The [manifest](manifest.json) records progress and all completed run assessments. Per-run analysis adds on-time peak successes, errors/timeouts, sampled desired/Ready replica-seconds with coverage gaps, and signal/desired/Ready timing. A final comparison summary is written only after all six runs are accepted. These are descriptive paired results; Ready does not establish a warm model and replica-seconds are not measured CPU cost.

## Verification and archive

- Preparation replay passed for both retained targets. The [preparation check](preparation-check.json) records it.
- All 248 Python tests passed in the repeat; 38 focused tests passed. The first full suite had one fixed-three fixture log-count mismatch; that unchanged test passed separately and in the full repeat. Both suite outputs are retained in `prelaunch-tests-first.txt` and `prelaunch-tests-repeat.txt`.
- The first read-only host preflight detected the local test k6 process and correctly refused admission. After tests ended, the separate saved preflight passed. Neither preflight launched inference load.
- [Preflight](preflight.json), [source hashes](source-sha256.json), [preparation code boundary](preparation-code-boundary.json), `inputs/` and `bundle/` preserve the environment and executable inputs. Collector/workload sources are unchanged since preparation; the recorded launcher/reviewer changes add comparison labels, archives and the shared comparison assessment branch.
- I reviewed and checked the change locally; external review was unavailable.

The original launch was left unattended. The driver performed the configured collection and cleanup checks and stopped on the clock error described above.

The original launch record and stdout/stderr paths are in `tmp/series-command/custom-comparison-20261113-180650-process.json` in the document-authoring workspace.
