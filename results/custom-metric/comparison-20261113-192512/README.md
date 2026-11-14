# CPU versus active-request HPA comparison v2

The series stopped again at 12:12:00 UTC (13:12 Berlin) on 14 November. Attempt 05 retry 04 recorded 393 started and 392 completed requests, with no summary. The clock guard failed again; the saved observation near 12:10:30 UTC shows Prometheus about 1.384 seconds ahead of the Windows receive time. Full cleanup passed. Four cells remain accepted; cell 6 never started.

I launched this fresh comparison at 19:25:13 UTC (20:25 Berlin) on 13 November. The startup snapshot confirmed launcher PID 24292 and interpreter/driver PID 42856 with this exact directory. Attempt 01 CPU was in recovery quiet, no errors were recorded, and 0/6 runs were complete. This records startup only.

The six cells are CPU / active-1, active-1 / CPU, CPU / active-1. Both use the same Envoy, Prometheus and Adapter, the 782-second 2 -> 12 -> 2 requests/10 s burst, 300 seconds post-load and one to three replicas. CPU target 60%, request target 1, model, workload and backend resources are unchanged.

The [clock correction](../clock-fix-20261113/README.md) reconciles the collector's clock allowance with preflight and saves query send/receive bounds. Source age remains limited to ten seconds in Prometheus's clock; missing/stale signals and offsets beyond one second still fail. Cleanup requires two new zero scrapes beyond its boundary plus the clock allowance. The [collector boundary](collector-fix.json), source archive and preparation-code-boundary record the exact old/new hashes.

All 254 Python tests, six browser checks, both archived preparation replays and the installed collector/cleanup check passed before launch. I retain the [earlier stopped comparison](../comparison-20261113-180650/README.md) separately. Its missing load cannot be recovered or counted as a complete cell. No raw historical file was rewritten.

The [manifest](manifest.json) records progress and accepted outcomes. A service target miss is retained; invalid collection, changed inputs or failed cleanup stops progression. I will assess the policies only after reviewing complete saved evidence. The original launch was left unattended. Failed attempts do not trigger automatic repeats.

## Continuation after a Windows client crash

The series stopped with four accepted cells after kubectl crashed during the fifth CPU run. I retained its incomplete evidence and [failure notes](attempt-05-cpu/notes.md). The [diagnostic check](resume-check-kubectl-crash-2/README.md) confirms the Windows event, healthy subsequent node reads, unchanged setup and 331 unchanged evidence files.

I verified explicit continuation with 51 focused and 263 full Python tests. Its dry run replayed cells 1-4 and left only 5-6 pending. I started continuation at 22:04:27 UTC (23:04 Berlin) on 13 November. Launcher PID 41876 and interpreter/driver PID 23464 matched this directory and `--resume --execute`. The startup snapshot confirmed `attempt-05-cpu-retry-01` in recovery quiet, four accepted cells and no new errors.

The [continuation record](resume-23464/source-boundary.json) records only driver and archive-review changes. The original source archive, failed manifest, attempt 05 and first four results remain preserved. Collector, model, workload, HPA policies and targets are unchanged. The sixth request-based cell follows the retry; neither remaining outcome is established by this startup snapshot.

## Continuation after the application interruption

The first retry stopped around 22:19 UTC on 13 November with 420 started and 419 completed requests (232 successes, 187 failures). The driver and children disappeared, stderr recorded kubectl exit code 3221225786, and Windows recorded a Codex hang in the same minute. I recovered the matching Windows Error Reporting event (1001, record 49361, `MoAppHang`) during the documentation review; it is saved in [the new event export](resume-check-app-interruption/windows-events-verified-20261114.json). The earlier `windows-events.json` contains null and is retained. The event confirms the hang at 22:19:52 UTC, but not why the driver processes ended. I retain this as a separate external interruption. See the [retry notes](attempt-05-cpu-retry-01/notes.md). Neither incomplete attempt is accepted.

I preserved the stale manifest and lock in [the recovery directory](resume-check-app-interruption/). [Independent cleanup](resume-check-app-interruption/cleanup/recovery.json) passed: HPA removed, one Ready copy, backend CPU quiet and fresh gateway zeros. The prior [prefix replay](resume-check-app-interruption/prefix-replay.json) accepted cells 1-4 and left only 5-6 pending; 17 continuation tests passed. Before this launch I rechecked all 477 protected file hashes with no changes, confirmed no Python/k6 processes, and observed no HPA, one Ready Ollama copy and three Ready metric components.

The existing task still pointed to the unsigned PowerShell worker and had last result 1. I preserved its [signing error](resume-check-app-interruption/task-signing-error.log) and replaced only its action with `.venv/Scripts/pythonw.exe` running the [Python worker](resume-check-app-interruption/task-worker.py). That worker starts the existing `.venv/Scripts/python.exe -B bench/run_custom_comparison.py` with the original preparation, this output directory and `--resume --execute`. I changed no PowerShell execution policy or task privileges.

The [task definition](resume-check-app-interruption/direct-python-task.xml) has Limited privileges, no triggers and no automatic restart. The worker runs without a console, captures stdout/stderr and exit status, and deletes its own task when it exits. The [launch record](resume-check-app-interruption/direct-python-launch.json) records 23:01:39 UTC on 13 November (00:01:39 Berlin on 14 November).

