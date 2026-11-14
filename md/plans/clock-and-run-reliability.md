# Clock and run reliability

I will keep the stopped 13 November series and every failed attempt. The final comparison will use a new six-run series after verification; I will not join new results to the old four.

## Work

1. Measure the Windows/guest clock boundary and inspect active time synchronizers. Do not call a passing idle check a permanent fix.
2. Use a verified monotonic k6 timer for request duration. Preserve replay of old evidence and detect clock steps in new records.
3. Hold one experiment lock through preparation, child runs and cleanup. Cover CLI and UI launch paths.
4. Reuse recorded recovery identities without treating them as a new mid-pair environment change.
5. Add paired wall/monotonic clock diagnostics and regression tests. Keep the one-second skew and ten-second freshness limits.
6. Record failure history, run relevant tests and saved-data replay, review the exact patch, and commit only this task's changes.
7. Start a fresh series only after the timing and runtime checks pass. Save the exact settings and verify real progress. Stop and report any unresolved failure.

## Acceptance

Clock-step simulations cannot silently change accepted latency. Concurrent launches are rejected. Recovery after five accepted cells works with the same recorded baseline. Old evidence is unchanged. Tests and a bounded live timing check pass. Runtime clock attribution and new-series progress are reported separately from code verification.

## Progress

Implemented the monotonic k6 runtime, paired clock bounds (including read uncertainty), shared experiment lock, recovery-baseline reuse and one fresh-series driver. New preparation is v2; comparison is v3. The stopped series is retained separately.

Verification: 288 Python tests and six browser tests passed. All four old accepted results replayed without changed assessments; 861 original non-Markdown files stayed unchanged. The new monitor passed 33 idle observations over three minutes and replayed its recorded clock intervals. See [verification](../../results/custom-metric/clock-check-20261114-final/verification.json).

Earlier full test runs exposed a fast Windows fixture boundary problem. A diagnostic captured identical periodic/final observation timestamps. The local HTTP fixture now gives simulated warmup responses and collection reads time to cross a clock tick. A 1.2-second test duration also avoids a request exactly on the one-second stop boundary. Production acceptance rules were not relaxed.

A real Windows admission probe exposed a false conflict with the driver's own venv redirector. I fixed the parent-PID/executable check; 20 affected lock/UI tests and the real no-load admission probe then passed. This focused check followed the full suite.

External review was unavailable because OpenCode could not open its log file. I did not switch provider or broaden access after that filesystem failure. The patch was reviewed locally.

The physical clock jump is unresolved. I kept both synchronizers and the existing Hyper-V clocksource unchanged. The fixes are committed as `5d50420`, and old evidence as `1dd97aa`. I started the [fresh cycle](../../results/custom-metric/series-20261114-150236/README.md) at 16:05:28 Berlin on 14 November through an independent one-time Windows task. Target 1 passed collection, scaling qualification and cleanup; target 2 is preparing. The six new comparison cells remain pending. Passing idle checks and one preparation do not guarantee that the full cycle will finish. The new code and launch are also recorded in Notion.


## Restart after identifying the competing synchronizer

The 16:05 cycle stopped at 16:38 Berlin during target-2 preparation; zero comparison cells were accepted. I matched the four clock failures to Ubuntu systemd-timesyncd initial synchronizations. Windows reported Local CMOS Clock without successful external synchronization.

I will start a separate cycle under a temporary, recorded environment change: keep Ubuntu alive and mask systemd-timesyncd only in /run for the duration. Docker/WSL's existing host-relative synchronization remains active. The worker holds experiment ownership during the check, series and restoration; it restores Ubuntu's prior enabled/active service and ends its own keep-alive process afterward. No persistent clock configuration, clock tolerance, workload or model is changed. The later Windows process-window correction is recorded below.

Before load: verify no competing experiment; verify the runtime mask; allow 40 seconds for the existing synchronizer; pass 180 seconds of strict Monitor observations and replay. Then run new targets 1/2 and all six new cells through the existing driver. Stop on any error, with no automatic retries. A successful startup or idle check does not prove completion.

The restart record and preserved clock attribution are in [launch evidence](../../results/custom-metric/launch-20261114-191048/launch-request.json). Ninety focused timer, lock, custom-metric, comparison and UI-result tests passed before this launch. The final gate is actual preparation progress and subsequent per-cell validation, not process existence alone.

The first new pre-load check, launch-20261114-185624, stopped before any workload because its diagnostic loop slept five seconds after collection; the two accepted-receipt times were 10.368 seconds apart. Ubuntu service restoration passed. I corrected only the standalone worker to include collection time in the five-second cycle, matching the existing observer scheduler. The replacement launch-20261114-185913 subsequently stopped as recorded below; production collection and its ten-second gap bound remain unchanged.

The replacement pre-load check stopped after ten good observations because a kubectl process exited with Windows code 0xc000013a. The saved clock bounds were within 0.256 seconds and observation gaps within 5.143 seconds. No experimental load started; restoration passed. Observer.read currently launches kubectl without CREATE_NO_WINDOW, unlike the log collector. I will align this process-launch option, retain strict errors, and verify that a child launched from pythonw has no console before another fresh launch. The external source of the interruption is not established.

I hid the captured Windows commands and k6 windows, and hid any new driver console while preserving inherited console interrupt behavior. The user reported pressing Ctrl+C once while an unexpected window appeared, which is consistent with the observed interruption but does not prove the exact event. A real Windows child-process check confirms no console in Observer.read. The 154-test focused suite passed, including real k6/local-HTTP lifecycle checks. I also corrected a stale missing-k6 mock that otherwise reached the real observer after the monotonic runtime migration; the test now asserts no observer construction. The previous hung suite was stopped and is not counted as passed.

The new launch passed 36 strict idle observations over three minutes. Fresh preparation started at 20:14:37 Berlin on 14 November; target 1 reached recovery quiet with no recorded errors. The six comparison cells had not started at this snapshot. See the new series README and launch startup.json. This verifies startup only.
