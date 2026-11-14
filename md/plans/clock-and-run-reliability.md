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