The [startup snapshot](resume-check-app-interruption/direct-python-startup.json) confirms worker PID 51220, launcher PID 31292, driver PID 37352 and pilot interpreter PID 45780, with exact commands and paths. [Process ancestry](resume-check-app-interruption/task-parent.json) reaches Windows Schedule service PID 4020. The manifest has four accepted cells and no errors; `attempt-05-cpu-retry-02` was in recovery quiet with the unchanged 782-second load and 300-second post-load settings. The driver revalidated the accepted prefix before creating this retry and saved the [previous manifest](resume-37352/manifest-before.json) and [source boundary](resume-37352/source-boundary.json).

That snapshot confirmed independent startup only. The subsequent stop is recorded below; no further cell was accepted.

## Latest stop before measured load

Attempt 05 retry 02 stopped at 23:04:55 UTC on 13 November (00:04:55 Berlin on 14 November). Its [metadata](attempt-05-cpu-retry-02/metadata.json) records a Prometheus/observer clock difference above one second. The measured load did not start, so there is no request-events file or summary. This attempt supplies no comparison result.

The task worker exited with code 1 and deleted the one-time task. The latest runtime check found no experiment processes, no HPA, one Ready Ollama copy and three Ready metric components. [Recovery](attempt-05-cpu-retry-02/recovery.json) passed backend CPU quiet but failed the fresh-zero check on the clock guard. I do not count cleanup as fully verified.

The original manifest reports the later missing `request-events.jsonl` error because the reviewer tried to load request data before reporting the failed launcher. I kept that manifest and all raw attempt files unchanged. The reviewer now reports the recorded preparation errors first and lists missing request files separately. This diagnostic correction does not change measurement or acceptance rules. Continuation still requires a healthy clock check and complete preparation/cleanup gates.

## Continuation after clock alignment recovered

The saved clock bounds changed abruptly between 23:04:01 and 23:04:06 UTC on 13 November. Prometheus was then about 1.015 seconds ahead of the Windows receive time. Live clocks were aligned again before I changed any clock setting. I could not establish the underlying host/guest trigger from the available logs. I did not change system clocks, restart the infrastructure, weaken the one-second guard or modify collectors.

Before launch, 36 idle observations over three minutes passed, followed by the existing backend CPU quiet and two fresh gateway-zero checks. All 53 focused tests passed. The accepted-prefix replay retained cells 1-4 and listed only cells 5-6. All 596 pre-existing non-Markdown series files matched their saved hashes before launch; the continuation intentionally updates the manifest and keeps its previous version in the resume directory.

I launched the existing Python worker through a new hidden, one-time Windows task at 23:41:39 UTC on 13 November (00:41:39 Berlin on 14 November). It has Limited privileges, no recurring triggers and no automatic restart. The recorded process ancestry reaches the Windows Schedule service. The worker deletes its task when it exits.

At 2026-11-13T23:47:28.942016+00:00, the continuation was running with four of six cells accepted. `attempt-05-cpu-retry-03` had reached measured CPU load: 11 requests started and 10 completed. The final active-1 cell follows only if the CPU cell passes full collection and cleanup. This snapshot confirms load startup, not either remaining result. See the [recovery and startup record](resume-check-clock-20261114/README.md).

## Stop after retry 04

The series stopped again at 12:12:00 UTC (13:12 Berlin) on 14 November. Attempt 05 retry 04 recorded 393 started and 392 completed requests, with no summary. The clock guard failed again; the saved observation near 12:10:30 UTC shows Prometheus about 1.384 seconds ahead of the Windows receive time. Full cleanup passed. Four cells remain accepted; cell 6 never started.

The Hyper-V clocksource was still selected at the subsequent runtime check, so the mitigation did not prevent recurrence. No experiment process or continuation task remained; HPA was absent and one Ollama copy was Ready. No new load was started. The cause of the clock jump remains unresolved.

The host recovery changed instance identities, the timing environment and the continuation procedure. The first four runs retain their own validated evidence, but matching images/configuration alone does not establish that a later recovered pair forms an unchanged six-cell protocol. The original frozen-configuration rule requires an explicit decision about that boundary. I must resolve it, together with the clock failure, before treating further runs as the final comparison. A fresh complete series under stable settings is the conservative option; it has not been launched.

## Decision on 14 November: keep this series separate

I will not resume this series. New preparation and a new six-cell comparison will use the revised timer and clock diagnostics. The four accepted cells and all five failed attempts remain here. The table uses UTC; a failed attempt is not a comparison result.

| CPU cell 5 attempt | Where it stopped | Recorded reason |
| --- | --- | --- |
| Original | 13 Nov, 21:19; 454 completions | Windows kubectl crash, `0xc0000409` |
| Retry 01 | 13 Nov, about 22:19; 420 starts, 419 completions | Driver disappeared; Codex hang in the same minute. Causation is unproven. |
| Retry 02 | 13 Nov, 23:04:55; no load | Clock difference about 1.015 s; fresh-zero cleanup also failed. |
| Retry 03 | 13 Nov, 23:48:56; 19 completions | Clock difference about 1.055 s during initial low load. Cleanup passed. |
| Retry 04 | 14 Nov, 12:11:59; 393 starts, 392 completions | Clock difference about 1.384 s. Cleanup passed. |

Cell 6 never started. The reporting and continuation fixes do not make incomplete attempts valid. The [new clock investigation](../clock-check-20261114-trace/README.md) separates verified code changes from the unresolved host clock cause.
